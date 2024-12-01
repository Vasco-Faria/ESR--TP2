
import socket, json, threading, sys
from queue import Queue
from oPop import oPop
from NetworkFunctions import getSelfIP
BUFFER_SIZE = 65536
MAX_QUEUE_SIZE = 100 
BUFFER_SIZE = 65536
MAX_QUEUE_SIZE = 100 

class oNode: 

	def __init__(self, manage_port=6010, stream_port=25000):
		self.IP = getSelfIP()
		self.manage_port = manage_port
		self.stream_port = stream_port
		self.upstream_neighbours = set()
		self.downstream_neighbours = set()
		self.management_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.stream_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.stream_queueMessages = Queue()
		self.activeStreams = {}

		self.stream_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
		self.stream_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
		self.oPop = None
		self.run()

	def run(self): 
		self.management_socket.bind((self.IP, self.manage_port))
		self.management_thread = threading.Thread(target=self.listenManagement).start() #run a thread to communicate other nodes about overlay network

		self.stream_socket.bind((self.IP, self.stream_port))
		self.stream_thread = threading.Thread(target=self.listenStream).start() #run a thread to communicate other nodes about stream
	
	def checkPopCondition(self): 
		if self.oPop is None and len(self.downstream_neighbours) == 0: 
			self.oPop = oPop(self.IP, self.stream_queueMessages)

	def getNeighbourFromIdx(self, set, index):
		temp = list(set)
		return temp[index]

	def propagateOverlay(self, overlay_conn):
		"""
		Propagates the overlay structure to downstream neighbors and aggregates their reports.
		"""
		print(f"[{self.IP}] Overlay: {overlay_conn}")

		# Base case: If no downstream neighbors, stop propagation
		if not self.downstream_neighbours:
			print(f"[{self.IP}] No downstream neighbours. Propagation stops here.")
			return {"status": "success", "node": self.IP}

		# Thread-safe list to collect reports from all downstream neighbors
		reports = []
		threads = []
		report_lock = threading.Lock()

		def send_to_neighbour(neighbour):
			"""
			Sends overlay data to a single neighbor and collects its response.
			"""
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
				try:
					print(f"[{self.IP}] Connecting to downstream neighbor {neighbour}")
					s.connect((neighbour, 6010))

					packet = json.dumps({
						"type": "overlay_setup",
						"from": self.IP,
						"data": {
							"overlay_conn": json.dumps(overlay_conn),
							"stream_port": self.stream_port,
						}
					})

					s.send(packet.encode('utf-8'))
					data = s.recv(1024).decode('utf-8')
					response = json.loads(data)
					print(f"[{self.IP}] Received response from {neighbour}: {response}")

					with report_lock:
						reports.append(response)

				except Exception as e:
					print(f"[{self.IP}] Error connecting to {neighbour}: {e}")
					with report_lock:
						reports.append({"status": "failure", "node": neighbour, "error": str(e)})

		# Create and start a thread for each downstream neighbor
		for neighbour in self.downstream_neighbours:
			thread = threading.Thread(target=send_to_neighbour, args=(neighbour,))
			threads.append(thread)
			thread.start()

		# Wait for all threads to complete
		for thread in threads:
			thread.join()

		# Aggregate reports from all neighbors and include this node's status
		final_report = {
			"status": "success" if all(r.get("status") == "success" for r in reports) else "failure",
			"node": self.IP,
			"reports": reports,
		}

		print(f"[{self.IP}] Aggregated report: {final_report}")
		return final_report
	
	def parseManagement(self, packet):
		try:
			data = json.loads(packet)
			overlay_conn = json.loads(data["data"]["overlay_conn"])

			if data["type"] == "overlay_setup":
				neighbours = overlay_conn.pop(self.IP, None)
				
				if neighbours is not None:
					self.downstream_neighbours.update(neighbours)
					
				self.upstream_neighbours.add(data["from"])
				print(f"\nDownstream neighbours: {self.downstream_neighbours} Upstream neighbours: {self.upstream_neighbours}")

				return overlay_conn
		
		except json.JSONDecodeError:
			print("Received invalid JSON data.")
		except Exception as e:
			print(f"Error handling data: {e}")

	def listenManagement(self): 
		try:
				self.management_socket.listen()
				print(f"[THREAD {self.management_socket.getsockname()}]Node listening")

				while True:
					conn, (fromIP, fromPort) = self.management_socket.accept()
					print(f"[THREAD {self.management_socket.getsockname()}]: Accepted connection from {fromIP}:{fromPort}")
					data = conn.recv(1024).decode('utf-8')
					print(f"[THREAD {self.management_socket.getsockname()}]: {data}")

					overlay_conn = self.parseManagement(data)
					report_packet = self.propagateOverlay(overlay_conn)
					self.checkPopCondition()

					conn.sendall(json.dumps(report_packet).encode("utf-8"))
					conn.close()		

		except Exception as e: 
			print(f"Error (listenManagement): {e}")
	
	def listenStream(self):
		try:
			print(f"[THREAD {self.stream_socket.getsockname()}]Node listening")

			while True:
				
				while (self.oPop is not None and not self.oPop.stream_queueMessages.empty()) or not self.stream_queueMessages.empty():
					packet = self.stream_queueMessages.get()
					print(f"[THREAD {self.stream_socket.getsockname()}] Upstream Nodes: {self.upstream_neighbours}")
					toIP = self.getNeighbourFromIdx(self.upstream_neighbours, 0)
					print(f"[THREAD {self.stream_socket.getsockname()}] sending: {packet}\nTo:{toIP}:{self.stream_port}\tSize:{len(packet)}]")
					packet = json.dumps(packet).encode("utf-8")

					self.stream_socket.sendto(packet, (toIP, self.stream_port))

				try:
					self.stream_socket.settimeout(0.5) 
					packet, (fromIP, fromPort) = self.stream_socket.recvfrom(30000)
					print(f"[THREAD {self.stream_socket.getsockname()}] Connect accepted from {fromIP}:{fromPort}\n")
					
					data = json.loads(packet.decode("utf-8"))
					print(f"[THREAD {self.stream_socket.getsockname()}] Data: {data}\n")
					
					if data["type"] == "request" and data["command"] == "SETUP":
						#data["path"].append(self.IP)
						filename = data["data"].split(' ')[1]
						print(f"STREAM DATA: {data}")

						if filename in self.activeStreams.keys(): 
							self.activeStreams[filename]['active_nodes'].update([fromIP]) 
						
						else:
							#Add entry
							self.activeStreams[filename] = {
								'active_nodes': set([fromIP]),
							}

						self.stream_queueMessages.put(data)

					elif data["type"] == "response": 
						print(f"STREAM DATA: {data}")
						print(f"Active Stream: {self.activeStreams}")
						#filename = data["data"].split(' ')[1]
						filename = data["filename"]

						# Verificar se oPop está configurado
						if self.oPop is not None:
							active_clients = {}
							# Filtrar os clientes "ativos" do dicionário de oPop
							for ip, client_status in self.oPop.clients_status.items():
								# Verificar se o status do cliente é "ativo"
								if client_status == "ativo":
									active_clients[ip] = client_status

							# Enviar a resposta apenas para os clientes "ativos"
							for client_ip in active_clients:
								addr = (client_ip, 25000)
								print(f"SENDING TO {addr}")
								self.stream_socket.sendto(packet, addr)

						else:
							# Lógica de envio padrão, caso oPop seja None
							for node in self.activeStreams[filename]['active_nodes']:
								addr = (node, 25000)
								print(f"SENDING TO {addr}")
								self.stream_socket.sendto(packet, addr)
				except json.JSONDecodeError as e:
					print(f"Received invalid JSON data: {e}")
					print(f"\nPacket: {packet}")
				except socket.timeout:
					continue

		except Exception as e: 
			print(f"Error (listenStream): {e}")

if __name__ == "__main__":
	node = oNode()
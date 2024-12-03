
import socket, json, threading, sys
from queue import Queue
from oPop import oPop
from NetworkFunctions import getSelfIP
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
			self.oPop = oPop(self.IP, self.stream_queueMessages,self.stream_socket)

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
					
					if packet["type"] == "request" and packet["command"] == "SETUP":
						if "filename" in packet and self.oPop is not None:
							filename = packet["filename"]
							print(f"[DEBUG] Verificando cache para o vídeo: {filename}")

							if self.oPop.is_video_in_cache(filename):
								print(f"[CACHE] Vídeo {filename} encontrado no cache. Enviando frames...")
								client_ip = packet["path"][0] 
								start_frame = self.oPop.clients_status.get(client_ip, {}).get("paused_frame", 0)
								self.oPop.start_sending_frames(filename, client_ip, start_frame)
								continue 
							else:
								print(f"[CACHE] Vídeo {filename} não encontrado no cache. Encaminhando para o próximo nó.")
					
					
					
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
					
					if data["type"]=="request":
						if data["command"]=="SETUP":
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
					
						elif ("command" in data and data["command"] == "END"):
							filename = data.get("filename", None)
							fromIP = data.get("from", None) 
							print(f"[END] Recebido comando 'END' para {filename} do nó {fromIP}.")

							
							if filename in self.activeStreams:
								self.activeStreams[filename]['active_nodes'].discard(fromIP)
								print(f"[END] Nó {fromIP} removido dos active_nodes do fluxo {filename}.")

								# Se não houver mais active_nodes, propagar END para o próximo upstream
								if not self.activeStreams[filename]['active_nodes']:
									print(f"[END] Nenhum active_node restante para {filename}. Propagando END para o próximo upstream.")
									
									# Criar e enviar pacote END para o upstream
									end_packet = {
										"type": "request",
										"command": "END",
										"filename": filename,
										"from": self.IP
									}
									if self.upstream_neighbours:
										upstream_node = self.getNeighbourFromIdx(self.upstream_neighbours, 0)
										addr = (upstream_node, self.stream_port)
										self.stream_socket.sendto(json.dumps(end_packet).encode('utf-8'), addr)
										print(f"[END] Comando 'END' propagado para o nó upstream {upstream_node}.")
							else:
								print(f"[END] Fluxo {filename} não encontrado no activeStreams.")	
								

					elif data["type"] == "response": 
						print(f"STREAM DATA: {data}")
						print(f"Active Stream: {self.activeStreams}")
						#filename = data["data"].split(' ')[1]
						filename = data["filename"]

						# Verificar se oPop está configurado
						if self.oPop is not None:
							if ("command" in data and data["command"] == "END"):
								print(f"[END] Recebido comando 'END' para {filename}. Preparando pacote de request.")

								# Criar um novo pacote de request para "END"
								end_request_packet = {
									"type": "request",
									"command": "END",
									"filename": filename,
									"from": self.IP
								}

								
								# Adicionar o pacote à fila de mensagens
								self.stream_queueMessages.put(end_request_packet)
								continue
							else:
								self.oPop.store_frame_in_cache(data["filename"],data["frame"],data["data"])
								active_clients = {
									ip: info for ip, info in self.oPop.clients_status.items()
									if info["status"] == "ativo" and info.get("transmission_mode") != "dedicated" and info.get("filename") == data["filename"]
								}


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
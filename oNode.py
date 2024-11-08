import socket, json, threading, sys
from queue import Queue

class oNode: 
	def __init__(self, host, client_port=5050, manage_port=6010, stream_port=25000):
		self.IP = host
		self.client_port = client_port
		self.manage_port = manage_port
		self.stream_port = stream_port
		self.upstream_neighbours = set()
		self.downstream_neighbours = set()
		self.management_socket = threading.Thread(target=self.listenManagement).start() #run a thread to communicate other nodes about overlay network
		self.stream_socket = threading.Thread(target=self.listenStream).start() #run a thread to communicate other nodes about stream
		self.stream_queueMessages = Queue()

	def getNeighbourFromIdx(self, set, index):
		temp = list(set)
		return temp[index]
	
	def handle_data(self, packet):
		try:
			data = json.loads(packet)

			if data["type"] == "init":
				self.downstream_neighbours.update(data["data"]["downstream_neighbours"])
				#self.stream_port = data["data"]["stream_port"] lets assume the stream port (25000) is fixed 
				self.upstream_neighbours.add(data["from"])
				print(f"\nDownstream neighbours: {self.downstream_neighbours} Stream_port: {self.stream_port}")
			
			elif data["type"] == "checkcomm":
				self.upstream_neighbours.add(data["from"])
				self.stream_port = data["data"]["stream_port"]
				self.startClientSocket()
			
			elif data["type"] == "request":
				data["path"].append(self.IP)
				print(f"STREAM DATA: {data}")
				self.stream_queueMessages.put(data)

			elif data["type"] == "response": 
				data["path"].pop()
				print(f"STREAM DATA: {data}")
				self.sendDownstream(data)

		except json.JSONDecodeError:
			print("Received invalid JSON data.")
		except Exception as e:
			print(f"Error handling data: {e}")

	def streamListen(self): 
		print("oNode started listening!")
		if self.stream_port_listening == 0:
			threading.Thread(target=self.awaitConn).start()
		else: 
			print("oNode already listening for streams!")
	
	def build_ReportPacket(self, array):
		return {
			"type":  "init_resp",
			"from": self.IP,
			"data": {} if len(array) <= 0 else { "error_nodes": array }
		}

	def checkNeighboursLink(self):
		report = []
		for neighbour_node in self.downstream_neighbours:
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
				try:
					print(f"Connecting to {neighbour_node}")
					s.connect((neighbour_node, 6010))
					packet = json.dumps({"type": "checkcomm", "from": self.IP, "data": { "stream_port": self.stream_port}})
					s.send(packet.encode('utf-8'))
					print(f"Sent neighbours! {neighbour_node}")
					s.close()

				except socket.error as e:
					print(f"Error connecting to {neighbour_node}: {e}")
					report.append(neighbour_node)

		return report
	
	def startClientSocket(self):
		#The node is not a server to another oNode
		if len(self.downstream_neighbours) == 0: 
			print("Starting client socket")
			self.client_socket = threading.Thread(target=self.listenClient).start()

	def listenManagement(self): 
		try:
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
				s.bind((self.IP, self.manage_port))
				s.listen()
				print(f"[THREAD]Node listening on {self.IP}:{self.manage_port}")

				while True:
					conn, (fromIP, fromPort) = s.accept()
					print(f"Accepted connection from {fromIP}:{fromPort}")
					data = conn.recv(1024).decode('utf-8')

					self.handle_data(data)
					report_packet = self.build_ReportPacket(self.checkNeighboursLink())

					conn.sendall(json.dumps(report_packet).encode("utf-8"))
					conn.close()		

		except Exception as e: 
			print(f"Error (listenManagement): {e}")

	def listenClient(self): 
		try:
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
				s.bind((self.IP, self.client_port))
				s.listen()
				print(f"[THREAD]Node listening on {self.IP}:{self.client_port}")

				while True: 	#Run if it doenst have downstream neighbour (oNodes that are clients) 	
					conn, (fromIP, fromPort) = s.accept()
					print(f"Connect accepted from {fromIP}:{fromPort}")
					data = conn.recv(1024).decode('utf-8')
					
					self.handle_data(data)

					s.close()

		except Exception as e: 
			print(f"Error (listenClient): {e}")
	
	def listenStream(self):
		try:
			with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
				s.bind((self.IP, self.stream_port))
				print(f"[THREAD]Node listening on {self.IP}:{self.stream_port}")

				while True:
					while not self.stream_queueMessages.empty():
						packet = self.stream_queueMessages.get()
						toIP = self.getNeighbourFromIdx(self.upstream_neighbours, 0)
						print(f"[THREAD] sending: {packet}\nTo:{toIP}:{self.stream_port}]")
						packet = json.dumps(packet).encode("utf-8")

						s.sendto(packet, (toIP, self.stream_port))

					try:
						s.settimeout(0.5) 
						data, (fromIP, fromPort) = s.recvfrom(1024)
						print(f"Connect accepted from {fromIP}:{fromPort}")
						
						self.handle_data(data.decode("utf-8"))
					except socket.timeout:
						continue

		except Exception as e: 
			print(f"Error (listenStream): {e}")

if __name__ == "__main__":
	try:
		selfIP = sys.argv[1]
	except:
		print("[Usage: oNode.py Self_IP]\n")	

	#Init oNode
	node = oNode(selfIP)
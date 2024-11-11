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
		self.management_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.stream_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.stream_queueMessages = Queue()
		self.run()

	def run(self): 
		self.management_socket.bind((self.IP, self.manage_port))
		self.management_thread = threading.Thread(target=self.listenManagement).start() #run a thread to communicate other nodes about overlay network

		self.stream_socket.bind((self.IP, self.stream_port))
		self.stream_thread = threading.Thread(target=self.listenStream).start() #run a thread to communicate other nodes about stream


	def getNeighbourFromIdx(self, set, index):
		temp = list(set)
		return temp[index]
		
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
			self.client_socket.bind((self.IP, self.client_port))
			self.client_thread = threading.Thread(target=self.listenClient).start()
	
	def parseManagement(self, packet):
		try:
			data = json.loads(packet)

			if data["type"] == "init":
				self.downstream_neighbours.update(data["data"]["downstream_neighbours"])
				self.upstream_neighbours.add(data["from"])
				print(f"\nDownstream neighbours: {self.downstream_neighbours} Stream_port: {self.stream_port}")
			
			elif data["type"] == "checkcomm":
				self.upstream_neighbours.add(data["from"])
				self.stream_port = data["data"]["stream_port"]
				self.startClientSocket()
		
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

					self.parseManagement(data)
					report_packet = self.build_ReportPacket(self.checkNeighboursLink())

					conn.sendall(json.dumps(report_packet).encode("utf-8"))
					conn.close()		

		except Exception as e: 
			print(f"Error (listenManagement): {e}")
	
	def parseClient(self, packet): 
		try:
			data = json.loads(packet)
			
			if data["type"] == "request":
				data["path"].append(self.IP)
				print(f"STREAM DATA: {data}")
				self.stream_queueMessages.put(data)

		except json.JSONDecodeError:
			print("Received invalid JSON data.")
		except Exception as e:
			print(f"Error handling data: {e}")

	def listenClient(self): 
		try:
			self.client_socket.listen()
			print(f"[THREAD {self.client_socket.getsockname()}]Node listening")

			while True: 	#Run if it doenst have downstream neighbour (oNodes that are clients) 	
				conn, (fromIP, fromPort) = self.client_socket.accept()
				print(f"[THREAD {self.client_socket.getsockname()}] Connect accepted from {fromIP}:{fromPort}")
				data = conn.recv(1024).decode('utf-8')
				
				self.parseClient(data)

				self.client_socket.close()

		except Exception as e: 
			print(f"Error (listenClient): {e}")

	def parseStream(self, packet):
		try:
			data = json.loads(packet)
			
			if data["type"] == "request":
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
	
	def listenStream(self):
		try:
			print(f"[THREAD {self.stream_socket.getsockname()}]Node listening")

			while True:
				while not self.stream_queueMessages.empty():
					packet = self.stream_queueMessages.get()
					toIP = self.getNeighbourFromIdx(self.upstream_neighbours, 0)
					print(f"[THREAD {self.stream_socket.getsockname()}] sending: {packet}\nTo:{toIP}:{self.stream_port}]")
					packet = json.dumps(packet).encode("utf-8")

					self.stream_socket.sendto(packet, (toIP, self.stream_port))

				try:
					self.stream_socket.settimeout(0.5) 
					packet, (fromIP, fromPort) = self.stream_socket.recvfrom(1024)
					print(f"[THREAD {self.stream_socket.getsockname()}] Connect accepted from {fromIP}:{fromPort}")
					
					data = json.loads(packet.decode("utf-8"))
					
					if data["type"] == "request":
						data["path"].append(self.IP)
						print(f"STREAM DATA: {data}")
						self.stream_queueMessages.put(data)

					elif data["type"] == "response": 
						data["path"].pop()
						print(f"STREAM DATA: {data}")
						self.sendDownstream(data)

				except json.JSONDecodeError:
					print("Received invalid JSON data.")
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
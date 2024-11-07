import socket, json, sys, threading, time 

class oNode: 
	def __init__(self, host, manage_port=6010):
		self.IP = host
		self.manage_port = manage_port
		self.stream_port = 0
		self.upstream_neighbours = set()
		self.downstream_neighbours = set()
		self.stream_port_listening = 0

		self.run()

	def getNeighbourFromIdx(self, set, index):
		temp = list(set)
		return temp[index]
	
	def handle_data(self, packet):
		try:
			data = json.loads(packet)

			if data["type"] == "init":
				self.downstream_neighbours.update(data["data"]["downstream_neighbours"])
				self.stream_port = data["data"]["stream_port"]
				self.upstream_neighbours.add(data["from"])
				print(f"Upstream neighbours: {self.downstream_neighbours}\n Stream_port: {self.stream_port}")
				self.checkNeighboursLink()
				self.streamListen()
			
			elif data["type"] == "checkcomm":
				self.upstream_neighbours.add(data["from"])
				self.stream_port = data["data"]["stream_port"]
				print(f"CheckCom: {self.downstream_neighbours} and stream_port:{self.stream_port}")
				self.streamListen()
			
			elif data["type"] == "request":
				data["path"].append(self.IP)
				print(f"STREAM DATA: {data}")
				self.sendUpstream(data)
			
			elif data["type"] == "response": 
				data["path"].pop()
				print(f"STREAM DATA: {data}")
				self.sendDownstream(data)

		except json.JSONDecodeError:
			print("Received invalid JSON data.")
		except Exception as e:
			print(f"Error handling data: {e}")
	
	def sendUpstream(self, packet): 
		with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
			print(f"Upstream neighbour: {self.upstream_neighbours}")
			#s.connect((self.getNeighbourFromIdx(self.upstream_neighbours, 0), 5050))
			addr = (self.getNeighbourFromIdx(self.upstream_neighbours, 0), 5050)
			s.sendto(json.dumps(packet).encode("utf-8"), addr)

			#Wait response 
			#data = s.recv(256)
			#temp = json.loads(data)
			#temp["path"] = packet["path"]
			#data = json.dumps(temp)
			#print(f"Receiving stream packet\n {data}")
			#self.handle_data(data)
	
	def sendDownstream(self, packet): 
		with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
			try:
				downstream_neighbour = packet["path"][-1]
				print(f"Downstream neighbour: {downstream_neighbour}")
				s.connect((packet["path"][-1], 5050))
				time.sleep(10)
				s.send(json.dumps(packet).encode("utf-8"))
				print("HERE")
			
			except Exception and socket.error as e:
				print(f"Error: {e}")

	
	def streamListen(self): 
		print("oNode started listening!")
		if self.stream_port_listening == 0:
			threading.Thread(target=self.awaitConn).start()
		else: 
			print("oNode already listening for streams!")

	def awaitConn(self):
		"""Open port for streaming data"""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtspSocket.bind(('', self.stream_port))
		#self.rtspSocket.listen(5)
		self.stream_port_listening = 1
		while True:
			#conn, addr = self.rtspSocket.accept()
			data, addr = self.rtspSocket.recvfrom(256)
			self.handle_data(data)

		
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
	
	def build_ReportPacket(self, array):
		if len(array) > 0:
			return {
				"type":  "init_resp",
				"from": self.IP,
				"data": {
					"error_nodes": array
				}
			}
		
		else:
			return {
				"type":  "init_resp",
				"from": self.IP,
				"data": {}
			}

	def run(self):
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
			s.bind((self.IP, self.manage_port))
			s.listen()
			print(f"Node listening on {self.IP}:{self.manage_port}")

			while True: 
				conn, addr = s.accept()
				data = conn.recv(1024).decode('utf-8')

				self.handle_data(data)
				report_packet = self.build_ReportPacket(self.checkNeighboursLink())

				conn.sendall(json.dumps(report_packet).encode("utf-8"))
				conn.close()

if __name__ == "__main__":
	try:
		selfIP = sys.argv[1]
	except:
		print("[Usage: oNode.py Self_IP]\n")	
	
	# Create a new client
	node = oNode(selfIP)
	node.run()
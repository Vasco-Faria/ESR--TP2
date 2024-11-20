import socket, json, threading
from queue import Queue

class oPop: 
	def __init__(self, host, client_port=5050):
		self.IP = host
		self.client_port = client_port
		self.upstream_neighbours = set()
		self.downstream_neighbours = set()
		self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.stream_queueMessages = Queue()
		self.startClientSocket()
	
	def startClientSocket(self):
		#The node is not a server to another oNode
		if len(self.downstream_neighbours) == 0: 
			print("Starting client socket")
			self.client_socket.bind((self.IP, self.client_port))
			self.client_thread = threading.Thread(target=self.listenClient).start()
	
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
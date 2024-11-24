import socket, json, threading
from queue import Queue

class oPop: 
	def __init__(self, host, client_port=5050):
		print(f"POP IP {host}")
		self.IP = host
		self.client_port = client_port
		self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.stream_queueMessages = Queue()
		self.startClientSocket()
	
	def startClientSocket(self):
		#The node is not a server to another oNode
		print("Starting client socket")
		try:
			# Bind to the specified IP and port
			self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self.client_socket.bind(('0.0.0.0', self.client_port))
			self.client_thread = threading.Thread(target=self.listenClient).start()
		except Exception as e:
			print(f"Error binding client socket: {e}")
			raise
	
	def parseClient(self, packet): 
		try:
			data = json.loads(packet)
			
			if data["type"] == "request":
				print(f"STREAM DATA: {data}")
				self.stream_queueMessages.put(data)

		except json.JSONDecodeError:
			print("Received invalid JSON data.")
		except Exception as e:
			print(f"Error handling data: {e}")

	def listenClient(self): 
		try:
			print(f"[THREAD {self.client_socket.getsockname()}]Node listening")

			while True: 	#Run if it doenst have downstream neighbour (oNodes that are clients) 	
				packet, (fromIP, fromPort) = self.client_socket.recvfrom(10240)
				print(f"[THREAD {self.client_socket.getsockname()}] Connect accepted from {fromIP}:{fromPort}")
				data = packet.decode('utf-8')
				
				self.parseClient(data)

		except Exception as e: 
			print(f"Error (listenClient): {e}")
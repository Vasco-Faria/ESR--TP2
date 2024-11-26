import socket, json, threading
from queue import Queue

class oPop: 
	def __init__(self, host, stream_queueMessages, client_port=5050):
		print(f"POP IP {host}")
		self.IP = host
		self.client_port = client_port
		self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.stream_queueMessages = stream_queueMessages
		self.startClientSocket()
		self.clients_status = {}

	def startClientSocket(self):
		#The node is not a server to another oNode
		print("Starting client socket")
		try:
			# Bind to the specified IP and port
			print(self.client_port)
			self.client_socket.bind((self.IP, self.client_port))
			self.client_thread = threading.Thread(target=self.listenClient).start()
		except Exception as e:
			print(f"Error binding client socket: {e}")
			raise


	def set_transmission_canceled(self, client_ip):
		"""Cancela a transmissão para um cliente, atualizando seu status para 'cancelado'."""
		if client_ip in self.clients_status:
			self.clients_status[client_ip] = "cancelado"
			print(f"Transmissão cancelada para o cliente {client_ip}. Status atualizado para 'cancelado'.")

	def add_client(self, client_ip):
		"""Adiciona um cliente ao dicionário com status 'ativo'."""
		if client_ip not in self.clients_status:
			self.clients_status[client_ip] = "ativo"
			print(f"Cliente {client_ip} adicionado com status 'ativo'.")
		else:
			self.clients_status[client_ip] = "ativo"


	def parseClient(self, packet, clientIP): 
		try:
			data = json.loads(packet)
			
			if data["type"] == "request":
				command = data.get("command")
				if command == "SETUP":
					self.add_client(clientIP)

				if command == "CANCEL":
					self.set_transmission_canceled(clientIP)
				data["path"] = [self.IP]
				print(f"STREAM DATA: {data}")

				self.stream_queueMessages.put(data)

		except json.JSONDecodeError:
			error_response = json.dumps({
				"status": "error", 
				"code": 400, 
				"message": "Invalid JSON format",
				"data": {}
			})
			self.client_socket.sendto(error_response.encode('utf-8'), (clientIP, self.client_port))
			print("Received invalid JSON data.")
		except Exception as e:
			error_response = json.dumps({
				"status": "error", 
				"code": 500, 
				"message": f"Server error: {str(e)}",
				"data": {}
			})
			self.client_socket.sendto(error_response.encode('utf-8'), (clientIP, self.client_port))
			print(f"Error handling data: {e}")

	def listenClient(self): 
		try:
			print(f"[THREAD {self.client_socket.getsockname()}]Node listening")

			while True: 	#Run if it doenst have downstream neighbour (oNodes that are clients) 	
				packet, (fromIP, fromPort) = self.client_socket.recvfrom(10240)
				print(f"[THREAD {self.client_socket.getsockname()}] Connect accepted from {fromIP}:{fromPort}")
				data = packet.decode('utf-8')
				
				self.parseClient(data, fromIP)

		except Exception as e: 
			print(f"Error (listenClient): {e}")
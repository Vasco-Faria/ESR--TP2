import socket, json, threading
from queue import Queue
import time

class oPop: 
	def __init__(self, host, stream_queueMessages,stream_socket,client_port=5050):
		print(f"POP IP {host}")
		self.IP = host
		self.client_port = client_port
		self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.stream_queueMessages = stream_queueMessages
		self.startClientSocket()
		self.clients_status = {}
		self.stream_socket = stream_socket


		self.initializeCache()


	# ================== CACHE FUNCTIONS ==================

	def initializeCache(self):
		if not hasattr(self, "cache") or self.cache is None:
			self.cache_order = [] 
			self.max_movies =5 
			self.cache = {} 
			print("[CACHE] Cache inicializado.")


	def store_frame_in_cache(self, file_name, frame_number, encoded_chunk):
		"""Armazena um frame no cache do PoP, removendo o filme mais antigo se o limite for atingido."""
		if file_name not in self.cache:
			if len(self.cache_order) >= self.max_movies:
				oldest_file = self.cache_order.pop(0)  
				del self.cache[oldest_file] 
				print(f"[CACHE] Filme mais antigo '{oldest_file}' removido do cache.")

			
			self.cache[file_name] = {}
			self.cache_order.append(file_name) 

		# Armazena o frame no cache
		self.cache[file_name][frame_number] = encoded_chunk
		print(f"[CACHE] Frame {frame_number} do vídeo {file_name} armazenado no cache.")

	def is_video_in_cache(self, filename):
		"""Verifica se o vídeo está no cache."""
		return filename in self.cache


	def send_frames_from_cache(self, filename, path):
		"""Envia todos os frames armazenados no cache para o cliente."""
		time.sleep(1)
		active_clients = {}
		for ip, client_status in self.clients_status.items():
			active_clients[ip] = client_status

		if filename in self.cache:
			frames = self.cache[filename]
			
			delay = 1 / 30
			for frame_number in sorted(frames.keys()): 
				frame_data = frames[frame_number]
				packet = {
					"type": "frame",
					"filename": filename,
					"frame_number": frame_number,
					"data": frame_data,
					"path": path
				}

				for client_ip in active_clients:
					addr = (client_ip, 25000)
					self.stream_socket.sendto(
						json.dumps(packet).encode("utf-8"),
						addr  
					)
					print(f"[CACHE] Frame {frame_number} do vídeo {filename} enviado.")
				time.sleep(delay*1.5)

	# ====================================================

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
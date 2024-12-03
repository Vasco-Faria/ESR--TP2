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
		self.client_threads = {}


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

	def send_frames_from_cache(self, filename, client_ip, start_frame=0):
		"""Envia todos os frames armazenados no cache para um cliente específico."""
		print(f"[DEBUG] Iniciando envio para {client_ip} do vídeo {filename} a partir do frame {start_frame}.")
		if filename not in self.cache:
			print(f"[DEBUG] Arquivo {filename} não encontrado no cache.")
			return

		frames = self.cache[filename]
		delay = 1 / 30  # 30 FPS

		try:
			for frame_number in sorted(frames.keys()):
				if frame_number < start_frame:
					continue

				# Verifica se o cliente pausou durante o envio
				if self.clients_status.get(client_ip, {}).get("status") == "pausado":
					print(f"[DEBUG] Transmissão pausada para {client_ip} no frame {frame_number}.")
					self.clients_status[client_ip]["pause_event"].wait()  # Aguarda o evento de retomada
					print(f"[DEBUG] Retomando transmissão para {client_ip} no frame {frame_number}.")
					

				frame_data = frames[frame_number]
				packet = {
					"type": "frame",
					"filename": filename,
					"frame_number": frame_number,
					"data": frame_data,
				}

				addr = (client_ip, 25000)
				self.stream_socket.sendto(
					json.dumps(packet).encode("utf-8"),
					addr
				)
				print(f"[CACHE] Frame {frame_number} do vídeo {filename} enviado para {client_ip}.")
				time.sleep(delay)  # Simular FPS ajustado

			print(f"[CACHE] Transmissão finalizada para o cliente {client_ip}.")
			self.clients_status[client_ip]["status"] = "finalizado"

		except Exception as e:
			print(f"[ERROR] Erro ao enviar frames para {client_ip}: {e}")


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
			self.clients_status.pop(client_ip)
			print(f"Transmissão cancelada para o cliente {client_ip}. Status atualizado para 'cancelado'.")

	def add_client(self, client_ip, filename):
		"""Adiciona um cliente ao dicionário com status 'ativo'."""
		if client_ip not in self.clients_status:
			self.clients_status[client_ip] = {
				"status": "ativo",
				"transmission_mode": "shared",
				"filename": filename,
				"pause_event": threading.Event()  # Evento para controlar pausa/retomada
			}
			self.clients_status[client_ip]["pause_event"].set()  # Inicia como 'ativo'
			print(f"Cliente {client_ip} adicionado com status 'ativo'.")
		else:
			self.clients_status[client_ip].update({
				"status": "ativo",
				"filename": filename,
				"pause_event": threading.Event()  # Atualiza evento se necessário
			})
			self.clients_status[client_ip]["pause_event"].set()



	def stop_client_thread(self, client_ip):
		"""Encerra todas as threads associadas a um cliente específico."""
		if client_ip in self.client_threads:
			threads = self.client_threads[client_ip]
			for thread in threads:
				if thread and thread.is_alive():
					print(f"[DEBUG] Encerrando thread {thread.name} para {client_ip}.")
					self.clients_status[client_ip]["status"] = "pausado"  # Atualiza status do cliente
					thread.join(timeout=1)  # Aguarda o término da thread
					print(f"[DEBUG] Thread {thread.name} para {client_ip} encerrada.")
			# Limpa todas as threads do cliente após encerrar
			self.client_threads.pop(client_ip, None)
			print(f"[DEBUG] Todas as threads para {client_ip} foram encerradas.")
		else:
			print(f"[DEBUG] Nenhuma thread ativa para {client_ip}.")


		# Caso o cliente tenha outra thread (como de resumir transmissão), também a encerre
		if "resume_thread" in self.clients_status.get(client_ip, {}):
			resume_thread = self.clients_status[client_ip].get("resume_thread")
			if resume_thread and resume_thread.is_alive():
				print(f"[DEBUG] Encerrando thread de resumo para {client_ip}.")
				self.clients_status[client_ip]["status"] = "pausado"
				resume_thread.join(timeout=1)  # Aguarda o término da thread
				print(f"[DEBUG] Thread de resumo para {client_ip} encerrada.")
			self.clients_status[client_ip].pop("resume_thread", None)  # Remove a referência


	def start_sending_frames(self, filename, client_ip, start_frame=0):
		"""Cria e inicia uma thread para enviar frames para um cliente."""
		if client_ip in self.client_threads:
			print(f"[DEBUG] Cliente {client_ip} já possui uma thread ativa.")
			return

		if client_ip not in self.client_threads:
			self.client_threads[client_ip] = []

		# Criar e iniciar a thread
		thread = threading.Thread(
			target=self.send_frames_from_cache,
			args=(filename, client_ip, start_frame),
		)
		thread.daemon = True  # Finalizar com o processo principal
		thread.start()

		self.client_threads[client_ip].append(thread)
		print(f"[DEBUG] Thread iniciada para envio de {filename} ao cliente {client_ip}.")


	def parseClient(self, packet, clientIP):
		try:
			data = json.loads(packet)

			if data["type"] == "request":
				command = data.get("command")
				filename = data.get("filename", None)
				if command == "SETUP":
					self.stop_client_thread(clientIP)
					self.add_client(clientIP, filename)
					self.stream_queueMessages.put(data)

				elif command == "PLAY":
					if clientIP in self.clients_status:
						self.clients_status[clientIP]["status"] = "ativo"
						self.clients_status[clientIP]["pause_event"].set()  # Retomar transmissão
						if clientIP not in self.client_threads or not any(t.is_alive() for t in self.client_threads[clientIP]):
							start_frame = data.get("frame_number", 0)  # Obtém o frame de início do comando PLAY
							filename = self.clients_status[clientIP]["filename"]
							
							print(f"[PLAY] Iniciando nova thread para {clientIP} no frame {start_frame}.")
							self.start_sending_frames(filename, clientIP, start_frame)
						else:
							print(f"[PLAY] Transmissão já ativa para {clientIP}.")

				elif command == "PAUSE":
					if clientIP in self.clients_status:
						self.clients_status[clientIP]["status"] = "pausado"
						self.clients_status[clientIP]["pause_event"].clear()  # Pausar transmissão
						print(f"[PAUSE] Transmissão pausada para {clientIP}.")

				elif command == "TEARDOWN":
					self.stop_client_thread(clientIP)
					self.set_transmission_canceled(clientIP)

				data["path"].append(self.IP)
				print(f"STREAM DATA: {data}")

		except json.JSONDecodeError:
			error_response = json.dumps({
				"status": "error",
				"code": 400,
				"message": "Invalid JSON format",
				"data": {}
			})
			self.client_socket.sendto(error_response.encode("utf-8"), (clientIP, self.client_port))
			print("Received invalid JSON data.")
		except Exception as e:
			error_response = json.dumps({
				"status": "error",
				"code": 500,
				"message": f"Server error: {str(e)}",
				"data": {}
			})
			self.client_socket.sendto(error_response.encode("utf-8"), (clientIP, self.client_port))
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
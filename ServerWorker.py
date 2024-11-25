import os
from random import randint
import json
import sys, traceback, threading, socket, json, base64, time 

from VideoStream import VideoStream
from RtpPacket import RtpPacket
import cv2

class ServerWorker:


	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'

	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2

	PACKET_SIZE = 30000
	pop_list=[{}]

	video_folder = "Videos" 



	def __init__(self,pop_list):
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtpSocket.bind(('', 25000))

		self.udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.udpSocket.bind(('', 8000))  

		self.pop_list=pop_list
		

		
	def run(self):
		#threading.Thread(target=self.recvRtspRequest).start()
		threading.Thread(target=self.recvRtpRequest).start()
		threading.Thread(target=self.listen_for_requests).start()

	def listen_for_requests(self):
		'''Escuta pedidos UDP do oClient'''
		print("Servidor aguardando pedidos UDP...")
		while True:
			try:
				data, addr = self.udpSocket.recvfrom(4096)  # Recebe pacotes UDP
				request = data.decode()
				
				if request == "GET_POP_LIST":
					self.send_pop_list(addr)    
				elif request == "GET_VIDEO_LIST":
					self.send_video_list(addr)
					
				else:
					print(f"Pedido desconhecido: {request}")
			except Exception as e:
				print(f"Erro ao processar o pedido UDP: {e}")
				break

	def send_pop_list(self, addr):
		'''Envia a lista de PoPs para o oClient'''
		try:
			pop_list_json = json.dumps(self.pop_list)  # Converte a lista de PoPs em JSON
			self.udpSocket.sendto(pop_list_json.encode(), addr)
			print("Lista de PoPs enviada para o oClient.")
		except Exception as e:
			print(f"Erro ao enviar lista de PoPs: {e}")

	def send_video_list(self, addr):
		'''Envia a lista de vídeos para o oClient'''
		try:
			# Lista os vídeos na pasta e converte para JSON
			videos = os.listdir(self.video_folder)
			video_list_json = json.dumps(videos)  # Enviar como JSON
			self.udpSocket.sendto(video_list_json.encode(), addr)
			print("Lista de vídeos enviada para o oClient:", video_list_json)


		except Exception as e:
			print(f"Erro ao enviar lista de vídeos: {e}")


	def recvRtpRequest(self):
		"""Receive RTP request from the oNode."""
		while True:
			try: 
				self.rtpSocket.settimeout(5)            
				packet, addr = self.rtpSocket.recvfrom(256)
				data = json.loads(packet.decode("utf-8"))
				if data["data"]:
					print(f"Data received:\n {data}")
					print(data["data"].split(' '))
					filename = data["data"].split(' ')[1]
					video_path = os.path.join(self.video_folder, filename)
					if os.path.isfile(video_path):
						# Initialize new video stream
						self.videoStream = VideoStream(video_path)
					#self.processRtspRequest(data)
					time.sleep(5)
					self.videoWorker = threading.Thread(target=self.sendRtp, args=(data["path"],)).start() 
			except socket.timeout:
				continue
			
	def sendRtp(self, path):
		"""Send RTP packets over UDP."""
		#fps = self.clientInfo['videoStream'].cap.get(cv2.CAP_PROP_FPS)
		fps = self.videoStream.cap.get(cv2.CAP_PROP_FPS)
		delay = 1 / fps # Delay between sending each frame based on video frame rate

		while True:
			#self.clientInfo['event'].wait(0.05) 
			
			# Stop sending if request is PAUSE or TEARDOWN
			#if self.clientInfo['event'].isSet(): 
			#	break 
			#print(self.clientInfo)
			#data = self.clientInfo['videoStream'].nextFrame()
			data = self.videoStream.nextFrame()
			if data is not None and len(data) > 0: 
				#frameNumber = self.clientInfo['videoStream'].frameNbr()
				frameNumber = self.videoStream.frameNbr()
				try:
					#address = self.clientInfo['rtspSocket'][1][0]
					#port = int(self.clientInfo['rtpPort'])
					

					print("A mandar ", frameNumber)
					for i in range(0, len(data), self.PACKET_SIZE):
						chunk = data[i:i+self.PACKET_SIZE]
						chunk_size=len(chunk)
						print(f"Sending chunk of size: {chunk_size} bytes")

						encoded_chunk = base64.b64encode(self.makeRtp(chunk, frameNumber)).decode("utf-8")
						packet = {"type": "response",
									"path": path,
									"data": encoded_chunk}
						
						try:
							packet = json.dumps(packet).encode("utf-8")
							packet_size = len(packet)
							print(f"JSON packet size: {packet_size} bytes")
							if packet_size > 65507:  # Max UDP packet size for IPv4
								print(f"Warning: Packet size exceeds UDP limit! ({packet_size} bytes)")
							#self.clientInfo['rtpSocket'].sendto(self.makeRtp(chunk, frameNumber), (address, port))
							addr = (path[-1], 25000)
							#print(f"SENDING TO {addr}")
							self.rtpSocket.sendto(packet, addr)

						except json.JSONDecodeError as e:
							print(f"Error encoding JSON: {e}. Invalid packet: {packet}")
						except Exception as e:
							print(f"Error sending packet: {e}")
						#time.sleep(1)
					
					time.sleep(delay)
				except:
					print("Connection Error")
					print('-'*60)
					traceback.print_exc(file=sys.stdout)
					print('-'*60)

	def makeRtp(self, payload, frameNbr, pt=96):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 1 if len(payload) < self.PACKET_SIZE else 0
		seqnum = frameNbr
		ssrc = 0 
		
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			connSocket = self.clientInfo['rtspSocket'][0]
			packet = {"type": "response", "from": "X", "data": reply}
			print(f"Sending packet:\n {packet}")
			connSocket.send(json.dumps(packet).encode("utf-8"))
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")


	""" def processRtspRequest(self, data):
		Process RTSP request sent from the client.
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')[1]
		
		print("Current State:", self.state)
		
		# Process SETUP request
		if requestType == self.SETUP:
			# Stop any ongoing streaming event before setting up a new video
			if 'event' in self.clientInfo:
				if not self.clientInfo['event'].is_set():
					print("Stopping previous streaming event.")
					self.clientInfo['event'].set()  # Signal to stop streaming
					self.clientInfo['worker'].join()  # Wait for the thread to finish
			
			# Proceed with new setup if in INIT, PLAYING, or READY states
			if self.state in [self.INIT, self.PLAYING, self.READY]:
				print("Processing SETUP\n")
				
				video_path = os.path.join(self.video_folder, filename)
				if os.path.isfile(video_path):
					try:
						# Initialize new video stream
						self.clientInfo['videoStream'] = VideoStream(video_path)
						self.state = self.READY
						
						# Generate a randomized RTSP session ID
						self.clientInfo['session'] = randint(100000, 999999)
						
						# Get the RTP/UDP port from the request (assuming it's on the third line)
						self.clientInfo['rtpPort'] = request[2].split(' ')[3]
						
						# Send RTSP reply
						self.replyRtsp(self.OK_200, seq)
					except IOError:
						self.replyRtsp(self.FILE_NOT_FOUND_404, seq)
				else:
					print("File not found: " + video_path)
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq)
		
		# Process PLAY request
		elif requestType == self.PLAY:
			if self.state == self.READY:
				print("Processing PLAY\n")
				self.state = self.PLAYING
				
				# Create a new socket for RTP/UDP
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq)
				
				# Create a new thread and start sending RTP packets
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker'] = threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
		
		# Process PAUSE request
		elif requestType == self.PAUSE:
			if self.state == self.PLAYING:
				print("Processing PAUSE\n")
				self.state = self.READY
				
				# Set the event to stop RTP streaming
				self.clientInfo['event'].set()
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq)
		
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			print("Processing TEARDOWN\n")
			
			# Set the event to stop RTP streaming
			self.clientInfo['event'].set()
			
			# Send RTSP reply
			self.replyRtsp(self.OK_200, seq)
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()
			
			# Reset client state
			self.state = self.INIT
			print("Client has been reset.")
			
			
		elif requestType == "SWITCH":
			if self.state in [self.PLAYING, self.READY]:
				print("Processing SWITCH to video:", filename)
				self.clientInfo['event'].set()  # Stop current streaming event
				
				# Wait for the current streaming thread to finish
				if 'worker' in self.clientInfo:
					self.clientInfo['worker'].join()
				
				# Set up the new video stream
				video_path = os.path.join(self.video_folder, filename)
				if os.path.isfile(video_path):
					try:
						self.clientInfo['videoStream'] = VideoStream(video_path)
						self.state = self.READY
						
						# Send RTSP reply
						self.replyRtsp(self.OK_200, seq)
					except IOError:
						self.replyRtsp(self.FILE_NOT_FOUND_404, seq)
				else:
					print("File not found: " + video_path)
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq)
			else:
				print("Cannot switch video in current state:", self.state)
				self.replyRtsp(self.CON_ERR_500, seq) """
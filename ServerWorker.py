from random import randint
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

	PACKET_SIZE = 14000
	
	clientInfo = {}
 
 
	
	def __init__(self, clientInfo,filename):
		self.clientInfo = clientInfo
		self.filename = filename
		self.videoStream = VideoStream(filename)
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtpSocket.bind(('', 25000))
			
	def run(self):
		#threading.Thread(target=self.recvRtspRequest).start()
		threading.Thread(target=self.recvRtpRequest).start()

	def recvRtpRequest(self):
		"""Receive RTP request from the oNode."""
		while True:
			try: 
				self.rtpSocket.settimeout(5)            
				packet, addr = self.rtpSocket.recvfrom(256)
				data = json.loads(packet.decode("utf-8"))
				if data["data"]:
					print(f"Data received:\n {data}")
					#self.processRtspRequest(data)
					self.videoWorker = threading.Thread(target=self.sendRtp, args=(data["path"],)).start()
			except socket.timeout:
				continue
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:            
			packet = connSocket.recv(256)
			data = json.loads(packet.decode("utf-8"))
			if data["data"]:
				print(f"Data received:\n {data}")
				self.processRtspRequest(data)
	
	def processRtspRequest(self, packet):
		"""Process RTSP request sent from the client."""
		# Get the request type
		data = packet["data"]
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
		# Process SETUP request
		if requestType == self.SETUP:
			if self.state == self.INIT:
				# Update state
				print("processing SETUP\n")
				
				try:
					#self.clientInfo['videoStream'] = VideoStream(self.filename)
					print("Video a enviar: ", self.filename)
					self.state = self.READY
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
				
				# Generate a randomized RTSP session ID
				self.clientInfo['session'] = randint(100000, 999999)
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq[1])
				
				# Get the RTP/UDP port from the last line
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]
		
		# Process PLAY request 		
		elif requestType == self.PLAY:
			if self.state == self.READY:
				print("processing PLAY\n")
				self.state = self.PLAYING
				
				# Create a new socket for RTP/UDP
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				self.replyRtsp(self.OK_200, seq[1])
				
				# Create a new thread and start sending RTP packets
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
		
		# Process PAUSE request
		elif requestType == self.PAUSE:
			if self.state == self.PLAYING:
				print("processing PAUSE\n")
				self.state = self.READY
				
				self.clientInfo['event'].set()
			
				self.replyRtsp(self.OK_200, seq[1])
		
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			print("processing TEARDOWN\n")

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1])
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()
			
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
					print("Size of data: ", len(data))
					
					for i in range(0, len(data), self.PACKET_SIZE):
						chunk = data[i:i+self.PACKET_SIZE]
						print("Size of chunk: ", len(chunk))
						encoded_chunk = base64.b64encode(self.makeRtp(chunk, frameNumber)).decode("utf-8")
						packet = {"type": "response",
									"path": path,
									"data": encoded_chunk}
						packet = json.dumps(packet).encode("utf-8")
						#self.clientInfo['rtpSocket'].sendto(self.makeRtp(chunk, frameNumber), (address, port))
						addr = (path[-1], 25000)
						#print(f"SENDING TO {addr}")
						self.rtpSocket.sendto(packet, addr)
						time.sleep(2)
					
					#time.sleep(delay)
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
		#pt = 26 # MJPEG type
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

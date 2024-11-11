from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os, json, subprocess, base64

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
	
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			print("Pressed play")
			# Create a new thread to listen for RTP packets
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
	
	def listenRtp(self):		
		"""Listen for RTP packets."""
		frame_data = b'' #Buffer to store the frame data

		while True:
			try:
				packet = self.rtpSocket.recv(20480)
				temp = json.loads(packet.decode("utf-8"))
				data = base64.b64decode(temp["data"])
				print(f"DATA: {data}")

				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					currFrameNbr = rtpPacket.seqNum()
					print("Current Seq Num: " + str(currFrameNbr))
										
					if currFrameNbr > self.frameNbr: # Discard the late packet
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo

	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""    
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number
			self.rtspSeq += 1

			# Write the RTSP request to be sent
			request = f"SETUP RTSP/1.0\nCSeq: {self.rtspSeq}\nTransport: RTP/UDP; client_port= {self.rtpPort}\n"

			# Keep track of the sent request
			self.requestSent = self.SETUP

		elif requestCode == self.PLAY and self.state == self.READY:
			self.rtspSeq += 1
			request = f"PLAY  RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}\n"
			self.requestSent = self.PLAY
			print('\nPLAY event\n')

		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			self.rtspSeq += 1
			request = f"PAUSE RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}\n"
			self.requestSent = self.PAUSE
			print('\nPAUSE event\n')

		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			self.rtspSeq += 1
			request = f"TEARDOWN RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}\n"
			self.requestSent = self.TEARDOWN
			print('\nTEARDOWN event\n')

		else:
			return

		#TODO change the encapsulate with a wrapper
		packet = json.dumps({"type": "request", "path": [self.get_myIP()], "data": request})
		# Send the RTSP request using rtspSocket
		self.rtspSocket.send(packet.encode("utf-8"))
		print('\nData sent:\n' + packet)
		self.openRtpPort()
		self.state = self.READY
		self.playMovie()
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])

		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			if self.sessionId == 0:
				self.sessionId = session

			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200:
					if self.requestSent == self.SETUP:
						self.state = self.READY
						self.openRtpPort() 
					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING
						print('\nPLAY sent\n')
					elif self.requestSent == self.PAUSE:
						self.state = self.READY
						self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						self.teardownAcked = 1
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtpSocket.settimeout(2)
		try:
			self.rtpSocket.bind(('', self.rtpPort))
			print('\nBind \n')
		except:
			tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()


	'''
		TODO how can it be possible to make that config.json file on server
		have the same IP's as the one we get from myIP function
	'''
	def get_myIP(self): 
		try: 
			ip = subprocess.check_output("hostname -I | awk '{print $1}'", shell=True).decode().strip()
			return ip
		except subprocess.CalledProcessError as e: 
			print(f"Error getting IP: {e}")
			return None 

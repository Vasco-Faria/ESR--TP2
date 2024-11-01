from tkinter import *
import tkinter.messagebox
from tkinter.simpledialog import askstring
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
from tkinter import Toplevel, OptionMenu, StringVar, Button, Label, messagebox

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
	SWITCH = 4
 
	videoN=0
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = None
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
  
		
	def createWidgets(self):
		"""Build GUI."""
		# Configurar o layout da janela
		self.master.title("Video Streaming Client")
		self.master.configure(bg="#f0f0f0")

		# Título
		self.title = Label(self.master, text="Streaming Player", font=("Arial", 18, "bold"), bg="#f0f0f0")
		self.title.grid(row=0, column=0, columnspan=5, pady=10)

		# Área para exibir o vídeo
		self.label = Label(self.master, height=19, bg="black", relief=SUNKEN)
		self.label.grid(row=1, column=0, columnspan=5, sticky=W+E+N+S, padx=10, pady=20)

		# Estilo moderno para os botões
		button_style = {
			"width": 20,
			"padx": 5,
			"pady": 5,
			"font": ("Arial", 12),
			"bg": "#cccccc",  # Gradiente cinza claro para branco
			"fg": "black",
		}

		# Botão Play
		self.start = Button(self.master, text="Play", command=self.playMovie, **button_style)
		self.start.grid(row=2, column=1, padx=5, pady=10)

		# Botão Pause
		self.pause = Button(self.master, text="Pause", command=self.pauseMovie, **button_style)
		self.pause.grid(row=2, column=2, padx=5, pady=10)
  
		# Botão Switch
		self.switch = Button(self.master, text="Conteúdo", command=self.switchVideo, **button_style)
		self.switch.grid(row=2, column=3, padx=5, pady=10)
  		

		# Botão Teardown (vermelho)
		self.teardown = Button(self.master, text="Teardown", command=self.exitClient, width=20, padx=5, pady=5, 
							font=("Arial", 12), bg="#F44336", fg="white")
		self.teardown.grid(row=2, column=4, padx=5, pady=10)
	
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.READY or self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
			print("Processing Setup for movie: "+ self.fileName)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
   
	def switchVideo(self):
		"""Open a window to select a new video from the server's list."""
		# Cria uma nova janela para seleção de vídeo
		self.switch_window = Toplevel(self.master)
		self.switch_window.title("Selecionar Vídeo")

		# Cria uma variável para armazenar a seleção do usuário
		self.selected_video = StringVar(self.switch_window)
		self.selected_video.set(self.videoList[0])  # Valor padrão

		# Cria um menu suspenso (OptionMenu) para selecionar o vídeo
		Label(self.switch_window, text="Escolha o vídeo:").pack(pady=10)
		OptionMenu(self.switch_window, self.selected_video, *self.videoList).pack()

		# Botão para confirmar a seleção
		Button(self.switch_window, text="Confirmar", command=self.confirmSwitch).pack(pady=10)

	def confirmSwitch(self):
		"""Confirma a seleção de vídeo e altera o vídeo no servidor."""
		selected_video = self.selected_video.get()
		
		if selected_video in self.videoList:
			# Atualiza o vídeo selecionado e reconfigura no servidor
			self.fileName = selected_video
			
			if self.videoN == 0:
				# Primeiro vídeo a ser escolhido: envia uma solicitação SETUP
				print("Configurando o primeiro vídeo:", self.fileName)
				self.sendRtspRequest(self.SETUP)
				self.videoN = 1  # Atualiza o contador para indicar que um vídeo foi escolhido
			else:
				# Envia uma solicitação SWITCH ao servidor
				print("Mudando para o vídeo:", self.fileName)
				self.sendRtspRequest(self.SWITCH)

			# Para a thread existente do listenRtp, se estiver rodando
			if hasattr(self, 'rtp_thread') and self.rtp_thread.is_alive():
				self.playEvent.set()  # Sinaliza para parar a thread
				self.rtp_thread.join()  # Espera a thread terminar
			
			self.switch_window.destroy()  # Fecha a janela de seleção
		else:
			messagebox.showerror("Erro", "Vídeo não encontrado na lista.")
			self.switch_window.destroy()
		
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
			self.videoN=1
			self.frameNbr=0
	
	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
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
		"""Connect to the Server. Start a new RTSP/TCP session and receive the video list."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
			print("Client joined server!")
			self.receiveVideoList()  
		except:
			tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)

	def receiveVideoList(self):
		"""Receive and process the list of videos sent by the server."""
		videoListData = self.rtspSocket.recv(1024).decode("utf-8")  # Recebe até 1024 bytes
		self.videoList = videoListData.splitlines()  # Divide a lista em linhas

		print("Lista de vídeos disponível:")
		for video in self.videoList:
			print(video)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""    
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			
			self.rtspSeq += 1

			request = (f"SETUP {self.fileName} RTSP/1.0\n"
                   f"CSeq: {self.rtspSeq}\n"
                   f"Transport: RTP/UDP; client_port= {self.rtpPort}\n")
			
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
   
		elif requestCode == self.SWITCH:
			self.rtspSeq += 1
			request = f"SWITCH {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}\n"
			self.requestSent = self.SWITCH
			print('\nSWITCH event\n')

		
		else:
			return

		# Send the RTSP request using rtspSocket
		self.rtspSocket.send(request.encode("utf-8"))
		print('\nData sent:\n' + request)
	
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
		self.rtpSocket.settimeout(0.5)
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
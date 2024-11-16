from tkinter import *

import tkinter.messagebox as tkMessageBox
import socket, threading, sys, traceback, os, json, subprocess, base64
from tkinter.simpledialog import askstring
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
from tkinter import Toplevel, OptionMenu, StringVar, Button, Label, messagebox
from oClient import oClient
import time

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
    def __init__(self, master, rtpport=25000):
        self.oclient=oClient()
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.rtpPort = int(rtpport)
        self.fileName = None
        self.sessionId = 0
        self.teardownAcked = 0
        self.frameNbr = 0

        self.videoList = self.oclient.get_video_list() 

        
    def createWidgets(self):
        """Build GUI."""
        # Configurar o layout da janela
        self.master.title("Video Streaming Client")
        self.master.configure(bg="#2c3e50")  # Fundo azul-escuro moderno

        # Título
        self.title = Label(
            self.master,
            text="Streaming Player",
            font=("Segoe UI", 20, "bold"),
            bg="#2c3e50",
            fg="#ecf0f1",  # Texto claro
        )
        self.title.grid(row=0, column=0, columnspan=5, pady=15)

        # Área para exibir o vídeo
        self.label = Label(
            self.master,
            height=19,
            bg="#34495e",  # Fundo cinza-escuro para a área do vídeo
            relief="flat",
        )
        self.label.grid(row=1, column=0, columnspan=5, sticky="nsew", padx=20, pady=20)

        # Estilo moderno para os botões
        button_style = {
            "width": 15,
            "padx": 10,
            "pady": 10,
            "font": ("Segoe UI", 12, "bold"),
            "bg": "#1abc9c",  # Verde-água
            "fg": "white",
            "bd": 0,  # Sem bordas
            "relief": "flat",
        }

        # Botão Play
        self.start = Button(self.master, text="▶ Play", command=self.playMovie, **button_style)
        self.start.grid(row=2, column=1, padx=10, pady=15)

        # Botão Pause
        self.pause = Button(self.master, text="⏸ Pause", command=self.pauseMovie, **button_style)
        self.pause.grid(row=2, column=2, padx=10, pady=15)

        # Botão Switch
        self.switch = Button(self.master, text="⏩ Conteúdo", command=self.switchVideo, **button_style)
        self.switch.grid(row=2, column=3, padx=10, pady=15)

        # Botão Teardown (vermelho)
        self.teardown = Button(
            self.master,
            text="⏹ Teardown",
            command=self.exitClient,
            width=15,
            padx=10,
            pady=10,
            font=("Segoe UI", 12, "bold"),
            bg="#e74c3c",  # Vermelho
            fg="white",
            bd=0,
            relief="flat",
        )
        self.teardown.grid(row=2, column=4, padx=10, pady=15)
    
    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.READY or self.state == self.INIT:
            self.sessionId = int(time.time())
            response = self.oclient.send_udp_request("SETUP", file_name=self.fileName)
            print("Setup response:", response)
            
            if response:
                self.state = self.READY
                self.openRtpPort() 
    
    def exitClient(self):
        """Teardown button handler."""
        response = self.oclient.send_udp_request("TEARDOWN", session_id=self.sessionId)
        print("Teardown response:", response)
        self.master.destroy()
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.oclient.send_udp_request("PAUSE", session_id=self.sessionId)
            self.State=READY

    def switchVideo(self):
        """Open a window to select a new video from the server's list."""
        self.pauseMovie()
        # Cria uma nova janela para seleção de vídeo
        self.switch_window = Toplevel(self.master)
        self.switch_window.title("Selecionar Vídeo")
        self.switch_window.configure(bg="#2c3e50")  # Fundo azul-escuro moderno

        # Cria uma variável para armazenar a seleção do usuário
        self.selected_video = StringVar(self.switch_window)
        self.selected_video.set(self.videoList[0])  # Valor padrão

        # Cria um menu suspenso (OptionMenu) para selecionar o vídeo
        Label(
            self.switch_window,
            text="Escolha o vídeo:",
            font=("Segoe UI", 14),
            bg="#2c3e50",
            fg="#ecf0f1",
        ).pack(pady=10)

        menu = OptionMenu(self.switch_window, self.selected_video, *self.videoList)
        menu.config(
            font=("Segoe UI", 12),
            bg="#34495e",
            fg="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        menu.pack(pady=10)

        # Botão para confirmar a seleção
        Button(
            self.switch_window,
            text="Confirmar",
            command=self.confirmSwitch,
            font=("Segoe UI", 12, "bold"),
            bg="#1abc9c",
            fg="white",
            bd=0,
            relief="flat",
            padx=15,
            pady=5,
        ).pack(pady=10)

    def confirmSwitch(self):
        """Confirma a seleção de vídeo e altera o vídeo no servidor."""
        selected_video = self.selected_video.get()
        
        if selected_video in self.videoList:
            # Atualiza o vídeo selecionado e reconfigura no servidor
            self.fileName = selected_video
            
            if self.videoN == 0:
                # Primeiro vídeo a ser escolhido: envia uma solicitação SETUP
                print("Configurando o primeiro vídeo:", self.fileName)
                self.setupMovie()
                self.videoN = 1  # Atualiza o contador para indicar que um vídeo foi escolhido
            else:
                # Envia uma solicitação SWITCH ao servidor
                print("Mudando para o vídeo:", self.fileName)
                self.oclient.send_udp_request("SWITCH", session_id=self.sessionId)
                self.state=READY

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
            print("Pressed play")
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.oclient.send_udp_request("PLAY", session_id=self.sessionId)
            self.videoN=1
            self.frameNbr=0
            self.state=PLAYING
    
    def listenRtp(self):		
        """Listen for RTP packets."""
        while True:
            try:
                packet = self.rtpSocket.recv(20480)
                temp = json.loads(packet.decode("utf-8"))
                data = base64.b64decode(temp["data"])
                print(f"DATA")

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



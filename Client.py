from tkinter import *

import tkinter.messagebox as tkMessageBox
import socket, threading, sys, traceback, os, json, subprocess, base64
from tkinter.simpledialog import askstring
from PIL import Image, ImageTk

from tkinter import Toplevel, OptionMenu, StringVar, Button, Label, messagebox
from oClient import oClient
import time
import cv2
import numpy as np
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
        self.openRtpPort() 
        self.videoList = self.oclient.get_video_list() 
        self.oclient.run()

        
    def createWidgets(self):
        """Build GUI."""
        # Configurar o layout da janela
        self.master.title("Video Streaming Client")
        self.master.configure(bg="#2c3e50")  # Fundo azul-escuro moderno


        # Rótulo para "loading"
        self.loading_label = Label(
            self.master,
            text="Carregando...",
            font=("Segoe UI", 16, "bold"),
            bg="#34495e",  # Fundo cinza-escuro
            fg="#ecf0f1",  # Texto claro
            relief="flat"
        )
        self.loading_label.grid(row=1, column=0, columnspan=5, pady=10)
        self.loading_label.grid_remove()  # Oculta o rótulo inicialmente

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
        self.start = Button(self.master, text="▶ Play", command=self.playMovie,state=DISABLED, **button_style)
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
            self.atualizar_config_json("filename", self.fileName)
            self.frameNbr=0
            response = self.oclient.send_udp_request("SETUP", file_name=self.fileName)
            self.state=self.READY
            threading.Thread(target=self.listen_rtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.state=self.PLAYING
            
    def atualizar_config_json(self, key, value):
        """
        Atualiza o arquivo config.json com a chave e o valor especificados.
        """
        config_file = "config.json"
        try:
            # Ler o arquivo config.json
            with open(config_file, "r") as f:
                config = json.load(f)
            
            # Atualizar a chave com o novo valor
            config[key] = value
            
            # Escrever de volta no arquivo
            with open(config_file, "w") as f:
                json.dump(config, f, indent=4)
            
            print(f"Configuração '{key}' atualizada para '{value}'.")
        except FileNotFoundError:
            print(f"Arquivo {config_file} não encontrado.")
        except Exception as e:
            print(f"Erro ao atualizar o config.json: {e}")

    def exitClient(self):
        """Teardown button handler."""
        response = self.oclient.send_udp_request("TEARDOWN", session_id=self.sessionId)
        print("Teardown response:", response)
        self.master.destroy()
        os._exit(0)

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.oclient.send_udp_request(
                "PAUSE",
                file_name=self.fileName,
                session_id=self.sessionId,
                frame_number=self.frameNbr
            )
            self.playEvent.set()
            self.start.config(state=NORMAL)
            self.state=self.READY

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
                self.setupMovie()

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
            threading.Thread(target=self.listen_rtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.oclient.send_udp_request(
                "PLAY",
                file_name=self.fileName,
                session_id=self.sessionId,
                frame_number=self.frameNbr
            )
            self.videoN=1
            self.state=self.PLAYING
            self.start.config(state=DISABLED)


    def listen_rtp(self):
        """Listen for RTP packets and process video chunks."""
        print("Listening for RTP packets")
        
        # Configura o timeout do socket RTP para 10 segundos
        self.rtpSocket.settimeout(10)
        self.rtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024 * 10)

        try:
            while True:
                try:
                    # Recebe os dados do socket RTP
                    data, addr = self.rtpSocket.recvfrom(20480)
                    if data:
                        # Decodifica o pacote JSON
                        json_packet = json.loads(data.decode("utf-8"))
                        
                        # Extrai o campo 'data' e decodifica o base64
                        encoded_data = json_packet.get("data")
                        if not encoded_data:
                            raise ValueError("No 'data' field in received packet")

                        # Decodifica o base64 para recuperar o pacote RTP
                        rtp_data = base64.b64decode(encoded_data)

                        # Decodifica o pacote RTP
                        rtp_packet = RtpPacket()
                        rtp_packet.decode(rtp_data)

                        # Obtém o número do frame do pacote atual
                        curr_frame_nbr = rtp_packet.seqNum()
                        print(f"Current Seq Num: {curr_frame_nbr}")

                        if curr_frame_nbr > self.frameNbr:  # Descartar pacotes atrasados
                            self.frameNbr = curr_frame_nbr

                            # Extrai o payload (frame codificado) do pacote
                            chunk = rtp_packet.getPayload()
                            
                            # Verifique se o payload não está vazio ou corrompido
                            if chunk is None or len(chunk) == 0:
                                print(f"Frame {curr_frame_nbr} está vazio ou corrompido. Ignorando...")
                                continue

                            # Decodifica e processa o frame
                            self.process_video_chunk(chunk)
                        else:
                            print(f"Pacote atrasado ou duplicado: {curr_frame_nbr}. Ignorando...")

                except socket.timeout:
                    # Timeout atingido: 10 segundos sem pacotes recebidos
                    print("Timeout: Nenhum pacote recebido nos últimos 10 segundos. Fechando o socket...")
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break

                except Exception as e:
                    print(f"Error while receiving RTP packets: {e}")

                    # Para de escutar se PAUSE ou TEARDOWN forem requisitados
                    if self.playEvent.isSet():
                        break

                    # Fecha o socket RTP ao receber TEARDOWN
                    if self.teardownAcked == 1:
                        self.rtpSocket.shutdown(socket.SHUT_RDWR)
                        self.rtpSocket.close()
                        break
        except Exception as e:
            print(f"Critical error in RTP listener: {e}")


    def process_video_chunk(self, chunk):
        """Decode and process the video chunk."""
        try:
            # Decodifica o chunk para criar o frame
            frame = cv2.imdecode(np.frombuffer(chunk, np.uint8), cv2.IMREAD_COLOR)

            # Verifica se o frame foi decodificado corretamente
            if frame is None:
                raise ValueError("Failed to decode frame from chunk (invalid format)")

            # Atualiza a interface com o novo frame
            self.update_movie(frame)
        except Exception as e:
            print(f"Error processing video chunk: {e}")

    def update_movie(self, frame):
        """Display frame in the GUI."""
        try:
            # Converte o frame do OpenCV para uma imagem PIL para uso no Tkinter
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            photo = ImageTk.PhotoImage(image)

            # Atualiza o label da interface
            self.label.configure(image=photo, height=288)
            self.label.image = photo
        except Exception as e:
            print(f"Error updating movie display: {e}")


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
            self.rtpSocket.bind((self.get_myIP(), self.rtpPort))
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







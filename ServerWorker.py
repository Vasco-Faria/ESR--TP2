import os
from random import randint
import cv2
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket

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
    video_folder = "Videos"  # Path to the folder containing videos
    
    def __init__(self, clientInfo):
        self.clientInfo = clientInfo
        self.sendVideoList()
        
    def run(self):
        threading.Thread(target=self.recvRtspRequest).start()
        
    def sendVideoList(self):
        """Envia a lista de vídeos para o cliente assim que ele se conecta."""
        videos = os.listdir(self.video_folder)  # Lista arquivos na pasta
        video_list = "\n".join(videos)
        connSocket = self.clientInfo['rtspSocket'][0]
        connSocket.sendall(f"AVAILABLE_VIDEOS:\n{video_list}".encode())
    
    def recvRtspRequest(self):
        """Receive RTSP request from the client."""
        connSocket = self.clientInfo['rtspSocket'][0]
        while True:            
            data = connSocket.recv(256)
            if data:
                print("Data received:\n" + data.decode("utf-8"))
                self.processRtspRequest(data.decode("utf-8"))
    
    def processRtspRequest(self, data):
        """Process RTSP request sent from the client."""
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
                self.replyRtsp(self.CON_ERR_500, seq)

    
    def sendRtp(self):
        """Send RTP packets over UDP."""
        videoStream = self.clientInfo['videoStream']
        fps = videoStream.cap.get(cv2.CAP_PROP_FPS)
        delay = 1 / fps 
        
        while True:
            self.clientInfo['event'].wait(0.05)
            if self.clientInfo['event'].isSet(): 
                break 
            data = videoStream.nextFrame()
            if data is not None and len(data) > 0: 
                frameNumber = videoStream.frameNbr()
                try:
                    address = self.clientInfo['rtspSocket'][1][0]
                    port = int(self.clientInfo['rtpPort'])
                    print("Size of data: ", len(data))
                    for i in range(0, len(data), self.PACKET_SIZE):
                        chunk = data[i:i+self.PACKET_SIZE]
                        print("Size of chunk: ", len(chunk))
                        self.clientInfo['rtpSocket'].sendto(self.makeRtp(chunk, frameNumber), (address, port))
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
            reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
            connSocket = self.clientInfo['rtspSocket'][0]
            connSocket.send(reply.encode())
        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
        elif code == self.CON_ERR_500:
        	print("500 CONNECTION ERROR")

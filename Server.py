import sys, socket

from ServerWorker import ServerWorker
from Overlay_Builder import Overlay_Builder

class Server:	
	
	def main(self):
		try:
			SERVER_PORT = int(sys.argv[1])
      
		except:
			print("[Usage: Server.py Server_port]\n")
		overlay_builder = Overlay_Builder(SERVER_PORT)
		overlay_builder.run()

		rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		rtspSocket.bind(('', SERVER_PORT))
		rtspSocket.listen(5)

		
		#while True:
		clientInfo = {}
		#clientInfo['rtspSocket'] = rtspSocket.accept()
		ServerWorker(clientInfo).run()

if __name__ == "__main__":
	(Server()).main()



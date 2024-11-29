import sys, socket

from ServerWorker import ServerWorker
from Overlay_Builder import Overlay_Builder
from NetworkFunctions import getSelfIP

class Server:
	
	def main(self):
		try:
			SERVER_PORT = int(sys.argv[1])
      
		except:
			print("[Usage: Server.py Server_port]\n")
		
		hostIP = getSelfIP()
		overlay_builder = Overlay_Builder(SERVER_PORT, hostIP)
		overlay_builder.run()
		pop_list = overlay_builder.computePop()
		print(f"POP's: {pop_list}")

		rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		rtspSocket.bind(('', SERVER_PORT))
		rtspSocket.listen(5)

		print("Server On! Port: " + str(SERVER_PORT))
		rtspSocket.listen(5)  
		
		ServerWorker(pop_list, overlay_builder.downstream_neighbours ).run()

if __name__ == "__main__":
	(Server()).main()



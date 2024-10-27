import socket
import json
import sys

class oNode: 
    def __init__(self, host, port=6010):
        self.host = host
        self.port = port
        self.neighbours = []
        self.run()

    
    def run(self): 
        print("RUNING!")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            print(f"Node listening on {self.host}:{self.port}")

            while True: 
                conn, addr = s.accept()
                print("Connected!")

                #data = conn.recv(1042).decode('utf-8')

if __name__ == "__main__":
	try:
		selfIP = sys.argv[1]
	except:
		print("[Usage: oNode.py Self_IP]\n")	
	
	# Create a new client
	node = oNode(selfIP)
	node.run()
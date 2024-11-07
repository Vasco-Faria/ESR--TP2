import socket
import json
import sys
import subprocess #TEMPORARY

class oNode: 
    def __init__(self, host, port=6010):
        self.host = host
        self.port = port
        self.neighbours = []
        self.run()

    #TEMPORARY
    def ping_neighbor(self, neighbor_ip):
        """Ping the neighbor and return True if the ping is successful."""
        try:
            # Ping the neighbor (This is for Linux/Mac, adjust for Windows)
            print(f"Pinging node {neighbor_ip}")
            result = subprocess.run(['ping', '-c', '1', neighbor_ip], stdout=subprocess.PIPE)
            return result.returncode == 0
        except Exception as e:
            print(f"Ping to {neighbor_ip} failed: {e}")
            return False

    def handle_data(self, conn):
        try:
            data = conn.recv(1024).decode('utf-8')

            if data:
                neighbours_info = json.loads(data)
                self.neighbours = neighbours_info.get("neighbours", [])
                print(f"Received neighbors: {self.neighbours}")

        except json.JSONDecodeError:
            print("Received invalid JSON data.")
        except Exception as e:
            print(f"Error handling data: {e}")
    
    def run(self): 
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            print(f"Node listening on {self.host}:{self.port}")

            while True: 
                conn, addr = s.accept()
                print("Connected!")
                self.handle_data(conn)

                ping_results = {}
                for neighbour in self.neighbours: 
                    result  = self.ping_neighbor(neighbour)
                    ping_results[neighbour] = "reachable" if result else "unreachable"

                conn.sendall(f"Results: {ping_results}".encode('utf-8'))
                conn.close()

if __name__ == "__main__":
	try:
		selfIP = sys.argv[1]
	except:
		print("[Usage: oNode.py Self_IP]\n")	
	
	# Create a new client
	node = oNode(selfIP)
	node.run()
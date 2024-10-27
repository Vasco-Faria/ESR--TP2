import socket 
import json

class Overlay_Builder: 
    def __init__(self, host='10.0.5.10', config_file='overlay.build.json', port=6010):
        self.host = host
        self.port = port
        self.config_file = config_file
        self.overlay = {}
        self.overlay['neighbours'] = {}
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_file) as json_file:
                data = json.load(json_file)
                self.parse_config(data)
        
        except FileNotFoundError:
            print(f"File {self.config_file} not found")
        except json.JSONDecodeError:
            print(f"File {self.config_file} is not a valid JSON file")

    def parse_config(self,data):
        for key in data: 
            if key == self.host:
                self.overlay['neighbours']['self'] = data[key]
            else: 
                self.overlay['neighbours'][key] = data[key]
        print(f"Overlay: {self.getOverlay()}")

    def getOverlay(self):
        return self.overlay
    
    def getNeighbours(self, host):
        return self.getOverlay()['neighbours'][host]
    
    def run(self):
        print("RUNNING SERVER")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            for neighbour_node in self.getNeighbours('self'):
                try:
                    print(f"Connecting to {neighbour_node}:{self.port}")
                    s.connect((neighbour_node, self.port))
                    neighbour_data = json.dumps({"neighbours": self.getNeighbours(neighbour_node)})
                    s.sendall(neighbour_data.encode('utf-8'))
                    print(f"Sent neighbours!")
                
                    log_data = s.recv(1024).decode('utf-8')
                    print(f"Log: {log_data}")
                    
                except socket.error as e:
                    print(f"Error connecting to {neighbour_node}: {e}")
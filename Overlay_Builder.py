import socket 
import json

class Overlay_Builder: 
    def __init__(self, stream_port, host='10.0.5.10', config_file='overlay.build.json', manage_port=6010):
        self.IP = host
        self.stream_port = stream_port
        self.manage_port = manage_port
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
            if key == self.IP:
                self.overlay['neighbours']['self'] = data[key]
            else: 
                self.overlay['neighbours'][key] = data[key]
        print(f"Overlay: {self.getOverlay()}")

    def getOverlay(self):
        return self.overlay
    
    def getNeighbours(self, host):
        return self.getOverlay()['neighbours'][host] if host in self.getOverlay()['neighbours'].keys() else []
    
    def build_initPacket(self, nodeIP):
        return {
            "type": "init",
            "from": self.IP,
            "data" : {
                "downstream_neighbours": self.getNeighbours(nodeIP),
                "stream_port": self.stream_port
            }}

    
    def run(self):
        print("RUNNING SERVER")
        for neighbour_node in self.getNeighbours('self'):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    print(f"Connecting to {neighbour_node}:{self.manage_port}")
                    s.connect((neighbour_node, self.manage_port))
                    packet = json.dumps(self.build_initPacket(neighbour_node))
                    s.sendall(packet.encode('utf-8'))
                    print(f"Sent neighbours!")
                
                    log_data = s.recv(1024).decode('utf-8')
                    print(f"Log: {log_data}")
                    
                except socket.error as e:
                    print(f"Error connecting to {neighbour_node}: {e}")
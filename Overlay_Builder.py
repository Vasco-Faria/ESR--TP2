import socket, json, os

class Overlay_Builder: 
	def __init__(self, stream_port, host, config_file='overlay.build.json', manage_port=6010):
		self.IP = host
		self.stream_port = stream_port
		self.manage_port = manage_port
		self.config_file = config_file
		self.downstream_neighbours = set()
		self.overlay = {}
		self.overlay['neighbours'] = {}
		self.load_config()
		

	def load_config(self):
		try:
			with open(self.config_file) as json_file:
				data = json.load(json_file)
				self.overlay['neighbours'] = data

				print(f"Overlay: {self.overlay['neighbours']}")
		
		except FileNotFoundError:
			print(f"File {self.config_file} not found")
		except json.JSONDecodeError:
			print(f"File {self.config_file} is not a valid JSON file")

	def getOverlay(self):
		return self.overlay
	
	def getNeighbours(self, host):
		return self.getOverlay()['neighbours'][host] if host in self.getOverlay()['neighbours'].keys() else []
	
	def computePop(self):
		temp = {}
		self.pop = []
		
		for (server_node, node_list) in self.overlay['neighbours'].items():
			if server_node != 'self': 
				temp[server_node] = 1
					
			for node in node_list:
				if node not in temp:
					temp[node] = 0
		
		for node in temp: 
			if temp[node] == 0: 
				self.pop.append(node)

		return self.pop
	
	def build_initPacket(self, neighbours_list):

		return {
			"type": "overlay_setup",
			"from": self.IP,
			"data" : {
				"overlay_conn": json.dumps(neighbours_list),
				"stream_port": self.stream_port
			}}

	def sendVideoList(self):
		"""Envia a lista de vídeos para o cliente assim que ele se conecta."""
		videos = os.listdir(self.videoFolderPath)  # Lista arquivos na pasta
		video_list = "\n".join(videos)

		#TODO Change the communication to send to POP's
		connSocket = self.clientInfo['rtspSocket'][0]
		connSocket.sendall(f"AVAILABLE_VIDEOS:\n{video_list}".encode())
	
	def run(self):
		print("RUNNING SERVER")
		self.downstream_neighbours = self.overlay['neighbours'].pop(self.IP)
		for node in self.downstream_neighbours:
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
				try:
					print(f"Connecting to {node}:{self.manage_port}")
					s.connect((node, self.manage_port))
					packet = json.dumps(self.build_initPacket(self.overlay['neighbours']))
					s.sendall(packet.encode('utf-8'))
					print(f"Sent neighbours!")
				
					log_data = s.recv(1024).decode('utf-8')
					print(f"Log: {log_data}")
					s.close()
					
				except socket.error as e:
					print(f"Error connecting to {node}: {e}")
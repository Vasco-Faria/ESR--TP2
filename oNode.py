import socket
import json
import sys

class oNode: 
	def __init__(self, host, port=6010):
		self.IP = host
		self.port = port
		self.upstream_neighbours = []
		self.downstream_neighbours = []
		self.run()

	def handle_data(self, packet):
		try:
			data = json.loads(packet)

			if data["type"] == "init":
				self.downstream_neighbours.extend(data["data"]["downstream_neighbours"])
				print(f"Upstream neighbours: {self.downstream_neighbours}")
				self.checkNeighboursLink()

		except json.JSONDecodeError:
			print("Received invalid JSON data.")
		except Exception as e:
			print(f"Error handling data: {e}")
		
	def checkNeighboursLink(self):
		report = []
		for neighbour_node in self.downstream_neighbours:
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
				try:
					print(f"Connecting to {neighbour_node}")
					s.connect((neighbour_node, 6010))
					packet = json.dumps({"type": "checkcomm", "from": self.IP, "data": {}})
					s.sendall(packet.encode('utf-8'))
					print(f"Sent neighbours!")
					s.close()

				except socket.error as e:
					print(f"Error connecting to {neighbour_node}: {e}")
					report.append(neighbour_node)

		return report
	
	def build_ReportPacket(self, array):
		if len(array) > 0:
			return {
				"type":  "init_resp",
				"from": self.IP,
				"data": {
					"error_nodes": array
				}
			}
		
		else:
			return {
				"type":  "init_resp",
				"from": self.IP,
				"data": {}
			}

	def run(self):
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
			s.bind((self.IP, self.port))
			s.listen()
			print(f"Node listening on {self.IP}:{self.port}")

			while True: 
				conn, addr = s.accept()
				data = conn.recv(1024).decode('utf-8')

				self.handle_data(data)
				report_packet = self.build_ReportPacket(self.checkNeighboursLink())

				conn.sendall(json.dumps(report_packet).encode("utf-8"))
				conn.close()

if __name__ == "__main__":
	try:
		selfIP = sys.argv[1]
	except:
		print("[Usage: oNode.py Self_IP]\n")	
	
	# Create a new client
	node = oNode(selfIP)
	node.run()
import socket, time, json, subprocess, threading

class oClient:

    def __init__(self,config_file="config.json"):

        #ler config.json
        with open(config_file,'r') as f:
            config=json.load(f)

        #infos config
        self.server_address = config['server_address']
        self.server_port = config['server_port']
        self.pop_check_interval = config['pop_check_interval'] #intervalo para monitorar POPs
        self.timeout = config['timeout'] #timeout udp

        
        # Criar o socket UDP 
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.pop_port=5050
        self.pop_list = []
        self.best_pop=None
        self.current_pop=None
        
        self.get_pops_list()

        


    def get_pops_list(self):
        '''Obter lista de PoPs e lista de vídeos do servidor via UDP'''
        try:
            # Solicitar a lista de PoPs
            print("Mandar para:", self.server_address,self.server_port)
            self.socket.sendto(b"GET_POP_LIST", (self.server_address, self.server_port))
            response, _ = self.socket.recvfrom(4096)
            self.pop_list = json.loads(response.decode())
            print("Lista de PoPs recebida:", self.pop_list)

            self.select_initial_pop()

        except socket.timeout:
            print("Timeout: Não foi possível obter a lista de PoPs do servidor.")

    
        
    def get_video_list(self):
        '''Solicita a lista de vídeos ao servidor via UDP e retorna a lista de vídeos.'''
        try:
           
            self.socket.sendto(b"GET_VIDEO_LIST", (self.server_address, self.server_port))
            response, _ = self.socket.recvfrom(4096)
            
           
            response_str = response.decode().replace('[', '').replace(']', '').replace('"','')
            
           
            video_list = response_str.split(',')
            
            
            video_list = [video.strip() for video in video_list if video.strip()]
            
            print(f"Lista de vídeos processada: {video_list}")

            
            return video_list
        
        except Exception as e:
            print(f"Erro ao obter a lista de vídeos: {e}")
            return []


    def switch_pop(self, new_pop):
        '''Troca para o PoP especificado e atualiza config.json'''
        print(f"Troca para o PoP {new_pop['name']} ({new_pop['ip']}) devido à disponibilidade de conteúdo.")
        self.current_pop = new_pop
        


    def measure_latency(self, ip):
        '''Medir a latência de um PoP dado seu IP.'''
        try:
            result = subprocess.run(["ping", "-c", "4", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output = result.stdout.decode()
            # Extrair a latência média
            for line in output.splitlines():
                if "avg" in line:
                    latency = float(line.split('/')[-3])
                    return latency
            return float('inf')  # Caso não consiga obter a latência
        except Exception as e:
            print(f"Erro ao medir latência para {ip}: {e}")
            return float('inf')

    def select_initial_pop(self):
        '''Seleciona o PoP inicial com a menor latência e define como current_pop.'''
        latencies = {}
        for ip in self.pop_list:
            latency = self.measure_latency(ip)
            latencies[ip] = latency
            print(f"Latência para o PoP {ip}: {latency} ms")

        # Ordena os IPs pela menor latência
        sorted_pops = sorted(latencies.items(), key=lambda x: x[1])
        self.current_pop = sorted_pops[0][0] if sorted_pops else None

        if self.current_pop:
            print(f"PoP inicial selecionado: {self.current_pop} com latência {latencies[self.current_pop]} ms")
        else:
            print("Nenhum PoP disponível para seleção inicial.")



    def monitor_current_pop(self):
        '''Monitorar a conexão com o current_pop para verificar a sua disponibilidade'''
        while True:
            if self.current_pop:
                latency = self.measure_latency(self.current_pop['ip'])
                print(f"Latência atual para o current_pop {self.current_pop['name']} ({self.current_pop['ip']}): {latency} ms")

                if latency == float('inf'):
                    print(f"Conexão perdida com {self.current_pop['name']}. Tentando reconectar...")
                    self.select_initial_pop()  # Re-seleciona o PoP com a menor latência

            else:
                print("Nenhum current_pop definido para monitorar.")

            time.sleep(self.pop_check_interval)



#Client functions 

    def send_udp_request(self, request_type, file_name=None, session_id=None):
        '''Enviar uma solicitação UDP ao current_pop'''
        if not self.current_pop:
            print("Erro: current_pop não está definido.")
            return None

        # Solicitações
        request_data = {
            "SETUP": f"SETUP {file_name} UDP/1.0\n",
            "PLAY": f"PLAY UDP/1.0\nSession: {session_id}\n",
            "PAUSE": f"PAUSE UDP/1.0\nSession: {session_id}\n",
            "TEARDOWN": f"TEARDOWN UDP/1.0\nSession: {session_id}\n",
            "SWITCH": f"SWITCH {file_name} UDP/1.0\nSession: {session_id}\n"
        }

        request_message = request_data.get(request_type)
        if request_message:
            packet = json.dumps({"type": "request", "data": request_message})
            self.socket.sendto(packet.encode("utf-8"), (self.current_pop, self.pop_port))
            print(f"Enviada solicitação {request_type}: {packet}")
            print(self.pop_port)
            print(self.current_pop)

            # Receber resposta
            try:
                response, _ = self.socket.recvfrom(4096)
                response_data = json.loads(response.decode())
                
                # Processar a resposta detalhada
                status = response_data.get("status")
                code = response_data.get("code")
                message = response_data.get("message", "")
                data = response_data.get("data", {})

                if status == "success":
                    print(f"Sucesso ({code}): {message}")
                    return data
                elif status == "error":
                    print(f"Erro ({code}): {message}")
                    return None
                else:
                    print(f"Resposta inesperada ({code}): {message}")
                    return None

            except socket.timeout:
                print(f"Timeout: Não foi possível receber resposta para {request_type}")
                return None
            except json.JSONDecodeError:
                print("Erro: A resposta recebida não está no formato JSON esperado.")
                return None
        else:
            print("Tipo de solicitação UDP inválido.")
            return None



if __name__ == '__main__':
    client = oClient() 
    client.monitor_connection()

    monitor_thread = threading.Thread(target=client.monitor_connection)
    monitor_thread.daemon = True
    monitor_thread.start()

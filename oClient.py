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


        
    def run(self):
        listen_thread = threading.Thread(target=self.listen_for_responses)
        listen_thread.start()

        monitor_thread = threading.Thread(target=self.monitor_current_pop)
        monitor_thread.start()

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
        '''Monitorar a latência de todos os PoPs e realizar o switch se necessário.'''
        while True:
            if self.pop_list:
                best_latency = float('inf')
                best_pop = None

                # Medir latência de todos os PoPs
                for ip in self.pop_list:
                    latency = self.measure_latency(ip)
                    print(f"Latência para o PoP {ip}: {latency} ms")

                    if latency < best_latency:
                        best_latency = latency
                        best_pop = ip

                # Se o PoP com melhor latência não for o atual, faz o switch
                if best_pop != self.current_pop:
                    print(f"Switching para o PoP {best_pop} com latência {best_latency} ms")
                    self.switch_pop(best_pop)

            else:
                print("Nenhum PoP disponível para monitorar.")

            # Esperar o próximo ciclo de monitoramento
            time.sleep(self.pop_check_interval)

    def switch_pop(self, new_pop):
        '''Troca para o PoP especificado e atualiza o current_pop.'''
        self.cancelar_transmissao()
        print(f"Troca para o PoP {new_pop} devido à melhor latência.")
        self.current_pop = new_pop
        file_name = self.obter_valor_config_json("filename")
        if file_name != "nada":
            self.send_udp_request("SETUP",file_name=filename)


    def obter_valor_config_json(self, key):
        """
        Obtém o valor de uma chave do arquivo config.json.
        """
        config_file = "config.json"
        try:
            # Ler o arquivo config.json
            with open(config_file, "r") as f:
                config = json.load(f)
            
            # Retornar o valor da chave
            return config.get(key)
        except FileNotFoundError:
            print(f"Arquivo {config_file} não encontrado.")
            return None
        except Exception as e:
            print(f"Erro ao ler o config.json: {e}")
            return None

    def cancelar_transmissao(self):
        """Envia uma mensagem UDP ao PoP especificado para cancelar a transmissão."""
        mensagem = "CANCEL"
        self.send_udp_request(mensagem) 
        print(f"Cancelamento enviado para o PoP.")

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
            "SWITCH": f"SWITCH {file_name} UDP/1.0\nSession: {session_id}\n",
            "CANCEL": f"CANCEL UDP/1.0\nSession: {session_id}\n"
        }

        request_message = request_data.get(request_type)
        if request_message:
            packet = json.dumps({"type": "request","command": request_type,"data": request_message})
            self.socket.sendto(packet.encode("utf-8"), (self.current_pop, self.pop_port))
            print(f"Enviada solicitação {request_type}: {packet}")
        else:
            print("Tipo de solicitação UDP inválido.")
            return None


    def listen_for_responses(self):
        '''Escutar por respostas do PoP e processá-las.'''
        print("Começar a escutar...")

        while True:
            try:
                response, _ = self.socket.recvfrom(4096)
                print(f"Pacote recebido: {response}")  # Verifica o pacote recebido
                response_data = json.loads(response.decode("utf-8"))
                print(f"Resposta recebida do PoP: {response_data}")

                # Verificar se a resposta é um dicionário ou lista
                if isinstance(response_data, dict):
                    # Processar resposta como um dicionário
                    if response_data.get("status") == "success":
                        print(f"Sucesso: {response_data.get('message')}")
                    else:
                        print(f"Erro: {response_data.get('message')}")
                elif isinstance(response_data, list):
                    # Processar resposta como uma lista
                    print(f"Resposta recebida como lista: {response_data}")
                    # Aqui você pode decidir como processar a lista
                else:
                    print(f"Resposta com formato desconhecido: {response_data}")
            except socket.timeout:
                # Não há resposta dentro do tempo limite
                continue
            except json.JSONDecodeError:
                print("Resposta inválida recebida do PoP.")
            except Exception as e:
                print(f"Erro ao processar resposta: {e}")



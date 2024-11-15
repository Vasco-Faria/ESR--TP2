import socket
import json
import time


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
        self.socket.settimeout(self.timeout)



        self.pop_list = []
        self.get_pops_list()


    def get_pops_list(self):
        '''Obter pops apartir do servidor'''
        try:
            self.socket.sendto(b"GET_POP_LIST",(self.server_address,self.server_port))
            respons,_= self.socket.recvfrom(1024)
            self.pop_list=json,loads(response.decode())
            print("Lista de POPs recebido: ",self.pop_list)

            self.save_pops_list_to_file()

            self.close()

        except socket.timeout:
            print("Timeout: Não foi possível obter a lista de PoPs do servidor.")



    def save_pops_list_to_file(self):
        '''Escrever pops no config.json '''
        try:
            with open(self.config_file,'r') as f:
                config=json.load(f)

            config['pop_list'] = self.pop_list

            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            print("Lista de PoPs salva em config.json.")

        except IOError:
            print("Erro ao salvar a lista de PoPs no arquivo JSON.")



if __name__ == '__main__':
    client = oClient() 
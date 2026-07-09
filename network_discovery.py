import socket
import threading
import time
import json
import sys

UDP_BROADCAST_PORT = 50005
BUFFER_SIZE = 1024

class NexusDistributedNode:
    def __init__(self, node_id, tcp_port):
        self.node_id = node_id
        self.tcp_port = tcp_port
        self.active_nodes = {}  # {node_id: {"ip": ip, "role": role, "last_seen": ts}}
        self.role = "FOLLOWER"   # Todo nó nasce como Follower
        self.running = True

        # Socket UDP Broadcast
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.bind(('', UDP_BROADCAST_PORT))

    def start_beacon(self):
        """Dispara a presença e o papel atual do nó para a rede."""
        def beacon_loop():
            print(f"📡 [Beacon] Nó {self.node_id} iniciado como [{self.role}]...")
            while self.running:
                try:
                    payload = {
                        "node_id": self.node_id,
                        "tcp_port": self.tcp_port,
                        "role": self.role
                    }
                    message = json.dumps(payload).encode('utf-8')
                    self.udp_socket.sendto(message, ('255.255.255.255', UDP_BROADCAST_PORT))
                except Exception as e:
                    print(f"⚠️ [Beacon Error]: {e}")
                time.sleep(2)
        threading.Thread(target=beacon_loop, daemon=True).start()

    def start_listener(self):
        """Escuta a rede e computa a topologia e papéis dos outros nós."""
        def listener_loop():
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(BUFFER_SIZE)
                    payload = json.loads(data.decode('utf-8'))
                    
                    r_id = payload["node_id"]
                    r_port = payload["tcp_port"]
                    r_role = payload["role"]
                    
                    if r_id == self.node_id:
                        continue
                        
                    self.active_nodes[r_id] = {
                        "ip": addr[0],
                        "port": r_port,
                        "role": r_role,
                        "last_seen": time.time()
                    }
                except Exception as e:
                    if self.running:
                        print(f"⚠️ [Listener Error]: {e}")
        threading.Thread(target=listener_loop, daemon=True).start()

    def check_election_logic(self):
        """Avaliador contínuo de liderança (Algoritmo do Bully adaptado)"""
        while self.running:
            time.sleep(1)
            now = time.time()
            
            # 1. Limpa nós defuntos (Timeout de 5 segundos)
            to_remove = [n_id for n_id, info in self.active_nodes.items() if now - info["last_seen"] > 5]
            for n_id in to_remove:
                print(f"🚨 [Rede] Nó {n_id} caiu por Timeout.")
                del self.active_nodes[n_id]

            # 2. Verifica se existe algum MASTER ativo na rede
            master_exists = any(info["role"] == "MASTER" for info in self.active_nodes.values())
            
            if not master_exists and self.role != "MASTER":
                # Se não há MASTER, quem tem o maior ID deve assumir
                higher_nodes = [n_id for n_id in self.active_nodes.keys() if n_id > self.node_id]
                
                if not higher_nodes:
                    # Se não há ninguém maior vivo na lista, eu me autodeclaro MASTER
                    print(f"👑 [Eleição] Sem líder detectado. Nó {self.node_id} assume como [MASTER]!")
                    self.role = "MASTER"
            
            # 3. Resolução de conflito: se dois acham que são MASTER, o de menor ID cede
            if self.role == "MASTER":
                for n_id, info in self.active_nodes.items():
                    if info["role"] == "MASTER" and n_id > self.node_id:
                        print(f"🏳️ [Conflito] Nó maior {n_id} também é MASTER. {self.node_id} cede e vira [FOLLOWER].")
                        self.role = "FOLLOWER"
                        break

    def stop(self):
        self.running = False
        self.udp_socket.close()
        print("🛑 Nó distribuído encerrado.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python network_discovery.py <NODE_ID> <TCP_PORT>")
        sys.exit(1)
        
    node = NexusDistributedNode(node_id=sys.argv[1], tcp_port=int(sys.argv[2]))
    node.start_beacon()
    node.start_listener()
    
    try:
        node.check_election_logic()
    except KeyboardInterrupt:
        node.stop()

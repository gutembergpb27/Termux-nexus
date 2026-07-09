import time

class ClusterRoleManager:
    def __init__(self, node_name="Node-Edge"):
        self.node_name = node_name
        self.current_role = "FOLLOWER" # Papéis possíveis: FOLLOWER, CANDIDATE, LEADER
        self.last_leader_ping = time.time()

    def update_leader_presence(self):
        """Chame isto sempre que um ping válido do Líder chegar via rede."""
        self.last_leader_ping = time.time()
        if self.current_role != "FOLLOWER":
            print(f"🔄 [Cluster] Antigo líder reapareceu. Retornando '{self.node_name}' para FOLLOWER.")
            self.current_role = "FOLLOWER"

    def check_liveness(self, timeout=4.0):
        """Avalia se o Líder sumiu. Se sim, assume papel de candidato a líder."""
        if self.current_role == "LEADER":
            return False # Se já for o líder, não faz checagem de timeout de si mesmo
            
        if time.time() - self.last_leader_ping > timeout:
            print(f"🚨 [Cluster] Silêncio do Líder detectado! Promovendo '{self.node_name}' para CANDIDATE/LEADER.")
            self.current_role = "LEADER"
            return True
        return False

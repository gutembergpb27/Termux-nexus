import re

with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# 1. Injeta propriedades criptográficas no construtor do Core
old_init = "        self.block_counter = 0"
new_init = """        self.block_counter = 0
        self.passport = None
        self.passport_ts = 0.0
        self.hub_signature = None"""

if old_init in code and "self.passport" not in code:
    code = code.replace(old_init, new_init)

# 2. Atualiza a thread de polling para extrair os dados de segurança do CA-Hub
old_polling = """                    if res_body.get("status") == "ACCEPTED":
                        raw_peers = res_body.get("active_peers", {})"""

new_polling = """                    if "ACCEPTED" in res_body.get("status", ""):
                        self.passport = res_body.get("your_passport")
                        self.passport_ts = res_body.get("passport_ts", 0.0)
                        self.hub_signature = res_body.get("hub_signature")
                        raw_peers = res_body.get("active_peers", {})"""

if old_polling in code:
    code = code.replace(old_polling, new_polling)

# 3. Injeta o passaporte no cabeçalho das propostas transacionais TCP
old_proposal = """                    payload = {
                        "origin": self.node_id, "content": text_message,
                        "prev_hash": prev_hash, "current_hash": current_hash
                    }"""

new_proposal = """                    payload = {
                        "origin": self.node_id, "content": text_message,
                        "prev_hash": prev_hash, "current_hash": current_hash,
                        "auth_passport": self.passport,
                        "auth_ts": self.passport_ts
                    }"""

if old_proposal in code:
    code = code.replace(old_proposal, new_proposal)

with open("nexus_distributed_core.py", "w") as f:
    f.write(code)
print("✔ [Patch v2000] Core móvel atualizado com suporte a passaportes criptográficos!")

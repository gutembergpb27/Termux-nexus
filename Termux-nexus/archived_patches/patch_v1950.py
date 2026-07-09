import re

with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# Substituição cirúrgical do método de envio para suportar roteamento híbrido local/remoto
old_block = """            target_ip = info["ip"]
            target_port = info["port"]"""

new_block = """            # Detecção inteligente: Se estiver na mesma rede/dispositivo, usa a porta interna
            target_ip = info["ip"]
            target_port = info["internal_tcp_port"] if info["ip"] == self.rendezvous_url.split("//")[1].split(":")[0] or info["ip"] in ["127.0.0.1", "localhost"] else info["port"]"""

if old_block in code:
    code = code.replace(old_block, new_block)
    with open("nexus_distributed_core.py", "w") as f:
        f.write(code)
    print("✔ [Patch v1950] Roteamento local/WAN corrigido com sucesso!")
else:
    print("❌ Trecho original não localizado. Arquivo mantido.")

with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# Substitui a linha problemática por um método .get() totalmente seguro
old_line = 'target_port = info["internal_tcp_port"] if info["ip"] == self.rendezvous_url.split("//")[1].split(":")[0] or info["ip"] in ["127.0.0.1", "localhost"] else info["port"]'

new_line = 'target_port = info.get("internal_tcp_port", 8080) if info["ip"] == self.rendezvous_url.split("//")[1].split(":")[0] or info["ip"] in ["127.0.0.1", "localhost"] else info["port"]'

if old_line in code:
    code = code.replace(old_line, new_line)
    with open("nexus_distributed_core.py", "w") as f:
        f.write(code)
    print("✔ [Hotfix v1950] Tratamento de erro com .get() inserido no Core!")
else:
    # Se o patch anterior mudou o recuo, reescrevemos o bloco de portas de forma limpa
    print("⚠️ Linha exata não achada. Aplicando substituição estrutural do bloco...")
    import re
    pattern = r'target_port = info\["internal_tcp_port"\].*?else info\["port"\]'
    code = re.sub(pattern, new_line, code)
    with open("nexus_distributed_core.py", "w") as f:
        f.write(code)
    print("✔ [Hotfix v1950] Bloco reestruturado com segurança!")

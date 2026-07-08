with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# Força a inicialização do timestamp de controle no construtor do nó se ele não existir
if "self.init_time = time.time()" not in code:
    code = code.replace(
        "self.role = role",
        "self.role = role\n        self.init_time = time.time()\n        self.last_master_heartbeat = time.time()"
    )

with open("nexus_distributed_core.py", "w") as f:
    f.write(code)

print("✔ [Maturidade v2100] Fallback de vacância inicial injetado com sucesso!")

with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# Alvo: Início da thread de polling assíncrona
target = "def async_polling_loop(self):"

failover_force = """def async_polling_loop(self):
        # Inicialização forçada v2100 para evitar estado órfão inicial
        if not hasattr(self, 'last_master_heartbeat'):
            self.last_master_heartbeat = time.time()"""

if "last_master_heartbeat = time.time()" not in code:
    code = code.replace(target, failover_force)
    with open("nexus_distributed_core.py", "w") as f:
        f.write(code)
    print("👑 [Sucesso] Fallback de tempo injetado diretamente na thread principal!")
else:
    print("⚠️ Fallback já presente ou injetado.")

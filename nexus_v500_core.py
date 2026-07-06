import sys
import os
import time
import json

# ==========================================
# --- CONFIGURAÇÃO DINÂMICA DA MALHA (v1400) ---
# ==========================================

# Parâmetros padrão caso o script seja executado isoladamente
DEFAULT_PORT = 8080
DEFAULT_ROLE = "MASTER"

# Captura de argumentos passados via Orchestrator
NODE_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
INITIAL_ROLE = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ROLE

print(f"⚡ [Core Boot] Inicializando nó na porta {NODE_PORT} como [{INITIAL_ROLE}]...")

# ==========================================
# --- INICIALIZAÇÃO DOS MÓDULOS COM PORTA DINÂMICA ---
# ==========================================

# A partir daqui, as variáveis globais do seu Core assumem os valores dinâmicos:
PORT = NODE_PORT
ROLE = INITIAL_ROLE

# Certifique-se de que as instâncias dos seus módulos importados (como MeshServer ou ClusterManager)
# usem as variáveis 'PORT' e 'ROLE' em vez do valor fixo 8080.

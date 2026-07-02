import os
import hashlib
import json

def run_forensic_analysis():
    print("\n" + "="*57)
    print("      NEXUS RUNTIME - AUDITORIA MULTI-ARQUIVO (RESILIENTE)  ")
    print("="*57)

    base_path = "outputs/nexus_store.db"
    backup_path = f"{base_path}.1"
    
    arquivos_para_auditar = []
    if os.path.exists(backup_path):
        arquivos_para_auditar.append(backup_path)
    if os.path.exists(base_path):
        arquivos_para_auditar.append(base_path)

    expected_prev_hash = None  # Inicializa sem exigir zeros fixos por arquivo
    total_blocks = 0
    global_integrity = True

    for filepath in arquivos_para_auditar:
        print(f"📁 Auditando fluxo físico: {os.path.basename(filepath)}...")
        
        with open(filepath, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    block = json.loads(line)
                    
                    # Define o hash inicial baseado no primeiríssimo bloco do histórico completo
                    if expected_prev_hash is None:
                        expected_prev_hash = block["prev_hash"]
                    
                    # 1. Checagem de integridade do encadeamento
                    if block["prev_hash"] != expected_prev_hash:
                        print(f"   🚨 Quebra no arquivo {os.path.basename(filepath)} | Bloco interno #{idx}")
                        global_integrity = False
                    
                    # 2. Recálculo do hash local
                    block_string = f"{block['timestamp']}{block['payload']}{block['prev_hash']}".encode('utf-8')
                    recalculated_hash = hashlib.sha256(block_string).hexdigest()
                    
                    if block["hash"] != recalculated_hash:
                        print(f"   🚨 Corrupção de dados no arquivo {os.path.basename(filepath)} | Bloco interno #{idx}")
                        global_integrity = False
                        
                    expected_prev_hash = block["hash"]
                    total_blocks += 1
                except Exception:
                    global_integrity = False

    print("-"*57)
    print("                     NEXUS RUNTIME REPORT                  ")
    print("-"*57)
    print(f"Total de eventos recuperados (Soma): {total_blocks}")
    print(f"Integridade fim-a-fim da cadeia    : {'✅ OK' if global_integrity and total_blocks > 0 else '❌ CORROMPIDA'}")
    print(f"Status da rotação de logs          : {'📦 OPERACIONAL' if os.path.exists(backup_path) else 'ℹ️ LIMITE NÃO ATINGIDO'}")
    print("="*57 + "\n")

if __name__ == "__main__":
    run_forensic_analysis()


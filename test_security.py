from nexus_security import NexusSecurityProvider

def run_test():
    print("--- Iniciando Teste de Integridade (v2000) ---")
    
    # 1. Simular um payload real
    payload_valido = "comando_de_simulacao_01"
    assinatura = NexusSecurityProvider.sign_payload(payload_valido)
    
    # 2. Teste A: Validar assinatura correta
    if NexusSecurityProvider.verify_payload(payload_valido, assinatura):
        print("[SUCESSO] Assinatura válida aceite pelo motor.")
    else:
        print("[ERRO] Assinatura válida rejeitada!")

    # 3. Teste B: Tentar forjar um payload (Ataque)
    payload_falso = "comando_de_simulacao_01_ALTERADO"
    if not NexusSecurityProvider.verify_payload(payload_falso, assinatura):
        print("[SUCESSO] Payload forjado foi corretamente rejeitado.")
    else:
        print("[ERRO] AVISO! Payload forjado foi aceite!")

run_test()

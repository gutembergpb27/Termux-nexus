#!/bin/bash

# ==============================================================================
# NEXUS RUNTIME (v500) - VALIDAÇÃO DE CONSISTÊNCIA OPERACIONAL (100 CYCLES)
# Autor: Gutemberg Procopio Barbosa
# Data: 30/06/2026
# ==============================================================================

TOTAL_TESTES=100
SUCESSOS=0
FALHAS=0

echo "========================================================="
echo "        NEXUS RUNTIME - TESTE DE ROBUSTEZ ESTATÍSTICA    "
echo "        Executando $TOTAL_TESTES ciclos de Engenharia de Caos... "
echo "========================================================="

for ((i=1; i<=TOTAL_TESTES; i++))
do
    echo -n "Ciclo $i/$TOTAL_TESTES: "
    
    # Executa o sandbox de forma silenciosa para coletar apenas o resultado
    ./init_nexus.sh > /dev/null 2>&1
    
    # Verifica se o relatório gerou integridade positiva
    if grep -q "Integridade dos hashes: OK" outputs/nexus_report.txt 2>/dev/null; then
        echo "✅ RECUPERADO (Hashes OK)"
        ((SUCESSOS++))
    else
        echo "❌ FALHA NA RECUPERAÇÃO"
        ((FALHAS++))
    fi
    
    # Pequeno intervalo para troca de contexto de CPU e limpeza de buffers
    sleep 0.1
done

TAXA_RECUPERACAO=$(( (SUCESSOS * 100) / TOTAL_TESTES ))

echo "========================================================="
echo "                  CONSOLIDAÇÃO FORENSE                   "
echo "========================================================="
echo -e "Execuções\tSucesso\tFalhas\tRecuperação"
echo -e "$TOTAL_TESTES\t\t$SUCESSOS\t$FALHAS\t$TAXA_RECUPERACAO%"
echo "========================================================="

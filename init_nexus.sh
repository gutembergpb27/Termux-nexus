#!/bin/bash
# ==============================================================================
# NEXUS RUNTIME (v500) - PROTOCOLO DE INJEÇÃO DE FALHAS (SIGKILL)
# ==============================================================================
echo "========================================================="
echo "        NEXUS RUNTIME - INICIALIZANDO SANDBOX            "
echo "========================================================="
echo "📁 [1/4] Estruturando árvore de diretórios..."
mkdir -p outputs
sleep 1

echo "🚀 [2/4] Disparando simulador de carga (125 Hz) em background..."
python3 test_persistence.py > /dev/null 2>&1 &
sleep 2

echo "========================================================="
echo "        NEXUS RUNTIME - LOOP DE CARGA DE ESTRESSE        "
echo "========================================================="
echo "⚡ Ingerindo fluxo contínuo a 125 Hz..."
echo "⚠️ Protocolo configurado para interrupção abrupta via SIGKILL."
echo "---------------------------------------------------------"

PID_SIMULADOR=$(pgrep -f "test_persistence.py")

if [ -n "$PID_SIMULADOR" ]; then
    echo "🛑 [ENGENHARIA DE CAOS] Injetando sinal SIGKILL (kill -9) no processo $PID_SIMULADOR..."
    kill -9 $PID_SIMULADOR
else
    echo "❌ Falha crítica: Processo do simulador não encontrado para injeção de sinal."
    exit 1
fi

sleep 1
echo "📊 [4/4] Invocando analisador forense de logs..."
python3 analyzer.py
# ==============================================================================


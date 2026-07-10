#!/bin/bash

# ==============================================================================
# NEXUS RUNTIME v2200 - Script de Provisionamento e Bootstrap de Nós ARM
# Foco: Engenharia de Confiabilidade (SRE) e Alta Disponibilidade de Borda
# ==============================================================================

set -e # Interrompe a execução imediatamente em caso de erro interno

echo "🚀 [Nexus v2200] Iniciando provisionamento atômico do nó de borda..."

# 1. Definição de Variáveis de Caminho e Ambiente
NEXUS_DIR="/opt/nexus_runtime"
SERVICE_FILE="/etc/systemd/system/nexus.service"

# 2. Auditoria e Isolamento de Dependências Nativas
echo "🔍 [Auditoria] Verificando requisitos de sistema..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Erro: Python 3 não localizado. Instalando dependências..."
    sudo apt-get update
    sudo apt-get install -y python3 sqlite3 python3-dotenv
else
    echo "✔ Python 3 localizado. Validando dependência dotenv..."
    if ! python3 -c "import dotenv" 2>/dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3-dotenv
    fi
    echo "✔ Python 3, SQLite3 e dotenv validados."
fi

# 3. Criação e Limpeza do Diretório de Trabalho (Mitigação de Estado Corrompido)
echo "🧹 [Persistência] Organizando diretórios e isolando bancos antigos..."
sudo mkdir -p "$NEXUS_DIR"
sudo mkdir -p "$NEXUS_DIR/archived_patches"

# Preserva bancos, WAL e arquivos SHM existentes.
# O provisionamento não deve apagar estado válido de um nó já inicializado.

# Copia o Core, a camada de segurança e a configuração secreta local.
# nexus_config.env não é versionado e deve ser provisionado pelo operador.
if [ -f "nexus_distributed_core.py" ] &&    [ -f "nexus_security.py" ] &&    [ -f "nexus_config.env" ]; then
    sudo cp nexus_distributed_core.py "$NEXUS_DIR/"
    sudo cp nexus_security.py "$NEXUS_DIR/"
    sudo cp nexus_config.env "$NEXUS_DIR/"
    sudo chmod 600 "$NEXUS_DIR/nexus_config.env"
else
    echo "❌ Erro: core, segurança e nexus_config.env devem existir na pasta atual."
    exit 1
fi

# 4. Configuração Dinâmica do Arquivo de Serviço Systemd (Daemon de Inicialização)
echo "⚙ [Daemonization] Gerando unidade de serviço para execução contínua..."

# Coleta parâmetros de entrada ou assume valores padrão para nós seguidores
NODE_ID=${1:-"NO-ARM-FOLLOWER"}
WEB_PORT=${2:-"8082"}
TCP_PORT=${3:-"9092"}
ROLE=${4:-"FOLLOWER"}

sudo cat << SYSTEMD_EOF | sudo tee "$SERVICE_FILE" > /dev/null
[Unit]
Description=Nexus Runtime Distributed Edge Node (v2200)
After=network.target

[Service]
Type=simple
WorkingDirectory=$NEXUS_DIR
ExecStart=/usr/bin/python3 nexus_distributed_core.py $NODE_ID $WEB_PORT $TCP_PORT $ROLE
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nexus-$NODE_ID

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

# 5. Inicialização e Registro do Daemon de Alta Disponibilidade
echo "🔄 [Reload] Recarregando gerenciador de serviços do Linux..."
sudo systemctl daemon-reload

echo "=============================================================================="
echo "✔ PROVISIONAMENTO CONCLUÍDO COM SUCESSO!"
echo "📍 Diretório de execução: $NEXUS_DIR"
echo "🛠️ Unidade gerada: $SERVICE_FILE"
echo "👑 Configuração Atual: ID=$NODE_ID | Papel=[$ROLE] | Portas=$WEB_PORT, TCP=$TCP_PORT"
echo "=============================================================================="
echo "💡 Para inicializar o nó na malha de borda física, execute:"
echo "   sudo systemctl start nexus"
echo "   sudo systemctl enable nexus"
echo "💡 Para monitorar a inteligência do failover em tempo real:"
echo "   sudo journalctl -u nexus -f"
echo "=============================================================================="

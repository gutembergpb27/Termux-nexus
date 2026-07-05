#!/data/data/com.termux/files/usr/bin/bash

echo "=========================================================="
echo " 🪐 INSTALADOR AUTOMÁTICO - NEXUS RUNTIME ECOSYSTEM"
echo "=========================================================="
echo "[*] Atualizando pacotes do ambiente Termux..."
pkg update -y && pkg upgrade -y

echo "[*] Verificando dependências de sistema (Python3)..."
pkg install python -y

echo "[*] Configurando permissões locais..."
chmod +x nexus_v500.py

echo "=========================================================="
echo " 🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!"
echo "=========================================================="
echo " Para rodar a infraestrutura resiliente agora, execute:"
echo " python3 nexus_v500.py"
echo "=========================================================="

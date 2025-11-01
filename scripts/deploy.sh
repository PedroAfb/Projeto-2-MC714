#!/bin/bash
# Script de deploy para VMs do GCP
# Uso: ./scripts/deploy.sh

set -e

echo "=== Deploy do sistema distribuído Bully + Lamport ==="

# 1. Atualizar sistema
echo "[1/4] Atualizando sistema..."
sudo apt-get update -qq

# 2. Instalar Python 3.11+ se necessário
echo "[2/4] Verificando Python..."
if ! command -v python3.11 &> /dev/null; then
    echo "Instalando Python 3.11..."
    sudo apt-get install -y python3.11 python3.11-venv python3-pip
else
    echo "Python 3.11+ já instalado: $(python3.11 --version)"
fi

# 3. Criar ambiente virtual e instalar dependências
echo "[3/4] Configurando ambiente virtual..."
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "[4/4] Deploy concluído!"
echo ""
echo "Para iniciar um nó, use:"
echo "  source .venv/bin/activate"
echo "  python -m src.node --id <ID> --host <IP> --port <PORT> --peers <id:host:port,id:host:port,...>"
echo ""
echo "Exemplo (3 nós locais):"
echo "  Terminal 1: python -m src.node --id 1 --host 127.0.0.1 --port 8001 --peers 2:127.0.0.1:8002,3:127.0.0.1:8003"
echo "  Terminal 2: python -m src.node --id 2 --host 127.0.0.1 --port 8002 --peers 1:127.0.0.1:8001,3:127.0.0.1:8003"
echo "  Terminal 3: python -m src.node --id 3 --host 127.0.0.1 --port 8003 --peers 1:127.0.0.1:8001,2:127.0.0.1:8002"

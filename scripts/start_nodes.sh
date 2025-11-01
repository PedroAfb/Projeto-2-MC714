#!/bin/bash
# Script para iniciar 3 nós localmente (teste local antes do GCP)
# Uso: ./scripts/start_nodes.sh

# Mata processos antigos
pkill -f "src.node" || true

# Configuração dos 3 nós
NODE1_ID=1
NODE1_HOST=127.0.0.1
NODE1_PORT=8001

NODE2_ID=2
NODE2_HOST=127.0.0.1
NODE2_PORT=8002

NODE3_ID=3
NODE3_HOST=127.0.0.1
NODE3_PORT=8003

# Peers no formato id:host:port
PEERS_NODE1="2:${NODE2_HOST}:${NODE2_PORT},3:${NODE3_HOST}:${NODE3_PORT}"
PEERS_NODE2="1:${NODE1_HOST}:${NODE1_PORT},3:${NODE3_HOST}:${NODE3_PORT}"
PEERS_NODE3="1:${NODE1_HOST}:${NODE1_PORT},2:${NODE2_HOST}:${NODE2_PORT}"

echo "=== Iniciando 3 nós localmente ==="
echo "Logs em: /tmp/node*.log"
echo ""

# Ativa ambiente virtual se existir
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Inicia nós em background
python -m src.node --id $NODE1_ID --host $NODE1_HOST --port $NODE1_PORT --peers "$PEERS_NODE1" > /tmp/node1.log 2>&1 &
echo "Nó 1 iniciado (PID: $!)"

python -m src.node --id $NODE2_ID --host $NODE2_HOST --port $NODE2_PORT --peers "$PEERS_NODE2" > /tmp/node2.log 2>&1 &
echo "Nó 2 iniciado (PID: $!)"

python -m src.node --id $NODE3_ID --host $NODE3_HOST --port $NODE3_PORT --peers "$PEERS_NODE3" > /tmp/node3.log 2>&1 &
echo "Nó 3 iniciado (PID: $!)"

echo ""
echo "Para acompanhar logs em tempo real:"
echo "  tail -f /tmp/node1.log"
echo "  tail -f /tmp/node2.log"
echo "  tail -f /tmp/node3.log"
echo ""
echo "Para parar os nós: pkill -f 'src.node'"

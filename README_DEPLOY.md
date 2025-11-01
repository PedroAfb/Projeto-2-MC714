# Sistema Distribuído: Bully + Lamport Clock

Sistema distribuído implementando o algoritmo de eleição Bully com relógios lógicos de Lamport.

## Estrutura do Projeto

```
├── src/
│   ├── lamport.py      # Implementação do relógio de Lamport
│   ├── network.py      # API HTTP (FastAPI) com endpoint /rpc
│   ├── election.py     # Algoritmo Bully de eleição de líder
│   └── node.py         # Orquestrador principal do nó
├── scripts/
│   ├── deploy.sh       # Script de setup para VMs
│   └── start_nodes.sh  # Script para iniciar 3 nós localmente
└── requirements.txt    # Dependências Python
```

## Instalação Local

```bash
git clone <repo-url>
cd Projeto2

./scripts/deploy.sh

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

### Formato dos Peers

Os peers devem ser especificados no formato: `id:host:port`

Exemplo: `1:192.168.1.10:8001,2:192.168.1.11:8002`

### Executar Nó Individual

```bash
source .venv/bin/activate
python -m src.node --id <ID> --host <IP> --port <PORT> --peers <id:host:port,...>
```

**Parâmetros:**
- `--id`: ID inteiro único do nó (maior id = maior prioridade)
- `--host`: IP para escutar (use IP público/privado da VM, não 0.0.0.0 em produção)
- `--port`: Porta HTTP
- `--peers`: Lista de peers no formato `id:host:port` separados por vírgula

**Exemplo (nó com id=1):**
```bash
python -m src.node --id 1 --host 10.128.0.2 --port 8001 \
  --peers 2:10.128.0.3:8002,3:10.128.0.4:8003
```

### Teste Local (3 nós)

```bash
./scripts/start_nodes.sh
```

Isso inicia 3 nós locais em localhost:8001-8003. Logs em `/tmp/node*.log`.

Para acompanhar logs:
```bash
tail -f /tmp/node1.log
tail -f /tmp/node2.log
tail -f /tmp/node3.log
```

Para parar:
```bash
pkill -f 'src.node'
```

### Comandos Interativos

Após iniciar um nó, você pode digitar comandos no terminal:

- `status` - mostra líder atual e timestamp do relógio
- `election` - força início de eleição
- `exit` ou `quit` - encerra o nó
- qualquer outro texto - tratado como evento local (incrementa relógio)

## Deploy em 3 VMs no GCP

### 1. Criar 3 VMs

```bash
gcloud compute instances create node1 node2 node3 \
  --zone=us-central1-a \
  --machine-type=e2-small \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud
```

### 2. Configurar Firewall

Abrir portas 8001-8003:

```bash
gcloud compute firewall-rules create allow-nodes \
  --allow tcp:8001-8003 \
  --source-ranges 0.0.0.0/0
```

### 3. Setup em Cada VM

SSH em cada VM e execute:

```bash
git clone <repo-url>
cd Projeto2

./scripts/deploy.sh
source .venv/bin/activate
```

### 4. Obter IPs Internos

```bash
gcloud compute instances list
```

Exemplo de saída:
```
NAME   ZONE           INTERNAL_IP  EXTERNAL_IP
node1  us-central1-a  10.128.0.2   34.x.x.x
node2  us-central1-a  10.128.0.3   35.x.x.x
node3  us-central1-a  10.128.0.4   36.x.x.x
```

### 5. Iniciar Nós (usar IPs internos)

**VM node1 (id=1, IP=10.128.0.2):**
```bash
python -m src.node --id 1 --host 10.128.0.2 --port 8001 \
  --peers 2:10.128.0.3:8002,3:10.128.0.4:8003 2>&1 | tee node1.log
```

**VM node2 (id=2, IP=10.128.0.3):**
```bash
python -m src.node --id 2 --host 10.128.0.3 --port 8002 \
  --peers 1:10.128.0.2:8001,3:10.128.0.4:8003 2>&1 | tee node2.log
```

**VM node3 (id=3, IP=10.128.0.4):**
```bash
python -m src.node --id 3 --host 10.128.0.4 --port 8003 \
  --peers 1:10.128.0.2:8001,2:10.128.0.3:8002 2>&1 | tee node3.log
```

## Testes e Experimentos

### Testar Eleição

1. Iniciar os 3 nós
2. Nó com maior ID (3) deve se tornar líder automaticamente
3. Digite `status` em qualquer nó para verificar líder
4. Digite `election` para forçar nova eleição

### Simular Falha do Líder

```bash
# Em uma VM, matar o processo do líder
pkill -f 'src.node'

# Nos outros nós, observar logs:
# - heartbeat detecta falha
# - nova eleição é iniciada
# - novo líder é eleito
```

### Coletar Logs

```bash
# Copiar logs das VMs para local
gcloud compute scp node1:~/Projeto2/node1.log ./logs/
gcloud compute scp node2:~/Projeto2/node2.log ./logs/
gcloud compute scp node3:~/Projeto2/node3.log ./logs/
```

## Arquitetura

### Protocolo RPC

Todas as mensagens usam POST /rpc com JSON:

```json
{
  "type": "ELECTION|OK|COORDINATOR|PING",
  "from": "node_id",
  "ts": lamport_timestamp,
  "payload": { ... }
}
```

### Algoritmo Bully (Simplificado)

1. Nó detecta falha do líder → inicia eleição
2. Envia `ELECTION` para todos os nós com ID maior
3. Se recebe `OK` → aguarda anúncio de coordenador
4. Se não recebe `OK` em 2s → assume liderança e anuncia `COORDINATOR`

### Relógio de Lamport

- `tick()`: incrementa ao enviar mensagem ou evento local
- `update(remote_ts)`: `max(local, remote) + 1` ao receber mensagem
- Todos os logs mostram: `[node_id][lamport_ts] EVENT: ...`

## Troubleshooting

**Nós não se comunicam:**
- Verificar firewall: `sudo ufw status` (se ativo, liberar portas)
- Verificar IPs: usar IPs internos da VPC, não 0.0.0.0
- Testar conectividade: `curl http://<peer-ip>:<port>/rpc`

**Eleição não acontece:**
- Verificar se heartbeat está rodando (deve aparecer nos logs a cada 3s)
- Verificar se peers estão corretos: `status` mostra líder
- Forçar eleição manualmente: digite `election`

**ImportError:**
- Certifique-se de executar como módulo: `python -m src.node` (não `python src/node.py`)
- Ativar venv: `source .venv/bin/activate`

## Licença

Projeto acadêmico - MC714 Unicamp 2S2025

# Guia de Teste Local — Sistema Bully + Lamport

## ✅ Testes Realizados com Sucesso

### 1. Eleição Inicial
```bash
./scripts/start_nodes.sh
sleep 4
grep -h "EVENT:" /tmp/node*.log | grep -E "eleição|líder"
```

**Resultado esperado:**
- Nó 3 (maior ID) assume liderança automaticamente
- Nós 1 e 2 aceitam nó 3 como líder

### 2. Falha do Líder e Reeleição

```bash
# Obter PID do nó 3
PID_NODE3=$(ps aux | grep 'src.node --id 3' | grep -v grep | awk '{print $2}')

# Matar líder
kill $PID_NODE3

# Aguardar nova eleição (3-5 segundos)
sleep 5

# Verificar nova eleição
grep -h "EVENT:" /tmp/node*.log | grep -E "eleição|líder|inacessível.*8003" | tail -15
```

**Resultado esperado:**
- Nós 1 e 2 detectam falha do nó 3
- Nova eleição é iniciada
- Nó 2 (maior ID restante) assume liderança
- Nó 1 aceita nó 2 como novo líder

### 3. Verificar Relógios de Lamport

```bash
grep -h "Mensagem recebida" /tmp/node*.log | head -20
```

**Resultado esperado:**
- Cada log mostra: `Mensagem recebida de X (ts=Y). clock=Z`
- `Z > Y` sempre (propriedade de Lamport: clock local > max(local, remoto))

### 4. Heartbeat e Detecção de Falhas

```bash
grep -h "peer.*inacessível" /tmp/node*.log | head -10
```

**Resultado esperado:**
- Após matar nó 3, aparecem logs: `peer 3 inacessível: http://127.0.0.1:8003`
- Heartbeat roda a cada 3 segundos

## Comandos Úteis

### Iniciar Nós
```bash
./scripts/start_nodes.sh
```

### Parar Todos os Nós
```bash
pkill -f 'src.node'
```

### Acompanhar Logs em Tempo Real
```bash
# Terminal 1
tail -f /tmp/node1.log

# Terminal 2
tail -f /tmp/node2.log

# Terminal 3
tail -f /tmp/node3.log
```

### Verificar Processos
```bash
ps aux | grep 'src.node' | grep -v grep
```

### Matar Nó Específico
```bash
# Nó 1
pkill -f 'src.node --id 1'

# Nó 2
pkill -f 'src.node --id 2'

# Nó 3
pkill -f 'src.node --id 3'
```

### Limpar Logs
```bash
rm /tmp/node*.log
```

## Cenários de Teste Recomendados

### Cenário 1: Eleição com Todos os Nós Vivos
1. Iniciar os 3 nós
2. Verificar que nó 3 vira líder
3. ✅ **Validado**

### Cenário 2: Falha do Líder
1. Iniciar os 3 nós (líder = nó 3)
2. Matar nó 3
3. Verificar que nó 2 assume liderança
4. ✅ **Validado**

### Cenário 3: Falha Sucessiva
1. Iniciar os 3 nós
2. Matar nó 3 → nó 2 vira líder
3. Matar nó 2 → nó 1 vira líder
4. **Para testar:**
```bash
./scripts/start_nodes.sh
sleep 4
pkill -f 'src.node --id 3'
sleep 5
pkill -f 'src.node --id 2'
sleep 5
grep -h "EVENT:" /tmp/node1.log | grep -E "líder"
```

### Cenário 4: Recuperação de Nó (Nó Volta)
1. Iniciar 3 nós
2. Matar nó 3
3. Nó 2 vira líder
4. Reiniciar nó 3 → deve aceitar líder atual ou forçar eleição
5. **Para testar:**
```bash
./scripts/start_nodes.sh
sleep 4
PID3=$(ps aux | grep 'src.node --id 3' | grep -v grep | awk '{print $2}')
kill $PID3
sleep 5
# Reiniciar nó 3 manualmente
python -m src.node --id 3 --host 127.0.0.1 --port 8003 \
  --peers 1:127.0.0.1:8001,2:127.0.0.1:8002 > /tmp/node3_new.log 2>&1 &
sleep 5
tail /tmp/node3_new.log
```

### Cenário 5: Ordenação de Eventos (Lamport)
1. Coletar todos os eventos com timestamps
2. Verificar que eventos causalmente relacionados respeitam ordem de Lamport
```bash
grep -h "\[.*\]\[.*\]" /tmp/node*.log | grep "EVENT:" | sort -t'[' -k3 -n | head -30
```

## Análise de Logs para Relatório

### Extrair Eventos de Eleição
```bash
grep -h "EVENT:" /tmp/node*.log | grep -E "eleição|líder|OK" > eleicao_events.txt
```

### Extrair Comunicação RPC
```bash
grep -h "Enviando RPC\|Mensagem recebida" /tmp/node*.log > rpc_communication.txt
```

### Contar Mensagens por Tipo
```bash
grep -h "tipo=" /tmp/node*.log | sed 's/.*tipo=\([A-Z]*\).*/\1/' | sort | uniq -c
```

### Timeline de Eventos (com Lamport timestamp)
```bash
grep -h "EVENT:" /tmp/node*.log | \
  sed 's/.*\[\([0-9]*\)\]\[\([0-9]*\)\] EVENT: \(.*\)/[\2] Nó \1: \3/' | \
  sort -t'[' -k2 -n
```

## Resultados Esperados (Checklist)

- [x] LamportClock implementado e funcionando
- [x] Servidor HTTP /rpc recebendo e respondendo mensagens
- [x] Bully election implementado
- [x] Eleição inicial automática (nó com maior ID vira líder)
- [x] Detecção de falha do líder via heartbeat
- [x] Reeleição automática após falha do líder
- [x] Novo líder eleito corretamente (maior ID entre sobreviventes)
- [x] Timestamps de Lamport atualizados em todas as mensagens
- [x] Logs formatados como `[node_id][lamport_ts] EVENT: ...`
- [ ] Teste em 3 VMs no GCP (próximo passo)
- [ ] Coleta de logs para relatório
- [ ] Análise de ordenação de eventos

## Próximos Passos

1. **Deploy em GCP**: seguir `README_DEPLOY.md`
2. **Testes em ambiente distribuído real**
3. **Coleta de logs**: usar scripts acima
4. **Relatório**: incluir logs, análise de timestamps, gráficos de eleição

# Nexus Runtime — Estado Atual do Projeto

## Referência

- Repositório: `Termux-nexus`
- Branch: `canonical-evidence`
- HEAD: `a10de14`
- Versão: `runtime-v1.1-rc1`
- Testes: **76 passed, 1 xfailed**

---

## Componentes

- Rendezvous Hub autenticado
- Nexus Distributed Core
- Nexus Protocol
- Nexus Persistence
- Web Panel

---

## Funcionalidades implementadas

### Segurança

- Registro autenticado
- Heartbeat autenticado
- HMAC
- Replay protection
- Nonce
- Timestamp validation

### Persistência

- Cadeia de hashes
- Checkpoints
- Validação de integridade
- Exportação incremental por altura
- Aplicação validada de lotes
- Recuperação de estado

### Sincronização

- STATE_SUMMARY
- SYNC_BATCH
- Catch-up incremental
- Sincronização automática
- Rejoin automático

### Cluster

- Registro de nós
- Heartbeat
- Descoberta de peers
- Failover automático
- Promoção de follower
- Convergência

### Transporte

- Dispatcher TCP
- Handlers especializados
- Framing TCP com prefixo de tamanho
- Camada `nexus_transport.py`
- `send_message()` e `recv_message()`

### Observabilidade

Endpoints disponíveis:

- `/status`
- `/metrics`
- `/cluster`
- `/health`
- `/liveness`
- `/readiness`

---

## Estado atual

- Runtime v1.1 RC1
- Branch sincronizada com origin
- 76 testes aprovados
- 1 teste xfailed conhecido
- Todos os testes verdes

---

## Últimos commits

- `a10de14` feat(runtime): derive readiness from cluster health
- `5a4cc19` refactor(core): remove duplicate peer snapshot assignments
- `c8037d7` feat(runtime): expose liveness and readiness endpoints
- `906ceda` feat(runtime): expose operational health endpoint
- `e8dfe03` refactor(transport): migrate core sync to framed messages

---

## Próximo objetivo

Evoluir o Runtime para diagnóstico distribuído real:

- detectar atraso de sincronização em relação ao MASTER;
- identificar múltiplos líderes;
- expor estado operacional do nó;
- preparar a máquina de estados do Runtime;
- manter a suíte completa verde.

---

## Procedimento após reinício do Termux

Sempre iniciar com:

```bash
cd ~/Termux-nexus
git branch --show-current
git status --short
git log -5 --oneline
python -m pytest -q
```

Nunca executar o pytest na HOME (`~`).

---

## Fonte de verdade

1. Código versionado
2. Testes automatizados
3. Este documento
4. Histórico Git
5. Conversas anteriores
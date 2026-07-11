# Nexus Runtime — Estado Atual do Projeto

## Referência

- Repositório: `Termux-nexus`
- Branch: `canonical-evidence`
- HEAD: `98de167`
- Versão: `runtime-v1.1-rc1`
- Testes: **60 passed, 1 xfailed**

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

### Observabilidade

Endpoints disponíveis:

- `/status`
- `/metrics`
- `/cluster`

---

## Estado atual

- Runtime v1.1 RC1
- Branch sincronizada com origin
- 60 testes aprovados
- 1 teste xfailed conhecido
- Todos os testes verdes

---

## Últimos commits

- `98de167` test(observability): cover runtime HTTP endpoints
- `c77f400` feat(observability): expose cluster peer snapshot
- `0061e65` feat(observability): expose runtime status and metrics API
- `ae88d2c` test(sync): cover follower rejoin convergence
- `d34b327` feat(sync): automatically sync followers from master

---

## Próximo objetivo

Implementar endpoints de saúde do Runtime:

- `/health`
- `/liveness`
- `/readiness`

com validação real da persistência utilizando:

`runtime.persistence.validate_chain()`

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
# Nexus Runtime v1 Beta

## Referência

- Branch: `canonical-evidence`
- Tag: `runtime-v1-beta`
- Commit: `ee11d0251212544e378fada628d43cf974b53344`

## Capacidades incluídas

- registro autenticado;
- heartbeat autenticado;
- identidade estável durante failover;
- promoção automática de follower;
- resumo autenticado de estado;
- sincronização incremental por altura;
- aplicação validada de lotes;
- persistência com cadeia de hashes;
- dispatcher TCP;
- logging operacional padronizado;
- demo automatizada de dois nós com failover.

## Validação

- `56 passed`
- `1 xfailed`
- demo automatizada concluída com sucesso.

## Limitações conhecidas

- eleição ainda é determinística e simplificada;
- o transporte TCP ainda não usa framing explícito;
- a demo cobre dois nós;
- observabilidade ainda é baseada em logs;
- sincronização automática de retorno do nó antigo ainda precisa ser demonstrada no cluster.

## Próximo objetivo

Demonstrar recuperação completa:

1. MASTER cai;
2. FOLLOWER assume;
3. MASTER antigo retorna como follower;
4. estado é sincronizado;
5. cluster converge sem perda de eventos.

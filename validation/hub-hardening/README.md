# W07: Hub hardening (experimental, isolado)

Este diretório **não** altera o runtime. `nexus_rendezvous.py` (blob `d61fedd2…`) e `nexus_distributed_core.py` não são alterados por este diretório; o blob de referência do core passou a ser `5bc69c40…` em W08-B / PR-B (modo de cluster explícito; antes `eb8a48da…`). Nada aqui inicia o hub real nem o cluster.

| Arquivo | Papel |
|---|---|
| `experimental_hub.py` | `HardenedHub`: concorrência limitada, timeouts, prazo por requisição, limite por cliente, allowlist, bind em 127.0.0.1 por padrão, bind exclusivo, lock de estado, reaper robusto, shutdown controlado, contadores. A validação HMAC é **importada** do original, não copiada. |
| `hub_probes.py` | Sondas de loopback compartilhadas por testes e comparador. O alvo "original" é o `NexusRendezvousHandler` original num `HTTPServer` em 127.0.0.1 com porta efêmera; o `__main__` dele nunca roda. |
| `test_hub_hardening.py` | 60 testes. `test_original_*` passam quando a limitação do original é reproduzida. |
| `compare_hubs.py` | Gera `evidence/hub-compare-*.json`, com PASS/FAIL/BLOCKED por verificação. |
| `INTEGRATION_PROPOSAL.md` | Proposta de integração (não aplicada). |

## Uso

```
python -B -X dev -m pytest -p no:cacheprovider -W error::ResourceWarning test_hub_hardening.py
python -B compare_hubs.py
```

- Os testes usam somente 127.0.0.1 (e 127.0.0.2 como origem em um teste) e um secret descartável gerado por execução.
- Não usam a rede e não exigem o gate de 2048 MB, porque rodam num único processo, sem cluster.
- O teste com o cluster S1/S5 aparece como BLOCKED.

## Evidências

O repositório versiona somente a evidência final:
- `hub-compare-20261103T200806Z-4878156d.json`: versão final. O `artifacts_sha256` dela confere com os quatro módulos deste diretório.

As duas execuções intermediárias permanecem **somente no disco local** de quem executou a W07 e não são versionadas:
- `hub-compare-20261103T193921Z-7f37c46a.json`: versão sem a thread de rejeição;
- `hub-compare-20261103T195703Z-89ad7a7a.json`: versão sem o limite por cliente.

O campo `artifacts_sha256` identifica a versão de cada execução.

Escopo: disponibilidade e robustez HTTP do hub. **Não** valida consenso, replicação nem fencing.

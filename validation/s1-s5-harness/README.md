# Nexus V2700 — Harness S1/S5 (W06)

Status: **endurecido e validado localmente**: lógica, gates, I/O e orquestração (com processos substitutos). Nenhuma execução S1/S5 do runtime Nexus foi realizada.
Runtime alvo: commit `30b774da`, `nexus_distributed_core.py` blob Git `eb8a48da88a75f9d58c954f8afeed86c2af27f93`.
A versão W05 está preservada em `history/`.

Evidência versionada: `evidence/preflight-20261103T183049Z-a675f9.json` e `evidence/s1-20261103T183050Z-2a11e1/` (BLOCKED nos gates de preflight). Antes da publicação, dois campos de `evidence.json` foram redigidos: `host.hostname` → `<redacted-hostname>` e o prefixo pessoal de `work_dir` → `<redacted-local-temp>`. O `SHA256SUMS` foi regenerado depois da redação; nenhum outro byte mudou. Os preflights W05 anteriores permanecem somente no disco local.

## Escopo

| Cenário | Pergunta | O que **não** testa |
|---|---|---|
| S1 | Com N=3 e o MASTER vivo, algum FOLLOWER se promove? (regressão P1) | replicação, commit, consenso |
| S5 | Com o MASTER parado, os sobreviventes detectam a falha, promovem **somente** o candidato determinístico e convergem? | replicação, commit, consenso, partições |

Cada evidência traz `claims`:
- liveness, eleição e nova coordenação = observados;
- replicação = não testada (fica bloqueada com N=3, e o harness só verifica a recusa);
- consenso e fencing de MASTER = não implementados, não reivindicados.

Um PASS **não** certifica consenso distribuído.

## Princípios

- Executa o runtime **sem alterações**, como processos filhos reais. Nada do runtime é simulado.
- Cada execução tem um diretório de trabalho novo, com um `cwd` por nó, porque o runtime grava `nexus_<id>.db` no diretório corrente. Os filhos rodam com `python -B` e `stdin=DEVNULL`.
- O harness só encerra processos que ele criou, pelo handle do `Popen`, nunca por PID ou nome. Não apaga arquivos.
- **Proteção contra órfãos:**
  - Windows: Job Object com `KILL_ON_JOB_CLOSE` e limite de memória do job de 2048 MB.
  - Linux/Android: `PR_SET_PDEATHSIG`.
  - SIGTERM, SIGHUP e SIGBREAK viram interrupção controlada.
- **Encerramento antes da evidência:** toda saída, inclusive exceção e Ctrl+C, para os filhos antes de coletar logs. A evidência registra `shutdown.completed_monotonic_s ≤ evidence_written_monotonic_s`. Se algum filho não for confirmado como parado, o resultado nunca é PASS.
- **Secret:** só entra pelo ambiente. É redigido em forma crua e em forma escapada para JSON, em logs, exceções e saída do console. Nenhum traceback chega ao console.

## Gates (BLOCKED, saída 3)

| Gate | Regra |
|---|---|
| Memória | memória livre ≥ **2048 MB**. Valores menores são recusados; reduzir exige autorização. |
| Orçamento | RSS dos filhos ≤ 2048 MB (também limitado pelo Job no Windows); memória livre ≥ 512 MB durante a execução. |
| Secret | `NEXUS_SECRET_KEY` presente, ≥ 16 caracteres. |
| Runtime | arquivos presentes, sem modificação no Git, blob do core igual ao esperado. |
| Portas | livres antes do preflight **e** imediatamente antes de cada processo. A checagem faz connect, bind exclusivo em `0.0.0.0` e bind em `127.0.0.1`. |
| Exposição | o runtime escuta em `0.0.0.0` (hub:407, core:391, web_panel:128). Rodar exige `--accept-lan-exposure`. |
| Relógio | multi-host: \|NTP − local\| ≤ 1,0 s em cada host. |
| Prontidão / filhos | o hub e os 3 nós respondem com a identidade e os papéis certos. Um filho que termina ou cuja thread morre (`Exception in thread`) gera BLOCKED. |

## Classificação

- **FAIL**: o runtime violou um critério.
- **BLOCKED**: pré-condição não atendida, ou observação insuficiente. Exemplos: lacuna de observação, hub não observável, sonda QS-C01 inconclusiva, recusa não confirmada no log, erro do harness, interrupção.
- **PASS**: nenhum motivo registrado.

Uma falha de observação nunca gera FAIL, e nunca há PASS com lacuna.

**S1 — FAIL** se ocorrer qualquer um destes:
- FOLLOWER como MASTER, ou dois MASTERs, **mesmo em uma única amostra**;
- MASTER rebaixado;
- divergência de papéis no hub;
- logs com `master_missing`, `leadership_promotion_started`, `leadership_promoted`, `sync_batch_applied`, `peer_sync_completed` ou `event_persisted`;
- identidade errada no `/status`;
- `STATE_SUMMARY` aceito ou resposta inesperada.

**S5 — FAIL** se ocorrer qualquer um destes:
- baseline violando as regras do S1;
- MASTER não parado ou ainda respondendo;
- **qualquer** sobrevivente que não seja o candidato `max(ids)` aparecer como MASTER, ou dois MASTERs em qualquer amostra (não há tolerância para transitórios);
- promoção antes de 10 s ou depois de 90 s;
- estado final mantido por menos de 30 s;
- hub sem convergir ou sem remover o MASTER antigo;
- escrita de estado após a parada;
- novo MASTER aceitando `STATE_SUMMARY`.

A sonda QS-C01 é somente leitura. Nos nós locais, a recusa precisa estar confirmada no log (`distributed_sync_blocked operation=state_summary`); sem essa confirmação, o resultado é BLOCKED.

Os limites de tempo e de disponibilidade só podem ficar mais rígidos via configuração (ver `TIMING_BOUNDS`).

## Uso

```
python s1s5_harness.py preflight --config topology-loopback.json [--accept-lan-exposure]
python s1s5_harness.py run --scenario s1|s5 --config topology-loopback.json --accept-lan-exposure
python s1s5_harness.py plan --config <config>
python s1s5_harness.py node --config <phone.json> --node-id NODE-C --accept-lan-exposure
```

Topologia B: veja `topology-b.example.json` (Windows) e `topology-b-phone.example.json` (Termux). Troque os placeholders pelos IPs do dia; placeholders são recusados. Use o mesmo secret nos dois.

Códigos de saída: 0 PASS/COMPLETED, 1 FAIL, 2 configuração, 3 BLOCKED.

## Testes

`python -B -m pytest -p no:cacheprovider test_s1s5_harness.py` (101 testes). A camada 3 usa stubs de hub e de nó, escutando só em 127.0.0.1. Ela valida a orquestração do harness e **não** é S1/S5 do runtime.

## Limitações conhecidas (runtime, fora do escopo do harness)

Veja o relatório W06:
- bind fixo em `0.0.0.0`;
- hub e painel web com servidor HTTP de thread única;
- conexões TCP sem timeout;
- `/peers` e `/status` sem autenticação;
- quorum de promoção baseado na visibilidade do hub;
- sem term e sem fencing de MASTER.

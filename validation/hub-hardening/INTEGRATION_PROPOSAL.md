# W07: Proposta de integração do hub endurecido

Status: **proposta, não aplicada**. Aplicar exige autorização. `nexus_rendezvous.py` continua no blob `d61fedd2…`.

## 1. Alterações necessárias no hub original

| # | Alteração | Origem no protótipo |
|---|---|---|
| 1 | Trocar `HTTPServer` (uma thread) por um servidor concorrente limitado: `max_connections=32`, `max_per_client=8`. Ao atingir o limite, responder 503 imediatamente. | `HardenedHub.process_request` |
| 2 | Timeout por socket de 5 s e prazo total de 10 s por requisição. O prazo é aplicado por uma thread janitor, para cortar clientes que enviam devagar (slow-drip). | `HardenedHubHandler.setup`, `_janitor` |
| 3 | Um lock único sobre `PEERS` e `REPLAY_CACHE`, cobrindo register, heartbeat, `/peers` e o reaper. **Obrigatório** junto com o item 1: sem ele, a verificação de replay deixa de ser atômica. | `state_lock` |
| 4 | Reaper que pode ser parado e que sobrevive a exceções. | `_reaper` / `reap_once` |
| 5 | Bind configurável (`NEXUS_HUB_BIND`), com allowlist opcional (`NEXUS_HUB_ALLOW=CIDR,...`). O wildcard só com opt-in explícito. | `host`, `allow_wildcard`, `allowed_networks` |
| 6 | `SO_EXCLUSIVEADDRUSE` no Windows, sem `SO_REUSEADDR`. | `server_bind` |
| 7 | Exceção inesperada vira resposta 500 JSON, sem traceback. GET em caminho desconhecido vira 404 JSON. | `_guarded`, `_do_get` |
| 8 | Encerramento controlado em SIGINT/SIGTERM/SIGBREAK: parar o accept, cortar as conexões pendentes e aguardar as threads com prazo. | `close()`, `main()` |

Forma sugerida: mover a classe para `nexus_hub_server.py` e fazer o `__main__` de `nexus_rendezvous.py` escolher a implementação por `NEXUS_HUB_IMPL=legacy|hardened`. O padrão inicial é `legacy`. As funções `register_peer`, `update_peer_heartbeat` e `normalize_*` não mudam.

## 2. Compatibilidade com os nós existentes

- **Nenhuma alteração no nó.** Verificado com os métodos reais de `NexusDistributedCore` (`post_envelope`, `build_registration_envelope`, `build_heartbeat_envelope`) e com o mesmo `urllib` (timeout de 2 s) usado no `/peers`. O resultado foi idêntico nos dois hubs.
- **Contrato preservado:**
  - HTTP/1.0, uma requisição por conexão;
  - mesmos caminhos;
  - mesmos status e corpos JSON nos 25 casos da matriz;
  - mesmos campos do registro de peer.
- **Diferenças deliberadas:**
  - GET em caminho desconhecido: o original fecha sem responder; o endurecido responde 404.
  - `/peers` passa a enviar `Content-Length`.
  - Header `Server` diferente.
  - Nenhum nó depende dessas três coisas.
- **Topologia B:** o hub precisa aceitar o NODE-C pela LAN. Configuração recomendada: `NEXUS_HUB_BIND=<IP LAN do Windows>` e `NEXUS_HUB_ALLOW=<IP do celular>/32,127.0.0.1/32`, no lugar de `0.0.0.0` sem filtro.

## 3. Impactos em HMAC e heartbeat

- Envelope, assinatura, TTL de 60 s, cache de replay e mensagens de erro (401/400) são **o mesmo código**, importado do original.
- Com concorrência, "verificar e depois inserir no cache de replay" precisa ser atômico. O lock garante isso. Teste: o mesmo envelope enviado 16 vezes em paralelo é aceito 1 vez e recebe 401 nas outras 15, nos dois hubs.
- **Latência do heartbeat:**
  - Requisições legítimas levam milissegundos.
  - O timeout do servidor (5 s) e o prazo total (10 s) não afetam clientes normais.
  - O timeout do cliente (2 s) continua sendo o limite do lado do nó.
- O `PEER_TIMEOUT` de 30 s e a remoção dos peers expirados ficam iguais.

## 4. Impactos sobre MASTER_PROBE

- O MASTER_PROBE é TCP de nó para nó e **não passa pelo hub**. O protocolo dele não muda.
- **Efeito indireto positivo:** hoje, um hub congelado faz o heartbeat falhar. Aí o laço de polling dá `continue` antes de chegar ao probe e à detecção de `master_missing`, e o failover para. Com o hub endurecido, um cliente parado no 8500 não congela mais o hub, então o laço segue rodando.
- **Isso não muda:**
  - a promoção continua dependendo da visão do hub no `/peers`, que mostra o MASTER morto por até 30 s;
  - não há term nem fencing;
  - disponibilidade do hub ≠ consenso.

## 5. Estratégia de migração

1. **Fase 0 (atual).** Protótipo isolado em `validation/hub-hardening/`, com testes e evidência.
2. **Fase 1** (com autorização, em um branch novo):
   - adicionar `nexus_hub_server.py`, mais o seletor `NEXUS_HUB_IMPL` com padrão `legacy`;
   - portar os testes deste diretório para `tests/`;
   - atualizar o contrato de identidade do harness S1/S5: hoje ele recusa um runtime modificado e não verifica o blob do hub.
3. **Fase 2.** S1 e S5 com `NEXUS_HUB_IMPL=hardened`, primeiro em loopback e depois na topologia B (rede doméstica). Exige que o gate de memória (≥ 2048 MB), o secret e a autorização de exposição estejam atendidos.
4. **Fase 3.** Tornar `hardened` o padrão, mantendo `legacy` disponível por um ciclo.
5. **Fase 4.** Remover o `legacy`.

## 6. Testes de regressão obrigatórios

- `validation/hub-hardening/test_hub_hardening.py` (60 testes), rodado com `-X dev -W error::ResourceWarning`. Cobre:
  - cliente parado, headers parciais e body parcial;
  - slow-drip;
  - concorrência;
  - replay em paralelo;
  - limite global e por cliente;
  - shutdown com conexões pendentes;
  - exceção no handler e reaper;
  - matriz de contrato;
  - cliente real do nó;
  - hub indisponível;
  - CLI com sinal.
- `tests/test_rendezvous_*.py` existentes.
- A suíte completa (`tests/`): 870 passed, 1 xfailed hoje.
- `python compare_hubs.py`: 0 FAIL.
- S1 e S5 (harness W06) com o hub endurecido, antes de mudar o padrão.

## 7. Riscos remanescentes

- **`/peers` continua sem autenticação.** O mapa do cluster (IP, portas, papéis, capacidades) é público para quem alcança o bind. Corrigir exige GET assinado, ou seja, uma mudança no nó. Mitigação: bind em IP específico e allowlist.
- **Flood ainda é possível.** O endurecimento troca "um único socket congela o hub" por "é preciso manter um flood contínuo de muitas origens".
  - Um único IP ocupa no máximo 8 slots e é cortado em 10 s.
  - Várias origens conseguem esgotar os 32 slots, e então chegam 503s.
  - Os nós tratam o 503 como falha de heartbeat, igual a hoje.
- **A allowlist é por IP de origem.** Não protege contra quem está na mesma LAN com IP permitido (ARP spoofing).
- **Fora do escopo do hub e não corrigidos:**
  - painel web de thread única em `0.0.0.0`, com `Access-Control-Allow-Origin: *`;
  - TCP do nó sem timeout e sem limite de threads;
  - `/status`, `/cluster` e `/metrics` sem autenticação;
  - quorum baseado na visibilidade do hub;
  - ausência de term e fencing.
- **Corrida do `PEERS` no original** (o reaper e o handler iteram e alteram o mesmo dict sem lock). A falha está confirmada no código, mas **não foi reproduzida**; é uma hipótese de baixa probabilidade. Se acontecer, ela mata a thread do reaper ou derruba uma resposta. O item 3 elimina o risco.
- **Overhead de threads.** No máximo 32 threads de conexão mais 4 de serviço. O custo de memória é pequeno, mas no Android/Termux ainda não foi medido.

## 8. Procedimento de reversão

- O hub não persiste estado: `PEERS` e o cache de replay vivem só em memória.
- **Para reverter:**
  1. pare o hub;
  2. volte `NEXUS_HUB_IMPL=legacy`, ou reverta o commit da Fase 1;
  3. inicie o hub de novo.
- Os nós se registram novamente sozinhos no próximo ciclo de polling (≤ 5 s), porque um heartbeat que falha faz o nó voltar a enviar `/register`.
- Não há migração de dados nem mudança no nó, então não é preciso coordenar a reversão entre Windows e celular. Basta reiniciar o hub.

# Nexus Runtime Platform V2700

## Multi-WAN 05K-2 — Piloto físico de controles negativos com correlação por requisição (Windows ↔ Motorola, experimental)

[English](NEXUS_V2700_MULTIWAN_05K2_PHYSICAL_EN.md) · **Português (Brasil)**

**Data de referência:** 23 de novembro de 2026

**Classificação:** documentação experimental pública; evidências brutas mantidas em caráter privado.

**Status:** piloto físico **executado e aprovado dentro dos limites
experimentais definidos**. O verificador experimental reportou
`CORRELATION=PASS`: cada uma das 20 requisições inválidas enviadas pelo Windows
foi associada individualmente a uma rejeição do servidor, e nenhuma tarefa
dessas requisições foi admitida ou concluída.

> [!IMPORTANT]
> **Escopo.** Este piloto se refere a uma cópia isolada e instrumentada do
> servidor de laboratório do MW05E. Ele **não** demonstra consenso distribuído,
> segurança universal, tolerância a partições, execução exatamente uma vez
> certificada nem prontidão para produção. Nada neste piloto altera o runtime
> da `main`.

---

### 1. Classes de evidência

| Classe | Significado |
|---|---|
| **Reportado pelo verificador** | Saída do programa experimental `--mode verify`, executado pelo operador no laboratório Android e apresentada como saída de terminal. O log e o journal do servidor Android **não** foram reprocessados pelo autor da documentação. |
| **Reconferido no lado cliente** | Recalculado pelo autor da documentação a partir do arquivo de evidência do cliente Windows (hash, tamanho, contagem por caso). |
| **Declarado pelo operador** | Detalhes do ambiente informados pelo operador e não medidos pelas ferramentas. |

---

### 2. Ambiente

| Item | Valor | Classe |
|---|---|---|
| Cliente | Computador Windows em conexão descrita como fibra | Declarado pelo operador |
| Servidor | Motorola Edge 40 Neo, Android/Termux, em conexão descrita como Starlink | Declarado pelo operador |
| Rede overlay | Tailscale (somente endereços privados da tailnet; sem listener público, sem bind curinga) | Declarado pelo operador |
| Servidor testado | Cópia isolada e instrumentada do servidor de laboratório do MW05E, com diretório de estado e journal próprios | Reportado pelo verificador |
| Uso do repositório | Checkout do Windows usado somente para leitura, para carregar o módulo de protocolo | Reconferido no lado cliente |
| Segredo HMAC | Segredo temporário novo, digitado em prompt oculto nos dois dispositivos; não salvo nem publicado | Declarado pelo operador |

O caminho de transporte de cada mensagem do piloto (direto ou via relay DERP)
não foi instrumentado.

---

### 3. Método

1. **Instrumentação.** Em uma cópia isolada do servidor de laboratório, foi
   acrescentada uma única linha **antes** da autenticação do envelope: ela
   registra, no evento de conexão do servidor, o SHA-256 do envelope recebido
   (JSON canônico). Os arquivos originais do laboratório não foram alterados. O
   rastro não contém ID de requisição, nonce, assinatura, segredo, payload nem
   endereço.
2. **Execução do cliente (uma rodada).** O cliente Windows enviou 20
   requisições inválidas ao servidor Android e guardou, para cada uma, o
   SHA-256 do mesmo envelope canônico:

   | Caso | Quantidade | Como a requisição foi invalidada |
   |---|---:|---|
   | Assinatura inválida | 10 | Envelope `COMPUTE_TASK` válido com um caractere da assinatura HMAC alterado |
   | Replay | 5 | Uma consulta autenticada `COMPUTE_STATUS` foi primeiro aceita, e sua resposta assinada `unknown_task` foi verificada pelo cliente (semente de replay); o envelope idêntico foi então reenviado |
   | Expirada | 5 | Envelope `COMPUTE_TASK` assinado com timestamp 180 s no passado (TTL do servidor: 60 s) |

3. **Transferência.** O JSONL do cliente foi copiado para o laboratório
   Android isolado por um canal privado do Tailscale, e seu SHA-256 foi
   conferido na chegada.
4. **Verificação.** Com o servidor parado, o `--mode verify` comparou, como
   multiconjuntos, os hashes de rastro do cliente com os rastros de rejeição do
   servidor e procurou no journal do servidor qualquer registro de tarefa ou de
   conclusão.

---

### 4. Resultados

**Execução do cliente — reconferido no lado cliente.**

| Verificação | Resultado |
|---|---:|
| Tentativas negativas enviadas | **20** (10 assinatura inválida · 5 replay · 5 expiradas) |
| Sementes de replay verificadas (resposta de status autenticada) | **5** / 5 |
| Tentativas negativas que receberam bytes de resposta | **0** (as 20 foram encerradas sem resposta) |
| JSONL de evidência do cliente | 4.395 bytes |
| SHA-256 da evidência do cliente | `40b8ab5dca0a705728c115ee68680d21949e4b77795a9ec398737edf82618ebd` |

**Verificação — reportado pelo verificador.**

| Controle | Observado |
|---|---:|
| Tentativas negativas do cliente | 20 |
| Rejeições negativas no servidor (`rejected_unauthenticated`) | 20 |
| Correspondências de rastro por requisição | **20** |
| Rastros do cliente ausentes no servidor | 0 |
| Rejeições inesperadas no servidor | 0 |
| Rastros únicos no cliente / no servidor | 20 / 20 |
| Falhas de semente de replay | 0 |
| Tentativas negativas com bytes de resposta | 0 |
| IDs de tarefas negativas submetidos ao journal | **0** |
| IDs de tarefas negativas concluídos | **0** |
| Linhas `task` / `done` no journal | 0 / 0 |
| Eventos `task_done` no servidor | 0 |
| Veredito | `CORRELATION=PASS` · `FRESH_INSTRUMENTED_PILOT_PASS_WITH_DEFINED_LIMITS` |

---

### 5. Relação com resultados anteriores

- **MW05E (histórico).** As 20 rejeições de autenticação no log do servidor do
  MW05E não trazem identificador de requisição. Elas continuam associadas
  **apenas por contagem** aos 20 controles negativos do cliente do MW05E; a
  correlação individual **não** está demonstrada para elas, e este piloto não
  muda isso.
- **Suíte local do MW05K-2.** Os 20/20 controles negativos locais anteriores
  foram executados em uma única máquina, com transporte simulado. Eles são
  mantidos como reportados no
  [relatório da série](NEXUS_V2700_MULTIWAN_05_SERIES_PT.md#5-mw05k-2--controles-negativos-locais-com-transporte-simulado).
- **Este piloto** acrescenta uma execução entre dispositivos em que cada
  requisição inválida é associada individualmente a uma rejeição do servidor.

---

### 6. O que este piloto mostra — e o que não mostra

**Sustentado, dentro dos limites definidos:**

- Em um enlace Tailscale Windows ↔ Android, 20 requisições inválidas
  (assinatura inválida, replay, expirada) foram rejeitadas na autenticação, e
  cada rejeição foi associada a exatamente uma requisição do cliente.
- Nenhuma dessas requisições produziu resposta, registro de tarefa no journal
  ou conclusão de tarefa no laboratório isolado.

**Limitações:**

- O rastro é o SHA-256 de um envelope **não autenticado**. Ele correlaciona o
  conteúdo em bytes dentro deste experimento; não é uma identidade confiável do
  remetente.
- Uma execução, 20 requisições. Sem repetição, benchmark ou teste de estresse.
- A ausência de registros de tarefa foi observada neste laboratório isolado;
  não é prova formal de que todos os caminhos de código do servidor falham de
  forma segura (fail-closed).
- Os números do lado Android vêm da saída do verificador apresentada pelo
  operador; o log e o journal do servidor não foram reprocessados de forma
  independente.
- As características de rede (fibra, Starlink) são declaradas pelo operador, e
  o caminho de transporte não foi instrumentado.

**Não demonstrado:** consenso distribuído, eleição por quórum, fencing de
líder, segurança universal, tolerância a partições, execução exatamente uma vez
nem prontidão para produção.

---

**Privacidade:** nenhum segredo HMAC, endereço privado, JSONL bruto,
identificador individual de requisição ou de tarefa, nem caminho de dispositivo
é publicado.

Relacionados: [Relatório da série Multi-WAN 05](NEXUS_V2700_MULTIWAN_05_SERIES_PT.md) ·
[Relatório Multi-WAN 05E](NEXUS_V2700_MULTIWAN_05E_PT.md) ·
[Índice da documentação](README.pt-BR.md)

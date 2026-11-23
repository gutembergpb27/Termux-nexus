# Nexus Runtime Platform V2700

## Multi-WAN 05E — Piloto físico experimental (Windows ↔ Android)

**Data de referência:** 23 de novembro de 2026

**Classificação:** documentação pública de experimento; evidências brutas mantidas em ambiente privado.

**Estado:** piloto cliente-servidor executado, manifests SHA-256 verificados nos dois equipamentos, conjuntos de identificadores concluídos correlacionados. Auditoria integral do protocolo **não** concluída.

> **Escopo:** este resultado se refere a ferramentas de laboratório MW05E isoladas. Não demonstra consenso distribuído, eleição por maioria, fencing, commit distribuído ou prontidão para produção.

### 1. Ambiente e método

O operador utilizou um computador Windows com acesso declarado por fibra e um Motorola Edge 40 Neo com Android/Termux e acesso declarado por Starlink. A comunicação entre dispositivos ocorreu via Tailscale. Diagnósticos anteriores observaram um caminho de controle Tailscale por DERP, mas o caminho de cada mensagem do piloto não foi comprovado por captura ou telemetria independente.

O cliente experimental Windows enviou tarefas a um servidor Python no Android com segredo HMAC compartilhado e journal persistente. O checkout de referência de ambos os laboratórios foi relatado no commit `d783a863d7b1ac5db88922726606e75c5d17c4fb`, sem alterações no repositório ao final das verificações apresentadas.

### 2. Resultados observados

| Verificação | Resultado apresentado |
|---|---:|
| Conectividade Windows → Android | TCP acessível na interface Tailscale |
| Código de saída do cliente MW05E | `0` |
| Eventos totais do cliente | 96 |
| Ocorrências de `completed` no cliente | 67 |
| **IDs únicos concluídos no cliente** | **66** |
| Eventos JSONL do servidor Android | 161 válidos / 161 |
| Eventos JSONL do journal Android | 202 válidos / 202 |
| **IDs únicos de tarefas no servidor / journal** | **66 / 66** |
| IDs coincidentes servidor × journal | 66, sem IDs exclusivos |
| Tarefas com `output_sha` presente nos dois registros | 66 |
| Tarefas sem interseção de hashes de saída comparáveis | 0 |
| Rejeições `rejected_unauthenticated` no servidor | 20 |
| Consultas respondidas `status_answered` | 2 |
| Resposta `answered_from_journal` | 1 |

O resumo do cliente incluiu operações confirmadas nas categorias warmup, consecutive, spaced e latency; registrou `CONFIRMED_CACHED` em cenário de duplicação e após um timeout inicial marcado `UNKNOWN`. Houve 20 resultados `UNKNOWN` em controles negativos e 20 rejeições não autenticadas registradas pelo servidor. **Essas duas contagens ainda não foram correlacionadas individualmente**; a ausência de execução indevida para cada controle não está atestada neste documento.

### 3. Correlação dos identificadores

Os identificadores `task_id` de tarefas concluídas foram deduplicados, ordenados, serializados como lista JSON canônica (`ensure_ascii=True`, `separators=(',', ':')`, UTF-8) e submetidos a SHA-256 em cada dispositivo. Ambos retornaram **66 IDs únicos** e a mesma fingerprint:

```text
dd2cb1d4672ec38fee4bfb279280757025a17497cd656c73c64cd6abfe797e5f
```

A igualdade da fingerprint é evidência forte de identidade dos conjuntos de identificadores registrados, não verificação independente dos conteúdos matemáticos retornados ou de todas as mensagens da rede. A diferença entre 67 ocorrências `completed` no cliente e 66 IDs únicos é compatível com uma repetição, mas a ocorrência específica não foi auditada evento a evento.

### 4. Integridade das evidências

As verificações de manifestos apresentadas pelo operador foram:

- **Windows:** `listed=1 mismatched=[] missing=[] invalid_entries=[] unlisted=[]`, referente ao arquivo de evidência do cliente.
- **Android:** `listed=4 mismatched=[] missing=[] invalid_entries=[] unlisted=[]`, para registros do servidor, journal e arquivos auxiliares.
- **SHA-256 do manifesto Android:** `5d115a3b172760e8cf2a4aac70094b79d6567f3f31bf81628a8e0d4e1166c5d8`.

As evidências originais e seus nomes de arquivo completos permanecem fora deste documento público. Estes resultados provêm de saídas do terminal compartilhadas pelo operador; os arquivos originais não foram independentemente reprocessados na elaboração desta documentação.

### 5. Limitações e trabalhos pendentes

- Comparação privada tarefa a tarefa de cliente, servidor e journal, inclusive payloads e cálculo independente de `output_sha`.
- Correlação individual de cada controle negativo e verificação de ausência de execução indevida.
- Auditoria específica de HMAC, replay, TTL, respostas reaproveitadas, timeout e recuperação transacional.
- Comprovação instrumentada do caminho de transporte da carga e eventual comparação de desempenho entre links.
- Validação de quorum, consenso, failover e segurança sob partição — **fora do escopo deste piloto**.

**Conclusão delimitada:** o Multi-WAN 05E demonstrou um fluxo experimental remoto concluído pelo cliente e **correlação 66/66 dos identificadores de tarefas concluídas entre Windows, servidor Android e journal**. Não constitui certificação do runtime distribuído nem promessa de exactly-once ou de segurança de produção.

**Privacidade:** não são publicados endereços privados, segredos HMAC, identificadores individuais das tarefas ou arquivos JSONL brutos.

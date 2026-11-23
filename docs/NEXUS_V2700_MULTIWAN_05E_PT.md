# Nexus Runtime Platform V2700

## Multi-WAN 05E — Piloto físico experimental entre dispositivos (Windows ↔ Android)

[English](NEXUS_V2700_MULTIWAN_05E_EN.md) · **Português (Brasil)**

**Data de referência:** 23 de novembro de 2026

**Classificação:** documentação experimental pública; evidências brutas mantidas em caráter privado.

**Status:** piloto cliente-servidor executado. Os conjuntos de identificadores de tarefas concluídas foram correlacionados, e as evidências do lado cliente (Windows) foram reverificadas de forma independente. Os números do servidor e do journal Android são reportados pelo operador. A auditoria completa do protocolo **não** foi concluída.

> **Escopo:** estes resultados se referem a ferramentas de laboratório MW05E isoladas. Não demonstram consenso distribuído, eleição por maioria, fencing de líder, commit distribuído, execução exatamente uma vez nem prontidão para produção.

### 1. Ambiente e método

O operador utilizou dois dispositivos:
- um computador Windows com conexão descrita como fibra;
- um Motorola Edge 40 Neo com Android/Termux e conexão descrita como Starlink.

Os dispositivos se comunicaram via Tailscale. Diagnósticos anteriores observaram conectividade de controle do Tailscale roteada por DERP. O caminho de transporte de cada mensagem de trabalho do piloto não foi instrumentado de forma independente.

Um cliente experimental no Windows enviou tarefas de computação a um servidor Python no Android. O servidor usava um segredo HMAC compartilhado e um journal persistente. Os dois checkouts de referência isolados foram relatados no commit `d783a863d7b1ac5db88922726606e75c5d17c4fb`, sem modificações no repositório nas verificações relatadas após a execução.

### 2. Resultados observados

Classes de evidência:
- **Verificado de forma independente**: recalculado a partir do arquivo de evidência do cliente Windows durante a preparação da documentação.
- **Reportado pelo operador**: extraído da saída de terminal apresentada pelo operador.

| Verificação | Resultado | Classe |
|---|---:|---|
| Conectividade Windows → Android | TCP acessível pela interface Tailscale | Reportado pelo operador |
| Código de saída do cliente MW05E | `0` | Reportado pelo operador |
| Registros JSONL do cliente | 96 | Verificado de forma independente |
| Ocorrências de `completed` no cliente | 67 | Verificado de forma independente |
| **IDs únicos de tarefas concluídas no cliente** | **66** | Verificado de forma independente |
| Registros JSONL do servidor Android | 161 válidos / 161 | Reportado pelo operador |
| Registros JSONL do journal Android | 202 válidos / 202 | Reportado pelo operador |
| **IDs únicos de tarefas no servidor / journal** | **66 / 66** | Reportado pelo operador |
| IDs coincidentes servidor × journal | 66, nenhum exclusivo de um dos lados | Reportado pelo operador |
| Tarefas com `output_sha` no servidor e no journal | 66 | Reportado pelo operador |
| Tarefas sem interseção entre conjuntos comparáveis de hashes de saída | 0 | Reportado pelo operador |
| Eventos `rejected_unauthenticated` no servidor | 20 | Reportado pelo operador |
| Eventos `status_answered` no servidor | 2 | Reportado pelo operador |
| Eventos `answered_from_journal` no servidor | 1 | Reportado pelo operador |

O resumo do cliente relatou resultados confirmados nas categorias warmup, consecutive, spaced e latency. `CONFIRMED_CACHED` apareceu em uma duplicata e novamente após um timeout inicial `UNKNOWN`.

As evidências do cliente, reverificadas de forma independente, contêm 20 tentativas de controle negativo (assinatura alterada, segredo errado, expirada, reenvio idêntico), todas classificadas como `UNKNOWN`: nenhum resultado foi aceito. O servidor registrou 20 rejeições não autenticadas (reportado pelo operador). **As tentativas individuais de controle negativo não foram associadas a essas rejeições do servidor.** Os registros de rejeição do servidor não trazem identificador de requisição nem de tarefa. Este relatório não atesta que cada operação inválida tentada deixou de causar execução.

O journal registra um `output_sha` para as 66 tarefas concluídas. O corpo da saída de uma tarefa não foi retido no journal. A auditoria posterior reconstruiu essa saída e constatou que seu hash coincidia (reportado pelo operador). Ver o [relatório consolidado da série Multi-WAN 05](NEXUS_V2700_MULTIWAN_05_SERIES_PT.md).

### 3. Correlação dos identificadores de tarefas

Os valores `task_id` concluídos foram processados em cada dispositivo:
1. sem duplicatas e ordenados;
2. serializados em JSON (`ensure_ascii=True`, `separators=(',', ':')`, UTF-8);
3. submetidos a SHA-256.

Os dois lados produziram **66 IDs distintos concluídos** e a mesma impressão digital:

```text
dd2cb1d4672ec38fee4bfb279280757025a17497cd656c73c64cd6abfe797e5f
```

A impressão digital do Windows foi recalculada de forma independente a partir das evidências do cliente e coincide. A impressão digital do Android é reportada pelo operador. Impressões digitais coincidentes são evidência forte de que os conjuntos registrados de IDs de tarefas concluídas são idênticos. Elas não verificam de forma independente as saídas matemáticas nem cada troca de rede.

As 67 ocorrências `completed` no cliente correspondem a 66 IDs distintos. Isso é coerente com pelo menos uma ocorrência duplicada, mas o evento repetido específico não foi rastreado individualmente.

### 4. Integridade das evidências

- **Windows:** `listed=1 mismatched=[] missing=[] invalid_entries=[] unlisted=[]` para o arquivo de evidência do cliente. Reverificado de forma independente: 1/1 arquivo OK.
- **Android:** `listed=4 mismatched=[] missing=[] invalid_entries=[] unlisted=[]` para as evidências do servidor, do journal e auxiliares. Reportado pelo operador.
- **SHA-256 do manifesto Android:** `5d115a3b172760e8cf2a4aac70094b79d6567f3f31bf81628a8e0d4e1166c5d8`. Reportado pelo operador.

As evidências originais e os nomes detalhados dos arquivos foram excluídos intencionalmente desta nota pública.

Os seguintes números do lado cliente foram reverificados de forma independente a partir do arquivo de evidência do Windows:
- 96 registros;
- 67 ocorrências `completed` / 66 IDs únicos;
- a impressão digital;
- 20 controles negativos `UNKNOWN`;
- o manifesto (1/1).

Os números do servidor e do journal Android provêm da saída de terminal apresentada pelo operador. Esses arquivos não foram reabertos nem reprocessados de forma independente.

### 5. Limitações e verificações pendentes

- Comparação privada, evento a evento, dos dados do cliente, do servidor e do journal, incluindo payloads e recálculo independente de `output_sha` (relatada posteriormente pelo operador; ver o relatório da série).
- Associação individual de todos os controles negativos e prova de ausência de execução indevida.
- Auditoria detalhada de HMAC, replay, TTL, cache, timeout e recuperação transacional.
- Verificação instrumentada do caminho do tráfego de trabalho real e eventual comparação controlada de desempenho entre links.
- Quórum, consenso, failover e segurança sob partição de rede, que estão **fora do escopo deste piloto**.

**Conclusão delimitada:** o Multi-WAN 05E produziu um fluxo experimental remoto concluído pelo cliente e **correlação 66/66 dos identificadores de tarefas concluídas entre o Windows, o servidor Android e seu journal**. O lado cliente foi reverificado de forma independente; o lado do servidor e do journal é reportado pelo operador. Isto não é certificação do runtime distribuído nem promessa de execução exatamente uma vez ou de segurança em nível de produção.

**Privacidade:** nenhum endereço privado, segredo HMAC, identificador individual de tarefa ou arquivo JSONL bruto é publicado.

Relacionados: [Multi-WAN 01–03](NEXUS_V2700_MULTIWAN_01_03_PT.md) · [Multi-WAN 04C](NEXUS_V2700_MULTIWAN_04C_PT.md) · [Série Multi-WAN 05](NEXUS_V2700_MULTIWAN_05_SERIES_PT.md) · [Índice da documentação](README.pt-BR.md)

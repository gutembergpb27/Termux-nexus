# Nexus Runtime Platform — Índice da documentação

[English](README.md) · **Português (Brasil)** · [Voltar ao README do projeto](../README.pt-BR.md)

Cada documento deste repositório pertence a um de quatro grupos. Confira o
grupo antes de usar um número de qualquer documento: apenas o primeiro grupo
descreve o estado atual da `main`.

| Grupo | Significado |
|---|---|
| **A · Estado atual da `main`** | Descreve o código, os testes e a CI da `main` hoje. |
| **B · Evidências de validação** | Experimentos registrados com escopo e data fixos. Os números valem apenas para aquele experimento. |
| **C · Laboratórios experimentais** | Ferramentas e resultados fora do runtime da `main`. |
| **D · Registros históricos e de release** | Preservados para rastreabilidade. Não os use como afirmações sobre o projeto atual. |

---

## Comece por aqui

1. [README do projeto](../README.pt-BR.md): visão geral, status, capacidades e limitações.
2. [Project State](PROJECT_STATE.md): estado atual detalhado, histórico de integração e achados em aberto.
3. [Auditoria de segurança de consenso W08-A](NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md): por que o runtime não implementa consenso.
4. [External Evaluation Guide](NEXUS_V2700_EXTERNAL_EVALUATION_GUIDE.md): roteiro guiado para avaliadores externos.

---

## A · Estado atual da `main`

| Documento | Finalidade |
|---|---|
| [Project State](PROJECT_STATE.md) | Estado atual, números da CI, histórico de integração (PR #101–#108) |
| [Auditoria de segurança de consenso W08-A](NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md) | Auditoria somente leitura do código de autoridade, quórum e fencing (F1–F10, INV-01..INV-07) |
| [Migração do modo de cluster W08-B](NEXUS_V2700_W08B_CLUSTER_MODE_MIGRATION.md) | Comportamento de `NEXUS_CLUSTER_MODE`, limites do `single`, migração |
| [Security Trust Boundary](NEXUS_V2700_SECURITY_TRUST_BOUNDARY.md) | Fronteiras de segurança e de confiança |
| [Distributed Commit Contract](NEXUS_V2700_DISTRIBUTED_COMMIT_CONTRACT.md) | Contrato que um futuro commit distribuído deverá cumprir |
| [V2700 Architecture Plan](NEXUS_V2700_ARCHITECTURE_PLAN.md) | Arquitetura e eixos de desenvolvimento |
| [Technical Positioning](NEXUS_V2700_TECHNICAL_POSITIONING.md) | Escopo e posicionamento tecnológico neutro |
| [Executive Technical Brief](NEXUS_V2700_EXECUTIVE_TECHNICAL_BRIEF.md) | Visão geral externa. Escrito antes das PRs #101/#104: leia em conjunto com as limitações do README |

## B · Evidências de validação

| Documento | Escopo |
|---|---|
| [Resilience Case Study](NEXUS_V2700_RESILIENCE_CASE_STUDY.md) | Cenário controlado de perda do MASTER em três nós |
| [Eixo 10 — Temporização de quórum](validation/NEXUS-V2700-AXIS-10-QUORUM-TIMING.md) | Temporização de quórum; medido antes do QS-C01 |
| [Eixo 11 — Resiliência estatística](validation/NEXUS-V2700-AXIS-11-STATISTICAL-RESILIENCE.md) | 29 amostras físicas; medido antes do QS-C01 |
| [External Resilience Demonstration](NEXUS_V2700_EXTERNAL_RESILIENCE_DEMO.md) | Navegação pelas evidências de resiliência |
| [External Reproduction Protocol](NEXUS_V2700_EXTERNAL_REPRODUCTION_PROTOCOL.md) | Como reproduzir os resultados registrados |
| [Validação Windows + Android](windows_android_validation.md) | Validação física anterior com múltiplos dispositivos |
| [Evidências físicas do Eixo 7](../validation/axis7-physical/README.md) | Registros de validação física |
| [Convergência multinó](../validation/multi-node-convergence/REAL-PROCESS-PASS.md) | Registro de convergência com processos reais |
| [Protocolo de recoordenação de papéis](../validation/role-recoordination/PROTOCOL.md) | Protocolo de teste de recoordenação |

## C · Laboratórios experimentais

### Experimentos Multi-WAN entre dispositivos

| Marco | Status | Relatório |
|---|---|---|
| Multi-WAN 01–03: mensagens autenticadas, Windows ↔ Android | Documentado, com errata (seção 8) | [PT](NEXUS_V2700_MULTIWAN_01_03_PT.md) · [EN](NEXUS_V2700_MULTIWAN_01_03_EN.md) |
| Multi-WAN 04C: computação remota autenticada | Documentado; reportado pelo operador, lado Android a partir de transcrição do operador | [PT](NEXUS_V2700_MULTIWAN_04C_PT.md) · [EN](NEXUS_V2700_MULTIWAN_04C_EN.md) |
| Multi-WAN 05E: piloto físico de computação remota | Documentado; lado cliente reverificado de forma independente; servidor/journal Android reportados pelo operador | [PT](NEXUS_V2700_MULTIWAN_05E_PT.md) · [EN](NEXUS_V2700_MULTIWAN_05E_EN.md) |
| Série consolidada MW05E–MW05K-2: auditoria e controles negativos locais | Relatório consolidado; números em grande parte reportados pelo operador | [PT](NEXUS_V2700_MULTIWAN_05_SERIES_PT.md) · [EN](NEXUS_V2700_MULTIWAN_05_SERIES_EN.md) |
| Piloto físico Windows–Motorola dos controles do MW05K-2 | Aguardando conectividade Starlink | — |

### Ferramental de validação não integrado ao runtime

| Documento | Finalidade |
|---|---|
| [Harness S1–S5](../validation/s1-s5-harness/README.md) | Harness de validação W05/W06 |
| [Endurecimento do hub](../validation/hub-hardening/README.md) | Protótipo de hub endurecido W07 |
| [Proposta de integração do hub endurecido](../validation/hub-hardening/INTEGRATION_PROPOSAL.md) | Proposta; não integrada |
| [NIRT-01](../nirt/NIRT-01.md) · [NIRT-02](../nirt/NIRT-02.md) | Registros de candidato externo e de integração auditada |

## D · Registros históricos e de release

### Notas de release

[v2700.0.0-rc2](../RELEASE_NOTES_v2700.0.0-rc2.md) ·
[v2700.0.0-rc1](../RELEASE_NOTES_v2700.0.0-rc1.md) ·
[v2600.0.0-alpha.1](../RELEASE_NOTES_v2600.0.0-alpha.1.md) ·
[v2500.0.0-rc1](../RELEASE_NOTES_v2500.0.0-rc1.md) ·
[runtime-v1-beta](../RUNTIME_V1_BETA_RELEASE.md)

### Arquitetura e especificações anteriores

| Documento | Observação |
|---|---|
| [Mapa de arquitetura v2500](NEXUS_V2500_ARCHITECTURE_MAP.md) | Referência histórica de arquitetura |
| [Architecture Reality Map](../NEXUS_ARCHITECTURE_REALITY_MAP.md) | Mapa de alegações e evidências anterior à V2700 |
| [Mesh Protocol V1](../NEXUS_MESH_PROTOCOL_V1.md) | Especificação de protocolo. Nem todas as capacidades descritas estão implementadas |
| [Linha de base canônica](canonical/BASELINE.md) · [limitações](canonical/LIMITATIONS.md) | Época da branch `canonical-evidence` (C20) |
| [Dossiê C20](../DOSSIE_TECNICO_C20.md) · [linha de base de integridade](../INTEGRITY_BASELINE_C20.md) · [manifesto](../MANIFESTO_CRIPTOGRAFICO_C20.md) · [registro final](../REGISTRO_FINAL_C20.md) | Ciclo de integridade C20 |
| [README legado](legacy/README_legacy.md) | README anterior do projeto |
| [Product Bridge](../NEXUS_PRODUCT_BRIDGE.md) | Texto de visão de produto. Não faz afirmações técnicas |

### Material inicial v500/v600, superado

Estes documentos são do período v500/v600. Eles contêm afirmações que as
evidências atuais **não sustentam**, como perda zero de dados, prontidão para
produção, percentuais de disponibilidade, valores de valuation e "consenso"
baseado em presença. Eles foram mantidos sem alterações como registros
históricos, e cada um traz um aviso no início.

[White paper](../WHITE_PAPER.md) ·
[Dashboard executivo](../EXECUTIVE_DASHBOARD.md) ·
[Pitch financeiro](../FINANCIAL_PITCH.md) ·
[Protocolo de validação v500](../VALIDATION.md)

---

## Convenções da documentação

- O inglês é o idioma principal. Os documentos que têm versão em português apontam para ela nas primeiras linhas.
- Todo número informa o commit, a execução ou o experimento de origem.
- Resultados informados pelo operador e não reprocessados de forma independente são identificados como **reportados pelo operador**.
- Logs brutos, endereços privados, segredos e identificadores de dispositivos nunca são publicados.

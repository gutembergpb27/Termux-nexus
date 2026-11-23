# Nexus Runtime Platform V2700

## Relatório experimental Multi-WAN 01–03

**Data de referência:** 22–23 de novembro de 2026

**Classificação:** Validação experimental entre dispositivos.

**Situação:** Evidências consolidadas. Não constitui
certificação de produção.

---

## 1. Objetivo

Investigar a comunicação entre dispositivos reais
utilizando componentes de transporte e autenticação
da Nexus Runtime Platform V2700.

O ambiente experimental envolveu:

- Windows, utilizando conexão identificada como fibra óptica.
- Motorola Edge 40 Neo com Android/Termux, utilizando conexão identificada como Starlink.
- Comunicação entre dispositivos utilizando Tailscale.

Os experimentos foram conduzidos separadamente
do runtime principal.

## 2. Multi-WAN 01 — Conectividade externa

Foram registrados cinco testes de conexão TCP/TLS
em cada dispositivo.

Medianas TLS observadas:

- Windows/fibra: 57,6 ms.
- Android/Starlink: 101,0 ms.

Resultado: conectividade externa demonstrada
nos dois ambientes experimentais.

As medições não representam uma comparação controlada
de desempenho entre os provedores, pois envolveram
equipamentos e condições diferentes.

## 3. Multi-WAN 02 — Comunicação entre dispositivos

Foi demonstrada comunicação TCP de aplicação
entre Windows e Android, utilizando Tailscale.

Resultados:

- Cinco mensagens enviadas pelo cliente.
- Cinco respostas ACK verificadas.
- Resultado: 5/5 mensagens confirmadas.
- RTT mediano: 76,74 ms.

O experimento utilizou um protocolo Python
independente do protocolo de consenso da Nexus.

O caminho efetivo de cada mensagem TCP, direto ou
por DERP, não foi registrado individualmente.

## 4. Multi-WAN 03 — Autenticação real de mensagens

Foram avaliados componentes reais do projeto Nexus:

- NexusProtocol.
- ReplayCache.
- NexusTransport.

### Validação funcional local

- 13 testes executados.
- 13 testes aprovados.
- Nenhuma falha registrada.

### Comunicação Windows/Android

Resultados consolidados:

- Windows: 5/5 mensagens autenticadas aprovadas.
- Windows: 2/2 controles negativos aprovados.
- Android: 5/5 conexões esperadas aceitas.
- Android: 2/2 controles negativos rejeitados.

RTT mediano registrado: 153,998 ms.

A auditoria cruzada foi classificada como:

**CROSS-DEVICE EVIDENCE PASS**

A validação demonstra o comportamento observado
no experimento específico, sem comprovar a integração
completa do runtime distribuído.

## 5. Integridade das evidências

### Pacote Multi-WAN 01/02

Arquivo:

`NEXUS-MULTIWAN-20261122T191044-e0a0252d.zip`

SHA-256:

`f630a50e2fd703a784de500f719f315f4ee50891929b9d615817cb3deacb6ee9`

### Pacote Multi-WAN 03

Arquivo:

`NEXUS-MW03-EVIDENCE-20261123T001842Z-853db823.zip`

SHA-256:

`9e9dda7e86f50598359a5365d231c21ddd6a34cad49589c773075461da8d489f`

### Relatório de auditoria cruzada

Arquivo:

`REPORT-MULTIWAN03.json`

SHA-256:

`9016f3a629726884bb7343412e8b9d04b40102b685a3592d1afdd797ea9a5cd4`

Os pacotes foram validados localmente.

Os arquivos brutos de evidência não são incluídos
nesta atualização do GitHub.

## 6. Limitações

Os resultados não demonstram:

- Consenso distribuído operacional.
- Eleição de líder por maioria em ambiente operacional.
- Replicação persistente entre nós.
- Fencing distribuído.
- Segurança diante de partições de rede.
- Tolerância arbitrária a falhas.
- Prontidão para produção.
- Comparação controlada entre provedores.

A comunicação autenticada observada no laboratório
não equivale à certificação do runtime principal.

## 7. Preservação

A documentação foi preparada em uma worktree
isolada do repositório oficial.

Os laboratórios W17-A/B/C/D e os arquivos originais
de evidências permanecem fora do escopo desta alteração.

Nenhuma chave, token ou endereço privado
é publicado neste relatório.

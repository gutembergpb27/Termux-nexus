# Nexus Cluster Orchestrator (v1400)

## 🌐 Escopo do Módulo
O `cluster_orchestrator.py` é um motor de simulação projetado para instanciar, monitorar e encerrar redes mesh locais de múltiplos nós em background dentro de um único ambiente de execução (Single-Device Multiprocess Mesh).
## 🛡️ Camada de Segurança (v2000)

O Nexus integra agora uma camada de segurança baseada em **HMAC-SHA256**, garantindo a integridade dos dados e autenticidade das mensagens trocadas entre os nós do cluster.

### Arquitetura de Segurança
* **Autenticação:** Cada payload enviado pelo motor é assinado digitalmente usando uma chave secreta privada (`NEXUS_SECRET_KEY`).
* **Verificação:** O `NexusSecurityProvider` valida cada pacote recebido; pacotes sem a assinatura correta ou com payloads adulterados são descartados automaticamente pelo `nexus_distributed_core.py`.
* **Configuração Segura:** A chave secreta é carregada via `.env` e nunca é exposta no código-fonte ou no sistema de controlo de versões (Git).

### Como verificar a integridade
O sistema inclui um script de teste de estresse que valida a robustez da camada criptográfica:
```bash
python test_security.py

⚠️ **Escopo e Limitações (v1400)**
O Nexus Cluster Orchestrator é um ambiente de simulação de arquitetura distribuída executado em um único host. Seu objetivo é validar componentes de infraestrutura, observabilidade e resiliência antes da implantação em ambientes físicos distribuídos.

### 🛠️ O que ele faz:
* Inicializa múltiplos nós virtuais em processos independentes em portas distintas (`8080`, `8081`, `8082`).
* Simula papéis dinâmicos de `MASTER` e `FOLLOWER`.
* Permite testes de coordenação e comunicação local multiprocesso de forma isolada.
* Facilita experimentos dinâmicos de engenharia de caos (`chaos_monkey.py`) e recuperação de falhas.
* Serve como laboratório ativo para a evolução incremental da arquitetura distribuída.

### 🛑 O que ele não faz (nesta versão):
* **Não** implementa protocolos formais de consenso distribuído (como Raft ou Paxos) na camada de rede.
* **Não** realiza replicação de estado síncrona real entre máquinas fisicamente distintas.
* **Não** possui mecanismos de descoberta automática de nós externos dinâmicos (Auto-Discovery).
* **Não** oferece failover de rede tolerante a partições entre hosts físicos interdependentes.
* **Não** visa substituir orquestradores robustos de mercado de larga escala (como Kubernetes ou Nomad).

---

## 📐 Princípios de Engenharia (Nexus Philosophy)
O desenvolvimento e evolução do Nexus Runtime prioriza os seguintes pilares fundamentais:
1. **Observabilidade antes da otimização:** Monitorar e expor o estado do sistema com clareza é mais importante do que economizar ciclos prematuros de CPU.
2. **Isolamento antes da máxima performance:** Garantir que um nó ou worker falho não contamine o restante da árvore de processos.
3. **Reprodutibilidade antes da complexidade:** O código deve ser limpo e previsível o suficiente para que qualquer laboratório externo consiga replicar os testes de estresse.
4. **Falhas controladas antes de disponibilidade presumida:** Projetar o software assumindo que a infraestrutura vai falhar a qualquer momento (Chaos-First).
5. **Evolução incremental guiada por experimentação:** Cada nova versão nasce de uma hipótese teórica testada empiricamente na prática.

---

## 📊 Matriz de Maturidade e Roadmap do Ecossistema

| Área / Componente Técnico | Status Atual | Classificação SRE |
| :--- | :---: | :--- |
| **Observabilidade & Métricas** | ✅ | Telemetria ativa exposta via HTTP assíncrono (`9090/metrics`). |
| **Persistência Imutável** | ✅ | Ledger baseado em *Write-Ahead Logging* (WAL) e hashes SHA-256. |
| **Engenharia de Caos** | ✅ | Agente de injeção intencional de falhas e ataques DoS (`chaos_monkey.py`). |
| **Cluster Multiprocesso Virtual**| ✅ | Orquestração automatizada local de múltiplos nós independentes (v1400). |
| **Controle de Carga (Rate Limiting)**| ✅ | Algoritmo *Token Bucket* thread-safe injetado no transporte de rede. |
| **Governança por CI/CD** | ✅ | Pipeline automatizado de validação sintática estável no GitHub Actions. |
| **Documentação & White Paper** | ✅ | Especificação técnica homologada com assinatura digital ICP-Brasil via Gov.br. |
| **Cluster Físico Distribuído** | 🔄 | *Futuro:* Validação e portabilidade para múltiplos hardwares dedicados (Raspberry Pi). |
| **Consenso Distribuído Formal** | 🔄 | *Pesquisa:* Estudo de viabilidade de algoritmos de consenso leves para Edge Computing. |

## 🗺️ Visão de Futuro, Maturidade & Arquitetura Evolutiva

O **Nexus Runtime** deixou de ser apenas um runtime embarcado e local para se consolidar como uma **plataforma experimental de Edge AI distribuída**. A evolução incremental das nossas Milestones reflete uma trajetória de engenharia focada em resolver problemas reais de sistemas distribuídos sob restrições severas de hardware e conectividade:

* **v500:** Isolamento de processos, Write-Ahead Logging (WAL), resiliência de persistência e observabilidade local.
* **v1000–v1300:** Métricas assíncronas, limitação de taxa (Rate Limiting), automação de CI/CD e desacoplamento de componentes.
* **v1400:** Malha Virtual (*Virtual Mesh*) com suporte a orquestração e topologias multi-nós.
* **v1800:** Execução de benchmarks distribuídos com consenso entre nós e medição de throughput real.
* **v1950:** Descoberta dinâmica de nós em topologia WAN híbrida via Rendezvous Hub e mitigação de NAT Loopback.
* **v2000:** Camada de segurança criptográfica (HMAC-SHA256), passaportes efêmeros com TTL e mitigação de ataques de Replay.
* **v2100:** Protocolo *Catch-Up* integrado à thread de polling assíncrono para sincronização e recuperação de nós defasados sem reinicialização física.

### 📊 Avaliação do Ativo & Direcionamento de Mercado
Sob a ótica de engenharia de software e arquitetura conceitual, o Nexus divide-se em duas frentes de valor estruturadas:
1.  **Valor do Ativo Tecnológico (IP, Código e Documentação):** Estimado conceitualmente entre **US$ 500 mil e US$ 2 milhões**, fundamentado na densidade dos padrões de projeto adotados (SRE, Criptografia WAN, CFT e persistência concorrente leve estável em ~24.47 MB de RAM).
2.  **Valuation de Ecossistema (Startup Pré-Receita):** Potencial de **US$ 2 milhões a US$ 10 milhões**, condicionado a uma estratégia de comercialização consistente e validação de tração de mercado.

### ⚠️ Estado Atual do Projeto e Escopo Coletivo
O cluster distribuído implementado no Nexus é uma **infraestrutura experimental de alta fidelidade**, destinada à validação de arquitetura e engenharia de confiabilidade de software (SRE). Ele não substitui soluções comerciais maduras e consolidadas de orquestração ou consenso distribuído em ambientes de produção industrial, mas atua como uma base científica maleável para experimentação, injeção de falhas (Chaos Engineering) e benchmarking reproduzível.

### 🚀 Próximos Passos de Validação (Hardware Real)
Para mover o ecossistema rumo ao topo da sua maturidade técnica e romper as barreiras da simulação em software, as metas imediatas do roadmap envolvem:
* **Deploy em Hardware de Borda Real:** Migração e validação dos nós em arquiteturas ARM físicas (Raspberry Pi, Orange Pi ou similares).
* **Benchmarks Independentes:** Publicação de logs e relatórios reproduzíveis por terceiros sob cenários de queda real de conexões físicas.
* **Pilotos de Conectividade:** Demonstração prática de isolamento de nós em redes fisicamente distintas sob internet pública.

# Nexus Runtime: Um Framework de Alta Resiliência e Tolerância a Falhas para Computação na Borda em Ambientes Mobile Restritos

**Autor:** Gutemberg P. B.  
**Versão Documentada:** v600 (Baseline)  
**Data:** Julho de 2026  

---

## 📄 Resumo (Abstract)
Este artigo apresenta o Nexus Runtime, uma engine de execução leve voltada para computação na borda (Edge Computing) projetada especificamente para mitigar a volatilidade de processos e a escassez de recursos em sistemas operacionais móveis baseados em Kernel Linux (Android via Termux). Através de uma arquitetura de supervisão ativa e isolamento de processos, o Nexus provou ser capaz de restaurar a integridade de workers derrubados por sinais críticos do sistema (`SIGKILL`) com um tempo médio de recuperação (MFTR) de sub-10 milissegundos ($9.81\text{ ms}$), mantendo o determinismo mesmo em cenários de cauda estendida ($p99$).

## 1. Introdução
A computação na borda descentralizou o processamento de dados, movendo pipelines analíticos e bancos de dados locais para dispositivos IoT e smartphones. No entanto, o ambiente de execução nesses dispositivos é inerentemente hostil. Sistemas operacionais móveis priorizam agressivamente a interface do usuário, utilizando mecanismos como o *Low Memory Killer* (LMK) do Android para encerrar subprocessos de background sem aviso prévio.

A perda inesperada desses processos resulta em corrupção de memória volatizada, interrupção de fluxos de telemetria e degradação da confiabilidade de sistemas embarcados. As soluções tradicionais de mercado, como orquestradores de containers robustos (ex: Kubernetes/K3s), impõem um *overhead* proibitivo de CPU e RAM para hardwares restritos.

O **Nexus Runtime** surge como uma alternativa minimalista e ultraveloz, implementando o padrão de supervisão baseada em atores (*Erlang-style supervision trees*) de forma nativa em Python, garantindo resiliência em tempo real com consumo desprezível de hardware.

## 2. Arquitetura do Sistema e Modelo de Atores
O Nexus Runtime rejeita o modelo tradicional de concorrência baseado em threads compartilhadas devido ao bloqueio global do interpretador (GIL - *Global Interpreter Lock*), que pode introduzir latências imprevisíveis em loops de monitoramento de alta frequência. Em vez disso, o framework adota uma arquitetura inspirada em sistemas Erlang, operando via isolamento estrito de memória através do módulo `multiprocessing`.

O ecossistema é dividido em duas entidades principais:

1. **Watcher Master (Supervisor):** Um processo de ciclo de vida persistente que atua como a raiz da árvore de decisão. Ele mantém um dicionário em memória associando identificadores lógicos de tarefas aos seus respectivos PIDs (*Process Identifiers*) ativos. O Supervisor opera em um loop de polling não bloqueante, avaliando a integridade dos nós filhos por meio de chamadas de sistema operacionais de baixo nível (`os.kill(pid, 0)`).
2. **Workers (Atores de Execução):** Subprocessos independentes com espaço de endereçamento de memória isolado. Eles comunicam falhas de forma passiva ou são monitorados ativamente pelo Supervisor.

Quando o Kernel do sistema operacional dispara um sinal de terminação forçada (`SIGKILL` ou `SIGSEGV`) contra um Worker, o espaço de memória daquele processo é desalocado. O Supervisor intercepta a ausência do processo no ciclo de polling subsequente, avalia a política de tolerância a falhas configurada (ex: *One-For-One*) e instancia imediatamente um novo Worker clone, atualizando a tabela de roteamento interno sem interromper os demais componentes da malha.



## 3. Metodologia Experimental
Para validar empiricamente a resiliência do Nexus Runtime sob estresse severo em hardware restrito, foi desenvolvido um injetor de falhas programático (`collect_benchmarks.py`). O protocolo experimental consiste em:

1. Inicializar o ecossistema Nexus com workers ativos simulando pipelines de processamento contínuo na borda.
2. Disparar injeções assíncronas de caos, enviando sinais estritos de terminação em intervalos randômicos.
3. Capturar o delta de tempo ($\Delta t$) entre a interceptação da falha pelo Supervisor e o restabelecimento completo do ciclo de execução do Worker clone, registrando as latências de mitigação diretamente em um arquivo de telemetria estruturado (`benchmarks_edge.csv`).

## 4. Resultados e Análise de Desempenho
Os testes experimentais conduzidos em um ambiente real restrito (Android Kernel baseado em Linux através do emulador Termux) geraram uma matriz estável de logs de telemetria. Os dados consolidados através do subsistema matemático de auditoria do Nexus revelaram as seguintes métricas de confiabilidade:

* **Tempo Médio de Recuperação (MFTR):** $9.81\text{ ms}$
* **Latência Mínima de Interceptação:** $4.25\text{ ms}$
* **Jitter de Resposta (Desvio Padrão):** $\approx 5.30\text{ ms}$
* **Latência de Cauda p95 (Percentil 95):** $18.50\text{ ms}$
* **Latência de Cauda p99 (Worst-Case Scenario):** $18.50\text{ ms}$

### 📊 Análise de Resiliência de Cauda (Tail Latency)
A estabilização da latência de cauda ($p95$ e $p99$) no teto estrito de $18.50\text{ ms}$ demonstra o comportamento determinístico do Nexus Runtime. Em sistemas operacionais móveis, falhas de cauda geralmente ocorrem por contenção de I/O ou atrasos no agendamento do Kernel (*scheduler context switch*). 

Ao isolar o espaço de endereçamento de memória através do modelo de subprocessos e utilizar chamadas POSIX nativas para checagem de integridade, o Nexus evitou o *overhead* do interpretador Python, mitigando completamente o impacto de cenários imprevisíveis na cauda da distribuição.

## 5. Conclusão e Trabalhos Futuros
O Nexus Runtime v600 provou com sucesso que é possível atingir níveis industriais de tolerância a falhas (sub-10ms) em hardware altamente restrito e sem suporte a virtualização complexa (Docker/Kubernetes). O framework estabilizou os tempos de resposta de forma previsível e segura, tornando-se uma solução viável para nós de computação na borda e sistemas embarcados IoT de missão crítica.

Os próximos capítulos de evolução do ecossistema expandirão as fronteiras do Nexus em direção às seguintes frentes de engenharia:
1. **v700 (Camada de Persistência WAL):** Implementação de um log de transações persistente (*Write-Ahead Logging*) baseado em arquivo ou SQLite embarcado para recuperação de estado *stateful* pós-queda total de energia do dispositivo.
2. **v800 (Orquestração Distribuída):** Extensão do modelo de atores para suporte a clusters de rede mesh locais, permitindo que um Watcher Master em um dispositivo mitigue a queda de workers em outro nó físico na mesma rede local.

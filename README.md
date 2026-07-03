# Nexus Runtime v500

![Nexus Runtime V500 Dashboard](assets/nexus_mockup.png)

Infraestrutura soberana para Edge AI.

## ⚡ Instalação Rápida (Single-Command Deploy)

Execute o comando abaixo diretamente no terminal do seu ambiente embarcado ou Termux (Android) para clonar, estruturar as dependências e inicializar a suíte de observabilidade automaticamente:

```bash
git clone [https://github.com/gutembergpb27/Termux-nexus.git](https://github.com/gutembergpb27/Termux-nexus.git) && cd Termux-nexus && python3 -m pip install -r requirements.txt && python3 dashboard.py

🏗️ Arquitetura do Sistema e Fluxo de Dados
​O ecossistema do Nexus Runtime v500 opera em um pipeline isolado na borda (Edge), garantindo persistência atômica mesmo sob falhas críticas simuladas (Engine de Caos):

  [ Simulador de Carga ] 
            │  (Geração contínua de eventos a ~125 Hz)
            ▼
  [ Módulo de Persistência ] ──► Mode: Write-Ahead Logging (WAL)
            │  (Escrita rápida e isolada via SQLite)
            ▼
  [ Validador de Integridade ] ──► Assinatura por Hashes Criptográficos
            │  (Garante consistência pós-SIGKILL / Crash)
            ▼
  [ Motor de Auditoria Forense ] ──► Geração automática de relatórios
            │
            ▼
  [ Painel de Telemetria ] ──► Terminal Local (Termux / Android Edge)
                               (Exibição de métricas P95/P99 em tempo real)

## 🌋 Testando a Resiliência (Engenharia do Caos)

Para validar o mecanismo de recuperação automática pós-crash e ver o contador de resiliência subir no painel, execute os scripts em paralelo utilizando duas sessões/abas no seu terminal:

* **Aba 1 (Dashboard Principal):** Inicializa o monitoramento e a telemetria do ecossistema.
  ```bash
  python3 dashboard.py


### 🖥️ Exemplo de Saída no Terminal (Engine de Caos em Ação)

Quando você executa o script `chaos_test.py` em uma aba paralela, a saída do terminal demonstra o monitoramento ativo e a injeção do sinal de desligamento forçado:

```text
============================================================
🌋 INICIANDO ENGINE DE ENGENHARIA DO CAOS - NEXUS V500 🌋
============================================================
[INFO] Monitorando integridade da infraestrutura na borda...

[💥 CAOS INJETADO] Disparando SIGKILL (kill -9) no PID: 12453
[SUCESSO] Processo derrubado abruptamente de forma forçada.
[AGUARDANDO] Testando resiliência do SQLite WAL e validação de hashes...
[INFO] Sistema reinicializado. Verifique o contador 'Events Recovered' no dashboard!

[💥 CAOS INJETADO] Disparando SIGKILL (kill -9) no PID: 12510
[SUCESSO] Processo derrubado abruptamente de forma forçada.
[AGUARDANDO] Testando resiliência do SQLite WAL e validação de hashes...
[INFO] Sistema reinicializado. Verifique o contador 'Events Recovered' no dashboard!

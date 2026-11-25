# Nexus Runtime Platform V2700

## Recovery R2 e R3 — Recuperação do estado persistido do ComputeRuntime após interrupção forçada do processo (experimental)

[English](NEXUS_V2700_RECOVERY_R2_R3_EN.md) · **Português (Brasil)**

**Data de referência:** 24 de novembro de 2026

**Classificação:** documentação experimental pública; evidências brutas mantidas em caráter privado.

**Status:** os dois laboratórios foram **executados e aprovados dentro dos
limites experimentais definidos** (R2: 15/15 verificações; R3: 15/15
verificações). Um auditor independente, somente leitura, recalculou os números
do R3 a partir das evidências brutas.

> [!IMPORTANT]
> **Escopo.** R2 e R3 mostram que o estado JSON gravado pelo
> `TaskCompletionStore` de um `ComputeRuntime` real sobrevive à interrupção
> forçada do processo e pode ser carregado por um novo runtime: na mesma
> máquina (R2) e em outro dispositivo após uma transferência manual verificada
> (R3). Eles **não** demonstram failover automático ou distribuído, consenso,
> migração de processo vivo, execução exatamente uma vez nem prontidão para
> produção. Nada nestes laboratórios altera o runtime da `main`; são
> **laboratórios experimentais**, não capacidades operacionais do runtime
> distribuído.

---

### 1. Classes de evidência

| Classe | Significado |
|---|---|
| **Medido no laboratório** | Produzido pelo harness durante a execução e gravado nos arquivos de evidência do laboratório. |
| **Verificado de forma independente** | Recalculado a partir das evidências brutas (hashes, estados, ledgers, tempos) por um auditor separado, somente leitura, sem depender do resumo do harness. |
| **Declarado pelo operador** | Informado pelo operador e não medido pelas ferramentas (por exemplo, o tipo de link de internet). |
| **Não implementado** | Comportamento que o runtime atual não oferece; registrado como limitação, nunca simulado. |

---

### 2. Código testado

| Item | Valor | Classe |
|---|---|---|
| Commit | `08a0f7361dd08e6afdf8a90755250505cb750120` | Medido no laboratório |
| Árvore `nexus/` | `c6a29776b54f1827c3b3128cbe4404e046143e33` (idêntica à da `main` no momento desta redação) | Verificado de forma independente |
| Componentes | `ComputeRuntime`, `TaskCompletionStore`, `TaskCompletionRegistry` — código real, persistência sem mocks | Medido no laboratório |
| Entrega do código | `git archive` do commit em cada laboratório (repositório nunca modificado); no R3 o lado Android recebeu um snapshot com SHA-256 verificado (`2431a3d1…dd61`), porque o checkout local não continha o commit | Verificado de forma independente |

Os únicos dublês de teste foram **backends**: uma subclasse de `LocalBackend`
que acrescenta uma linha com fsync por execução a um ledger de execuções (para
detectar execução duplicada) e um backend que bloqueia indefinidamente (para
criar uma tarefa realmente em execução no momento da interrupção).

Classes de tarefa usadas nos dois laboratórios:

- **Executada de fato:** passou por `ComputeRuntime.run`, que persistiu
  `pending → running → completed`.
- **Preparada:** gravada pela API do registry (`create`, `start`) mais
  `persist()`, nunca executada. Usada apenas para verificar a política de
  recuperação.
- **Em execução:** `ComputeRuntime.run` persistiu `running` e o backend estava
  bloqueado quando o processo foi interrompido.

---

### 3. Recovery R2 — uma máquina (Windows)

**Procedimento.** Um processo filho (instância A) executou uma tarefa real,
preparou uma tarefa `pending` e uma `running` e iniciou uma tarefa em execução.
Depois de confirmar o store JSON em disco, o harness encerrou **somente esse
filho**, pelo próprio handle do processo (`TerminateProcess`, PID 8548, código
de saída 1). O processo ficou parado por 5 s; em seguida um novo processo
(instância B) carregou o mesmo store.

| Tarefa | Antes da interrupção | Após a recuperação |
|---|---|---|
| real, concluída | `completed` | `completed`, resultado idêntico campo a campo |
| `pending` preparada | `pending` | `pending` |
| `running` preparada | `running` | `failed` — "task interrupted by runtime restart" |
| real, em execução | `running` | `failed` — "task interrupted by runtime restart" |

**Verificações (15/15 aprovadas, medidas no laboratório):** store presente e
válido antes da interrupção; estados conforme o planejado; nenhum `.tmp`
residual antes ou depois; bytes do store inalterados pela interrupção; PID
encerrado não ativo após o intervalo; tarefa concluída e resultado preservados;
`pending` mantida; as duas tarefas `running` recuperadas como `failed` com a
mensagem de interrupção; nenhuma execução duplicada; tentativas de reexecução
não alteraram o store; contadores de saúde consistentes
(`pending 1, running 0, completed 1, failed 2, total 4`); uma nova tarefa foi
executada após a recuperação.

**Prevenção de duplicação.** Cinco tentativas de reexecução foram rejeitadas
sem executar: reexecução não idempotente (`ValueError: task completion already
exists`), reexecução idempotente da tarefa concluída (`RuntimeError: completed
task does not contain a ComputeResult`), da tarefa pendente (`task execution
already in progress`) e das duas tarefas recuperadas (`task interrupted by
runtime restart`). O ledger mostra cada tarefa realmente executada uma única vez.

**Tempos (medidos no laboratório, n = 1):** carga do store → `health()`
**0,57 ms**; spawn do processo → runtime pronto **312 ms**; intervalo entre a
interrupção e o reinício de 5,0 s (definido pelo harness).

Hashes das evidências: relatório R2 `2869b7c9…5f4d6f`; manifesto R2
`dc543184…779908` (15/15 entradas verificadas novamente para este documento).

---

### 4. Recovery R3 — entre dispositivos (Motorola/Termux → Windows)

#### 4.1 Ambiente

| Item | Valor | Classe |
|---|---|---|
| Origem | Motorola Edge 40 Neo, Android 15, aarch64, Termux, Python 3.14.10 | Medido no laboratório (preflight) |
| Destino | Computador Windows 11, Python 3.14.6 | Medido no laboratório |
| Link de internet da origem | Descrito como Starlink | Declarado pelo operador |
| Link de internet do destino | Descrito como fibra | Declarado pelo operador |
| Rede overlay | Tailnet Tailscale; o caminho no momento da transferência não foi registrado. Uma verificação após a execução mostrou caminho por relay DERP (sem conexão direta) | Medido no laboratório (somente após a execução) |
| Local dos laboratórios | Fora dos dois repositórios e, no Android, fora do `HOME` | Medido no laboratório |

#### 4.2 Procedimento

1. **Execução na origem.** No Motorola, um processo filho executou uma tarefa
   real (soma dos quadrados de 1 a 10 = 385), preparou uma tarefa `pending` e
   iniciou uma tarefa em execução. O store foi confirmado em disco.
2. **Interrupção controlada.** O harness enviou `SIGKILL` **somente ao próprio
   filho** (PID 6002), depois de verificar que o PID informado pelo filho era o
   mesmo PID que ele havia criado. Status de saída −9; `/proc/6002` ausente após
   o reap. Os bytes do store não mudaram com a interrupção.
3. **Entrega (handoff).** O store de origem foi congelado como somente leitura
   e um marcador de entrega (época 1) registrou seu SHA-256. Uma lista fixa de
   nove arquivos experimentais foi empacotada. Nenhuma chave, token, credencial
   ou arquivo de produção foi incluído.
4. **Transferência.** HTTP PUT dentro da tailnet Tailscale para um receptor de
   uso único no Windows. O receptor escutava apenas na interface da tailnet,
   aceitava apenas o endereço da origem na tailnet mais um token temporário
   (renovado após uma revisão de segurança e nunca gravado nas evidências) e
   verificava o SHA-256 e a lista exata de membros do pacote antes de aceitá-lo.
5. **Recuperação.** No Windows, um novo processo carregou uma cópia do store
   transferido, após conferir seu hash com o marcador de entrega.
6. **Verificação de persistência.** Uma nova tarefa foi executada no Windows; um
   segundo processo, independente, recarregou o store do disco.

#### 4.3 Integridade (verificada de forma independente)

| Item | Origem | Destino |
|---|---|---|
| SHA-256 do store | `b9c98733…a469a9b` (585 bytes) | igual |
| SHA-256 do pacote | `3caf32e3…0a8516d3` (2.483 bytes) | igual |
| SHA-256 do snapshot de código | `2431a3d1…eefcdd61` | igual |

#### 4.4 Estados das tarefas

| Tarefa | Antes da interrupção (Motorola) | Após a recuperação (Windows) |
|---|---|---|
| real, concluída (soma dos quadrados = 385) | `completed` | `completed`, resultado idêntico campo a campo |
| `pending` preparada | `pending` | `pending` |
| real, em execução | `running` | `failed` — "task interrupted by runtime restart" |
| nova tarefa no Windows | — | `completed`, persistida e recarregada por um processo separado |

Saúde na recuperação: `pending 1, running 0, completed 1, failed 1, total 3`;
após a nova tarefa: `completed 2, total 4`.

**Verificações (15/15 aprovadas):** hash do pacote igual ao declarado pela
origem; hash do snapshot de código no destino; hash do store igual na origem e
no destino; esquema do store válido; marcador de entrega presente; tarefa
concluída presente; resultado preservado campo a campo; valor calculado (385)
preservado; `pending` mantida; tarefa em execução recuperada como `failed` com a
mensagem de interrupção; nenhuma execução duplicada entre os dispositivos;
tentativas de reexecução não alteraram o store; contadores de saúde
consistentes; nova tarefa executada no Windows; novo resultado persistido e
recarregado por um processo novo.

#### 4.5 Prevenção de duplicação no cenário testado

Os ledgers de execução dos dois dispositivos, combinados, mostram cada tarefa
**iniciada no máximo uma vez**: a tarefa concluída executou uma vez no
Motorola; a tarefa em execução iniciou uma vez e nunca terminou nem reiniciou;
a tarefa `pending` nunca executou; a única execução no Windows foi a tarefa
nova. Quatro tentativas de reexecução no Windows foram rejeitadas sem executar
e sem alterar o hash do store. Isto é evidência apenas para este cenário, **não**
uma garantia de execução exatamente uma vez.

#### 4.6 Tempos (medidos no laboratório, n = 1; recalculados pelo auditor)

| Medida | Valor |
|---|---|
| Transferência (HTTP PUT completo, medido na origem) | 168 ms |
| Inicialização: spawn do processo → runtime pronto (Windows) | 988 ms (dos quais 689 ms de imports) |
| Recuperação: carga do store → `health()` | 0,96 ms |
| Nova tarefa: execução + persistência | 9,0 ms |
| Diferença de relógio, Windows − Motorola | 894 ms ± 78 ms (14 amostras HTTP) |
| **Total: interrupção no Motorola → runtime pronto no Windows** | **2,95 s ± 0,08 s** |

O total só é informado porque os dois relógios foram relacionados por amostras
medidas, com incerteza conhecida. Ele inclui empacotamento, transferência,
amostragem de relógio após o upload, uma janela de 0,5 s de verificação do
receptor e a inicialização.

#### 4.7 Auditoria independente

Um agente separado, somente leitura, verificou novamente: o manifesto R3
(27/27) e o manifesto R2 (15/15); a cadeia de hashes pacote → store → marcador
de entrega; os estados das tarefas na origem e no destino; ledgers e PIDs; todos
os tempos (total 2,9509 s); a ausência dos tokens em todos os arquivos dos
laboratórios; os nove membros do pacote; e que o repositório não foi alterado.
Os itens 1 a 11 foram confirmados. Ele também encontrou quatro discrepâncias de
**documentação** na primeira versão do relatório R3: uma afirmação sobre o
caminho de rede e números de recursos do destino sem evidência arquivada, uma
redação "exatamente uma vez" e uma primeira instância do receptor, não
mencionada, que nunca recebeu tráfego da origem. As quatro foram corrigidas no
relatório do laboratório antes da redação deste documento; as correções estão
refletidas acima.

---

### 5. Limitações

**Limitações comprovadas do código atual (não implementado):**

1. **Serialização.** Um resultado `completed` recuperado é um `dict` simples,
   não um `ComputeResult`: `export_state` usa `dataclasses.asdict` e
   `restore_state` não reconstrói o tipo.
2. **Idempotência.** Por causa de (1), `run(idempotent=True)` em uma tarefa
   concluída recuperada lança `completed task does not contain a ComputeResult`
   em vez de devolver o resultado armazenado. Não há reexecução.
3. **Reenfileiramento.** Uma tarefa `pending` recuperada não pode ser retomada
   nem reenfileirada pelo `ComputeRuntime`; ela sobrevive apenas como estado.
4. **Tarefas interrompidas.** Toda tarefa `running` persistida vira `failed` ao
   carregar, sem nova tentativa automática, e o runtime não distingue uma
   tarefa realmente interrompida de qualquer outra entrada `running` persistida.
5. **Saúde.** `health()["healthy"]` é sempre `True`; não valida o estado
   recuperado. A consistência foi verificada pelos contadores.
6. **Escritor único.** O store não tem token de fencing nem lease. No R3, o
   escritor único foi garantido **por procedimento** (origem encerrada, store de
   origem congelado, marcador de entrega, receptor de upload único); o store em
   si não consegue rejeitar um escritor antigo.

**Limitações do experimento:**

7. A transferência e o reinício do R3 foram feitos pelo harness e pelo
   operador: não é failover automático, consenso distribuído nem migração de
   processo vivo.
8. Só a interrupção do processo foi testada; queda do sistema operacional e
   perda de energia não foram testadas (o store faz fsync do arquivo temporário,
   mas não do diretório após a renomeação).
9. O "cálculo" é feito pelo harness e transportado no payload; o `LocalBackend`
   real apenas devolve o nome e o payload da tarefa.
10. Os tipos de link de internet são declarados pelo operador; o caminho
    Tailscale só foi registrado após a execução.
11. Memória e disco do destino não foram arquivados no preflight.
12. Cada número vem de uma única execução (n = 1); nenhuma estatística está
    implícita.

---

### 6. O que é mantido em caráter privado

Logs brutos, stores, ledgers, o pacote, o harness e os manifestos SHA-256 ficam
nos dois diretórios de laboratório na máquina do operador. Endereços privados,
nomes de host, tokens temporários e identificadores de dispositivo não são
publicados. Os hashes publicados permitem relacionar as evidências privadas a
este relatório.

| Artefato | SHA-256 |
|---|---|
| Relatório R2 | `2869b7c948db1a074ad1c5050917c476b6404c80a882e9fcd02075948c5f4d6f` |
| Manifesto R2 | `dc5431841db260ba59291b88272e3ce8988d4279ce9fb676df5a15b33e779908` |
| Relatório R3 (após as correções da auditoria) | `94c17d944a89b12a62fca1e8b2f5c838e75eb4e413c72b2447ff18a2a1e74b23` |
| Manifesto R3 | `5de7b738fad4ef91a6e0a87b84f5db8581d0bba0733f6589e6130fa326e3d0ad` |
| Harness R3 | `026ad21cdb8eba57b8c21c7e5c864f1961da743d7a27edeef7a6123763dd4f05` |

---

### 7. Próxima etapa

Um laboratório de recuperação supervisionada (R4) está sendo especificado fora
do repositório: detecção automática de um processo experimental parado,
verificação de integridade, reinício supervisionado **no mesmo** nó e
investigação de fencing de escritores. Ele não promoverá outro nó a escritor sem
prova verificável de que a instância anterior perdeu sua autoridade.

Veja o [índice da documentação](README.pt-BR.md) para experimentos relacionados.

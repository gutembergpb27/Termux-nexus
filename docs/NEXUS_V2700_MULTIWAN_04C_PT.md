# Nexus Runtime Platform V2700 — Multi-WAN 04C: execução Compute remota experimental

**Status:** PASS (experimento limitado)<br>
**Data:** 22 de novembro de 2026<br>
**Base Git:** `d783a863d7b1ac5db88922726606e75c5d17c4fb`<br>
**Repositório:** `gutembergpb27/Termux-nexus`

## Visão geral

Foi realizada uma experiência real entre Windows e Motorola Edge 40 Neo (Android 15/Termux) para verificar a interoperabilidade de componentes existentes do Nexus Runtime Platform V2700. O cliente utilizou `TransportNodeExecutor` e `NexusProtocol` para enviar tarefas `COMPUTE_TASK` por TCP sobre Tailscale. O Android recebeu, verificou e executou tarefas por meio de `NexusDistributedCore.handle_compute_task`, `TaskWorker` e handlers permitidos; os resultados `COMPUTE_RESULT` foram validados pelo cliente.

Ambos os laboratórios utilizaram o commit Git indicado e foram verificados como limpos após a execução. A inicialização do runtime distribuído completo foi evitada.

## Evidência resumida

| Critério | Resultado |
| --- | --- |
| Tarefas remotas aprovadas (`echo`, `data_transform`, `matrix_multiply`, `echo` adicional) | 4/4 |
| Controle negativo: assinatura inválida | Rejeitado |
| Controle negativo: repetição de mensagem | Rejeitado |
| Resumo Android | 4 aceitas; 2 rejeitadas; 0 erros; servidor encerrado |
| RTT mediano observado no cliente | 165,659 ms (n=4) |
| Preservação das worktrees | CLEAN em ambos os dispositivos |
| Escritas distribuídas | Não utilizadas |

A preparação também incluiu 33 testes offline aprovados no Windows, 33 no Android e um ensaio TCP loopback entre dois processos Python no Windows (4 solicitações positivas e 2 controles negativos aprovados).

## Limitações e interpretação

Trata-se de validação de **execução Compute autenticada entre dois dispositivos**, não de consenso distribuído. Não foram comprovados quorum commit, replicação persistente, fencing, segurança contra split-brain ou prontidão para produção. Não se observou se o Tailscale usou transporte direto ou retransmissão DERP. O RTT agrega rede e execução, e as quatro amostras não constituem benchmark estatístico. A autenticação é baseada em segredo HMAC compartilhado, sem identidade individual criptográfica dos nós. Hashes de arquivo locais diferiram entre plataformas, embora o commit Git e o estado limpo das worktrees coincidissem; a causa dessas diferenças não foi investigada.

**Privacidade:** os logs brutos, os endereços Tailscale e qualquer segredo temporário permanecem fora da documentação pública.

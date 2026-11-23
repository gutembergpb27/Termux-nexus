# Nexus Runtime Platform V2700 — Multi-WAN 04C: execução Compute remota experimental

[English](NEXUS_V2700_MULTIWAN_04C_EN.md) · **Português (Brasil)**

**Status:** PASS (experimento limitado; reportado pelo operador, ver a nota sobre as evidências)<br>
**Data:** 22 de novembro de 2026<br>
**Base Git:** `d783a863d7b1ac5db88922726606e75c5d17c4fb`<br>
**Repositório:** `gutembergpb27/Termux-nexus`<br>
**Classe de evidência:** reportado pelo operador. Os números do cliente Windows vêm da saída do terminal apresentada pelo operador. Os números do Android são uma **transcrição da saída do terminal feita pelo operador**, e não um log bruto capturado e hasheado no aparelho. Os logs brutos são mantidos em caráter privado e não foram reprocessados de forma independente para este relatório.

## Visão geral

Um experimento físico entre Windows e um Motorola Edge 40 Neo (Android 15 / Termux) avaliou a interoperabilidade de componentes existentes do Nexus Runtime Platform V2700. O cliente utilizou `TransportNodeExecutor` e `NexusProtocol` para enviar mensagens `COMPUTE_TASK` autenticadas por TCP via Tailscale. O servidor experimental no Android verificou e executou as requisições usando `NexusDistributedCore.handle_compute_task`, `TaskWorker` e handlers registrados explicitamente. O cliente verificou as respostas `COMPUTE_RESULT` autenticadas.

Ambos os laboratórios isolados utilizaram o commit Git indicado e relataram worktrees limpas após a execução. O relato do Android provém da transcrição do operador. O runtime distribuído completo não foi inicializado.

## Resultados observados

| Critério | Resultado reportado pelo operador | Origem |
| --- | --- | --- |
| Tarefas Compute remotas aprovadas (`echo`, `data_transform`, `matrix_multiply`, `echo` adicional) | 4/4 | Saída do cliente Windows |
| Controle negativo: assinatura alterada | Rejeitado | Saída do cliente Windows |
| Controle negativo: repetição de mensagem (replay) | Rejeitado | Saída do cliente Windows |
| Resumo do servidor Android | 4 aceitas; 2 rejeitadas; 0 erros; servidor encerrado | Transcrição do operador (Android) |
| RTT mediano observado no cliente | 165,659 ms (n=4) | Saída do cliente Windows |
| Integridade do repositório | Worktrees relatadas como limpas nos dois dispositivos | Saída do Windows; transcrição do operador (Android) |
| Escritas distribuídas | Não utilizadas | Desenho do experimento |

Os pré-requisitos também foram relatados como aprovados:
- 33 testes offline específicos no Windows;
- 33 testes offline específicos no Android (transcrição do operador);
- um ensaio TCP real em loopback entre dois processos Python no Windows, com 4 requisições Compute bem-sucedidas e 2 controles negativos.

As etapas preparatórias anteriores 04A e 04B não têm arquivos de evidência arquivados.

## Nota sobre as evidências

- **Números do lado Android.** As 4 requisições aceitas, as 2 rejeitadas, os 0 erros, o servidor encerrado, a worktree limpa e os 33 testes vêm de uma transcrição da saída do terminal feita pelo operador. Não vêm de um log bruto capturado e hasheado no aparelho.
- **Diferenças de hashes.** Os SHA-256 dos arquivos brutos diferiram entre plataformas, embora o commit Git coincidisse e as duas worktrees tenham sido relatadas como limpas. No Windows, a diferença corresponde à conversão de finais de linha no checkout (`core.autocrlf=true`, CRLF na worktree, LF no índice Git). Isso não foi confirmado no Android.
- **Segredo temporário.** O segredo HMAC temporário usado neste teste foi exposto fora dos dispositivos durante o experimento. Ele é tratado como comprometido e não é reutilizado.
- **RTT.** A mediana de 165,659 ms (n=4) inclui o estabelecimento da conexão TCP e o processamento no servidor. A primeira amostra foi bem mais lenta que as demais. A rota Tailscale não foi observada.

## Escopo e limitações

Trata-se de evidência de **execução Compute remota autenticada entre dois dispositivos físicos**, e não de consenso distribuído. Não estabelece commit por maioria, replicação durável, fencing de líder, proteção contra split-brain, execução exatamente uma vez nem prontidão para produção.

- Não foi registrado se o Tailscale usou transporte direto ou retransmissão DERP.
- As observações de RTT incluem rede e computação, e quatro amostras não constituem benchmark estatístico.
- O protocolo usa um segredo HMAC compartilhado por todo o cluster, sem identidade criptográfica por nó.

**Privacidade:** logs brutos do terminal, endereços Tailscale privados e credenciais temporárias não fazem parte deste relatório público.

Relacionados: [Multi-WAN 01–03](NEXUS_V2700_MULTIWAN_01_03_PT.md) · [Multi-WAN 05E](NEXUS_V2700_MULTIWAN_05E_PT.md) · [Série Multi-WAN 05](NEXUS_V2700_MULTIWAN_05_SERIES_PT.md) · [Índice da documentação](README.pt-BR.md)

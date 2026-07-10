# Nexus Architecture Reality Map

## Objetivo

Registrar, de forma objetiva, o estado atual da arquitetura do Nexus Runtime após a revisão da malha fechada, separando capacidades funcionais, componentes fragmentados e promessas ainda não comprovadas.

## 1. Funcional de ponta a ponta

### Persistência e integridade

- cadeia de transações com hashes;
- checkpoint local;
- âncora externa opcional;
- detecção de adulteração, truncamento, reordenação, replay e rollback em cenários cobertos;
- recuperação consistente após reinicialização;
- baseline C20 com `23 passed, 1 xfailed`.

### Provisionamento

- preserva bancos e arquivos WAL existentes;
- instala o core distribuído;
- instala a dependência de segurança;
- garante a dependência `dotenv`;
- exige configuração secreta local;
- aplica permissão restrita ao arquivo secreto;
- permite configurar a URL do Hub.

### Failover básico

- nó mantém identidade estável ao mudar de papel;
- `FOLLOWER` pode ser promovido a `MASTER`;
- polling permanece ativo após promoção;
- registro periódico no Hub;
- consulta de peers ativos.

## 2. Implementado, mas fragmentado

### Liderança e eleição

Existem mecanismos relacionados em:

- `nexus_distributed_core.py`;
- `network_discovery.py`;
- `cluster_state.py`;
- `heartbeat.py`.

Ainda não há uma única fonte de verdade para identidade, papel, eleição e liveness.

### Comunicação de malha

Existem:

- TCP direto;
- rendezvous HTTP;
- beacon/listener de descoberta;
- heartbeat;
- envio de transações;
- mensagens `SYNC_CHECK` e `SYNC_BATCH`.

Esses mecanismos ainda não estão consolidados num protocolo único.

### Segurança

Existe HMAC-SHA256 com segredo compartilhado.

Ainda faltam:

- nonce;
- proteção contra replay;
- timestamp ou expiração;
- identidade criptográfica por nó;
- rotação de chaves;
- serialização canônica;
- autenticação integrada ao Hub e ao TCP.

### Sincronização

Existe suporte a `SYNC_CHECK` e `SYNC_BATCH`.

Ainda faltam:

- emissão efetiva de `SYNC_CHECK` no fluxo principal;
- cálculo real de delta;
- validação completa dos blocos recebidos;
- integração com a persistência C20;
- autenticação das mensagens;
- controle de tamanho e framing de pacotes.

## 3. Parcialmente demonstrado

- operação em mais de um sistema operacional;
- execução em Android/Termux e Windows;
- uso de dispositivos físicos distintos;
- failover lógico;
- catch-up;
- dashboard;
- malha física local.

Essas capacidades possuem evidências visuais e operacionais, mas ainda precisam de uma baseline reproduzível única e independente.

## 4. Ainda não comprovado como capacidade consolidada

- consenso distribuído formal;
- tolerância a partições de rede;
- quorum autenticado;
- operação WAN robusta;
- descoberta segura sem ponto central;
- confiança entre nós sem segredo compartilhado único;
- escalabilidade para muitos nós;
- recuperação automática completa após partição;
- execução independente por terceiros;
- produto utilizado por usuários reais;
- tração comercial.

## 5. Risco arquitetural principal

O maior risco atual não é falta de componentes.

É a existência de múltiplos componentes parcialmente sobrepostos sem um protocolo canônico único para:

- identidade;
- descoberta;
- liderança;
- heartbeat;
- sincronização;
- persistência;
- segurança.

## 6. Próxima decisão arquitetural

Antes de adicionar novas funcionalidades, o Nexus deve definir um único caminho canônico de execução da malha:

1. identidade estável do nó;
2. configuração local;
3. registro autenticado;
4. descoberta de peers;
5. eleição;
6. troca de mensagens;
7. persistência;
8. sincronização;
9. recuperação;
10. observabilidade.

## 7. Critério de avanço

Uma capacidade só deve ser considerada consolidada quando possuir:

- implementação integrada;
- teste automatizado;
- evidência reproduzível;
- documentação alinhada;
- limitação conhecida registrada.

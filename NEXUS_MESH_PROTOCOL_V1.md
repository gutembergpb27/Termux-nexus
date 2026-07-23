# Nexus Mesh Protocol v1

## Status

Especificação arquitetural inicial do caminho canônico da malha Nexus.

Este documento define contratos de protocolo.

Ele não afirma que todas as capacidades descritas já estão implementadas.

## 1. Objetivo

O Nexus Mesh Protocol v1 define como nós de borda:

- mantêm identidade estável;
- autenticam mensagens;
- registram presença;
- descobrem peers;
- detectam falhas;
- elegem liderança;
- sincronizam estado;
- recuperam continuidade.

O protocolo deve operar em redes locais e ambientes de borda com conectividade intermitente.

A nuvem ou um Hub remoto podem ampliar a malha, mas não constituem a identidade nem a fonte final de verdade de um nó.

## 2. Princípios

### 2.1. Identidade não é papel

O identificador do nó deve permanecer estável durante toda a sua vida operacional.

Mudanças entre `FOLLOWER`, `CANDIDATE` e `MASTER` não alteram `node_id`.

### 2.2. Toda mensagem deve ser autenticada

Mensagens de controle e dados devem usar um envelope autenticado.

Mensagens sem assinatura válida devem ser rejeitadas antes do processamento.

### 2.3. Replay deve ser detectável

Cada mensagem deve carregar:

- identificador único;
- timestamp;
- nonce;
- emissor;
- tipo;
- payload;
- assinatura.

Mensagens expiradas ou já processadas devem ser rejeitadas.

### 2.4. Persistência é parte do protocolo

Estado recebido pela rede só pode ser considerado aceito depois de:

- autenticação;
- validação de estrutura;
- validação de sequência;
- validação de integridade;
- persistência confirmada.

### 2.5. Recuperação não pode depender de intervenção manual

Um nó que retorna deve descobrir sua defasagem e solicitar apenas o estado necessário para recuperar continuidade.

## 3. Papéis

### FOLLOWER

- registra presença;
- acompanha o líder;
- aceita sincronização;
- mantém estado local;
- participa da eleição quando necessário.

### CANDIDATE

- inicia processo de eleição;
- solicita apoio ou aplica regra determinística;
- não aceita comandos de liderança até a eleição terminar.

### MASTER

- publica presença como líder;
- aceita submissões;
- distribui estado confirmado;
- responde a solicitações de sincronização;
- continua sujeito a validação e observabilidade.

## 4. Identidade do nó

Cada nó possui:

- `node_id` estável;
- `instance_id` efêmero por inicialização;
- papel atual;
- endereço de serviço;
- versão de protocolo;
- capacidade declarada;
- material de autenticação.

Exemplo conceitual:

    {
      "node_id": "NO-ARM-01",
      "instance_id": "boot-uuid",
      "role": "FOLLOWER",
      "protocol_version": "1",
      "tcp_port": 9092
    }

## 5. Envelope canônico

Toda mensagem de malha deve seguir um envelope equivalente a:

    {
      "version": 1,
      "message_id": "uuid",
      "timestamp": 0,
      "nonce": "random",
      "sender": "NO-ARM-01",
      "type": "HEARTBEAT",
      "payload": {},
      "signature": "hex"
    }

A assinatura deve ser calculada sobre uma serialização canônica dos campos, excluindo `signature`.

## 6. Tipos mínimos de mensagem

### Registro e presença

- `REGISTER`
- `REGISTER_ACK`
- `HEARTBEAT`
- `PEER_LIST`

### Liderança

- `ELECTION_START`
- `ELECTION_VOTE`
- `LEADER_ANNOUNCE`
- `LEADER_CONFLICT`

### Estado e sincronização

- `STATE_SUMMARY`
- `SYNC_REQUEST`
- `SYNC_BATCH`
- `SYNC_ACK`

### Operação

- `EVENT_SUBMIT`
- `EVENT_COMMIT`
- `ERROR`

## 7. Registro

Um nó registra:

- identidade estável;
- papel atual;
- endereço observado;
- porta;
- versão;
- resumo de estado;
- timestamp;
- assinatura.

O Hub ou serviço de rendezvous:

- valida autenticação;
- rejeita identidades conflitantes;
- atualiza `last_seen`;
- não decide sozinho a verdade do estado;
- não pode criar liderança por declaração não autenticada.

## 8. Descoberta

A descoberta pode ocorrer por:

- Hub de rendezvous;
- broadcast ou multicast local;
- configuração estática;
- cache local de peers conhecidos.

O protocolo deve permitir mais de um mecanismo sem duplicar identidade ou estado.

## 9. Liveness

Cada nó mantém informação de última presença dos peers.

Um peer é considerado suspeito antes de ser considerado ausente.

Estados mínimos:

- `ALIVE`
- `SUSPECT`
- `DEAD`

A transição deve usar timeout configurável e múltiplas observações quando possível.

## 10. Eleição

A versão v1 pode usar uma regra determinística simples, desde que explicitamente documentada.

Exemplo:

- maior prioridade declarada;
- em empate, maior `node_id`;
- liderança válida por termo;
- anúncio autenticado;
- conflito resolvido pelo termo mais alto e, depois, pela regra determinística.

A versão v1 não deve ser descrita como Raft, Paxos ou consenso formal.

## 11. Termo de liderança

Cada eleição incrementa um `term`.

Mensagens de liderança devem carregar o termo.

Um nó rejeita comandos de termo inferior ao maior termo conhecido.

## 12. Resumo de estado

Cada nó publica:

- altura local;
- hash da ponta;
- termo conhecido;
- último evento confirmado.

Exemplo:

    {
      "height": 42,
      "tip_hash": "abc123",
      "term": 7
    }

## 13. Sincronização

Fluxo canônico:

1. follower envia `STATE_SUMMARY`;
2. master compara altura e hash;
3. follower envia `SYNC_REQUEST`;
4. master envia somente o delta necessário;
5. follower valida cada bloco;
6. follower persiste;
7. follower responde `SYNC_ACK`;
8. ambos atualizam observabilidade.

O `SYNC_BATCH` não deve ser aceito sem validação de cadeia e autenticação.

## 14. Persistência

A implementação canônica deve reutilizar a camada validada em `persistence.py`.

O núcleo distribuído não deve manter uma segunda cadeia incompatível ou gravar hashes fictícios.

A persistência distribuída deve respeitar:

- cadeia hash-linked;
- checkpoint;
- âncora externa quando configurada;
- recuperação fail-closed;
- limitação conhecida da C20.

## 15. Segurança v1

A primeira versão pode usar HMAC com segredo compartilhado como mecanismo transitório.

Requisitos mínimos:

- serialização canônica;
- timestamp;
- nonce;
- cache de mensagens processadas;
- expiração;
- comparação constante;
- separação entre configuração e código;
- rotação operacional documentada.

Limitação:

Se um nó for comprometido, o segredo comum da malha pode ser exposto.

Evolução futura:

- chaves por nó;
- assinaturas assimétricas;
- certificados;
- revogação;
- rotação distribuída.

## 16. Framing de transporte

TCP deve usar framing explícito.

Opções aceitáveis:

- prefixo de tamanho;
- newline-delimited JSON com limite estrito;
- protocolo binário versionado.

A implementação deve impor:

- tamanho máximo;
- timeout;
- leitura completa;
- rejeição de frames incompletos;
- tratamento explícito de erro.

## 17. Observabilidade

Eventos mínimos:

- nó iniciado;
- registro aceito ou rejeitado;
- peer suspeito;
- peer expirado;
- eleição iniciada;
- liderança assumida;
- conflito detectado;
- sincronização solicitada;
- batch validado;
- batch rejeitado;
- recuperação concluída;
- erro de autenticação;
- replay rejeitado.

## 18. Configuração canônica

A configuração deve possuir uma única fonte de verdade.

Variáveis mínimas:

- `NEXUS_NODE_ID`
- `NEXUS_ROLE`
- `NEXUS_BIND_HOST`
- `NEXUS_WEB_PORT`
- `NEXUS_TCP_PORT`
- `NEXUS_HUB_URL`
- `NEXUS_DB_PATH`
- `NEXUS_ANCHOR_PATH`
- `NEXUS_SECRET_KEY`
- `NEXUS_HEARTBEAT_INTERVAL`
- `NEXUS_PEER_TIMEOUT`
- `NEXUS_MESSAGE_TTL`

## 19. Caminho canônico de execução

1. carregar configuração;
2. validar segredo e identidade;
3. abrir persistência;
4. recuperar e validar estado;
5. iniciar transporte;
6. registrar presença autenticada;
7. descobrir peers;
8. iniciar liveness;
9. participar da eleição;
10. sincronizar estado;
11. aceitar eventos;
12. observar e recuperar.

## 20. Critérios de conformidade

Uma implementação só pode declarar conformidade com o Nexus Mesh Protocol v1 quando possuir:

- identidade estável;
- configuração canônica;
- envelopes autenticados;
- proteção contra replay;
- registro autenticado;
- liveness;
- eleição versionada por termo;
- sincronização por delta;
- persistência integrada à C20;
- framing de transporte;
- testes automatizados;
- evidência reproduzível;
- limitações registradas.

## 21. Fora de escopo da versão v1

- consenso bizantino;
- tolerância completa a partições;
- confiança zero entre nós;
- escalabilidade massiva;
- WAN adversarial;
- descoberta global descentralizada;
- hardware roots of trust;
- garantia de tempo real rígido.

## 22. Próximo bloco de implementação

A primeira implementação deve focar somente em:

1. configuração canônica;
2. envelope autenticado;
3. timestamp, nonce e replay cache;
4. registro autenticado no Hub;
5. testes automatizados.

Nenhuma nova funcionalidade de produto deve ser adicionada antes desse caminho mínimo estar integrado.

## 23. Definição central

O Nexus é um runtime de continuidade para inteligência distribuída na borda.

A malha é a unidade fundamental.

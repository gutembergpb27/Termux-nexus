# Nexus v2200 — Validação Distribuída Windows + Android

**Data:** 15/07/2026

## Ambiente

- Nexus Hub (Windows)
  - IP: 192.168.1.7
  - Porta: 8500

- MASTER
  - Nó: NO-WIN-A
  - Sistema: Windows
  - HTTP: 8081
  - TCP: 9091

- FOLLOWER
  - Nó: NO-TERMUX
  - Sistema: Android (Termux)
  - HTTP: 8083
  - TCP: 9093

## Resultados

- Registro automático do Android no Hub.
- Descoberta de peers entre Windows e Android.
- Comunicação TCP estabelecida.
- Sincronização inicial do ledger.
- Replicação dos eventos:
  - TESTE_ANDROID_001
  - TESTE_ANDROID_002
  - TESTE_ANDROID_003
- Height final: 6
- Tip hash idêntico nos dois nós.

## Conclusão

Validação concluída com sucesso entre um nó Windows e um nó Android físico utilizando a mesma rede Wi-Fi.
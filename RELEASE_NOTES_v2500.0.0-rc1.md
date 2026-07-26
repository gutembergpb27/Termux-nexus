# Nexus Runtime Platform v2500.0.0-rc1

## Release Candidate 1

Esta é a primeira versão candidata da linha v2500 da Nexus Runtime Platform.

O RC1 consolida o núcleo de execução distribuída, gerenciamento do ciclo de vida, cluster, persistência, diagnóstico, métricas, telemetria, SDK, CLI e empacotamento oficial da plataforma.

## Estado da validação

- 193 testes aprovados
- 1 teste marcado como xfailed
- Wheel validada em ambiente virtual limpo
- Source Distribution gerada com sucesso
- CLI e Nexus Doctor validados
- Integração Contínua configurada
- Metadados do pacote atualizados
- Artefatos acompanhados de hashes SHA-256

## Componentes principais

- Runtime Core e gerenciamento do ciclo de vida
- Cluster, descoberta, sincronização e replicação de estado
- Persistência, checkpoints, recuperação e validação de integridade
- Diagnóstico, métricas, observabilidade, telemetria e tracing
- SDK, clientes públicos e operações programáticas
- CLI e empacotamento Python

## Comandos básicos

```text
nexus version
nexus doctor
nexus status
```

## Instalação local do RC1

```powershell
python -m pip install .\nexus_runtime_platform-2500.0.0rc1-py3-none-any.whl
nexus version
nexus doctor
```

## Artefatos

- `nexus_runtime_platform-2500.0.0rc1-py3-none-any.whl`
- `nexus_runtime_platform-2500.0.0rc1.tar.gz`
- `SHA256SUMS.txt`

## Verificação de integridade

Compare os hashes SHA-256 dos artefatos com o conteúdo de `SHA256SUMS.txt`.

## Finalidade do RC1

Esta versão destina-se à homologação, testes externos e coleta de feedback antes da publicação da versão estável v2500.0.0.

## Aviso

Esta é uma versão de pré-lançamento. Embora validada pela suíte automatizada e por instalação isolada, ainda não representa a versão final estável da linha v2500.

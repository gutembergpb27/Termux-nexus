> [!CAUTION]
> **Historical document (v500/v600 period), kept unchanged for traceability.** It contains statements that current evidence does not support. For the current state, capabilities and limitations see the [project README](README.md) and the [documentation index](docs/README.md).
>
> **Documento histórico (período v500/v600), mantido sem alterações para rastreabilidade.** Contém afirmações que as evidências atuais não sustentam. Para o estado atual, as capacidades e as limitações, veja o [README do projeto](README.pt-BR.md) e o [índice da documentação](docs/README.pt-BR.md).

cat << 'EOF' > VALIDATION.md
# Protocolo de Validação Externa e Reprodutibilidade — Nexus v500

Este documento estabelece o protocolo de teste padronizado para que avaliadores independentes, engenheiros de sistemas e comitês técnicos possam reproduzir a suíte de testes estocásticos de caos do **Nexus Runtime (v500)** em diferentes ambientes de hardware e sistemas operacionais.

## 🎯 Objetivo da Validação
Demonstrar empiricamente que as propriedades de **Zero Data Loss (Persistência Íntegra)** e **Recuperação Criptográfica Sub-30ms** sob interrupção abrupta via `SIGKILL` são consistentes, mensuráveis e independentes de hardware específico ou timing de CPU.

## 💻 Requisitos de Ambiente
Para garantir a fidelidade do isolamento das chamadas de sistema (`os.fsync` e `os.rename`), o protocolo deve ser executado em ambientes POSIX nativos ou emulados:
1. **Ambiente Móvel/Edge Emulado**: Termux (Android) com Python 3.10+.
2. **Ambiente Linux Nativo**: Ubuntu 22.04 LTS ou superior (X86_64 / ARM64).
3. **Sistema de Arquivos Recomendado**: ext4, F2FS ou APFS.

## 🚀 Passos para Execução Independente

### Passo 1: Isolamento do Ambiente
Garanta que nenhum resíduo de execuções anteriores interfira na amostragem estocástica:
```bash
rm -rf outputs/ && mkdir -p outputs/


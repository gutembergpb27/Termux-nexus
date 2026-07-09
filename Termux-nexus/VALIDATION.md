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


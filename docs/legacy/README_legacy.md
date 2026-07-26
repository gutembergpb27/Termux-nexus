
---

## ⚠️ Limitações Conhecidas & Fronteiras do Sistema

Como plataforma experimental de Engenharia de Caos, o Nexus Runtime (v500) opera sob os seguintes limites arquiteturais documentados:

* **Gargalo de I/O do Hardware Periférico**: Como o sistema invoca o `os.fsync()` a cada bloco gravado para mitigar o cache volátil da RAM, a taxa máxima de ingestão está diretamente limitada pela velocidade de escrita física do armazenamento (eMMC, UFS ou SSD). Em mídias ou cartões SD de baixa performance, taxas abusivas de frequência podem gerar latência de contrapressão (*backpressure*).
* **Volatilidade do Arquivo Ativo Isolado**: Se o `SIGKILL` for disparado no microssegundo exato entre a exclusão do arquivo `.db.1` antigo e o *flush* físico do novo bloco de ancoragem no `.db`, o elo de transição é preservado na RAM, mas o histórico anterior pode sofrer truncamento se os descritores de arquivo do Kernel forem encerrados antes da sincronização atômica do bloco inicial.

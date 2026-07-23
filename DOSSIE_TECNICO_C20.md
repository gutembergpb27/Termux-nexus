# Dossiê Técnico de Evidências

## Nexus Runtime — Baseline Canônica de Integridade C20

### Identificação do responsável

- Nome: Gutemberg Procopio Barbosa
- Contato técnico: gtembergpb27@gmail.com
- Projeto: Nexus Runtime
- Repositório: Termux-nexus
- Branch canônica: `canonical-evidence`

## 1. Finalidade

Este dossiê registra, de forma técnica e verificável, as evidências produzidas durante a sequência de controles C1–C20 aplicada ao caminho de persistência do Nexus Runtime.

O objetivo é preservar uma referência documental vinculada a artefatos de software identificáveis por commit Git, tag e hashes SHA-256.

Este documento não constitui certificação independente, auditoria de terceira parte, prova formal de segurança ou garantia de invulnerabilidade.

## 2. Identidade da baseline técnica

A baseline técnica foi fixada nos seguintes identificadores:

- Commit completo: `680b03cb6b7c9a8c0199561e7c54d53e6014700a`
- Commit abreviado: `680b03c`
- Tag: `integrity-baseline-c20`
- Resultado da suíte: `23 passed, 1 xfailed`
- Ambiente observado: Android / Termux / Python 3.14.6 / pytest 9.1.1

A tag histórica foi criada com metadados Git genéricos de autor e tagger. Esses metadados são preservados como parte do histórico e não são apresentados como identificação pessoal válida do responsável.

A identidade técnica da baseline é estabelecida pelos objetos Git, pelos hashes dos artefatos e pela reprodutibilidade da suíte.

## 3. Continuidade entre a baseline e o estado documental

Após a tag C20, foram adicionados dois commits documentais:

- `afb7673` — publicação do relatório da baseline C20;
- `90a5ca4` — ligação do README ao relatório canônico.

A verificação realizada demonstrou que `persistence.py` e `tests/test_integrity.py` permaneceram byte a byte idênticos entre a tag C20 e o estado documental posterior.


## 4. Identificação criptográfica dos artefatos

### Artefatos da baseline técnica C20

Os seguintes hashes SHA-256 identificam os artefatos centrais testados:

- `persistence.py`
  - SHA-256: `dbf356837f333ab06cf26481874544e9b3907cecf8be05ed26ca5ee4d96b2244`

- `tests/test_integrity.py`
  - SHA-256: `5ae22f43444c1242dee423e384d8f7b4d35a808548d09095528e811a17ae0f65`

Esses hashes foram verificados tanto na tag `integrity-baseline-c20` quanto no estado documental posterior, com resultados idênticos.

### Artefatos documentais observados antes da criação deste dossiê

- `INTEGRITY_BASELINE_C20.md`
  - SHA-256: `fcb1696636feecff1ff1c65d8cbdc9f971af39237150f61d7e6f0be125e1204d`

- `README.md`
  - SHA-256 observado antes da inclusão deste dossiê: `f3835cf626b45af91bf0f68c37d1ab0780a43eacabdcfaaa8ea38bf8c076b74e`

O hash do README acima identifica o estado documental no commit `90a5ca4`.

## 5. Matriz resumida de evidências

A suíte canônica contém 24 casos coletados: 23 aprovados e 1 falha esperada documentada.

### Integridade da cadeia

Foram demonstrados:

- rejeição de payload adulterado;
- rejeição de `prev_hash` adulterado;
- aceitação de cadeia intacta;
- aceitação de cadeia válida após rotação;
- rejeição de âncora de rotação adulterada;
- rejeição de histórico rotacionado adulterado;
- rejeição de cauda truncada;
- rejeição de blocos reordenados;
- rejeição de bloco intermediário removido;
- rejeição de bloco forjado inserido;
- rejeição de replay de bloco válido.

### Rollback e metadados de integridade

Foram demonstrados:

- rejeição de snapshot antigo por comparação com checkpoint preservado;
- rejeição de `height` adulterado no checkpoint;
- rejeição de `tip_hash` adulterado no checkpoint;
- detecção de rollback coordenado quando uma âncora externa é preservada;
- rejeição de âncora externa configurada e ausente;
- rejeição de `height` adulterado na âncora externa;
- rejeição de `tip_hash` adulterado na âncora externa;
- rejeição de JSON corrompido na âncora externa.

### Consistência após interrupção e reinicialização

Foram demonstrados:

- rejeição de log à frente do checkpoint e da âncora;
- rejeição de checkpoint à frente da âncora externa;
- rejeição de checkpoint parcialmente escrito;
- recuperação correta de estado consistente após nova instância.


## 6. Limitação conhecida preservada

A suíte mantém deliberadamente um teste marcado como xfail:

test_recover_state_does_not_yet_reject_coordinated_log_and_checkpoint_rollback

Esse teste registra que, sem uma âncora externa preservada fora do conjunto restaurado, um rollback coordenado de log e checkpoint local pode permanecer internamente coerente.

## 7. Declaração de escopo

Este dossiê não afirma invulnerabilidade geral, certificação de segurança, validação independente por terceiros, resistência contra atacante com controle total do código/dados/âncora, nem equivalência entre arquivo de âncora e hardware seguro.

## 8. Reprodutibilidade

Com o repositório na branch canonical-evidence, execute:

python -m py_compile persistence.py tests/test_integrity.py
python -m pytest tests/test_integrity.py -v

Resultado esperado da baseline C20:

23 passed, 1 xfailed

## 9. Preparação para assinatura digital

Este documento foi preparado para posterior conversão em PDF e assinatura digital.

A assinatura digital deverá ser interpretada como registro de autoria, integridade documental e existência temporal deste dossiê, e não como certificação independente de segurança do software.

## 10. Conclusão

A Baseline Canônica de Integridade C20 consolida uma cadeia reproduzível de evidências técnicas para o caminho de persistência do Nexus Runtime.

O valor técnico principal está na combinação de testes automatizados, commits públicos, tag canônica, hashes SHA-256, limitação conhecida preservada e documentação explícita do escopo de confiança.

# Contributing to Nexus Runtime Platform

**English** · [Português (Brasil)](#contribuindo--português-brasil)

Nexus is an experimental, evidence-first project. Contributions are welcome
through GitHub issues and pull requests.

## Rules

1. **Pull requests only.** `main` is protected. Every change goes through a
   pull request and must pass the three required CI checks:
   `test-and-build`, `W05/W06 S1-S5 harness tests` and
   `W07 experimental hub hardening tests`.
2. **Evidence before claims.** Describe a capability as implemented only when
   code, tests and recorded evidence support it. State every known gap.
3. **Do not overstate.** Do not describe the project as providing distributed
   consensus, exactly-once execution, partition tolerance or production
   readiness. None of these is demonstrated; see the README limitations.
4. **Give the source of every figure:** the commit, CI run or experiment.
   Mark results that were not independently re-processed as
   *operator-reported*.
5. **Preserve evidence.** Never rewrite or delete recorded validation evidence.
   Add new evidence alongside it.
6. **No sensitive data.** Never commit secrets, private IP addresses, device
   identifiers or raw logs.
7. **Bilingual documentation.** `README.md` is the primary README.
   `README.pt-BR.md` and the Portuguese documents in `docs/` must stay
   equivalent to their English versions.

## Local checks

```bash
python -m pip install --upgrade pip pytest
python -m pip install -e .
python -m pytest -q
```

See the [documentation index](docs/README.md) for the project structure.

---

## Contribuindo — Português (Brasil)

O Nexus é um projeto experimental orientado por evidências. Contribuições são
bem-vindas por meio de issues e pull requests no GitHub.

1. **Somente via pull request.** A `main` é protegida. Toda alteração passa
   por um pull request e precisa ser aprovada nos três checks obrigatórios da
   CI: `test-and-build`, `W05/W06 S1-S5 harness tests` e
   `W07 experimental hub hardening tests`.
2. **Evidência antes de alegações.** Uma capacidade só é descrita como
   implementada quando código, testes e evidências registradas a sustentam.
   Toda lacuna conhecida deve ser declarada.
3. **Não exagere.** Não descreva o projeto como provedor de consenso
   distribuído, execução exatamente uma vez, tolerância a partições ou
   prontidão para produção. Nada disso foi demonstrado; veja as limitações no
   README.
4. **Informe a origem de cada número:** o commit, a execução de CI ou o
   experimento. Marque como *reportado pelo operador* o que não foi
   reprocessado de forma independente.
5. **Preserve as evidências.** Nunca reescreva nem apague evidências de
   validação registradas. Acrescente as novas evidências ao lado delas.
6. **Sem dados sensíveis.** Nunca publique segredos, IPs privados,
   identificadores de dispositivos ou logs brutos.
7. **Documentação bilíngue.** `README.md` é o README principal. O
   `README.pt-BR.md` e os documentos em português de `docs/` devem permanecer
   equivalentes às versões em inglês.

### Verificações locais

```bash
python -m pip install --upgrade pip pytest
python -m pip install -e .
python -m pytest -q
```

Veja o [índice da documentação](docs/README.pt-BR.md) para a estrutura do projeto.

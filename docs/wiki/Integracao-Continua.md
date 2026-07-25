# Integração contínua

O workflow `.github/workflows/ci.yml` executa automaticamente em pushes para `main`, branches `incremento/**` e pull requests destinados à `main`.

## Trilha 1 — qualidade e testes rápidos

- instala Python 3.12;
- instala o projeto com dependências de desenvolvimento e qualificação;
- executa `pip check`;
- executa Ruff;
- executa `manage.py check` com SQLite em memória;
- verifica migrações não versionadas;
- executa pytest;
- publica relatório JUnit como artefato.

## Trilha 2 — PostgreSQL e migrações

- inicia PostgreSQL 17 em contêiner de serviço;
- instala o projeto;
- verifica a configuração Django real;
- aplica todas as migrações em banco vazio;
- confirma ausência de alterações não registradas.

## Por que duas trilhas

SQLite torna os testes rápidos e isolados. PostgreSQL valida o comportamento do banco-alvo, as restrições e a cadeia completa de migrações. Uma trilha não substitui a outra.

## Proteção recomendada da main

Em `Settings → Branches → Branch protection rules`, proteger `main` e exigir:

- pull request antes de merge;
- aprovação quando houver equipe revisora;
- atualização da branch antes do merge;
- sucesso dos checks `Qualidade e testes` e `PostgreSQL e migrações`;
- bloqueio de force push e exclusão da branch.

## Execução manual

Na aba `Actions`, selecionar o workflow `CI` e usar `Run workflow`. O evento `workflow_dispatch` permite escolher a branch.

# Convenções de nomenclatura

## Diretriz geral

Todo nome novo criado especificamente para o Protocolo HIS deve ser escrito em português. A regra abrange arquivos, diretórios, módulos, scripts, classes, funções, métodos, variáveis, constantes, campos, rotas, tabelas, tarefas, fluxos e identificadores de domínio.

## Exceções técnicas

Permanecem em inglês nomes exigidos ou fortemente convencionados por Python, Django, Prefect, PostgreSQL, bibliotecas, protocolos e formatos. Exemplos: `__init__.py`, `models.py`, `views.py`, `apps.py`, `admin.py`, `urls.py`, `tests.py`, `migrations`, `save`, `ForeignKey`, `FileField`, `pyproject.toml`, `README.md`, `WSGI`, `SHA-256` e chaves padronizadas de JSON Schema.

Prefixos exigidos por ferramentas também são preservados. Funções de teste continuam começando com `test_`, pois essa é a convenção de descoberta do pytest.

## Nomes legados preservados

Os pacotes `config` e `applications`, já incorporados à base Django e ao histórico de migrações, permanecem inalterados para evitar riscos de compatibilidade e migrações puramente cosméticas. Eles constituem exceções legadas e não servem de precedente para novos nomes em inglês.

Outros nomes legados em inglês poderão ser preservados quando a alteração introduzir risco técnico, quebrar compatibilidade, modificar contratos externos ou gerar migração sem benefício funcional proporcional. Cada exceção deverá ser explicitamente justificada.

## Forma dos nomes

- Python: `snake_case` para módulos, funções, métodos e variáveis; `PascalCase` para classes.
- Diretórios e arquivos próprios: letras minúsculas, sem espaços, com palavras separadas por sublinhado.
- Campos e tabelas: português, sem acentos, em `snake_case`.
- Classes e textos exibidos ao usuário: português com acentuação normal.
- Siglas consolidadas, como HIS, IBGE, PDF, OCR, RAG e SHA-256, podem ser mantidas.

## Exemplos

Preferir `aplicacao_municipal`, `documento_normativo`, `calcular_sha256`, `raiz_dados_protocolo`, `cartao_evidencia` e `fatia_vertical`.

Evitar `municipal_application`, `normative_document`, `calculate_hash`, `data_root`, `evidence_card` e `vertical_slice` em novos componentes próprios.

## Aplicação da regra

Toda revisão de código deve verificar a aderência a esta convenção. Novas exceções devem resultar de uma exigência concreta de ferramenta, padrão externo ou compatibilidade histórica e devem ser registradas neste documento.

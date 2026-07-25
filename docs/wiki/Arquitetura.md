# Arquitetura

## Núcleo

- Django: domínio, interface, usuários, decisões e histórico;
- PostgreSQL: fonte oficial de dados transacionais e metodológicos;
- sistema de arquivos: originais imutáveis e artefatos derivados;
- conversor-his: diagnóstico, OCR, extração, Markdown e manifestos;
- HTMX: interatividade progressiva sem frontend separado.

## Processamento e análise

- Prefect: orquestração, retomada, cache e reprocessamento seletivo;
- pgvector: recuperação semântica dentro do banco governado;
- Ollama: execução local de modelos e embeddings;
- Docling: extração complementar de layouts e tabelas complexas;
- scikit-learn: modelos supervisionados artigo × variável;
- DuckDB + Parquet: snapshots, benchmarks e análise reprodutível.

## Relatórios

- python-docx e docxtpl para DOCX editável;
- conversão headless para PDF;
- validação de seções, tabelas, referências e integridade.

## Princípios

- PostgreSQL como fonte oficial da verdade;
- artigo como unidade canônica;
- originais imutáveis e derivados versionados;
- fonte separada de interpretação;
- sugestão automática separada de decisão humana;
- prompts, regras e modelos versionados;
- execuções reproduzíveis e retomáveis;
- relatório apenas a partir de resultados validados.

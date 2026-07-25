# Apêndice — Decisões tecnológicas e critérios de escolha

## Finalidade

A arquitetura da Plataforma Protocolo HIS foi escolhida para sustentar um processo longo, auditável e progressivamente automatizado, no qual os arquivos originais devem ser preservados, as transformações precisam ser reproduzíveis e as decisões metodológicas permanecem sob controle humano.

A seleção de componentes não decorre apenas de popularidade. Cada tecnologia foi avaliada segundo os seguintes critérios:

1. **licença aberta e sustentabilidade do ecossistema**;
2. **execução local e independência de serviços proprietários**;
3. **rastreabilidade, versionamento e possibilidade de auditoria**;
4. **integração com Python e com processamento documental**;
5. **maturidade para uso institucional**;
6. **portabilidade entre Windows, Linux e contêineres**;
7. **facilidade de teste automatizado**;
8. **capacidade de evolução incremental sem reescrita integral**;
9. **separação entre dados oficiais, artefatos derivados e sugestões automatizadas**;
10. **compatibilidade com a exigência de intervenção humana nas decisões jurídicas e metodológicas**.

## Quadro sintético

| Componente | Função | Motivo principal da escolha | Alternativas consideradas |
|---|---|---|---|
| Python | linguagem principal | ecossistema documental, científico, jurídico e de IA; legibilidade; ampla oferta de bibliotecas | Java, .NET, Node.js |
| Django | aplicação web e domínio transacional | ORM maduro, migrações, autenticação, Admin, segurança e testes integrados | FastAPI, Flask, Rails |
| HTMX | interatividade da interface | reduz complexidade de frontend e mantém regras e validações no servidor | React, Vue, Alpine.js |
| PostgreSQL | banco oficial | integridade transacional, JSON, busca, extensões, maturidade e portabilidade | SQLite, MySQL, MariaDB |
| pgvector | recuperação vetorial | embeddings no mesmo banco governado e transacional | Qdrant, Weaviate, Milvus, Chroma |
| Prefect | orquestração | fluxos Python, retomada, observabilidade e execução local | Airflow, Dagster, Celery |
| sistema de arquivos | originais e artefatos | preservação simples, verificável por hash e independente do banco | armazenamento em BLOB, S3/MinIO |
| conversor-his | conversão normativa | controle do pipeline específico do projeto e artefatos auditáveis | pipelines genéricos isolados |
| OCRmyPDF | coordenação de OCR em PDF | preserva o PDF, adiciona camada pesquisável e registra transformações | execução direta de OCR página a página |
| Tesseract | reconhecimento óptico | software livre, local, amplamente testado e multilíngue | PaddleOCR, EasyOCR, serviços em nuvem |
| Docling | layout e tabelas complexas | extração estruturada complementar para documentos heterogêneos | Unstructured, Marker, Camelot/Tabula isolados |
| Markdown | formato intermediário | legível por humanos, versionável, pesquisável e adequado a RAG | HTML, XML, texto simples, JSON puro |
| Ollama | execução local de modelos | isolamento de dados, API simples e substituição de modelos | servidores proprietários, vLLM, llama.cpp direto |
| scikit-learn | aprendizado supervisionado inicial | modelos interpretáveis, benchmarks sólidos e baixo custo operacional | PyTorch, TensorFlow, XGBoost |
| DuckDB | análise de snapshots | consultas analíticas locais sobre Parquet sem infraestrutura adicional | Spark, Polars isolado, PostgreSQL analítico |
| Parquet | snapshots analíticos | formato colunar aberto, compacto e interoperável | CSV, JSON Lines, formatos proprietários |
| python-docx/docxtpl | relatório editável | geração de DOCX institucionalmente revisável | LaTeX, HTML puro, LibreOffice UNO |
| PDF headless | versão final estável | padronização visual e validação independente do DOCX | geração PDF inteiramente customizada |
| pytest | testes | fixtures, integração Django e relatórios JUnit | unittest puro, nose |
| Ruff | qualidade estática | rapidez e consolidação de múltiplas verificações | Flake8, isort e pyupgrade separados |
| GitHub Actions | integração contínua | execução reproduzível associada a commits e PRs | Jenkins, GitLab CI, Woodpecker CI |

## Python

Python foi adotado como linguagem principal porque concentra, no mesmo ecossistema, ferramentas para aplicações web, processamento de PDF, OCR, linguagem natural, aprendizado de máquina, análise tabular e geração de relatórios. A legibilidade favorece auditoria e transferência de conhecimento entre pesquisadores e desenvolvedores.

A opção evita a fragmentação de um pipeline distribuído entre várias linguagens. Componentes externos podem ser incorporados quando oferecem vantagem clara, mas a camada de orquestração e de domínio permanece em Python.

## Django

Django foi escolhido para representar o domínio operacional e metodológico do Protocolo HIS. A plataforma precisa manter entidades relacionadas, restrições de integridade, histórico, permissões, formulários, migrações e interface administrativa. Django entrega esses elementos como um conjunto coerente e maduro.

O Django Admin permite disponibilizar rapidamente operações internas sem antecipar um frontend completo. O ORM e as migrações tornam explícita a evolução do modelo de dados. O sistema de autenticação cria base para papéis como operador, curador, revisor e adjudicador.

FastAPI seria adequado para uma API de alto desempenho, mas exigiria compor separadamente administração, autenticação, formulários, migrações e interface. Para este MVP, a prioridade é consistência transacional e velocidade de evolução do domínio, não uma API pública de altíssima concorrência.

## HTMX

HTMX foi previsto para acrescentar interatividade progressiva às páginas Django sem criar uma aplicação JavaScript independente. Essa decisão reduz duplicação de validações, contratos de API e estados de interface.

A maior parte das operações do Protocolo é transacional e orientada a formulários, filas, leitura e comparação. Nessa situação, renderização no servidor com atualizações parciais tende a ser suficiente e mais simples de auditar. Um frontend especializado continua possível para visualizações que realmente o exijam.

## PostgreSQL

PostgreSQL é a fonte oficial de dados porque oferece integridade referencial, transações, restrições, índices, JSON, busca textual e extensões. Essas capacidades permitem manter no mesmo núcleo governado os objetos documentais, metodológicos e decisórios.

SQLite é utilizado apenas em testes rápidos, pois não reproduz integralmente concorrência, tipos, extensões e comportamento transacional do ambiente-alvo. Por essa razão, a integração contínua possui uma etapa adicional que aplica todas as migrações em PostgreSQL vazio.

## pgvector

pgvector foi escolhido para a primeira camada semântica porque mantém vetores junto aos artigos, metadados, versões e decisões. Isso simplifica backup, controle de acesso e rastreabilidade.

Bancos vetoriais especializados poderão ser avaliados quando volume ou latência demonstrarem necessidade objetiva. Antes disso, introduzi-los criaria uma segunda fonte de dados, sincronização adicional e maior custo operacional.

## Prefect

Prefect foi selecionado para orquestrar tarefas longas e retomáveis, como diagnóstico, OCR, conversão, segmentação, indexação, recuperação e geração de relatórios. Seus fluxos são definidos em Python, o que reduz a distância entre código operacional e código de domínio.

A escolha considera:

- estados explícitos de execução;
- retentativas controladas;
- cache e reprocessamento seletivo;
- observabilidade;
- execução local ou em workers;
- parametrização por aplicação, documento e versão.

Airflow é maduro, porém orientado principalmente a agendas e DAGs de engenharia de dados, com infraestrutura mais pesada. Celery é excelente como fila distribuída, mas exige construir parte relevante da observabilidade e da semântica de fluxos. Dagster permanece alternativa tecnicamente forte e poderá ser reavaliado se a gestão de ativos de dados se tornar o eixo dominante.

## Preservação em sistema de arquivos

Arquivos originais e artefatos derivados são mantidos em armazenamento persistente com caminhos determinísticos e hashes. O banco registra identidade, localização e metadados, mas não substitui o arquivo como objeto preservado.

Essa separação:

- evita inflar o banco com grandes BLOBs;
- facilita inspeção e cópia controlada;
- permite validação independente por SHA-256;
- prepara migração futura para armazenamento compatível com S3, como MinIO.

## conversor-his, OCRmyPDF e Tesseract

O `conversor-his` encapsula as decisões específicas de conversão normativa: diagnóstico, seleção de rota, OCR seletivo, extração, estrutura, Markdown, ativos, métricas e manifesto.

OCRmyPDF é usado como coordenador de OCR porque preserva o PDF e acrescenta uma camada textual pesquisável. Tesseract é o mecanismo padrão por ser livre, executável localmente e amplamente difundido. A combinação permite registrar versão, idioma, resolução e demais parâmetros.

PaddleOCR e outros motores podem ser testados em benchmark, principalmente para layouts ou digitalizações em que Tesseract apresente baixo desempenho. A substituição deve ser orientada por métricas de caracteres, palavras, estrutura e recuperação, não por preferência abstrata.

## Docling

Docling foi selecionado como ferramenta complementar para documentos com estrutura visual complexa, tabelas, múltiplas colunas e elementos gráficos. Ele não substitui a preservação do PDF nem a auditoria visual.

A estratégia é combinar ferramentas especializadas por rota documental, mantendo um formato intermediário comum e registrando a origem de cada elemento extraído.

## Markdown como formato intermediário

Markdown oferece equilíbrio entre legibilidade humana e processamento automatizado. Pode ser versionado em Git, comparado linha a linha, renderizado com segurança e segmentado por marcadores estáveis.

Ele não pretende representar sozinho toda a semântica do documento. Estruturas, coordenadas, relações, métricas e manifestos permanecem em objetos JSON ou no banco. O Markdown é a superfície textual auditável, não a única fonte de metadados.

## Ollama e modelos locais

Ollama foi previsto como camada inicial para executar modelos e embeddings localmente. Isso reduz exposição de corpora normativos e permite trocar modelos sem alterar toda a aplicação.

A IA será usada para descoberta, organização, síntese e sugestão. Classificação final, resolução de conflito e adjudicação permanecem humanas. Toda execução relevante deverá registrar modelo, versão, prompt, parâmetros, entrada, saída e estado de validação.

vLLM ou servidores especializados poderão substituir Ollama quando houver requisitos medidos de concorrência e desempenho. A interface deverá permanecer desacoplada do fornecedor.

## scikit-learn

Os primeiros modelos supervisionados devem priorizar interpretabilidade e comparação. TF-IDF, regressão logística, SVM linear, árvores e calibração permitem medir ganhos sobre regras e busca sem introduzir uma arquitetura pesada.

Redes neurais poderão ser testadas posteriormente, mas apenas quando houver dataset validado suficiente e benefício demonstrável. O princípio é usar o modelo mais simples capaz de produzir melhoria mensurável.

## DuckDB e Parquet

Parquet foi escolhido para snapshots analíticos por ser aberto, colunar, compacto e interoperável. DuckDB permite consultar esses arquivos diretamente com SQL, sem implantar um segundo servidor.

Essa combinação é adequada para benchmarks, comparação de versões, matrizes de avaliação e análise de métricas. PostgreSQL continua sendo a fonte transacional; Parquet representa fotografias versionadas para pesquisa e auditoria.

## python-docx, docxtpl e PDF headless

O relatório precisa ser editável durante revisão institucional. DOCX atende a esse requisito e pode ser gerado a partir de templates controlados. `python-docx` e `docxtpl` permitem preencher tabelas, textos e referências sem depender de software proprietário durante a geração.

A versão PDF será derivada em ambiente headless e validada separadamente. O processo deverá verificar existência de seções, tabelas, referências, paginação e integridade do arquivo.

## pytest e Ruff

pytest foi escolhido pela integração com Django, fixtures, parametrização e produção de relatórios JUnit. Ruff concentra lint, importações e várias verificações em uma ferramenta rápida, reduzindo tempo de CI e divergência de configuração.

Testes são organizados em camadas:

- unidade e regras de domínio;
- integridade de modelos e migrações;
- serviços documentais;
- interface;
- integração com PostgreSQL;
- regressão com corpora de referência.

## GitHub Actions

GitHub Actions foi adotado como primeira infraestrutura de integração contínua porque associa automaticamente resultados ao commit e ao pull request. O workflow inicial executa duas trilhas:

1. qualidade e testes rápidos com SQLite em memória;
2. verificação real de migrações em PostgreSQL 17 vazio.

Essa separação preserva velocidade sem perder compatibilidade com o banco-alvo. Artefatos JUnit são retidos para inspeção. Novas etapas poderão incluir cobertura, segurança de dependências, build de contêiner, benchmarks e testes de conversão.

## Critério de reavaliação

Nenhuma escolha é irreversível. Uma tecnologia deve ser reavaliada quando pelo menos uma destas condições ocorrer:

- não atender requisito funcional ou de segurança;
- apresentar falhas recorrentes sem correção sustentável;
- produzir custo operacional desproporcional;
- impedir portabilidade ou reprodutibilidade;
- ser superada, em benchmark documentado, por alternativa aberta equivalente;
- introduzir dependência externa incompatível com a governança dos dados;
- deixar de receber manutenção adequada.

A substituição deverá incluir registro da decisão, benchmark, plano de migração, compatibilidade com versões anteriores e testes de regressão.

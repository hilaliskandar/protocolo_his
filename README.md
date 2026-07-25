# Plataforma Protocolo HIS

A Plataforma Protocolo HIS organiza, em um processo único e rastreável, a passagem da legislação municipal ao relatório de avaliação da receptividade normativa à produção de Habitação de Interesse Social.

O projeto combina cadastro do corpus normativo, preservação dos arquivos originais, qualificação documental, conversão para Markdown, registro de artefatos derivados, inspeção página a página e visualização integrada de PDF e texto convertido.

## Estado atual

A plataforma já possui os seguintes incrementos implementados:

1. **Base operacional e cadastro do corpus**
   - municípios;
   - aplicações municipais;
   - tipos normativos;
   - documentos normativos;
   - versões documentais imutáveis;
   - hash SHA-256 dos arquivos originais;
   - identificação de duplicatas.

2. **Qualificação documental**
   - classificação da rota de processamento;
   - diagnóstico página a página;
   - identificação de páginas com texto nativo, OCR, mapas, tabelas e conteúdo visual;
   - registro de avisos, métricas e dados técnicos;
   - armazenamento do diagnóstico JSON;
   - execução idempotente e auditável.

3. **Interface da qualificação**
   - painel geral do pipeline;
   - páginas de aplicações, documentos, processamentos e diagnósticos;
   - filtros por rota, tipo de página e avisos;
   - visualização estruturada de JSON;
   - acesso aos artefatos produzidos.

4. **Visualizador documental**
   - leitura integrada do PDF original;
   - renderização segura do Markdown convertido;
   - comparação lado a lado entre PDF e Markdown;
   - indicação de disponibilidade ou ausência da conversão;
   - acesso ao leitor a partir do corpus municipal e da página do documento.

5. **Conversão documental**
   - integração com o pacote `conversor-his`;
   - conversão seletiva com texto nativo, OCR e preservação de conteúdo visual;
   - registro do Markdown como artefato;
   - geração de pacote ZIP contendo manifesto, tokens OCR, estrutura OCR, imagens e Markdown;
   - validação de hashes do original e do Markdown;
   - métricas de páginas, revisão, OCR, mapas, tabelas e ativos visuais;
   - reutilização de conversões anteriores com os mesmos parâmetros.

## Arquitetura resumida

```text
Arquivo original
    ↓
VersaoDocumento imutável
    ↓
Qualificação documental
    ├── ProcessamentoDocumento
    ├── DiagnosticoPagina
    └── Diagnóstico JSON
    ↓
Conversão documental
    ├── Markdown
    ├── manifesto
    ├── tokens OCR
    ├── estrutura OCR
    ├── ativos visuais
    └── pacote ZIP auditável
    ↓
Leitor PDF / Markdown
    ↓
Validação humana e análise HIS
```

## Tecnologias principais

- Python 3.12 ou superior;
- Django 5.2;
- PostgreSQL 17;
- psycopg 3;
- `conversor-his`;
- `markdown-it-py`;
- pytest e pytest-django;
- Ruff.

## Ambiente local de referência

A configuração local atualmente utilizada no desenvolvimento é:

```text
Projeto:      F:\ale_2_0\protocolo_his_local
Python:       C:\Users\USER\.conda\envs\protocolo-his\python.exe
PostgreSQL:   C:\Program Files\PostgreSQL\17\bin
Cluster:      F:\ale_2_0\postgres_his_17\data
Banco:        protocolo_his
Host:         127.0.0.1
Porta:        55432
Django:       http://127.0.0.1:8000/
```

Esses caminhos são apenas a configuração do ambiente de desenvolvimento atual e podem ser adaptados em outras instalações.

## Instalação

Clone o repositório e entre na pasta do projeto:

```powershell
git clone https://github.com/hilaliskandar/protocolo_his.git
git switch incremento/conversao-documental
cd protocolo_his
```

Crie ou ative o ambiente Python e instale as dependências:

```powershell
& "C:\Users\USER\.conda\envs\protocolo-his\python.exe" -m pip install -e ".[dev,qualificacao]"
```

Crie um arquivo `.env` na raiz do projeto. Exemplo:

```dotenv
DJANGO_SECRET_KEY=altere-esta-chave
DJANGO_DEBUG=true
POSTGRES_DB=protocolo_his
POSTGRES_USER=protocolo_his
POSTGRES_PASSWORD=altere-esta-senha
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=55432
PROTOCOL_DATA_ROOT=F:\ale_2_0\protocolo_his_local\data
```

Não versione senhas reais ou chaves de produção.

## Inicialização completa no Windows

O repositório contém um inicializador em:

```text
scripts/windows/INICIAR_PROTOCOLO_HIS.bat
```

O arquivo:

- valida os caminhos configurados;
- verifica se o PostgreSQL está ativo;
- inicia o cluster na porta 55432 quando necessário;
- aguarda o banco aceitar conexões;
- executa `manage.py check`;
- inicia o Django;
- abre a plataforma no navegador.

Antes do primeiro uso, confira as variáveis no início do arquivo `.bat` e ajuste os caminhos locais.

Também é possível iniciar manualmente:

```powershell
$py = "C:\Users\USER\.conda\envs\protocolo-his\python.exe"
$pg = "C:\Program Files\PostgreSQL\17\bin"
$data = "F:\ale_2_0\postgres_his_17\data"
$log = "F:\ale_2_0\postgres_his_17\postgresql.log"

& "$pg\pg_ctl.exe" status -D $data
if ($LASTEXITCODE -ne 0) {
    & "$pg\pg_ctl.exe" start -D $data -l $log -o "-p 55432"
}

& "$pg\pg_isready.exe" -h 127.0.0.1 -p 55432 -d protocolo_his
& $py manage.py runserver
```

Para encerrar apenas o Django, pressione `Ctrl+C`. O PostgreSQL permanecerá ativo.

Para encerrar o cluster manualmente:

```powershell
& "$pg\pg_ctl.exe" stop -D $data -m fast
```

## Preparação do banco

Execute as migrações:

```powershell
& $py manage.py migrate
```

Crie um superusuário:

```powershell
& $py manage.py createsuperuser
```

A administração ficará disponível em:

```text
http://127.0.0.1:8000/admin/
```

## Fluxo operacional

### 1. Cadastro e ingestão

Cadastre o município, a aplicação municipal, os tipos normativos e os documentos pelo Admin ou pelas rotinas de importação existentes.

Cada arquivo recebido é registrado como `VersaoDocumento` e recebe:

- nome original;
- MIME type;
- tamanho;
- SHA-256;
- origem do recebimento;
- situação de ingestão;
- relação com eventual duplicata.

O arquivo original deve permanecer preservado e não deve ser sobrescrito.

### 2. Qualificação documental

A qualificação deve ser realizada antes da conversão.

Por aplicação:

```powershell
& $py manage.py qualificar_documentos --aplicacao 1
```

Por documento:

```powershell
& $py manage.py qualificar_documentos --documento 1
```

Por versão:

```powershell
& $py manage.py qualificar_documentos --versao 1
```

Para forçar nova execução:

```powershell
& $py manage.py qualificar_documentos --aplicacao 1 --forcar
```

A qualificação registra:

- rota geral do documento;
- páginas nativas;
- páginas para OCR;
- páginas visuais;
- mapas e tabelas suspeitos;
- avisos;
- duração;
- parâmetros utilizados;
- diagnóstico JSON.

### 3. Conversão documental

A conversão só é executada quando existe qualificação concluída para a versão.

Por aplicação:

```powershell
& $py manage.py converter_documentos --aplicacao 1
```

Por documento:

```powershell
& $py manage.py converter_documentos --documento 1
```

Por versão:

```powershell
& $py manage.py converter_documentos --versao 1
```

Com DPI específico:

```powershell
& $py manage.py converter_documentos --aplicacao 1 --dpi 300
```

Para forçar nova execução:

```powershell
& $py manage.py converter_documentos --aplicacao 1 --forcar
```

O DPI deve estar entre 150 e 600.

O processo produz:

- Markdown convertido;
- manifesto de conversão;
- tokens OCR posicionais;
- estrutura OCR reconstruída;
- imagens de mapas, tabelas, diagramas e páginas para revisão;
- métricas e avisos;
- pacote ZIP auditável.

## Interface web

### Painel

```text
http://127.0.0.1:8000/
```

O painel mostra:

- municípios;
- aplicações;
- documentos;
- documentos verificados;
- documentos em quarentena;
- processamentos;
- páginas diagnosticadas;
- páginas destinadas a OCR;
- páginas visuais;
- processamentos recentes.

### Aplicações municipais

```text
http://127.0.0.1:8000/aplicacoes/
```

Uma aplicação específica pode ser acessada por:

```text
http://127.0.0.1:8000/aplicacoes/<id>/
```

### Documento

```text
http://127.0.0.1:8000/documentos/<id>/
```

A página reúne identificação, versões, processamentos e artefatos.

### Leitor documental

```text
http://127.0.0.1:8000/documentos/<id>/leitor/
```

Modos disponíveis:

```text
?modo=pdf
?modo=markdown
?modo=comparacao
```

O modo Markdown é ativado automaticamente quando existe artefato convertido concluído.

### Processamento

```text
http://127.0.0.1:8000/processamentos/<id>/
```

A página apresenta:

- etapa;
- estado;
- ferramenta e versão;
- rota;
- métricas;
- parâmetros;
- avisos;
- páginas diagnosticadas;
- filtros;
- artefatos relacionados.

### Artefatos

```text
http://127.0.0.1:8000/artefatos/<id>/
```

JSON, Markdown e outros arquivos textuais de até 5 MB podem ser lidos na interface. Arquivos maiores permanecem disponíveis para download.

## Modelos centrais

### `Municipio`

Identifica o município e seus metadados territoriais.

### `AplicacaoMunicipal`

Representa uma aplicação do Protocolo HIS a um corpus municipal.

### `DocumentoNormativo`

Representa um diploma normativo incluído no corpus.

### `VersaoDocumento`

Preserva uma versão recebida, imutável e identificada por SHA-256.

### `ProcessamentoDocumento`

Registra uma execução de qualificação, conversão ou validação, incluindo ferramenta, versão, parâmetros, métricas, estado e duração.

### `DiagnosticoPagina`

Registra o diagnóstico técnico de cada página do documento.

### `ArtefatoProcessado`

Registra arquivos derivados, como diagnóstico JSON, Markdown, logs e pacotes de conversão.

## Armazenamento e rastreabilidade

Os arquivos originais são armazenados em caminhos estáveis derivados de seu hash:

```text
immutable/documentos/<documento_id>/<sha256>.<extensão>
```

Os artefatos derivados são armazenados em:

```text
derived/processamentos/<processamento_id>/<sha256>.<extensão>
```

Cada processamento deve preservar:

- arquivo-fonte;
- hash do original;
- ferramenta;
- versão da ferramenta;
- versão do código;
- parâmetros;
- métricas;
- avisos;
- duração;
- artefatos resultantes.

## Verificações de qualidade

Execute antes de consolidar um incremento:

```powershell
& $py manage.py check
& $py -m ruff check .
& $py -m pytest -q
& $py manage.py makemigrations --check --dry-run
```

Resultados esperados:

```text
System check identified no issues
All checks passed!
Todos os testes aprovados
No changes detected
```

## Segurança do leitor

O Markdown é renderizado com HTML bruto desabilitado. Conteúdo como `<script>` é apresentado como texto e não executado.

Os PDFs são servidos com conteúdo embutido e cabeçalhos que evitam interpretação incorreta do tipo de arquivo.

Arquivos textuais têm limite de visualização na interface para evitar consumo excessivo de memória.

## Organização das branches de incremento

As principais branches produzidas até o momento são:

```text
incremento/qualificacao-documental
incremento/interface-qualificacao
incremento/visualizador-documental
incremento/conversao-documental
```

Cada incremento foi construído sobre o anterior para preservar uma cadeia verificável de evolução.

## Próximos incrementos

As próximas etapas previstas são:

1. validação humana da conversão;
2. aprovação ou rejeição por página;
3. registro de divergências e correções;
4. segmentação hierárquica da legislação;
5. reconstrução de títulos, capítulos, seções e artigos;
6. indexação e recuperação de trechos;
7. formulação e execução das perguntas-agulha;
8. identificação de dispositivos candidatos às variáveis HIS;
9. validação humana dos dispositivos;
10. geração do relatório técnico final.

## Princípios metodológicos

A plataforma é orientada por:

- reprodutibilidade;
- rastreabilidade;
- preservação do original;
- separação entre fonte, processamento e interpretação;
- automação assistida, sem substituição da validação humana;
- registro explícito de ferramentas, versões e parâmetros;
- tratamento conservador de mapas, tabelas, OCR e estruturas visuais;
- possibilidade de auditoria de cada resultado.

## Licença

Este projeto está licenciado sob a licença MIT. Consulte o arquivo `LICENSE`.

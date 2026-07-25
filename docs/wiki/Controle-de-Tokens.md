# Controle de tokens e consumo de IA

## Finalidade

O controle de tokens é uma camada de planejamento, auditoria e eficiência das operações que envolvem modelos de linguagem. Ele não altera a análise jurídica nem substitui as métricas de qualidade; permite estimar contexto, tempo, custo potencial, volume de processamento e adequação entre tarefa, modelo e infraestrutura.

Nesta fase, a funcionalidade permanece opcional. A conversão de PDF, OCR e reconstrução de Markdown continua local e não deve ser contabilizada como consumo de tokens de LLM. A mensuração começa na geração de embeddings e nas chamadas generativas de recuperação, extração, classificação, validação e redação.

## Duas medidas diferentes

1. **estimativa local**: calculada antes da chamada, com tokenizer e encoding declarados;
2. **uso efetivo**: informado pelo provedor ou pelo servidor local após a execução.

A estimativa serve para orçamento e desenho de contexto. O uso efetivo é a fonte final para consolidação operacional. Tokens posicionais produzidos por OCR não equivalem a tokens de modelos de linguagem.

## Utilitário disponível

O repositório inclui:

```text
scripts/contar_tokens_corpus_his.py
```

Instalação opcional:

```bash
python -m pip install -e ".[observabilidade-ia]"
```

Exemplo de execução:

```bash
python scripts/contar_tokens_corpus_his.py \
  --raiz caminho/para/o/corpus_markdown \
  --encoding o200k_base \
  --csv artefatos/tokens_por_arquivo.csv \
  --json artefatos/resumo_tokens.json
```

Quando o modelo estiver reconhecido pelo tokenizer, pode-se usar `--modelo` em lugar de `--encoding`. Se o mapeamento não existir, o script registra explicitamente o fallback para `o200k_base`.

## Saídas auditáveis

O CSV registra por arquivo:

- caminho relativo;
- bytes e caracteres;
- tokens estimados;
- razão de tokens por mil caracteres;
- hash SHA-256.

O JSON de resumo registra:

- data e raiz do corpus;
- modelo solicitado;
- encoding e origem da escolha;
- versão do `tiktoken`;
- quantidade de arquivos;
- totais de bytes, caracteres e tokens;
- caminho do CSV correspondente.

## Unidade futura de auditoria

A unidade adequada para o controle operacional será a chamada de IA. Quando a camada de execução de modelos for implementada, cada chamada deverá registrar ao menos:

- identificadores da execução e da chamada;
- etapa do pipeline;
- município e variável;
- modelo, provedor ou servidor local;
- tokenizer e encoding usados na previsão;
- versão do template de prompt;
- documentos e chunks recuperados;
- tokens estimados de entrada;
- tokens efetivos de entrada, cache e saída;
- latência, tentativas, status e erro;
- vínculo com o resultado validado.

## Indicadores derivados

A base permitirá calcular, entre outros:

- desvio entre estimativa e uso real;
- tokens e tempo por município, variável e etapa;
- p50, p90 e p95 do contexto recuperado;
- taxa de reutilização de contexto;
- volume de retries e retrabalho;
- custo estimado ou efetivo por modelo, quando houver tarifa aplicável;
- relação entre consumo, precisão, revocação, F1 e validação humana.

## Gates iniciais

Os valores devem ser calibrados empiricamente, mas podem começar com os seguintes controles:

- mesma versão do corpus e mesmo encoding devem reproduzir a mesma contagem;
- contexto recuperado não deve ocupar mais de 80% da janela do modelo sem justificativa;
- alertas de orçamento em 70%, 85% e 100%;
- desvio absoluto entre previsão e uso real de até 10% após a fase de calibração;
- retrabalho generativo acima de 15% deve gerar investigação;
- releitura integral repetida do corpus deve ser evitada quando houver evidência persistida ou recuperação seletiva.

## Momento de incorporação ao banco

A persistência em modelos Django será feita junto com a camada real de chamadas de IA. Antecipá-la agora poderia cristalizar campos dependentes de provedores ainda não escolhidos. Até lá, CSV e JSON versionados por execução oferecem uma solução simples, portátil e auditável.

## Critério metodológico

O controle de tokens deve ser analisado junto com qualidade e rastreabilidade. Menor consumo não é, isoladamente, melhor resultado: a eficiência relevante é obter evidência suficiente, resposta válida e baixa necessidade de retrabalho com o menor uso justificável de contexto, tempo e recursos.

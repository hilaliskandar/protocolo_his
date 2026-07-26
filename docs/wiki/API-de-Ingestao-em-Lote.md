# API de ingestão em lote

A API recebe um ZIP preservado integralmente, inspeciona seus itens, produz um manifesto provisório, admite correção humana dos metadados e somente depois cria os registros definitivos do corpus.

## Autenticação

Defina no `.env`:

```dotenv
API_INGESTAO_TOKEN=troque-por-um-token-longo
```

Todas as rotas exigem `Authorization: Bearer <token>`. A autenticação administrativa por sessão permanece restrita ao Admin e não é aceita pela API.

## Fluxo

### 1. Receber o ZIP

```bash
curl -X POST http://127.0.0.1:8000/api/v1/importacoes/ \
  -H "Authorization: Bearer $API_INGESTAO_TOKEN" \
  -H "Idempotency-Key: rm-jundiai-lote-4" \
  -F "arquivo_zip=@lote.zip" \
  -F "titulo=RM Jundiaí — lote 4" \
  -F "origem_recebimento=corpus municipal" \
  -F "uf_padrao=SP"
```

A chave de idempotência é opcional, mas recomendada. Repetir a mesma chave reutiliza o lote já registrado e não grava uma segunda cópia do ZIP.

### 2. Inspecionar

```bash
curl -X POST http://127.0.0.1:8000/api/v1/importacoes/UUID/inspecionar/ \
  -H "Authorization: Bearer $API_INGESTAO_TOKEN"
```

A inspeção valida caminhos, limites, assinatura PDF, hashes e duplicatas. Também realiza leitura preliminar de até três páginas para registrar quantidade de páginas, caracteres amostrados e rota sugerida: `texto_nativo`, `misto`, `ocr` ou `manual`.

Nenhum ato é criado nessa etapa.

## Metadados aceitos e sugestões textuais

Os campos utilizados para confirmar o corpus permanecem separados dos indícios encontrados nas primeiras páginas:

| Finalidade | Campos principais |
|---|---|
| metadados candidatos aceitos | `numero_candidato`, `numero_normalizado`, `ano_candidato`, `fontes_metadados` |
| sugestões extraídas do texto | `numero_sugerido_texto`, `numero_sugerido_normalizado`, `ano_sugerido_texto`, `fontes_sugestoes` |
| conflitos detectados | `divergencias_metadados` |

A leitura preliminar **não valida a identidade jurídica do ato**. Número ou ano encontrados somente no texto não preenchem os campos aceitos e não promovem o item para `pronto`.

Quando o texto divergir do nome do arquivo ou de outra fonte estrutural, a API preserva os dois valores, registra a divergência e mantém o item em `revisao`. Isso evita que uma remissão a outra lei seja confundida com a identificação do documento principal.

Os campos de sugestão e divergência são produzidos pela inspeção e expostos para consulta; não são editáveis pelo `PATCH`. A adjudicação humana ocorre nos campos candidatos aceitos.

### Documentos de apoio

Anexos e fragmentos possuem dois vínculos distintos:

- `documento_principal_sugerido`: hipótese automática, sem efeito de confirmação;
- `documento_principal_candidato`: vínculo aceito após revisão humana.

Sugestões baseadas apenas no conteúdo textual não criam vínculo automático com o ato principal.

### 3. Corrigir um item

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/itens-importacao/ITEM_ID/ \
  -H "Authorization: Bearer $API_INGESTAO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "municipio_candidato": "Jundiaí",
    "uf": "SP",
    "natureza": "normativo_municipal",
    "tipo_normativo_codigo": "lei_ordinaria",
    "numero_candidato": "7016",
    "ano_candidato": 2008,
    "titulo_candidato": "Política Municipal de Habitação",
    "estado": "pronto"
  }'
```

Arquivos sem assinatura PDF válida não podem ser marcados como `pronto`, mesmo por correção manual. O vínculo confirmado de um documento de apoio pode ser informado por `documento_principal_candidato`; o item principal deve pertencer ao mesmo lote e não pode ser o próprio item.

### 4. Confirmar

```bash
curl -X POST http://127.0.0.1:8000/api/v1/importacoes/UUID/confirmar/ \
  -H "Authorization: Bearer $API_INGESTAO_TOKEN"
```

Somente itens `pronto` são materializados. A confirmação revalida índice, caminho, tamanho, assinatura e SHA-256 do PDF. Itens já confirmados não geram novas versões em uma reexecução. Enquanto houver itens em revisão ou com falha, o lote permanece `inspecionado`.

## Controles

- preservação imutável do ZIP original;
- hash SHA-256 do ZIP e de cada PDF;
- chave de idempotência armazenada somente como hash;
- proteção contra `zip slip`;
- limites de tamanho, quantidade de arquivos, expansão e razão de compactação;
- validação da assinatura `%PDF-` no manifesto e na confirmação;
- preservação de arquivos com caminhos repetidos por índice interno do ZIP;
- detecção de duplicatas por conteúdo;
- diagnóstico preliminar de páginas e necessidade provável de OCR;
- separação entre metadados aceitos e sugestões automatizadas;
- registro explícito de divergências;
- vínculos sugeridos e confirmados mantidos em campos distintos;
- `dry-run` estrutural antes da confirmação;
- estados de revisão humana;
- criação ou reutilização controlada de município, aplicação, documento e versão;
- registro do caminho original nas observações da versão documental.

## Painel

O cartão **Municípios em análise** contabiliza apenas municípios que já possuam ao menos um documento normativo associado. Municípios cadastrados exclusivamente como referência territorial não entram nesse indicador.

## Canário RM Jundiaí

O lote de 35 PDFs da RM Jundiaí é o canário da funcionalidade. Ele não integra o repositório e deve ser executado localmente após a atualização do banco.

Critérios de aceite da versão `0.3.5`:

- 35 PDFs reconhecidos;
- uma duplicata exata identificada;
- nenhum item promovido exclusivamente por número ou ano extraído do texto;
- divergências entre nome e conteúdo preservadas para revisão;
- anexos e fragmentos sem vínculo confirmado automático;
- manutenção dos atos estruturalmente completos, salvo divergência real;
- rotas de texto nativo, OCR, misto e manual registradas no manifesto.

No CI, o contrato é exercitado por testes unitários e ZIPs sintéticos pequenos. O canário real permanece reservado ao teste local de aceitação para evitar exposição ou duplicação do corpus.

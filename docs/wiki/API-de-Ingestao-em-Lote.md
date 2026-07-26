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

A inspeção valida caminhos, limites, assinatura PDF, hashes, duplicatas e candidatos de município, natureza, tipo, número e ano. Nenhum ato é criado nessa etapa.

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

Arquivos sem assinatura PDF válida não podem ser marcados como `pronto`, mesmo por correção manual.

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
- `dry-run` estrutural antes da confirmação;
- estados de revisão humana;
- criação ou reutilização controlada de município, aplicação, documento e versão;
- registro do caminho original nas observações da versão documental.

## Canário RM Jundiaí

O lote de 35 PDFs da RM Jundiaí é o canário da funcionalidade. Ele não integra o repositório e deve ser executado localmente após a atualização do banco. A expectativa é que atos com metadados completos sejam marcados como prontos, enquanto PLHIS, páginas institucionais, Diário Oficial, fragmentos e anexos permaneçam para adjudicação.

No CI, o contrato é exercitado por um ZIP sintético pequeno; o canário real permanece reservado ao teste local de aceitação para evitar exposição ou duplicação do corpus.

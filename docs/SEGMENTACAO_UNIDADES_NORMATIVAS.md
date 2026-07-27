# Segmentação determinística de unidades normativas

## Escopo da versão 0.4.1

A segmentação parte do artefato Markdown vinculado à mesma `VersaoDocumento` e registra um ato principal, artigos, anexos e ocorrências documentais. O artigo é a unidade canônica para as etapas posteriores de alinhamento, recuperação e análise das variáveis do Protocolo HIS.

O procedimento é prioritariamente determinístico. Expressões regulares reconhecem cabeçalhos de artigos, sufixos, anexos e marcadores de página. A rotina não reescreve o texto, não corrige numeração e não usa IA para escolher limites quando a estrutura documental já oferece sinais suficientes.

## Modos de execução

A execução padrão apenas analisa e exibe métricas:

```powershell
python manage.py segmentar_unidades_normativas --versao 10
```

Para guardar também o diagnóstico em arquivo local:

```powershell
python manage.py segmentar_unidades_normativas `
  --versao 10 `
  --saida-json .\data\diagnosticos\versao-10.json
```

A persistência exige confirmação explícita:

```powershell
python manage.py segmentar_unidades_normativas `
  --versao 10 `
  --confirmar
```

Uma entrada já processada com o mesmo hash e a mesma versão do segmentador é reutilizada. `--forcar` cria uma nova execução. Unidades revisadas ou adjudicadas não são substituídas sem `--substituir-revisados`.

## Rastreabilidade

Cada artigo preserva no campo `estrutura`:

- posição inicial e final no Markdown;
- linha inicial e final;
- hash do Markdown de origem;
- indicação de segmentação automática.

Cada anexo preserva os mesmos elementos e o texto extraído em `metadados`. O processamento produz ainda um artefato JSON com todos os segmentos, inclusive ocorrências duplicadas que não podem coexistir como artigos canônicos por causa da restrição de unicidade do domínio.

## Ocorrências

São registradas sem correção silenciosa:

- ausência de artigos reconhecidos;
- numeração duplicada;
- lacuna de sequência;
- ordem regressiva.

Em caso de duplicação, o primeiro artigo é persistido como unidade canônica com status `duplicado`, enquanto todas as ocorrências permanecem integralmente no diagnóstico e nas evidências da `OcorrenciaDocumental`.

## Métricas e gates iniciais

O processamento registra:

- artigos detectados e artigos canônicos;
- anexos detectados;
- ocorrências;
- duplicações e lacunas;
- caracteres totais e não atribuídos;
- cobertura percentual.

Os gates iniciais são cobertura mínima de 98%, no máximo 2% de caracteres não atribuídos e ausência de duplicação não adjudicada. Esses gates são diagnósticos: não eliminam dados nem substituem a validação humana.

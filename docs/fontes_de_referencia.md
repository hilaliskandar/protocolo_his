# Fontes de referência

## Municípios

A identificação oficial dos municípios utiliza a API de Localidades do Instituto Brasileiro de Geografia e Estatística (IBGE). Nome oficial, código IBGE, unidade federativa e código da unidade federativa são carregados de forma idempotente e associados à fotografia preservada da resposta utilizada.

Fonte principal: `https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome`.

## Geometrias municipais

As geometrias GeoJSON são tratadas como enriquecimento espacial de registros municipais previamente identificados pelo código IBGE. O projeto não cria municípios a partir da malha: cada feição deve corresponder a um município já existente na referência oficial.

Fonte complementar: `https://git.c3sl.ufpr.br/simcaq/geodata-br`.

Os arquivos seguem o padrão `geojson/geojs-<codigo_uf>-mun.json`. Cada feição deve apresentar o código IBGE na propriedade `id`, o nome na propriedade `name` e uma geometria GeoJSON válida.

## Espécies normativas

O catálogo inicial de espécies normativas utiliza a Lei Complementar nº 95, de 26 de fevereiro de 1998, em seu texto compilado. A fonte disciplina a elaboração, a redação, a alteração e a consolidação das leis, alcança as espécies referidas no art. 59 da Constituição Federal e, no que couber, decretos e outros atos regulamentares.

Fonte normativa: `https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp95compilado.htm`.

O catálogo inicial não pretende esgotar as espécies existentes em cada município. Tipos próprios de uma jurisdição deverão ser acrescentados com indicação da Lei Orgânica, da norma local de processo legislativo ou de outra fonte competente.

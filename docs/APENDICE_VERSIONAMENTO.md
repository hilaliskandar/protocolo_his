## Apêndice — versionamento do desenvolvimento

**Versão corrente documentada:** `0.4.1`.

A plataforma adota uma convenção de versionamento própria para registrar o avanço do protótipo antes da versão estável `1.0.0`.

### Regra de numeração

- **Implementação inicial:** inicia em `0.0.1`.
- **Incremento de roadmap:** quando uma nova etapa funcional é incorporada, avança-se o componente intermediário: `0.x.0` → `0.(x+1).0`.
- **Ajuste, aperfeiçoamento ou correção:** dentro da etapa corrente, avança-se o último componente: `0.x.y` → `0.x.(y+1)`.
- **Teste de alternativa em branch:** recebe uma letra após a versão de referência, por exemplo `0.4.1a`, `0.4.1b` e `0.4.1c`. A letra identifica uma alternativa experimental e não substitui uma versão integrada à `main`.
- **Integração à `main`:** somente alterações incorporadas à branch principal entram no histórico oficial abaixo.

### Histórico consolidado

| Versão | Natureza | Marco incorporado | Referência |
|---|---|---|---|
| `0.0.1` | implementação inicial | Fundação do MVP: aplicação Django, modelos iniciais, ingestão documental, diagnóstico e conversão básica, interface e estrutura do pipeline. | PR #1 |
| `0.1.0` | incremento de roadmap | Auditoria de corpus, atos, artigos, anexos, ocorrências, adjudicações, releases, CI em PostgreSQL e documentação técnica versionada. | PR #2 |
| `0.2.0` | incremento de roadmap | Observabilidade de IA com controle auditável e opcional de tokens, hashes, encoding e versão do tokenizer. | PR #3 |
| `0.2.1` | correção | Serviço local de arquivos de mídia em desenvolvimento, restrito a `DEBUG=True`. | PR #4 |
| `0.3.0` | incremento de roadmap | Revisão de Markdown por IA local via Ollama, com segmentação, métricas, artefatos derivados, gates conservadores e validação humana. | PR #5 |
| `0.3.1` | aperfeiçoamento | Configuração padrão do Ollama e dos thresholds no ambiente, com sobrescrita opcional pela CLI. | PR #6 |
| `0.3.2` | correção | Exibição de PDFs no leitor interno por `iframe`, mantendo bloqueio contra incorporação por origens externas. | PR #7 |
| `0.3.3` | documentação e governança | Formalização da convenção de versionamento e inclusão deste histórico no README. | atualização do README |
| `0.3.4` | aperfeiçoamento da ingestão | API autenticada para receber ZIPs, inspecionar itens, gerar manifesto provisório, corrigir metadados e confirmar registros do corpus com controles de segurança. | PR #10 |
| `0.3.5` | aperfeiçoamento metodológico da ingestão | Diagnóstico preliminar de PDFs, separação entre sugestões textuais e metadados aceitos, registro de divergências, vínculos sugeridos de documentos de apoio, testes de regressão e painel restrito aos municípios com legislação em análise. | PR #11 |
| `0.3.6` | correção e portabilidade | Execução integral dos testes no PostgreSQL canônico, correções de handles de arquivo e compatibilidade com Windows. | PR #12 |
| `0.3.7` | correção de consistência documental | O leitor seleciona explicitamente a versão documental e carrega PDF e Markdown provenientes da mesma versão. | PR #13 |
| `0.4.0` | incremento de roadmap | Classificação auditável da natureza das versões documentais e registro de sucessão, equivalência e derivação, com validação humana e exposição no manifesto. | PR #16 |
| `0.4.1` | aperfeiçoamento metodológico | Segmentação determinística e idempotente de artigos e anexos, registro de posições, métricas, gates e ocorrências sem correção silenciosa da fonte. | PR em revisão |

### Delimitação metodológica da versão 0.4.1

A segmentação usa o Markdown correspondente à própria versão documental. O artigo é a unidade canônica e preserva texto, hash, páginas, linhas e posições no documento. Anexos são identificados separadamente, e lacunas, ordens regressivas e duplicações produzem ocorrências auditáveis.

Uma execução sem `--confirmar` não modifica o banco. Processamentos concluídos com o mesmo artefato, hash e versão do segmentador são reutilizados. A reexecução forçada não substitui artigos revisados ou adjudicados sem autorização explícita.

A versão não usa IA para decidir limites de artigos, não escolhe automaticamente uma versão canônica e não elimina duplicações da fonte. Quando a restrição de unicidade impede persistir dois artigos com a mesma numeração, todas as ocorrências continuam preservadas no diagnóstico JSON e nas evidências da ocorrência documental.

### Uso em branches experimentais

Uma alternativa ainda não incorporada deve partir da versão vigente e receber uma letra, sem alterar o histórico oficial. Exemplos:

```text
0.4.1a  alternativa A para alinhamento de artigos
0.4.1b  alternativa B para o mesmo ensaio
0.4.1c  terceira alternativa comparável
```

Os próximos aperfeiçoamentos da série `0.4.x` devem usar os artigos segmentados como base para alinhamento entre versões, comparação assistida e adjudicação humana.

### Princípio de rastreabilidade

Cada versão oficial deve ser associada, sempre que possível, ao PR, commit de integração, testes executados, documentação atualizada e eventuais migrações de banco. O número da versão descreve a evolução funcional do protótipo; não substitui hashes, tags Git ou releases, que continuam sendo as referências técnicas imutáveis.

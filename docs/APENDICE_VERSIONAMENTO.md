## Apêndice — versionamento do desenvolvimento

**Versão corrente documentada:** `0.3.7`.

A plataforma adota uma convenção de versionamento própria para registrar o avanço do protótipo antes da versão estável `1.0.0`.

### Regra de numeração

- **Implementação inicial:** inicia em `0.0.1`.
- **Incremento de roadmap:** quando uma nova etapa funcional é incorporada, avança-se o componente intermediário: `0.x.0` → `0.(x+1).0`.
- **Ajuste, aperfeiçoamento ou correção:** dentro da etapa corrente, avança-se o último componente: `0.x.y` → `0.x.(y+1)`.
- **Teste de alternativa em branch:** recebe uma letra após a versão de referência, por exemplo `0.3.7a`, `0.3.7b` e `0.3.7c`. A letra identifica uma alternativa experimental e não substitui uma versão integrada à `main`.
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
| `0.3.7` | correção de consistência documental | O leitor passa a selecionar explicitamente a versão documental e a carregar PDF e Markdown provenientes da mesma versão, impedindo combinações cruzadas de artefatos. | PR em revisão |

### Delimitação metodológica da versão 0.3.7

A seleção de uma versão no leitor controla conjuntamente o PDF original e o Markdown convertido. O comportamento padrão continua a abrir a versão documental mais recente, mas versões anteriores podem ser consultadas explicitamente sem que o sistema misture seus artefatos com processamentos posteriores.

A correção não classifica relações jurídicas entre versões, não escolhe versão canônica para o corpus e não altera a detecção de duplicatas por SHA-256. Esses incrementos pertencem à etapa seguinte do roadmap.

### Uso em branches experimentais

Uma alternativa ainda não incorporada deve partir da versão vigente e receber uma letra, sem alterar o histórico oficial. Exemplos:

```text
0.3.7a  alternativa A para classificação documental
0.3.7b  alternativa B para o mesmo ensaio
0.3.7c  terceira alternativa comparável
```

Com a recepção e a qualificação documental estabilizadas, a passagem para `0.4.0` fica reservada à modelagem de versões normativas sucessivas, comparação entre versões e adjudicação das diferenças.

### Princípio de rastreabilidade

Cada versão oficial deve ser associada, sempre que possível, ao PR, commit de integração, testes executados, documentação atualizada e eventuais migrações de banco. O número da versão descreve a evolução funcional do protótipo; não substitui hashes, tags Git ou releases, que continuam sendo as referências técnicas imutáveis.

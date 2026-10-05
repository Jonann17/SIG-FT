---
tags: [gerenciamento, core]
---

# Mapeamento das Listas de Sobressalentes

Arquivo: `Box/15 - PDM/SOBRESSALENTES - PMIB/Mapeamento Listas de Sobressalentes.xlsx`

## O que e

A **visão macro**. Enquanto o [[Planilha STATUS_PMIB]] rastreia **item a item dentro de
uma lista**, a mapeadora rastreia **lista a lista dentro do projeto**.

Duas funções:
1. **Descobrir listas novas** — varre a arvore de pastas procurando `*_STATUS_PMIB.xlsx`
   e confronta com o que já esta mapeado.
2. **Agregar** — lê cada `_STATUS_PMIB` e consolida os indicadores por lista.

Alimentada pelo módulo **Gestão PMIB** do SIG-FT.

## As abas

### `Acompanhamento Sobressalente` — a principal
**94 listas x 35 colunas** (95 em 01/10/2026), organizadas em três blocos:

#### Bloco GERAL — identidade e responsabilidade
| Coluna | Conteudo |
|---|---|
| `N° DOCUMENTO ITAIPU` | código RDS-PP da lista |
| `N° DOCUMENTO CMI` | código CMI |
| `ULTIMA REVISAO EMITIDA` | 0, 0A, 0C, 1, 1A... |
| `STATUS DA REVISAO` | Aprovado / Aprovado com Comentários / Para Assinatura / Em Processo |
| `DATA DE ATUALIZACAO` | |
| `STATUS REAL` | APROVADO / NÃO APROVADO / NÃO EMITIDO / EM PROCESSO |
| `REVISAO EM USO` | qual revisão o `_STATUS_PMIB` reflete — **vem da linha de revisão do próprio `_STATUS_PMIB`** (desde 05/10/2026; o Gestão PMIB copia — T3). Para mudar, atualize a linha no arquivo. Vermelho quando ≠ ÚLTIMA REVISÃO EMITIDA |
| `DESCRICAO` | título do documento |
| `ESPECIFICACAO TECNICA` · `CAPITULO` | ver [[Estrutura ET, Capitulo e Sistema]] |
| `RESPONSAVEL` · `PROCUREMENT` · `ELABORADOR DO DOCUMENTO` | pessoas |
| `ORIGEM FORNECEDOR` | NACIONAL / INTERNACIONAL |
| `ENTREGA` | data ou estado |
| `OBSERVACAO` | texto livre |

#### Bloco FINANCEIRO
| `EVENTOS DE PAGAMENTOS RELACIONADOS` | ex.: `2835 / 2835 a / 2836` |

Esta e a coluna que amarra a lista ao **evento de pagamento** do contrato. E o motivo
pelo qual atraso de ficha vira atraso de dinheiro.

#### Bloco PMIB — os indicadores
| Coluna | O que conta |
|---|---|
| `SITUACAO NO PMIB` | estado consolidado (cascata) da lista |
| `FICHAS EXISTENTES` | total de fichas criadas |
| `FICHAS COM O FORNECEDOR` | aguardando o fornecedor |
| `FICHAS RECEBIDAS` | fornecedor devolveu |
| `FICHAS EM ELABORACAO` | sendo preenchidas |
| `INFO. DO FORNECEDOR COMPLETO` | seções do fornecedor fechadas |
| `VALORIZACAO` | ver [[Secao - Valorizacao]] |
| `FICHAS COM APLICACAO - LMR FINALIZADA` | ver [[Secao - Aplicacao LMR]] |
| `FICHAS EM ANALISE DE ITAIPU` | emitidas, aguardando |
| `FICHAS EM CORRECAO` | devolvidas por Itaipu |
| `FICHAS APROVADAS` | fechadas |
| `FICHAS DE ENTREGA FÍSICA` *(nova, 05/10/2026)* | fichas com TIPO DE ENTREGA = FÍSICA E DOCUMENTAL — **as únicas que precisam de autorização de Itaipu** |
| `APTO PARA ENTREGA` | fichas com SITUAÇÃO DA AUTORIZAÇÃO = AUTORIZADO **e ainda não entregues** (sem DOCUMENTAL/TÍTULO). Nome mantido: o `.pbix` atual usa |
| `AGUARDANDO AUTORIZAÇÃO ITAIPU` *(nova)* | fichas físicas com e-mail de intenção, dentro do prazo de 15 dias úteis |
| `ATRASO DE AUTORIZACAO DE ENTREGA ITAIPU` | **fichas** físicas (PMIB distinto, sem DUPLICADO) além dos **15 dias úteis** do e-mail, sem autorização (SITUAÇÃO = ATRASADO ITAIPU). Até 04/10 o SIG-FT contava 14 dias corridos e todos os tipos |
| `MAIOR ATRASO ITAIPU (DIAS)` *(nova)* | maior DIAS DE ATRASO (dias corridos além do prazo) entre as atrasadas da lista |

> [!warning] Decisão do Luan (05/10/2026, tarde): a mapeadora vira **CADASTRO**
> As contagens (`FICHAS EXISTENTES` … `ÍNDICE DE CONCLUSÃO`, inclusive as três colunas abaixo) saem da
> mapeadora assim que o **Power BI v2** estiver montado — ele conta item a item nos `_STATUS_PMIB`. Ficam o
> cadastro, `SITUAÇÃO NO PMIB`, `LINK DA PLANILHA` e `CÓDIGO DO PROJETO PARA O PMIB`. A tabela abaixo descreve o
> estado intermediário.

> [!info] Mapeadora no tratamento v2 (05/10/2026)
> As três colunas novas foram **inseridas** (o resto andou para a direita, nada mudou de nome) e os
> números de APTO/ATRASO recalculados pela regra nova. Clicar no cabeçalho mostra a definição.
> Quem mantém daqui para a frente é o Gestão PMIB do SIG-FT — ver
> [[Tarefa SIG-FT - Calculo e Gravacao sem Perda]]. Script: `_gestao_v2/atualizar_mapeadora_v2.py`.

### `Dropbox` — a lista de validação de `SITUACAO NO PMIB`
```
INICIAR
PRE-CADASTRO EM PROCESSO
PRE-CADASTRO COMPLETO
PARCIALMENTE EM ANALISE IB / PARCIALMENTE EM ...
EM ANALISE IB
FASE DE CORRECAO
APROVADO
```

> [!note] Os valores reais divergem do dropdown
> Na coluna `SITUACAO NO PMIB` aparecem também `FICHAS CRIADAS`, `FICHAS COM O
> FORNECEDOR`, `FORNECEDOR / ELABORAÇÃO`, `EM PROCESSO DE PREENCHIMENTO`,
> `EM PROCESSO / ANALISE ITAIPU`, `CORRECAO / ELABORACAO`, `FINALIZADO`, `SEM LISTA`.
> O vocabulario da coluna cresceu além da lista de validação. Ver
> [[Diagnostico - Deficiencias]].

### `Lista de preços Follow-up` (desde set/2026)
Uma linha por lista de preços no Aconex: documento, revisão, status, data, ET, e a **lista
de sobressalentes** a que se refere, com alerta quando o RDS-PP da lista mudou. Em
01/10/2026 tinha 16 linhas, todas no código antigo `PB020-0x`. Ver [[Lista de Precos]].

### `Atividades` (substituiu `Atividades Pendentes`)
O plano de ação: nível 1 = frente (uma lista), nível 2 = atividade, com datas previstas e
reais, status (Não iniciada / Em desenvolvimento / Travada / Concluída), com quem está e
criticidade. Ver [[Aba de Atividades e Cronograma]].

## O outro artefato de visão macro
`Sobressalentes - Dashboard.pbix` — Power BI na mesma pasta. **Inspecionado em 30/09/2026:**
lê **só a aba principal** desta planilha (uma consulta, 4 medidas de soma, sem
relacionamentos), por um caminho fixo de uma máquina (`C:\Users\560083605\Box\...`). Duas
páginas, a segunda cópia da primeira com um gráfico de "listas com preço" apontando para a
coluna errada. Logo: o painel herda o atraso da mapeadora e não enxerga item, prazo,
procurement nem tipo de entrega. A proposta de substituição está em
[[Plano - Sistema de Gestao v2]].

## Relacionados
[[Planilha STATUS_PMIB]] · [[Indicadores e Como Ler]] · [[Panorama Quantitativo]] · [[SIG-FT - Modulos]]

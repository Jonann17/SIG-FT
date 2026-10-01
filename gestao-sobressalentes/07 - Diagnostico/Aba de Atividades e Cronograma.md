---
tags: [gerenciamento, mapeadora, atividades, cronograma]
status: em-uso
criado: 2026-08-31
atualizado: 2026-09-02
---

# Aba de Atividades e Cronograma

> [!warning] Documento de trabalho, nao conhecimento permanente
> Contem numeros e situacoes de uma data especifica. O que descreve **como o processo
> funciona** mora no nucleo do cofre (`01` a `06`).


> [!success] Construída e em uso
> A aba existe em
> `SOBRESSALENTES - PMIB/Mapeamento Listas de Sobressalentes - COM ABA ATIVIDADES.xlsx`.
> A mapeadora original não foi tocada. **55 atividades em 17 sistemas, todas com prazo.**

---

## Para que serve — e para que não serve

**Serve** para nomear as atividades a fazer, por sistema, e acompanhar o andamento de cada
uma.

> [!warning] Não resolve o gargalo de tempo
> A ausência de dimensão temporal no gerenciamento é um problema estrutural, que exige
> mudanças no [[Planilha STATUS_PMIB|_STATUS_PMIB]], na organização das pastas e na
> própria mapeadora. Discussão de estratégia à parte — ver [[Plano - Dimensao de Tempo]].
>
> Sobrecarregar uma aba simples com essa responsabilidade seria estragar as duas coisas.

---

## A estrutura

Dois níveis no agrupamento do Excel, três na coluna `NV`.

| `NV` | O que é | Agrupamento |
|---|---|---|
| **1** | o sistema — código Itaipu, descrição da lista, agregado das filhas | nível 0 |
| **2** | a atividade | nível 1 |
| **3** | subitem da atividade acima | nível 1 também |

O nível 3 é marcado na coluna, mas **não cria um terceiro nível de recolhimento** —
decisão consciente, para não complicar um acompanhamento que é simples.

`ATIVIDADES GERAIS` fecha a planilha: atividades que não pertencem a nenhum sistema, com o
título no lugar do código do documento.

### As 16 colunas

`NV` · `CÓDIGO ITAIPU` · `DESCRIÇÃO` · `ATIVIDADES` · `CONCLUÍDAS` · `TRAVADAS` ·
`DATA PREVISTA DE INÍCIO` · `DATA DE INÍCIO` · `PREVISÃO DE TÉRMINO` · `DATA DE TÉRMINO` ·
`STATUS` · `ALTERAÇÃO DO STATUS` · `COM QUEM ESTÁ` · `DETALHE` · `CRITICIDADE` ·
`CONCLUÍDA`

As datas vêm em dois pares — previsto e real, de início e de término. `ALTERAÇÃO DO STATUS`
guarda quando o status mudou pela última vez, e é dela que sai o *há quantos dias está
parado*.

> [!note] `COM QUEM ESTÁ` serve a dois estados
> Guarda **quem está tocando** quando a atividade está em desenvolvimento, e **com quem
> parou** quando está travada. É a mesma pergunta: *de quem depende agora*.
>
> `RESPONSÁVEL` seria enganoso — sugere dono permanente, e a mapeadora já tem uma coluna
> com esse nome, desatualizada.

### Criticidade — escala 1 a 5, nos dois níveis

Mesma escala para o sistema (linha de nível 1) e para a atividade, medindo coisas
diferentes: no sistema é a prioridade dele no plano; na atividade, a urgência daquela ação.
Escala de cor condicional na coluna, do azul (1) ao vermelho (5).

---

## As fórmulas

### Agregados na linha do sistema
`COUNTIFS` sobre `NV = 2`, contando só as filhas diretas — subitens de nível 3 não inflam
a contagem. Com os grupos recolhidos, a linha do sistema vira painel.

### Rollup de datas
Toda linha que tenha filhas herda o intervalo delas: `MIN` nas datas de início, `MAX` nas
de término. Vale também para uma atividade de nível 2 que tenha subitens de nível 3 — e é
isso que faz a estrutura escalar sem mudar nada.

### `DATA DE TÉRMINO` do pai — regra própria

> [!important] Só mostra data quando **todas** as filhas estiverem concluídas
> ```
> =SE(nº de filhas = 0; "";
>    SE(nº de filhas = nº de concluídas; MÁXIMO(datas de término); ""))
> ```
> Um `MÁXIMO` simples mostraria data assim que a primeira filha terminasse, o que faria a
> linha do sistema parecer fechada com trabalho em aberto. A conta usa a caixa
> `CONCLUÍDA`, que é o que o módulo Gestão PMIB vai preencher.

---

## Armadilhas do Excel descobertas ao montar

> [!danger] Custaram tempo e vão voltar a custar se forem esquecidas
> **Booleano vira fórmula.** Ao salvar, o Excel converte células booleanas em `=FALSE()`.
> Fórmula não aceita caixa de seleção e atrapalha a leitura por `openpyxl`.
>
> **Caixa de Controle de Formulário não guarda valor na célula.** É objeto flutuante: o
> `openpyxl` não lê e ela se desloca quando linhas são inseridas. Usar a **caixa nativa do
> Excel 365**, que grava `TRUE`/`FALSE` na célula.
>
> **`summaryBelow` é invertido pelo Excel.** Ao salvar, volta para `True`, o que desalinha
> o controle `+/−` das linhas de sistema. Precisa ser `False`.
>
> **`insert_cols` do openpyxl cria coluna sem estilo.** A coluna nova nasce sem
> preenchimento; nas linhas de sistema aparece como faixa branca cortando o cinza. É
> preciso copiar o estilo da linha.
>
> **Intervalo de `CONT.SES` não se estende sozinho.** Inserir linha dentro de um bloco não
> amplia o intervalo escrito à mão: três sistemas ficaram contando parte das filhas —
> RV Hidráulica 3 de 5, Água Pura 2 de 3, Painéis 1 de 4.
>
> **Acento importa para filtro.** `STATUS` tem de bater exatamente com a lista da aba
> `Dropbox`. 36 linhas com `Nao iniciada` sem acento ficaram órfãs de qualquer filtro.

---

## O cronograma

Gerado da aba por `_scripts/gera_cronograma.py`, que produz um Gantt em SVG numa página
HTML.

| Elemento | Significado |
|---|---|
| barra clara | previsto — `DATA PREVISTA DE INÍCIO` a `PREVISÃO DE TÉRMINO` |
| barra escura por dentro | realizado — `DATA DE INÍCIO` até o término, ou até hoje |
| barra fina com marcadores | linha de sistema, abrangendo as filhas |
| cor | o `STATUS` |
| linha tracejada | hoje |
| rótulo à direita da barra | duração e, nas travadas, há quantos dias está parada |

O script **recalcula os rollups em Python** em vez de ler o valor em cache das fórmulas —
assim funciona mesmo com a planilha editada por fora e não aberta no Excel.

Escala adaptativa: semanas quando o plano cabe em 45 dias, meses acima disso. Atividades
sem data caem numa faixa própria, para que a ausência apareça em vez de sumir.

> [!tip] O ganho de arquitetura
> A estrutura da aba **já é a de um Gantt** — o rollup do pai é exatamente a barra de
> resumo. Isso não foi coincidência de desenho, mas vale registrar: qualquer relatório
> gerado dessa aba herda a hierarquia de graça.

---

## O que fica para a automação

Registrado como pendência no repositório do SIG-FT
(`docs/refatoracao/PENDENCIAS.md`, mesclado em 02/09/2026):

1. o módulo **Gestão PMIB** ler e atualizar a aba;
2. **gerar o relatório do plano** a partir dela — hoje relatório e planilha são mantidos à
   mão e divergem;
3. desenhar o **cronograma na Home** do app.

Ideias levantadas e não implementadas: aba `Pessoas` (nome → e-mail → empresa) para
resolver destinatário e gerar a seção de pendências de Itaipu por filtro; aba `Histórico`
de mudança de status; lembretes via Outlook COM gerando **rascunho, não envio**; painel na
abertura do app.

> [!note] Identificador e dependência ficaram de fora
> Chegaram a existir colunas `ID` (no formato KKS completo + código de sobressalentes +
> sequencial do documento CMI, ex. `MEU04-PB01-03`) e `DEPENDE DE`. Foram removidas por
> decisão de manter o acompanhamento simples. Elas só seriam necessárias para setas entre
> barras e caminho crítico — o cronograma em si não precisa delas.

## Relacionados
[[Plano de Acao - ESTRUTURA]] · [[Mapeamento das Listas de Sobressalentes]] ·
[[Plano - Dimensao de Tempo]] · [[Plano - Aba de Listas de Precos]] · [[SIG-FT - Modulos]]

---
tags: [processo, lista-de-precos, ficha-tecnica, conceito-chave]
status: verificado-em-campo
criado: 2026-08-31
---

# Entrega Documental e Explosão de Itens

> [!important] Conceito estruturante
> Um item **complexo** entregue a Itaipu — composto de vários componentes — **deve ser
> explodido** em fichas dos seus componentes, **mesmo que no sistema da GE só exista o
> equipamento inteiro**.

## A lógica de Itaipu

Se um componente estragar, Itaipu quer **trocar só o componente**, não o equipamento
inteiro. Para isso ela precisa que o componente tenha:
- **ficha técnica própria** no PMIB;
- **código PMIB próprio**;
- part number do fabricante, para conseguir comprar a peça.

Sem a explosão, um monitor de contaminacao inteiro seria descartado porque um plug
conector de US$ 20 falhou.

## Como isso aparece na prática

Verificado na lista de preços **`#ST00=M00MEU10&MPB020-01`** (Regulação de Velocidade,
parte hidráulica) — 168 linhas, **143 fichas**. Reemitida em set/2026 com o código novo,
**`#ST00=M00MEU10&MPB021`** (176 linhas, 144 fichas) — ver [[Lista de Precos]].

### Pai e filho

| Tipo de linha | `ITEM` | `TIPO DE ENTREGA` | `CODIGO GE` | `VALOR UNITARIO` | `CODIGO PMIB` |
|---|---|---|---|---|---|
| **Pai** (equipamento) | `11` | `FISICA E DOCUMENTAL` | **preenchido** | **preenchido** | próprio |
| **Filho** (componente) | `11.1`, `11.2`... | `DOCUMENTAL` | **vazio** | **vazio** | próprio |

### Exemplo real

```
11     MONITOR DE CONTAMINACAO E AGUA   HYDAC   COD GE: 08934100MEU51-135F
       PMIB 4500063671.0781   US$ 8.768,08   FISICA E DOCUMENTAL
  11.1   CORPO BASICO HBR9730 BLOCO FMM   HYDAC   (sem cod GE)
         PMIB 4500063671.1071   (sem valor)   DOCUMENTAL
  11.2   CS1320-A-0-0-0-1/-000            HYDAC   (sem cod GE)
         PMIB 4500063671.1169   (sem valor)   DOCUMENTAL
  ...ate 11.16
```

Um único item pai gerou **16 fichas filhas**.

### Dois tipos de linha sem item próprio — não confundir

| | `TIPO DE ENTREGA` | Código GE | PMIB | O que e |
|---|---|---|---|---|
| **Cabeçalho de categoria** | *(vazio)* | não | não | agrupamento visual: `INSTRUMENTACAO`, `EQUIPAMENTOS`, `VALVULAS E BLOCOS`, `ELEMENTOS FILTRANTES E VEDACOES` |
| **Linha de conjunto** | **`TITULO`** | **sim — as vezes dois** | `N/A` | a engenharia criou como **conjunto**, mas ha **rastreabilidade interna** dos itens que o compoem; esses itens podem, por sua vez, ser equipamentos explodiveis |

Exemplo de linha de conjunto nesta lista: itens **4, 5, 6 e 7** —
`CONJUNTO MOTOBOMBA REGULACAO, 3 FUSOS` e `CONJUNTO MOTOBOMBA INFILTRACAO, ENGRENAGEM` —
cada um com **dois códigos GE** e PMIB `N/A`.

---

## A regra que identifica o tipo de entrega

> [!success] Invariante verificada — zero exceções nos 160 itens com ficha
> **`CODIGO GE` preenchido ⟺ `FISICA E DOCUMENTAL`**
> **`CODIGO GE` vazio ⟺ `DOCUMENTAL`**
>
> Conferido nos dois sentidos na lista `#ST00=M00MEU10&MPB020-01`:
> nenhum item `DOCUMENTAL` com código GE, nenhum item físico sem código GE.

**Por que a regra funciona**: o `CODIGO GE` existe quando o item foi **comprado
separadamente** e portanto tem rastreabilidade no sistema da GE. O componente explodido
não foi comprado separado — veio dentro do equipamento — logo **não existe no rastreio
da GE**, e por isso não tem código GE nem preço unitario próprio.

Isso da um **teste de consistencia automatizável** para a lista de preços: qualquer
linha que viole a equivalencia e erro de preenchimento.

---

## Composição da lista de exemplo

| | Quantidade |
|---|---:|
| Linhas na lista de preços | 168 |
| — `FISICA E DOCUMENTAL` | 89 |
| — `DOCUMENTAL` | 71 |
| — linhas de conjunto (`TITULO`) | 4 |
| — cabeçalhos de categoria | 4 |
| **FICHAS — códigos PMIB distintos** | **143** |

> [!danger] Contar linha não e contar ficha
> **O mesmo código PMIB pode aparecer em mais de uma linha da lista** — quando o mesmo
> componente e usado em conjuntos diferentes. Nesta lista, **19 códigos se repetem**.
> 168 linhas correspondem a **143 fichas**.
>
> Contar linhas superestima o trabalho em ~17% nesta lista, e em até **72%** em outras
> (o Selo do Eixo tem 36 linhas e apenas **10** fichas). **A unidade e sempre o código
> PMIB distinto.**

> [!warning] O impacto no dimensionamento de trabalho
> Boa parte das fichas desta lista são **componentes explodidos**. Estimativa feita sobre
> "número de equipamentos" subdimensiona a realidade.
>
> Mas o erro oposto também existe: estimar por **linha** superestima. O certo e contar
> **códigos PMIB distintos** no `_STATUS_PMIB` — 143 nesta lista, nem 67 (equipamentos)
> nem 168 (linhas).

---

## A quantidade dos componentes

> [!important] A quantidade é o **valor final**, não a receita do conjunto
> A pergunta que a coluna responde é: **quantas peças são necessárias para compor a
> quantidade de conjuntos da lista?**
>
> Não é quantas peças cabem em *um* conjunto.

### O exemplo

Um conjunto composto por **1 item X** e **2 itens Y**. Na lista há **2 conjuntos**:

| Item | Por conjunto | Conjuntos | **Quantidade na lista** |
|---|---:|---:|---:|
| X | 1 | 2 | **2** |
| Y | 2 | 2 | **4** |

### Como era antes

A quantidade registrava a **composição unitária** — `1` para o X e `2` para o Y —
independentemente de quantos conjuntos a lista pedia. A multiplicação ficava implícita,
para quem lesse fazer de cabeça.

> [!warning] Mudou a pedido de Itaipu
> A leitura de Itaipu é de **almoxarifado**, não de engenharia: a quantidade tem de dizer
> quantas peças existem para receber, guardar e repor. A composição unitária obriga quem
> confere a saber o número de conjuntos e multiplicar — e é aí que entra erro de contagem
> no recebimento.

### Consequência prática

**Lista emitida sob a regra antiga não é comparável com lista sob a nova.** Ao revisar uma
lista que ainda traga composição unitária, as quantidades dos componentes precisam ser
recalculadas — e a diferença não é erro de digitação, é troca de critério.

Vale para os dois lados da explosão:

- **itens já explodidos** nas listas existentes, quando forem revisados;
- **fichas novas criadas por explosão** — o caso das Bombas de Extrema Emergência e da
  Sala Segura, onde Itaipu abriu a caixa e pediu o desdobramento. A quantidade de cada
  componente novo já nasce multiplicada pela quantidade de equipamentos entregues.

> [!note] A quantidade do conjunto não muda
> A linha de conjunto continua com a quantidade de conjuntos. O que mudou é só a leitura
> das linhas filhas.

### Onde a regra vale

Em **todo documento que carregue a quantidade do item**, não só na lista de preços:

| Documento | Coluna |
|---|---|
| [[Lista de Sobressalentes]] | quantidade do item |
| [[Lista de Precos]] | quantidade do item |
| **[[Planilha STATUS_PMIB\|_STATUS_PMIB]]** | `QTD.` |

O `_STATUS_PMIB` é uma **cópia da lista** com colunas de gestão acrescentadas — ele herda a
coluna de quantidade e, com ela, a regra.

> [!warning] Isso entra na reconciliação de revisão
> Quando uma lista é revisada, alinhar o `_STATUS_PMIB` deixou de ser só conferir itens que
> entraram e saíram: **as quantidades dos componentes explodidos também podem mudar sem que
> nenhum item tenha mudado**, se a revisão trouxer a lista para o critério novo.
>
> Quem carimba a `REVISÃO EM USO` precisa ter conferido as duas coisas. Ver
> [[Plano - Revisao em Uso automatica]].


## Consequências para o processo

### Para a Aplicação LMR
Cada componente explodido **precisa da sua própria Aplicação LMR** — e a localização
dele e a mesma do equipamento pai. isso é uma oportunidade: a LMR do filho e **derivavel
da LMR do pai**. Um item pai com 16 filhos gera 17 aplicações que compartilham a mesma
localização física. Ver [[Plano de Acao - Aplicacao LMR]].

### Para a entrega física
O componente `DOCUMENTAL` **não e entregue** — ele já esta dentro do equipamento pai,
que e entregue fisicamente. Não ha etiqueta MTA própria nem conferencia física separada.
A entrega dele e **só a ficha**.

### Para a valorização
O componente **não tem valor unitario próprio**: o preço está no pai. A
[[Secao - Valorizacao|valorização]] de uma ficha `DOCUMENTAL` e um caso a parte — e
provavelmente uma das razões pelas quais a valorização anda mais devagar que as demais
seções.

### Para o rastreio da GE
> [!note] O descasamento de fronteira
> No **MTA e no rastreio da GE**, o item explodido **não existe**. No **PMIB**, ele
> existe e tem ficha. São dois universos com granularidades diferentes, e a lista de
> preços e o único documento onde os dois se encontram — por isso ela carrega tanto o
> `CODIGO GE` quanto o `CODIGO PMIB` na mesma linha.

---

## Relacionados
[[Lista de Precos]] · [[Planilha STATUS_PMIB]] · [[Secao - Valorizacao]] ·
[[Secao - Aplicacao LMR]] · [[MTA, Etiquetas e Entrega no Almoxarifado]] ·
[[Plano - Aba de Listas de Precos]]

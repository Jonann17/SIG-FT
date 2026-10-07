---
tags: [plano, gerenciamento, indicadores]
status: proposta
criado: 2026-08-31
---

# Plano — A Dimensão de Tempo no Gerenciamento

> [!warning] Documento de trabalho, nao conhecimento permanente
> Contem numeros e situacoes de uma data especifica. O que descreve **como o processo
> funciona** mora no nucleo do cofre (`01` a `06`).


## O diagnostico em uma frase

> As 35 colunas da mapeadora são **contagem ou estado**. Nenhuma e tempo de trabalho.
> Por isso é impossível saber se uma ficha esta `EM ELABORACAO` ha três dias ou ha oito
> meses — as duas aparecem identicas.

Consequências praticas:
- **não da para prever entrega** — só descrever o presente;
- **não da para defender prazo com Itaipu** — só reagir quando cobram;
- **não da para saber se uma lista esta andando ou parada**;
- o campo `ENTREGA` virou campo-lembrete (`Atualizar data`, `Informar data`) porque a
  planilha não tinha onde guardar tempo, e o tempo vazou para um campo de texto.

---

## A descoberta que muda o custo da solução

> [!success] O relogio já existe. Ninguém lê.
> A coluna **`DATA DO EMAIL COMUNICANDO ENTREGA`** do [[Planilha STATUS_PMIB]] esta
> **preenchida, como data de verdade** (`datetime`, não texto), em **511 itens
> distribuidos por 44 arquivos**.
>
> E dela que parte o compromisso de **2 a 3 meses** do CMI para subir a
> [[Secao - Aplicacao LMR|Aplicação LMR]] e reenviar para avaliacao.

Ou seja: **não e preciso começar a coletar dado nenhum para ter a primeira métrica de
tempo do projeto.** Basta calcular a partir do que já esta gravado.

### O que o cálculo revelou (31/08/2026)

| Faixa desde o e-mail de intenção | Itens sem LMR concluída |
|---|---:|
| dentro do prazo (até 60 d) | 2 |
| janela 60-90 d (limite dos 3 meses) | 2 |
| **estourado 90-180 d** | **95** |
| **estourado 180-365 d** | **286** |
| **estourado há mais de 1 ano** | **33** |
| **TOTAL ESTOURADO** | **414** |

O item mais antigo tem **441 dias**, no Selo do Eixo da Turbina.

> [!warning] Números já corrigidos de um erro de conversão
> Os 56 itens de Inversores e PDE estavam gravados com `12/03/2025` por **erro de
> conversão de data do Excel**; a data correta e **03/12/2025**. Isso move os 56 da faixa
> "mais de 1 ano" para "180-365 d" — de 89 para 33 na primeira, de 230 para 286 na
> segunda. O total estourado não muda.
>
> **O `_STATUS_PMIB` ainda tem a data errada.** Corrigir antes de rodar o script de novo.
> Ver [[Plano de Acao - Aplicacao LMR]], seção 8.2.

Duas leituras independentes convergem: o agregado da mapeadora aponta **413 fichas** de
passivo, e a contagem item a item nos `_STATUS_PMIB` aponta **418**. A diferença e ruido
de arredondamento entre métodos; a ordem de grandeza esta confirmada por dois caminhos.

---

## A proposta — três camadas, da mais barata para a mais cara

### Camada 1 — calcular o que já existe (esforço: horas)

Nenhuma coluna nova, nenhum dado novo. Derivar de
`DATA DO EMAIL COMUNICANDO ENTREGA`:

| Coluna derivada | Onde | Fórmula |
|---|---|---|
| `DIAS DESDE A INTENCAO` | `_STATUS_PMIB`, por item | `hoje − data do e-mail` |
| `PRAZO LMR (D+90)` | `_STATUS_PMIB`, por item | `data do e-mail + 90 dias` |
| `SITUACAO DO PRAZO` | `_STATUS_PMIB`, por item | `NO PRAZO` / `ATENCAO (60-90 d)` / `ESTOURADO` |
| `ITENS COM PRAZO LMR ESTOURADO` | mapeadora, por lista | contagem |
| `MAIOR ATRASO (DIAS)` | mapeadora, por lista | máximo |

Implementação: o módulo **Gestão PMIB** já lê todos os `_STATUS_PMIB` e escreve na
mapeadora. São duas colunas novas na agregação que ele já faz.

> [!tip] Por que começar por aqui
> Entrega a métrica **mais urgente do projeto** sem pedir a ninguém que mude habito.
> E o único número que permite chegar em Itaipu com um plano em vez de uma desculpa.

---

### Camada 2 — carimbar as transições (esforço: baixo, mas muda habito)

O problema de fundo contínua: sabe-se quando o item foi **emitido**, mas não quando ele
**entrou no estado atual**. Duas colunas resolvem — e apenas duas, porque uma coluna de
data por etapa seria abandonada na primeira semana:

| Coluna nova em `_STATUS_PMIB` | Preenchida por |
|---|---|
| `DATA DE CRIACAO DA FICHA` | **SIG-FT**, no módulo Criar Fichas, junto com o `CODIGO PMIB` |
| `DATA DA ULTIMA MUDANCA DE STATUS` | **SIG-FT**, sempre que qualquer módulo grava `COMPLETO` numa seção ou altera `STATUS` |

**As duas são escritas por automação, não por pessoa.** Esse e o ponto todo: os módulos
Criar Fichas, Upload Condições, Upload Specs, Cadastro LMR e Ficha Duplicada **já
escrevem** nessas planilhas. Carimbar a data no mesmo movimento e barato e não depende
de disciplina de ninguém.

Delas saem os indicadores que hoje não existem:

| Indicador | Fórmula | Responde |
|---|---|---|
| **Idade da ficha** | `hoje − criacao` | ha quanto tempo esse item existe sem fechar |
| **Tempo no estado atual** (*aging*) | `hoje − ultima mudanca` | esta andando ou parado |
| **Fichas paradas há mais de 30 dias** | contagem | onde intervir hoje |
| **Tempo de ciclo** | `aprovacao − criacao` | quanto realmente demora, para prometer prazo com base em histórico |

> [!important] O indicador que mais muda a conversa e o *aging*
> "180 fichas em elaboração" não diz nada. "180 fichas em elaboração, **das quais 90
> paradas há mais de 60 dias**" diz onde esta o problema e quem precisa ser chamado.

---

### Camada 3 — a aba de exceções (esforço: baixo, alto retorno)

Hoje a mapeadora **conta** em vez de **listar**. Ela diz que 413 fichas tem problema,
mas não quais — entao todo plano de ação obriga a re-derivar da base, arquivo por
arquivo. Foi exatamente o que foi preciso fazer para produzir
[[Levantamento - Fichas sem Aplicacao LMR]].

Proposta: uma aba **`Excecoes`** gerada pelo mesmo módulo Gestão PMIB, com **uma linha
por ficha problematica**:

| Código PMIB | Lista | Sistema | Pendência | Dias parado | Prazo estourado? | Responsável |
|---|---|---|---|---|---|---|

Onde `Pendencia` e a seção que falta (`APLICACAO - LMR`, `VALORIZACAO`,
`CARACT. TECNICAS`...). Ordenada por dias parado.

**Essa aba e a lista de trabalho do dia.** Substitui o exercicio de garimpo que hoje se
refaz a cada vez que alguém pergunta "o que esta pendente?".

---

## O que eu faria primeiro

1. **Camada 1** — porque o dado já existe, o módulo já roda, e o resultado (414 itens
   estourados, o mais antigo com 441 dias) e o que sustenta a negociação com Itaipu.
2. **Camada 3** — porque transforma o número em fila de trabalho.
3. **Camada 2** — porque só ela permite medir *tempo de ciclo* e passar de "reagir" para
   "prometer com base em histórico". Mas ela só acumula valor com o tempo: as datas
   começam a valer a partir de quando forem carimbadas.

> [!note] O que **não** fazer
> Não criar uma coluna de data por etapa do fluxo. Seriam 6 ou 7 colunas preenchidas a
> mao, e a experiência da própria mapeadora mostra o que acontece: `RESPONSAVEL` esta
> vazio em 39% das listas e `ENTREGA` em 68%. **Coluna que depende de disciplina humana
> para ser preenchida fica vazia.** As duas da Camada 2 funcionam porque quem escreve e
> o SIG-FT.

---

## Relação com o resto do diagnostico

Esta proposta ataca, de uma vez:
- a crítica central de [[Diagnostico - Deficiencias]] — ausência de tempo;
- **D6** (campos de gestão em branco) — datas automaticas não dependem de preenchimento;
- **D5** (57% das listas em `INICIAR`) — com *aging* da para separar "não começou porque
  e novo" de "não começou ha oito meses";
- o insumo de priorização de [[Plano de Acao - Aplicacao LMR]].

## Relacionados
[[Indicadores e Como Ler]] · [[Planilha STATUS_PMIB]] · [[Mapeamento das Listas de Sobressalentes]] · [[SIG-FT - Modulos]]

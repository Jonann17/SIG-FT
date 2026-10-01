---
tags: [plano, lmr, acao, handoff]
status: rascunho-v2
criado: 2026-08-31
atualizado: 2026-08-31
destino: virar documento formal para Itaipu e equipe CMI
---

# Plano de Ação — Aplicação LMR

> [!warning] Documento de trabalho, nao conhecimento permanente
> Contem numeros e situacoes de uma data especifica. O que descreve **como o processo
> funciona** mora no nucleo do cofre (`01` a `06`).


> [!info] Estado: rascunho v2
> Prioridades já declaradas pelo Luan. **Falta apenas definir quantas pessoas** e a data
> de início para converter o cronograma relativo (seção 5) em datas absolutas.

---

## 1. Por que este plano existe

> [!danger] O plano e a condição para a formalizacao
> O compromisso dos **2 a 3 meses** para a Aplicação LMR **está em processo de
> aprovação** — e, para ser aprovado, **Itaipu exige este plano de ação**. Sem ele, não
> ha acordo formal; sem acordo formal, o CMI opera sem regra escrita sobre o único prazo
> que hoje está sendo cobrado.

Duas coisas ao mesmo tempo:

**1.1 O passivo.** O CMI emitiu fichas para análise **sem a seção de Aplicação LMR
preenchida** — o portal e Itaipu aceitavam. Itaipu **passou a bloquear o recebimento**
enquanto a LMR não estiver la.

**1.2 A proposta de novo fluxo.** O CMI pediu que a Aplicação LMR **deixe de ser condição
para entregar**, permanecendo condição para **aprovar** — e prometeu este plano como
contrapartida.

> [!important] O plano só funciona se fizer as duas coisas
> Um plano que só pede a mudança de fluxo e um pedido de favor. Um que só limpa o passivo
> repete o problema no próximo lote. **A credibilidade do pedido vem do compromisso
> datado sobre o passivo.**

---

## 2. O tamanho do problema

Contagem **item a item** nos `_STATUS_PMIB` (fonte confiável — ver seção 8).

> [!danger] Unidade de contagem: **código PMIB distinto**
> Dentro de uma mesma lista o mesmo item pode aparecer em várias linhas, mas e **um único
> código PMIB — uma única ficha**. Todos os números abaixo foram recontados nessa base em
> 31/08/2026. Ver [[Plano de Acao - ESTRUTURA]], anexo de método.

| | Fichas |
|---|---:|
| **Sem Aplicação LMR nos sistemas do plano** | **622** |
| — **MAXIMA** — RV Digital + RV Hidráulico | 170 |
| — **4** — Sala Segura | 33 |
| — **3** — Fire Fighting, Água Pura, GD | 184 |
| — **2** — Selo do Eixo, Baterias, Aeração Axial, SMF, PDG, Painéis, Inversores e PDE | 235 |

> [!important] A escala e **ascendente**: maior número = mais urgente
> Ordem de ataque: **MAXIMA → 4 → 3 → 2**.

### O relogio dos 2/3 meses já estourou

Calculado a partir de `DATA DO EMAIL COMUNICANDO ENTREGA` — ver
[[Plano - Dimensao de Tempo]]:

| Faixa desde o e-mail de intenção | Itens sem LMR |
|---|---:|
| dentro do prazo (até 60 d) | 2 |
| janela 60-90 d | 2 |
| estourado 90-180 d | 95 |
| estourado 180-365 d | 286 |
| **estourado há mais de 1 ano** | **33** |
| **TOTAL ESTOURADO** | **414** |

> [!warning] Levar este número para Itaipu e decisão consciente
> Ele expoe o CMI. Mas Itaipu **já sabe** que as fichas foram sem LMR — foi por isso que
> passou a exigir, e por isso pede o plano. **Número sem plano e confissao. Número com
> plano e gestão.**

---

## 3. Prioridades declaradas

Graus declarados pelo Luan em 31/08/2026. Contagem por **código PMIB distinto**, de lista
inteira — a orientacao e fechar a lista, não só o passivo.

Em ordem de urgência — **MAXIMA primeiro, depois 4, 3 e 2**.

| Grau | Sistema | Código Itaipu | Fichas | LMR ok | **Falta** | Dias-pessoa |
|---|---|---|---:|---:|---:|---:|
| **MAXIMA** | RV — Parte Digital (CCAR + TGC) | `#ST00=M00MEU10&EPB020` | 58 | 28 | **30** | 6,0 |
| **MAXIMA** | RV — Parte Hidráulica | `#ST00=M00MEU10&MPB020` | 142 | 2 | **140** | 28,0 |
| **4** | Sala Segura | `#ST00=U01&MPB020` | 38 | 5 | **33** | 6,6 |
| **3** | Fire Fighting | `#ST00=X00XGF10&MPB020` | 29 | 0 | **29** | 5,8 |
| **3** | UG — Água Pura | `#ST00=M00MKF10&MPB020` | 79 | 0 | **79** | 15,8 |
| **3** | Grupo Gerador Diesel (GD) | `#ST50=B01BDV10&EPB020` | 76 | 0 | **76** | 15,2 |
| **2** | UG — Selo do Eixo da Turbina | `#ST00=M00MES10&MPB020` | 10 | 0 | **10** | 2,0 |
| **2** | Banco de Baterias e Carregadores | `#ST00=B03BPA10TB010-TB903&EPB020` | 61 | 0 | **61** | 12,2 |
| **2** | UG — Aeração Axial da Turbina | `#ST00=M00MEG20&MPB020` | 14 | 0 | **14** | 2,8 |
| **2** | SMF — Medição de Faturamento | `#ITA0=A01AAM10&EPB020-01` | 22 | 0 | **22** | 4,4 |
| **2** | Serv. Aux. Essenciais — Painéis *(JVM)* | `#ST00=B03BPA10UC012-UC903&EPB020` | 64 | 0 | **64** | 12,8 |
| **2** | Serv. Aux. Essenciais — Inversores e PDE *(JVM)* | `#ST00=B04BMA10TB020&EPB020` | 48 | 0 | **48** | 9,6 |
| **2** | Grupo Gerador Diesel — PDG *(JVM)* | `#ST00=B03BDV10UC012-UC001&EPB020` | 16 | 0 | **16** | 3,2 |
| | **TOTAL** | | **657** | **35** | **622** | **124,4** |

### Concluídos — saem da fila

| Sistema | Código | Fichas | Nota |
|---|---|---:|---|
| SCADA / EMS | `#ITA0=C01CUC01&EPB020` | 29 | ✅ LMR 100%; resta investigar a não-entrega |
| Coleta e Separacao de Água e Óleo | `#ST00=B01BDV10&MPB020` | 4 | ✅ LMR 100%; resta correção das fichas (atividade G) |
| Bombas de Extrema Emergência | `#ST00=B01BDV10EQ010-GP901&MPB020` | 2 | ✅ LMR 100%; resta a explosão (atividade A) |

> [!tip] Parte das 622 pode ser mais barata do que parece
> Ha fichas com a **Aplicação LMR pronta na planilha** e apenas o **upload pendente** —
> caso confirmado nas 6 NETZSCH do RV Hidráulico. Nessas, o custo e de minutos, não de
> dias. ⬜ *Levantar, sistema a sistema, quais já tem planilha pronta antes de fechar o
> cronograma.* Ver [[Plano de Acao - ESTRUTURA]], atividade **H**.

---

## 4. Produtividade

| Referência | Volume | Prazo | Regime |
|---|---|---|---|
| **CCAR** | 33 fichas | 1 semana | 1 pessoa, 4 h/dia |
| **Média observada** | ~50 fichas | 2 semanas | 1 pessoa, 4 h/dia |
| RTA | 57 fichas / 8.557 aplicações | — | **atípico, não usar** |

**Taxa de planejamento: 5 fichas por dia-pessoa** (1 pessoa, 4 h/dia). O CCAR entregou
6,6/dia — ha ~25% de folga.

> [!note] Por que o RTA não serve de base
> No **CCAR**, o `CODIGO LMR` e um **produto cartesiano regular**: um material x 20
> unidades geradoras (M01-M09 e M19 no ST50; M10-M18 e M20 no ST60). 1.020 linhas para 33
> fichas — ~31 por ficha, e a variacao entre linhas e só o número da unidade.
> No **RTA** eram 8.557 localizacoes fisicas genuinamente distintas (~150 por ficha),
> cada uma com elevacao, eixo e trecho próprios. Não da para gerar por regra.

### Duas classes de lista, com custos diferentes

| Classe | Padrão | Exemplos | Automatizável? |
|---|---|---|---|
| **Replicada por unidade** | mesmo equipamento em N unidades geradoras | Regulação (P1, P2), Selo do Eixo (P3), Aeração Axial | **sim** — a aba 3 e gerada da aba 1 mais a enumeracao de unidades |
| **Distribuida pela planta** | cada item num lugar diferente | Sala Segura (P8), SMF, Painéis (P4) | não — exige garimpo real |

> [!tip] Oportunidade de reducao de custo
> Nas listas da classe replicada, o SIG-FT poderia **gerar a aba 3 sozinho** depois que a
> aba 1 (`DOCS DE REFERENCIA`) estivesse pronta. Isso ataca justamente P1, P2 e P3 — as
> três primeiras prioridades, 230 fichas. Ver [[Diagnostico - Plano de Melhoria]], M6.

---

## 5. Cronograma

### Balanceamento por raia

O paralelismo e limitado por **quantos sistemas diferentes** se ataca, não por quantas
pessoas se aloca — duas pessoas no mesmo sistema competem pela mesma equipe de
engenharia. Por isso as raias seguem a **equipe de engenharia**, não o volume.

| Raia | Sistemas | Engenharia | Fichas | Dias-pessoa |
|---|---|---|---:|---:|
| **A — Unidade Geradora** | P1, P2, P3 | Celio Silva | 230 | 46,0 |
| **B — Serv. Aux. Essenciais** | P4, P5, P6 | Bruno Romaniv / David Duran | 212 | 42,4 |
| **C — resto** | P7, P8, P9, P10 | Bruno / Fabio / Marcelo | 155 | 31,0 |

### Cenarios

| Pessoas | Dias úteis | Semanas | Cabe no compromisso de 2/3 meses? |
|---:|---:|---:|---|
| 1 | 119 | 24 | **não** (~5,5 meses) |
| 2 | ~60 | ~12 | no limite (~3 meses) |
| **3** | **~40** | **~8** | **sim, com folga** (~2 meses) |

> [!important] Recomendação: **3 pessoas, ~2 meses**
> Com 2 pessoas o plano aterrissa exatamente no teto dos 3 meses — sem margem para o
> risco que o plano não controla (tempo de resposta da engenharia de cada sistema).
> Com 3, sobra folga, e o compromisso apresentado a Itaipu fica defensável.

### Ondas sugeridas

**Onda 0 — semana 1 e meia · destrava uma entrega**
- **P1, Regulação Parte Digital** (32 fichas, 6,4 dias-pessoa)
- Entrega: reenvio do e-mail de intenção de entrega do CCAR, já com LMR completa.
- E o menor esforço com o maior retorno imediato do plano inteiro.

**Onda 1 — semanas 2 a 10 · duas raias em paralelo**
- Raia A: **P2** (162) e **P3** (36)
- Raia B: **P4** (92), **P5** (64), **P6** (56)

**Onda 2 — semanas 10 a 14**
- **P7** (16), **P8** (33), **P9** (29), **P10** (77)

**Onda 3 — encaixe em folgas**
- SCADA (6), SMF (22), Aeração Axial (24), sem-lista (7)

---

## 6. O caso P1 — Regulação Parte Digital (CCAR + TGC)

Merece nota própria porque **não e uma lista de um subsistema só**.

A lista `#ST00=M00MEU10&EPB020` cobre **CCAR e TGC**. A estratégia adotada foi:

> Emitir a lista de preços **com o CCAR preenchido e o TGC em branco**, para conseguir
> emitir as fichas do CCAR e realizar a entrega deles — mas a Aplicação LMR do TGC
> também precisa ser feita, e e passivo.

Estado atual dos 60 itens:

| | Fichas | Situação |
|---|---:|---|
| CCAR com LMR completa | 28 | pronto |
| CCAR sem LMR | **5** | **material não encontrado no desenho do painel** |
| TGC sem LMR | ~27 | ainda não iniciado |

> [!warning] Os 5 do CCAR são o único item deste plano que dinheiro e tempo não resolvem
> São os casos em que o fluxo manda **buscar suporte da engenharia do sistema**. Precisam
> ser escalados nominalmente, com prazo, **fora** da conta de 5 fichas/dia — senao
> seguram a onda 0 inteira.

> [!note] O e-mail de intenção foi removido de proposito
> O CMI **já havia enviado** o e-mail de intenção de entrega desta lista, e **combinou
> retirar** para preencher a Aplicação LMR e reenviar. Por isso o `_STATUS_PMIB` dela
> está com `DATA DO EMAIL COMUNICANDO ENTREGA` vazia — **não** porque nunca foi emitida.
> Fechar P1 e o que permite reenviar.

---

## 7. Mecanismo de devolucao das fichas já emitidas

Definido pelo Luan:

- **Caso a caso**, com base neste plano de ação.
- Em geral: **se a ficha já foi autorizada, o CMI se compromete a finalizar a Aplicação
  LMR** — não se pede devolucao.
- Quando ha devolucao, ela e **por ficha**.
- Mas a **identificação do lote no portal e pelo código da lista**.

> [!tip] Consequência operacional
> Pede-se por ficha, organiza-se por lista. As tabelas da seção 3 já estão na unidade
> certa para montar o pedido: um bloco por linha da tabela.

---

## 8. Qualidade de dado — dois achados a corrigir antes de publicar

### 8.1 A mapeadora estava desatualizada
`FICHAS COM APLICACAO - LMR FINALIZADA` mostrava **0** para a lista do CCAR, quando o
`_STATUS_PMIB` já tinha **28 completas**. Causa: o módulo Gestão PMIB não foi executado
depois do avanço. Sem malicia — mas mostra que **a agregação envelhece em silêncio**.

| Lista | Mapeadora | Arquivo | Dif. |
|---|---:|---:|---:|
| `#ST00=M00MEU10&EPB020` | 0 | 28 | +28 |
| `#ST00=B03BPA10UC012-UC903&EPB020` | 0 | 5 | +5 |
| `#ST00=B04BMA10TB020&EPB020` | 0 | 4 | +4 |
| `#ST00=B03BPA10TB010-TB903&EPB020` | 0 | 3 | +3 |

**Ação**: rodar o Gestão PMIB **antes** de publicar qualquer número deste plano.

### 8.2 Uma data invertida distorce um sistema inteiro

> [!danger] `#ST00=B04BMA10TB020&EPB020` — Inversores e PDE
> Os **56 itens** da lista estão com `DATA DO EMAIL COMUNICANDO ENTREGA = 2025-03-12`.
> **A data correta e 03/12/2025** — foi **erro de conversão de data do Excel**, confirmado
> pelo Luan em 31/08/2026.
>
> | | Atraso |
> |---|---:|
> | como esta gravado (`12/03/2025`) | 537 dias |
> | **correto (`03/12/2025`)** | **271 dias** |
>
> Um erro de conversão **inflou o atraso de um sistema inteiro em 266 dias** — e criou o
> "item mais antigo do projeto", que não existe. Com a correção, o item mais antigo real
> passa a ser o do **Selo do Eixo, com 441 dias**.

**Ação**: corrigir no `_STATUS_PMIB` antes de publicar, e **incluir validação de data no
SIG-FT**. Como a causa foi **conversão do Excel** e não digitacao, a defesa certa e ler a
coluna como texto e converter explicitamente com formato fixo (`%d/%m/%Y`), em vez de
deixar o pandas/openpyxl inferir — e recusar a inferencia ambigua em lote.

---

## 9. A negociação do novo fluxo

### O que se pede
Que a Aplicação LMR deixe de ser condição para **entregar** e passe a ser condição apenas
para **aprovar**.

### Os argumentos

> [!success] 1. Já existe precedente no próprio fluxo: emitida basta, aprovada não
> A **lista de preços** funciona exatamente assim — **emitida** no Aconex libera a
> entrega; **aprovada** pela SM.DT só e exigida no Evento de Aprovação.
> **O pedido do CMI e aplicar a Aplicação LMR a mesma lógica que Itaipu já aceita para a
> lista de preços.** Não e exceção nova: e coerencia com o fluxo vigente.

> [!success] 2. O almoxarifado temporario já e o controle
> Material entregue com ficha não aprovada fica em **almoxarifado temporario** e só passa
> ao definitivo após a aprovação. **Itaipu já tem o mecanismo para segurar material com
> documentação aberta.** Exigir a LMR antes da entrega não acrescenta proteção — antecipa
> a exigencia para um ponto onde ela não muda o resultado.

**3. A rastreabilidade logistica não depende da LMR.** O `CODIGO PMIB` nasce na criação
da ficha e já basta para o MTA e a etiqueta.

**4. As três condicionais de entrega já acordadas** — etiquetas MTA, e-mail de
autorização, lista EN.DT aprovada — **não incluem a LMR**. O pedido preserva as três.

**5. A LMR não qualifica o material.** Não valida preço, não afeta o recebimento físico
nem a conferencia de quantidade. E informação de **onde aplicar**, útil a manutenção —
que só passa a importar quando o material sai do almoxarifado.

### O que o CMI oferece
1. **Compromisso datado** de eliminacao do passivo (seção 5).
2. **Regra interna: nenhuma ficha nova sai sem LMR.** Fechar a torneira e mais barato que
   secar o chao.
3. **Relatório periodico** com o indicador de prazo da
   [[Plano - Dimensao de Tempo|Camada 1]] — que até hoje não existia.

### O custo de não mudar
Material pronto, pago e conferido fica retido por trabalho documental que não afeta a
integridade dele. Empurra o início da garantia, ocupa espaco no fornecedor ou no
almoxarifado do CMI (contra a regra da ET, que manda entregar direto) e atrasa os eventos
**2783 a 2842**.

---

## 10. O template de referência

O padrão vigente e o **CCAR**, não o RTA:
`SOBRESSALENTES - PMIB/05 - UNIDADE GERADORA/REGULACAO VEL E POT/PARTE DIGITAL/APLICACAO LMR - CCAR.xlsx`

| Aba | Papel | Tamanho no CCAR |
|---|---|---:|
| 1 — `DOCS DE REFERENCIA` | **o garimpo**: em que desenho cada material aparece | 77 linhas |
| 2 — `DESCRICAO DOCUMENTOS` | catalogo dos desenhos (cod. Itaipu / cod. CMI / descrição) | 5 documentos |
| 3 — `APLICACAO - LMR` | **o que sobe pelo SIG-FT**: `FICHA PMIB`, `CODIGO LMR`, `TAG LMR`, `Status` | 1.020 linhas |

Já atende ao pedido de Itaipu de 20/08/2026 (cabeçalho com `LISTA DE DOCUMENTOS` e
`WORKSTATEMENT` preenchidos) e fundiu em um só arquivo as duas planilhas que o RTA usava.

> [!important] Consolidar antes de escalar
> O template do CCAR ainda vive **na pasta do próprio sistema**. Antes de 2 ou 3 pessoas
> comecarem em paralelo, ele precisa substituir o
> `Templates/APLICACAO LMR - SOBRESSALENTES_template.xlsx`, que ainda reflete o modelo
> antigo. **Pessoas em paralelo com templates diferentes = retrabalho garantido.**

---

## 11. Pendências para fechar o plano

1. **Quantas pessoas** e a partir de quando — converte a seção 5 em datas absolutas.
2. Prioridade das 4 listas ainda não declaradas (SMF, Aeração Axial, SCADA, sem-lista).
3. Confirmar a data de `#ST00=B04BMA10TB020&EPB020` (seção 8.2).
4. Escalar nominalmente os **5 itens do CCAR não encontrados no desenho** (seção 6).
5. Consolidar o template do CCAR em `Templates/` (seção 10).
6. Rodar o **Gestão PMIB** para atualizar a mapeadora antes de publicar números.

## Relacionados
[[Levantamento - Fichas sem Aplicacao LMR]] · [[Secao - Aplicacao LMR]] ·
[[Plano - Dimensao de Tempo]] · [[Fluxo Macro de Entrega]] ·
[[Entrega Documental e Explosao de Itens]] · [[Lista de Precos]] ·
[[MTA, Etiquetas e Entrega no Almoxarifado]] · [[Diagnostico - Riscos]]

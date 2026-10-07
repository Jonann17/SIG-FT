---
tags: [plano, lmr, acao, estrutura, rascunho]
status: esqueleto-para-refino
criado: 2026-08-31
origem: reuniao com Itaipu de 31/08/2026
destino: documento formal para Itaipu e equipe CMI
---

# Plano de Ação — ESTRUTURA

> [!warning] Documento de trabalho, nao conhecimento permanente
> Contem numeros e situacoes de uma data especifica. O que descreve **como o processo
> funciona** mora no nucleo do cofre (`01` a `06`).


> [!info] Isto e um esqueleto, não um plano pronto
> A **finalizacao e do Luan**. Este documento define a **forma** — a taxonomia de
> atividades, o template de ficha por sistema, e onde cada informação entra — e já traz
> o conteudo da reunião de 31/08/2026 encaixado.
>
> Tudo marcado com **⬜** e lacuna consciente, a preencher.
> Datas ficam de fora **de proposito** nesta versão.

---

## A forma proposta

Itaipu pediu o plano **separado por atividade e por sistema**, e que o CMI **indique as
pendências da própria Itaipu**. Isso sugere cinco partes:

| Parte | O que responde | Para quem serve mais |
|---|---|---|
| **I. Sumario** | qual o tamanho do problema e o que se pede | Itaipu — leitura de 1 minuto |
| **II. Por ATIVIDADE** | quantas frentes existem, e quanto pesa cada uma | CMI — alocar gente |
| **III. Por SISTEMA** | o que acontece em cada lista, com ações nomeadas | os dois — e o corpo do documento |
| **IV. Pendências de ITAIPU** | o que o CMI precisa e não depende dele | Itaipu — foi ela quem pediu |
| **V. Cronograma** | quando | ⬜ última a preencher |

> [!tip] Por que a Parte IV vale mais do que parece
> Itaipu **pediu** para o CMI listar as pendências dela. Isso transforma o documento de
> "prestacao de contas do CMI" em **acordo de duas vias**. Toda linha da Parte IV e uma
> linha que o CMI **não** precisa justificar sozinho — e o argumento mais forte para o
> pedido de alteração de fluxo.

---

# Parte I — Sumario

⬜ *A escrever por último, quando os números pararem de mudar.*

Deve conter, em no máximo meia página:
- o número total de fichas e quantas faltam de Aplicação LMR;
- as frentes de trabalho (Parte II) em uma frase cada;
- o pedido de alteração de fluxo, com o argumento da lista de preços
  (ver [[Plano de Acao - Aplicacao LMR]], seção 9);
- o compromisso: ⬜ *datas*.

---

# Parte II — Visão por ATIVIDADE

Seis tipos de atividade sairam da reunião. Proposta de nomenclatura:

| Cod. | Atividade | O que e | Sistemas afetados |
|---|---|---|---|
| **A** | **Explosão de itens e criação de fichas documentais** | item complexo entregue como conjunto precisa virar N fichas de componentes | Bombas de Extrema Emergência, Sala Segura, ⬜ Inversores/Retificador |
| **B** | **Aplicação LMR** | fazer o garimpo no desenho e montar a planilha | 14 listas, com grau de prioridade |
| **C** | **Investigacao de entrega** | material autorizado mas não entregue, ou não localizado no almoxarifado de IB | SCADA, GD, Sala Segura, Fire Fighting, Selo do Eixo |
| **D** | **Regularizacao de nota fiscal** | NF divergente do material entregue | Fire Fighting, Banco de Baterias, Aeração Axial |
| **E** | **Finalizacao de fichas nominais** | fichas especificas pedidas por Itaipu | RV Hidráulico (NETZSCH), SMF |
| **F** | **Pendência de ITAIPU** | ação que não depende do CMI | Farina (doc. de explosão), SMF (liberacao de fichas) |
| **G** | **Correção de fichas devolvidas** | Itaipu não aprovou; ha comentários a atender e o status vai para *em correção* | Coleta e Separacao de Água e Óleo, ⬜ outras |
| **H** | **Upload da Aplicação LMR no portal** | a LMR **já está feita na planilha**, falta subir pelo SIG-FT | RV Hidráulico (1223-1227, 1229) |

> [!note] Por que separar C, D, G e H de B
> São **naturezas diferentes de trabalho, com responsáveis diferentes**: a Aplicação LMR e
> engenharia sobre desenho; investigacao de entrega e logistica/Procurement; nota fiscal e
> fiscal/Procurement; correção de ficha devolvida e quem elaborou a ficha. Se entrarem
> tudo como "pendência", o plano vira uma lista que ninguém sabe quem executa.

> [!important] H não e B — e a distinção mais facil de perder
> **Fazer a Aplicação LMR** (garimpo no desenho, montar a planilha) e **subir a Aplicação
> LMR no portal** pelo SIG-FT são duas coisas. Ha fichas com a **LMR pronta na planilha**
> cuja coluna `APLICACAO - LMR` do `_STATUS_PMIB` ainda está vazia, porque o upload não
> foi feito.
>
> **Consequência para todo este plano**: a coluna do `_STATUS_PMIB` mede *estado no
> portal*, não *trabalho de engenharia feito*. Onde a planilha de LMR já existe, o custo
> restante e de **minutos de upload**, não de dias de garimpo — e o número de fichas
> "faltando" superestima o esforço real.
> ⬜ *Conferir, sistema a sistema, quais já tem planilha de LMR pronta.*

### Escala de prioridade da Aplicação LMR

> [!important] Escala **ascendente**, de 2 a 5: quanto **maior** o número, **mais urgente**
> Ordem de ataque: **5 → 4 → 3 → 2**.
> (A leitura anterior estava invertida, e o rótulo MÁXIMA virou o grau 5.)

| Grau | Sistemas | Fichas |
|---|---|---:|
| **5** | RV — Parte Digital / CCAR + TGC (30), Sala Segura (33) | 63 |
| **4** | RV — Parte Hidráulica (140) | 140 |
| **3** | Fire Fighting (29), Água Pura (79), Grupo Gerador Diesel (76) | 184 |
| **2** | Selo do Eixo (10), Banco de Baterias (61), Aeração Axial (14), SMF (22), PDG (16), Painéis (64), Inversores e PDE (48) | 235 |
| | **TOTAL** | **622** |

> [!note] A criticidade da planilha é outra coisa
> Na [[Aba de Atividades e Cronograma|aba de Atividades]] há uma coluna `CRITICIDADE`, na
> mesma escala de 1 a 5, aplicada **por atividade**. O grau acima é do **sistema**, e vale
> só para a Aplicação LMR. Um sistema de grau 2 pode ter uma atividade crítica; um de grau
> 5 pode ter uma trivial.

> [!note] Coleta e Separação de Água e Óleo saiu da escala de LMR
> As 4 fichas já estão com Aplicação LMR `COMPLETO` — mas o sistema continua no plano, por
> pendência de outra natureza (atividade G). Ver o bloco do sistema.

---

# Parte III — Visão por SISTEMA

## Template do bloco de sistema

> [!note] Por que "bloco" e não "ficha"
> No projeto, **ficha** já significa *ficha técnica do material no PMIB*. Usar a mesma
> palavra para a seção do plano criaria ambiguidade em todo o documento. Aqui: **bloco de
> sistema**.

Bloco padrão, **curto de proposito** — o plano tem ~14 destes, e bloco longo não e lido.

```markdown
### [Nome do sistema]
`[codigo Itaipu]` · CMI `[codigo CMI]` · Evento [xxxx]
Fichas: **N** · com LMR: X · **falta: Y**

**Situacao** — 2 a 3 linhas, factual.

**Acoes do CMI**
| # | Atividade | Tipo | Responsavel | Prazo |
|---|---|---|---|---|

**Pendencias de ITAIPU**
| # | O que precisamos | De quem | Impacto se nao vier |
|---|---|---|---|

**Aplicacao LMR** — prioridade [grau] · Y fichas
```

---

## Blocos de sistema — rascunho a partir da reunião

### Bombas de Extrema Emergência
`#ST00=B01BDV10EQ010-GP901&MPB020` · Evento ⬜
Fichas: **2** · falta explosão

**Situação** — Foram entregues **dois conjuntos de motobombas**, que na lista do CMI eram
apenas **dois itens com dois códigos CMI**. Ao abrir a caixa, Itaipu encontrou vários
componentes e pediu a **explosão** dos itens, com criação de novas fichas de
**entrega documental**. Itaipu pediu **uma data** para a resolucao.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | Explodir os 2 itens e definir a lista de componentes | A | ⬜ | ⬜ |
| 2 | Criar as novas fichas no PMIB | A | ⬜ | ⬜ |
| 3 | Pedir ao Procurement responsável o preenchimento das novas fichas — ou, no mínimo, o envio dos datasheets | A | ⬜ | ⬜ |
| 4 | Informar a Itaipu a data de conclusão | — | ⬜ | ⬜ |

**Pendências de ITAIPU**
| # | O que precisamos | De quem | Impacto se não vier |
|---|---|---|---|
| 1 | Documento que explica **como realizar a explosão** | **Farina** | sem critério comum, a explosão pode ser refeita |

**Aplicação LMR** — ✅ **confirmado: os 2 itens já estão com LMR `COMPLETO`**
(`4500063671.0381` e `4500063671.0382` — MOTOR PUMP SET AHLSTAR A33-125 LM, 50 e 60 Hz).
E-mail de intenção em **11/03/2025**.
Para os componentes explodidos e **simples**: são aplicados no próprio item entregue.

---

### Sala Segura
`#ST00=U01&MPB020` · Evento 2831 / 2832
Fichas: **38** · com LMR: 5 · **falta: 33**

**Situação** — Mesmo caso das Bombas de Extrema Emergência, nos itens da **unidade
condensadora e evaporadora**: vários componentes que devem ter fichas documentais.
Fornecedor: **Vertiv** (a Zeitec comprou da Vertiv).

> [!success] Os itens a explodir estão identificados
> São exatamente os **5 itens da lista que já tem LMR `COMPLETO`** — os outros 33 estão
> `INCOMPLETO`:
>
> | Ficha | Item |
> |---|---|
> | `4500063671.0152` | UNIDADE EVAPORADORA LIEBERT PEX 4 |
> | `4500063671.0153` | UNIDADE CONDENSADORA LIEBERT PEX 4 COM PES DE FIXACAO |
> | `4500063671.0272` | RETIFICADOR (CCKR 125-500A) |
> | `4500063671.0273` | INVERSOR DE 60 kVA |
> | `4500063671.0274` | SOBRESSALENTES — INVERSOR — DEFASADOR 3F |
>
> **Confirma que os inversores e o retificador são itens de dentro da Sala Segura**, e
> não da lista SAE Inversores e PDE (que e da JVM e tem grau 2).
>
> Consequência boa: a LMR dos 5 pais **já está feita**, e a dos filhos explodidos e
> derivavel dela — mesma localização física.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | Explodir os itens da unidade condensadora e evaporadora | A | ⬜ | ⬜ |
| 2 | Criar as novas fichas documentais | A | ⬜ | ⬜ |
| 3 | Obter datasheets junto a Vertiv / Zeitec | A | ⬜ | ⬜ |
| 5 | Aplicação LMR das 33 fichas | B | ⬜ | ⬜ |

**Pendências de ITAIPU**
| # | O que precisamos | De quem | Impacto se não vier |
|---|---|---|---|
| 1 | Documento que explica como realizar a explosão (o mesmo das Bombas) | **Farina** | critério de explosão indefinido |

**Aplicação LMR** — prioridade **4** · 33 fichas

> [!note] A ficha 0176 foi para o bloco do Grupo Gerador Diesel
> O número correto e **`4500063671.0176`** — `COMPRESSOR ATLAS LT3 30 BM 460V 50HZ`, da
> lista **`#ST50=B01BDV10&EPB020`** (GD), não da Sala Segura. A ação de investigar a
> não-entrega está no bloco daquele sistema.

> [!note] Inversores e retificador — **tema a ser trabalhado**
> Também precisarao ser explodidos (`0272`, `0273`, `0274`). A estratégia atual e
> **tentar fazer Itaipu aceitar os itens sem a explosão**, e explodir depois.
> Entra no plano como **tema a trabalhar**, não como ação com prazo: e posição de
> negociação, e declarar prazo enfraqueceria a posição.

---

### SCADA / EMS
`#ITA0=C01CUC01&EPB020` · Evento 2823 / 2824
Fichas: **29** · com LMR: **29** · **falta: 0** ✅

**Situação** — Aplicação LMR **100% concluída**. O `_STATUS_PMIB` estava defasado e já foi
corrigido. Pendência única: os equipamentos **nunca foram entregues**.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | **Investigar por que a entrega dos equipamentos nunca ocorreu** | C | ⬜ | ⬜ |

**Aplicação LMR** — concluída.

---

### Selo do Eixo da Turbina
`#ST00=M00MES10&MPB020` · Evento 2783 a 2822
Fichas: **10** · **falta: 10**

**Situação** — ⬜ *Confirmar:* 4 itens foram entregues, 6 restantes em situação a apurar.
(A contagem de 10 fichas bate com os "4 + 6" citados na reunião.)

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | Verificar se os **4 itens** foram entregues | C | ⬜ | ⬜ |
| 2 | Levantar a situação dos **6 itens restantes** | C | ⬜ | ⬜ |
| 3 | Aplicação LMR | B | ⬜ | ⬜ |

**Aplicação LMR** — prioridade **2** · 10 fichas

---

### Sistema de Combate a Incendio (Fire Fighting)
`#ST00=X00XGF10&MPB020` · Evento 2837 / 2838
Fichas: **29** · **falta: 29**

**Situação** — **6 equipamentos não foram encontrados no almoxarifado de IB.** A nota
fiscal precisa ser regularizada.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | **Identificar quais são os 6 equipamentos** não encontrados | C | ⬜ | ⬜ |
| 2 | Apurar por que não foram entregues | C | ⬜ | ⬜ |
| 3 | Regularizar a nota fiscal | D | ⬜ | ⬜ |
| 4 | Aplicação LMR | B | ⬜ | ⬜ |

**Aplicação LMR** — prioridade **3** · 29 fichas

---

### SMF — Sistema de Medição de Faturamento
`#ITA0=A01AAM10&EPB020-01` · Evento 2841 / 2842
Fichas: **22** · **falta: 22**

**Situação** — A entrega esta **travada por pendência de Itaipu**: 5 fichas já solicitadas
aguardam liberacao. A entrega dos itens da **Enerwatt** só ocorrera após a liberacao de
**3 fichas: 0640, 0525 e 1153**.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | **Cobrar formalmente** a liberacao das 5 fichas, por este plano | E/F | ⬜ | ⬜ |

**Pendências de ITAIPU**
| # | O que precisamos | De quem | Impacto se não vier |
|---|---|---|---|
| 1 | Liberacao de **5 fichas** já solicitadas | ⬜ | entrega parada |
| 2 | Liberacao das fichas **0640** (disjuntor termomagnetico bipolar 16 A curva C), **0525** (medidor de energia Power Logic) e **1153** (módulo de expansao PM8000 E/S analogicas Schneider) — as três com e-mail de intenção em **28/11/2025** | ⬜ | **bloqueia toda a entrega Enerwatt** |

**Aplicação LMR** — prioridade ⬜ · 22 fichas

---

### Grupo Gerador Diesel — lista principal
`#ST50=B01BDV10&EPB020` · Evento 2835 / 2835a / 2836
Fichas: **76** · **falta: 76**

**Situação** — Faltaram entregar **2 itens: as fichas `0197` e `0176`** — esta última
citada na reunião como "solicitada e autorizada, mas nunca entregue".

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | Verificar por que a ficha **0197** não foi entregue — VALV. GAVETA ASC ROSQ. A216 NPT 300#; LMR `INCOMPLETO`; e-mail de intenção em **05/12/2025** | C | ⬜ | ⬜ |
| 2 | Verificar por que a ficha **0176** nunca foi entregue, apesar de **solicitada e autorizada** — COMPRESSOR ATLAS LT3 30 BM 460V 50HZ; mesmo e-mail de intenção, **05/12/2025** | C | ⬜ | ⬜ |
| 3 | Aplicação LMR | B | ⬜ | ⬜ |

> [!note] São duas fichas não entregues da mesma remessa
> `0176` e `0197` compartilham o e-mail de intenção de **05/12/2025**. Vale investigar as
> duas juntas — provavelmente e a mesma causa.

**Aplicação LMR** — prioridade ⬜ · 76 fichas

---

### Coleta e Separacao de Água e Óleo
`#ST00=B01BDV10&MPB020` · Evento ⬜
Fichas: **4** · **falta: 4**

**Situação** — ✅ **A Aplicação LMR já esta 100% concluída.** As 4 fichas
(`4500063671.0238` a `.0241` — kit de diafragma, esfera de teflon, assento de esferas,
o-ring) estão todas com `COMPLETO`. E-mail de intenção em **04/01/2025**.

> [!warning] Mas o sistema **não** sai do plano
> **Itaipu não aprovou as fichas.** Ha comentários a atender: o CMI deve colocar o
> **status de cada ficha em "em correção"** e ajustar conforme os comentários recebidos.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | Colocar o status de cada uma das 4 fichas em **"em correção"** | G | ⬜ | ⬜ |
| 2 | Ajustar as fichas conforme os comentários de Itaipu | G | ⬜ | ⬜ |
| 3 | Reenviar para análise | G | ⬜ | ⬜ |

**Aplicação LMR** — **concluída**. Sai da escala de prioridade, mas não do plano.

---

### Regulação de Velocidade e Potencia — Parte Hidráulica
`#ST00=M00MEU10&MPB020` · Evento 2783 a 2822
Fichas: **142** · com LMR: 2 · **falta: 140**

**Situação** — Itaipu pediu **prioridade para finalizar as fichas 1226 e 1229**, por
necessidade própria. A Aplicação LMR do conjunto e **prioridade maxima**.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | **Finalizar as 6 fichas NETZSCH** pedidas por Itaipu — `1223`, `1224`, `1225`, `1226`, `1227`, `1229` | E | ⬜ | ⬜ |
| 2 | **Subir a Aplicação LMR dessas 6 no portal** — já está feita na planilha, falta o upload pelo SIG-FT | **H** | ⬜ | ⬜ |
| 3 | Aplicação LMR das demais fichas | B | ⬜ | ⬜ |

> [!success] As 6 NETZSCH já tem a LMR pronta
> `APLICACAO - LMR` no `_STATUS_PMIB` está vazia para as seis, **mas a planilha de
> Aplicação LMR já as contém** — falta apenas o upload pelo SIG-FT. O custo e de
> **minutos**, não de dias.
>
> | Ficha | Item | E-mail de intenção |
> |---|---|---|
> | `1223` | SENSOR DE VIBRACAO MOTOBOMBAS, VKV022 | 11/05/2026 |
> | `1224` | SEMI ELASTIC COUPLING SET (MOTOR-PUMP) | 09/04/2026 |
> | `1225` | COUPLING LANTERN, WITH WIRE MESH OPENING | 09/04/2026 |
> | `1226` | NETZSCH SCREW PUMP — 3NS388/80S11I | 09/04/2026 |
> | `1227` | ELECTRIC MOTOR, 160 kW, 50 Hz | 09/04/2026 |
> | `1229` | NETZSCH SCREW PUMP — 3NS476/80S11I | 09/04/2026 |

**Aplicação LMR** — prioridade **MAXIMA** · 140 fichas

> [!warning] E a maior frente isolada do plano
> 140 fichas — mais de um quarto de tudo que falta. E a lista com maior proporcao de
> [[Entrega Documental e Explosao de Itens|itens explodidos]].

---

### Banco de Baterias e Carregadores
`#ST00=B03BPA10TB010-TB903&EPB020` · Evento 2826a / 2826b
Fichas: **61** · **falta: 61**

**Situação** — Divergência na nota fiscal: verificar se o item e **botao pulsador preto**
ou **verde e vermelho**.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | Verificar a nota fiscal — botao pulsador preto ou verde/vermelho | D | ⬜ | ⬜ |
| 2 | Aplicação LMR | B | ⬜ | ⬜ |

**Aplicação LMR** — prioridade **2** · 61 fichas

---

### Aeração Axial da Turbina
`#ST00=M00MEG20&MPB020` · Evento 2783 a 2822
Fichas: **14** · **falta: 14**

**Situação** — **Nota fiscal esta errada** e precisa ser verificada.

**Ações do CMI**
| # | Atividade | Tipo | Responsável | Prazo |
|---|---|---|---|---|
| 1 | Verificar e corrigir a nota fiscal | D | ⬜ | ⬜ |
| 2 | Aplicação LMR | B | ⬜ | ⬜ |

**Aplicação LMR** — prioridade **2** · 14 fichas

---

### Sistemas sem pendência operacional levantada na reunião

Não foram citados em 31/08, mas **tem Aplicação LMR pendente** e grau já definido.

| Sistema | Código | Falta LMR | Grau |
|---|---|---:|---|
| **RV — Parte Digital (CCAR + TGC)** | `#ST00=M00MEU10&EPB020` | 30 | **MAXIMA** |
| UG — Água Pura | `#ST00=M00MKF10&MPB020` | 79 | 3 |
| Serv. Aux. Essenciais — Painéis *(JVM)* | `#ST00=B03BPA10UC012-UC903&EPB020` | 64 | 2 |
| Serv. Aux. Essenciais — Inversores e PDE *(JVM)* | `#ST00=B04BMA10TB020&EPB020` | 48 | 2 |
| Grupo Gerador Diesel — PDG *(JVM)* | `#ST00=B03BDV10UC012-UC001&EPB020` | 16 | 2 |

> [!important] O RV Parte Digital merece bloco de sistema próprio
> Além da LMR, restam os **5 itens do CCAR não encontrados no desenho do painel** e a
> **Aplicação LMR do TGC**, que e passivo. Com grau **MAXIMA**, não pode ficar numa tabela
> de rodape. ⬜ *Montar o bloco.*

---

# Parte IV — Pendências de ITAIPU (consolidado)

> [!important] Itaipu pediu esta seção
> Repete, num só lugar, tudo que aparece nas fichas da Parte III. E a parte que o CMI
> **não** consegue resolver sozinho.

| # | O que o CMI precisa | De quem | Sistema(s) | Impacto |
|---|---|---|---|---|
| 1 | **Documento que explica como realizar a explosão de itens** | **Farina** | Bombas de Extrema Emergência, Sala Segura | sem critério comum, a explosão pode ser refeita |
| 2 | **Liberacao de 5 fichas** já solicitadas | ⬜ | SMF | entrega parada |
| 3 | **Liberacao das fichas 0640, 0525 e 1153** | ⬜ | SMF — Enerwatt | bloqueia toda a entrega Enerwatt |
| 4 | ⬜ | | | |

⬜ *Acrescentar: aceite (ou não) dos itens de inversores/retificador da Sala Segura sem
explosão — hoje e uma tentativa, não um acordo.*

---

# Parte V — Cronograma

⬜ *Deliberadamente vazio nesta versão.*

Quando for preenchido, o insumo está em [[Plano de Acao - Aplicacao LMR]]:
- taxa de **5 fichas por dia-pessoa** (1 pessoa, 4 h/dia), calibrada pelo CCAR;
- balanceamento por **equipe de engenharia**, não por volume;
- cenarios de 1, 2 e 3 pessoas.

---

# Anexo — Notas de método

### Contagem: código PMIB distinto, nunca linha

> [!danger] Erro corrigido em 31/08/2026
> Dentro de uma mesma lista, **o mesmo item pode aparecer em mais de uma linha, mas e um
> único código PMIB — logo, uma única ficha.** Contar linhas superestima o trabalho.

| Lista | Linhas | **Fichas (PMIB distintos)** | Diferença |
|---|---:|---:|---:|
| RV Hidráulico | 164 | **142** | −22 |
| Painéis | 97 | **64** | −33 |
| Selo do Eixo | 36 | **10** | **−26** |
| Sala Segura | 38 | **38** | 0 |
| Inversores e PDE | 60 | **48** | −12 |
| Aeração Axial | 24 | **14** | −10 |
| **Total das 13 listas** | **719** | **607** | **−112** |

A contagem por PMIB **bate com a realidade relatada na reunião**: o Selo do Eixo tem
**10** fichas — exatamente os "4 entregues + 6 restantes" citados por Itaipu. A contagem
por linha daria 36.

### Linhas de conjunto

Na lista de preços ha **dois** tipos de linha sem item próprio, que não devem ser
confundidos:

| | `TIPO DE ENTREGA` | Tem código GE? | Tem PMIB? | O que e |
|---|---|---|---|---|
| **Cabeçalho de categoria** | *(vazio)* | não | não | agrupamento visual: `INSTRUMENTACAO`, `EQUIPAMENTOS`... |
| **Linha de conjunto** | **`TITULO`** | **sim, as vezes dois** | `N/A` | a engenharia criou como **conjunto**, mas ha **rastreabilidade interna** dos itens que o compoem — e esses itens podem, por sua vez, ser equipamentos explodiveis |

Exemplo real (`#ST00=M00MEU10&MPB020-01`): os itens 4, 5, 6 e 7 —
`CONJUNTO MOTOBOMBA REGULACAO` e `CONJUNTO MOTOBOMBA INFILTRACAO` — são linhas de
conjunto, com dois códigos GE cada e PMIB `N/A`.

## Relacionados
[[Plano de Acao - Aplicacao LMR]] · [[Entrega Documental e Explosao de Itens]] ·
[[Fluxo Macro de Entrega]] · [[Secao - Aplicacao LMR]] · [[Lista de Precos]]

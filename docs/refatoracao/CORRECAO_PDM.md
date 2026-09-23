# Correção de PDM preservando as características técnicas

> **Estado: PLANO APROVADO, nada implementado.** A Parte I é o levantamento; a
> Parte II traz as decisões do usuário (2026-09-23) e o plano em seis etapas.
>
> Pedido do usuário em 2026-09-23: *"sempre que faço atualização ou troca
> (atualização acaba também sendo troca de pdm) todas as características
> técnicas salvas no portal se perdem, e ficam em branco, mesmo aquelas que não
> mudaram [...] queria criar um módulo de correção de pdm onde eu possa
> reaproveitar essas características já subidas no portal"*.

---

## 1. O problema, na mecânica do portal

Trocar o PDM de uma ficha abre este modal (já documentado em
`docs/PORTAL_COMO_ELE_SE_COMPORTA.md` §3):

> **Trocar PDM** — Você tem certeza? Todos os dados de Características Técnicas
> serão removidos. Deseja continuar? **[CONFIRMAR] [CANCELAR]**

O portal cumpre o que promete: **apaga todas**, inclusive as que o PDM novo
também tem e que continuariam válidas. Não é defeito do SIG-FT; é como o PMIB
funciona. O que o módulo faz é fotografar antes e repor depois.

Vale para os dois casos, e o usuário tem os dois agora:

| Caso | Volume atual | O que muda |
|---|---|---|
| **Atualizar a revisão** (mesmo código, R1 → R2) | ~25 fichas | o portal trata como troca e apaga tudo |
| **Trocar o PDM** (código diferente) | alguns | além de apagar, o conjunto de características muda |

---

## 2. O que JÁ EXISTE no app — quase tudo

Esta é a razão pela qual o módulo é viável: ele é, em grande parte, orquestração
de peças que já rodam contra o portal real há meses.

| Peça | Onde mora | O que resolve |
|---|---|---|
| Achar e abrir a ficha em edição | `PMIBPortal.pesquisar_e_abrir` | retry 3×, `StaleElement`, timeout. Usada por 6 módulos |
| Abrir a aba de características | `sel.XPATH_CARACTERISTICAS_ABA` | `//button[@role='tab' and contains(., 'Características técnicas')]` |
| **Varrer a tabela paginada** | `duplicadas_injetor.limpar_caracteristicas` | o laço completo: paginação, e o índice que **não avança** quando a linha some (a tabela encolhe) |
| **Descobrir o tipo da linha** | `tech_specs._tipo_da_linha` | pergunta à TELA: `CHAR` / `NUM` / `INT` / `LISTA`. A ordem importa (INT antes de NUM) |
| **Escrever uma linha** | `tech_specs._preencher_linha` | os 4 tipos, com auditoria de escrita |
| **Trocar o PDM** | `duplicadas_pdm.garantir_pdm` | combo `vscomp`, salva, **relê para provar** que ficou |
| Salvar esperando o toast | `PMIBPortal.salvar_e_confirmar` | com âncora de seção, para não pegar o SALVAR errado |
| Combos de unidade e lista | `tech_specs.selecionar_dropdown_unidade` / `_lista` | tenta PT e ES |
| Excluir linha com confirmação | `PMIBPortal.excluir_linha_com_confirmacao` | |
| Catálogo de PDMs | `core/pdm_catalogo` | código, classe, características, revisão vigente |

E três armadilhas já pagas, que o módulo novo herda de graça:

1. **O blur do OutSystems.** Nem `fill` do Playwright nem `send_keys` do Selenium
   disparam `change` — ele nasce do BLUR. Sem clicar fora, o texto fica na caixa,
   o servidor nunca soube dele, e **o SALVAR grava o valor antigo sem erro
   nenhum**. `limpar_caracteristicas` já faz o `click_nativo` no campo vizinho.
2. **`click_nativo` ≠ `click_raw`.** O clique por JavaScript dispara o evento mas
   não executa os passos de foco do navegador — ou seja, não tira o foco do
   textarea, que é justamente o que se quer.
3. **A descrição TEM de ser lida por `textContent`.** Numa tabela rolável, a
   célula fora da viewport devolve string vazia em `.text`. `RPAEngine.texto()`
   já garante isso nos dois motores.

### Os seletores das colunas (já existem, em dois lugares)

| Campo | XPath relativo à linha |
|---|---|
| Descrição | `.//td[contains(@data-header, 'Descrição')]` |
| Valor PT | `.//textarea[contains(@id, "TextArea_ValuePT")]` |
| Valor ES | `.//textarea[contains(@id, "TextArea_ValueES")]` |
| Numérico | `.//input[contains(@id, "NumberValue_Input")]` |
| Intervalo mín/máx | `.//input[contains(@id, "MinValue_Input")]` / `MaxValue_Input` |
| Lista | `.//select[contains(@id, "Dropdown1")]` |
| Subtipo de intervalo | `.//select[contains(@id, "Dropdown_IntervalOptions")]` |
| Unidade | `.//select[contains(@id, "DropdownTCUnitsOfMeasurement")]` |

⚠️ **Eles estão DUPLICADOS** entre `core/rpa/seletores_duplicada.py` e
`services/tech_specs.py`. O módulo novo precisa deles também — seria o terceiro
lugar. Isso é oportunidade de unificação (ver §6).

---

## 3. O que FALTA — o pedaço genuinamente novo

Só quatro coisas, e a primeira é o coração:

1. **LER uma linha de característica** — o inverso exato de `_preencher_linha`.
   Dado o tipo, ler valor PT, valor ES, unidade, mín/máx, subtipo. Hoje o app só
   sabe **escrever** e **apagar**; ler valor de característica não existe.
2. **Gravar o retrato em disco ANTES de trocar.** Não é zelo: depois do
   CONFIRMAR, o dado não existe mais no portal. Se o robô morrer entre a troca e
   a reposição, o retrato em memória morre junto e a ficha fica vazia.
3. **Casar antigo ↔ novo** (ver §4).
4. **Orquestração + tela** — serviço `correcao_pdm.py` + view, no padrão do
   projeto.

---

## 4. A chave do casamento: o CÓDIGO da característica

O portal mostra a descrição no formato **`<código>-<NOME>`**. Duas provas
independentes:

- `tech_specs.limpar_pergunta` usa o regex `^\d+\s*-\s*(.*)` — e **descarta** o
  código para casar pelo nome;
- o relatório de recomendações da Itaipu escreve "1308-SECCION DEL CONDUCTOR" e
  "1064-Corriente Nominal".

Medido no Master real (1193 PDMs, revisão vigente de cada):

| | |
|---|---|
| códigos de característica distintos | **2278** |
| nomes distintos | **2278** |
| códigos com mais de um nome | **0** |
| nomes sob mais de um código | **0** |

É uma **bijeção perfeita**. Casar por código ou por nome dá hoje o mesmo
resultado — mas o código é a chave certa mesmo assim, por três motivos:

1. é imune a tradução (a tela alterna PT/ES);
2. é imune a renomeação futura — e a Itaipu **está** mexendo em nome e formato
   de características ("ajusta la característica FRECUENCIA NOMINAL para texto
   libre");
3. o nome vira **conferência**: se código bate e nome não, o módulo tem como
   avisar em vez de repor calado.

---

## 5. Quanto se recupera — medido, não estimado

### Atualização de revisão (o caso das 25 fichas de agora)

| | |
|---|---|
| PDMs com mais de uma revisão | 1023 de 1193 |
| reaproveitamento por código | **mediana 100%, média 89%** |
| PDMs onde a revisão nova mantém 100% dos códigos | 557 |
| PDMs onde sobra menos da metade | 35 |

Os três PDMs que a Itaipu cobrou, no Master atual (desatualizado):

| PDM | revisões no Master | reaproveitável |
|---|---|---|
| `PDM.5920.020` | R0 (17 caract.) → R1 (28) | 13 — **76%** |
| `PDM.5925.001` | R0 (63) → R1 (47) | 36 — **57%** |
| `PDM.5925.008` | só R0 | o Master novo dirá |

### Troca de PDM (código diferente)

| Troca | origem → destino | reaproveitável |
|---|---|---|
| `PDM.5925.001` → `PDM.5925.008` | 47 → 19 | 15 |
| `PDM.3010.800` → `PDM.4320.031` | 22 → 17 | 4 |
| `PDM.4820.002` → `PDM.4820.004` | 29 → 29 | 14 |

**Conclusão honesta: o módulo não devolve 100% numa troca de PDM** — tipicamente
30 a 50%. O que ele garante é que *nada do que era reaproveitável se perde*, e
que o que **não** casou sai numa lista explícita, em vez de sumir em silêncio.

---

## 6. Riscos, e o que cada um exige

| Risco | Por que importa | Como tratar |
|---|---|---|
| **Perder o retrato no meio** | depois do CONFIRMAR o dado só existe no arquivo | gravar em disco **antes** de trocar; e o módulo deve poder rodar "só repor" a partir de um retrato salvo |
| **O tipo muda entre revisões** | medido: 8 características do `PDM.4820.015` trocaram de tipo entre r0 e r1 | o "recuo de tipo" de `_preencher_linha` já resolve — reusar, não reinventar |
| **Valor não cabe no campo novo** | `NUM` aceita 2 casas em 6060 das 6085 linhas do Master | o transbordo para `CARACTERISTICAS ADICIONAIS` já existe em `tech_specs.realocar_por_casas_decimais` |
| **Opção de LISTA não existe no PDM novo** | o valor antigo pode não ser opção válida | não repor; listar como pendência. Repor errado é pior que deixar vazio |
| **O modal trava a página** | nenhum clique passa enquanto ele está aberto, e o log culpa o botão errado | `garantir_pdm` já confirma; manter o padrão `//*[@role='dialog']` |
| **Seletores em 3 lugares** | manutenção divergente | unificar em `core/rpa/` antes de crescer (ver abaixo) |
| **Nada disso é prova de portal** | `check.sh` verde roda contra dublês | roteiro de teste numa ficha de mentira, em sessão local, antes de tocar as 25 |

---

## 7. Desenho proposto (para discussão)

```
sigft/core/rpa/caracteristicas.py     (NOVO) os seletores das colunas, num lugar só
sigft/services/correcao_pdm.py        (NOVO) ler / casar / repor — a regra
sigft/app/views/correcao_pdm.py       (NOVO) a tela
```

Fluxo por ficha:

```
1. abrir a ficha           PMIBPortal.pesquisar_e_abrir          (existe)
2. ler o PDM atual         duplicadas_pdm.pdm_atual              (existe)
3. LER as características  ← O PEDAÇO NOVO
4. gravar o retrato        Documentos\SIG-FT\retratos\<pmib>.json
5. trocar o PDM            duplicadas_pdm.garantir_pdm           (existe, generalizar)
6. salvar + confirmar      PMIBPortal.salvar_e_confirmar         (existe)
7. reler a tabela nova     (o mesmo leitor do passo 3)
8. casar por CÓDIGO        ← O PEDAÇO NOVO
9. repor o que casou       tech_specs._preencher_linha           (existe)
10. salvar + conferir      PMIBPortal.salvar_e_confirmar         (existe)
11. relatar                reposto / não casou / falhou
```

O passo 4 é o que permite um modo **"só repor"**: se algo der errado depois da
troca, o retrato continua no disco e a reposição roda sozinha, sem refazer nada.

---

## 8. Decisões que dependem do usuário

1. **De onde vem a lista de fichas a corrigir?** Da planilha `_STATUS_PMIB`
   (com uma coluna de "PDM novo"), de uma seleção na tela, ou das duas?
2. **O que fazer com o que não casou?** Deixar em branco e listar, ou tentar
   aproximar por nome quando o código não existir no PDM novo?
3. **Conferência antes de gravar?** Mostrar o "de → para" numa tela de revisão
   antes de mexer no portal, ou seguir direto com relatório no fim?
4. **Unificar os seletores agora** (mexe em `tech_specs` e `duplicadas`, que
   rodam hoje) ou duplicar por ora e unificar depois?

---

## 9. Melhorias avistadas no `tech_specs` (para outro momento)

O usuário pediu para citar sem desenvolver. Anotadas ao ler o módulo:

- `processar_lista` marca a ficha como COMPLETO **incondicionalmente**, mesmo
  com pendências já registradas (já está em `PENDENCIAS.md`, 2026-08-18);
- as entradas `REMOVER` no JSON são o que limpa o portal — não podem ser
  retiradas sem antes resolver o Master (já registrado, e o usuário **rejeitou**
  o redesenho em 2026-08-19: correção incremental guiada por caso real);
- `limpar_pergunta` joga fora o código da característica, que é a melhor chave
  que existe — a mesma descoberta que sustenta este módulo;
- `indexar_por_caracteristica` resolve o conflito de revisões no JSON, mas a
  causa raiz é o Master trazer todas as revisões (ligado ao item acima);
- não há leitura de valor de característica — o app só escreve e apaga. Este
  módulo cria a peça que falta, e ela serve ao `tech_specs` também (permitiria
  "só preencher o que está vazio", em vez de reescrever tudo).

---

# PARTE II — Decisões e plano (2026-09-23)

## 10. As decisões, respondidas

| # | Pergunta | Resposta do usuário |
|---|---|---|
| 1 | De onde vem o PDM novo? | **Seleção na tela.** Carrega o `_STATUS_PMIB`, seleciona as fichas, e precisa de *"um jeito sofisticado de poder colocar o novo pdm dessas fichas"* |
| 2 | O que não casou? | **Listar sempre**, com o valor em **PT e ES**, *"pra não perdermos nada"* |
| 3 | Tela de revisão antes? | delegada a mim — decidida abaixo |
| 4 | Unificar os seletores? | **Não agora.** O mais seguro, e registrar em `PENDENCIAS.md` o que seria o certo |

E dois requisitos novos:

5. **Prevenir a mudança de tipo** entre revisões (§11);
6. **Apagar as características que ficaram em branco** ao final, e **relatar** as
   que ficaram em branco de cada ficha.

### Decisão 3, tomada: prévia calculada, sem revisão característica a característica

**Não** haverá uma tela de aprovação por característica. Três razões:

- com 25 fichas × dezenas de características, a revisão interativa seria mais
  cara do que o trabalho manual que o módulo veio eliminar;
- a **prévia sai do catálogo, sem tocar o portal e sem risco**: já sabemos, de
  graça, quais códigos o PDM novo tem. Dá para dizer *"desta ficha, 36 das 63
  características casam; 27 não existem no PDM novo"* **antes** de qualquer
  clique;
- o ponto de confirmação passa a ser a **tela de mapeamento** (§12, E5), que o
  usuário já precisa ver para escolher o PDM novo. Uma tela, não duas.

A rede continua sendo o **retrato em disco**: se algo der errado depois da
troca, a reposição roda de novo a partir do arquivo.

---

## 11. A mudança de tipo — medida, e o que ela obriga

Preocupação do usuário: *"em novas revisões algumas características mudaram de
tipo, antes era NUM e viraram CHAR na nova revisão (é o caso mais comum)"*.

Medido no Master, entre a revisão mais velha e a vigente de cada PDM:

| | |
|---|---|
| características presentes nas duas revisões | 8841 |
| **que mudaram de tipo** | **3160 — 35,7%**, em 748 PDMs |

Ou seja: **a preocupação é mais do que justificada — é um terço das linhas.**

As direções, no conjunto R0→R1 (1023 PDMs):

| De → Para | Ocorrências |
|---|---|
| CHAR → NUM | 2659 |
| CHAR → INT | 291 |
| CHAR → LISTA | 207 |
| NUM → INT | 2 |
| **NUM → CHAR** | **1** |

> ⚠️ **Limite honesto deste número.** O usuário está vivendo **R1 → R2** (a
> Itaipu já pede R2), e o Master que tenho só tem essa transição em **56 PDMs**
> — contra 1023 de R0→R1. Então a direção dominante que eu observo pode
> simplesmente não ser a que ele vê. Na amostra de R1→R2 que existe, aparecem as
> duas: CHAR→NUM (59), mas também **NUM→CHAR (3)** e **INT→CHAR (3)**.
>
> **Conclusão de desenho: as seis direções acontecem.** O módulo não pode
> apostar em nenhuma.

### O que isso obriga

1. **Nunca confiar no tipo do retrato.** Depois da troca, perguntar à TELA qual
   o tipo da linha nova — `tech_specs._tipo_da_linha` já faz exatamente isso, e
   nasceu deste mesmo problema.
2. **Uma matriz de conversão explícita**, e a regra de ouro: *converter só
   quando a conversão é sem perda e sem ambiguidade; no resto, não repor e
   listar*. Repor um valor plausível e errado é pior que deixar vazio — é a
   mesma lição do prompt de Condições (2026-08-18).

| De → Para | O que fazer | Por quê |
|---|---|---|
| **igual** | repor direto | caso comum |
| NUM → CHAR | **converter**: número + unidade viram texto (`juntar_para_char`, já existe) | sem perda |
| INT → CHAR | **converter**: "mín a máx + unidade" vira texto | sem perda |
| LISTA → CHAR | **converter**: a opção vira texto | sem perda |
| CHAR → NUM | **tentar**: só se o texto for um número puro. Senão, listar | "Aço inox" não vira número |
| CHAR → LISTA | **tentar**: só se o texto casar uma opção (PT ou ES). Senão, listar | inventar opção é inventar dado |
| CHAR → INT | **listar** | "de -10 a 50" exige interpretar; não é determinístico |
| NUM → INT | **listar** | um valor só não define uma faixa |
| NUM/INT → LISTA | **tentar** casar opção; senão listar | |
| qualquer → tipo desconhecido | **listar** | tipo novo do portal não pode virar palpite |

O `tech_specs` já tem duas peças desta matriz, e elas devem ser **reusadas, não
reescritas**: `juntar_para_char` (junta valor + unidade + subtipo) e
`realocar_por_casas_decimais` (o transbordo quando o número não cabe em 2 casas
— 6060 das 6085 linhas `NUM` do Master aceitam exatamente 2).

---

## 12. O plano

Seis etapas. As cinco primeiras são **testáveis sem portal**; a sexta é a única
que exige sessão local, e nada se declara pronto antes dela.

| Etapa | Estado | Onde |
|---|---|---|
| E1 — leitor da tabela | ✅ feita | `sigft/core/rpa/caracteristicas.py` |
| E2 — retrato em disco | ✅ feita | `sigft/services/correcao_pdm_retrato.py` |
| E3 — casamento e conversão | ✅ feita | `sigft/services/correcao_pdm_casamento.py` |
| E4 — portal + serviço | ✅ feita | `sigft/services/correcao_pdm_portal.py` + `correcao_pdm.py` |
| E5 — tela | ✅ feita | `sigft/app/views/correcao_pdm.py` + `services/correcao_pdm_planilha.py` |
| E6 — portal real | **pendente — é a única que prova** | roteiro em [`docs/ROTEIRO_CORRECAO_PDM.md`](../ROTEIRO_CORRECAO_PDM.md) |

> ⚠️ Verde nas cinco primeiras **não é prova de portal**: elas rodam contra
> dublês escritos pelo próprio Claude. Só a E6 prova.

### E1 — O leitor de características (`core/rpa/caracteristicas.py`)

O pedaço que não existe: o inverso de `_preencher_linha`.

- os seletores das colunas num módulo só (copiados, **não** movidos — decisão 4);
- `ler_linha(engine, seletor_linha) -> Caracteristica` com
  `codigo`, `nome`, `tipo` (perguntado à tela), `valor_pt`, `valor_es`,
  `unidade`, `minimo`, `maximo`, `subtipo`;
- `ler_tabela(portal) -> list[Caracteristica]`, com a paginação e a leitura por
  `textContent` — o laço é o de `limpar_caracteristicas`, sem o apagar;
- `codigo_e_nome("1064-CORRENTE NOMINAL") -> ("1064", "CORRENTE NOMINAL")`.

**Aceite:** testes com dublê de engine cobrindo os 4 tipos, a paginação, a
descrição vazia (linha fora da viewport) e o formato `<código>-<NOME>`.

### E2 — O retrato em disco

- grava em `Documentos\SIG-FT\retratos_pdm\<PMIB>_<data>.json`
  (via `dados_usuario.resolver_config`, a regra do mural de 2026-09-21);
- guarda: PMIB, PDM antigo (com revisão), PDM novo pretendido, e a lista de
  características com **PT e ES** (decisão 2);
- **grava ANTES de trocar** — depois do CONFIRMAR o dado não existe mais no
  portal;
- lê de volta, para o modo "só repor".

**Aceite:** ida e volta sem perda, incluindo acento e texto multilinha.

### E3 — Casamento e conversão (regra pura, sem portal)

O coração, e onde mora o risco de perder dado em silêncio.

- `casar(retrato, caracteristicas_novas) -> Plano` com quatro listas:
  **repor** / **converter** / **nao_casou** / **sem_valor**;
- casamento por **código**, nome como conferência (divergência vira aviso);
- a matriz de tipos da §11;
- as que ficaram sem valor entram na lista de **apagar** (requisito 6).

**Aceite:** um teste por linha da matriz, mais os casos reais medidos
(`PDM.5920.020` R0→R1: 13 de 17; `PDM.5925.001`: 36 de 63).

#### O que a implementação acrescentou à matriz

Três pontos que a §11 não previa e que saíram de testes:

1. **`CHAR → NUM` aceita também "número + símbolo", em três casos fechados.**
   A §11 dizia "só número puro". O acréscimo é o caminho de volta do recuo de
   2026-08-18: `"220 V"` com unidade `AD` é exatamente o que
   `juntar_para_char` escreve quando o robô cai de NUM para CHAR, e `AD` não
   carrega informação. Também vale quando o símbolo do texto **é** a unidade
   já gravada. Quando o símbolo **contradiz** a unidade (texto `"220 V"`,
   unidade `A`), volta a ser `listar`: os dois não podem estar certos.
2. **A pendência guarda valor e unidade em campos SEPARADOS.** Colá-los num
   texto só fazia uma linha `CHAR` com texto `"220 V"` e unidade `A` virar
   `"220 V A"` no relatório — um valor que nunca esteve na ficha. Quem junta
   os dois é a linha do relatório (`"220" [V]`), e ela omite a unidade quando
   é `AD`.
3. **`chave()` é exportada.** É a mesma função que a E4 usa para reencontrar a
   linha na tela. Se o serviço calculasse a dele, uma diferença de
   normalização faria a reposição pular linhas em silêncio.

`CHAR → INT` continua **listado**, como a §11 decidiu — mesmo quando o texto
tem a forma `"-10 / 50"`, que seria decodificável. Ver `PENDENCIAS.md`.

### E4 — O serviço (`services/correcao_pdm.py`)

Orquestra, com dublê de portal nos testes:

```
abrir → ler PDM atual → LER (E1) → gravar retrato (E2) →
trocar PDM → salvar → reler tabela nova (E1) → casar (E3) →
repor → apagar as vazias → salvar → relatar
```

Regras de ordem que não são detalhe:

- **apagar só DEPOIS de repor** — apagar antes eliminaria linhas que iam receber
  valor;
- **não trocar o PDM se o retrato não gravou** — sem rede, não salta;
- **não apagar nada se a reposição falhou** — melhor uma ficha com linhas vazias
  do que uma ficha sem as linhas.

#### O que a implementação acrescentou

A E4 saiu em dois arquivos: `correcao_pdm_portal.py` (as duas operações de
portal que faltavam) e `correcao_pdm.py` (a ordem e as recusas). Cinco pontos
que o plano não previa, todos vindos de teste:

1. **"Já é o PDM certo" não se decide pelo código.** O caso das 25 fichas é
   mesmo código com revisão diferente: um guard por código diria "já está
   certo" e não faria nada, calado, nas 25. Quem decide é o confronto entre o
   que a ficha tem e **o que o combo oferece** — os dois textos completos, com
   a revisão. O outro lado importa igual: ficha já na revisão vigente **não é
   tocada**, porque trocar apagaria as características para chegar ao mesmo
   lugar.
2. **Uma quarta recusa**, que não estava no plano: *não apagar nada quando o
   retrato tinha valores e nenhum voltou*. Isso não é "não havia o que
   reaproveitar" — é o sintoma de uma leitura quebrada, e nesse estado apagar
   as "vazias" apagaria a ficha inteira. É a proteção que a `PENDENCIAS.md` da
   E3 pediu.
3. **O SALVAR que não confirma impede o apagamento.** Ignorar o retorno era um
   defeito de verdade: os valores repostos ficam na TELA, e a exclusão de uma
   linha chega ao servidor na hora — a ficha terminaria com as linhas apagadas
   e a reposição perdida.
4. **"Apaguei" não é prova de que sumiu.** O laço de exclusão de propósito não
   avança o índice (a linha de baixo sobe para o lugar). Um `True` mentiroso
   travava o app para sempre, sem mensagem; conferir a contagem custa uma
   chamada. Há teste que **não termina** sem o guard.
5. **O modo "só repor"** (`repor_do_retrato`) foi implementado junto: é o que
   dá razão ao retrato em disco. Ele **não** troca o PDM — nesse ponto ele já
   está certo, e trocar de novo apagaria tudo outra vez, com o segundo retrato
   saindo da ficha vazia.

`tech_specs._preencher_linha` é **reusada inteira**, com o engine do portal já
aberto anexado a uma `TechSpecsAutomation` (que não abre navegador no
`__init__`). São duzentas linhas de regra nascidas de falha real — o blur do
OutSystems, a auditoria com injeção forçada, a lista em PT e ES, a unidade
pelos parênteses — e uma cópia divergiria na primeira correção. Há teste que
reprova se `TechSpecsAutomation()` passar a abrir navegador.

⚠️ E um guard novo: **os três lugares com os seletores da tabela têm de
continuar iguais** (`test_correcao_pdm_portal.py`). A unificação segue adiada
por decisão do usuário, mas agora um seletor ajustado num lugar e não nos
outros reprova, em vez de fazer o robô LER de um elemento e ESCREVER noutro.

**Aceite:** o dublê prova a ordem, e prova que uma falha em qualquer passo
**interrompe** antes do passo destrutivo seguinte.

### E5 — A tela (`app/views/correcao_pdm.py`)

O *"jeito sofisticado"* da decisão 1:

| Ficha | Descrição | PDM atual | **PDM novo** | Prévia |
|---|---|---|---|---|
| …0242 | PROTETOR SURTO | PDM.5920.020 R1 | *(a definir)* | — |

Com três ações em massa sobre as linhas selecionadas:

- **"Só atualizar a revisão"** — copia o código atual para o PDM novo. **É o
  caso das 25 fichas: um clique resolve todas**, porque o portal já atribui a
  revisão vigente sozinho;
- **"Escolher PDM…"** — abre a `JanelaEscolherPDM` (já existe, com busca sobre
  o catálogo, classe e características à vista) e aplica às selecionadas;
- **"Limpar"**.

A coluna **Prévia** é calculada do catálogo, sem tocar o portal: *"36 de 63
casam"*. É o que dá ao usuário a decisão informada antes de qualquer clique.

#### O que a implementação acrescentou

**A prévia se recusa a dar um número na atualização de revisão.** O catálogo
guarda só a revisão vigente de cada PDM; numa atualização o código é o mesmo
dos dois lados, então comparar catálogo com catálogo daria "100%" sempre — um
número bonito e vazio, porque o que a ficha tem é a revisão ANTIGA, que o
catálogo não tem. Prévia que mente é pior que prévia ausente: é justamente ela
que o usuário olha antes de autorizar uma operação que apaga características.
Então ela diz o que sabe ("só a revisão: o portal atribui a vigente") e, para
um PDM fora do catálogo, diz que não sabe — em vez de "0 de N", que se leria
como "não recupera nada".

**Sem seleção, a ação em massa vale para todas.** Obrigar a selecionar 25
linhas para aplicar a ação que resolve as 25 seria o oposto do "um clique".

**Dois guards novos nos testes, e nenhum deles é sobre esta tela:**

1. **toda tela registrada em `main.py` tem de ter botão na barra lateral e card
   na home** (e vice-versa). Uma tela que existe, compila e passa nos testes
   mas não aparece em lugar nenhum não é pega por nenhuma das três partes da
   verificação do `CLAUDE.md` — o app abre normalmente, só que sem ela;
2. **toda chamada a `file_dialogs` na UI tem de bater com a assinatura real.**
   Isto nasceu de um erro concreto: a primeira versão desta tela chamava
   `ask_open_file("chave", title="...")` — sem o argumento `categoria` e com
   `title` em vez de `titulo`. Compila, passa no `pyflakes`, passa em tudo, e
   levanta `TypeError` no primeiro clique. Quem pegaria é o `--smoke`, que não
   roda em ambiente sem tkinter; conferir a assinatura pega a mesma classe de
   defeito sem precisar de janela.

⚠️ **A terceira parte da verificação do `CLAUDE.md` (abrir o app) continua
pendente**: este ambiente não tem `tkinter` nem `customtkinter`, então
`python frontend.py --smoke` não roda aqui. `compileall` e `pyflakes` (partes 1
e 2) estão verdes, e o guard de fiação cobre o caso do widget órfão que o CP
5.5 pagou — mas **abrir o app é do usuário**, antes da E6.

### E6 — Validação no portal real (sessão local)

Roteiro, nesta ordem:

1. **uma ficha de mentira**, atualização de revisão — conferir que o retrato
   gravou, que as características voltaram, e que as vazias sumiram;
2. **uma ficha de mentira**, troca de PDM de código diferente — conferir o
   relatório do que não casou;
3. uma ficha **real** das 25, conferida à mão contra o retrato;
4. só então o lote.

⚠️ `scripts/check.sh` verde não é prova de portal. Nada acima se declara pronto
sem esta etapa.

---

## 13. O relatório (requisito 2 + 6)

Um arquivo por lote, ao lado dos retratos, e o resumo no console. Por ficha:

| Seção | Conteúdo |
|---|---|
| Reposto | código, nome, valor PT, valor ES |
| Convertido | idem + o tipo de origem e destino, e a conversão aplicada |
| **Não casou** | código, nome, **valor PT e ES** — o que se perderia sem esta lista |
| **Ficou em branco** | as linhas do PDM novo sem valor (apagadas), para conferência |
| Falhou | o que o portal recusou, com o motivo |

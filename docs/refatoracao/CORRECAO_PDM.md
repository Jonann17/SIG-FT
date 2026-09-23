# Correção de PDM preservando as características técnicas

> **Estado: LEVANTAMENTO.** Nada implementado ainda. Este documento reúne o que
> já existe no app, o que falta, os números medidos e as decisões abertas —
> para que o plano seja discutido com o usuário sobre fatos, não sobre palpite.
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

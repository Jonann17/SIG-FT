---
tags: [gestao-v2, power-bi, handoff]
criado: 2026-10-01
atualizado: 2026-10-04
---

# Power BI v2 — como montar

> [!success] MONTADO e testado em 05/10/2026
> Está no Box em **`SOBRESSALENTES - PMIB/Sobressalentes v2 (Power BI)/`** como *Projeto do Power BI*:
> - `Sobressalentes v2 - Interno.pbip` (5 páginas) e `Sobressalentes v2 - Itaipu.pbip` (2 páginas), sobre um
>   modelo só (`Sobressalentes v2.SemanticModel`).
> - **Abrir**: Power BI Desktop › Arquivo › Abrir › o `.pbip` › **Página Inicial › Atualizar** (≈ 1 min na primeira vez).
> - O parâmetro `PastaPMIB` aponta para `C:\Users\560083605\Box\...\SOBRESSALENTES - PMIB`. Se o usuário do Windows
>   for outro: Transformar dados › Gerenciar parâmetros › PastaPMIB.
> - Arquivo único: Arquivo › Salvar como › `.pbix`.
> - Testado aqui com os dados reais (os 47 `_STATUS_PMIB` e a mapeadora): as 7 tabelas atualizam e as medidas batem
>   com a referência em Python (1.649 linhas, 615 emitidas, 73 aprovadas, 580 autorizadas, 88 aguardando, 53
>   atrasadas, 62 que não precisam de autorização). "Fichas" = PMIB distinto (1.352; 5 fichas aparecem em duas listas).
> - Gerado por `montar_pbip.py` a partir destes `.pq` e do `05 - Medidas.dax`: mudou a regra, rode de novo.
> - O `Sobressalentes - Dashboard.pbix` antigo **deixou de atualizar** (a mapeadora não tem mais as colunas de
>   contagem, decisão de 05/10); ele mostra os últimos dados carregados até ser aposentado.

O roteiro abaixo é o que o gerador faz — serve para entender ou montar à mão.

O protótipo `_gerado/prototipo-dashboard.html` mostra o resultado esperado com os dados reais.
Este roteiro reproduz o mesmo painel no Power BI Desktop. As regras são as de
`_scripts/regras_sobressalentes.py`. **Situação da autorização e dias de atraso são calculados
pelo SIG-FT** e gravados no `_STATUS_PMIB`; o Power BI só lê (decisão de 04/10/2026).

> [!info] Layout do `_STATUS_PMIB` que este pacote lê (04/10/2026)
> `... APLICAÇÃO - LMR | TIPO DE ENTREGA | DATA DO EMAIL | SITUAÇÃO DA AUTORIZAÇÃO | DIAS DE ATRASO |
> EQUIPAMENTO ENTREGUE | FORNECEDOR | PROCUREMENT | OBSERVAÇÕES`, mais a linha
> "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO" acima do cabeçalho.
> - `SITUAÇÃO DA AUTORIZAÇÃO` substituiu `APTO PARA ENTREGA` (SIM = AUTORIZADO). Valores:
>   AGUARDANDO ITAIPU · ATRASADO ITAIPU · AUTORIZADO · **N/A**. **Só FÍSICA E DOCUMENTAL precisa de
>   autorização**: DOCUMENTAL (componente) e TÍTULO (agrupamento) = N/A; TIPO vazio aparece no painel
>   como "SEM TIPO DE ENTREGA" e não conta. Arquivo antigo cai no APTO.
> - `DIAS DE ATRASO` = dias corridos além do prazo de 15 dias úteis do e-mail; congela quando
>   Itaipu autoriza (por isso `Autorizadas com Atraso` = autorizada com dias > 0).
> - Não há data de autorização nem coluna de prazo: o prazo é regra, não dado.

## O que muda em relação ao `Sobressalentes - Dashboard.pbix` atual

| Hoje | v2 |
|---|---|
| Uma tabela: a aba principal da mapeadora (contagens por lista) | Tabela fato **Itens** lida direto dos `_STATUS_PMIB`, uma linha por material |
| Os números só ficam certos depois de rodar o SIG-FT | Atualizou o `_STATUS_PMIB`, o Power BI já vê |
| Caminho fixo `C:\Users\560083605\Box\...` | Parâmetro **PastaPMIB** — cada máquina põe o seu |
| Funil misturando etapas que correm em paralelo | Barras empilhadas por etapa e por "com quem está" |
| "Atraso de Itaipu" contado pelo SIG-FT com 14 dias corridos | situação e dias de atraso **calculados pelo SIG-FT** (15 dias úteis) e lidos do `_STATUS_PMIB` — o Power BI não calcula dias úteis |
| Sem tempo, sem tipo de entrega, sem valor | Situação da autorização, dias de atraso, LMR, tipo de entrega, valor US$ |
| Revisão em uso digitada à mão na mapeadora | Lida da linha de revisão de cada `_STATUS_PMIB` (`Listas[Revisao em Uso]`), com alerta de revisão desatualizada |
| Uma página interna copiada numa segunda, com gráfico de preço apontando para a coluna errada | Dois relatórios: **Interno** e **Itaipu** |

## Passo a passo (≈ 1 h na primeira vez)

1. **Novo arquivo** no Power BI Desktop.
2. **Consultas** — Página Inicial › Transformar dados › Nova Fonte › Consulta Nula ›
   Editor Avançado. Para cada bloco `// CONSULTA: Nome` dos arquivos `.pq`, cole o bloco e
   renomeie a consulta com o mesmo nome. Ordem:
   - `00` — `PastaPMIB` (parâmetro: **troque o caminho**), `DataReferencia`, `fxNorm`, `fxPMIB`,
     `fxLerTabela`, `fxData`, `fxStatus`, `fxTipoEntrega`, `fxRevisaoEmUso`
   - `01` — `Calendario`
   - `02` — `PrecosArquivos`, `PrecosPorPMIB`, `PrecosAconex`
   - `03` — `Itens`
   - `04` — `Listas`, `Atividades`, `Eventos`, `ListaEvento`
3. **Desabilite o carregamento** (clique direito › Habilitar carga) de: funções, `DataReferencia`,
   `PrecosArquivos`, `PrecosPorPMIB`. Fechar e aplicar.
4. **Relacionamentos** (Exibição de modelo):

   | De (muitos) | Para (um) | Filtro cruzado |
   |---|---|---|
   | `Itens[Lista]` | `Listas[Lista]` | único |
   | `Atividades[Lista]` | `Listas[Lista]` | único |
   | `PrecosAconex[Lista]` | `Listas[Lista]` | único |
   | `ListaEvento[Lista]` | `Listas[Lista]` | **ambos** |
   | `ListaEvento[Evento]` | `Eventos[Evento]` | único |
   | `Itens[Data Email]` | `Calendario[Data]` | único (ativo) |

   Marque `Calendario` como tabela de datas.
5. **Medidas** — Exibição de consulta DAX › cole `05 - Medidas.dax` inteiro › clique em
   **Atualizar modelo com alterações**. Formate: contagens `0`, `%` com 0 casas, US$ `#,##0`.
6. **Páginas** — abaixo. Comece pela visão interna.
7. **Publicação** — salve como `Sobressalentes - Interno.pbix`. Para o cliente, **Salvar como**
   `Sobressalentes - Itaipu.pbix` e apague as páginas internas (não basta ocultar: página oculta
   continua no arquivo). Se tiverem workspace, o melhor é um modelo semântico publicado e dois
   relatórios finos conectados a ele.

## Cores (validadas para daltonismo, claro e escuro)

| Uso | Cores |
|---|---|
| Com quem está (CMI · Fornecedor · Itaipu · Aprovada) | `#2a78d6` · `#eb6834` · `#1baf7a` · `#eda100` |
| Etapa para o cliente (preparação → análise → aprovada) | `#86b6ef` → `#2a78d6` → `#104281` |
| Situação (no prazo · atenção · fora) | `#0ca30c` · `#fab219` · `#d03b3b`, sempre com rótulo |
| "Depende do fornecedor" (seções) e "sem status válido" | `#898781` |

Tema do relatório: fundo `#fcfcfb`, texto `#0b0b0b`, secundário `#52514e`, grade `#e1e0d9`.
Nada de funil, rosca ou medidor: barras horizontais finas com rótulo na ponta.

## Visão interna (CMI) — 5 páginas

**1. Painel**
- Cartões: `Fichas` · `Fichas Emitidas` (+ `% Emitidas`) · `Autorizações Atrasadas Itaipu`
  (+ `Maior Atraso Itaipu (dias)`) · `LMR Fora do Compromisso` · `Valor Entregue USD` / `Valor Físico USD` ·
  `Pendências CMI`. Subtítulo com `Atualizado em`.
- Barras empilhadas 100%: eixo `Itens[Area]`, legenda `Itens[Com Quem]`, valor `Fichas`.
- Barras: seções da ficha — use uma tabela de apoio com as 6 medidas `%` (ou 6 cartões de linha).
  Valorização e LMR em azul; as do fornecedor em cinza.
- Segmentações (uma linha, no topo): `Itens[Area]`, `Listas[Nome]`, `Itens[Tipo de Entrega]`, `Itens[PROCUREMENT]`.

**2. Entrega (trilha logística)**
- Barras empilhadas por `Listas[Nome]`: `Aguardando Itaipu no Prazo` + `Autorizações Atrasadas Itaipu`;
  rótulo `Maior Atraso Itaipu (dias)`.
- Tabela: Lista, PMIB, Descrição, Data Email, Dias de Atraso, Situacao Autorizacao —
  filtro de página `Situacao Autorizacao` = ATRASADO ITAIPU. **É a pauta da cobrança.**
- Cartões: `Itens Físicos Entregues` / `Itens Físicos`, `Aptas Aguardando Entrega`, `Autorizadas com Atraso`,
  `Aguardando Cálculo do SIG-FT`.

**3. Documental**
- Matriz Lista × seção (% completo) com formatação condicional — mostra onde a ficha trava.
- Barras empilhadas `Situacao LMR` por lista (no prazo / atenção / fora), rótulo `Maior Atraso LMR (dias)`.

**4. Fila de trabalho**
- Tabela com `Itens[Pendencia]` ≠ "—", ordenada por Pendência e Dias de Atraso.
  Segmentação por Pendência e por PROCUREMENT. Detalhamento (drill-through) para a ficha.

**5. Plano de ação e listas de preços**
- Tabela de `Atividades` com `Situacao` ≠ CONCLUÍDA (ícone em ATRASADA / TRAVADA).
- Tabela de `PrecosAconex` com `Geracao` (destacar PB020-0x) e `Situacao Preco`.
- Tabela de `Listas` com `Revisao em Uso`, `Ultima Revisao` e `Revisao Desatualizada` (cartão
  `Listas com Revisão Desatualizada`): lista cujo `_STATUS_PMIB` ainda não foi conferido com a revisão nova.
- Página extra opcional: **Eventos de pagamento** — tabela `Eventos` com `% do Evento Cumprido`.

## Visão Itaipu (cliente) — 2 páginas

O que **não** vai: nomes de pessoas, procurement, observações internas, valor em US$, fila de
trabalho, LMR fora do compromisso, qualidade de dados.

**1. Panorama**
- Cartões: `Fichas Emitidas` ("fichas técnicas enviadas a Itaipu"), `Fichas em Análise IB`,
  `Fichas Aprovadas`, fichas com material entregue, `Pedidos de Autorização` pendentes
  (`Aguardando Itaipu no Prazo` + `Autorizações Atrasadas Itaipu`).
- Barras empilhadas por área, rampa de uma cor: em preparação/ajuste (CMI) → em análise
  Itaipu → aprovada.
- Linha: acumulado de `Fichas Emitidas` por `Calendario[Mes Ano]` (data do e-mail de intenção).

**2. Pendências e listas**
- "Pedidos de autorização de entrega": por lista, no prazo × além de 15 d.u., com a data do pedido e os dias de atraso.
- "Listas de preços aguardando a SM.DT": `PrecosAconex` com `Situacao Preco` = EMITIDA.
- Tabela por lista: fichas, enviadas, em análise, aprovadas, material entregue, autorização pendente.

> [!tip] Tom com o cliente
> "Pedidos de autorização além de 15 dias úteis" é fato contratual, não acusação — o painel
> mostra a data do pedido e os dias de atraso, e a conversa sai do "achismo" para a data.

## Atualização

Power BI Desktop › Atualizar. Se o Box estiver com arquivos "somente online", a primeira
atualização baixa os `_STATUS_PMIB` (pequenos). Erro de arquivo aberto: feche a planilha e repita.

## Relacionados
[[Plano - Sistema de Gestao v2]] · [[Planilha STATUS_PMIB]] · [[Indicadores e Como Ler]]

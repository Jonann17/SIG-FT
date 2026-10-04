---
tags: [gerenciamento, core]
---

# Planilha STATUS_PMIB

> [!important] `QTD.` é o valor final, não a composição unitária
> Para item explodido dentro de um conjunto, a quantidade responde *quantas peças são
> necessárias para compor a quantidade de conjuntos da lista* — já multiplicada. Dois
> conjuntos que levam duas peças cada resultam em `4`, não `2`.
>
> Regra mudada a pedido de Itaipu, cuja leitura é de almoxarifado: a coluna tem de dizer
> quantas peças existem para receber e guardar. Detalhe e exemplo em
> [[Entrega Documental e Explosao de Itens]].


## O que e

Uma **copia da lista de sobressalentes emitida para Itaipu, com colunas extras de
gerenciamento**. E o instrumento de rastreio **item a item** — uma linha por material,
uma planilha por lista.

Template: `Box/15 - PDM/Templates/codigo_itaipu_STATUS_PMIB.xlsx` (era `no_itaipu_STATUS_PMIB.xlsx`).
No template de setembro/2026 o cabeçalho desceu para a **linha 5**: a linha 4 passou a dizer
a revisão da lista em uso e a data da alteração.

> [!tip] Layout v2 (proposto em 01/10/2026)
> Bloco novo à direita: **TIPO DE ENTREGA · FORNECEDOR · PROCUREMENT · PRAZO AUTORIZAÇÃO
> ITAIPU (15 D.U.) · DATA DA AUTORIZAÇÃO ITAIPU · SITUAÇÃO DA AUTORIZAÇÃO · DIAS ÚTEIS DE
> ATRASO · DATA DA ENTREGA**, abas `Feriados` e `Listas`, e listas suspensas por nome
> definido. Template, migração e regras em [[Plano - Sistema de Gestao v2]].

> [!warning] As listas suspensas somem quando o SIG-FT salva
> A validação da coluna STATUS aponta para outra aba (`Checklist!$A$3:$A$8`). O Excel grava
> esse tipo como **extensão**, e o openpyxl — que o SIG-FT usa para gravar — **apaga
> extensões ao salvar**. Em 01/10/2026, 21 planilhas ainda tinham a lista; as outras já a
> tinham perdido. Validação que aponta para um **nome definido** (`=lst_status`) é gravada
> no formato padrão e sobrevive. No template atual, o nome `dados_validos` aponta para
> `A5:A11` e deixa de fora FICHA CRIADA e DUPLICADO.

## Nomenclatura do arquivo

```
{codigo Itaipu da lista}_STATUS_PMIB.xlsx
```
Exemplo: `#ITA0=Y01TF001&BPB020_STATUS_PMIB.xlsx`

O prefixo e o [[Codigo CMI e Codigo Itaipu|código Itaipu]] do documento da lista
principal. E o que permite a [[Mapeamento das Listas de Sobressalentes|mapeadora]]
casar cada planilha com a linha correta.

> [!warning] Quando a lista muda de código
> Se a lista e revisada e o Aconex muda o `No. do Documento`, o arquivo fica orfao.
> O módulo **Gestão PMIB** do SIG-FT resolve isso pelo **Tracking ID** do Aconex,
> renomeando o arquivo. Ver [[SIG-FT - Modulos]].

## As abas

### `Lista de Materiais`
Cabeçalho em duas linhas de título (`GERENCIAMENTO DOS MATERIAIS SOBRESSALENTES
CADASTRADOS NO PMIB` / `ESPECIFICAÇÃO TÉCNICA / CAPÍTULO`), e a tabela a partir dai.

| Coluna | Origem | Para que serve |
|---|---|---|
| `ITEM` | lista | número do item |
| `QTD.`, `UNID.` | lista | quantidade e unidade — **valor final**, ver nota abaixo |
| `DESCRICAO` | lista | **chave de casamento** usada pelo SIG-FT |
| `CODIGO DO MATERIAL` | lista | part number |
| `CODIGO CMI` | CMI | ver [[Codigo CMI e Codigo Itaipu]] |
| `MARCA/MODELO` | lista | fabricante |
| `CODIGO PMIB` | portal | preenchido na criação da ficha |
| `PDM usado` | decisão | qual PDM foi escolhido — ver [[PDM - Padrao de Descricao de Material]] |
| `STATUS` | gestão | estado geral da ficha — ou `DUPLICADO` quando a linha **repete uma ficha da mesma lista** (ver abaixo) |
| `INFO. GERAIS` | gestão | COMPLETO / INCOMPLETO / N/A |
| `CARACT. TECNICAS` | gestão | idem |
| `DOCUMENTOS E IMAGENS` | gestão | idem |
| `CONDICOES` | gestão | idem |
| `VALORIZACAO` | gestão | idem |
| `APLICACAO - LMR` | gestão | idem |
| `DATA DO EMAIL COMUNICANDO ENTREGA` | gestão | marca o início dos 15 d.u. |
| `APTO PARA ENTREGA` | gestão | SIM / NÃO |
| `EQUIPAMENTO ENTREGUE` | gestão | SIM / NÃO |
| `OBSERVACOES` | gestão | texto livre. **Também carrega o PMIB da ficha original** nas fichas duplicadas de outro sistema (`PDM.9900.000`) |

> [!important] `DUPLICADO` ≠ ficha duplicada (corrigido em 04/10/2026)
> - **STATUS `DUPLICADO`**: o mesmo item aparece **duas vezes na mesma lista**. A linha repete o
>   código PMIB de outra linha da lista e não tem as seções preenchidas — para não marcar
>   COMPLETO duas vezes para a mesma ficha. Não conta como ficha nova; a quantidade conta.
> - **Ficha duplicada de outro sistema**: ficha **nova**, com PMIB próprio, `PDM usado` =
>   `PDM.9900.000 - FICHA PMIB, DUPLICADA, R0` e o **PMIB da original em OBSERVAÇÕES**. O STATUS
>   segue o ciclo normal. É o que o módulo Ficha Duplicada do SIG-FT procura.
>
> Detalhe em [[Ciclo de Vida de um Item]] e [[Fichas Duplicadas]].

### `Checklist`
Os valores validos, que evitam status inventado:

| Coluna 1 — STATUS | Coluna 2 — seções | Coluna 3 |
|---|---|---|
| FICHA CRIADA | COMPLETO | SIM |
| DUPLICADO | INCOMPLETO | NÃO |
| COM O FORNECEDOR | N/A | N/A |
| EM ELABORAÇÃO | | |
| EM CORREÇÃO | | |
| EM ANÁLISE IB | | |
| APROVADO | | |
| INICIAR | | |

## Por que ele e o coracao da automação

Praticamente todo módulo do SIG-FT lê ou escreve neste arquivo:

| Módulo | O que faz com o `_STATUS_PMIB` |
|---|---|
| Criar Fichas | escreve `CODIGO PMIB` e `PDM usado` |
| Upload Condições | lê `CODIGO PMIB` e `CONDICOES`; marca `COMPLETO` |
| Upload Specs | lê `PDM usado`; marca `CARACT. TECNICAS` = `COMPLETO` |
| Ficha Duplicada | lê `PDM usado` (`PDM.9900.000`) e `OBSERVACOES` (PMIB base) |
| Buscar Material | varre todos os `_STATUS_PMIB` recursivamente |
| Gestão PMIB | renomeia, agrega e alimenta a mapeadora |
| AutoSpec | lê PMIB e descrição do material |

## A fragilidade estrutural

> [!warning] O cabeçalho não esta numa linha fixa
> Cada `_STATUS_PMIB` pode ter o cabeçalho em linha diferente, porque a lista de origem
> varia de formato (problema declarado no slide 21 da apresentação R5).
>
> Por isso **~10 lugares diferentes do SIG-FT implementam "busca dinâmica da linha de
> cabeçalho"** — o diagnostico da refatoracao lista isso como a duplicacao nº 1 da
> camada Excel. A causa raiz não e o código: e a **falta de padrão da lista de origem**.
> Ver [[Diagnostico - Deficiencias]].

## Relacionados
[[Mapeamento das Listas de Sobressalentes]] · [[Ciclo de Vida de um Item]] · [[SIG-FT - Modulos]]

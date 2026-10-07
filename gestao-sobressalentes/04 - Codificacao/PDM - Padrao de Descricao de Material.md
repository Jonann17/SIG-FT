---
tags: [codificacao, core]
---

# PDM — Padrão de Descrição de Material

## O que e

Um **modelo de descrição por tipo de material**. Ele define quais características
técnicas aquele tipo de material precisa declarar. Uma válvula direcional pede coisas
diferentes de um disjuntor de baixa tensão.

Do [[Anexos II e III - Ficha de Material Reserva e PDM|Anexo III]]:
> Cada equipamento possui um conjunto diferente de características técnicas
> importantes, ou seja, um conjunto de **metadados específico** para cada tipo.

Exemplo da ET: "Disjuntor, baixa tensão" tem **26 características técnicas**.

## Formato do código

```
PDM.4820.012 - VALVULA, DIRECIONAL, R1
└─┬─┘ └─┬─┘ └┬┘   └────────┬────────┘ └┬┘
  │     │    │             │           └── revisao
  │     │    │             └── descricao (nome basico, nome modificador)
  │     │    └── sequencial dentro do grupo
  │     └── grupo / classe
  └── prefixo fixo
```

O SIG-FT extrai com o regex `PDM_\d{4}_\d{3}`.

O **`PDM.9900.000`** e especial: "FICHA PMIB - DUPLICADA". Ver [[Fichas Duplicadas]].

## Quantos existem

A apresentação R5 diz **~1174 PDMs**, um por tipo de material. No Box ha dois
catalogos:
- `1174 - PDMs - SAMGM PMIB.xlsx`
- `PDMs SAM-GM (1193).xlsx`

> [!question] Qual e o vigente?
> Os dois números diferem em 19 PDMs. Confirmar qual catalogo e a fonte de verdade
> antes de usar em automação. Anotado em [[findings]].

Ha ainda `Todos PDMs & Instrucoes.xlsx` e a pasta `PDMs modificados/`.

## Estrutura de um PDM (aba `TEMPLATE_PDM`)

| Coluna | Conteudo |
|---|---|
| `CODIGO PDM` | `PDM.4820.012` |
| `CARACTERISTICA - DESCRIPCION PT` | a pergunta que vai para a linha 79+ da ficha |
| `TEXTO DE AYUDA PT` | ajuda ao preenchedor |
| `TIPO DE CARACTERISTICA` | CHAR / INT / NUM / LISTA |
| `VALORES PT` | valores admitidos, quando LISTA |
| `SIMBOLO` | a unidade |

O SIG-FT chama esse arquivo de **Master PDM** e o cruza com a ficha do fornecedor para
tipar e validar cada resposta. Ver [[Secao - Caracteristicas Tecnicas]].

## Quando o material não tem PDM

O [[Fluxo Macro de Entrega]] tem um passo explicito:
**"Solicita a ITAIPU criação de PDMs (no PMIB)"**.

Base contratual: o Anexo III manda a CONTRATADA **enumerar os metadados** de cada
equipamento novo cujo tipo não conste na listagem atual, com aprovação de Itaipu e
submissao a **ETIM** e ao **bSDD**.

> [!note] O que a ET pediu vs. o que se faz
> A ET manda fazer isso **no início do projeto**, em lote. Na prática os PDMs são
> solicitados **item a item, ao longo do projeto**. Ver [[Diagnostico - Riscos]].

## As regras de escrita (Anexo I 2.2 e 2.3)
- nome padronizado = **nome básico + nome modificador**
- maiusculas, sem acento, **sem C-cedilha e sem N-til**
- sem abreviaturas nos valores
- características ordenadas: físico -> quimico -> elétrico -> mecânico -> construtivo -> dimensional -> normativo
- padrão gráfico com limites de posições (ver [[Anexo I - Classificacao de Materiais Sobressalentes]] item 2.7)

## Como escolher o PDM certo

E uma decisão de julgamento: dado o material, qual dos ~1174 PDMs descreve o tipo dele.
O SIG-FT automatiza com IA no módulo **Criar Fichas** — a IA recebe a descrição do
material da lista, o catalogo de PDMs e um manual de regras, e devolve
`pdm_escolhido` + `descricao_curta` + `origem` + `tipo` + `unidade`.

A escolha e registrada na coluna **`PDM usado`** do [[Planilha STATUS_PMIB]] — e isso
importa, porque **o PDM define as perguntas da ficha**. PDM errado = ficha inteira
errada.

## Relacionados
[[Anatomia de uma Ficha Tecnica]] · [[Secao - Caracteristicas Tecnicas]] · [[Planilha PMIB]]

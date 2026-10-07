---
tags: [codificacao]
---

# Código PMIB

## Formato

```
4500063671.0066
└────┬────┘ └┬─┘
     │       └── sequencial de 4 digitos da ficha
     └── numero do contrato
```

O prefixo **`4500063671`** e o número do contrato do CMI com a Itaipu. Todas as fichas
do projeto compartilham ele. O que identifica a ficha e o sequencial de 4 digitos.

## Quando nasce

**Na criação da ficha no portal**, antes de qualquer preenchimento. Do slide 13:
> Apenas com a criação da ficha e suficiente para a geração do código PMIB necessário
> para incluir no MTA.

Isso desacopla a trilha logistica da documental. Ver
[[MTA, Etiquetas e Entrega no Almoxarifado]].

## Onde ele aparece

| Lugar | Formato |
|---|---|
| Portal PMIB | `4500063671.0066` |
| Campo *Supplier Code* do MTA | `/ CÓD. PMIB 4500063671.0066` |
| Nome do arquivo da ficha Excel | `4500063671.0066.xlsx` |
| Coluna `CÓDIGO PMIB` do `_STATUS_PMIB` | `4500063671.0066` |
| Aba `APLICACAO - LMR` | coluna `FICHA_PMIB` |
| Lista de sobressalentes SM.DT | coluna `Codigo PMIB` |

## As armadilhas de formato

> [!warning] Zeros que somem
> O sequencial tem **4 digitos** e começa com zero em quase toda ficha (`.0066`).
> Excel e pandas tratam `4500063671.0066` como **número** e comem o zero final:
> `4500063671.0066` vira `4500063671.066` ou `4500063671.66`.

O SIG-FT lida com isso em vários lugares (e o `PLANO_REFATORACAO` lista essa
normalização como duplicada **6 vezes** no código):
- ler sempre com `dtype=str`
- remover apostrofo inicial (`'4500063671.0066`) que o Excel insere
- `.ljust(4, '0')` no sequencial
- formatar float como `f"{v:.4f}"` quando já virou número
- regex de detecção: `4500063671\.\d{4}` e `\d{10}\.\d+`

> [!tip] Regra prática
> Toda planilha que contém código PMIB deve ser lida como **texto**. Se você abriu no
> Excel e salvou, confira os zeros antes de usar.

## Relacionados
[[Planilha STATUS_PMIB]] · [[Anatomia de uma Ficha Tecnica]] · [[SIG-FT - Arquitetura]]

---
tags: [processo, ficha, secao]
---

# Seção — Valorização

> [!note] Por que ela e tratada a parte neste cofre
> No portal PMIB as **condições financeiras** aparecem **dentro** da seção de Condições.
> Aqui elas são separadas porque, no processo do CMI, esta parte **não vem do
> fornecedor** — envolve outra área da GE. E uma fronteira organizacional, não de tela.

## O que entra

- **Preço do material em US$** (dolar americano)
- **Quantidade de unidades**
- **Números de série** das unidades novas entregues (quando aplicavel — explicito no
  [[Procedimento de Fichas Duplicadas]] item 4.2)

Base normativa: [[Anexo I - Classificacao de Materiais Sobressalentes]] item 1.1 —
*"custo unitario atualizado em dolares americanos dos Estados Unidos da America (USD)"*.

## Como o preço e validado

Do slide 17 da apresentação R5:
> Deve-se informar na ficha técnica o preço do material em US$ e entregar a **nota
> fiscal** ou a **LISTA COM PREÇOS UNITARIOS** para validação dos preços.

O projeto optou pela **[[Lista de Precos]]**, porque a nota fiscal só existe no momento
do envio e travaria todo o ciclo de aprovação até la.

## A regra de precedencia

```
Lista de Sobressalentes EN.DT aprovada
        ↓
Lista de Precos emitida no Aconex (SM.DT)
        ↓
VALORIZACAO na ficha
```

Nota 3 do slide 12: **"A valorização somente e feita se a lista de sobressalentes
EN.DT estiver aprovada."**

## Por que ela e complexa na prática

1. **Depende de outra área.** Quem preenche o resto da ficha não controla essa etapa.
2. **Depende de um documento externo aprovado** (a lista EN.DT), que pode estar em
   revisão.
3. **Não ha mapeadora de [[Lista de Precos|listas de preços]]** — a rastreabilidade
   entre ficha, lista de preços e revisão da lista de sobressalentes e manual.
4. Se a lista de sobressalentes muda de revisão, o preço pode precisar de revisão
   também, sem gatilho automático.

## Onde ela está no indicador

Na [[Mapeamento das Listas de Sobressalentes|mapeadora]], coluna `VALORIZACAO`.
No [[Planilha STATUS_PMIB]], coluna `VALORIZACAO`.

O acompanhamento fica na coluna `VALORIZAÇÃO` do [[Planilha STATUS_PMIB|_STATUS_PMIB]],
agregada por lista na [[Mapeamento das Listas de Sobressalentes|mapeadora]].
Ver [[Panorama Quantitativo]].

## Relacionados
[[Lista de Precos]] · [[Ata AR-EN.DT-001-2026 - As Duas Listas]] · [[Diagnostico - Deficiencias]]

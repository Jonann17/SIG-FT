---
tags: [processo, documento, gargalo]
---

# Lista de Preços

Também chamada **Tabela com Preços Unitarios**.

## Por que ela existe

Base contratual: [[Capitulo 18 - Pecas de Reposicao e Sobressalentes]] —
> Após aprovada a Lista de Peças de reposicao, a CONTRATADA deve apresentar uma tabela
> com preços unitarios para cada item, garantindo o fornecimento por no mínimo 10 anos
> após a emissão do CAP.

Origem operacional: **proposta do time da Superintendencia de Manutenção de Itaipu em
substituição a nota fiscal** como validação de preço (slide 7 da apresentação R5).

## O ganho de prazo que ela da

Do slide 17:

| Validar preço por | Consequência |
|---|---|
| **Nota fiscal** | a NF só e emitida quando o material e enviado. Logo, a verificação e aprovação das fichas **só começa nesse momento** |
| **Tabela de Preços Unitarios** | permite entregar as fichas **antecipadamente**, e antecipa toda a verificação e aprovação |

Como a aprovação das fichas leva 2 a 3 meses, antecipar esse relogio e o que evita
que o material chegue e fique parado sem evento de aprovação.

## Codificação

A Lista de Preços e emitida no **Aconex** com o código Itaipu da lista de sobressalentes a
que se refere, trocando o **DCC** (classe do documento) no fim do código:

| Documento | DCC | Exemplo |
|---|---|---|
| Lista de Sobressalentes | `PB020` | `#ST00=M00MEU10&MPB020` |
| **Lista de Preços (vigente)** | **`PB021`** | **`#ST00=M00MEU10&MPB021`** |
| Lista de Preços (legado) | `PB020-0x` | `#ST00=M00MEU10&MPB020-01` |

> [!important] Mudou em setembro/2026
> Com a nova revisão do **ITAIPU-REF-0013**, a lista de preços deixou de ser
> "código da lista + sequencial" (`...PB020-01`, `-02`) e passou a ter DCC próprio, **PB021**.
> As listas antigas estão sendo reemitidas com o código novo (atividade "Atualizar o RDS-PP de
> todas as listas de preços com o DCC correto" na aba Atividades da mapeadora). Enquanto isso,
> **os dois formatos convivem** nas pastas.
>
> Consequência boa: reconhecer uma lista de preço **pelo código** ficou trivial — é `PB021`.
> A regra antiga não servia porque há lista de sobressalentes que termina em sequencial
> (`#ITA0=A01AAM10&EPB020-01`, do SMF). Ver [[Plano - Aba de Listas de Precos]].

A rastreabilidade entre lista de preços e lista de sobressalentes continua **no código**:
mesmo prefixo, DCC `PB021` no lugar de `PB020`. Lista renomeada (mudança de RDS-PP) quebra
essa ligação — a aba **Lista de preços Follow-up** da mapeadora guarda o vínculo explícito.

Colunas: ITEM · QTD. · UNID. · DESCRIÇÃO · FABRICANTE / MODELO · CÓDIGO DE MATERIAL ·
**CÓDIGO GE** · **CÓDIGO PMIB** · **VALOR UNITÁRIO** · **TIPO DE ENTREGA**
(`FÍSICA E DOCUMENTAL` / `DOCUMENTAL`; linha de conjunto aparece como `TITULO`).

Template: `Box/15 - PDM/Templates/Lista de Sobressalentes com preço.xlsm`

## Regra de precedencia

**A valorização só e feita se a lista de sobressalentes EN.DT estiver aprovada**
(nota 3 do slide 12). A ordem e:

```
Lista EN.DT aprovada  ->  Lista de Precos (SM.DT)  ->  Valorizacao na ficha
```

Ver [[Secao - Valorizacao]].

## O gargalo

> [!warning] O acompanhamento das Listas de Preços ainda é parcial
> Desde setembro/2026 a [[Mapeamento das Listas de Sobressalentes|mapeadora]] tem a aba
> **Lista de preços Follow-up** (gerada pelo SIG-FT em 03/09), com revisão, status no Aconex
> e a lista de sobressalentes vinculada. Em 01/10/2026 ela tinha 16 documentos, **todos no
> código antigo `PB020-0x`** — nenhuma das 9 `PB021` que já estão nas pastas. E ainda falta o
> campo que diz **a que revisão da lista de sobressalentes** a lista de preços se refere,
> sem o qual a defasagem não aparece sozinha.

Agravantes:
1. O **fluxo Aconex de aprovação da SM.DT ficou "a definir"** na ata de 23/06/2026.
   Sem fluxo formal, não ha estado de documento para rastrear.
2. A **valorização envolve outra área da GE** — não e informação do fornecedor.
   Isso quebra a cadeia: quem preenche o resto da ficha não controla essa parte.
3. Se a lista de sobressalentes muda de revisão, a lista de preços correspondente
   **precisaria ser revisada também**, e não ha gatilho automático para isso.

Ver [[Diagnostico - Deficiencias]] e [[Diagnostico - Plano de Melhoria]].

> [!tip] TIPO DE ENTREGA também no `_STATUS_PMIB`
> A lista de preços é onde o tipo de entrega já existia. No layout v2 do `_STATUS_PMIB` ele
> vira coluna própria (pré-preenchida a partir daqui), porque a maioria das listas ainda não
> tem lista de preços. Ver [[Plano - Sistema de Gestao v2]].

> [!important] Quantidade de componente é valor final
> Nas linhas de itens explodidos, a quantidade responde *quantas peças compõem a
> quantidade de conjuntos da lista* — já multiplicada. Regra mudada a pedido de
> Itaipu; ver [[Entrega Documental e Explosao de Itens]].

## Relacionados
[[Lista de Sobressalentes]] · [[Secao - Valorizacao]] · [[Ata AR-EN.DT-001-2026 - As Duas Listas]]

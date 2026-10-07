---
tags: [processo, ficha]
---

# Fichas Duplicadas

> [!warning] Não confundir com o STATUS `DUPLICADO`
> Esta nota trata da ficha duplicada **de outro sistema** (ficha nova, `PDM.9900.000`). O
> STATUS `DUPLICADO` do `_STATUS_PMIB` é outra coisa: o mesmo item repetido **na mesma lista**,
> sem ficha nova. Ver [[Ciclo de Vida de um Item]].
>
> No `_STATUS_PMIB`, a ficha duplicada de outro sistema tem `PDM usado` =
> `PDM.9900.000 - FICHA PMIB, DUPLICADA, R0`, STATUS no ciclo normal e o **PMIB da original em
> OBSERVAÇÕES** (em 01/10/2026: 111 fichas, 3 sem a referência).

## O problema

O mesmo material aparece em **duas listas de sobressalentes diferentes**. O portal
PMIB **recusa** criar uma segunda ficha com uma referência de fabricante já existente.

Base contratual: [[Anexo I - Classificacao de Materiais Sobressalentes]] item 1.3 —
itens com mesmo PDM e valores idênticos devem ser identificados e encaminhados a
Itaipu para avaliacao.

## A solução: PDM.9900.000

| | Ficha original | Ficha duplicada |
|---|---|---|
| **PDM** | o PDM real do material | **`PDM.9900.000`** ("FICHA PMIB - DUPLICADA") |
| **Referência do fabricante** | a original | original + `D1` (depois `D2`, `D3`...) |
| **Características técnicas** | as do PDM real | **apenas o código PMIB da ficha original** |
| **Condições** | completas | iguais a original (só os obrigatorios) |
| **Valorização** | — | preço atual, quantidade, números de série |
| **Aplicação LMR** | do sistema da lista original | **do sistema da lista NOVA** |

Detalhe completo em [[Procedimento de Fichas Duplicadas]].

## O ponto que confunde

> [!important] A LMR da duplicada não e copia
> Todo o resto da duplicada e copia da original. A **[[Secao - Aplicacao LMR]] não e** —
> ela descreve onde o material esta aplicado **no sistema da nova lista**. Faz sentido:
> e o mesmo material em outro lugar da usina.

## Como o SIG-FT faz

Módulo **Ficha Duplicada**, 3 fases:
1. **Fila** — `sigft/services/duplicadas.py -> localizar_duplicadas()` varre o
   `_STATUS_PMIB` procurando o prefixo `PDM.9900.000` na coluna de PDM, e extrai o
   PMIB da ficha base da coluna `OBSERVACOES` (regex `\d{10}\.\d+`).
2. **Extração** — `ExtratorFichaBase` faz scraping da ficha base no portal.
3. **Injecao** — `InjetorFichaAlvo` preenche a ficha alvo: info gerais, fornecedores,
   4 abas de condições, características (purgando as existentes e preservando o código
   PMIB da base), documentos e imagens.

### O que mudou em 17/08/2026 (CP 6.2)

Quem monta a fila deixou de ser `GerenciadorFilaPMIB`. O que a troca corrigiu:

| Situação | Antes | Depois |
|---|---|---|
| Cabeçalho `PDMs usados` (plural) | achava **zero** fichas | acha |
| Ficha sem original ou sem material | **descartada em silêncio** | fica na lista, com o motivo no log |
| `OBSERVACOES` sem código PMIB | descartada em silêncio | entra com aviso, editavel em "Revisar" |

> [!tip] A lição
> O bug pior não era achar errado — era **descartar em silêncio**. A ficha sumia da
> fila sem log, e ninguém sabia que faltava. Vale como principio para o resto do
> processo: **falha silenciosa e pior que falha ruidosa.**

### O estado do módulo
E o único módulo ainda em **Selenium** (todos os outros migraram para Playwright), e
esta marcado para **reconstrucao na Fase 6** da refatoracao — a decisão de produto
registrada diz que ele *"não funciona como deveria e esta muito fraco"*.
Ver [[SIG-FT - Refatoracao]].

## Relacionados
[[Procedimento de Fichas Duplicadas]] · [[Codigo PMIB]] · [[Secao - Aplicacao LMR]]

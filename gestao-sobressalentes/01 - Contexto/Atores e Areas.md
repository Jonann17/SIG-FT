---
tags: [contexto, atores]
---

# Atores e Áreas

## Lado CMI

| Papel | O que faz |
|---|---|
| **Engenharia do sistema** | Desenvolve o projeto, define o que vai na [[Lista de Sobressalentes]], e a fonte de verdade para localizar equipamento nos desenhos (suporte da [[Secao - Aplicacao LMR]]) |
| **Equipe PDM / Fichas** | Cria e preenche as fichas no PMIB, opera o [[SIG-FT - Visao Geral]], mantém o [[Planilha STATUS_PMIB]] e o [[Mapeamento das Listas de Sobressalentes]] |
| **Procurement** | Contato com fornecedor, cadastro no MTA, insere o [[Codigo PMIB]] no campo *Supplier Code* |
| **Financeiro / Valorização** | Responsável pela [[Secao - Valorizacao]]. **Não e o fornecedor** — e outra área da GE |
| **Almoxarifado do CMI** | Armazém administrado pelo CMI. Materiais sobressalentes **não devem passar por ele** — vao direto ao almoxarifado de Itaipu |

## Lado Itaipu (IB)

Siglas que aparecem na ata AR/EN.DT/001/2026 e no dia a dia:

| Sigla | Papel no processo de sobressalentes |
|---|---|
| **EN.DT** | Superintendencia de Engenharia. Analisa e aprova a **lista de engenharia** (item, descrição, quantidade, marca/modelo, código do material) |
| **SM.DT** | Superintendencia de Manutenção. Analisa e aprova a **lista com preço e código PMIB**. Dona do dominio de preço e PMIB |
| **SMIT.DT** | Divisão que repassa as fichas para o financeiro (prazo de 5 dias) |
| **SMME.DT**, **MTS.DF**, **MTSI.DF**, **MTAA.DF**, **MTSE.DF**, **ENEE.DT** | Áreas presentes na reunião de alinhamento das listas |
| **ENCA.DT** | Gestora da ferramenta Aconex — implanta os fluxos de aprovação |
| **Almoxarifado de Itaipu** | Destino físico dos sobressalentes |

## Fornecedor
Preenche a **[[Planilha PMIB]]** que o CMI envia: informações gerais, condições
(armazenamento, manutenção, descarte) e características técnicas — e fornece
datasheets, catalogos e fotos.

> [!important] O que o fornecedor NÃO preenche
> - A **[[Secao - Valorizacao]]** (condições financeiras) — e da GE.
> - A **[[Secao - Aplicacao LMR]]** — e responsabilidade GE, porque depende dos
>   desenhos do projeto, que o fornecedor não tem.

## Ferramentas por ator
- **PMIB** (`apps.itaipu.gov.br/PMIB`) — portal de materiais da Itaipu, onde a ficha vive
- **Aconex** — emissão e aprovação de documentos (listas, listas de preço)
- **MTA** — cadastro de material e etiqueta de entrega
- **SAP ECC 6.07** — destino final dos dados do PDM, do lado Itaipu

## Relacionados
[[Fluxo Macro de Entrega]] · [[Ata AR-EN.DT-001-2026 - As Duas Listas]]

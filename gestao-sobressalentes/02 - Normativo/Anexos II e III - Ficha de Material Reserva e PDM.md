---
tags: [normativo, fonte-primaria]
fonte: ET Geral 6047-20-T0018-P R1, p. 304-311
---

# Anexos II e III — Ficha de Material Reserva e PDM

## Anexo II — Ficha de Material Reserva (p. 304)
E o **modelo de exemplo** da ficha, referenciado pelo [[Capitulo 18 - Pecas de Reposicao e Sobressalentes]]:
> "conforme modelo de exemplo do ANEXO II — FICHA TÉCNICA DE MATERIAL DE RESERVA"

No PDF o anexo e uma **imagem**, sem texto extraivel. O que vale hoje na operação e o
template vivo em `Box/15 - PDM/Templates/Ficha Tecnica do PDM-R3.xlsx`, já na revisão
R3. Ver [[Anatomia de uma Ficha Tecnica]].

## Anexo III — Padrão de Descrição de Material (p. 306)

> Cada equipamento possui um conjunto diferente de características técnicas
> importantes, ou seja, um **conjunto de metadados específico para cada tipo de
> equipamento**.

O anexo exemplifica com "Disjuntor, baixa tensão" e suas **26 características
técnicas** — 26 metadados que deveriam fazer parte do modelo BIM daquele equipamento.

### A amarracao com padrões internacionais
A ET amarra o PDM a padrões abertos de classificação:
- **ETIM** — exemplo citado: `eiyp.etim-international.com/class/EC000042/7`
- **bSDD** (buildingSMART Data Dictionary, baseado na ETIM)
- **UNSPSC**
- **LOD do BIMForum.org**

### A obrigacao de estender o catalogo
> A listagem completa de metadados exigidos pelo PDM de ITAIPU **para cada tipo de
> equipamento instalado atualmente** será entregue para a CONTRATADA. Com base nesta
> listagem a CONTRATADA deverá **enumerar os metadados que cada equipamento novo**
> (cujo tipo não conste na listagem atual) deve possuir. Tal listagem deve ser aprovada
> por ITAIPU e submetida a ETIM e ao bSDD **ao início do projeto**.

**Leitura prática**: e a base contratual do pedido de **criação de PDM novo** que
aparece no [[Fluxo Macro de Entrega]] ("Solicita a ITAIPU criação de PDMs no PMIB").
Quando o material não tem PDM no catalogo, o CMI propoe e Itaipu cria.

> [!note] O que na prática ficou diferente
> A ET manda submeter os PDMs novos a ETIM e ao bSDD **no início do projeto**.
> Na operação real os PDMs são solicitados **item a item, ao longo do projeto**,
> conforme aparecem materiais sem PDM. Ver [[Diagnostico - Riscos]].

## Relacionados
[[PDM - Padrao de Descricao de Material]] · [[Anexo I - Classificacao de Materiais Sobressalentes]]

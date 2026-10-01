---
tags: [processo, ficha]
---

# Planilha PMIB

## O que e
Um **extrato em Excel dos campos do PDM** referentes a informações logisticas,
financeiras e características técnicas. E o veículo pelo qual o CMI pede ao fornecedor
os dados da ficha — o fornecedor não entra no portal PMIB.

Do slide 14 da apresentação R5:
> Esta Planilha e um extrato dos PDMs referentes a informações logisticas e financeiras.
> A equipe do CMI envia um Excel de acordo com o tipo de equipamento que está sendo tratado.
> Exemplo: `PDM.4820.012 - VALVULA, DIRECIONAL, R1`
> **O equipamento deve estar contido em uma lista de sobressalente.**

## O que o fornecedor preenche

Nota 2 do slide 12:
> Planilha contendo os campos de **informações gerais**, **condições (exceção da seção
> financeira)** e **características técnicas**.

E nota do slide 10:
> O Fornecedor deve preencher as seções de informações gerais, condições (de
> armazenamento, manutenção e descarte) [e características técnicas], **e fornecer
> datasheets**.

| Seção | Fornecedor preenche? |
|---|---|
| [[Secao - Informacoes Gerais]] | sim |
| [[Secao - Condicoes]] | sim (armazenamento, transporte, manutenção, descarte) |
| [[Secao - Caracteristicas Tecnicas]] | sim |
| [[Secao - Documentos e Imagens]] | fornece o material (datasheets, catalogos, fotos) |
| [[Secao - Valorizacao]] | **não** — outra área da GE |
| [[Secao - Aplicacao LMR]] | **não** — responsabilidade GE, depende dos desenhos do projeto |

## Como e gerada

O módulo **PDM** do [[SIG-FT - Modulos|SIG-FT]] fatia o catalogo geral de PDMs em
arquivos individuais e aplica o template da ficha, injetando as perguntas daquele PDM
a partir da **linha 79**. O resultado e um arquivo por código PMIB, pronto para enviar.

## Relacionados
[[Anatomia de uma Ficha Tecnica]] · [[PDM - Padrao de Descricao de Material]] · [[SIG-FT - Modulos]]

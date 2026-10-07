---
tags: [processo, ficha, secao]
---

# Seção — Documentos e Imagens

## O que entra
Datasheets, catalogos, esquemas eletricos, manuais de montagem e manutenção, e
**fotografias** do material.

Base normativa: [[Capitulo 18 - Pecas de Reposicao e Sobressalentes]] —
*"fichas técnicas para catalogacao (modo de aplicação, modo de manutenção, esquemas
eletricos, etc.)"* — e [[Anexo I - Classificacao de Materiais Sobressalentes]] item
**1.1.9 Fotografia**.

## Os critérios de fotografia — são contratuais

Isto costuma ser tratado como exigencia informal do portal. **Não e**: esta escrito
no Anexo I, item 1.1.9.

| Critério | Exigencia |
|---|---|
| Resolucao | **800 x 600 pixel** |
| Formato | **jpeg** |
| Fundo | **fundo infinito** proposto pela IB |
| Quantidade | **1 a 4 fotos** por item, conforme posicionamento e angulo. **A IB decide** a quantidade necessária |
| Material pequeno | a foto deve mostrar **referência, modelo, códigos gravados, número de série e lote de fabricacao** |
| Organização | fotos ficam **na mesma pasta de cada material**, mesma nomenclatura e taxonomia |
| Apoio | a IB pode disponibilizar local e pessoal habilitado para movimentacao de materiais |

### Avaliacao qualitativa
A ET diz que as fotos **serão avaliadas**. Critérios listados:
- posicionamento (centralizacao)
- foco e nitidez
- **isencao de sombras**
- dados de placa visiveis (marca, modelo, número de série, lote de fabricacao)
- **ocupacao minima de 90% da área de enquadramento**

> [!tip] Consequência prática
> Foto reprovada e retrabalho físico: precisa acessar o material de novo, muitas vezes
> já embalado ou no almoxarifado. Vale conferir os 90% de enquadramento e as sombras
> **antes** de o material sair do fornecedor.

## Coluna de controle
No [[Planilha STATUS_PMIB]]: coluna **`DOCUMENTOS E IMAGENS`**.

## Automação
O módulo **Ficha Duplicada** do SIG-FT clona documentos associados e faz upload das
imagens da ficha base para a alvo (`duplicadas_documentos.py`, `duplicadas_imagens.py`).
Não ha, hoje, módulo que valide os critérios de qualidade da foto.
Ver [[Diagnostico - Plano de Melhoria]].

## Relacionados
[[Anexo I - Classificacao de Materiais Sobressalentes]] · [[Fichas Duplicadas]]

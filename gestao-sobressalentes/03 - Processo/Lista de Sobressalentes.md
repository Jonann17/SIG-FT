---
tags: [processo, documento]
---

# Lista de Sobressalentes

## O que e
O documento que declara **quais materiais de reserva serão entregues** para um
sistema. E gerado pelo projeto de engenharia daquele sistema, junto com a lista de
materiais de aplicação.

Emitida no **Aconex**, aprovada pela **EN.DT**. Ver [[Ata AR-EN.DT-001-2026 - As Duas Listas]].

## Quanto entregar — não existe regra única

O critério vem da **ET do sistema**, não da ET Geral. Exemplos de critério que
aparecem no projeto:
- percentual do que foi aplicado (ex.: 20% do total instalado)
- ao menos 1 peça de cada material
- critério próprio da ET

> [!important] Sempre volte a ET do sistema
> Não ha atalho. A ET Geral ([[Capitulo 18 - Pecas de Reposicao e Sobressalentes]]) da
> a obrigacao geral; o **quanto** e da ET específica.

## Codificação

Cada lista tem **dois códigos**, e ambos importam:

| Código | Exemplo | Quem usa |
|---|---|---|
| **N. Documento Itaipu** (RDS-PP) | `#ITA0=Y01TF001&BPB020` | Itaipu, Aconex |
| **N. Documento CMI** | `0893410CYU20-224FPD-95` | CMI |

Ver [[RDS-PP e KKS]] e [[Codigo CMI e Codigo Itaipu]].

O código Itaipu da lista e o que **nomeia o arquivo de gerenciamento**:
`#ITA0=Y01TF001&BPB020_STATUS_PMIB.xlsx`. Ver [[Planilha STATUS_PMIB]].

## Campos minimos (decisão da ata de 23/06/2026)
Item · Descrição · Quantidade · Marca/Modelo · Código do Material

A lista da SM.DT acrescenta: Unidade · Fabricante/Modelo · **Código CMI** ·
**Código PMIB** · **Valor Unitario** · **Tipo de Entrega**. Ver [[Lista de Precos]].

## Padronização — problema declarado

O slide 21 da apresentação R5 registra, sem rodeio:
> As listas de sobressalentes **não estão seguindo um padrão** de formato e informações.
> Deve-se utilizar para a lista de sobressalentes o **mesmo template de lista de materiais**.

Os slides 22-24 mostram exemplos recebidos fora do padrão e os templates propostos
(inclusive um com Código CMI).

## O problema gerencial: a lista se move

A nota 1 do slide 12 diz que **toda atualização da lista após a aprovação obriga
atualizar os itens conforme a última versão**. E o Capítulo 18 obriga rever quantidade
e tecnologia se houver mudança tecnológica no curso da AT.

Consequência prática: o `_STATUS_PMIB` de um sistema pode ficar **dessincronizado**
da lista vigente. Itens somem, entram, mudam de quantidade — e as fichas já criadas
não acompanham automaticamente.

Este e um dos problemas centrais do processo. Ver [[Diagnostico - Deficiencias]].

## Revisão e status

Na [[Mapeamento das Listas de Sobressalentes|mapeadora]] cada lista carrega:
- `ULTIMA REVISAO EMITIDA` (0, 0A, 0C, 1, 1A...)
- `STATUS DA REVISAO` (Aprovado, Aprovado com Comentários, Para Assinatura, Em Processo)
- `STATUS REAL` (APROVADO, NÃO APROVADO, NÃO EMITIDO, EM PROCESSO)
- `REVISAO EM USO`

> [!note] Por que `STATUS DA REVISAO` e `STATUS REAL` são colunas diferentes
> O Aconex reporta o estado do fluxo documental; `STATUS REAL` e a leitura do CMI
> sobre se aquela lista **vale** para trabalhar. Uma revisão "Para Assinatura" pode
> já estar aprovada na prática.

## Relacionados
[[Lista de Precos]] · [[Planilha STATUS_PMIB]] · [[Mapeamento das Listas de Sobressalentes]]

---
tags: [normativo, procedimento]
documento: Procedimiento - Fichas PMIB Duplicadas PDM_9900_000
---

# Procedimento de Fichas Duplicadas

Arquivo: `Box/15 - PDM/Procedimiento - Fichas PMIB Duplicadas PDM_9900_000.pdf` (espanhol, 4 p.)
Origem contratual: [[Anexo I - Classificacao de Materiais Sobressalentes]] item **1.3 Duplicidade dos códigos**.

## Quando usar

> Se considera necesaria la utilizacion del **PDM.9900.000 "FICHA PMIB - DUPLICADA"**
> para todo mismo material que este en **dos listas de materiales distintas**.
> Las características deben de ser identicas, asi como tambien las referências.

Condição para duplicar: **material idêntico em duas listas diferentes**, com
características e referências identicas. Toda informação distinta deve ser adicionada
na ficha "Duplicada".

> [!tip] Qual PDM escolher
> A ficha **original** fica com o PDM real do material. A ficha da **segunda lista**
> usa `PDM.9900.000`. E o que permite ao portal aceitar duas fichas para o mesmo item
> sem conflito de referência.

## Como preencher, seção por seção

### 1. Informação Geral
Adicionar o **código de projeto da lista de sobressalentes correspondente**
(documento da lista, subsistema e sistema a que pertence), o **código RDS-PP** do
documento da lista de sobressalentes e o **evento de pagamento associado**. Mais o
texto breve do material.

### 2. Fabricantes e Fornecedores

#### 2.1 Fabricante / Referência — a regra do sufixo D
> Tras un intento fallido de creacion de una ficha técnica con una referência ya
> existente en el portal PMIB [...] se debe ingresar la **referência original seguida
> de la etiqueta "D1" entre comillas**. En caso de una segunda duplicacion, se
> utilizara **"D2"**, y asi sucesivamente.

O portal recusa referência repetida. O sufixo `D1`, `D2`, ... e o desempate.

> [!question] A confirmar
> O documento escreve `"D1"` entre aspas. Não esta claro se as aspas fazem parte do
> valor gravado no campo ou se são notacao do texto. Anotado em [[findings]].

#### 2.2 Fornecedores / Referência
Quando ha vários fornecedores (por exemplo, o CMI compra uma solução de um
sub-fornecedor), **cada fornecedor e sua referência devem constar**. Em caso de
duplicacao, mesmo critério do sufixo D.

### 3. Características Técnicas
Adiciona-se **uma única característica**: o **código PMIB da ficha original**.
E o que amarra a duplicada a sua origem.

### 4. Condições

#### 4.1 Armazenamento e transporte
**Igual a ficha original**, completando apenas todos os campos obrigatorios.

#### 4.2 Condições financeiras
Adiciona-se o **preço atual do material**, a **quantidade de unidades** e os
**números de série** das unidades novas entregues.

### 5. Aplicação LMR
> En este campo se tendra de cargar **todos los campos necesarios de la nueva ficha
> técnica**: Código RDSPP (material "Tag" y su respectiva localizacion).

**Atenção**: a LMR da duplicada e a da **nova** lista, não a copia da original. Faz
sentido — o mesmo material, aplicado em outro sistema, tem outra localização.

## Como o SIG-FT implementa isso
O módulo **Ficha Duplicada** (`sigft/services/duplicadas*.py`) clona a ficha base e
injeta na alvo, **preservando o código PMIB da base** nas características.
A identificação das duplicadas mudou em 17/08/2026: quem monta a fila agora e
`duplicadas.localizar_duplicadas`, que procura pelo prefixo `PDM.9900.000`.
Ver [[SIG-FT - Modulos]] e [[Fichas Duplicadas]].

## Relacionados
[[Fichas Duplicadas]] · [[Codigo PMIB]] · [[Secao - Aplicacao LMR]]

---
tags: [normativo, fonte-primaria]
fonte: ET Geral 6047-20-T0018-P R1, p. 294-303
---

# Anexo I — Classificação de Materiais Sobressalentes da AT

Este e **o anexo que define o conteudo da ficha**. Quando alguém pergunta "por que a
ficha pede isso?", a resposta quase sempre está aqui.

## 1. Objeto e disponibilizacao dos dados

Toda descrição técnica e referência de fabricante (part number) deve vir no conceito
e formato de **PDM**, com os dados **extraidos diretamente do modelo 3D BIM**.

Deve ser informado:
- vida útil
- **quantidade instalada na Usina**
- custo unitario atualizado em **USD**

> [!warning] Duas exigencias que a operação real não cumpre como escrito
> - **"extraidos do modelo 3D BIM"** — na prática os dados vem do fornecedor pela
>   [[Planilha PMIB]].
> - **"quantidade instalada na Usina"** — e exatamente o que a
>   [[Secao - Aplicacao LMR]] tenta responder, e e o que Itaipu cobrou em
>   [[Revisao da Aplicacao LMR - Agosto 2026]] ("faltaria a cantidad de bombas
>   aplicados en el equipamiento").
> Ver [[Diagnostico - Riscos]].

## 1.1.1 Grupo de mercadorias
Enquadramento no código padrão de mercado. A IB fornece a lista.

## 1.1.3 Condições de armazenagem — a lista completa (a-k)
Esta lista e a fonte da [[Secao - Condicoes]] da ficha:

| | Requisito |
|---|---|
| a | **Climatizacao** — temperatura minima e maxima conforme características do material |
| b | **Ambiente desumidificado** — controle de umidade, valor máximo e mínimo |
| c | **Descarga eletrostatica** — operacionalidade e materiais usados (pulseira, manta, embalagem) |
| d | **Perecibilidade** — materiais com prazo de validade pre-determinado |
| e | **Posição de armazenamento** — horizontal, vertical ou indiferente |
| f | **Proteção contra agentes nocivos** |
| g | **Sujeito a intemperies** |
| h | **Necessidade de embalagem especial** e o tipo |
| i | **Empilhamento** — se sujeito, informar quantidade maxima |
| j | **Legislacao ambiental brasileira e paraguaia** — classificação de descarte, tipo de descarte, local de descarte, **logistica reversa** |
| k | **Normas técnicas aplicaveis** para armazenagem |

## 1.1.5 Criticidade
Classificação pelo impacto na operação da usina:

| Tipo | Definição |
|---|---|
| **Tipo 1** | As falhas acarretam **perda de geração** (ou transmissão). Indispensaveis ao processo |
| **Tipo 2** | As falhas **reduzem a confiabilidade** da geração |
| **Tipo 3** | As falhas **não afetam nem reduzem** a geração |

> [!note] O texto da ET tem um erro de redacao
> O Tipo 3 diz "não se incluem nos tipos **A e B**" — heranca de uma versão anterior
> que usava letras. Leia como "tipos 1 e 2".

## 1.1.6 Permutabilidade
Indicacao de material alternativo que pode apresentar diferenças fisicas mas serve a
mesma finalidade sem prejuizo operacional. **Atenção a assimetria**: A ser permutavel
por B não implica B ser permutavel por A.

## 1.1.8 Procedencia
- **Nacional** — adquirido no mercado brasileiro ou paraguaio (item de prateleira)
- **Importado** — outros paises

Na mapeadora aparece como coluna `ORIGEM FORNECEDOR` (NACIONAL / INTERNACIONAL).

## 1.1.9 Fotografia — os critérios exatos
Esta e a seção que a equipe costuma achar que e "pedido informal do portal". **Não e.**

- Resolucao **800x600 pixel**, extensão **jpeg**, **fundo infinito** proposto pela IB
- Materiais de pequeno porte: a foto deve mostrar **referência, modelo, códigos
  gravados, número de série e lote de fabricacao**
- **De 1 a 4 fotografias** por item, em função de posicionamento e angulo. A IB se
  reserva o direito de definir a quantidade
- As fotos ficam **na mesma pasta de cada material**, com a mesma nomenclatura e taxonomia
- A IB pode disponibilizar local e apoio de pessoal habilitado em movimentacao de materiais
- **Avaliacao qualitativa**: posicionamento (centralizacao), foco, nitidez, ausência de
  sombras, dados de placa, e **ocupacao minima de 90% da área de enquadramento**

Ver [[Secao - Documentos e Imagens]].

## 1.1.10 a 1.1.13 — SAP
- Formato deve ser cadastravel no **SAP ERP Central Component 6.07**
- Dados compativeis com as classificacoes do SAP para relacionar material ao PDM
- Textos gravados em **português e espanhol**
- **A carga no SAP e responsabilidade da Itaipu**, não do CMI

## 1.2 Normas
Prioridade: **NBR** (Brasil) e/ou **INTN** (Paraguai). Na ausência: IEC, ANSI, VDE,
BSI, ISO, DIN, CEN. Unidades no **Sistema Internacional (SI)**.

## 1.3 Duplicidade de códigos
> No caso da identificação de itens fornecidos, porém, com **mesmo PDM e valores
> idênticos** para suas características, estes deverão ser identificados e
> encaminhados a ITAIPU para avaliacao e posterior carga no SAP.

E a base contratual de [[Fichas Duplicadas]] e do `PDM.9900.000`.

## 2. Disposicoes normativas — nomenclatura

### Nome padronizado = Nome básico + Nome modificador

| Nome principal | Nome modificador |
|---|---|
| FREQUENCIMETRO | DIGITAL |
| RELE | FREQUÊNCIA |
| PURGADOR | TERMODINAMICO |

**Nome básico**: denominacao mais elementar, no singular. Deve individualizar o item.

| Correto | Incorreto | Por que |
|---|---|---|
| AUTOMOVEL | VEÍCULO | genérico demais |
| POLIDOR | KAOL | marca virou nome |
| TINTA | CORALIT | marca virou nome |
| LAMINA | GILLETTE | marca virou nome |
| PRISIONEIRO | STUD | estrangeirismo |
| ESTRADO | PALLET | estrangeirismo |
| CHAVE | SWITCH | estrangeirismo |

Material coletivo usa termo genérico adequado (INSTRUMENTOS, FERRAMENTAS).

**Nome modificador**: distingue itens de mesmo nome básico, por aplicação,
composição, tipo ou formato.

## 2.3 Características técnicas
Conjunto de dados que individualizam itens de mesmo nome padronizado. **Devem estar
ordenadas** segundo aspectos: fisicos, quimicos, eletricos, mecanicos, construtivos,
dimensionais e normativos — nessa ordem.

### Regras de escrita que quebram ficha
- Descrição em **letras maiusculas**
- **Sem acentuacao**
- **Proibidos** os caracteres **cedilha (C)** e **enhe (N)**
- **Não são permitidas abreviaturas** para os valores das características

Ver [[Secao - Caracteristicas Tecnicas]] — e por isso que o SIG-FT normaliza texto
com `unicodedata.normalize('NFD')` em vários módulos.

### Número de posições no SAP
| Formato | Posições |
|---|---|
| Caractere | 30 |
| Data | 10 |
| Numérico | 15 |
| Casas decimais | 12 |

## 2.4 a 2.6 — Código de Referência e de Fornecedor
- **CR (Código de Referência)**: código do fabricante/fornecedor para o item.
  A transcricao deve **obedecer rigorosamente a forma grafica original**.
  CRs diferentes para o mesmo item representam **equivalencia**.
- **CF (Código de Fornecedor)**: identifica fabricante ou fornecedor. E
  **complemento obrigatório** do registro do CR.
- Principio: o CR se vincula **sempre ao fabricante**; vincular a fornecedor só em
  situação excepcional.

## 2.7 Padrão gráfico

| Descrição | Posições | Formato | Padrão IB |
|---|---|---|---|
| PDM | 05 | alfabetico | `Z_GGO` |
| Descrição do PDM | 40 | alfabetico | `TRANSFORMADOR, DISTRIBUICAO` |
| Código da característica técnica | 06 | alfanumerico | `Z_1001` |
| Denominacao da característica | 30 | alfanumerico | `MATERIAL` |
| Valor da característica | 30 | alfanumerico | — |
| Referência de fabricante | 100 | alfanumerico | — |

## Relacionados
[[PDM - Padrao de Descricao de Material]] · [[Secao - Condicoes]] · [[Secao - Caracteristicas Tecnicas]] · [[Secao - Documentos e Imagens]]

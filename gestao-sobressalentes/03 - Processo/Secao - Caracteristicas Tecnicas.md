---
tags: [processo, ficha, secao]
---

# Seção — Características Técnicas

**A única seção que muda de material para material.** O conjunto de perguntas vem do
[[PDM - Padrao de Descricao de Material|PDM]] escolhido.

## De onde vem o conteudo

No template Excel, as características começam na **linha 79**:
- colunas **C-L**: a pergunta (a denominacao da característica, do PDM)
- colunas **M-V**: a resposta

A ficha do fornecedor volta com as respostas, e o SIG-FT cruza com o **Master PDM**
(aba `TEMPLATE_PDM`) para saber, de cada característica: `TIPO DE CARACTERISTICA`,
`VALORES PT` possiveis, e `SIMBOLO` (unidade).

## As regras de escrita que quebram a ficha

Do [[Anexo I - Classificacao de Materiais Sobressalentes]] item 2.3.1:

- **Maiusculas**
- **Sem acentuacao**
- **Proibidos** cedilha (**C**) e enhe (**N**)
- **Não são permitidas abreviaturas** nos valores

E item 2.3: as características devem estar **ordenadas** por aspectos
**fisicos -> quimicos -> eletricos -> mecanicos -> construtivos -> dimensionais -> normativos**.

## Tipos de dado

O portal e o SAP tipam cada característica. O SIG-FT trabalha com quatro:

| Tipo | Regra |
|---|---|
| **CHAR** | texto livre, 30 posições |
| **INT** | inteiro |
| **NUM** | numérico, **virgula decimal**, 15 posições / 12 casas |
| **LISTA** | valor tem que ser **um dos** `VALORES PT` do PDM |

Regras de formatação que o SIG-FT aplica:
- **virgula** como separador decimal
- **ponto-e-virgula** para separar itens de lista
- **conversão de unidade** quando o simbolo do PDM difere do datasheet
  (ex.: `l/min` -> `m3/h`)
- valores `N/A` e tracos: decisão de **reter ou excluir** a característica

## O idioma duplo

A ET exige tudo em **português e espanhol** (Anexo I 1.1.12: "todos os textos e
descrições serão gravados no SAP nos idiomas português e espanhol").

Por isso a ficha ganha a aba **"Especificações técnicas copiar"** com três colunas:

| Pergunta | Resposta (Espanhol, sem acento) | Resposta (Português, sem acento) |
|---|---|---|

Gerada pelo módulo **Tradutor** do SIG-FT (xlwings + GoogleTranslator com fallback
MyMemory + `unidecode`). Ver [[SIG-FT - Modulos]].

## Coluna de controle
No [[Planilha STATUS_PMIB]]: coluna **`CARACT. TECNICAS`**.

## Automação
Módulo **Upload Specs** (Características Técnicas): cruza `_STATUS_PMIB` + Master PDM,
manda a IA normalizar cada característica (com auditoria de tipo, unidade e paginacao)
e preenche a tabela no portal, lidando com paginacao e exclusão segura de linhas.
Campos que o portal rejeita viram **relatório de pendências manuais**.

O módulo **AutoSpec AI** preenche características vazias via RAG sobre datasheets
locais e busca web, marcando o que preencheu em **fonte azul**.

## Relacionados
[[PDM - Padrao de Descricao de Material]] · [[Anexo I - Classificacao de Materiais Sobressalentes]] · [[SIG-FT - Modulos]]

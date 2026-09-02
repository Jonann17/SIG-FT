# Como uma ficha técnica nasce — do PDM da Itaipu à ficha em branco

> Mapeado em 2026-08-28. Este documento não descreve **um** módulo: descreve o
> **processo** que atravessa `sigft/services/pdm.py`, `sigft/app/views/pdm.py`,
> o `_STATUS_PMIB` e os templates de ficha. Ele existe porque a pergunta
> "de onde vêm as características técnicas da ficha?" não tinha resposta em
> lugar nenhum — estava espalhada por três funções e uma tela de três abas.

## O resumo em uma frase

A Itaipu manda **uma lista geral de PDMs**; o aplicativo a fatia em um arquivo
por PDM, transforma cada um numa **tabela de perguntas**, e depois cola essas
perguntas dentro de um **template de ficha** — escolhendo qual tabela entra em
qual ficha pelo **PDM que o `_STATUS_PMIB` associa àquele código PMIB**.

## As três etapas, e as pastas de cada uma

```
  PDM's SAM-GM.xlsx                    (1 arquivo, a lista geral da Itaipu)
        │
        │  Op 1a  ·  pdms_fromItaipu_lista_geral()
        ▼
  PDMs From Itaipu/                    (1 arquivo por PDM, formato original)
        │                               PDM_1234_001....xlsx
        │  Op 1b  ·  processar_arquivo_pdm() + salvar_tabela_formatada()
        ▼
  PDMs Modificados/                    (1 arquivo por PDM, DUAS COLUNAS)
        │                               PDM_1234_001..._formatado.xlsx
        │
        │  Op 2   ·  processar_pastas_fichas() + aplicar_templates_fichas()
        │            + o template da ficha + o _STATUS_PMIB
        ▼
  Fichas/4500063671.0071.xlsx          (a ficha em branco, pronta p/ o fornecedor)
```

### Op 1a — fatiar a lista geral

`pdms_fromItaipu_lista_geral(lista, pasta_destino)`. Lê a aba `TEMPLATE_PDM`,
pega cada código único da **coluna A a partir da linha 7**, e escreve um
arquivo por código **preservando os estilos** (fonte, borda, preenchimento,
`number_format`, alinhamento). O formato de saída é o mesmo da entrada.

### Op 1b — virar tabela de perguntas

Esta é a etapa que dá nome à pasta "PDMs **Modificados**".

`processar_arquivo_pdm(arquivo)` lê a aba `TEMPLATE_PDM` com
`skiprows=6, header=None` e usa **duas colunas só**:

| Coluna do PDM original | Índice | O que é |
|---|---|---|
| **Q** | 16 | a descrição da característica técnica |
| **S** | 18 | a unidade |

e monta a linha final assim:

```python
'Descrição': f"{i+1} - {q} ({s}):"     # "1 - Pressão de trabalho (bar):"
'Resposta':  ''                        # vazia de propósito: quem preenche é o fornecedor
```

`salvar_tabela_formatada` grava `<nome>_formatado.xlsx` com:

| | Colunas | Conteúdo |
|---|---|---|
| Descrição | **1 a 10, mescladas** | `"1 - Pressão de trabalho (bar):"` |
| Resposta | **11 a 20, mescladas** | vazio |

Formatação: fonte 8, `wrap_text`, altura 32, bordas finas em todas as células.

> ⚠️ **Guarda de sobrescrita:** sem `force=True`, se já existir na pasta um
> arquivo cujo nome CONTENHA o nome do original, o PDM é ignorado com
> `"Ignorado (já existe)"`. É comparação por substring em maiúsculas — não é
> igualdade de nome.

### Op 2 — colar as perguntas dentro do template

Duas funções em sequência:

**`processar_pastas_fichas(arquivo_STATUS_PMIB, destino, ...)`** lê a planilha
de status e devolve, para cada material, a tripla
`(código PMIB formatado, "PDM.1234.001 - NOME", pasta de destino)`. É aqui que
a associação **material → PDM** acontece: ela vem da coluna *"PDM usado"* do
`_STATUS_PMIB`, não de nenhuma regra do código.

**`aplicar_templates_fichas(lista, pasta_pdms_modificados, path_template)`** é
o montador propriamente dito:

```python
id_pdm = pdm_nome.split(" - ")[0].replace(".", "_")   # "PDM.1234.001 - X" -> "PDM_1234_001"
src    = <o arquivo da pasta cujo NOME CONTÉM esse id>
...
ws_target = wb_target["Ficha Técnica Padrão"]          # nome de aba FIXO
start_row = 79                                          # linha inicial FIXA
```

e para cada linha do PDM modificado:

| Lê do PDM modificado | Escreve na ficha |
|---|---|
| `cell(i, 1)` → Descrição | coluna **C**, mesclando **3–12** |
| `cell(i, 2)` → Resposta | coluna **M**, mesclando **13–22** |

O template é lido do disco **uma vez só**, para `BytesIO`, e cada ficha recebe
uma cópia limpa a partir desses bytes (CP 4.3 — antes era um `load_workbook`
por ficha).

## Quatro coisas que só se descobrem lendo o código

1. **O nome da aba de destino é fixo: `"Ficha Técnica Padrão"`.** Um template
   cuja aba se chame outra coisa faz `aplicar_templates_fichas` levantar
   `KeyError` — e o erro cai no `except` genérico do laço, virando
   `"ERRO ao gerar ficha {pmib}"` para **todas** as fichas.

2. **A linha 79 é fixa em três lugares independentes.** Aqui
   (`start_row = 79`), em `sigft/config.LINHA_SPECS_FICHA` (usado pelo
   `analyzer` e pelo `autospec`) e em `translator.py` (`current_row = 79`).
   Só os dois últimos estão unificados; este não. Ver `PENDENCIAS.md`, entrada
   de 2026-07-28 do CP 2.4.

3. **A coluna da Resposta não casa entre quem escreve e quem lê.**
   `salvar_tabela_formatada` grava a Resposta na **coluna 11**;
   `aplicar_templates_fichas` a lê na **coluna 2** — que, dentro do intervalo
   mesclado 1–10, é uma `MergedCell` e vale sempre `None`.
   **Hoje isso é inofensivo**, porque a Resposta é vazia por definição nesta
   etapa (quem responde é o fornecedor, depois). Mas significa que, no estado
   atual, **só a coluna 1 do PDM modificado carrega conteúdo** — e é só ela que
   precisa ser traduzida.

4. **A escolha do arquivo PDM é por SUBSTRING do id no nome.**
   `id_pdm in os.path.basename(f)` — o primeiro que casar vence. Duas versões
   do mesmo PDM na pasta e o resultado depende da ordem do `glob`. É o que a
   Op 3 (`logica_excluir_duplicados`) existe para evitar.

## Onde cada coisa mora

| O quê | Onde |
|---|---|
| As três operações | `sigft/services/pdm.py` |
| A tela (3 abas) | `sigft/app/views/pdm.py` |
| Pastas padrão (`pdms_modificados`, `templates_ficha`) | `sigft/core/prefs.py` → `PASTAS_PADRAO_SEED` |
| Chaves de diálogo (`pdm.template`, `pdm.status_pmib`) | `sigft/core/prefs.py` → `PASTAS_PADRAO_POR_CHAVE` |
| Layout da ficha preenchida (`CONFIG_MAP`) | `sigft/core/rpa/ficha_layout.py` |

## O template, hoje

O aplicativo **não sabe em que idioma o template está**. A tela pede
*"Selecionar Template (.xlsx)"* e usa o arquivo que o usuário escolher; nada no
código distingue o template PT-BR do template em inglês. As perguntas coladas
vêm sempre da mesma pasta de PDMs Modificados, que está em português.

É exatamente essa lacuna que a frente de 2026-08-28 vai fechar — ver
[`docs/FICHA_EM_INGLES.md`](../FICHA_EM_INGLES.md).

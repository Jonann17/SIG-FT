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

> **Desde 2026-09-24 há um segundo caminho**, que pula as pastas: as perguntas
> saem direto da planilha de PDMs. É o padrão da tela; o caminho das pastas
> continua como método antigo. Ver
> [a seção própria](#desde-2026-09-24-a-ficha-pode-nascer-direto-da-planilha).

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
| **S** | 18 | o texto de ajuda, a instrução de preenchimento (ver [a forma da pergunta](#a-forma-da-pergunta--o-que-ela-realmente-é)); não é a unidade |

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
ws_target = wb_target[nome_da_aba_da_ficha(wb_target)]  # resolvido, ver nº 1
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

1. **O nome da aba de destino ERA fixo: `"Ficha Técnica Padrão"`.** Um template
   cuja aba se chamasse outra coisa fazia `aplicar_templates_fichas` levantar
   `KeyError` — e o erro caía no `except` genérico do laço, virando
   `"ERRO ao gerar ficha {pmib}"` para **todas** as fichas: num lote de 200
   materiais, 200 linhas idênticas, nenhuma dizendo que o problema era a aba.
   **Corrigido em 2026-08-28** (`nome_da_aba_da_ficha`): aceita variações,
   usa a aba única quando só há uma, e quando não reconhece nenhuma **para o
   lote** com os nomes encontrados na mensagem.

   O template em inglês real confirmou que a preocupação não era teórica — mas
   pelo avesso do que eu esperava: `Technical_Sheet_of_PDM-R3.xlsx` traz a aba
   com o nome **em português**, herdado do template do qual foi derivado, e é
   a ficha já preenchida (`4500063671.0052_enUS.xlsx`) que traz
   `Standard Technical Sheet`. Os dois nomes circulam.

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

   **Desde 2026-09-24** vence o arquivo de **revisão mais alta no nome**
   (`_escolher_arquivo`; sem revisão no nome conta como a mais baixa), com
   aviso no log dizendo quantos havia e qual foi usado. O casamento continua
   por substring.

## Desde 2026-09-24: a ficha pode nascer direto da planilha

As pastas "From Itaipu" e "PDMs Modificados" eram uma cópia da planilha que
precisava ser refeita a cada revisão de PDM, e ninguém refazia: em setembro de
2026 as pastas inteiras estavam desatualizadas. O caminho novo lê a planilha
exportada pela Itaipu e monta a ficha sem passar por elas:

```
  PDMs_SAM-GM_<data>.xlsx              (a exportação da Itaipu, aba TEMPLATE_PDM)
        │
        │  pdm_catalogo.carregar()      revisão vigente, características em ordem
        ▼
  CatalogoPDM
        │
        │  pdm_planilha.perguntas_do_pdm()   as 9 regras abaixo, uma ficha por vez
        ▼
  as perguntas  "1 - NOME (AJUDA):"
        │
        │  pdm.aplicar_templates_fichas_da_planilha()   o MESMO motor do método antigo
        ▼
  Fichas/4500063671.0071.xlsx
```

O motor (`pdm._montar_fichas`) é um só para os dois caminhos: template lido uma
vez, aba resolvida por `nome_da_aba_da_ficha`, perguntas a partir da C79, a
mesma geometria. Só muda de onde vêm as perguntas.

| # | Situação | O que acontece |
|---|---|---|
| 1 | Qual revisão | A vigente: a maior `REVISIÓN` do código (a mesma regra do módulo 1 e do Upload Specs) |
| 2 | Ordem | Pela coluna `SECUENCIA`, numeradas de 1 a N; sem sequência legível, vai para o fim |
| 3 | Texto | `"N - NOME (AJUDA):"`, ou `"N - NOME:"` sem ajuda; nome e ajuda como a Itaipu escreveu. Acabou o `(nan)` |
| 4 | Portal numa revisão **menor** que a planilha | Gera com a da planilha; aviso de que o PDM precisa subir de revisão no portal |
| 5 | Portal numa revisão **maior** que a planilha | Gera com a da planilha; aviso para exportar uma planilha nova da Itaipu |
| 6 | Código com dois nomes base na planilha | Gera só se o título do "PDM usado" começar pelo nome base da revisão vigente; se não, recusa mostrando os dois |
| 7 | "PDM usado" sem código, código fora da planilha, PDM sem característica | Recusa aquela ficha; o lote segue |
| 8 | Planilha sem característica nenhuma (o formato manipulado antigo) | O lote para antes de começar |
| 9 | "PDM usado" sem revisão (formato antigo) | Sem conferência de revisão; gera com a vigente |

Os avisos 4 e 5 também saem agrupados no fim do log, com a lista dos PMIBs de
cada caso. A ficha em inglês **não** tem esse caminho: as perguntas traduzidas
só existem na pasta.

**As pastas continuam, agora regeneráveis.** O botão "Regenerar as pastas"
(`pdm_regeneracao.regenerar_pastas`) refaz as duas a partir da planilha, com a
revisão no nome: `PDM_1650_001 - ACUMULADOR - R2.xlsx` na From Itaipu e
`PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx` na Modificados. O arquivo
desatualizado vai para a subpasta `_versoes_antigas` (nada é apagado), o que já
está na revisão vigente não é regravado, e a revisão no nome é o que o item 4
acima usa para escolher entre dois arquivos do mesmo PDM.

## Onde cada coisa mora

| O quê | Onde |
|---|---|
| As três operações | `sigft/services/pdm.py` |
| A leitura da planilha de PDMs (`CatalogoPDM`) | `sigft/core/pdm_catalogo.py` |
| As regras da ficha pela planilha | `sigft/services/pdm_planilha.py` |
| A regeneração das duas pastas | `sigft/services/pdm_regeneracao.py` |
| A tela (3 abas) | `sigft/app/views/pdm.py` |
| Pastas padrão (`pdms_modificados`, `templates_ficha`) | `sigft/core/prefs.py` → `PASTAS_PADRAO_SEED` |
| Chaves de diálogo (`pdm.template`, `pdm.status_pmib`) | `sigft/core/prefs.py` → `PASTAS_PADRAO_POR_CHAVE` |
| Layout da ficha preenchida (`CONFIG_MAP`) | `sigft/core/rpa/ficha_layout.py` |

## O template, nos dois idiomas

Até 2026-08-28 o aplicativo **não sabia em que idioma o template estava**: a
tela pedia *"Selecionar Template (.xlsx)"* e usava o arquivo escolhido; nada no
código distinguia o PT-BR do inglês, e as perguntas coladas vinham sempre da
mesma pasta de PDMs Modificados, em português. A tela agora tem um **seletor de
idioma** que decide de qual pasta as perguntas saem — ver
[`docs/FICHA_EM_INGLES.md`](../FICHA_EM_INGLES.md).

### A geometria dos dois, medida (2026-09-03)

Os dois templates são **o mesmo documento traduzido**, e a geometria não mudou
em nenhum ponto que o montador toca:

| | PT-BR | Inglês |
|---|---|---|
| Título da seção (B75) | `ESPECIFICAÇÕES TÉCNICAS - INDIQUE...` | `TECHNICAL SPECIFICATIONS - INDICATE...` |
| Primeira pergunta | **C79** | **C79** |
| Mescla da pergunta | `C{n}:L{n}` | `C{n}:L{n}` |
| Mescla da resposta | `M{n}:V{n}` | `M{n}:V{n}` |
| Abaixo da seção | vazio até a 156 | vazio até a 156 |
| Nome da aba | `Ficha Técnica Padrão` | `Ficha Técnica Padrão` **no template**, `Standard Technical Sheet` na ficha entregue |

Nada abaixo da linha 76 nos dois: por mais perguntas que o PDM traga, a
injeção não tem rodapé para sobrescrever.

### A forma da pergunta — o que ela realmente é

Não é um rótulo curto com a unidade entre parênteses. É o nome da
característica em MAIÚSCULAS seguido da **instrução de preenchimento inteira**,
com parênteses aninhados dentro:

```
9 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item. Nota: Material
especifico de compra com (Número de desenho, referência, nome usual, outros)):
```

De 100 a 200 caracteres. Quem for mexer em qualquer coisa que **leia ou
escreva** essa string — tradução, validação por IA, extração de campo — precisa
partir daqui, e não de `"1 - Pressão (bar):"`. Essa suposição errada já custou
uma regra de prompt que mandava deixar a instrução em português.

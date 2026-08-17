r"""
Seletores da ficha duplicada — levantados do DOM real (2026-08-11).

CP 6.1/6.2 da Fase 6. São os seletores dos três componentes que o módulo
precisa e que **não são campos comuns**: o combo de fabricante, o diálogo de
imagens e o diálogo de documentos. Vieram do "inspecionar elemento" do usuário
no portal, não de suposição — o que muda tudo, porque os três têm ids
PARCIALMENTE GERADOS e isso não se descobre adivinhando.

A regra que organiza o arquivo: **cada seletor diz por que está escrito assim**,
e em especial qual pedaço do id foi descartado e por quê. Foi a lição mais cara
da Fase 5 — seletor sem justificativa é seletor que ninguém sabe consertar.

Módulo só de constantes: nada de import de motor. É lido pelo inventário
(`core/rpa/inventario.py`) e consumido pelo serviço de duplicação.
"""

# ===========================================================================
# 1. Combo de FABRICANTE — widget `virtual-select` (vscomp)
# ===========================================================================
# HTML levantado:
#   <div class="vscomp-toggle-button">
#     <div class="vscomp-value" data-tooltip="Selecione um fabricante">…</div>
#     <div class="vscomp-arrow"></div>
#     <div class="vscomp-clear-button …"><i class="vscomp-clear-icon"></i></div>
#   </div>
#   <input type="text" class="vscomp-search-input"
#          placeholder="Pesquisar um fabricante " id="vscomp-search-input-3940">
#
# ⚠️ O `id="vscomp-search-input-3940"` tem NÚMERO GERADO pelo widget. Amarrar o
# seletor a `3940` funciona na sessão em que foi lido e falha na seguinte, com
# "elemento não encontrado" que parece mudança de portal e não é. Por isso o
# casamento é pela CLASSE.
#
# É a mesma família de widget que `cria_fichas.XPATH_PDM_FINAL` já usa
# (`div.vscomp-value[data-tooltip^='PDM']`), o que é um bom sinal: o padrão de
# seletor já foi validado contra o portal em outro módulo.
XPATH_FABRICANTE_TOGGLE = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-toggle-button ')]"
)
XPATH_FABRICANTE_VALOR = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-value ')]"
)
# O usuário confirmou que a busca por digitação é o caminho bom: "esse aqui é
# melhor por digitando texto, que daí filtra o fornecedor".
XPATH_FABRICANTE_BUSCA = (
    "//input[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-search-input ')]"
)
# A opção filtrada, casada pelo texto. `{texto}` é preenchido pelo consumidor.
XPATH_FABRICANTE_OPCAO = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-option ')]"
    "[normalize-space(.)={texto}]"
)

# ===========================================================================
# 2. Diálogo de IMAGENS — widget FilePond
# ===========================================================================
# A pergunta era "o `<input type=file>` é alcançável?". O HTML responde SIM:
#   <input class="filepond--browser" type="file"
#          id="filepond--browser-h1d4zvekk" name="filePondUpload5"
#          accept="image/jpeg,image/png" multiple="">
#
# Três consequências, todas boas:
#
#   1. **Não precisa de área de transferência nem de arraste simulado.** Existe
#      um input de arquivo de verdade; Playwright preenche com
#      `set_input_files` e Selenium com `send_keys(caminho)`. Isso confirma a
#      recomendação de BAIXAR da original e SUBIR na duplicada, em vez de
#      reproduzir o copiar/colar humano.
#
#   2. **O input é escondido** (o FilePond mostra o rótulo "Arraste e solte…"
#      e esconde o nativo). Não é problema: preencher input de arquivo
#      escondido é justamente o que `set_input_files`/`send_keys` fazem sem
#      precisar que o elemento esteja visível. NÃO clique no rótulo — isso
#      abriria o diálogo de arquivo do sistema operacional, que o navegador
#      não controla e que travaria o robô.
#
#   3. ⚠️ **O `id` é GERADO a cada renderização** (`filepond--browser-h1d4zvekk`,
#      e o mesmo sufixo aparece em `filepond--drop-label-…` e
#      `filepond--assistant-…`). Amarrar a ele é garantia de quebra. O
#      casamento é pela classe `filepond--browser`, ancorado no container do
#      OutSystems, cujo id é estável.
XPATH_IMAGENS_ABRIR = "//a[.//span[normalize-space()='Adicionar imagens']]"
XPATH_IMAGENS_DESCRICAO_ES = "//input[contains(@id, 'Input_DescriptionES')]"
XPATH_IMAGENS_DESCRICAO_PT = "//input[contains(@id, 'Input_DescriptionPT')]"
# `contains(@id, ...)` e não igualdade: o prefixo `b10-b15-` é o caminho do
# bloco na tela e muda se alguém reorganizar o formulário no OutSystems. O
# sufixo é o que nomeia o campo.
XPATH_IMAGENS_CONTAINER = "//div[contains(@id, 'MultiUploadContainer')]"
XPATH_IMAGENS_INPUT_ARQUIVO = (
    "//div[contains(@id, 'MultiUploadContainer')]"
    "//input[@type='file' and contains(concat(' ', normalize-space(@class), ' '), ' filepond--browser ')]"
)

# `accept="image/jpeg,image/png"` — declarado pelo próprio input. A imagem
# baixada da ficha original TEM de ser um destes dois; o portal recusa o resto,
# e uma imagem em outro formato (webp, gif) falharia no envio.
FORMATOS_DE_IMAGEM_ACEITOS = (".jpg", ".jpeg", ".png")

# ===========================================================================
# 3. Diálogo de DOCUMENTOS — associar, não subir
# ===========================================================================
# O documento já existe como objeto no portal; associa-se pela busca textual.
# A busca não é opcional: a lista tem 809 itens em 162 páginas (tela levantada),
# então paginar até achar não é alternativa.
XPATH_DOCUMENTOS_ABRIR = "//a[.//span[normalize-space()='Associar documentos']]"
XPATH_DOCUMENTOS_BUSCA = "//input[contains(@id, 'Input_SearchFilter')]"
XPATH_DOCUMENTOS_LUPA = (
    "//button[contains(concat(' ', normalize-space(@class), ' '), ' search-button ')]"
)
# A linha do resultado, casada pela descrição. `{texto}` é do consumidor.
XPATH_DOCUMENTOS_LINHA = "//tr[.//td[contains(normalize-space(.), {texto})]]"
XPATH_DOCUMENTOS_CHECKBOX_DA_LINHA = ".//input[@type='checkbox']"
XPATH_DOCUMENTOS_ASSOCIAR = "//button[normalize-space()='ASSOCIAR']"

# ===========================================================================
# 4. O que NÃO usar — registro dos ids voláteis
# ===========================================================================
# Deixado explícito porque o erro é atraente: o id aparece no "inspecionar
# elemento", parece o seletor mais preciso possível, e funciona na primeira
# tentativa. A falha vem depois, noutra sessão, parecendo mudança de portal.
IDS_GERADOS_NAO_USAR = (
    "filepond--browser-",     # sufixo aleatório por renderização
    "filepond--drop-label-",  # mesmo sufixo
    "filepond--assistant-",   # mesmo sufixo
    "vscomp-search-input-",   # número sequencial do widget
)

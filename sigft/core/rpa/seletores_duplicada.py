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
# A opção filtrada. HTML levantado:
#   <div role="option" aria-selected="false" id="vscomp-option-3940-1625"
#        class="vscomp-option focused" data-value="1533" data-index="1625">
#     <span class="vscomp-option-text" data-tooltip="SCHNEIDER">SCHNEIDER</span>
#   </div>
#
# O casamento é pelo `@data-tooltip` do span, e não pelo texto do `<div>`:
#   - o `data-tooltip` traz o nome EXATO, sem os espaços e quebras de linha que
#     o HTML tem em volta do texto (`\n            SCHNEIDER\n          `);
#   - `id="vscomp-option-3940-1625"` é gerado nas DUAS metades (3940 = instância
#     do widget, 1625 = índice da opção na lista completa) -- inútil;
#   - `data-value="1533"` é o id interno do fabricante no portal. Seria o
#     casamento mais forte de todos, mas não temos esse número em lugar nenhum:
#     a ficha original dá o NOME, não o id.
#
# `role="option"` entra como âncora semântica: sobrevive a mudança de classe do
# widget, que é o tipo de coisa que uma atualização de biblioteca faz.
XPATH_FABRICANTE_OPCAO = (
    "//div[@role='option']"
    "//span[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-option-text ')]"
    "[@data-tooltip={texto}]"
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

# O checkbox da linha. HTML levantado:
#   <td data-header="Selecionar">…<input class="checkbox" type="checkbox"
#       id="b10-b15-b19-l1_0-521_0-Checkbox1"></td>
#
# ⚠️ Mais um id gerado, e de um tipo novo: `l1_0-521_0` é o índice da LINHA na
# lista do OutSystems. Muda a cada busca (é a posição no resultado), então nem
# entre duas execuções da mesma pesquisa ele se repete.
#
# `@data-header='Selecionar'` é a âncora boa: é o cabeçalho da coluna, escrito
# por quem desenhou a tela, e o mesmo atributo que `tech_specs` já usa para
# achar a coluna de descrição (`XPATH_REL_COL_DESCRICAO`).
XPATH_DOCUMENTOS_CHECKBOX_DA_LINHA = ".//td[@data-header='Selecionar']//input[@type='checkbox']"
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
    "vscomp-option-",         # instância do widget + índice da opção
    # Índice de LINHA das listas do OutSystems (`…-l1_0-521_0-Checkbox1`,
    # `…-l1_0-535_0-View`). Muda a cada busca -- nem entre duas execuções da
    # mesma pesquisa se repete.
    "-l1_0-",
)

# ===========================================================================
# 5. Campo de REFERÊNCIA e o aviso de colisão
# ===========================================================================
# HTML levantado:
#   <div class="vertical-align flex-direction-row" id="b10-b11-b4-b3-Content">
#     <label><span class="text-primary…">Referência</span></label>
#     <input class="form-control OSFillParent" required type="text"
#            maxlength="100" id="b10-b11-b4-Input_TextVar">
#     <div data-block="PMIB_DataSheet_Forms.Block_ReferenceCoincidence"
#          id="b10-b11-b4-CoincidenceReference">…</div>
#     …<a href="#"><i class="icon fa fa-plus-circle fa-2x"></i></a>
#   </div>
#
# ⚠️ `Input_TextVar` é um nome GENÉRICO -- "input de variável de texto". Não
# identifica o campo de Referência coisa nenhuma, e provavelmente existe em
# outros pontos da tela. Por isso o seletor ancora no RÓTULO: é o que a pessoa
# lê na tela, e o que muda junto se o campo mudar de sentido.
XPATH_REFERENCIA_INPUT = (
    "//div[.//span[normalize-space()='Referência']]"
    "//input[contains(@id, 'Input_TextVar')]"
)

# O ACHADO desta rodada: o aviso "A referência já existe!" não é texto solto na
# página -- tem um bloco próprio, com id SEMÂNTICO (`CoincidenceReference`) e
# nome de bloco declarado (`Block_ReferenceCoincidence`).
#
# Isso muda a qualidade da detecção de colisão. A alternativa era varrer a tela
# atrás da frase, o que é frágil em três frentes: idioma (a tela alterna PT/ES),
# redação (o portal pode reescrever a mensagem) e escopo (outra mensagem
# parecida em outro ponto da página daria falso positivo, e falso positivo aqui
# gasta as 20 tentativas de sufixo escondendo o erro real).
#
# Com este seletor, a pergunta vira "este bloco tem conteúdo?", que é estável.
# `e_erro_de_referencia_repetida()` continua existindo para o caso de a
# mensagem vir por outro caminho -- as duas checagens se somam, não se
# substituem.
XPATH_REFERENCIA_AVISO_COLISAO = "//div[contains(@id, 'CoincidenceReference')]"

# O "+" que adiciona a linha de fabricante/referência à tabela.
XPATH_REFERENCIA_ADICIONAR = (
    "//a[.//i[contains(concat(' ', normalize-space(@class), ' '), ' fa-plus-circle ')]]"
)

# ===========================================================================
# 6. Lista de fichas: achar a original e ABRIR EM VISUALIZAÇÃO
# ===========================================================================
# A original pode estar em qualquer um dos 7 status, e o portal separa a lista
# em abas. HTML da aba:
#   <button class="osui-tabs__header-item osui-tabs--is-active" role="tab"
#           data-tab="0" aria-selected="true">
#     …<span data-expression="">Em Elaboração</span>
#     …<div class="badge…"><span class="OSFillParent">1</span></div>
#   </button>
#
# `role="tab"` + o texto é o casamento; `data-tab="0"` é posicional e
# `name="0.22zxs6p0948"` é gerado. O BADGE é útil: dá para pular direto para a
# aba que tem contagem > 0 em vez de abrir as 7.
XPATH_ABA_STATUS = "//button[@role='tab'][.//span[normalize-space()={texto}]]"
XPATH_ABA_STATUS_CONTAGEM = (
    "//button[@role='tab'][.//span[normalize-space()={texto}]]"
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' badge ')]"
)

# A coluna "Ações" de cada linha da lista. HTML levantado:
#   <td data-header="Ações">
#     <div id="b7-b23-l1_0-535_0-View">   …<i class="icon fa fa-file-o fa-1x">
#     <div id="b7-b23-l1_0-535_0-Edit">   …<i class="icon fa fa-pencil-square-o">
#     <div id="b7-b23-l1_0-535_0-Delete"> …<i class="icon fa fa-trash">
#
# De novo `l1_0-535_0` gerado, mas os SUFIXOS `-View`/`-Edit`/`-Delete` são
# semânticos e é neles que se ancora. Confirmam também, no HTML, a distinção
# que a especificação já tinha feito: são DUAS portas para a mesma ficha, e o
# extrator usa a primeira.
#
# `fa-file-o` (folha) = visualizar; `fa-pencil-square-o` (lápis) = editar. O
# seletor exige as duas coisas -- o sufixo do id E o ícone -- porque cada um
# sozinho já apareceu como armadilha: o id é parcialmente gerado, e o ícone
# `fa-pencil-square-o` é o MESMO do lápis de `cria_fichas.XPATH_LAPIS_MASSA`,
# em outra tela.
XPATH_ACAO_VISUALIZAR = (
    ".//div[contains(@id, '-View')]"
    "//a[.//i[contains(concat(' ', normalize-space(@class), ' '), ' fa-file-o ')]]"
)
XPATH_ACAO_EDITAR = (
    ".//div[contains(@id, '-Edit')]"
    "//a[.//i[contains(concat(' ', normalize-space(@class), ' '), ' fa-pencil-square-o ')]]"
)

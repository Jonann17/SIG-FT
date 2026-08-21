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
    # Sequencial de bloco do OutSystems no modo de visualização
    # (`b12-b20-b1-$b3`, `$b4`, `$b5`). O `$` já denuncia que é gerado.
    "-$b",
    # 6º tipo, das abas INTERNAS da ficha (2026-08-18): o `aria-controls` do
    # botão de aba aponta um id gerado (`aria-controls="b12-$b12"`). Cai no
    # padrão do `-$b` acima, e está listado à parte porque o atributo é
    # OUTRO -- quem for amarrar a navegação pelas abas olha o `aria-controls`
    # antes de olhar o `id`.
    "aria-controls=",
)

# Atributos que NÃO são ids gerados, mas que também não servem de âncora --
# e que enganam mais, justamente por parecerem estáveis.
ATRIBUTOS_INSTAVEIS_NAO_USAR = (
    # `name="0.4z9qbl6cvoj"` / `name="0.22zxs6p0948"`: aleatório por
    # renderização. Aparece nas abas de status E nas abas internas da ficha --
    # duas telas, então é padrão da plataforma.
    "name",
    # `data-tab="1"`: ORDINAL da aba. Não é gerado, é POSIÇÃO -- e posição
    # muda quando o portal reordena a tela, fazendo o robô abrir a aba errada
    # sem nenhum aviso. Mesmo raciocínio de §6.5c.
    "data-tab",
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

# ===========================================================================
# 7. Modo de VISUALIZAÇÃO — o padrão que dispensa mapear campo a campo
# ===========================================================================
# HTML levantado de um bloco (Volume, na aba de armazenamento):
#
#   <fieldset>
#     <legend><div id="…-Legend">
#       <span class="text-primary font-size-base">Volume (cm3)</span>
#     </div></legend>
#     <div id="…-Content">
#       <div data-container="">
#         <label data-label=""><span class="text-primary">Comprimento…</span></label>
#         <div data-container="" class="margin-top-s">
#           <div data-block="PMIB_DataSheetView.Block_Expression" id="b12-b20-b1-$b3">
#             <span data-expression="">6</span>
#           </div>
#         </div>
#       </div>
#       …repete para Largura e Altura…
#     </div>
#   </fieldset>
#
# É por isso que NÃO se mapeia campo a campo: a estrutura é uniforme. Um
# extrator que leia pares rótulo→valor cobre as três abas inteiras, e continua
# funcionando quando o portal acrescentar um campo -- ao contrário de cinquenta
# seletores nomeados, que envelheceriam juntos.
#
# `data-block="PMIB_DataSheetView.Block_Expression"` é a peça central: é o
# marcador semântico de "aqui há um valor exibido em modo de leitura", e vem
# namespaceado pelo módulo OutSystems (`PMIB_DataSheetView`). Distingue o valor
# de qualquer outro `<span>` da página sem depender de classe de layout.
#
# ⚠️ `id="b12-b20-b1-$b3"` é gerado e sequencial (`$b3`, `$b4`, `$b5`) -- mais um
# para a lista de proibidos.
XPATH_VIEW_BLOCO = "//fieldset"
XPATH_VIEW_TITULO_DO_BLOCO = ".//legend//span"
# Rótulo e valor, em ordem de documento. O pareamento é "cada valor pertence ao
# rótulo imediatamente anterior" -- ver `duplicadas_spec.parear_rotulos_e_valores`,
# que é onde a regra está testada contra o HTML real.
XPATH_VIEW_ROTULO = ".//label[@data-label]//span"
XPATH_VIEW_VALOR = (
    ".//div[@data-block='PMIB_DataSheetView.Block_Expression']//span[@data-expression]"
)
# Os dois juntos, em ordem de documento -- é assim que o extrator lê a aba de
# uma vez só, em vez de fazer duas varreduras e tentar casá-las por posição.
XPATH_VIEW_ROTULOS_E_VALORES = (
    ".//label[@data-label]//span"
    " | "
    ".//div[@data-block='PMIB_DataSheetView.Block_Expression']//span[@data-expression]"
)

# ---------------------------------------------------------------------------
# 7b. Modo de visualização: o SEGUNDO padrão (opções marcadas)
# ---------------------------------------------------------------------------
# Levantado depois, e ele INVERTE o padrão de cima -- é a razão de ter valido
# a pena pedir o HTML em vez de generalizar a partir de um exemplo só.
#
#   <fieldset><legend>…<span class="text-primary font-size-base">
#       Nocivos ou Outros Cuidados</span></legend>
#     <div>
#       <span class="text-primary font-size-base">Nocivo</span>   <-- RÓTULO
#       <div class="custom">
#         <span><input class="radio-button" disabled type="checkbox" checked
#                      id="b12-b20-b1-Checkbox1"></span>
#         <label data-label="">Não contém agentes nocivos</label> <-- VALOR
#       </div>
#     </div>
#     …repete para "Outros cuidados"…
#   </fieldset>
#
# As duas inversões, e as duas quebrariam a leitura em silêncio:
#
#   1. o RÓTULO do campo não é um `<label>`: é um `<span class="text-primary">`
#      -- a MESMA classe da legenda do fieldset;
#   2. o VALOR está DENTRO de um `<label data-label>` -- ou seja, exatamente o
#      seletor que no padrão de cima significa "rótulo". Sem discriminar, o
#      extrator leria "Não contém agentes nocivos" como um rótulo de campo, com
#      valor vazio, e o campo "Nocivo" sumiria da ficha copiada.
#
# O que discrimina é a presença de `<span>` DENTRO do label:
#   - `label[@data-label]/span`      -> rótulo   (padrão do Volume)
#   - `label[@data-label]` sem span  -> valor    (padrão da opção marcada)
#
# `checked` no input é o que diz qual opção está selecionada; `disabled` é só o
# modo de leitura. Na tela levantada o portal renderiza apenas a opção marcada,
# mas o seletor exige `@checked` de qualquer forma -- se um dia renderizar
# todas, ler a errada seria pior que não ler nenhuma.
XPATH_VIEW_ROTULO_DE_SECAO = (
    ".//span[contains(concat(' ', normalize-space(@class), ' '), ' text-primary ')]"
    "[not(ancestor::label)][not(ancestor::legend)]"
)
# ⚠️ CORREÇÃO DE 2026-08-17: das duas metades do discriminador acima, só uma é
# load-bearing. Quem impede a inversão é o ramo do RÓTULO exigir `//span` -- o
# label da opção marcada não tem nenhum, então nunca entra como rótulo. O
# `[not(span)]` daqui é a segunda tranca da mesma porta: sabotá-lo não quebra
# nenhum teste contra o HTML real. Fica porque custa zero, mas está registrado
# que ninguém deve contar com ele (ver `test_duplicadas_xpath_real.py`).
XPATH_VIEW_OPCAO_MARCADA = (
    ".//div[.//input[@type='checkbox'][@checked]]/label[@data-label][not(span)]"
)

# ⚠️ ARMADILHA que o bloco "Logística de reversa" revelou: o contador de anexos
# (clipe de papel) também é um `<span data-expression>`:
#
#   <div data-block="Numbers.Badge">…<span data-expression="" class="OSFillParent">0</span>
#
# Ele NÃO é valor de campo -- é a quantidade de anexos. Só não é lido por
# acidente: `XPATH_VIEW_VALOR` exige o ancestral
# `data-block='PMIB_DataSheetView.Block_Expression'`, e o badge está sob
# `Numbers.Badge`. Ou seja, o namespace do bloco não é preciosismo: é o que
# separa valor de contador. Sem ele, "Logística de reversa" viria como "0".
XPATH_VIEW_BADGE_DE_ANEXO = (
    ".//div[@data-block='Numbers.Badge']//span[@data-expression]"
)


# ---------------------------------------------------------------------------
# 7c. A linha da lista, ancorada no PMIB — para ABRIR a ficha original
# ---------------------------------------------------------------------------
# `XPATH_ACAO_VISUALIZAR`/`XPATH_ACAO_EDITAR` acima são RELATIVOS a uma linha
# (`.//`). Para `portal.pesquisar_e_abrir`, que recebe um XPath absoluto com
# `{pmib}` interpolado, é preciso a versão ancorada -- e é ela que decide em
# qual das duas portas da ficha o robô entra.
#
# `contains(., '{pmib}')` na `<tr>` inteira, e não `span[text()='{pmib}']`
# (o default do portal): é a MESMA estratégia que o módulo antigo de ficha
# duplicada já usava (`_LAPIS_XPATH_TEMPLATE_FICHA_DUPLICADA`), e ela é a certa
# aqui porque o código da original vem das OBSERVAÇÕES -- pode estar numa
# célula que não é o `<span>` do código, e o texto exato da célula não é
# garantido.
XPATH_LINHA_ACAO_VISUALIZAR = (
    "//tr[contains(., '{pmib}')]"
    "//div[contains(@id, '-View')]"
    "//a[.//i[contains(concat(' ', normalize-space(@class), ' '), ' fa-file-o ')]]"
)
XPATH_LINHA_ACAO_EDITAR = (
    "//tr[contains(., '{pmib}')]"
    "//div[contains(@id, '-Edit')]"
    "//a[.//i[contains(concat(' ', normalize-space(@class), ' '), ' fa-pencil-square-o ')]]"
)

# Campo de busca da lista. Mesma string que o módulo antigo de ficha duplicada
# usa (`_BUSCA_XPATH_FICHA_DUPLICADA`): aceita id OU placeholder, porque as
# telas de lista do portal não concordam entre si sobre qual dos dois existe.
XPATH_BUSCA_DA_LISTA = (
    "//input[contains(@id, 'InputDatasheetFilter') or contains(@placeholder, 'Código')]"
)

# ---------------------------------------------------------------------------
# 7d. A varredura de um bloco em modo de visualização
# ---------------------------------------------------------------------------
# União dos QUATRO seletores dos dois padrões (§7 e §7b), em ordem de
# documento. É o que permite ler a seção inteira numa passada só, em vez de
# quatro varreduras que depois teriam de ser casadas por posição -- e bastaria
# um campo vazio para desalinhar tudo dali para baixo.
#
# A ordem dos ramos da união é irrelevante: XPath devolve nó em ordem de
# DOCUMENTO, não na ordem em que os ramos foram escritos. É justamente disso
# que o pareamento depende.
XPATH_VIEW_VARREDURA = " | ".join((
    ".//label[@data-label]//span",                       # rótulo, padrão A
    ".//div[@data-block='PMIB_DataSheetView.Block_Expression']//span[@data-expression]",
    XPATH_VIEW_ROTULO_DE_SECAO.lstrip(),                 # rótulo, padrão B
    XPATH_VIEW_OPCAO_MARCADA.lstrip(),                   # valor, padrão B
))

# Predicado que separa VALOR de RÓTULO dentro da varredura, aplicado ao nó de
# índice `i` da união. Um `<span data-expression>` é valor do padrão A; um
# `<label>` (que só entra na união pelo ramo `[not(span)]`) é valor do padrão
# B. Todo o resto é rótulo.
#
# Uma pergunta por nó, e não três: o extrator só precisa saber "isto é valor?"
# -- `parear_rotulos_e_valores` não distingue os dois padrões, e é de propósito
# (a ordem é a mesma nos dois; só a origem muda).
PREDICADO_VIEW_E_VALOR = "self::span[@data-expression] or self::label"


# ---------------------------------------------------------------------------
# 8. Características técnicas — a purga que preserva o CÓDIGO PMIB
# ---------------------------------------------------------------------------
# "Vai haver 4 seções; devemos apagar 3 e deixar somente a da imagem anexa.
# Nesse campo devemos preencher o código da ficha original."
#
# Estes seletores NÃO foram inventados: são os do módulo antigo
# (`ficha_duplicada.InjetorFichaAlvo._limpar_caracteristicas_tecnicas`), que
# roda contra o portal real há meses. Copiá-los é a decisão certa mesmo na
# reconstrução -- seletor que funciona é conhecimento caro, e a Fase 6 está
# trocando o MOTOR e a ESTRUTURA, não redescobrindo o DOM.
XPATH_CARACTERISTICAS_ABA = (
    "//button[@role='tab' and contains(., 'Características técnicas')]"
)
XPATH_CARACTERISTICAS_LINHAS = (
    "//div[contains(@id, 'TechnicalCharacteristics')]//table/tbody/tr"
)
# O container da seção -- âncora para achar o SALVAR DELA, e não o primeiro da
# tela (ver `PMIBPortal.XPATH_SALVAR_DO_BLOCO` e o defeito de 2026-08-20).
XPATH_CARACTERISTICAS_SECAO = "//div[contains(@id, 'TechnicalCharacteristics')]"
# Relativos à linha (ver `PREFIXO_RELATIVO` no inventário): sozinhos casariam
# a célula de QUALQUER linha, e um "existe" desses não prova nada.
XPATH_REL_CARACTERISTICA_DESCRICAO = ".//td[contains(@data-header, 'Descrição')]"
XPATH_REL_CARACTERISTICA_VALOR_PT = ".//textarea[contains(@id, 'TextArea_ValuePT')]"

# A tabela é PAGINADA, e o módulo antigo já tratava isso: apagar a página 1 não
# apaga a ficha: as características das páginas seguintes continuariam lá.
XPATH_CARACTERISTICAS_PROXIMA_PAGINA = (
    "//button[@aria-label='Ir para a página seguinte']"
)

# ⚠️ A leitura da descrição TEM de ser por `textContent`, não pelo texto
# visível. O módulo antigo usa `get_attribute("textContent")` e o motivo é
# concreto: numa tabela paginada e rolável, a célula da linha que está fora da
# viewport devolve string VAZIA em `.text`. Se a descrição vier vazia, nenhuma
# linha casa "CODIGO PMIB" -- e a purga apaga JUSTAMENTE a linha que deveria
# preservar, deixando a ficha sem a única característica que ela precisa ter.
#
# O contrato de `RPAEngine.texto()` já garante isso nos dois motores (Selenium
# lê `get_attribute("textContent")`, Playwright lê `text_content()`), então
# aqui é só o registro de por que isso importa -- se alguém "otimizar" o
# contrato para texto visível, este comentário é o aviso.


# ---------------------------------------------------------------------------
# 9. Fabricante x fornecedor: como distinguir as duas linhas
# ---------------------------------------------------------------------------
# HTML levantado pelo usuário em 2026-08-17, depois de o robô escrever na linha
# errada. São três achados, e cada um resolve um pedaço:
#
# 1. O COMBO SE IDENTIFICA SOZINHO enquanto está vazio:
#
#      <div class="vscomp-toggle-button">
#        <div class="vscomp-value" data-tooltip="Selecione um fabricante">
#          Selecione um fabricante</div>
#
#    O placeholder NOMEIA o campo. O combo do fornecedor diz "fornecedor" no
#    mesmo lugar. É um discriminador direto -- e vale exatamente no momento em
#    que precisamos dele, antes de escolher. Depois de escolhido, o tooltip
#    vira o nome do fabricante e o discriminador se perde; por isso ele é a
#    PRIMEIRA estratégia, não a única.
#
# 2. A CAIXA DE BUSCA também nomeia:
#
#      <input class="vscomp-search-input" placeholder="Pesquisar um fabricante ">
#
#    (com espaço no fim -- daí `contains`, e não igualdade).
#
# 3. O CAMPO DE REFERÊNCIA SÓ APARECE DEPOIS DE ESCOLHER O FABRICANTE:
#    *"daí quando seleciona uma caixa do dropdown aparece o campo de referência
#    à direita"*. É o achado mais útil dos três, porque transforma "qual dos
#    campos de Referência é o certo?" numa pergunta com resposta objetiva:
#    **é o que não existia antes**. Ver `duplicadas_injetor.escolher_fabricante`.
PLACEHOLDER_COMBO_FABRICANTE = "fabricante"
# O combo do fornecedor diz "fornecedor" no mesmo lugar -- é o que separa
# as duas linhas da seção, e é a mesma mecânica dos dois lados.
PLACEHOLDER_COMBO_FORNECEDOR = "fornecedor"

XPATH_COMBO_POR_PLACEHOLDER = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-toggle-button ')]"
    "[.//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-value ')]"
    "[contains(@data-tooltip, {texto})]]"
)
XPATH_BUSCA_POR_PLACEHOLDER = (
    "//input[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-search-input ')]"
    "[contains(@placeholder, {texto})]"
)

# O campo de Referência e o "+" da MESMA linha compartilham o caminho do bloco
# no OutSystems:
#
#      <input id="b10-b11-b4-Input_TextVar">          (referência)
#      <div data-block="Content.Tooltip" id="b10-b11-b4-$b6">  (o "+")
#
# O prefixo `b10-b11-b4-` é gerado e NÃO deve ser escrito no código (ver
# `IDS_GERADOS_NAO_USAR`) -- mas pode ser LIDO em tempo de execução e usado
# para amarrar os dois. É a diferença entre depender de um id e usar a
# estrutura que ele revela.
XPATH_POR_ID = "//*[@id={id}]"
XPATH_ADICIONAR_DO_BLOCO = (
    "//*[starts-with(@id, {prefixo})]"
    "//a[.//i[contains(concat(' ', normalize-space(@class), ' '), ' fa-plus-circle ')]]"
)
SUFIXO_ID_REFERENCIA = "Input_TextVar"


# ---------------------------------------------------------------------------
# 10. A referência da GE Vernova — o terceiro campo da seção
# ---------------------------------------------------------------------------
# Levantado pelo usuário em 2026-08-17: *"outro botão que eu havia esquecido, é
# o de referência da GE Vernova; quando a coluna CÓDIGO CMI ou CÓDIGO GE
# estiver preenchida no _STATUS_PMIB vale a pena preencher esse campo, com o
# valor da coluna"*.
#
# ⚠️ ELE CORRIGE UMA SUPOSIÇÃO MINHA. Eu havia implementado a referência do
# fornecedor como "seleciona GE no combo e escreve no campo que nascer" -- por
# simetria com o fabricante. O HTML mostra que **não há combo**: a linha da GE
# Vernova é um campo FIXO, que já está na tela, com um "+" próprio. Simetria é
# hipótese, não evidência.
#
# O que a distingue da linha do fabricante é estrutural e visível no markup: o
# container dela tem um ÍCONE DE INFORMAÇÃO entre o rótulo e o campo.
#
#   fabricante:   <label>Referência</label><span class="input-text"><input …>
#   GE Vernova:   <label>Referência</label>
#                 <div data-block="Content.Tooltip"><i class="fa fa-info-circle">…
#                 <span class="input-text"><input …>
#
# Casar pelo ícone é melhor do que casar por posição ("o terceiro campo"):
# posição muda quando o portal reordena a tela, e um campo a mais na seção
# faria o robô escrever no lugar errado sem nenhum aviso.
# ⚠️ A ÂNCORA É O CONTAINER IMEDIATO, e a primeira versão errou isso: escrita
# como `//div[tem Referência][tem ícone]//input[...]`, ela casava QUALQUER div
# ancestral que contivesse as duas coisas em qualquer lugar -- inclusive o
# `<div>` da seção inteira, que contém as três linhas. O resultado eram 3
# "campos da GE" em vez de 1. `ancestor::div[…][1]` é o que diz "o container
# MAIS PRÓXIMO", e é ele que representa a linha.
XPATH_REFERENCIA_GE_INPUT = (
    "//input[contains(@id, 'Input_TextVar')]"
    "[ancestor::div[.//span[normalize-space()='Referência']][1]"
    "[.//i[contains(concat(' ', normalize-space(@class), ' '), ' fa-info-circle ')]]]"
)

# Contraparte: os campos de Referência que NÃO são o da GE Vernova (fabricante
# e fornecedor). Necessário porque `XPATH_REFERENCIA_INPUT` casa os três, e o
# "campo que nasceu" do fabricante seria confundido com este se um dia ele
# passasse a ser renderizado junto.
XPATH_REFERENCIA_INPUT_SEM_GE = (
    "//input[contains(@id, 'Input_TextVar')]"
    "[ancestor::div[.//span[normalize-space()='Referência']][1]"
    "[not(.//i[contains(concat(' ', normalize-space(@class), ' '), ' fa-info-circle ')])]]"
)

# ---------------------------------------------------------------------------
# 11. Navegação entre as SEÇÕES da ficha, no modo de visualização
# ---------------------------------------------------------------------------
# HTML levantado pelo usuário em 2026-08-18. Era o que faltava para o CP 6.4:
# até aqui o extrator só sabia ler a seção que já estivesse aberta.
#
#   <button data-advancedhtml="" class="osui-tabs__header-item"
#           name="0.4z9qbl6cvoj" data-tab="1" role="tab" tabindex="-1"
#           aria-selected="false" aria-controls="b12-$b12">
#     <div class="display-contents ph" id="b12-b5-Title">Fabricantes e fornecedores</div>
#   </button>
#
# ⚠️ TRÊS coisas nesse markup NÃO servem de âncora, e as três parecem servir:
#
#   name="0.4z9qbl6cvoj"   aleatório por renderização (o `0.` denuncia)
#   aria-controls="b12-$b12"  id gerado, com o `$` que já catalogamos
#   data-tab="1"           ORDINAL. Não é gerado, é a posição -- e posição é
#                          justamente o que muda quando o portal reordena a
#                          tela. O projeto já decidiu contra isso em §6.5c
#                          ("casar pelo ícone é melhor do que casar por
#                          posição"); vale igual aqui.
#
# O que resta, e é o que se usa: o TEXTO do `<div>` interno. É o mesmo que o
# usuário lê na tela, e é o que ele nos passou.
ABA_FABRICANTES_E_FORNECEDORES = "Fabricantes e fornecedores"
# ⚠️ A ABA TEM NOMES DIFERENTES NOS DOIS MODOS, e foi o que produziu
# `[Erro] A aba 'Documentos' não existe nesta tela` na rodada de 2026-08-20.
#
#   visualização: "Documentos"            -- só documentos; as imagens ficam
#                                            sempre visíveis, num carrossel
#   edição:       "Documentos e imagens"  -- aria-controls="…-DocumentsandImages_Content"
#
# Não dá para unificar num nome só: o texto é o que o usuário lê na tela, e é
# ele o casamento (`XPATH_ABA_DA_FICHA`). Duas constantes, e cada chamador diz
# em que modo está -- que é informação que ele tem e o seletor não.
ABA_DOCUMENTOS = "Documentos"
ABA_DOCUMENTOS_EDICAO = "Documentos e imagens"
ABA_CONDICOES = "Condições"

XPATH_ABA_DA_FICHA = (
    "//button[contains(concat(' ', normalize-space(@class), ' '), ' osui-tabs__header-item ')]"
    "[.//div[normalize-space()={texto}]]"
)
# Conferência pós-clique: `aria-selected` vira "true" na aba aberta. Sem ela,
# um clique que não pegou (aba coberta, render em andamento) faria o extrator
# ler a seção ANTERIOR e devolver dados plausíveis da seção errada -- que é o
# pior tipo de falha, porque não parece falha.
XPATH_ABA_DA_FICHA_ATIVA = (
    "//button[contains(concat(' ', normalize-space(@class), ' '), ' osui-tabs__header-item ')]"
    "[@aria-selected='true'][.//div[normalize-space()={texto}]]"
)


# ---------------------------------------------------------------------------
# 12. As sub-abas DENTRO de Condições (modo de visualização)
# ---------------------------------------------------------------------------
#   <div data-container="" class="dummy-active OSInline"
#        style="text-align: center; cursor: pointer; width: 20%; padding: 8px;">
#     Armazenamento e transporte</div>
#   <div data-container="" class="OSInline" style="...">Manutenção e descarte</div>
#
# Não são `role="tab"` -- são `<div>` com `cursor: pointer`. Ou seja, o seletor
# das abas de cima (§11) NÃO serve aqui, e supor que servisse era plausível:
# é exatamente o tipo de generalização que a §7 dos seletores manda não fazer
# sem HTML na mão.
#
# 🎯 `dummy-active` marca a sub-aba ABERTA. É o par da conferência de
# `aria-selected` -- e aqui ela vale mais ainda, porque as três sub-abas ficam
# todas no DOM: sem checar qual está ativa, o extrator lê a primeira e acha
# que leu a que pediu.
#
# Confirma a tabela de §3.4 da especificação: visualização tem 3 sub-abas
# (Armazenamento e transporte | Financeira | Manutenção e descarte), contra 5
# no modo de edição. A Financeira é a que `e_aba_financeira` exclui.
CLASSE_SUBABA_ATIVA = "dummy-active"

XPATH_SUBABA_CONDICOES = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' OSInline ')]"
    "[normalize-space()={texto}]"
)
XPATH_SUBABA_CONDICOES_ATIVA = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' dummy-active ')]"
    "[normalize-space()={texto}]"
)


# ---------------------------------------------------------------------------
# 13. Fabricantes e fornecedores em VISUALIZAÇÃO — são DUAS TABELAS
# ---------------------------------------------------------------------------
# ⚠️ ESTE ACHADO DERRUBA UMA SUPOSIÇÃO DO EXTRATOR, e é o mais importante do
# levantamento de 2026-08-18.
#
# A seção NÃO é um bloco de pares rótulo→valor. São duas tabelas irmãs:
#
#   <div class="full-fieldset" id="b12-b13-ManufacturerAndProvider">
#     <table><thead><tr><th>Nome do Fabricante</th><th>Referência</th></tr></thead>
#     <tbody>
#       <tr><td data-header="Nome do Fabricante"><span data-expression>ENERSYS</span></td>
#           <td data-header="Referência"><span data-expression>E24-256-10</span></td></tr>
#       <tr><td data-header="Nome do Fabricante"><span data-expression>SASSI</span></td>
#           <td data-header="Referência"><span data-expression>DGA 0-300V DC</span></td></tr>
#
#   <div class="full-fieldset" id="b12-b14-ManufacturerAndProvider">
#     <table><thead><tr><th>Nome do Fornecedor</th><th>Referência</th></tr></thead>
#     <tbody>
#       <tr><td data-header="Nome do Fornecedor"><span data-expression>GE ENERGIAS RENOVAVEIS LTDA</span></td>
#           <td data-header="Referência"><span data-expression>08934120BTM99-064F</span></td></tr>
#
# Consequência prática, e ela explica um sintoma: `XPATH_VIEW_VALOR` exige o
# ancestral `data-block='PMIB_DataSheetView.Block_Expression'`, e estas células
# NÃO o têm. Ou seja, a varredura de rótulo→valor **não enxerga esta seção**
# -- `achar_fabricante`/`achar_fornecedor` lendo de `blocos` devolveriam vazio
# para esta ficha. A seção precisa de leitor próprio.
#
# 🎯 OS DOIS CONTÊINERES TÊM O MESMO SUFIXO DE id (`-ManufacturerAndProvider`),
# só mudando o prefixo gerado (`b12-b13-` x `b12-b14-`). Então o id NÃO
# distingue fabricante de fornecedor -- quem distingue é o `@data-header` da
# célula, que é o MESMO atributo semântico que `tech_specs` já usa para achar
# coluna de tabela do OutSystems.
#
# E o `<tbody>` pode ter VÁRIAS linhas: nesta ficha o fabricante tem duas
# ("a gente comprou de um que comprou do fabricante" -- ENERSYS fabrica, SASSI
# revende). Ler só a primeira perderia a segunda sem avisar.
COLUNA_NOME_FABRICANTE = "Nome do Fabricante"
COLUNA_NOME_FORNECEDOR = "Nome do Fornecedor"
COLUNA_REFERENCIA = "Referência"

# Linhas de uma das tabelas, escolhida pelo texto do cabeçalho da 1ª coluna.
# `ancestor::table[1]` é o container MAIS PRÓXIMO -- a mesma armadilha de §6.5c
# vale aqui: sem o `[1]`, um ancestral que contenha as duas tabelas casaria as
# duas e o fabricante viria com a linha da GE junto.
XPATH_LINHAS_DA_TABELA_DE = (
    "//td[@data-header={coluna}]/ancestor::table[1]//tr[td[@data-header={coluna}]]"
)

# ⚠️ "Descrição" NÃO É EXCLUSIVA DOS DOCUMENTOS -- e isso fez o robô, em
# 2026-08-20, ler as CARACTERÍSTICAS e sair procurando "TENSÃO DE ENTRADA" no
# catálogo de documentos. As duas tabelas têm a coluna:
#
#     características:  Ordem | Código | Descrição | Valor
#     documentos:                      | Descrição | …
#
# Sem escopo, `//td[@data-header='Descrição']` casa a página inteira e
# `ancestor::table[1]` fica com a primeira em ordem de documento.
#
# O discriminador "óbvio" não serve: a célula do documento vem aninhada em
# `Content.Tooltip`, mas o dump prova que a de CARACTERÍSTICA tem o mesmo
# aninhamento. O que discrimina é semântico e está no HTML das abas:
#
#     <button role="tab" aria-controls="b12-$b15">Características Técnicas</button>
#     <button role="tab" aria-controls="b12-$b17">Documentos</button>
#
# `aria-controls` aponta o PAINEL da seção. O id é gerado (não se escreve no
# código), mas pode ser LIDO em tempo de execução -- a mesma técnica do
# prefixo do campo de referência.
XPATH_PAINEL_POR_ID = "//*[@id={id}]"
# Célula de uma coluna dentro de UMA linha já endereçada por índice.
XPATH_REL_CELULA = "/td[@data-header={coluna}]//span[@data-expression]"


# ---------------------------------------------------------------------------
# 14. Documentos — o TERCEIRO padrão de aninhamento do valor
# ---------------------------------------------------------------------------
# HTML levantado pelo usuário em 2026-08-18, nos DOIS modos. A descrição do
# documento não é `span` solto nem valor de bloco de leitura: vem dentro de um
# TOOLTIP.
#
#   <td data-header="Descrição">
#     <div data-block="Content.Tooltip" id="…-l1_0-227_0-$b6">
#       <div class="osui-tooltip osui-tooltip--is-hover" name="0.2r2d7ttp763" …>
#         <div class="osui-tooltip__content" role="button" tabindex="0">
#           <span data-expression="">1188 web replaced</span>
#
# ⚠️ CONSEQUÊNCIA, e ela repete a lição das tabelas (§13): `XPATH_VIEW_VALOR`
# exige o ancestral `data-block='PMIB_DataSheetView.Block_Expression'`, e aqui
# o bloco é `Content.Tooltip`. A varredura de rótulo→valor **também não
# enxerga os documentos**. Já são três seções que ela não cobre -- o padrão de
# §8 vale para os campos de formulário, não para tabelas.
#
# 🎯 O que salva é o `//span` de `XPATH_REL_CELULA` (§13) ser DESCENDENTE em
# qualquer profundidade: o mesmo seletor que lê a célula rasa do fabricante lê
# a célula aninhada do documento. Isso não foi sorte -- `/td[…]/span` teria
# funcionado no fabricante e falhado aqui, em silêncio. Tem teste com os dois
# markups para o `//` não virar `/` numa "simplificação" futura.
#
# Os dois modos usam a MESMA estrutura, mudando só o prefixo gerado:
#   edição:       b10-b15-b19-l1_0-227_0-…
#   visualização: b12-b18-l1_0-452_0-…
# `-l1_0-` já está em `IDS_GERADOS_NAO_USAR` (índice de linha do OutSystems).
COLUNA_DESCRICAO = "Descrição"

# Linha do documento, casada pela descrição EXATA na coluna certa.
#
# Substitui o casamento por substring em qualquer `<td>` que
# `XPATH_DOCUMENTOS_LINHA` faz: uma descrição curta ("1188") apareceria também
# numa coluna de data ou de código, e associar o documento errado é do tipo de
# erro que ninguém percebe -- o diálogo fecha igual.
XPATH_DOCUMENTO_LINHA_POR_DESCRICAO = (
    "//td[@data-header='Descrição'][.//span[@data-expression][normalize-space()={texto}]]"
    "/ancestor::tr[1]"
)

# Checkbox DENTRO de uma linha já endereçada.
#
# `XPATH_DOCUMENTOS_CHECKBOX_DA_LINHA` (§6.5) ancora em
# `td[@data-header='Selecionar']`, que foi levantado do DOM e continua sendo a
# 1ª escolha. Este é o plano B: o HTML de 2026-08-18 mostra o input dentro de
# `<div class="display-flex justify-content-center">`, sem que a captura
# revele o `<td>` em volta -- então não dá para AFIRMAR que a coluna se chama
# "Selecionar" em toda tela. Procurar o checkbox na própria linha é verdadeiro
# nos dois casos, e a linha já foi escolhida pela descrição.
XPATH_DOCUMENTO_CHECKBOX_QUALQUER = ".//input[@type='checkbox']"

# `data-checkbox` é o marcador semântico do widget (o `id` traz `-l1_0-`, que
# é índice de linha e muda a cada busca).
XPATH_DOCUMENTO_CHECKBOX_SEMANTICO = ".//input[@data-checkbox][@type='checkbox']"


# ---------------------------------------------------------------------------
# 15. CONDIÇÕES no modo de EDIÇÃO — a cópia literal, campo a campo
# ---------------------------------------------------------------------------
# CP 6.4. O mapa abaixo é portado de `ficha_duplicada.ExtratorFichaBase.
# _ler_condicoes` / `InjetorFichaAlvo._preencher_condicoes` -- o módulo antigo,
# que roda contra o portal real. Não é levantamento novo: é o que já funciona.
#
# 🎯 A IDEIA QUE FAZ ISTO SER BARATO: a cópia é **por XPath**, não por
# significado. Lê-se o valor de `Input_PackingLength` na ficha original e
# escreve-se em `Input_PackingLength` na ficha alvo. Nenhum rótulo precisa ser
# interpretado, nenhuma unidade convertida, nenhum radio traduzido para "SIM"/
# "NÃO" -- é uma duplicação, não um preenchimento.
#
# A alternativa (ler a ficha original em VISUALIZAÇÃO, casando rótulo→valor, e
# depois mapear cada rótulo para o campo certo da edição) exigiria conhecer a
# redação exata de cada rótulo nos dois idiomas, e erraria em silêncio no dia
# em que o portal mudasse uma palavra. Este mapa erra ALTO: XPath que não casa
# é campo que não copia, e o log diz qual.
#
# ⚠️ CONSEQUÊNCIA: a ficha ORIGINAL precisa ser aberta em modo de EDIÇÃO para a
# leitura -- é o único modo em que estes `input`/`textarea` existem. Nada é
# salvo nela; `duplicadas_condicoes.ler` só lê. É o que o módulo antigo já faz.
#
# `contains(@id, ...)` e não o id inteiro: o prefixo (`b10-b17-b1-`) é gerado
# pelo OutSystems e muda de sessão para sessão -- ver `IDS_GERADOS_NAO_USAR`.
XPATH_CONDICOES_ABRIR_SECAO = "//*[contains(@id, 'Conditions_Header')]//button"

# As sub-abas na EDIÇÃO são divs posicionais dentro do cabeçalho `Title`. É o
# que o módulo antigo usa e o que `upload_conditions` usa (lá com o id inteiro,
# que este projeto proíbe). Armazenamento é a aba que já vem aberta.
XPATH_CONDICOES_SUBABA = "//*[contains(@id, 'Title')]/div[{posicao}]"

# Nome da sub-aba -> (posição no cabeçalho, campos de TEXTO, campos BOOLEANOS).
# `None` na posição = a aba que já está aberta quando a seção abre.
CONDICOES_POR_SUBABA = {
    "Armazenamento": {
        "posicao": None,
        "textos": (
            "Input_PackingLength", "Input_PackagingWidth", "Input_PackagingHeight",
            "Input_LiquidWeight", "Input_GrossWeight", "Input_Stacking",
            "TextArea_StorageCareES", "TextArea_StorageCarePT",
            "TextArea_OtherCareES", "TextArea_OtherCarePT",
        ),
        "booleanos": (
            "RadioButton5-input", "RadioButton4-input",
            "Checkbox4", "Checkbox5",
            "RadioButton-input", "RadioButton7-input", "RadioButton8-input",
            "RadioButton2-input", "RadioButton1-input",
            "Checkbox3", "Checkbox6", "Checkbox7", "Checkbox8",
            "RadioButton6-input", "RadioButton3-input",
        ),
    },
    "Transporte": {
        "posicao": 3,
        "textos": (
            "TextArea_TransportPackagingES", "TextArea_TransportPackagingPT",
            "TextArea_PositionCareES", "TextArea_PositionCarePT",
        ),
        "booleanos": (),
    },
    "Manutenção": {
        "posicao": 4,
        "textos": (
            "TextArea_PreservationCareES", "TextArea_PreservationCarePT",
            "TextArea_CleaningMethodES", "TextArea_CleaningMethodPT",
            "TextArea_ToolPreservationES", "TextArea_ToolPreservationPT",
        ),
        "booleanos": (),
    },
    "Descarte": {
        "posicao": 5,
        "textos": (
            "TextArea_TypeLegislationES", "TextArea_TypeLegislationPT",
            "TextArea_DiscardTypeES", "TextArea_DiscardTypePT",
            "TextArea_ReserveLogisticES", "TextArea_ReserveLogisticPT",
        ),
        # ⚠️ Estes quatro aparecem TAMBÉM em Armazenamento no mapa antigo
        # (`RadioButton1-input`, `RadioButton2-input`). Não é engano de
        # transcrição: `contains(@id, ...)` casa o campo de QUALQUER sub-aba
        # que tenha esse sufixo, e cada aba renderiza os seus. Ler e escrever
        # com a mesma sub-aba aberta mantém a simetria -- é o que torna a
        # cópia correta apesar do seletor ser ambíguo fora de contexto.
        "booleanos": (
            "RadioButton1-input", "RadioButton2-input",
            "Applies-input", "DoesNotApply-input",
        ),
    },
}

XPATH_CONDICOES_CAMPO = "//*[contains(@id, {sufixo})]"


# ---------------------------------------------------------------------------
# 16. O PDM da ficha ALVO — conferir ANTES de mexer nas características
# ---------------------------------------------------------------------------
# Achado do usuário em 2026-08-20, depois da rodada real: *"a ficha 922 estava
# com um PDM diferente, então as características técnicas não estavam corretas
# na ficha. Devemos primeiro ver que tipo de PDM é a ficha alvo."*
#
# 🎯 POR QUE ISSO É PRÉ-REQUISITO, E NÃO UM DETALHE: **o PDM determina QUAIS
# características a ficha tem.** A 4500063671.0922 estava com
# `PDM.4820.010 - REGULADOR, PRESSAO` e o robô apagou as 26 características
# daquele PDM procurando uma linha `CODIGO PMIB` que ali não existe -- saiu
# com "26 apagada(s), 0 preservada(s)" e a ficha sem a característica da
# duplicação. Trocar o PDM DEPOIS não desfaz isso.
#
# A ordem certa é: trocar o PDM para o da duplicada, SALVAR (aí o portal
# renderiza as características do PDM novo), e só então purgar.
#
# HTML do combo, levantado pelo usuário:
#
#   <div class="vscomp-toggle-button">
#     <div class="vscomp-value" data-tooltip="PDM.4820.010 - REGULADOR, PRESSAO, R1"
#          …>PDM.4820.010 - REGULADOR, PRESSAO, R1</div>
#     <div class="vscomp-arrow"></div>
#     …
#
# É o MESMO widget `virtual-select` do fabricante -- muda só o que o
# `data-tooltip` diz. Por isso o combo se identifica pelo prefixo "PDM.": ele
# está lá com o PDM que for, e nenhum outro combo da tela começa assim.
PDM_DA_DUPLICADA = "PDM.9900.000"
# ⚠️ SÓ O PREFIXO. O texto completo é "PDM.9900.000 - FICHA PMIB, DUPLICADA,
# R0" e *"a revisão R0 pode mudar"* (usuário). Casar o texto inteiro faria o
# robô parar de achar o PDM no dia em que a revisão virasse R1 -- e o sintoma
# seria "não achei no combo", que ninguém liga a uma revisão nova.
NOME_DA_ABA_INFO_GERAIS = "Informações gerais"

XPATH_PDM_COMBO = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-toggle-button ')]"
    "[.//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-value ')]"
    "[starts-with(@data-tooltip, 'PDM.')]]"
)
XPATH_PDM_VALOR = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-value ')]"
    "[starts-with(@data-tooltip, 'PDM.')]"
)
# A opção casada pelo PREFIXO, pelo motivo da revisão acima.
XPATH_PDM_OPCAO_POR_PREFIXO = (
    "//div[@role='option']"
    "//span[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-option-text ')]"
    "[starts-with(@data-tooltip, {texto})]"
)

# Âncora para achar o SALVAR **desta** seção (ver `XPATH_SALVAR_DO_BLOCO` e o
# defeito de 2026-08-20). O id vem do `aria-controls` da aba, que o usuário
# mandou: `aria-controls="b10-GeneralInformations_Content"`.
XPATH_INFO_GERAIS_SECAO = "//*[contains(@id, 'GeneralInformations')]"

# ---------------------------------------------------------------------------
# 17. A linha do CÓDIGO PMIB — os TRÊS campos, não só o português
# ---------------------------------------------------------------------------
# *"A 3626 - CODIGO PMIB deve ser preenchida com a ficha original, tanto no
# campo de espanhol quanto no de português, e colocar a unidade adimensional."*
# (usuário, 2026-08-20)
#
# Até aqui só o português era preenchido. Os sufixos são os mesmos que
# `tech_specs` usa há meses para preencher característica -- não é
# levantamento novo.
XPATH_REL_CARACTERISTICA_VALOR_ES = './/textarea[contains(@id, "TextArea_ValueES")]'
XPATH_REL_CARACTERISTICA_UNIDADE = (
    './/select[contains(@id, "DropdownTCUnitsOfMeasurement")]'
)
# O símbolo da unidade adimensional no Master de PDMs. `tech_specs` já usa
# exatamente este ("AD") como o valor que significa "sem unidade".
SIMBOLO_ADIMENSIONAL = "AD"


# ---------------------------------------------------------------------------
# 18. IMAGENS — copiar (baixar da original, subir na alvo)
# ---------------------------------------------------------------------------
# HTML levantado pelo usuário em 2026-08-20. É a última seção do CP 6.4, e a
# única que NÃO se resolve associando: documento já existe como objeto no
# portal; imagem é arquivo, e tem de sair de uma ficha e entrar na outra.
#
# VISUALIZAÇÃO -- as imagens ficam sempre visíveis, num carrossel `splide`:
#
#   <div class="splide__slide is-active is-visible" aria-label="1 of 3">
#     …<img data-image="" class="custom-img"
#           src="blob:https://apps.itaipu.gov.br/29077935-75a6-…">
#     …<figcaption><span data-expression="">Botão</span></figcaption>
#
# ⚠️ `splide` CLONA slides para o laço infinito. Contar `.splide__slide` sem
# filtrar clone faria a mesma imagem ser copiada duas ou três vezes -- e o
# portal aceitaria as três, porque para ele são uploads distintos.
XPATH_IMAGENS_SLIDES = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' splide__slide ')]"
    "[not(contains(@class, 'clone'))]"
)
XPATH_REL_IMAGEM_DO_SLIDE = (
    ".//img[contains(concat(' ', normalize-space(@class), ' '), ' custom-img ')]"
)
# A legenda da imagem na original. Quando existe, é ela que vai para a ficha
# nova -- é mais fiel do que qualquer texto que a gente invente.
XPATH_REL_LEGENDA_DO_SLIDE = ".//figcaption//span[@data-expression]"

# EDIÇÃO -- o formulário de adicionar. Os três campos são preenchidos por
# imagem: descrição em espanhol, em português, e o arquivo.
#
# `XPATH_IMAGENS_ABRIR` casa o `<a>` que envolve o rótulo; a variante do span
# existe porque a captura do usuário mostra só o `<span class="margin-left-s">
# Adicionar imagens</span>`, sem revelar o que há em volta.
XPATH_IMAGENS_ABRIR_SPAN = "//span[normalize-space()='Adicionar imagens']"

# ⚠️ QUEM GRAVA A IMAGEM É ESTE BOTÃO, não o SALVAR da seção. Levantado pelo
# usuário em 2026-08-20, depois de o robô gastar 20 s de timeout tentando o
# SALVAR -- que fica inacessível enquanto o diálogo de imagem está aberto:
#
#   <button data-button="" class="btn btn-primary text-uppercase"
#           type="button">Confirmar</button>
#
# E o portal responde com toast próprio: "A imagem foi adicionada com
# sucesso!" (ver `PALAVRA_DA_SECAO`).
XPATH_IMAGENS_CONFIRMAR = "//button[normalize-space()='Confirmar']"

# O `<li>` que o FilePond cria quando ACEITA o arquivo. É a prova de que o
# upload entrou -- sem ela, "enviei o arquivo" é só "chamei a função".
XPATH_IMAGENS_ITEM_NA_LISTA = (
    "//ul[contains(concat(' ', normalize-space(@class), ' '), ' filepond--list ')]/li"
)

# Assinaturas de arquivo. O `<input>` declara `accept="image/jpeg,image/png"`,
# então o portal recusa qualquer outra coisa -- e o nome do arquivo temporário
# precisa da extensão certa para o navegador anunciar o MIME certo.
ASSINATURAS_DE_IMAGEM = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
)


# O ESTADO do item no FilePond, que é diferente da existência dele.
#
# ⚠️ 2026-08-21, do log do usuário: a imagem entrava na lista e o "Confirmar"
# vinha logo depois, com uma pausa FIXA de 2 s no meio. O portal não devolvia
# toast nenhum e a seção fechava como falha. Hipótese do usuário, e ela bate
# com o funcionamento do FilePond: *"quando carregamos uma imagem, pode ser que
# demore a fazer o upload, e talvez seja esse o erro, tentar clicar antes de
# esperar dar o upload"*.
#
# O `<li>` nasce quando o arquivo é ACEITO; o processamento vem depois, e o
# FilePond o anuncia em `data-filepond-item-state`. Os estados que interessam:
#
#     processing            está subindo AGORA
#     processing-complete   terminou  (contém "processing" -- daí o `not`)
#     load-invalid / error  recusado
#
# Esperar o estado, em vez de dormir um número fixo, é a diferença entre
# "confirmei depois que subiu" e "confirmei depois de 2 segundos".
XPATH_IMAGENS_ITEM_PROCESSANDO = (
    "//*[@data-filepond-item-state]"
    "[contains(@data-filepond-item-state, 'processing')]"
    "[not(contains(@data-filepond-item-state, 'processing-complete'))]"
)
XPATH_IMAGENS_ITEM_COM_ESTADO = "//*[@data-filepond-item-state]"

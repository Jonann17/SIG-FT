r"""
sigft/core/rpa/portal.py — `PMIBPortal`: mecânica de interação com o portal
PMIB, sobre um `RPAEngine` (Checkpoint 2.2 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.2, diagnóstico
seção 1.1 ("Duplicação de RPA"): `safe_click` (4x idêntico), `safe_send_keys`
(3 variantes), loop lixeira+CONFIRMAR (3x), flag de parada (4x), pesquisar+
lápis (6 variantes/módulos) e URL do portal hardcoded (10+ ocorrências).

Este módulo é a camada "PMIBPortal ... a API pública é definida em termos de
intenção (`clicar`, `preencher`, `esperar_linha`, `pesquisar_e_abrir`), não
de Selenium" citada na nota introdutória da Fase 2 do plano. Mas nem toda
mecânica abaixo é coberta pela interface abstrata de `RPAEngine` (CP 2.1):
`StaleElementReferenceException`, `current_url`, `find_elements` de uma LINHA
já localizada, ou o atributo `checked` de um checkbox não têm equivalente no
contrato de intenção de `engine.py`. Por isso `PMIBPortal` acessa
`self.engine.driver`/`self.engine.wait` DIRETAMENTE quando precisa (aceitável
nesta fase — "a Fase 2 ainda roda sobre Selenium... a implementação interna
de PMIBPortal pode ser Selenium-specific por enquanto; a Fase 5 é quem
generaliza de verdade", ver plano). `SeleniumEngine` (CP 2.1) já expõe esses
2 atributos publicamente para esse fim.

IMPORTS SELENIUM NESTE ARQUIVO (decisão registrada em
docs/refatoracao/PENDENCIAS.md): o aceite do checkpoint autoriza
explicitamente `selenium.common.exceptions` ("exceptions, temporariamente")
em `portal.py`/serviços; `By` é necessário para construir os locators
`(By.XPATH, seletor)` que `self.engine.driver`/`self.engine.wait` (objetos
Selenium reais) entendem. Além desses dois, este módulo também importa
`expected_conditions` (`EC`) e `Keys` — NÃO citados literalmente pelo texto
do aceite, mas necessários para reproduzir `presence_of_element_located`/
`element_to_be_clickable`/`ENTER` EXATAMENTE como os originais (`apagar_lmr`,
`upload_conditions`, `upload_tech_specs`, `upload_ficha_duplicada`) os
usavam — reimplementar essas condições de espera manualmente (via polling
cru) foi avaliado como risco MAIOR (divergência silenciosa da semântica já
testada do Selenium) do que importar um módulo padrão que já é dependência
do projeto (o mesmo `selenium_engine.py` irmão, na mesma pasta `core/rpa/`,
já importa livremente `webdriver`/`By`/`Keys`/`EC`/`WebDriverWait`/
`ActionChains` — este arquivo é, como aquele, infraestrutura Selenium-
specific desta fase, não um "serviço"). O aceite "serviços não importam
selenium diretamente" refere-se aos 6 `*_backend.py`/`upload_ficha_
duplicada.py` (ver seção "Migração dos 6 backends" abaixo) — esses SIM
seguem restritos a `By` + exceções (pelos MUITOS call sites internos que
ainda constroem locators `(By.XPATH, ...)`, ver PENDENCIAS.md).

Cobertura, por método (ver docstring de cada um para o racional específico):
  - `safe_click`/`safe_fill`: delegação FINA para `self.engine.click`/
    `.fill` — a mecânica REAL (scroll + JS click / Ctrl+A+Backspace+texto)
    já vive em `SeleniumEngine` desde o CP 2.1; aqui só o nome de domínio
    ("safe_click") é exposto no nível de intenção do portal.
  - `check_or_uncheck`: só existia em `upload_conditions_backend.py` — só
    "movida" (não duplicada antes).
  - `clicar_salvar_visivel`: só existia em `upload_ficha_duplicada.py`
    (`InjetorFichaAlvo._clicar_salvar_visivel`) — só "movida".
  - `excluir_linha_com_confirmacao`: mecânica CENTRAL comum a
    `upload_tech_specs_backend.TechSpecsAutomation._excluir_linha_segura` e
    `upload_ficha_duplicada.InjetorFichaAlvo._limpar_caracteristicas_tecnicas`
    (ramo de exclusão) — recebe uma LINHA (`row`) já localizada, não busca
    por índice global. `apagar_lmr_backend.executar_limpeza` tem uma 3ª
    variante estruturalmente diferente (busca a 1ª lixeira visível da
    tabela inteira via um XPath ESPECÍFICO desse módulo, sem "linha" para
    passar) — NÃO usa este método; ver docs/refatoracao/PENDENCIAS.md.
  - `pesquisar_e_abrir`: adota a ESTRUTURA de robustez de
    `upload_tech_specs_backend.TechSpecsAutomation._pesquisar_e_abrir` (a
    variante mais robusta: retry 3x, trata `StaleElementReferenceException`/
    `TimeoutException`, retorna bool) para TODOS os módulos, com os
    SELETORES de busca/lápis PARAMETRIZADOS (default = apagar_lmr/
    tech_specs, que já usam exatamente esses; overrides para
    `upload_conditions`/`upload_ficha_duplicada` — ver docstring do método).
  - `solicitar_parada`/`deve_parar`: stop-flag único, usado pelas 2 classes
    x 2 arquivos que já tinham essa flag hoje (`ConditionsProcessor`/
    `UploadAutomation` em `upload_conditions_backend.py`;
    `TechSpecsProcessor`/`TechSpecsAutomation` em
    `upload_tech_specs_backend.py`) — NÃO inventado para os outros 4
    backends (`apagar_lmr`, `lmr`, `cria_fichas`, `upload_ficha_duplicada`),
    que não têm essa flag hoje.
  - `aguardar_login_manual`: capacidade NOVA (o padrão atual é 100% do lado
    do `frontend.py`, via `messagebox.showinfo`/janela de pausa bloqueante
    chamada ANTES de `processar_lista`/`executar_limpeza`) — nasce aqui SEM
    nenhum consumidor de produção ainda, mesmo espírito de `screenshot`/
    `set_download_dir` no CP 2.1 ("capacidade nova sem consumidor").
  - `ir_para_lista`: o padrão `if driver.current_url != URL: driver.get(URL);
    sleep(N)` que abre TODAS as variantes de `pesquisar_e_abrir` — usa
    `sigft.config.PORTAL_URL` (CP 1.1) em vez de qualquer literal local.

`engine` é OPCIONAL (default `None`) por decisão deste checkpoint: as duas
classes de PROCESSAMENTO DE IA que têm stop-flag hoje (`ConditionsProcessor`
em `upload_conditions_backend.py`, `TechSpecsProcessor` em
`upload_tech_specs_backend.py`) não têm driver/browser NENHUM — só chamam a
API do Gemini. Para que a MESMA implementação de stop-flag sirva a essas 2
classes (conforme pedido pelo checkpoint: "migre APENAS as 4 ocorrências
reais... para delegar a isso"), essas 2 constroem um `PMIBPortal()` sem
engine, usado SÓ para `solicitar_parada`/`deve_parar` (que nunca tocam
`self.engine`) — ver docs/refatoracao/PENDENCIAS.md. Qualquer OUTRO método
chamado num `PMIBPortal` sem engine falha com `AttributeError` óbvio
(`self.engine` é `None`), o que é aceitável: essas 2 classes nunca chamam
outra coisa.

CP 2.3 (Fase 2 -> CP 2.3, "Sincronização: sleeps -> waits"): as constantes
`PAUSA_*` logo abaixo (módulo, não atributos de `PMIBPortal`) nomeiam os 72
`time.sleep(<literal numérico>)` que ainda viviam CRUS nos 6 `*_backend.py`/
`upload_ficha_duplicada.py` -- ver o bloco de comentários acima da primeira
constante para o racional completo e docs/refatoracao/PENDENCIAS.md para os
casos limítrofes.
"""

from __future__ import annotations

import time

# CP 5.3: este arquivo não importa mais NADA do Selenium. Os últimos 3 métodos
# que alcançavam `self.engine.driver`/`.wait` crus (`check_or_uncheck`,
# `clicar_salvar_visivel`, `excluir_linha_com_confirmacao`) foram portados para
# as primitivas de `RPAEngine` -- `PMIBPortal` inteiro passa a ser
# motor-agnóstico, que era o que faltava para os uploads rodarem em Playwright.
from sigft import config
from sigft.core.rpa.engine import ElementoObsoleto, RPAEngine, TempoEsgotado

# Seletores DEFAULT de `pesquisar_e_abrir` -- IDÊNTICOS aos de
# `apagar_lmr_backend.ApagarLMRAutomation._pesquisar_e_abrir` e
# `upload_tech_specs_backend.TechSpecsAutomation._pesquisar_e_abrir` (2 dos 4
# sites reais já usam exatamente isso hoje -- ver docstring de
# `pesquisar_e_abrir` abaixo para a lista completa de overrides por módulo).
# CP 5.3: os XPaths que `clicar_salvar_visivel`/`excluir_linha_com_confirmacao`
# tinham embutidos viram constantes -- as primitivas os usam 2x (contar/agir,
# esperar/agir), e literal repetido convida divergência.
XPATH_BOTAO_SALVAR = (
    "//button[contains(@class, 'btn-primary') and normalize-space(text())='SALVAR']"
)
XPATH_CONFIRMAR = '//button[@type="button" and text()="CONFIRMAR"]'

# ⚠️ O SALVAR **DA SEÇÃO**, e não o primeiro da tela (2026-08-20).
#
# A ficha tem QUATRO botões SALVAR -- um por seção. `clicar_salvar_visivel`
# clica o primeiro visível, e na rodada de 2026-08-20 isso gravou Informações
# Gerais cinco vezes seguidas enquanto o log dizia "salvo e conferido" para
# Características e para as quatro sub-abas de Condições. As duas fichas
# saíram vazias.
#
# A fórmula abaixo não precisa saber o id de container nenhum: partindo de um
# elemento QUALQUER da seção (um campo, a div da tabela), ela sobe até o
# ancestral MAIS PRÓXIMO que contenha um SALVAR -- que é o container da seção,
# por construção -- e desce para o botão de lá.
#
# `ancestor-or-self` e não `ancestor`: assim a âncora pode ser o próprio
# container (`//div[contains(@id,'TechnicalCharacteristics')]`) ou um campo
# dentro dele, e os dois funcionam.
#
# ⚠️ SÃO DUAS FÓRMULAS, E A ORDEM ENTRE ELAS É O SEGUNDO CONSERTO (2026-08-20,
# 14h). Com só a subida, o defeito continuou:
#
#     [Injetor] SALVAR da seção Características Técnicas (ancorado…)
#     [!] Não vi a confirmação. A última mensagem foi: 'A Ficha Técnica … foi
#         modificada com sucesso.'   <- genérica, de Informações Gerais
#
# A subida para no primeiro ancestral que CONTENHA um SALVAR. Se a div da
# âncora não contém o seu, ela não para na seção: sobe até o container de
# TODOS os botões, e `//button[SALVAR]` de lá devolve o primeiro do documento.
#
# Olhar PARA DENTRO primeiro resolve o caso normal sem subida nenhuma.
XPATH_SALVAR_DENTRO_DO_BLOCO = "{ancora}//button[normalize-space()='SALVAR']"
XPATH_SALVAR_SUBINDO_DO_BLOCO = (
    "{ancora}/ancestor-or-self::*[.//button[normalize-space()='SALVAR']][1]"
    "//button[normalize-space()='SALVAR']"
)

# --- Confirmação de salvamento (2026-08-18) ---------------------------------
# O portal avisa, em toast, quando gravou uma seção:
#
#     <div class="feedback-message-text">As condições de armazenamento foram
#      modificadas com sucesso!</div>
#
# Levantado pelo usuário com a tela à vista. Até aqui NADA no projeto lia essa
# mensagem: `upload_conditions` clicava em SALVAR, dormia e marcava a ficha
# como COMPLETO na planilha -- sem uma única evidência de que o portal tivesse
# gravado. Uma ficha em que todos os campos falharam saía marcada como pronta,
# e ninguém volta para conferir o que está marcado como pronto.
#
# ⚠️ CASAR SÓ POR "sucesso" NÃO SERVE, e o motivo é a mecânica do toast: ele
# aparece rápido, FICA UM TEMPO e some. Ou seja, quando o robô salva a 2ª
# seção, o toast da 1ª pode ainda estar na tela. Uma checagem de "existe
# mensagem de sucesso?" leria o toast VELHO e daria seção gravada sem ter
# sido -- exatamente o erro que este código existe para impedir.
#
# Por isso o casamento exige a PALAVRA DA SEÇÃO. Um toast remanescente de
# outra seção não casa, o laço continua esperando, e o erro cai para o lado
# seguro (falso negativo: pendência a conferir, em vez de COMPLETO mentiroso).
XPATH_MENSAGEM_DE_FEEDBACK = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' feedback-message-text ')]"
)

# ⚠️ O MARCADOR BOM É A CLASSE, não a palavra (2026-08-19). HTML completo do
# toast, mandado pelo usuário:
#
#   <div class="feedback-message feedback-message-success feedback-message-autoclose"
#        role="alert"><i></i>
#     <div class="feedback-message-text">As características técnicas foram
#      salvas com sucesso!</div>
#   </div>
#
# `feedback-message-success` é semântico e escrito pelo portal: não depende de
# idioma nem de redação. A checagem por palavra ("sucesso"/"exito") continua
# como RESERVA -- as duas se somam, e é o mesmo princípio já aplicado ao aviso
# de colisão de referência. Ganha-se também o caso perverso que a palavra não
# cobre: uma mensagem de ERRO que contenha "sucesso" ("não foi possível
# concluir com sucesso") passaria pela palavra e não passa pela classe.
XPATH_MENSAGEM_DE_SUCESSO = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' feedback-message-success ')]"
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' feedback-message-text ')]"
)

# A tela do PMIB alterna PT/ES (ver docs/refatoracao/FICHA_DUPLICADA.md §6.5),
# então o marcador de sucesso é aceito nos dois idiomas.
MARCADORES_DE_SUCESSO = ("sucesso", "exito")

# Palavra que identifica cada seção dentro da mensagem. Uma só por seção, e
# nenhuma aparece na mensagem de outra ("As condições de transporte e
# movimentação..." x "As condições de armazenamento...").
#
# ⚠️ SÓ PORTUGUÊS, DE PROPÓSITO. As mensagens que temos vieram do usuário, com
# a tela à vista, e são estas:
#
#     "As condições de armazenamento foram modificadas com sucesso!"
#     "As condições de transporte e movimentação foram modificadas com sucesso!"
#
# Não temos a versão em espanhol de nenhuma delas. Escrever aqui um palpite
# ("manutención"? "mantenimiento"?) seria repetir o erro que já custou uma
# sessão de teste neste projeto -- e um palpite ERRADO é invisível, porque a
# consequência dele é silenciosa.
#
# O que acontece se o portal renderizar em espanhol: nenhuma palavra casa, a
# seção não é confirmada e a ficha vira INCOMPLETO com a mensagem lida no log
# -- pendência a conferir, nunca COMPLETO mentiroso. É o lado seguro do erro,
# e o log traz o texto real, que é justamente o que falta para completar esta
# tabela numa sessão.
PALAVRA_DA_SECAO = {
    "Armazenamento": "armazenamento",
    "Transporte": "transporte",
    "Manutenção": "manutencao",
    "Descarte": "descarte",
    # ⚠️ NO SINGULAR, e a diferença é de UMA LETRA (2026-08-20). A redação que
    # o usuário tinha mandado é plural -- "As características técnicas foram
    # salvas com sucesso!" -- e eu mapeei "caracteristicas". O portal, na
    # rodada real, escreveu:
    #
    #     "A característica técnica foi salva com sucesso!. A característica
    #      técnica não está marcada como breve descrição"
    #
    # A seção GRAVOU; quem falhou foi a checagem, e a ficha saiu marcada como
    # incompleta por causa de um "s". O radical no singular casa as duas.
    "Características Técnicas": "caracteristica",
    # 2026-08-20: "A Ficha Técnica 4500063671.0922 foi modificada com sucesso."
    # É genérica -- não nomeia a seção --, e foi exatamente ela que passou por
    # confirmação das OUTRAS quatro seções na rodada em que o robô clicava o
    # SALVAR errado. Mapeá-la aqui faz o contrário do que parece: agora ela
    # confirma SÓ Informações Gerais, e deixa de servir para as demais.
    "Informações gerais": "ficha tecnica",
    # 2026-08-20, redação do usuário: "A imagem foi adicionada com sucesso!"
    # A seção se chama "Documentos e imagens" na edição, e é esse o nome que
    # os chamadores passam.
    "Documentos e imagens": "imagem",
}

# Quanto se espera pelo toast. O usuário descreve que ele aparece
# "relativamente rápido"; a folga é para o portal sob carga. Não é tempo
# perdido no caso bom: o laço devolve assim que a mensagem casa.
TIMEOUT_CONFIRMACAO_S = 8.0
INTERVALO_POLL_CONFIRMACAO_S = 0.25


def _sem_acento(texto):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn")


def mensagem_confirma_secao(mensagem, secao):
    """A mensagem do portal confirma o salvamento DESTA seção?

    Exige as duas coisas -- o marcador de sucesso E a palavra da seção. Ver o
    comentário acima para por que a palavra da seção não é redundante.

    Seção desconhecida devolve False: inventar um casamento para um nome que
    não está na tabela seria adivinhar, e adivinhar aqui produz COMPLETO.
    """
    palavra = PALAVRA_DA_SECAO.get(secao)
    if not palavra:
        return False
    texto = _sem_acento(mensagem).lower()
    if not any(m in texto for m in MARCADORES_DE_SUCESSO):
        return False
    return palavra in texto


DEFAULT_BUSCA_XPATH = "//input[contains(@placeholder, 'Código')]"
DEFAULT_LAPIS_XPATH_TEMPLATE = "//span[text()='{pmib}']/ancestor::tr//i[contains(@class, 'fa-pencil')]/parent::a"


# =============================================================================
# CP 2.3 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.3): sleeps
# CRUS -> constantes NOMEADAS. Migra os 72 `time.sleep(<literal numérico>)`
# levantados nos 6 arquivos-alvo (`apagar_lmr_backend.py`, `lmr_backend.py`,
# `upload_tech_specs_backend.py`, `upload_conditions_backend.py`,
# `upload_ficha_duplicada.py`, `cria_fichas_no_pmib_v1_backend.py`) -- TODOS
# fora do engine/deste módulo (o próprio corpo de `PMIBPortal`, acima e
# abaixo, e o `time.sleep(0.5)` interno de `SeleniumEngine.click`/`.fill`
# (CP 2.1) já eram sleeps CENTRALIZADOS antes deste checkpoint -- por
# decisão explícita do checkpoint, permanecem intocados aqui).
#
# Nomeadas por CONTEXTO/PROPÓSITO, não pelo valor numérico -- dois sleeps
# do mesmo valor podem ter propósitos bem diferentes (ex.: `PAUSA_ANIMACAO`
# e `PAUSA_AUDITORIA` são ambas 0.5s, mas uma é o "deixa a tela assentar"
# genérico e a outra existe especificamente para que a LEITURA de auditoria
# seguinte veja o valor já assentado) -- e reaproveitadas ENTRE arquivos só
# quando o PROPÓSITO (e o valor) são genuinamente os mesmos (ex.:
# `PAUSA_ABERTURA_ABA` -- mesmo XPath, mesma ação, mesmo valor -- em
# `apagar_lmr_backend.py` e `lmr_backend.py`).
#
# Das 72 ocorrências, só 1 foi ELIMINADA (não virou constante): o
# `time.sleep(1)` que antecedia a busca da lixeira, dentro do loop de
# exclusão de `apagar_lmr_backend.ApagarLMRAutomation.executar_limpeza` --
# a busca imediatamente seguinte já é um
# `wait.until(EC.element_to_be_clickable(xpath_lixeira))` para o MESMO
# elemento (a próxima lixeira a excluir) que o sleep tentava dar tempo de
# (re)aparecer, com retry/timeout PRÓPRIOS (o loop inteiro já depende de
# `TimeoutException` para decidir "acabou"); ver o comentário no local
# (`executar_limpeza`). As demais 71 (nenhuma outra) não tinham, na MESMA
# função, uma espera explícita adjacente da qual se pudesse ter CERTEZA de
# que cobria a MESMA transição de estado -- viraram constante (critério
# conservador do checkpoint; casos limítrofes considerados e descartados
# estão documentados em docs/refatoracao/PENDENCIAS.md).
# =============================================================================

# --- Família "genérica" (sem elemento novo e específico a localizar) --------
# Depois de um clique/tecla, sem elemento novo a localizar -- só dar tempo
# da tela/transição do OutSystems assentar. É o tratamento DEFAULT do
# checkpoint (citado literalmente pelo plano) para sleeps de 0.5s sem
# propósito mais específico. Usada por: lmr_backend.py (entre TAGs
# digitadas em `_processar_ficha_lmr_interna`), upload_tech_specs_backend.py
# (`_preencher_linha`, tipos LISTA/INT, depois de escolher opção do
# dropdown), upload_ficha_duplicada.py (scroll->clique em 3 pontos de
# `ExtratorFichaBase._ler_condicoes`/`InjetorFichaAlvo._preencher_condicoes`)
# e cria_fichas_no_pmib_v1_backend.py (11 pontos do "TAB dance" de
# `processar_item_individual`/`atualizar_projeto_em_massa` -- INCLUI o caso
# com comentário ORIGINAL explícito "o OutSystems tem uma animação de
# 'deslizar' a tela que às vezes rouba o foco do clique", que confirma
# textualmente ser exatamente esta a pausa que o plano nomeou).
PAUSA_ANIMACAO = 0.5

# Variante mais longa (~1s) da pausa genérica acima -- usada onde o
# cria_fichas_no_pmib_v1_backend.py original já ajustava 1s em vez de 0.5s
# para o mesmo tipo de propósito (assentar antes do próximo passo de
# teclado, sem elemento novo a localizar). Usada só por
# `processar_item_individual`/`atualizar_projeto_em_massa`.
PAUSA_FOCO = 1

# Variante ainda mais longa (~1.5s) da mesma família, usada quando o
# elemento que ganha foco é um widget mais pesado (dropdown/campo de
# busca), não um TAB simples. Usada só por
# cria_fichas_no_pmib_v1_backend.processar_item_individual (abrir a busca
# de PDM e o dropdown de Unidade).
PAUSA_MUDANCA_FOCO = 1.5

# Pausa curta depois de um `scrollIntoView`, antes do clique -- variante da
# família genérica para um valor menor (0.2s) já usado assim no original.
# Usada só por upload_tech_specs_backend.TechSpecsAutomation.
# safe_send_keys_elem.
PAUSA_SCROLL = 0.2

# --- Família "digitação" (entre teclas) -------------------------------------
# Pausa entre ações de teclado numa sequência (depois de TAB, antes de ler o
# novo foco; depois de digitar um valor, antes do TAB seguinte) -- nome
# citado literalmente pelo prompt do checkpoint. Usada por
# upload_tech_specs_backend.TechSpecsAutomation.safe_send_keys_elem e
# upload_conditions_backend.UploadAutomation.processar_lista (dança de TABs
# de Temperatura/Umidade, 4 ocorrências).
PAUSA_DIGITACAO = 0.2

# Pausa um pouco maior que PAUSA_DIGITACAO, usada especificamente depois de
# enviar o VALOR numérico (temperatura/umidade) e antes do próximo TAB --
# valor sempre 0.3s no original, distinto do 0.2s de PAUSA_DIGITACAO. Usada
# só por upload_conditions_backend.UploadAutomation.processar_lista (4
# ocorrências).
PAUSA_ENTRE_CAMPOS = 0.3

# --- Família "tabela/lista" --------------------------------------------------
# Depois de pesquisar/ENTER num campo de busca, a tabela/lista de
# resultados recarrega -- nome citado literalmente pelo prompt do
# checkpoint. Usada só por
# upload_ficha_duplicada.InjetorFichaAlvo._associar_documentos (depois de
# pesquisar o nome do documento a associar).
PAUSA_RECARGA_TABELA = 2

# Depois de entrar numa aba/seção pela primeira vez, as LINHAS da tabela
# ainda estão carregando (o container pode já estar visível antes das
# linhas existirem) -- distinto de PAUSA_RECARGA_TABELA (que é depois de
# uma BUSCA, não da abertura inicial da aba). Usada por
# upload_tech_specs_backend.TechSpecsAutomation.processar_lista e
# upload_ficha_duplicada.InjetorFichaAlvo._limpar_caracteristicas_tecnicas
# -- mesma aba "Características técnicas", mesmo valor no original.
PAUSA_CARGA_TABELA = 2

# Depois de clicar no botão "página seguinte", antes de ler as novas
# linhas. Usada por upload_tech_specs_backend.TechSpecsAutomation.
# processar_lista e upload_ficha_duplicada.InjetorFichaAlvo.
# _limpar_caracteristicas_tecnicas -- mesma tabela de características
# técnicas, mesmo valor no original.
PAUSA_PAGINACAO = 3

# Depois de navegar (via `driver.get`) direto para a lista de fichas, antes
# de localizar o campo de pesquisa -- equivalente ao `time.sleep(3)` de
# `PMIBPortal.ir_para_lista` (CP 2.2, fora de escopo aqui), mas para o
# único fluxo que NÃO passa por `pesquisar_e_abrir`/`ir_para_lista`:
# cria_fichas_no_pmib_v1_backend.AutomacaoPMIB.atualizar_projeto_em_massa
# (a "6ª variante" de pesquisar+lápis não migrada para `PMIBPortal`, ver
# docs/refatoracao/PENDENCIAS.md do CP 2.2).
PAUSA_CARGA_LISTA = 2

# --- Família "abertura de aba/seção/modal/ficha" ----------------------------
# Depois de clicar no BOTÃO de uma aba de nível superior (ex.: "Aplicação -
# LMR"), espera o conteúdo da aba renderizar. Usada por
# apagar_lmr_backend.ApagarLMRAutomation.executar_limpeza e
# lmr_backend.LMRAutomation.processar_lista -- MESMO XPath
# (`//*[@id="b10-ApplicationMRL"]/button`), mesma ação, mesmo valor.
PAUSA_ABERTURA_ABA = 2

# Depois de clicar no cabeçalho de uma seção "sanfona" (Condições), espera
# ela abrir/expandir completamente -- comentário ORIGINAL: "Tempo para a
# sanfona abrir completamente". Usada só por upload_ficha_duplicada.py, nos
# dois sentidos (leitura em ExtratorFichaBase._ler_condicoes e escrita em
# InjetorFichaAlvo._preencher_condicoes).
PAUSA_ABERTURA_SECAO = 1.5

# Depois de trocar para uma SUB-aba já dentro de uma seção aberta
# (Transporte/Manutenção/Descarte dentro de Condições), espera os campos
# daquela sub-aba renderizarem -- distinto de PAUSA_ABERTURA_SECAO (que é
# abrir a seção inteira pela 1ª vez). Usada só por
# upload_ficha_duplicada.py, nos dois sentidos (leitura e escrita).
PAUSA_TROCA_SUBABA = 1

# Depois de clicar num botão que abre um modal/painel novo (ex.: "Associar
# documentos"), espera ele aparecer antes de pesquisar dentro dele. Usada
# só por upload_ficha_duplicada.InjetorFichaAlvo._associar_documentos --
# também referenciada (só em comentário, sem efeito funcional) no trecho
# desabilitado de `_upload_imagens`, já comentado ANTES deste checkpoint
# (ver docs/refatoracao/PENDENCIAS.md).
PAUSA_ABERTURA_MODAL = 1

# Depois de clicar em "Nova Ficha", espera o formulário novo (modal
# completo, mais pesado que uma aba simples) terminar de renderizar --
# mesma família de evento citada como exemplo pelo prompt do checkpoint
# ("depois de clicar no lápis, ficha abre"; aqui o gatilho é "Nova Ficha",
# não o lápis de edição, mas o propósito -- esperar uma ficha/formulário
# abrir -- é o mesmo). Usada só por cria_fichas_no_pmib_v1_backend.
# AutomacaoPMIB.processar_item_individual. Valor grande (5s) sem
# comentário original explicando o motivo exato -- ver
# docs/refatoracao/PENDENCIAS.md para validação futura contra o portal
# real.
PAUSA_ABERTURA_FICHA = 5

# Antes de clicar em "Nova Ficha", ao iniciar o processamento de CADA item
# do lote -- dá tempo da lista (para onde o item anterior navegou de
# volta, via `driver.get` sem nenhuma espera) ficar pronta para a próxima
# interação. Usada só por cria_fichas_no_pmib_v1_backend.AutomacaoPMIB.
# processar_item_individual (início da função).
PAUSA_INICIO_ITEM = 1.5

# --- Família "salvar/confirmar" ---------------------------------------------
# Depois de confirmar/salvar (clique em Salvar/Confirmar/"+"), servidor
# processa -- nome citado literalmente pelo prompt do checkpoint. Usada por
# lmr_backend.py (Salvar + Confirmar do formulário de TAGs em
# `_processar_ficha_lmr_interna`), upload_conditions_backend.
# UploadAutomation.safe_save_with_pause (Salvar de cada uma das 4 abas de
# Condições) e upload_ficha_duplicada.InjetorFichaAlvo.
# _adicionar_fornecedores (clique no "+" que insere cada fornecedor).
PAUSA_SALVAMENTO = 1

# Variante mais longa de PAUSA_SALVAMENTO, para o Salvar de cada sub-aba de
# Condições ao INJETAR dados na ficha alvo -- valor já era 1,5s (não 1s) no
# original. Usada só por
# upload_ficha_duplicada.InjetorFichaAlvo._preencher_condicoes (comentário
# original: "Aguarda o salvamento processar").
PAUSA_SALVAMENTO_LONGA = 1.5

# Variante mais longa ainda, para o Salvar FINAL/definitivo de
# `atualizar_projeto_em_massa` (aguarda mensagem de sucesso) -- comentário
# original: "Aguarda a mensagem de sucesso ou salvamento processar". Usada
# só por cria_fichas_no_pmib_v1_backend.AutomacaoPMIB.
# atualizar_projeto_em_massa.
PAUSA_SALVAMENTO_FINAL = 3

# Pausa de segurança usada SÓ quando um clique de Salvar falha e não há
# `callback_pause` disponível para travar a execução interativamente (sem
# esse callback, não há como pedir intervenção do usuário) -- comentário
# original: "Fallback caso falte o callback". Usada só por
# upload_conditions_backend.UploadAutomation.safe_save_with_pause.
PAUSA_FALLBACK_SALVAMENTO = 5

# Depois de excluir e confirmar uma linha (lixeira + CONFIRMAR), espera a
# tabela atualizar -- comentário original: "Pausa para refresh da tabela".
# Usada só por apagar_lmr_backend.ApagarLMRAutomation.executar_limpeza
# (distinto do sleep ELIMINADO na mesma função -- ver nota no topo desta
# seção -- e de `PMIBPortal.excluir_linha_com_confirmacao`, que já usa
# 2,5s, fora de escopo do CP 2.3).
PAUSA_POS_EXCLUSAO = 1.5

# --- Família "busca/filtro (autocomplete)" ----------------------------------
# Depois de digitar o texto de busca do PDM, antes de confirmar com ENTER
# -- dá tempo do autocomplete filtrar. Usada só por
# cria_fichas_no_pmib_v1_backend.AutomacaoPMIB.processar_item_individual.
PAUSA_FILTRO_PDM = 1

# Mesma ideia de PAUSA_FILTRO_PDM (autocomplete/AJAX), mas para o campo de
# busca de Fabricante (componente VSComp) -- comentário original: "Pausa
# levemente maior para dar tempo de o OutSystems filtrar os resultados
# AJAX". Usada só por
# upload_ficha_duplicada.InjetorFichaAlvo._adicionar_fornecedores.
PAUSA_FILTRO_FORNECEDOR = 1.5

# --- Família "auditoria/injeção JS" (upload_tech_specs) ---------------------
# Depois de preencher e clicar fora (blur) de um campo numérico, antes de
# ler o valor de volta para auditar se o site aceitou -- propósito
# ESPECÍFICO (a leitura seguinte depende deste tempo), não a pausa
# genérica de PAUSA_ANIMACAO (mesmo valor, propósito diferente). Usada só
# por upload_tech_specs_backend.TechSpecsAutomation.
# _preencher_input_com_auditoria.
PAUSA_AUDITORIA = 0.5

# Depois que a auditoria acima detecta que o site rejeitou o valor, antes
# de tentar a injeção forçada via JavaScript -- comentário original: "Dá
# tempo para o usuário ver na tela e o JS do site assentar". Usada só por
# upload_tech_specs_backend.TechSpecsAutomation._preencher_input_com_auditoria.
PAUSA_INJECAO_JS = 1.5

# Depois da injeção forçada via JavaScript, antes de auditar o resultado
# pela 2ª vez -- comentário original: "Pausa maior após a injeção para
# validar o resultado". Usada só por upload_tech_specs_backend.
# TechSpecsAutomation._preencher_input_com_auditoria.
PAUSA_POS_INJECAO_JS = 1.0

# --- Família "download/upload de arquivo" -----------------------------------
# Intervalo de cada iteração do polling manual que espera um arquivo
# baixado pelo Chrome aparecer na pasta temporária (não é um elemento DOM;
# não dá pra usar `wait.until` do engine aqui). Usada só por
# upload_ficha_duplicada.ExtratorFichaBase._esperar_download_e_renomear.
PAUSA_POLL_DOWNLOAD = 1

# Depois de enviar o caminho do arquivo para o input do FilePond, espera a
# barra de progresso do upload processar. Usada só por
# upload_ficha_duplicada.InjetorFichaAlvo._upload_imagens.
PAUSA_UPLOAD_ARQUIVO = 3

# --- Família "retry" (IA e arquivo bloqueado -- NÃO é sincronização de
#     RPA/navegador, mas o sleep vive dentro de um dos 6 arquivos-alvo) ----
# Espera entre tentativas de retry de uma chamada de IA (Gemini) que
# falhou. Variante CURTA (2s). Usada só por upload_tech_specs_backend.
# TechSpecsProcessor._chamar_gemini_specs.
PAUSA_RETRY_IA_CURTA = 2

# Mesma ideia de PAUSA_RETRY_IA_CURTA, variante LONGA (30s, backoff
# deliberado) -- comentário original: "Aguardando 30 segundos antes da
# próxima tentativa...". Usada só por upload_conditions_backend.
# ConditionsProcessor.processar_ia_lote.
PAUSA_RETRY_IA_LONGA = 30

# Espera antes de tentar salvar de novo um Excel de status bloqueado
# (arquivo aberto) -- retry AUTOMÁTICO sem limite de tentativas; é I/O de
# Excel, não sincronização de navegador. Usada só por
# upload_ficha_duplicada.AtualizadorStatusPMIB.atualizar_ficha_concluida
# (via `locking.save_with_retry`).
PAUSA_RETRY_ARQUIVO_BLOQUEADO = 5

# Depois do 1º Salvar da ficha nova, espera o portal gerar e exibir o novo
# CÓDIGO PMIB -- comentário original: "Aumentado de 3 para 6 segundos para
# cobrir a latência da 1ª ficha" (valor empírico; ver
# docs/refatoracao/PENDENCIAS.md para validação futura contra o portal
# real). Usada só por cria_fichas_no_pmib_v1_backend.AutomacaoPMIB.
# processar_item_individual.
PAUSA_GERACAO_PMIB = 6

# --- Família "navegação de retorno" (lmr) -----------------------------------
# Antes e depois de clicar no controle de "voltar para a lista" ao fim do
# processamento de uma ficha. Usada só por lmr_backend.LMRAutomation.
# processar_lista (2 ocorrências: antes e depois do clique).
PAUSA_RETORNO_LISTA = 1


class PMIBPortal:
    """Mecânica de interação com o portal PMIB, sobre um `RPAEngine` (hoje
    sempre um `SeleniumEngine`, ver CP 2.1) -- ver docstring do módulo."""

    def __init__(self, engine: "RPAEngine | None" = None) -> None:
        self.engine = engine
        self.parar_solicitado = False

    # =========================================================================
    # Stop-flag -- ver docstring do módulo: só as 4 ocorrências reais (2
    # classes x 2 arquivos: `ConditionsProcessor`/`UploadAutomation` em
    # upload_conditions_backend.py; `TechSpecsProcessor`/`TechSpecsAutomation`
    # em upload_tech_specs_backend.py) delegam para isto -- NÃO inventado
    # para os outros 4 backends.
    # =========================================================================
    def solicitar_parada(self) -> None:
        """Sinaliza pedido de parada -- equivalente a `self.cancel_requested
        = True` nas 4 ocorrências originais."""
        self.parar_solicitado = True

    def deve_parar(self) -> bool:
        """Equivalente a checar `self.cancel_requested` nas 4 ocorrências
        originais."""
        return self.parar_solicitado

    # =========================================================================
    # Login manual -- capacidade NOVA, sem consumidor de produção ainda (ver
    # docstring do módulo). `motivo` default = "LOGIN_NECESSARIO", a mesma
    # string já usada como convenção por `upload_tech_specs_backend.
    # executar_pipeline_rpa` (`callback_pause("LOGIN_NECESSARIO")`) e checada
    # em `frontend.py` (`if section_name == "LOGIN_NECESSARIO":` /
    # `if estado_ou_pmib == "LOGIN_NECESSARIO":`) -- reaproveita a convenção
    # já existente em vez de inventar uma nova.
    # =========================================================================
    def aguardar_login_manual(self, callback_pause=None, motivo: str = "LOGIN_NECESSARIO") -> None:
        """Chama `callback_pause(motivo)` se fornecido; sem-op se não.

        Não é chamado por nenhum backend/`frontend.py` ainda neste
        checkpoint -- o fluxo de login manual continua 100% do lado da UI
        (`messagebox.showinfo`/janela de pausa bloqueante ANTES de invocar
        `processar_lista`/`executar_limpeza`). Fazer os backends/`frontend.py`
        chamarem isto de fato exigiria reencanar o fluxo de login para passar
        por um callback -- mudança maior que este checkpoint deveria arriscar
        sem validação do usuário contra o portal real (mesmo espírito das
        capacidades novas do CP 2.1 -- `screenshot`/`set_download_dir` -- que
        também nasceram sem consumidor). Ver docs/refatoracao/PENDENCIAS.md.
        """
        if callback_pause:
            callback_pause(motivo)

    # =========================================================================
    # Navegação -- usa `sigft.config.PORTAL_URL` (CP 1.1) em vez de qualquer
    # literal local. `pesquisar_e_abrir` chama isto como 1º passo interno.
    # =========================================================================
    def ir_para_lista(self) -> None:
        """`if driver.current_url != PORTAL_URL: goto(PORTAL_URL); sleep(3)`
        -- o padrão que abre TODAS as variantes de `pesquisar_e_abrir` hoje
        (`apagar_lmr`/`upload_tech_specs`/`upload_ficha_duplicada` já
        faziam exatamente isso, com sleeps de 2/3/2s respectivamente;
        `upload_conditions` fazia um `driver.get(url)` INCONDICIONAL com
        sleep de 2s, sem checar `current_url` antes -- ver
        docs/refatoracao/PENDENCIAS.md sobre a consolidação do sleep em 3s
        para todos os chamadores via `pesquisar_e_abrir`).
        """
        # CP 5.1: `self.engine.driver.current_url` virou `engine.current_url()`
        # -- um `PlaywrightEngine` não tem `.driver` nenhum. Mesma leitura,
        # mesmo `!=`, mesmo sleep.
        if self.engine.current_url() != config.PORTAL_URL:
            self.engine.goto(config.PORTAL_URL)
            time.sleep(3)

    # =========================================================================
    # Clique/preenchimento -- delegação FINA para o engine (a mecânica REAL
    # de scroll+JS-click / Ctrl+A+Backspace+texto já vive em
    # `SeleniumEngine.click`/`.fill` desde o CP 2.1 -- "safe_click existe em
    # um único lugar" refere-se a essa mecânica, não ao nome do método, que
    # continua existindo como alias fino em cada uma das 6 classes -- ver
    # docstring do módulo, seção "Migração dos 6 backends").
    # =========================================================================
    def safe_click(self, seletor: str) -> None:
        """Clica em `seletor` (XPath) com a mecânica canônica de
        scroll+espera+clique-via-JS (`SeleniumEngine.click`)."""
        self.engine.click(seletor)

    def safe_fill(self, seletor: str, texto) -> None:
        """Preenche `seletor` (XPath) com `texto` via a mecânica canônica
        Ctrl+A/Backspace/digitar (`SeleniumEngine.fill`) -- ex-`safe_send_keys`."""
        self.engine.fill(seletor, texto)

    # =========================================================================
    # Confirmação de salvamento -- lê o toast que o portal emite ao gravar.
    # =========================================================================
    def esperar_confirmacao_de_salvamento(
        self, secao, timeout_s=None, callback_log=None,
        sleep_fn=None, agora_fn=None,
    ):
        """Espera o toast de "modificadas com sucesso" DESTA seção.

        Devolve `(confirmou: bool, mensagem_lida: str)`. `mensagem_lida` é o
        texto que estava na tela quando o tempo acabou -- é ele que permite
        descobrir a redação real (idioma, texto novo do portal) a partir do
        log, em vez de adivinhar. Ver `mensagem_confirma_secao`.

        Não levanta: um toast que não aparece é pendência, não erro fatal. A
        ficha continua, e quem decide o que fazer com a pendência é o
        chamador.

        `sleep_fn`/`agora_fn` existem para o teste poder rodar sem esperar 8
        segundos de verdade -- mesmo padrão de `core.excel.locking.
        save_with_retry`.
        """
        limite = TIMEOUT_CONFIRMACAO_S if timeout_s is None else timeout_s
        dormir = sleep_fn or time.sleep
        agora = agora_fn or time.monotonic

        fim = agora() + limite
        ultima = ""
        while True:
            for mensagem in self._mensagens_de_feedback():
                if mensagem:
                    ultima = mensagem
                if mensagem_confirma_secao(mensagem, secao):
                    return True, mensagem
            if agora() >= fim:
                break
            dormir(INTERVALO_POLL_CONFIRMACAO_S)

        if callback_log:
            if ultima:
                callback_log(
                    f"      [!] Não vi a confirmação de '{secao}'. A última mensagem "
                    f"na tela foi: {ultima!r}"
                )
            else:
                callback_log(
                    f"      [!] Não vi nenhuma mensagem de confirmação ao salvar '{secao}'."
                )
        return False, ultima

    # =========================================================================
    # Ler o que PODE NÃO EXISTIR -- sem pagar o timeout
    # =========================================================================
    # ⚠️ O TRAVAMENTO DE 2026-08-20 SAIU DAQUI. `Locator.text_content()` e
    # `Locator.input_value()` do Playwright AUTO-ESPERAM o elemento: ausente,
    # esperam o `wait_timeout` inteiro (20 s) antes de levantar. Num laço que
    # percorre linhas de tabela ou 45 campos de Condições, isso vira minutos
    # de silêncio -- e de fora é indistinguível de um laço infinito.
    #
    # `contar` é IMEDIATO nos dois motores (`Locator.count()` no Playwright,
    # `find_elements` no Selenium). Perguntar antes custa nada e troca 20 s
    # por 0.
    #
    # Estes dois métodos existem para os casos em que a AUSÊNCIA É NORMAL --
    # célula de uma coluna que aquela tabela não tem, campo de outra sub-aba.
    # Onde o elemento DEVE estar, continue usando `engine.texto`/`get_value`
    # direto: ali a espera é o comportamento certo, porque o elemento pode
    # estar a caminho.
    def texto_se_existir(self, seletor: str) -> str:
        """Texto do elemento, ou `""` na hora se ele não estiver na tela."""
        try:
            if not self.engine.contar(seletor):
                return ""
            return self.engine.texto(seletor) or ""
        except Exception:  # noqa: BLE001 -- ler a tela não derruba a ficha
            return ""

    # O balão de tooltip: `aria-describedby` no gatilho aponta para o id do
    # balão. Formato do portal, mandado pelo usuário em 2026-08-24:
    #
    #   <div class="osui-tooltip__content" aria-describedby="b12-...-b2-Tooltip">
    #     <div data-block="PMIB_DataSheetView.Block_Expression">
    #       <span data-expression="">Aplicam-se as normas ... (PORTUGUÊS)</span>
    XPATH_POR_ID = "//*[@id={id}]"

    # Quanto esperar o balão nascer depois do hover. É animação de CSS, não
    # ida ao servidor -- meio segundo cobre, e o custo é por campo de texto
    # longo (dois por sub-aba), não por ficha.
    PAUSA_DO_BALAO = 0.5

    def texto_do_balao(self, seletor_gatilho: str, sleep_fn=None) -> str:
        """O texto ESCONDIDO atrás do tooltip do gatilho. `""` se não houver.

        🎯 É COMO O ESPANHOL DAS CONDIÇÕES SAI DA VISUALIZAÇÃO. Eu tinha
        concluído, do dump de 2026-08-24, que a visualização não trazia
        espanhol nenhum -- não havia um id `..._ES` nem um segundo
        `Block_Expression` na seção. O usuário corrigiu: *"a página tem
        espanhol sim, só que ele só aparece quando passamos o mouse por cima
        da versão em português, como um balão"*. Eu tinha procurado pelo
        padrão errado; o certo é o par `aria-describedby` → `#...-Tooltip`.

        O balão NÃO está no DOM até alguém apontar para o gatilho
        (`osui-tooltip--is-hover`), e é por isso que ele não aparecia no dump
        da seção: a foto é do HTML como está, e naquele momento o elemento
        não existia. Daí a ordem aqui -- tenta ler direto (barato, e cobre o
        caso de o balão já estar montado), e só então paga o hover.

        Nunca levanta: ler a tela não pode derrubar a ficha.
        """
        sleep_fn = sleep_fn or time.sleep
        try:
            id_do_balao = self.engine.atributo(seletor_gatilho, "aria-describedby")
        except Exception:  # noqa: BLE001
            return ""
        if not id_do_balao:
            return ""

        # Aspas simples bastam: o alvo é um id GERADO pelo OutSystems
        # (`b12-b20-b4-b3-b2-Tooltip`), e id de HTML não carrega aspas.
        # Um que carregasse não casaria com elemento nenhum, e a função
        # devolve "" -- que é o mesmo desfecho de "não há balão".
        if "'" in id_do_balao:
            return ""
        seletor_balao = self.XPATH_POR_ID.format(id=f"'{id_do_balao}'")
        texto = self.texto_se_existir(seletor_balao).strip()
        if texto:
            return texto

        # O balão só nasce na interação. `passar_o_mouse` é o caminho bom (o
        # tooltip do OSUI escuta evento de ponteiro de verdade); `focar` fica
        # como reserva porque o gatilho é `role="button" tabindex="0"`, então
        # ele responde ao teclado também -- e num motor sem ponteiro é a
        # única porta que sobra.
        for acordar in (self.engine.passar_o_mouse, self.engine.focar):
            try:
                acordar(seletor_gatilho)
            except Exception:  # noqa: BLE001
                continue
            sleep_fn(self.PAUSA_DO_BALAO)
            texto = self.texto_se_existir(seletor_balao).strip()
            if texto:
                return texto
        return ""

    def valor_se_existir(self, seletor: str):
        """Valor do campo, ou `None` na hora se ele não estiver na tela.

        `None` e não `""` de propósito: quem lê Condições precisa distinguir
        "o campo não está nesta sub-aba" de "o campo está vazio". Confundir os
        dois faria a cópia APAGAR um campo da ficha alvo por causa de uma
        leitura que falhou.
        """
        try:
            if not self.engine.contar(seletor):
                return None
            return self.engine.get_value(seletor) or ""
        except Exception:  # noqa: BLE001
            return None

    def _mensagens_de_feedback(self, so_sucesso=False):
        """Textos dos toasts visíveis agora. Nunca levanta -- ler a tela não
        pode ser o que derruba a ficha.

        Percorre por ÍNDICE (`(xpath)[i]`) e não por elemento, pelo mesmo
        motivo de `clicar_salvar_visivel`: é o que funciona igual nos dois
        motores.
        """
        seletor = XPATH_MENSAGEM_DE_SUCESSO if so_sucesso else XPATH_MENSAGEM_DE_FEEDBACK
        try:
            total = self.engine.contar(seletor)
        except Exception:  # noqa: BLE001
            return []
        textos = []
        for posicao in range(1, (total or 0) + 1):
            try:
                textos.append(self.engine.texto(f"({seletor})[{posicao}]"))
            except Exception:  # noqa: BLE001
                continue
        return textos

    # =========================================================================
    # check_or_uncheck -- só existia em upload_conditions_backend.py (não
    # duplicado antes, só "movido"). Precisa do atributo `checked`, que não
    # tem equivalente na interface de intenção de `RPAEngine` -- acessa
    # `self.engine.driver`/`.wait` diretamente (ver docstring do módulo).
    # =========================================================================
    def check_or_uncheck(self, seletor: str, should_check: bool,
                         callback_log=None) -> bool:
        """Marca/desmarca um checkbox/radio e **confere se pegou**.

        Devolve `True` quando o estado final é o pedido. O retorno é novo
        (2026-08-18) e aditivo -- quem ignora continua funcionando.

        CP 5.3: portado para as primitivas. O `scrollIntoView` que o original
        fazia antes de LER o estado sumiu -- ele não influencia a leitura, e o
        clique que vem depois (`safe_click`) já rola por conta própria. Ler
        `checked` não exige o elemento na viewport.

        **Por que a releitura (2026-08-18).** A versão anterior clicava e ia
        embora, dentro de um `except Exception: pass`. Num checkbox isso é
        pior do que em qualquer outro elemento, porque o estado é observável e
        barato de ler: dava para saber, e não se olhava. Em Condições, onde há
        19 controles desses, uma ficha inteira podia sair vazia sem uma linha
        de log -- e depois ser marcada COMPLETO na planilha.

        As duas tentativas não são "tentar de novo até dar certo", são
        mecanismos DIFERENTES: `safe_click` clica como um usuário; `click_dom`
        dispara o `click()` do próprio elemento, alcançando o `<input>`
        coberto pelo rótulo estilizado do OutSystems. Se a primeira já
        resolveu, a segunda nem acontece -- clicar de novo num checkbox que já
        está certo o DESmarcaria.
        """
        def _log(mensagem):
            if callback_log:
                callback_log(mensagem)

        try:
            if self.engine.esta_marcado(seletor) == should_check:
                return True  # já estava como se queria
        except Exception as erro:  # noqa: BLE001
            # Não dá para LER o estado -- e aí não se clica. `esta_marcado`
            # levanta quando o elemento não existe e também quando ele existe
            # mas não é um controle marcável; nos dois casos, clicar seria um
            # palpite sobre um alvo que não entendemos. É o comportamento da
            # versão anterior, PRESERVADO de propósito.
            #
            # O que muda é só o silêncio: antes isto era `except: pass` e o
            # campo sumia sem deixar rastro. A correção deste ponto é o log,
            # não um clique a mais.
            _log(f"      [!] Não consigo ler o estado do controle {seletor}: {erro}. "
                 f"Não cliquei -- preencher à mão.")
            return False

        try:
            self.safe_click(seletor)
        except Exception:  # noqa: BLE001
            pass

        try:
            if self.engine.esta_marcado(seletor) == should_check:
                return True
        except Exception:  # noqa: BLE001
            pass

        # 2ª tentativa por outro mecanismo.
        try:
            self.engine.click_dom(seletor)
        except Exception as erro:  # noqa: BLE001
            _log(f"      [!] Não consegui alcançar o controle {seletor}: {erro}")
            return False

        try:
            final = self.engine.esta_marcado(seletor)
        except Exception as erro:  # noqa: BLE001
            _log(f"      [!] Cliquei em {seletor} mas não consigo ler o estado: {erro}")
            return False

        if final != should_check:
            _log(f"      [!] O controle {seletor} continuou em {final!r} depois de "
                 f"duas tentativas (esperado {should_check!r}) -- preencher à mão.")
            return False
        return True

    # =========================================================================
    # clicar_salvar_visivel -- só existia em upload_ficha_duplicada.py
    # (InjetorFichaAlvo._clicar_salvar_visivel, não duplicado, só "movido").
    # Preserva os `print()` originais tal qual (mover != melhorar).
    # =========================================================================
    def clicar_salvar_visivel(self, nome_secao: str = "", callback_log=None) -> bool:
        """Procura na tela o botão SALVAR (`btn-primary`, texto exato
        "SALVAR") que estiver visível/habilitado no momento e clica nele.
        Mecânica idêntica à original de
        `upload_ficha_duplicada.InjetorFichaAlvo._clicar_salvar_visivel`
        (incluindo os `print()` de progresso/aviso, preservados tal qual).

        CP 5.3: o `find_elements` + laço sobre ELEMENTOS virou `contar` + laço
        sobre ÍNDICES, com o XPath indexado `(...)[i]`. É a mesma varredura,
        na mesma ordem, com os mesmos testes de visível/habilitado -- o que
        muda é só como cada botão é endereçado.
        """
        # ⚠️ `print` NÃO SERVE, e isso escondeu um defeito inteiro em
        # 2026-08-19: no app empacotado não há console, então estas linhas
        # simplesmente não existiam para quem estava lendo o log. O `print`
        # continua como RESERVA (o módulo antigo chama sem callback), mas
        # quem passa `callback_log` recebe tudo no log e no arquivo de
        # auditoria.
        def _diga(mensagem):
            if callback_log:
                callback_log(mensagem)
            else:
                print(mensagem)

        if nome_secao:
            _diga(f"      [Injetor] Salvando {nome_secao}...")

        total = self.engine.contar(XPATH_BOTAO_SALVAR)
        for posicao in range(1, total + 1):
            # XPath é base 1, daí o range começar em 1.
            seletor = f"({XPATH_BOTAO_SALVAR})[{posicao}]"
            if self.engine.esta_visivel(seletor) and self.engine.esta_habilitado(seletor):
                self.engine.scroll_to(seletor)
                time.sleep(0.5)
                self.engine.click_raw(seletor)
                # QUAL botão, de quantos. A ficha tem um SALVAR por seção, e
                # este método clica o PRIMEIRO visível -- que nem sempre é o
                # da seção que se quer gravar. Sem o índice no log, "salvei a
                # seção errada" e "não salvei" produzem o mesmo silêncio.
                _diga(f"      [Injetor] Cliquei no botão SALVAR {posicao} de "
                      f"{total} da tela.")
                time.sleep(2.5)  # Aguarda a requisição do servidor OutSystems
                return True

        _diga(f"      [Aviso] Botão SALVAR não encontrado/visível para "
              f"{nome_secao}. Se o portal não habilitou o botão, é sinal de "
              f"que ele não registrou nenhuma mudança.")
        return False

    def clicar_salvar_do_bloco(self, ancora: str, nome_secao: str = "",
                               callback_log=None) -> bool:
        """Clica o SALVAR **da seção** onde `ancora` está.

        `ancora` é qualquer elemento da seção: o container dela ou um campo
        dentro. Ver `XPATH_SALVAR_DO_BLOCO` para o porquê da fórmula.

        Âncora que não casa botão nenhum cai na varredura antiga -- mas
        AVISANDO. Cair em silêncio recriaria o defeito de 2026-08-20 sem
        deixar rastro no log, que é a pior combinação possível.
        """
        def _diga(mensagem):
            if callback_log:
                callback_log(mensagem)
            else:
                print(mensagem)

        # DENTRO primeiro, SUBINDO depois -- ver `XPATH_SALVAR_DENTRO_DO_BLOCO`.
        tentativas = (
            ("dentro da seção", XPATH_SALVAR_DENTRO_DO_BLOCO),
            ("subindo da seção", XPATH_SALVAR_SUBINDO_DO_BLOCO),
        )
        seletor = como = ""
        for descricao, formula in tentativas:
            candidato = formula.format(ancora=ancora)
            try:
                if self.engine.contar(candidato):
                    seletor, como = candidato, descricao
                    break
            except Exception:  # noqa: BLE001
                continue

        if not seletor:
            _diga(f"      [Aviso] A âncora da seção {nome_secao!r} não achou "
                  f"botão SALVAR. Caindo na varredura da tela -- confira se a "
                  f"seção certa foi gravada.")
            return self.clicar_salvar_visivel(nome_secao, callback_log)

        alvo = f"({seletor})[1]"
        try:
            self.engine.scroll_to(alvo)
            time.sleep(0.5)
            self.engine.click_raw(alvo)
        except Exception as erro:  # noqa: BLE001 -- ver abaixo
            # ⚠️ SALVAR QUE NÃO DÁ PARA CLICAR É PENDÊNCIA, NÃO QUEDA DA FICHA.
            # Em 2026-08-20 o botão da seção de imagens resolveu, estava
            # "visible, enabled and stable", rolou para a tela -- e o clique
            # nunca completou (algo o cobria; o `tabindex="-1"` sugere painel
            # inativo). A exceção subiu até `processar_ficha` e virou ERRO
            # FATAL, apagando do placar tudo o que já tinha dado certo na
            # ficha. Salvar é UMA etapa.
            _diga(f"      [Erro] Não consegui clicar no SALVAR de "
                  f"{nome_secao!r} ({como}): {type(erro).__name__}. Algo pode "
                  f"estar cobrindo o botão -- salve à mão.")
            return False
        _diga(f"      [Injetor] SALVAR da seção {nome_secao} ({como}).")
        time.sleep(2.5)  # requisição do servidor OutSystems
        return True

    def clicar_e_confirmar(self, seletor_botao: str, nome_secao: str = "",
                           callback_log=None, timeout_s=None,
                           sleep_fn=None, agora_fn=None) -> bool:
        """Clica UM botão e só devolve `True` com o toast de sucesso NOVO.

        É a mecânica de `salvar_e_confirmar` sem a parte de ACHAR o SALVAR --
        existe porque nem toda gravação passa por ele. A imagem, por exemplo,
        é confirmada pelo botão "Confirmar" DENTRO do diálogo; o SALVAR da
        seção fica inacessível enquanto ele está aberto, e tentar clicá-lo
        gastava 20 s de timeout (log de 2026-08-20).
        """
        antes = {m for m in self._mensagens_de_feedback() if m}
        try:
            self.engine.click_raw(f"({seletor_botao})[1]")
        except Exception as erro:  # noqa: BLE001 -- clique que não pega é pendência
            if callback_log:
                callback_log(f"      [Erro] Não consegui clicar em "
                             f"{nome_secao!r}: {type(erro).__name__}.")
            return False

        confirmou, mensagem = self.esperar_confirmacao_nova(
            nome_secao, antes, timeout_s=timeout_s, callback_log=callback_log,
            sleep_fn=sleep_fn, agora_fn=agora_fn)
        if confirmou and callback_log:
            callback_log(f"      Portal confirmou: {' '.join(mensagem.split())[:90]}")
        return confirmou

    def salvar_e_confirmar(self, nome_secao: str = "", callback_log=None,
                           timeout_s=None, sleep_fn=None, agora_fn=None,
                           ancora=None) -> bool:
        """SALVA e só devolve `True` com o toast de sucesso NOVO na tela.

        Pedido do usuário em 2026-08-19: *"tal como fizemos para upload
        característica, devemos esperar a mensagem de salvo com sucesso"*.

        ⚠️ POR QUE "NOVO", E NÃO SÓ "DE SUCESSO". O toast *"aparece
        relativamente rápido, fica um tempo e depois some"*. Quando o robô
        salva a 2ª seção, o toast da 1ª ainda pode estar na tela -- e uma
        checagem de "existe mensagem de sucesso?" leria o toast VELHO e daria
        a 2ª seção por gravada sem ter sido. Em Condições isso é resolvido
        exigindo a PALAVRA DA SEÇÃO (`PALAVRA_DA_SECAO`); aqui não dá, porque
        não sabemos a redação do toast de Fabricantes nem do de
        Características.

        A saída é a foto de ANTES, a mesma mecânica que este módulo já usa
        para achar o campo que nasce ao escolher o fabricante: vale o toast
        que for de sucesso **e não estava na tela antes do clique**. Funciona
        sem conhecer a redação.

        Limite conhecido e declarado: salvar DUAS VEZES a mesma seção, na
        mesma tela, produziria um toast de texto idêntico ao anterior e este
        método não o reconheceria como novo. No fluxo da ficha duplicada cada
        seção é salva uma vez; se um dia deixar de ser, esta é a linha a
        rever.

        O texto lido vai para o log mesmo quando não confirma -- é assim que a
        redação real aparece, sem ninguém precisar inspecionar a tela.
        """
        antes = {m for m in self._mensagens_de_feedback() if m}

        # `ancora` decide QUAL botão. Sem ela, cai na varredura da tela -- que
        # é o caminho do módulo antigo e o defeito de 2026-08-20. Todo
        # chamador novo passa âncora.
        if ancora:
            clicou = self.clicar_salvar_do_bloco(ancora, nome_secao, callback_log)
        else:
            clicou = self.clicar_salvar_visivel(nome_secao, callback_log)
        if not clicou:
            return False

        confirmou, mensagem = self.esperar_confirmacao_nova(
            nome_secao, antes, timeout_s=timeout_s, callback_log=callback_log,
            sleep_fn=sleep_fn, agora_fn=agora_fn)
        if confirmou and callback_log:
            callback_log(f"      Portal confirmou: {' '.join(mensagem.split())[:90]}")
        return confirmou

    def esperar_confirmacao_nova(self, secao, ja_na_tela=(), timeout_s=None,
                                 callback_log=None, sleep_fn=None, agora_fn=None):
        """Espera um toast de sucesso que NÃO estava em `ja_na_tela`.

        Devolve `(confirmou, mensagem_lida)`, como
        `esperar_confirmacao_de_salvamento` -- de que é a variante para as
        seções cuja redação o projeto ainda não conhece. Quando a seção TEM
        palavra mapeada, ela continua sendo exigida: a checagem nova se soma à
        antiga, não a substitui.
        """
        limite = TIMEOUT_CONFIRMACAO_S if timeout_s is None else timeout_s
        dormir = sleep_fn or time.sleep
        agora = agora_fn or time.monotonic
        vistas = {m for m in (ja_na_tela or ()) if m}

        fim = agora() + limite
        ultima = ""
        while True:
            # A CLASSE primeiro: `feedback-message-success` é o marcador que o
            # portal escreve, e não depende de idioma. A palavra
            # ("sucesso"/"exito") entra só quando a classe não casa nada -- se
            # o portal mudar o markup, a reserva ainda pega. As duas se somam.
            por_classe = [m for m in self._mensagens_de_feedback(so_sucesso=True) if m]
            todas = [m for m in self._mensagens_de_feedback() if m]
            if todas:
                ultima = todas[-1]

            # ⚠️ A PALAVRA DA SEÇÃO É EXIGIDA SEMPRE QUE CONHECIDA -- e isto
            # DESFAZ uma decisão minha da véspera.
            #
            # Eu tinha afrouxado: "veio pela classe ⇒ 'novo' já basta", com o
            # argumento de que exigir a palavra amarraria a confirmação ao
            # idioma. O argumento era hipotético. A falha foi real: em
            # 2026-08-20 o robô clicou o SALVAR errado cinco vezes, o portal
            # respondeu "A Ficha Técnica X foi modificada com sucesso" (classe
            # de sucesso, mensagem genérica) e as cinco passaram por
            # confirmadas. As fichas saíram vazias.
            #
            # A classe diz que ALGO foi salvo; a palavra diz que foi ISTO. As
            # duas são necessárias, e o custo de exigir as duas é uma pendência
            # a conferir -- barato ao lado de uma ficha gravada pela metade.
            #
            # Seção sem palavra mapeada continua aceitando só a classe: não há
            # o que exigir, e o `ancora` do salvamento já garante o botão certo.
            palavra = PALAVRA_DA_SECAO.get(secao)

            # `palavra=palavra` captura por VALOR. Hoje `_serve` e chamada no
            # mesmo ciclo do laco, entao fechar sobre a variavel funcionaria --
            # mas basta alguem passar a guardar a funcao numa lista, ou adiar a
            # chamada, para todas as voltas passarem a usar a ULTIMA palavra.
            # Congelar aqui custa uma linha e tira a armadilha do caminho.
            def _serve(mensagem, palavra=palavra):
                if mensagem in vistas:
                    return False      # estava lá antes do clique
                if not palavra:
                    return True
                return palavra in _sem_acento(mensagem).lower()

            for mensagem in por_classe:
                if _serve(mensagem):
                    return True, mensagem

            for mensagem in todas:
                if not any(x in _sem_acento(mensagem).lower()
                           for x in MARCADORES_DE_SUCESSO):
                    continue
                if _serve(mensagem):
                    return True, mensagem
            if agora() >= fim:
                break
            dormir(INTERVALO_POLL_CONFIRMACAO_S)

        if callback_log:
            if ultima:
                callback_log(
                    f"      [!] Não vi a confirmação de '{secao}'. A última mensagem "
                    f"na tela foi: {ultima!r}")
            else:
                callback_log(
                    f"      [!] Não vi nenhuma mensagem de confirmação ao salvar "
                    f"'{secao}'. Confira a ficha antes de seguir.")
        return False, ultima

    # =========================================================================
    # excluir_linha_com_confirmacao -- mecânica CENTRAL comum a
    # `upload_tech_specs_backend.TechSpecsAutomation._excluir_linha_segura` e
    # ao ramo de exclusão de `upload_ficha_duplicada.InjetorFichaAlvo.
    # _limpar_caracteristicas_tecnicas`. Adota a estrutura mais completa
    # (tech_specs: sleep de 0,5s antes do clique na lixeira, 2,5s após
    # confirmar) -- ficha_duplicada não tinha o sleep de 0,5s e usava 2s (não
    # 2,5s) após confirmar; ver docs/refatoracao/PENDENCIAS.md.
    #
    # `apagar_lmr_backend.executar_limpeza` tem uma 3ª variante
    # ESTRUTURALMENTE diferente (busca a 1ª lixeira visível da TABELA INTEIRA
    # via um XPath específico desse módulo -- não tem uma "linha" para
    # passar) -- NÃO usa este método; ver PENDENCIAS.md.
    # =========================================================================
    def excluir_linha_com_confirmacao(self, seletor_linha: str) -> bool:
        """Clica na lixeira DENTRO da linha `seletor_linha` e confirma o
        popup. Retorna `True` em sucesso, `False` em qualquer falha (mesmo
        contrato de retorno de `TechSpecsAutomation._excluir_linha_segura`).

        CP 5.3 -- MUDANÇA DE ASSINATURA: o parâmetro era um ELEMENTO Selenium
        de linha (`row`), e passou a ser o SELETOR XPath dessa linha. Foi o
        que destravou o checkpoint: um elemento é um objeto do motor, e passá-lo
        por aí é o que impedia `tech_specs`/`ficha_duplicada` de rodarem em
        Playwright. Com seletor, a busca da lixeira "dentro da linha" vira
        concatenação de XPath -- mesmo alvo, sem objeto de motor no meio.

        Os 2 chamadores foram atualizados junto. Quem chamava com um elemento
        recebe `False` com aviso, em vez de um erro obscuro (ver abaixo).
        """
        if not isinstance(seletor_linha, str):
            # Rede de segurança para um chamador não migrado: falhar aqui com
            # mensagem é muito melhor do que deixar a concatenação produzir um
            # XPath inválido e o motor reclamar de sintaxe.
            print(
                "      [Aviso] excluir_linha_com_confirmacao passou a receber o "
                "SELETOR da linha (str), não o elemento -- ver CP 5.3."
            )
            return False

        seletor_lixeira = f'{seletor_linha}//i[contains(@class, "fa-trash")]/parent::a'
        try:
            self.engine.scroll_to(seletor_lixeira)
            time.sleep(0.5)
            self.engine.click_raw(seletor_lixeira)

            self.safe_click(XPATH_CONFIRMAR)

            time.sleep(2.5)  # Pausa crucial para o site reconstruir a tabela HTML
            return True
        except Exception:
            return False

    # =========================================================================
    # pesquisar_e_abrir -- ver docstring do módulo e o levantamento completo
    # no prompt do checkpoint (docs/refatoracao/PENDENCIAS.md tem o resumo).
    # =========================================================================
    def pesquisar_e_abrir(
        self,
        pmib,
        *,
        busca_xpath: str = DEFAULT_BUSCA_XPATH,
        lapis_xpath_template: str = DEFAULT_LAPIS_XPATH_TEMPLATE,
        ir_para_lista: bool = True,
    ) -> bool:
        """Navega para a lista (se `ir_para_lista`), pesquisa `pmib` e clica
        no ícone de edição (lápis) da linha correspondente. Adota a
        ESTRUTURA de robustez de
        `upload_tech_specs_backend.TechSpecsAutomation._pesquisar_e_abrir`
        (a variante mais robusta do diagnóstico) para TODOS os chamadores:
        retry de até 3 tentativas em cada etapa (busca e clique), tratando
        `StaleElementReferenceException`/`TimeoutException`; retorna `bool`.

        Isso é seguro (só adiciona resiliência, não muda o alvo final), mas
        NÃO é 100% sem efeito colateral observável -- ver
        docs/refatoracao/PENDENCIAS.md: (a) os sleeps ficam nos valores de
        tech_specs (0,5s após limpar campo, 4s após ENTER, 1s antes do
        clique no lápis) em vez dos valores originais mais curtos de
        `apagar_lmr` (0,2s/3s) ou mais longos de `upload_ficha_duplicada`
        (sem retry, sleeps fixos de 2-3s); (b) uma falha total (3 tentativas
        esgotadas) agora retorna `False` em vez de deixar a exceção Selenium
        original propagar sem tratamento nenhum (era o caso de
        `ExtratorFichaBase`/`InjetorFichaAlvo`, que não tinham NENHUM
        try/except) -- os delegadores em `upload_ficha_duplicada.py` tratam
        isso explicitamente (levantam `RuntimeError` quando `False`, para
        preservar a característica de "falha alta" do comportamento
        original). Reproduz também um detalhe estrutural do original citado
        acima: se as 3 tentativas da ETAPA DE BUSCA se esgotarem todas por
        `StaleElementReferenceException` (sem nunca cair no `except
        Exception: return False` nem no `break` de sucesso), a função
        PROSSEGUE para a etapa do lápis mesmo assim (não há `return False`
        explícito ao fim desse laço específico) -- comportamento idêntico ao
        de `tech_specs`, preservado tal qual (não é uma correção deste
        checkpoint).

        Parâmetros de override de seletor (por módulo, ver levantamento
        completo em docs/refatoracao/PENDENCIAS.md):
          - `busca_xpath` (XPath do campo de busca, SEM interpolação de
            `pmib`):
              * DEFAULT (`DEFAULT_BUSCA_XPATH`,
                `"//input[contains(@placeholder, 'Código')]"`) -- usado por
                `apagar_lmr_backend.ApagarLMRAutomation._pesquisar_e_abrir` e
                `upload_tech_specs_backend.TechSpecsAutomation.
                _pesquisar_e_abrir` (idênticos hoje) e por
                `lmr_backend.LMRAutomation.processar_lista` (que NUNCA teve
                seletor próprio para preservar -- usava 24 TABs cegos; ver
                exceção autorizada abaixo).
              * `upload_conditions_backend.UploadAutomation.processar_lista`
                passa
                `"//input[@placeholder='Código, Nome ES/PT pela Ficha Técnica, Código do projeto e/ou contrato']"`
                (placeholder EXATO, string diferente do default).
              * `upload_ficha_duplicada.ExtratorFichaBase`/`InjetorFichaAlvo.
                _pesquisar_e_abrir` passam
                `"//input[contains(@id, 'InputDatasheetFilter') or contains(@placeholder, 'Código')]"`
                (aceita id OU placeholder, string diferente do default).
          - `lapis_xpath_template` (XPath do ícone de edição, COM `{pmib}`
            interpolado via `str.format(pmib=pmib)`):
              * DEFAULT (`DEFAULT_LAPIS_XPATH_TEMPLATE`,
                `"//span[text()='{pmib}']/ancestor::tr//i[contains(@class, 'fa-pencil')]/parent::a"`)
                -- usado por `apagar_lmr`/`upload_tech_specs`/`lmr` (span
                com texto EXATO igual ao PMIB, classe de ícone `fa-pencil`).
              * `upload_conditions_backend.UploadAutomation.processar_lista`
                passa
                `"//span[text()='{pmib}']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]"`
                -- mesma estratégia de span exato, mas classe de ícone
                DIFERENTE (`fa-pencil-square-o`, não `fa-pencil`).
              * `upload_ficha_duplicada.ExtratorFichaBase`/`InjetorFichaAlvo`
                passam
                `"//tr[contains(., '{pmib}')]//a[.//i[contains(@class, 'fa-pencil')]]"`
                -- estratégia DIFERENTE (substring em qualquer texto da
                linha inteira, não span exato), classe `fa-pencil`.
          - `ir_para_lista` (bool, default `True`): quando `False`, pula a
            checagem/navegação para `config.PORTAL_URL` (nenhum chamador
            real usa `False` neste checkpoint -- existe para permitir
            compor `pesquisar_e_abrir` depois de uma navegação já feita por
            fora, sem repetir o passo).

        `upload_ficha_duplicada` tinha um passo EXTRA que os outros 3 não
        têm: esperar a linha aparecer
        (`wait.until(presence_of_element_located((By.XPATH,
        f"//tr[contains(., '{pmib}')]")))`) ANTES de procurar o lápis.
        DECISÃO: não foi adicionado um parâmetro `espera_linha_xpath_template`
        para preservar esse passo à parte -- ele é REDUNDANTE com o
        retry-loop novo: o `lapis_xpath_template` de `upload_ficha_duplicada`
        já é `"//tr[contains(., '{pmib}')]//a[...]"`, ou seja, JÁ EXIGE que a
        linha contendo o `pmib` exista para casar; se a linha ainda não
        apareceu, a mesma condição de espera (`presence_of_element_located`)
        simplesmente ainda não é satisfeita, e o retry (3 tentativas, com
        sleep entre elas) dá exatamente o mesmo tempo extra que a espera
        separada dava. Ver docs/refatoracao/PENDENCIAS.md.

        EXCEÇÃO AUTORIZADA (`lmr_backend`): o fluxo de 24 TABs cegos de
        `LMRAutomation.processar_lista` foi SUBSTITUÍDO por uma chamada a
        este método com os seletores DEFAULT (mesmo alvo final: abrir a
        ficha em modo de edição) -- única classe onde o PLANO autoriza
        explicitamente uma mudança de MECANISMO (não só reorganização) nas
        Fases 1-4.
        """
        # CP 5.1: as 6 operações Selenium cruas deste corpo viraram chamadas às
        # primitivas de `RPAEngine` (`clear`/`type_text`/`press`/`wait_present`/
        # `click_estrito`), e as duas exceções capturadas viraram as neutras de
        # `engine.py`. As primitivas do `SeleniumEngine` são as MESMAS linhas
        # movidas -- este método continua fazendo exatamente o que fazia no
        # motor Selenium; agora ele também roda no de Playwright.
        #
        # A única troca de mecânica é `campo.send_keys(Keys.ENTER)` ->
        # `engine.press("ENTER")`: o `send_keys` do Selenium é sempre no
        # elemento, o `press` do contrato é no elemento COM FOCO. Dá no mesmo
        # aqui porque o `type_text` imediatamente anterior deixa o foco no
        # campo de busca -- é o que ambos os motores garantem (Selenium pelo
        # próprio `send_keys`, Playwright pelo `press_sequentially`, que foca
        # o elemento antes de digitar).
        if ir_para_lista:
            self.ir_para_lista()

        # 2. Pesquisar (com retry) -- estrutura de tech_specs.
        for _tentativa in range(3):
            try:
                self.engine.clear(busca_xpath)
                time.sleep(0.5)
                self.engine.type_text(busca_xpath, pmib)
                time.sleep(0.5)
                self.engine.press("ENTER")
                time.sleep(4)  # Espera tabela recarregar
                break
            except ElementoObsoleto:
                time.sleep(1)
            except Exception:
                return False

        # 3. Clicar no lápis de edição (com retry) -- estrutura de tech_specs.
        xpath_lapis = lapis_xpath_template.format(pmib=pmib)
        for _tentativa in range(3):
            try:
                self.engine.wait_present(xpath_lapis)
                self.engine.scroll_to(xpath_lapis)
                time.sleep(1)
                self.engine.click_raw(xpath_lapis)
                time.sleep(4)  # Espera abrir a edição
                return True
            except ElementoObsoleto:
                time.sleep(2)
            except TempoEsgotado:
                time.sleep(2)

        return False

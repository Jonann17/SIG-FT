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

# CP 5.1: `Keys` e as exceções do Selenium saíram daqui -- `pesquisar_e_abrir`
# passou a usar as primitivas de `RPAEngine` e as exceções NEUTRAS de
# `engine.py`. `By`/`EC` continuam porque `check_or_uncheck`,
# `clicar_salvar_visivel` e `excluir_linha_com_confirmacao` ainda alcançam
# `self.engine.driver`/`.wait` crus: só rodam nos módulos que a Fase 5 migra
# nos CP 5.3 / Fase 6 (ver docs/refatoracao/PENDENCIAS.md).
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from sigft import config
from sigft.core.rpa.engine import ElementoObsoleto, RPAEngine, TempoEsgotado

# Seletores DEFAULT de `pesquisar_e_abrir` -- IDÊNTICOS aos de
# `apagar_lmr_backend.ApagarLMRAutomation._pesquisar_e_abrir` e
# `upload_tech_specs_backend.TechSpecsAutomation._pesquisar_e_abrir` (2 dos 4
# sites reais já usam exatamente isso hoje -- ver docstring de
# `pesquisar_e_abrir` abaixo para a lista completa de overrides por módulo).
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
    # check_or_uncheck -- só existia em upload_conditions_backend.py (não
    # duplicado antes, só "movido"). Precisa do atributo `checked`, que não
    # tem equivalente na interface de intenção de `RPAEngine` -- acessa
    # `self.engine.driver`/`.wait` diretamente (ver docstring do módulo).
    # =========================================================================
    def check_or_uncheck(self, seletor: str, should_check: bool) -> None:
        """Marca/desmarca um checkbox/radio localizado por `seletor` (XPath)
        só se o estado atual (`get_attribute('checked')`) divergir de
        `should_check` -- mecânica idêntica à original de
        `upload_conditions_backend.UploadAutomation.check_or_uncheck`."""
        driver = self.engine.driver
        wait = self.engine.wait
        try:
            el = wait.until(EC.presence_of_element_located((By.XPATH, seletor)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            is_checked = el.get_attribute("checked") == "true"
            if is_checked != should_check:
                self.safe_click(seletor)
        except Exception:
            pass

    # =========================================================================
    # clicar_salvar_visivel -- só existia em upload_ficha_duplicada.py
    # (InjetorFichaAlvo._clicar_salvar_visivel, não duplicado, só "movido").
    # Preserva os `print()` originais tal qual (mover != melhorar).
    # =========================================================================
    def clicar_salvar_visivel(self, nome_secao: str = "") -> bool:
        """Procura na tela o botão SALVAR (`btn-primary`, texto exato
        "SALVAR") que estiver visível/habilitado no momento e clica nele.
        Mecânica idêntica à original de
        `upload_ficha_duplicada.InjetorFichaAlvo._clicar_salvar_visivel`
        (incluindo os `print()` de progresso/aviso, preservados tal qual)."""
        driver = self.engine.driver
        if nome_secao:
            print(f"      [Injetor] Salvando {nome_secao}...")

        botoes_salvar = driver.find_elements(
            By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space(text())='SALVAR']"
        )
        for btn in botoes_salvar:
            if btn.is_displayed() and btn.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2.5)  # Aguarda a requisição do servidor OutSystems
                return True

        print(f"      [Aviso] Botão SALVAR não encontrado/visível para {nome_secao}.")
        return False

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
    def excluir_linha_com_confirmacao(self, row) -> bool:
        """Clica na lixeira DENTRO de `row` (elemento de linha já
        localizado, via `.//i[contains(@class,"fa-trash")]/parent::a`) e
        confirma o popup (`//button[@type="button" and text()="CONFIRMAR"]`).
        Retorna `True` em sucesso, `False` em qualquer falha (mesmo contrato
        de retorno de `TechSpecsAutomation._excluir_linha_segura`)."""
        driver = self.engine.driver
        try:
            btn_lixo = row.find_element(By.XPATH, './/i[contains(@class, "fa-trash")]/parent::a')
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_lixo)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", btn_lixo)

            self.safe_click('//button[@type="button" and text()="CONFIRMAR"]')

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

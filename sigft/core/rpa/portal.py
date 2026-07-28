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
"""

from __future__ import annotations

import time

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from sigft import config
from sigft.core.rpa.engine import RPAEngine

# Seletores DEFAULT de `pesquisar_e_abrir` -- IDÊNTICOS aos de
# `apagar_lmr_backend.ApagarLMRAutomation._pesquisar_e_abrir` e
# `upload_tech_specs_backend.TechSpecsAutomation._pesquisar_e_abrir` (2 dos 4
# sites reais já usam exatamente isso hoje -- ver docstring de
# `pesquisar_e_abrir` abaixo para a lista completa de overrides por módulo).
DEFAULT_BUSCA_XPATH = "//input[contains(@placeholder, 'Código')]"
DEFAULT_LAPIS_XPATH_TEMPLATE = "//span[text()='{pmib}']/ancestor::tr//i[contains(@class, 'fa-pencil')]/parent::a"


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
        if self.engine.driver.current_url != config.PORTAL_URL:
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
        driver = self.engine.driver
        wait = self.engine.wait

        if ir_para_lista:
            self.ir_para_lista()

        # 2. Pesquisar (com retry) -- estrutura de tech_specs.
        locator_pesquisa = (By.XPATH, busca_xpath)
        for _tentativa in range(3):
            try:
                campo = wait.until(EC.element_to_be_clickable(locator_pesquisa))
                campo.clear()
                time.sleep(0.5)
                campo.send_keys(pmib)
                time.sleep(0.5)
                campo.send_keys(Keys.ENTER)
                time.sleep(4)  # Espera tabela recarregar
                break
            except StaleElementReferenceException:
                time.sleep(1)
            except Exception:
                return False

        # 3. Clicar no lápis de edição (com retry) -- estrutura de tech_specs.
        xpath_lapis = lapis_xpath_template.format(pmib=pmib)
        for _tentativa in range(3):
            try:
                botao = wait.until(EC.presence_of_element_located((By.XPATH, xpath_lapis)))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", botao)
                time.sleep(4)  # Espera abrir a edição
                return True
            except StaleElementReferenceException:
                time.sleep(2)
            except TimeoutException:
                time.sleep(2)

        return False

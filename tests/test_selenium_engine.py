r"""
Testes do Checkpoint 2.1 — `sigft/core/rpa/selenium_engine.py`
(`create_chrome_driver` + `SeleniumEngine`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.1.

Duas estratégias de teste bem distintas (ver docstring do módulo para o
racional completo):

  1. `create_chrome_driver`/`SeleniumEngine.create`: `selenium.webdriver`/
     `WebDriverWait` já são `MagicMock`s neste ambiente (via
     tests/conftest.py) -- chamar a função de VERDADE não lança navegador
     nenhum, só invoca métodos mockados. Cada teste substitui
     `webdriver.Chrome`/`webdriver.ChromeOptions`/`WebDriverWait` (dentro do
     módulo `selenium_engine`, via `monkeypatch`) por `MagicMock()` NOVOS --
     isola cada teste de qualquer chamada feita por outro teste/módulo
     (evita poluição de call_count/call_args entre testes, já que o mock
     "real" de `selenium.webdriver` é compartilhado globalmente pelo
     processo de teste inteiro -- `monkeypatch` restaura o valor original
     ao final de cada teste automaticamente).

  2. `SeleniumEngine` (click/fill/press/wait_*/get_value/element_exists/
     screenshot/set_download_dir): `driver`/`wait` são FAKES Python simples
     (duck-typed, NÃO MagicMock) -- um `_FakeWait.until(condicao)` ignora a
     condição real do Selenium (`EC.presence_of_element_located` etc.) e
     devolve sempre o mesmo elemento pré-configurado (ou levanta uma
     exceção configurada). Não há como testar a integração real de
     `EC`/`By` neste ambiente sem o pacote `selenium` de verdade, e não é
     necessário: é lógica interna do Selenium, não nossa. O que testamos é
     a MECÂNICA que É nossa: ordem e argumentos exatos de
     `execute_script`/`send_keys`.
"""
from unittest.mock import MagicMock

import pytest

import sigft.core.rpa.selenium_engine as se
from sigft.core.rpa.engine import ElementoObsoleto, RPAEngine, TempoEsgotado


# ===========================================================================
# 1. create_chrome_driver — fábrica de baixo nível.
# ===========================================================================

def test_create_chrome_driver_sem_download_dir_chama_chrome_sem_options(monkeypatch):
    driver_mock = MagicMock(name="driver")
    chrome_mock = MagicMock(name="webdriver.Chrome", return_value=driver_mock)
    chrome_options_mock = MagicMock(name="webdriver.ChromeOptions")
    wait_mock = MagicMock(name="WebDriverWait")
    monkeypatch.setattr(se.webdriver, "Chrome", chrome_mock)
    monkeypatch.setattr(se.webdriver, "ChromeOptions", chrome_options_mock)
    monkeypatch.setattr(se, "WebDriverWait", wait_mock)

    driver, wait = se.create_chrome_driver(wait_timeout=20)

    # Sem download_dir: nenhum ChromeOptions é construído; Chrome() é
    # chamado SEM nenhum argumento -- comportamento de 5 dos 6 pontos
    # originais (todos exceto upload_ficha_duplicada).
    chrome_options_mock.assert_not_called()
    chrome_mock.assert_called_once_with()
    assert driver is driver_mock
    driver_mock.maximize_window.assert_called_once_with()
    wait_mock.assert_called_once_with(driver_mock, 20)
    assert wait is wait_mock.return_value


def test_create_chrome_driver_preserva_wait_timeout_recebido_sem_unificar(monkeypatch):
    # Os 6 call sites originais divergem entre 10/15/20 -- a fábrica NÃO
    # unifica: repassa o valor recebido tal qual para WebDriverWait.
    chrome_mock = MagicMock(name="webdriver.Chrome")
    wait_mock = MagicMock(name="WebDriverWait")
    monkeypatch.setattr(se.webdriver, "Chrome", chrome_mock)
    monkeypatch.setattr(se, "WebDriverWait", wait_mock)

    se.create_chrome_driver(wait_timeout=10)

    wait_mock.assert_called_once_with(chrome_mock.return_value, 10)


def test_create_chrome_driver_com_download_dir_monta_options_com_4_prefs_certos(monkeypatch):
    driver_mock = MagicMock(name="driver")
    chrome_mock = MagicMock(name="webdriver.Chrome", return_value=driver_mock)
    options_instance = MagicMock(name="options_instance")
    chrome_options_mock = MagicMock(name="webdriver.ChromeOptions", return_value=options_instance)
    wait_mock = MagicMock(name="WebDriverWait")
    monkeypatch.setattr(se.webdriver, "Chrome", chrome_mock)
    monkeypatch.setattr(se.webdriver, "ChromeOptions", chrome_options_mock)
    monkeypatch.setattr(se, "WebDriverWait", wait_mock)

    driver, wait = se.create_chrome_driver(wait_timeout=15, download_dir="/tmp/downloads")

    chrome_options_mock.assert_called_once_with()
    options_instance.add_experimental_option.assert_called_once_with(
        "prefs",
        {
            "download.default_directory": "/tmp/downloads",
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    chrome_mock.assert_called_once_with(options=options_instance)
    assert driver is driver_mock
    driver_mock.maximize_window.assert_called_once_with()
    wait_mock.assert_called_once_with(driver_mock, 15)
    assert wait is wait_mock.return_value


def test_create_chrome_driver_download_dir_vazio_equivale_a_none(monkeypatch):
    # "" é falsy -- mesmo branch de download_dir=None (nenhum dos 6 call
    # sites originais passa string vazia, mas a condição `if download_dir:`
    # nasce tratando os dois casos igual).
    chrome_mock = MagicMock(name="webdriver.Chrome")
    chrome_options_mock = MagicMock(name="webdriver.ChromeOptions")
    wait_mock = MagicMock(name="WebDriverWait")
    monkeypatch.setattr(se.webdriver, "Chrome", chrome_mock)
    monkeypatch.setattr(se.webdriver, "ChromeOptions", chrome_options_mock)
    monkeypatch.setattr(se, "WebDriverWait", wait_mock)

    se.create_chrome_driver(wait_timeout=20, download_dir="")

    chrome_options_mock.assert_not_called()
    chrome_mock.assert_called_once_with()


# ===========================================================================
# 2. SeleniumEngine.create — combina a fábrica + construção do engine num
#    só passo (consumido a partir do CP 2.2 -- ainda sem call site real).
# ===========================================================================

def test_selenium_engine_create_delega_para_create_chrome_driver(monkeypatch):
    fake_driver = object()
    fake_wait = object()
    factory_mock = MagicMock(return_value=(fake_driver, fake_wait))
    monkeypatch.setattr(se, "create_chrome_driver", factory_mock)

    engine = se.SeleniumEngine.create(wait_timeout=15, download_dir="/tmp/x")

    factory_mock.assert_called_once_with(wait_timeout=15, download_dir="/tmp/x")
    assert isinstance(engine, se.SeleniumEngine)
    assert isinstance(engine, RPAEngine)
    assert engine.driver is fake_driver
    assert engine.wait is fake_wait


def test_selenium_engine_create_usa_defaults_wait_timeout_20_sem_download_dir(monkeypatch):
    factory_mock = MagicMock(return_value=(object(), object()))
    monkeypatch.setattr(se, "create_chrome_driver", factory_mock)

    se.SeleniumEngine.create()

    factory_mock.assert_called_once_with(wait_timeout=20, download_dir=None)


# ===========================================================================
# Fakes duck-typed para os testes de MECÂNICA abaixo (click/fill/etc.) --
# nunca MagicMock: `wait.until(condicao)` IGNORA `condicao` de propósito
# (ver docstring do módulo) e devolve sempre o mesmo elemento
# pré-configurado, a não ser que uma exceção tenha sido configurada.
# ===========================================================================

class _FakeElement:
    def __init__(self, valor=None):
        self.valor = valor
        self.send_keys_chamadas = []
        self.click_chamadas = 0

    def get_attribute(self, nome):
        assert nome == "value"
        return self.valor

    def send_keys(self, *args):
        self.send_keys_chamadas.append(args)

    def click(self):
        """Clique NATIVO do WebDriver -- o que `click_nativo` usa e que
        nenhuma outra primitiva de clique deste motor usa."""
        self.click_chamadas += 1


class _FakeWait:
    def __init__(self, elemento=None, excecao=None):
        self.elemento = elemento
        self.excecao = excecao
        self.chamadas = []

    def until(self, condicao):
        self.chamadas.append(condicao)
        if self.excecao is not None:
            raise self.excecao
        return self.elemento


class _FakeDriver:
    def __init__(self):
        self.execute_script_chamadas = []
        self.get_chamadas = []
        self.find_elements_chamadas = []
        self.find_elements_retorno = []
        self.screenshot_chamadas = []
        self.cdp_chamadas = []

    def get(self, url):
        self.get_chamadas.append(url)

    def execute_script(self, script, *args):
        # CP 5.3: `forcar_valor` passa o VALOR como 2º argumento do script
        # (`arguments[1]`), então o fake precisa aceitar mais de um.
        self.execute_script_chamadas.append((script, *args))

    def find_elements(self, by, seletor):
        self.find_elements_chamadas.append((by, seletor))
        return self.find_elements_retorno

    def save_screenshot(self, caminho):
        self.screenshot_chamadas.append(caminho)

    def execute_cdp_cmd(self, comando, params):
        self.cdp_chamadas.append((comando, params))


def test_selenium_engine_e_instancia_concreta_de_rpaengine():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait())
    assert isinstance(engine, RPAEngine)


# ===========================================================================
# goto
# ===========================================================================

def test_goto_chama_driver_get_com_a_url():
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait())

    engine.goto("https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList")

    assert driver.get_chamadas == ["https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"]


# ===========================================================================
# click — mecânica canônica de safe_click: scroll, DEPOIS click via JS,
# nesta ordem, no MESMO elemento devolvido por wait.until.
# ===========================================================================

def test_click_faz_scroll_e_depois_click_via_js_no_elemento_certo_e_nesta_ordem():
    elemento = _FakeElement()
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=elemento))

    engine.click("//button[@id='salvar']")

    assert len(driver.execute_script_chamadas) == 2
    script_scroll, el_scroll = driver.execute_script_chamadas[0]
    script_click, el_click = driver.execute_script_chamadas[1]
    assert "scrollIntoView" in script_scroll
    assert el_scroll is elemento
    assert "click();" in script_click
    assert el_click is elemento


def test_click_engole_excecao_silenciosamente_mecanica_canonica_de_safe_click():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=TimeoutError("sumiu")))

    # Não levanta -- mesmo `except Exception: pass` das 4 cópias de
    # safe_click hoje (apagar_lmr, upload_conditions, upload_tech_specs,
    # upload_ficha_duplicada).
    engine.click("//nao/existe")


# ===========================================================================
# fill — mecânica canônica de safe_send_keys: scroll, click (foca), depois
# Ctrl+A, Backspace, texto -- nesta ordem.
# ===========================================================================

def test_fill_faz_scroll_foca_e_digita_ctrl_a_backspace_texto_na_ordem_certa():
    elemento = _FakeElement()
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=elemento))

    engine.fill("//textarea[@id='obs']", "novo texto")

    assert len(driver.execute_script_chamadas) == 2
    script_scroll, el_scroll = driver.execute_script_chamadas[0]
    script_click, el_click = driver.execute_script_chamadas[1]
    assert "scrollIntoView" in script_scroll
    assert el_scroll is elemento
    assert "click();" in script_click
    assert el_click is elemento

    # send_keys: Ctrl+A, Backspace, texto -- nesta ordem exata.
    assert len(elemento.send_keys_chamadas) == 3
    assert elemento.send_keys_chamadas[0] == (se.Keys.CONTROL, "a")
    assert elemento.send_keys_chamadas[1] == (se.Keys.BACKSPACE,)
    assert elemento.send_keys_chamadas[2] == ("novo texto",)


def test_fill_converte_texto_nao_string_via_str_como_o_original():
    elemento = _FakeElement()
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=elemento))

    engine.fill("//input[@id='qtd']", 42)

    assert elemento.send_keys_chamadas[2] == ("42",)


def test_fill_engole_excecao_silenciosamente_mecanica_canonica_de_safe_send_keys():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=TimeoutError("sumiu")))

    engine.fill("//nao/existe", "x")


# ===========================================================================
# press — NÃO recebe seletor; envia tecla(s) ao elemento com foco via
# ActionChains(driver).send_keys(...).perform().
# ===========================================================================

def test_press_com_string_unica_envia_1_tecla_e_finaliza_com_perform(monkeypatch):
    actions_mock = MagicMock(name="actions")
    action_chains_cls = MagicMock(name="ActionChains", return_value=actions_mock)
    monkeypatch.setattr(se, "ActionChains", action_chains_cls)

    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait())

    engine.press("ENTER")

    action_chains_cls.assert_called_once_with(driver)
    actions_mock.send_keys.assert_called_once_with(se.Keys.ENTER)
    actions_mock.perform.assert_called_once_with()


def test_press_com_lista_envia_cada_tecla_na_ordem_e_finaliza_com_1_perform(monkeypatch):
    actions_mock = MagicMock(name="actions")
    action_chains_cls = MagicMock(name="ActionChains", return_value=actions_mock)
    monkeypatch.setattr(se, "ActionChains", action_chains_cls)

    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait())

    engine.press(["TAB", "TAB", "ENTER"])

    assert actions_mock.send_keys.call_args_list == [
        ((se.Keys.TAB,),),
        ((se.Keys.TAB,),),
        ((se.Keys.ENTER,),),
    ]
    actions_mock.perform.assert_called_once_with()


# ===========================================================================
# wait_visible / wait_clickable — NÃO engolem exceção (ver docstring do
# módulo: apagar_lmr/upload_tech_specs dependem de capturar
# TimeoutException para decidir fim de loop/StaleElement).
# ===========================================================================

def test_wait_visible_propaga_excecao_quando_condicao_nao_e_satisfeita():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=TimeoutError("nunca ficou visível")))

    with pytest.raises(TimeoutError):
        engine.wait_visible("//div[@id='spinner']")


def test_wait_visible_nao_levanta_quando_elemento_aparece():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=_FakeElement()))

    engine.wait_visible("//div[@id='ok']")  # não levanta


def test_wait_clickable_propaga_excecao_quando_condicao_nao_e_satisfeita():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=TimeoutError("nunca ficou clicável")))

    with pytest.raises(TimeoutError):
        engine.wait_clickable("//button[@id='salvar']")


def test_wait_clickable_nao_levanta_quando_elemento_aparece():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=_FakeElement()))

    engine.wait_clickable("//button[@id='ok']")  # não levanta


# ===========================================================================
# get_value — lê get_attribute("value"); NÃO engole exceção.
# ===========================================================================

def test_get_value_le_o_atributo_value_do_elemento():
    elemento = _FakeElement(valor="4500063671.1234")
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=elemento))

    assert engine.get_value("//input[@id='codigo']") == "4500063671.1234"


def test_get_value_propaga_excecao_quando_elemento_nao_aparece():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=TimeoutError("sumiu")))

    with pytest.raises(TimeoutError):
        engine.get_value("//input[@id='nao-existe']")


# ===========================================================================
# element_exists — checagem IMEDIATA via driver.find_elements (nunca
# espera, diferente de wait_visible/wait_clickable).
# ===========================================================================

def test_element_exists_true_quando_find_elements_devolve_algo():
    driver = _FakeDriver()
    driver.find_elements_retorno = [_FakeElement()]
    engine = se.SeleniumEngine(driver, _FakeWait())

    assert engine.element_exists("//div[@id='existe']") is True
    assert driver.find_elements_chamadas == [(se.By.XPATH, "//div[@id='existe']")]


def test_element_exists_false_quando_find_elements_devolve_lista_vazia():
    driver = _FakeDriver()
    driver.find_elements_retorno = []
    engine = se.SeleniumEngine(driver, _FakeWait())

    assert engine.element_exists("//div[@id='nao-existe']") is False


# ===========================================================================
# screenshot / set_download_dir
# ===========================================================================

def test_screenshot_chama_save_screenshot_com_o_caminho():
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait())

    engine.screenshot("/tmp/erro.png")

    assert driver.screenshot_chamadas == ["/tmp/erro.png"]


def test_set_download_dir_chama_cdp_page_set_download_behavior():
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait())

    engine.set_download_dir("/tmp/downloads")

    assert driver.cdp_chamadas == [
        ("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": "/tmp/downloads"}),
    ]


# ===========================================================================
# CP 5.1 — primitivas novas (`click_estrito`, `scroll_to`, `click_raw`,
# `wait_present`, `clear`, `type_text`, `current_url`, `fechar`) e a
# TRADUÇÃO de exceção do SDK para as neutras de `engine.py`.
#
# Estes testes são a outra metade da mudança feita em `portal.py`: a mecânica
# Selenium que vivia dentro de `PMIBPortal.pesquisar_e_abrir`
# (`wait.until(EC...)`, `execute_script("scrollIntoView")`,
# `execute_script("click")`, `clear()`, `send_keys()`) saiu de lá e desceu
# para cá. Se estas asserções não existissem, a cobertura daquela mecânica
# teria simplesmente sumido junto com o refactor -- e a promessa de que o
# motor Selenium continua se comportando IGUAL ficaria sem prova.
# ===========================================================================

class _TimeoutExceptionFalsa(Exception):
    """Nome IDÊNTICO ao da classe real do Selenium é o que importa: a
    tradução casa por nome ao longo da MRO, justamente porque neste ambiente
    `selenium.common.exceptions` é um MagicMock (ver `_traduzir`)."""
    __name__ = "TimeoutException"


_TimeoutExceptionFalsa.__name__ = "TimeoutException"


class _StaleFalsa(Exception):
    pass


_StaleFalsa.__name__ = "StaleElementReferenceException"


class _SubclasseDeTimeout(_TimeoutExceptionFalsa):
    pass


# --- scroll_to --------------------------------------------------------------

def test_scroll_to_faz_scroll_into_view_no_elemento_e_nao_clica():
    elemento = _FakeElement()
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=elemento))

    engine.scroll_to("//a[@id='lapis']")

    assert driver.execute_script_chamadas == [
        ("arguments[0].scrollIntoView({block: 'center'});", elemento),
    ]


# --- click_raw --------------------------------------------------------------

def test_click_raw_clica_via_js_sem_rolar_e_sem_esperar_clicavel():
    # É EXATAMENTE o que `pesquisar_e_abrir` fazia no lápis depois do scroll:
    # `driver.execute_script("arguments[0].click();", botao)`. Nada de
    # `element_to_be_clickable` -- acrescentar essa espera aqui mudaria o
    # comportamento de 4 módulos que seguem no Selenium.
    elemento = _FakeElement()
    driver = _FakeDriver()
    wait = _FakeWait(elemento=elemento)
    engine = se.SeleniumEngine(driver, wait)

    engine.click_raw("//a[@id='lapis']")

    assert driver.execute_script_chamadas == [("arguments[0].click();", elemento)]
    assert len(wait.chamadas) == 1  # só a espera de presença


# --- click_nativo -----------------------------------------------------------

def test_click_nativo_usa_o_clique_do_webdriver_e_nao_javascript():
    """A distinção que este método existe para fazer.

    `execute_script("arguments[0].click()")` dispara o evento de clique mas
    NÃO move o foco do navegador; o clique nativo move. Em `cria_fichas` tudo
    o que vem depois de um clique é `press("TAB")`/`digitar_no_foco(...)`, ou
    seja, relativo ao foco -- com clique por JS as teclas caem no elemento
    errado, em silêncio (foi o Contrato em branco do 1º teste real).
    """
    elemento = _FakeElement()
    driver = _FakeDriver()
    wait = _FakeWait(elemento=elemento)
    engine = se.SeleniumEngine(driver, wait)

    engine.click_nativo("//button[@id='salvar']")

    assert elemento.click_chamadas == 1
    # A asserção que importa: NENHUM JavaScript. Se algum dia alguém
    # "unificar" isto com `click_raw`, este teste cai.
    assert driver.execute_script_chamadas == []
    assert len(wait.chamadas) == 1  # a espera de "clicável"


def test_click_nativo_traduz_o_timeout_da_espera_de_clicavel():
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(excecao=_TimeoutExceptionFalsa("sumiu")))

    with pytest.raises(TempoEsgotado):
        engine.click_nativo("//button")


def test_scroll_to_mais_click_raw_reproduzem_a_sequencia_original_do_lapis():
    # Contraprova de ordem: scroll ANTES do clique, no mesmo elemento.
    elemento = _FakeElement()
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=elemento))

    engine.scroll_to("//a")
    engine.click_raw("//a")

    assert driver.execute_script_chamadas == [
        ("arguments[0].scrollIntoView({block: 'center'});", elemento),
        ("arguments[0].click();", elemento),
    ]


# --- click_estrito ----------------------------------------------------------

def test_click_estrito_tem_a_mesma_mecanica_de_click():
    elemento = _FakeElement()
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=elemento))

    engine.click_estrito("//button")

    assert driver.execute_script_chamadas == [
        ("arguments[0].scrollIntoView({block: 'center'});", elemento),
        ("arguments[0].click();", elemento),
    ]


def test_click_estrito_propaga_enquanto_click_engole():
    # A diferença INTEIRA entre os dois -- e a razão de `click_estrito`
    # existir: num laço, um clique que falha em silêncio vira giro infinito.
    driver = _FakeDriver()
    engine_estrito = se.SeleniumEngine(driver, _FakeWait(excecao=_TimeoutExceptionFalsa("sumiu")))
    engine_tolerante = se.SeleniumEngine(driver, _FakeWait(excecao=_TimeoutExceptionFalsa("sumiu")))

    with pytest.raises(TempoEsgotado):
        engine_estrito.click_estrito("//button")

    engine_tolerante.click("//button")  # não levanta


# --- click_dom --------------------------------------------------------------

def test_click_dom_clica_por_javascript_sem_rolar_nem_esperar_clicavel():
    """No Selenium `click_dom` não é capacidade nova -- é o mesmo
    `arguments[0].click()` que `click_estrito` já fazia. O que muda é o
    contrato ficar explícito, para o motor Playwright poder oferecer o
    equivalente (lá `Locator.click()` roda checagem de hit target e NÃO
    alcança o `<input>` coberto pelo rótulo do OutSystems).

    A diferença para `click_estrito` é o que NÃO acontece: sem scroll e sem
    espera de "clicável" -- `element_to_be_clickable` exige visibilidade, e
    quem chama esta primitiva já sabe que o alvo não é acionável.
    """
    elemento = _FakeElement()
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=elemento))

    engine.click_dom("//input[@id='b10-b17-b1-RadioButton1-input']")

    assert driver.execute_script_chamadas == [("arguments[0].click();", elemento)]


def test_click_dom_propaga_a_falha_traduzida_quando_o_elemento_nao_existe():
    """Presença continua obrigatória: clicar por DOM em nada não pode virar
    sucesso silencioso."""
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=_TimeoutExceptionFalsa("sumiu")))

    with pytest.raises(TempoEsgotado):
        engine.click_dom("//nao-existe")


# --- wait_present -----------------------------------------------------------

def test_wait_present_espera_presenca_e_nao_devolve_nada():
    wait = _FakeWait(elemento=_FakeElement())
    engine = se.SeleniumEngine(_FakeDriver(), wait)

    assert engine.wait_present("//tr") is None
    assert len(wait.chamadas) == 1


def test_wait_present_traduz_timeout_para_tempo_esgotado():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=_TimeoutExceptionFalsa("nada")))

    with pytest.raises(TempoEsgotado):
        engine.wait_present("//tr")


# --- clear / type_text ------------------------------------------------------

def test_clear_chama_clear_do_elemento_sem_digitar_nada():
    elemento = _FakeElement()
    elemento.clear_chamadas = 0
    elemento.clear = lambda: setattr(elemento, "clear_chamadas", elemento.clear_chamadas + 1)
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=elemento))

    engine.clear("//input")

    assert elemento.clear_chamadas == 1
    assert elemento.send_keys_chamadas == []


def test_type_text_digita_sem_limpar_antes():
    # `campo.send_keys(pmib)` do original -- SEM o Ctrl+A/Backspace que o
    # `fill` faz. A limpeza, quando o consumidor quer, é o `clear` separado.
    elemento = _FakeElement()
    elemento.clear = lambda: pytest.fail("type_text não pode limpar o campo")
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=elemento))

    engine.type_text("//input", "4500063671.1234")

    assert elemento.send_keys_chamadas == [("4500063671.1234",)]


def test_type_text_converte_valor_nao_string():
    # `pesquisar_e_abrir` recebe `pmib` de planilha, que às vezes chega como
    # número -- `send_keys` de um int estouraria no Selenium real.
    elemento = _FakeElement()
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=elemento))

    engine.type_text("//input", 4500063671)

    assert elemento.send_keys_chamadas == [("4500063671",)]


# --- current_url / fechar ---------------------------------------------------

def test_current_url_le_do_driver():
    driver = _FakeDriver()
    driver.current_url = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"
    engine = se.SeleniumEngine(driver, _FakeWait())

    assert engine.current_url() == "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"


def test_fechar_chama_quit_uma_vez_e_e_idempotente():
    quits = []
    driver = _FakeDriver()
    driver.quit = lambda: quits.append(1)
    engine = se.SeleniumEngine(driver, _FakeWait())

    engine.fechar()
    engine.fechar()  # contrato de engine.py: idempotente

    assert quits == [1]


def test_fechar_engole_falha_do_quit():
    # Chamado do `finally` de quem usa -- estourar aqui mascararia o erro
    # real que levou ao fechamento.
    driver = _FakeDriver()
    driver.quit = lambda: (_ for _ in ()).throw(RuntimeError("browser já morreu"))
    engine = se.SeleniumEngine(driver, _FakeWait())

    engine.fechar()  # não levanta


# --- tradução de exceção ----------------------------------------------------

def test_traduz_timeout_e_stale_e_deixa_o_resto_passar():
    assert isinstance(se._traduzir(_TimeoutExceptionFalsa("x")), TempoEsgotado)
    assert isinstance(se._traduzir(_StaleFalsa("x")), ElementoObsoleto)

    original = ValueError("outra coisa")
    assert se._traduzir(original) is original


def test_traduz_subclasse_das_excecoes_do_selenium():
    # Selenium tem subclasses (ex.: exceções específicas que herdam de
    # TimeoutException); casar só `type(e).__name__` deixaria essas passarem
    # sem tradução, e o laço que decide por tipo quebraria.
    assert isinstance(se._traduzir(_SubclasseDeTimeout("x")), TempoEsgotado)


def test_excecao_traduzida_preserva_a_original_encadeada():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=_TimeoutExceptionFalsa("detalhe")))

    with pytest.raises(TempoEsgotado) as capturado:
        engine.wait_present("//x")

    assert isinstance(capturado.value.__cause__, _TimeoutExceptionFalsa)
    assert "detalhe" in str(capturado.value)


def test_traducao_nao_toca_excecao_generica_das_esperas():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(excecao=RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        engine.wait_clickable("//x")


# ===========================================================================
# CP 5.3 — primitivas dos uploads
# ===========================================================================

def _driver_com(elementos):
    driver = _FakeDriver()
    driver.find_elements_retorno = elementos
    return driver


class _ElementoRico:
    def __init__(self, *, displayed=True, enabled=True, checked=None, texto=""):
        self.displayed = displayed
        self.enabled = enabled
        self.checked = checked
        self._texto = texto

    def is_displayed(self):
        return self.displayed

    def is_enabled(self):
        return self.enabled

    def get_attribute(self, nome):
        if nome == "checked":
            return self.checked
        if nome == "textContent":
            return self._texto
        raise AssertionError(f"atributo inesperado: {nome}")


# --- contar / estados -------------------------------------------------------

def test_contar_devolve_quantos_elementos_casam():
    engine = se.SeleniumEngine(_driver_com([object(), object(), object()]), _FakeWait())
    assert engine.contar("//tr") == 3


def test_contar_zero_quando_nada_casa():
    assert se.SeleniumEngine(_driver_com([]), _FakeWait()).contar("//tr") == 0


def test_esta_visivel_e_habilitado_olham_o_primeiro_casamento():
    driver = _driver_com([_ElementoRico(displayed=False, enabled=True)])
    engine = se.SeleniumEngine(driver, _FakeWait())
    assert engine.esta_visivel("//button") is False
    assert engine.esta_habilitado("//button") is True


def test_estados_devolvem_false_quando_o_elemento_nao_existe():
    # Sem isto, `clicar_salvar_visivel` estouraria com IndexError em vez de
    # simplesmente não achar botão.
    engine = se.SeleniumEngine(_driver_com([]), _FakeWait())
    assert engine.esta_visivel("//x") is False
    assert engine.esta_habilitado("//x") is False
    assert engine.esta_marcado("//x") is False


def test_esta_marcado_compara_com_a_string_true():
    # O Selenium devolve a STRING "true" no atributo `checked`, não um bool --
    # é a comparação do original de `upload_conditions.check_or_uncheck`.
    marcado = se.SeleniumEngine(_driver_com([_ElementoRico(checked="true")]), _FakeWait())
    desmarcado = se.SeleniumEngine(_driver_com([_ElementoRico(checked=None)]), _FakeWait())
    assert marcado.esta_marcado("//input") is True
    assert desmarcado.esta_marcado("//input") is False


# --- forcar_valor -----------------------------------------------------------

def test_forcar_valor_escreve_e_dispara_os_tres_eventos_nesta_ordem():
    # Os eventos NÃO são adorno: sem eles o OutSystems não percebe a mudança e
    # devolve o campo ao valor antigo no próximo redesenho -- e a "2ª
    # tentativa" de `_preencher_input_com_auditoria` viraria teatro.
    elemento = _FakeElement()
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=elemento))

    engine.forcar_valor("//input", "42")

    scripts = [chamada[0] for chamada in driver.execute_script_chamadas]
    assert scripts[0] == "arguments[0].value = arguments[1];"
    assert "input" in scripts[1] and "dispatchEvent" in scripts[1]
    assert "change" in scripts[2]
    assert "blur" in scripts[3]
    assert len(scripts) == 4


def test_forcar_valor_passa_o_texto_por_argumento_e_nao_interpolado():
    # O original interpolava o valor DENTRO da string do script. Um valor com
    # aspas simples (medidas como `5' 1/2"` aparecem em ficha técnica)
    # quebrava o JavaScript e a injeção falhava em silêncio -- justamente no
    # caminho que existe para salvar um campo que já estava dando problema.
    driver = _FakeDriver()
    driver.execute_script_chamadas = []

    def _execute_script(script, *args):
        driver.execute_script_chamadas.append((script, args))

    driver.execute_script = _execute_script
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=_FakeElement()))

    engine.forcar_valor("//input", "5' 1/2\"")

    script, args = driver.execute_script_chamadas[0]
    assert "5'" not in script  # o valor NÃO entrou na string do script
    assert args[1] == "5' 1/2\""


# --- texto ------------------------------------------------------------------

def test_texto_le_o_textcontent_e_nao_o_value():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=_ElementoRico(texto=" 12 - Tensão ")))
    assert engine.texto("//td") == " 12 - Tensão "


def test_texto_devolve_string_vazia_quando_o_atributo_e_none():
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=_ElementoRico(texto=None)))
    assert engine.texto("//td") == ""


# --- foco -------------------------------------------------------------------

class _SwitchTo:
    def __init__(self, elemento):
        self.active_element = elemento


def test_focar_usa_js_e_nao_clica():
    # Clicar desmarcaria o checkbox que `upload_conditions` usa como âncora
    # da navegação por TAB -- por isso foco por JS, não clique.
    elemento = _FakeElement()
    driver = _FakeDriver()
    engine = se.SeleniumEngine(driver, _FakeWait(elemento=elemento))

    engine.focar("//input[@id='chk']")

    assert driver.execute_script_chamadas == [("arguments[0].focus();", elemento)]


def test_digitar_no_foco_envia_ao_elemento_ativo():
    ativo = _FakeElement()
    driver = _FakeDriver()
    driver.switch_to = _SwitchTo(ativo)
    engine = se.SeleniumEngine(driver, _FakeWait())

    engine.digitar_no_foco(25)

    assert ativo.send_keys_chamadas == [("25",)]  # converte para string


# --- dropdowns --------------------------------------------------------------

class _OpcaoFalsa:
    def __init__(self, texto):
        self.text = texto


class _SelectFalso:
    def __init__(self, opcoes):
        self.options = [_OpcaoFalsa(t) for t in opcoes]
        self.por_texto = []
        self.por_indice = []

    def select_by_visible_text(self, texto):
        if texto not in [o.text for o in self.options]:
            raise ValueError("sem opção com esse texto")
        self.por_texto.append(texto)

    def select_by_index(self, indice):
        self.por_indice.append(indice)


def test_opcoes_devolve_os_textos_na_ordem(monkeypatch):
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=_FakeElement()))
    falso = _SelectFalso(["Milímetro (MM)", "Metro (M)"])
    monkeypatch.setattr(engine, "_select", lambda seletor: falso)

    assert engine.opcoes("//select") == ["Milímetro (MM)", "Metro (M)"]


def test_selecionar_por_texto_e_por_indice(monkeypatch):
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=_FakeElement()))
    falso = _SelectFalso(["A", "B"])
    monkeypatch.setattr(engine, "_select", lambda seletor: falso)

    engine.selecionar_por_texto("//select", "B")
    engine.selecionar_por_indice("//select", 0)

    assert falso.por_texto == ["B"]
    assert falso.por_indice == [0]


def test_selecionar_por_texto_propaga_quando_nao_ha_a_opcao(monkeypatch):
    # `selecionar_dropdown_lista` DEPENDE dessa falha para cair na 2ª
    # tentativa (casamento normalizado). Engolir aqui mataria o fallback.
    engine = se.SeleniumEngine(_FakeDriver(), _FakeWait(elemento=_FakeElement()))
    monkeypatch.setattr(engine, "_select", lambda seletor: _SelectFalso(["A"]))

    with pytest.raises(Exception):
        engine.selecionar_por_texto("//select", "Z")

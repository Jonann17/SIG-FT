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
from sigft.core.rpa.engine import RPAEngine


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

    def get_attribute(self, nome):
        assert nome == "value"
        return self.valor

    def send_keys(self, *args):
        self.send_keys_chamadas.append(args)


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

    def execute_script(self, script, elemento):
        self.execute_script_chamadas.append((script, elemento))

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

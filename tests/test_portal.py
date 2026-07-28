r"""
Testes do Checkpoint 2.2 — `sigft/core/rpa/portal.py` (`PMIBPortal`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.2.

Duas famílias de teste (mesmo espírito de tests/test_selenium_engine.py):

  1. Lógica que É NOSSA e não depende de Selenium de verdade (stop-flag,
     `aguardar_login_manual`, `ir_para_lista` no nível de `config.PORTAL_URL`)
     -- testada com um `_FakeEngine` mínimo (duck-typed, nem precisa herdar
     de `RPAEngine`).
  2. Mecânica Selenium-specific (`safe_click`/`safe_fill` -- delegação fina
     para o engine --, `check_or_uncheck`, `clicar_salvar_visivel`,
     `excluir_linha_com_confirmacao`, `pesquisar_e_abrir`) -- testada com
     fakes duck-typed de `driver`/`wait` (nunca Selenium real), e com
     `EC.element_to_be_clickable`/`EC.presence_of_element_located`
     substituídos por wrappers triviais que devolvem o PRÓPRIO locator (em
     vez do MagicMock opaco que o `EC` stubado por tests/conftest.py
     devolveria) -- assim dá para inspecionar EXATAMENTE qual XPath foi
     pedido em cada chamada de `wait.until(...)`, sem depender da semântica
     real do Selenium (que não está instalado neste ambiente).

`time.sleep` é substituído por um no-op em TODOS os testes deste arquivo
(via fixture `_sem_sleep`, autouse) -- `pesquisar_e_abrir` soma vários
segundos de sleep por chamada (até ~15s no pior caso de retries); sem isso
a suíte ficaria lenta.
"""
from __future__ import annotations

import pytest

import sigft.core.rpa.portal as portal_mod
from sigft import config
from sigft.core.rpa.portal import PMIBPortal


# ===========================================================================
# Fixture global: elimina os `time.sleep(...)` reais de portal.py.
# ===========================================================================
@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    monkeypatch.setattr(portal_mod.time, "sleep", lambda *_a, **_kw: None)


# ===========================================================================
# Fakes duck-typed -- nunca MagicMock (ver docstring do módulo).
# ===========================================================================
class _FakeElemento:
    def __init__(self, *, checked=None, displayed=True, enabled=True, filhos=None):
        self.checked = checked
        self.displayed = displayed
        self.enabled = enabled
        self.filhos = filhos or {}
        self.send_keys_chamadas = []
        self.clear_chamadas = 0

    def clear(self):
        self.clear_chamadas += 1

    def send_keys(self, *args):
        self.send_keys_chamadas.append(args)

    def get_attribute(self, nome):
        assert nome == "checked"
        return self.checked

    def is_displayed(self):
        return self.displayed

    def is_enabled(self):
        return self.enabled

    def find_element(self, by, seletor):
        try:
            return self.filhos[seletor]
        except KeyError:
            raise Exception(f"filho não configurado para seletor: {seletor}")


class _FakeWait:
    """`until(condicao)` consome uma fila de respostas PRÉ-configurada, na
    ordem: cada item é um elemento (devolvido) ou uma instância de exceção
    (levantada). Fila vazia -> AssertionError (bug de teste, não silêncio)."""

    def __init__(self, respostas=None):
        self.respostas = list(respostas or [])
        self.chamadas = []

    def until(self, condicao):
        self.chamadas.append(condicao)
        if not self.respostas:
            raise AssertionError("FakeWait esgotado -- configure mais respostas no teste")
        proxima = self.respostas.pop(0)
        if isinstance(proxima, BaseException):
            raise proxima
        return proxima


class _FakeDriver:
    def __init__(self, current_url=""):
        self.current_url = current_url
        self.execute_script_chamadas = []
        self.find_elements_chamadas = []
        self.find_elements_retorno = []

    def execute_script(self, script, elemento):
        self.execute_script_chamadas.append((script, elemento))

    def find_elements(self, by, seletor):
        self.find_elements_chamadas.append((by, seletor))
        return self.find_elements_retorno


class _FakeEngine:
    """Duck-typed -- expõe só o que `PMIBPortal` usa (`driver`/`wait`
    diretamente, ou `goto`/`click`/`fill` via delegação)."""

    def __init__(self, driver=None, wait=None):
        self.driver = driver if driver is not None else _FakeDriver()
        self.wait = wait if wait is not None else _FakeWait()
        self.goto_chamadas = []
        self.click_chamadas = []
        self.fill_chamadas = []

    def goto(self, url):
        self.goto_chamadas.append(url)
        self.driver.current_url = url

    def click(self, seletor):
        self.click_chamadas.append(seletor)

    def fill(self, seletor, texto):
        self.fill_chamadas.append((seletor, texto))


@pytest.fixture(autouse=True)
def _ec_transparente(monkeypatch):
    """Substitui `EC.element_to_be_clickable`/`presence_of_element_located`
    (opacos, MagicMock, via tests/conftest.py) por wrappers que devolvem o
    PRÓPRIO locator -- assim `_FakeWait.chamadas` registra exatamente qual
    `(By.XPATH, xpath)` foi pedido, sem depender da semântica real do
    Selenium (indisponível neste ambiente de teste)."""
    monkeypatch.setattr(portal_mod.EC, "element_to_be_clickable", lambda locator: ("clickable", locator))
    monkeypatch.setattr(portal_mod.EC, "presence_of_element_located", lambda locator: ("presence", locator))


# ===========================================================================
# Construção / stop-flag -- não precisam de engine real (`engine=None` é o
# default, usado por `ConditionsProcessor`/`TechSpecsProcessor`, que não têm
# driver nenhum -- ver docstring do módulo).
# ===========================================================================
def test_engine_e_opcional_default_none():
    p = PMIBPortal()
    assert p.engine is None


def test_parar_solicitado_comeca_false():
    assert PMIBPortal().parar_solicitado is False


def test_deve_parar_false_antes_de_solicitar_parada():
    assert PMIBPortal(_FakeEngine()).deve_parar() is False


def test_solicitar_parada_faz_deve_parar_devolver_true():
    p = PMIBPortal()  # sem engine -- stop-flag não toca self.engine
    p.solicitar_parada()
    assert p.deve_parar() is True
    assert p.parar_solicitado is True


# ===========================================================================
# aguardar_login_manual -- capacidade nova, sem consumidor de produção.
# ===========================================================================
def test_aguardar_login_manual_chama_callback_com_motivo_default():
    chamadas = []
    PMIBPortal().aguardar_login_manual(callback_pause=chamadas.append)
    assert chamadas == ["LOGIN_NECESSARIO"]


def test_aguardar_login_manual_aceita_motivo_customizado():
    chamadas = []
    PMIBPortal().aguardar_login_manual(callback_pause=chamadas.append, motivo="OUTRO_MOTIVO")
    assert chamadas == ["OUTRO_MOTIVO"]


def test_aguardar_login_manual_sem_callback_nao_levanta():
    PMIBPortal().aguardar_login_manual()  # callback_pause=None -- sem-op


# ===========================================================================
# ir_para_lista -- usa config.PORTAL_URL, não um literal local.
# ===========================================================================
def test_ir_para_lista_navega_quando_url_atual_e_diferente():
    engine = _FakeEngine(driver=_FakeDriver(current_url="https://outro-lugar"))
    PMIBPortal(engine).ir_para_lista()
    assert engine.goto_chamadas == [config.PORTAL_URL]
    assert engine.driver.current_url == config.PORTAL_URL


def test_ir_para_lista_nao_navega_quando_ja_esta_na_url():
    engine = _FakeEngine(driver=_FakeDriver(current_url=config.PORTAL_URL))
    PMIBPortal(engine).ir_para_lista()
    assert engine.goto_chamadas == []


# ===========================================================================
# safe_click / safe_fill -- delegação FINA para o engine (mecânica real já
# em SeleniumEngine.click/.fill desde o CP 2.1).
# ===========================================================================
def test_safe_click_delega_para_engine_click_com_o_mesmo_seletor():
    engine = _FakeEngine()
    PMIBPortal(engine).safe_click("//button[@id='salvar']")
    assert engine.click_chamadas == ["//button[@id='salvar']"]


def test_safe_fill_delega_para_engine_fill_com_seletor_e_texto():
    engine = _FakeEngine()
    PMIBPortal(engine).safe_fill("//textarea[@id='obs']", "novo texto")
    assert engine.fill_chamadas == [("//textarea[@id='obs']", "novo texto")]


# ===========================================================================
# check_or_uncheck -- só existia em upload_conditions_backend.py.
# ===========================================================================
def test_check_or_uncheck_clica_quando_desmarcado_e_deveria_estar_marcado():
    elemento = _FakeElemento(checked=None)  # get_attribute('checked') != 'true' -> desmarcado
    driver = _FakeDriver()
    engine = _FakeEngine(driver=driver, wait=_FakeWait(respostas=[elemento]))

    PMIBPortal(engine).check_or_uncheck("//input[@id='chk']", True)

    assert engine.click_chamadas == ["//input[@id='chk']"]


def test_check_or_uncheck_nao_clica_quando_ja_no_estado_esperado():
    elemento = _FakeElemento(checked="true")
    engine = _FakeEngine(wait=_FakeWait(respostas=[elemento]))

    PMIBPortal(engine).check_or_uncheck("//input[@id='chk']", True)

    assert engine.click_chamadas == []


def test_check_or_uncheck_desmarca_quando_marcado_e_deveria_estar_desmarcado():
    elemento = _FakeElemento(checked="true")
    engine = _FakeEngine(wait=_FakeWait(respostas=[elemento]))

    PMIBPortal(engine).check_or_uncheck("//input[@id='chk']", False)

    assert engine.click_chamadas == ["//input[@id='chk']"]


def test_check_or_uncheck_engole_excecao_silenciosamente():
    engine = _FakeEngine(wait=_FakeWait(respostas=[TimeoutError("sumiu")]))
    PMIBPortal(engine).check_or_uncheck("//input[@id='nao-existe']", True)  # não levanta


# ===========================================================================
# clicar_salvar_visivel -- só existia em upload_ficha_duplicada.py.
# ===========================================================================
def test_clicar_salvar_visivel_clica_no_primeiro_botao_visivel_e_habilitado():
    btn_invisivel = _FakeElemento(displayed=False, enabled=True)
    btn_desabilitado = _FakeElemento(displayed=True, enabled=False)
    btn_alvo = _FakeElemento(displayed=True, enabled=True)
    driver = _FakeDriver()
    driver.find_elements_retorno = [btn_invisivel, btn_desabilitado, btn_alvo]
    engine = _FakeEngine(driver=driver)

    resultado = PMIBPortal(engine).clicar_salvar_visivel("Armazenamento")

    assert resultado is True
    # scroll + click, nesta ordem, no elemento certo.
    assert len(driver.execute_script_chamadas) == 2
    assert driver.execute_script_chamadas[0][1] is btn_alvo
    assert driver.execute_script_chamadas[1][1] is btn_alvo


def test_clicar_salvar_visivel_devolve_false_quando_nenhum_botao_visivel():
    driver = _FakeDriver()
    driver.find_elements_retorno = [_FakeElemento(displayed=False)]
    engine = _FakeEngine(driver=driver)

    assert PMIBPortal(engine).clicar_salvar_visivel() is False


def test_clicar_salvar_visivel_devolve_false_quando_lista_vazia():
    engine = _FakeEngine()
    assert PMIBPortal(engine).clicar_salvar_visivel() is False


# ===========================================================================
# excluir_linha_com_confirmacao -- recebe uma LINHA já localizada.
# ===========================================================================
def test_excluir_linha_com_confirmacao_sucesso():
    lixeira = _FakeElemento()
    row = _FakeElemento(filhos={'.//i[contains(@class, "fa-trash")]/parent::a': lixeira})
    driver = _FakeDriver()
    engine = _FakeEngine(driver=driver)

    resultado = PMIBPortal(engine).excluir_linha_com_confirmacao(row)

    assert resultado is True
    assert driver.execute_script_chamadas == [
        ("arguments[0].scrollIntoView({block: 'center'});", lixeira),
        ("arguments[0].click();", lixeira),
    ]
    # Confirma via safe_click -> engine.click, com o XPath genérico do popup.
    assert engine.click_chamadas == ['//button[@type="button" and text()="CONFIRMAR"]']


def test_excluir_linha_com_confirmacao_devolve_false_se_lixeira_nao_existe():
    row = _FakeElemento(filhos={})  # find_element levanta (sem lixeira configurada)
    engine = _FakeEngine()

    assert PMIBPortal(engine).excluir_linha_com_confirmacao(row) is False
    assert engine.click_chamadas == []  # nunca chegou a tentar confirmar


# ===========================================================================
# pesquisar_e_abrir -- estrutura de robustez de tech_specs, seletores
# parametrizados (default = apagar_lmr/tech_specs).
# ===========================================================================
def test_pesquisar_e_abrir_usa_seletores_default_e_ir_para_lista_por_padrao():
    campo = _FakeElemento()
    lapis = _FakeElemento()
    driver = _FakeDriver(current_url="https://outro-lugar")
    wait = _FakeWait(respostas=[campo, lapis])
    engine = _FakeEngine(driver=driver, wait=wait)

    resultado = PMIBPortal(engine).pesquisar_e_abrir("4500063671.1234")

    assert resultado is True
    assert engine.goto_chamadas == [config.PORTAL_URL]  # ir_para_lista chamado

    assert campo.clear_chamadas == 1
    assert campo.send_keys_chamadas == [("4500063671.1234",), (portal_mod.Keys.ENTER,)]

    locator_busca_esperado = (portal_mod.By.XPATH, portal_mod.DEFAULT_BUSCA_XPATH)
    locator_lapis_esperado = (
        portal_mod.By.XPATH,
        portal_mod.DEFAULT_LAPIS_XPATH_TEMPLATE.format(pmib="4500063671.1234"),
    )
    assert wait.chamadas == [
        ("clickable", locator_busca_esperado),
        ("presence", locator_lapis_esperado),
    ]

    # scroll + click no lápis, nesta ordem.
    assert driver.execute_script_chamadas == [
        ("arguments[0].scrollIntoView({block: 'center'});", lapis),
        ("arguments[0].click();", lapis),
    ]


def test_pesquisar_e_abrir_ir_para_lista_false_pula_navegacao():
    engine = _FakeEngine(
        driver=_FakeDriver(current_url="https://outro-lugar"),
        wait=_FakeWait(respostas=[_FakeElemento(), _FakeElemento()]),
    )

    PMIBPortal(engine).pesquisar_e_abrir("123", ir_para_lista=False)

    assert engine.goto_chamadas == []


def test_pesquisar_e_abrir_aceita_overrides_de_busca_e_lapis_upload_conditions():
    # Seletores EXATOS usados por upload_conditions_backend.UploadAutomation.
    busca_upload_conditions = (
        "//input[@placeholder='Código, Nome ES/PT pela Ficha Técnica, "
        "Código do projeto e/ou contrato']"
    )
    lapis_upload_conditions = "//span[text()='{pmib}']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]"

    campo = _FakeElemento()
    lapis = _FakeElemento()
    wait = _FakeWait(respostas=[campo, lapis])
    engine = _FakeEngine(driver=_FakeDriver(current_url=config.PORTAL_URL), wait=wait)

    resultado = PMIBPortal(engine).pesquisar_e_abrir(
        "4500063671.9999",
        busca_xpath=busca_upload_conditions,
        lapis_xpath_template=lapis_upload_conditions,
    )

    assert resultado is True
    assert wait.chamadas[0] == ("clickable", (portal_mod.By.XPATH, busca_upload_conditions))
    assert wait.chamadas[1] == (
        "presence",
        (portal_mod.By.XPATH, "//span[text()='4500063671.9999']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]"),
    )


def test_pesquisar_e_abrir_aceita_overrides_ficha_duplicada():
    # Seletores EXATOS usados por upload_ficha_duplicada (Extrator/Injetor).
    busca_fd = "//input[contains(@id, 'InputDatasheetFilter') or contains(@placeholder, 'Código')]"
    lapis_fd = "//tr[contains(., '{pmib}')]//a[.//i[contains(@class, 'fa-pencil')]]"

    wait = _FakeWait(respostas=[_FakeElemento(), _FakeElemento()])
    engine = _FakeEngine(driver=_FakeDriver(current_url=config.PORTAL_URL), wait=wait)

    PMIBPortal(engine).pesquisar_e_abrir("77", busca_xpath=busca_fd, lapis_xpath_template=lapis_fd)

    assert wait.chamadas[0] == ("clickable", (portal_mod.By.XPATH, busca_fd))
    assert wait.chamadas[1] == ("presence", (portal_mod.By.XPATH, "//tr[contains(., '77')]//a[.//i[contains(@class, 'fa-pencil')]]"))


def test_pesquisar_e_abrir_retenta_apos_stale_element_na_busca_e_depois_sucede():
    campo = _FakeElemento()
    lapis = _FakeElemento()
    wait = _FakeWait(respostas=[StaleElementReferenceExceptionFake(), campo, lapis])
    engine = _FakeEngine(driver=_FakeDriver(current_url=config.PORTAL_URL), wait=wait)

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is True
    assert len(wait.chamadas) == 3  # 1 stale + 1 sucesso na busca + 1 sucesso no lápis


def test_pesquisar_e_abrir_excecao_generica_na_busca_devolve_false_sem_tentar_lapis():
    wait = _FakeWait(respostas=[RuntimeError("falha genérica")])
    engine = _FakeEngine(driver=_FakeDriver(current_url=config.PORTAL_URL), wait=wait)

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is False
    assert len(wait.chamadas) == 1  # nunca tentou o lápis


def test_pesquisar_e_abrir_stale_esgota_3x_na_busca_mas_prossegue_pro_lapis():
    # Quirk preservado do original de tech_specs: 3 StaleElement seguidos na
    # busca NÃO retornam False -- a função segue para a etapa do lápis.
    lapis = _FakeElemento()
    wait = _FakeWait(
        respostas=[
            StaleElementReferenceExceptionFake(),
            StaleElementReferenceExceptionFake(),
            StaleElementReferenceExceptionFake(),
            lapis,
        ]
    )
    engine = _FakeEngine(driver=_FakeDriver(current_url=config.PORTAL_URL), wait=wait)

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is True
    assert len(wait.chamadas) == 4  # 3 tentativas de busca (todas stale) + 1 sucesso no lápis


def test_pesquisar_e_abrir_retenta_apos_timeout_no_lapis_e_depois_sucede():
    campo = _FakeElemento()
    lapis = _FakeElemento()
    wait = _FakeWait(respostas=[campo, TimeoutExceptionFake(), lapis])
    engine = _FakeEngine(driver=_FakeDriver(current_url=config.PORTAL_URL), wait=wait)

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is True


def test_pesquisar_e_abrir_lapis_esgota_3_tentativas_devolve_false():
    campo = _FakeElemento()
    wait = _FakeWait(
        respostas=[
            campo,
            TimeoutExceptionFake(),
            TimeoutExceptionFake(),
            TimeoutExceptionFake(),
        ]
    )
    engine = _FakeEngine(driver=_FakeDriver(current_url=config.PORTAL_URL), wait=wait)

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is False


# ---------------------------------------------------------------------------
# Exceções fake: usamos as classes REAIS de `portal_mod` (StaleElement.../
# TimeoutException) -- que, neste ambiente de teste, são atributos MagicMock
# de um módulo `selenium.common.exceptions` stubado (ver tests/conftest.py) e
# portanto NÃO são subclasses de BaseException de verdade, então não podem
# ser instanciadas/levantadas com `raise`. Para testar os ramos `except
# StaleElementReferenceException`/`except TimeoutException` de
# `pesquisar_e_abrir` sem o pacote selenium real, apontamos os NOMES usados
# por portal.py, dentro deste módulo de teste, para exceções Python de
# verdade equivalentes -- ver fixture `_excecoes_selenium_de_verdade` abaixo.
# ---------------------------------------------------------------------------
class StaleElementReferenceExceptionFake(Exception):
    pass


class TimeoutExceptionFake(Exception):
    pass


@pytest.fixture(autouse=True)
def _excecoes_selenium_de_verdade(monkeypatch):
    monkeypatch.setattr(portal_mod, "StaleElementReferenceException", StaleElementReferenceExceptionFake)
    monkeypatch.setattr(portal_mod, "TimeoutException", TimeoutExceptionFake)

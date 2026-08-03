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
from sigft.core.rpa.engine import ElementoObsoleto, TempoEsgotado
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
    """Duck-typed -- expõe só o que `PMIBPortal` usa.

    CP 5.1: além de `driver`/`wait` (ainda alcançados por `check_or_uncheck`,
    `clicar_salvar_visivel` e `excluir_linha_com_confirmacao`, que a Fase 5
    migra nos CP 5.3/Fase 6), agora registra as PRIMITIVAS de `RPAEngine`
    usadas por `ir_para_lista`/`pesquisar_e_abrir`.

    `passos` guarda a sequência inteira, na ordem, como tuplas
    `(nome_da_primitiva, *argumentos)`. É isso que os testes de
    `pesquisar_e_abrir` passam a verificar -- o CONTRATO do portal ("quais
    primitivas, em que ordem, com que seletor"). A mecânica Selenium de cada
    primitiva (que `wait.until` com que `EC`, que `execute_script`) continua
    verificada, mas no lugar certo: tests/test_selenium_engine.py.

    `falhas` injeta exceção por primitiva: `{"clear": [Erro(), None]}` faz a
    1ª chamada de `clear` levantar e a 2ª passar. Uma lista mais curta que o
    número de chamadas continua com `None` (sucesso).
    """

    def __init__(self, driver=None, wait=None, *, url_atual="", falhas=None):
        self.driver = driver if driver is not None else _FakeDriver()
        self.wait = wait if wait is not None else _FakeWait()
        self.goto_chamadas = []
        self.click_chamadas = []
        self.fill_chamadas = []
        self.passos = []
        self._url_atual = url_atual or getattr(self.driver, "current_url", "")
        self._falhas = {nome: list(seq) for nome, seq in (falhas or {}).items()}

    def _registrar(self, nome, *args):
        self.passos.append((nome, *args))
        fila = self._falhas.get(nome)
        if fila:
            problema = fila.pop(0)
            if problema is not None:
                raise problema

    # -- primitivas usadas por ir_para_lista / pesquisar_e_abrir -----------
    def current_url(self):
        return self._url_atual

    def goto(self, url):
        self.goto_chamadas.append(url)
        self._registrar("goto", url)
        self._url_atual = url
        self.driver.current_url = url

    def clear(self, seletor):
        self._registrar("clear", seletor)

    def type_text(self, seletor, texto):
        self._registrar("type_text", seletor, texto)

    def press(self, teclas):
        self._registrar("press", teclas)

    def wait_present(self, seletor):
        self._registrar("wait_present", seletor)

    def scroll_to(self, seletor):
        self._registrar("scroll_to", seletor)

    def click_raw(self, seletor):
        self._registrar("click_raw", seletor)

    # -- delegação fina (CP 2.2) -------------------------------------------
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
    engine = _FakeEngine(url_atual="https://outro-lugar")
    PMIBPortal(engine).ir_para_lista()
    assert engine.goto_chamadas == [config.PORTAL_URL]
    assert engine.current_url() == config.PORTAL_URL


def test_ir_para_lista_nao_navega_quando_ja_esta_na_url():
    engine = _FakeEngine(url_atual=config.PORTAL_URL)
    PMIBPortal(engine).ir_para_lista()
    assert engine.goto_chamadas == []


def test_ir_para_lista_le_a_url_pelo_engine_e_nao_por_um_driver():
    # CP 5.1: contraprova da migração. Antes, `ir_para_lista` fazia
    # `self.engine.driver.current_url` -- um engine SEM `.driver` (que é o
    # caso do PlaywrightEngine) estouraria aqui. Este engine não tem `driver`
    # nenhum de propósito: se alguém reintroduzir o acesso, este teste falha.
    class _EngineSemDriver:
        def __init__(self):
            self.navegou_para = []

        def current_url(self):
            return "https://outro-lugar"

        def goto(self, url):
            self.navegou_para.append(url)

    engine = _EngineSemDriver()
    PMIBPortal(engine).ir_para_lista()
    assert engine.navegou_para == [config.PORTAL_URL]


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
#
# CP 5.1: estes testes passaram a verificar o CONTRATO do portal -- quais
# primitivas de `RPAEngine` ele chama, em que ordem, com que seletor -- em vez
# da mecânica Selenium interna (`wait.until(EC...)`, `execute_script`). A
# mecânica não deixou de ser testada: ela migrou para
# tests/test_selenium_engine.py, que verifica, primitiva por primitiva, que
# `SeleniumEngine` faz exatamente as mesmas chamadas de antes. A divisão é
# essa mesma que torna a Fase 5 possível: portal descreve a INTENÇÃO, engine
# executa no motor.
# ===========================================================================
def _passos_esperados(pmib, busca_xpath, lapis_xpath):
    """A sequência EXATA que `pesquisar_e_abrir` executa num caminho feliz --
    espelha, passo a passo, o que o corpo Selenium fazia antes do CP 5.1:
    `clear()` / `send_keys(pmib)` / `send_keys(ENTER)` na busca, e
    `presence_of_element_located` + `scrollIntoView` + `click` no lápis."""
    return [
        ("clear", busca_xpath),
        ("type_text", busca_xpath, pmib),
        ("press", "ENTER"),
        ("wait_present", lapis_xpath),
        ("scroll_to", lapis_xpath),
        ("click_raw", lapis_xpath),
    ]


def test_pesquisar_e_abrir_usa_seletores_default_e_ir_para_lista_por_padrao():
    engine = _FakeEngine(url_atual="https://outro-lugar")

    resultado = PMIBPortal(engine).pesquisar_e_abrir("4500063671.1234")

    assert resultado is True
    assert engine.goto_chamadas == [config.PORTAL_URL]  # ir_para_lista chamado

    lapis = portal_mod.DEFAULT_LAPIS_XPATH_TEMPLATE.format(pmib="4500063671.1234")
    assert engine.passos == [
        ("goto", config.PORTAL_URL),
        *_passos_esperados("4500063671.1234", portal_mod.DEFAULT_BUSCA_XPATH, lapis),
    ]


def test_pesquisar_e_abrir_ir_para_lista_false_pula_navegacao():
    engine = _FakeEngine(url_atual="https://outro-lugar")

    PMIBPortal(engine).pesquisar_e_abrir("123", ir_para_lista=False)

    assert engine.goto_chamadas == []
    assert engine.passos[0][0] == "clear"  # começa direto na busca


def test_pesquisar_e_abrir_aceita_overrides_de_busca_e_lapis_upload_conditions():
    # Seletores EXATOS usados por upload_conditions_backend.UploadAutomation.
    busca_upload_conditions = (
        "//input[@placeholder='Código, Nome ES/PT pela Ficha Técnica, "
        "Código do projeto e/ou contrato']"
    )
    lapis_upload_conditions = "//span[text()='{pmib}']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]"

    engine = _FakeEngine(url_atual=config.PORTAL_URL)

    resultado = PMIBPortal(engine).pesquisar_e_abrir(
        "4500063671.9999",
        busca_xpath=busca_upload_conditions,
        lapis_xpath_template=lapis_upload_conditions,
    )

    assert resultado is True
    assert engine.passos == _passos_esperados(
        "4500063671.9999",
        busca_upload_conditions,
        "//span[text()='4500063671.9999']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]",
    )


def test_pesquisar_e_abrir_aceita_overrides_ficha_duplicada():
    # Seletores EXATOS usados por upload_ficha_duplicada (Extrator/Injetor).
    busca_fd = "//input[contains(@id, 'InputDatasheetFilter') or contains(@placeholder, 'Código')]"
    lapis_fd = "//tr[contains(., '{pmib}')]//a[.//i[contains(@class, 'fa-pencil')]]"

    engine = _FakeEngine(url_atual=config.PORTAL_URL)

    PMIBPortal(engine).pesquisar_e_abrir("77", busca_xpath=busca_fd, lapis_xpath_template=lapis_fd)

    assert engine.passos == _passos_esperados(
        "77", busca_fd, "//tr[contains(., '77')]//a[.//i[contains(@class, 'fa-pencil')]]"
    )


def test_pesquisar_e_abrir_retenta_apos_stale_element_na_busca_e_depois_sucede():
    engine = _FakeEngine(
        url_atual=config.PORTAL_URL,
        falhas={"clear": [StaleElementReferenceExceptionFake()]},
    )

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is True
    # 1 tentativa de busca que morreu no `clear` + 1 busca inteira + lápis.
    nomes = [passo[0] for passo in engine.passos]
    assert nomes == ["clear", "clear", "type_text", "press", "wait_present", "scroll_to", "click_raw"]


def test_pesquisar_e_abrir_excecao_generica_na_busca_devolve_false_sem_tentar_lapis():
    engine = _FakeEngine(
        url_atual=config.PORTAL_URL,
        falhas={"clear": [RuntimeError("falha genérica")]},
    )

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is False
    assert engine.passos == [("clear", portal_mod.DEFAULT_BUSCA_XPATH)]  # nunca tentou o lápis


def test_pesquisar_e_abrir_stale_esgota_3x_na_busca_mas_prossegue_pro_lapis():
    # Quirk preservado do original de tech_specs: 3 StaleElement seguidos na
    # busca NÃO retornam False -- a função segue para a etapa do lápis.
    engine = _FakeEngine(
        url_atual=config.PORTAL_URL,
        falhas={
            "clear": [
                StaleElementReferenceExceptionFake(),
                StaleElementReferenceExceptionFake(),
                StaleElementReferenceExceptionFake(),
            ]
        },
    )

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is True
    nomes = [passo[0] for passo in engine.passos]
    assert nomes == ["clear", "clear", "clear", "wait_present", "scroll_to", "click_raw"]


def test_pesquisar_e_abrir_retenta_apos_timeout_no_lapis_e_depois_sucede():
    engine = _FakeEngine(
        url_atual=config.PORTAL_URL,
        falhas={"wait_present": [TimeoutExceptionFake()]},
    )

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is True
    nomes = [passo[0] for passo in engine.passos]
    assert nomes.count("wait_present") == 2


def test_pesquisar_e_abrir_lapis_esgota_3_tentativas_devolve_false():
    engine = _FakeEngine(
        url_atual=config.PORTAL_URL,
        falhas={
            "wait_present": [
                TimeoutExceptionFake(),
                TimeoutExceptionFake(),
                TimeoutExceptionFake(),
            ]
        },
    )

    resultado = PMIBPortal(engine).pesquisar_e_abrir("1")

    assert resultado is False


def test_pesquisar_e_abrir_nao_toca_em_driver_nem_wait():
    # CP 5.1: contraprova estrutural. Este engine implementa SÓ as primitivas
    # neutras -- nada de `.driver`/`.wait`. Se `pesquisar_e_abrir` voltar a
    # alcançar o driver cru, o `AttributeError` derruba este teste (o
    # `except Exception` do laço de busca converteria em `False`, e o assert
    # de `True` pega).
    class _EngineNeutro:
        def __init__(self):
            self.passos = []

        def current_url(self):
            return config.PORTAL_URL

        def __getattr__(self, nome):
            if nome in ("driver", "wait"):
                raise AttributeError(nome)
            def _registrar(*args):
                self.passos.append((nome, *args))
            return _registrar

    engine = _EngineNeutro()

    assert PMIBPortal(engine).pesquisar_e_abrir("9") is True
    assert [p[0] for p in engine.passos] == [
        "clear", "type_text", "press", "wait_present", "scroll_to", "click_raw",
    ]




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
# CP 5.1: as exceções que `pesquisar_e_abrir` discrimina deixaram de ser as do
# SDK do Selenium e passaram a ser as NEUTRAS de `core/rpa/engine.py` -- que
# são exceções Python de verdade, definidas por nós. Com isso o `monkeypatch`
# que existia aqui (apontar os nomes `StaleElementReferenceException`/
# `TimeoutException` de portal.py para fakes, porque os originais viram
# MagicMock neste ambiente) deixou de ser necessário: basta levantar as
# neutras. Esses aliases mantêm os nomes que os testes abaixo já usavam.
StaleElementReferenceExceptionFake = ElementoObsoleto
TimeoutExceptionFake = TempoEsgotado

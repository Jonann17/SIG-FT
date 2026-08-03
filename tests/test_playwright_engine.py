r"""
Testes do Checkpoint 5.1 — `sigft/core/rpa/playwright_engine.py`.

Ver docs/refatoracao/PLANO_REFATORACAO.md, decisão de produto nº 5 e Fase 5 ->
CP 5.1.

Playwright NÃO está instalado neste ambiente (nem precisa estar): o import do
SDK é preguiçoso, feito só dentro de `PlaywrightEngine.criar()`, então o
módulo importa e a classe se instancia com `page`/`context` FAKES. É o mesmo
padrão de tests/test_selenium_engine.py -- fakes duck-typed, nunca MagicMock,
para que cada asserção diga algo sobre a mecânica que é NOSSA (qual método do
locator, em que ordem, com que argumento) e não sobre a integração real do
SDK.

O que estes testes NÃO cobrem, e não têm como cobrir: se o portal PMIB de
verdade responde bem a este motor. Isso é o aceite do CP 5.1 -- "validado
pelo usuário em sessão real" -- e continua pendente por definição. O que
cobrem é o contrato: que `PlaywrightEngine` implementa `RPAEngine` inteira,
que traduz a exceção de timeout para a neutra, e que cada primitiva do CP 5.1
faz no Playwright o equivalente do que a versão Selenium faz.
"""
from __future__ import annotations

import pytest

import sigft.core.rpa.playwright_engine as pe
from sigft.core.rpa.engine import RPAEngine, TempoEsgotado
from sigft.core.rpa.playwright_engine import PlaywrightEngine


# ===========================================================================
# Fakes duck-typed do Playwright
# ===========================================================================
class _PlaywrightTimeoutErrorFalso(Exception):
    """O SDK expõe a classe como `playwright.sync_api.TimeoutError`. Como a
    tradução casa por NOME (para não precisar importar o SDK), um fake com o
    mesmo nome exercita exatamente o caminho real."""


_PlaywrightTimeoutErrorFalso.__name__ = "TimeoutError"


class _FakeLocator:
    def __init__(self, dono, seletor, *, valor="", quantidade=1, habilitado=True, erro=None):
        self.dono = dono
        self.seletor = seletor
        self.valor = valor
        self.quantidade = quantidade
        self.habilitado = habilitado
        self.erro = erro

    @property
    def first(self):
        return self

    def _registrar(self, acao, *args):
        self.dono.acoes.append((acao, self.seletor, *args))
        if self.erro is not None:
            raise self.erro

    def click(self):
        self._registrar("click")

    def scroll_into_view_if_needed(self):
        self._registrar("scroll")

    def fill(self, texto):
        self._registrar("fill", texto)

    def press_sequentially(self, texto):
        self._registrar("type", texto)

    def wait_for(self, state):
        self._registrar("wait_for", state)

    def input_value(self):
        self._registrar("input_value")
        return self.valor

    def count(self):
        self.dono.acoes.append(("count", self.seletor))
        return self.quantidade

    def is_enabled(self):
        return self.habilitado


class _FakeKeyboard:
    def __init__(self, dono):
        self.dono = dono

    def press(self, tecla):
        self.dono.acoes.append(("press", tecla))


class _FakePage:
    def __init__(self, *, url="", valor="", quantidade=1, habilitado=True, erro=None):
        self.url = url
        self.acoes = []
        self.handlers = {}
        self._valor = valor
        self._quantidade = quantidade
        self._habilitado = habilitado
        self._erro = erro
        self.keyboard = _FakeKeyboard(self)

    def locator(self, seletor):
        return _FakeLocator(
            self,
            seletor,
            valor=self._valor,
            quantidade=self._quantidade,
            habilitado=self._habilitado,
            erro=self._erro,
        )

    def goto(self, url):
        self.acoes.append(("goto", url))
        self.url = url

    def screenshot(self, path):
        self.acoes.append(("screenshot", path))

    def on(self, evento, handler):
        self.handlers[evento] = handler


class _FakeContext:
    def __init__(self):
        self.fechado = 0

    def close(self):
        self.fechado += 1


def _engine(**kwargs):
    return PlaywrightEngine(_FakePage(**kwargs))


# ===========================================================================
# Contrato
# ===========================================================================
def test_playwright_engine_implementa_rpaengine_inteira():
    # Se `RPAEngine` ganhar um método abstrato novo e o motor Playwright não
    # o implementar, esta instanciação levanta TypeError -- é o que impede a
    # Fase 5 de descobrir um buraco só na sessão de validação com o usuário.
    assert isinstance(_engine(), RPAEngine)


def test_seletor_xpath_recebe_o_prefixo_do_playwright():
    # Os seletores do projeto são XPath puro; o Playwright só os reconhece
    # como XPath com o prefixo explícito.
    assert pe._sel("//button[@id='x']") == "xpath=//button[@id='x']"
    assert pe._sel("(//a)[1]") == "xpath=(//a)[1]"


def test_seletor_ja_prefixado_nao_e_prefixado_de_novo():
    assert pe._sel("xpath=//a") == "xpath=//a"


# ===========================================================================
# Navegação
# ===========================================================================
def test_goto_navega_e_current_url_le_a_pagina():
    engine = _engine(url="https://inicio")
    assert engine.current_url() == "https://inicio"

    engine.goto("https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList")

    assert engine.page.acoes == [("goto", "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList")]
    assert engine.current_url() == "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"


# ===========================================================================
# Interação
# ===========================================================================
def test_click_estrito_rola_antes_de_clicar():
    engine = _engine()

    engine.click_estrito("//button")

    assert engine.page.acoes == [
        ("scroll", "xpath=//button"),
        ("click", "xpath=//button"),
    ]


def test_click_engole_a_falha_e_click_estrito_propaga():
    # Mesma dupla de contratos da versão Selenium -- é o que permite ao laço
    # de `apagar_lmr` funcionar igual nos dois motores.
    engine_tolerante = _engine(erro=_PlaywrightTimeoutErrorFalso("sumiu"))
    engine_estrito = _engine(erro=_PlaywrightTimeoutErrorFalso("sumiu"))

    engine_tolerante.click("//button")  # não levanta

    with pytest.raises(TempoEsgotado):
        engine_estrito.click_estrito("//button")


def test_click_raw_clica_sem_rolar():
    engine = _engine()

    engine.click_raw("//a")

    assert engine.page.acoes == [("click", "xpath=//a")]


def test_scroll_to_so_rola():
    engine = _engine()

    engine.scroll_to("//a")

    assert engine.page.acoes == [("scroll", "xpath=//a")]


def test_fill_limpa_e_preenche_e_engole_falha():
    engine = _engine()
    engine.fill("//input", "texto")
    assert engine.page.acoes == [("fill", "xpath=//input", "texto")]

    quebrado = _engine(erro=_PlaywrightTimeoutErrorFalso("x"))
    quebrado.fill("//input", "texto")  # não levanta


def test_clear_esvazia_o_campo():
    engine = _engine()

    engine.clear("//input")

    assert engine.page.acoes == [("fill", "xpath=//input", "")]


def test_type_text_digita_tecla_a_tecla_sem_limpar_e_sem_clicar():
    # `press_sequentially` (e não `fill`) porque os campos OutSystems do PMIB
    # reagem aos eventos de teclado -- é o equivalente do `send_keys`. E SEM
    # `click()` antes: `press_sequentially` já foca sozinho, e um clique extra
    # que o motor Selenium não dá poderia abrir dropdown no portal.
    engine = _engine()

    engine.type_text("//input", "4500063671.1234")

    assert engine.page.acoes == [("type", "xpath=//input", "4500063671.1234")]


def test_type_text_converte_valor_nao_string():
    engine = _engine()

    engine.type_text("//input", 4500063671)

    assert engine.page.acoes[-1] == ("type", "xpath=//input", "4500063671")


# ===========================================================================
# Teclas
# ===========================================================================
def test_press_traduz_nomes_do_selenium_para_o_playwright():
    engine = _engine()

    engine.press("ENTER")
    engine.press(["TAB", "TAB", "ENTER"])

    assert engine.page.acoes == [
        ("press", "Enter"),
        ("press", "Tab"),
        ("press", "Tab"),
        ("press", "Enter"),
    ]


def test_press_repassa_nome_desconhecido_sem_traduzir():
    engine = _engine()

    engine.press("F5")

    assert engine.page.acoes == [("press", "F5")]


def test_todas_as_teclas_usadas_pelos_servicos_tem_traducao():
    # Levantamento por grep de `Keys.` no repositório na época do CP 5.1.
    for tecla in ("ENTER", "TAB", "BACKSPACE"):
        assert tecla in pe._TECLAS


# ===========================================================================
# Espera
# ===========================================================================
def test_wait_visible_e_wait_present_usam_estados_diferentes():
    engine = _engine()

    engine.wait_visible("//div")
    engine.wait_present("//div")

    assert engine.page.acoes == [
        ("wait_for", "xpath=//div", "visible"),
        ("wait_for", "xpath=//div", "attached"),
    ]


def test_wait_clickable_exige_visivel_e_habilitado():
    engine = _engine(habilitado=True)

    engine.wait_clickable("//button")

    assert engine.page.acoes == [("wait_for", "xpath=//button", "visible")]


def test_wait_clickable_estoura_quando_o_elemento_nunca_habilita():
    # Sem esta metade, um botão visível-porém-desabilitado passaria por
    # clicável -- e o laço de `apagar_lmr`, que usa o estouro do tempo como
    # sinal de "acabou", encerraria o lote cedo demais.
    engine = PlaywrightEngine(_FakePage(habilitado=False), timeout_ms=50)

    with pytest.raises(TempoEsgotado):
        engine.wait_clickable("//button")


def test_wait_traduz_timeout_do_playwright_para_a_neutra():
    engine = _engine(erro=_PlaywrightTimeoutErrorFalso("nunca apareceu"))

    with pytest.raises(TempoEsgotado) as capturado:
        engine.wait_present("//div")

    assert isinstance(capturado.value.__cause__, _PlaywrightTimeoutErrorFalso)


def test_excecao_generica_nao_e_traduzida():
    engine = _engine(erro=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        engine.wait_present("//div")


# ===========================================================================
# Leitura
# ===========================================================================
def test_element_exists_usa_count_e_nao_espera():
    assert _engine(quantidade=2).element_exists("//tr") is True
    assert _engine(quantidade=0).element_exists("//tr") is False


def test_get_value_le_input_value():
    engine = _engine(valor="Bomba centrífuga")

    assert engine.get_value("//input") == "Bomba centrífuga"


# ===========================================================================
# Diagnóstico / configuração
# ===========================================================================
def test_screenshot_salva_no_caminho_pedido():
    engine = _engine()

    engine.screenshot("/tmp/erro.png")

    assert engine.page.acoes == [("screenshot", "/tmp/erro.png")]


def test_set_download_dir_registra_um_handler_so_e_troca_a_pasta(tmp_path):
    engine = _engine()
    primeira = tmp_path / "a"
    segunda = tmp_path / "b"

    engine.set_download_dir(str(primeira))
    engine.set_download_dir(str(segunda))

    # Um handler só -- registrar de novo duplicaria o salvamento.
    assert list(engine.page.handlers) == ["download"]
    assert engine._download_dir == str(segunda)
    assert primeira.is_dir() and segunda.is_dir()


def test_handler_de_download_salva_na_pasta_atual(tmp_path):
    engine = _engine()
    engine.set_download_dir(str(tmp_path))
    salvos = []

    class _FakeDownload:
        suggested_filename = "ficha.xlsx"

        def save_as(self, caminho):
            salvos.append(caminho)

    engine.page.handlers["download"](_FakeDownload())

    assert salvos == [str(tmp_path / "ficha.xlsx")]


def test_falha_ao_salvar_download_nao_derruba_a_automacao(tmp_path):
    engine = _engine()
    engine.set_download_dir(str(tmp_path))

    class _DownloadQuebrado:
        suggested_filename = "x.xlsx"

        def save_as(self, caminho):
            raise OSError("disco cheio")

    engine.page.handlers["download"](_DownloadQuebrado())  # não levanta


# ===========================================================================
# Encerramento
# ===========================================================================
def test_fechar_encerra_contexto_e_playwright_e_e_idempotente():
    paradas = []
    contexto = _FakeContext()

    class _FakePlaywright:
        def stop(self):
            paradas.append(1)

    engine = PlaywrightEngine(_FakePage(), context=contexto, playwright=_FakePlaywright())

    engine.fechar()
    engine.fechar()  # contrato de engine.py: idempotente

    assert contexto.fechado == 1
    assert paradas == [1]


def test_fechar_engole_falha_de_cada_etapa():
    class _ContextoQuebrado:
        def close(self):
            raise RuntimeError("browser já morreu")

    class _PlaywrightQuebrado:
        def stop(self):
            raise RuntimeError("nó já morreu")

    engine = PlaywrightEngine(
        _FakePage(), context=_ContextoQuebrado(), playwright=_PlaywrightQuebrado()
    )

    engine.fechar()  # não levanta


# ===========================================================================
# Perfil persistente
# ===========================================================================
def test_perfil_padrao_fica_fora_do_repositorio(monkeypatch):
    # O perfil guarda cookies de sessão do portal -- mesmo motivo pelo qual
    # `api_config.json`/`user_prefs.json` não são versionados.
    monkeypatch.setattr(pe.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\fulano\AppData\Local")

    caminho = pe.perfil_padrao()

    assert caminho.endswith("perfil-navegador")
    assert "SIG-FT" in caminho
    assert caminho.startswith(r"C:\Users\fulano\AppData\Local")


def test_perfil_padrao_tem_fallback_fora_do_windows(monkeypatch):
    monkeypatch.setattr(pe.sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    caminho = pe.perfil_padrao()

    assert caminho.endswith("perfil-navegador")
    assert "SIG-FT" in caminho


def test_criar_para_o_playwright_quando_o_browser_nao_sobe(monkeypatch):
    # Sem isso, uma falha ao subir o Chromium (não instalado, perfil travado
    # por outra instância) deixaria o processo-nó do Playwright rodando órfão.
    paradas = []

    class _Chromium:
        def launch_persistent_context(self, *a, **k):
            raise RuntimeError("Executable doesn't exist")

    class _Playwright:
        chromium = _Chromium()

        def stop(self):
            paradas.append(1)

    class _SyncPlaywright:
        def start(self):
            return _Playwright()

    modulo_falso = type("_m", (), {"sync_playwright": lambda: _SyncPlaywright()})
    monkeypatch.setitem(__import__("sys").modules, "playwright", type("_p", (), {})())
    monkeypatch.setitem(__import__("sys").modules, "playwright.sync_api", modulo_falso)

    with pytest.raises(RuntimeError):
        PlaywrightEngine.criar()

    assert paradas == [1]

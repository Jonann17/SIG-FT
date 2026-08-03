r"""
Testes do Checkpoint 5.1 — o piloto (`apagar_lmr`) rodando de ponta a ponta
sobre CADA UM dos dois motores.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 5 -> CP 5.1: "Piloto:
`apagar_lmr` (menor risco, fluxo simples e reversível de testar). *Aceite*:
`apagar_lmr` roda em Playwright de ponta a ponta, validado pelo usuário em
sessão real; rollback por config demonstrado."

O aceite do checkpoint é a sessão real com o usuário -- isso não tem
substituto offline e continua pendente. O que ESTE arquivo faz é a parte que
dá para fazer sem portal: exercitar o serviço inteiro (`executar_limpeza`,
com seu laço de exclusão) através das classes de motor DE VERDADE
(`SeleniumEngine` e `PlaywrightEngine`, sem mock nenhum no meio), trocando
apenas o browser por um duplo. Assim, se a migração tiver quebrado alguma
peça da cadeia serviço -> portal -> engine, isso aparece aqui, e não só na
frente do usuário.

O ponto que mais importa é o do MOTOR NOVO. O laço de exclusão decide quando
parar pelo TIPO da exceção que a espera levanta:

    except TempoEsgotado:   # não há mais lixeiras -> lote encerrado

Antes do CP 5.1 esse `except` era da exceção do Selenium. Um
`playwright.sync_api.TimeoutError` não é parente dela: no motor novo o laço
NUNCA veria o sinal de fim e giraria para sempre, apagando nada e sem
resposta. `test_o_laco_termina_no_motor_playwright` é a prova de que a
tradução para as exceções neutras fecha esse buraco -- ele tem timeout
próprio justamente porque a falha que ele vigia é um travamento, não um
assert quebrado.
"""
from __future__ import annotations

import threading

import pytest

from sigft.core.callbacks import UICallbacks
from sigft.core.rpa.playwright_engine import PlaywrightEngine
from sigft.core.rpa.selenium_engine import SeleniumEngine
from sigft.services import apagar_lmr


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    monkeypatch.setattr(apagar_lmr.time, "sleep", lambda *_a, **_kw: None)


# ===========================================================================
# Duplo de browser -- lado Playwright
# ===========================================================================
class _PlaywrightTimeoutErrorFalso(Exception):
    """Mesmo NOME da classe real do SDK: é por nome que `PlaywrightEngine`
    traduz (para não precisar importar o SDK). Um fake com outro nome
    passaria batido pela tradução -- e o teste deixaria de exercitar o
    caminho real."""


_PlaywrightTimeoutErrorFalso.__name__ = "TimeoutError"


class _LocatorPW:
    def __init__(self, pagina, seletor):
        self.pagina = pagina
        self.seletor = seletor

    @property
    def first(self):
        return self

    def wait_for(self, state):
        self.pagina.registrar_espera(self.seletor)

    def is_enabled(self):
        return True

    def click(self):
        self.pagina.registrar_clique(self.seletor)

    def scroll_into_view_if_needed(self):
        pass


class _PaginaPW:
    """Simula uma ficha com `lmrs` aplicações: cada rodada do laço espera a
    lixeira, clica, espera o CONFIRMAR e clica. Quando as aplicações acabam,
    a espera da lixeira estoura -- exatamente o que o portal real faz."""

    def __init__(self, lmrs):
        self.restantes = lmrs
        self.url = ""
        self.cliques = []

    def locator(self, seletor):
        return _LocatorPW(self, seletor)

    def registrar_espera(self, seletor):
        if "fa-trash" in seletor and self.restantes <= 0:
            raise _PlaywrightTimeoutErrorFalso("nenhuma lixeira na tela")

    def registrar_clique(self, seletor):
        self.cliques.append(seletor)
        if "CONFIRMAR" in seletor:
            self.restantes -= 1

    def goto(self, url):
        self.url = url

    def on(self, evento, handler):
        pass


# ===========================================================================
# Duplo de browser -- lado Selenium
# ===========================================================================
class _TimeoutExceptionFalsa(Exception):
    pass


_TimeoutExceptionFalsa.__name__ = "TimeoutException"


class _ElementoSel:
    pass


class _WaitSel:
    """`until(condicao)` recebe o LOCATOR em vez do MagicMock opaco do `EC`
    graças à fixture `_ec_transparente` abaixo -- mesma técnica de
    tests/test_portal.py. Com o seletor à vista, o duplo consegue distinguir
    "esperando a lixeira" de "esperando o CONFIRMAR", que é o que o portal
    real distingue na tela."""

    def __init__(self, driver):
        self.driver = driver

    def until(self, condicao):
        _, (_by, seletor) = condicao
        self.driver.ultimo_seletor = seletor
        if "fa-trash" in seletor and self.driver.restantes <= 0:
            raise _TimeoutExceptionFalsa("nenhuma lixeira na tela")
        return _ElementoSel()


class _DriverSel:
    def __init__(self, lmrs):
        self.restantes = lmrs
        self.current_url = ""
        self.ultimo_seletor = ""
        self.cliques = []

    def find_elements(self, by, seletor):
        return []

    def execute_script(self, script, elemento):
        if "click" in script:
            self.cliques.append(self.ultimo_seletor)
            if "CONFIRMAR" in self.ultimo_seletor:
                self.restantes -= 1

    def quit(self):
        pass

    def get(self, url):
        self.current_url = url


@pytest.fixture(autouse=True)
def _ec_transparente(monkeypatch):
    """`EC` é MagicMock neste ambiente (tests/conftest.py). Trocando as duas
    condições usadas pelo engine por wrappers que devolvem o próprio locator,
    o `_WaitSel` acima consegue ler o XPath pedido."""
    import sigft.core.rpa.selenium_engine as se

    monkeypatch.setattr(se.EC, "element_to_be_clickable", lambda loc: ("clickable", loc))
    monkeypatch.setattr(se.EC, "presence_of_element_located", lambda loc: ("presence", loc))


def _automacao_selenium(lmrs):
    driver = _DriverSel(lmrs)
    auto = apagar_lmr.ApagarLMRAutomation()
    auto.engine = SeleniumEngine(driver, _WaitSel(driver))
    auto.portal = apagar_lmr.PMIBPortal(auto.engine)
    return auto


def _papeis(cliques):
    """Classifica cada clique do laço. O 1º é sempre a aba "Aplicação - LMR"
    (passo 2 de `executar_limpeza`, antes do lote começar); depois vem o par
    lixeira/CONFIRMAR de cada aplicação."""
    papeis = []
    for clique in cliques:
        if "ApplicationMRL" in clique:
            papeis.append("aba")
        elif "fa-trash" in clique:
            papeis.append("lixeira")
        elif "CONFIRMAR" in clique:
            papeis.append("confirmar")
        else:
            papeis.append(f"?{clique}")
    return papeis


# ===========================================================================
# Testes
# ===========================================================================
def _rodar(auto, pmib="4500063671.1234"):
    logs = []
    callbacks = UICallbacks(log=lambda msg, nivel="info", contexto=None: logs.append(str(msg)))
    auto.portal.pesquisar_e_abrir = lambda *a, **k: True  # o foco aqui é o laço
    auto.executar_limpeza(pmib, callbacks=callbacks)
    return "\n".join(logs)


def _automacao_playwright(lmrs):
    auto = apagar_lmr.ApagarLMRAutomation()
    auto.engine = PlaywrightEngine(_PaginaPW(lmrs))
    auto.portal = apagar_lmr.PMIBPortal(auto.engine)
    return auto


def test_o_laco_termina_no_motor_playwright():
    # TRAVA DE SEGURANÇA: a falha que este teste vigia é um laço infinito.
    # Sem o timeout, uma regressão aqui pendura a suíte inteira em vez de
    # reportar -- foi exatamente o que aconteceu no CP 4.2 com um sentinela
    # que herdava de Exception e era engolido pelo `except` sob teste.
    resultado = {}

    def _alvo():
        try:
            resultado["texto"] = _rodar(_automacao_playwright(lmrs=3))
        except BaseException as erro:  # noqa: BLE001
            resultado["erro"] = erro

    thread = threading.Thread(target=_alvo, daemon=True)
    thread.start()
    thread.join(timeout=10)

    assert not thread.is_alive(), (
        "o laço de exclusão não terminou no motor Playwright -- sinal de que o "
        "TimeoutError do SDK deixou de ser traduzido para TempoEsgotado"
    )
    assert "erro" not in resultado, resultado.get("erro")
    texto = resultado["texto"]
    assert "✅ Aplicação 3" in texto
    assert "3 sucesso(s)" in texto
    assert "Todas as aplicações visíveis foram apagadas" in texto


def test_playwright_clica_na_lixeira_e_no_confirmar_de_cada_aplicacao():
    auto = _automacao_playwright(lmrs=2)

    _rodar(auto)

    # Alterna lixeira/confirmar, sempre nessa ordem -- nunca duas lixeiras
    # seguidas sem um CONFIRMAR no meio (seria uma exclusão sem confirmação).
    assert _papeis(auto.engine.page.cliques) == [
        "aba", "lixeira", "confirmar", "lixeira", "confirmar",
    ]


def test_playwright_ficha_sem_nenhuma_lmr_encerra_com_resumo_zerado():
    texto = _rodar(_automacao_playwright(lmrs=0))

    assert "Todas as aplicações visíveis foram apagadas" in texto
    assert "0 sucesso(s)" in texto


def test_playwright_volta_para_a_lista_no_fim():
    auto = _automacao_playwright(lmrs=1)

    _rodar(auto)

    assert auto.engine.page.url == auto.url_inicial


def test_o_laco_termina_no_motor_selenium():
    # O motor antigo continua funcionando pelo mesmo caminho novo -- é isso
    # que sustenta o rollback por config exigido pelo CP 5.1.
    auto = _automacao_selenium(lmrs=2)

    resultado = {}
    thread = threading.Thread(
        target=lambda: resultado.setdefault("texto", _rodar(auto)), daemon=True
    )
    thread.start()
    thread.join(timeout=10)

    assert not thread.is_alive(), "o laço de exclusão não terminou no motor Selenium"
    assert "2 sucesso(s)" in resultado["texto"]
    assert _papeis(auto.engine.driver.cliques) == [
        "aba", "lixeira", "confirmar", "lixeira", "confirmar",
    ]


def test_os_dois_motores_produzem_o_mesmo_resumo():
    # A promessa central da Fase 5: trocar o motor não muda o que o usuário vê.
    texto_sel = _rodar(_automacao_selenium(lmrs=2))
    texto_pw = _rodar(_automacao_playwright(lmrs=2))

    def _linhas_de_lote(texto):
        # Fora as durações (que variam entre execuções), o relato tem de ser
        # o mesmo caractere a caractere.
        import re

        return [
            re.sub(r"\(\d+[,.]\d+s\)", "(Xs)", linha)
            for linha in texto.split("\n")
            if "Aplicação" in linha or "sucesso(s)" in linha
        ]

    assert _linhas_de_lote(texto_sel) == _linhas_de_lote(texto_pw)

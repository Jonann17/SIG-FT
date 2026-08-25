r"""
Testes do Checkpoint 5.2 — `sigft/services/lmr.py` rodando sobre CADA UM dos
dois motores.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 5 -> CP 5.2: "Migrar
leitura/edição simples: `lmr` e `cria_fichas` (edição em massa). *Aceite*:
validação assistida pelo usuário; flag de engine por módulo atualizada."

Mesma estrutura de tests/test_apagar_lmr_nos_dois_motores.py (CP 5.1): o
serviço roda através das classes de motor DE VERDADE, só o browser é duplo.
O aceite -- a sessão com o usuário no portal real -- continua pendente por
definição; o que dá para provar offline é que a cadeia serviço -> engine está
inteira nos dois motores e que os dois produzem a mesma sequência de ações.

O fluxo coberto é o de `_processar_ficha_lmr_interna`, que é onde vive toda a
interação de formulário do módulo: para cada código PMIB, preencher código +
quantidade, e para cada TAG do grupo preencher a TAG e disparar TAB/ENTER,
terminando em salvar + confirmar.

O `DataFrame` falso é o mesmo de tests/test_lmr_indice_except.py -- só o que
o serviço realmente usa (`.empty`, `.shape`, `len()`, `.loc`, `.iloc`).

⚠️ CP 5.5 (2026-08-25): a metade Selenium saiu daqui junto com o motor. O que
fica vale pelo motivo original -- é o único lugar que exercita a cadeia
serviço -> portal -> motor com as classes DE VERDADE, trocando só o browser.
"""
from __future__ import annotations

import pytest

import sigft.services.lmr as lmr_mod
from sigft import config
from sigft.core.callbacks import UICallbacks
from sigft.core.rpa.playwright_engine import PlaywrightEngine
from sigft.services.lmr import LMRAutomation


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    monkeypatch.setattr(lmr_mod.time, "sleep", lambda *_a, **_kw: None)


# ===========================================================================
# DataFrame falso (idêntico ao de tests/test_lmr_indice_except.py)
# ===========================================================================
class _Linha(dict):
    pass


class _Loc:
    def __init__(self, linhas):
        self._linhas = linhas

    def __getitem__(self, chave):
        if isinstance(chave, tuple):
            indice, coluna = chave
            return self._linhas[indice][coluna]
        return _Linha(self._linhas[chave])


class _ILoc:
    def __init__(self, linhas):
        self._linhas = linhas

    def __getitem__(self, indice):
        return _Linha(self._linhas[indice])


class _FakeDF:
    def __init__(self, linhas):
        self._linhas = linhas
        self.empty = not linhas
        self.shape = (len(linhas), 3)
        self.loc = _Loc(linhas)
        self.iloc = _ILoc(linhas)

    def __len__(self):
        return len(self._linhas)


def _df(*pares):
    """`_df(("COD-1", "TAG-A"), ("COD-1", "TAG-B"), ("COD-2", "TAG-C"))` ->
    duas TAGs no primeiro código, uma no segundo."""
    return _FakeDF(
        [
            {"PMIB": "4500063671.0001", "Código_PMIB": codigo, "TAG_PMIB": tag}
            for codigo, tag in pares
        ]
    )


# ===========================================================================
# Duplos de browser
# ===========================================================================
class _LocatorPW:
    def __init__(self, pagina, seletor):
        self.pagina = pagina
        self.seletor = seletor

    @property
    def first(self):
        return self

    def fill(self, texto):
        self.pagina.registrar("fill" if texto else "clear", self.seletor, texto)

    def press_sequentially(self, texto):
        self.pagina.registrar("type", self.seletor, texto)

    def click(self):
        self.pagina.registrar("click", self.seletor)

    def scroll_into_view_if_needed(self):
        pass

    def wait_for(self, state):
        pass

    def is_enabled(self):
        return True


class _KeyboardPW:
    def __init__(self, pagina):
        self.pagina = pagina

    def press(self, tecla):
        self.pagina.registrar("press", tecla)


class _PaginaPW:
    def __init__(self):
        self.acoes = []
        self.url = ""
        self.keyboard = _KeyboardPW(self)

    def locator(self, seletor):
        return _LocatorPW(self, seletor.replace("xpath=", ""))

    def registrar(self, *args):
        self.acoes.append(args)

    def goto(self, url):
        self.url = url

    def on(self, evento, handler):
        pass


def _automacao_playwright():
    auto = LMRAutomation.__new__(LMRAutomation)
    auto.engine = PlaywrightEngine(_PaginaPW())
    auto.portal = None
    auto.url_inicial = config.PORTAL_URL
    return auto


def _acoes(auto):
    alvo = getattr(auto.engine, "page", None) or auto.engine.driver
    return alvo.acoes


def _rodar(auto, df):
    logs = []
    callbacks = UICallbacks(log=lambda msg, nivel="info", contexto=None: logs.append(str(msg)))
    erros = auto._processar_ficha_lmr_interna(df, callbacks)
    return erros, "\n".join(logs)


# ===========================================================================
# Testes
# ===========================================================================
# CP 5.5: a parametrização tinha os DOIS motores -- era ela que provava
# paridade. Ficou com um só quando o Selenium saiu do projeto; a forma
# parametrizada fica porque é o encaixe do dia em que houver outro motor.
@pytest.mark.parametrize("montar", [_automacao_playwright], ids=["playwright"])
def test_preenche_codigo_quantidade_e_cada_tag(montar):
    auto = montar()

    erros, texto = _rodar(auto, _df(("COD-1", "TAG-A"), ("COD-1", "TAG-B")))

    assert erros == []
    assert "Processando Cód COD-1 com 2 TAG(s)" in texto
    assert "inserido ✔️" in texto

    acoes = _acoes(auto)
    digitados = [(sel, txt) for tipo, sel, txt in
                 [a for a in acoes if a[0] == "type"]]
    assert digitados == [
        (lmr_mod.XPATH_CAMPO_CODIGO, "COD-1"),
        (lmr_mod.XPATH_CAMPO_QUANTIDADE, "2"),  # quantidade = nº de TAGs
        (lmr_mod.XPATH_CAMPO_TAG, "TAG-A"),
        (lmr_mod.XPATH_CAMPO_TAG, "TAG-B"),
    ]


# CP 5.5: a parametrização tinha os DOIS motores -- era ela que provava
# paridade. Ficou com um só quando o Selenium saiu do projeto; a forma
# parametrizada fica porque é o encaixe do dia em que houver outro motor.
@pytest.mark.parametrize("montar", [_automacao_playwright], ids=["playwright"])
def test_cada_tag_dispara_tab_e_depois_enter(montar):
    # O par TAB/ENTER era um `ActionChains(...).send_keys(TAB).pause(0.5).
    # send_keys(ENTER)`: o autocomplete do OutSystems precisa dos dois, nessa
    # ordem, para aceitar a TAG. Se a migração tivesse trocado por um
    # `press(["TAB", "ENTER"])` sem pausa, ou invertido a ordem, este teste
    # pega.
    auto = montar()

    _rodar(auto, _df(("COD-1", "TAG-A"), ("COD-1", "TAG-B")))

    # Cada motor escreve o nome da tecla no seu formato ("TAB" no Selenium,
    # "Tab" no Playwright) -- é a MESMA tecla, e a tradução tem teste próprio
    # em tests/test_playwright_engine.py. Aqui interessa a sequência.
    teclas = [a[1].upper() for a in _acoes(auto) if a[0] == "press"]
    assert teclas == ["TAB", "ENTER", "TAB", "ENTER"]


# CP 5.5: a parametrização tinha os DOIS motores -- era ela que provava
# paridade. Ficou com um só quando o Selenium saiu do projeto; a forma
# parametrizada fica porque é o encaixe do dia em que houver outro motor.
@pytest.mark.parametrize("montar", [_automacao_playwright], ids=["playwright"])
def test_limpa_cada_campo_antes_de_digitar(montar):
    # `clear()` + `send_keys()` -- sem a limpeza, o valor da TAG anterior fica
    # no campo e a próxima TAG é digitada colada nela.
    auto = montar()

    _rodar(auto, _df(("COD-1", "TAG-A")))

    pares = [(a[0], a[1]) for a in _acoes(auto) if a[0] in ("clear", "type")]
    assert pares == [
        ("clear", lmr_mod.XPATH_CAMPO_CODIGO),
        ("type", lmr_mod.XPATH_CAMPO_CODIGO),
        ("clear", lmr_mod.XPATH_CAMPO_QUANTIDADE),
        ("type", lmr_mod.XPATH_CAMPO_QUANTIDADE),
        ("clear", lmr_mod.XPATH_CAMPO_TAG),
        ("type", lmr_mod.XPATH_CAMPO_TAG),
    ]


# CP 5.5: a parametrização tinha os DOIS motores -- era ela que provava
# paridade. Ficou com um só quando o Selenium saiu do projeto; a forma
# parametrizada fica porque é o encaixe do dia em que houver outro motor.
@pytest.mark.parametrize("montar", [_automacao_playwright], ids=["playwright"])
def test_salva_e_confirma_no_fim_de_cada_codigo(montar):
    auto = montar()

    _rodar(auto, _df(("COD-1", "TAG-A"), ("COD-2", "TAG-B")))

    cliques = [a[1] for a in _acoes(auto) if a[0] == "click"]
    assert cliques == [
        lmr_mod.XPATH_BOTAO_SALVAR,
        lmr_mod.XPATH_BOTAO_CONFIRMAR,
        lmr_mod.XPATH_BOTAO_SALVAR,
        lmr_mod.XPATH_BOTAO_CONFIRMAR,
    ]


# CP 5.5: a parametrização tinha os DOIS motores -- era ela que provava
# paridade. Ficou com um só quando o Selenium saiu do projeto; a forma
# parametrizada fica porque é o encaixe do dia em que houver outro motor.
@pytest.mark.parametrize("montar", [_automacao_playwright], ids=["playwright"])
def test_agrupa_tags_consecutivas_do_mesmo_codigo(montar):
    auto = montar()

    _rodar(auto, _df(("COD-1", "TAG-A"), ("COD-1", "TAG-B"), ("COD-2", "TAG-C")))

    quantidades = [
        txt for tipo, sel, txt in [a for a in _acoes(auto) if a[0] == "type"]
        if sel == lmr_mod.XPATH_CAMPO_QUANTIDADE
    ]
    assert quantidades == ["2", "1"]



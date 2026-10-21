"""O console embaixo das telas muda de tamanho arrastando a barrinha (2026-10-21).

Pedido do Luan: em toda tela com o console embaixo, a pessoa arrasta a barrinha
entre a tela e o console para aumentá-lo ou diminuí-lo. Cada tela lembra o
tamanho (`prefs`, chave `console.<classe>`); o duplo clique volta ao padrão e
esquece o guardado. Nenhum dos lados some, e sem arrastar NADA muda de lugar
(os testes de medida das telas seguem como estavam).
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from sigft.app import theme
from sigft.app_qt.widgets import puxador_console as puxador_mod
from sigft.app_qt.widgets.module_frame import ModuleFrame


class Tela(ModuleFrame):
    def _build_ui(self):
        self.content_layout.addStretch()


class OutraTela(ModuleFrame):
    def _build_ui(self):
        self.content_layout.addStretch()


@pytest.fixture
def prefs_do_teste(monkeypatch, tmp_path):
    """As preferências num arquivo do teste, lidas como o app lê."""
    arquivo = tmp_path / "user_prefs.json"
    monkeypatch.setattr(puxador_mod, "_arquivo_de_prefs", lambda: str(arquivo))
    monkeypatch.setattr(puxador_mod, "MS_PARA_GRAVAR", 10)
    return arquivo


def _guardado(chave):
    from sigft.core import prefs
    return prefs.ler_preferencia(chave, "", config_path=puxador_mod._arquivo_de_prefs())


def _aberta(qtbot, classe=Tela, tamanho=(1003, 750), **kw):
    t = classe(titulo="x", **kw)
    qtbot.addWidget(t)
    t.resize(*tamanho)
    t.show()
    qtbot.waitExposed(t)
    QApplication.processEvents()
    return t


def _mouse(alvo, tipo, local, botoes):
    ev = QMouseEvent(tipo, QPointF(local), QPointF(alvo.mapToGlobal(local)),
                     Qt.MouseButton.LeftButton, botoes, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(alvo, ev)


def arrastar(puxador, dy: int) -> None:
    """Aperta no meio da barrinha, move `dy` px (negativo = para cima) e solta."""
    meio = puxador.rect().center()
    _mouse(puxador, QEvent.Type.MouseButtonPress, meio, Qt.MouseButton.LeftButton)
    _mouse(puxador, QEvent.Type.MouseMove, meio + QPoint(0, dy), Qt.MouseButton.LeftButton)
    _mouse(puxador, QEvent.Type.MouseButtonRelease, meio + QPoint(0, dy), Qt.MouseButton.NoButton)
    QApplication.processEvents()
    QApplication.processEvents()


def _topo(w, tela):
    return w.mapTo(tela, QPoint(0, 0)).y()


# --- a barrinha ---------------------------------------------------------------------

def test_a_barrinha_fica_entre_a_tela_e_o_console(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    p = t.puxador_console
    assert p is not None and p.isVisible()
    assert p.objectName() == "puxador_console"
    assert p.cursor().shape() == Qt.CursorShape.SplitVCursor
    assert p.toolTip() == ("Arraste para mudar o tamanho do console. "
                           "Duplo clique volta ao tamanho padrão.")
    assert p.height() <= 8                                 # fininha
    topo_console = _topo(t.console, t)
    fim_conteudo = _topo(t.content, t) + t.content.height()
    assert fim_conteudo <= _topo(p, t) and _topo(p, t) + p.height() <= topo_console
    assert p.width() == t.console.width()


def test_sem_arrastar_nada_muda_de_lugar(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    assert t.console.height() == theme.ALTURA_CONSOLE
    assert t.altura_console_escolhida is None


def test_tela_embutida_nao_tem_barrinha(qt_interface, qtbot, prefs_do_teste):
    pai = _aberta(qtbot)
    filha = Tela(titulo="filha", embutida=True, console_externo=pai.console)
    qtbot.addWidget(filha)
    assert filha.puxador_console is None


# --- arrastar -----------------------------------------------------------------------

def test_arrastar_para_cima_aumenta_o_console_e_guarda(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    conteudo_antes = t.content.height()
    arrastar(t.puxador_console, -80)
    assert t.console.height() == theme.ALTURA_CONSOLE + 80
    assert t.content.height() == conteudo_antes - 80
    # a barrinha acompanha o console
    assert _topo(t.puxador_console, t) + t.puxador_console.height() <= _topo(t.console, t)
    qtbot.waitUntil(lambda: _guardado("console.Tela") == str(theme.ALTURA_CONSOLE + 80),
                    timeout=2000)


def test_arrastar_para_baixo_diminui_mas_nao_some(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    arrastar(t.puxador_console, 2000)
    minimo = puxador_mod.altura_minima_do_console(t.console)
    assert t.console.height() == minimo
    # a barra do filtro e duas linhas ainda cabem
    linha = t.console.fontMetrics().lineSpacing()
    assert minimo >= t.console.barra.height() + 2 * linha


def test_arrastar_para_cima_demais_deixa_a_tela_com_o_minimo(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    arrastar(t.puxador_console, -2000)
    assert t.content.height() >= puxador_mod.MIN_CONTEUDO
    assert t.console.height() > theme.ALTURA_CONSOLE


def test_cada_tela_lembra_o_seu_tamanho(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    arrastar(t.puxador_console, -60)
    qtbot.waitUntil(lambda: _guardado("console.Tela") != "", timeout=2000)
    de_novo = _aberta(qtbot)
    assert de_novo.console.height() == theme.ALTURA_CONSOLE + 60
    outra = _aberta(qtbot, OutraTela)
    assert outra.console.height() == theme.ALTURA_CONSOLE


def test_esconder_a_tela_grava_na_hora(qt_interface, qtbot, prefs_do_teste, monkeypatch):
    monkeypatch.setattr(puxador_mod, "MS_PARA_GRAVAR", 60_000)
    t = _aberta(qtbot)
    arrastar(t.puxador_console, -30)
    assert _guardado("console.Tela") == ""
    t.hide()
    assert _guardado("console.Tela") == str(theme.ALTURA_CONSOLE + 30)


def test_duplo_clique_volta_ao_padrao_e_esquece(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    arrastar(t.puxador_console, -70)
    qtbot.waitUntil(lambda: _guardado("console.Tela") != "", timeout=2000)
    QTest.mouseDClick(t.puxador_console, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert t.console.height() == theme.ALTURA_CONSOLE
    assert t.altura_console_escolhida is None
    assert _guardado("console.Tela") == ""


def test_tamanho_guardado_estragado_vale_o_padrao(qt_interface, qtbot, prefs_do_teste):
    from sigft.core import prefs
    prefs.gravar_preferencia("console.Tela", "muito", config_path=str(prefs_do_teste))
    t = _aberta(qtbot)
    assert t.console.height() == theme.ALTURA_CONSOLE


def test_ler_ou_gravar_que_falha_nao_quebra_a_tela(qt_interface, qtbot, prefs_do_teste, monkeypatch):
    from sigft.core import prefs

    def quebra(*_a, **_k):
        raise OSError("disco cheio")

    monkeypatch.setattr(prefs, "ler_preferencia", quebra)
    monkeypatch.setattr(prefs, "gravar_preferencia", quebra)
    t = _aberta(qtbot)
    assert t.console.height() == theme.ALTURA_CONSOLE
    arrastar(t.puxador_console, -40)
    t.hide()                                        # grava: falha calada
    assert t.console.height() == theme.ALTURA_CONSOLE + 40


def test_janela_menor_encolhe_o_console_escolhido_sem_esquecer(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    arrastar(t.puxador_console, -300)
    escolhida = t.altura_console_escolhida
    t.resize(1003, 520)
    QApplication.processEvents()
    QApplication.processEvents()
    assert t.content.height() >= puxador_mod.MIN_CONTEUDO - 1
    assert t.altura_console_escolhida == escolhida
    t.resize(1003, 750)
    QApplication.processEvents()
    QApplication.processEvents()
    assert t.console.height() == escolhida


# --- as telas de verdade ------------------------------------------------------------

def _telas_com_console():
    from sigft.app_qt.views.analyzer import ModuloAnalyzer
    from sigft.app_qt.views.aplicacao_lmr import ModuloAplicacaoLMR
    from sigft.app_qt.views.autospec import ModuloAutoSpec
    from sigft.app_qt.views.busca_pmib import ModuloBuscaPMIB
    from sigft.app_qt.views.copia_fichas import ModuloCopiaFichas
    from sigft.app_qt.views.correcao_pdm import ModuloCorrecaoPDM
    from sigft.app_qt.views.cria_fichas import ModuloCriaFichas
    from sigft.app_qt.views.pdm import ModuloPDM
    from sigft.app_qt.views.pmib_manager import ModuloPMIBManager
    from sigft.app_qt.views.translator import ModuloTranslator
    from sigft.app_qt.views.upload_conditions import ModuloUploadConditions
    from sigft.app_qt.views.upload_tech_specs import ModuloUploadTechSpecs
    return [ModuloAnalyzer, ModuloAplicacaoLMR, ModuloAutoSpec, ModuloBuscaPMIB,
            ModuloCopiaFichas, ModuloCorrecaoPDM, ModuloCriaFichas, ModuloPDM,
            ModuloPMIBManager, ModuloTranslator, ModuloUploadConditions,
            ModuloUploadTechSpecs]


def _aberta_de_verdade(qtbot, classe):
    t = classe()
    qtbot.addWidget(t)
    t.resize(1003, 850)
    t.show()
    qtbot.waitExposed(t)
    QApplication.processEvents()
    QApplication.processEvents()
    return t


@pytest.mark.parametrize("indice", range(12))
def test_toda_tela_com_console_arrasta_e_volta(qt_interface, qtbot, prefs_do_teste, indice):
    classe = _telas_com_console()[indice]
    t = _aberta_de_verdade(qtbot, classe)
    p = t.puxador_console
    assert p is not None and p.isVisible(), classe.__name__
    assert _topo(p, t) + p.height() <= _topo(t.console, t)
    padrao = t.console.height()
    # A barrinha segue o cursor: 30 para baixo, depois 10 para cima (cabe em
    # toda tela: na Busca e na Gestão o console já tem toda a sobra e só
    # diminui, mas os 30 de antes liberam espaço).
    inicio = _topo(p, t)
    arrastar(p, 30)
    assert abs(_topo(p, t) - (inicio + 30)) <= 1, classe.__name__
    arrastar(p, -10)
    assert abs(_topo(p, t) - (inicio + 20)) <= 1, classe.__name__
    assert _topo(p, t) + p.height() <= _topo(t.console, t)
    QTest.mouseDClick(p, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    QApplication.processEvents()
    assert t.console.height() == padrao, classe.__name__
    assert _topo(p, t) == inicio, classe.__name__


def test_correcao_de_pdm_um_pixel_para_cima_sobe_um_pixel(qt_interface, qtbot, prefs_do_teste):
    """A faixa da Correção é maior que o console centrado nela (200 x 150 a
    1003x850): a barrinha não pode pular quando o console passa a enchê-la."""
    from sigft.app_qt.views.correcao_pdm import ModuloCorrecaoPDM

    t = _aberta_de_verdade(qtbot, ModuloCorrecaoPDM)
    p = t.puxador_console
    assert t.faixa_console.height() > t.console.height()      # o caso da revisão
    inicio = _topo(p, t)
    arrastar(p, -1)
    assert _topo(p, t) == inicio - 1
    assert t.console.height() == t.faixa_console.height()
    assert _topo(p, t) + p.height() <= _topo(t.console, t)


# --- tema e letra -------------------------------------------------------------------

@pytest.mark.parametrize("tema", ["claro", "escuro"])
def test_a_barrinha_tem_cor_nos_dois_temas(tema):
    from sigft.app import tokens
    from sigft.app_qt import estilo

    folha = estilo.folha_de_estilo(tema)
    p = tokens.paleta(tema)
    assert f'#puxador_console[ativo="true"] {{ background: {p["borda"]}; }}' in folha
    assert f'#puxador_console_marca[ativo="true"] {{ background: {p["primaria"]}; }}' in folha


def test_mouse_em_cima_destaca_a_barrinha(qt_interface, qtbot, prefs_do_teste):
    t = _aberta(qtbot)
    p = t.puxador_console
    QApplication.sendEvent(p, QEvent(QEvent.Type.Enter))
    assert p.property("ativo") is True and p.marca.property("ativo") is True
    QApplication.sendEvent(p, QEvent(QEvent.Type.Leave))
    assert p.property("ativo") is False


def test_tema_trocado_com_a_tela_aberta_continua_arrastando(qt_interface, qtbot, prefs_do_teste,
                                                            tmp_path, monkeypatch):
    from sigft.app_qt import estilo, tema

    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "t.json")
    atual, folha = estilo.TEMA_ATUAL, qt_interface.styleSheet()
    try:
        t = _aberta(qtbot)
        tema.aplicar(qt_interface, "claro", gravar=False)
        QApplication.processEvents()
        arrastar(t.puxador_console, -40)
        tema.aplicar(qt_interface, "escuro", gravar=False)
        QApplication.processEvents()
        assert t.console.height() == theme.ALTURA_CONSOLE + 40
        assert _topo(t.puxador_console, t) + t.puxador_console.height() <= _topo(t.console, t)
    finally:
        estilo.TEMA_ATUAL = atual
        qt_interface.setStyleSheet(folha)


def test_letra_grande_sobe_o_minimo_e_arrasta(qt_interface, qtbot, prefs_do_teste,
                                              tmp_path, monkeypatch):
    from sigft.app_qt import estilo, letra

    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "l.json")
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = _aberta(qtbot)
        normal = puxador_mod.altura_minima_do_console(t.console)
        letra.aplicar(qt_interface, "grande", gravar=False)
        QApplication.processEvents()
        assert puxador_mod.altura_minima_do_console(t.console) > normal
        arrastar(t.puxador_console, 2000)
        assert t.console.height() == puxador_mod.altura_minima_do_console(t.console)
        arrastar(t.puxador_console, -60)
        assert t.console.height() == puxador_mod.altura_minima_do_console(t.console) + 60
    finally:
        letra.aplicar(qt_interface, "normal", gravar=False)
        qt_interface.setStyleSheet(anterior)


def test_letra_grande_sobe_a_altura_guardada_que_ficou_abaixo_do_minimo(
        qt_interface, qtbot, prefs_do_teste, tmp_path, monkeypatch):
    from sigft.app_qt import estilo, letra
    from sigft.core import prefs

    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "l.json")
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        sonda = _aberta(qtbot, OutraTela)
        normal = puxador_mod.altura_minima_do_console(sonda.console)
        prefs.gravar_preferencia("console.Tela", str(normal), config_path=str(prefs_do_teste))
        t = _aberta(qtbot)
        assert t.console.height() == normal
        letra.aplicar(qt_interface, "grande", gravar=False)
        minimo = puxador_mod.altura_minima_do_console(t.console)
        assert minimo > normal
        qtbot.waitUntil(lambda: t.console.height() == minimo, timeout=2000)
        assert t.altura_console_escolhida == normal          # a escolha fica
    finally:
        letra.aplicar(qt_interface, "normal", gravar=False)
        qt_interface.setStyleSheet(anterior)

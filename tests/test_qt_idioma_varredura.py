"""As 12 telas em espanhol e em inglês, a 1280x850 (2026-10-22).

Nada cortado e nada rolando de lado, com a letra normal e com a grande, nos
dois temas e em todas as abas. O que já
fica apertado em português (o "Limpar" de 100 px da Criação de Fichas, travado
pelo teste de medida) não conta: a referência é a mesma tela em português, com
os textos traduzidos. Se esta varredura acusar, encurte a tradução antes de
mexer no layout (Glossário e estilo, no plano de 2026-10-22).

Fora das 12 telas: as janelas auxiliares (Escolha a aba, Novas Listas, Resultados
da Busca, Configuração de Pesos) e as dicas, que eram mais de 20% maiores que as
do português em alguns botões (Task 4).
"""
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QToolTip, QWidget

from _idioma import em_idioma
from _varredura import cortados, varrer
from sigft.app import idioma
from sigft.app_qt import letra, tema
from sigft.app_qt import main as qmain


@pytest.fixture
def montar(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.delenv("SIGFT_SEM_COMO_FUNCIONA", raising=False)   # as telas com o "Como funciona"
    anterior = qt_interface.styleSheet()

    def _montar():
        janela = qmain.SIG_FT_App()
        janela.fechar_sem_perguntar = True
        qtbot.addWidget(janela)
        janela.resize(1280, 850)
        janela.show()
        qtbot.waitExposed(janela)
        return janela

    yield _montar
    letra.aplicar(qt_interface, "normal", gravar=False)
    tema.aplicar(qt_interface, tema.PADRAO, gravar=False)
    qt_interface.setStyleSheet(anterior)


@pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
@pytest.mark.parametrize("codigo", ["es", "en"])
def test_nenhuma_tela_corta_texto_nem_rola_de_lado_em_outro_idioma(montar, qtbot, qt_interface, codigo,
                                                                    nome_tema):
    tema.aplicar(qt_interface, nome_tema, gravar=False)
    letra.aplicar(qt_interface, "normal", gravar=False)
    em_portugues, _ = varrer(montar(), qtbot)
    with em_idioma(codigo):
        ja_apertados = {alvo: {idioma.t(texto) for texto in textos} for alvo, textos in em_portugues.items()}
        letra.aplicar(qt_interface, "normal", gravar=False)   # o vigia do idioma liga aqui
        janela = montar()
        normal, rolando_normal = varrer(janela, qtbot)
        letra.aplicar(qt_interface, "grande", gravar=False)
        grande, rolando_grande = varrer(janela, qtbot)
        assert rolando_normal == [] and rolando_grande == []
        for medida in (normal, grande):
            sobra = {alvo: textos - ja_apertados[alvo] for alvo, textos in medida.items()
                     if textos - ja_apertados[alvo]}
            assert sobra == {}
    letra.aplicar(qt_interface, "normal", gravar=False)


# --- as janelas auxiliares (2026-10-22) --------------------------------------

def _janelas_auxiliares(qtbot) -> dict[str, QWidget]:
    """As quatro janelas que não são tela, montadas no idioma de agora."""
    from sigft.app_qt.views import analyzer, busca_pmib, lmr, pmib_manager
    from sigft.core.rpa.ficha_layout import CONFIG_MAP

    busca = busca_pmib.ModuloBuscaPMIB(None, None)
    analise = analyzer.ModuloAnalyzer(None, SimpleNamespace(get_key=lambda _k: ""))
    for tela in (busca, analise):
        qtbot.addWidget(tela)
    resultado = {"codigo_itaipu": "4500063671.0012", "coluna_match": "DESCRIÇÃO", "amostra": "ROLAMENTO",
                 "caminho_arquivo": "/fichas/UG01/4500063671.0012.xlsx", "caminho_pasta": "/fichas/UG01"}
    janelas = {
        "Escolha a aba": lmr.DialogoDaAba(None, nome_arquivo="LMR_Aplicacoes_2026.xlsx", abas=["Plan1", "LMR"]),
        "Novas Listas": pmib_manager.NovasListasDialog(None, itens=[(0, "[L-1]  -  Lista 1")],
                                                       evento_espera=threading.Event(), resultado={}),
        "Resultados": busca_pmib.JanelaResultados(busca, [resultado]),
        # Os rótulos dos pesos ("Texto Breve Material") vêm das chaves do
        # `CONFIG_MAP`: nome de campo da ficha, não se traduz. A pesagem só mede.
        "Pesos": analyzer.JanelaPesos(analise, CONFIG_MAP),
    }
    for janela in janelas.values():
        qtbot.addWidget(janela)
        janela.show()
        qtbot.waitExposed(janela)
    return janelas


@pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
@pytest.mark.parametrize("tamanho", ["normal", "grande"])
@pytest.mark.parametrize("codigo", ["es", "en"])
def test_janelas_auxiliares_nao_cortam_texto_em_outro_idioma(montar, qtbot, qt_interface, codigo, tamanho,
                                                             nome_tema):
    with em_idioma(codigo):
        tema.aplicar(qt_interface, nome_tema, gravar=False)
        letra.aplicar(qt_interface, tamanho, gravar=False)
        janelas = _janelas_auxiliares(qtbot)
        qtbot.wait(20)
        assert {nome: cortados(j) for nome, j in janelas.items() if cortados(j)} == {}
        for janela in janelas.values():
            janela.close()


def _largura_da_dica(qtbot, texto: str) -> int:
    """A largura da dica como o Qt a mostra (a `QTipLabel`, com a folha do app).

    Mostrada no meio da tela de verdade, não em (0, 0): no Windows do Release
    (offscreen) o (0, 0) não cai em tela nenhuma, o Qt não mostra a dica e a
    `QTipLabel` nem existe (2026-10-23)."""
    QToolTip.showText(QApplication.primaryScreen().geometry().center(), texto)

    def _rotulo():
        return next((w for w in QApplication.topLevelWidgets()
                     if w.metaObject().className() == "QTipLabel" and w.isVisible()), None)

    qtbot.waitUntil(lambda: _rotulo() is not None, timeout=2000)
    rotulo = _rotulo()
    largura = rotulo.width()
    QToolTip.hideText()
    return largura


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_nenhuma_dica_passa_da_tela_em_outro_idioma(montar, qtbot, qt_interface, codigo):
    # As dicas mais compridas no espanhol (Task 4) passam de 800 px numa linha
    # só; o Qt quebra a dica de texto simples que não cabe na tela. A trava é
    # essa: nenhuma dica, de nenhuma tela, mais larga que a tela.
    from sigft.app_qt import catalogo

    with em_idioma(codigo):
        letra.aplicar(qt_interface, "grande", gravar=False)
        janela = montar()
        dicas = {w.toolTip() for w in janela.findChildren(QWidget) if w.toolTip()}
        for alvo in [m[0] for m in catalogo.MODULOS if m[0] not in catalogo.TELAS_BLOQUEADAS]:
            janela.show_frame(alvo)
            dicas |= {w.toolTip() for w in janela.telas[alvo].findChildren(QWidget) if w.toolTip()}
        tela = QApplication.primaryScreen().availableGeometry().width()
        assert len(dicas) > 40
        assert {d[:40]: lg for d in dicas if (lg := _largura_da_dica(qtbot, d)) > tela} == {}

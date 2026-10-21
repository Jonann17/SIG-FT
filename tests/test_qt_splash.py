"""A splash do sistema visual (Task 10, 2026-10-20).

Ela aparece ANTES da janela principal, então pinta com o tema guardado nas
preferências (`tema.escolhido`), não com o que a folha do app tiver: quem usa o
claro vê a abertura clara. Fundo `fundo`, logo da GE Vernova, "SIG-FT" 22 em
negrito, a versão em `texto_suave` e uma barra de 4 px em `primaria`.
"""
import pytest

from sigft import _build_info
from sigft.app import tokens
from sigft.app_qt import main as qmain
from sigft.app_qt import tema
from sigft.core import prefs as prefs_do_app


@pytest.fixture
def prefs(tmp_path, monkeypatch):
    """Um `user_prefs.json` de teste; devolve a função que grava o tema nele."""
    arquivo = tmp_path / "p.json"
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: arquivo)

    def gravar(escolha: str) -> None:
        prefs_do_app.gravar_preferencia(tema.CHAVE_PREFERENCIA, escolha, config_path=arquivo)

    return gravar


def _cor(imagem, x, y) -> str:
    return imagem.pixelColor(x, y).name().upper()


def _splash(qtbot):
    splash = qmain.SplashScreen()
    qtbot.addWidget(splash)
    splash.barra.setValue(splash.barra.maximum())
    splash.show()
    qtbot.waitExposed(splash)
    return splash


@pytest.mark.parametrize("escolha", ["escuro", "claro"])
def test_fundo_e_barra_seguem_o_tema_guardado(qt_interface, qtbot, prefs, escolha):
    prefs(escolha)
    p = tokens.paleta(escolha)
    splash = _splash(qtbot)
    imagem = splash.grab().toImage()

    # Uma faixa da margem esquerda, longe do logo e do texto: só fundo.
    assert _cor(imagem, 12, splash.height() // 2) == p["fundo"].upper()
    barra = splash.barra
    assert barra.height() == 4
    meio = barra.mapTo(splash, barra.rect().center())
    assert _cor(imagem, meio.x(), meio.y()) == p["primaria"].upper()


def test_sistema_escolhido_pinta_o_do_windows(qt_interface, qtbot, prefs, monkeypatch):
    prefs("sistema")
    monkeypatch.setattr(tema, "_esquema_do_sistema", lambda: "claro")
    splash = _splash(qtbot)
    imagem = splash.grab().toImage()
    assert _cor(imagem, 12, splash.height() // 2) == tokens.CLARO["fundo"].upper()


def test_cantos_arredondados(qt_interface, qtbot, prefs):
    """Raio 10 (`tokens.RAIO["cartao"]`): o pixel do canto fica de fora."""
    prefs("claro")
    splash = _splash(qtbot)
    imagem = splash.grab().toImage()
    assert imagem.pixelColor(0, 0).alpha() == 0
    assert _cor(imagem, 12, 12) == tokens.CLARO["fundo"].upper()


def test_titulo_e_versao(qt_interface, qtbot, prefs, monkeypatch):
    prefs("escuro")
    # O Release reescreve o `_build_info` (`tools/preparar_build.py`): a splash
    # mostra exatamente o número dele.
    monkeypatch.setattr(_build_info, "VERSAO", "1.2.1-rc.9")
    splash = _splash(qtbot)
    assert splash.titulo.text() == "SIG-FT"
    fonte = splash.titulo.font()
    assert fonte.pixelSize() == 22 and fonte.bold()
    assert splash.versao.text() == "versão 1.2.1-rc.9"
    cor = splash.versao.palette().color(splash.versao.foregroundRole()).name().upper()
    assert cor == tokens.ESCURO["texto_suave"].upper()


def test_sem_versao_no_build_info_nao_quebra(qt_interface, qtbot, prefs, monkeypatch):
    """Rodando do código-fonte, um `_build_info` sem `VERSAO` não derruba a abertura."""
    prefs("escuro")
    monkeypatch.delattr(_build_info, "VERSAO")
    splash = _splash(qtbot)
    assert splash.versao.text() == "versão de desenvolvimento"


def test_tamanho_de_sempre(qt_interface, qtbot, prefs):
    prefs("escuro")
    splash = _splash(qtbot)
    assert (splash.width(), splash.height()) == (500, 350)

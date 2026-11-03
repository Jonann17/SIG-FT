"""A lâmpada da Home e a janela Sugestões (2026-10-30): o rascunho de e-mail
sai de `services/sugestoes.py`, falsificado aqui."""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QCheckBox, QPushButton

from sigft.app_qt import aviso_windows, catalogo, estilo, letra, tema
from sigft.app_qt.views import home as home_mod
from sigft.app_qt.views import sugestoes as sug_mod
from sigft.services import sugestoes, updater


class Controller:
    api_keys: dict = {}

    def get_key(self, _chave):
        return ""

    def save_keys(self, _novas):
        pass

    def show_frame(self, _nome):
        pass


@pytest.fixture
def home(qt_interface, qtbot, tmp_path, monkeypatch):
    for modulo in (tema, letra, aviso_windows):
        monkeypatch.setattr(modulo, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(updater, "canal_testes_ligado", lambda **_k: False)
    folha, atual = qt_interface.styleSheet(), estilo.TEMA_ATUAL
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    yield tela
    estilo.TEMA_ATUAL = atual
    qt_interface.setStyleSheet(folha)


class _Lista(list):
    pass


@pytest.fixture
def pedidos(monkeypatch):
    """O serviço falso e a thread trocada por chamada direta."""
    vistos = _Lista()
    resposta = {"resultado": sugestoes.Resultado(via="outlook")}

    def abrir_rascunho(texto, **kw):
        vistos.append((texto, kw))
        if isinstance(resposta["resultado"], Exception):
            raise resposta["resultado"]
        return resposta["resultado"]

    monkeypatch.setattr(sugestoes, "abrir_rascunho", abrir_rascunho)
    monkeypatch.setattr(sug_mod.JanelaSugestoes, "disparar", staticmethod(lambda alvo, *a: alvo(*a)))
    monkeypatch.setattr(sug_mod._build_info, "VERSAO", "9.9.9")
    vistos.resposta = resposta
    return vistos


def test_a_lampada_fica_logo_a_esquerda_da_engrenagem(home, qtbot):
    home.resize(1100, 850)
    home.show()
    qtbot.waitExposed(home)
    lampada, engrenagem = home.btn_sugestoes, home.btn_configuracao
    assert lampada.parentWidget() is engrenagem.parentWidget()
    corpo = home.widget()
    a, b = lampada.mapTo(corpo, QPoint(0, 0)), engrenagem.mapTo(corpo, QPoint(0, 0))
    assert a.y() == b.y() and a.x() + lampada.width() == b.x()
    assert lampada.size() == engrenagem.size()
    assert lampada.property("icone") == "lightbulb" and not lampada.icon().isNull()
    assert lampada.property("variante") == engrenagem.property("variante") == "fantasma"
    assert lampada.toolTip() == "Sugestões" and lampada.accessibleName() == "Sugestões"
    assert lampada.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_a_lampada_abre_uma_janela_so(home, qtbot):
    home.show()
    qtbot.mouseClick(home.btn_sugestoes, Qt.MouseButton.LeftButton)
    janela = home._janelas["sugestoes"]
    assert isinstance(janela, sug_mod.JanelaSugestoes)
    assert janela.isVisible() and janela.windowTitle() == "Sugestões"
    qtbot.mouseClick(home.btn_sugestoes, Qt.MouseButton.LeftButton)
    assert [j for j in home.findChildren(sug_mod.JanelaSugestoes) if j.isVisible()] == [janela]
    # Fechada, volta a MESMA, com o texto que a pessoa tinha escrito.
    janela.caixa_texto.setPlainText("ideia pela metade")
    janela.close()
    de_novo = home.abrir_sugestoes()
    assert de_novo is janela and de_novo.isVisible()
    assert de_novo.caixa_texto.toPlainText() == "ideia pela metade"


def test_o_ctrl_k_tem_sugestoes():
    chaves = [a[0] for a in catalogo.ACOES]
    assert "sugestoes" in chaves
    assert catalogo.ACAO_SUGESTOES in catalogo.ACOES_QUE_A_HOME_FAZ


def test_botao_so_com_texto_e_log_marcado_por_padrao(home):
    janela = home.abrir_sugestoes()
    assert janela.caixa_anexar_log.isChecked()
    assert not janela.btn_escrever.isEnabled()
    janela.caixa_texto.setPlainText("   \n ")
    assert not janela.btn_escrever.isEnabled()
    janela.caixa_texto.setPlainText("Uma ideia")
    assert janela.btn_escrever.isEnabled()
    for controle in janela.findChildren(QPushButton) + janela.findChildren(QCheckBox):
        assert controle.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_escrever_chama_o_servico_e_mostra_que_abriu_no_outlook(home, qtbot, pedidos):
    janela = home.abrir_sugestoes()
    janela.caixa_texto.setPlainText("  Uma ideia boa  ")
    janela.caixa_anexar_log.setChecked(False)
    qtbot.mouseClick(janela.btn_escrever, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: janela.status.text() == "Rascunho aberto no Outlook. Revise e envie.",
                    timeout=1000)
    ((texto, kw),) = pedidos
    assert texto == "Uma ideia boa"
    assert kw["versao"] == "9.9.9" and kw["anexar_log"] is False and kw["idioma"]
    # O texto fica: o SIG-FT não sabe se o e-mail foi enviado.
    assert janela.caixa_texto.toPlainText() == "  Uma ideia boa  "
    assert janela.btn_escrever.isEnabled()


def test_pelo_mailto_mostra_onde_esta_o_log(home, qtbot, pedidos, tmp_path):
    pedidos.resposta["resultado"] = sugestoes.Resultado(via="mailto", log=tmp_path / "sigft.log")
    janela = home.abrir_sugestoes()
    janela.caixa_texto.setPlainText("x")
    qtbot.mouseClick(janela.btn_escrever, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: str(tmp_path / "sigft.log") in janela.status.text(), timeout=1000)
    assert janela.status.text().startswith("Rascunho aberto no seu programa de e-mail.")
    assert pedidos[0][1]["anexar_log"] is True


def test_falha_vira_mensagem_de_erro(home, qtbot, pedidos):
    pedidos.resposta["resultado"] = RuntimeError("nenhum programa de e-mail")
    janela = home.abrir_sugestoes()
    janela.caixa_texto.setPlainText("x")
    qtbot.mouseClick(janela.btn_escrever, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "nenhum programa de e-mail" in janela.status.text(), timeout=1000)
    assert janela.status.property("papel") == "erro"
    assert janela.btn_escrever.isEnabled()

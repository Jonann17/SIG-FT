"""A janela "O que mudou na vX" (`sigft/app_qt/novidades.py`).

A regra (quando mostrar) e do core e tem os testes dela em
`tests/test_novidades_na_abertura.py`; aqui, so a tela e a ligacao com a
janela principal.
"""
import pytest

from sigft.app_qt import novidades as tela
from sigft.core import novidades, prefs
from sigft.services import updater

BLOCO = novidades.Bloco(versao="1.2.0", data="2026-10-19",
                        itens=["Home: a janela de **novidades**", "Upload: `mais rapido`"])


@pytest.fixture
def raiz(qt_interface, qtbot):
    from PySide6.QtWidgets import QMainWindow

    janela = QMainWindow()
    qtbot.addWidget(janela)
    janela.show()
    return janela


def _textos(widget):
    from PySide6.QtWidgets import QLabel, QPushButton

    achados = widget.findChildren(QLabel) + widget.findChildren(QPushButton)
    return [w.text() for w in achados if w.text()]


def test_a_janela_mostra_o_titulo_e_os_itens_como_texto(raiz, qtbot):
    janela = tela.JanelaNovidades(raiz, bloco=BLOCO)
    qtbot.addWidget(janela)

    assert "O que mudou na v1.2.0" in _textos(janela)
    texto = janela.caixa_texto.toPlainText()
    assert "• Home: a janela de novidades" in texto
    assert "• Upload: mais rapido" in texto
    assert "**" not in texto and "`" not in texto
    assert janela.caixa_texto.isReadOnly()


def test_a_janela_nao_e_modal_e_o_OK_fecha(raiz, qtbot):
    janela = tela.JanelaNovidades(raiz, bloco=BLOCO)
    qtbot.addWidget(janela)
    janela.show()

    assert not janela.isModal()
    assert janela.botao_ok.text() == "OK"
    janela.botao_ok.click()
    assert not janela.isVisible()


def test_mostrar_se_houver_abre_a_janela_com_o_bloco(raiz, monkeypatch):
    monkeypatch.setattr(novidades, "para_mostrar_na_abertura", lambda versao, **kw: BLOCO)

    janela = tela.mostrar_se_houver(raiz, versao_atual="1.2.0", empacotado=True)

    assert isinstance(janela, tela.JanelaNovidades) and janela.isVisible()
    janela.close()


def test_mostrar_se_houver_sem_bloco_nao_abre_nada(raiz, monkeypatch):
    monkeypatch.setattr(novidades, "para_mostrar_na_abertura", lambda versao, **kw: None)
    assert tela.mostrar_se_houver(raiz, versao_atual="1.2.0", empacotado=True) is None


def test_com_o_aviso_de_atualizacao_aberto_NAO_compete_nem_grava(raiz, monkeypatch, qtbot):
    from PySide6.QtWidgets import QDialog

    aviso = QDialog(raiz)
    aviso.fechada = False
    qtbot.addWidget(aviso)
    raiz._janela_de_atualizacao = aviso
    chamadas = []
    monkeypatch.setattr(novidades, "para_mostrar_na_abertura",
                        lambda versao, **kw: chamadas.append(versao) or BLOCO)

    assert tela.mostrar_se_houver(raiz, versao_atual="1.2.0", empacotado=True) is None
    assert chamadas == [], "decidiu (e gravou a versao como vista) sem mostrar"


def test_janela_principal_escondida_nao_mostra(qt_interface, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMainWindow

    principal = QMainWindow()
    qtbot.addWidget(principal)
    monkeypatch.setattr(novidades, "para_mostrar_na_abertura", lambda versao, **kw: BLOCO)
    assert tela.mostrar_se_houver(principal, versao_atual="1.2.0", empacotado=True) is None


def test_ponta_a_ponta_com_a_preferencia_de_verdade(raiz, tmp_path, monkeypatch):
    caminho = str(tmp_path / "user_prefs.json")
    prefs.set_ultima_versao_vista("1.1.0", config_path=caminho)
    arquivo = tmp_path / "CHANGELOG.md"
    arquivo.write_text("## 1.2.0 - 2026-10-19\n- Home: novidade\n", encoding="utf-8")
    monkeypatch.setattr(novidades, "caminho_changelog", lambda: str(arquivo))

    janela = tela.mostrar_se_houver(raiz, versao_atual="1.2.0", empacotado=True,
                                    config_path=caminho)
    assert janela is not None
    janela.close()
    assert tela.mostrar_se_houver(raiz, versao_atual="1.2.0", empacotado=True,
                                  config_path=caminho) is None


# -- agendar_na_abertura: a abertura nao espera --------------------------------

def test_pelo_codigo_fonte_nem_agenda(raiz, monkeypatch):
    monkeypatch.setattr(updater, "empacotado", lambda: False)
    agendados = []
    assert tela.agendar_na_abertura(raiz, agendar=lambda *a: agendados.append(a)) is False
    assert agendados == []


def test_empacotado_agenda_para_DEPOIS_e_nao_mostra_na_hora(raiz, monkeypatch):
    monkeypatch.setattr(updater, "empacotado", lambda: True)
    monkeypatch.setattr(novidades, "para_mostrar_na_abertura",
                        lambda *a, **kw: pytest.fail("decidiu dentro da abertura"))
    agendados = []

    assert tela.agendar_na_abertura(raiz, agendar=lambda ms, f: agendados.append((ms, f)))
    assert len(agendados) == 1 and agendados[0][0] > 0


def test_o_agendado_mostra_a_janela(raiz, monkeypatch):
    monkeypatch.setattr(updater, "empacotado", lambda: True)
    monkeypatch.setattr(novidades, "para_mostrar_na_abertura", lambda versao, **kw: BLOCO)
    agendados = []
    tela.agendar_na_abertura(raiz, versao_atual="1.2.0",
                             agendar=lambda ms, f: agendados.append(f))

    agendados[0]()

    assert isinstance(raiz._janela_de_novidades, tela.JanelaNovidades)
    raiz._janela_de_novidades.close()


def test_a_janela_principal_agenda_as_novidades_na_abertura(monkeypatch, qt_interface, qtbot,
                                                            tmp_path):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    chamadas = []
    monkeypatch.setattr(qmain.novidades, "agendar_na_abertura", lambda j: chamadas.append(j))

    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)

    assert chamadas == [janela]

"""A janela "Revisão antes do portal" e a função que as quatro telas de robô chamam.

Com problema: a janela diz o que deu erro e onde, e a pessoa escolhe "Seguir sem
as fichas com erro" (padrão, Enter), "Seguir com todas" ou "Cancelar" (Esc/X).
O mesmo relatório vai para o console. Sem problema, nada aparece.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from sigft.app_qt.widgets import revisao_portal as rp
from sigft.core.pmib_regras import Problema


def _p(indice, ficha="4500.1", campo="Texto breve do material", interno="Input_ShortText",
       valor="VÁLVULA", mensagem="tem caractere que o portal recusa ('Á')"):
    return Problema(ficha=ficha, campo=campo, interno=interno, valor=valor, regra="regra",
                    mensagem=mensagem, indice=indice)


@pytest.fixture
def janela(qt_interface, qtbot):
    problemas = [_p(0), _p(0, campo="Código do projeto", interno="TextArea_ProjectCode", valor="",
                            mensagem="está vazio"), _p(2, ficha="4500.3")]
    dlg = rp.RevisaoAntesDoPortalDialog(None, problemas, total=5)
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg


def test_titulo_contagem_e_tabela(janela):
    assert janela.windowTitle() == "Revisão antes do portal"
    assert janela.contagem.text() == "3 problema(s) em 2 ficha(s) de 5"
    tree = janela.tabela
    assert [tree.headerItem().text(i) for i in range(tree.columnCount())] == [
        "Ficha", "Campo", "Valor", "O que o portal vai recusar"]
    assert tree.topLevelItemCount() == 3
    linha = [tree.topLevelItem(1).text(i) for i in range(4)]
    assert linha == ["4500.1", "Código do projeto (TextArea_ProjectCode)", "", "está vazio"]


def test_botoes_na_ordem(janela):
    assert [b.text() for b in janela.botoes] == [
        "Seguir sem as fichas com erro", "Seguir com todas", "Cancelar"]
    assert janela.isModal()


@pytest.mark.parametrize("indice, esperado", [(0, rp.SEM_ERROS), (1, rp.TODAS), (2, None)])
def test_cada_botao_decide(janela, indice, esperado):
    janela.botoes[indice].click()
    assert janela.decisao == esperado and not janela.isVisible()


def test_enter_e_seguir_sem_as_fichas_com_erro(janela, qtbot):
    qtbot.keyClick(janela, Qt.Key.Key_Return)
    assert janela.decisao == rp.SEM_ERROS
    assert janela.result() == QDialog.DialogCode.Accepted


def test_esc_cancela(janela, qtbot):
    qtbot.keyClick(janela, Qt.Key.Key_Escape)
    assert janela.decisao is None and not janela.isVisible()


def test_fechar_no_x_cancela(janela):
    janela.close()
    assert janela.decisao is None


# --- a função compartilhada ----------------------------------------------------------
class Log(list):
    def __call__(self, texto):
        self.append(texto)


def _perguntar(resposta, chamadas):
    def perguntar(parent, problemas, total):
        chamadas.append((parent, list(problemas), total))
        return resposta
    return perguntar


def test_sem_problema_nada_aparece_e_segue_com_todas(qt_interface):
    chamadas, log = [], Log()
    assert rp.conferir_antes_do_portal(None, [], 3, log, perguntar=_perguntar("x", chamadas)) == [0, 1, 2]
    assert chamadas == [] and log == []


def test_com_problema_loga_uma_linha_por_problema_e_pergunta(qt_interface):
    chamadas, log = [], Log()
    problemas = [_p(0), _p(2, ficha="4500.3")]
    seguem = rp.conferir_antes_do_portal("tela", problemas, 4, log, perguntar=_perguntar(rp.SEM_ERROS, chamadas))
    assert seguem == [1, 3]
    assert chamadas == [("tela", problemas, 4)]
    assert log[0] == "Revisão antes do portal: 2 problema(s) em 2 ficha(s) de 4."
    assert log[1].startswith("[!] 4500.1 · Texto breve do material (Input_ShortText) · 'VÁLVULA' · ")
    assert log[2].startswith("[!] 4500.3 ·")
    assert log[-1] == "Seguindo sem as 2 ficha(s) com erro: 2 vão ao portal."


def test_seguir_com_todas(qt_interface):
    log = Log()
    seguem = rp.conferir_antes_do_portal(None, [_p(1)], 2, log, perguntar=_perguntar(rp.TODAS, []))
    assert seguem == [0, 1]
    assert log[-1] == "Seguindo com todas as fichas, inclusive as com erro."


def test_cancelar(qt_interface):
    log = Log()
    assert rp.conferir_antes_do_portal(None, [_p(1)], 2, log, perguntar=_perguntar(None, [])) is None
    assert log[-1] == "Cancelado na revisão antes do portal."


def test_sem_nenhuma_ficha_sem_erro_avisa_e_nao_segue(qt_interface, monkeypatch):
    avisos, log = [], Log()
    monkeypatch.setattr(rp.QMessageBox, "warning", lambda *a: avisos.append(a[1:]))
    assert rp.conferir_antes_do_portal(None, [_p(0), _p(1)], 2, log,
                                       perguntar=_perguntar(rp.SEM_ERROS, [])) is None
    assert log[-1] == rp.MSG_NADA_SOBROU
    assert avisos == [(rp.TITULO, rp.MSG_NADA_SOBROU)]


def test_perguntar_de_verdade_abre_a_janela_modal(qt_interface, qtbot, monkeypatch):
    vistas = []

    def exec_(self):
        vistas.append((self.contagem.text(), self.isModal()))
        self.botoes[1].click()
        return 1

    monkeypatch.setattr(rp.RevisaoAntesDoPortalDialog, "exec", exec_)
    assert rp.perguntar_revisao(None, [_p(0)], 1) == rp.TODAS
    assert vistas == [("1 problema(s) em 1 ficha(s) de 1", True)]

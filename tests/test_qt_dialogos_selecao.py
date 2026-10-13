"""Diálogos de seleção e de arquivos travados da interface Qt (E3.1).

Mesmo contrato dos CustomTkinter (`sigft/app/widgets/dialogs.py`): a escolha
volta por `ao_confirmar`, o "X" não chama ninguém, e o de arquivos travados
solta o worker com a resposta segura (Seguir).
"""
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView, QMessageBox, QWidget

from sigft.app.textos_dialogos import TEXTOS_TRAVADOS
from sigft.app_qt.widgets import dialogos_selecao as qd
from sigft.app_qt.widgets.espera import DialogosDeEspera


@pytest.fixture
def folha_do_app(qapp):
    """A folha do app aplicada, como em produção (sem ela os botões medem outra coisa)."""
    from sigft.app_qt import estilo as _estilo
    anterior = qapp.styleSheet()
    qapp.setStyleSheet(_estilo.folha_de_estilo())
    yield
    qapp.setStyleSheet(anterior)


def _abertos(tipo):
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, tipo) and w.isVisible()]


# --- SelecaoMultiplaDialog ---------------------------------------------------

def test_selecao_multipla_devolve_os_textos_marcados(qt_interface, qtbot):
    escolhas = []
    dlg = qd.SelecaoMultiplaDialog(None, itens=["A", "B", "C"], ao_confirmar=escolhas.append)
    qtbot.addWidget(dlg)
    assert dlg.isVisible()  # nasce aberta, como o CTkToplevel
    dlg.listbox.item(0).setSelected(True)
    dlg.listbox.item(2).setSelected(True)
    dlg.botao_confirmar.click()
    assert escolhas == [["A", "C"]]
    assert not dlg.isVisible()


def test_selecao_multipla_clique_alterna_sem_ctrl(qt_interface, qtbot):
    # tk.Listbox(selectmode="multiple"): cada clique marca/desmarca o item.
    dlg = qd.SelecaoMultiplaDialog(None, itens=["A", "B"])
    qtbot.addWidget(dlg)
    assert dlg.listbox.selectionMode() == QAbstractItemView.SelectionMode.MultiSelection


def test_selecao_multipla_devolve_indices_e_seleciona_todos(qt_interface, qtbot):
    escolhas = []
    dlg = qd.SelecaoMultiplaDialog(None, itens=["x", "y", "z"], com_selecionar_todos=True,
                                   devolver_indices=True, ao_confirmar=escolhas.append)
    qtbot.addWidget(dlg)
    dlg.botao_todos.click()
    dlg.botao_confirmar.click()
    assert escolhas == [[0, 1, 2]]


def test_selecao_multipla_sem_selecionar_todos_nao_tem_o_botao(qt_interface, qtbot):
    dlg = qd.SelecaoMultiplaDialog(None, itens=["x"])
    qtbot.addWidget(dlg)
    assert dlg.botao_todos is None


def test_selecao_multipla_fechar_no_x_nao_chama_ninguem(qt_interface, qtbot):
    escolhas = []
    dlg = qd.SelecaoMultiplaDialog(None, itens=["x"], ao_confirmar=escolhas.append)
    qtbot.addWidget(dlg)
    dlg.listbox.item(0).setSelected(True)
    dlg.close()
    assert escolhas == []


def test_selecao_multipla_modal_e_esperar(qt_interface, qtbot):
    # `esperar()` é o `wait_window` do CTk: volta quando a janela fecha e
    # devolve a escolha (None se fechou sem confirmar).
    dlg = qd.SelecaoMultiplaDialog(None, itens=["a", "b"], modal=True, geometria="400x500")
    qtbot.addWidget(dlg)
    assert dlg.windowModality() == Qt.WindowModality.ApplicationModal
    assert (dlg.width(), dlg.height()) == (400, 500)

    def confirmar():
        dlg.listbox.item(1).setSelected(True)
        dlg.botao_confirmar.click()

    from PySide6.QtCore import QTimer
    QTimer.singleShot(50, confirmar)
    assert dlg.esperar() == ["b"]

    outro = qd.SelecaoMultiplaDialog(None, itens=["a"], modal=True)
    qtbot.addWidget(outro)
    QTimer.singleShot(50, outro.close)
    assert outro.esperar() is None


def test_selecao_multipla_estilo_da_lista_vira_folha(qt_interface, qtbot):
    dlg = qd.SelecaoMultiplaDialog(
        None, itens=["x"], fonte_lista=("Consolas", 12), fonte_instrucao=("Roboto", 14, "bold"),
        estilo_lista={"bg": "#1E1E1E", "fg": "white", "selectbackground": "#035D67",
                      "highlightthickness": 0, "borderwidth": 0})
    qtbot.addWidget(dlg)
    folha = dlg.listbox.styleSheet()
    assert "#1E1E1E" in folha and "#035D67" in folha and "white" in folha
    # tk.Listbox: tamanho positivo é PONTO; CTkLabel: pixel.
    assert dlg.listbox.font().pointSize() == 12
    assert dlg.rotulo.font().pixelSize() == 14 and dlg.rotulo.font().bold()


def test_selecao_multipla_sem_estilo_e_a_listbox_crua_clara(qt_interface, qtbot):
    dlg = qd.SelecaoMultiplaDialog(None, itens=["x"])
    qtbot.addWidget(dlg)
    assert dlg.listbox.property("claro") is True


# --- TabelaSelecaoDialog -----------------------------------------------------

def _tabela(qtbot, **kw):
    kw.setdefault("colunas", ("Descrição", "PMIB"))
    kw.setdefault("linhas", [(10, ("Bomba", "001")), (20, ("Motor", "002")), (30, ("Eixo", "003"))])
    dlg = qd.TabelaSelecaoDialog(None, **kw)
    qtbot.addWidget(dlg)
    return dlg


def test_tabela_devolve_as_chaves_e_nao_a_posicao(qt_interface, qtbot):
    escolhas = []
    dlg = _tabela(qtbot, ao_confirmar=escolhas.append)
    assert dlg.isVisible()
    assert dlg.windowModality() == Qt.WindowModality.ApplicationModal  # modal por padrão
    assert dlg.tree.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    dlg.tree.topLevelItem(2).setSelected(True)
    dlg.tree.topLevelItem(0).setSelected(True)
    assert dlg.selecionados == ["10", "30"]  # ordem da tabela, chave em texto (iid do Treeview)
    dlg.botao_confirmar.click()
    assert escolhas == [["10", "30"]]


def test_tabela_preselecionar_tudo_larguras_e_ancora(qt_interface, qtbot):
    dlg = _tabela(qtbot, preselecionar_tudo=True,
                  larguras={"Descrição": {"width": 400}, "PMIB": {"width": 150, "anchor": "center"}})
    assert dlg.selecionados == ["10", "20", "30"]
    # ttk estica as colunas: a sobra da largura vai IGUAL para cada uma.
    qtbot.waitExposed(dlg)
    largura0, largura1 = dlg.tree.columnWidth(0), dlg.tree.columnWidth(1)
    assert largura0 >= 400 and largura0 - largura1 == 400 - 150
    assert largura0 + largura1 == dlg.tree.viewport().width()
    item = dlg.tree.topLevelItem(0)
    assert item.textAlignment(1) & Qt.AlignmentFlag.AlignHCenter
    assert dlg.tree.headerItem().text(0) == "Descrição"
    # sem largura informada: 120, o padrão do código antigo (e a mesma sobra)
    outro = _tabela(qtbot)
    qtbot.waitExposed(outro)
    assert outro.tree.columnWidth(0) == outro.tree.columnWidth(1) >= 120


def test_tabela_confirmar_sem_nada_avisa_e_nao_fecha(qt_interface, qtbot, monkeypatch):
    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: avisos.append(a[1:3]))
    escolhas = []
    dlg = _tabela(qtbot, ao_confirmar=escolhas.append)
    dlg.botao_confirmar.click()
    assert avisos == [("Aviso", "Selecione ao menos um item.")]
    assert escolhas == [] and dlg.isVisible()


def test_tabela_cancelar_e_sem_cancelar(qt_interface, qtbot):
    escolhas = []
    dlg = _tabela(qtbot, ao_confirmar=escolhas.append)
    dlg.botao_cancelar.click()
    assert escolhas == [] and not dlg.isVisible()
    sem = _tabela(qtbot, com_cancelar=False, modal=False)
    assert sem.botao_cancelar is None
    assert sem.windowModality() == Qt.WindowModality.NonModal


# --- Esc nunca joga fora uma seleção feita à mão (revisão final) ----------------
# O Tk não tinha tecla nenhuma nestas janelas; no Qt o Esc fecharia, e a lista
# pode ter dezenas de itens marcados um a um. O "X" continua cancelando.

def test_selecao_multipla_esc_nao_descarta_e_o_x_cancela(qt_interface, qtbot):
    escolhas = []
    dlg = qd.SelecaoMultiplaDialog(None, itens=["A", "B"], ao_confirmar=escolhas.append)
    qtbot.addWidget(dlg)
    dlg.listbox.item(1).setSelected(True)
    qtbot.keyClick(dlg, Qt.Key.Key_Escape)
    qtbot.keyClick(dlg.listbox, Qt.Key.Key_Escape)
    assert dlg.isVisible() and dlg.listbox.item(1).isSelected()
    dlg.close()
    assert escolhas == [] and not dlg.isVisible()


def test_tabela_esc_nao_descarta_e_o_x_cancela(qt_interface, qtbot):
    escolhas = []
    dlg = _tabela(qtbot, ao_confirmar=escolhas.append)
    qtbot.keyClick(dlg, Qt.Key.Key_Escape)
    qtbot.keyClick(dlg.tree, Qt.Key.Key_Escape)
    assert dlg.isVisible()
    dlg.close()
    assert escolhas == [] and not dlg.isVisible()


def test_selecao_com_caixas_esc_nao_descarta_e_o_x_cancela(qt_interface, qtbot):
    from sigft.app_qt.widgets.dialogs import SelecaoComCaixasDialog

    dlg = SelecaoComCaixasDialog(None, titulo="Selecione as Fichas", mensagem="Marque:",
                                 itens=["PMIB-1", "PMIB-2"])
    qtbot.addWidget(dlg)
    dlg.show()
    dlg.lista.item(0).setCheckState(Qt.CheckState.Checked)
    qtbot.keyClick(dlg, Qt.Key.Key_Escape)
    assert dlg.isVisible() and dlg.selecionados() == ["PMIB-1"]
    dlg.close()
    assert dlg.result() == dlg.DialogCode.Rejected and not dlg.isVisible()


def test_tabela_de_dataframe_usa_o_indice(qt_interface, qtbot):
    pd = pytest.importorskip("pandas")
    if not isinstance(getattr(pd, "DataFrame", None), type):
        pytest.skip("pandas dublado pelo conftest")
    df = pd.DataFrame({"A": ["x", "y", "z"], "B": [1, 2, 3]}, index=[5, 7, 9])
    escolhas = []
    dlg = qd.TabelaSelecaoDialog.de_dataframe(None, df[df["B"] > 1], ao_confirmar=escolhas.append)
    qtbot.addWidget(dlg)
    assert dlg.tree.topLevelItemCount() == 2
    assert dlg.tree.topLevelItem(0).text(0) == "y"
    dlg.tree.topLevelItem(1).setSelected(True)
    dlg.botao_confirmar.click()
    assert escolhas == [["9"]]


def test_tabela_de_dataframe_com_um_dublê(qt_interface, qtbot):
    # Independe do pandas real: só usa `columns` e `iterrows()`.
    class Linha(list):
        def to_numpy(self):
            return SimpleNamespace(tolist=lambda: list(self))

    df = SimpleNamespace(columns=["A", "B"],
                         iterrows=lambda: iter([(3, Linha(["p", 1.5])), (8, Linha(["q", None]))]))
    dlg = qd.TabelaSelecaoDialog.de_dataframe(None, df, preselecionar_tudo=True)
    qtbot.addWidget(dlg)
    assert dlg.selecionados == ["3", "8"]
    assert [dlg.tree.topLevelItem(1).text(i) for i in range(2)] == ["q", "None"]


# --- ArquivosTravadosDialog e perguntar_arquivos_travados ------------------

ITENS = [("_STATUS_PMIB.xlsx", "está aberto no Excel", "Feche-o."),
         ("mapa.xlsx", "é somente leitura", "Tire o atributo.")]


@pytest.mark.parametrize("momento", ["antes", "depois", "na_hora"])
def test_travados_mostra_os_textos_do_momento(qt_interface, qtbot, momento):
    evento, resultado = threading.Event(), {}
    dlg = qd.ArquivosTravadosDialog(None, itens=ITENS, momento=momento,
                                    evento_espera=evento, resultado=resultado)
    qtbot.addWidget(dlg)
    textos = TEXTOS_TRAVADOS[momento]
    assert dlg.windowTitle() == textos["titulo"]
    assert dlg.botao_repetir.text() == textos["repetir"]
    assert dlg.botao_seguir.text() == textos["seguir"]
    rotulos = [r.text() for r in dlg.findChildren(type(dlg.rotulo_explicacao))]
    assert textos["explicacao"] in rotulos and textos["rodape"] in rotulos
    assert "_STATUS_PMIB.xlsx" in rotulos
    assert "Motivo: está aberto no Excel. Feche-o." in rotulos


def test_travados_repetir_seguir_e_x(qt_interface, qtbot):
    for acao, esperado in (("repetir", True), ("seguir", False), ("fechar", False)):
        evento, resultado = threading.Event(), {}
        dlg = qd.ArquivosTravadosDialog(None, itens=ITENS, momento="antes",
                                        evento_espera=evento, resultado=resultado)
        qtbot.addWidget(dlg)
        dlg.show()
        {"repetir": dlg.botao_repetir.click, "seguir": dlg.botao_seguir.click,
         "fechar": dlg.close}[acao]()
        assert resultado == {"repetir": esperado}, acao
        assert evento.is_set()


class Tela(DialogosDeEspera, QWidget):
    pass


def _falha(nome, motivo, o_que_fazer):
    return SimpleNamespace(nome=nome, diagnostico=SimpleNamespace(motivo=motivo, o_que_fazer=o_que_fazer))


def test_perguntar_arquivos_travados_do_worker(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    respostas = []
    falhas = [_falha(*item) for item in ITENS]
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_arquivos_travados(falhas, "depois")),
                         daemon=True)
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.ArquivosTravadosDialog)) == 1, timeout=2000)
    dlg = _abertos(qd.ArquivosTravadosDialog)[0]
    assert dlg.itens == ITENS
    assert dlg.thread() is tela.thread()
    dlg.botao_repetir.click()
    t.join(3)
    assert respostas == [True]


def test_perguntar_arquivos_travados_esc_e_seguir(qt_interface, qtbot):
    from PySide6.QtTest import QTest

    tela = Tela()
    qtbot.addWidget(tela)
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(
        tela.perguntar_arquivos_travados([_falha(*ITENS[0])], "na_hora")), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.ArquivosTravadosDialog)) == 1, timeout=2000)
    QTest.keyClick(_abertos(qd.ArquivosTravadosDialog)[0], Qt.Key.Key_Escape)
    t.join(3)
    assert respostas == [False]


def test_travados_medidas_do_customtkinter(qt_interface, qtbot, folha_do_app):
    evento, resultado = threading.Event(), {}
    dlg = qd.ArquivosTravadosDialog(None, itens=ITENS, momento="antes",
                                    evento_espera=evento, resultado=resultado)
    qtbot.addWidget(dlg)
    assert (dlg.width(), dlg.height()) == (620, 380)
    for botao in (dlg.botao_repetir, dlg.botao_seguir):
        assert (botao.width(), botao.height()) == (170, 40)
    assert dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert dlg.windowModality() == Qt.WindowModality.NonModal


def test_falha_ao_abrir_a_lista_de_travados_solta_o_worker(qt_interface, qtbot, monkeypatch, capsys):
    def quebrado(*a, **k):
        raise RuntimeError("falha de construcao")

    monkeypatch.setattr(qd, "ArquivosTravadosDialog", quebrado)
    tela = Tela()
    qtbot.addWidget(tela)
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(
        tela.perguntar_arquivos_travados([_falha(*ITENS[0])], "antes")), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: not t.is_alive(), timeout=3000)
    assert respostas == [False]  # resposta segura: Seguir
    assert "falha de construcao" in capsys.readouterr().err


def test_travados_minimiza_e_e_janela_independente(qt_interface, qtbot):
    # O original manda a pessoa ir ao Excel e "minimizar esta janela, se quiser":
    # CTkToplevel sem transient() -- janela própria, com minimizar, sempre por cima.
    tela = Tela()
    qtbot.addWidget(tela)
    dlg = qd.ArquivosTravadosDialog(tela, itens=ITENS, momento="antes",
                                    evento_espera=threading.Event(), resultado={})
    qtbot.addWidget(dlg)
    flags = dlg.windowFlags()
    assert flags & Qt.WindowType.WindowMinimizeButtonHint
    assert flags & Qt.WindowType.WindowCloseButtonHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert dlg.parent() is None and dlg.dono is tela  # não "possuída" pela janela principal
    assert dlg.windowModality() == Qt.WindowModality.NonModal


def test_perguntar_arquivos_travados_da_thread_da_interface(qt_interface, qtbot):
    # Sem worker (um clique que grava direto): `exec()`, que bloqueia sem parar o
    # laço de eventos. Aqui a janela fica modal -- ver o relatório da E3.1.
    from PySide6.QtCore import QTimer

    tela = Tela()
    qtbot.addWidget(tela)

    def clicar():
        _abertos(qd.ArquivosTravadosDialog)[0].botao_repetir.click()

    QTimer.singleShot(50, clicar)
    assert tela.perguntar_arquivos_travados([_falha(*ITENS[0])], "na_hora") is True


def test_esperar_volta_quando_a_janela_e_escondida_por_fora(qt_interface, qtbot):
    from PySide6.QtCore import QTimer

    dlg = qd.SelecaoMultiplaDialog(None, itens=["a"], modal=True)
    qtbot.addWidget(dlg)
    QTimer.singleShot(50, dlg.hide)
    assert dlg.esperar() is None

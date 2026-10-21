"""`FileQueueList` da interface Qt: mesma API da interface antiga (E3.1)."""
import pytest

from sigft.app_qt import estilo
from sigft.app_qt.widgets import pickers


@pytest.fixture
def folha_do_app(qapp):
    """A folha do app aplicada, como em produção (sem ela os botões medem outra coisa)."""
    from sigft.app_qt import estilo as _estilo
    anterior = qapp.styleSheet()
    qapp.setStyleSheet(_estilo.folha_de_estilo())
    yield
    qapp.setStyleSheet(anterior)


def _fila(qtbot, respostas, **kw):
    respostas = iter(respostas)
    avisos = []
    fila = pickers.FileQueueList(chave="upload_conditions.fichas", rotulo="Planilhas PMIB Selecionadas",
                                 ao_mudar=lambda *a: avisos.append(a),
                                 dialog_fn=lambda **k: next(respostas), **kw)
    qtbot.addWidget(fila)
    qtbot.addWidget(fila.label_contador)
    return fila, avisos


def test_adicionar_sem_repetir_e_contador(qt_interface, qtbot):
    fila, avisos = _fila(qtbot, [("/a/F1.xlsx", "/a/F2.xlsx"), ("/a/F2.xlsx", "/b/F3.xlsx")])
    assert fila.label_contador.text() == "Planilhas PMIB Selecionadas (0)"
    fila.botao_adicionar.click()
    fila.botao_adicionar.click()
    assert fila.arquivos == ["/a/F1.xlsx", "/a/F2.xlsx", "/b/F3.xlsx"]
    assert fila.label_contador.text() == "Planilhas PMIB Selecionadas (3)"
    # o aviso conta os ESCOLHIDOS (2), não os novos -- como na interface antiga
    assert avisos == [("adicionou", 2, 2), ("adicionou", 2, 3)]
    assert fila.listbox.item(0).text() == estilo.mono(pickers.PREFIXO_ITEM + "F1.xlsx")


def test_cancelar_o_dialogo_nao_muda_nada(qt_interface, qtbot):
    fila, avisos = _fila(qtbot, [()])
    fila.botao_adicionar.click()
    assert fila.arquivos == [] and avisos == []


def test_remover_selecionados_de_tras_para_frente(qt_interface, qtbot):
    fila, avisos = _fila(qtbot, [("/1.xlsx", "/2.xlsx", "/3.xlsx", "/4.xlsx")])
    fila.botao_adicionar.click()
    fila.listbox.item(1).setSelected(True)
    fila.listbox.item(3).setSelected(True)
    fila.botao_remover.click()
    assert fila.arquivos == ["/1.xlsx", "/3.xlsx"]
    assert avisos[-1] == ("removeu", 2, 2)
    assert fila.label_contador.text().endswith("(2)")
    # sem seleção, remover não faz nada nem avisa
    fila.botao_remover.click()
    assert len(avisos) == 2


def test_limpar_definir_e_copia(qt_interface, qtbot):
    fila, avisos = _fila(qtbot, [])
    fila.definir(["/x.xlsx", "/y.xlsx"])
    assert fila.label_contador.text().endswith("(2)") and avisos == []
    copia = fila.arquivos
    copia.append("/z")
    assert fila.arquivos == ["/x.xlsx", "/y.xlsx"]
    fila.botao_limpar.click()
    assert fila.arquivos == [] and avisos == [("limpou", 0, 0)]
    assert fila.listbox.count() == 0


def test_selecao_estendida_e_cores_da_lista(qt_interface, qtbot):
    from PySide6.QtWidgets import QAbstractItemView

    fila, _ = _fila(qtbot, [], texto_adicionar="Adicionar JSONs")
    assert fila.listbox.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert fila.botao_adicionar.text() == "Adicionar JSONs"
    folha = fila.listbox.styleSheet()
    # 2026-10-20: fundo, texto e seleção são os do QListWidget da folha do tema
    # (eram #1E1E1E e o primary escritos aqui).
    assert "background" not in folha.replace("background: transparent", "")
    assert "color" not in folha
    # tk.Listbox("Segoe UI", 11): 11 PONTOS
    assert fila.listbox.font().pointSize() == 11


def test_medidas_iguais_as_do_interface_antiga(qt_interface, qtbot, folha_do_app):
    # Botões 140x28 (CTkButton padrão) empilhados com pady=5; coluna à direita
    # com padx=(10, 0); lista com padx=(5, 0) e pady=5.
    fila, _ = _fila(qtbot, [])
    fila.resize(600, 200)
    fila.show()
    qtbot.waitExposed(fila)
    b1, b2, b3 = fila.botao_adicionar, fila.botao_remover, fila.botao_limpar
    assert (b1.width(), b1.height()) == (140, 28)
    assert b2.y() - (b1.y() + b1.height()) == 10  # pady=5 dos dois
    assert b3.y() - (b2.y() + b2.height()) == 10
    assert b1.y() == 5
    assert fila.width() - (b1.x() + b1.width()) == 0
    assert fila.listbox.x() == 5 and fila.listbox.y() == 5
    assert fila.height() - (fila.listbox.y() + fila.listbox.height()) == 5

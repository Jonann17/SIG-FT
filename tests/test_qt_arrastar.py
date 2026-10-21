"""Arrastar o arquivo para o botão e os "Últimos arquivos" (2026-10-21, etapa 1b)."""
import os

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QPushButton

from sigft.app import tokens
from sigft.app_qt import estilo, file_dialogs
from sigft.app_qt.widgets import arrastar, pickers
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import prefs

COPIAR = Qt.DropAction.CopyAction
ESQUERDO = Qt.MouseButton.LeftButton
NADA = Qt.KeyboardModifier.NoModifier


def _mesmo(a, b):
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def _nao_abre(**_):
    raise AssertionError("o diálogo não devia abrir")


def _arrastar(widget, *caminhos, soltar=True):
    """Entra, move e (se `soltar`) solta `caminhos` em `widget`. Devolve (mover, soltar)."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(c)) for c in caminhos])
    QApplication.sendEvent(widget, QDragEnterEvent(QPoint(5, 5), COPIAR, mime, ESQUERDO, NADA))
    mover = QDragMoveEvent(QPoint(6, 6), COPIAR, mime, ESQUERDO, NADA)
    QApplication.sendEvent(widget, mover)
    solta = None
    if soltar:
        solta = QDropEvent(QPointF(6, 6), COPIAR, mime, ESQUERDO, NADA)
        QApplication.sendEvent(widget, solta)
    return mover, solta


@pytest.fixture
def planilha(tmp_path):
    caminho = tmp_path / "STATUS.xlsx"
    caminho.write_text("x", encoding="utf-8")
    return caminho


class _Selecionar:
    """O `selecionar_...` de uma tela, sem mudança nenhuma: só chama o diálogo."""

    def __init__(self, chave, varios=False):
        self.chave, self.varios, self.recebidos = chave, varios, []

    def __call__(self):
        funcao = file_dialogs.ask_open_files if self.varios else file_dialogs.ask_open_file
        self.recebidos.append(funcao(self.chave, "excel", dialog_fn=lambda **_: ""))


def test_soltar_no_botao_entrega_sem_dialogo(qt_interface, qtbot, planilha):
    botao = QPushButton("Selecionar")
    qtbot.addWidget(botao)
    selecionar = _Selecionar("t.status")
    botao.clicked.connect(selecionar)
    arrastar.aceitar_arquivo(botao, "t.status", (".xlsx",))
    mover, solta = _arrastar(botao, planilha)
    assert mover.isAccepted() and solta.isAccepted()
    assert len(selecionar.recebidos) == 1 and _mesmo(selecionar.recebidos[0], planilha)
    assert botao.property("arrasto") == ""
    assert len(prefs.recentes("t.status")) == 1


def test_extensao_errada_fica_vermelho_e_nao_aceita(qt_interface, qtbot, tmp_path):
    pdf = tmp_path / "manual.pdf"
    pdf.write_text("x", encoding="utf-8")
    botao = QPushButton("Selecionar")
    qtbot.addWidget(botao)
    selecionar = _Selecionar("t.status")
    botao.clicked.connect(selecionar)
    arrastar.aceitar_arquivo(botao, "t.status", (".xlsx",))
    mover, _ = _arrastar(botao, pdf, soltar=False)
    assert botao.property("arrasto") == arrastar.RECUSADO
    assert not mover.isAccepted()
    QApplication.sendEvent(botao, QDragLeaveEvent())
    assert botao.property("arrasto") == ""
    _arrastar(botao, pdf)                 # soltar mesmo assim
    assert selecionar.recebidos == []


def test_dois_arquivos_so_onde_aceita_varios(qt_interface, qtbot, tmp_path):
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    for p in (a, b):
        p.write_text("x", encoding="utf-8")
    um = QPushButton("um")
    varios = QPushButton("varios")
    for botao in (um, varios):
        qtbot.addWidget(botao)
    sel_um, sel_varios = _Selecionar("t.um"), _Selecionar("t.varios", varios=True)
    um.clicked.connect(sel_um)
    varios.clicked.connect(sel_varios)
    arrastar.aceitar_arquivo(um, "t.um", (".xlsx",))
    arrastar.aceitar_arquivo(varios, "t.varios", (".xlsx",), varios=True)
    _arrastar(um, a, b)
    _arrastar(varios, a, b)
    assert sel_um.recebidos == []
    assert len(sel_varios.recebidos[0]) == 2


def test_entrega_nao_sobra_se_a_tela_nao_pediu(qt_interface, qtbot, planilha):
    botao = QPushButton("x")                      # nenhum `clicked` ligado
    qtbot.addWidget(botao)
    arrastar.aceitar_arquivo(botao, "t.k", (".xlsx",)).receber([str(planilha)])
    assert file_dialogs.pendente("t.k") is None


def test_menu_de_recentes_entrega_o_escolhido(qt_interface, qtbot, planilha):
    prefs.lembrar_recente("t.k", str(planilha))
    botao = QPushButton("x")
    qtbot.addWidget(botao)
    selecionar = _Selecionar("t.k")
    botao.clicked.connect(selecionar)
    receptor = arrastar.aceitar_arquivo(botao, "t.k", (".xlsx",), menu_de_contexto=True)
    assert botao.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    menu = arrastar.MenuDeRecentes(receptor)
    menu.aboutToShow.emit()
    assert [acao.text() for acao in menu.actions()] == ["STATUS.xlsx"]
    menu.actions()[0].trigger()
    assert len(selecionar.recebidos) == 1 and _mesmo(selecionar.recebidos[0], planilha)
    menu.deleteLater()


def test_menu_sem_recentes(qt_interface, qtbot):
    botao = QPushButton("x")
    qtbot.addWidget(botao)
    receptor = arrastar.aceitar_arquivo(botao, "t.nada", (".xlsx",))
    menu = arrastar.MenuDeRecentes(receptor)
    menu.aboutToShow.emit()
    assert [(a.text(), a.isEnabled()) for a in menu.actions()] == [(arrastar.TEXTO_SEM_RECENTES, False)]
    menu.deleteLater()


def test_linha_de_selecao_aceita_arrasto_e_mostra_a_seta(qt_interface, qtbot, planilha):
    avisos = []
    linha = pickers.FilePickerRow(chave="t.linha", categoria="excel", texto_botao="Selecionar",
                                  filetypes=[("Excel", "*.xlsx")], ao_escolher=avisos.append,
                                  dialog_fn=_nao_abre)
    qtbot.addWidget(linha)
    assert linha.seta_recentes.isHidden()        # sem recente: nada muda na linha
    _arrastar(linha, planilha)
    assert _mesmo(linha.valor, planilha)
    assert linha.botao.property("variante") == "primario"
    assert len(avisos) == 1
    assert not linha.seta_recentes.isHidden()


def test_linha_de_selecao_recusa_extensao(qt_interface, qtbot, tmp_path):
    pdf = tmp_path / "manual.pdf"
    pdf.write_text("x", encoding="utf-8")
    linha = pickers.FilePickerRow(chave="t.linha", categoria="excel", texto_botao="Selecionar",
                                  filetypes=[("Excel", "*.xlsx")], dialog_fn=_nao_abre)
    qtbot.addWidget(linha)
    _arrastar(linha, pdf, soltar=False)
    assert linha.botao.property("arrasto") == arrastar.RECUSADO
    QApplication.sendEvent(linha, QDragLeaveEvent())
    assert linha.valor is None


def test_fila_de_fichas_aceita_varios(qt_interface, qtbot, tmp_path):
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    for p in (a, b):
        p.write_text("x", encoding="utf-8")
    fila = pickers.FileQueueList(chave="t.fila", filetypes=[("Excel", "*.xlsx")], dialog_fn=_nao_abre)
    qtbot.addWidget(fila)
    _arrastar(fila, a, b)
    assert [os.path.basename(c) for c in fila.arquivos] == ["a.xlsx", "b.xlsx"]


class _TelaComBotao(ModuleFrame):
    ARRASTAVEIS = (arrastar.Arrastavel("btn", "t.tela", (".xlsx",)),)

    def _build_ui(self):
        self.recebidos = []
        self.btn = QPushButton("Selecionar")
        self.content_layout.addWidget(self.btn)
        self.btn.clicked.connect(self._sel)

    def _sel(self):
        self.recebidos.append(file_dialogs.ask_open_file("t.tela", "excel", dialog_fn=lambda **_: ""))


def test_module_frame_liga_os_arrastaveis(qt_interface, qtbot, planilha):
    tela = _TelaComBotao(titulo="x")
    qtbot.addWidget(tela)
    tela.receptores_de_arquivo["btn"].receber([str(planilha)])
    assert tela.recebidos == [str(planilha)]
    assert arrastar.DICA_ARRASTAR in tela.btn.toolTip()


def test_arrastavel_com_nome_errado_falha_alto(qt_interface, qtbot):
    class Errada(_TelaComBotao):
        ARRASTAVEIS = (arrastar.Arrastavel("btn_que_nao_existe", "t.tela", (".xlsx",)),)

    with pytest.raises(AttributeError, match="btn_que_nao_existe"):
        Errada(titulo="x")


def test_folha_pinta_aceito_e_recusado():
    for tema in ("escuro", "claro"):
        p = tokens.paleta(tema)
        folha = estilo.folha_de_estilo(tema)
        assert ('QPushButton[arrasto="recusado"], QListWidget[arrasto="recusado"] '
                f'{{ border: 1px solid {p["perigo"]}; color: {p["perigo"]}; }}') in folha
        assert ('QPushButton[arrasto="aceito"], QListWidget[arrasto="aceito"] '
                f'{{ border: 1px solid {p["primaria"]}; }}') in folha


def test_recente_que_sumiu_depois_do_menu_aberto_nao_entrega(qt_interface, qtbot, planilha):
    """O arquivo some entre abrir o menu e clicar: a tela não recebe um caminho morto."""
    prefs.lembrar_recente("t.k", str(planilha))
    botao = QPushButton("x")
    qtbot.addWidget(botao)
    selecionar = _Selecionar("t.k")
    botao.clicked.connect(selecionar)
    menu = arrastar.MenuDeRecentes(arrastar.aceitar_arquivo(botao, "t.k", (".xlsx",)))
    menu.aboutToShow.emit()
    planilha.unlink()
    menu.actions()[0].trigger()
    assert selecionar.recebidos == []
    assert file_dialogs.pendente("t.k") is None
    menu.deleteLater()

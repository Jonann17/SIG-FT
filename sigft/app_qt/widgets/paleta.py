"""Ctrl+K: a caixa de busca dos módulos e das ações (2026-10-21, etapa 1b).

Abre no meio da janela; filtra enquanto se digita (sem acento e sem caixa,
`catalogo.filtrar`); as setas andam na lista sem tirar o cursor do campo; Enter
ou clique escolhe, Esc fecha. A lista é `catalogo.comandos()`; quem faz cada
comando é `main.SIG_FT_App.executar_comando`.

Fecha sozinha quando perde o foco: é uma janela `Popup` (o Qt a fecha no clique
fora dela) e ouve o app ficar inativo (Alt+Tab para outro programa), que no
Windows não fecha popup por conta própria.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout,
)

from sigft.app.idioma import marcar, t
from sigft.app_qt import catalogo, estilo, icones

TEXTO_DICA = marcar("Buscar módulo ou ação")
TEXTO_VAZIO = marcar("Nada com esse nome.")
LARGURA = 560
ALTURA_LISTA = 320


class PaletaDeComandos(QDialog):
    escolheu = Signal(str)

    def __init__(self, parent, comandos) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("paleta")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(LARGURA)
        self._comandos = list(comandos)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText(t(TEXTO_DICA))
        self.campo.installEventFilter(self)
        self.campo.textChanged.connect(self._filtrar)
        lay.addWidget(self.campo)
        self.lista = QListWidget(objectName="lista_paleta")
        self.lista.setFixedHeight(ALTURA_LISTA)
        self.lista.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lista.itemClicked.connect(self._clicou)
        lay.addWidget(self.lista)
        self.vazio = QLabel(t(TEXTO_VAZIO))
        self.vazio.setProperty("papel", "legenda")
        lay.addWidget(self.vazio)
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._estado_do_app)
        self._filtrar("")

    def _filtrar(self, consulta: str) -> None:
        self.lista.clear()
        cor = estilo.cor_do_papel("texto")
        for comando in catalogo.filtrar(self._comandos, consulta):
            item = QListWidgetItem(icones.icone(comando.icone, cor), comando.texto)
            item.setData(Qt.ItemDataRole.UserRole, comando.chave)
            if comando.dica:
                item.setToolTip(comando.dica)
            if comando.bloqueado:
                # Como o botão do menu: apagado e fora do alcance das setas e do Enter.
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)
            self.lista.addItem(item)
        self.lista.setCurrentRow(next(iter(self._linhas_que_se_escolhem()), -1))
        self.vazio.setVisible(self.lista.count() == 0)

    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 -- nome do Qt
        if obj is self.campo and evento.type() == QEvent.Type.KeyPress:
            tecla = evento.key()
            if tecla in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self._mover(1 if tecla == Qt.Key.Key_Down else -1)
                return True
            if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.escolher_atual()
                return True
        return super().eventFilter(obj, evento)

    def _linhas_que_se_escolhem(self) -> list[int]:
        return [i for i in range(self.lista.count())
                if self.lista.item(i).flags() & Qt.ItemFlag.ItemIsEnabled]

    def _mover(self, passo: int) -> None:
        """A próxima linha que se escolhe no sentido do `passo`; no fim, fica."""
        atual = self.lista.currentRow()
        linhas = self._linhas_que_se_escolhem()
        adiante = [i for i in linhas if i > atual] if passo > 0 else [i for i in reversed(linhas) if i < atual]
        if adiante:
            self.lista.setCurrentRow(adiante[0])

    def _clicou(self, item) -> None:
        self.lista.setCurrentItem(item)
        self.escolher_atual()

    def _estado_do_app(self, estado) -> None:
        if estado != Qt.ApplicationState.ApplicationActive and self.isVisible():
            self.reject()

    def escolher_atual(self) -> None:
        """Fecha a caixa e SÓ ENTÃO avisa a escolha: a ação que abre janela
        (Chaves de API) já não encontra o popup segurando teclado e mouse."""
        item = self.lista.currentItem()
        if item is None or not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        chave = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        self.escolheu.emit(chave)

    def abrir_sobre(self, janela) -> None:
        """No meio da `janela`, a um quinto da altura, com o cursor no campo."""
        self.adjustSize()
        geometria = janela.frameGeometry()
        self.move(geometria.x() + (geometria.width() - self.width()) // 2,
                  geometria.y() + geometria.height() // 5)
        self.show()
        self.activateWindow()
        self.campo.setFocus()

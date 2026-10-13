"""Janelas que param o robô à espera da pessoa. Mesmos textos de hoje.

Regra que não pode ser esquecida: fechar no "X" SEMPRE solta o worker, com a
resposta mais segura (continuar o login; não repetir a gravação). Sem isso, a
thread do robô fica presa em `Event.wait()` para sempre.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from sigft.app.textos_dialogos import MSG_EXCEL_BLOQUEADO, TEXTO_CONTINUAR


class _DialogoDeAcaoManual(QDialog):
    def __init__(self, parent, *, titulo: str, mensagem: str, largura: int, altura: int) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setFixedSize(largura, altura)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._decidido = False
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(20, 20, 20, 20)
        self.rotulo = QLabel(mensagem)
        self.rotulo.setWordWrap(True)
        self.rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo.setStyleSheet("font-size: 13px;")
        self.layout_principal.addWidget(self.rotulo, 1)

    def _ao_fechar_sem_decidir(self) -> None:
        raise NotImplementedError

    def reject(self) -> None:
        """Esc (e qualquer `reject()`) esconde o diálogo SEM passar pelo
        `closeEvent`; sem isto o worker ficaria preso. Só responde se ainda
        ninguém decidiu -- os botões já responderam antes de chamar `reject()`."""
        if not self._decidido:
            self._ao_fechar_sem_decidir()
        super().reject()

    def closeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if not self._decidido:
            self._ao_fechar_sem_decidir()
        super().closeEvent(evento)


class PausaLoginDialog(_DialogoDeAcaoManual):
    """"Ação Manual Necessária" com um botão: continuar a automação."""

    def __init__(self, parent, *, mensagem: str, evento_espera, texto_botao: str = TEXTO_CONTINUAR) -> None:
        super().__init__(parent, titulo="Ação Manual Necessária", mensagem=mensagem,
                         largura=450, altura=250)
        self._evento = evento_espera
        self.botao = QPushButton(texto_botao)
        self.botao.setMinimumHeight(45)
        self.botao.setProperty("variante", "primario")
        self.botao.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.botao.clicked.connect(self.liberar)
        self.layout_principal.addWidget(self.botao, 0, Qt.AlignmentFlag.AlignHCenter)

    def liberar(self) -> None:
        self._decidido = True
        self._evento.set()
        self.accept()

    def _ao_fechar_sem_decidir(self) -> None:
        self._decidido = True
        self._evento.set()


class RetryLockDialog(_DialogoDeAcaoManual):
    """"Arquivo Bloqueado": Tentar Novamente × Ignorar e Continuar (chave "retry")."""

    def __init__(self, parent, *, mensagem: str = MSG_EXCEL_BLOQUEADO, evento_espera, resultado: dict) -> None:
        super().__init__(parent, titulo="Arquivo Bloqueado", mensagem=mensagem,
                         largura=450, altura=200)
        self._evento = evento_espera
        self._resultado = resultado
        linha = QHBoxLayout()
        self.botao_repetir = QPushButton("Tentar Novamente")
        self.botao_repetir.setProperty("variante", "primario")
        self.botao_cancelar = QPushButton("Ignorar e Continuar")
        self.botao_cancelar.setProperty("variante", "contorno")
        for botao in (self.botao_repetir, self.botao_cancelar):
            botao.setFixedSize(150, 40)
            linha.addWidget(botao)
        self.botao_repetir.clicked.connect(self.repetir)
        self.botao_cancelar.clicked.connect(self.cancelar)
        self.layout_principal.addLayout(linha)

    def _responder(self, repetir: bool) -> None:
        self._decidido = True
        self._resultado["retry"] = repetir
        self._evento.set()

    def repetir(self) -> None:
        self._responder(True)
        self.accept()

    def cancelar(self) -> None:
        self._responder(False)
        self.reject()

    def _ao_fechar_sem_decidir(self) -> None:
        self._responder(False)


class SelecaoComCaixasDialog(QDialog):
    """Lista com caixas de marcar + "Todos" + "CONFIRMAR".

    É a janela de seleção de fichas da Aplicação LMR (450x600). A lista é um
    QListWidget: desenha só as linhas visíveis, ao contrário de um widget por
    ficha -- com centenas de PMIBs a diferença aparece.
    """

    def __init__(self, parent, *, titulo: str, mensagem: str, itens: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(450, 600)
        layout = QVBoxLayout(self)
        rotulo = QLabel(mensagem)
        rotulo.setStyleSheet("font-size: 14px; font-weight: bold;")
        rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(rotulo)
        self.lista = QListWidget()
        for texto in itens:
            item = QListWidgetItem(texto)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.lista.addItem(item)
        layout.addWidget(self.lista, 1)
        linha = QHBoxLayout()
        self.botao_todos = QPushButton("Todos")
        self.botao_todos.setProperty("variante", "neutro")
        self.botao_todos.setFixedWidth(80)
        self.botao_todos.clicked.connect(self._marcar_todos)
        self.botao_confirmar = QPushButton("CONFIRMAR")
        self.botao_confirmar.setProperty("variante", "acento")
        self.botao_confirmar.setStyleSheet("color: #161616;")
        self.botao_confirmar.setFixedWidth(150)
        self.botao_confirmar.clicked.connect(self.accept)
        linha.addWidget(self.botao_todos)
        linha.addStretch()
        linha.addWidget(self.botao_confirmar)
        layout.addLayout(linha)

    def _marcar_todos(self) -> None:
        for i in range(self.lista.count()):
            self.lista.item(i).setCheckState(Qt.CheckState.Checked)

    def selecionados(self) -> list[str]:
        return [self.lista.item(i).text() for i in range(self.lista.count())
                if self.lista.item(i).checkState() == Qt.CheckState.Checked]

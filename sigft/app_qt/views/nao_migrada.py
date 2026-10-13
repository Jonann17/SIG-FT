"""Lugar-tenente das telas que ainda não foram migradas para Qt."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TelaNaoMigrada(QWidget):
    def __init__(self, nome: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tela")
        layout = QVBoxLayout(self)
        self.mensagem = QLabel(
            f"A tela \"{nome}\" ainda não foi migrada para a interface nova.\n"
            "Use a interface antiga (python frontend.py --ctk) para ela.")
        self.mensagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mensagem.setStyleSheet("font-size: 16px; color: #B3B3B3;")
        layout.addWidget(self.mensagem)


class TelaComErro(QWidget):
    """A tela existe mas não montou. Mostra o porquê em vez de sumir."""

    def __init__(self, nome: str, erro: BaseException, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tela")
        # O `--smoke` lê o motivo (com a pilha) daqui para o relatório do Release.
        self.erro = erro
        layout = QVBoxLayout(self)
        self.mensagem = QLabel(
            f"A tela \"{nome}\" não conseguiu abrir.\n\n{type(erro).__name__}: {erro}\n\n"
            "O detalhe está em Documentos\\SIG-FT\\logs\\sigft.log.")
        self.mensagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mensagem.setWordWrap(True)
        self.mensagem.setStyleSheet("font-size: 15px; color: #E0E0E0;")
        layout.addWidget(self.mensagem)

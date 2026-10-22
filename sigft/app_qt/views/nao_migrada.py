"""O que aparece no lugar de uma tela que não existe ou que não montou."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from sigft.app.idioma import t


class TelaNaoMigrada(QWidget):
    """Uma chave do menu sem fábrica em `TELAS`. Desde a E4.10 todas as telas
    estão registradas: isto só aparece se uma sair do registro por engano."""

    def __init__(self, nome: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tela")
        layout = QVBoxLayout(self)
        self.mensagem = QLabel(
            t("A tela \"{nome}\" não está disponível nesta versão do SIG-FT.", nome=nome))
        self.mensagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mensagem.setProperty("papel", "legenda")
        self.mensagem.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.mensagem)


class TelaComErro(QWidget):
    """A tela existe mas não montou. Mostra o porquê em vez de sumir."""

    def __init__(self, nome: str, erro: BaseException, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tela")
        # O `--smoke` lê o motivo (com a pilha) daqui para o relatório do Release.
        self.erro = erro
        layout = QVBoxLayout(self)
        self.mensagem = QLabel(t(
            "A tela \"{nome}\" não conseguiu abrir.\n\n{erro}\n\n"
            "O detalhe está em Documentos\\SIG-FT\\logs\\sigft.log. "
            "Mande esse arquivo para quem cuida do SIG-FT.",
            nome=nome, erro=f"{type(erro).__name__}: {erro}"))
        self.mensagem.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.mensagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mensagem.setWordWrap(True)
        self.mensagem.setStyleSheet("font-size: 15px;")
        layout.addWidget(self.mensagem)

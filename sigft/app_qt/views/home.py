"""A Home em Qt: cabeçalho, barra de botões e um card clicável por módulo.

Aparência aprovada no protótipo de 2026-10-07: cards compactos (a descrição
ocupa a largura do card), ícones em preto e branco, espaçamento de hoje.
Os painéis da barra (Atividades, Modelos de IA, Gastos, Chaves, Atualizações)
migram no plano da Etapa 6; até lá cada botão avisa isso.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from sigft.app_qt import catalogo
from sigft.app_qt.estilo import mono

BARRA = [
    ("atividades", "\U0001F4CB  Atividades do dia", "acento"),
    ("modelos", "\U0001F916  Modelos de IA", None),
    ("gastos", "\U0001F4B0  Gastos de IA", None),
    ("chaves", "\U0001F511  Chaves de API", "neutro"),
    ("atualizacoes", "\U0001F504  Atualizações", "neutro"),
]
TEXTO_CANAL_TESTES = "Versões de teste"


class _Card(QFrame):
    def __init__(self, alvo, titulo, descricao, ao_clicar) -> None:
        super().__init__(objectName="card")
        self._alvo = alvo
        self._ao_clicar = ao_clicar
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(QLabel(titulo, objectName="card_titulo"))
        desc = QLabel(descricao, objectName="card_desc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        for rotulo in self.findChildren(QLabel):
            rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mousePressEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if evento.button() == Qt.MouseButton.LeftButton:
            self._ao_clicar(self._alvo)
        super().mousePressEvent(evento)


class HomeView(QScrollArea):
    def __init__(self, parent=None, controller=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWidgetResizable(True)
        self.setObjectName("conteudo")
        corpo = QWidget(objectName="conteudo")
        layout = QVBoxLayout(corpo)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(6)
        layout.addWidget(QLabel("SIG-FT", objectName="titulo_home"))
        layout.addWidget(QLabel("Sistema Integrado de Gestão de Fichas Técnicas - GE Vernova",
                                objectName="subtitulo_home"))
        layout.addSpacing(30)
        layout.addWidget(QLabel("Clique num módulo abaixo para abri-lo. Os botões desta barra "
                                "abrem painéis em janela, para a Home ficar limpa.",
                                objectName="texto_simples"))
        layout.addSpacing(6)
        layout.addLayout(self._barra())
        layout.addSpacing(10)
        layout.addLayout(self._cards())
        layout.addStretch()
        self.setWidget(corpo)

    def _barra(self) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(10)
        self.botoes_barra: dict[str, QPushButton] = {}
        for chave, texto, variante in BARRA:
            botao = QPushButton(mono(texto))
            botao.setProperty("barra", True)
            if variante:
                botao.setProperty("variante", variante)
            botao.clicked.connect(lambda _=False, t=texto: self._painel_em_migracao(t))
            self.botoes_barra[chave] = botao
            linha.addWidget(botao)
        self.caixa_canal_testes = QCheckBox(TEXTO_CANAL_TESTES)
        try:
            from sigft.services import updater
            self.caixa_canal_testes.setChecked(bool(updater.canal_testes_ligado()))
        except Exception:  # noqa: BLE001 -- preferência é conveniência
            pass
        self.caixa_canal_testes.toggled.connect(self._lembrar_canal_testes)
        linha.addWidget(self.caixa_canal_testes)
        linha.addStretch()
        return linha

    def _cards(self) -> QGridLayout:
        grade = QGridLayout()
        grade.setSpacing(12)
        self.cards: dict[str, _Card] = {}
        for indice, (alvo, titulo, descricao) in enumerate(catalogo.MODULOS):
            card = _Card(alvo, titulo, descricao, self._ir)
            self.cards[alvo] = card
            grade.addWidget(card, indice // 2, indice % 2)
        return grade

    def _ir(self, alvo: str) -> None:
        if self.controller is not None:
            self.controller.show_frame(alvo)

    def _lembrar_canal_testes(self, ligado: bool) -> None:
        try:
            from sigft.services import updater
            updater.ligar_canal_testes(bool(ligado))
        except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar o clique
            pass

    def _painel_em_migracao(self, texto: str) -> None:
        QMessageBox.information(self, "SIG-FT", f"O painel \"{texto.split('  ')[-1]}\" "
                                "ainda não foi migrado. Use a versão atual (python frontend.py).")

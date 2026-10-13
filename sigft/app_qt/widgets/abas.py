"""CTkTabview em Qt: botões segmentados centrados em cima de um quadro arredondado.

O QTabWidget põe as abas coladas à esquerda e o painel começa embaixo delas. O
CTkTabview não: a barra de botões (um CTkSegmentedButton) fica CENTRADA e
entra 18 px no quadro. Medidas do CustomTkinter (ctk_tabview.py) conferidas na
captura da E3.1:

* 10 px livres acima da barra (`_outer_spacing`); barra de 26 (`_button_height`;
  27 na tela);
* o quadro começa 18 px abaixo do topo (os 10 livres + os 8 da barra que
  ficam acima dele, `_outer_button_overhang`), cantos de 6;
* o conteúdo da aba começa em x=6, y=42 (36 da barra + 6 do canto) e termina
  6 px antes da borda de baixo e da direita;
* cada botão: texto + 14 px (6 do canto + 1 do rótulo do Tk, dos dois lados),
  borda de 3 na cor da barra -- o selecionado é o miolo azul dentro dela.

API como a do CTkTabview: `add(nome)` devolve o QWidget da aba (com um
QVBoxLayout), `tab(nome)`, `set(nome)`, `get()`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout,
    QWidget,
)

from sigft.app_qt import estilo

ESPACO_ACIMA = 10
ALTURA_BARRA = 26
SOBRA_DA_BARRA = 8          # quanto da barra fica ACIMA do quadro
# Na captura a barra tem 27 px, não 26 (o CTkSegmentedButton arredonda para
# cima). A grade continua com 26 -- o quadro e o conteúdo não andam --, e a barra
# desce 1 px a mais sobre o quadro.
ALTURA_BARRA_VISIVEL = 27
CANTO = 6
BORDA_BOTAO = 3
FOLGA_TEXTO = 7             # de cada lado do texto (estilo.FOLGA_TEXTO_BOTAO_CTK)


class Abas(QWidget):
    def __init__(self, parent=None, *, cor_fundo: str | None = None, cor_barra: str | None = None,
                 cor_selecionada: str = estilo.AZUL_CTK, cor_selecionada_hover: str = estilo.AZUL_CTK_HOVER,
                 cor_nao_selecionada: str | None = None, cor_nao_selecionada_hover: str | None = None,
                 tamanho_fonte: int = 13, ao_mudar=None) -> None:
        """Cores com os nomes do CTkTabview: `fg_color` (cor_fundo, padrão gray13 --
        use `estilo.FUNDO_QUADRO_INTERNO_CTK` quando o CTk a punha dentro de um
        CTkFrame de fundo padrão), `segmented_button_fg_color` (cor_barra, gray29),
        `segmented_button_selected_color`/`_hover_color`, e
        `segmented_button_unselected_color` (gray29) / `_hover_color` (gray41).
        `ao_mudar(nome)` é o `command` do CTkTabview: só no clique da pessoa."""
        super().__init__(parent)
        c = estilo.cinza_tk
        self.cor_fundo = c(cor_fundo or estilo.FUNDO_QUADRO_CTK)
        self.cor_barra = c(cor_barra or "gray29")
        self._cor_sel, self._cor_sel_hover = c(cor_selecionada), c(cor_selecionada_hover)
        self._cor_nao_sel = c(cor_nao_selecionada or "gray29")
        self._cor_nao_sel_hover = c(cor_nao_selecionada_hover or "gray41")
        self._tamanho_fonte = tamanho_fonte
        self._ao_mudar = ao_mudar
        self.abas: dict[str, QWidget] = {}
        self.botoes: dict[str, QPushButton] = {}

        # Grade de 4 linhas, como a do CTk: a barra ocupa as linhas 1-2 e o quadro
        # as 2-3 -- as duas se sobrepõem na linha 2 (18 px).
        grade = QGridLayout(self)
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setSpacing(0)
        grade.setRowMinimumHeight(0, ESPACO_ACIMA)
        grade.setRowMinimumHeight(1, SOBRA_DA_BARRA)
        grade.setRowMinimumHeight(2, ALTURA_BARRA - SOBRA_DA_BARRA)
        grade.setRowStretch(3, 1)

        self.quadro = QFrame(objectName="quadro_abas")
        self.quadro.setStyleSheet(
            f"#quadro_abas {{ background: {self.cor_fundo}; border-radius: {CANTO}px; }}")
        dentro = QVBoxLayout(self.quadro)
        # 24 = o que sobra da barra dentro do quadro (18) + o canto (6).
        dentro.setContentsMargins(CANTO, ALTURA_BARRA - SOBRA_DA_BARRA + CANTO, CANTO, CANTO)
        self.pilha = QStackedWidget()
        self.pilha.setStyleSheet("QStackedWidget { background: transparent; }")
        dentro.addWidget(self.pilha)
        grade.addWidget(self.quadro, 2, 0, 2, 1)

        self.barra = QFrame(objectName="barra_abas")
        self._linha = QHBoxLayout(self.barra)
        self._linha.setContentsMargins(0, 0, 0, 0)
        self._linha.setSpacing(0)
        self.barra.setFixedHeight(ALTURA_BARRA_VISIVEL)
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        grade.addWidget(self.barra, 1, 0, 2, 1, Qt.AlignmentFlag.AlignHCenter)
        self.barra.raise_()
        self._pintar_barra()

    # -- API do CTkTabview ---------------------------------------------------
    def add(self, nome: str) -> QWidget:
        if nome in self.abas:
            raise ValueError(f"Já existe uma aba chamada {nome!r}")
        aba = QWidget()
        aba.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.abas[nome] = aba
        self.pilha.addWidget(aba)

        botao = QPushButton(nome)
        botao.setCheckable(True)
        botao.setCursor(Qt.CursorShape.PointingHandCursor)
        botao.clicked.connect(lambda _=False, n=nome: self._clicou(n))
        self._grupo.addButton(botao)
        self.botoes[nome] = botao
        self._linha.addWidget(botao)
        if len(self.abas) == 1:
            botao.setChecked(True)
            self.pilha.setCurrentWidget(aba)
        self._pintar_barra()
        return aba

    def tab(self, nome: str) -> QWidget:
        return self.abas[nome]

    def set(self, nome: str) -> None:
        self.botoes[nome].setChecked(True)
        self.pilha.setCurrentWidget(self.abas[nome])

    def get(self) -> str:
        atual = self.pilha.currentWidget()
        return next((n for n, a in self.abas.items() if a is atual), "")

    # -- interno -------------------------------------------------------------
    def _clicou(self, nome: str) -> None:
        self.set(nome)
        if self._ao_mudar is not None:
            self._ao_mudar(nome)

    def _pintar_barra(self) -> None:
        """Folha da barra e largura de cada botão (texto + 14, como o CTkButton)."""
        r = CANTO
        self.barra.setStyleSheet(
            f"#barra_abas {{ background: {self.cor_barra}; border-radius: {r}px; }}"
            f" #barra_abas QPushButton {{ background: {self._cor_nao_sel}; color: {estilo.TEXTO_BOTAO_CTK};"
            f" border: {BORDA_BOTAO}px solid {self.cor_barra}; border-radius: 0;"
            f" padding: 0 {FOLGA_TEXTO - BORDA_BOTAO}px; font-size: {self._tamanho_fonte}px;"
            f" min-height: {ALTURA_BARRA_VISIVEL - 2 * BORDA_BOTAO}px;"
            f" max-height: {ALTURA_BARRA_VISIVEL - 2 * BORDA_BOTAO}px; }}"
            f" #barra_abas QPushButton:hover {{ background: {self._cor_nao_sel_hover}; }}"
            f" #barra_abas QPushButton:checked {{ background: {self._cor_sel}; border-radius: {r}px; }}"
            f" #barra_abas QPushButton:checked:hover {{ background: {self._cor_sel_hover}; }}"
            f" #barra_abas QPushButton:disabled {{ color: {estilo.cinza_tk('gray60')}; }}")
        botoes = list(self.botoes.values())
        for i, botao in enumerate(botoes):
            # Cantos de fora arredondados nos botões das pontas; o selecionado
            # (regra :checked acima) arredonda os quatro, como lá.
            cantos = []
            if i == 0:
                cantos += [f"border-top-left-radius: {r}px;", f"border-bottom-left-radius: {r}px;"]
            if i == len(botoes) - 1:
                cantos += [f"border-top-right-radius: {r}px;", f"border-bottom-right-radius: {r}px;"]
            botao.setStyleSheet(f"QPushButton:!checked {{ {' '.join(cantos)} }}" if cantos else "")
            botao.ensurePolished()
            botao.setFixedWidth(botao.fontMetrics().horizontalAdvance(botao.text()) + 2 * FOLGA_TEXTO)

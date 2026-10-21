"""CTkTabview em Qt: botões segmentados centrados em cima de um quadro arredondado.

O QTabWidget põe as abas coladas à esquerda e o painel começa embaixo delas. O
CTkTabview não: a barra de botões (um CTkSegmentedButton) fica CENTRADA e
entra 18 px no quadro. Medidas da interface antiga (ctk_tabview.py) conferidas na
captura da E3.1:

* 10 px livres acima da barra (`_outer_spacing`); barra de 26 (`_button_height`;
  27 na tela);
* o quadro começa 18 px abaixo do topo (os 10 livres + os 8 da barra que
  ficam acima dele, `_outer_button_overhang`), cantos de 6;
* o conteúdo da aba começa em x=6, y=43 (37 da barra + 6 do canto) e termina
  6 px antes da borda de baixo e da direita;
* cada botão: texto + 14 px (6 do canto + 1 do rótulo do Tk, dos dois lados),
  borda de 3 na cor da barra -- o selecionado é o miolo azul dentro dela.

API como a do CTkTabview: `add(nome)` devolve o QWidget da aba (com um
QVBoxLayout), `tab(nome)`, `set(nome)`, `get()`. Nome repetido em `add` ou
desconhecido em `tab`/`set` levanta ValueError, como lá.

Limites (o que o CTkTabview também não faz, ou que nenhuma tela usa):
* a largura de cada botão é fixada quando a aba é criada (texto + 14): mudar o
  texto ou a fonte depois não a refaz; não há `delete`, `rename` nem `insert`;
* sem teclado: os botões não pegam o foco nem trocam de aba por tecla, como na interface antiga;
* só `anchor="n"` (barra em cima, centrada) -- o único que as telas usam;
* a barra não encolhe: abas que não cabem na largura alargam o widget;
* a altura pedida é a da MAIOR aba (a do QStackedWidget), a não ser com
  `altura_da_escolhida=True`: aí é a da aba escolhida, como no CTkTabview, que
  só põe na grade a aba que aparece. Faz diferença onde as abas não esticam
  (num formulário que rola, como o do PDM).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QPushButton, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

from sigft.app_qt.widgets import blocos

ESPACO_ACIMA = 10
ALTURA_BARRA = 26
SOBRA_DA_BARRA = 8          # quanto da barra fica ACIMA do quadro
# Na captura a barra tem 27 px, não 26 (o CTkSegmentedButton arredonda para
# cima), e no Tk ela alarga a linha 2 da grade para 19: o quadro continua em 18,
# mas o conteúdo da aba começa em 43 (medido com winfo), não em 42.
ALTURA_BARRA_VISIVEL = 27
CANTO = 6
BORDA_BOTAO = 3
FOLGA_TEXTO = 7             # de cada lado do texto (estilo.FOLGA_TEXTO_BOTAO_CTK)


class Abas(QWidget):
    def __init__(self, parent=None, *, interno: bool = False, tamanho_fonte: int = 13,
                 ao_mudar=None, altura_da_escolhida: bool = False) -> None:
        """As cores são da folha (`_folha_telas` em `estilo.py`), desde 2026-10-20:
        quadro `fundo` -- ou `superficie` com `interno=True`, quando as abas vão
        dentro de um cartão --, barra e aba não escolhida `superficie_alta`,
        `borda` sob o mouse, escolhida `marca` com texto branco (7,6:1).
        `ao_mudar(nome)` é o `command` do CTkTabview: só no clique da pessoa.
        `altura_da_escolhida`: a altura pedida é a da aba escolhida (ver o topo)."""
        super().__init__(parent)
        self._tamanho_fonte = tamanho_fonte
        self._ao_mudar = ao_mudar
        self._altura_da_escolhida = altura_da_escolhida
        self.abas: dict[str, QWidget] = {}
        self.botoes: dict[str, QPushButton] = {}

        # Grade de 4 linhas, como a da interface antiga: a barra ocupa as linhas 1-2 e o quadro
        # as 2-3 -- as duas se sobrepõem na linha 2 (18 px).
        grade = QGridLayout(self)
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setSpacing(0)
        grade.setRowMinimumHeight(0, ESPACO_ACIMA)
        grade.setRowMinimumHeight(1, SOBRA_DA_BARRA)
        grade.setRowMinimumHeight(2, ALTURA_BARRA_VISIVEL - SOBRA_DA_BARRA)
        grade.setRowStretch(3, 1)

        self.quadro = QFrame(objectName="quadro_abas")
        if interno:
            self.quadro.setProperty("interno", True)
        dentro = QVBoxLayout(self.quadro)
        # 25 = o que sobra da barra dentro do quadro (19) + o canto (6).
        dentro.setContentsMargins(CANTO, ALTURA_BARRA_VISIVEL - SOBRA_DA_BARRA + CANTO, CANTO, CANTO)
        self.pilha = QStackedWidget()
        self.pilha.setStyleSheet("QStackedWidget { background: transparent; }")
        if altura_da_escolhida:
            self.pilha.currentChanged.connect(self._altura_da_aba_escolhida)
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
        aba = QWidget(objectName="aba_abas")
        # COM seletor: "background: transparent" solto vale para todos os
        # descendentes e apagava o fundo do cartão e dos botões da aba.
        aba.setStyleSheet("#aba_abas { background: transparent; }")
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.abas[nome] = aba
        self.pilha.addWidget(aba)

        botao = QPushButton(nome)
        blocos.sem_tecla(botao)   # os do CTkSegmentedButton nunca pegam o foco
        botao.setCheckable(True)
        botao.setCursor(Qt.CursorShape.PointingHandCursor)
        botao.clicked.connect(lambda _=False, n=nome: self._clicou(n))
        self._grupo.addButton(botao)
        self.botoes[nome] = botao
        self._linha.addWidget(botao)
        if len(self.abas) == 1:
            botao.setChecked(True)
            self.pilha.setCurrentWidget(aba)
        if self._altura_da_escolhida:
            self._altura_da_aba_escolhida()
        self._pintar_barra()
        return aba

    def tab(self, nome: str) -> QWidget:
        self._conferir(nome)
        return self.abas[nome]

    def set(self, nome: str) -> None:
        self._conferir(nome)
        self.botoes[nome].setChecked(True)
        self.pilha.setCurrentWidget(self.abas[nome])

    def get(self) -> str:
        atual = self.pilha.currentWidget()
        return next((n for n, a in self.abas.items() if a is atual), "")

    # -- interno -------------------------------------------------------------
    def _conferir(self, nome: str) -> None:
        if nome not in self.abas:
            raise ValueError(f"Não existe aba chamada {nome!r}")

    def _altura_da_aba_escolhida(self, *_):
        """As abas que não aparecem não pedem altura (política `Ignored`): a
        pilha fica com a altura da escolhida, como o CTkTabview."""
        atual = self.pilha.currentWidget()
        for aba in self.abas.values():
            vertical = QSizePolicy.Policy.Preferred if aba is atual else QSizePolicy.Policy.Ignored
            aba.setSizePolicy(QSizePolicy.Policy.Preferred, vertical)

    def _clicou(self, nome: str) -> None:
        self.set(nome)
        if self._ao_mudar is not None:
            self._ao_mudar(nome)

    def _pintar_barra(self) -> None:
        """Folha da barra (só as medidas: as cores são da folha do app) e
        largura de cada botão (texto + 14, como o CTkButton)."""
        r = CANTO
        self.barra.setStyleSheet(
            f"#barra_abas {{ border-radius: {r}px; }}"
            f" #barra_abas QPushButton {{ border-width: {BORDA_BOTAO}px; border-style: solid;"
            f" border-radius: 0; padding: 0 {FOLGA_TEXTO - BORDA_BOTAO}px; font-size: {self._tamanho_fonte}px;"
            f" min-height: {ALTURA_BARRA_VISIVEL - 2 * BORDA_BOTAO}px;"
            f" max-height: {ALTURA_BARRA_VISIVEL - 2 * BORDA_BOTAO}px; }}"
            f" #barra_abas QPushButton:checked {{ border-radius: {r}px; }}")
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

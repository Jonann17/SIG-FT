"""Janela que a Home abre para um painel (chaves, modelos e gastos de IA, mural).

O de `sigft/app/widgets/painel_janela.py` em Qt. Não para robô nenhum (nada de
`threading.Event`): abre, a pessoa olha, fecha. Minimiza, segue o tema e não
trava a janela principal (sem modal).
"""
from __future__ import annotations

import functools

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from sigft.app.idioma import t
from sigft.app_qt.widgets import blocos, dialogs

# O conteúdo do CTkScrollableFrame começa 6 px para dentro (o canto do quadro).
RECUO_ROLAGEM = 6

# Mesma ideia do `_ABERTOS` dos diálogos: a janela vive enquanto está aberta,
# mesmo que quem a abriu não guarde a referência. Chave = id(): as conexões que
# a tiram daqui não podem guardar a própria janela (o ciclo a prenderia).
_ABERTAS: dict = {}


def _esquecer(chave: int, *_sinal) -> None:
    _ABERTAS.pop(chave, None)


class JanelaPainel(QWidget):
    """Hospeda o painel que `montar(parent)` desenha.

    `parent` (= `self.conteudo`) é o QWidget de dentro de uma área rolável (o
    CTkScrollableFrame de lá) e já vem com um QVBoxLayout alinhado ao topo: o
    painel faz `parent.layout().addWidget(...)`. Abre ao ser construída.

    Fechar só ESCONDE (o padrão do Qt, sem WA_DeleteOnClose), como o `destroy()`
    da interface antiga do ponto de vista de quem abriu: a tela não precisa saber se a janela
    ainda existe. Sem pai, ao fechar ela sai de `_ABERTAS` e o Python a recolhe;
    com pai (a Home), fica oculta até o pai morrer -- e sai de `_ABERTAS` também
    se o pai for destruído com ela aberta (`destroyed`). A Home guarda uma janela
    de cada painel: o segundo clique traz a aberta para a frente, e a fechada dá
    lugar a uma nova (`HomeView._abrir_painel`).
    """

    def __init__(self, master=None, *, titulo: str, montar, geometria: str = "900x680") -> None:
        # Janela de verdade (com minimizar), e não QDialog: no Windows o QDialog
        # não tem o botão de minimizar, e o CTkToplevel tem.
        super().__init__(master, Qt.WindowType.Window)
        self.setObjectName("janela_painel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # O fundo (o `fundo` do tema; era o gray10 do CTkToplevel) é a regra
        # `#janela_painel` da folha.
        self.setWindowTitle(titulo)
        self.resize(*blocos.geometria_tk(geometria))

        layout = QVBoxLayout(self)
        # CTkScrollableFrame pack(padx=10, pady=10); botão pack(pady=(0, 12)):
        # entre os dois, 10 + 0.
        layout.setContentsMargins(10, 10, 10, 12)
        layout.setSpacing(0)
        # E5.1: a barra SEMPRE à vista, como no CTkScrollableFrame (que reserva a
        # faixa mesmo sem nada para rolar, com a alça cheia). Sem isso os painéis
        # da Home saíam 11 px mais largos que lá (o quadro das chaves: 708 x 697).
        self.area, self._layout_conteudo = blocos.area_rolavel(margem=RECUO_ROLAGEM,
                                                               barra_sempre_visivel=True)
        self.conteudo = self.area.widget()
        layout.addWidget(self.area, 1)
        layout.addSpacing(10)

        montar(self.conteudo)

        # primary com hover primary_hover: é a variante "primario" da folha.
        self.botao_fechar = blocos.botao(t("Fechar"), variante="primario", largura=120, altura=28)
        # Nenhuma tecla o aperta (o CTkButton nunca pega o foco): um Espaço
        # perdido fecharia o painel e jogaria fora as chaves digitadas.
        dialogs.sem_tecla(self.botao_fechar)
        self.botao_fechar.clicked.connect(self.close)
        layout.addWidget(self.botao_fechar, 0, Qt.AlignmentFlag.AlignHCenter)

        _ABERTAS[id(self)] = self
        self.destroyed.connect(functools.partial(_esquecer, id(self)))
        self.show()
        # A interface antiga punha `-topmost` por 200 ms só para a janela nascer na frente;
        # no Qt, trocar a flag de "sempre por cima" exige reabrir a janela
        # (pisca). Trazer para a frente faz o mesmo.
        self.raise_()
        self.activateWindow()

    def closeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        _ABERTAS.pop(id(self), None)
        super().closeEvent(evento)

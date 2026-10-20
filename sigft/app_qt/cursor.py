"""
A mãozinha do mouse em tudo o que se clica -- num lugar só.

Até 2026-10-20 a mãozinha era posta botão a botão (`setCursor` em quatro
widgets), e a fábrica que faz QUASE todos os botões do app, `blocos.botao`
(125 usos), não punha. Na Home, "Salvar Chaves", "Aplicar recomendados" e o
menu lateral mostravam a seta, e a pessoa não tinha como saber que eram
botões antes de clicar. Relato do Jonathan.

Pôr o `setCursor` na fábrica consertaria a maior parte e deixaria de fora o
resto (menu lateral, rádios, os botões das caixas de diálogo do Qt). Um filtro
na APLICAÇÃO pega todo widget clicável quando ele é polido -- inclusive o que
alguém criar amanhã sem lembrar desta regra.

Duas regras do filtro:

- **Quem já escolheu o próprio cursor manda.** Widget com `WA_SetCursor` no
  momento do polimento não é tocado (o cartão da Home, por exemplo).
- **Desabilitado volta à seta.** O Qt mostra o cursor do widget mesmo com ele
  desabilitado, e a mãozinha num botão que não responde é uma promessa falsa.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractButton, QComboBox, QTabBar

CLICAVEIS = (QAbstractButton, QComboBox, QTabBar)

# Marca dos widgets cujo cursor é DESTE filtro (e não de quem os criou).
_PROPRIEDADE = "_sigft_maozinha"


def aplicar(widget) -> None:
    """Mãozinha se habilitado, seta se não."""
    widget.setCursor(Qt.CursorShape.PointingHandCursor if widget.isEnabled()
                     else Qt.CursorShape.ArrowCursor)


class MaozinhaNoClicavel(QObject):
    def eventFilter(self, obj, evento):  # noqa: N802 -- nome do Qt
        tipo = evento.type()
        if tipo == QEvent.Type.Polish:
            if (isinstance(obj, CLICAVEIS)
                    and not obj.testAttribute(Qt.WidgetAttribute.WA_SetCursor)):
                obj.setProperty(_PROPRIEDADE, True)
                aplicar(obj)
        elif tipo == QEvent.Type.EnabledChange:
            if isinstance(obj, CLICAVEIS) and obj.property(_PROPRIEDADE):
                aplicar(obj)
        return False


def instalar(app) -> MaozinhaNoClicavel:
    """Instala o filtro uma vez só. O filtro fica pendurado no `app` (é o
    pai dele), então não some com o coletor de lixo."""
    existente = app.findChild(MaozinhaNoClicavel)
    if existente is not None:
        return existente
    filtro = MaozinhaNoClicavel(app)
    app.installEventFilter(filtro)
    return filtro

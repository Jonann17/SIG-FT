"""Tamanho da letra: Normal ou Grande, trocado com o app aberto (2026-10-21, etapa 1b).

Como o tema (`tema.py`): a escolha fica nas preferências (`prefs`, chave `letra`)
e `aplicar` faz a troca inteira na hora:

1. `estilo.AUMENTO_LETRA` (de `tokens.AUMENTO_DA_LETRA`) e a folha do app
   regerada: `folha_de_estilo` soma o aumento a cada `font-size`;
2. as peças com folha PRÓPRIA (`blocos.botao(tamanho_fonte=...)`, rótulos,
   caixas) e com `setFont` em pixel: a folha própria ganha da do app, então cada
   uma é refeita a partir da folha de antes do aumento, guardada nela;
3. peça criada depois (tela aberta pela primeira vez) ou que trocou de folha
   (`blocos.pintar`, a repintura do tema): um vigia no app ajusta no
   `Polish`/`StyleChange`. O vigia só existe com a letra grande: no normal nada
   muda, nem as medidas;
4. botão ou rótulo de uma linha com largura FIXA (fix round 1, 2026-10-21): com
   a letra grande o texto passaria da largura e seria cortado ("APLICAR
   AUTORIZAÇÕES" em 200 px), então a largura sobe até o `sizeHint`; no normal
   volta à de antes, guardada na peça. O rótulo que elide (`RotuloElidido`) e o
   de várias linhas ficam como estão: estreitar é o trabalho deles.

No fim, `mudou` avisa quem arruma a tela pelo tamanho (a barra da Home).
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

from sigft.app import tokens
from sigft.app_qt import estilo
from sigft.app_qt.widgets.blocos import RotuloElidido

_log = logging.getLogger(__name__)

TAMANHOS = ("normal", "grande")
PADRAO = "normal"
CHAVE_PREFERENCIA = "letra"
_PROP_FONTE_BASE = "_letra_fonte_base"
_PROP_LARGURA_FIXA = "_letra_largura_fixa"
_SEM_LIMITE = 16777215   # o QWIDGETSIZE_MAX do Qt: largura máxima "solta"
_TIPOS_VIGIADOS = (QEvent.Type.Polish, QEvent.Type.StyleChange)


class _Avisador(QObject):
    mudou = Signal(str)


_avisador = _Avisador()
# Emite a escolha que valeu, depois da troca inteira (como `tema.mudou`).
mudou = _avisador.mudou


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta de
    dados. Função para os testes apontarem outro arquivo."""
    return None


def _valida(escolha) -> str:
    return escolha if escolha in TAMANHOS else PADRAO


def escolhido() -> str:
    """A escolha guardada; nenhuma, ou uma que não é tamanho: o normal."""
    from sigft.core import prefs

    try:
        valor = prefs.ler_preferencia(CHAVE_PREFERENCIA, PADRAO, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return PADRAO
    return _valida(valor)


def atual() -> str:
    """A letra que está VALENDO (pelo `estilo.AUMENTO_LETRA`), que pode não ser
    a guardada: o `--smoke --letra grande` aplica sem gravar."""
    return next((t for t in TAMANHOS if tokens.AUMENTO_DA_LETRA[t] == estilo.AUMENTO_LETRA), PADRAO)


def aumento(escolha: str) -> int:
    """Os px que a `escolha` soma a cada tamanho de letra (inválida: 0)."""
    return tokens.AUMENTO_DA_LETRA[_valida(escolha)]


def ajustar_widget(widget: QWidget, aumento_px: int) -> None:
    """Refaz a folha própria (e a fonte em pixel) de `widget` com `aumento_px`,
    sempre a partir da de antes do aumento: chamar duas vezes não soma duas.
    Depois, a largura fixa (`_ajustar_largura`)."""
    _ajustar_folha_e_fonte(widget, aumento_px)
    _ajustar_largura(widget, aumento_px)


def _ajustar_folha_e_fonte(widget: QWidget, aumento_px: int) -> None:
    folha = widget.styleSheet()
    if folha:
        base = estilo.folha_sem_aumento(widget)
        nova = estilo.ajustar_tamanhos(base, aumento_px)
        widget.setProperty(estilo.PROP_FOLHA_BASE, base)
        widget.setProperty(estilo.PROP_FOLHA_POSTA, nova)
        if nova != folha:
            widget.setStyleSheet(nova)
        if "font-size" in base:
            return   # a folha decide o tamanho: mexer no QFont não muda nada
    if not widget.testAttribute(Qt.WidgetAttribute.WA_SetFont):
        return
    fonte = widget.font()
    base_px = widget.property(_PROP_FONTE_BASE)
    if base_px is None:
        if fonte.pixelSize() <= 0:
            return   # fonte em pontos: o tamanho vem da folha, que já foi ajustada
        base_px = fonte.pixelSize()
        widget.setProperty(_PROP_FONTE_BASE, base_px)
    if fonte.pixelSize() != base_px + aumento_px:
        fonte.setPixelSize(base_px + aumento_px)
        widget.setFont(fonte)


def _texto_de_largura_fixa(widget: QWidget) -> bool:
    if not isinstance(widget, (QAbstractButton, QLabel)) or isinstance(widget, RotuloElidido):
        return False
    if isinstance(widget, QLabel) and widget.wordWrap():
        return False
    largura = widget.maximumWidth()
    return widget.minimumWidth() == largura < _SEM_LIMITE and bool(widget.text())


def _ajustar_largura(widget: QWidget, aumento_px: int) -> None:
    """Largura fixa com a letra grande: no mínimo o `sizeHint` (o texto inteiro).
    No normal, a largura de antes, ao pixel; peça nunca alargada: nada muda."""
    original = widget.property(_PROP_LARGURA_FIXA)
    if original is None:
        if not aumento_px or not _texto_de_largura_fixa(widget):
            return
        original = widget.maximumWidth()
    alvo = max(original, widget.sizeHint().width()) if aumento_px else original
    if (widget.minimumWidth(), widget.maximumWidth()) != (alvo, alvo):
        widget.setFixedWidth(alvo)
    widget.setProperty(_PROP_LARGURA_FIXA, original if aumento_px else None)


class _Vigia(QObject):
    """Ajusta a peça que nasce ou troca de folha com a letra grande valendo."""

    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() in _TIPOS_VIGIADOS and estilo.AUMENTO_LETRA and isinstance(obj, QWidget):
            try:
                ajustar_widget(obj, estilo.AUMENTO_LETRA)
            except RuntimeError:
                pass   # peça já destruída
        return False


# O vigia instalado no app (no máximo um; nenhum com a letra normal).
_vigia: list = []


def _vigiar(app, ligado: bool) -> None:
    if ligado and not _vigia:
        vigia = _Vigia()
        app.installEventFilter(vigia)
        _vigia.append(vigia)
    elif not ligado and _vigia:
        app.removeEventFilter(_vigia.pop())


def aplicar(app, escolha: str, *, gravar: bool = True) -> str:
    """Troca a letra do app inteiro para `escolha` (inválida: normal) e devolve a
    escolha que valeu, que é a que o seletor marca, mesmo se gravar falhar.

    `gravar=False` não mexe nas preferências: é a abertura (que acabou de lê-las)
    e o `--smoke --letra`."""
    escolha = _valida(escolha)
    if gravar:
        from sigft.core import prefs

        try:
            prefs.gravar_preferencia(CHAVE_PREFERENCIA, escolha, config_path=_arquivo_de_prefs())
        except Exception:  # noqa: BLE001 -- lembrar não pode impedir a troca
            _log.warning("nao consegui gravar o tamanho de letra escolhido", exc_info=True)
    estilo.AUMENTO_LETRA = aumento(escolha)
    _vigiar(app, bool(estilo.AUMENTO_LETRA))
    app.setStyleSheet(estilo.folha_de_estilo())
    # Duas passadas: a largura mede o texto com a fonte NOVA, e a de uma peça
    # pode vir da folha do pai (as abas), refeita na primeira passada.
    widgets = app.allWidgets()
    for ajuste in (_ajustar_folha_e_fonte, _ajustar_largura):
        for widget in widgets:
            try:
                ajuste(widget, estilo.AUMENTO_LETRA)
            except RuntimeError:
                pass   # peça já destruída
    mudou.emit(escolha)
    return escolha

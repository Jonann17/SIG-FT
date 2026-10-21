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
   muda, nem as medidas.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget

from sigft.app import tokens
from sigft.app_qt import estilo

_log = logging.getLogger(__name__)

TAMANHOS = ("normal", "grande")
PADRAO = "normal"
CHAVE_PREFERENCIA = "letra"
_PROP_FONTE_BASE = "_letra_fonte_base"
_TIPOS_VIGIADOS = (QEvent.Type.Polish, QEvent.Type.StyleChange)


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
    sempre a partir da de antes do aumento: chamar duas vezes não soma duas."""
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
    for widget in app.allWidgets():
        try:
            ajustar_widget(widget, estilo.AUMENTO_LETRA)
        except RuntimeError:
            pass   # peça já destruída
    return escolha

"""Tema escuro, claro ou o do sistema, trocado com o app aberto (sistema visual, 2026-10-20).

A escolha da pessoa ("escuro", "claro" ou "sistema") fica nas preferências
(`core/prefs.ler_preferencia`, chave `tema`); o tema DE FATO (`efetivo`) é
"escuro" ou "claro": "sistema" pergunta ao Qt o esquema de cores do Windows.

`aplicar` faz a troca inteira, nesta ordem: grava a escolha, muda
`estilo.TEMA_ATUAL` (o que as peças pintadas à mão leem na hora de pintar),
regera a folha do app, repinta os ícones de cada janela (`icones.reaplicar`) e
emite `mudou` para quem desenhou outra coisa com a paleta.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication

from sigft.app_qt import estilo, icones

_log = logging.getLogger(__name__)

TEMAS = ("escuro", "claro", "sistema")
PADRAO = "escuro"
CHAVE_PREFERENCIA = "tema"


class _Avisador(QObject):
    mudou = Signal(str)


_avisador = _Avisador()
# Emitido depois de cada `aplicar`, com o tema efetivo ("escuro" ou "claro").
mudou = _avisador.mudou


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta
    de dados. Função para os testes apontarem outro arquivo."""
    return None


def _valida(escolha) -> str:
    return escolha if escolha in TEMAS else PADRAO


def escolhido() -> str:
    """A escolha guardada; nenhuma, ou uma que não é tema: o escuro."""
    from sigft.core import prefs

    try:
        valor = prefs.ler_preferencia(CHAVE_PREFERENCIA, PADRAO, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return PADRAO
    return _valida(valor)


def _esquema_do_sistema() -> str:
    """O esquema de cores do sistema operacional: "claro" ou "escuro". Sem
    resposta (`Unknown`, ou um sistema que não diz): escuro, o padrão do app."""
    try:
        esquema = QGuiApplication.styleHints().colorScheme()
    except Exception:  # noqa: BLE001 -- Qt sem a pergunta: fica o padrão
        return PADRAO
    return "claro" if esquema == Qt.ColorScheme.Light else "escuro"


def efetivo(escolha: str) -> str:
    """O tema que se pinta para a `escolha`: "sistema" vira o do Windows."""
    if escolha == "sistema":
        return _esquema_do_sistema()
    return "claro" if escolha == "claro" else "escuro"


def aplicar(app, escolha: str, *, gravar: bool = True) -> None:
    """Troca o tema do app inteiro para `escolha` (inválida: escuro).

    `gravar=False` não mexe nas preferências: é a abertura (que acabou de lê-las)
    e o `--smoke --tema`. Gravar que falha (pasta só de leitura) não impede a
    troca: fica no log."""
    escolha = _valida(escolha)
    if gravar:
        from sigft.core import prefs

        try:
            prefs.gravar_preferencia(CHAVE_PREFERENCIA, escolha, config_path=_arquivo_de_prefs())
        except Exception:  # noqa: BLE001 -- lembrar não pode impedir a troca
            _log.warning("nao consegui gravar o tema escolhido", exc_info=True)
    estilo.TEMA_ATUAL = efetivo(escolha)
    app.setStyleSheet(estilo.folha_de_estilo())
    for janela in app.topLevelWidgets():
        icones.reaplicar(janela)
        janela.update()
    mudou.emit(estilo.TEMA_ATUAL)


_seguindo: list = []


def seguir_o_sistema(app) -> None:
    """Com "sistema" escolhido, a troca de tema do Windows com o app aberto
    também troca o do app. Liga uma vez só, por mais que seja chamada."""
    if _seguindo:
        return

    def _ao_mudar(_esquema) -> None:
        if escolhido() == "sistema":
            aplicar(app, "sistema", gravar=False)

    try:
        QGuiApplication.styleHints().colorSchemeChanged.connect(_ao_mudar)
    except Exception:  # noqa: BLE001 -- Qt sem o sinal: segue sem acompanhar
        return
    _seguindo.append(_ao_mudar)

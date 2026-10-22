"""Aviso do Windows quando uma tarefa termina ou pede algo (2026-10-21, etapa 1b).

Só quando o SIG-FT não está em foco (outro programa na frente, ou minimizado):
quem está olhando para a tela já vê a faixa "Terminou" e a caixa da espera.
`QSystemTrayIcon.showMessage` vira a notificação nativa do Windows, sem
dependência nova; clicar nela (ou no ícone da bandeja) traz a janela para a frente.

O ícone da bandeja só fica aceso enquanto há aviso que a pessoa não viu: clicar
nele ou no aviso, ou voltar ao SIG-FT, o apaga (`_ao_mudar_estado`). Apagar logo
depois do aviso (com um temporizador) deixaria o aviso da central de
notificações sem dono, e o clique nele não traria mais a janela.

Liga e desliga na Home ("Avisar no Windows"), ligado por padrão (`prefs.get_opcao`).
Sem área de notificação no sistema (`isSystemTrayAvailable` falso), não faz nada.
NUNCA nos testes nem no `--smoke`: `tests/conftest.py` põe `ENV_DESLIGAR`, e quem
testa o aviso tira a variável E troca `_mostrar`; no `--smoke` a janela está em
foco ou a plataforma offscreen não tem bandeja.
"""
from __future__ import annotations

import os
import weakref

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from shiboken6 import isValid

from sigft.app.idioma import marcar, t
from sigft.app_qt import estilo, icones

ENV_DESLIGAR = "SIGFT_SEM_AVISO_DO_WINDOWS"
CHAVE_OPCAO = "avisos_do_windows"
TITULO_FIM = "SIG-FT"          # o nome do app: não se traduz
TITULO_ESPERA = marcar("O SIG-FT está esperando você")
MS_NA_TELA = 10_000
LIMITE_DO_TEXTO = 180

# Os ícones acesos, para a volta ao SIG-FT apagar. Referência FRACA: o ícone é
# filho da janela e morre com ela.
_acesos: "weakref.WeakSet[QSystemTrayIcon]" = weakref.WeakSet()
_ouvindo_o_estado = False


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta de
    dados. Função para os testes apontarem outro arquivo."""
    return None


def ligado() -> bool:
    from sigft.core import prefs

    try:
        return prefs.get_opcao(CHAVE_OPCAO, True, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return True


def ligar(valor: bool) -> None:
    from sigft.core import prefs

    try:
        prefs.set_opcao(CHAVE_OPCAO, bool(valor), config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar o clique
        pass


def primeira_linha(texto) -> str:
    """A primeira linha com texto, cortada em `LIMITE_DO_TEXTO`."""
    linhas = [linha.strip() for linha in str(texto or "").splitlines() if linha.strip()]
    linha = linhas[0] if linhas else ""
    if len(linha) <= LIMITE_DO_TEXTO:
        return linha
    return linha[:LIMITE_DO_TEXTO - 3].rstrip() + "..."


def _em_foco(janela) -> bool:
    """O SIG-FT é o aplicativo ativo e a janela não está minimizada (um painel da
    Home na frente também conta como SIG-FT em foco)."""
    if janela.isMinimized() or not janela.isVisible():
        return False
    return QGuiApplication.applicationState() == Qt.ApplicationState.ApplicationActive


def avisar(janela, texto, *, titulo: str = TITULO_FIM) -> bool:
    """Na thread da interface. Mostra o aviso se ligado e fora de foco; devolve se saiu."""
    if os.environ.get(ENV_DESLIGAR) or janela is None or not texto:
        return False
    if not ligado() or _em_foco(janela):
        return False
    # O título é traduzido aqui (constante marcada); o texto já chega traduzido.
    return _mostrar(janela, t(titulo), primeira_linha(texto))


def trazer_para_frente(janela) -> None:
    if janela.isMinimized():
        janela.setWindowState(janela.windowState() & ~Qt.WindowState.WindowMinimized)
    janela.show()
    janela.raise_()
    janela.activateWindow()


def _icone(janela):
    for icone in (janela.windowIcon(), QApplication.windowIcon()):
        if not icone.isNull():
            return icone
    return icones.icone("house", estilo.cor_do_papel("primaria"))


def _apagar(bandeja) -> None:
    if isValid(bandeja):
        bandeja.hide()
    _acesos.discard(bandeja)


def _ao_mudar_estado(estado) -> None:
    """A pessoa voltou ao SIG-FT: os avisos já não têm o que dizer."""
    if estado == Qt.ApplicationState.ApplicationActive:
        for bandeja in list(_acesos):
            _apagar(bandeja)


def bandeja_da(janela) -> QSystemTrayIcon:
    """O ícone de bandeja da `janela` (um só, criado na primeira vez). Guarda só
    uma referência FRACA à janela: o sinal do filho não segura a tela viva."""
    bandeja = getattr(janela, "_bandeja_do_aviso", None)
    if bandeja is None:
        bandeja = QSystemTrayIcon(_icone(janela), janela)
        bandeja.setToolTip("SIG-FT")
        ref_janela = weakref.ref(janela)
        ref_bandeja = weakref.ref(bandeja)

        def _clicou(*_args) -> None:
            icone = ref_bandeja()
            if icone is not None:
                _apagar(icone)
            alvo = ref_janela()
            if alvo is not None:
                trazer_para_frente(alvo)

        bandeja.messageClicked.connect(_clicou)
        bandeja.activated.connect(_clicou)
        janela._bandeja_do_aviso = bandeja
    return bandeja


def _ouvir_o_estado() -> None:
    global _ouvindo_o_estado
    app = QGuiApplication.instance()
    if _ouvindo_o_estado or app is None:
        return
    app.applicationStateChanged.connect(_ao_mudar_estado)
    _ouvindo_o_estado = True


def _mostrar(janela, titulo: str, texto: str) -> bool:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return False
    _ouvir_o_estado()
    bandeja = bandeja_da(janela)
    bandeja.show()
    _acesos.add(bandeja)
    bandeja.showMessage(titulo, texto, _icone(janela), MS_NA_TELA)
    return True

"""O nome da pessoa na saudação da Home, perguntado uma vez (sistema visual, 2026-10-20).

O SIG-FT não sabe quem o usa (o usuário do Windows é a matrícula). A Home diz
"Bom dia, <nome>" com o nome que a pessoa dá UMA vez: na primeira abertura sem
nome guardado, o que cobre a instalação nova e a primeira abertura depois de
uma atualização (quem já tinha o app não tem nem nome nem o registro de que já
se perguntou). Não é no instalador: ele roda como administrador, para a
máquina inteira, e o nome é de cada pessoa.

Fica nas preferências (`core/prefs.ler_preferencia`, chaves `nome` e
`ja_perguntou_nome`), no mesmo arquivo do tema. "Agora não" ou fechar só
registra que já perguntou; a pessoa troca depois clicando na saudação.

O nome só aparece na tela: não vai para log, planilha, IA ou portal. Por isso
quem o lê (`guardado`) é só a Home, e há teste que trava isso
(`tests/test_qt_nome.py`). Os avisos de log daqui nunca levam o nome.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout
from shiboken6 import isValid

from sigft.app.idioma import marcar, t
from sigft.app_qt import tema
from sigft.app_qt.widgets import blocos

_log = logging.getLogger(__name__)

CHAVE_NOME = "nome"
CHAVE_JA_PERGUNTOU = "ja_perguntou_nome"
LIMITE = 40

TITULO = marcar("Seu nome")
PERGUNTA = marcar("Como podemos te chamar?")
EXPLICACAO = marcar("Ele só aparece na saudação da Home. Dá para mudar depois, clicando nela.")
TEXTO_SALVAR = marcar("Salvar")
TEXTO_AGORA_NAO = marcar("Agora não")
DICA_DA_SAUDACAO = marcar("Mudar como te chamamos")


def _arquivo_de_prefs():
    """O mesmo arquivo de preferências do tema (`None`: o `user_prefs.json`
    da pasta de dados). Função para os testes apontarem outro."""
    return tema._arquivo_de_prefs()


def _ler(chave: str):
    """A preferência, ou `None` se o arquivo não se deixa ler."""
    from sigft.core import prefs

    try:
        return prefs.ler_preferencia(chave, "", config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        _log.warning("nao consegui ler a preferencia %s", chave, exc_info=True)
        return None


# Gravar já falhou nesta sessão: não pergunta mais (a resposta não ficaria
# guardada, e a pergunta voltaria a cada abertura).
_sem_gravar: list = []


def _gravar(chave: str, valor: str) -> None:
    from sigft.core import prefs

    try:
        prefs.gravar_preferencia(chave, valor, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- lembrar não pode derrubar a abertura
        _sem_gravar.append(chave)
        _log.warning("nao consegui gravar a preferencia %s", chave, exc_info=True)


def guardado() -> str:
    """O nome guardado, ou `""` sem nome."""
    return (_ler(CHAVE_NOME) or "").strip()[:LIMITE]


def precisa_perguntar() -> bool:
    """Sem nome e sem o registro de que já se perguntou. Arquivo que não se
    deixa ler não pergunta: perguntaria a cada abertura sem conseguir lembrar."""
    nome, ja = _ler(CHAVE_NOME), _ler(CHAVE_JA_PERGUNTOU)
    if nome is None or ja is None or _sem_gravar:
        return False
    return not nome.strip() and not ja


def guardar(texto: str) -> None:
    """Guarda o nome (aparado, no máximo `LIMITE` letras; vazio tira o nome)
    e registra que já se perguntou."""
    _gravar(CHAVE_NOME, (texto or "").strip()[:LIMITE].strip())
    recusar()


def recusar() -> None:
    """Só registra que já se perguntou: o "Agora não"."""
    _gravar(CHAVE_JA_PERGUNTOU, "sim")


def saudacao(agora: datetime, quem: str) -> str:
    """Boa noite (até 5h), Bom dia (até 12h), Boa tarde (até 18h), Boa noite;
    mais o nome, se houver. A spec dizia "Bom dia até 12h"; às 2h soava
    estranho e a madrugada virou "Boa noite" (2026-10-20). No idioma da sessão
    (2026-10-22); o nome vai como a pessoa o escreveu."""
    if agora.hour < 5:
        inicio = marcar("Boa noite")
    elif agora.hour < 12:
        inicio = marcar("Bom dia")
    elif agora.hour < 18:
        inicio = marcar("Boa tarde")
    else:
        inicio = marcar("Boa noite")
    quem = (quem or "").strip()
    return t("{saudacao}, {nome}", saudacao=t(inicio), nome=quem) if quem else t(inicio)


class PerguntaDoNome(QDialog):
    """"Como podemos te chamar?": campo, "Salvar" (primário) e "Agora não".

    Responde sozinha: "Salvar" guarda, "Agora não" e o X só registram que já
    perguntou (e mantêm o nome que houver). Modal da janela que a abre: é uma
    pergunta curta, e a resposta muda a saudação de trás."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t(TITULO))
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._respondida = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(0)
        lay.addWidget(blocos.rotulo(t(PERGUNTA), tamanho=16, negrito=True, alinhar="esquerda"))
        lay.addSpacing(4)
        explicacao = blocos.rotulo(t(EXPLICACAO), tamanho=13, papel="legenda", alinhar="esquerda")
        explicacao.setWordWrap(True)
        lay.addWidget(explicacao)
        lay.addSpacing(14)

        self.campo = QLineEdit(guardado())
        self.campo.setMaxLength(LIMITE)
        self.campo.setPlaceholderText(t(TITULO))
        self.campo.setMinimumWidth(320)
        self.campo.returnPressed.connect(self._salvar)
        lay.addWidget(self.campo)
        lay.addSpacing(18)

        botoes = QHBoxLayout()
        botoes.setSpacing(10)
        botoes.addStretch()
        self.botao_agora_nao = blocos.botao(t(TEXTO_AGORA_NAO), variante="secundario", largura=120)
        self.botao_agora_nao.setAutoDefault(False)
        self.botao_agora_nao.clicked.connect(self.reject)
        self.botao_salvar = blocos.botao(t(TEXTO_SALVAR), variante="primario", largura=120,
                                         negrito=True)
        self.botao_salvar.setAutoDefault(False)
        self.botao_salvar.clicked.connect(self._salvar)
        botoes.addWidget(self.botao_agora_nao)
        botoes.addWidget(self.botao_salvar)
        lay.addLayout(botoes)
        self.campo.setFocus()

    def _salvar(self) -> None:
        self._respondida = True
        guardar(self.campo.text())
        self.accept()

    def reject(self) -> None:
        # "Agora não", Esc e o X chegam aqui (o X via `closeEvent` do QDialog).
        if not self._respondida:
            self._respondida = True
            recusar()
        super().reject()


def perguntar_na_abertura(janela, *, depois=None, agendar=None) -> bool:
    """Agenda a pergunta para logo depois de a janela aparecer, se precisa.
    `True` se agendou.

    Chamada pelo lançador (`app_qt/main.main`, depois do `show()`), e NÃO pelo
    `SIG_FT_App`: assim nenhum teste que monta a janela fica esperando a
    resposta. O `--smoke` nunca pergunta (fecha sozinho, sem ninguém para
    responder). `depois()` roda quando a pessoa responde (a Home redesenha a
    saudação); `agendar(ms, funcao)` é a costura do teste.
    """
    if "--smoke" in sys.argv or not precisa_perguntar():
        return False

    def abrir() -> None:
        if not isValid(janela) or not janela.isVisible():
            return
        caixa = PerguntaDoNome(janela)
        janela._pergunta_do_nome = caixa
        if depois is not None:
            caixa.finished.connect(lambda _codigo: depois())
        caixa.open()

    if agendar is None:
        QTimer.singleShot(0, janela, abrir)
    else:
        agendar(0, abrir)
    return True


def pergunta_aberta(janela):
    """A caixa da pergunta, se está na tela agora; senão `None`."""
    caixa = getattr(janela, "_pergunta_do_nome", None)
    if caixa is not None and isValid(caixa) and caixa.isVisible():
        return caixa
    return None

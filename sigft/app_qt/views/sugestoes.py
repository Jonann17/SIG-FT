"""A janela Sugestões: a lâmpada ao lado da engrenagem da Home (2026-10-30).

Pedido do Jonathan, com o cabeçalho do CMI Suite como modelo (a lâmpada à
esquerda da engrenagem). A pessoa escreve a ideia e o SIG-FT abre um RASCUNHO
de e-mail no Outlook, com o "Para" vazio: quem envia, e para quem, é ela. Com
"Anexar o log do SIG-FT" (marcada), vai uma cópia do `sigft.log`. Sem Outlook,
o programa de e-mail padrão abre pelo `mailto:` e a janela mostra o caminho do
log para anexar à mão. A regra mora em `services/sugestoes.py` (sem Qt).

É uma `JanelaPainel`, como a Configuração: uma só aberta por vez (a Home
guarda a referência em `_janelas["sugestoes"]`) e "Fechar" no rodapé. Fechar
só esconde: o texto digitado continua lá na próxima vez que a lâmpada abrir.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QPlainTextEdit, QVBoxLayout

from sigft import _build_info
from sigft.app import idioma
from sigft.app.idioma import marcar, t
from sigft.app_qt import estilo, icones, interface
from sigft.app_qt.catalogo import ACAO_SUGESTOES
from sigft.app_qt.widgets import blocos, controles, dialogs
from sigft.app_qt.widgets.module_frame import aplicar_dicas
from sigft.app_qt.widgets.painel_janela import JanelaPainel
from sigft.services import sugestoes

TITULO = ACAO_SUGESTOES.texto
GEOMETRIA = "620x500"
TEXTO_EXPLICACAO = marcar("Tem uma ideia ou algo que poderia funcionar melhor? Escreva aqui: o SIG-FT "
                          "abre um rascunho de e-mail no Outlook, e você escolhe para quem enviar.")
DICA_CAIXA = marcar("O que você sugere? Em qual tela? O que esperava que acontecesse?")
TEXTO_ANEXAR_LOG = marcar("Anexar o log do SIG-FT")
DICA_ANEXAR_LOG = marcar("O log ajuda a entender o que aconteceu. Ele tem os passos das tarefas, "
                         "nunca as chaves de API.")
TEXTO_ESCREVER_EMAIL = marcar("Escrever o e-mail")
MSG_ABRINDO = marcar("Abrindo o rascunho...")
MSG_OUTLOOK = marcar("Rascunho aberto no Outlook. Revise e envie.")
MSG_MAILTO = marcar("Rascunho aberto no seu programa de e-mail. Revise e envie.")
MSG_ANEXAR_A_MAO = marcar("O log não vai junto por este caminho: anexe-o à mão. Ele está em {caminho}")
MSG_FALHOU = marcar("Não foi possível abrir um rascunho de e-mail ({erro}). Copie o texto e mande por "
                    "onde preferir.")
ALTURA_CAIXA = 180


def _em_segundo_plano(alvo, *args) -> None:
    """Thread `daemon`: o Outlook pode levar segundos para subir, e a janela não
    pode congelar esperando."""
    threading.Thread(target=alvo, args=args, daemon=True, name="sigft-sugestoes").start()


def _sem_conteudo(_pai) -> None:
    """O `montar` da `JanelaPainel`: o conteúdo é montado depois do
    `super().__init__`, porque usa `self`."""


class JanelaSugestoes(JanelaPainel):
    # Quem roda o rascunho fora da thread da interface (o teste troca).
    disparar = staticmethod(_em_segundo_plano)

    def __init__(self, home) -> None:
        super().__init__(home, titulo=t(TITULO), montar=_sem_conteudo, geometria=GEOMETRIA)
        self.home = home
        quadro = QFrame(objectName="painel_home")
        coluna = QVBoxLayout(quadro)
        coluna.setContentsMargins(16, 16, 16, 16)
        coluna.setSpacing(10)

        self.titulo = blocos.rotulo(t(TITULO), tamanho=15, negrito=True, papel="destaque",
                                    alinhar="esquerda")
        coluna.addWidget(self.titulo)
        self.explicacao = blocos.rotulo(t(TEXTO_EXPLICACAO), tamanho=12, papel="legenda",
                                        alinhar="esquerda")
        self.explicacao.setWordWrap(True)
        coluna.addWidget(self.explicacao)

        self.caixa_texto = QPlainTextEdit(objectName="caixa_texto")
        self.caixa_texto.setPlaceholderText(t(DICA_CAIXA))
        self.caixa_texto.setMinimumHeight(ALTURA_CAIXA)
        self.caixa_texto.setTabChangesFocus(True)
        self.caixa_texto.textChanged.connect(self._texto_mudou)
        coluna.addWidget(self.caixa_texto)

        self.caixa_anexar_log = controles.CaixaDeMarcar(t(TEXTO_ANEXAR_LOG), tamanho_fonte=12)
        self.caixa_anexar_log.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # como as da Configuração
        self.caixa_anexar_log.setChecked(True)
        self.caixa_anexar_log.setToolTip(t(DICA_ANEXAR_LOG))
        coluna.addWidget(self.caixa_anexar_log)

        self.btn_escrever = blocos.botao(t(TEXTO_ESCREVER_EMAIL), variante="primario", altura=32,
                                         largura_minima=estilo.LARGURA_BOTAO_CTK)
        icones.aplicar(self.btn_escrever, ACAO_SUGESTOES.icone)
        dialogs.sem_tecla(self.btn_escrever)
        self.btn_escrever.setEnabled(False)
        self.btn_escrever.clicked.connect(self._escrever_email)
        coluna.addWidget(self.btn_escrever, 0, Qt.AlignmentFlag.AlignLeft)

        self.status = blocos.rotulo("", tamanho=12, papel="legenda", alinhar="esquerda")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status.hide()
        coluna.addWidget(self.status)

        self._layout_conteudo.addWidget(quadro)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        aplicar_dicas(self)
        self.caixa_texto.setFocus()

    def _texto_mudou(self) -> None:
        self.btn_escrever.setEnabled(bool(self.caixa_texto.toPlainText().strip()))

    def _escrever_email(self) -> None:
        texto = self.caixa_texto.toPlainText().strip()
        if not texto:
            return
        self.btn_escrever.setEnabled(False)
        self._mostrar_status(t(MSG_ABRINDO))
        self.disparar(self._abrir_rascunho, texto, self.caixa_anexar_log.isChecked(),
                      _build_info.VERSAO, idioma.atual())

    def _abrir_rascunho(self, texto: str, anexar_log: bool, versao: str, codigo_idioma: str) -> None:
        """Roda na THREAD. O texto fica na caixa: o SIG-FT não sabe se foi enviado."""
        try:
            resultado = sugestoes.abrir_rascunho(texto, versao=versao, idioma=codigo_idioma,
                                                 anexar_log=anexar_log)
        except Exception as erro:  # noqa: BLE001 -- vira mensagem na janela
            print(f"[sugestoes] o rascunho nao abriu: {erro}")
            interface.na_interface(self._falhou, str(erro))
            return
        interface.na_interface(self._aberto, resultado)

    def _aberto(self, resultado: sugestoes.Resultado) -> None:
        if resultado.via == "outlook":
            texto = t(MSG_OUTLOOK)
        else:
            texto = t(MSG_MAILTO)
            if resultado.log is not None:
                texto += "\n" + t(MSG_ANEXAR_A_MAO, caminho=str(resultado.log))
        self._mostrar_status(texto)
        self._texto_mudou()

    def _falhou(self, erro: str) -> None:
        self._mostrar_status(t(MSG_FALHOU, erro=erro), papel="erro")
        self._texto_mudou()

    def _mostrar_status(self, texto: str, papel: str = "legenda") -> None:
        self.status.setText(texto)
        estilo.definir_papel(self.status, papel)
        self.status.show()

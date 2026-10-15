"""Atualização automática -- a metade da INTERFACE, em Qt.

Mesma API e mesmo comportamento de `sigft/app/atualizacao.py` (CustomTkinter);
os textos vêm de `sigft/app/atualizacao_textos.py`, o trabalho de rede de
`sigft/services/updater.py`. Aqui mora só o que é de tela:

* `verificar_na_abertura(janela)` -- chamada pela janela principal ao montar.
  Pergunta numa thread e, havendo versão nova, abre a `JanelaAtualizacao`.
  Falha de rede ou de token é ENGOLIDA (vai para o `sigft.log`): a abertura
  do app não pode depender do GitHub;
* `procurar_agora(janela, ao_terminar=...)` -- o botão "Atualizações" da Home.
  O mesmo caminho, mas FALANDO: diz que a versão é a mais recente, mostra o
  erro, ou explica por que esta cópia não se atualiza por aqui;
* `JanelaAtualizacao` -- o aviso: a versão nova, o que mudou, "Atualizar
  agora" e "Agora não". Atualizar baixa com barra de progresso, dispara o
  instalador e fecha o app, que o instalador reabre atualizado.

Threads
-------
A consulta e o download rodam numa thread `daemon` (não é tarefa da pessoa:
não pode fazer o "X" perguntar por "tarefa em andamento", nem segurar o
processo). Nada aqui toca em widget fora da thread da interface: tudo volta
por `interface.na_interface`.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextBlockFormat, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QTextEdit, QVBoxLayout, QWidget,
)
from shiboken6 import isValid

from sigft import _build_info
from sigft.app import theme
from sigft.app.atualizacao_textos import (
    MSG_COMO_FUNCIONA,
    MSG_DOWNLOAD_CONFERIDO,
    MSG_TAREFA_AO_ATUALIZAR,
    MSG_UAC,
    TEXTO_AGORA_NAO,
    TEXTO_ATUALIZANDO,
    TEXTO_ATUALIZAR,
    TEXTO_O_QUE_MUDOU,
    TEXTO_TENTAR_DE_NOVO,
    TITULO,
    msg_baixando,
    msg_caiu_no_completo,
    msg_em_dia,
    msg_erro_ao_procurar,
    msg_falhou,
    msg_sem_verificar,
    notas_para_exibir,
    resumo_da_versao,
    titulo_do_aviso,
)
from sigft.app_qt import estilo, interface
from sigft.app_qt.widgets import blocos
from sigft.core import instancia
from sigft.services import updater

__all__ = [
    "JanelaAtualizacao", "TITULO", "notas_para_exibir", "procurar_agora",
    "resumo_da_versao", "verificar_na_abertura",
]

# Texto de um CTkLabel que não diz `text_color` (tema dark-blue): gray84.
_COR_ROTULO_CTK = estilo.cinza_tk("gray84")
# `wraplength=530` dos rótulos que quebram linha na janela CTk.
_LARGURA_DO_TEXTO = 530


# ─────────────────────────────── utilidades ─────────────────────────────────

def _log(msg: object) -> None:
    """Para o `sigft.log`: no app empacotado o `print` vai para lá."""
    print(f"[atualizacao] {msg}")


def _em_segundo_plano(alvo, *args) -> None:
    """Thread `daemon`: uma consulta pendurada não pode segurar o fechamento."""
    threading.Thread(target=alvo, args=args, daemon=True,
                     name="sigft-atualizacao").start()


# ─────────────────────────── a pergunta ao GitHub ───────────────────────────

def verificar_na_abertura(janela, *, versao_atual: str | None = None,
                          disparar=_em_segundo_plano) -> bool:
    """Pergunta ao GitHub sem segurar a abertura. `True` se a pergunta saiu.

    Só pergunta quando a política deixa (`updater.deve_verificar`): app
    empacotado, instalado pelo instalador e com token. `disparar` é a costura
    do teste: a produção usa uma thread.
    """
    if not updater.deve_verificar():
        return False
    disparar(_consultar, janela, versao_atual or _build_info.VERSAO, False, None)
    return True


def procurar_agora(janela, *, versao_atual: str | None = None, ao_terminar=None,
                   disparar=_em_segundo_plano) -> None:
    """O botão "Atualizações": a mesma pergunta, mas que SEMPRE responde.

    `ao_terminar` roda na thread da interface quando a resposta chega, seja
    ela qual for -- a Home o usa para devolver o botão ao normal.
    """
    versao = versao_atual or _build_info.VERSAO
    motivo = updater.motivo_para_nao_verificar()
    if motivo is not None:
        if ao_terminar is not None:
            ao_terminar()
        QMessageBox.information(janela, TITULO, msg_sem_verificar(versao, motivo))
        return
    disparar(_consultar, janela, versao, True, ao_terminar)


def _consultar(janela, versao_atual: str, falar: bool, ao_terminar) -> None:
    """Roda na THREAD. Não toca em widget: a resposta volta por `na_interface`."""
    resposta = None
    try:
        info = updater.checar(versao_atual, log_cb=_log)
    except Exception as erro:  # noqa: BLE001 -- rede, token, JSON: tudo vira aviso
        _log(f"nao foi possivel procurar atualizacao: {erro}")
        if falar:
            resposta = (_avisar_erro, janela, erro)
    else:
        if info is not None:
            resposta = (_mostrar_aviso, janela, info, versao_atual)
        elif falar:
            resposta = (_avisar_em_dia, janela, versao_atual)

    if resposta is None and ao_terminar is None:
        return

    def na_interface():
        # O botão volta ao normal ANTES da mensagem: a caixa é modal, e o botão
        # ficaria dizendo "Procurando..." enquanto ela estivesse aberta.
        if ao_terminar is not None:
            ao_terminar()
        if resposta is not None:
            resposta[0](*resposta[1:])

    interface.na_interface(na_interface)


def _avisar_em_dia(janela, versao_atual: str) -> None:
    QMessageBox.information(janela, TITULO, msg_em_dia(versao_atual))


def _avisar_erro(janela, erro: BaseException) -> None:
    QMessageBox.warning(janela, TITULO, msg_erro_ao_procurar(erro))


def _mostrar_aviso(janela, info: updater.Atualizacao, versao_atual: str):
    """Abre o aviso -- ou traz para a frente o que já estiver aberto.

    A pergunta da abertura e o botão da Home podem responder quase juntos; dois
    avisos, cada um com o seu "Atualizar agora", seriam dois downloads.
    """
    aberta = getattr(janela, "_janela_de_atualizacao", None)
    # Fechado, o aviso é apagado (WA_DeleteOnClose): só se usa o que está vivo.
    if aberta is not None and isValid(aberta) and not aberta.fechada:
        aberta.raise_()
        aberta.activateWindow()
        return aberta
    aviso = JanelaAtualizacao(janela, info=info, versao_atual=versao_atual)
    janela._janela_de_atualizacao = aviso
    aviso.show()
    aviso.raise_()
    aviso.activateWindow()
    return aviso


def _fechar_o_app(janela_principal) -> None:
    """Fecha o SIG-FT para o instalador trocar os arquivos. Não volta.

    `instancia.encerrar`, e não `close()`: o `closeEvent` da janela principal
    perguntaria por "tarefa em andamento", e uma thread comum viva seguraria o
    processo com os arquivos do app em uso. É o mesmo encerramento do "X" da
    janela principal -- uma implementação só.
    """
    try:
        janela_principal.hide()
    except Exception:  # noqa: BLE001
        pass
    instancia.encerrar(0)


# ───────────────────────────── a janela do aviso ────────────────────────────

def _rotulo(texto: str, *, tamanho: int, cor: str, negrito: bool = False,
            quebra: bool = False) -> QLabel:
    """O CTkLabel com `anchor="w"`: 28 px de altura mínima, texto à esquerda.
    Com `quebra`, o `wraplength=530` (largura máxima do texto)."""
    rotulo = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, cor=cor, alinhar="esquerda")
    rotulo.setWordWrap(quebra)
    if quebra:
        rotulo.setMaximumWidth(_LARGURA_DO_TEXTO)
    return rotulo


class JanelaAtualizacao(QDialog):
    """"Nova versão disponível": o que mudou, e o "Atualizar agora" de um clique.

    Modal de propósito (o contrário dos diálogos de pausa do robô): atualizar
    FECHA o app. Sem a modalidade, dava para começar um lote na tela de trás
    com o aviso aberto, e o "Atualizar agora" mataria o robô no meio.

    Geometria da janela CTk (580x560, `pack`), medida sob Xvfb: os `pady` de
    vizinhos SOMAM, então o layout tem espaçamento zero e cada vão é escrito.
    """

    def __init__(self, master, *, info: updater.Atualizacao, versao_atual: str,
                 disparar=_em_segundo_plano, fechar_app=_fechar_o_app,
                 tarefas_em_andamento=None):
        super().__init__(master)
        self.info = info
        self._tarefas_em_andamento = tarefas_em_andamento
        self.fechada = False
        self._baixando = False
        self._disparar = disparar
        self._fechar_app = fechar_app
        self._master = master
        self._ultimo_percentual = -1

        self.setWindowTitle(TITULO)
        self.resize(580, 560)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)   # "-topmost"
        self.setWindowModality(Qt.WindowModality.ApplicationModal)     # o grab_set
        # Fechado ("Agora não", "X" ou Esc), o aviso é APAGADO, como o `destroy()`
        # da janela CTk -- e não só escondido, vivo até o app fechar.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)   # padx=20 de todos
        lay.setSpacing(0)

        # Título: pady=(20, 4).
        lay.addSpacing(20)
        self.rotulo_titulo = _rotulo(titulo_do_aviso(info), tamanho=16, negrito=True,
                                     cor=_COR_ROTULO_CTK)
        lay.addWidget(self.rotulo_titulo)
        lay.addSpacing(4)
        self.rotulo_resumo = _rotulo(resumo_da_versao(info, versao_atual), tamanho=13,
                                     cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO_CLARO),
                                     quebra=True)
        lay.addWidget(self.rotulo_resumo)
        # "O que mudou:": pady=(14, 4).
        lay.addSpacing(14)
        lay.addWidget(_rotulo(TEXTO_O_QUE_MUDOU, tamanho=14, negrito=True, cor=_COR_ROTULO_CTK))
        lay.addSpacing(4)

        # As notas são quem ENCOLHE quando a parte de baixo cresce (UAC + erro
        # longo): no CTk isso exigiu empacotar os botões primeiro; aqui é o
        # fator de esticamento 1 e uma altura mínima pequena.
        self.caixa_notas = QTextEdit(objectName="notas_atualizacao")
        self.caixa_notas.setAcceptRichText(False)
        self.caixa_notas.setPlainText(notas_para_exibir(info.notas))
        self.caixa_notas.setReadOnly(True)
        self.caixa_notas.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.caixa_notas.setMinimumHeight(40)
        # A cara (CTkTextbox do tema) é a regra #notas_atualizacao da folha do app.
        self._linhas_de_15px()
        lay.addWidget(self.caixa_notas, 1)

        # UAC: pady=(10, 0) -- 10 acima e, com o status, 10 abaixo.
        lay.addSpacing(10)
        self.rotulo_uac = None
        if updater.precisa_elevacao():
            self.rotulo_uac = _rotulo(MSG_UAC, tamanho=12, cor=theme.COLORS["warning"],
                                      quebra=True)
            lay.addWidget(self.rotulo_uac)
            lay.addSpacing(10)

        # Status: pady=(10, 4) (os 10 de cima já foram).
        self.rotulo_status = _rotulo(MSG_COMO_FUNCIONA, tamanho=12,
                                     cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO), quebra=True)
        lay.addWidget(self.rotulo_status)
        lay.addSpacing(4)

        # A barra só entra na tela quando o download começa: parada em zero,
        # antes do clique, ela parece um download travado. Vai numa faixa com os
        # 6 px de baixo dela (pady=(0, 6)), para a faixa escondida não ocupar nada.
        self._faixa_barra = QWidget()
        faixa = QVBoxLayout(self._faixa_barra)
        faixa.setContentsMargins(0, 0, 0, 6)
        faixa.setSpacing(0)
        # CTkProgressBar(width=530) do tema, progresso na cor `accent`; o valor
        # aqui é o percentual (0 a 100).
        self.barra = blocos.barra_progresso(largura=530, altura=8, cor=theme.COLORS["accent"])
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        faixa.addWidget(self.barra, 0, Qt.AlignmentFlag.AlignHCenter)
        self._faixa_barra.hide()
        lay.addWidget(self._faixa_barra)

        # Botões: pady=(10, 20); cada um com padx=10 (20 entre os dois).
        lay.addSpacing(10)
        self.quadro_botoes = QWidget()
        botoes = QHBoxLayout(self.quadro_botoes)
        botoes.setContentsMargins(0, 0, 0, 0)
        botoes.setSpacing(20)
        self.botao_atualizar = blocos.botao(TEXTO_ATUALIZAR, variante="primario", largura=170,
                                            altura=40, tamanho_fonte=14, negrito=True)
        self.botao_atualizar.clicked.connect(self.atualizar)
        self.botao_agora_nao = blocos.botao(TEXTO_AGORA_NAO, variante="contorno", largura=150,
                                            altura=40,
                                            cor_texto=estilo.cinza_tk(theme.COR_TEXTO_APOIO))
        self.botao_agora_nao.clicked.connect(self.agora_nao)
        botoes.addWidget(self.botao_atualizar)
        botoes.addWidget(self.botao_agora_nao)
        lay.addWidget(self.quadro_botoes, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(20)

        self.botao_atualizar.setDefault(False)
        self.botao_atualizar.setAutoDefault(False)
        self.botao_agora_nao.setAutoDefault(False)

    def _linhas_de_15px(self) -> None:
        """A linha do Tk com Roboto 12 tem 15 px; a do Qt, 14. Numa caixa de
        notas com vários parágrafos, a diferença somava ~10 px até a última
        linha. Altura fixa de 15 px em cada bloco (só aparência; o texto é o mesmo)."""
        formato = QTextBlockFormat()
        formato.setLineHeight(15, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        cursor = QTextCursor(self.caixa_notas.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(formato)

    # -- as duas escolhas ------------------------------------------------------
    def agora_nao(self) -> None:
        """Fecha o aviso. Na próxima abertura do app ele volta."""
        self.fechada = True
        self.close()

    def atualizar(self) -> None:
        """Baixa em segundo plano; a janela acompanha pela barra."""
        if not self._pode_fechar_o_app():
            return
        self.botao_atualizar.setEnabled(False)
        self.botao_atualizar.setText(TEXTO_ATUALIZANDO)
        self.botao_agora_nao.setEnabled(False)
        # Fechar no "X" no meio do download não cancela nada (o download não
        # tem como parar no meio), então o "X" e o Esc ficam mudos até terminar.
        self._baixando = True
        self._ultimo_percentual = -1
        self.barra.setValue(0)
        self._faixa_barra.show()
        self._mostrar_status(msg_baixando(self.info))
        self._disparar(self._baixar_e_instalar)

    def _pode_fechar_o_app(self) -> bool:
        """Com tarefa em andamento, pergunta antes: o app fecha sozinho quando
        o download termina, e um robô no meio do lote morreria ali. A mesma
        regra do "X" da janela principal; Enter responde "Não"."""
        tarefas = (self._tarefas_em_andamento or instancia.tarefas_em_andamento)()
        if not tarefas:
            return True
        resposta = QMessageBox.question(
            self, TITULO, MSG_TAREFA_AO_ATUALIZAR,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return resposta == QMessageBox.StandardButton.Yes

    # -- o trabalho, na thread ------------------------------------------------
    def _baixar_e_instalar(self) -> None:
        """Roda na THREAD. Só fecha o app depois que o instalador SUBIU."""
        try:
            caminho = updater.baixar(self.info, progresso_cb=self._ao_progredir,
                                     log_cb=_log,
                                     ao_cair_no_completo=self._ao_cair_no_completo)
            interface.na_interface(self._mostrar_status, MSG_DOWNLOAD_CONFERIDO)
            updater.instalar(caminho, log_cb=_log)
        except Exception as erro:  # noqa: BLE001 -- vira mensagem na janela
            _log(f"a atualizacao falhou: {erro}")
            interface.na_interface(self._falhou, erro)
            return
        interface.na_interface(self._fechar_app, self._master)

    def _ao_cair_no_completo(self, completo: updater.Atualizacao) -> None:
        """Roda na THREAD: o pequeno falhou e o download virou o do completo
        (a barra recomeça pelo `progresso_cb` do serviço)."""
        interface.na_interface(self._mostrar_status, msg_caiu_no_completo(completo))

    def _ao_progredir(self, fracao: float) -> None:
        """Roda na THREAD, a cada bloco de 256 KB. Só agenda quando o
        percentual muda: são ~400 blocos num instalador de 100 MB."""
        percentual = int(max(0.0, min(1.0, fracao)) * 100)
        if percentual == self._ultimo_percentual:
            return
        self._ultimo_percentual = percentual
        interface.na_interface(self.barra.setValue, percentual)

    # -- de volta à interface ---------------------------------------------------
    def _mostrar_status(self, texto: str, cor: str | None = None) -> None:
        self.rotulo_status.setText(texto)
        self.rotulo_status.setStyleSheet(
            f"font-size: 12px; background: transparent; color: {cor or theme.COLORS['text_light']};")

    def _falhou(self, erro: BaseException) -> None:
        self._mostrar_status(msg_falhou(erro), cor=theme.COLORS["danger"])
        self.barra.setValue(0)
        self.botao_atualizar.setEnabled(True)
        self.botao_atualizar.setText(TEXTO_TENTAR_DE_NOVO)
        self.botao_agora_nao.setEnabled(True)
        self._baixando = False

    # -- fechar ---------------------------------------------------------------
    def reject(self) -> None:  # o Esc
        if self._baixando:
            return
        self.fechada = True
        super().reject()

    def closeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if self._baixando:
            evento.ignore()
            return
        self.fechada = True
        evento.accept()

"""Atualização automática -- a metade da INTERFACE, em Qt.

Mesma API e mesmo comportamento de `sigft/app/atualizacao.py` (interface antiga);
os textos vêm de `sigft/app/atualizacao_textos.py`, o trabalho de rede de
`sigft/services/updater.py`. Aqui mora só o que é de tela:

* `verificar_na_abertura(janela)` -- chamada pela janela principal ao montar.
  Pergunta numa thread e, havendo versão nova, abre a `JanelaAtualizacao`.
  Falha de rede ou de token é ENGOLIDA (vai para o `sigft.log`): a abertura
  do app não pode depender do GitHub;
* `procurar_agora(janela, ao_terminar=...)` -- o botão "Procurar atualizações"
  da janela Configuração (a engrenagem da Home, 2026-10-22) e o Ctrl+K.
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
from sigft.app.atualizacao_textos import (
    MSG_APLICANDO,
    MSG_COMO_FUNCIONA,
    MSG_CONFERINDO_ARQUIVOS,
    MSG_DOWNLOAD_CONFERIDO,
    MSG_REABRINDO,
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
    msg_instalador_nao_iniciou,
    msg_sem_verificar,
    notas_para_exibir,
    resumo_da_versao,
    titulo_do_aviso,
)
from sigft.app.idioma import t
from sigft.app_qt import estilo, interface
from sigft.app_qt.widgets import blocos
from sigft.core import diario, instancia
from sigft.services import pacote_arquivos, updater

__all__ = [
    "JanelaAtualizacao", "TITULO", "notas_para_exibir", "procurar_agora",
    "resumo_da_versao", "verificar_na_abertura",
]

# `wraplength=530` dos rótulos que quebram linha na janela antiga.
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
    disparar(_limpar_e_consultar, janela, versao_atual or _build_info.VERSAO)
    return True


def _limpar_e_consultar(janela, versao_atual: str) -> None:
    """Roda na THREAD. [2026-10-19] Antes da consulta, apaga os instaladores
    que atualizações anteriores deixaram no %TEMP% (`updater.limpar_downloads`).
    A limpeza é um extra: se falhar, vai para o log e a consulta segue.
    [2026-10-27] E os `.sigft-old` que a atualização por arquivos deixou na
    pasta do programa (`pacote_arquivos.limpar_restos`), só no app empacotado."""
    try:
        updater.limpar_downloads(log_cb=_log)
    except Exception as erro:  # noqa: BLE001 -- limpeza não segura a consulta
        _log(f"Limpeza da pasta de atualizacao falhou: {erro}")
    try:
        if updater.empacotado() and (pasta := updater.pasta_instalacao()) is not None:
            if (apagados := pacote_arquivos.limpar_restos(pasta)):
                _log(f"Limpeza: {apagados} resto(s) da atualizacao por arquivos apagados.")
    except Exception as erro:  # noqa: BLE001 -- limpeza não segura a consulta
        _log(f"Limpeza dos restos da atualizacao por arquivos falhou: {erro}")
    _consultar(janela, versao_atual, False, None)


def procurar_agora(janela, *, versao_atual: str | None = None, ao_terminar=None,
                   disparar=_em_segundo_plano) -> None:
    """O botão "Procurar atualizações" (janela Configuração): a mesma pergunta,
    mas que SEMPRE responde.

    `ao_terminar` roda na thread da interface quando a resposta chega, seja
    ela qual for -- a Home (`procurar_atualizacoes`) o usa para devolver o botão
    da janela Configuração ao normal.
    """
    versao = versao_atual or _build_info.VERSAO
    motivo = updater.motivo_para_nao_verificar()
    if motivo is not None:
        if ao_terminar is not None:
            ao_terminar()
        QMessageBox.information(janela, t(TITULO), msg_sem_verificar(versao, motivo))
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
    QMessageBox.information(janela, t(TITULO), msg_em_dia(versao_atual))


def _avisar_erro(janela, erro: BaseException) -> None:
    QMessageBox.warning(janela, t(TITULO), msg_erro_ao_procurar(erro))


def _mostrar_aviso(janela, info: updater.Atualizacao, versao_atual: str):
    """Abre o aviso -- ou traz para a frente o que já estiver aberto.

    A pergunta da abertura e o botão da Configuração podem responder quase juntos; dois
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

    Sem o `closeEvent`, o `FECHAMENTO` do diário é gravado aqui (2026-10-27):
    sem ele, a sessão seguinte a toda atualização diria "encerrado de fora".
    A thread já o gravou (`JanelaAtualizacao._anotar_no_diario`); o diário
    grava uma vez por sessão, então chamar de novo não repete a linha.
    """
    try:
        janela_principal.hide()
    except Exception:  # noqa: BLE001
        pass
    diario.registrar_fechamento()   # nunca levanta
    instancia.encerrar(0)


# ───────────────────────────── a janela do aviso ────────────────────────────

def _rotulo(texto: str, *, tamanho: int, papel: str | None = None, negrito: bool = False,
            quebra: bool = False) -> QLabel:
    """O CTkLabel com `anchor="w"`: 28 px de altura mínima, texto à esquerda.
    Com `quebra`, o `wraplength=530` (largura máxima do texto). `papel`: o
    papel de texto da folha (sem ele, o texto comum)."""
    rotulo = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, papel=papel, alinhar="esquerda")
    rotulo.setWordWrap(quebra)
    if quebra:
        rotulo.setMaximumWidth(_LARGURA_DO_TEXTO)
    return rotulo


class JanelaAtualizacao(QDialog):
    """"Nova versão disponível": o que mudou, e o "Atualizar agora" de um clique.

    Modal de propósito (o contrário dos diálogos de pausa do robô): atualizar
    FECHA o app. Sem a modalidade, dava para começar um lote na tela de trás
    com o aviso aberto, e o "Atualizar agora" mataria o robô no meio.

    Geometria da janela antiga (580x560, `pack`), medida sob Xvfb: os `pady` de
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
        self._versao_atual = versao_atual
        self._ultimo_percentual = -1

        self.setWindowTitle(t(TITULO))
        self.resize(580, 560)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)   # "-topmost"
        self.setWindowModality(Qt.WindowModality.ApplicationModal)     # o grab_set
        # Fechado ("Agora não", "X" ou Esc), o aviso é APAGADO, como o `destroy()`
        # da janela antiga -- e não só escondido, vivo até o app fechar.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)   # padx=20 de todos
        lay.setSpacing(0)

        # Título: pady=(20, 4).
        lay.addSpacing(20)
        self.rotulo_titulo = _rotulo(titulo_do_aviso(info), tamanho=16, negrito=True)
        lay.addWidget(self.rotulo_titulo)
        lay.addSpacing(4)
        self.rotulo_resumo = _rotulo(resumo_da_versao(info, versao_atual), tamanho=13,
                                     papel="legenda", quebra=True)
        lay.addWidget(self.rotulo_resumo)
        # "O que mudou:": pady=(14, 4).
        lay.addSpacing(14)
        lay.addWidget(_rotulo(t(TEXTO_O_QUE_MUDOU), tamanho=14, negrito=True))
        lay.addSpacing(4)

        # As notas são quem ENCOLHE quando a parte de baixo cresce (UAC + erro
        # longo): na interface antiga isso exigiu empacotar os botões primeiro; aqui é o
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
            self.rotulo_uac = _rotulo(t(MSG_UAC), tamanho=12, papel="aviso", quebra=True)
            lay.addWidget(self.rotulo_uac)
            lay.addSpacing(10)

        # Status: pady=(10, 4) (os 10 de cima já foram).
        self.rotulo_status = _rotulo(t(MSG_COMO_FUNCIONA), tamanho=12, papel="legenda", quebra=True)
        lay.addWidget(self.rotulo_status)
        lay.addSpacing(4)

        # A barra só entra na tela quando o download começa: parada em zero,
        # antes do clique, ela parece um download travado. Vai numa faixa com os
        # 6 px de baixo dela (pady=(0, 6)), para a faixa escondida não ocupar nada.
        self._faixa_barra = QWidget()
        faixa = QVBoxLayout(self._faixa_barra)
        faixa.setContentsMargins(0, 0, 0, 6)
        faixa.setSpacing(0)
        # CTkProgressBar(width=530), progresso na cor da folha (`primaria`); o
        # valor aqui é o percentual (0 a 100).
        self.barra = blocos.barra_progresso(largura=530, altura=8)
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
        self.botao_atualizar = blocos.botao(t(TEXTO_ATUALIZAR), variante="primario", largura=170,
                                            altura=40, tamanho_fonte=14, negrito=True)
        self.botao_atualizar.clicked.connect(self.atualizar)
        self.botao_agora_nao = blocos.botao(t(TEXTO_AGORA_NAO), variante="contorno", largura=150,
                                            altura=40)
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
        self.botao_atualizar.setText(t(TEXTO_ATUALIZANDO))
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
            self, t(TITULO), t(MSG_TAREFA_AO_ATUALIZAR),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return resposta == QMessageBox.StandardButton.Yes

    # -- o trabalho, na thread ------------------------------------------------
    def _baixar_e_instalar(self) -> None:
        """Roda na THREAD. Só fecha o app depois que o instalador SUBIU.

        [2026-10-27] Primeiro, quando dá (`updater.pode_por_arquivos`), a
        atualização por arquivos: o próprio app aplica, se reabre e fecha.
        Qualquer falha nela vai para o log e cai no instalador completo (desde
        2026-10-30 o único outro caminho, como no DocManager)."""
        if self._por_arquivos():
            return
        try:
            caminho = updater.baixar(self.info, progresso_cb=self._ao_progredir, log_cb=_log)
            interface.na_interface(self._mostrar_status, t(MSG_DOWNLOAD_CONFERIDO))
            updater.instalar(caminho, log_cb=_log)
        except Exception as erro:  # noqa: BLE001 -- vira mensagem na janela
            _log(f"a atualizacao falhou: {erro}")
            interface.na_interface(self._falhou, erro)
            return
        log = updater.caminho_log_instalacao()
        self._anotar_no_diario("pelo instalador completo", f" (exe={caminho.name}, log={log})")  # nao-e-interface
        interface.na_interface(self._fechar_app, self._master)

    def _anotar_no_diario(self, caminho: str, detalhe: str = "") -> None:
        """Roda na THREAD, logo antes de mandar fechar para atualizar
        (2026-10-27): `ATUALIZACAO <caminho> v<de> -> v<para>` e o FECHAMENTO.
        Aqui, e não só no `_fechar_o_app`: o `CloseApplications=force` do
        instalador pode matar o app antes de a thread da interface rodar, e a
        sessão seguinte diria "encerrado de fora". O diário não repete o
        FECHAMENTO quando o `_fechar_o_app` grava de novo. Nunca levanta."""
        de, para = self._versao_atual, self.info.versao
        diario.registrar_evento(f"{diario.ATUALIZACAO} {caminho} v{de} -> v{para}{detalhe}")  # nao-e-interface
        diario.registrar_fechamento()

    def _por_arquivos(self) -> bool:
        """Roda na THREAD. `True` se aplicou, reabriu e mandou fechar."""
        try:
            pode = updater.pode_por_arquivos(self.info)
        except Exception as erro:  # noqa: BLE001 -- na dúvida, o instalador
            _log(f"nao deu para saber se a atualizacao por arquivos serve: {erro}")
            pode = False
        if not pode:
            if self.info.arquivos is not None:
                # O status do clique dizia o tamanho do zip: vai o completo.
                interface.na_interface(self._mostrar_status, msg_baixando(self.info, so_completo=True))
            return False
        interface.na_interface(self._mostrar_status, t(MSG_APLICANDO))
        try:
            exe = updater.aplicar_por_arquivos(self.info, progresso_cb=self._ao_progredir,
                                               log_cb=_log, ao_conferir=self._ao_conferir)
        except Exception as erro:  # noqa: BLE001 -- cai no instalador
            _log(f"a atualizacao por arquivos falhou, vai o instalador: {erro}")
            self._ultimo_percentual = -1
            interface.na_interface(self.barra.setValue, 0)
            interface.na_interface(self._mostrar_status, msg_caiu_no_completo(self.info))
            return False
        # Antes de reabrir: o processo novo lê a sessão anterior ao abrir.
        self._anotar_no_diario("por arquivos")  # nao-e-interface
        interface.na_interface(self._mostrar_status, t(MSG_REABRINDO))
        try:
            updater.reabrir(exe)
            _log(f"SIG-FT atualizado reaberto: {exe}")
        except Exception as erro:  # noqa: BLE001 -- os arquivos já são os novos
            # Os arquivos já são os da versão nova: fechar assim mesmo, e a
            # pessoa abre de novo à mão.
            _log(f"nao foi possivel reabrir o SIG-FT ({exe}): {erro}")
        interface.na_interface(self._fechar_app, self._master)
        return True

    def _ao_conferir(self) -> None:
        """Roda na THREAD: o zip já foi aplicado e a pasta está sendo conferida
        (a barra recomeça pelo `progresso_cb` do serviço)."""
        interface.na_interface(self._mostrar_status, t(MSG_CONFERINDO_ARQUIVOS))

    def _ao_progredir(self, fracao: float) -> None:
        """Roda na THREAD, a cada bloco de 256 KB. Só agenda quando o
        percentual muda: são ~400 blocos num instalador de 100 MB."""
        percentual = int(max(0.0, min(1.0, fracao)) * 100)
        if percentual == self._ultimo_percentual:
            return
        self._ultimo_percentual = percentual
        interface.na_interface(self.barra.setValue, percentual)

    # -- de volta à interface ---------------------------------------------------
    def _mostrar_status(self, texto: str, papel: str | None = None) -> None:
        """O status em texto comum (`papel=None`) ou no papel pedido (`erro`)."""
        self.rotulo_status.setText(texto)
        estilo.definir_papel(self.rotulo_status, papel)

    def _falhou(self, erro: BaseException) -> None:
        texto = (msg_instalador_nao_iniciou(erro) if isinstance(erro, updater.InstaladorNaoIniciou)
                 else msg_falhou(erro))
        self._mostrar_status(texto, papel="erro")
        self.barra.setValue(0)
        self.botao_atualizar.setEnabled(True)
        self.botao_atualizar.setText(t(TEXTO_TENTAR_DE_NOVO))
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

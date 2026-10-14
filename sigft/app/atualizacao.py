"""Atualização automática — a metade da INTERFACE.

A outra metade (perguntar ao GitHub, baixar, conferir o SHA256, disparar o
instalador) é `sigft/services/updater.py`, que não conhece tkinter (princípio
nº 2 do projeto). Aqui mora só o que é de tela:

* `verificar_na_abertura(janela)` — chamada pela janela principal ao montar.
  Pergunta numa thread e, havendo versão nova, abre a `JanelaAtualizacao`.
  Falha de rede ou de token é ENGOLIDA (vai para o `sigft.log`): a abertura
  do app não pode depender do GitHub;
* `procurar_agora(janela)` — o botão "Atualizações" da Home. O mesmo caminho,
  mas FALANDO: diz que a versão é a mais recente, mostra o erro, ou explica
  por que esta cópia não se atualiza por aqui;
* `JanelaAtualizacao` — o aviso: a versão nova, o que mudou, "Atualizar
  agora" e "Agora não". Atualizar baixa com barra de progresso, dispara o
  instalador e fecha o app, que o instalador reabre atualizado.

A causa raiz que este módulo fecha (2026-09-25)
-----------------------------------------------
O usuário publicou a v1.1.0 e nenhum app instalado percebeu: o serviço estava
pronto desde 2026-09-18, com 45 testes verdes, mas NENHUMA linha da interface
o chamava. O `latest.json` do Release, que o app baixa ao oferecer a versão
nova, ficou com zero downloads. Pedido do usuário: "no momento de
inicialização ele deve identificar o release".

`tests/test_atualizacao_na_abertura.py` monta a janela principal de verdade e
exige a pergunta — é o teste que teria pego o defeito.

Threads
-------
A consulta e o download rodam em thread (a cascata de rede pode levar dezenas
de segundos com a VPN mal configurada). Nada aqui toca em widget fora da
thread do Tk: tudo volta por `_na_interface`, que é o `after(0, ...)` da casa
(ver `widgets/console.py`, CP 7.1).
"""
from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from sigft import _build_info
from sigft.app import theme
# Os textos e as funções puras moram em `atualizacao_textos` (sem tkinter, para
# a interface Qt dizer as mesmas palavras). Reexportados com os nomes de antes.
from sigft.app.atualizacao_textos import (  # noqa: F401 -- reexportados
    MSG_COMO_FUNCIONA,
    MSG_DOWNLOAD_CONFERIDO,
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
from sigft.app.atualizacao_textos import data_br as _data_br  # noqa: F401
from sigft.app.atualizacao_textos import erro_curto as _erro_curto  # noqa: F401
from sigft.app.atualizacao_textos import mb as _mb  # noqa: F401
from sigft.core import instancia
from sigft.services import updater

# ─────────────────────────────── utilidades ─────────────────────────────────

def _log(msg: object) -> None:
    """Para o `sigft.log`: no app empacotado o `print` vai para lá."""
    print(f"[atualizacao] {msg}")


def _em_segundo_plano(alvo, *args) -> None:
    """Thread `daemon`: uma consulta pendurada não pode segurar o fechamento."""
    threading.Thread(target=alvo, args=args, daemon=True,
                     name="sigft-atualizacao").start()


def _na_interface(widget, func, *args) -> None:
    """Agenda `func` na thread do Tk. Silencioso se a janela já fechou.

    O `except` é largo de propósito: com a janela destruída o Tk levanta
    `TclError`, e com o laço de eventos parado, `RuntimeError`. Nos dois casos
    o certo é deixar a notícia cair, não derrubar a thread com traceback.
    """
    try:
        widget.after(0, func, *args)
    except Exception:  # noqa: BLE001
        pass


# ─────────────────────────── a pergunta ao GitHub ───────────────────────────

def verificar_na_abertura(janela, *, versao_atual: str | None = None,
                          disparar=_em_segundo_plano) -> bool:
    """Pergunta ao GitHub sem segurar a abertura. `True` se a pergunta saiu.

    Só pergunta quando a política deixa (`updater.deve_verificar`): app
    empacotado, instalado pelo instalador e com token. Nas outras cópias não
    há o que instalar por aqui, e bater na rede à toa só poluiria o log.

    `disparar` é a costura do teste: a produção usa uma thread.
    """
    if not updater.deve_verificar():
        return False
    disparar(_consultar, janela, versao_atual or _build_info.VERSAO, False, None)
    return True


def procurar_agora(janela, *, versao_atual: str | None = None, ao_terminar=None,
                   disparar=_em_segundo_plano) -> None:
    """O botão "Atualizações": a mesma pergunta, mas que SEMPRE responde.

    `ao_terminar` roda na thread da interface quando a resposta chega, seja
    ela qual for — a Home o usa para devolver o botão ao normal.
    """
    versao = versao_atual or _build_info.VERSAO
    motivo = updater.motivo_para_nao_verificar()
    if motivo is not None:
        if ao_terminar is not None:
            ao_terminar()
        messagebox.showinfo(TITULO, msg_sem_verificar(versao, motivo), parent=janela)
        return
    disparar(_consultar, janela, versao, True, ao_terminar)


def _consultar(janela, versao_atual: str, falar: bool, ao_terminar) -> None:
    """Roda na THREAD. Não toca em widget: a resposta volta por `_na_interface`."""
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
        # O botão volta ao normal ANTES da mensagem: a caixa do Tk é modal, e
        # o botão ficaria dizendo "Procurando..." enquanto ela estivesse aberta.
        if ao_terminar is not None:
            ao_terminar()
        if resposta is not None:
            resposta[0](*resposta[1:])

    _na_interface(janela, na_interface)


def _avisar_em_dia(janela, versao_atual: str) -> None:
    messagebox.showinfo(TITULO, msg_em_dia(versao_atual), parent=janela)


def _avisar_erro(janela, erro: BaseException) -> None:
    messagebox.showwarning(TITULO, msg_erro_ao_procurar(erro), parent=janela)


def _mostrar_aviso(janela, info: updater.Atualizacao, versao_atual: str):
    """Abre o aviso — ou traz para a frente o que já estiver aberto.

    A pergunta da abertura e o botão da Home podem responder quase juntos; duas
    janelas do mesmo aviso, cada uma com o seu "Atualizar agora", seriam dois
    downloads do mesmo instalador.
    """
    aberta = getattr(janela, "_janela_de_atualizacao", None)
    if aberta is not None and not aberta.fechada:
        try:
            aberta.lift()
            aberta.focus()
        except Exception:  # noqa: BLE001
            pass
        return aberta
    janela._janela_de_atualizacao = JanelaAtualizacao(
        janela, info=info, versao_atual=versao_atual)
    return janela._janela_de_atualizacao


def _fechar_o_app(janela_principal) -> None:
    """Fecha o SIG-FT para o instalador trocar os arquivos. Não volta.

    `instancia.encerrar`, e não esperar o fim natural do processo: uma thread
    de robô que não seja `daemon` o seguraria vivo, com os arquivos do app em
    uso, e o instalador acabaria brigando com ele. É o mesmo encerramento do
    "X" da janela principal -- uma implementação só.
    """
    try:
        janela_principal.destroy()
    except Exception:  # noqa: BLE001
        pass
    instancia.encerrar(0)


# ───────────────────────────── a janela do aviso ────────────────────────────

class JanelaAtualizacao(ctk.CTkToplevel):
    """"Nova versão disponível": o que mudou, e o "Atualizar agora" de um clique.

    Modal de propósito (o contrário dos diálogos de pausa do robô): atualizar
    FECHA o app. Sem o `grab_set()`, dava para começar um lote na tela de trás
    com o aviso aberto, e o "Atualizar agora" mataria o robô no meio.
    """

    def __init__(self, master, *, info: updater.Atualizacao, versao_atual: str,
                 disparar=_em_segundo_plano, fechar_app=_fechar_o_app):
        super().__init__(master)
        self.info = info
        self.fechada = False
        self._disparar = disparar
        self._fechar_app = fechar_app
        self._ultimo_percentual = -1

        self.title(TITULO)
        self.geometry("580x560")
        self.attributes("-topmost", True)
        self.transient(master)
        self._segurar_o_foco()
        self.protocol("WM_DELETE_WINDOW", self.agora_nao)

        # ⚠️ A PARTE DE BAIXO É EMPACOTADA PRIMEIRO, presa embaixo. O `pack`
        # reparte a altura na ordem de empacotamento e corta os últimos; com os
        # botões por último, o aviso do UAC mais um erro de rede (uma linha por
        # rota tentada) os empurrava para fora da janela -- visto no ensaio sob
        # xvfb em 2026-09-25. Assim, quem encolhe é a caixa de notas, que rola.
        self.quadro_botoes = botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(side="bottom", pady=(10, 20))

        self.rotulo_status = ctk.CTkLabel(
            self, text=MSG_COMO_FUNCIONA, font=theme.FONTE_CORPO_MIUDO,
            text_color=theme.COR_TEXTO_APOIO, wraplength=530, justify="left",
        )
        self.rotulo_status.pack(side="bottom", pady=(10, 4), padx=20, anchor="w")

        self.rotulo_uac = None
        if updater.precisa_elevacao():
            self.rotulo_uac = ctk.CTkLabel(
                self, text=MSG_UAC, font=theme.FONTE_CORPO_MIUDO,
                text_color=theme.COLORS["warning"], wraplength=530,
                justify="left",
            )
            self.rotulo_uac.pack(side="bottom", pady=(10, 0), padx=20, anchor="w")

        # A barra só entra na tela quando o download começa: parada em zero,
        # antes do clique, ela parece um download travado.
        self.barra = ctk.CTkProgressBar(
            self, width=530, progress_color=theme.COLORS["accent"])
        self.barra.set(0)

        # [2026-10-07] Pelo canal de testes chega pré-lançamento: o título diz.
        ctk.CTkLabel(
            self, text=titulo_do_aviso(info),
            font=theme.FONTE_SECAO,
        ).pack(pady=(20, 4), padx=20, anchor="w")
        self.rotulo_resumo = ctk.CTkLabel(
            self, text=resumo_da_versao(info, versao_atual),
            font=theme.FONTE_CORPO, text_color=theme.COR_TEXTO_APOIO_CLARO,
            wraplength=530, justify="left",
        )
        self.rotulo_resumo.pack(padx=20, anchor="w")

        ctk.CTkLabel(
            self, text=TEXTO_O_QUE_MUDOU, font=theme.FONTE_ROTULO,
        ).pack(pady=(14, 4), padx=20, anchor="w")
        self.caixa_notas = ctk.CTkTextbox(
            self, height=220, wrap="word", font=theme.FONTE_CORPO_MIUDO)
        self.caixa_notas.insert("1.0", notas_para_exibir(info.notas))
        self.caixa_notas.configure(state="disabled")
        self.caixa_notas.pack(fill="both", expand=True, padx=20)

        self.botao_atualizar = ctk.CTkButton(
            botoes, text=TEXTO_ATUALIZAR, command=self.atualizar,
            fg_color=theme.COLORS["primary"],
            hover_color=theme.COLORS["primary_hover"],
            width=170, height=40, font=theme.FONTE_BOTAO,
        )
        self.botao_atualizar.pack(side="left", padx=10)
        self.botao_agora_nao = ctk.CTkButton(
            botoes, text=TEXTO_AGORA_NAO, command=self.agora_nao,
            fg_color="transparent", border_width=1, border_color="#555",
            text_color=theme.COR_TEXTO_APOIO, width=150, height=40,
        )
        self.botao_agora_nao.pack(side="left", padx=10)

        try:
            self.lift()
            self.focus()
        except Exception:  # noqa: BLE001
            pass

    def _segurar_o_foco(self) -> None:
        """`grab_set` pode falhar enquanto a janela ainda não está visível
        ("window not viewable"). Uma segunda tentativa, logo depois, resolve --
        e um aviso sem grab é melhor do que nenhum aviso."""
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            self.after(200, self._tentar_grab_de_novo)

    def _tentar_grab_de_novo(self) -> None:
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass

    # -- as duas escolhas ------------------------------------------------------
    def agora_nao(self) -> None:
        """Fecha o aviso. Na próxima abertura do app ele volta."""
        self.destroy()

    def atualizar(self) -> None:
        """Baixa em segundo plano; a janela acompanha pela barra."""
        self.botao_atualizar.configure(state="disabled", text=TEXTO_ATUALIZANDO)
        self.botao_agora_nao.configure(state="disabled")
        # Fechar no "X" no meio do download não cancela nada (o download não
        # tem como parar no meio), então o "X" fica mudo até terminar.
        self.protocol("WM_DELETE_WINDOW", self._ignorar)
        self._ultimo_percentual = -1
        self.barra.set(0)
        # Logo depois dos botões na ordem de empacotamento: como os dois estão
        # presos embaixo, a barra fica imediatamente ACIMA deles.
        self.barra.pack(side="bottom", pady=(0, 6), padx=20, after=self.quadro_botoes)
        self._mostrar_status(msg_baixando(self.info))
        self._disparar(self._baixar_e_instalar)

    # -- o trabalho, na thread ------------------------------------------------
    def _baixar_e_instalar(self) -> None:
        """Roda na THREAD. Só fecha o app depois que o instalador SUBIU."""
        try:
            caminho = updater.baixar(self.info, progresso_cb=self._ao_progredir,
                                     log_cb=_log,
                                     ao_cair_no_completo=self._ao_cair_no_completo)
            _na_interface(self, self._mostrar_status, MSG_DOWNLOAD_CONFERIDO)
            updater.instalar(caminho, log_cb=_log)
        except Exception as erro:  # noqa: BLE001 -- vira mensagem na janela
            _log(f"a atualizacao falhou: {erro}")
            _na_interface(self, self._falhou, erro)
            return
        _na_interface(self, self._fechar_app, self.master)

    def _ao_cair_no_completo(self, completo: updater.Atualizacao) -> None:
        """Roda na THREAD: o pequeno falhou e o download virou o do completo
        (a barra recomeça pelo `progresso_cb` do serviço)."""
        _na_interface(self, self._mostrar_status, msg_caiu_no_completo(completo))

    def _ao_progredir(self, fracao: float) -> None:
        """Roda na THREAD, a cada bloco de 256 KB. Só agenda quando o
        percentual muda: são ~400 blocos num instalador de 100 MB, e cada
        agendamento é uma ida e volta à thread do Tk."""
        percentual = int(max(0.0, min(1.0, fracao)) * 100)
        if percentual == self._ultimo_percentual:
            return
        self._ultimo_percentual = percentual
        _na_interface(self, self.barra.set, percentual / 100)

    # -- de volta à interface ---------------------------------------------------
    def _mostrar_status(self, texto: str, cor: str | None = None) -> None:
        self.rotulo_status.configure(
            text=texto, text_color=cor or theme.COLORS["text_light"])

    def _falhou(self, erro: BaseException) -> None:
        self._mostrar_status(msg_falhou(erro), cor=theme.COLORS["danger"])
        self.barra.set(0)
        self.botao_atualizar.configure(state="normal", text=TEXTO_TENTAR_DE_NOVO)
        self.botao_agora_nao.configure(state="normal")
        self.protocol("WM_DELETE_WINDOW", self.agora_nao)

    def _ignorar(self) -> None:
        """O "X" durante o download."""

    def destroy(self) -> None:
        self.fechada = True
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001
            pass
        super().destroy()

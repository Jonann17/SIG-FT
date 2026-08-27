"""Diálogos de ação manual — UMA implementação de cada.

Checkpoint 7.2 do plano (`docs/refatoracao/PLANO_REFATORACAO.md`, Fase 7).

Substitui:

* as **3 cópias** de `_mostrar_janela_pausa` (`ModuloUploadConditions`,
  `ModuloUploadTechSpecs`, `ModuloCopiaFichas`) — esqueleto idêntico nas três,
  só a mensagem muda;
* `_mostrar_janela_retry` (`ModuloUploadConditions`), a janela de "Excel
  bloqueado".

O protocolo que estes diálogos implementam
------------------------------------------
Todos seguem o mesmo par, e ele NÃO é detalhe de implementação — é o que
permite ao robô rodar em thread sem congelar a interface:

1. o worker (numa `threading.Thread`) cria um `threading.Event`, pede à
   interface que abra o diálogo com `self.after(0, ...)` e chama
   `evento.wait()`;
2. o diálogo roda na thread da interface e chama `evento.set()` quando o
   usuário decide — soltando o worker.

Por que NÃO há `grab_set()` aqui
--------------------------------
O comentário original, no `ModuloCopiaFichas`, merece sobreviver à
refatoração porque registra uma tentativa que deu errado:

    "Nós propositalmente NÃO usamos top.grab_set() aqui. É ele que bloqueava
    tudo!"

`grab_set()` torna o diálogo modal e captura TODOS os eventos da aplicação —
o usuário deixa de conseguir clicar no console para copiar as pendências, que
é justamente o que ele precisa fazer enquanto o diálogo está aberto. O
`-topmost` dá a visibilidade desejada sem tirar o resto do app do ar.
"""
from __future__ import annotations

import customtkinter as ctk

from sigft.app import theme

# Sentinela que as três telas já usavam para escolher a mensagem de login em
# vez da mensagem de "confira e salve". Era uma string solta repetida em três
# arquivos-classe; aqui é uma constante, e quem compara importa daqui.
LOGIN_NECESSARIO = "LOGIN_NECESSARIO"

# As mensagens, palavra por palavra como estavam. A Fase 7 é zero redesign, e
# texto de interface é aparência: mudar "solte o robô" para "iniciar" seria
# uma alteração de produto sem pedido.
MSG_LOGIN_SOLTAR_ROBO = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Navegue até a tela inicial do PMIB.\n"
    "3. Clique abaixo para soltar o robô."
)
MSG_LOGIN_LOTE = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Navegue até a tela inicial do PMIB.\n"
    "3. Clique abaixo para iniciar a automação em lote."
)
MSG_EXCEL_BLOQUEADO = (
    "O arquivo _STATUS_PMIB está aberto no Excel.\n\n"
    "Por favor, FECHE O ARQUIVO e clique em 'Tentar Novamente' para salvar o "
    "status da ficha concluída."
)


def msg_falha_ao_salvar(nome_secao: str) -> str:
    """Mensagem do `ModuloUploadConditions` quando uma aba não salva."""
    return (
        f"Falha ao salvar a aba '{nome_secao}'. Ocorreu um erro no site.\n\n"
        "1. Resolva o problema no navegador.\n"
        "2. Clique em SALVAR no site.\n"
        "3. Clique no botão abaixo para continuar."
    )


def msg_ficha_preenchida(pmib: str) -> str:
    """Mensagem do `ModuloCopiaFichas` ao terminar uma ficha."""
    return (
        f"Ficha {pmib} preenchida!\n\n"
        "Verifique na tela e copie as pendências (se houverem) do painel ao "
        "lado.\nApós clicar em SALVAR no site, clique no botão abaixo."
    )


class _DialogoDeAcaoManual(ctk.CTkToplevel):
    """Base das janelas que param o robô à espera do usuário.

    Cuida do que as cópias repetiam: título, geometria, `-topmost`, o texto
    centralizado com `wraplength`, e — o mais fácil de esquecer — ligar o
    fechamento no "X" a uma ação que SOLTA o worker. Sem isso, fechar a janela
    deixa a thread do robô presa em `wait()` para sempre.
    """

    def __init__(self, master, *, titulo: str, mensagem: str, geometria: str, pady_texto: int):
        super().__init__(master)
        self.title(titulo)
        self.geometry(geometria)
        # Sem grab_set() -- ver o docstring do módulo.
        self.attributes("-topmost", True)

        ctk.CTkLabel(
            self,
            text=mensagem,
            font=theme.FONTE_CORPO,
            wraplength=400,
            justify="center",
        ).pack(pady=pady_texto, padx=20, expand=True)


class PausaLoginDialog(_DialogoDeAcaoManual):
    """"Ação Manual Necessária" com um botão só: CONTINUAR AUTOMAÇÃO.

    Uso (a partir da thread da interface)::

        PausaLoginDialog(self, mensagem=dialogs.MSG_LOGIN_LOTE,
                         evento_espera=evento)
    """

    def __init__(self, master, *, mensagem: str, evento_espera):
        super().__init__(
            master,
            titulo="Ação Manual Necessária",
            mensagem=mensagem,
            geometria="450x250",
            pady_texto=30,
        )
        self._evento = evento_espera

        # Fechar no "X" tem de soltar o robô, igual ao botão.
        self.protocol("WM_DELETE_WINDOW", self.liberar)

        self.botao = ctk.CTkButton(
            self,
            text="CONTINUAR AUTOMAÇÃO",
            command=self.liberar,
            fg_color=theme.COLORS["primary"],
            hover_color=theme.COLORS["primary_hover"],
            height=45,
            font=theme.FONTE_BOTAO,
        )
        self.botao.pack(pady=(0, 20))

    def liberar(self) -> None:
        """Solta o worker e fecha."""
        self._evento.set()
        self.destroy()


class RetryLockDialog(_DialogoDeAcaoManual):
    """"Arquivo Bloqueado": Tentar Novamente × Ignorar e Continuar.

    A decisão volta pelo dicionário `resultado`, na chave ``"retry"`` — o
    mesmo contrato que `_mostrar_janela_retry` já usava, para que o worker do
    lado de lá não precise mudar.

    Fechar no "X" equivale a CANCELAR: a alternativa seria repetir uma
    gravação que o usuário acabou de recusar.
    """

    def __init__(self, master, *, mensagem: str = MSG_EXCEL_BLOQUEADO, evento_espera, resultado: dict):
        super().__init__(
            master,
            titulo="Arquivo Bloqueado",
            mensagem=mensagem,
            geometria="450x200",
            pady_texto=20,
        )
        self._evento = evento_espera
        self._resultado = resultado

        self.protocol("WM_DELETE_WINDOW", self.cancelar)

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(pady=(0, 20))

        self.botao_repetir = ctk.CTkButton(
            botoes,
            text="Tentar Novamente",
            command=self.repetir,
            fg_color=theme.COLORS["primary"],
            width=150,
            height=40,
        )
        self.botao_repetir.pack(side="left", padx=10)

        self.botao_cancelar = ctk.CTkButton(
            botoes,
            text="Ignorar e Continuar",
            command=self.cancelar,
            fg_color="transparent",
            border_width=1,
            border_color="#555",
            text_color=theme.COR_TEXTO_APOIO,
            width=150,
            height=40,
        )
        self.botao_cancelar.pack(side="left", padx=10)

    def repetir(self) -> None:
        self._resultado["retry"] = True
        self._evento.set()
        self.destroy()

    def cancelar(self) -> None:
        self._resultado["retry"] = False
        self._evento.set()
        self.destroy()

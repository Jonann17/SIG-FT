"""O console de log das telas — UMA implementação, thread-safe de verdade.

Checkpoint 7.1 do plano (`docs/refatoracao/PLANO_REFATORACAO.md`, Fase 7).

O que existia antes
-------------------
12 telas do `frontend.py`, 12 métodos `log()`, em QUATRO variantes:

1. `self.console.insert(...)` direto            — 7 telas
2. `self.after(0, lambda: [insert, see])`       — 3 telas
3. `self.after(0, self._log_thread_safe, txt)`  — 2 telas
4. um `_safe_log()` extra, só no `ModuloPDM`

As sete da variante 1 são um BUG, não um estilo: `_worker()` roda numa
`threading.Thread`, e o Tk só pode ser tocado pela thread que criou o widget.
Mexer no widget de fora é corrupção de estado — na prática dá desde log
faltando até `RuntimeError: main thread is not in main loop` e travamento da
janela. Não é teórico: é o motivo de log de lote longo "sumir" no meio.

Unificar as quatro variantes numa só conserta as sete de uma vez, que é o
ganho real deste checkpoint — não a economia de linhas.

O formato da linha NÃO muda
---------------------------
`> {msg}` seguido de quebra, e rolagem para o fim. É o que as 12 telas já
faziam, e a Fase 7 é zero redesign.

`nivel`/`contexto` são ACEITOS (o protocolo do CP 1.4 os exige na assinatura)
e deliberadamente IGNORADOS na renderização — o próprio `core/callbacks.py`
diz, no cabeçalho: *"a UI de HOJE continua imprimindo exatamente como sempre
(`> msg`) — nível/contexto ficam disponíveis, sem consumidor"*. Dar cor a
`nivel="error"` seria mudar a aparência do app, e isso é outro checkpoint.
"""
from __future__ import annotations

import customtkinter as ctk

from sigft.app import theme


# Prefixo de cada linha do console. Está numa constante porque dois lugares
# precisam concordar sobre ele: quem escreve (`ConsoleFrame.log`) e quem
# testa. Literal repetido nos dois é como o formato deriva sem ninguém notar.
PREFIXO_LINHA = "> "


def formatar_linha(msg: object) -> str:
    """A linha exatamente como as 12 telas a escreviam: ``"> {msg}\\n"``.

    Aceita `object` (e não `str`) de propósito: várias chamadas de hoje passam
    número, `Path` ou exceção direto. As telas antigas caíam na interpolação
    de f-string, que aceita qualquer coisa — manter isso evita um
    `TypeError` novo em produção num caminho de log, que é justamente o
    caminho que ninguém exercita antes de precisar dele.
    """
    return f"{PREFIXO_LINHA}{msg}\n"


class ConsoleFrame(ctk.CTkTextbox):
    """Caixa de texto de log, com `log()` seguro para chamar de QUALQUER thread.

    Substitui o par `self.console = ctk.CTkTextbox(...)` + `def log(self, ...)`
    que cada tela repetia. É um `CTkTextbox` (e não um `CTkFrame` que contém
    um) porque as telas hoje fazem `self.console.grid(...)` direto no textbox
    — herdar mantém esse posicionamento idêntico, sem uma camada de frame a
    mais que mudaria o espaçamento.
    """

    def __init__(self, master, *, altura: int | None = theme.ALTURA_CONSOLE, **kwargs):
        # `altura=None` reproduz as 5 telas que criam o console SEM `height`,
        # deixando o grid esticá-lo. Passar `height=None` ao CustomTkinter não
        # é a mesma coisa que omitir, então o parâmetro entra ou não entra.
        if altura is not None:
            kwargs.setdefault("height", altura)
        kwargs.setdefault("font", theme.FONTE_CONSOLE)
        super().__init__(master, **kwargs)

    # -- API pública ---------------------------------------------------------
    def log(self, msg: object, nivel: str = "info", contexto: object | None = None) -> None:
        """Escreve uma linha no console. Pode ser chamado de qualquer thread.

        Assinatura completa do protocolo do CP 1.4 (`core/callbacks.py`), para
        que um `UICallbacks(log=console.log)` funcione sem adaptador.
        """
        # `after(0, ...)` ENFILEIRA na thread do Tk. Chamado da própria thread
        # da interface, o efeito é o mesmo (só que no próximo ciclo do loop) —
        # por isso não há dois caminhos aqui: um só, correto nos dois casos.
        try:
            self.after(0, self._escrever, msg)
        except RuntimeError:
            # Tk já não está rodando (app fechando enquanto um worker ainda
            # loga). Perder a linha é o comportamento certo; derrubar a thread
            # do worker com um traceback no fechamento, não.
            pass

    # -- interno -------------------------------------------------------------
    def _escrever(self, msg: object) -> None:
        """Roda SEMPRE na thread da interface (agendado por `after`)."""
        try:
            self.insert("end", formatar_linha(msg))
            self.see("end")
        except Exception:
            # O widget pode ter sido destruído entre o `after` e a execução
            # (usuário troca de tela com lote rodando). Silencioso de
            # propósito: é o fim normal de um worker, não um erro do usuário.
            pass

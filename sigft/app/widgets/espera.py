"""Diálogos que param o robô e esperam o usuário — o mecanismo, uma vez só.

Ver `docs/superpowers/specs/2026-08-28-padronizacao-dialogos-design.md` (CP A).

O problema que isto resolve
---------------------------
O robô roda numa `threading.Thread`; o Tk só pode ser tocado pela thread que
criou os widgets. Abrir um diálogo de dentro do worker e esperar a resposta
exige, portanto, um trio:

    evento = threading.Event()
    self.after(0, lambda: AlgumDialogo(self, evento_espera=evento))
    evento.wait()

Esse trio estava **copiado em 3 telas**. Outras 4 nem o faziam — chamavam
`messagebox.showinfo` direto do worker, criando widget fora da thread da
interface. É a mesma classe de defeito que o CP 7.1 corrigiu no console, onde
7 telas escreviam no `CTkTextbox` de dentro da thread do robô.

Por que um MIXIN, e não um método na `ModuleFrame`
--------------------------------------------------
Era esse o desenho original, e ele não sobreviveu ao contato com o código: das
12 telas, **só 2 herdam de `ModuleFrame`** (`ApagarLMR` e `Translator`, os
pilotos do CP 7.1). As outras 10 continuam `ctk.CTkFrame` puro.

Exigir a migração das 10 para poder trocar 4 caixas de diálogo seria deixar a
correção refém de um trabalho muito maior. Como mixin, cada tela adota o
comportamento com uma linha:

    class ModuloLMR(DialogosDeEspera, ctk.CTkFrame):

E a `ModuleFrame` herda dele, então as 2 telas que já a usam ganham de graça,
sem mudar nada.

**A ordem importa:** o mixin vem ANTES da classe do CustomTkinter, para que o
`super().__init__(parent)` da tela passe por ele (que registra a thread da
interface) antes de chegar ao widget de verdade.
"""
from __future__ import annotations

import threading

from sigft.app.widgets import dialogs


class DialogosDeEspera:
    """Dá à tela `pausar_e_esperar` e `perguntar_retry_excel`.

    Ambos são chamáveis de dentro do `_worker` (a thread do robô) — que é o
    ponto: é de lá que eles precisam ser chamados.
    """

    def __init__(self, *args, **kwargs):
        # Quem constrói a tela É a thread da interface. Guardar isso aqui é o
        # que permite recusar uma chamada feita da própria thread do Tk, que
        # travaria o app em vez de abrir a janela.
        self._thread_da_interface = threading.get_ident()
        super().__init__(*args, **kwargs)

    # -- o mecanismo ---------------------------------------------------------
    def _abrir_e_esperar(self, construir_dialogo) -> dict:
        """Abre um diálogo na thread da interface e BLOQUEIA quem chamou até o
        usuário decidir. Chamável de qualquer thread MENOS a da interface.

        `construir_dialogo(evento, resultado)` recebe o `threading.Event` que
        solta quem chamou e o dicionário onde o diálogo grava a decisão.
        Devolve esse dicionário, já preenchido.
        """
        if threading.get_ident() == getattr(self, "_thread_da_interface", None):
            # Chamar daqui travaria o app: `wait()` seguraria justamente a
            # thread que precisa processar o `after` que solta o `wait()`.
            # Falhar alto é melhor que congelar em silêncio — congelado, o
            # usuário não tem nem o que reportar.
            raise RuntimeError(
                f"{type(self).__name__}: _abrir_e_esperar foi chamado da thread da "
                "interface, o que travaria o aplicativo. Chame de dentro do worker "
                "(a thread do robô), ou abra o diálogo direto se já está na interface."
            )

        evento = threading.Event()
        resultado: dict = {}
        self.after(0, lambda: construir_dialogo(evento, resultado))
        evento.wait()
        return resultado

    # -- os dois usos --------------------------------------------------------
    def pausar_e_esperar(
        self,
        mensagem: str,
        texto_botao: str = dialogs.TEXTO_CONTINUAR,
    ) -> None:
        """Pausa para ação manual (login no portal). Volta quando liberado.

        Substitui os `messagebox.showinfo("Login Necessário", ...)` e as cópias
        de `_mostrar_janela_pausa`.
        """
        self._abrir_e_esperar(
            lambda evento, _resultado: dialogs.PausaLoginDialog(
                self, mensagem=mensagem, evento_espera=evento, texto_botao=texto_botao
            )
        )

    def perguntar_retry_excel(self, caminho: object = None) -> bool:
        """Arquivo travado no Excel: pergunta se deve tentar de novo.

        `True` = tentar novamente, `False` = ignorar e seguir. É o formato que
        `core/excel/locking.save_with_retry` espera em `on_locked`, e o canal
        `retry_lock` do `UICallbacks` (CP C) aponta para cá.

        Sem `caminho`, usa a mensagem histórica do `_STATUS_PMIB`; com ele,
        NOMEIA o arquivo travado — o que importa agora que a janela serve
        também `pdm`, `analyzer`, `autospec` e `translator`.
        """
        mensagem = (
            dialogs.msg_excel_bloqueado(caminho)
            if caminho is not None
            else dialogs.MSG_EXCEL_BLOQUEADO
        )
        resultado = self._abrir_e_esperar(
            lambda evento, res: dialogs.RetryLockDialog(
                self, mensagem=mensagem, evento_espera=evento, resultado=res
            )
        )
        return bool(resultado.get("retry", False))

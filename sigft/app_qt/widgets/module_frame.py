"""O esqueleto de uma tela: cabeçalho + conteúdo + (progresso) + console.

Mesma ideia e mesmos parâmetros do `ModuleFrame` CustomTkinter, mais duas
coisas que lá eram disciplina e aqui são mecanismo:

* `backend(nome)`: um backend que não carregou vira aviso com o motivo, nunca
  `AttributeError: 'NoneType'` (defeito 3 da revisão de 2026-10-07);
* `iniciar_tarefa(...)`: desabilita o botão NO CLIQUE (dois cliques não sobem
  dois robôs -- defeito 5), roda numa thread comum (o "X" pergunta antes de
  fechar) e, aconteça o que acontecer, devolve o botão e loga a exceção.
"""
from __future__ import annotations

import threading
import traceback

from PySide6.QtWidgets import (
    QLabel, QMessageBox, QProgressBar, QScrollArea, QVBoxLayout, QWidget,
)

from sigft.app import backends, theme
from sigft.app_qt import interface
from sigft.app_qt.widgets.console import ConsoleFrame
from sigft.app_qt.widgets.espera import DialogosDeEspera

# O padx/pady=20 com que o `show_frame` do CustomTkinter põe cada tela na janela.
MARGEM_DA_TELA = 20


def _reabilitar(botao) -> None:
    """Devolve o botão. A tela pode ter sido fechada antes de a tarefa acabar."""
    try:
        botao.setEnabled(True)
    except RuntimeError:
        pass  # widget já destruído pelo Qt: nada a devolver


class ModuleFrame(DialogosDeEspera, QWidget):
    def __init__(
        self,
        parent=None,
        controller=None,
        *,
        titulo: str,
        cor_titulo: str | None = None,
        peso_conteudo: int = 1,
        altura_console: int | None = theme.ALTURA_CONSOLE,
        com_progresso: bool = False,
        construir: bool = True,
        embutida: bool = False,
        console_externo=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("tela")
        self.controller = controller
        self.embutida = embutida
        raiz = QVBoxLayout(self)
        # As medidas do CustomTkinter somadas: `show_frame` põe a tela inteira
        # com padx=20/pady=20 (sigft/app/main.py), e o `ModuleFrame` de lá põe
        # header, conteúdo e console cada um com padx=PADDING_X/pady=PADDING_Y
        # (sigft/app/widgets/module_frame.py). O pady de dois vizinhos soma:
        # entre eles ficam 2 * PADDING_Y.
        raiz.setContentsMargins(MARGEM_DA_TELA + theme.PADDING_X, MARGEM_DA_TELA + theme.PADDING_Y,
                                MARGEM_DA_TELA + theme.PADDING_X, MARGEM_DA_TELA + theme.PADDING_Y)
        raiz.setSpacing(2 * theme.PADDING_Y)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)

        if embutida:
            # Dentro da aba de outra tela: sem cabeçalho nem console próprios, e
            # ROLÁVEL -- numa aba sobra menos altura, e o que não cabe sumiria.
            self.header = None
            self.label_titulo = None
            self.progress_bar = None
            self.console = console_externo
            rolagem = QScrollArea()
            rolagem.setWidgetResizable(True)
            rolagem.setWidget(self.content)
            raiz.setContentsMargins(0, 0, 0, 0)
            raiz.addWidget(rolagem)
        else:
            self.header = QWidget()
            linha_header = QVBoxLayout(self.header)
            linha_header.setContentsMargins(0, 0, 0, 0)
            self.label_titulo = QLabel(titulo, objectName="titulo_modulo")
            if cor_titulo:
                self.label_titulo.setStyleSheet(f"color: {cor_titulo};")
            linha_header.addWidget(self.label_titulo)
            # SEM `setFixedHeight(theme.ALTURA_HEADER)`: lá o título entra no
            # header com `pack`, e o quadro encolhe até a altura do título
            # (29 px medidos, não os 50 pedidos). Altura natural aqui também.
            raiz.addWidget(self.header)
            raiz.addWidget(self.content, peso_conteudo)
            self.progress_bar = None
            if com_progresso:
                self.progress_bar = QProgressBar()
                self.progress_bar.setRange(0, 1000)
                self.progress_bar.setTextVisible(False)
                raiz.addWidget(self.progress_bar)
            self.console = ConsoleFrame(altura=altura_console)
            raiz.addWidget(self.console, 0 if altura_console is not None else 1)

        if construir:
            self._build_ui()

    def _build_ui(self) -> None:
        raise NotImplementedError(f"{type(self).__name__} precisa implementar _build_ui().")

    def log(self, msg: object, nivel: str = "info", contexto: object | None = None) -> None:
        if self.console is not None:
            self.console.log(msg, nivel, contexto)

    def backend(self, nome: str):
        """O backend `nome`, ou `None` depois de avisar a pessoa do porquê.

        Pode ser chamado de uma thread de fundo: o aviso sempre aparece na
        thread da interface.
        """
        try:
            return backends.exigir(nome)
        except backends.BackendIndisponivel as erro:
            self.log(f"[ERRO] {erro}")
            if interface.na_thread_da_interface():
                QMessageBox.warning(self, "Módulo indisponível", str(erro))
            else:
                # As telas leem o backend dentro do worker; um QMessageBox criado
                # fora da thread da interface derruba o app (macOS).
                interface.na_interface(
                    QMessageBox.warning, self, "Módulo indisponível", str(erro))
            return None

    def iniciar_tarefa(self, alvo, *args, botao=None) -> threading.Thread:
        """Roda `alvo(*args)` numa thread comum. Chamar da thread da interface."""
        if botao is not None:
            botao.setEnabled(False)

        def rodar() -> None:
            try:
                alvo(*args)
            except Exception as erro:  # noqa: BLE001 -- vira log, e o botão volta
                self.log(f"[ERRO] {type(erro).__name__}: {erro}")
                traceback.print_exc()
            finally:
                if botao is not None:
                    interface.na_interface(_reabilitar, botao)

        thread = threading.Thread(target=rodar, name=f"tarefa:{type(self).__name__}")
        thread.start()
        return thread

"""O esqueleto de uma tela: cabeçalho + conteúdo + (progresso) + console.

Mesma ideia e mesmos parâmetros do `ModuleFrame` interface antiga, mais duas
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

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import (
    QLabel, QMessageBox, QProgressBar, QScrollArea, QVBoxLayout, QWidget,
)

from sigft.app import backends, textos_dicas, theme
from sigft.app import resumo_lote as resumo_regras
from sigft.app.idioma import t
from sigft.app_qt import aviso_windows, interface
from sigft.app_qt.widgets import arrastar
from sigft.app_qt.widgets import puxador_console
from sigft.app_qt.widgets.atividade import ROTULO_ITEM, FaixaDeAtividade
from sigft.app_qt.widgets.console import ConsoleFrame
from sigft.app_qt.widgets.espera import DialogosDeEspera
from sigft.app_qt.widgets import resumo_lote as janela_de_resumo

# O padx/pady=20 com que o `show_frame` da interface antiga põe cada tela na janela.
MARGEM_DA_TELA = 20


def aplicar_dicas(tela) -> None:
    """Põe em cada botão da tela a dica de `sigft/app/textos_dicas.py`."""
    for atributo, dica in textos_dicas.dicas_da_classe(type(tela)).items():
        widget = getattr(tela, atributo, None)
        if widget is not None and not widget.toolTip():
            widget.setToolTip(dica)


def _reabilitar(botao) -> None:
    """Devolve o botão. A tela pode ter sido fechada antes de a tarefa acabar."""
    try:
        botao.setEnabled(True)
    except RuntimeError:
        pass  # widget já destruído pelo Qt: nada a devolver


class ModuleFrame(DialogosDeEspera, QWidget):
    # Os botões da tela que recebem arquivo arrastado (2026-10-21): tuplas
    # `arrastar.Arrastavel(atributo, chave, extensoes, varios)`. A tela só declara;
    # a montagem liga (`arrastar.ligar_arrastaveis`).
    ARRASTAVEIS: tuple = ()

    def __init__(
        self,
        parent=None,
        controller=None,
        *,
        titulo: str,
        papel_titulo: str | None = None,
        peso_conteudo: int = 1,
        altura_console: int | None = theme.ALTURA_CONSOLE,
        com_progresso: bool = False,
        construir: bool = True,
        embutida: bool = False,
        console_externo=None,
        progresso_externo=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("tela")
        self.controller = controller
        self.embutida = embutida
        # O nome que o resumo e o aviso do Windows dão à tela (2026-10-21).
        self.titulo_da_tela = resumo_regras.nome_da_tela(titulo)
        # O console que a pessoa redimensiona (2026-10-21): a altura escolhida
        # arrastando a barrinha (`None` = a da tela) e a barrinha.
        self.altura_console_escolhida: int | None = None
        self.puxador_console = None
        self._padrao_do_console: list = []
        self._gravar_console = QTimer(self)
        self._gravar_console.setSingleShot(True)
        self._gravar_console.timeout.connect(self._gravar_altura_do_console)
        raiz = QVBoxLayout(self)
        # As medidas da interface antiga somadas: `show_frame` põe a tela inteira
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
            # A barra, como o console, é a da tela de fora (o PMIB Manager tem
            # uma para as três abas); sem ela, nenhuma.
            self.progress_bar = progresso_externo
            self.console = console_externo
            rolagem = QScrollArea()
            rolagem.setWidgetResizable(True)
            rolagem.setWidget(self.content)
            # Transparente como o CTkScrollableFrame(fg_color="transparent") de
            # lá: o `setWidget` liga o autoFill do conteúdo, que pintava a
            # paleta clara do Qt atrás do cartão.
            self.content.setAutoFillBackground(False)
            rolagem.viewport().setAutoFillBackground(False)
            raiz.setContentsMargins(0, 0, 0, 0)
            raiz.addWidget(rolagem)
            self.atividade = FaixaDeAtividade()
            raiz.addWidget(self.atividade)
        else:
            self.header = QWidget()
            linha_header = QVBoxLayout(self.header)
            linha_header.setContentsMargins(0, 0, 0, 0)
            self.label_titulo = QLabel(titulo, objectName="titulo_modulo")
            if papel_titulo:
                # A cor é da folha: `#titulo_modulo[papel=...]` (2026-10-20).
                self.label_titulo.setProperty("papel", papel_titulo)
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
            # A faixa "Rodando…" fica entre o conteúdo e o console: é onde o
            # olho já está quando se clica no botão. Escondida quando nada roda.
            self.atividade = FaixaDeAtividade()
            raiz.addWidget(self.atividade)
            self.console = ConsoleFrame(altura=altura_console)
            raiz.addWidget(self.console, 0 if altura_console is not None else 1)

        self._tarefas_rodando = 0
        self._tarefa_falhou = False
        # A linha do console em que o lote atual começou (`console.marca`).
        self._marca_console = 0
        self.receptores_de_arquivo: dict = {}
        if construir:
            self._build_ui()
            aplicar_dicas(self)
            self.receptores_de_arquivo = arrastar.ligar_arrastaveis(self, self.ARRASTAVEIS)
            if not embutida and self.console is not None:
                self._ligar_puxador_do_console()

    # -- o console redimensionável (2026-10-21) ------------------------------------
    def _alvos_do_console(self) -> list:
        """As peças que levam a altura escolhida. A Correção de PDM soma a faixa
        em que o console fica."""
        return [self.console]

    def _console_voltou_ao_padrao(self) -> None:
        """Gancho das telas que repartem a altura no `resizeEvent`."""

    def _ligar_puxador_do_console(self) -> None:
        # Medido no fim da montagem, ANTES do primeiro `_repartir_altura` (que só
        # vem no `resizeEvent`) da Criação, da Cópia e da Correção: lá o mínimo e
        # o máximo guardados não são a altura da tela. Voltar ao padrão ainda dá
        # certo porque elas recalculam no `_console_voltou_ao_padrao`, depois de
        # devolvidos o mínimo e o máximo.
        self._padrao_do_console = [(w, w.minimumHeight(), w.maximumHeight())
                                   for w in self._alvos_do_console()]
        self.puxador_console = puxador_console.PuxadorDoConsole(self)
        guardada = puxador_console.ler_altura(self)
        if guardada is not None:
            # O mínimo de agora é o da fonte antes do polimento: a escolha fica
            # como foi guardada, e o `_ajustar_console_ao_espaco` (no resize e na
            # troca de fonte) acerta o mínimo de verdade.
            self.altura_console_escolhida = guardada
            self._aplicar_altura_do_console(max(guardada, self._altura_minima_do_console()))

    def _altura_minima_do_console(self) -> int:
        return puxador_console.altura_minima_do_console(self.console)

    def altura_do_console(self) -> int:
        """A altura da peça de fora do console (na Correção de PDM, a faixa)."""
        return self._alvos_do_console()[0].height()

    def base_do_console_global(self) -> int:
        """O y global do fim da peça de fora do console: o que não se mexe
        quando o console muda de altura."""
        alvo = self._alvos_do_console()[0]
        return alvo.mapToGlobal(QPoint(0, alvo.height())).y()

    def limites_do_console(self) -> tuple[int, int]:
        """(mínimo, máximo) da altura agora: o máximo deixa ao conteúdo o que
        ele pede, e nunca menos que `MIN_CONTEUDO`."""
        minimo = self._altura_minima_do_console()
        return minimo, max(minimo, self._altura_que_cabe())

    def _altura_que_cabe(self) -> int:
        """A maior altura do console com o resto da tela no mínimo dela: a
        folga do layout (altura da tela menos o mínimo do layout, que já conta
        o console de agora) vai toda para o console, menos o que falta para o
        conteúdo ter `MIN_CONTEUDO`. Medir a folga, e não a altura do conteúdo,
        conta também o vão vazio das telas de conteúdo com peso 0 (Busca e
        Gestão), em que a sobra não vai para o conteúdo."""
        folga = self.height() - self.layout().minimumSize().height()
        falta = max(0, puxador_console.MIN_CONTEUDO - self.content.minimumSizeHint().height())
        return self.altura_do_console() + folga - falta

    def _aplicar_altura_do_console(self, altura: int) -> None:
        for widget in self._alvos_do_console():
            if widget.minimumHeight() != altura or widget.maximumHeight() != altura:
                widget.setFixedHeight(altura)

    def escolher_altura_do_console(self, altura: int) -> None:
        """A altura que a pessoa arrastou. Grava daqui a pouco."""
        self.altura_console_escolhida = int(altura)
        self._aplicar_altura_do_console(self.altura_console_escolhida)
        self._gravar_console.start(puxador_console.MS_PARA_GRAVAR)

    def console_ao_padrao(self) -> None:
        """O duplo clique: a altura da tela de volta, e o guardado esquecido."""
        self.altura_console_escolhida = None
        for widget, minimo, maximo in self._padrao_do_console:
            widget.setMinimumHeight(minimo)
            widget.setMaximumHeight(maximo)
        self._console_voltou_ao_padrao()
        self._gravar_console.stop()
        puxador_console.gravar_altura(self, None)

    def _gravar_altura_do_console(self) -> None:
        if self.puxador_console is not None:
            puxador_console.gravar_altura(self, self.altura_console_escolhida)

    def _ajustar_console_ao_espaco(self) -> None:
        """Janela menor: o console escolhido encolhe até o conteúdo ter o que
        pede; janela maior: volta à altura escolhida. A escolha fica."""
        if self.altura_console_escolhida is None or self.puxador_console is None:
            return
        minimo = self._altura_minima_do_console()
        altura = max(minimo, min(self.altura_console_escolhida, self._altura_que_cabe()))
        self._aplicar_altura_do_console(altura)

    def resizeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().resizeEvent(evento)
        self._ajustar_console_ao_espaco()

    def hideEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # Escondeu (trocou de tela, fechou o app) com a gravação esperando: grava já.
        if self._gravar_console.isActive():
            self._gravar_console.stop()
            self._gravar_altura_do_console()
        super().hideEvent(evento)

    def _build_ui(self) -> None:
        raise NotImplementedError(f"{type(self).__name__} precisa implementar _build_ui().")

    def log(self, msg: object, nivel: str = "info", contexto: object | None = None) -> None:
        if self.console is not None:
            self.console.log(msg, nivel, contexto)

    def rodando(self) -> bool:
        """Alguma tarefa da tela (`iniciar_tarefa`) ainda roda. A aba ao lado pergunta
        antes de usar o que esta produz (a Revisão no AMP espera a Conferência)."""
        return self._tarefas_rodando > 0

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
                QMessageBox.warning(self, t("Módulo indisponível"), str(erro))
            else:
                # As telas leem o backend dentro do worker; um QMessageBox criado
                # fora da thread da interface derruba o app (macOS).
                interface.na_interface(
                    QMessageBox.warning, self, t("Módulo indisponível"), str(erro))
            return None

    def iniciar_tarefa(self, alvo, *args, botao=None) -> threading.Thread:
        """Roda `alvo(*args)` numa thread comum. Chamar da thread da interface.

        Liga a faixa "Rodando…" (`FaixaDeAtividade`) e a desliga quando a
        última tarefa da tela acaba, dizendo se ela terminou bem ou com erro.
        """
        if botao is not None:
            botao.setEnabled(False)
        if self._tarefas_rodando == 0:
            self._tarefa_falhou = False
            self._marca_console = self._marca_do_console()
            self.atividade.comecar()
        self._tarefas_rodando += 1

        def rodar() -> None:
            ok = True
            try:
                alvo(*args)
            except Exception as erro:  # noqa: BLE001 -- vira log, e o botão volta
                ok = False
                self.log(f"[ERRO] {type(erro).__name__}: {erro}")
                traceback.print_exc()
            finally:
                if botao is not None:
                    interface.na_interface(_reabilitar, botao)
                interface.na_interface(self._tarefa_acabou, ok)

        thread = threading.Thread(target=rodar, name=f"tarefa:{type(self).__name__}")
        thread.start()
        return thread

    def _tarefa_acabou(self, ok: bool) -> None:
        """Na thread da interface. A tela pode ter sido fechada antes."""
        try:
            self._tarefas_rodando = max(self._tarefas_rodando - 1, 0)
            self._tarefa_falhou = self._tarefa_falhou or not ok
            if self._tarefas_rodando == 0:
                self.atividade.terminar(ok=not self._tarefa_falhou)
                self._fim_do_lote()
        except RuntimeError:
            pass  # widget já destruído pelo Qt

    def _marca_do_console(self) -> int:
        # A tela embutida usa o console da tela de fora (`console_externo`), que
        # pode não ser um `ConsoleFrame`: sem `marca`, não há resumo.
        marca = getattr(self.console, "marca", None)
        return marca() if callable(marca) else 0

    def pares_do_lote(self) -> list[tuple[str, str]]:
        """(mensagem, nível) do que o lote que acabou escreveu no console."""
        linhas = getattr(self.console, "linhas", None)
        if not callable(linhas):
            return []
        return [(linha.msg, linha.nivel) for linha in linhas(desde=self._marca_console)]

    def _fim_do_lote(self) -> None:
        """Na thread da interface, quando a ÚLTIMA tarefa da tela acaba: com erro
        ou aviso no console, a janela de resumo (2026-10-21). E o aviso do Windows,
        se o SIG-FT está fora de foco. Nunca levanta: o fim da tarefa já
        aconteceu, e um defeito aqui não pode prender o botão."""
        try:
            pares = self.pares_do_lote()
            grupos = resumo_regras.agrupar(pares)
        except Exception:  # noqa: BLE001 -- vira traceback no log
            traceback.print_exc()
            return
        # O aviso do Windows ANTES do resumo: o foco é lido antes de a janela
        # nova aparecer, e um defeito num não cala o outro (2026-10-21).
        try:
            erros, avisos = resumo_regras.contar(grupos)
            aviso_windows.avisar(self.window(), resumo_regras.frase_do_fim(
                self.titulo_da_tela, erros, avisos, falhou=self._tarefa_falhou))
        except Exception:  # noqa: BLE001 -- vira traceback no log
            traceback.print_exc()
        try:
            if grupos and resumo_regras.ligado():
                janela_de_resumo.abrir_resumo(self, self.titulo_da_tela, pares)
        except Exception:  # noqa: BLE001 -- vira traceback no log
            traceback.print_exc()

    def informar_progresso(self, atual: int, total: int, rotulo: str = ROTULO_ITEM) -> None:
        """"Ficha 3 de 8" na faixa. Chamável de qualquer thread."""
        interface.na_interface(self.atividade.progresso, atual, total, rotulo)

"""Janelas que param o robô à espera da pessoa. Mesmos textos de hoje.

Regra que não pode ser esquecida: fechar no "X" SEMPRE solta o worker, com a
resposta mais segura (continuar o login; não repetir a gravação). Sem isso, a
thread do robô fica presa em `Event.wait()` para sempre.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStyledItemDelegate, QVBoxLayout,
)

from sigft.app import theme
from sigft.app.textos_dialogos import MSG_EXCEL_BLOQUEADO, TEXTO_CONTINUAR
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos, controles
# Botão das janelas que seguram o robô: nenhuma tecla o aperta. Mora em `blocos`
# desde o polimento (todo `blocos.botao` nasce assim); o nome continua aqui.
from sigft.app_qt.widgets.blocos import sem_tecla

# CTkCheckBox na lista de lá: caixa de 24, `pack(pady=2)` -> uma linha a cada 28;
# o texto começa `controles.VAO_TEXTO_CAIXA` (6) px depois da caixa.
ALTURA_LINHA_CAIXA = 28
# O wraplength=400 do texto das janelas de ação manual.
LARGURA_QUEBRA_TEXTO = 400


class IgnoraEsc:
    """Mixin (antes do QDialog): Esc não fecha. O Tk não tinha tecla nenhuma
    nas janelas de seleção e de revisão, e nelas fechar tem custo: jogar fora
    uma escolha feita item a item, o que foi digitado, ou parar um lote. O
    "X" continua fechando (e cancelando) normalmente."""

    def keyPressEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if evento.key() == Qt.Key.Key_Escape:
            evento.accept()
            return
        super().keyPressEvent(evento)


class SoltaAoFechar:
    """Mixin (antes do QDialog) das janelas em que um worker espera a resposta.

    Fechar no "X", Esc ou qualquer `reject()` responde `_ao_fechar_sem_decidir()`
    se ninguém decidiu ainda -- sem isso a thread do robô fica presa em
    `Event.wait()`. Quem decide (um botão) põe `_decidido = True` antes.
    """

    _decidido = False

    def _ao_fechar_sem_decidir(self) -> None:
        raise NotImplementedError

    def reject(self) -> None:
        """Esc (e qualquer `reject()`) esconde o diálogo SEM passar pelo
        `closeEvent`; sem isto o worker ficaria preso. Só responde se ainda
        ninguém decidiu -- os botões já responderam antes de chamar `reject()`."""
        if not self._decidido:
            self._ao_fechar_sem_decidir()
        super().reject()

    def closeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if not self._decidido:
            self._ao_fechar_sem_decidir()
        super().closeEvent(evento)


class _DialogoDeAcaoManual(SoltaAoFechar, QDialog):
    def __init__(self, parent, *, titulo: str, mensagem: str, largura: int, altura: int,
                 pady_texto: int) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setFixedSize(largura, altura)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._decidido = False
        # Medidas do CTk (E4.4/E4.5, capturas/e4.45): o texto vai com
        # pady=`pady_texto` e `expand=True` (centrado na sobra acima dos
        # botões), padx=20 e wraplength=400; os botões com pady=(0, 20).
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(20, 0, 20, 20)
        self.layout_principal.setSpacing(0)
        self.layout_principal.addSpacing(pady_texto)
        self.rotulo = QLabel(mensagem)
        self.rotulo.setWordWrap(True)
        self.rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo.setMaximumWidth(LARGURA_QUEBRA_TEXTO)
        self.rotulo.setStyleSheet(f"font-size: 13px; color: {controles.COR_TEXTO_CTK};")
        # Numa linha com sobras dos lados (e não com `alignment`): com alinhamento,
        # o QLabel com quebra escolhe uma largura estreita e quebra cedo demais.
        linha_texto = QHBoxLayout()
        linha_texto.addStretch()
        linha_texto.addWidget(self.rotulo, 100)
        linha_texto.addStretch()
        self.layout_principal.addLayout(linha_texto, 1)
        self.layout_principal.addSpacing(pady_texto)


class PausaLoginDialog(_DialogoDeAcaoManual):
    """"Ação Manual Necessária" com um botão: continuar a automação."""

    def __init__(self, parent, *, mensagem: str, evento_espera, texto_botao: str = TEXTO_CONTINUAR) -> None:
        super().__init__(parent, titulo="Ação Manual Necessária", mensagem=mensagem,
                         largura=450, altura=250, pady_texto=30)
        self._evento = evento_espera
        # height=45 e FONTE_BOTAO (Roboto 14 bold); a largura é a do CTkButton:
        # 140, ou o texto + 7 px de cada lado (195 com "CONTINUAR AUTOMAÇÃO").
        self.botao = blocos.botao(texto_botao, variante="primario", altura=45, tamanho_fonte=14,
                                  negrito=True, largura_minima=estilo.LARGURA_BOTAO_CTK)
        sem_tecla(self.botao)
        self.botao.clicked.connect(self.liberar)
        self.layout_principal.addWidget(self.botao, 0, Qt.AlignmentFlag.AlignHCenter)

    def liberar(self) -> None:
        self._decidido = True
        self._evento.set()
        self.accept()

    def _ao_fechar_sem_decidir(self) -> None:
        self._decidido = True
        self._evento.set()


class RetryLockDialog(_DialogoDeAcaoManual):
    """"Arquivo Bloqueado": Tentar Novamente × Ignorar e Continuar (chave "retry")."""

    def __init__(self, parent, *, mensagem: str = MSG_EXCEL_BLOQUEADO, evento_espera, resultado: dict) -> None:
        super().__init__(parent, titulo="Arquivo Bloqueado", mensagem=mensagem,
                         largura=450, altura=200, pady_texto=20)
        self._evento = evento_espera
        self._resultado = resultado
        # Dois botões de 150x40 com padx=10, o par centrado.
        linha = QHBoxLayout()
        linha.setSpacing(20)
        linha.addStretch()
        # fg_color=primary SEM hover_color lá: o hover é o do tema (#14375E).
        self.botao_repetir = blocos.botao("Tentar Novamente", cor_fundo=theme.COLORS["primary"],
                                          largura=150, altura=40)
        self.botao_cancelar = blocos.botao("Ignorar e Continuar", variante="contorno", largura=150, altura=40)
        for botao in (self.botao_repetir, self.botao_cancelar):
            sem_tecla(botao)
            linha.addWidget(botao)
        linha.addStretch()
        self.botao_repetir.clicked.connect(self.repetir)
        self.botao_cancelar.clicked.connect(self.cancelar)
        self.layout_principal.addLayout(linha)

    def _responder(self, repetir: bool) -> None:
        self._decidido = True
        self._resultado["retry"] = repetir
        self._evento.set()

    def repetir(self) -> None:
        self._responder(True)
        self.accept()

    def cancelar(self) -> None:
        self._responder(False)
        self.reject()

    def _ao_fechar_sem_decidir(self) -> None:
        self._responder(False)


class _DelegadoDaCaixa(QStyledItemDelegate):
    """Cada linha da lista desenhada como uma CTkCheckBox (caixa de 24 + texto).

    Clicar na caixa OU no texto alterna, como lá; o resto da linha, não.
    """

    def __init__(self, parent, *, cor_marcada: str) -> None:
        super().__init__(parent)
        self._cor_marcada = cor_marcada

    @staticmethod
    def _marcada(index) -> bool:
        valor = index.data(Qt.ItemDataRole.CheckStateRole)
        return valor in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 -- nome do Qt
        return QSize(option.rect.width(), ALTURA_LINHA_CAIXA)

    def paint(self, pintor, option, index) -> None:
        r = option.rect
        # pack(pady=2): a caixa fica 2 px abaixo do topo da linha de 28.
        controles.pintar_caixa(pintor, r.x(), r.y() + 2, self._marcada(index), self._cor_marcada)
        pintor.save()
        pintor.setPen(QColor(controles.COR_TEXTO_CTK))
        pintor.setFont(option.font)
        x_texto = r.x() + controles.LADO_CAIXA + controles.VAO_TEXTO_CAIXA
        pintor.drawText(QRect(x_texto, r.y(), r.right() - x_texto, r.height()),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        index.data(Qt.ItemDataRole.DisplayRole))
        pintor.restore()

    def editorEvent(self, evento, modelo, option, index) -> bool:  # noqa: N802 -- nome do Qt
        tipo = evento.type()
        if tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            return True  # sem seleção nem edição: só o soltar do botão conta
        if tipo != QEvent.Type.MouseButtonRelease or evento.button() != Qt.MouseButton.LeftButton:
            return False
        texto = index.data(Qt.ItemDataRole.DisplayRole) or ""
        alcance = (controles.LADO_CAIXA + controles.VAO_TEXTO_CAIXA
                   + option.fontMetrics.horizontalAdvance(texto))
        if evento.position().x() - option.rect.x() <= alcance:
            novo = Qt.CheckState.Unchecked if self._marcada(index) else Qt.CheckState.Checked
            modelo.setData(index, novo, Qt.ItemDataRole.CheckStateRole)
        return True


class SelecaoComCaixasDialog(IgnoraEsc, QDialog):
    """Lista com caixas de marcar + "Todos" + "CONFIRMAR".

    É a janela de seleção de fichas da Aplicação LMR (450x600). A lista é um
    QListWidget: desenha só as linhas visíveis, ao contrário de um widget por
    ficha -- com centenas de PMIBs a diferença aparece. Cada linha é pintada
    como a CTkCheckBox de lá (`_DelegadoDaCaixa`), dentro de um quadro como o
    CTkScrollableFrame.

    Esc não fecha (`IgnoraEsc`): as fichas podem ter sido marcadas uma a uma.
    """

    def __init__(self, parent, *, titulo: str, mensagem: str, itens: list[str],
                 cor_caixa: str = theme.COLORS["primary"]) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(450, 600)
        # Espaços do `pack` de lá; o pady de dois vizinhos SOMA no Tk.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addSpacing(10)                           # rótulo: pady=10
        self.rotulo = blocos.rotulo(mensagem, tamanho=14, negrito=True, cor=controles.COR_TEXTO_CTK)
        layout.addWidget(self.rotulo)
        layout.addSpacing(15)                           # rótulo (…, 10) + quadro (5, …)
        # CTkScrollableFrame(padx=10): quadro #212121 de cantos 6; a lista começa
        # 6 px para dentro, e a barra de rolagem (16 px) encosta 1 px da borda.
        self.quadro = QFrame(objectName="quadro_caixas")
        dentro = QVBoxLayout(self.quadro)
        dentro.setContentsMargins(6, 6, 1, 6)
        self.lista = QListWidget(objectName="lista_caixas")
        self.lista.setItemDelegate(_DelegadoDaCaixa(self.lista, cor_marcada=cor_caixa))
        self.lista.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.lista.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lista.setUniformItemSizes(True)
        self.lista.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        for texto in itens:
            item = QListWidgetItem(texto)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.lista.addItem(item)
        dentro.addWidget(self.lista)
        linha_quadro = QHBoxLayout()
        linha_quadro.setContentsMargins(10, 0, 10, 0)
        linha_quadro.addWidget(self.quadro)
        layout.addLayout(linha_quadro, 1)
        layout.addSpacing(15)                           # quadro (…, 5) + botões (10, …)
        linha = QHBoxLayout()
        linha.setContentsMargins(10, 0, 10, 0)          # Todos: padx=10; CONFIRMAR: padx=10
        self.botao_todos = blocos.botao("Todos", variante="cinza", largura=80)
        self.botao_todos.clicked.connect(self._marcar_todos)
        self.botao_confirmar = blocos.botao("CONFIRMAR", variante="acento", largura=150,
                                            cor_texto="#161616")
        self.botao_confirmar.clicked.connect(self.accept)
        linha.addWidget(self.botao_todos)
        linha.addStretch()
        linha.addWidget(self.botao_confirmar)
        layout.addLayout(linha)
        layout.addSpacing(10)                           # botões: pady=10

    def _marcar_todos(self) -> None:
        for i in range(self.lista.count()):
            self.lista.item(i).setCheckState(Qt.CheckState.Checked)

    def selecionados(self) -> list[str]:
        return [self.lista.item(i).text() for i in range(self.lista.count())
                if self.lista.item(i).checkState() == Qt.CheckState.Checked]

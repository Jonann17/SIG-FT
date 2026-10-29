"""A boas-vindas: a página que aparece no lugar da Home na primeira abertura (2026-10-28).

Ideia do Corella Automation (`corella_suite/ui/boas_vindas.py`, v1.4.0): quem
abre pela primeira vez escolhe por onde começar, e cada escolha leva à tela
certa. Desenho: `docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`,
parte 2.

NÃO É MODAL. É uma página da pilha da janela principal, registrada em
`main.TELAS` (chave `main.CHAVE_BOAS_VINDAS`) mas FORA do menu lateral: diálogo
na montagem da janela bloqueia a abertura (e num teste, a suíte), e a pessoa
sempre pode sair pelo menu. Quando aparece sozinha é decisão de
`sigft/app/boas_vindas.py` (sem Qt); reabre pelo Ctrl+K ("Boas-vindas") e pela
Configuração (seção Ajuda).

Sair por "Ir para o início" ou por um caminho grava `boas_vindas_vista`. Sair
pelo menu lateral ou pelo Ctrl+K NÃO grava, de propósito: quem fecha sem
escolher vê de novo. A página só sai de cena para sempre quando a pessoa
escolheu por onde começar; quem a pulou pelo menu (ou nem a leu) a encontra na
próxima abertura, até escolher, e o rastro de uso que o trabalho num módulo
deixa (`core/rastros_de_uso.py`) a desliga sozinho. Os
cliques vão para MÉTODOS da página (um sinal do cartão), nunca para `lambda` com
`self`: o ciclo que ela cria é destruído depois do app, e a saída cai.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from sigft.app import boas_vindas as regra
from sigft.app.idioma import marcar, t
from sigft.app_qt import catalogo, estilo, icones
from sigft.app_qt.widgets import blocos

TITULO = marcar("Bem-vindo ao SIG-FT")
FRASE = marcar("Ele cria as fichas técnicas dos sobressalentes de Itaipu no Portal PMIB, completa as que "
               "já existem e acompanha as listas. Por onde você quer começar?")

# Os três caminhos: a tela que abre (chave de `catalogo.MENU`), o título e o que é.
CAMINHOS = (
    ("CriaFichas", marcar("Criar fichas novas"),
     marcar("Você tem a lista de materiais e as fichas ainda não existem no portal. "
            "Abre o Cria Fichas PMIB.")),
    ("UploadConditions", marcar("Completar fichas que já existem"),
     marcar("As fichas já estão no portal e faltam condições, características ou aplicações (LMR). "
            "Começa pelo Upload de Condições; os outros estão logo abaixo dele, no menu.")),
    ("PMIBManager", marcar("Acompanhar as listas de sobressalentes"),
     marcar("Atualiza o mapeamento pelo Aconex, confere as revisões das listas e calcula o avanço. "
            "Abre o PMIB Manager.")),
)

# Os lembretes do pé: ícone e texto.
LEMBRETES = (
    ("circle-help", marcar("Cada tela tem, logo abaixo do título, o botão \"Como funciona\": o que ela "
                           "espera receber, o que ela muda e o que acontece se parar no meio.")),
    ("search", marcar("Ctrl+K abre a busca: digite o nome de um módulo ou de uma ação (tema, letra, "
                      "logs) e aperte Enter.")),
)

TEXTO_INICIO = marcar("Ir para o início")
DICA_INICIO = marcar("Abre a Home. Para ver esta página de novo: Ctrl+K, \"Boas-vindas\", ou a "
                     "Configuração, em Ajuda.")

# Medidas: as margens da Home (o conteúdo começa no mesmo x), o cartão de caminho
# mais alto que o da Home (é a escolha da página) e o ícone dele.
MARGENS = (46, 46, 57, 20)
ALTURA_MINIMA_CARTAO = 140
TAMANHO_ICONE_CARTAO = 28
TAMANHO_ICONE_LEMBRETE = 18
ALTURA_BOTAO_INICIO = 36

# As teclas que escolhem o cartão com foco, como num botão.
TECLAS_QUE_ESCOLHEM = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)


class CartaoDeCaminho(QFrame):
    """Um caminho: ícone da tela, título e descrição. Clicar emite `escolhido(alvo)`.
    Bloqueado: apagado, com a dica do menu, e o clique não faz nada."""

    escolhido = Signal(str)

    def __init__(self, alvo: str, titulo: str, descricao: str, parent=None) -> None:
        super().__init__(parent, objectName="card")
        self.alvo = alvo
        self.setProperty("caminho", True)
        self.setMinimumHeight(ALTURA_MINIMA_CARTAO)
        bloqueado = alvo in catalogo.TELAS_BLOQUEADAS
        self.setEnabled(not bloqueado)
        self.setCursor(Qt.CursorShape.ArrowCursor if bloqueado else Qt.CursorShape.PointingHandCursor)
        # Pelo teclado também (fix round 2026-10-28): o Tab chega no cartão, Enter
        # ou Espaço escolhem, e o foco aparece (`#card[caminho="true"]:focus`, em
        # `estilo`, pelos papéis do tema).
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(catalogo.dica_do_menu(alvo))
        self.setAccessibleName(titulo)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(18, 16, 18, 16)
        # O conteúdo vai num quadro alinhado ao topo: na linha, a sobra do cartão
        # mais baixo fica embaixo. Um `addStretch` (ou fator de estica) deixaria o
        # cartão "expansível", e os três cresceriam com a janela em vez de a sobra
        # ficar no pé da página.
        conteudo = QWidget()
        conteudo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.icone = QLabel(objectName="card_icone")
        icones.aplicar(self.icone, catalogo.ICONE_DA_TELA[alvo],
                       papel_cor="texto_suave" if bloqueado else "primaria", tamanho=TAMANHO_ICONE_CARTAO)
        layout.addWidget(self.icone)
        self.titulo = QLabel(titulo, objectName="card_titulo")
        self.titulo.setWordWrap(True)
        layout.addWidget(self.titulo)
        self.descricao = QLabel(descricao, objectName="card_desc")
        self.descricao.setWordWrap(True)
        layout.addWidget(self.descricao)
        externo.addWidget(conteudo, 0, Qt.AlignmentFlag.AlignTop)
        for rotulo in self.findChildren(QLabel):
            rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def keyPressEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if evento.key() in TECLAS_QUE_ESCOLHEM and not evento.isAutoRepeat():
            evento.accept()
            if self.isEnabled():
                self.escolhido.emit(self.alvo)
            return
        super().keyPressEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # No soltar, como um botão: quem aperta e arrasta para fora desiste.
        if (self.isEnabled() and evento.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(evento.position().toPoint())):
            self.escolhido.emit(self.alvo)
        super().mouseReleaseEvent(evento)


class BoasVindasView(QScrollArea):
    def __init__(self, parent=None, controller=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWidgetResizable(True)
        self.setObjectName("conteudo")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        corpo = QWidget(objectName="conteudo")
        layout = QVBoxLayout(corpo)
        layout.setContentsMargins(*MARGENS)
        layout.setSpacing(0)

        self.titulo = QLabel(t(TITULO), objectName="titulo_home")
        self.titulo.setWordWrap(True)
        layout.addWidget(self.titulo)
        layout.addSpacing(8)
        self.frase = QLabel(t(FRASE), objectName="subtitulo_home")
        self.frase.setWordWrap(True)
        layout.addWidget(self.frase)
        layout.addSpacing(28)

        grade = QGridLayout()
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setHorizontalSpacing(16)
        self.cartoes: dict[str, CartaoDeCaminho] = {}
        for coluna, (alvo, titulo, descricao) in enumerate(CAMINHOS):
            cartao = CartaoDeCaminho(alvo, t(titulo), t(descricao))
            cartao.escolhido.connect(self.escolher)
            self.cartoes[alvo] = cartao
            grade.addWidget(cartao, 0, coluna)
            grade.setColumnStretch(coluna, 1)
        layout.addLayout(grade)
        layout.addSpacing(24)

        quadro = QFrame(objectName="cartao")
        lembretes = QVBoxLayout(quadro)
        lembretes.setContentsMargins(16, 12, 16, 12)
        lembretes.setSpacing(8)
        self.lembretes: list[QLabel] = []
        for nome_icone, texto in LEMBRETES:
            lembretes.addLayout(self._lembrete(nome_icone, t(texto)))
        layout.addWidget(quadro)
        layout.addSpacing(24)

        self.btn_inicio = blocos.botao(t(TEXTO_INICIO), variante="primario", altura=ALTURA_BOTAO_INICIO,
                                       largura_minima=estilo.LARGURA_BOTAO_CTK)
        icones.aplicar(self.btn_inicio, "house", tamanho=16)
        self.btn_inicio.setToolTip(t(DICA_INICIO))
        self.btn_inicio.clicked.connect(self.ir_para_o_inicio)
        layout.addWidget(self.btn_inicio, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        self.setWidget(corpo)

    def _lembrete(self, nome_icone: str, texto: str) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(10)
        marca = QLabel(objectName="card_icone")
        icones.aplicar(marca, nome_icone, papel_cor="primaria", tamanho=TAMANHO_ICONE_LEMBRETE)
        linha.addWidget(marca, 0, Qt.AlignmentFlag.AlignTop)
        rotulo = QLabel(texto, objectName="texto_simples")
        rotulo.setWordWrap(True)
        self.lembretes.append(rotulo)
        linha.addWidget(rotulo, 1)
        return linha

    # --- os cliques ------------------------------------------------------------------
    def escolher(self, alvo: str) -> None:
        """Um caminho: grava a vista e abre a tela dele (pelo funil de sempre)."""
        if alvo in catalogo.TELAS_BLOQUEADAS:
            return
        regra.marcar_vista()
        if self.controller is not None:
            self.controller.show_frame(alvo)

    def ir_para_o_inicio(self) -> None:
        """"Ir para o início": grava a vista e mostra a Home."""
        regra.marcar_vista()
        if self.controller is not None:
            self.controller.show_home()

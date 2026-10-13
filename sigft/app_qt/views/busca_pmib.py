"""Tela "Search PMIB" (Busca de Sobressalentes) na interface Qt.

Mesma tela de `sigft/app/views/busca_pmib.py`: procura fichas numa árvore de
pastas e mostra cada achado num cartão, com atalhos para abrir o arquivo e a
pasta. O que muda é só COMO o worker fala com a interface: lá o botão voltava
e a janela abria por `self.after` (disciplina); aqui o botão é de
`iniciar_tarefa` e a janela abre por `interface.na_interface` (mecanismo).
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QRadioButton, QVBoxLayout, QWidget,
)

from sigft.app import theme
from sigft.app_qt import estilo, file_dialogs, interface
from sigft.app_qt.widgets import blocos, controles
from sigft.app_qt.widgets.module_frame import MARGEM_DA_TELA, ModuleFrame
from sigft.core import plataforma

COLUNAS = ["DESCRIÇÃO", "CÓDIGO DO MATERIAL", "CÓDIGO CMI", "MARCA/MODELO", "CÓDIGO PMIB"]
# O #3A3A3A/#454545 que a tela antiga escrevia à mão nos botões e no menu.
CINZA, CINZA_SETA = "#3A3A3A", "#454545"
LARGURA_ROTULO = 150


def _altura_do_textbox(texto, largura_em_caracteres=90, altura_da_linha=20, folga=12):
    """Altura em pixels para a caixa de texto do cartão caber `texto` sem cortar.

    A MESMA conta da tela antiga (`sigft/app/views/busca_pmib.py`, que importa
    o Tk e por isso não pode ser importada daqui): quebras de linha reais mais
    as que o `wrap="word"` vai fazer, 20 px por linha e 12 de folga. Copiada
    em vez de trocada por uma medida da fonte do Qt para os cartões terem a
    mesma altura nas duas interfaces. Subestimar caracteres por linha é o lado
    seguro: sobra altura, não falta (e, se faltar, a caixa rola).
    """
    linhas = texto.split("\n")
    # `-(-a // b)` é divisão para cima: uma linha de 91 caracteres ocupa 2.
    total = sum(max(1, -(-len(linha) // largura_em_caracteres)) for linha in linhas)
    return max(35, total * altura_da_linha + folga)


def _rotulo_da_linha(texto: str, largura: int | None = LARGURA_ROTULO) -> QLabel:
    """CTkLabel de uma linha, `anchor="w"`, texto gray84 (o do tema), fonte 13."""
    r = QLabel(texto)
    r.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    r.setFixedHeight(blocos.ALTURA_MINIMA_ROTULO)
    if largura:
        r.setFixedWidth(largura)
    r.setStyleSheet(f"font-size: 13px; background: transparent; color: {controles.COR_TEXTO_CTK};")
    return r


def _botao_cinza(texto: str, largura: int) -> QPushButton:
    """O CTkButton #3A3A3A (hover #454545) que a tela escrevia à mão: a variante "cinza".

    Sem o padding de 14 da folha do app (regra própria, somada à do `blocos`):
    o texto que passa da largura transborda centrado, como no CTk, em vez de
    ser cortado pela margem ("Buscar Pasta" em 100 px, "Abrir Arquivo" em 120).
    """
    b = blocos.botao(texto, variante="cinza", largura=largura, altura=28)
    b.setStyleSheet(b.styleSheet() + " QPushButton { padding: 0; }")
    return b


def _caixa_de_texto(texto: str, *, fonte: tuple, cor: str) -> QPlainTextEdit:
    """CTkTextbox transparente, sem borda e desabilitado (dá para selecionar e copiar)."""
    caixa = QPlainTextEdit()
    caixa.setReadOnly(True)
    caixa.setFrameShape(QFrame.Shape.NoFrame)
    caixa.setPlainText(texto)
    # A conta da tela antiga, sobre o texto que ela via (sem o seletor U+FE0E do `mono`).
    caixa.setFixedHeight(_altura_do_textbox(texto.replace("\ufe0e", "")))
    caixa.document().setDocumentMargin(0)
    caixa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    # O tk.Text do CTkTextbox fica 6 px para dentro (o canto), e a primeira letra
    # sai 2 px mais à direita e 3 abaixo do que no Qt (medido nas capturas):
    # padding 9/8 em cima/à esquerda, e a soma vertical continua 12 (a folga).
    caixa.setStyleSheet(
        f"QPlainTextEdit {{ background: transparent; border: none; color: {cor};"
        " padding: 9px 6px 3px 8px;"
        f" selection-background-color: {estilo.AZUL_CTK}; {blocos.folha_fonte_tk(fonte)} }}")
    caixa.viewport().setStyleSheet("background: transparent;")
    return caixa


class CartaoResultado(QFrame):
    """Um achado: PMIB, coluna, caminho, amostra (se houver) e os dois botões."""

    def __init__(self, resultado: dict, *, abrir_arquivo, abrir_pasta) -> None:
        super().__init__()
        self.setObjectName("cartao_resultado")
        self.setStyleSheet("#cartao_resultado { background: #1E1E1E; border: 1px solid #3A3A3A;"
                           " border-radius: 8px; }")
        cod_itaipu = resultado.get("codigo_itaipu", "N/A")
        coluna = resultado.get("coluna_match", "N/A")
        amostra = resultado.get("amostra", "")
        caminho_arq = resultado.get("caminho_arquivo", "")
        caminho_pasta = resultado.get("caminho_pasta", "")

        # Espaços do `pack` de lá (o pady de dois vizinhos SOMA no Tk). A borda
        # de 1 px já desloca o conteúdo: as margens são o padx/pady menos 1.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)           # f_top: padx=10, pady=(10, …); botões (…, 10)
        layout.setSpacing(0)

        linha_topo = QHBoxLayout()
        linha_topo.setSpacing(0)
        # O PMIB num campo "invisível" (dá para copiar), 450 px para não cortar.
        self.campo_pmib = QLineEdit(f"PMIB: {cod_itaipu}")
        self.campo_pmib.setReadOnly(True)
        self.campo_pmib.setFixedSize(450, 28)
        self.campo_pmib.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #FFFFFF; padding: 0 0 0 4px;"
            " min-height: 28px; max-height: 28px; font-size: 14px; font-weight: bold; }")
        linha_topo.addWidget(self.campo_pmib)
        linha_topo.addSpacing(5)                        # rótulo: padx=5
        self.rotulo_coluna = QLabel(f"| Match na coluna: {coluna}")
        self.rotulo_coluna.setFixedHeight(28)
        self.rotulo_coluna.setStyleSheet(
            f"font-size: 12px; background: transparent; color: {estilo.cinza_tk('gray')};")
        linha_topo.addWidget(self.rotulo_coluna)
        linha_topo.addStretch()
        layout.addLayout(linha_topo)

        layout.addSpacing(7)                            # f_top (…, 5) + caminho (2, …)
        self.texto_caminho = _caixa_de_texto(estilo.mono("📂 Caminho:") + f"\n{caminho_arq}",
                                             fonte=("Consolas", 11), cor="#A0A0A0")
        layout.addWidget(self.texto_caminho)

        self.texto_amostra = None
        if amostra:
            layout.addSpacing(4)                        # caminho (…, 2) + amostra (2, …)
            self.texto_amostra = _caixa_de_texto(estilo.mono("🔎 Amostra: ") + amostra,
                                                 fonte=("Roboto", 12), cor="#E0E0E0")
            layout.addWidget(self.texto_amostra)
            layout.addSpacing(5)                        # amostra (…, 5) + botões (0, …)
        else:
            layout.addSpacing(2)                        # caminho (…, 2) + botões (0, …)

        linha_botoes = QHBoxLayout()
        linha_botoes.setContentsMargins(5, 0, 0, 0)     # botões: padx=15 (10 já vêm do cartão)
        linha_botoes.setSpacing(10)                     # "Abrir Arquivo": padx=(0, 10)
        self.botao_arquivo = _botao_cinza(estilo.mono("📄 Abrir Arquivo"), 120)
        self.botao_arquivo.clicked.connect(lambda: abrir_arquivo(caminho_arq))
        self.botao_pasta = _botao_cinza(estilo.mono("📁 Abrir Pasta"), 120)
        self.botao_pasta.clicked.connect(lambda: abrir_pasta(caminho_pasta))
        linha_botoes.addWidget(self.botao_arquivo)
        linha_botoes.addWidget(self.botao_pasta)
        linha_botoes.addStretch()
        layout.addLayout(linha_botoes)


class JanelaResultados(QWidget):
    """O CTkToplevel de 900x650 com um cartão por achado.

    Janela de verdade (com minimizar e maximizar, como lá, que tirou o
    `transient` por isso) e modal para o app inteiro (o `grab_set`).
    """

    def __init__(self, tela, resultados: list[dict]) -> None:
        super().__init__(tela, Qt.WindowType.Window)
        self.tela = tela
        self.setObjectName("janela_resultados")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        # CTkToplevel do tema dark-blue: fundo gray10.
        self.setStyleSheet(f"#janela_resultados {{ background: {estilo.cinza_tk('gray10')}; }}")
        self.setWindowTitle(f"Resultados da Busca: {len(resultados)} encontrados")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(900, 650)

        layout = QVBoxLayout(self)
        # título pady=(15, 5); quadro padx=20, pady=(0, 15); "Fechar" pady=(0, 20).
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(0)
        self.rotulo_titulo = blocos.rotulo("Resultados Encontrados", tamanho=18, negrito=True,
                                           cor=theme.COLORS.get("accent", "#00C975"))
        self.rotulo_titulo.setFixedHeight(blocos.ALTURA_MINIMA_ROTULO)
        layout.addWidget(self.rotulo_titulo)
        layout.addSpacing(5)
        self.area, lista = blocos.area_rolavel(cor=theme.COR_CARTAO)
        # O conteúdo do CTkScrollableFrame vai até a barra de rolagem, sem os
        # 6 px do canto à direita (medido: cartão de 817 = 860 - 6 - 16 - 1 - 20).
        lista.setContentsMargins(6, 6, 1, 6)
        layout.addWidget(self.area, 1)
        layout.addSpacing(15)

        self.cartoes: list[CartaoResultado] = []
        for i, r in enumerate(resultados):
            # Cartões com pady=8: 8 nas pontas, 16 entre dois.
            lista.addSpacing(8 if i == 0 else 16)
            cartao = CartaoResultado(r, abrir_arquivo=self.abrir_arquivo, abrir_pasta=self.abrir_pasta)
            # padx=10 (o recuo de 6 do quadro já está nas margens da lista).
            linha = QHBoxLayout()
            linha.setContentsMargins(10, 0, 10, 0)
            linha.addWidget(cartao)
            lista.addLayout(linha)
            self.cartoes.append(cartao)
        lista.addSpacing(8)

        self.botao_fechar = _botao_cinza("Fechar", 150)
        self.botao_fechar.clicked.connect(self.close)
        layout.addWidget(self.botao_fechar, 0, Qt.AlignmentFlag.AlignHCenter)

    # [CP 8.4] `os.startfile` saiu daqui para `core/plataforma.py`: o mesmo
    # comando nos três sistemas, e "não existe" vira aviso.
    def abrir_arquivo(self, caminho: str) -> None:
        if os.path.exists(caminho):
            self.tela.log(f"Abrindo arquivo: {os.path.basename(caminho)}")
            plataforma.abrir_no_sistema(caminho)
        else:
            QMessageBox.critical(self, "Erro", "Arquivo não encontrado.")

    def abrir_pasta(self, pasta: str) -> None:
        if os.path.exists(pasta):
            self.tela.log(f"Abrindo pasta: {pasta}")
            plataforma.abrir_no_sistema(pasta)
        else:
            QMessageBox.critical(self, "Erro", "Pasta não encontrada.")


class ModuloBuscaPMIB(ModuleFrame):
    def __init__(self, parent=None, controller=None) -> None:
        self.janela_resultados = None
        # Console sem altura fixa (lá: row 2 com weight=1, sticky="nsew") e
        # conteúdo só com o necessário (row 1, weight=0).
        super().__init__(parent, controller, titulo="Search PMIB (Buscador de Sobressalentes)",
                         peso_conteudo=0, altura_console=None)
        # A tela antiga não é um ModuleFrame do CTk: tem grid próprio. Header
        # pady=10, conteúdo pady=5, console pady=(15, 20) -- no grid cada linha
        # soma os dois lados: 15 entre header e conteúdo, 20 até o console e 20
        # embaixo (mais os 20 do `show_frame`).
        raiz = self.layout()
        raiz.setSpacing(0)
        raiz.setContentsMargins(MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10,
                                MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 20)
        raiz.insertSpacing(1, 15)                       # header (…, 10) + conteúdo (5, …)
        raiz.insertSpacing(3, 20)                       # conteúdo (…, 5) + console (15, …)

    @property
    def tipo_busca(self) -> str:
        return "generalista" if self.rb_geral.isChecked() else "direcionada"

    def _build_ui(self) -> None:
        self.content_layout.setSpacing(0)
        self.content_layout.addSpacing(5)               # quadro: pady=5
        corpo = blocos.cartao(self.content_layout)
        self.content_layout.addSpacing(5)
        corpo.setSpacing(0)
        corpo.setContentsMargins(15, 10, 15, 15)        # título pady=(10, 5); termo (5, 15); padx=15
        self.rotulo_secao = blocos.rotulo("1. Parâmetros de Busca", tamanho=14, negrito=True,
                                          cor=theme.COLORS["accent"], alinhar="esquerda")
        corpo.addWidget(self.rotulo_secao)
        self.rotulos_linha: list[QLabel] = []

        # 1. Seleção da Pasta Raiz
        corpo.addSpacing(10)                            # título (…, 5) + linha (5, …)
        linha = self._linha(corpo, "Pasta Raiz da Busca:")
        self.entry_pasta = QLineEdit()
        self.entry_pasta.setFixedWidth(400)
        linha.addSpacing(5)                             # campo: padx=5
        linha.addWidget(self.entry_pasta)
        linha.addSpacing(5)
        self.btn_pasta = _botao_cinza("Buscar Pasta", 100)
        self.btn_pasta.clicked.connect(self._selecionar_pasta)
        linha.addWidget(self.btn_pasta)
        linha.addStretch()

        # 2. Modo de Busca e Coluna
        corpo.addSpacing(10)
        linha = self._linha(corpo, "Modo de Busca:")
        self.rb_direc = QRadioButton("Direcionada (Rápida)")
        self.rb_geral = QRadioButton("Generalista (Lenta)")
        self.rb_direc.setChecked(True)
        self._grupo_modo = QButtonGroup(self)
        for rb in (self.rb_direc, self.rb_geral):
            self._grupo_modo.addButton(rb)
            rb.clicked.connect(self._toggle_modo_busca)
        linha.addWidget(self.rb_direc)
        linha.addSpacing(15)                            # padx=(0, 15)
        linha.addWidget(self.rb_geral)
        linha.addSpacing(30)                            # rádio (…, 20) + rótulo (10, …)
        self.rotulo_coluna = _rotulo_da_linha("Coluna Alvo:", largura=None)
        linha.addWidget(self.rotulo_coluna)
        linha.addSpacing(5)
        self.opt_coluna = controles.MenuDeOpcoes(COLUNAS, cor=CINZA, cor_seta=CINZA_SETA)
        self.opt_coluna.setFixedWidth(140)              # `width` padrão do CTkOptionMenu
        linha.addWidget(self.opt_coluna)
        linha.addStretch()

        # 3. Termo de Busca
        corpo.addSpacing(10)
        linha = self._linha(corpo, "Termo Procurado:")
        self.entry_termo = QLineEdit()
        self.entry_termo.setFixedWidth(400)
        self.entry_termo.setPlaceholderText("Digite o que deseja encontrar...")
        linha.addSpacing(5)
        linha.addWidget(self.entry_termo)
        linha.addSpacing(15)                            # campo (…, 5) + botão (10, …)
        self.btn_search = blocos.botao(estilo.mono("🔍 PESQUISAR"), variante="primario", largura=150,
                                       altura=28, negrito=True)
        self.btn_search.clicked.connect(self.iniciar_busca)
        linha.addWidget(self.btn_search)
        linha.addStretch()

    def _linha(self, corpo, texto: str) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(0)
        rotulo = _rotulo_da_linha(texto)
        self.rotulos_linha.append(rotulo)
        linha.addWidget(rotulo)
        corpo.addLayout(linha)
        return linha

    def _toggle_modo_busca(self) -> None:
        """Ativa ou desativa a seleção de coluna conforme o modo de busca."""
        self.opt_coluna.setEnabled(self.tipo_busca != "generalista")

    def _selecionar_pasta(self) -> None:
        p = file_dialogs.ask_directory("search.pasta_raiz", "pasta", titulo="Selecione a Pasta Raiz de Busca")
        if p:
            self.entry_pasta.setText(p)

    def iniciar_busca(self) -> None:
        pasta = self.entry_pasta.text()
        termo = self.entry_termo.text().strip()
        modo = self.tipo_busca
        coluna = self.opt_coluna.currentText()

        if not pasta:
            QMessageBox.warning(self, "Atenção", "Selecione a pasta raiz antes de pesquisar.")
            return
        if not termo:
            QMessageBox.warning(self, "Atenção", "Digite o termo que deseja pesquisar.")
            return
        modulo = self.backend("search_pmib_backend")
        if modulo is None:
            return
        self.console.clear()
        self.iniciar_tarefa(self._worker_busca, modulo, pasta, modo, termo, coluna, botao=self.btn_search)

    def _worker_busca(self, modulo, pasta, modo, termo, coluna) -> None:
        try:
            searcher = modulo.PMIBSearcher()
            resultados = searcher.executar_busca(
                pasta_raiz=pasta,
                tipo_busca=modo,
                termo_busca=termo,
                coluna_especifica=coluna,
                callback_log=self.log,
            )
            # A janela é widget: nasce na thread da interface.
            interface.na_interface(self._mostrar_janela_resultados, resultados)
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Crítico: {e}")

    def _mostrar_janela_resultados(self, resultados) -> None:
        """Abre a janela com um cartão por resultado (ou avisa que não há nenhum)."""
        if not resultados:
            QMessageBox.information(self, "Resultados", "Nenhum material encontrado com esses parâmetros.")
            return
        self.janela_resultados = JanelaResultados(self, resultados)
        # WA_DeleteOnClose: fechada, a janela some; a referência não pode sobrar.
        self.janela_resultados.destroyed.connect(self._janela_fechada)
        self.janela_resultados.show()

    def _janela_fechada(self, *_args) -> None:
        self.janela_resultados = None

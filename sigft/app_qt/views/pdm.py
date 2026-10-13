"""Tela "Gerenciador de PDMs" (PDM) na interface Qt.

Mesma tela de `sigft/app/views/pdm.py`: fatia o arquivo geral de PDMs vindo de
Itaipu, formata e traduz os PDMs Modificados, regenera as pastas a partir da
planilha, cria as fichas PMIB a partir do template e limpa duplicatas de pasta.

O que muda é só COMO os workers falam com a tela: lá eram `self.after(0, ...)`
e threads `daemon` sem dono; aqui o log vai pelo console (seguro de qualquer
thread), as mensagens do fim por `avisar` e cada tarefa por `iniciar_tarefa`
(o botão fica desligado enquanto ela roda). Tudo o que o worker lê dos campos
é lido NO CLIQUE, na thread da interface.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLineEdit, QRadioButton, QSizePolicy, QVBoxLayout,
)

from sigft.app import theme
from sigft.app_qt import estilo, file_dialogs
from sigft.app_qt.widgets import blocos, controles, dialogos_selecao
from sigft.app_qt.widgets.abas import Abas
from sigft.app_qt.widgets.module_frame import MARGEM_DA_TELA, ModuleFrame
from sigft.core import pdm_catalogo, prefs
from sigft.core.callbacks import from_legacy

TEXTO_NENHUM_ARQUIVO = "Nenhum arquivo selecionado"
EXCEL = [("Excel", "*.xlsx *.xls")]
# Fundo dos quadros de dentro das abas e o cinza escuro dos botões de arquivo
# (fg/hover escritos à mão na tela antiga).
FUNDO_QUADRO = "#333333"
HOVER_CINZA = "#454545"
COR_TEXTO = controles.COR_TEXTO_CTK          # CTkLabel sem text_color: gray84
COR_APOIO = estilo.cinza_tk(theme.COR_TEXTO_APOIO)
LARGURA_RADIO_CTK = 100


# --- peças -------------------------------------------------------------------
def _rotulo(texto: str, *, largura: int | None = None, tamanho: int = 13, negrito: bool = False,
            cor: str = COR_TEXTO):
    """CTkLabel de uma linha, `anchor="w"` (sem quebra: lá o texto não quebra)."""
    r = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, cor=cor, alinhar="esquerda")
    r.setWordWrap(False)
    if largura:
        r.setFixedWidth(largura)
    return r


def _botao(texto: str, *, largura: int = estilo.LARGURA_BOTAO_CTK, variante: str | None = None,
           altura: int = 28, tamanho_fonte: int | None = None):
    """CTkButton: `largura` é o `width` (mínima); o texto que não cabe alarga o
    botão com 7 px de folga de cada lado (`blocos.botao(largura_minima=)`)."""
    return blocos.botao(texto, variante=variante, altura=altura, tamanho_fonte=tamanho_fonte,
                        largura_minima=largura)


def _quadro(layout_pai, margens):
    """CTkFrame #333333 de cantos 8 (os quadros de dentro das abas)."""
    quadro = QFrame(objectName="quadro_pdm")
    quadro.setStyleSheet(f"#quadro_pdm {{ background: {FUNDO_QUADRO}; border-radius: 8px; }}")
    layout = QVBoxLayout(quadro)
    layout.setContentsMargins(*margens)
    layout.setSpacing(0)
    layout_pai.addWidget(quadro)
    return quadro, layout


def _linha(*itens, margens=(0, 0, 0, 0)) -> QHBoxLayout:
    """`pack(side="left")` em fila: widgets e, entre eles, os padx somados (int)."""
    linha = QHBoxLayout()
    linha.setContentsMargins(*margens)
    linha.setSpacing(0)
    for item in itens:
        if isinstance(item, int):
            linha.addSpacing(item)
        else:
            linha.addWidget(item)
    linha.addStretch()
    return linha


class _Opcoes(QButtonGroup):
    """Os CTkRadioButton de uma mesma `StringVar`: `get()`/`set()` como lá."""

    def __init__(self, padrao: str, parent) -> None:
        super().__init__(parent)
        self.setExclusive(True)
        self._padrao = padrao
        self.botoes: dict[str, QRadioButton] = {}

    def adicionar(self, texto: str, valor: str) -> QRadioButton:
        rb = QRadioButton(texto)
        # O `width` padrão do CTkRadioButton (100) é largura MÍNIMA: "Português"
        # e "English" ocupam 100 e empurram o vizinho para o mesmo x de lá.
        rb.setMinimumWidth(LARGURA_RADIO_CTK)
        self.addButton(rb)
        self.botoes[valor] = rb
        if valor == self._padrao:
            rb.setChecked(True)
        return rb

    def get(self) -> str:
        return next((v for v, rb in self.botoes.items() if rb.isChecked()), "")

    def set(self, valor: str) -> None:
        self.botoes[valor].setChecked(True)


class _SelecaoDeCodigos(dialogos_selecao.SelecaoMultiplaDialog):
    """A seleção dos códigos PMIB, sem Esc: a lista pode ter dezenas de
    códigos marcados um a um, e o Tk não tinha tecla nenhuma -- uma tecla
    escapada não pode jogar a escolha fora. "X" continua cancelando."""

    def keyPressEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if evento.key() == Qt.Key.Key_Escape:
            evento.accept()
            return
        super().keyPressEvent(evento)


# =============================================================================
class ModuloPDM(ModuleFrame):
    def __init__(self, parent=None, controller=None) -> None:
        # Os caminhos de ARQUIVO (os StringVar sem campo visível de lá).
        self.path_sam_gm = self.path_status_pmib = self.path_template = ""
        super().__init__(parent, controller, titulo="Gerenciador de PDMs")
        # Lá a tela não é o ModuleFrame: header, conteúdo e console com
        # padx=20/pady=10 cada, dentro do padx/pady=20 do `show_frame`. Os pady
        # vizinhos SOMAM: 20 entre eles. O conteúdo fica com a sobra e rola; o
        # console tem a altura padrão (tests/test_pdm_tela_layout.py).
        raiz = self.layout()
        raiz.setContentsMargins(MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10,
                                MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10)
        raiz.setSpacing(20)

        # Pré-preenchimento com a pasta padrão dos "PDMs modificados" (decisão
        # de produto nº 7 / CP 1.5), quando ela existe no disco desta máquina.
        # Os campos de ARQUIVO não: os diálogos deles já abrem na pasta padrão
        # (ver o comentário da tela antiga e docs/refatoracao/PENDENCIAS.md).
        pasta_padrao_destino = prefs.get_default_dir("pdms_modificados")
        if pasta_padrao_destino is not None:
            self.entry_dest.setText(pasta_padrao_destino)

    # --- montagem -------------------------------------------------------------
    def _build_ui(self) -> None:
        self._rotulos = {}
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        # CTkScrollableFrame transparente. A barra fica sempre à vista, como lá
        # (alça cheia quando não há o que rolar): com ela só às vezes, a largura
        # do formulário mudaria de uma aba para outra.
        self.area, corpo = blocos.area_rolavel(self.content_layout)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        # Lá o formulário (900) encosta na barra: sem a margem de 6 à direita.
        corpo.setContentsMargins(6, 6, 1, 6)
        corpo.addSpacing(10)                            # frm_config: pady=10
        self._painel_global(corpo)
        corpo.addSpacing(20)                            # frm_config (…, 10) + abas (10, …)

        # --- ABAS DE OPERAÇÃO ---
        self.tabview = Abas(cor_fundo=theme.COR_CARTAO, cor_barra="#161616",
                            cor_selecionada=theme.COLORS["primary"],
                            cor_selecionada_hover=theme.COLORS["primary_hover"])
        self._build_tab1(self.tabview.add("Processar PDMs"))
        self._build_tab2(self.tabview.add("Criar planilhas PMIB"))
        self._build_tab3(self.tabview.add("Excluir Duplicados"))
        # O CTkTabview (dentro do formulário que rola) tem a altura da aba
        # ESCOLHIDA; o QStackedWidget teria a da maior.
        self.tabview.pilha.currentChanged.connect(self._altura_da_aba_escolhida)
        self._altura_da_aba_escolhida()
        corpo.addWidget(self.tabview)
        corpo.addSpacing(10)                            # abas: pady=10
        # A sobra (aba curta) fica embaixo; sem isto as abas esticariam.
        corpo.addStretch(1)

    def _altura_da_aba_escolhida(self, *_):
        atual = self.tabview.pilha.currentWidget()
        for aba in self.tabview.abas.values():
            vertical = QSizePolicy.Policy.Preferred if aba is atual else QSizePolicy.Policy.Ignored
            aba.setSizePolicy(QSizePolicy.Policy.Preferred, vertical)

    def _painel_global(self, corpo) -> None:
        r = self._rotulos
        layout = blocos.cartao(corpo)
        self.cartao_config = layout.parentWidget()
        layout.setContentsMargins(15, 10, 15, 15)       # padx=15; título pady=(10, …); f_plan (…, 15)
        layout.setSpacing(0)
        r["config"] = _rotulo("Configuração Global", tamanho=14, negrito=True, cor=theme.COLORS["accent"])
        layout.addWidget(r["config"])
        layout.addSpacing(5)                            # título (…, 5)

        r["destino"] = _rotulo("Pasta dos PDMs Modificados:", largura=190)
        self.entry_dest = QLineEdit()
        self.entry_dest.setFixedWidth(350)
        self.btn_sel_destino = _botao("Selecionar", largura=100, variante="cinza")
        self.btn_sel_destino.clicked.connect(self._sel_destino)
        layout.addLayout(_linha(r["destino"], 5, self.entry_dest, 5, self.btn_sel_destino))
        layout.addSpacing(5)                            # f_path (…, 5) + f_plan (0, …)

        # A planilha de PDMs subiu da aba 1 para cá em 2026-09-24: as duas
        # abas passaram a usá-la (regenerar/fatiar e criar as fichas).
        r["sam_gm"] = _rotulo("Planilha de PDMs (SAM-GM):", largura=190)
        self.btn_sam_gm = _botao("Selecionar", largura=100, variante="cinza")
        self.btn_sam_gm.clicked.connect(self._sel_sam_gm)
        self.lbl_sam_gm_status = _rotulo(TEXTO_NENHUM_ARQUIVO, cor=COR_APOIO)
        layout.addLayout(_linha(r["sam_gm"], 5, self.btn_sam_gm, 20, self.lbl_sam_gm_status))

    def _campo_de_pasta(self, layout, chave_rotulo, texto, *, largura_rotulo=240):
        """Rótulo + campo (280, padx=5) + "Buscar" (80): a linha de pasta das abas."""
        self._rotulos[chave_rotulo] = _rotulo(texto, largura=largura_rotulo)
        campo = QLineEdit()
        campo.setFixedWidth(280)
        botao = _botao("Buscar", largura=80)
        layout.addLayout(_linha(self._rotulos[chave_rotulo], 5, campo, 5, botao))
        return campo, botao

    def _cabecalho_com_botao(self, layout, chave, titulo, botao) -> None:
        """Título à esquerda e o botão à direita, na mesma linha."""
        self._rotulos[chave] = _rotulo(titulo, tamanho=14, negrito=True)
        linha = QHBoxLayout()
        linha.setSpacing(0)
        linha.addWidget(self._rotulos[chave])
        linha.addStretch()
        linha.addWidget(botao)
        layout.addLayout(linha)

    def _build_tab1(self, aba) -> None:
        r = self._rotulos
        lay = aba.layout()
        lay.setContentsMargins(20, 0, 20, 0)            # tudo com padx=20
        # A pasta From Itaipu fica no topo da aba: a regeneração e o passo 1
        # antigo usam a mesma.
        lay.addSpacing(10)                              # f_dir: pady=(10, 0)
        self.entry_pdms_itaipu, self.btn_buscar_itaipu = self._campo_de_pasta(
            lay, "itaipu", "Pasta (PDMs From Itaipu):")
        self.btn_buscar_itaipu.clicked.connect(self._buscar_itaipu)
        lay.addSpacing(6)                               # quadro: pady=6

        # --- Regenerar as pastas a partir da planilha (2026-09-24) ---
        # Título e botão na MESMA linha, aqui e no passo 1 (o console sumia
        # numa janela de 960 px de altura).
        self.quadro_regen, q = _quadro(lay, (10, 6, 10, 8))
        self.btn_regenerar = _botao("Executar: Regenerar as pastas", variante="primario")
        self.btn_regenerar.clicked.connect(self._op1_regenerar)
        self._cabecalho_com_botao(q, "regen", "Regenerar as pastas a partir da planilha", self.btn_regenerar)
        r["regen_desc"] = _rotulo(
            "Com a revisão no nome (PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx); "
            "a versão antiga vai para _versoes_antigas, nada é apagado.", tamanho=11, cor=COR_APOIO)
        q.addWidget(r["regen_desc"])
        lay.addSpacing(12)                              # pady=6 de cada quadro

        # --- SEÇÃO 1: Fatiar lista geral (From Itaipu), método antigo ---
        self.quadro_from, q = _quadro(lay, (10, 6, 10, 8))
        self.btn_from_itaipu = _botao("Executar: Criar PDMs From Itaipu", variante="primario")
        self.btn_from_itaipu.clicked.connect(self._op1_from_itaipu)
        self._cabecalho_com_botao(q, "from", "1. Fatiar Arquivo Geral (From Itaipu)", self.btn_from_itaipu)
        r["from_desc"] = _rotulo("Usa a planilha do painel de cima; só cria os PDMs que faltam na pasta.",
                                 tamanho=11, cor=COR_APOIO)
        q.addWidget(r["from_desc"])
        lay.addSpacing(12)

        # --- SEÇÃO 2: Formatar PDMs (Modificados) ---
        self.quadro_mod, q = _quadro(lay, (10, 5, 10, 10))
        r["mod"] = _rotulo("2. Formatar PDMs (Modificados)", tamanho=14, negrito=True)
        q.addWidget(r["mod"])
        q.addSpacing(5)                                 # título: pady=5
        r["mod_desc"] = _rotulo("Utiliza a 'Pasta (PDMs From Itaipu)' como base para leitura.",
                                tamanho=11, cor=COR_APOIO)
        q.addWidget(r["mod_desc"])
        q.addSpacing(5)                                 # rádios: pady=5
        self.modo_proc = _Opcoes("todos", self)
        self.rb_lote = self.modo_proc.adicionar("Lote (Todos os Novos)", "todos")
        self.rb_especifico = self.modo_proc.adicionar("Específico (Escolher 1 arquivo)", "especifico")
        q.addLayout(_linha(10, self.rb_lote, 20, self.rb_especifico))
        q.addSpacing(15)                                # rádios (…, 5) + botão (10, …)
        self.btn_modificados = _botao("Executar: Criar PDMs Modificados", variante="primario")
        self.btn_modificados.clicked.connect(self._op1_modificados)
        q.addWidget(self.btn_modificados, alignment=Qt.AlignmentFlag.AlignHCenter)

        # --- Tradução para inglês (2026-08-28) ---
        # Fica nesta aba porque produz uma pasta de PDMs, como os dois botões
        # acima -- e não na aba 2, que só CONSOME o que existe.
        q.addSpacing(25)                                # botão (…, 10) + título (15, …)
        r["traduzir"] = _rotulo("3. Traduzir para inglês (ficha em inglês)", tamanho=14, negrito=True)
        q.addWidget(r["traduzir"])
        q.addSpacing(5)
        r["traduzir_desc"] = _rotulo(
            "Lê a 'Pasta dos PDMs Modificados' e grava a versão em inglês noutra pasta.\n"
            "Rode uma vez; o resultado fica em cache e o glossário editável "
            "(_GLOSSARIO_PT_EN.txt) corrige termo técnico de vez.", tamanho=11, cor=COR_APOIO)
        q.addWidget(r["traduzir_desc"])
        q.addSpacing(5)                                 # f_en: pady=5
        self.entry_destino_en, self.btn_buscar_en = self._campo_de_pasta(
            q, "en", "Pasta dos PDMs Modificados (EN):")
        self.btn_buscar_en.clicked.connect(self._buscar_en)
        q.addSpacing(15)                                # f_en (…, 5) + botão (10, …)
        self.btn_traduzir = _botao("Executar: Traduzir PDMs Modificados para inglês", variante="primario")
        self.btn_traduzir.clicked.connect(self._op1_traduzir)
        q.addWidget(self.btn_traduzir, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(6)                               # quadro: pady=6

    def _build_tab2(self, aba) -> None:
        r = self._rotulos
        lay = aba.layout()
        lay.setContentsMargins(20, 0, 20, 0)
        lay.addSpacing(10)                              # frm_files: pady=10

        # --- SEÇÃO 1: Configuração de Arquivos e Pastas ---
        self.quadro_fichas, q = _quadro(lay, (10, 5, 10, 8))
        r["fichas"] = _rotulo("Configuração das Fichas PMIB", tamanho=14, negrito=True)
        q.addWidget(r["fichas"])
        q.addSpacing(13)                                # título (…, 5) + linha (8, …)

        # FONTE DAS PERGUNTAS (2026-09-24). A planilha de PDMs é a padrão; a
        # pasta continua como método antigo, e é por ela que sai a ficha em
        # inglês, que usa os PDMs traduzidos.
        r["fonte"] = _rotulo("Fonte das características:", largura=240)
        self.fonte_perguntas = _Opcoes("planilha", self)
        self.rb_fonte_planilha = self.fonte_perguntas.adicionar("Planilha de PDMs", "planilha")
        self.rb_fonte_pasta = self.fonte_perguntas.adicionar("Pasta de PDMs Modificados (método antigo)", "pasta")
        q.addLayout(_linha(r["fonte"], 10, self.rb_fonte_planilha, 20, self.rb_fonte_pasta))
        q.addSpacing(16)                                # pady=8 de cada linha

        # STATUS_PMIB (botão + rótulo)
        self.btn_pmib = _botao("Selecionar STATUS_PMIB (.xlsx)", largura=240, variante="cinza", tamanho_fonte=12)
        self.btn_pmib.clicked.connect(self._sel_status_pmib)
        self.lbl_pmib_status = _rotulo(TEXTO_NENHUM_ARQUIVO, cor=COR_APOIO)
        q.addLayout(_linha(self.btn_pmib, 15, self.lbl_pmib_status))
        q.addSpacing(16)

        # Destino das fichas (campo + Buscar)
        self.entry_destino_fichas, self.btn_buscar_fichas = self._campo_de_pasta(
            q, "destino_fichas", "Pasta Destino das Fichas:")
        self.btn_buscar_fichas.clicked.connect(self._buscar_destino_fichas)
        q.addSpacing(16)

        # Template (botão + rótulo)
        self.btn_template = _botao("Selecionar Template (.xlsx)", largura=240, variante="cinza", tamanho_fonte=12)
        self.btn_template.clicked.connect(self._sel_template)
        self.lbl_template_status = _rotulo(TEXTO_NENHUM_ARQUIVO, cor=COR_APOIO)
        q.addLayout(_linha(self.btn_template, 15, self.lbl_template_status))
        q.addSpacing(16)

        # IDIOMA DA FICHA (2026-08-28). Explícito, e não deduzido do nome do
        # template: deduzir quebraria em silêncio no dia em que alguém
        # renomeasse o arquivo.
        r["idioma"] = _rotulo("Idioma da ficha:", largura=240)
        self.idioma_ficha = _Opcoes("pt", self)
        self.rb_pt = self.idioma_ficha.adicionar("Português", "pt")
        self.rb_en = self.idioma_ficha.adicionar("English", "en")
        r["idioma_dica"] = _rotulo("(English usa a pasta de PDMs traduzidos)", tamanho=11, cor=COR_APOIO)
        q.addLayout(_linha(r["idioma"], 10, self.rb_pt, 20, self.rb_en, 20, r["idioma_dica"]))
        lay.addSpacing(20)                              # frm_files (…, 10) + frm_exec (10, …)

        # --- SEÇÃO 2: Modo de Execução ---
        self.quadro_exec, q = _quadro(lay, (10, 10, 10, 10))
        r["selecao"] = _rotulo("Seleção de Itens:", largura=120, tamanho=12, negrito=True)
        self.modo_pmib = _Opcoes("todos", self)
        self.rb_todos = self.modo_pmib.adicionar("Todos da Lista", "todos")
        self.rb_selecionar = self.modo_pmib.adicionar("Selecionar Manualmente", "selecionar")
        q.addLayout(_linha(r["selecao"], 10, self.rb_todos, 20, self.rb_selecionar))
        q.addSpacing(10)                                # f_rad (…, 5) + f_out (5, …)
        r["saida"] = _rotulo("Formato de Saída:", largura=120, tamanho=12, negrito=True)
        self.modo_saida_fichas = _Opcoes("apenas_planilhas", self)
        self.rb_apenas = self.modo_saida_fichas.adicionar("Apenas Planilhas (Padrão)", "apenas_planilhas")
        self.rb_com_pastas = self.modo_saida_fichas.adicionar("Criar Subpastas + Planilhas", "com_pastas")
        q.addLayout(_linha(r["saida"], 10, self.rb_apenas, 20, self.rb_com_pastas))
        q.addSpacing(20)                                # f_out (…, 10) + botão (10, …)
        self.btn_criar_fichas = _botao("Executar: Criar Fichas PMIB", variante="primario")
        self.btn_criar_fichas.clicked.connect(self._op2_executar)
        q.addWidget(self.btn_criar_fichas, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(10)                              # frm_exec: pady=10

    def _build_tab3(self, aba) -> None:
        r = self._rotulos
        lay = aba.layout()
        lay.addSpacing(20)                              # rótulo: pady=20
        r["limpeza"] = _rotulo("Remove versões antigas de arquivos na pasta (limpeza de versões).", tamanho=14)
        lay.addWidget(r["limpeza"], alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(28)                              # rótulo (…, 20) + linha (8, …)
        linha = QVBoxLayout()
        linha.setContentsMargins(10, 0, 10, 0)          # f_clean: padx=10
        self.entry_clean, self.btn_buscar_clean = self._campo_de_pasta(linha, "clean", "Pasta para Limpeza:")
        self.btn_buscar_clean.clicked.connect(self._buscar_clean)
        lay.addLayout(linha)
        lay.addSpacing(38)                              # linha (…, 8) + botão (30, …)
        self.btn_exec_clean = _botao("Executar Limpeza", largura=300, altura=40, variante="perigo")
        self.btn_exec_clean.clicked.connect(self._op3_executar)
        lay.addWidget(self.btn_exec_clean, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(30)

    # --- seletores ------------------------------------------------------------
    @staticmethod
    def _marcar_escolhido(botao, rotulo, caminho) -> None:
        """Arquivo escolhido: o nome em verde e o botão na cor primária (o
        hover continua o cinza, como o `configure(fg_color=...)` de lá)."""
        rotulo.setText(os.path.basename(caminho))
        rotulo.setStyleSheet(rotulo.styleSheet() + f" color: {theme.COLORS['accent']};")
        botao.setStyleSheet(botao.styleSheet() + f" QPushButton {{ background: {theme.COLORS['primary']}; }}"
                            f" QPushButton:hover {{ background: {HOVER_CINZA}; }}")

    @staticmethod
    def _escolher_pasta(campo, chave, titulo=None) -> None:
        """Lá o campo recebia o "" do cancelar e apagava o caminho já escolhido."""
        pasta = file_dialogs.ask_directory(chave, "pasta", **({"titulo": titulo} if titulo else {}))
        if pasta:
            campo.setText(pasta)

    def _sel_destino(self) -> None:
        self._escolher_pasta(self.entry_dest, "pdm.caminho_destino")

    def _buscar_itaipu(self) -> None:
        self._escolher_pasta(self.entry_pdms_itaipu, "pdm.pdms_itaipu", "Pasta de Origem dos PDMs")

    def _buscar_en(self) -> None:
        self._escolher_pasta(self.entry_destino_en, "pdm.pdms_modificados_en",
                             "Pasta dos PDMs Modificados em INGLÊS")

    def _buscar_destino_fichas(self) -> None:
        self._escolher_pasta(self.entry_destino_fichas, "pdm.destino_fichas", "Pasta onde as fichas serão criadas")

    def _buscar_clean(self) -> None:
        self._escolher_pasta(self.entry_clean, "pdm.clean_dir", "Selecione a pasta para limpar duplicatas")

    def _sel_sam_gm(self) -> None:
        f = file_dialogs.ask_open_file("pdm.sam_gm", "excel", titulo="Selecione o PDM's SAM-GM", filetypes=EXCEL)
        if f:
            self.path_sam_gm = f
            self._marcar_escolhido(self.btn_sam_gm, self.lbl_sam_gm_status, f)

    def _sel_status_pmib(self) -> None:
        f = file_dialogs.ask_open_file("pdm.status_pmib", "excel", titulo="Selecione o STATUS_PMIB", filetypes=EXCEL)
        if f:
            self.path_status_pmib = f
            self._marcar_escolhido(self.btn_pmib, self.lbl_pmib_status, f)

    def _sel_template(self) -> None:
        f = file_dialogs.ask_open_file("pdm.template", "excel", titulo="Selecione o Template", filetypes=EXCEL)
        if f:
            self.path_template = f
            self._marcar_escolhido(self.btn_template, self.lbl_template_status, f)

    # --- Aba 1 ------------------------------------------------------------------
    def _op1_from_itaipu(self) -> None:
        lista = self.path_sam_gm
        pasta_alvo = self.entry_pdms_itaipu.text()
        if not lista:
            return self.avisar("Aviso", "Por favor, selecione a Planilha de PDMs no painel de cima.", tipo="aviso")
        if not pasta_alvo:
            return self.avisar("Aviso", "Por favor, selecione a Pasta (PDMs From Itaipu) na tela.", tipo="aviso")
        modulo = self.backend("pdm_backend")
        if modulo is None:
            return None
        self.iniciar_tarefa(self._tarefa_from_itaipu, modulo, lista, pasta_alvo, botao=self.btn_from_itaipu)
        return None

    def _tarefa_from_itaipu(self, modulo, lista, pasta_alvo) -> None:
        self.log(f"Fatiando a lista geral: {os.path.basename(lista)}...")
        res = modulo.pdms_fromItaipu_lista_geral(lista, pasta_alvo, log_callback=self.log,
                                                 retry_lock=self.perguntar_retry_excel)
        self.log(res)
        self.avisar("Relatório", res)

    def _op1_modificados(self) -> None:
        destino = self.entry_dest.text()
        if not destino:
            return self.avisar("Aviso", "Selecione a Pasta dos PDMs Modificados primeiro.", tipo="aviso")
        origem = self.entry_pdms_itaipu.text()
        if not origem:
            return self.avisar("Aviso", "Por favor, selecione a 'Pasta (PDMs From Itaipu)' na tela.", tipo="aviso")
        modulo = self.backend("pdm_backend")
        if modulo is None:
            return None

        if self.modo_proc.get() == "todos":
            self.iniciar_tarefa(self._tarefa_modificados, modulo, origem, destino, botao=self.btn_modificados)
            return None
        # `initialdir=origem`: override CONTEXTUAL -- a pasta que a pessoa ACABOU
        # de escolher em "Pasta (PDMs From Itaipu)" nesta mesma tela (não é
        # memória entre sessões; ver `sigft.app.file_dialogs._resolver_initialdir`).
        arq = file_dialogs.ask_open_file("pdm.arquivo_especifico", "excel",
                                         titulo="Selecione o arquivo PDM específico", filetypes=EXCEL,
                                         initialdir=origem)
        if not arq:
            self.log("Seleção de arquivo específico cancelada.")
            return None
        self.iniciar_tarefa(self._tarefa_especifico, modulo, arq, destino, botao=self.btn_modificados)
        return None

    def _tarefa_modificados(self, modulo, origem, destino) -> None:
        self.log(f"Processando todos em: {origem}")
        count = 0
        for arq in modulo.listar_arquivos_excel(origem):
            tbl = modulo.processar_arquivo_pdm(arq)
            if tbl is not None:
                ok, msg = modulo.salvar_tabela_formatada(tbl, arq, destino, retry_lock=self.perguntar_retry_excel)
                self.log(msg)
                if ok:
                    count += 1
        self.log(f"Fim: {count} arquivos processados com sucesso.")
        self.avisar("Fim", f"{count} arquivos processados com sucesso.")

    def _tarefa_especifico(self, modulo, arq, destino) -> None:
        tbl = modulo.processar_arquivo_pdm(arq)
        if tbl is not None:
            ok, msg = modulo.salvar_tabela_formatada(tbl, arq, destino, force=True,
                                                     retry_lock=self.perguntar_retry_excel)
            self.log(msg)
            self.avisar("Status", msg)

    def _op1_traduzir(self) -> None:
        """Traduz a pasta de PDMs Modificados para inglês (generator de linhas
        de log, o contrato do resto do projeto)."""
        origem = self.entry_dest.text()
        destino = self.entry_destino_en.text()
        if not origem:
            return self.avisar("Aviso", "Selecione a 'Pasta dos PDMs Modificados' primeiro.", tipo="aviso")
        if not destino:
            return self.avisar("Aviso", "Selecione a pasta de destino dos PDMs Modificados em INGLÊS.", tipo="aviso")
        if os.path.abspath(origem) == os.path.abspath(destino):
            return self.avisar("Erro", "A pasta de destino não pode ser a mesma da origem.\n"
                                       "Os arquivos em português seriam sobrescritos.", tipo="erro")
        self.iniciar_tarefa(self._tarefa_traduzir, origem, destino, botao=self.btn_traduzir)
        return None

    def _tarefa_traduzir(self, origem, destino) -> None:
        try:
            from sigft.services import traducao_pdm
            self.log("Traduzindo PDMs Modificados para inglês...")
            # SEM `api_key=`: `get_llm` resolve a chave do provedor escolhido
            # para `traduzir_pdm` em "Modelos de IA" (ver a tela antiga).
            for linha in traducao_pdm.traduzir_pasta(
                    origem, destino,
                    traduzir=traducao_pdm.motor_padrao(callbacks=from_legacy(callback_log=self.log)),
                    retry_lock=self.perguntar_retry_excel):
                self.log(linha)
            self.avisar("Tradução", f"Tradução concluída.\n\nPasta: {destino}")
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"ERRO na tradução: {e}")
            self.avisar("Erro", f"Falha na tradução:\n{e}", tipo="erro")

    def _op1_regenerar(self) -> None:
        """A validação de verdade (as duas pastas iguais, a planilha no formato
        certo) é do serviço: a tela só confere que os campos foram preenchidos."""
        planilha = self.path_sam_gm
        pasta_modificados = self.entry_dest.text()
        pasta_itaipu = self.entry_pdms_itaipu.text()
        if not planilha:
            return self.avisar("Aviso", "Selecione a planilha de PDMs no painel de cima.", tipo="aviso")
        if not pasta_modificados:
            return self.avisar("Aviso", "Selecione a 'Pasta dos PDMs Modificados' no painel de cima.", tipo="aviso")
        self.iniciar_tarefa(self._tarefa_regenerar, planilha, pasta_modificados, pasta_itaipu or None,
                            botao=self.btn_regenerar)
        return None

    def _tarefa_regenerar(self, planilha, pasta_modificados, pasta_itaipu) -> None:
        try:
            from sigft.services import pdm_regeneracao
            self.log("Regenerando as pastas a partir da planilha de PDMs...")
            resumo = pdm_regeneracao.regenerar_pastas(planilha, pasta_modificados, pasta_itaipu,
                                                      log_callback=self.log, retry_lock=self.perguntar_retry_excel)
            self.log(resumo)
            self.avisar("Regeneração", resumo)
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"ERRO na regeneração: {e}")
            self.avisar("Erro", f"A regeneração não foi feita:\n{e}", tipo="erro")

    # --- Aba 2 ------------------------------------------------------------------
    def _op2_executar(self) -> None:
        # A FONTE das perguntas (2026-09-24): a planilha de PDMs, ou a pasta de
        # PDMs Modificados (método antigo). Em inglês, só a pasta: as perguntas
        # coladas têm de ser as traduzidas. Ver `_op1_traduzir`.
        da_planilha = self.fonte_perguntas.get() == "planilha"
        idioma = self.idioma_ficha.get()
        em_ingles = idioma == "en"
        planilha = self.path_sam_gm
        pasta_modificados = None
        if da_planilha:
            if em_ingles:
                return self.avisar("Aviso", "A ficha em inglês usa a pasta traduzida. Escolha a fonte "
                                            "'Pasta de PDMs Modificados' ou o idioma Português.", tipo="aviso")
            if not planilha:
                return self.avisar("Aviso", "Selecione a planilha de PDMs no painel de cima.", tipo="aviso")
        else:
            pasta_modificados = self.entry_destino_en.text() if em_ingles else self.entry_dest.text()
            if not pasta_modificados:
                if em_ingles:
                    return self.avisar(
                        "Aviso", "Idioma da ficha = English, mas a 'Pasta dos PDMs Modificados "
                                 "(EN)' não foi selecionada.\n\nEla fica na aba 1, no passo 3 "
                                 "(Traduzir para inglês).", tipo="aviso")
                return self.avisar("Aviso", "Selecione a 'Pasta dos PDMs Modificados' primeiro.", tipo="aviso")

        status_pmib = self.path_status_pmib
        destino_fichas = self.entry_destino_fichas.text()
        template = self.path_template
        if not status_pmib:
            return self.avisar("Aviso", "Por favor, busque o arquivo STATUS_PMIB na tela.", tipo="aviso")
        if not destino_fichas:
            return self.avisar("Aviso", "Por favor, busque a Pasta Destino das Fichas na tela.", tipo="aviso")
        if not template:
            return self.avisar("Aviso", "Por favor, busque o Template Ficha Técnica na tela.", tipo="aviso")
        modulo = self.backend("pdm_backend")
        if modulo is None:
            return None

        lista_sel = None
        if self.modo_pmib.get() == "selecionar":
            try:
                # [2026-10-05, T0] A leitura (cabeçalho ACHADO, não fixo na
                # linha 4) e a normalização moram no serviço.
                try:
                    codigos = modulo.codigos_pmib_da_lista(status_pmib)
                except ValueError as erro:
                    return self.avisar("Erro", str(erro), tipo="erro")
                # Modal (o `grab_set` de lá): a tela não tem o que fazer sem a
                # resposta; `esperar()` é o `wait_window`.
                lista_sel = self._escolher_codigos(codigos)
                if not lista_sel:
                    self.log("Seleção manual de códigos cancelada.")
                    return None
            except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
                return self.avisar("Erro", f"Ocorreu um erro ao ler o STATUS_PMIB:\n{e}", tipo="erro")

        criar_pastas = self.modo_saida_fichas.get() == "com_pastas"
        self.iniciar_tarefa(self._tarefa_fichas, modulo, da_planilha, planilha, pasta_modificados, idioma,
                            status_pmib, destino_fichas, template, lista_sel, criar_pastas,
                            botao=self.btn_criar_fichas)
        return None

    def _escolher_codigos(self, codigos):
        escolhidos = []
        dialogo = _SelecaoDeCodigos(
            self, itens=codigos, titulo="Selecione os Códigos PMIB", instrucao="Selecione um ou mais códigos:",
            geometria="400x500", fonte_instrucao=("Roboto", 14), fonte_lista=("Consolas", 11), modal=True,
            ao_confirmar=escolhidos.extend)
        dialogo.esperar()
        return escolhidos

    def _tarefa_fichas(self, modulo, da_planilha, planilha, pasta_modificados, idioma, status_pmib,
                       destino_fichas, template, lista_sel, criar_pastas) -> None:
        catalogo = None
        if da_planilha:
            # Antes de criar qualquer subpasta: planilha ilegível para o lote
            # sem deixar pasta vazia para trás.
            self.log("Lendo a planilha de PDMs...")
            try:
                catalogo = pdm_catalogo.carregar(planilha)
            except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
                self.log(f"ERRO ao ler a planilha de PDMs: {e}")
                self.avisar("Erro", f"Não consegui ler a planilha de PDMs:\n{e}", tipo="erro")
                return

        self.log(f"Preparando diretórios (Modo: {'Com Pastas' if criar_pastas else 'Apenas Planilhas'})...")
        dados_pastas, msg = modulo.processar_pastas_fichas(status_pmib, destino_fichas, lista_sel,
                                                           criar_subpastas=criar_pastas)
        self.log(msg)
        if not dados_pastas:
            self.avisar("Aviso", "Nenhum código foi processado.")
            return

        if da_planilha:
            msg_res, _logs = modulo.aplicar_templates_fichas_da_planilha(
                dados_pastas, catalogo, template, log_callback=self.log, retry_lock=self.perguntar_retry_excel)
        else:
            self.log("Injetando os dados dos PDMs no Template (a partir da linha 79)...")
            # O idioma vai para o serviço, e não o nome da aba: quem sabe como a
            # aba se chama em inglês é o serviço (`NOME_DA_ABA_EM_INGLES`).
            msg_res, _logs = modulo.aplicar_templates_fichas(
                dados_pastas, pasta_modificados, template, log_callback=self.log,
                retry_lock=self.perguntar_retry_excel, idioma=idioma)
        self.log(msg_res)
        self.log(">>> Processo de criação de fichas finalizado!")
        self.avisar("Fim", f"Processo de criação de fichas finalizado.\n\n{msg_res}")

    # --- Aba 3 ------------------------------------------------------------------
    def _op3_executar(self) -> None:
        pasta_limpeza = self.entry_clean.text()
        if not pasta_limpeza:
            return self.avisar("Aviso", "Por favor, selecione a pasta para limpeza primeiro.", tipo="aviso")
        modulo = self.backend("pdm_backend")
        if modulo is None:
            return None
        self.iniciar_tarefa(self._tarefa_limpeza, modulo, pasta_limpeza, botao=self.btn_exec_clean)
        return None

    def _tarefa_limpeza(self, modulo, pasta_limpeza) -> None:
        self.log(f"Iniciando varredura por duplicados em: {pasta_limpeza}...")
        res = modulo.logica_excluir_duplicados(pasta_limpeza, log_callback=self.log)
        self.log(res)
        self.avisar("Resultado", "Limpeza concluída.")

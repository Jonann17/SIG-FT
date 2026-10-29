"""Tela "Planilhas PMIB" (PDM) na interface Qt.

Duas coisas, desde 2026-10-21 (pedido do Luan): o painel de cima com a
planilha de PDMs (SAM-GM) e, abaixo dele, a criação das planilhas PMIB, que
monta cada ficha a partir do template com as características da planilha
(em inglês, traduzidas pelo serviço).
Sairam as abas "Processar PDMs" (fatiar From Itaipu, PDMs Modificados,
traduzir a pasta, regenerar) e "Excluir Duplicados", e com elas tudo da pasta
de PDMs Modificados; com uma aba só, a tela deixou de ter abas.

O worker fala com a tela pelo console (seguro de qualquer thread), pelas
mensagens do fim (`avisar`) e por `iniciar_tarefa` (o botão fica desligado
enquanto ela roda). Tudo o que o worker lê dos campos é lido NO CLIQUE, na
thread da interface.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLineEdit, QRadioButton, QVBoxLayout

from sigft.app.idioma import marcar, t
from sigft.app_qt import estilo, file_dialogs
from sigft.app_qt.widgets import blocos, dialogos_selecao
from sigft.app_qt.widgets.arrastar import Arrastavel
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.module_frame import MARGEM_DA_TELA, ModuleFrame
from sigft.core import pdm_catalogo

TEXTO_NENHUM_ARQUIVO = marcar("Nenhum arquivo selecionado")
EXCEL = [("Excel", "*.xlsx *.xls")]


# --- peças -------------------------------------------------------------------
def _rotulo(texto: str, *, largura: int | None = None, tamanho: int = 13, negrito: bool = False,
            papel: str | None = None, elidir: bool = False):
    """CTkLabel de uma linha, `anchor="w"` (sem quebra: lá o texto não quebra).
    `elidir`: o rótulo de um nome de arquivo (`blocos.RotuloElidido`)."""
    r = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, papel=papel, alinhar="esquerda",
                      elidir=elidir)
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
    """CTkFrame de cantos 8 (os quadros de dentro das abas): a `superficie_alta`,
    um degrau acima do quadro das abas (regra `#quadro_pdm` da folha)."""
    quadro = QFrame(objectName="quadro_pdm")
    quadro.setStyleSheet("#quadro_pdm { border-radius: 8px; }")
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
        rb = QRadioButton(texto)   # 100 de largura no mínimo, como lá: regra da folha do app
        self.addButton(rb)
        self.botoes[valor] = rb
        if valor == self._padrao:
            rb.setChecked(True)
        return rb

    def get(self) -> str:
        return next((v for v, rb in self.botoes.items() if rb.isChecked()), "")

    def set(self, valor: str) -> None:
        self.botoes[valor].setChecked(True)


# =============================================================================
class ModuloPDM(ModuleFrame):
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_sam_gm", "pdm.sam_gm", (".xlsx", ".xls")),
        Arrastavel("btn_pmib", "pdm.status_pmib", (".xlsx", ".xls")),
        Arrastavel("btn_template", "pdm.template", (".xlsx", ".xls")),
    )

    def __init__(self, parent=None, controller=None) -> None:
        # Os caminhos de ARQUIVO (os StringVar sem campo visível de lá).
        self.path_sam_gm = self.path_status_pmib = self.path_template = ""
        super().__init__(parent, controller, titulo=t("Gerenciador de PDMs"))
        # Header, conteúdo e console com 20 px entre eles. O conteúdo fica com
        # a sobra e rola; o console tem a altura padrão
        # (tests/test_pdm_tela_layout.py).
        raiz = self.layout()
        raiz.setContentsMargins(MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10,
                                MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10)
        raiz.setSpacing(20)

    # --- montagem -------------------------------------------------------------
    def _build_ui(self) -> None:
        instalar_como_funciona(self, "PDM")
        self._rotulos = {}
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        # A barra de rolagem fica sempre à vista: a largura do formulário (900)
        # não muda quando o conteúdo passa a caber.
        self.area, corpo = blocos.area_rolavel(self.content_layout, barra_sempre_visivel=True)
        corpo.addSpacing(10)
        self._painel_global(corpo)
        corpo.addSpacing(20)
        # A criação das planilhas PMIB num cartão, como era dentro da aba: os
        # dois quadros (configuração e execução) um degrau acima dele.
        cartao = blocos.cartao(corpo)
        self.cartao_fichas = cartao.parentWidget()
        cartao.setContentsMargins(20, 0, 20, 0)
        cartao.setSpacing(0)
        self._build_fichas(cartao)
        corpo.addSpacing(10)
        # A sobra fica embaixo; sem isto o cartão esticaria.
        corpo.addStretch(1)

    def _painel_global(self, corpo) -> None:
        r = self._rotulos
        layout = blocos.cartao(corpo)
        self.cartao_config = layout.parentWidget()
        layout.setContentsMargins(15, 10, 15, 15)       # padx=15; título pady=(10, …); f_plan (…, 15)
        layout.setSpacing(0)
        r["config"] = _rotulo(t("Configuração Global"), tamanho=14, negrito=True, papel="destaque")
        layout.addWidget(r["config"])
        layout.addSpacing(5)                            # título (…, 5)

        # A planilha de PDMs (SAM-GM): de onde vêm as características de
        # cada ficha.
        r["sam_gm"] = _rotulo(t("Planilha de PDMs (SAM-GM):"), largura=190)
        self.btn_sam_gm = _botao(t("Selecionar"), largura=100, variante="cinza")
        self.btn_sam_gm.clicked.connect(self._sel_sam_gm)
        self.lbl_sam_gm_status = _rotulo(t(TEXTO_NENHUM_ARQUIVO), papel="legenda", elidir=True)
        layout.addLayout(_linha(r["sam_gm"], 5, self.btn_sam_gm, 20, self.lbl_sam_gm_status))

    def _campo_de_pasta(self, layout, chave_rotulo, texto, *, largura_rotulo=240):
        """Rótulo + campo (280, padx=5) + "Buscar" (80): a linha de pasta."""
        self._rotulos[chave_rotulo] = _rotulo(texto, largura=largura_rotulo)
        campo = QLineEdit()
        campo.setFixedWidth(280)
        botao = _botao(t("Buscar"), largura=80)
        layout.addLayout(_linha(self._rotulos[chave_rotulo], 5, campo, 5, botao))
        return campo, botao

    def _build_fichas(self, lay) -> None:
        r = self._rotulos
        lay.addSpacing(10)                              # frm_files: pady=10

        # --- SEÇÃO 1: Configuração de Arquivos e Pastas ---
        self.quadro_fichas, q = _quadro(lay, (10, 5, 10, 8))
        r["fichas"] = _rotulo(t("Configuração das Fichas PMIB"), tamanho=14, negrito=True)
        q.addWidget(r["fichas"])
        q.addSpacing(13)                                # título (…, 5) + linha (8, …)

        # STATUS_PMIB (botão + rótulo)
        self.btn_pmib = _botao(t("Selecionar STATUS_PMIB (.xlsx)"), largura=240, variante="cinza", tamanho_fonte=12)
        self.btn_pmib.clicked.connect(self._sel_status_pmib)
        self.lbl_pmib_status = _rotulo(t(TEXTO_NENHUM_ARQUIVO), papel="legenda", elidir=True)
        q.addLayout(_linha(self.btn_pmib, 15, self.lbl_pmib_status))
        q.addSpacing(16)

        # Destino das fichas (campo + Buscar)
        self.entry_destino_fichas, self.btn_buscar_fichas = self._campo_de_pasta(
            q, "destino_fichas", t("Pasta Destino das Fichas:"))
        self.btn_buscar_fichas.clicked.connect(self._buscar_destino_fichas)
        q.addSpacing(16)

        # Template (botão + rótulo)
        self.btn_template = _botao(t("Selecionar Template (.xlsx)"), largura=240, variante="cinza", tamanho_fonte=12)
        self.btn_template.clicked.connect(self._sel_template)
        self.lbl_template_status = _rotulo(t(TEXTO_NENHUM_ARQUIVO), papel="legenda", elidir=True)
        q.addLayout(_linha(self.btn_template, 15, self.lbl_template_status))
        q.addSpacing(16)

        # IDIOMA DA FICHA (2026-08-28). Explícito, e não deduzido do nome do
        # template: deduzir quebraria em silêncio no dia em que alguém
        # renomeasse o arquivo.
        r["idioma"] = _rotulo(t("Idioma da ficha:"), largura=240)
        self.idioma_ficha = _Opcoes("pt", self)
        self.rb_pt = self.idioma_ficha.adicionar("Português", "pt")
        self.rb_en = self.idioma_ficha.adicionar("English", "en")
        r["idioma_dica"] = _rotulo(t("(English traduz as características da planilha)"), tamanho=11,
                                   papel="legenda")
        q.addLayout(_linha(r["idioma"], 10, self.rb_pt, 20, self.rb_en, 20, r["idioma_dica"]))
        lay.addSpacing(20)                              # frm_files (…, 10) + frm_exec (10, …)

        # --- SEÇÃO 2: Modo de Execução ---
        self.quadro_exec, q = _quadro(lay, (10, 10, 10, 10))
        r["selecao"] = _rotulo(t("Seleção de Itens:"), largura=120, tamanho=12, negrito=True)
        self.modo_pmib = _Opcoes("todos", self)
        self.rb_todos = self.modo_pmib.adicionar(t("Todos da Lista"), "todos")
        self.rb_selecionar = self.modo_pmib.adicionar(t("Selecionar Manualmente"), "selecionar")
        q.addLayout(_linha(r["selecao"], 10, self.rb_todos, 20, self.rb_selecionar))
        q.addSpacing(10)                                # f_rad (…, 5) + f_out (5, …)
        r["saida"] = _rotulo(t("Formato de Saída:"), largura=120, tamanho=12, negrito=True)
        self.modo_saida_fichas = _Opcoes("apenas_planilhas", self)
        self.rb_apenas = self.modo_saida_fichas.adicionar(t("Apenas Planilhas (Padrão)"), "apenas_planilhas")
        self.rb_com_pastas = self.modo_saida_fichas.adicionar(t("Criar Subpastas + Planilhas"), "com_pastas")
        q.addLayout(_linha(r["saida"], 10, self.rb_apenas, 20, self.rb_com_pastas))
        q.addSpacing(20)                                # f_out (…, 10) + botão (10, …)
        self.btn_criar_fichas = _botao(t("Executar: Criar Fichas PMIB"), variante="primario")
        self.btn_criar_fichas.clicked.connect(self._op2_executar)
        q.addWidget(self.btn_criar_fichas, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(10)                              # frm_exec: pady=10

    # --- seletores ------------------------------------------------------------
    @staticmethod
    def _escolher_pasta(campo, chave, titulo=None) -> None:
        """Lá o campo recebia o "" do cancelar e apagava o caminho já escolhido."""
        pasta = file_dialogs.ask_directory(chave, "pasta", **({"titulo": titulo} if titulo else {}))
        if pasta:
            campo.setText(pasta)

    def _buscar_destino_fichas(self) -> None:
        self._escolher_pasta(self.entry_destino_fichas, "pdm.destino_fichas", t("Pasta onde as fichas serão criadas"))

    def _sel_sam_gm(self) -> None:
        f = file_dialogs.ask_open_file("pdm.sam_gm", "excel", titulo=t("Selecione o PDM's SAM-GM"), filetypes=EXCEL)
        if f:
            self.path_sam_gm = f
            blocos.marcar_arquivo_escolhido(self.btn_sam_gm, self.lbl_sam_gm_status, f)

    def _sel_status_pmib(self) -> None:
        f = file_dialogs.ask_open_file("pdm.status_pmib", "excel", titulo=t("Selecione o STATUS_PMIB"), filetypes=EXCEL)
        if f:
            self.path_status_pmib = f
            blocos.marcar_arquivo_escolhido(self.btn_pmib, self.lbl_pmib_status, f)

    def _sel_template(self) -> None:
        f = file_dialogs.ask_open_file("pdm.template", "excel", titulo=t("Selecione o Template"), filetypes=EXCEL)
        if f:
            self.path_template = f
            blocos.marcar_arquivo_escolhido(self.btn_template, self.lbl_template_status, f)

    # --- Criar planilhas PMIB ---------------------------------------------------
    def _op2_executar(self) -> None:
        # As características vêm sempre da planilha de PDMs do painel de cima;
        # em inglês, o serviço as traduz (2026-10-21).
        idioma = self.idioma_ficha.get()
        planilha = self.path_sam_gm
        if not planilha:
            return self.avisar(t("Aviso"), t("Selecione a planilha de PDMs no painel de cima."), tipo="aviso")

        status_pmib = self.path_status_pmib
        destino_fichas = self.entry_destino_fichas.text()
        template = self.path_template
        if not status_pmib:
            return self.avisar(t("Aviso"), t("Por favor, busque o arquivo STATUS_PMIB na tela."), tipo="aviso")
        if not destino_fichas:
            return self.avisar(t("Aviso"), t("Por favor, busque a Pasta Destino das Fichas na tela."), tipo="aviso")
        if not template:
            return self.avisar(t("Aviso"), t("Por favor, busque o Template Ficha Técnica na tela."), tipo="aviso")
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
                    return self.avisar(t("Erro"), str(erro), tipo="erro")
                # Modal (o `grab_set` de lá): a tela não tem o que fazer sem a
                # resposta; `esperar()` é o `wait_window`.
                lista_sel = self._escolher_codigos(codigos)
                if not lista_sel:
                    self.log("Seleção manual de códigos cancelada.")
                    return None
            except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
                return self.avisar(t("Erro"), t("Ocorreu um erro ao ler o STATUS_PMIB:\n{erro}", erro=e), tipo="erro")

        criar_pastas = self.modo_saida_fichas.get() == "com_pastas"
        self.iniciar_tarefa(self._tarefa_fichas, modulo, planilha, idioma,
                            status_pmib, destino_fichas, template, lista_sel, criar_pastas,
                            botao=self.btn_criar_fichas)
        return None

    def _escolher_codigos(self, codigos):
        escolhidos = []
        # Sem Esc (o diálogo compartilhado o ignora): a lista pode ter dezenas
        # de códigos marcados um a um. "X" continua cancelando.
        dialogo = dialogos_selecao.SelecaoMultiplaDialog(
            self, itens=codigos, titulo=t("Selecione os Códigos PMIB"), instrucao=t("Selecione um ou mais códigos:"),
            geometria="400x500", fonte_instrucao=("Roboto", 14), fonte_lista=("Consolas", 11), modal=True,
            ao_confirmar=escolhidos.extend)
        dialogo.esperar()
        return escolhidos

    def _tarefa_fichas(self, modulo, planilha, idioma, status_pmib, destino_fichas, template,
                       lista_sel, criar_pastas) -> None:
        # Antes de criar qualquer subpasta: planilha ilegível para o lote sem
        # deixar pasta vazia para trás.
        self.log("Lendo a planilha de PDMs...")
        try:
            catalogo = pdm_catalogo.carregar(planilha)
        except Exception as e:  # noqa: BLE001 -- a mensagem vai inteira para a pessoa
            self.log(f"ERRO ao ler a planilha de PDMs: {e}")
            self.avisar(t("Erro"), t("Não consegui ler a planilha de PDMs:\n{erro}", erro=e), tipo="erro")
            return

        self.log(f"Preparando diretórios (Modo: {'Com Pastas' if criar_pastas else 'Apenas Planilhas'})...")
        dados_pastas, msg = modulo.processar_pastas_fichas(status_pmib, destino_fichas, lista_sel,
                                                           criar_subpastas=criar_pastas)
        self.log(msg)
        if not dados_pastas:
            self.avisar(t("Aviso"), t("Nenhum código foi processado."))
            return

        # O idioma vai para o serviço, e não o nome da aba: quem sabe como a
        # aba se chama em inglês é o serviço (`NOME_DA_ABA_EM_INGLES`). Em
        # inglês, `traduzir=None` é o motor padrão (IA com a reserva), que o
        # serviço monta DEPOIS de ler o glossário, para os termos dele irem à
        # IA; sem `api_key`, `get_llm` resolve a chave do provedor escolhido
        # para `traduzir_pdm` em "Modelos de IA". Outro motor (um tradutor
        # local) entra aqui, como `traduzir=`.
        msg_res, _logs = modulo.aplicar_templates_fichas_da_planilha(
            dados_pastas, catalogo, template, log_callback=self.log, retry_lock=self.perguntar_retry_excel,
            idioma=idioma, traduzir=None)
        self.log(msg_res)
        self.log(">>> Processo de criação de fichas finalizado!")
        self.avisar(t("Fim"), t("Processo de criação de fichas finalizado.\n\n{resultado}", resultado=msg_res))

"""A Home em Qt: cabeçalho, barra de botões, um card clicável por módulo e os
painéis que a barra abre em janela (chaves de API, modelos de IA, gastos de IA
e o mural de atividades).

É a `sigft/app/views/home.py` (interface antiga) em Qt, com o mesmo comportamento:
as mesmas chaves de configuração (gravadas pela janela principal no
`api_config.json`), os mesmos serviços (`sigft.config`, `core.llm.catalogo`,
`core.llm.selecao`, `core.llm.usage`, `services.atividades`,
`services.mural_atividades`, `services.updater`)
e os mesmos textos. Os cards seguem a decisão do protótipo de 2026-10-07
(compactos: a descrição ocupa a largura do card); o resto tem as medidas do
interface antiga, tiradas das capturas da E5.1.

Diferenças deliberadas (com o porquê no relatório da E5.1):
* um painel de cada tipo por vez: o segundo clique traz para a frente a janela
  que já está aberta. Lá cada clique abria outra, e as duas disputavam os mesmos
  campos da Home (a mais velha salvaria pelos campos da mais nova);
* a lista de modelos do provedor é buscada numa thread `daemon` e volta só por
  `interface.na_interface`; se o painel sumiu nesse meio-tempo, a resposta é
  descartada em vez de tocar em widget destruído;
* nenhum botão nem caixa dos painéis pega o foco (como os da interface antiga): Enter, Espaço
  e Esc não salvam nem descartam o que a pessoa digitou.
"""
from __future__ import annotations

import html
import threading
from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QScrollArea,
    QVBoxLayout, QWidget,
)
from shiboken6 import isValid

from sigft import config as sigft_config
from sigft.app import textos_dicas
from sigft.app_qt import atualizacao, estilo, interface
from sigft.app_qt.catalogo import MODULOS
from sigft.app_qt.estilo import mono
from sigft.app_qt.widgets import blocos, controles, dialogs, mural
from sigft.app_qt.widgets.module_frame import aplicar_dicas
from sigft.app_qt.widgets.painel_janela import JanelaPainel
from sigft.core import plataforma
from sigft.core.llm import catalogo, selecao
from sigft.core.llm import usage as llm_usage
from sigft.services import updater

# O botão da barra que procura versão nova. Constante porque dois lugares
# precisam concordar: quem cria o botão e quem o devolve ao normal.
TEXTO_BOTAO_ATUALIZACOES = "\U0001F504  Atualizações"
TEXTO_PROCURANDO = "\U0001F504  Procurando..."
# [2026-10-07] O canal de testes: marcada, a atualização oferece também
# pré-lançamentos. Ver services/updater.py.
TEXTO_CANAL_TESTES = "Versões de teste"

# A barra (`_criar_barra_de_botoes` de lá): chave, texto, variante do botão e o que
# abre. A cor de cada um é a da variante, na folha do tema. O "Atualizações" vem depois, fora da lista, porque o texto muda.
BARRA = [
    ("atividades", "\U0001F4CB  Atividades do dia", "primario", "abrir_mural_atividades"),
    ("modelos", "\U0001F916  Modelos de IA", "primario", "abrir_janela_modelos_ia"),
    ("gastos", "\U0001F4B0  Gastos de IA", "primario", "abrir_janela_gastos_ia"),
    ("chaves", "\U0001F511  Chaves de API", "secundario", "abrir_janela_chaves_api"),
]
COR_BOTAO_ATUALIZACOES = "secundario"   # variante (2026-10-20)

# As chaves do painel "Chaves de API" (o `keys_info` de lá, sem o valor padrão,
# que é sempre vazio: as chaves vêm do .env ou do api_config.json).
CHAVES_API = (
    ("GEMINI", "Gemini API Key:"),
    ("GOOGLE_SEARCH", "Google Search API:"),
    ("GOOGLE_CSE", "Google CSE ID:"),
    ("LLAMA", "LlamaCloud API:"),
    # [CP 3.2] Gateway OpenRouter (padrão) + endpoint OpenAI-compatível da
    # futura IA interna da empresa.
    ("OPENROUTER", "OpenRouter API Key:"),
    ("EMPRESA_LLM_BASE_URL", "IA Empresa (Base URL):"),
    ("EMPRESA_LLM_API_KEY", "IA Empresa (API Key):"),
)

ROTULOS_TAREFA_IA = {
    "categorizar_pdm": "Categorizar PDM (Cria Fichas):",
    "validar_ficha": "Validar ficha (Analyzer):",
    "condicoes": "Condições (Upload Condições):",
    "tech_specs": "Caract. Técnicas (Upload Specs):",
    "autospec": "AutoSpec (RAG):",
    "interpretar_material": "Interpretar material (Cria Fichas):",
    "traduzir_pdm": "Traduzir PDM (Planilhas PMIB):",
}

DESCRICAO_MODELOS_IA = (
    "Escolha primeiro COM QUAL CHAVE trabalhar; a lista de modelos passa a ser a daquele "
    "provedor. \"Aplicar recomendados\" usa os modelos sugeridos em "
    "docs/refatoracao/MODELOS_IA.md, que são mais econômicos. Valide a qualidade numa amostra "
    "antes de rodar em lote.")
SEM_PROVEDOR_IA = (
    "Nenhum provedor de IA tem chave configurada acima. Configure ao menos uma "
    "chave (ex.: Gemini ou OpenRouter) para escolher o modelo aqui.")

# --- aparência (as cores são da folha do tema, desde 2026-10-20) ---------------
FONTE_CTK = ("Roboto", 13)                 # CTkFont() do tema
FONTE_TITULO_PAINEL = ("Arial", 16, "bold")
FONTE_DICA = ("Roboto", 12)
# O Tk dá 15 px por linha ao Roboto 12 (o "linespace" da fonte); o Qt, 14. Num
# texto de 11 linhas (o relatório de gastos) seriam 11 px a menos. Os rótulos de
# várias linhas fixam a linha do Tk (como a caixa de notas da atualização).
LINHA_TK_ROBOTO_12 = 15
# `wraplength=800` dos rótulos de várias linhas dos painéis.
QUEBRA_PAINEL = 800
# Larguras de lá (`width=`): rótulo das linhas, menus e campos.
LARGURA_ROTULO_CHAVE = 140
LARGURA_ROTULO_IA = 220
LARGURA_CAMPO_IA = 300
LARGURA_MENU_PROVEDOR = 300
LARGURA_MENU_MODELO = 420
LARGURA_LIMPAR = 70


# =============================================================================
# Peças
# =============================================================================
def _rotulo(texto: str, fonte: tuple = FONTE_CTK, *, largura_minima: int | None = None) -> QLabel:
    """CTkLabel de uma linha, `anchor="w"` (`blocos.rotulo_tk`, com a fonte
    padrão do CTkLabel e o texto comum); `largura_minima` é o `width=` (o texto
    maior alarga)."""
    return blocos.rotulo_tk(texto, fonte, largura_minima=largura_minima)


def _titulo_painel(texto: str) -> QLabel:
    """O título em negrito com emoji dos painéis (rótulo fixo: o emoji vai em P&B)."""
    return _rotulo(mono(texto), FONTE_TITULO_PAINEL)


class _Texto(QLabel):
    """CTkLabel de várias linhas (`justify="left"`, `wraplength`).

    Vai DIRETO na coluna do painel (não numa linha horizontal, que o centraria):
    ocupa a largura até `largura_maxima` e quebra linha nela, como o
    `wraplength` de lá. `altura_linha` fixa a altura da linha do Tk (texto rico
    com `white-space: pre-wrap`, que guarda os espaços do começo das linhas).
    `texto_puro` é o texto que a pessoa lê; `papel`, o papel de texto da folha
    (sem ele, o texto comum).
    """

    def __init__(self, texto: str = "", fonte: tuple = FONTE_DICA, *, papel: str | None = None,
                 largura_maxima: int | None = QUEBRA_PAINEL, altura_linha: int | None = None) -> None:
        super().__init__()
        self.texto_puro = ""
        self._altura_linha = altura_linha
        self._fonte, self._papel = fonte, papel
        self.setTextFormat(Qt.TextFormat.RichText if altura_linha else Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        if largura_maxima:
            self.setMaximumWidth(largura_maxima)
        self.setStyleSheet(f"{blocos.folha_fonte_tk(self._fonte)} background: transparent;")
        self.definir(texto)

    def definir(self, texto, *, papel: str | None = None) -> None:
        """`papel` troca o papel só desta vez (um erro); sem ele, volta o de nascença."""
        estilo.definir_papel(self, papel or self._papel)
        self.texto_puro = str(texto)
        if self._altura_linha:
            self.setText(f'<div style="white-space: pre-wrap; line-height: {self._altura_linha}px">'
                         f"{html.escape(self.texto_puro)}</div>")
        else:
            self.setText(self.texto_puro)


def _botao(texto: str, *, variante: str | None = None,
           largura_minima: int = estilo.LARGURA_BOTAO_CTK, **kw):
    """CTkButton de 28 px: largura 140 (ou o texto + 7 de cada lado), sem foco."""
    b = blocos.botao(texto, variante=variante, altura=28,
                     largura_minima=largura_minima, **kw)
    dialogs.sem_tecla(b)
    return b


def _botao_cinza(texto: str, *, largura_minima: int = estilo.LARGURA_BOTAO_CTK):
    """O botão cinza que a tela escrevia à mão: a variante "cinza" (= secundário)."""
    return _botao(texto, variante="cinza", largura_minima=largura_minima)


def _menu(opcoes: list[str], largura: int) -> controles.MenuDeOpcoes:
    """CTkOptionMenu(width=largura), com as cores da paleta (`controles.MenuDeOpcoes`).

    Sem foco (as setas do teclado trocariam a escolha sem abrir o menu; a interface antiga
    não tem teclado ali) e sem roda (ver `MenuDeOpcoes.wheelEvent`).
    """
    m = controles.MenuDeOpcoes(opcoes)
    m.setFixedWidth(largura)
    m.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return m


def _trocar_opcoes(menu, valores: list[str]) -> None:
    """O `configure(values=...)` do CTkOptionMenu: troca a lista e mantém a escolha,
    se ela continua na lista; senão, a primeira (a opção neutra)."""
    atual = menu.currentText()
    menu.blockSignals(True)
    menu.clear()
    menu.addItems(valores)
    menu.setCurrentIndex(valores.index(atual) if atual in valores else 0)
    menu.blockSignals(False)
    menu.update()


def _painel(parent):
    """O quadro dos painéis: CTkFrame com cantos de 10 (`#painel_home`, a superfície), `pack(padx=10,
    pady=10)` no conteúdo da JanelaPainel. Devolve (casca, quadro, coluna); a
    coluna já tem os `padx=10` que todos os filhos usam lá."""
    casca = QWidget()
    caixa = QVBoxLayout(casca)
    caixa.setContentsMargins(10, 10, 10, 10)
    caixa.setSpacing(0)
    quadro = QFrame(objectName="painel_home")
    caixa.addWidget(quadro)
    coluna = QVBoxLayout(quadro)
    coluna.setContentsMargins(10, 0, 10, 0)
    coluna.setSpacing(0)
    parent.layout().addWidget(casca)
    return casca, quadro, coluna


def _linha(coluna, *, cima: int = 0, baixo: int = 0) -> QHBoxLayout:
    """Um CTkFrame transparente `pack(fill="x", pady=(cima, baixo))` com filhos
    `pack(side="left")`: o chamador põe os widgets e o `addStretch()` do fim."""
    linha = QHBoxLayout()
    linha.setContentsMargins(0, cima, 0, baixo)
    linha.setSpacing(0)
    coluna.addLayout(linha)
    return linha


def _empilhar(coluna, widget, *, cima: int = 0, baixo: int = 0, centro: bool = False) -> None:
    """`widget.pack(anchor="w" ou centrado, pady=(cima, baixo))` com a largura dele."""
    linha = _linha(coluna, cima=cima, baixo=baixo)
    if centro:
        linha.addStretch()
    linha.addWidget(widget)
    linha.addStretch()


def _empilhar_texto(coluna, texto: _Texto, *, cima: int = 0, baixo: int = 0) -> None:
    """Um `_Texto` na coluna (direto: ver `_Texto`) com os `pady` de lá."""
    if cima:
        coluna.addSpacing(cima)
    coluna.addWidget(texto)
    if baixo:
        coluna.addSpacing(baixo)


def _vivo(widget) -> bool:
    return widget is not None and isValid(widget)


class _Card(QFrame):
    def __init__(self, alvo, titulo, descricao, ao_clicar) -> None:
        super().__init__(objectName="card")
        self._alvo = alvo
        self._ao_clicar = ao_clicar
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(QLabel(titulo, objectName="card_titulo"))
        desc = QLabel(descricao, objectName="card_desc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        # A sobra do card mais baixo da linha fica embaixo, como na interface antiga (grid
        # sticky="nsew" e os rótulos no topo): sem isto o título descia.
        layout.addStretch()
        for rotulo in self.findChildren(QLabel):
            rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mousePressEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if evento.button() == Qt.MouseButton.LeftButton:
            self._ao_clicar(self._alvo)
        super().mousePressEvent(evento)


# =============================================================================
# A Home
# =============================================================================
class HomeView(QScrollArea):
    # Redesenho de 2026-08-11 do painel de modelos -- PROVEDOR PRIMEIRO: uma
    # pergunta de cada vez (com qual CHAVE trabalhar; depois, qual MODELO dela).
    # (O comentário longo estava na Home da interface antiga, no histórico do
    # repositório: `sigft/app/views/home.py`, removida em 2026-10-15.)
    ROTULO_PROVIDER_IA = {
        "gemini": "Gemini (chave direta do Google)",
        "openrouter": "OpenRouter (vários modelos, uma chave)",
        "openai_compat": "AMP / IA da empresa",
    }

    def __init__(self, parent=None, controller=None) -> None:
        super().__init__(parent)
        self.controller = controller
        # Um painel de cada tipo por vez (chave -> JanelaPainel).
        self._janelas: dict[str, JanelaPainel] = {}
        # Referências que os métodos do painel de modelos consultam antes de
        # existir o painel (lá, zeradas em `criar_painel_modelos_ia`).
        self.entries: dict[str, QLineEdit] = {}
        self.frame_modelos_ia = None
        self._casca_modelos_ia = None
        self._parent_modelos_ia = None
        self.opt_provider_ia = None
        self.lbl_resumo_modelo_ia = None
        self.lbl_catalogo_ia = None
        self.opts_modelo_ia: list = []
        self.menus_modelo_ia_por_tarefa: dict = {}
        self._pares_modelo_ia: list = []

        self.setWidgetResizable(True)
        self.setObjectName("conteudo")
        corpo = QWidget(objectName="conteudo")
        layout = QVBoxLayout(corpo)
        # A Home da interface antiga é um CTkScrollableFrame no grid(padx=20, pady=20): o
        # conteúdo começa 6 px para dentro (o canto) e cada filho tem padx=20 --
        # 46 dos dois lados de cima; à direita, mais os 17 da barra de rolagem
        # dele (sempre reservada): 57.
        layout.setContentsMargins(46, 46, 57, 20)
        layout.setSpacing(0)

        # --- CABEÇALHO --- (pady (20, 5); (0, 20); 10; os de baixo somam)
        self.label_titulo = QLabel("SIG-FT", objectName="titulo_home")
        layout.addWidget(self.label_titulo)
        layout.addSpacing(5)
        self.label_subtitulo = QLabel("Sistema Integrado de Gestão de Fichas Técnicas - GE Vernova",
                                      objectName="subtitulo_home")
        self.label_subtitulo.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        self.label_subtitulo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label_subtitulo)
        layout.addSpacing(30)
        resumo = ("Clique num módulo abaixo para abri-lo. Os botões desta barra "
                  "abrem painéis em janela, para a Home ficar limpa.")
        self.label_texto = self.criar_texto_simples(resumo)
        layout.addWidget(self.label_texto)
        layout.addSpacing(10)

        # --- BARRA DE BOTÕES --- [2026-09-03] Os painéis de configuração e de
        # gastos de IA saíram da Home e viraram janelas.
        layout.addLayout(self._criar_barra_de_botoes())
        layout.addSpacing(16)

        # --- MÓDULOS, CLICÁVEIS ---
        layout.addLayout(self._cards())
        layout.addStretch()
        self.setWidget(corpo)
        self._aplicar_dicas()

    def _aplicar_dicas(self) -> None:
        """As dicas de `sigft/app/textos_dicas.py`. Chamada de novo a cada
        painel aberto: os botões dele só existem depois de montado."""
        aplicar_dicas(self)
        for chave, botao in self.botoes_barra.items():
            dica = textos_dicas.DICAS_DA_BARRA_DA_HOME.get(chave)
            if dica and not botao.toolTip():
                botao.setToolTip(dica)
        if not self.caixa_canal_testes.toolTip():
            self.caixa_canal_testes.setToolTip(textos_dicas.DICAS_DA_BARRA_DA_HOME["canal_testes"])

    def criar_texto_simples(self, texto: str) -> QLabel:
        """CTkLabel(font=("Arial", 14), wraplength=800) da Home."""
        r = QLabel(texto, objectName="texto_simples")
        r.setWordWrap(True)
        r.setMaximumWidth(QUEBRA_PAINEL)
        r.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        r.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        r.setStyleSheet(blocos.folha_fonte_tk(("Arial", 14)))
        return r

    # =====================================================================
    # BARRA DE BOTÕES  [2026-09-03]
    # =====================================================================
    def _criar_barra_de_botoes(self) -> QHBoxLayout:
        barra = QHBoxLayout()
        barra.setSpacing(0)
        self.botoes_barra = {}
        for chave, texto, variante, metodo in BARRA:
            botao = self._botao_da_barra(texto, variante)
            botao.clicked.connect(lambda _=False, m=metodo: getattr(self, m)())
            self.botoes_barra[chave] = botao
            barra.addWidget(botao)
            barra.addSpacing(10)                        # pack(side="left", padx=(0, 10))

        # [2026-09-25] Fora da lista porque o texto muda enquanto procura. A
        # abertura do app já pergunta sozinha, mas CALADA; este botão é o
        # caminho que responde.
        self.btn_atualizacoes = self._botao_da_barra(TEXTO_BOTAO_ATUALIZACOES, COR_BOTAO_ATUALIZACOES)
        self.btn_atualizacoes.clicked.connect(self.procurar_atualizacoes)
        self.botoes_barra["atualizacoes"] = self.btn_atualizacoes
        barra.addWidget(self.btn_atualizacoes)
        barra.addSpacing(10)

        # [2026-10-07] O canal de testes, desmarcado por padrão: marcado, o
        # aviso de atualização oferece também pré-lançamentos.
        self.caixa_canal_testes = controles.CaixaDeMarcar(TEXTO_CANAL_TESTES, tamanho_fonte=12)
        self.caixa_canal_testes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        try:
            ligado = updater.canal_testes_ligado()
        except Exception:  # noqa: BLE001 -- preferência é conveniência
            ligado = False
        self.caixa_canal_testes.setChecked(bool(ligado))
        self.caixa_canal_testes.toggled.connect(self._lembrar_canal_testes)
        barra.addWidget(self.caixa_canal_testes)
        barra.addStretch()
        return barra

    @staticmethod
    def _botao_da_barra(texto: str, variante: str):
        # height=40, font=("Roboto", 13, "bold"); a largura é a do CTkButton.
        botao = blocos.botao(mono(texto), variante=variante, altura=estilo.ALTURA_BOTAO_BARRA,
                             tamanho_fonte=13, negrito=True, largura_minima=estilo.LARGURA_BOTAO_CTK)
        dialogs.sem_tecla(botao)
        return botao

    def _lembrar_canal_testes(self, ligado: bool) -> None:
        try:
            updater.ligar_canal_testes(bool(ligado))
        except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar o clique
            pass

    def procurar_atualizacoes(self) -> None:
        """Pergunta ao GitHub agora e SEMPRE responde (ver `app_qt/atualizacao.py`)."""
        botao = self.btn_atualizacoes
        botao.setEnabled(False)
        botao.setText(mono(TEXTO_PROCURANDO))

        def ao_terminar():
            if _vivo(botao):
                botao.setEnabled(True)
                botao.setText(mono(TEXTO_BOTAO_ATUALIZACOES))

        atualizacao.procurar_agora(self.controller, ao_terminar=ao_terminar)

    # --- as janelas -----------------------------------------------------------
    def _trazer_para_frente(self, chave: str):
        """A janela do painel `chave`, se está aberta: trazida para a frente."""
        janela = self._janelas.get(chave)
        if not _vivo(janela) or not janela.isVisible():
            return None
        if janela.isMinimized():
            # Só tira o "minimizado": `showNormal()` também desmaximizaria a
            # janela que a pessoa tinha maximizado antes de minimizar.
            janela.setWindowState(janela.windowState() & ~Qt.WindowState.WindowMinimized)
        janela.raise_()
        janela.activateWindow()
        return janela

    def _abrir_painel(self, chave: str, *, titulo: str, montar, geometria: str):
        aberta = self._trazer_para_frente(chave)
        if aberta is not None:
            return aberta
        # A fechada (só escondida) dá lugar a uma nova, montada com o que vale
        # agora -- como a interface antiga, que recriava o painel a cada clique.
        velha = self._janelas.pop(chave, None)
        if _vivo(velha):
            velha.deleteLater()
        janela = JanelaPainel(self, titulo=titulo, montar=montar, geometria=geometria)
        self._janelas[chave] = janela
        self._aplicar_dicas()
        return janela

    def _janela_aberta(self, chave: str) -> bool:
        janela = self._janelas.get(chave)
        return _vivo(janela) and janela.isVisible()

    def _janela_de(self, widget):
        """O pai das caixas de mensagem: a janela do painel, para a caixa nascer
        na frente dela (e não atrás, na janela principal)."""
        return widget.window() if _vivo(widget) else self

    def abrir_janela_chaves_api(self):
        return self._abrir_painel("chaves", titulo="Chaves de API",
                                  montar=self.criar_area_config_api, geometria="760x520")

    def abrir_janela_modelos_ia(self):
        return self._abrir_painel("modelos", titulo="Modelos de IA",
                                  montar=self.criar_painel_modelos_ia, geometria="900x680")

    def abrir_janela_gastos_ia(self):
        return self._abrir_painel("gastos", titulo="Gastos de IA",
                                  montar=self.criar_painel_gastos_ia, geometria="860x600")

    # =====================================================================
    # MURAL DE ATIVIDADES  [2026-09-03]
    # =====================================================================
    # Abre por BOTÃO, não na abertura do app -- decisão do usuário. Ler a
    # planilha do Box a cada abertura faria o SIG-FT depender do Box estar
    # sincronizado só para abrir.
    def abrir_mural_atividades(self):
        aberta = self._trazer_para_frente("atividades")
        if aberta is not None:
            return aberta
        gavetas, erro = self._ler_mural()
        return self._abrir_painel(
            "atividades", titulo="Atividades do dia",
            montar=lambda pai: mural.montar(pai, gavetas, date.today().strftime("%d/%m/%Y"), erro),
            geometria="820x640")

    def _ler_mural(self):
        """`(gavetas, erro)` -- a aba Atividades do mapeamento, lida pelo
        serviço (`services/mural_atividades.ler_mural_do_mapeamento`), o mesmo da
        Home interface antiga. O erro vem como TEXTO: o mural é informativo."""
        from sigft.services import mural_atividades

        return mural_atividades.ler_mural_do_mapeamento(self._caminho_do_mapeamento(), date.today())

    def _caminho_do_mapeamento(self):
        """O último arquivo gerenciadora que o usuário escolheu, se existir
        (`services/mural_atividades.caminho_do_mapeamento`)."""
        from sigft.services import mural_atividades

        return mural_atividades.caminho_do_mapeamento()

    # =====================================================================
    # CARDS DOS MÓDULOS  [2026-09-03] -- clicáveis
    # =====================================================================
    def _cards(self) -> QGridLayout:
        grade = QGridLayout()
        # CTkFrame(padx=20, pady=(0, 20)) com os cards em grid(padx=6, pady=6):
        # 6 em volta e 12 entre eles; colunas `uniform`.
        grade.setContentsMargins(6, 6, 6, 6)
        grade.setSpacing(12)
        grade.setColumnStretch(0, 1)
        grade.setColumnStretch(1, 1)
        self.cards: dict[str, _Card] = {}
        for indice, (alvo, titulo, descricao) in enumerate(MODULOS):
            card = _Card(alvo, titulo, descricao, self._ir)
            self.cards[alvo] = card
            grade.addWidget(card, indice // 2, indice % 2)
        return grade

    def _ir(self, alvo: str) -> None:
        if self.controller is not None:
            self.controller.show_frame(alvo)

    # =====================================================================
    # CHAVES DE API
    # =====================================================================
    def criar_area_config_api(self, parent) -> None:
        """O painel de configuração das chaves de API, dentro de `parent`."""
        _casca, quadro, coluna = _painel(parent)
        self.frame_chaves_api = quadro
        self.lbl_titulo_chaves_api = _titulo_painel("🔑 Configuração de Chaves API (Global)")
        _empilhar(coluna, self.lbl_titulo_chaves_api, cima=10, baixo=10)

        # [SEGURANÇA] Sem valores padrão escritos aqui: as chaves vêm do .env ou
        # do api_config.json (ambos fora do versionamento). Os campos ficam
        # mascarados (show="*") e o valor nunca vai para o log.
        self.entries = {}
        self.rotulos_chaves_api = {}
        for key_id, texto in CHAVES_API:
            linha = _linha(coluna, cima=2, baixo=2)
            rotulo = _rotulo(texto, largura_minima=LARGURA_ROTULO_CHAVE)
            linha.addWidget(rotulo)
            entry = QLineEdit()
            entry.setEchoMode(QLineEdit.EchoMode.Password)
            # O caractere da máscara do Tk é o asterisco; o do Qt, a bolinha.
            entry.setStyleSheet("lineedit-password-character: 42;")
            entry.setText(self.controller.get_key(key_id) or "")
            linha.addSpacing(5)                         # pack(fill="x", expand=True, padx=5)
            linha.addWidget(entry, 1)
            linha.addSpacing(5)
            self.entries[key_id] = entry
            self.rotulos_chaves_api[key_id] = rotulo

        self.btn_salvar_chaves = _botao("Salvar Chaves", variante="primario")
        self.btn_salvar_chaves.clicked.connect(self.salvar_chaves_api)
        _empilhar(coluna, self.btn_salvar_chaves, cima=10, baixo=10, centro=True)

    def salvar_chaves_api(self) -> None:
        # `.strip()`: uma chave colada com espaço/quebra de linha no fim vira
        # `400 API_KEY_INVALID` no Google, e a mensagem culpa a chave.
        new_keys = {k: e.text().strip() for k, e in self.entries.items()}
        self.controller.save_keys(new_keys)

        # O painel "Modelos de IA" filtra os modelos pelos provedores que TÊM
        # chave: se ele está aberto, é remontado para enxergar a chave nova na
        # hora (fechado, a próxima abertura já a vê).
        try:
            if self._janela_aberta("modelos"):
                self._recarregar_painel_modelos_ia()
        except Exception:  # noqa: BLE001 -- a chave JÁ foi gravada
            pass

        primeiro = next(iter(self.entries.values()), None)
        QMessageBox.information(self._janela_de(primeiro), "Sucesso",
                                "Chaves API salvas com sucesso!\nTodos os módulos usarão as novas chaves.")

    # =====================================================================
    # PAINEL "MODELOS DE IA" (Checkpoint 3.3 do plano de refatoração)
    # =====================================================================
    # Persistência via `sigft.core.llm.selecao` (o mesmo api_config.json das
    # chaves, sob "_modelos_ia"): efeito imediato, sem reiniciar o app. A
    # montagem lê SÓ o cache do catálogo (a Home não pode ficar pendurada em
    # rede); "Atualizar lista de modelos" busca de fato, numa thread.
    def criar_painel_modelos_ia(self, parent) -> None:
        """Painel "Modelos de IA": provedor -> modelo, com filtro de texto,
        override por tarefa e campo manual. Provedores sem chave não aparecem."""
        # Zeradas antes de qualquer `return` curto: métodos disparados por
        # widgets checam estas referências.
        self.lbl_resumo_modelo_ia = None
        self.lbl_catalogo_ia = None
        self.opt_provider_ia = None
        self.lbl_sem_provedor_ia = None
        self.opts_modelo_ia = []
        self.menus_modelo_ia_por_tarefa = {}
        self.rotulos_modelo_ia_por_tarefa = {}

        casca, quadro, coluna = _painel(parent)
        self._casca_modelos_ia = casca
        self.frame_modelos_ia = quadro
        # Guardado para o painel se remontar ONDE estava (`_recarregar_painel_modelos_ia`).
        self._parent_modelos_ia = parent

        self.lbl_titulo_modelos_ia = _titulo_painel("🤖 Modelos de IA")
        _empilhar(coluna, self.lbl_titulo_modelos_ia, cima=10, baixo=10)
        self.lbl_descricao_modelos_ia = _Texto(DESCRICAO_MODELOS_IA, papel="legenda",
                                               altura_linha=LINHA_TK_ROBOTO_12)
        _empilhar_texto(coluna, self.lbl_descricao_modelos_ia, baixo=10)

        providers_com_chave = sorted(
            provider_id
            for provider_id, chave_id in sigft_config.CHAVE_POR_PROVIDER.items()
            if self.controller.get_key(chave_id)
        )
        if not providers_com_chave:
            self.lbl_sem_provedor_ia = _Texto(SEM_PROVEDOR_IA, papel="erro",
                                              altura_linha=LINHA_TK_ROBOTO_12)
            _empilhar_texto(coluna, self.lbl_sem_provedor_ia, baixo=15)
            return

        estado_atual = selecao.carregar(config_path=sigft_config.CONFIG_FILE)

        # --- 1. PROVEDOR --- Pré-seleciona o da seleção já salva: reabrir tem
        # de mostrar o que está valendo, não recomeçar do primeiro da lista.
        provider_salvo = self._provider_ia_da_selecao(estado_atual)
        if provider_salvo not in providers_com_chave:
            provider_salvo = providers_com_chave[0]
        self._provider_por_rotulo = {self._rotulo_provider_ia(p): p for p in providers_com_chave}

        linha = _linha(coluna, baixo=5)
        linha.addWidget(_rotulo("Provedor (chave a usar):", largura_minima=LARGURA_ROTULO_IA))
        linha.addSpacing(5)
        self.opt_provider_ia = _menu(list(self._provider_por_rotulo), LARGURA_MENU_PROVEDOR)
        self.opt_provider_ia.setCurrentText(self._rotulo_provider_ia(provider_salvo))
        self.opt_provider_ia.activated.connect(
            lambda _i: self._trocou_provider_ia(self.opt_provider_ia.currentText()))
        linha.addWidget(self.opt_provider_ia)
        linha.addSpacing(10)
        self.btn_atualizar_catalogo_ia = _botao_cinza("Atualizar lista de modelos")
        self.btn_atualizar_catalogo_ia.clicked.connect(self._atualizar_catalogo_ia)
        linha.addWidget(self.btn_atualizar_catalogo_ia)
        linha.addStretch()

        self.lbl_catalogo_ia = _Texto("", ("Roboto", 11), papel="legenda")
        _empilhar_texto(coluna, self.lbl_catalogo_ia)

        # --- 2. FILTRO --- (o OpenRouter tem centenas de modelos e o menu não
        # tem busca)
        linha = _linha(coluna, cima=5, baixo=5)
        linha.addWidget(_rotulo("Filtrar modelos:", largura_minima=LARGURA_ROTULO_IA))
        linha.addSpacing(5)
        self.entry_filtro_modelo_ia = QLineEdit()
        self.entry_filtro_modelo_ia.setPlaceholderText("ex.: flash, haiku, minimax (vazio mostra todos)")
        self.entry_filtro_modelo_ia.setFixedWidth(LARGURA_CAMPO_IA)
        self.entry_filtro_modelo_ia.textChanged.connect(lambda _t: self._refiltrar_modelos_ia())
        linha.addWidget(self.entry_filtro_modelo_ia)
        linha.addStretch()

        # --- 3. MODELO PADRÃO ---
        linha = _linha(coluna, baixo=5)
        linha.addWidget(_rotulo("Modelo padrão (todas as tarefas):", largura_minima=LARGURA_ROTULO_IA))
        linha.addSpacing(5)
        self.opt_modelo_ia_global = _menu([self._rotulo_padrao_sistema_ia()], LARGURA_MENU_MODELO)
        self.opt_modelo_ia_global.activated.connect(
            lambda _i: self._escolheu_favorito_global_ia(self.opt_modelo_ia_global.currentText()))
        linha.addWidget(self.opt_modelo_ia_global)
        linha.addStretch()
        self.opts_modelo_ia.append((self.opt_modelo_ia_global, self._rotulo_padrao_sistema_ia()))

        # --- 4. MODO AVANÇADO ---
        self.caixa_modo_avancado_ia = controles.CaixaDeMarcar(
            "Configurar por tarefa (modo avançado)")
        self.caixa_modo_avancado_ia.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.caixa_modo_avancado_ia.setChecked(bool(estado_atual["por_tarefa"]))
        self.caixa_modo_avancado_ia.toggled.connect(lambda _v: self._toggle_modelos_ia_modo_avancado())
        _empilhar(coluna, self.caixa_modo_avancado_ia, cima=5, baixo=5)

        # As tarefas, entre a caixa e o campo manual; o `pady=(0, 10)` de lá vai
        # DENTRO do quadro, para sumir junto quando ele some.
        self.frame_modelos_ia_avancado = QWidget()
        avancado = QVBoxLayout(self.frame_modelos_ia_avancado)
        avancado.setContentsMargins(0, 0, 0, 10)
        avancado.setSpacing(0)
        for tarefa in sigft_config.TAREFAS_DO_PAINEL:
            linha = _linha(avancado, cima=2, baixo=2)
            rotulo = _rotulo(ROTULOS_TAREFA_IA.get(tarefa, tarefa), largura_minima=LARGURA_ROTULO_IA)
            linha.addWidget(rotulo)
            linha.addSpacing(5)
            menu = _menu(["Usar o global"], LARGURA_MENU_MODELO)
            menu.activated.connect(lambda _i: self._atualizar_resumo_modelo_ia())
            linha.addWidget(menu)
            linha.addStretch()
            self.menus_modelo_ia_por_tarefa[tarefa] = menu
            self.rotulos_modelo_ia_por_tarefa[tarefa] = rotulo
            self.opts_modelo_ia.append((menu, "Usar o global"))
        coluna.addWidget(self.frame_modelos_ia_avancado)
        self.frame_modelos_ia_avancado.setVisible(self.caixa_modo_avancado_ia.isChecked())

        # --- 5. MANUAL --- a saída para um id que não está na lista; o
        # provedor dele é o escolhido lá em cima.
        linha = _linha(coluna, cima=10, baixo=5)
        linha.addWidget(_rotulo("Modelo manual (se não estiver na lista):", largura_minima=LARGURA_ROTULO_IA))
        linha.addSpacing(5)
        self.entry_modelo_ia_livre = QLineEdit()
        self.entry_modelo_ia_livre.setPlaceholderText("id exato, ex.: meta-llama/llama-4")
        self.entry_modelo_ia_livre.setFixedWidth(LARGURA_CAMPO_IA)
        self.entry_modelo_ia_livre.textChanged.connect(lambda _t: self._atualizar_resumo_modelo_ia())
        linha.addWidget(self.entry_modelo_ia_livre)
        linha.addSpacing(5)
        self.btn_limpar_modelo_ia = _botao_cinza("Limpar", largura_minima=LARGURA_LIMPAR)
        self.btn_limpar_modelo_ia.clicked.connect(self._limpar_modelo_ia_livre)
        linha.addWidget(self.btn_limpar_modelo_ia)
        linha.addStretch()

        # --- 6. RESUMO ---
        self.lbl_resumo_modelo_ia = _Texto("", papel="legenda", altura_linha=LINHA_TK_ROBOTO_12)
        _empilhar_texto(coluna, self.lbl_resumo_modelo_ia, cima=8)

        # Popula as listas a partir do cache e restaura a seleção salva.
        self._recarregar_modelos_do_provider(estado_atual)

        # --- 7. BOTÕES ---
        linha = _linha(coluna, cima=10, baixo=15)
        self.btn_aplicar_recomendados_ia = _botao(mono("✨ Aplicar recomendados"), variante="primario")
        self.btn_aplicar_recomendados_ia.clicked.connect(self._aplicar_recomendados_ia)
        linha.addWidget(self.btn_aplicar_recomendados_ia)
        linha.addSpacing(10)
        self.btn_salvar_selecao_ia = _botao("Salvar seleção", variante="primario")
        self.btn_salvar_selecao_ia.clicked.connect(self._salvar_selecao_modelos_ia)
        linha.addWidget(self.btn_salvar_selecao_ia)
        linha.addStretch()

    # ------------------------------------------------------------------
    # Rótulos
    # ------------------------------------------------------------------
    def _rotulo_padrao_sistema_ia(self) -> str:
        return "Padrão do sistema (modelos atuais)"

    def _rotulo_provider_ia(self, provider) -> str:
        return self.ROTULO_PROVIDER_IA.get(provider, provider)

    @staticmethod
    def _provider_ia_da_selecao(estado_atual):
        """Provedor que a seleção salva usa: o do global, ou -- se o global
        estiver vazio -- o da maioria dos overrides por tarefa ("maioria", e
        não "o primeiro": `aplicar_recomendados` grava provedores MISTOS)."""
        if not estado_atual:
            return None
        global_salvo = estado_atual.get("global") or {}
        if global_salvo.get("provider"):
            return global_salvo["provider"]

        contagem = {}
        for cfg in (estado_atual.get("por_tarefa") or {}).values():
            provider = (cfg or {}).get("provider")
            if provider:
                contagem[provider] = contagem.get(provider, 0) + 1
        if not contagem:
            return None
        return max(sorted(contagem), key=contagem.get)

    def _rotulo_modelo_ia(self, fav) -> str:
        """Rótulo de um favorito curado -- com preço, que é o que ele acrescenta
        sobre o id cru do catálogo."""
        tier_legivel = {"padrao": "Padrão", "economia": "Economia", "poder": "Poder"}.get(fav["tier"], fav["tier"])
        return (
            f"{fav['rotulo']} ({tier_legivel}, "
            f"${fav['preco_input']:.2f} / ${fav['preco_output']:.2f} por 1M tokens)"
        )

    # ------------------------------------------------------------------
    # Lista de modelos do provedor escolhido
    # ------------------------------------------------------------------
    def _provider_ia_atual(self):
        return self._provider_por_rotulo.get(self.opt_provider_ia.currentText(), "gemini")

    def _modelos_do_provider_ia(self, provider, somente_cache=True, forcar=False):
        """[(rótulo, id, provider)] do provedor: favoritos curados primeiro (com
        preço), depois o catálogo ao vivo, sem repetir. O provider viaja JUNTO
        de cada opção: uma seleção salva em outro provedor sobrevive a uma volta
        ao painel sem ser regravada com o provedor errado."""
        recomendados = catalogo.modelos_recomendados(provider)
        pares = [(self._rotulo_modelo_ia(fav), fav["model"], provider) for fav in recomendados]
        ja_listados = {fav["model"] for fav in recomendados}

        self._catalogo_ia = catalogo.consultar(
            provider, self.controller.api_keys, somente_cache=somente_cache, forcar=forcar,
        )
        for model_id in self._catalogo_ia.modelos:
            if model_id not in ja_listados:
                pares.append((model_id, model_id, provider))
        return pares

    def _acrescentar_selecoes_salvas_ia(self, estado_atual) -> None:
        """Toda seleção já gravada aparece na lista ("(salvo) ..."), mesmo de
        outro provedor: sem isto, o "Salvar seleção" seguinte a APAGARIA."""
        if not estado_atual:
            return
        gravadas = [estado_atual.get("global")] + list(
            (estado_atual.get("por_tarefa") or {}).values()
        )
        conhecidos = {model_id for _r, model_id, _p in self._pares_modelo_ia}
        for entrada in gravadas:
            if not entrada or entrada.get("model") in conhecidos:
                continue
            model_id = entrada["model"]
            provider = entrada.get("provider") or self._provider_ia_atual()
            self._pares_modelo_ia.append((f"(salvo) {provider} / {model_id}", model_id, provider))
            conhecidos.add(model_id)

    def _recarregar_modelos_do_provider(self, estado_atual=None, forcar=False,
                                        erro_catalogo=None) -> None:
        """Repopula TODOS os menus de modelo com os do provedor atual. Na
        montagem (`estado_atual`), pré-seleciona o que já estava salvo.
        `erro_catalogo` é o motivo de o "Atualizar lista" ter falhado: vira
        aviso no rótulo do catálogo, e a lista que havia continua."""
        provider = self._provider_ia_atual()
        self._pares_modelo_ia = self._modelos_do_provider_ia(provider, forcar=forcar)
        # As seleções gravadas entram SEMPRE, não só na montagem: trocar de
        # provedor e voltar não pode fazer o que está valendo sumir.
        self._acrescentar_selecoes_salvas_ia(
            estado_atual if estado_atual is not None
            else selecao.carregar(config_path=sigft_config.CONFIG_FILE)
        )

        if self.lbl_catalogo_ia is not None:
            # Conta só as entradas VINDAS do catálogo: nelas o rótulo é o
            # próprio id (recomendados trazem preço; as salvas, "(salvo)").
            do_catalogo = sum(1 for r, m, _p in self._pares_modelo_ia if r == m)
            # O serviço diz de quando a lista é; a tela só escreve a data.
            baixado_em = self._catalogo_ia.baixado_em
            de_quando = (datetime.fromtimestamp(baixado_em).strftime("%d/%m")
                         if baixado_em is not None else None)
            if erro_catalogo and de_quando:
                texto = (f"Não foi possível atualizar a lista de modelos ({erro_catalogo}). "
                         f"Continua valendo a lista de {de_quando}.")
            elif erro_catalogo:
                texto = (f"Não foi possível baixar a lista de modelos ({erro_catalogo}). "
                         "Enquanto isso valem os recomendados e o campo manual.")
            elif do_catalogo > 0:
                extra = f", lista de {de_quando}" if self._catalogo_ia.vencido and de_quando else ""
                texto = (f"{len(self._pares_modelo_ia)} modelos disponíveis "
                         f"({do_catalogo} do catálogo do provedor{extra}).")
            else:
                texto = ("Catálogo ainda não baixado para este provedor. Clique em "
                         "\"Atualizar lista de modelos\". Enquanto isso valem os recomendados "
                         "e o campo manual.")
            self.lbl_catalogo_ia.definir(texto, papel="erro" if erro_catalogo else None)

        salvo_global = (estado_atual or {}).get("global") if estado_atual else None
        salvos_tarefa = (estado_atual or {}).get("por_tarefa", {}) if estado_atual else {}

        for menu, rotulo_neutro in self.opts_modelo_ia:
            _trocar_opcoes(menu, [rotulo_neutro] + [rotulo for rotulo, _m, _p in self._pares_modelo_ia])

        if estado_atual is not None:
            self._preselecionar_modelo_ia(self.opt_modelo_ia_global, salvo_global,
                                          self._rotulo_padrao_sistema_ia())
            for tarefa, menu in self.menus_modelo_ia_por_tarefa.items():
                self._preselecionar_modelo_ia(menu, salvos_tarefa.get(tarefa), "Usar o global")

        self._refiltrar_modelos_ia()
        self._atualizar_resumo_modelo_ia()

    def _preselecionar_modelo_ia(self, menu, salvo, rotulo_neutro) -> None:
        """Deixa o menu mostrando o que está gravado no disco (sempre acha:
        `_acrescentar_selecoes_salvas_ia` já pôs toda seleção gravada na lista)."""
        if not salvo:
            menu.setCurrentText(rotulo_neutro)
            return
        for rotulo, model_id, _provider in self._pares_modelo_ia:
            if model_id == salvo.get("model"):
                menu.setCurrentText(rotulo)
                return
        menu.setCurrentText(rotulo_neutro)

    def _refiltrar_modelos_ia(self) -> None:
        """Aplica o filtro de texto às listas. A opção escolhida NUNCA some por
        causa do filtro: sumir mudaria a seleção sem o usuário pedir."""
        termo = self.entry_filtro_modelo_ia.text().strip().lower()
        for menu, rotulo_neutro in self.opts_modelo_ia:
            casam = [
                rotulo for rotulo, model_id, _provider in self._pares_modelo_ia
                if not termo or termo in rotulo.lower() or termo in model_id.lower()
            ]
            escolhido = menu.currentText()
            valores = [rotulo_neutro] + casam
            if escolhido not in valores:
                valores.append(escolhido)
            _trocar_opcoes(menu, valores)

    def _trocou_provider_ia(self, _escolha) -> None:
        # Trocar de provedor troca a lista inteira -- e o modelo manual do
        # provedor antigo não vale para o novo.
        self.entry_modelo_ia_livre.clear()
        self._recarregar_modelos_do_provider()

    def _atualizar_catalogo_ia(self) -> None:
        """Busca o catálogo do provedor atual (rede), numa thread `daemon`: não é
        tarefa da pessoa, não segura o fechamento do app."""
        provider = self._provider_ia_atual()
        if self.lbl_catalogo_ia is not None:
            self.lbl_catalogo_ia.definir("Buscando a lista de modelos do provedor...")
        # A thread recebe uma CÓPIA das chaves e não toca em nada da Home.
        chaves = dict(self.controller.api_keys)
        threading.Thread(target=self._worker_catalogo_ia, args=(provider, chaves),
                         daemon=True, name="sigft-catalogo-ia").start()

    def _worker_catalogo_ia(self, provider, chaves) -> None:
        # `consultar` não levanta (o motivo de uma falha volta em `.erro`) e
        # grava o cache; o desenho volta para a thread da interface por
        # `na_interface`, e a resposta vai junto, guardada aqui.
        resultado = None
        try:
            resultado = catalogo.consultar(provider, chaves, forcar=True)
        finally:
            self._catalogo_baixado_ia = (provider, resultado)
            interface.na_interface(self._catalogo_chegou)

    def _catalogo_chegou(self) -> None:
        """Na thread da interface: redesenha com o cache novo -- se o painel
        ainda existe (a janela pode ter sido fechada e destruída no meio). A
        falha vira aviso só se o provedor ainda é o que foi buscado."""
        if not _vivo(self.frame_modelos_ia) or self.opt_provider_ia is None:
            return
        provider, resultado = getattr(self, "_catalogo_baixado_ia", (None, None))
        erro = resultado.erro if resultado is not None else None
        if erro and provider == self._provider_ia_atual():
            self._recarregar_modelos_do_provider(erro_catalogo=erro)
        else:
            self._recarregar_modelos_do_provider()

    # ------------------------------------------------------------------
    # Precedência e resumo
    # ------------------------------------------------------------------
    def _toggle_modelos_ia_modo_avancado(self) -> None:
        self.frame_modelos_ia_avancado.setVisible(self.caixa_modo_avancado_ia.isChecked())
        self._atualizar_resumo_modelo_ia()

    def _recarregar_painel_modelos_ia(self) -> None:
        """Remonta o painel ONDE ele estava (na janela dele)."""
        casca, pai = self._casca_modelos_ia, self._parent_modelos_ia
        if _vivo(casca):
            casca.hide()
            pai.layout().removeWidget(casca)
            casca.deleteLater()
        self.criar_painel_modelos_ia(pai)
        self._aplicar_dicas()

    def _escolheu_favorito_global_ia(self, _escolha) -> None:
        """Escolher na lista DESISTE do modelo manual -- vale sempre o último
        controle mexido (o manual vence na hora de salvar)."""
        self._limpar_modelo_ia_livre()

    def _limpar_modelo_ia_livre(self) -> None:
        self.entry_modelo_ia_livre.clear()
        self._atualizar_resumo_modelo_ia()

    def _id_do_rotulo_modelo_ia(self, rotulo):
        """(model_id, provider) da opção, ou `(None, None)` para a neutra. O
        provider vem do PAR, nunca do menu de provedor."""
        for texto, model_id, provider in self._pares_modelo_ia:
            if texto == rotulo:
                return model_id, provider
        return None, None

    def _modelo_ia_global_efetivo(self):
        """(provider, model, origem) que "Salvar seleção" vai gravar como global.
        Fonte ÚNICA -- o resumo e o salvamento leem daqui."""
        provider = self._provider_ia_atual()
        manual = self.entry_modelo_ia_livre.text().strip()
        if manual:
            return provider, manual, "campo manual"
        model_id, provider_do_modelo = self._id_do_rotulo_modelo_ia(self.opt_modelo_ia_global.currentText())
        if model_id is None:
            return None, None, "padrão do sistema"
        return provider_do_modelo, model_id, "lista de modelos"

    def _atualizar_resumo_modelo_ia(self) -> None:
        if self.lbl_resumo_modelo_ia is None:
            return

        provider, model, origem = self._modelo_ia_global_efetivo()
        if provider is None:
            linha = "Ao salvar: todas as tarefas voltam ao padrão do sistema (modelos atuais)."
        else:
            linha = f"Ao salvar: {provider} / {model}  (veio do {origem})"

        if self.menus_modelo_ia_por_tarefa and self.caixa_modo_avancado_ia.isChecked():
            com_override = [
                tarefa for tarefa, menu in self.menus_modelo_ia_por_tarefa.items()
                if self._id_do_rotulo_modelo_ia(menu.currentText())[0] is not None
            ]
            if com_override:
                linha += (
                    f"  |  {len(com_override)} tarefa(s) com modelo próprio "
                    f"({', '.join(sorted(com_override))}), que vence o padrão acima."
                )

        self.lbl_resumo_modelo_ia.definir(linha)

    def _aplicar_recomendados_ia(self) -> None:
        # Os recomendados podem levar alguma tarefa para um provider diferente
        # do usado hoje (ex.: Grok 4.5 só via OpenRouter). Sem a chave dele, a
        # troca só falharia no meio da próxima execução: avisa ANTES de gravar.
        faltando = sorted(
            provider
            for provider in selecao.providers_exigidos_pelos_recomendados()
            if not self.controller.get_key(sigft_config.CHAVE_POR_PROVIDER[provider])
        )
        if faltando:
            chaves = ", ".join(sigft_config.CHAVE_POR_PROVIDER[p] for p in faltando)
            # "Não" é o botão padrão: um Enter não aplica às cegas.
            resposta = QMessageBox.question(
                self._janela_de(self.frame_modelos_ia), "Chave de API faltando",
                f"Os modelos recomendados exigem {chaves}, que ainda não está configurada "
                "no painel de chaves acima.\n\nSe aplicar assim, os módulos que dependem "
                "desse provedor vão falhar até a chave ser preenchida.\n\nAplicar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if resposta != QMessageBox.StandardButton.Yes:
                return

        selecao.aplicar_recomendados(config_path=sigft_config.CONFIG_FILE)
        self._recarregar_painel_modelos_ia()
        QMessageBox.information(
            self._janela_de(self.frame_modelos_ia), "Recomendados aplicados",
            "Os modelos recomendados (docs/refatoracao/MODELOS_IA.md) foram aplicados: Gemini 3 Flash "
            "Preview como padrão global, com Grok 4.5 para a classificação de PDM.\n\n"
            "São modelos mais econômicos que os usados até agora. Vale validar a qualidade "
            "num punhado de fichas (comparando com o resultado anterior) antes de rodar em lote.",
        )

    def _salvar_selecao_modelos_ia(self) -> None:
        # A precedência (campo manual > menu > padrão) vive em
        # `_modelo_ia_global_efetivo`, a MESMA fonte do resumo na tela.
        provider_global, model_global, _origem = self._modelo_ia_global_efetivo()
        if provider_global is None:
            selecao.limpar_global(config_path=sigft_config.CONFIG_FILE)
        else:
            selecao.definir_global(provider_global, model_global, config_path=sigft_config.CONFIG_FILE)

        # Os overrides por tarefa: o provider vem do PAR de cada opção.
        for tarefa, menu in self.menus_modelo_ia_por_tarefa.items():
            model_id, provider_do_modelo = self._id_do_rotulo_modelo_ia(menu.currentText())
            if model_id is None:
                selecao.limpar_por_tarefa(tarefa, config_path=sigft_config.CONFIG_FILE)
            else:
                selecao.definir_por_tarefa(
                    tarefa, provider_do_modelo, model_id, config_path=sigft_config.CONFIG_FILE,
                )

        self._recarregar_painel_modelos_ia()
        QMessageBox.information(
            self._janela_de(self.frame_modelos_ia), "Seleção salva",
            "Seleção de modelos de IA salva. A próxima execução de cada módulo já usa o modelo "
            "escolhido. Não é preciso reiniciar o SIG-FT.",
        )

    # =========================================================================
    # PAINEL "GASTOS DE IA" (Checkpoint 3.4 do plano de refatoração)
    # =========================================================================
    # Resumo do `logs/llm_usage.jsonl` (`sigft.core.llm.usage`). A leitura fica
    # inteira dentro de `_atualizar_texto_gastos_ia` (try/except): o painel
    # NUNCA pode impedir a Home de abrir.
    def criar_painel_gastos_ia(self, parent) -> None:
        """Painel "Gastos de IA": o relatório em texto, "Atualizar" e "Abrir
        pasta de logs". Sem registros, a mensagem amigável do próprio relatório."""
        _casca, quadro, coluna = _painel(parent)
        self.frame_gastos_ia = quadro
        self.lbl_titulo_gastos_ia = _titulo_painel("💰 Gastos de IA")
        _empilhar(coluna, self.lbl_titulo_gastos_ia, cima=10, baixo=10)

        self.lbl_gastos_ia = _Texto("Carregando...", altura_linha=LINHA_TK_ROBOTO_12)
        _empilhar_texto(coluna, self.lbl_gastos_ia, baixo=10)
        self._atualizar_texto_gastos_ia()

        linha = _linha(coluna, baixo=15)
        self.btn_atualizar_gastos_ia = _botao_cinza("Atualizar")
        self.btn_atualizar_gastos_ia.clicked.connect(self._atualizar_texto_gastos_ia)
        linha.addWidget(self.btn_atualizar_gastos_ia)
        linha.addSpacing(10)
        self.btn_pasta_logs_ia = _botao_cinza("Abrir pasta de logs")
        self.btn_pasta_logs_ia.clicked.connect(self._abrir_pasta_logs_gastos_ia)
        linha.addWidget(self.btn_pasta_logs_ia)
        linha.addStretch()

    def _atualizar_texto_gastos_ia(self) -> None:
        """Recalcula o texto a partir de `logs/llm_usage.jsonl` (leitura local,
        síncrona). NUNCA levanta: falha vira mensagem amigável."""
        try:
            relatorio = llm_usage.usage_report()
            texto = llm_usage.formatar_relatorio_texto(relatorio)
        except Exception as e:
            texto = f"Não foi possível carregar os gastos de IA agora ({e})."
        self.lbl_gastos_ia.definir(texto)

    def _abrir_pasta_logs_gastos_ia(self) -> None:
        """Abre `Documentos\\SIG-FT\\logs\\` no explorador, criando-a se ainda
        não existir (nenhuma tarefa de IA rodou ainda)."""
        from sigft.core.dados_usuario import pasta_logs

        pasta = str(pasta_logs())
        try:
            plataforma.abrir_pasta_criando_se_preciso(pasta)
        except Exception as e:
            QMessageBox.critical(self._janela_de(getattr(self, "frame_gastos_ia", None)), "Erro",
                                 f"Não foi possível abrir a pasta de logs: {e}")

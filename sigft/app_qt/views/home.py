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
from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QScrollArea,
    QVBoxLayout, QWidget,
)
from shiboken6 import isValid

from sigft import config as sigft_config
from sigft.app import textos_dicas
from sigft.app import ia_por_modulo
from sigft.app.idioma import marcar, t
from sigft.app_qt import atualizacao, estilo, icones, letra, nome, pasta_de_logs, propriedades, tema
from sigft.app_qt.catalogo import ACAO_CONFIGURACAO, ACAO_SUGESTOES, ACOES_DA_CONFIGURACAO, ACOES_DA_HOME, ICONE_DA_TELA, MODULOS
from sigft.app_qt.widgets import blocos, controles, dialogs, mural
from sigft.app_qt.widgets.fraco import chamada_fraca
from sigft.app_qt.widgets.module_frame import aplicar_dicas
from sigft.app_qt.widgets.painel_janela import JanelaPainel
from sigft.core import diario
from sigft.core.llm import usage as llm_usage

# A barra e a engrenagem saem de `catalogo` (2026-10-21; a engrenagem, 2026-10-22):
# as ações da Home moram num lugar só (`catalogo.ACOES_DA_HOME`, `ACAO_CONFIGURACAO`
# e `ACOES_DA_CONFIGURACAO`), de onde saem também o Ctrl+K e o `main.ACAO_NA_HOME`.
_ATUALIZACOES = next(a for a in ACOES_DA_CONFIGURACAO if a.chave == "atualizacoes")
# O texto do botão que procura versão nova (na janela Configuração desde
# 2026-10-22). Constante porque dois lugares precisam concordar: quem o põe em
# "Procurando..." e quem o devolve (`HomeView.procurar_atualizacoes`).
TEXTO_BOTAO_ATUALIZACOES = _ATUALIZACOES.texto
TEXTO_PROCURANDO = marcar("Procurando...")
# O aviso da sessão anterior no topo da Home (2026-10-26): o diário de quedas
# (`sigft/core/diario.py`) diz se a última sessão caiu ou foi encerrada de fora.
AVISO_DA_SESSAO = {
    diario.CAIU: marcar("Da última vez, o SIG-FT fechou de forma inesperada."),
    diario.ENCERRADO: marcar("Da última vez, o SIG-FT foi encerrado sem fechar a janela "
                             "(pelo Gerenciador de Tarefas ou ao desligar o computador)."),
}
TEXTO_ABRIR_REGISTRO = marcar("Abrir o registro")
TEXTO_ENTENDIDO = marcar("Entendido")
DICA_ABRIR_REGISTRO = marcar("Abre a pasta de logs, onde fica o diário do SIG-FT (diario.log).")

# A barra (`_criar_barra_de_botoes` de lá): chave, texto, variante do botão e o que
# abre. A cor de cada um é a da variante, na folha do tema. Desde 2026-10-22 só
# "Atividades do dia" e "Gastos de IA": o resto foi para a janela Configuração.
BARRA = [(a.chave, a.texto, a.variante, a.metodo) for a in ACOES_DA_HOME]
# O ícone de cada botão da barra (Lucide, `sigft/app_qt/icones.py`).
ICONE_DA_BARRA = {a.chave: a.icone for a in ACOES_DA_HOME}
# A engrenagem (2026-10-22): quadrada, só o ícone, à direita do título.
LADO_ENGRENAGEM = 36
TAMANHO_ICONE_ENGRENAGEM = 20

# As chaves do painel "Chaves de API" (o `keys_info` de lá, sem o valor padrão,
# que é sempre vazio: as chaves vêm do .env ou do api_config.json).
CHAVES_API = (
    ("GEMINI", marcar("Gemini API Key:")),
    ("GOOGLE_SEARCH", marcar("Google Search API:")),
    ("GOOGLE_CSE", marcar("Google CSE ID:")),
    ("LLAMA", marcar("LlamaCloud API:")),
    # [CP 3.2] Gateway OpenRouter (padrão) + endpoint OpenAI-compatível da
    # futura IA interna da empresa.
    ("OPENROUTER", marcar("OpenRouter API Key:")),
    ("EMPRESA_LLM_BASE_URL", marcar("IA Empresa (Base URL):")),
    ("EMPRESA_LLM_API_KEY", marcar("IA Empresa (API Key):")),
    # [2026-11-03] O webhook da Revisão no AMP saiu daqui: cada workflow do AMP tem o seu,
    # configurado na própria aba (botão Webhook…, `widgets/webhook_amp.py`).
)

# Os nomes das tarefas moram em `sigft/app/ia_por_modulo.py` (2026-11-04): a central e o
# "Configurar IA" de cada tela usam os mesmos.
ROTULOS_TAREFA_IA = ia_por_modulo.ROTULOS

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
    """O título em negrito dos painéis. O emoji da frente saiu em 2026-10-20: o
    ícone fica no botão da barra que abre o painel."""
    return _rotulo(texto, FONTE_TITULO_PAINEL)


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


def _agora() -> datetime:
    """O relógio da saudação. Função para os testes fixarem a hora."""
    return datetime.now()


class _Saudacao(blocos.RotuloElidido):
    """O título da Home: "Bom dia, <nome>" (2026-10-20). Clicar troca o nome.

    Elide à direita: um nome comprido (até `nome.LIMITE` letras, na fonte de
    32 px do título) não empurra a engrenagem (janela Configuração) nem abre rolagem
    horizontal; `text()` continua sendo a saudação inteira."""

    MODO = Qt.TextElideMode.ElideRight

    def __init__(self, ao_clicar) -> None:
        super().__init__("", objectName="titulo_home")
        # Fraca: a Home segura este título (ver `widgets/fraco.py`).
        self._ao_clicar = chamada_fraca(ao_clicar)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(t(nome.DICA_DA_SAUDACAO))

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # No soltar, como um botão: quem aperta e arrasta para fora desiste.
        if (evento.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(evento.position().toPoint())):
            self._ao_clicar()
        super().mouseReleaseEvent(evento)


class _Card(QFrame):
    def __init__(self, alvo, titulo, descricao, ao_clicar) -> None:
        super().__init__(objectName="card")
        self._alvo = alvo
        # Fraca: a Home segura o card (ver `widgets/fraco.py`).
        self._ao_clicar = chamada_fraca(ao_clicar)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        # O ícone da tela ao lado do título, na cor dele (`primaria`): o mesmo
        # do menu (`catalogo.ICONE_DA_TELA`, 2026-10-20).
        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.setSpacing(8)
        self.icone = QLabel(objectName="card_icone")
        icones.aplicar(self.icone, ICONE_DA_TELA.get(alvo, ""), papel_cor="primaria", tamanho=18)
        topo.addWidget(self.icone)
        topo.addWidget(QLabel(titulo, objectName="card_titulo"), 1)
        layout.addLayout(topo)
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
    def __init__(self, parent=None, controller=None) -> None:
        super().__init__(parent)
        self.controller = controller
        # Um painel de cada tipo por vez (chave -> JanelaPainel).
        self._janelas: dict[str, JanelaPainel] = {}
        self.entries: dict[str, QLineEdit] = {}

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

        # --- AVISO DA SESSÃO ANTERIOR --- [2026-10-26] Só quando a última sessão
        # caiu ou foi encerrada de fora; sem janela modal.
        self.aviso_sessao = self._criar_aviso_da_sessao()
        if self.aviso_sessao is not None:
            layout.addWidget(self.aviso_sessao)
            layout.addSpacing(16)

        # --- CABEÇALHO --- (pady (20, 5); (0, 20); 10; os de baixo somam)
        # [2026-10-20] O título virou a saudação ("Bom dia, <nome>"), com a
        # mesma fonte e altura do "SIG-FT" de antes (o nome do app já está na
        # barra lateral). Ver `sigft/app_qt/nome.py`.
        self._pergunta_do_nome = None
        self.label_titulo = _Saudacao(self.mudar_nome)
        self.atualizar_saudacao()
        linha_titulo = QHBoxLayout()
        linha_titulo.setSpacing(0)
        linha_titulo.addWidget(self.label_titulo, 1)
        linha_titulo.addWidget(self._criar_lampada(), 0, Qt.AlignmentFlag.AlignVCenter)
        linha_titulo.addWidget(self._criar_engrenagem(), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(linha_titulo)
        layout.addSpacing(5)
        self.label_subtitulo = QLabel(t("Sistema Integrado de Gestão de Fichas Técnicas - GE Vernova"),
                                      objectName="subtitulo_home")
        self.label_subtitulo.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        self.label_subtitulo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label_subtitulo)
        layout.addSpacing(30)
        resumo = t("Clique num módulo abaixo para abri-lo. Os botões desta barra "
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
            dica = textos_dicas.dica_da_barra(chave)
            if dica and not botao.toolTip():
                botao.setToolTip(dica)

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
    # AVISO DA SESSÃO ANTERIOR  [2026-10-26]
    # =====================================================================
    def _criar_aviso_da_sessao(self):
        """O cartão com borda de aviso, o texto e os botões "Abrir o registro" e
        "Entendido". `None` quando a sessão anterior fechou normal (ou o diário
        está desligado, ou outra instância segura o diário), ou quando o aviso já
        foi dispensado."""
        texto = AVISO_DA_SESSAO.get(diario.aviso_pendente())
        if texto is None:
            return None
        quadro = QFrame(objectName="cartao")
        quadro.setProperty("borda", "aviso")
        linha = QHBoxLayout(quadro)
        linha.setContentsMargins(14, 10, 14, 10)
        linha.setSpacing(10)
        self.lbl_aviso_sessao = blocos.rotulo(t(texto), alinhar="esquerda")
        linha.addWidget(self.lbl_aviso_sessao, 1)
        self.btn_abrir_registro = blocos.botao(t(TEXTO_ABRIR_REGISTRO), variante="secundario")
        self.btn_abrir_registro.setToolTip(t(DICA_ABRIR_REGISTRO))
        self.btn_abrir_registro.clicked.connect(self.abrir_registro)
        linha.addWidget(self.btn_abrir_registro)
        self.btn_entendido = blocos.botao(t(TEXTO_ENTENDIDO), variante="primario")
        self.btn_entendido.clicked.connect(self.dispensar_aviso_da_sessao)
        linha.addWidget(self.btn_entendido)
        return quadro

    def abrir_registro(self) -> None:
        """A pasta de logs (o `diario.log` e o `queda.log.anterior`), como o "Abrir logs"."""
        pasta_de_logs.abrir(self)

    def dispensar_aviso_da_sessao(self) -> None:
        """"Entendido": o aviso some até a próxima queda."""
        diario.dispensar_aviso()
        if _vivo(self.aviso_sessao):
            self.aviso_sessao.hide()

    # =====================================================================
    # BARRA DE BOTÕES  [2026-09-03; 2026-10-22: só atividades e gastos]
    # =====================================================================
    def _criar_barra_de_botoes(self) -> QHBoxLayout:
        barra = QHBoxLayout()
        barra.setSpacing(0)
        self.botoes_barra = {}
        for chave, texto, variante, metodo in BARRA:
            botao = self._botao_da_barra(t(texto), variante, ICONE_DA_BARRA[chave])
            # O método pela propriedade, não por `lambda` com `self`: a
            # lambda segurava a Home (ciclo; ver `widgets/fraco.py`).
            botao.setProperty("metodo", metodo)
            botao.clicked.connect(self._clicou_na_barra)
            self.botoes_barra[chave] = botao
            barra.addWidget(botao)
            barra.addSpacing(10)                        # pack(side="left", padx=(0, 10))
        barra.addStretch()
        return barra

    def _clicou_na_barra(self) -> None:
        getattr(self, propriedades.ler(self.sender(), "metodo"))()

    # =====================================================================
    # ENGRENAGEM  [2026-10-22]
    # =====================================================================
    def _criar_engrenagem(self):
        """A engrenagem: abre a janela Configuração. Botão fantasma quadrado, só
        o ícone; o nome vai na dica e no nome acessível (leitor de tela)."""
        botao = blocos.botao("", variante=ACAO_CONFIGURACAO.variante, largura=LADO_ENGRENAGEM,
                             altura=LADO_ENGRENAGEM)
        icones.aplicar(botao, ACAO_CONFIGURACAO.icone, tamanho=TAMANHO_ICONE_ENGRENAGEM)
        botao.setToolTip(t(ACAO_CONFIGURACAO.texto))
        botao.setAccessibleName(t(ACAO_CONFIGURACAO.texto))
        dialogs.sem_tecla(botao)
        botao.clicked.connect(self.abrir_configuracao)
        self.btn_configuracao = botao
        return botao

    def abrir_configuracao(self):
        """A janela Configuração (a engrenagem e o Ctrl+K); aberta, vem para a frente.
        Fechada (só escondida), dá lugar a uma nova, com o que vale agora."""
        aberta = self._trazer_para_frente("configuracao")
        if aberta is not None:
            return aberta
        velha = self._janelas.pop("configuracao", None)
        if _vivo(velha):
            velha.deleteLater()
        from sigft.app_qt.views.configuracao import JanelaConfiguracao

        janela = JanelaConfiguracao(self)
        self._janelas["configuracao"] = janela
        return janela

    def _criar_lampada(self):
        """[2026-10-30] A lâmpada, à esquerda da engrenagem e do mesmo jeito que
        ela: abre a janela Sugestões."""
        botao = blocos.botao("", variante=ACAO_SUGESTOES.variante, largura=LADO_ENGRENAGEM,
                             altura=LADO_ENGRENAGEM)
        icones.aplicar(botao, ACAO_SUGESTOES.icone, tamanho=TAMANHO_ICONE_ENGRENAGEM)
        botao.setToolTip(t(ACAO_SUGESTOES.texto))
        botao.setAccessibleName(t(ACAO_SUGESTOES.texto))
        dialogs.sem_tecla(botao)
        botao.clicked.connect(self.abrir_sugestoes)
        self.btn_sugestoes = botao
        return botao

    def abrir_sugestoes(self):
        """A janela Sugestões (a lâmpada e o Ctrl+K); uma só aberta por vez, como
        a Configuração. O texto digitado fica nela enquanto o app estiver aberto:
        fechar só esconde."""
        aberta = self._trazer_para_frente("sugestoes")
        if aberta is not None:
            return aberta
        velha = self._janelas.get("sugestoes")
        if _vivo(velha):
            velha.show()
            velha.raise_()
            velha.activateWindow()
            return velha
        from sigft.app_qt.views.sugestoes import JanelaSugestoes

        janela = JanelaSugestoes(self)
        self._janelas["sugestoes"] = janela
        return janela

    def _configuracao_viva(self):
        janela = self._janelas.get("configuracao")
        return janela if _vivo(janela) else None

    # =====================================================================
    # SAUDAÇÃO  [2026-10-20]
    # =====================================================================
    def atualizar_saudacao(self) -> None:
        """Recalcula a saudação pelo relógio e pelo nome guardado. A janela
        chama ao mostrar a Home: "Bom dia" vira "Boa tarde" sem reabrir."""
        self.label_titulo.setText(nome.saudacao(_agora(), nome.guardado()))
        # [2026-10-22] O nome pode ter mudado pela saudação: o campo "Seu nome"
        # da janela Configuração aberta acompanha.
        if (janela := self._configuracao_viva()) is not None:
            janela.mostrar_nome()

    def mudar_nome(self) -> None:
        """Clicar na saudação: a pergunta do nome, com o nome de agora no campo."""
        if self._pergunta_do_nome is not None and isValid(self._pergunta_do_nome):
            self._pergunta_do_nome.raise_()
            self._pergunta_do_nome.activateWindow()
            return
        caixa = nome.PerguntaDoNome(self)
        self._pergunta_do_nome = caixa
        caixa.finished.connect(self.atualizar_saudacao)
        caixa.open()

    @staticmethod
    def _botao_da_barra(texto: str, variante: str, icone: str):
        # height=40, font=("Roboto", 13, "bold"); a largura é a do CTkButton.
        botao = blocos.botao(texto, variante=variante, altura=estilo.ALTURA_BOTAO_BARRA,
                             tamanho_fonte=13, negrito=True, largura_minima=estilo.LARGURA_BOTAO_CTK)
        icones.aplicar(botao, icone)
        dialogs.sem_tecla(botao)
        return botao

    def escolher_tema(self, escolha: str) -> str:
        """Troca o tema do app inteiro e lembra a escolha (`tema.aplicar`). A janela
        Configuração, se existe, marca o que VALEU (gravar pode ter falhado)."""
        valeu = tema.aplicar(QApplication.instance(), escolha)
        if (janela := self._configuracao_viva()) is not None:
            janela.marcar_tema(valeu)
        return valeu

    def escolher_letra(self, escolha: str) -> None:
        """Troca a letra do app inteiro e lembra a escolha (`letra.aplicar`); o
        `letra.mudou` marca o seletor da janela Configuração."""
        letra.aplicar(QApplication.instance(), escolha)

    def procurar_atualizacoes(self, botao=None) -> None:
        """Pergunta ao GitHub agora e SEMPRE responde (ver `app_qt/atualizacao.py`).
        `botao` é o da janela Configuração, que fica em "Procurando..." até a
        resposta; o Ctrl+K chama sem botão."""
        if botao is not None:
            botao.setEnabled(False)
            botao.setText(t(TEXTO_PROCURANDO))

        def ao_terminar():
            if _vivo(botao):
                botao.setEnabled(True)
                botao.setText(t(TEXTO_BOTAO_ATUALIZACOES))

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
        return self._abrir_painel("chaves", titulo=t("Chaves de API"),
                                  montar=self.criar_area_config_api, geometria="760x520")

    def abrir_janela_ia_por_modulo(self):
        """[2026-11-04] A IA por módulo (IA Externa, IA Interna, Workflow AMP; pedido do
        Luan): é a porta de "Modelos de IA" na Configuração. [2026-11-05] O painel de
        antes (provedor, modelo padrão, modo avançado) saiu: o novo basta."""
        return self._abrir_painel("ia_por_modulo", titulo=t("Modelos de IA"),
                                  montar=self.criar_painel_ia_por_modulo, geometria="1000x600")

    def criar_painel_ia_por_modulo(self, parent) -> None:
        from sigft.app_qt.widgets import ia_do_modulo

        casca, _quadro, coluna = _painel(parent)
        self._casca_ia_por_modulo = casca
        _empilhar(coluna, _titulo_painel(t(ia_do_modulo.TITULO_CENTRAL)), cima=10, baixo=6)
        _empilhar_texto(coluna, _Texto(t(ia_do_modulo.EXPLICACAO_CENTRAL), papel="legenda",
                                       altura_linha=LINHA_TK_ROBOTO_12), baixo=8)
        self.painel_ia_por_modulo = ia_do_modulo.PainelIaDoModulo(
            self.controller, sigft_config.TAREFAS_DO_PAINEL, abrir_chaves=self.abrir_janela_chaves_api)
        self.painel_ia_por_modulo.setMinimumHeight(380)
        coluna.addWidget(self.painel_ia_por_modulo)
        coluna.addSpacing(12)

    def abrir_janela_gastos_ia(self):
        return self._abrir_painel("gastos", titulo=t("Gastos de IA"),
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
            "atividades", titulo=t("Atividades do dia"),
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
            card = _Card(alvo, t(titulo), t(descricao), self._ir)
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
        self.lbl_titulo_chaves_api = _titulo_painel(t("Configuração de Chaves API (Global)"))
        _empilhar(coluna, self.lbl_titulo_chaves_api, cima=10, baixo=10)

        # [SEGURANÇA] Sem valores padrão escritos aqui: as chaves vêm do .env ou
        # do api_config.json (ambos fora do versionamento). Os campos ficam
        # mascarados (show="*") e o valor nunca vai para o log.
        self.entries = {}
        self.rotulos_chaves_api = {}
        for key_id, texto in CHAVES_API:
            linha = _linha(coluna, cima=2, baixo=2)
            rotulo = _rotulo(t(texto), largura_minima=LARGURA_ROTULO_CHAVE)
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

        self.btn_salvar_chaves = _botao(t("Salvar Chaves"), variante="primario")
        self.btn_salvar_chaves.clicked.connect(self.salvar_chaves_api)
        _empilhar(coluna, self.btn_salvar_chaves, cima=10, baixo=10, centro=True)

    def salvar_chaves_api(self) -> None:
        # `.strip()`: uma chave colada com espaço/quebra de linha no fim vira
        # `400 API_KEY_INVALID` no Google, e a mensagem culpa a chave.
        new_keys = {k: e.text().strip() for k, e in self.entries.items()}
        self.controller.save_keys(new_keys)

        primeiro = next(iter(self.entries.values()), None)
        QMessageBox.information(self._janela_de(primeiro), t("Sucesso"),
                                t("Chaves API salvas com sucesso!\nTodos os módulos usarão as novas chaves."))

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
        self.lbl_titulo_gastos_ia = _titulo_painel(t("Gastos de IA"))
        _empilhar(coluna, self.lbl_titulo_gastos_ia, cima=10, baixo=10)

        self.lbl_gastos_ia = _Texto(t("Carregando..."), altura_linha=LINHA_TK_ROBOTO_12)
        _empilhar_texto(coluna, self.lbl_gastos_ia, baixo=10)
        self._atualizar_texto_gastos_ia()

        linha = _linha(coluna, baixo=15)
        self.btn_atualizar_gastos_ia = _botao_cinza(t("Atualizar"))
        self.btn_atualizar_gastos_ia.clicked.connect(self._atualizar_texto_gastos_ia)
        linha.addWidget(self.btn_atualizar_gastos_ia)
        linha.addSpacing(10)
        self.btn_pasta_logs_ia = _botao_cinza(t("Abrir pasta de logs"))
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
            texto = t("Não foi possível carregar os gastos de IA agora ({erro}).", erro=e)
        self.lbl_gastos_ia.definir(texto)

    def _abrir_pasta_logs_gastos_ia(self) -> None:
        """Abre `Documentos\\SIG-FT\\logs\\` no explorador, criando-a se ainda
        não existir (nenhuma tarefa de IA rodou ainda)."""
        # O mesmo ajudante do "Abrir logs" do Ctrl+K (2026-10-21). O pai só é
        # procurado se der erro.
        pasta_de_logs.abrir(
            lambda: self._janela_de(getattr(self, "frame_gastos_ia", None)))

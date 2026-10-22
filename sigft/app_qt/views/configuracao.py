"""A janela Configuração: o que se ajusta no SIG-FT, num lugar só (2026-10-22).

Abre pela engrenagem da Home (`HomeView.abrir_configuracao`) e pelo Ctrl+K
("Configuração"). Não tem regra nova: cada controle chama a MESMA função que o
controle da Home chamava até 2026-10-21 (`tema`, `letra`, `nome`,
`aviso_windows`, `updater` e os métodos da Home que abrem Chaves de API, Modelos
de IA e a busca de versão nova). Cada mudança vale e é guardada na hora: não há
"Salvar".

É uma `JanelaPainel`, como os painéis da Home, e não um `QDialog`: no Windows o
QDialog não tem o botão de minimizar. Uma só aberta por vez (a Home guarda a
referência em `_janelas["configuracao"]`) e "Fechar" no rodapé.

Os botões de escolha guardam a escolha na propriedade `escolha` e ligam a um
MÉTODO da janela, que lê `self.sender()`: `lambda` com `self` no sinal de um
filho vaza a janela, que morre antes do app (aviso do mural de 2026-10-14).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from sigft.app import idioma
from sigft.app.idioma import marcar, t
from sigft.app_qt import aviso_windows, estilo, icones, letra, nome, reinicio, tema
from sigft.app_qt.catalogo import (
    ACOES_DA_CONFIGURACAO, SECOES_DA_CONFIGURACAO, SELETOR_LETRA, SELETOR_TEMA,
)
from sigft.app_qt.widgets import blocos, controles, dialogs
from sigft.app_qt.widgets.module_frame import aplicar_dicas
from sigft.app_qt.widgets.painel_janela import JanelaPainel
from sigft.services import updater

TITULO = marcar("Configuração")
GEOMETRIA = "720x620"
# A coluna dos títulos das seções, à esquerda.
LARGURA_TITULO_SECAO = 190
ESPACO_ENTRE_SECOES = 18
LARGURA_CAMPO_NOME = 360
TEXTO_AVISOS_WINDOWS = marcar("Avisar no Windows quando uma tarefa terminar ou pedir algo")
DICA_AVISOS_WINDOWS = marcar("Com o SIG-FT atrás de outra janela, um aviso do Windows diz quando uma "
                             "tarefa termina ou quando o robô espera você (o login no portal, por exemplo).")
TEXTO_CANAL_TESTES = marcar("Receber versões de teste")
TEXTO_IDIOMA_AO_REINICIAR = marcar("O idioma muda na próxima vez que o SIG-FT abrir.")
TEXTO_REINICIAR = marcar("Reiniciar agora")
# Os botões que vieram da barra da Home, pela chave (`catalogo.ACOES_DA_CONFIGURACAO`).
ACAO = {a.chave: a for a in ACOES_DA_CONFIGURACAO}


def _sem_conteudo(_pai) -> None:
    """O `montar` da `JanelaPainel`: o conteúdo desta janela é montado depois do
    `super().__init__`, porque usa `self`."""


class JanelaConfiguracao(JanelaPainel):
    def __init__(self, home) -> None:
        super().__init__(home, titulo=t(TITULO), montar=_sem_conteudo, geometria=GEOMETRIA)
        self.home = home
        # Chave da seção -> o rótulo do título dela, na ordem de `SECOES_DA_CONFIGURACAO`.
        self.secoes: dict = {}
        quadro = QFrame(objectName="painel_home")
        grade = QGridLayout(quadro)
        grade.setContentsMargins(16, 16, 16, 16)
        grade.setHorizontalSpacing(16)
        grade.setVerticalSpacing(ESPACO_ENTRE_SECOES)
        grade.setColumnMinimumWidth(0, LARGURA_TITULO_SECAO)
        grade.setColumnStretch(1, 1)
        for linha, (chave, titulo) in enumerate(SECOES_DA_CONFIGURACAO):
            rotulo = blocos.rotulo(t(titulo), tamanho=15, negrito=True, papel="destaque",
                                   alinhar="esquerda")
            rotulo.setWordWrap(False)
            self.secoes[chave] = rotulo
            grade.addWidget(rotulo, linha, 0, Qt.AlignmentFlag.AlignTop)
            grade.addWidget(getattr(self, f"_secao_{chave}")(), linha, 1, Qt.AlignmentFlag.AlignTop)
        self._layout_conteudo.addWidget(quadro)
        # [2026-10-22] A barra só quando há o que rolar: o `JanelaPainel` a deixa
        # sempre à vista (a faixa do CTkScrollableFrame), e aqui ela aparecia
        # cheia, sem nada para rolar. Com a letra grande ela volta se precisar.
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        aplicar_dicas(self)

    # --- peças ----------------------------------------------------------------------
    @staticmethod
    def _coluna(espaco: int = 8) -> tuple[QWidget, QVBoxLayout]:
        caixa = QWidget()
        coluna = QVBoxLayout(caixa)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(espaco)
        return caixa, coluna

    @staticmethod
    def _seletor(nome_do_quadro: str) -> tuple[QFrame, QHBoxLayout]:
        """O quadro dos botões de escolha; a folha pinta o `ativo` por objectName."""
        quadro = QFrame(objectName=nome_do_quadro)
        linha = QHBoxLayout(quadro)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(4)
        return quadro, linha

    @staticmethod
    def _botao_de_escolha(texto: str, escolha: str, dica: str = ""):
        botao = blocos.botao(texto, variante="secundario", tamanho_fonte=12)
        botao.setProperty("escolha", escolha)
        if dica:
            botao.setToolTip(dica)
        dialogs.sem_tecla(botao)
        return botao

    @staticmethod
    def _botao_de_acao(chave: str):
        acao = ACAO[chave]
        botao = blocos.botao(t(acao.texto), variante=acao.variante, altura=32,
                             largura_minima=estilo.LARGURA_BOTAO_CTK)
        icones.aplicar(botao, acao.icone)
        dialogs.sem_tecla(botao)
        return botao

    # --- Aparência --------------------------------------------------------------
    def _secao_aparencia(self) -> QWidget:
        caixa, coluna = self._coluna()
        coluna.addWidget(self._seletor_tema())
        coluna.addWidget(self._seletor_letra())
        return caixa

    def _seletor_tema(self) -> QFrame:
        quadro, linha = self._seletor("seletor_tema")
        self.botoes_tema = {}
        for escolha, texto, icone, dica in SELETOR_TEMA:
            botao = self._botao_de_escolha(t(texto), escolha, t(dica))
            icones.aplicar(botao, icone, papel_cor_ativo=estilo.PAPEL_MENU_ESCOLHIDO, tamanho=16)
            botao.clicked.connect(self._clicou_tema)
            self.botoes_tema[escolha] = botao
            linha.addWidget(botao)
        linha.addStretch()
        self.marcar_tema(tema.escolhido())
        return quadro

    def _clicou_tema(self) -> None:
        # Pela Home, que aplica e marca esta janela (`HomeView.escolher_tema`).
        self.home.escolher_tema(self.sender().property("escolha"))

    def marcar_tema(self, escolha: str) -> None:
        """Marca o tema que VALEU, não o das prefs: gravar pode ter falhado."""
        for chave, botao in self.botoes_tema.items():
            estilo.definir_propriedade(botao, "ativo", chave == escolha)
            icones.reaplicar(botao)

    def _seletor_letra(self) -> QFrame:
        quadro, linha = self._seletor("seletor_letra")
        self.botoes_letra = {}
        for escolha, texto, dica in SELETOR_LETRA:
            botao = self._botao_de_escolha(t(texto), escolha, t(dica))
            botao.clicked.connect(self._clicou_letra)
            self.botoes_letra[escolha] = botao
            linha.addWidget(botao)
        linha.addStretch()
        self.marcar_letra(letra.atual())
        # A troca pode vir de fora (o Ctrl+K): o aviso marca o seletor. Método
        # ligado: o Qt desliga sozinho quando a janela morre.
        letra.mudou.connect(self.marcar_letra)
        return quadro

    def _clicou_letra(self) -> None:
        self.home.escolher_letra(self.sender().property("escolha"))

    def marcar_letra(self, escolha: str) -> None:
        for chave, botao in self.botoes_letra.items():
            estilo.definir_propriedade(botao, "ativo", chave == escolha)

    # --- Idioma -----------------------------------------------------------------
    def _secao_idioma(self) -> QWidget:
        caixa, coluna = self._coluna()
        quadro, linha = self._seletor("seletor_idioma")
        self.botoes_idioma = {}
        for codigo in idioma.IDIOMAS:
            # O nome de cada idioma no próprio idioma (`idioma.NOMES`): não se traduz.
            botao = self._botao_de_escolha(idioma.NOMES[codigo], codigo)
            botao.clicked.connect(self._clicou_idioma)
            self.botoes_idioma[codigo] = botao
            linha.addWidget(botao)
        linha.addStretch()
        coluna.addWidget(quadro)
        self.aviso_idioma = blocos.rotulo(t(TEXTO_IDIOMA_AO_REINICIAR), tamanho=12, papel="legenda",
                                          alinhar="esquerda")
        coluna.addWidget(self.aviso_idioma)
        self.btn_reiniciar = blocos.botao(t(TEXTO_REINICIAR), variante="primario", altura=32,
                                          largura_minima=estilo.LARGURA_BOTAO_CTK)
        dialogs.sem_tecla(self.btn_reiniciar)
        self.btn_reiniciar.clicked.connect(self._reiniciar)
        coluna.addWidget(self.btn_reiniciar, 0, Qt.AlignmentFlag.AlignLeft)
        self._marcar_idioma(idioma.escolhido() or idioma.atual())
        return caixa

    def _clicou_idioma(self) -> None:
        # Guardado no clique (como tema e letra): fechar pelo X também vale.
        self._marcar_idioma(idioma.guardar(self.sender().property("escolha")))

    def _marcar_idioma(self, codigo: str) -> None:
        for chave, botao in self.botoes_idioma.items():
            estilo.definir_propriedade(botao, "ativo", chave == codigo)
        # Só faz sentido reiniciar para um idioma diferente do que está valendo.
        self.btn_reiniciar.setEnabled(codigo != idioma.atual())

    def _reiniciar(self) -> None:
        reinicio.reiniciar(self.home.controller, pai=self)

    # --- Seu nome ---------------------------------------------------------------
    def _secao_nome(self) -> QWidget:
        # O nome só aparece na saudação da Home (`nome.py`): nunca vai para log.
        self.campo_nome = QLineEdit(nome.guardado())
        self.campo_nome.setMaxLength(nome.LIMITE)
        self.campo_nome.setPlaceholderText(t(nome.TITULO))
        self.campo_nome.setMaximumWidth(LARGURA_CAMPO_NOME)
        self.campo_nome.editingFinished.connect(self._guardar_nome)
        return self.campo_nome

    def _guardar_nome(self) -> None:
        """Sair do campo ou Enter: guarda (vazio tira o nome) e a Home refaz a saudação."""
        nome.guardar(self.campo_nome.text())
        # O campo passa a mostrar o que ficou guardado (aparado): é o mesmo nome
        # da saudação. O `setText` também zera o "sendo digitado" (`isModified`).
        self.campo_nome.setText(nome.guardado())
        self.home.atualizar_saudacao()

    def mostrar_nome(self) -> None:
        """O nome guardado no campo, quando ele muda por fora (a saudação da
        Home, 2026-10-22). Não atropela o que a pessoa está digitando."""
        if not self.campo_nome.isModified() and self.campo_nome.text() != nome.guardado():
            self.campo_nome.setText(nome.guardado())

    # --- Avisos -----------------------------------------------------------------
    def _secao_avisos(self) -> QWidget:
        caixa = controles.CaixaDeMarcar(t(TEXTO_AVISOS_WINDOWS), tamanho_fonte=12)
        caixa.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        caixa.setChecked(aviso_windows.ligado())
        caixa.setToolTip(t(DICA_AVISOS_WINDOWS))
        caixa.toggled.connect(aviso_windows.ligar)
        self.caixa_avisos_windows = caixa
        return caixa

    # --- Inteligência artificial ------------------------------------------------
    def _secao_ia(self) -> QWidget:
        caixa = QWidget()
        linha = QHBoxLayout(caixa)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(10)
        self.btn_modelos = self._botao_de_acao("modelos")
        self.btn_modelos.clicked.connect(self._abrir_modelos)
        self.btn_chaves = self._botao_de_acao("chaves")
        self.btn_chaves.clicked.connect(self._abrir_chaves)
        linha.addWidget(self.btn_modelos)
        linha.addWidget(self.btn_chaves)
        linha.addStretch()
        return caixa

    def _abrir_modelos(self) -> None:
        self.home.abrir_janela_modelos_ia()

    def _abrir_chaves(self) -> None:
        self.home.abrir_janela_chaves_api()

    # --- Atualizações -------------------------------------------------------------
    def _secao_atualizacoes(self) -> QWidget:
        caixa, coluna = self._coluna()
        self.caixa_canal_testes = controles.CaixaDeMarcar(t(TEXTO_CANAL_TESTES), tamanho_fonte=12)
        self.caixa_canal_testes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        try:
            ligado = updater.canal_testes_ligado()
        except Exception:  # noqa: BLE001 -- preferência é conveniência
            ligado = False
        self.caixa_canal_testes.setChecked(bool(ligado))
        self.caixa_canal_testes.toggled.connect(self._lembrar_canal_testes)
        coluna.addWidget(self.caixa_canal_testes)
        self.btn_atualizacoes = self._botao_de_acao("atualizacoes")
        self.btn_atualizacoes.clicked.connect(self._procurar_atualizacoes)
        coluna.addWidget(self.btn_atualizacoes, 0, Qt.AlignmentFlag.AlignLeft)
        return caixa

    @staticmethod
    def _lembrar_canal_testes(ligado: bool) -> None:
        try:
            updater.ligar_canal_testes(bool(ligado))
        except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar o clique
            pass

    def _procurar_atualizacoes(self) -> None:
        self.home.procurar_atualizacoes(self.btn_atualizacoes)

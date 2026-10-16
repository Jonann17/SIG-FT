"""O que as telas "Upload de Condições" e "Upload Características Técnicas" têm em comum.

As duas telas antigas (`sigft/app/views/upload_conditions.py` e
`upload_tech_specs.py`) são quase gêmeas: quadro "Configuração Global" com o
_STATUS_PMIB e o interruptor "Forçar processamento", abas IA × Robô Web, a fila
de fichas numa área rolável, a linha INICIAR/PARAR e a aba do robô com os três
botões. Lá cada uma tinha a sua cópia; aqui a montagem mora em `TelaDeUpload`
e cada tela diz só os textos (atributos de classe) e o que é dela (a aba 1 da
Tech Specs tem o quadro "Referência para IA"; os workers são de cada uma).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QSizePolicy, QVBoxLayout

from sigft.app import theme
from sigft.app_qt import estilo
from sigft.app_qt.widgets import abas, blocos, controles, pickers, revisao_portal
from sigft.app_qt.widgets.module_frame import ModuleFrame

ABA_WEB = "Robô Web (Preencher Portal)"
URL_PORTAL = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"
TEXTO_NAO_SELECIONADO = "Não selecionado"
# O tk.Listbox da fila tem as 10 linhas padrão: 200 px medidos na tela antiga.
ALTURA_LISTA_FILA = 200
# Um robô por vez: o "Continuar" do fim da IA (ou uma seleção antiga
# confirmada agora) não sobe um segundo navegador com o primeiro rodando.
MSG_ROBO_OCUPADO = ("O robô já está preenchendo uma fila no portal. Espere ele terminar "
                    "(ou use PARAR ROBÔ WEB) antes de iniciar outra.")


def reabilitar(*botoes_e_estados) -> None:
    """`(botão, ligado)`: a tela pode ter sido fechada antes de a tarefa acabar."""
    for botao, ligado in botoes_e_estados:
        try:
            botao.setEnabled(ligado)
        except RuntimeError:
            pass  # widget já destruído pelo Qt


class TelaDeUpload(ModuleFrame):
    """Base das duas telas de upload. A subclasse define os textos abaixo,
    `_build_tab1` (que chama `_area_da_aba_ia`, `_fila_de_fichas` e
    `_linha_acoes_ia`) e os comandos `_sel_status`, `_start_ia_process`,
    `_stop_ia_process`, `_pre_start_web`, `_start_web_from_file` e
    `_stop_web_process`."""

    ABA_IA = ""
    TEXTO_CONFIG = ""
    # Margens do quadro global (padx=15 e os pady do título e da linha de lá).
    MARGENS_CONFIG = (15, 10, 15, 10)
    TEXTO_INTERRUPTOR = ""
    TEXTO_WEB = ""
    TEXTO_CARREGAR = ""

    # Liga no `_inicio_do_robo` e desliga no `_fim_do_robo`, os dois na thread
    # da interface. Não dá para olhar o PARAR: ele desliga no clique, com o
    # robô ainda fechando o ciclo.
    _robo_ativo = False

    def _chave(self) -> str:
        return self.controller.get_key("GEMINI") if self.controller is not None else ""

    # --- um robô por vez ----------------------------------------------------------
    def _robo_ocupado(self) -> bool:
        """Com um robô já rodando, diz no console por que nada começa."""
        if self._robo_ativo:
            self.log(MSG_ROBO_OCUPADO)
            return True
        return False

    # --- revisão antes do portal (R2) ---------------------------------------------
    def _revisar_antes_do_portal(self, dados, conferir):
        """No clique, antes de abrir o navegador: confere `dados` com as regras
        do portal (`conferir`, de `sigft.core.pmib_regras`) e devolve a lista que
        segue para o robô -- a MESMA, sem problema ou com "Seguir com todas";
        sem as fichas com erro, se a pessoa pediu; `None` para não abrir o robô.
        Só filtra: nenhuma ficha é alterada."""
        seguem = revisao_portal.conferir_antes_do_portal(self, conferir(dados), len(dados), self.log)
        if seguem is None or len(seguem) == len(dados):
            return None if seguem is None else dados
        return [dados[i] for i in seguem]

    def _inicio_do_robo(self) -> None:
        self._robo_ativo = True
        reabilitar((self.btn_web_mem, False), (self.btn_web_file, False), (self.btn_parar_web, True))

    def _fim_do_robo(self) -> None:
        """Na thread da interface, quando o worker do robô acaba (bem ou mal)."""
        self._robo_ativo = False
        reabilitar((self.btn_web_mem, True), (self.btn_web_file, True), (self.btn_parar_web, False))

    # --- montagem -------------------------------------------------------------
    def _build_ui(self) -> None:
        # Espaços do `pack` de lá; o pady de dois vizinhos SOMA no Tk.
        self.content_layout.setSpacing(0)
        self.content_layout.addSpacing(10)              # quadro global: pady=10
        self._quadro_global()
        self.content_layout.addSpacing(20)              # quadro (…, 10) + abas (10, …)
        self.tabview = abas.Abas(cor_fundo="#2B2B2B", cor_barra="#161616",
                                 cor_selecionada=theme.COLORS["primary"],
                                 cor_selecionada_hover=theme.COLORS["primary_hover"])
        self.content_layout.addWidget(self.tabview, 1)
        self.content_layout.addSpacing(10)              # abas: pady=(…, 10)
        self._build_tab1(self.tabview.add(self.ABA_IA).layout())
        self._build_tab2(self.tabview.add(ABA_WEB).layout())

    def _linha_arquivo(self, texto_botao, ao_clicar):
        """Botão cinza de 200 + "Não selecionado" cinza (padx=10), à esquerda."""
        botao = blocos.botao(texto_botao, variante="cinza", largura=200, altura=28, tamanho_fonte=12)
        botao.clicked.connect(ao_clicar)
        # Elidido: um nome comprido não alarga a tela (passava de 1280 para 1682 px).
        rotulo = blocos.rotulo(TEXTO_NAO_SELECIONADO, cor=estilo.cinza_tk("gray"), alinhar="esquerda",
                               elidir=True)
        linha = QHBoxLayout()
        linha.setSpacing(0)
        linha.addWidget(botao)
        linha.addSpacing(10)
        linha.addWidget(rotulo)
        linha.addStretch()
        return linha, botao, rotulo

    def _quadro_global(self) -> None:
        # O _STATUS_PMIB é usado na IA e no robô: fica no quadro de cima.
        corpo = blocos.cartao(self.content_layout)
        corpo.setSpacing(0)
        corpo.setContentsMargins(*self.MARGENS_CONFIG)
        self.rotulo_config = blocos.rotulo(self.TEXTO_CONFIG, tamanho=14, negrito=True,
                                           cor=theme.COLORS["accent"], alinhar="esquerda")
        self.rotulo_config.setWordWrap(False)
        corpo.addWidget(self.rotulo_config)
        corpo.addSpacing(10)                            # título + linha (5+5 ou 0+10 lá)
        linha, self.btn_status, self.lbl_status_status = self._linha_arquivo(
            "Selecionar _STATUS_PMIB", self._sel_status)
        self.switch_completos = controles.Interruptor(self.TEXTO_INTERRUPTOR,
                                                      cor_ligado=theme.COLORS["primary"])
        linha.addWidget(self.switch_completos)
        linha.addSpacing(10)                            # interruptor: pack(side="right", padx=10)
        corpo.addLayout(linha)

    @staticmethod
    def _area_da_aba_ia(aba: QVBoxLayout) -> QVBoxLayout:
        """O CTkScrollableFrame transparente da aba 1; devolve o layout de dentro.

        Com a barra SEMPRE à vista, como lá: na Condições, que não tem o que
        rolar, o cartão das fichas saía 16 px mais largo que os 868 da interface antiga. E o
        conteúdo é CORTADO 6 px antes da borda da aba: sem o recorte, o topo dos
        botões aparecia na beirada de baixo.
        """
        _area, rolavel = blocos.area_rolavel(aba, barra_sempre_visivel=True)
        return rolavel

    @staticmethod
    def _cartao_na_aba(rolavel, margens) -> QVBoxLayout:
        """Quadro #2B2B2B com padx=10 dentro da área rolável."""
        recuo = QVBoxLayout()
        recuo.setContentsMargins(10, 0, 10, 0)
        rolavel.addLayout(recuo)
        corpo = blocos.cartao(recuo)
        corpo.setSpacing(0)
        corpo.setContentsMargins(*margens)
        return corpo

    def _fila_de_fichas(self, corpo, **kw) -> None:
        """O FileQueueList (as duas cópias idênticas de lá): contador, 5 px, fila."""
        self.fila_fichas = pickers.FileQueueList(categoria="excel", titulo_dialogo="Selecione as Fichas PMIB",
                                                 ao_mudar=self._logar_mudanca_na_fila, **kw)
        self.fila_fichas.listbox.setFixedHeight(ALTURA_LISTA_FILA)
        # Lá a área rolável não estica o que tem dentro: a fila fica com a
        # altura natural (10 linhas), não com a sobra da aba.
        self.fila_fichas.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        corpo.addWidget(self.fila_fichas.label_contador)
        corpo.addSpacing(5)                             # contador (…, 0) + fila (5, …)
        corpo.addWidget(self.fila_fichas)

    def _linha_acoes_ia(self) -> QHBoxLayout:
        """INICIAR (pack expand=True: centrado no que sobra) e PARAR encostado à
        direita; os dois com padx=5, dentro do padx=10 da linha."""
        # width=200 lá, mas o CTkButton cresce até caber o texto (202 na interface antiga).
        self.btn_ia = blocos.botao("INICIAR PROCESSAMENTO IA", largura_minima=200, altura=40,
                                   tamanho_fonte=13, negrito=True, cor_fundo=theme.COLORS["primary"])
        self.btn_ia.clicked.connect(self._start_ia_process)
        self.btn_parar_ia = blocos.botao("PARAR", largura=100, altura=40, tamanho_fonte=13, negrito=True,
                                         cor_fundo=theme.COLORS["danger"])
        self.btn_parar_ia.setEnabled(False)
        self.btn_parar_ia.clicked.connect(self._stop_ia_process)
        linha = QHBoxLayout()
        linha.setContentsMargins(15, 0, 15, 0)
        linha.setSpacing(0)
        linha.addStretch()
        linha.addWidget(self.btn_ia)
        linha.addStretch()
        linha.addSpacing(10)
        linha.addWidget(self.btn_parar_ia)
        return linha

    def _build_tab2(self, aba: QVBoxLayout) -> None:
        aba.addSpacing(20)                              # texto: pady=20
        self.rotulo_web = blocos.rotulo(self.TEXTO_WEB, tamanho=14, cor=controles.COR_TEXTO_CTK)
        aba.addWidget(self.rotulo_web)
        self.btn_web_mem = blocos.botao("Usar Dados Recém Processados (Memória)", variante="primario",
                                        largura=350, altura=40, tamanho_fonte=13, negrito=True)
        self.btn_web_mem.clicked.connect(lambda: self._pre_start_web(self.dados_em_memoria))
        self.btn_web_file = blocos.botao(self.TEXTO_CARREGAR, variante="cinza",
                                         largura=350, altura=40, tamanho_fonte=13, negrito=True)
        self.btn_web_file.clicked.connect(self._start_web_from_file)
        # fg_color danger sem hover_color lá: o hover é o do tema.
        self.btn_parar_web = blocos.botao("PARAR ROBÔ WEB", largura=350, altura=40, tamanho_fonte=13,
                                          negrito=True, cor_fundo=theme.COLORS["danger"])
        self.btn_parar_web.setEnabled(False)
        self.btn_parar_web.clicked.connect(self._stop_web_process)
        # texto (…, 20) + memória (10, …); memória (…, 10) + arquivo (10, …);
        # arquivo (…, 10) + parar (20, …).
        for espaco, b in ((30, self.btn_web_mem), (20, self.btn_web_file), (30, self.btn_parar_web)):
            aba.addSpacing(espaco)
            aba.addWidget(b, alignment=Qt.AlignmentFlag.AlignHCenter)
        aba.addSpacing(10)                              # parar: pady=(…, 10)
        aba.addStretch()

    # --- comum aos comandos ------------------------------------------------------
    @property
    def lista_fichas_paths(self) -> list[str]:
        """Os caminhos na fila (a fila é a dona deles)."""
        return self.fila_fichas.arquivos

    def _confirmar(self, mensagem: str) -> bool:
        """O askyesno "Confirmar" dos botões PARAR (Sim é o padrão, como no Tk)."""
        resposta = QMessageBox.question(self, "Confirmar", mensagem,
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.Yes)
        return resposta == QMessageBox.StandardButton.Yes

    def _perguntar_se_continua(self) -> bool:
        """Depois de salvar: pular para a aba 2 e iniciar o robô? Com um robô já
        rodando, nem pergunta: o Sim não teria como ser atendido."""
        if self._robo_ocupado():
            return False
        resposta = QMessageBox.question(
            self, "Continuar", "Dados salvos! Deseja pular para a Aba 2 e iniciar o Robô Web agora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        return resposta == QMessageBox.StandardButton.Yes

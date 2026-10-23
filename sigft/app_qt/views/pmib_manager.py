"""Tela "Gestão de Sobressalentes" (PMIB Manager) na interface Qt.

Mesma tela da interface antiga (`sigft/app/views/pmib_manager.py`, removida em 2026-10-15): varre a Pasta Raiz, cruza
com a base do Aconex e a planilha de mapeamento e mantém os `_STATUS_PMIB` em
dia; gera o painel HTML e aplica as autorizações de entrega de Itaipu.

O que muda é só COMO os workers falam com a tela: lá eram `self.after(0, ...)`
espalhados (e um esquecido era widget tocado fora da thread); aqui o log vai
pelo console (seguro de qualquer thread), a barra de progresso e os botões por
`interface.na_interface`, as caixas de mensagem por `avisar` e o popup das
listas novas por `_abrir_e_esperar` -- o worker espera num `Event`.
"""
from __future__ import annotations

import os
import pathlib
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMessageBox, QVBoxLayout

from sigft.app.idioma import marcar, t
from sigft.app.textos_dialogos import MSG_LOGIN_CONFERIR_AUTORIZACOES, texto_dos_avisos
from sigft.app_qt import file_dialogs, interface
from sigft.app_qt.widgets import blocos, controles, dialogs
from sigft.app_qt.widgets.arrastar import Arrastavel
from sigft.app_qt.widgets.module_frame import MARGEM_DA_TELA, ModuleFrame
from sigft.core import prefs
from sigft.core.excel import travas
# [2026-09-03] Chave sob a qual o caminho do mapeamento fica lembrado --
# a Home lê por ela para montar o mural de atividades.
from sigft.core.prefs import CHAVE_MAPEAMENTO

# [2026-10-05, T7] A caixa "Gerar painel ao terminar", lembrada entre aberturas.
OPCAO_GERAR_PAINEL = "pmib_manager.gerar_painel"

TEXTO_NENHUM_ARQUIVO = marcar("Nenhum arquivo selecionado")

# Os botões de arquivo pedem width=280, mas o CTkButton CRESCE até caber o
# texto com 7 px de cada lado (medido: 272 px de texto -> 286): é o
# `largura_minima` do `blocos.botao`.
LARGURA_BOTAO_ARQUIVO = 280
# A descrição das autorizações quebra em 720 px (wraplength) e ocupa duas
# linhas de 17 px do Tk (medido: 34). O QLabel tem a linha mais baixa.
LARGURA_QUEBRA_DESCRICAO = 720
ALTURA_DESCRICAO_CTK = 34
# [2026-10-14] A descrição do CONFERIR NO PORTAL quebra em 480 px, como o
# wraplength da tela antiga.
LARGURA_QUEBRA_PORTAL = 480


def _rotulo_status():
    """O "Nenhum arquivo selecionado" em legenda ao lado de cada botão de arquivo. É
    um `blocos.RotuloElidido`: um nome comprido não alarga a tela."""
    return blocos.rotulo(t(TEXTO_NENHUM_ARQUIVO), papel="legenda", alinhar="esquerda",
                         elidir=True)


class NovasListasDialog(QDialog):
    """"Novas Listas Encontradas": uma caixa de marcar por lista nova, todas
    marcadas; Marcar/Desmarcar Todas; Confirmar × Ignorar.

    `itens`: `(índice no DataFrame, texto)`. A decisão volta em
    `resultado["indices"]`: a lista dos marcados (Confirmar) ou `None`
    (Ignorar, "X" ou Esc -- como lá, fechar a janela é ignorar todas).
    Modal (o `grab_set` de lá).
    """

    def __init__(self, parent=None, *, itens, evento_espera, resultado: dict) -> None:
        super().__init__(parent)
        self._evento, self._resultado = evento_espera, resultado
        self._decidido = False
        self.setWindowTitle(t("Novas Listas Encontradas"))
        self.resize(750, 550)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        # Espaços do `pack` de lá; o pady de dois vizinhos SOMA no Tk.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(0)
        layout.addSpacing(15)                           # título: pady=(15, …)
        self.rotulo_titulo = blocos.rotulo(t("Novas Listas de Sobressalentes Encontradas na base de dados:"),
                                           tamanho=16, negrito=True, papel="destaque")
        layout.addWidget(self.rotulo_titulo)
        layout.addSpacing(5)                            # título (…, 5) + instrução (0, …)
        self.rotulo_instrucao = blocos.rotulo(
            t("Selecione abaixo quais você deseja adicionar à Planilha de Mapeamento."),
            papel="legenda")
        layout.addWidget(self.rotulo_instrucao)
        layout.addSpacing(15)                           # instrução (…, 10) + lista (5, …)

        self.area, lista = blocos.area_rolavel(fundo="cartao")
        self.caixas: dict = {}
        for indice, texto in itens:
            caixa = controles.CaixaDeMarcar(texto, tamanho_fonte=12)
            caixa.setChecked(True)  # começam todas marcadas
            caixa.setContentsMargins(0, 0, 0, 0)
            lista.addSpacing(6)                         # cada caixa: padx=10, pady=6
            linha = QHBoxLayout()
            linha.setContentsMargins(10, 0, 10, 0)
            linha.addWidget(caixa)
            linha.addStretch()
            lista.addLayout(linha)
            lista.addSpacing(6)
            self.caixas[indice] = caixa
        layout.addWidget(self.area, 1)
        layout.addSpacing(20)                           # lista (…, 5) + botões (15, …)

        # Fonte padrão do CTkButton (13) e a folga de texto dele: com a da folha
        # do app, "Ignorar (Não Adicionar)" não cabe nos 150.
        self.botao_marcar = blocos.botao(t("Marcar Todas"), largura_minima=120, variante="cinza", tamanho_fonte=13)
        self.botao_desmarcar = blocos.botao(t("Desmarcar Todas"), largura_minima=120, variante="cinza", tamanho_fonte=13)
        self.botao_confirmar = blocos.botao(t("Confirmar Seleção"), largura_minima=150, variante="primario",
                                            tamanho_fonte=13)
        # O cinza escrito à mão na tela antiga: a variante secundária.
        self.botao_ignorar = blocos.botao(t("Ignorar (Não Adicionar)"), largura_minima=150, tamanho_fonte=13,
                                          variante="secundario")
        # Ela segura o worker: nenhuma tecla aperta um botão (Enter ou Espaço
        # não confirmam nem ignoram as listas no lugar da pessoa).
        for b in (self.botao_marcar, self.botao_desmarcar, self.botao_confirmar, self.botao_ignorar):
            dialogs.sem_tecla(b)
        self.botao_marcar.clicked.connect(self.marcar_todas)
        self.botao_desmarcar.clicked.connect(self.desmarcar_todas)
        self.botao_confirmar.clicked.connect(self.confirmar)
        self.botao_ignorar.clicked.connect(self.ignorar)
        # Esquerda: as de massa; direita: Confirmar encostado, Ignorar antes dele
        # (pack side="right" na ordem Confirmar, Ignorar). Cada um com padx=5.
        botoes = QHBoxLayout()
        botoes.setContentsMargins(5, 0, 5, 0)
        botoes.setSpacing(10)
        botoes.addWidget(self.botao_marcar)
        botoes.addWidget(self.botao_desmarcar)
        botoes.addStretch()
        botoes.addWidget(self.botao_ignorar)
        botoes.addWidget(self.botao_confirmar)
        layout.addLayout(botoes)
        layout.addSpacing(15)                           # botões: pady=(…, 15)

    def marcar_todas(self) -> None:
        for caixa in self.caixas.values():
            caixa.setChecked(True)

    def desmarcar_todas(self) -> None:
        for caixa in self.caixas.values():
            caixa.setChecked(False)

    def _responder(self, indices) -> None:
        self._decidido = True
        self._resultado["indices"] = indices
        self._evento.set()

    def confirmar(self) -> None:
        self._responder([i for i, caixa in self.caixas.items() if caixa.isChecked()])
        self.accept()

    def ignorar(self) -> None:
        self._responder(None)
        self.reject()

    def reject(self) -> None:
        """Esc chega aqui sem passar pelo `closeEvent`: também solta o worker."""
        if not self._decidido:
            self._responder(None)
        super().reject()

    def closeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if not self._decidido:
            self._responder(None)
        super().closeEvent(evento)


class ModuloPMIBManager(ModuleFrame):
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_api", "pmib_manager.api", (".xlsx", ".xls")),
        Arrastavel("btn_master", "pmib_manager.master", (".xlsx", ".xls")),
        Arrastavel("btn_autorizados", "pmib_manager.autorizados", (".xlsx",)),
    )
    def __init__(self, parent=None, controller=None) -> None:
        # Os caminhos escolhidos (os StringVar de lá). A Pasta Raiz é o campo.
        self.path_api = self.path_master = self.path_autorizados = ""
        super().__init__(parent, controller, titulo=t("Gestão de Sobressalentes"),
                         peso_conteudo=0, altura_console=None, com_progresso=True)
        # Lá a tela não é o ModuleFrame: header pady=10, conteúdo pady=5,
        # barra pady=5 e console pady=(5, 20), dentro do padx/pady=20 do
        # `show_frame`. Os pady vizinhos SOMAM: 15 entre header e conteúdo,
        # 10 dos dois lados da barra, 20 + 20 embaixo.
        raiz = self.layout()
        raiz.setContentsMargins(MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10,
                                MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 20)
        raiz.setSpacing(0)
        raiz.insertSpacing(1, 15)                       # header (…, 10) + conteúdo (5, …)
        raiz.insertSpacing(3, 10)                       # conteúdo (…, 5) + barra (5, …)
        raiz.insertSpacing(5, 10)                       # barra (…, 5) + console (5, …)
        # CTkProgressBar(width=600, height=12, progress_color=primary), centrada.
        blocos.barra_progresso(barra=self.progress_bar, largura=600, altura=12)
        raiz.setAlignment(self.progress_bar, Qt.AlignmentFlag.AlignHCenter)
        self._definir_progresso(0)

    # --- montagem -------------------------------------------------------------
    def _build_ui(self) -> None:
        self._rotulos = r = {}
        # Os dois quadros: pady=10 no primeiro e (0, 10) no segundo.
        self.content_layout.setSpacing(0)
        self.content_layout.addSpacing(10)
        self._quadro_gestao(r)
        self.content_layout.addSpacing(10)
        self._quadro_autorizacoes(r)
        self.content_layout.addSpacing(10)

    def _cartao(self):
        corpo = blocos.cartao(self.content_layout)
        corpo.setSpacing(0)
        corpo.setContentsMargins(15, 15, 15, 15)        # padx=15; título pady=(15, …); fim (…, 15)
        return corpo

    def _quadro_gestao(self, r) -> None:
        corpo = self._cartao()
        r["config"] = blocos.rotulo(t("Configuração de Gestão de Fichas PMIB"), tamanho=16, negrito=True,
                                    papel="destaque", alinhar="esquerda")
        corpo.addWidget(r["config"])
        corpo.addSpacing(13)                            # título (…, 5) + linha (8, …)

        # 1. Histórico do Aconex (botão + rótulo)
        self.btn_api = blocos.botao(t("1. Selecionar Histórico Aconex DocManager (.xlsx)"),
                                    largura_minima=LARGURA_BOTAO_ARQUIVO, variante="cinza", tamanho_fonte=12)
        self.btn_api.clicked.connect(self._sel_api)
        self.lbl_api_status = _rotulo_status()
        corpo.addLayout(self._linha_arquivo(self.btn_api, self.lbl_api_status))
        corpo.addSpacing(16)                            # linha (…, 8) + linha (8, …)

        # 2. Pasta Raiz (rótulo + campo + Buscar)
        linha = QHBoxLayout()
        linha.setSpacing(0)
        r["raiz"] = blocos.rotulo(t("2. Pasta Raiz (Arquivos _STATUS_PMIB):"),
                                  alinhar="esquerda")
        r["raiz"].setWordWrap(False)
        r["raiz"].setFixedWidth(280)
        linha.addWidget(r["raiz"])
        linha.addSpacing(5)                             # campo: padx=5
        self.entry_root = QLineEdit()  # o visual (28 px, cores) é o do CTkEntry, na folha do app
        self.entry_root.setFixedWidth(300)
        linha.addWidget(self.entry_root)
        linha.addSpacing(5)
        self.btn_buscar = blocos.botao(t("Buscar"), largura=80)
        self.btn_buscar.clicked.connect(self._sel_root)
        linha.addWidget(self.btn_buscar)
        linha.addStretch()
        corpo.addLayout(linha)
        corpo.addSpacing(16)

        # 3. Planilha de mapeamento (botão + rótulo)
        self.btn_master = blocos.botao(t("3. Selecionar Mapeamento Sobressalentes (.xlsx)"),
                                       largura_minima=LARGURA_BOTAO_ARQUIVO, variante="cinza",
                                       tamanho_fonte=12)
        self.btn_master.clicked.connect(self._sel_master)
        self.lbl_master_status = _rotulo_status()
        corpo.addLayout(self._linha_arquivo(self.btn_master, self.lbl_master_status))
        corpo.addSpacing(28)                            # linha (…, 8) + iniciar (20, …)

        self.btn_run = blocos.botao(t("INICIAR PROCESSO DE GESTÃO"), variante="primario", largura=350,
                                    altura=50, tamanho_fonte=14, negrito=True,)
        self.btn_run.clicked.connect(self.iniciar_gestao)
        corpo.addWidget(self.btn_run, alignment=Qt.AlignmentFlag.AlignHCenter)
        corpo.addSpacing(8)                             # iniciar (…, 8) + painel (0, …)

        # [2026-10-05, T7] Painel HTML: a foto do dia para quem não tem o Power
        # BI (que continua sendo o painel oficial). Gerado DEPOIS da gravação
        # dos `_STATUS_PMIB`, para mostrar o que acabou de ser gravado.
        try:
            gerar_por_padrao = prefs.get_opcao(OPCAO_GERAR_PAINEL, True)
        except Exception:  # noqa: BLE001 -- preferência é conveniência: nunca impede a tela de abrir
            gerar_por_padrao = True
        self.caixa_gerar_painel = controles.CaixaDeMarcar(t("Gerar painel ao terminar"), tamanho_fonte=12)
        self.caixa_gerar_painel.setChecked(bool(gerar_por_padrao))
        self.caixa_gerar_painel.toggled.connect(self._lembrar_gerar_painel)
        self.btn_painel = blocos.botao(t("Gerar painel"), largura_minima=160, variante="cinza", tamanho_fonte=12)
        self.btn_painel.clicked.connect(self.gerar_painel)
        # Lá o quadro é `pack` sem `fill` (centrado); caixa e botão com padx=10.
        linha = QHBoxLayout()
        linha.setSpacing(0)
        linha.addStretch()
        linha.addWidget(self.caixa_gerar_painel)
        linha.addSpacing(20)
        linha.addWidget(self.btn_painel)
        linha.addStretch()
        corpo.addLayout(linha)

    def _quadro_autorizacoes(self, r) -> None:
        # [2026-10-05, T4] Autorizações de entrega de Itaipu: o export que
        # Itaipu manda vira AUTORIZADO nos `_STATUS_PMIB` da Pasta Raiz (era o
        # script `apto_para_entrega_att.py`, com os caminhos fixos no código).
        corpo = self._cartao()
        r["autorizacoes"] = blocos.rotulo(t("Autorizações de entrega de Itaipu"), tamanho=16, negrito=True,
                                          papel="destaque", alinhar="esquerda")
        corpo.addWidget(r["autorizacoes"])
        r["descricao_aut"] = blocos.rotulo(
            t("Grava AUTORIZADO nos _STATUS_PMIB da Pasta Raiz (passo 2) para cada PMIB do "
              "export de Itaipu (sobressalentes_autorizados_AAAAMMDDhhmm.xlsx)."),
            papel="legenda", alinhar="esquerda")
        r["descricao_aut"].setMaximumWidth(LARGURA_QUEBRA_DESCRICAO)
        r["descricao_aut"].setMinimumHeight(ALTURA_DESCRICAO_CTK)
        corpo.addWidget(r["descricao_aut"])
        corpo.addSpacing(8)                             # linha: pady=(8, 15)

        self.btn_autorizados = blocos.botao(t("4. Selecionar export de autorizados (.xlsx)"),
                                            largura_minima=LARGURA_BOTAO_ARQUIVO, variante="cinza",
                                            tamanho_fonte=12)
        self.btn_autorizados.clicked.connect(self._sel_autorizados)
        self.lbl_autorizados = _rotulo_status()
        linha = self._linha_arquivo(self.btn_autorizados, self.lbl_autorizados)
        self.btn_aplicar = blocos.botao(t("APLICAR AUTORIZAÇÕES"), variante="primario", largura=200,
                                        tamanho_fonte=12, negrito=True)
        self.btn_aplicar.clicked.connect(self.aplicar_autorizacoes)
        linha.addWidget(self.btn_aplicar)               # pack(side="right")
        corpo.addLayout(linha)

        # [2026-10-14] Ou direto no portal, sem esperar o export: o robô abre
        # cada ficha FÍSICA E DOCUMENTAL ainda sem AUTORIZADO e lê o código SAP
        # de recebimento (`services/autorizacao_portal.py`). O mesmo botão da
        # tela antiga.
        corpo.addSpacing(15)                            # o pady de baixo da linha do export
        linha_portal = QHBoxLayout()
        linha_portal.setSpacing(0)
        r["descricao_portal"] = blocos.rotulo(
            t("Ou confira no portal: o SIG-FT abre cada ficha física ainda sem AUTORIZADO e lê o "
              "código SAP de recebimento. Precisa do login no PMIB."),
            papel="legenda", alinhar="esquerda")
        # O texto é mais longo que 480 px, então o CTkLabel ocupa os 480 inteiros;
        # o QLabel com quebra prefere a metade disso se ninguém fixar.
        r["descricao_portal"].setFixedWidth(LARGURA_QUEBRA_PORTAL)
        r["descricao_portal"].setMinimumHeight(ALTURA_DESCRICAO_CTK)    # duas linhas do Tk
        linha_portal.addWidget(r["descricao_portal"])    # pack(side="left")
        linha_portal.addStretch()
        self.btn_conferir = blocos.botao(t("CONFERIR NO PORTAL"), variante="primario", largura=200,
                                         tamanho_fonte=12, negrito=True)
        self.btn_conferir.clicked.connect(self.conferir_no_portal)
        linha_portal.addWidget(self.btn_conferir)        # pack(side="right")
        corpo.addLayout(linha_portal)                    # pady=(0, 15): a margem do cartão

    @staticmethod
    def _linha_arquivo(botao, rotulo) -> QHBoxLayout:
        """Botão + rótulo de status (padx=15), encostados à esquerda."""
        linha = QHBoxLayout()
        linha.setSpacing(0)
        linha.addWidget(botao)
        linha.addSpacing(15)
        linha.addWidget(rotulo)
        linha.addStretch()
        return linha

    # --- seletores ------------------------------------------------------------
    def _sel_api(self) -> None:
        f = file_dialogs.ask_open_file("pmib_manager.api", "excel", titulo=t("Selecione a Base de Dados API"),
                                       filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_api = f
            blocos.marcar_arquivo_escolhido(self.btn_api, self.lbl_api_status, f)

    def _sel_root(self) -> None:
        pasta = file_dialogs.ask_directory("pmib_manager.pasta_raiz", "pasta", titulo=t("Selecione a Pasta Raiz"))
        # Lá o campo recebia o "" do cancelar e apagava o caminho já escolhido.
        if pasta:
            self.entry_root.setText(pasta)

    def _sel_master(self) -> None:
        f = file_dialogs.ask_open_file("pmib_manager.master", "excel", titulo=t("Selecione a Planilha Mestra"),
                                       filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_master = f
            blocos.marcar_arquivo_escolhido(self.btn_master, self.lbl_master_status, f)
            # [2026-09-03] Guarda o ARQUIVO (não só a pasta) para o mural de
            # atividades da Home poder ler o mapeamento sem pedir nada.
            try:
                prefs.remember_file(CHAVE_MAPEAMENTO, f)
            except Exception:  # noqa: BLE001 -- lembrar é conveniência; não atrapalha a seleção
                pass

    def _sel_autorizados(self) -> None:
        f = file_dialogs.ask_open_file("pmib_manager.autorizados", "excel",
                                       titulo=t("Selecione o export de autorizados de Itaipu"),
                                       filetypes=[("Excel", "*.xlsx")])
        if f:
            self.path_autorizados = f
            blocos.marcar_arquivo_escolhido(self.btn_autorizados, self.lbl_autorizados, f)

    def _lembrar_gerar_painel(self, ligado) -> None:
        try:
            prefs.set_opcao(OPCAO_GERAR_PAINEL, bool(ligado))
        except Exception:  # noqa: BLE001 -- lembrar é conveniência; não pode atrapalhar o clique
            pass

    # --- botões e barra (só na thread da interface) ---------------------------
    def _travar_botoes(self, travar) -> None:
        for botao in (self.btn_run, self.btn_aplicar, self.btn_conferir, self.btn_painel):
            try:
                botao.setEnabled(not travar)
            except RuntimeError:
                pass  # tela fechada antes de a tarefa acabar

    def _definir_progresso(self, fracao) -> None:
        try:
            blocos.definir_progresso(self.progress_bar, fracao)
        except RuntimeError:
            pass  # tela fechada antes de a tarefa acabar

    def _progresso(self, fracao) -> None:
        """Do worker: a barra só muda na thread da interface."""
        interface.na_interface(self._definir_progresso, fracao)

    def _destravar(self) -> None:
        interface.na_interface(self._travar_botoes, False)

    # --- painel ---------------------------------------------------------------
    def gerar_painel(self) -> None:
        root_folder = self.entry_root.text()
        master_path = self.path_master
        if not root_folder:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a Pasta Raiz (Passo 2)."))
            return
        if not master_path:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a Planilha de mapeamento (Passo 3)."))
            return
        self._travar_botoes(True)
        self.iniciar_tarefa(self._tarefa_painel, root_folder, master_path)

    def _tarefa_painel(self, root_folder, master_path) -> None:
        try:
            self._gerar_painel_e_abrir(root_folder, master_path)
        finally:
            self._destravar()

    def _gerar_painel_e_abrir(self, root_folder, master_path) -> bool:
        """Gera `Painel de Sobressalentes.html` na Pasta Raiz e o abre no
        navegador. Roda na thread do trabalho. Falhar aqui só gera aviso:
        nunca desfaz o que o Gestão PMIB já gravou."""
        from sigft.services import painel  # pandas: só na hora de usar

        saida = os.path.join(root_folder, painel.NOME_DO_ARQUIVO)
        self.log("Gerando o painel de sobressalentes...")
        try:
            caminho = painel.gerar_painel(root_folder, master_path, saida, callback_log=self.log)
        except OSError as e:
            motivo = travas.diagnosticar(saida, e)
            self.log(f"[AVISO] O painel não foi gravado: {os.path.basename(saida)} {motivo.motivo}. "
                     f"{motivo.o_que_fazer} Depois, clique em 'Gerar painel'.")
            return False
        except Exception as e:  # noqa: BLE001 -- vira aviso no log
            self.log(f"[AVISO] O painel não foi gerado: {type(e).__name__}: {e}")
            return False
        try:
            webbrowser.open(pathlib.Path(caminho).resolve().as_uri())
        except Exception as e:  # noqa: BLE001 -- o painel já está gravado
            self.log(f"[AVISO] Painel gravado, mas não consegui abri-lo no navegador ({e}): {caminho}")
        return True

    # --- autorizações de Itaipu -----------------------------------------------
    def aplicar_autorizacoes(self) -> None:
        export = self.path_autorizados
        root_folder = self.entry_root.text()
        if not export:
            QMessageBox.warning(self, t("Aviso"),
                                t("Por favor, selecione o export de autorizados de Itaipu (Passo 4)."))
            return
        if not root_folder:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a Pasta Raiz dos _STATUS_PMIB (Passo 2)."))
            return
        self._travar_botoes(True)
        self.iniciar_tarefa(self._worker_autorizados, export, root_folder)

    def _worker_autorizados(self, export, root_folder) -> None:
        try:
            # Importado aqui: o serviço é leve, mas a tela não precisa dele
            # até alguém clicar.
            from sigft.services import autorizados

            self._progresso(0)
            self.log("Aplicando o export de autorizados de Itaipu...")
            erros = avisos = nao_gravados = 0
            # Arquivo travado: a lista de antes e a do fim (`perguntar_arquivos_travados`).
            for linha in autorizados.executar(export, root_folder,
                                              callback_travados=self.perguntar_arquivos_travados):
                self.log(linha)
                erros += "[ERRO]" in linha
                avisos += "[AVISO]" in linha
                nao_gravados = travas.quantos_no_resumo(linha) or nao_gravados
            self._progresso(1.0)
            if erros:
                self.avisar(t("Aviso"), t("As autorizações não foram aplicadas. Veja o motivo no log."), tipo="aviso")
            elif avisos:
                texto = texto_dos_avisos(t("As autorizações foram aplicadas"), avisos, nao_gravados)
                self.avisar(t("Concluído com avisos"), texto, tipo="aviso")
            else:
                self.avisar(t("Sucesso"), t("Autorizações de Itaipu aplicadas."))
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"[ERRO FATAL]: {e}")
            self.avisar(t("Erro"), t("Ocorreu um erro ao aplicar as autorizações:\n{erro}", erro=e), tipo="erro")
        finally:
            self._destravar()

    # --- [2026-10-14] conferir as autorizações no portal ----------------------
    def conferir_no_portal(self) -> None:
        root_folder = self.entry_root.text()
        if not root_folder:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a Pasta Raiz dos _STATUS_PMIB (Passo 2)."))
            return
        self._travar_botoes(True)
        self.iniciar_tarefa(self._worker_conferir_portal, root_folder)

    def _worker_conferir_portal(self, root_folder) -> None:
        """Abre o navegador, pausa para o login e confere as fichas físicas
        ainda sem AUTORIZADO. Só RPA -- ver `services/autorizacao_portal.py`.
        O navegador fecha no `finally`, dê certo ou errado."""
        from sigft.services import autorizacao_portal

        conferencia = autorizacao_portal.ConferenciaNoPortal()
        try:
            self._progresso(0)
            self.log("Iniciando navegador...")
            conferencia.iniciar_navegador()
            self.log("Carregando portal...")
            conferencia.abrir_portal()
            self.pausar_e_esperar(t(MSG_LOGIN_CONFERIR_AUTORIZACOES))
            erros = avisos = nao_gravados = 0
            for linha in conferencia.executar(root_folder, callback_travados=self.perguntar_arquivos_travados):
                self.log(linha)
                erros += "[ERRO]" in linha
                avisos += "[AVISO]" in linha
                nao_gravados = travas.quantos_no_resumo(linha) or nao_gravados
            self._progresso(1.0)
            if erros:
                self.avisar(t("Aviso"), t("A conferência no portal não terminou. Veja o motivo no log."), tipo="aviso")
            elif avisos:
                texto = texto_dos_avisos(t("A conferência no portal terminou"), avisos, nao_gravados)
                self.avisar(t("Concluído com avisos"), texto, tipo="aviso")
            else:
                self.avisar(t("Sucesso"), t("Conferência no portal concluída."))
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"[ERRO FATAL]: {e}")
            self.avisar(t("Erro"), t("Ocorreu um erro na conferência no portal:\n{erro}", erro=e), tipo="erro")
        finally:
            conferencia.fechar_navegador()
            self._destravar()

    # --- Gestão PMIB ------------------------------------------------------------
    def iniciar_gestao(self) -> None:
        # 1. Coleta e valida os dados ANTES de travar a tela
        api_path = self.path_api
        root_folder = self.entry_root.text()
        master_path = self.path_master
        if not api_path:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a Base do Aconex (Passo 1)."))
            return
        if not root_folder:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a Pasta Raiz (Passo 2)."))
            return
        if not master_path:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a Planilha de mapeamento (Passo 3)."))
            return
        # 2. O backend no clique: se não carregou, diz o motivo e não trava nada.
        modulo = self.backend("pmib_manager_backend")
        if modulo is None:
            return
        # 3. Desativa os botões (dois cliques não sobem dois fluxos) e lê a
        # caixa AQUI, na thread da tela.
        self._travar_botoes(True)
        gerar_painel = self.caixa_gerar_painel.isChecked()
        self.iniciar_tarefa(self._worker, modulo, api_path, root_folder, master_path, gerar_painel)

    def _confirmar_novas(self, df_novos):
        """O `callback_confirm` do backend: mostra as listas novas e devolve só
        as marcadas. Roda na thread do worker, que espera a pessoa decidir."""
        import pandas as pd  # o backend já o carregou; aqui só quando há lista nova

        # Os textos saem do DataFrame AQUI, no worker: a janela só recebe texto.
        itens = [(idx, f"[{row['No. do Documento']}]  -  {row['Título']}") for idx, row in df_novos.iterrows()]
        resultado = self._abrir_e_esperar(lambda evento, res: NovasListasDialog(
            self, itens=itens, evento_espera=evento, resultado=res))
        indices = resultado.get("indices")
        if indices is None:  # Ignorar, "X", Esc ou a janela não abriu
            return pd.DataFrame()
        return df_novos.loc[indices]

    def _worker(self, modulo, api_path, root_folder, master_path, gerar_painel=False) -> None:
        try:
            self.log("Iniciando fluxo de gestão de sobressalentes...")
            manager = modulo.PMIBManager()

            sucesso_total = True
            # [2026-10-05] Avisos não interrompem (um `_STATUS_PMIB` aberto no
            # Excel é pulado e o resto segue), mas não podem terminar num
            # "Sucesso" seco: a pessoa precisa saber que algo ficou para trás.
            avisos = nao_gravados = 0

            # [2026-10-06] Arquivo travado: a lista de antes, a do fim da etapa
            # e a pergunta da mapeadora, todas por `perguntar_arquivos_travados`.
            for resposta in manager.executar_fluxo(api_path, root_folder, master_path,
                                                   callback_confirm=self._confirmar_novas,
                                                   callback_travados=self.perguntar_arquivos_travados):
                if isinstance(resposta, tuple):
                    msg, progresso = resposta
                    self.log(msg)
                    if progresso is not None:
                        self._progresso(progresso)
                else:
                    self.log(resposta)
                    # Se o backend jogar um erro (ex: abortado), marcamos como falha
                    if "[ERRO]" in resposta:
                        sucesso_total = False
                    elif "[AVISO]" in resposta:
                        avisos += 1
                    nao_gravados = travas.quantos_no_resumo(resposta) or nao_gravados

            # [T7] O painel, DEPOIS da gravação: mostra o que acabou de ser
            # gravado. Fluxo com erro não gera (o botão continua lá).
            if gerar_painel and sucesso_total:
                if not self._gerar_painel_e_abrir(root_folder, master_path):
                    avisos += 1
            elif gerar_painel:
                self.log(" -> Painel não gerado: o processo terminou com erro. Use o botão 'Gerar painel'.")

            if sucesso_total and avisos:
                self._progresso(1.0)
                texto = texto_dos_avisos(t("O processo de Gestão PMIB terminou"), avisos, nao_gravados)
                self.avisar(t("Concluído com avisos"), texto, tipo="aviso")
            elif sucesso_total:
                self._progresso(1.0)
                self.avisar(t("Sucesso"), t("Processo de Gestão PMIB finalizado com sucesso!"))
            else:
                # Não dá mais para dizer "nenhuma alteração foi salva": os
                # `_STATUS_PMIB` e a mapeadora são gravados ao longo do fluxo,
                # e o que foi gravado antes do erro continua gravado.
                self.avisar(t("Aviso"), t("O processo foi interrompido ou terminou com erros.\n\n"
                                          "O que foi gravado antes do erro continua gravado. "
                                          "Veja o log para saber o que faltou."), tipo="aviso")
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"[ERRO FATAL]: {e}")
            self.avisar(t("Erro"), t("Ocorreu um erro fatal durante a execução:\n{erro}", erro=e), tipo="erro")
        finally:
            # Reativa os botões ao final de tudo (seja erro ou sucesso)
            self._destravar()

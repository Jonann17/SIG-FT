"""Aba "Upload de Aplicações" (Automação LMR) na interface Qt.

Mesma tela da interface antiga (`sigft/app/views/lmr.py`, removida em 2026-10-15). O que muda é só COMO o worker fala com
a pessoa: lá `callback_ask`/`callback_input` chamavam `messagebox`/`simpledialog`
de dentro da thread do robô, e o fim do lote (e as falhas do pré-processamento)
mexiam no botão pela thread; aqui as perguntas são `perguntar_sim_nao` e
`pedir_texto` (abrem na thread da interface) e o botão volta por `iniciar_tarefa`.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMessageBox, QVBoxLayout

from sigft.app import theme
from sigft.app.textos_dialogos import MSG_LOGIN_LMR
from sigft.app_qt import estilo, file_dialogs
from sigft.app_qt.widgets import blocos, controles, pickers, revisao_portal
from sigft.app_qt.widgets.dialogs import SelecaoComCaixasDialog
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import pmib_regras


class DialogoDaAba(QDialog):
    """"Escolha a aba": uma pergunta só, como o CTkToplevel de 420x220 de lá.

    QUEM ESCOLHE A ABA É A PESSOA (a primeira versão adivinhava, e o usuário
    recusou: adivinhar acerta nove vezes e, na décima, cadastra o lote a partir
    da planilha errada sem ninguém notar).
    """

    def __init__(self, parent, *, nome_arquivo: str, abas: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Escolha a aba")
        self.setFixedSize(420, 220)
        # Espaços do `pack` de lá; o pady de dois vizinhos SOMA no Tk.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addSpacing(20)                           # arquivo: pady=(20, …)
        self.rotulo_arquivo = blocos.rotulo(nome_arquivo, tamanho=12, negrito=True,
                                            cor=controles.COR_TEXTO_CTK)
        layout.addWidget(self.rotulo_arquivo)
        layout.addSpacing(4)                            # arquivo (…, 4) + pergunta (0, …)
        self.rotulo_pergunta = blocos.rotulo("Qual aba contém as aplicações de LMR?", tamanho=12,
                                             cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO_CLARO))
        layout.addWidget(self.rotulo_pergunta)
        layout.addSpacing(17)                           # pergunta (…, 12) + menu (5, …)
        self.menu = controles.MenuDeOpcoes(abas)
        self.menu.setFixedWidth(300)
        layout.addWidget(self.menu, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(20)                           # menu (…, 5) + ler (15, …)
        self.botao_ler = blocos.botao("Ler esta aba", variante="primario", largura=300)
        self.botao_ler.clicked.connect(self.accept)
        layout.addWidget(self.botao_ler, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)                           # ler (…, 5) + cancelar (5, …)
        self.botao_cancelar = blocos.botao("Cancelar", variante="cinza", largura=300)
        self.botao_cancelar.clicked.connect(self.reject)
        layout.addWidget(self.botao_cancelar, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def aba_escolhida(self) -> str:
        return self.menu.currentText()


class ModuloLMR(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, embutida=False, console_externo=None) -> None:
        # Antes do super(): o `_build_ui` roda lá dentro, e o seletor grava aqui.
        self.caminho_status_pmib = None
        super().__init__(parent, controller, titulo="Automação LMR",
                         embutida=embutida, console_externo=console_externo)

    def _build_ui(self) -> None:
        # Espaços verticais do `pack` da tela antiga. O pady de dois vizinhos
        # SOMA no Tk, por isso o espaçamento automático do cartão vai a zero e
        # cada espaço é a soma escrita à mão.
        cinza_claro = estilo.cinza_tk(theme.COR_TEXTO_APOIO_CLARO)
        self._rotulos = r = {}

        self.content_layout.addSpacing(20)              # cartão: pady=20
        corpo = blocos.cartao(self.content_layout)
        corpo.setSpacing(0)
        corpo.setContentsMargins(20, 20, 20, 20)        # título: pady=(20, …); "O script": (…, 20)
        r["titulo"] = blocos.rotulo("Preenchimento Automático de LMR (Aplicações)", tamanho=16,
                                    negrito=True, cor=theme.COLORS["accent"])
        corpo.addWidget(r["titulo"])
        corpo.addSpacing(10)                            # título (…, 10) + texto (0, …)
        r["info"] = blocos.rotulo(
            "Este módulo lê uma aba de um arquivo Excel e cadastra as aplicações no Portal PMIB.\n"
            "Você escolhe a aba depois de selecionar o arquivo.\n"
            "Colunas esperadas: FICHA PMIB, CÓDIGO LMR e TAG LMR.\n"
            "Será solicitado login no navegador durante o processo.",
            cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO))
        corpo.addWidget(r["info"])
        # _STATUS_PMIB opcional: quem só quer cadastrar no portal continua
        # clicando direto em "Selecionar Excel e Iniciar".
        corpo.addSpacing(20)                            # texto (…, 20) + marcar (0, …)
        r["marcar"] = blocos.rotulo("Marcar o resultado no _STATUS_PMIB (opcional):",
                                    negrito=True, cor=theme.COLORS["text_light"])
        corpo.addWidget(r["marcar"])
        corpo.addSpacing(6)                             # marcar (…, 6) + seletor (0, …)
        self.picker_status = pickers.FilePickerRow(
            chave="lmr.status_pmib", categoria="excel", texto_botao="Selecionar _STATUS_PMIB",
            largura_botao=240, titulo="Selecione o _STATUS_PMIB",
            filetypes=[("Excel", "*.xlsx *.xlsm")],
            texto_vazio="Nenhum (o lote não será marcado na planilha)",
            ao_escolher=self._ao_escolher_status)
        # Lá o seletor é `pack` sem `fill`: centrado, com a largura natural.
        corpo.addWidget(self.picker_status, alignment=Qt.AlignmentFlag.AlignHCenter)
        corpo.addSpacing(30)                            # seletor (…, 20) + iniciar (10, …)
        self.btn_run = blocos.botao("Selecionar Excel e Iniciar", variante="primario", largura=300,
                                    altura=50, tamanho_fonte=14, negrito=True,
                                    cor_texto=theme.COLORS["text_white"])
        self.btn_run.clicked.connect(self.iniciar_lmr)
        corpo.addWidget(self.btn_run, alignment=Qt.AlignmentFlag.AlignHCenter)
        corpo.addSpacing(14)                            # iniciar (…, 10) + linha do código (4, …)
        corpo.addLayout(self._linha_do_codigo())
        corpo.addSpacing(8)                             # linha do código (…, 8) + explicação (0, …)
        r["desligado"] = blocos.rotulo(
            "Desligado, processa a ficha inteira desde o começo.\n"
            "O número conta CÓDIGOS LMR (não linhas do Excel): o mesmo código\n"
            "espalhado pela planilha é uma aplicação só.", tamanho=11, cor=cinza_claro)
        corpo.addWidget(r["desligado"])
        corpo.addSpacing(20)                            # explicação (…, 10) + "O script" (10, …)
        r["script"] = blocos.rotulo(
            "O script pedirá:\n1. Arquivo Excel LMR\n2. Seleção das Fichas (Checkbox)",
            tamanho=12, cor=cinza_claro)
        corpo.addWidget(r["script"])
        self.content_layout.addSpacing(20)
        self.content_layout.addStretch()

    def _linha_do_codigo(self) -> QHBoxLayout:
        """"Começar de um código específico" + campo de 70 px, centrados.

        Desligado por padrão. Pedido do usuário (2026-08-21): o padrão é
        começar do 0, e só quando ele pede é que o número entra -- antes TODA
        execução abria um Sim/Não e mais um diálogo pedindo o número.
        """
        linha = QHBoxLayout()
        linha.setSpacing(0)
        linha.addStretch()
        self.caixa_linha_inicial = controles.Interruptor(
            "Começar de um código específico", cor_ligado=theme.COLORS["accent"], tamanho_fonte=12)
        self.caixa_linha_inicial.toggled.connect(self._alternar_linha_inicial)
        linha.addWidget(self.caixa_linha_inicial)
        linha.addSpacing(10)                            # interruptor: padx=(0, 10)
        self.entry_linha_inicial = QLineEdit()  # o visual (28 px) é o do CTkEntry, na folha do app
        self.entry_linha_inicial.setFixedWidth(70)
        self.entry_linha_inicial.setPlaceholderText("0")
        self.entry_linha_inicial.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.entry_linha_inicial.setEnabled(False)
        linha.addWidget(self.entry_linha_inicial)
        linha.addStretch()
        return linha

    # --- linha inicial ----------------------------------------------------------
    def _alternar_linha_inicial(self, ligado: bool) -> None:
        self.entry_linha_inicial.setEnabled(ligado)
        if not ligado:
            self.entry_linha_inicial.clear()

    def _linha_inicial_escolhida(self) -> int | None:
        """Número do interruptor, ou `None` quando ele está desligado.

        `None` e `0` NÃO são a mesma coisa para o serviço: `None` quer dizer
        "não me pergunte nada, comece do começo"; um número quer dizer "a tela
        já perguntou, use este". Chamar na thread da interface.
        """
        if not self.caixa_linha_inicial.isChecked():
            return None
        texto = self.entry_linha_inicial.text().strip()
        if not texto:
            return None
        try:
            return int(texto)
        except ValueError:
            self.log(f"Linha inicial {texto!r} não é um número. Começando do 0.")
            return None

    # --- escolhas (a pessoa decide; sobrescrevíveis em teste) ---------------------
    def escolher_aba(self, nome_arquivo: str, abas: list[str]) -> str | None:
        dialogo = DialogoDaAba(self, nome_arquivo=nome_arquivo, abas=abas)
        aba = dialogo.aba_escolhida() if dialogo.exec() else None
        dialogo.deleteLater()  # filho da tela: sem isto, cada clique deixava uma janela escondida
        return aba

    def escolher_pmibs(self, pmibs: list[str]) -> list[str]:
        dialogo = SelecaoComCaixasDialog(self, titulo="Selecione as Fichas",
                                         mensagem="Selecione os PMIBs para processar:", itens=pmibs)
        # Fechar no "X" é "nenhuma": o que estiver marcado não vale.
        escolhidos = dialogo.selecionados() if dialogo.exec() else []
        dialogo.deleteLater()
        return escolhidos

    # --- _STATUS_PMIB opcional -------------------------------------------------------
    def _ao_escolher_status(self, caminho) -> None:
        self.caminho_status_pmib = caminho
        self.log(f"_STATUS_PMIB selecionado: {os.path.basename(caminho)}")

    def _marcar_status_do_lote(self, modulo, completas, incompletas) -> None:
        """Marca a coluna "APLICAÇÃO - LMR" das fichas do lote.

        Roda no worker, DEPOIS do portal. Nunca deixa uma falha de planilha
        escapar: o cadastro no portal já aconteceu, e é ele que custa caro.
        """
        if not self.caminho_status_pmib:
            if completas or incompletas:
                self.log("[i] Nenhum _STATUS_PMIB selecionado. A planilha não foi marcada.")
            return
        self.log("Marcando o _STATUS_PMIB...")
        try:
            _marcadas, recado = modulo.marcar_status_pmib(
                self.caminho_status_pmib, completas, incompletas,
                retry_lock=self.perguntar_retry_excel, callback_log=self.log)
            self.log(recado)
        except Exception as erro:  # noqa: BLE001 -- o portal já foi feito
            self.log(f"[!] Não consegui marcar o _STATUS_PMIB: {type(erro).__name__}: {erro}")
            self.log("    O cadastro no portal FOI feito. Marque a planilha à mão.")

    # --- execução -----------------------------------------------------------------------
    def iniciar_lmr(self) -> None:
        # Antes do seletor: escolher o arquivo para depois ouvir que o módulo
        # não carregou seria pedir o trabalho à toa.
        modulo = self.backend("lmr_backend")
        if modulo is None:
            return
        excel_path = file_dialogs.ask_open_file("lmr.excel", "excel", titulo="Selecione o Excel LMR",
                                                filetypes=[("Excel", "*.xlsx")])
        if not excel_path:
            return
        try:
            abas = modulo.listar_abas(excel_path)
        except Exception as e:  # noqa: BLE001 -- vira aviso
            QMessageBox.critical(self, "Erro", f"Não consegui ler as abas do arquivo:\n{e}")
            return
        if not abas:
            QMessageBox.critical(self, "Erro", "O arquivo não tem nenhuma aba.")
            return
        nome = os.path.basename(excel_path)
        aba = self.escolher_aba(nome, abas)
        if aba is None:
            return
        self.log(f"Lendo {nome} (aba '{aba}')...")
        self.iniciar_tarefa(self._pre_processamento, modulo, excel_path, aba, botao=self.btn_run)

    def _pre_processamento(self, modulo, excel_path, aba) -> None:
        """Lê o Excel, pede as fichas e roda o robô, TUDO na mesma tarefa.

        Uma tarefa só de propósito: o botão desliga em "Ler esta aba" e só
        volta quando o robô termina, como lá. Com duas tarefas, a devolução do
        botão da primeira podia chegar depois do começo da segunda e religá-lo
        com o robô rodando.
        """
        try:
            automator = modulo.LMRAutomation()
            ok, df_completo, pmibs_unicos, msg = automator.carregar_dados_excel(excel_path, aba)
            self.log(msg)
            if not ok:
                self.avisar("Erro", f"Falha ao ler Excel:\n{msg}", tipo="erro")
                return
            if not pmibs_unicos:
                self.log("Nenhum PMIB encontrado.")
                return
            selecionados = self._escolher_pmibs_e_esperar(pmibs_unicos)
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Pré-processamento: {e}")
            return
        if not selecionados:
            self.log("Seleção cancelada.")
            return
        selecionados = self._revisar_antes_do_portal(modulo, selecionados, df_completo)
        if not selecionados:
            return
        self.log(f"{len(selecionados)} fichas selecionadas. Iniciando robô...")
        self._worker_lmr(modulo, selecionados, df_completo)

    def _revisar_antes_do_portal(self, modulo, selecionados, df_completo):
        """R2: as regras do portal nas fichas escolhidas, antes do navegador.

        Roda na tarefa; a janela, na thread da interface. Os grupos saem da
        MESMA função do robô (`agrupar_por_codigo`, sobre as linhas da ficha
        filtradas como ele filtra). Devolve os PMIBs que seguem (só filtra) ou
        `None` para não abrir o robô. Se a conferência em si falhar, o robô
        segue como antes e o console diz que a revisão não rodou: ela é um
        aviso, e o portal continua sendo o juiz.
        """
        try:
            fichas = []
            for pmib in selecionados:
                linhas = df_completo[df_completo["PMIB"] == pmib].reset_index(drop=True)
                fichas.append((pmib, modulo.agrupar_por_codigo(
                    (linhas.loc[i, "Código_PMIB"], linhas.loc[i, "TAG_PMIB"]) for i in range(len(linhas)))))
            problemas = pmib_regras.conferir_lmr(fichas)
        except Exception as erro:  # noqa: BLE001 -- a revisão nunca derruba o robô
            self.log(f"[!] Não consegui conferir as fichas antes do portal ({type(erro).__name__}: "
                     f"{erro}). Seguindo sem a revisão.")
            return selecionados
        seguem = self._na_interface_e_esperar(lambda: revisao_portal.conferir_antes_do_portal(
            self, problemas, len(selecionados), self.log))
        if seguem is None:
            return None
        return [selecionados[i] for i in seguem]

    def _escolher_pmibs_e_esperar(self, pmibs) -> list[str]:
        """A janela de seleção abre na thread da interface; a tarefa espera.

        Um erro da janela volta para cá e é relançado: `_na_interface_e_esperar`
        sozinho o engoliria (só traceback) e viraria "Seleção cancelada."
        """
        def escolher():
            try:
                return ("ok", self.escolher_pmibs(pmibs))
            except Exception as erro:  # noqa: BLE001 -- relançado na tarefa
                return ("erro", erro)

        tipo, valor = self._na_interface_e_esperar(escolher)
        if tipo == "erro":
            raise valor
        return valor

    def _perguntar_com_sim_padrao(self, titulo: str, mensagem: str) -> bool:
        """O `callback_ask` do serviço: o `askyesno` da interface antiga tinha o "Sim" no
        Enter, e aqui a pergunta é "SIM = tentar este item de novo / NÃO =
        pular" -- nada foi enviado, então repetir é a resposta segura."""
        return self.perguntar_sim_nao(titulo, mensagem, padrao_sim=True)

    def _worker_lmr(self, modulo, selecionados, df_completo) -> None:
        auto = modulo.LMRAutomation()
        try:
            self.log("Iniciando navegador...")
            auto.iniciar_driver()
            self.log("Carregando portal...")
            auto.abrir_portal()
            self.pausar_e_esperar(MSG_LOGIN_LMR)
            # Lido DEPOIS do login, como lá (a pessoa pode ligar o interruptor
            # enquanto loga), mas na thread da interface: é widget.
            linha_inicio = self._na_interface_e_esperar(self._linha_inicial_escolhida)
            completas, incompletas = auto.processar_lista(
                selecionados, df_completo, callback_log=self.log,
                callback_ask=self._perguntar_com_sim_padrao, callback_input=self.pedir_texto,
                linha_inicio=linha_inicio)
            self.log("Automação LMR finalizada.")
            # DEPOIS do portal e com try/except próprio (ver o método).
            self._marcar_status_do_lote(modulo, completas, incompletas)
            self.avisar("Sucesso", "Processo concluído.")
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Fatal LMR: {e}")
        finally:
            auto.fechar_driver()

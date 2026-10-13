"""Tela "Apagar Aplicações LMR" (aba "Exclusão" da Aplicação LMR) na interface Qt.

Ação destrutiva: título em vermelho e confirmação antes de começar. Mesma tela
de `sigft/app/views/apagar_lmr.py`; o que muda é só COMO o worker fala com a
pessoa: lá `messagebox.showinfo` e `btn_run.configure` eram chamados de dentro
da thread; aqui é `self.avisar(...)` e `iniciar_tarefa`, que sempre passam pela
thread da interface.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QMessageBox

from sigft.app import theme
from sigft.app.textos_dialogos import MSG_LOGIN_APAGAR_LMR, TEXTO_COMECAR_EXCLUSAO
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos, pickers
from sigft.app_qt.widgets.module_frame import ModuleFrame


class ModuloApagarLMR(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, embutida=False, console_externo=None) -> None:
        # Antes do super(): o `_build_ui` roda lá dentro e cria o seletor, que
        # grava aqui quando a pessoa escolhe a planilha.
        self.caminho_status = None
        super().__init__(parent, controller, titulo="Apagar Aplicações LMR",
                         cor_titulo=theme.COLORS["danger"],
                         embutida=embutida, console_externo=console_externo)

    def _build_ui(self) -> None:
        # Espaços verticais do `pack` da tela antiga. O pady de dois vizinhos
        # SOMA no Tk, por isso o espaçamento automático do cartão vai a zero e
        # cada espaço é a soma escrita à mão.
        cinza = estilo.cinza_tk(theme.COR_TEXTO_APOIO)
        cinza_claro = estilo.cinza_tk(theme.COR_TEXTO_APOIO_CLARO)
        self._rotulos = r = {}

        self.content_layout.addSpacing(20)              # cartão: pady=20
        corpo = blocos.cartao(self.content_layout)
        corpo.setSpacing(0)
        corpo.setContentsMargins(20, 20, 20, 20)        # aviso: pady=(20, …); passos: (…, 20)
        r["atencao"] = blocos.rotulo("ATENÇÃO: AÇÃO DESTRUTIVA", tamanho=16, negrito=True,
                                     cor=theme.COLORS["danger"])
        corpo.addWidget(r["atencao"])
        corpo.addSpacing(5)                             # aviso (…, 5) + irreversível (0, …)
        r["irreversivel"] = blocos.rotulo(
            "Esta ferramenta apaga TODAS as aplicações LMR de uma ficha.\nO processo é irreversível.",
            cor=cinza)
        corpo.addWidget(r["irreversivel"])
        corpo.addSpacing(30)                            # irreversível (…, 20) + linha do PMIB (10, …)
        corpo.addLayout(self._linha_pmib())
        corpo.addSpacing(25)                            # linha do PMIB (…, 10) + opcional (15, …)
        r["opcional"] = blocos.rotulo(
            "Opcional: informe o _STATUS_PMIB para LIMPAR a marcação da coluna\n"
            "\"APLICAÇÃO - LMR\" das fichas que forem apagadas com sucesso.",
            tamanho=12, cor=cinza_claro)
        corpo.addWidget(r["opcional"])
        corpo.addSpacing(5)                             # opcional (…, 5) + seletor (0, …)
        self.picker_status = pickers.FilePickerRow(
            chave="apagar_lmr.status_pmib", categoria="excel",
            texto_botao="Selecionar _STATUS_PMIB", largura_botao=220,
            titulo="Selecione o _STATUS_PMIB (opcional)",
            filetypes=[("Excel", "*.xlsx;*.xlsm")],
            texto_vazio="Nenhum (a planilha não será alterada)",
            ao_escolher=self._ao_escolher_status)
        # Lá o seletor é `pack` sem `fill`: centrado, com a largura natural.
        corpo.addWidget(self.picker_status, alignment=Qt.AlignmentFlag.AlignHCenter)
        corpo.addSpacing(30)                            # seletor (…, 10) + iniciar (20, …)
        self.btn_run = blocos.botao("INICIAR LIMPEZA", variante="perigo", largura=350, altura=50,
                                    tamanho_fonte=14, negrito=True,
                                    cor_texto=theme.COLORS["text_white"])
        self.btn_run.clicked.connect(self.iniciar_limpeza)
        corpo.addWidget(self.btn_run, alignment=Qt.AlignmentFlag.AlignHCenter)
        corpo.addSpacing(20)                            # iniciar (…, 20) + passos (0, …)
        r["passos"] = blocos.rotulo(
            "O robô irá:\n1. Abrir o navegador\n2. Solicitar login manual\n3. Acessar a ficha\n"
            "4. Clicar em todas as lixeiras até esvaziar a lista.",
            tamanho=12, cor=cinza_claro)
        corpo.addWidget(r["passos"])
        self.content_layout.addSpacing(20)
        self.content_layout.addStretch()

    def _linha_pmib(self) -> QHBoxLayout:
        """"Código PMIB:" + campo de 250 px, centrados (lá: padx=10 em cada um)."""
        linha = QHBoxLayout()
        linha.addStretch()
        rotulo = blocos.rotulo("Código PMIB:", tamanho=14, negrito=True)
        rotulo.setWordWrap(False)  # com quebra, a largura natural do rótulo na linha sai errada
        self._rotulos["pmib"] = rotulo
        linha.addWidget(rotulo)
        linha.addSpacing(20)                            # rótulo (…, 10) + campo (10, …)
        self.entry_pmib = QLineEdit()  # o visual (28 px, cores, fonte) é o do CTkEntry, na folha do app
        self.entry_pmib.setFixedWidth(250)
        self.entry_pmib.setPlaceholderText("Ex: 4500063671.1234")
        linha.addWidget(self.entry_pmib)
        linha.addStretch()
        return linha

    # --- _STATUS_PMIB opcional ------------------------------------------------
    def _ao_escolher_status(self, caminho) -> None:
        self.caminho_status = caminho
        self.log(f"_STATUS_PMIB selecionado: {caminho}")

    def _limpar_status_do_lote(self, modulo, pmib, limpou) -> None:
        """Limpa a coluna "APLICAÇÃO - LMR" da ficha apagada.

        Só age quando as DUAS condições valem: a pessoa informou a planilha E a
        exclusão terminou bem. Limpar a marcação de uma ficha cuja exclusão
        falhou diria que ela está por fazer enquanto as aplicações continuam no
        portal.
        """
        if not self.caminho_status:
            return
        if not limpou:
            self.log("   [i] A exclusão não terminou limpa. O _STATUS_PMIB NÃO foi "
                     "alterado. A marcação continua como estava, o que é o certo "
                     "enquanto houver aplicação na ficha.")
            return
        try:
            _n, recado = modulo.limpar_status_pmib(
                self.caminho_status, [pmib],
                retry_lock=self.perguntar_retry_excel, callback_log=self.log)
            self.log(f"   {recado}")
        except Exception as erro:  # noqa: BLE001 -- o trabalho no portal já foi feito
            self.log(f"   [!] Não consegui atualizar o _STATUS_PMIB: {erro}")

    # --- execução -------------------------------------------------------------
    def iniciar_limpeza(self) -> None:
        pmib = self.entry_pmib.text().strip()
        if not pmib:
            QMessageBox.warning(self, "Aviso", "Digite o código PMIB.")
            return
        # Antes da confirmação: perguntar "tem certeza?" para depois dizer que
        # o módulo não carregou seria pedir a decisão à toa.
        modulo = self.backend("apagar_lmr_backend")
        if modulo is None:
            return
        if not self.perguntar_sim_nao(
                "Confirmar", f"Tem certeza que deseja APAGAR todas as aplicações do PMIB {pmib}?"):
            return
        self.log(f"Preparando limpeza para: {pmib}...")
        self.iniciar_tarefa(self._worker, modulo, pmib, botao=self.btn_run)

    def _worker(self, modulo, pmib) -> None:
        auto = modulo.ApagarLMRAutomation()
        try:
            self.log("Iniciando navegador...")
            auto.iniciar_driver()
            self.log("Carregando portal...")
            auto.abrir_portal()
            # A ação é destrutiva: o botão da pausa diz o que vai acontecer.
            self.pausar_e_esperar(MSG_LOGIN_APAGAR_LMR, texto_botao=TEXTO_COMECAR_EXCLUSAO)
            self.log("Iniciando varredura...")
            limpou = auto.executar_limpeza(pmib, callback_log=self.log)
            self.log("Processo Finalizado.")
            self._limpar_status_do_lote(modulo, pmib, limpou)
            self.avisar("Sucesso", "Limpeza concluída.")
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Fatal: {e}")
        finally:
            auto.fechar_driver()

"""Tela "Tradutor Técnico (PT -> ES)" na interface Qt.

Mesma tela de `sigft/app/views/translator.py`. O que muda é só COMO ela fala
com a pessoa a partir do worker: lá eram `messagebox` e `btn.configure`
chamados de dentro da thread (proibido no Tk, fatal no macOS); aqui é
`self.avisar(...)` e `iniciar_tarefa`, que sempre passam pela thread da
interface.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from sigft.app import backends, theme
from sigft.app_qt import file_dialogs, interface
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import plataforma


class ModuloTranslator(ModuleFrame):
    def __init__(self, parent=None, controller=None) -> None:
        self.tradutor = None  # nasce no primeiro clique, não aqui
        super().__init__(parent, controller, titulo="Tradutor Técnico (PT -> ES)")

    def _build_ui(self) -> None:
        corpo = blocos.cartao(self.content_layout)
        corpo.addWidget(blocos.rotulo("Tradução Automática de Características", tamanho=16,
                                      negrito=True, cor=theme.COLORS["accent"]))
        descricao = blocos.rotulo(
            "Selecione as planilhas para traduzir do Português para Espanhol.\n"
            "O sistema cria uma nova aba traduzida.\n"
            "A tradução roda neste computador: nenhuma resposta sai daqui.",
            cor="#BEBEBE")
        # As 3 linhas já vêm quebradas no texto. Com quebra automática, o
        # rótulo centralizado no cartão recebe largura estreita e altura de
        # uma linha, e o texto aparece cortado.
        descricao.setWordWrap(False)
        corpo.addWidget(descricao)
        self.btn_run = blocos.botao("Selecionar Arquivos e Iniciar", variante="primario",
                                    largura=300, altura=50, tamanho_fonte=14, negrito=True)
        self.btn_run.clicked.connect(self.iniciar_traducao)
        self.btn_stop = blocos.botao("PARAR AGORA", variante="perigo", largura=200, altura=40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.parar_traducao)
        self.btn_glossario = blocos.botao("Abrir glossário (correções de termos)",
                                          variante="contorno", largura=300, altura=32)
        self.btn_glossario.clicked.connect(self.abrir_glossario)
        for b in (self.btn_run, self.btn_stop, self.btn_glossario):
            corpo.addWidget(b, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.content_layout.addStretch()

    def _tradutor(self):
        if self.tradutor is None:
            modulo = self.backend("translator_backend")
            if modulo is None:
                return None
            self.tradutor = modulo.TechnicalTranslator()
        return self.tradutor

    def iniciar_traducao(self) -> None:
        if self._tradutor() is None:
            return
        files = file_dialogs.ask_open_files("translator.fichas", "excel",
                                            titulo="Selecione as Fichas (.xlsx)",
                                            filetypes=[("Excel", "*.xlsx")])
        if not files:
            return
        self.log(f"Iniciando tradução de {len(files)} arquivos...")
        self.btn_stop.setEnabled(True)
        self.iniciar_tarefa(self._worker, files, botao=self.btn_run)

    def parar_traducao(self) -> None:
        if self.tradutor is not None:
            self.tradutor.request_stop()
        self.log("[COMANDO] Parada solicitada...")

    def abrir_glossario(self) -> None:
        tradutor = self._tradutor()
        if tradutor is None:
            return
        try:
            caminho = tradutor.caminho_do_glossario()
            self.log(f"Abrindo o glossário: {caminho}")
            plataforma.abrir_no_sistema(caminho)
        except Exception as e:  # noqa: BLE001 -- vira aviso
            QMessageBox.critical(self, "Glossário", f"Não consegui abrir o glossário: {e}")

    def _worker(self, files) -> None:
        status = backends.exigir("translator_backend").STATUS
        ultimo_erro = ""
        try:
            for msg in self.tradutor.processar_arquivos(files, retry_lock=self.perguntar_retry_excel):
                if msg == "PARADO":
                    self.log("Processo interrompido pelo usuário.")
                    return
                if msg == "ABORTADO":
                    self.log("Tradução não iniciada.")
                    self.avisar("Tradutor", ultimo_erro or "A tradução não pôde começar.", tipo="erro")
                    return
                if msg in status:
                    continue
                if msg.startswith("[ERRO]"):
                    ultimo_erro = msg
                self.log(msg)
            self.log("Tradução em lote finalizada.")
            self.avisar("Sucesso", "Processo concluído.")
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Fatal: {e}")
        finally:
            interface.na_interface(self.btn_stop.setEnabled, False)

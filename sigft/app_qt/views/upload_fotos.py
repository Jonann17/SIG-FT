"""Tela "Upload de Fotos" (2026-10-30): sobe as fotos de um subsistema nas fichas
do PMIB e marca a coluna DOCUMENTOS E IMAGENS do _STATUS_PMIB.

A regra mora em `sigft/services/upload_fotos.py`; o caderno é
`docs/UPLOAD_DE_FOTOS.md`. Aqui ficam só os seletores, o modo e as conversas com
a pessoa (login, a pergunta por ficha, o resumo antes de começar).
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import QFrame, QHBoxLayout, QMessageBox, QVBoxLayout

from sigft.app.idioma import marcar, t
from sigft.app.textos_dialogos import MSG_LOGIN_LOTE
from sigft.app_qt import estilo, interface
from sigft.app_qt.widgets import blocos, controles, dialogos_selecao, pickers
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.app_qt.widgets.trava_robo import ComTravaDeRobo
from sigft.services import upload_fotos as svc

# Na ordem do `MenuDeOpcoes`: o índice escolhido é o modo.
MODOS = (svc.MODO_SUBSTITUIR, svc.MODO_PERGUNTAR)
TEXTOS_DOS_MODOS = (
    marcar("Excluir as fotos que já estão na ficha e subir as da pasta"),
    marcar("Perguntar em cada ficha que já tiver fotos"),
)
# "Velocidade do portal" (2026-11-03, o PMIB lento estourando os tempos): o
# fator multiplica todas as esperas do robô (`upload_fotos.Esperas`). No caso
# bom não custa nada -- cada espera acaba quando a tela responde --, por isso
# o padrão é "Lento".
VELOCIDADES = (1, 2, 4)
TEXTOS_DAS_VELOCIDADES = (
    marcar("Normal: o portal responde rápido"),
    marcar("Lento: espera até o dobro"),
    marcar("Muito lento: espera até 4 vezes mais"),
)
VELOCIDADE_PADRAO = 1   # índice de "Lento"
# A prévia do lote (2026-11-04): os quatro números, na ordem da tela.
NUMEROS_DA_PREVIA = (
    ("fotos", marcar("fotos na pasta")),
    ("fichas", marcar("fichas que recebem fotos")),
    ("sem_ficha", marcar("finais sem ficha certa")),
    ("fora", marcar("arquivos fora do padrão")),
)
TEXTO_PREVIA_VAZIA = marcar("Escolha a pasta de fotos e o _STATUS_PMIB: aqui aparece o que vai subir em cada "
                            "ficha, antes de abrir o portal.")


class ModuloUploadFotos(ComTravaDeRobo, ModuleFrame):
    # Só vai ao console (`ComTravaDeRobo.robo_ocupado`): fica em português.
    NOME_DO_ROBO = "Upload de fotos"

    def __init__(self, parent=None, controller=None) -> None:
        # Antes do super(): o `_build_ui` roda lá dentro e cria os seletores.
        self.pasta = None
        self.caminho_status = None
        self.automacao = None
        super().__init__(parent, controller, titulo=t("Upload de Fotos"))
        instalar_como_funciona(self, "UploadFotos")  # nao-e-interface: a chave do texto

    def _build_ui(self) -> None:
        # Rolável: tests/test_qt_tela_1366.py (notebook 1366x768).
        self.area, rolavel = blocos.area_rolavel(self.content_layout)
        rolavel.addSpacing(12)

        # [2026-11-04] Duas colunas em cima (o que subir | como subir) e a
        # prévia embaixo: antes era uma coluna só, comprida e vazia, e a pessoa
        # só descobria o que ia subir depois de clicar em Iniciar.
        topo = QHBoxLayout()
        topo.setSpacing(16)
        rolavel.addLayout(topo)

        esquerda = QVBoxLayout()
        topo.addLayout(esquerda, 3)
        arquivos = blocos.cartao(esquerda)
        arquivos.setContentsMargins(18, 16, 18, 16)
        arquivos.addWidget(blocos.rotulo(t("O que subir"), tamanho=15, negrito=True, papel="destaque", alinhar="esquerda"))
        arquivos.addWidget(blocos.rotulo(t("1. Pasta de fotos do subsistema"), negrito=True, alinhar="esquerda"))
        arquivos.addWidget(blocos.rotulo(
            t("Os arquivos se chamam pelos 4 últimos dígitos do código PMIB, mais uma letra "
              "para a sequência: 0071.jpg, 0071a.jpg, 0071b.jpg…"), tamanho=12, papel="legenda", alinhar="esquerda"))
        self.picker_pasta = pickers.FolderPickerRow(
            chave="upload_fotos.pasta", texto_botao=t("Selecionar pasta"), largura_botao=220,
            titulo=t("Selecione a pasta de fotos do subsistema"), ao_escolher=self._ao_escolher_pasta)
        arquivos.addWidget(self.picker_pasta)
        arquivos.addSpacing(6)
        arquivos.addWidget(blocos.rotulo(t("2. _STATUS_PMIB do sistema"), negrito=True, alinhar="esquerda"))
        self.picker_status = pickers.FilePickerRow(
            chave="upload_fotos.status_pmib", categoria="excel",
            texto_botao=t("Selecionar _STATUS_PMIB"), largura_botao=220,
            titulo=t("Selecione o _STATUS_PMIB"), filetypes=[("Excel", "*.xlsx;*.xlsm")],
            ao_escolher=self._ao_escolher_status)
        arquivos.addWidget(self.picker_status)

        direita = QVBoxLayout()
        topo.addLayout(direita, 2)
        opcoes = blocos.cartao(direita)
        opcoes.setContentsMargins(18, 16, 18, 16)
        opcoes.addWidget(blocos.rotulo(t("Como subir"), tamanho=15, negrito=True, papel="destaque", alinhar="esquerda"))
        opcoes.addWidget(blocos.rotulo(t("3. Fichas que já têm fotos"), negrito=True, alinhar="esquerda"))
        self.menu_modo = controles.MenuDeOpcoes([t(texto) for texto in TEXTOS_DOS_MODOS])
        opcoes.addWidget(self.menu_modo)
        opcoes.addSpacing(6)
        opcoes.addWidget(blocos.rotulo(t("4. Velocidade do portal"), negrito=True, alinhar="esquerda"))
        self.menu_velocidade = controles.MenuDeOpcoes([t(texto) for texto in TEXTOS_DAS_VELOCIDADES])
        self.menu_velocidade.setCurrentIndex(VELOCIDADE_PADRAO)
        opcoes.addWidget(self.menu_velocidade)
        opcoes.addStretch()

        rolavel.addSpacing(14)
        previa = blocos.cartao(rolavel)
        previa.setContentsMargins(18, 16, 18, 16)
        cabeca = QHBoxLayout()
        cabeca.addWidget(blocos.rotulo(t("Prévia do lote"), tamanho=15, negrito=True, papel="destaque", alinhar="esquerda"))
        cabeca.addStretch()
        self.btn_previa = blocos.botao(t("Atualizar prévia"), variante="secundario", altura=30)
        self.btn_previa.clicked.connect(self.atualizar_previa)
        cabeca.addWidget(self.btn_previa)
        previa.addLayout(cabeca)

        numeros = QHBoxLayout()
        numeros.setSpacing(12)
        self.numeros = {}
        for chave, texto in NUMEROS_DA_PREVIA:
            valor, caixa = self._numero(t(texto))
            self.numeros[chave] = valor
            numeros.addWidget(caixa, 1)
        previa.addLayout(numeros)

        self.rotulo_previa = blocos.rotulo(t(TEXTO_PREVIA_VAZIA), tamanho=12, papel="legenda", alinhar="esquerda")
        self.rotulo_previa.setWordWrap(True)
        previa.addWidget(self.rotulo_previa)
        self.tabela_previa = dialogos_selecao.tabela_ttk(
            [(t("Código PMIB"), 170, "w"), (t("Fotos"), 60, "center"), (t("Arquivos"), 360, "w")],
            selecao="browse", barra_horizontal=False)
        self.tabela_previa.setMinimumHeight(140)
        self.tabela_previa.setVisible(False)
        previa.addWidget(self.tabela_previa)

        rolavel.addSpacing(14)
        botoes = QHBoxLayout()
        botoes.addStretch()
        self.btn_run = blocos.botao(t("INICIAR UPLOAD"), largura=260, altura=44, negrito=True)
        self.btn_run.clicked.connect(self.iniciar)
        botoes.addWidget(self.btn_run)
        self.btn_parar = blocos.botao(t("PARAR"), variante="perigo", largura=120, altura=44)
        self.btn_parar.clicked.connect(self.parar)
        botoes.addWidget(self.btn_parar)
        botoes.addStretch()
        rolavel.addLayout(botoes)
        rolavel.addStretch()

    @staticmethod
    def _numero(legenda):
        """Uma caixinha "número grande + legenda" da prévia."""
        caixa = QFrame(objectName="painel_home")
        lay = QVBoxLayout(caixa)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(0)
        valor = blocos.rotulo("–", tamanho=20, negrito=True, papel="destaque", alinhar="esquerda")
        lay.addWidget(valor)
        lay.addWidget(blocos.rotulo(legenda, tamanho=11, papel="legenda", alinhar="esquerda"))
        return valor, caixa

    # --- seletores ------------------------------------------------------------
    def _ao_escolher_pasta(self, caminho) -> None:
        self.pasta = caminho
        self.log(f"Pasta de fotos: {caminho}")
        self.atualizar_previa()

    def _ao_escolher_status(self, caminho) -> None:
        self.caminho_status = caminho
        self.log(f"_STATUS_PMIB: {caminho}")
        self.atualizar_previa()

    # --- prévia ---------------------------------------------------------------
    def atualizar_previa(self) -> None:
        """Lê a pasta e o _STATUS_PMIB ao lado (planilha grande congelaria a
        janela) e mostra o que vai subir. Só leitura: nada vai ao portal."""
        if not self.pasta:
            return
        self.rotulo_previa.setText(t("Lendo a pasta e o _STATUS_PMIB…"))
        self.iniciar_tarefa(self._calcular_previa, self.pasta, self.caminho_status, botao=self.btn_previa)

    def _calcular_previa(self, pasta, caminho_status) -> None:
        """Na thread de trabalho."""
        try:
            grupos, ignorados = svc.agrupar_fotos(pasta)
            if caminho_status:
                fichas, sem_ficha, ambiguas = svc.ligar_as_fichas(grupos, svc.ler_codigos(caminho_status))
            else:
                fichas, sem_ficha, ambiguas = None, [], {}
        except Exception as erro:  # noqa: BLE001 -- a pessoa precisa ver o motivo
            interface.na_interface(self._mostrar_erro_da_previa, str(erro))
            return
        interface.na_interface(self._mostrar_previa, grupos, ignorados, fichas, sem_ficha, ambiguas)

    def _mostrar_erro_da_previa(self, erro) -> None:
        self.rotulo_previa.setText(t("Não foi possível ler: {erro}", erro=erro))
        estilo.definir_papel(self.rotulo_previa, "erro")

    def _mostrar_previa(self, grupos, ignorados, fichas, sem_ficha, ambiguas) -> None:
        estilo.definir_papel(self.rotulo_previa, "legenda")
        total = sum(len(c) for c in grupos.values())
        self.numeros["fotos"].setText(str(total))
        self.numeros["fora"].setText(str(len(ignorados)))
        if fichas is None:
            self.numeros["fichas"].setText("–")
            self.numeros["sem_ficha"].setText("–")
            self.rotulo_previa.setText(t("Escolha o _STATUS_PMIB para ligar as fotos às fichas."))
            self.tabela_previa.setVisible(False)
            return
        self.numeros["fichas"].setText(str(len(fichas)))
        self.numeros["sem_ficha"].setText(str(len(sem_ficha) + len(ambiguas)))
        avisos = []
        if ignorados:
            avisos.append(t("Fora do padrão (não sobem): {nomes}", nomes=", ".join(ignorados[:8])
                            + ("…" if len(ignorados) > 8 else "")))
        if sem_ficha:
            avisos.append(t("Sem ficha no _STATUS_PMIB: {finais}", finais=", ".join(sem_ficha[:12])
                            + ("…" if len(sem_ficha) > 12 else "")))
        for quatro, codigos in list(ambiguas.items())[:5]:
            avisos.append(t("{quatro}: mais de uma ficha termina assim ({codigos})",
                            quatro=quatro, codigos=", ".join(codigos)))
        if not fichas:
            avisos.insert(0, t("Nenhuma foto da pasta corresponde a uma ficha do _STATUS_PMIB."))
        self.rotulo_previa.setText("\n".join(avisos) if avisos else
                                   t("Tudo certo: cada foto tem a sua ficha."))
        self.tabela_previa.clear()
        for pmib, _quatro, caminhos in fichas:
            dialogos_selecao.linha_ttk(self.tabela_previa, [
                pmib, str(len(caminhos)), ", ".join(os.path.basename(c) for c in caminhos)])
        self.tabela_previa.setVisible(bool(fichas))
        self.btn_run.setText(t("SUBIR FOTOS EM {n} FICHA(S)", n=len(fichas)) if fichas else t("INICIAR UPLOAD"))

    # --- execução -------------------------------------------------------------
    def iniciar(self) -> None:
        if self.robo_ocupado():
            return
        if not self.pasta or not self.caminho_status:
            QMessageBox.warning(self, t("Aviso"), t("Escolha a pasta de fotos e o _STATUS_PMIB."))
            return
        # A leitura da pasta e do _STATUS_PMIB vai para o robô: feita aqui, na
        # thread da interface, congelava a janela com planilha grande.
        self.iniciar_com_trava(self._worker, MODOS[self.menu_modo.currentIndex()],
                               VELOCIDADES[self.menu_velocidade.currentIndex()], botao=self.btn_run)

    def _montar_lote(self, modo):
        """As fichas a subir, depois do "Começar?" da pessoa; `None` se não há o
        que fazer ou ela desistiu. Roda na thread do robô."""
        try:
            grupos, ignorados = svc.agrupar_fotos(self.pasta)
            fichas, sem_ficha, ambiguas = svc.ligar_as_fichas(grupos, svc.ler_codigos(self.caminho_status))
        except Exception as erro:  # noqa: BLE001 -- a pessoa precisa ver o motivo
            self.avisar(t("Aviso"), str(erro), "aviso")
            return None

        for nome in ignorados:
            self.log(f"   ⚠️ {nome}: fora do padrão 0071.jpg / 0071a.jpg, não sobe.")
        for quatro in sem_ficha:
            self.log(f"   ⚠️ {quatro}: nenhum código do _STATUS_PMIB termina assim, não sobe.")
        for quatro, codigos in ambiguas.items():
            self.log(f"   ⚠️ {quatro}: mais de uma ficha termina assim ({', '.join(codigos)}), não sobe.")
        if not fichas:
            self.avisar(t("Aviso"), t("Nenhuma foto da pasta corresponde a uma ficha do _STATUS_PMIB."), "aviso")
            return None
        fichas = self._escolher_fichas(fichas)
        if not fichas:
            self.log("Nenhuma ficha escolhida: nada foi feito.")
            return None
        resumo = t("{n} ficha(s) e {f} foto(s) para subir.", n=len(fichas),
                   f=sum(len(caminhos) for _p, _q, caminhos in fichas))
        if modo == svc.MODO_SUBSTITUIR:
            resumo += "\n\n" + t("As fotos que já estiverem nessas fichas serão EXCLUÍDAS antes.")
        if not self.perguntar_sim_nao(t("Confirmar"), resumo + "\n\n" + t("Começar?")):
            return None
        return fichas

    def _dialogo_de_fichas(self, fichas, ao_confirmar):
        """A janela das fichas da pasta: marca uma a uma, ou "Selecionar Todos"."""
        return dialogos_selecao.SelecaoMultiplaDialog(
            self, itens=[t("{pmib}  ({n} foto(s))", pmib=pmib, n=len(caminhos)) for pmib, _q, caminhos in fichas],
            titulo=t("Fichas para subir as fotos"),
            instrucao=t("Marque as fichas que vão receber as fotos:"),
            geometria="460x520", modal=True, com_selecionar_todos=True, devolver_indices=True,
            texto_confirmar=t("Subir nas marcadas"), ao_confirmar=ao_confirmar)

    def _escolher_fichas(self, fichas):
        """As fichas que a pessoa marcou (`[]` se fechou a janela). Roda na
        thread do robô; a janela abre na da interface."""
        escolhidas = []

        def abrir():
            self._dialogo_de_fichas(fichas, escolhidas.extend).esperar()
        self._na_interface_e_esperar(abrir, aviso=t("Marque as fichas na janela aberta."))
        return [fichas[i] for i in escolhidas]

    def parar(self) -> None:
        if self.automacao is not None:
            self.automacao.solicitar_parada()
            self.log("Parada solicitada: termino a ficha atual e paro.")

    def _perguntar(self, pmib, quantas):
        """A pergunta do modo "perguntar", da thread do robô."""
        def perguntar():
            caixa = QMessageBox(self)
            caixa.setWindowTitle(t("Ficha com fotos"))
            caixa.setText(t("A ficha {pmib} já tem {n} foto(s). O que fazer?", pmib=pmib, n=quantas))
            respostas = {
                caixa.addButton(t("Excluir e subir"), QMessageBox.ButtonRole.AcceptRole): svc.SUBSTITUIR,
                caixa.addButton(t("Adicionar"), QMessageBox.ButtonRole.YesRole): svc.ADICIONAR,
                caixa.addButton(t("Pular"), QMessageBox.ButtonRole.RejectRole): svc.PULAR,
            }
            caixa.exec()
            return respostas.get(caixa.clickedButton(), svc.PULAR)
        # Sem resposta (janela fechada à força): pular é o lado seguro.
        return self._na_interface_e_esperar(perguntar, aviso=t("Ficha com fotos: escolha o que fazer.")) or svc.PULAR

    def _worker(self, modo, fator) -> None:
        fichas = self._montar_lote(modo)
        if not fichas:
            return
        self.automacao = auto = svc.UploadFotosAutomation(esperas=svc.Esperas(fator=fator))
        self.log(f"Velocidade do portal: esperas x{fator}.")
        try:
            self.log("Iniciando navegador...")
            auto.iniciar_driver()
            auto.abrir_portal()
            self.pausar_e_esperar(t(MSG_LOGIN_LOTE))
            resultados = auto.processar(fichas, modo, self._perguntar, callback_log=self.log)
            ok = sum(1 for r in resultados if r.ok)
            self.log(f"Fotos: {ok} de {len(fichas)} ficha(s) concluídas.")
            _n, recado = svc.marcar_status(self.caminho_status, resultados,
                                           retry_lock=self.perguntar_retry_excel, callback_log=self.log)
            self.log(recado)
            self.avisar(t("Concluído"), t("{ok} de {n} ficha(s) com as fotos no portal.", ok=ok, n=len(fichas)))
        except Exception as erro:  # noqa: BLE001
            self.log(f"Erro Fatal: {type(erro).__name__}: {erro}")
        finally:
            auto.fechar_driver()
            self.automacao = None

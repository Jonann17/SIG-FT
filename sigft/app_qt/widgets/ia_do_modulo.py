"""A IA de cada módulo: IA Externa, IA Interna (AMP) ou Workflow AMP (2026-11-04).

Pedido do Luan: a escolha é por módulo e interativa. `PainelIaDoModulo` mostra os módulos
(quando há mais de um), os três modos e o conteúdo do modo escolhido:

- IA Externa: o catálogo do OpenRouter (os favoritos curados primeiro), o filtro de busca,
  "Atualizar catálogo" (numa thread) e "Chave do OpenRouter…";
- IA Interna (AMP): aparece desligada, até o AMP ter API;
- Workflow AMP: o endereço e a chave do webhook DAQUELE módulo.

A central (janela "Modelos de IA") e o botão "Configurar IA" de cada tela
(`instalar_configurar_ia`) usam este mesmo painel e gravam no mesmo lugar
(`core/llm/modo.py` + as chaves). Quando um grava, o outro, se aberto, se redesenha
(`avisos().mudou`). Desenho: `docs/superpowers/specs/2026-11-04-ia-por-modulo-design.md`.
"""
from __future__ import annotations

import threading
import weakref

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QStackedWidget, QVBoxLayout,
    QWidget,
)

from sigft import config
from sigft.app.ia_por_modulo import EXPLICACAO_DOS_MODOS, NOMES_DOS_MODOS, ROTULOS
from sigft.app.idioma import marcar, t
from sigft.app_qt import estilo, icones, interface, propriedades
from sigft.app_qt.widgets import blocos, dialogs
from sigft.app_qt.widgets.webhook_amp import ROTULO_CHAVE, ROTULO_ENDERECO, problema_do_endereco
from sigft.core.llm import catalogo, modo

TITULO_CENTRAL = marcar("IA por módulo")
TITULO_JANELA = marcar("Configurar IA")
TEXTO_BOTAO = marcar("Configurar IA")
DICA_BOTAO = marcar("Escolhe a IA deste módulo: IA Externa (OpenRouter) ou Workflow AMP.")
DICA_INTERNA = marcar("Em breve: o AMP ainda não tem API para escolher um modelo.")
EXPLICACAO_CENTRAL = marcar("Clique num módulo e escolha a IA dele. O botão \"Configurar IA\" de cada "
                            "tela abre esta mesma escolha.")
TEXTO_FILTRO = marcar("Filtrar modelos:")
DICA_FILTRO = marcar("ex.: flash, haiku, minimax (vazio mostra todos)")
TEXTO_ATUALIZAR = marcar("Atualizar catálogo")
TEXTO_MANUAL = marcar("Modelo manual:")
DICA_MANUAL = marcar("id exato do OpenRouter, se não estiver na lista (ex.: meta-llama/llama-4)")
TEXTO_CHAVE_OPENROUTER = marcar("Chave do OpenRouter...")
TEXTO_SALVAR = marcar("Salvar")
TEXTO_FECHAR = marcar("Fechar")
SEM_CHAVE_OPENROUTER = marcar("Sem a chave do OpenRouter: configure-a para ver o catálogo.")
BUSCANDO = marcar("Buscando o catálogo do OpenRouter...")
CATALOGO_COM = marcar("{n} modelos no catálogo.")
CATALOGO_FALHOU = marcar("Não deu para atualizar o catálogo: {erro}")
ESCOLHA_UM_MODELO = marcar("Escolha um modelo da lista.")
SALVO_EXTERNA = marcar("Salvo: {rotulo} usa {modelo}.")
SALVO_WORKFLOW = marcar("Salvo: {rotulo} usa o Workflow AMP.")
VALENDO_EXTERNA = marcar("Valendo agora: IA Externa, {modelo}.")
VALENDO_PADRAO = marcar("Valendo agora: o modelo padrão do sistema.")
VALENDO_WORKFLOW = marcar("Valendo agora: Workflow AMP.")


class _Avisos(QObject):
    mudou = Signal(str)   # a tarefa cuja IA foi gravada


_AVISOS: list[_Avisos] = []


def avisos() -> _Avisos:
    """O aviso de "a IA desta tarefa mudou", um só para o app (criado na primeira vez)."""
    if not _AVISOS:
        _AVISOS.append(_Avisos())
    return _AVISOS[0]


def _caminho_config() -> str:
    return config.CONFIG_FILE


class PainelIaDoModulo(QWidget):
    """Os módulos (se mais de um), os três modos e o conteúdo do modo. `controller` dá as
    chaves (`get_key`, `save_keys`, `api_keys`); `abrir_chaves()` abre o painel de chaves."""

    def __init__(self, controller, tarefas, *, abrir_chaves=None, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.tarefas = tuple(tarefas)
        self._abrir_chaves = abrir_chaves
        self.tarefa = self.tarefas[0]
        self.modo = modo.EXTERNA
        self._modelos: list[tuple[str, str]] = []   # (rótulo, id)
        self._catalogo_baixado = None
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(16)

        self.lista_modulos = None
        if len(self.tarefas) > 1:
            self.lista_modulos = QListWidget(objectName="ia_modulos")
            self.lista_modulos.setFixedWidth(260)
            for tarefa in self.tarefas:
                item = QListWidgetItem(t(ROTULOS.get(tarefa, tarefa)).rstrip(":"))
                item.setData(Qt.ItemDataRole.UserRole, tarefa)
                self.lista_modulos.addItem(item)
            self.lista_modulos.currentRowChanged.connect(self._trocou_modulo)
            raiz.addWidget(self.lista_modulos)

        coluna = QVBoxLayout()
        coluna.setSpacing(8)
        raiz.addLayout(coluna, 1)
        self.lbl_modulo = blocos.rotulo("", tamanho=15, negrito=True, papel="destaque", alinhar="esquerda")
        coluna.addWidget(self.lbl_modulo)

        linha = QHBoxLayout()
        linha.setSpacing(4)
        self.botoes_modo = {}
        for chave in modo.MODOS:
            botao = blocos.botao(t(NOMES_DOS_MODOS[chave]), variante="secundario", tamanho_fonte=12)
            botao.setProperty("escolha", chave)
            dialogs.sem_tecla(botao)
            if chave in modo.SELECIONAVEIS:
                botao.clicked.connect(self._clicou_modo)
            else:
                botao.setEnabled(False)
                botao.setToolTip(t(DICA_INTERNA))
            self.botoes_modo[chave] = botao
            linha.addWidget(botao)
        linha.addStretch()
        coluna.addLayout(linha)
        self.lbl_explicacao = blocos.rotulo("", papel="legenda", alinhar="esquerda")
        self.lbl_explicacao.setWordWrap(True)
        coluna.addWidget(self.lbl_explicacao)

        self.paginas = QStackedWidget()
        self.pagina_externa = self._montar_externa()
        self.pagina_interna = self._montar_interna()
        self.pagina_workflow = self._montar_workflow()
        for pagina in (self.pagina_externa, self.pagina_interna, self.pagina_workflow):
            self.paginas.addWidget(pagina)
        coluna.addWidget(self.paginas, 1)

        rodape = QHBoxLayout()
        self.lbl_status = blocos.rotulo("", papel="legenda", alinhar="esquerda")
        self.lbl_status.setWordWrap(True)
        rodape.addWidget(self.lbl_status, 1)
        self.botao_salvar = blocos.botao(t(TEXTO_SALVAR), variante="primario", largura=120, negrito=True)
        self.botao_salvar.clicked.connect(self.salvar)
        rodape.addWidget(self.botao_salvar)
        coluna.addLayout(rodape)

        avisos().mudou.connect(self._outro_gravou)
        if self.lista_modulos is not None:
            self.lista_modulos.setCurrentRow(0)
        else:
            self._mostrar_tarefa(self.tarefa)

    # -- montagem ---------------------------------------------------------------------
    def _montar_externa(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        linha = QHBoxLayout()
        linha.addWidget(blocos.rotulo(t(TEXTO_FILTRO), alinhar="esquerda"))
        self.campo_filtro = QLineEdit()
        self.campo_filtro.setPlaceholderText(t(DICA_FILTRO))
        self.campo_filtro.textChanged.connect(self._refiltrar)
        linha.addWidget(self.campo_filtro, 1)
        self.botao_atualizar = blocos.botao(t(TEXTO_ATUALIZAR), variante="secundario")
        icones.aplicar(self.botao_atualizar, "refresh-cw")
        self.botao_atualizar.clicked.connect(self.atualizar_catalogo)
        linha.addWidget(self.botao_atualizar)
        self.botao_chave = blocos.botao(t(TEXTO_CHAVE_OPENROUTER), variante="secundario")
        icones.aplicar(self.botao_chave, "key-round")
        self.botao_chave.clicked.connect(self._clicou_chave)
        linha.addWidget(self.botao_chave)
        lay.addLayout(linha)
        self.lista_modelos = QListWidget(objectName="ia_modelos")
        self.lista_modelos.setMinimumHeight(120)
        lay.addWidget(self.lista_modelos, 1)
        self.lbl_catalogo = blocos.rotulo("", papel="legenda", alinhar="esquerda")
        lay.addWidget(self.lbl_catalogo)
        # [2026-11-05] Veio do painel de antes (que saiu): um id do OpenRouter que ainda
        # não está no catálogo baixado. Preenchido, vale ele, e não o da lista.
        manual = QHBoxLayout()
        manual.addWidget(blocos.rotulo(t(TEXTO_MANUAL), alinhar="esquerda"))
        self.campo_manual = QLineEdit()
        self.campo_manual.setPlaceholderText(t(DICA_MANUAL))
        manual.addWidget(self.campo_manual, 1)
        lay.addLayout(manual)
        return pagina

    def _montar_interna(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(blocos.rotulo(t(DICA_INTERNA), papel="legenda", alinhar="esquerda"))
        lay.addStretch()
        return pagina

    def _montar_workflow(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(blocos.rotulo(t(ROTULO_ENDERECO), alinhar="esquerda"))
        self.campo_url = QLineEdit()
        lay.addWidget(self.campo_url)
        lay.addWidget(blocos.rotulo(t(ROTULO_CHAVE), alinhar="esquerda"))
        self.campo_chave = QLineEdit()
        self.campo_chave.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_chave.setStyleSheet("lineedit-password-character: 42;")
        lay.addWidget(self.campo_chave)
        lay.addStretch()
        return pagina

    # -- o módulo e o modo -----------------------------------------------------------------
    def _trocou_modulo(self, linha: int) -> None:
        if 0 <= linha < len(self.tarefas):
            self._mostrar_tarefa(self.tarefas[linha])

    def selecionar_tarefa(self, tarefa: str) -> None:
        if self.lista_modulos is not None and tarefa in self.tarefas:
            self.lista_modulos.setCurrentRow(self.tarefas.index(tarefa))
        else:
            self._mostrar_tarefa(tarefa)

    def _mostrar_tarefa(self, tarefa: str) -> None:
        """Lê o que vale AGORA para a tarefa (a fonte é o `api_config.json`)."""
        self.tarefa = tarefa
        self.lbl_modulo.setText(t(ROTULOS.get(tarefa, tarefa)).rstrip(":"))
        caminho = _caminho_config()
        self._externo = modo.modelo_externo(tarefa, config_path=caminho)
        self.campo_manual.clear()
        nome_url, nome_chave = modo.chaves_do_webhook(tarefa)
        self.campo_url.setText(self._chave(nome_url))
        self.campo_chave.setText(self._chave(nome_chave))
        self._recarregar_modelos()
        self._escolher_modo(modo.modo_da_tarefa(tarefa, config_path=caminho))
        self.lbl_status.setText(self._valendo())

    def _clicou_modo(self) -> None:
        botao = self.sender()
        escolha = propriedades.ler(botao, "escolha") if botao is not None else None
        if escolha in modo.SELECIONAVEIS:
            self._escolher_modo(escolha)

    def _escolher_modo(self, escolha: str) -> None:
        self.modo = escolha
        for chave, botao in self.botoes_modo.items():
            estilo.definir_variante(botao, "primario" if chave == escolha else "secundario")
        self.lbl_explicacao.setText(t(EXPLICACAO_DOS_MODOS[escolha]))
        self.paginas.setCurrentWidget({modo.EXTERNA: self.pagina_externa, modo.INTERNA: self.pagina_interna,
                                       modo.WORKFLOW: self.pagina_workflow}[escolha])

    def _valendo(self) -> str:
        if modo.modo_da_tarefa(self.tarefa, config_path=_caminho_config()) == modo.WORKFLOW:
            return t(VALENDO_WORKFLOW)
        if self._externo:
            return t(VALENDO_EXTERNA, modelo=self._externo["model"])
        return t(VALENDO_PADRAO)

    def _chave(self, nome: str) -> str:
        if self.controller is None:
            return ""
        return (self.controller.get_key(nome) or "").strip()

    # -- o catálogo ------------------------------------------------------------------------
    def _recarregar_modelos(self, *, erro: str | None = None) -> None:
        provider = config.PROVIDER_OPENROUTER
        recomendados = catalogo.modelos_recomendados(provider)
        pares = [(f"{fav.get('rotulo') or fav['model']}", fav["model"]) for fav in recomendados]
        vistos = {fav["model"] for fav in recomendados}
        chaves = dict(getattr(self.controller, "api_keys", {}) or {})
        achado = catalogo.consultar(provider, chaves, somente_cache=True)
        for model_id in achado.modelos:
            if model_id not in vistos:
                pares.append((model_id, model_id))
                vistos.add(model_id)
        self._modelos = pares
        if erro:
            self.lbl_catalogo.setText(t(CATALOGO_FALHOU, erro=erro))
        elif not self._chave(config.CHAVE_POR_PROVIDER[provider]):
            self.lbl_catalogo.setText(t(SEM_CHAVE_OPENROUTER))
        else:
            self.lbl_catalogo.setText(t(CATALOGO_COM, n=len(achado.modelos)))
        self._refiltrar()

    def _refiltrar(self, *_args) -> None:
        filtro = self.campo_filtro.text().strip().lower()
        atual = self.modelo_escolhido() or ((self._externo or {}).get("model")
                                            if getattr(self, "_externo", None) else None)
        self.lista_modelos.clear()
        for rotulo, model_id in self._modelos:
            if filtro and filtro not in rotulo.lower() and filtro not in model_id.lower():
                continue
            item = QListWidgetItem(rotulo if rotulo == model_id else f"{rotulo}  ({model_id})")
            item.setData(Qt.ItemDataRole.UserRole, model_id)
            self.lista_modelos.addItem(item)
            if model_id == atual:
                self.lista_modelos.setCurrentItem(item)

    def modelo_escolhido(self) -> str | None:
        manual = self.campo_manual.text().strip() if hasattr(self, "campo_manual") else ""
        if manual:
            return manual
        item = self.lista_modelos.currentItem() if hasattr(self, "lista_modelos") else None
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def atualizar_catalogo(self) -> None:
        """Busca o catálogo do OpenRouter numa thread `daemon` (a rede nunca na interface)."""
        self.lbl_catalogo.setText(t(BUSCANDO))
        chaves = dict(getattr(self.controller, "api_keys", {}) or {})
        threading.Thread(target=self._buscar_catalogo, args=(chaves,), daemon=True,
                         name="sigft-catalogo-ia-modulo").start()

    def _buscar_catalogo(self, chaves) -> None:
        resultado = None
        try:
            resultado = catalogo.consultar(config.PROVIDER_OPENROUTER, chaves, forcar=True)
        finally:
            self._catalogo_baixado = resultado
            interface.na_interface(self._catalogo_chegou)

    def _catalogo_chegou(self) -> None:
        resultado = self._catalogo_baixado
        self._recarregar_modelos(erro=resultado.erro if resultado is not None else None)

    def _clicou_chave(self) -> None:
        if self._abrir_chaves is not None:
            self._abrir_chaves()

    # -- gravar ----------------------------------------------------------------------------
    def salvar(self) -> bool:
        """Grava o modo da tarefa. `False` (com o motivo no status) quando falta algo."""
        rotulo = t(ROTULOS.get(self.tarefa, self.tarefa)).rstrip(":")
        caminho = _caminho_config()
        if self.modo == modo.WORKFLOW:
            problema = problema_do_endereco(self.campo_url.text())
            if problema:
                estilo.definir_papel(self.lbl_status, "erro")
                self.lbl_status.setText(problema)
                return False
            nome_url, nome_chave = modo.chaves_do_webhook(self.tarefa)
            if self.controller is not None:
                self.controller.save_keys({nome_url: self.campo_url.text().strip(),
                                           nome_chave: self.campo_chave.text().strip()})
            modo.definir_workflow(self.tarefa, config_path=caminho)
            texto = t(SALVO_WORKFLOW, rotulo=rotulo)
        else:
            modelo = self.modelo_escolhido()
            if not modelo:
                estilo.definir_papel(self.lbl_status, "erro")
                self.lbl_status.setText(t(ESCOLHA_UM_MODELO))
                return False
            modo.definir_externa(self.tarefa, modelo, config_path=caminho)
            self._externo = {"provider": config.PROVIDER_OPENROUTER, "model": modelo}
            texto = t(SALVO_EXTERNA, rotulo=rotulo, modelo=modelo)
        estilo.definir_papel(self.lbl_status, None)
        self.lbl_status.setText(texto)
        self._gravando = True
        try:
            avisos().mudou.emit(self.tarefa)
        finally:
            self._gravando = False
        return True

    def _outro_gravou(self, tarefa: str) -> None:
        """Outra porta (a central ou a da tela) gravou: redesenha se é a tarefa mostrada."""
        if getattr(self, "_gravando", False) or tarefa != self.tarefa:
            return
        self._mostrar_tarefa(tarefa)


class JanelaIaDoModulo(QDialog):
    """O mesmo painel, só com as tarefas de uma tela, e "Fechar"."""

    def __init__(self, parent, controller, tarefas, *, abrir_chaves=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t(TITULO_JANELA))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        self.painel = PainelIaDoModulo(controller, tarefas, abrir_chaves=abrir_chaves, parent=self)
        lay.addWidget(self.painel, 1)
        linha = QHBoxLayout()
        linha.addStretch()
        self.botao_fechar = blocos.botao(t(TEXTO_FECHAR), variante="secundario", largura=120)
        self.botao_fechar.clicked.connect(self.accept)
        linha.addWidget(self.botao_fechar)
        lay.addLayout(linha)
        self.resize(760 if len(tuple(tarefas)) == 1 else 960, 480)


class _AbreConfigurarIa(QObject):
    """O clique do botão "Configurar IA" de uma tela (um objeto, e não uma `lambda` com a
    tela: a lambda seguraria a tela num ciclo)."""

    def __init__(self, tela, tarefas) -> None:
        super().__init__(tela)
        # Fraca: a tela já segura este objeto (`_abre_configurar_ia`); forte de volta
        # seria um ciclo, e a tela só morreria com o coletor (ver `widgets/fraco.py`).
        self._ref_tela = weakref.ref(tela)
        self._tarefas = tuple(tarefas)

    def abrir(self) -> JanelaIaDoModulo | None:
        tela = self._ref_tela()
        if tela is None:
            return None
        controller = getattr(tela, "controller", None)
        home = getattr(controller, "_home_view", None)
        home = home() if callable(home) else None
        abrir_chaves = getattr(home, "abrir_janela_chaves_api", None)
        janela = JanelaIaDoModulo(tela.window(), controller, self._tarefas, abrir_chaves=abrir_chaves)
        tela.janela_configurar_ia = janela
        janela.open()
        return janela


def instalar_configurar_ia(tela, tarefas):
    """Põe "Configurar IA" na linha do título do `ModuleFrame`, à direita (não soma altura).
    Tela embutida (sem cabeçalho) não ganha o botão: devolve `None`."""
    titulo = getattr(tela, "label_titulo", None)
    header = getattr(tela, "header", None)
    if header is None or titulo is None or not tarefas:
        return None
    cabecalho = header.layout()
    indice = cabecalho.indexOf(titulo)
    linha_widget = QWidget()
    linha = QHBoxLayout(linha_widget)
    linha.setContentsMargins(0, 0, 0, 0)
    cabecalho.removeWidget(titulo)
    linha.addWidget(titulo, 1)
    botao = blocos.botao(t(TEXTO_BOTAO), variante="secundario", tamanho_fonte=12, altura=26)
    icones.aplicar(botao, "bot")
    botao.setToolTip(t(DICA_BOTAO))
    dialogs.sem_tecla(botao)
    abridor = _AbreConfigurarIa(tela, tarefas)
    botao.clicked.connect(abridor.abrir)
    linha.addWidget(botao, 0, Qt.AlignmentFlag.AlignVCenter)
    cabecalho.insertWidget(max(indice, 0), linha_widget)
    tela.botao_configurar_ia = botao
    tela._abre_configurar_ia = abridor
    return botao

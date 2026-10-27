"""Colunas lembradas nas tabelas (2026-10-26).

Arrastar o cabeçalho troca a ordem; arrastar a borda muda a largura; o botão
direito no cabeçalho abre um menu para esconder e mostrar cada coluna, e
"Restaurar colunas". Fica nas preferências (`core/prefs`, seção `colunas`) pela
chave da tabela e pela chave INTERNA de cada coluna: o texto do cabeçalho muda
com o idioma, a chave não.

`juntar` (função pura) casa o que foi guardado com as colunas de agora: coluna
que deixou de existir é ignorada; coluna nova entra no fim, visível; preferência
estragada vale o padrão (`None`). A última coluna visível não se esconde.

Na tabela com `EsticaColunas` (`dialogos_selecao.tabela_ttk`, a sobra repartida
igual), mexer nas colunas o desliga e a última coluna passa a esticar; o
"Restaurar colunas" o religa.

A coluna que ESTICA (a última visível, com `stretchLastSection`) não tem largura
de quem usa: a dela é a sobra da janela. Não se registra nem se grava (vai
`largura: None`, e ao reabrir ela fica com a de nascença e volta a esticar) --
senão a sobra de uma janela larga virava barra horizontal numa janela estreita,
e cada redimensionamento da janela regravava as preferências.

Uso: `instalar_colunas(tabela, "selecao_duplicadas", ("descricao", ...))`.
"""
from __future__ import annotations

from typing import NamedTuple, Sequence

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QMenu, QTreeView

from sigft.app.idioma import marcar, t

TEXTO_RESTAURAR = marcar("Restaurar colunas")
# Arrastar a borda solta dezenas de `sectionResized`: grava uma vez, quando para.
MS_PARA_GRAVAR = 400


class Coluna(NamedTuple):
    chave: str
    largura: int | None
    visivel: bool


def _largura(valor: object) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        return None
    return valor


def juntar(guardado: object, colunas: Sequence[str]) -> list[Coluna] | None:
    """A ordem, a largura e a visibilidade de `colunas` (as chaves internas de
    agora) segundo `guardado` (o que `descrever` gravou). `None`: nada que sirva,
    vale o padrão da tabela."""
    if not isinstance(guardado, list):
        return None
    existentes = set(colunas)
    vistas: set[str] = set()
    lista: list[Coluna] = []
    for item in guardado:
        if not isinstance(item, dict):
            continue
        chave = item.get("chave")
        if not isinstance(chave, str) or chave not in existentes or chave in vistas:
            continue
        vistas.add(chave)
        visivel = item.get("visivel")
        lista.append(Coluna(chave, _largura(item.get("largura")),
                            visivel if isinstance(visivel, bool) else True))
    if not lista:
        return None
    lista += [Coluna(chave, None, True) for chave in colunas if chave not in vistas]
    if not any(coluna.visivel for coluna in lista):
        lista[0] = lista[0]._replace(visivel=True)
    return lista


def descrever(colunas: Sequence[Coluna]) -> list[dict]:
    """O que vai para as preferências (JSON), na ordem da tela."""
    return [{"chave": c.chave, "largura": c.largura, "visivel": c.visivel} for c in colunas]


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta de
    dados. Função para os testes apontarem outro arquivo."""
    return None


def _ler(chave: str) -> object:
    from sigft.core import prefs

    try:
        return prefs.ler_colunas(chave, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return None


def _gravar(chave: str, valor: object) -> None:
    from sigft.core import prefs

    try:
        prefs.gravar_colunas(chave, valor, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar a tabela
        pass


class ColunasLembradas(QObject):
    """Liga o cabeçalho de `tabela` às preferências. Filho da tabela: morre com ela."""

    def __init__(self, tabela: QTreeView, chave: str, colunas: Sequence[str]) -> None:
        super().__init__(tabela)
        self._tabela = tabela
        self.chave = chave
        self.colunas = [str(c) for c in colunas]
        self._cabecalho = tabela.header()
        self._aplicando = False
        self._estica_ultima = self._cabecalho.stretchLastSection()
        self._padrao = {i: self._cabecalho.sectionSize(i) for i in range(len(self.colunas))}
        self._larguras = dict(self._padrao)
        self._gravar_depois = QTimer(self)
        self._gravar_depois.setSingleShot(True)
        self._gravar_depois.setInterval(MS_PARA_GRAVAR)
        self._gravar_depois.timeout.connect(self.gravar)

        cabecalho = self._cabecalho
        cabecalho.setSectionsMovable(True)
        cabecalho.setFirstSectionMovable(True)
        cabecalho.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        cabecalho.customContextMenuRequested.connect(self._abrir_menu)
        cabecalho.sectionMoved.connect(self._mexeu)
        cabecalho.sectionResized.connect(self._redimensionou)
        # A janela que fecha antes do relógio grava o que esperava (Hide).
        tabela.installEventFilter(self)
        self.aplicar(juntar(_ler(chave), self.colunas))

    # -- estado -----------------------------------------------------------------------
    def _esticador(self):
        return getattr(self._tabela, "esticar_colunas", None)

    def _ocupado(self) -> bool:
        """A mudança é do programa (aplicando, ou o `EsticaColunas`), não de quem usa."""
        return self._aplicando or bool(getattr(self._esticador(), "ajustando", False))

    def estado(self) -> list[Coluna]:
        """As colunas na ordem da tela, com a última largura vista de cada uma."""
        cabecalho = self._cabecalho
        lista = []
        for posicao in range(len(self.colunas)):
            logico = cabecalho.logicalIndex(posicao)
            lista.append(Coluna(self.colunas[logico], self._larguras.get(logico),
                                not cabecalho.isSectionHidden(logico)))
        return lista

    def _que_estica(self) -> int | None:
        """O índice lógico da coluna que estica (a última visível), ou `None`
        se nenhuma estica."""
        cabecalho = self._cabecalho
        if not cabecalho.stretchLastSection():
            return None
        for posicao in range(cabecalho.count() - 1, -1, -1):
            logico = cabecalho.logicalIndex(posicao)
            if not cabecalho.isSectionHidden(logico):
                return logico
        return None

    def _para_gravar(self) -> list[Coluna]:
        """O `estado()` sem a largura da coluna que estica (é a sobra da janela)."""
        estica = self._que_estica()
        cabecalho = self._cabecalho
        lista = []
        for posicao, coluna in enumerate(self.estado()):
            if cabecalho.logicalIndex(posicao) == estica:
                coluna = coluna._replace(largura=None)
            lista.append(coluna)
        return lista

    def _logicos(self, lista: Sequence[Coluna], padrao: bool) -> list[int]:
        """O índice lógico de cada item de `lista`. Chave repetida pega a próxima
        coluna com aquele nome, não sempre a primeira."""
        if padrao:
            return list(range(len(lista)))
        livres: dict[str, list[int]] = {}
        for logico, chave in enumerate(self.colunas):
            livres.setdefault(chave, []).append(logico)
        return [livres[coluna.chave].pop(0) for coluna in lista]

    def _soltar_esticador(self) -> None:
        """Daqui em diante vale a largura de quem mexeu: a sobra repartida igual
        (`EsticaColunas`) para, e a última coluna estica."""
        esticador = self._esticador()
        if esticador is not None and esticador.ligado:
            esticador.desligar()
        if not self._cabecalho.stretchLastSection():
            antes, self._aplicando = self._aplicando, True
            try:
                self._cabecalho.setStretchLastSection(True)
            finally:
                self._aplicando = antes

    def aplicar(self, lista: list[Coluna] | None) -> None:
        """Põe a tabela como `lista` diz; `None` é o padrão (a ordem e as larguras
        de nascença, tudo visível, a sobra repartida como antes)."""
        cabecalho = self._cabecalho
        padrao = lista is None
        if lista is None:
            lista = [Coluna(c, self._padrao.get(i), True) for i, c in enumerate(self.colunas)]
        self._aplicando = True
        try:
            for posicao, (coluna, logico) in enumerate(zip(lista, self._logicos(lista, padrao))):
                if cabecalho.visualIndex(logico) != posicao:
                    cabecalho.moveSection(cabecalho.visualIndex(logico), posicao)
                if coluna.largura:
                    cabecalho.resizeSection(logico, coluna.largura)
                    self._larguras[logico] = coluna.largura
                cabecalho.setSectionHidden(logico, not coluna.visivel)
            if padrao:
                cabecalho.setStretchLastSection(self._estica_ultima)
                esticador = self._esticador()
                if esticador is not None:
                    esticador.ligar()
            else:
                self._soltar_esticador()
        finally:
            self._aplicando = False

    # -- o que quem usa faz --------------------------------------------------------------
    def _redimensionou(self, logico: int, _antes: int, agora: int) -> None:
        if logico == self._que_estica():
            return   # a sobra da janela, não a largura de quem usa
        if agora > 0 and logico < len(self.colunas):
            self._larguras[logico] = agora
        if self._ocupado() or agora <= 0:
            return
        self._soltar_esticador()
        self._gravar_depois.start()

    def _mexeu(self, *_args) -> None:
        if self._ocupado():
            return
        self._soltar_esticador()
        self._gravar_depois.start()

    def mostrar_coluna(self, chave: str, visivel: bool) -> bool:
        """Mostra ou esconde a coluna `chave` e grava. A última visível não se
        esconde: devolve `False` e nada muda."""
        return self._mostrar_logico(self.colunas.index(chave), visivel)

    def _mostrar_logico(self, logico: int, visivel: bool) -> bool:
        cabecalho = self._cabecalho
        visiveis = [i for i in range(len(self.colunas)) if not cabecalho.isSectionHidden(i)]
        if not visivel and visiveis == [logico]:
            return False
        self._aplicando = True
        try:
            cabecalho.setSectionHidden(logico, not visivel)
        finally:
            self._aplicando = False
        self._soltar_esticador()
        self.gravar()
        return True

    def gravar(self) -> None:
        self._gravar_depois.stop()
        _gravar(self.chave, descrever(self._para_gravar()))

    def restaurar(self, *_args) -> None:
        """"Restaurar colunas": esquece o guardado e volta ao padrão."""
        self._gravar_depois.stop()
        _gravar(self.chave, None)
        self.aplicar(None)

    # -- o menu do botão direito -------------------------------------------------------
    def montar_menu(self) -> QMenu:
        """Uma linha marcável por coluna (na ordem da tela) e "Restaurar colunas"."""
        menu = QMenu(self._cabecalho)
        cabecalho = self._cabecalho
        estado = self.estado()
        visiveis = [c for c in estado if c.visivel]
        modelo = self._tabela.model()
        for posicao, coluna in enumerate(estado):
            # O dado da ação é o índice LÓGICO: com duas colunas de mesmo nome,
            # `colunas.index(chave)` apontaria sempre a primeira.
            logico = cabecalho.logicalIndex(posicao)
            texto = str(modelo.headerData(logico, Qt.Orientation.Horizontal) or coluna.chave)
            acao = menu.addAction(texto)
            acao.setCheckable(True)
            acao.setChecked(coluna.visivel)
            acao.setData(logico)
            acao.setEnabled(not (coluna.visivel and len(visiveis) == 1))
            acao.toggled.connect(self._marcou)
        menu.addSeparator()
        restaurar = menu.addAction(t(TEXTO_RESTAURAR))
        restaurar.triggered.connect(self.restaurar)
        return menu

    def _marcou(self, marcado: bool) -> None:
        acao = self.sender()
        if acao is not None:
            self._mostrar_logico(int(acao.data()), marcado)

    def _abrir_menu(self, posicao) -> None:
        menu = self.montar_menu()
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.popup(self._cabecalho.mapToGlobal(posicao))

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() == QEvent.Type.Hide and self._gravar_depois.isActive():
            self.gravar()
        return False


def instalar_colunas(tabela: QTreeView, chave: str, colunas: Sequence[str]) -> ColunasLembradas:
    """Liga as colunas lembradas em `tabela` numa linha. `colunas`: a chave interna
    de cada coluna, na ordem lógica (a de criação)."""
    lembradas = ColunasLembradas(tabela, chave, colunas)
    tabela.colunas_lembradas = lembradas
    return lembradas

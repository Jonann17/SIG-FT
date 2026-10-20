"""A janela "Revisão antes do portal" (R2) e a função que as quatro telas de robô chamam.

No clique do robô, ANTES de abrir o navegador, cada tela confere a lista que ia
para ele (`sigft.core.pmib_regras.conferir_<robô>`) e passa os problemas para
`conferir_antes_do_portal`. Sem problema, nada aparece e a lista segue inteira.
Com problema, o relatório vai para o console (uma linha por problema) e a
janela diz o que deu erro e onde; a pessoa escolhe:

* **Seguir sem as fichas com erro** (padrão, Enter);
* **Seguir com todas** (o portal continua sendo o juiz);
* **Cancelar** (Esc ou "X"): o robô não abre.

Só FILTRA: os dados que seguem vão ao robô como vieram. Só da thread da
interface (é um `exec()` modal); a tela que confere num worker chama por
`_na_interface_e_esperar`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout

from sigft.app import theme
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.dialogos_selecao import linha_ttk, tabela_ttk
from sigft.core import pmib_regras

TITULO = "Revisão antes do portal"
SEM_ERROS = "sem_erros"
TODAS = "todas"
TEXTO_SEM_ERROS = "Seguir sem as fichas com erro"
TEXTO_TODAS = "Seguir com todas"
TEXTO_CANCELAR = "Cancelar"
EXPLICACAO = ("O portal deve recusar os campos abaixo. Nada foi corrigido: "
              "o robô recebe os dados como vieram.")
MSG_CANCELADO = "Cancelado na revisão antes do portal."
MSG_TODAS = "Seguindo com todas as fichas, inclusive as com erro."
MSG_NADA_SOBROU = "Todas as fichas têm erro: nenhuma vai ao portal, e o robô não abre."
# Ficha | Campo | Valor | O que o portal vai recusar (as larguras esticam com a janela).
COLUNAS = [("Ficha", 160, "w"), ("Campo", 250, "w"), ("Valor", 180, "w"),
           ("O que o portal vai recusar", 490, "w")]
GEOMETRIA = "1150x520"
LARGURA_BOTAO = 210


class RevisaoAntesDoPortalDialog(QDialog):
    """Modal. `decisao`: `SEM_ERROS`, `TODAS` ou `None` (Cancelar, Esc, "X")."""

    def __init__(self, parent, problemas, total: int) -> None:
        super().__init__(parent)
        self.decisao: str | None = None
        self.setWindowTitle(TITULO)
        self.resize(*blocos.geometria_tk(GEOMETRIA))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setModal(True)
        problemas = list(problemas)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(0)
        self.titulo = self._rotulo(TITULO, theme.FONTE_SECAO)
        layout.addWidget(self.titulo)
        self.contagem = self._rotulo(pmib_regras.resumo(problemas, total), theme.FONTE_CORPO)
        layout.addWidget(self.contagem)
        self.explicacao = self._rotulo(EXPLICACAO, theme.FONTE_CORPO_MIUDO, papel="legenda")
        layout.addWidget(self.explicacao)
        layout.addSpacing(10)

        self.tabela = tabela_ttk(COLUNAS, selecao="browse")
        for p in problemas:
            item = linha_ttk(self.tabela, [p.ficha, f"{p.campo} ({p.interno})", p.valor, p.mensagem])
            for coluna, texto in enumerate((p.ficha, f"{p.campo} ({p.interno})", p.valor, p.mensagem)):
                item.setToolTip(coluna, texto)
        quadro = QHBoxLayout()
        quadro.setContentsMargins(10, 0, 10, 0)
        quadro.addWidget(self.tabela)
        layout.addLayout(quadro, 1)
        layout.addSpacing(20)

        self.botoes = [
            self._botao(TEXTO_SEM_ERROS, SEM_ERROS, variante="primario"),
            self._botao(TEXTO_TODAS, TODAS),
            self._botao(TEXTO_CANCELAR, None, variante="secundario"),
        ]
        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(20)
        linha.addStretch()
        for b in self.botoes:
            linha.addWidget(b)
        linha.addStretch()
        layout.addLayout(linha)

    @staticmethod
    def _rotulo(texto: str, fonte: tuple, *, papel: str | None = None) -> QLabel:
        r = QLabel(texto)
        if papel:
            r.setProperty("papel", papel)
        r.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r.setWordWrap(True)
        r.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        r.setStyleSheet(f"QLabel {{ {blocos.folha_fonte_tk(fonte)} background: transparent; }}")
        return r

    def _botao(self, texto: str, decisao: str | None, *, variante: str | None = None):
        b = blocos.botao(texto, variante=variante, largura=LARGURA_BOTAO, altura=28)
        b.clicked.connect(lambda: self._decidir(decisao))
        return b

    def _decidir(self, decisao: str | None) -> None:
        self.decisao = decisao
        if decisao is None:
            self.reject()
        else:
            self.accept()

    def keyPressEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # Os botões não pegam foco (`blocos.sem_tecla`): o Enter é daqui. Esc
        # já é `reject()` no QDialog, e `decisao` continua None.
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            evento.accept()
            self._decidir(SEM_ERROS)
            return
        super().keyPressEvent(evento)


def perguntar_revisao(parent, problemas, total: int) -> str | None:
    """Abre a janela (modal) e devolve `SEM_ERROS`, `TODAS` ou `None`."""
    dialogo = RevisaoAntesDoPortalDialog(parent, problemas, total)
    try:
        dialogo.exec()
        return dialogo.decisao
    finally:
        dialogo.deleteLater()


def conferir_antes_do_portal(parent, problemas, total: int, log, *, perguntar=None) -> list[int] | None:
    """As POSIÇÕES (0..total-1) das fichas que seguem para o robô, ou `None`
    quando nada segue (Cancelar, ou todas com erro e a pessoa escolheu tirá-las).

    Sem problema: todas seguem, sem janela e sem log. Com problema: o relatório
    no console (`log`, uma linha por problema), a janela (`perguntar`, que os
    testes trocam) e uma linha dizendo o que foi decidido.
    """
    problemas = list(problemas)
    todas = list(range(total))
    if not problemas:
        return todas
    log(f"{TITULO}: {pmib_regras.resumo(problemas, total)}.")
    for p in problemas:
        log(pmib_regras.linha_do_console(p))
    decisao = (perguntar or perguntar_revisao)(parent, problemas, total)
    if decisao is None:
        log(MSG_CANCELADO)
        return None
    if decisao == TODAS:
        log(MSG_TODAS)
        return todas
    com_erro = pmib_regras.fichas_com_erro(problemas)
    seguem = [i for i in todas if i not in com_erro]
    if not seguem:
        log(MSG_NADA_SOBROU)
        QMessageBox.warning(parent, TITULO, MSG_NADA_SOBROU)
        return None
    log(f"Seguindo sem as {len(com_erro)} ficha(s) com erro: {len(seguem)} vão ao portal.")
    return seguem

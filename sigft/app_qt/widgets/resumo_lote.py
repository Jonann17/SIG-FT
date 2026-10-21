"""A janela "Resumo" do fim do lote (2026-10-21, etapa 1b).

Abre sozinha quando a ÚLTIMA tarefa da tela acaba e ela escreveu erro ou aviso no
console (`ModuleFrame._fim_do_lote`); tarefa limpa fica só com a faixa
"Terminou". As linhas vêm agrupadas pela ficha (o código PMIB da linha); a regra
mora em `sigft/app/resumo_lote.py`.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QMessageBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from sigft.app import niveis_log, resumo_lote
from sigft.app_qt import estilo, tema
from sigft.app_qt.widgets import blocos
from sigft.core import plataforma
from sigft.core.dados_usuario import pasta_logs

TEXTO_COPIAR = "Copiar lista"
TEXTO_COPIADO = "Copiado"
TEXTO_LOG = "Abrir log"
TEXTO_FECHAR = "Fechar"
DICA_COPIAR = "Copia a lista agrupada por ficha, para colar num e-mail ou numa planilha."
DICA_LOG = "Grava num arquivo tudo o que esta tarefa escreveu no console e abre o arquivo."
PASTA_DOS_RESUMOS = "resumos"
MS_DO_COPIADO = 1500


class JanelaResumoDoLote(QDialog):
    def __init__(self, parent, titulo: str, pares) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(f"Resumo: {titulo}")
        self.resize(760, 480)
        self._titulo = titulo
        self._pares = [(str(texto), nivel) for texto, nivel in pares]
        self.grupos = resumo_lote.agrupar(self._pares)
        erros, avisos = resumo_lote.contar(self.grupos)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.rotulo = blocos.rotulo(f"Terminou com {resumo_lote.frase_da_contagem(erros, avisos)}.",
                                    tamanho=15, negrito=True, alinhar="esquerda")
        lay.addWidget(self.rotulo)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderHidden(True)
        # (item, nível) de cada linha: a cor sai do papel e é repintada na troca
        # de tema (`tema.mudou`), porque o `QTreeWidgetItem` guarda a cor dada.
        self._itens: list[tuple[QTreeWidgetItem, str]] = []
        for grupo in self.grupos:
            pai = QTreeWidgetItem([f"{grupo.rotulo} ({len(grupo.linhas)})"])
            for texto, nivel in grupo.linhas:
                filho = QTreeWidgetItem([texto])
                filho.setToolTip(0, texto)
                pai.addChild(filho)
                self._itens.append((filho, nivel))
            self.arvore.addTopLevelItem(pai)
            pai.setExpanded(True)
        lay.addWidget(self.arvore, 1)
        self._pintar_cores()
        # Método ligado (e não `lambda` com `self`): o Qt desfaz a ligação
        # quando a janela morre (aviso do mural de 2026-10-14).
        tema.mudou.connect(self._pintar_cores)

        linha = QHBoxLayout()
        linha.setSpacing(8)
        self.botao_copiar = blocos.botao(TEXTO_COPIAR, variante="secundario")
        self.botao_copiar.setToolTip(DICA_COPIAR)
        self.botao_copiar.clicked.connect(self.copiar)
        self.botao_log = blocos.botao(TEXTO_LOG, variante="secundario")
        self.botao_log.setToolTip(DICA_LOG)
        self.botao_log.clicked.connect(self.abrir_log)
        self.botao_fechar = blocos.botao(TEXTO_FECHAR, variante="primario")
        self.botao_fechar.clicked.connect(self.close)
        linha.addWidget(self.botao_copiar)
        linha.addWidget(self.botao_log)
        linha.addStretch()
        linha.addWidget(self.botao_fechar)
        lay.addLayout(linha)

        self._volta = QTimer(self)
        self._volta.setSingleShot(True)
        self._volta.timeout.connect(self._texto_do_copiar)

    def _pintar_cores(self, *_tema) -> None:
        for item, nivel in self._itens:
            papel = "perigo" if nivel == niveis_log.ERRO else "aviso"
            item.setForeground(0, QBrush(QColor(estilo.cor_do_papel(papel))))

    def copiar(self) -> str:
        texto = resumo_lote.texto_para_copiar(self._titulo, self.grupos)
        QApplication.clipboard().setText(texto)
        self.botao_copiar.setText(TEXTO_COPIADO)
        self._volta.start(MS_DO_COPIADO)
        return texto

    def _texto_do_copiar(self) -> None:
        self.botao_copiar.setText(TEXTO_COPIAR)

    def abrir_log(self):
        """Grava TUDO o que o lote escreveu (não só os problemas) em
        `Documentos\\SIG-FT\\logs\\resumos\\` e abre: a maioria dos módulos não
        tem log em arquivo próprio. Devolve o caminho, ou `None` se falhou."""
        try:
            caminho = resumo_lote.gravar_log(self._titulo, self._pares,
                                             pasta_logs() / PASTA_DOS_RESUMOS, datetime.now())
            plataforma.abrir_no_sistema(caminho)
        except Exception as erro:  # noqa: BLE001 -- vira aviso, a janela segue
            QMessageBox.warning(self, TEXTO_LOG, f"Não consegui abrir o log: {erro}")
            return None
        return caminho


def abrir_resumo(tela, titulo: str, pares) -> JanelaResumoDoLote:
    """Abre (sem prender ninguém: a tarefa já acabou) e devolve a janela."""
    janela = JanelaResumoDoLote(tela, titulo, pares)
    janela.show()
    janela.raise_()
    return janela

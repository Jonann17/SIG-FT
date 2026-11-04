"""Seção "DocPack": as duas etapas do dossiê das listas sem `_STATUS_PMIB`, em abas,
com UM console e UMA barra de progresso (2026-11-04).

Pedido do Luan: o DocPack sai do PMIB Manager (onde era a quarta aba desde
2026-11-03) e vira módulo próprio do menu, na Gestão, em duas etapas. A Etapa 1
(`docpack.py`) cria a estrutura: as pastas e os templates. A Etapa 2
(`docpack_etapa2.py`) preenche o conteúdo. As telas entram EMBUTIDAS, como na
Aplicação LMR (`aplicacao_lmr.py`).
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from sigft.app.idioma import marcar, t
from sigft.app_qt.views.aplicacao_lmr import MARGEM_DA_ROLAGEM, MARGEM_DIREITA_DA_ROLAGEM
from sigft.app_qt.views.docpack import ModuloDocPack
from sigft.app_qt.views.docpack_etapa2 import ModuloDocPackEtapa2
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.abas import Abas
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.module_frame import ModuleFrame

TITULO = marcar("DocPack")
# O nome da aba é também a chave dela no `abas.Abas` (`add`, `set`).
ABA_ETAPA1 = marcar("Etapa 1: Estrutura")
ABA_ETAPA2 = marcar("Etapa 2: Conteúdo")


class ModuloDocPackSecao(ModuleFrame):
    """Cabeçalho + abas (Etapa 1 / Etapa 2) + barra + console compartilhados."""

    def __init__(self, parent=None, controller=None) -> None:
        super().__init__(parent, controller, titulo=t(TITULO), peso_conteudo=3, com_progresso=True)

    def _build_ui(self) -> None:
        blocos.barra_progresso(barra=self.progress_bar, largura=600, altura=12)
        self.layout().setAlignment(self.progress_bar, Qt.AlignmentFlag.AlignHCenter)
        blocos.definir_progresso(self.progress_bar, 0)

        self.abas = Abas()
        self.content_layout.addWidget(self.abas)
        da_secao = {"controller": self.controller, "embutida": True, "console_externo": self.console,
                    "progresso_externo": self.progress_bar}
        self.tela_etapa1 = ModuloDocPack(**da_secao)
        self.tela_etapa2 = ModuloDocPackEtapa2(**da_secao)
        for nome, tela in ((ABA_ETAPA1, self.tela_etapa1), (ABA_ETAPA2, self.tela_etapa2)):
            tela.layout().setContentsMargins(MARGEM_DA_ROLAGEM, MARGEM_DA_ROLAGEM,
                                             MARGEM_DIREITA_DA_ROLAGEM, MARGEM_DA_ROLAGEM)
            self.abas.add(t(nome)).layout().addWidget(tela)
        self.abas.set(t(ABA_ETAPA1))
        instalar_como_funciona(self, {t(ABA_ETAPA1): "DocPack.etapa1",  # nao-e-interface
                                      t(ABA_ETAPA2): "DocPack.etapa2"}, abas=self.abas)  # nao-e-interface

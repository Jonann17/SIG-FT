"""Seção "Gestão de Sobressalentes" (o PMIB Manager do menu): a Gestão PMIB, com o
console e a barra de progresso da seção.

[2026-11-04] Pedido do Luan: a Conferência de Revisões e a Revisão no AMP saíram
daqui para o módulo "Conferência de Listas" (`conferencia_listas.py`), e o DocPack
virou módulo próprio (`docpack_secao.py`). Sobrou uma tela só, e por isso não há
mais barra de abas; a Gestão PMIB continua EMBUTIDA (`embutida=True`), escrevendo
no console e na barra desta seção, como desde 2026-10-27.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from sigft.app.idioma import t
from sigft.app_qt.views.aplicacao_lmr import MARGEM_DA_ROLAGEM, MARGEM_DIREITA_DA_ROLAGEM
from sigft.app_qt.views.pmib_manager import ModuloPMIBManager
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.module_frame import ModuleFrame


class ModuloGestaoSobressalentes(ModuleFrame):
    """Cabeçalho + Gestão PMIB + barra + console da seção."""

    def __init__(self, parent=None, controller=None) -> None:
        super().__init__(parent, controller, titulo=t("Gestão de Sobressalentes"), peso_conteudo=3,
                         com_progresso=True)

    def _build_ui(self) -> None:
        # `self.console` e `self.progress_bar` já existem aqui: o ModuleFrame os cria
        # antes de chamar `_build_ui`. A barra é a do PMIB Manager de sempre:
        # 600 x 12, centrada.
        blocos.barra_progresso(barra=self.progress_bar, largura=600, altura=12)
        self.layout().setAlignment(self.progress_bar, Qt.AlignmentFlag.AlignHCenter)
        blocos.definir_progresso(self.progress_bar, 0)

        self.tela_gestao = ModuloPMIBManager(controller=self.controller, embutida=True,
                                             console_externo=self.console,
                                             progresso_externo=self.progress_bar)
        self.tela_gestao.layout().setContentsMargins(MARGEM_DA_ROLAGEM, MARGEM_DA_ROLAGEM,
                                                     MARGEM_DIREITA_DA_ROLAGEM, MARGEM_DA_ROLAGEM)
        self.content_layout.addWidget(self.tela_gestao)
        instalar_como_funciona(self, "PMIBManager")

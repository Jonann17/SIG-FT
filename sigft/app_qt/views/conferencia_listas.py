"""Seção "Conferência de Listas": a Conferência de Revisões e a Revisão no AMP em
abas, com UM console e UMA barra de progresso (2026-11-04).

Pedido do Luan: as duas telas saem do PMIB Manager (onde eram abas desde
2026-10-27) e viram um módulo próprio do menu, na Gestão. O padrão é o da
Aplicação LMR (`aplicacao_lmr.py`): as telas entram EMBUTIDAS (`embutida=True`),
sem cabeçalho nem console próprios. A Revisão no AMP parte da última conferência
da aba ao lado (`fonte`).
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from sigft.app import ia_por_modulo
from sigft.app.idioma import marcar, t
from sigft.app_qt.views.aplicacao_lmr import MARGEM_DA_ROLAGEM, MARGEM_DIREITA_DA_ROLAGEM
from sigft.app_qt.views.conferencia_revisoes import ModuloConferenciaRevisoes
from sigft.app_qt.views.revisao_amp import ModuloRevisaoAmp
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.abas import Abas
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.ia_do_modulo import instalar_configurar_ia
from sigft.app_qt.widgets.module_frame import ModuleFrame

TITULO = marcar("Conferência de Listas")
# O nome da aba é também a chave dela no `abas.Abas` (`add`, `set`).
ABA_CONFERENCIA = marcar("Conferência de Revisões")
ABA_AMP = marcar("Revisão no AMP")


class ModuloConferenciaListas(ModuleFrame):
    """Cabeçalho + abas (Conferência / AMP) + barra + console compartilhados."""

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
        self.tela_conferencia = ModuloConferenciaRevisoes(**da_secao)
        self.tela_amp = ModuloRevisaoAmp(fonte=self.tela_conferencia, **da_secao)
        for nome, tela in ((ABA_CONFERENCIA, self.tela_conferencia), (ABA_AMP, self.tela_amp)):
            tela.layout().setContentsMargins(MARGEM_DA_ROLAGEM, MARGEM_DA_ROLAGEM,
                                             MARGEM_DIREITA_DA_ROLAGEM, MARGEM_DA_ROLAGEM)
            self.abas.add(t(nome)).layout().addWidget(tela)
        self.abas.set(t(ABA_CONFERENCIA))
        # O "Como funciona" da seção segue a aba aberta: cada uma tem a sua regra.
        instalar_como_funciona(self, {t(ABA_CONFERENCIA): "ConferenciaListas.conferencia",  # nao-e-interface
                                      t(ABA_AMP): "ConferenciaListas.amp"}, abas=self.abas)  # nao-e-interface
        # [2026-11-05] O webhook da Revisão no AMP no padrão dos outros módulos (pedido do Luan).
        instalar_configurar_ia(self, ia_por_modulo.TAREFAS_DA_TELA.get("ModuloConferenciaListas", ()))

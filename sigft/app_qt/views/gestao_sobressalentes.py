"""Seção "Gestão de Sobressalentes" (o PMIB Manager do menu): quatro abas, UM console e
UMA barra de progresso.

A Gestão PMIB de sempre (`pmib_manager.py`), a Conferência de Revisões
(`conferencia_revisoes.py`) e a Revisão no AMP (`revisao_amp.py`). Correção do Luan
(2026-10-27): as duas telas novas são abas do PMIB Manager, e não módulos novos no
menu. O padrão é o da Aplicação LMR (`aplicacao_lmr.py`): as telas entram EMBUTIDAS
(`embutida=True`), sem cabeçalho nem console próprios, e escrevem no console e na
barra desta seção. A Revisão no AMP parte da última conferência da aba ao lado.
[2026-11-03] A quarta aba é o DocPack (`docpack.py`): a pasta, com os templates, de
cada lista que ainda não tem `_STATUS_PMIB`. Abre na Gestão PMIB.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from sigft.app.idioma import marcar, t
from sigft.app_qt.views.aplicacao_lmr import MARGEM_DA_ROLAGEM, MARGEM_DIREITA_DA_ROLAGEM
from sigft.app_qt.views.conferencia_revisoes import ModuloConferenciaRevisoes
from sigft.app_qt.views.docpack import ModuloDocPack
from sigft.app_qt.views.docpack_etapa2 import ModuloDocPackEtapa2
from sigft.app_qt.views.pmib_manager import ModuloPMIBManager
from sigft.app_qt.views.revisao_amp import ModuloRevisaoAmp
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.abas import Abas
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.module_frame import ModuleFrame

# O nome da aba é também a chave dela no `abas.Abas` (`add`, `set`).
ABA_GESTAO = marcar("Gestão PMIB")
ABA_CONFERENCIA = marcar("Conferência de Revisões")
ABA_AMP = marcar("Revisão no AMP")
ABA_DOCPACK = marcar("DocPack")
# TEMPORARIO: a Etapa 2 do DocPack como aba, ate o modulo DocPack proprio (sai na integracao).
ABA_DOCPACK_ETAPA2 = marcar("DocPack · Etapa 2")


class ModuloGestaoSobressalentes(ModuleFrame):
    """Cabeçalho + abas (Gestão / Conferência / AMP / DocPack) + barra + console compartilhados."""

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

        self.abas = Abas()
        self.content_layout.addWidget(self.abas)
        da_secao = {"controller": self.controller, "embutida": True, "console_externo": self.console,
                    "progresso_externo": self.progress_bar}
        self.tela_gestao = ModuloPMIBManager(**da_secao)
        self.tela_conferencia = ModuloConferenciaRevisoes(**da_secao)
        self.tela_amp = ModuloRevisaoAmp(fonte=self.tela_conferencia, **da_secao)
        self.tela_docpack = ModuloDocPack(**da_secao)
        self.tela_docpack_etapa2 = ModuloDocPackEtapa2(**da_secao)
        for nome, tela in ((ABA_GESTAO, self.tela_gestao), (ABA_CONFERENCIA, self.tela_conferencia),
                           (ABA_AMP, self.tela_amp), (ABA_DOCPACK, self.tela_docpack),
                           (ABA_DOCPACK_ETAPA2, self.tela_docpack_etapa2)):
            tela.layout().setContentsMargins(MARGEM_DA_ROLAGEM, MARGEM_DA_ROLAGEM,
                                             MARGEM_DIREITA_DA_ROLAGEM, MARGEM_DA_ROLAGEM)
            self.abas.add(t(nome)).layout().addWidget(tela)
        self.abas.set(t(ABA_GESTAO))
        # O "Como funciona" da seção segue a aba aberta: cada uma tem a sua regra.
        instalar_como_funciona(self, {t(ABA_GESTAO): "PMIBManager.gestao",
                                      t(ABA_CONFERENCIA): "PMIBManager.conferencia",
                                      t(ABA_AMP): "PMIBManager.amp",
                                      t(ABA_DOCPACK): "PMIBManager.docpack",
                                      t(ABA_DOCPACK_ETAPA2): "PMIBManager.docpack_conteudo"}, abas=self.abas)

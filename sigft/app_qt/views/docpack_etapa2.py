"""DocPack, Etapa 2: Conteúdo (2026-11-04): ESBOÇO.

A tela de verdade (baixar do Aconex a revisão vigente de cada lista e preencher o
`_STATUS_PMIB` e a lista de preços) está sendo escrita à parte e substitui este
arquivo inteiro. Por ora só ocupa o lugar da aba em `docpack_secao.py`.
"""
from __future__ import annotations

from sigft.app.idioma import marcar, t
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.module_frame import ModuleFrame

TITULO = marcar("DocPack: Etapa 2")
TEXTO_EM_CONSTRUCAO = marcar("Em construção.")


class ModuloDocPackEtapa2(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, embutida=False, console_externo=None,
                 progresso_externo=None) -> None:
        super().__init__(parent, controller, titulo=t(TITULO), peso_conteudo=1, altura_console=None,
                         embutida=embutida, console_externo=console_externo,
                         progresso_externo=progresso_externo)

    def _build_ui(self) -> None:
        self.rotulo_em_construcao = blocos.rotulo(t(TEXTO_EM_CONSTRUCAO), tamanho=13, papel="legenda",
                                                  alinhar="esquerda")
        self.content_layout.addWidget(self.rotulo_em_construcao)
        self.content_layout.addStretch(1)


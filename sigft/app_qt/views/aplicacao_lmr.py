"""Seção "Aplicação LMR" na interface Qt: Upload e Exclusão em abas, UM console.

Mesma seção de `sigft/app/views/aplicacao_lmr.py` (pedido de 2026-08-28): duas
operações sobre a MESMA aba do portal e a MESMA coluna da planilha ficam juntas,
e o log fica num lugar só -- com um console, a ordem dos eventos é a ordem na
tela. Abre sempre na aba de Upload: a outra APAGA.

As duas telas entram EMBUTIDAS (`embutida=True`): sem cabeçalho nem console
próprios, escrevendo no console desta seção.
"""
from __future__ import annotations

from sigft.app_qt.views.apagar_lmr import ModuloApagarLMR
from sigft.app_qt.views.lmr import ModuloLMR
from sigft.app_qt.widgets.abas import Abas
from sigft.app_qt.widgets.module_frame import ModuleFrame

ABA_UPLOAD = "Upload de Aplicações"
ABA_EXCLUSAO = "Exclusão de Aplicações"

# A área rolável de cada aba, medida na captura do CTk: o CTkScrollableFrame
# põe o canvas a 6 px (corner_radius) da borda do quadro da aba -- que o `Abas`
# já recua 6 do quadro do Tabview. À direita, 1 + a faixa de 16 px onde o
# CTkScrollableFrame desenha a barra, SEMPRE visível lá. Aqui a faixa fica vazia
# e a barra do Qt só aparece quando há o que rolar (a mesma decisão da barra
# lateral): a área tem a largura de lá (888 px na janela de 1280), sem o traço
# inútil.
MARGEM_DA_ROLAGEM = 6
MARGEM_DIREITA_DA_ROLAGEM = 1 + 16


class ModuloAplicacaoLMR(ModuleFrame):
    """Cabeçalho + abas (Upload / Exclusão) + console compartilhado."""

    def __init__(self, parent=None, controller=None) -> None:
        # O conteúdo é o Tabview, que precisa do espaço; o console fica com a
        # altura padrão embaixo, como nas outras telas.
        super().__init__(parent, controller, titulo="Aplicação LMR", peso_conteudo=3)

    def _build_ui(self) -> None:
        # `self.console` já existe aqui: o ModuleFrame cria o console antes de
        # chamar `_build_ui`. Quadro na cor padrão do `Abas` (gray13, o fg_color
        # do CTkFrame): lá o pai do Tabview é transparente, não um CTkFrame de
        # fundo padrão -- o quadro some no fundo, como na captura.
        self.abas = Abas()
        self.content_layout.addWidget(self.abas)

        self.tela_upload = ModuloLMR(controller=self.controller, embutida=True,
                                     console_externo=self.console)
        self.tela_exclusao = ModuloApagarLMR(controller=self.controller, embutida=True,
                                             console_externo=self.console)
        for nome, tela in ((ABA_UPLOAD, self.tela_upload), (ABA_EXCLUSAO, self.tela_exclusao)):
            tela.layout().setContentsMargins(MARGEM_DA_ROLAGEM, MARGEM_DA_ROLAGEM,
                                             MARGEM_DIREITA_DA_ROLAGEM, MARGEM_DA_ROLAGEM)
            self.abas.add(nome).layout().addWidget(tela)

        # Abrir direto na tela que APAGA seria um convite ao erro.
        self.abas.set(ABA_UPLOAD)

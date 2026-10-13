"""As fontes que os testes de interface Qt veem são as do APP, em todo sistema.

No Release (Windows, `QT_QPA_PLATFORM=offscreen`) o Qt não vê fonte nenhuma
do sistema: só as que o app registra. Teste que não chamava
`estilo.carregar_fontes()` -- e que rodava antes de qualquer um que chamasse --
desenhava cada letra como uma caixa da largura do tamanho da fonte (13 px):
"English" 7 x 13 + 28 = o rádio de 119 px, as abas de 522 px (2026-10-13, seis
falhas que no Linux passavam). No contêiner de desenvolvimento era o oposto:
o Roboto do `~/.fonts`, COM o Roboto-Medium, que o app nunca registra
(`estilo.ARQUIVOS_DE_FONTE`), deixava o negrito 2 px mais largo que no app.

Por isso o `qapp` dos testes carrega as fontes como o `_preparar_qt` do app, e
no Linux o `tests/fontes_dos_testes.conf` esconde do fontconfig o Roboto e o
Noto Emoji instalados na máquina (ver `tests/conftest.py`).
"""
import sys

import pytest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication


def test_qapp_dos_testes_ja_vem_com_a_fonte_do_app(qapp):
    # Sem chamar `carregar_fontes` aqui: o `qapp` é que tem de trazê-la.
    assert "Roboto" in QFontDatabase.families()
    assert QApplication.font().families()[:1] == ["Roboto"]


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="o fontconfig só manda nas fontes do Qt no Linux")
def test_o_roboto_dos_testes_e_so_o_do_app(qapp):
    # O Medium do sistema mudaria a letra do negrito (ver estilo.ARQUIVOS_DE_FONTE).
    estilos = QFontDatabase.styles("Roboto")
    assert not any("Medium" in e for e in estilos), estilos

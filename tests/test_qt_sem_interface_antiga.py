"""A interface Qt importa sem as bibliotecas da interface antiga.

Nasceu quando as duas interfaces conviviam: as telas Qt importavam textos de
módulos que puxavam a biblioteca gráfica antiga, e falhavam num Python sem ela
(ex.: Homebrew no macOS). Desde 2026-10-15 a interface antiga saiu do SIG-FT,
e `tests/test_sem_interface_antiga.py` trava, por AST, que nenhum arquivo a importa.
Este teste é a outra metade: importa cada módulo DE VERDADE num interpretador
limpo, com as bibliotecas bloqueadas por um finder, e pega também um import
indireto (de uma dependência de terceiros, por exemplo).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_sem_interface_antiga import MODULOS_PROIBIDOS

RAIZ = Path(__file__).resolve().parent.parent

_BLOQUEIO = """
import importlib.abc, sys
sys.path.insert(0, {raiz!r})

class _SemTk(importlib.abc.MetaPathFinder):
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split('.')[0] in {proibidos!r}:
            raise ImportError('Tk bloqueado pelo teste: ' + nome)

sys.meta_path.insert(0, _SemTk())
import {modulo}
assert not [m for m in sys.modules if m.split('.')[0] in {proibidos!r}]
"""


def _importa_sem_tk(modulo):
    ambiente = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    return subprocess.run(
        [sys.executable, "-c", _BLOQUEIO.format(raiz=str(RAIZ), modulo=modulo,
                                                   proibidos=tuple(sorted(MODULOS_PROIBIDOS)))],
        capture_output=True, text=True, timeout=60, env=ambiente, cwd=str(RAIZ))


@pytest.mark.parametrize("modulo", [
    "sigft.app.textos_dialogos",
    "sigft.app_qt.widgets.dialogs",
    "sigft.app_qt.widgets.espera",
    "sigft.app_qt.widgets.module_frame",
    "sigft.app_qt.main",
    "sigft.app_qt.file_dialogs",
    "sigft.app_qt.widgets.pickers",
    "sigft.app_qt.widgets.blocos",
    "sigft.app_qt.widgets.dialogos_selecao",
    "sigft.app_qt.widgets.revisao_portal",
    "sigft.core.pmib_regras",
    "sigft.app_qt.widgets.abas",
    "sigft.app_qt.widgets.painel_janela",
    "sigft.app_qt.views.translator",
    "sigft.app_qt.views.apagar_lmr",
    "sigft.app_qt.views.lmr",
    "sigft.app_qt.views.aplicacao_lmr",
    "sigft.app_qt.views.analyzer",
    "sigft.app_qt.views.busca_pmib",
    "sigft.app_qt.views.janelas",
    "sigft.app_qt.views.pmib_manager",
    "sigft.app_qt.views.copia_fichas",
    "sigft.app_qt.views.pdm",
    "sigft.app_qt.views._upload_comum",
    "sigft.app_qt.views.upload_conditions",
    "sigft.app_qt.views.upload_tech_specs",
    "sigft.app_qt.views.correcao_pdm",
    "sigft.app_qt.views.cria_fichas",
    "sigft.app_qt.views.autospec",
    "sigft.app_qt.widgets.controles",
    "sigft.app.atualizacao_textos",
    "sigft.app_qt.atualizacao",
    "sigft.app_qt.views.home",
    "sigft.app_qt.widgets.mural",
    "sigft.services.mural_atividades",
    "sigft.app.file_dialogs",
    "sigft.app.conferencia",
    "sigft.core.erro_de_abertura",
    "sigft.core.novidades",
])
def test_importa_sem_a_interface_antiga(modulo):
    resultado = _importa_sem_tk(modulo)
    assert resultado.returncode == 0, resultado.stderr[-800:]

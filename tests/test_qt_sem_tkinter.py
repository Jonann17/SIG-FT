"""A interface Qt nao pode depender do Tk.

`sigft.app_qt.widgets.dialogs`/`espera` importavam os textos de
`sigft.app.widgets.dialogs`, que importa tkinter/ttk/customtkinter no topo:
toda tela Qt falhava num Python sem Tk (ex.: Homebrew no macOS) e o Tk entrava
no processo Qt sem necessidade. Os textos agora moram em
`sigft.app.textos_dialogos` (so biblioteca padrao).

O subprocesso bloqueia `tkinter`/`customtkinter` com um finder, entao o teste
vale mesmo numa maquina que TEM Tk (o conftest dubla o Tk neste processo, por
isso e preciso um interpretador limpo).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

_BLOQUEIO = """
import importlib.abc, sys
sys.path.insert(0, {raiz!r})

class _SemTk(importlib.abc.MetaPathFinder):
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split('.')[0] in ('tkinter', '_tkinter', 'customtkinter'):
            raise ImportError('Tk bloqueado pelo teste: ' + nome)

sys.meta_path.insert(0, _SemTk())
import {modulo}
assert not [m for m in sys.modules if m.split('.')[0] in ('tkinter', 'customtkinter')]
"""


def _importa_sem_tk(modulo):
    ambiente = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    return subprocess.run(
        [sys.executable, "-c", _BLOQUEIO.format(raiz=str(RAIZ), modulo=modulo)],
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
    "sigft.app_qt.views.translator",
    "sigft.app_qt.views.apagar_lmr",
    "sigft.app_qt.views.lmr",
    "sigft.app_qt.widgets.controles",
    "sigft.app.atualizacao_textos",
    "sigft.app_qt.atualizacao",
])
def test_importa_sem_tkinter(modulo):
    resultado = _importa_sem_tk(modulo)
    assert resultado.returncode == 0, resultado.stderr[-800:]


def test_reexportacao_do_customtkinter_continua_igual():
    # `sigft.app.widgets.dialogs` (CustomTkinter) reexporta os mesmos objetos.
    from sigft.app import textos_dialogos
    from sigft.app.widgets import dialogs
    for nome in ("LOGIN_NECESSARIO", "MSG_EXCEL_BLOQUEADO", "TEXTO_CONTINUAR",
                 "TEXTO_COMECAR_EXCLUSAO", "TEXTOS_TRAVADOS", "msg_excel_bloqueado",
                 "msg_falha_ao_salvar", "msg_ficha_preenchida", "MSG_LOGIN_LOTE"):
        assert getattr(dialogs, nome) is getattr(textos_dialogos, nome)


def test_reexportacao_dos_textos_da_atualizacao():
    # `sigft.app.atualizacao` (CustomTkinter) segue com os nomes de antes.
    from sigft.app import atualizacao, atualizacao_textos
    for nome in ("TITULO", "MSG_UAC", "MSG_COMO_FUNCIONA", "notas_para_exibir",
                 "resumo_da_versao"):
        assert getattr(atualizacao, nome) is getattr(atualizacao_textos, nome)
    assert atualizacao._erro_curto is atualizacao_textos.erro_curto
    assert atualizacao._data_br is atualizacao_textos.data_br
    assert atualizacao._mb is atualizacao_textos.mb

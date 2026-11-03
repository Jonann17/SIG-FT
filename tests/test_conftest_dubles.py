"""Os dublês de módulo do conftest sobrevivem ao `monkeypatch` (2026-10-30).

O pytest 9.2 passou a desfazer `monkeypatch.setattr` num filho de `MagicMock`
com `delattr`, e o filho sumia do dublê compartilhado (`sys.modules`): os
testes seguintes do mesmo processo quebravam. Ver `_DubleDeModulo` no
`conftest.py`."""
import sys
from unittest.mock import MagicMock

import pytest


def test_desfazer_o_monkeypatch_devolve_o_mesmo_filho_do_duble():
    duble = sys.modules["pypdf"]
    if not isinstance(duble, MagicMock):
        pytest.skip("pypdf real instalado: não há dublê para conferir")
    filho = duble.PdfReader
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(duble, "PdfReader", object())
    assert duble.PdfReader is filho


def test_desfazer_o_monkeypatch_num_filho_nunca_lido_nao_o_apaga():
    duble = sys.modules["xlwings"]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(duble, "atributo_nunca_lido_antes", object())
    # Depois do `undo`, o atributo continua respondendo (um filho do dublê),
    # em vez de levantar ou ficar com o valor do teste.
    assert isinstance(duble.atributo_nunca_lido_antes, MagicMock)

r"""
`autorizados.aplicar` -- a gravação de AUTORIZADO separada da leitura do
export (2026-10-14).

Duas fontes dizem quais PMIBs a Itaipu autorizou: o export que ela manda
(`sobressalentes_autorizados_*.xlsx`) e, desde 2026-10-14, a conferência no
portal (`autorizacao_portal`), que lê o código SAP de recebimento de cada
ficha. As duas gravam pela MESMA função, para que AUTORIZADO e os dias de
atraso saiam iguais venha a lista de onde vier. O comportamento de
`executar` (o export) não muda: os testes dele estão em test_autorizados.py.
"""
from __future__ import annotations

import datetime as dt
import shutil
import warnings
from pathlib import Path

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade

from sigft import config
from sigft.services import autorizados

RAIZ = Path(__file__).resolve().parent.parent
KIT = RAIZ / "gestao-sobressalentes" / "_gestao_v2" / "fixtures" / "kit_gestao_pmib"
T1 = "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"

precisa_do_kit = pytest.mark.skipif(not (KIT / "status" / T1).is_file(),
                                    reason="kit de teste do cofre ausente (gestao-sobressalentes/)")


@pytest.fixture
def pasta(tmp_path):
    destino = tmp_path / "status"
    shutil.copytree(KIT / "status", destino)
    return destino


def _aba(caminho):
    from openpyxl import load_workbook

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_workbook(caminho)[config.ABA_LISTA_MATERIAIS]


@precisa_do_kit
def test_aplicar_grava_autorizado_com_a_data_dada_sem_arquivo_de_export(pasta):
    pytest.importorskip("lxml")
    with openpyxl_de_verdade():
        list(autorizados.aplicar({"4500063671.9003", "4500063671.9006"}, pasta,
                                 data_autorizacao=dt.date(2026, 10, 9), origem="conferidos no portal"))
        ws = _aba(pasta / T1)

        # linha 6: e-mail 15/09 -> prazo 06/10; autorizado em 09/10 -> 3 dias de atraso
        assert (ws["S6"].value, ws["T6"].value) == ("AUTORIZADO", 3)
        # linha 7: e-mail 01/10 -> prazo 23/10; no prazo -> dias em branco
        assert (ws["S7"].value, ws["T7"].value) == ("AUTORIZADO", None)
        assert ws["S9"].value is None


@precisa_do_kit
def test_o_aviso_do_pmib_que_falta_diz_de_onde_veio_a_lista(pasta):
    pytest.importorskip("lxml")
    with openpyxl_de_verdade():
        linhas = list(autorizados.aplicar({"4500063671.7777"}, pasta,
                                          data_autorizacao=dt.date(2026, 10, 9), origem="conferidos no portal"))

    aviso = [linha for linha in linhas if "4500063671.7777" in linha]
    assert aviso and "conferidos no portal" in aviso[0]

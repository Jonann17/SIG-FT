r"""
Os escritores do `_STATUS_PMIB` gravando num arquivo de VERDADE sem apagar os
comentários em thread -- T1 do roteiro do Gestão PMIB v2.

`tests/test_status_sheet.py` prova o contrato do `StatusPMIB` com dublês;
`tests/test_cirurgico.py` prova o editor. Aqui os dois juntos, do jeito que o
app usa: lê com openpyxl, acha a linha, marca, grava. A fixture é o
`_STATUS_PMIB` sintético v2 (ver `tests/fixtures/status_pmib/LEIA-ME.md`).

O ponto que só um arquivo real prova: a cada tentativa de gravar o arquivo é
RELIDO. Se a pessoa fecha o Excel salvando uma mudança entre uma tentativa e
outra, a mudança dela fica -- o openpyxl regravava a versão que tinha lido
antes, por cima.
"""
from __future__ import annotations

import shutil
import warnings
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("lxml")

from _openpyxl_de_verdade import openpyxl_de_verdade  # noqa: E402

from sigft import config  # noqa: E402
from sigft.core.excel import cirurgico  # noqa: E402
from sigft.core.excel.status_sheet import StatusPMIB  # noqa: E402

V2 = Path(__file__).resolve().parent / "fixtures" / "status_pmib" / "status_pmib_v2_sintetico.xlsx"
ABA = config.ABA_LISTA_MATERIAIS
COMENTARIOS = ("xl/threadedComments/threadedComment1.xml", "xl/persons/person.xml", "xl/comments1.xml")


def _partes(caminho):
    with zipfile.ZipFile(caminho) as z:
        return {n: z.read(n) for n in z.namelist()}


def _ler(caminho):
    from openpyxl import load_workbook

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_workbook(caminho)[ABA]


@pytest.fixture
def status_pmib(tmp_path):
    destino = tmp_path / "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"
    shutil.copyfile(V2, destino)
    return destino


def test_statuspmib_marca_completo_sem_apagar_os_comentarios(status_pmib):
    antes = _partes(status_pmib)

    with openpyxl_de_verdade():
        painel = StatusPMIB(str(status_pmib))
        painel.abrir(keywords={config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
                               config.COL_INFO_GERAIS: config.COL_INFO_GERAIS})
        linha = painel.buscar_linha("4500063671.9006")
        assert linha == 7  # cabeçalho na linha 5 (v2), segunda ficha
        painel.marcar_linha(linha, [config.COL_INFO_GERAIS])
        assert painel.salvar() is True
        painel.fechar()

        assert _ler(status_pmib)["K7"].value == "COMPLETO"

    depois = _partes(status_pmib)
    for parte in COMENTARIOS:
        assert depois[parte] == antes[parte], parte
    assert [n for n in antes if antes[n] != depois[n]] == ["xl/worksheets/sheet1.xml"]


def test_cria_fichas_grava_pmib_e_pdm_sem_apagar_os_comentarios(status_pmib, monkeypatch):
    # `DataManager.atualizar_excel_final`: depois de criar as fichas no portal,
    # o Cria Fichas escreve o PMIB e o PDM de volta na linha de cada material.
    from sigft.services import cria_fichas

    antes = _partes(status_pmib)
    with openpyxl_de_verdade() as openpyxl_real:
        monkeypatch.setattr(cria_fichas, "openpyxl", openpyxl_real)
        ok, mensagem = cria_fichas.DataManager.atualizar_excel_final(
            str(status_pmib), ABA, [("TEXTO DE TESTE 69", "4500063671.1234", "PDM.0001.002")])

        ws = _ler(status_pmib)
        assert (ok, mensagem) == (True, "1 linhas atualizadas.")
        assert ws["H7"].value == "4500063671.1234"
        assert ws["I7"].value == "PDM.0001.002"
        assert ws["H6"].value == "4500063671.9003"  # a outra linha, intocada

    depois = _partes(status_pmib)
    for parte in COMENTARIOS:
        assert depois[parte] == antes[parte], parte


def test_cria_fichas_com_o_arquivo_aberto_avisa_e_nao_grava(status_pmib, monkeypatch):
    from sigft.services import cria_fichas

    antes = status_pmib.read_bytes()

    def _aberto_no_excel(self, destino=None):
        raise PermissionError(13, "arquivo aberto no Excel")

    with openpyxl_de_verdade() as openpyxl_real:
        monkeypatch.setattr(cria_fichas, "openpyxl", openpyxl_real)
        monkeypatch.setattr(cirurgico.PlanilhaXlsx, "salvar", _aberto_no_excel)
        ok, mensagem = cria_fichas.DataManager.atualizar_excel_final(
            str(status_pmib), ABA, [("TEXTO DE TESTE 69", "4500063671.1234", "PDM.0001.002")])

    assert (ok, mensagem) == (False, "Erro: O arquivo Excel está ABERTO.")
    assert status_pmib.read_bytes() == antes


def test_a_retentativa_rele_o_arquivo_e_preserva_o_que_a_pessoa_salvou(status_pmib, monkeypatch):
    # 1ª tentativa: o arquivo está aberto no Excel. A pessoa escreve uma
    # observação, salva e fecha o Excel; o SIG-FT tenta de novo. O que ela
    # salvou tem de estar lá no fim, junto com o COMPLETO do SIG-FT.
    salvar_de_verdade = cirurgico.PlanilhaXlsx.salvar
    tentativas = []

    def _primeira_falha(self, destino=None):
        tentativas.append(1)
        if len(tentativas) == 1:
            raise PermissionError(13, "arquivo aberto no Excel")
        return salvar_de_verdade(self, destino)

    def _pessoa_salva_e_fecha_o_excel(_tentativa, _erro):
        monkeypatch.setattr(cirurgico.PlanilhaXlsx, "salvar", salvar_de_verdade)
        cirurgico.gravar_celulas(status_pmib, ABA, {(7, 24): "ANOTADO PELA PESSOA"})
        monkeypatch.setattr(cirurgico.PlanilhaXlsx, "salvar", _primeira_falha)
        return True

    with openpyxl_de_verdade():
        painel = StatusPMIB(str(status_pmib))
        painel.abrir(keywords={config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
                               config.COL_INFO_GERAIS: config.COL_INFO_GERAIS})
        painel.marcar_linha(painel.buscar_linha("4500063671.9006"), [config.COL_INFO_GERAIS])
        monkeypatch.setattr(cirurgico.PlanilhaXlsx, "salvar", _primeira_falha)

        painel.salvar(on_locked=_pessoa_salva_e_fecha_o_excel)

        ws = _ler(status_pmib)
        assert ws["K7"].value == "COMPLETO"
        assert ws["X7"].value == "ANOTADO PELA PESSOA"

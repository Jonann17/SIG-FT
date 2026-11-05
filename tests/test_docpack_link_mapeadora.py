"""[2026-11-05] DocPack grava o LINK DA PLANILHA do dossiê novo na mapeadora (só
quando a célula está vazia), e as tabelas rolam de lado em vez de cortar."""
from __future__ import annotations

import os

import pytest
from _openpyxl_de_verdade import openpyxl_de_verdade

from sigft.services import docpack
from sigft.services.pmib_manager import COLUNA_CHAVE_SOBRESSALENTES, NOME_ABA_SOBRESSALENTES


@pytest.fixture
def openpyxl():
    with openpyxl_de_verdade():
        import openpyxl as real
        yield real


def _mapeadora(openpyxl, caminho, linhas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = NOME_ABA_SOBRESSALENTES
    ws.append(["MAPEAMENTO"])
    ws.append([COLUNA_CHAVE_SOBRESSALENTES, "DESCRIÇÃO", "LINK DA PLANILHA"])
    for codigo, link in linhas:
        ws.append([codigo, "LISTA", None])
        if link:
            c = ws.cell(row=ws.max_row, column=3)
            c.value, c.hyperlink = "Abrir Box", link
    wb.save(caminho)


def _dossie(raiz, codigo, situacao="criado"):
    pasta = raiz / "05 - UG" / codigo.replace("#", "").replace("&", "_")
    pasta.mkdir(parents=True)
    (pasta / f"{codigo}_STATUS_PMIB.xlsx").write_bytes(b"x")
    return docpack.Resultado(codigo=codigo, situacao=situacao, pasta=pasta)


def test_grava_link_relativo_so_onde_esta_vazio(tmp_path, openpyxl):
    mapa = tmp_path / "Mapeamento.xlsx"
    _mapeadora(openpyxl, mapa, [("#A&MPB020", None), ("#B&MPB020", "outra/pasta/x.xlsx")])
    resultados = [_dossie(tmp_path, "#A&MPB020"), _dossie(tmp_path, "#B&MPB020")]
    logs = []

    n = docpack.gravar_links(mapa, resultados, log_cb=logs.append)

    assert n == 1
    ws = openpyxl.load_workbook(mapa)[NOME_ABA_SOBRESSALENTES]
    a, b = ws.cell(row=3, column=3), ws.cell(row=4, column=3)
    assert a.value == "Abrir Box"
    assert a.hyperlink.target == os.path.relpath(resultados[0].pasta / "#A&MPB020_STATUS_PMIB.xlsx", tmp_path)
    assert b.hyperlink.target == "outra/pasta/x.xlsx"   # o que já existia ficou
    assert any("já tem link" in m for m in logs)


def test_dossie_que_falhou_nao_vira_link(tmp_path, openpyxl):
    mapa = tmp_path / "Mapeamento.xlsx"
    _mapeadora(openpyxl, mapa, [("#A&MPB020", None)])
    r = docpack.Resultado(codigo="#A&MPB020", situacao="falhou", pasta=None)
    assert docpack.gravar_links(mapa, [r], log_cb=lambda _m: None) == 0


def test_mapeadora_aberta_no_excel_pede_de_novo(tmp_path, monkeypatch, openpyxl):
    mapa = tmp_path / "Mapeamento.xlsx"
    _mapeadora(openpyxl, mapa, [("#A&MPB020", None)])
    resultados = [_dossie(tmp_path, "#A&MPB020")]
    salvar_original, tentativas = openpyxl.Workbook.save, []

    def salvar(self, caminho):
        tentativas.append(1)
        if len(tentativas) == 1:
            raise PermissionError("aberta")
        return salvar_original(self, caminho)
    monkeypatch.setattr(openpyxl.Workbook, "save", salvar)
    assert docpack.gravar_links(mapa, resultados, log_cb=lambda _m: None, retry_lock=lambda _c: True) == 1
    assert len(tentativas) == 2


def test_tabela_alarga_a_coluna_e_rola_de_lado(qtbot):
    from PySide6.QtCore import Qt

    from sigft.app_qt.widgets import dialogos_selecao as ds
    tree = ds.tabela_ttk([("Código", 120, "w"), ("Pasta", 120, "w")])
    qtbot.addWidget(tree)
    tree.resize(300, 200)
    ds.linha_ttk(tree, ("#ST00=M00MEU10&MPB020", "SISTEMA DE AGUA DE RESFRIAMENTO DO GERADOR DIESEL - SFC 50 E 60"))
    ds.ajustar_ao_conteudo(tree)
    assert tree.columnWidth(1) > 300
    assert tree.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn

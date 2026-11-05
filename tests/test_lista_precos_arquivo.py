"""Lista de Preços (`services/lista_precos_arquivo.py`, 2026-11-05): achar, criar e preencher
a lista com preço de cada sistema, e conferir uma pasta contra o `_STATUS_PMIB`. Com o
openpyxl de verdade e os templates do repositório."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest
from _openpyxl_de_verdade import openpyxl_de_verdade

from sigft.core.excel.cirurgico import PlanilhaXlsx
from sigft.services import lista_precos_arquivo as lp


@pytest.fixture(autouse=True)
def _openpyxl():
    with openpyxl_de_verdade():
        yield


def load_workbook(*args, **kw):
    from openpyxl import load_workbook as real
    return real(*args, **kw)


RAIZ_REPO = Path(__file__).resolve().parents[1]
TEMPLATE_PRECOS = (RAIZ_REPO / "gestao-sobressalentes/_gestao_v2/fixtures/kit_lista_precos/"
                   "Lista de Sobressalentes com preço.xlsm")
TEMPLATE_STATUS = RAIZ_REPO / "gestao-sobressalentes/_gestao_v2/template/codigo_itaipu_STATUS_PMIB_v2.xlsx"
STATUS_COM_MATERIAIS = RAIZ_REPO / "tests/fixtures/status_pmib/status_pmib_v2_sintetico.xlsx"
CODIGO = "#ST00=M00MEU10&MPB020"
PRECOS = "#ST00=M00MEU10&MPB021"


def _sistema(raiz: Path, nome: str, codigo: str = CODIGO, status: Path = STATUS_COM_MATERIAIS) -> Path:
    pasta = raiz / "03 - EBOP" / nome
    pasta.mkdir(parents=True)
    shutil.copyfile(status, pasta / f"{codigo}_STATUS_PMIB.xlsx")
    return pasta


def _materiais_do_status():
    return lp.ler_itens(STATUS_COM_MATERIAIS, lp.COLUNAS_STATUS)[0]


# ------------------------------------------------------------------ código e detecção

@pytest.mark.parametrize("codigo, esperado", [
    ("#ST00=M00MEU10&MPB020", "#ST00=M00MEU10&MPB021"),
    ("#ITA0=A01AAM10&EPB020-01", "#ITA0=A01AAM10&EPB021"),
    (" #ST00=X&MPB020 ", "#ST00=X&MPB021"),
])
def test_codigo_da_lista_de_precos(codigo, esperado):
    assert lp.codigo_lista_de_precos(codigo) == esperado


def test_codigo_sem_pb020_e_recusado():
    with pytest.raises(lp.ErroListaDePrecos):
        lp.codigo_lista_de_precos("#ST00=X&MPB021")


def test_le_os_materiais_do_status_pmib():
    itens = _materiais_do_status()
    assert len(itens) > 5
    assert itens[0].codigo_pmib == "4500063671.9003" and itens[0].descricao == "TEXTO DE TESTE 68"


def test_varredura_diz_quem_tem_lista_e_o_legado(tmp_path):
    sem = _sistema(tmp_path, "SEM LISTA")
    com = _sistema(tmp_path, "COM LISTA", "#ST00=B&MPB020")
    shutil.copyfile(TEMPLATE_PRECOS, com / "#ST00=B&MPB021.xlsm")
    legado = _sistema(tmp_path, "LEGADO", "#ST00=C&MPB020")
    shutil.copyfile(TEMPLATE_PRECOS, legado / "#ST00=C&MPB020-01.xlsm")
    por_pasta = {s.pasta.name: s for s in lp.varrer(tmp_path)}
    assert por_pasta["SEM LISTA"].lista is None and por_pasta["SEM LISTA"].materiais > 0
    assert por_pasta["COM LISTA"].lista.name == "#ST00=B&MPB021.xlsm" and not por_pasta["COM LISTA"].legado
    assert por_pasta["LEGADO"].lista.name == "#ST00=C&MPB020-01.xlsm" and por_pasta["LEGADO"].legado
    assert sem.is_dir()


# ------------------------------------------------------------------ criar

def test_cria_com_capa_e_materiais_sem_preco(tmp_path):
    pasta = _sistema(tmp_path, "GERADOR DIESEL")
    [sistema] = lp.varrer(tmp_path)
    r = lp.criar_lista(sistema, TEMPLATE_PRECOS, titulo="LISTA DE SOBRESSALENTES - GERADOR DIESEL")
    assert r.situacao == "criada" and r.arquivo == pasta / f"{PRECOS}.xlsm"
    capa = load_workbook(r.arquivo, keep_vba=True)["Capa"]
    assert capa["F37"].value == PRECOS
    assert capa["E27"].value == "LISTA DE SOBRESSALENTES - GERADOR DIESEL - LISTA DE SOBRESSALENTE COM PREÇO"
    itens = lp.ler_itens(r.arquivo, lp.COLUNAS_PRECOS)[0]
    esperados = _materiais_do_status()
    assert r.materiais == len(esperados) == len(itens)
    assert [i.codigo_pmib for i in itens] == [m.codigo_pmib for m in esperados]
    assert all(i.valor in (None, "") for i in itens)      # preço nunca se inventa
    assert [i.item for i in itens] == list(range(1, len(itens) + 1))


def test_o_vba_sai_byte_a_byte(tmp_path):
    _sistema(tmp_path, "X")
    [sistema] = lp.varrer(tmp_path)
    r = lp.criar_lista(sistema, TEMPLATE_PRECOS)
    with zipfile.ZipFile(r.arquivo) as novo, zipfile.ZipFile(TEMPLATE_PRECOS) as velho:
        assert novo.read("xl/vbaProject.bin") == velho.read("xl/vbaProject.bin")
        mudaram = {n for n in velho.namelist() if n in novo.namelist() and novo.read(n) != velho.read(n)}
    assert mudaram and all(n.startswith("xl/worksheets/") or n in ("xl/workbook.xml", "[Content_Types].xml",
                                                                    "xl/_rels/workbook.xml.rels")
                           for n in mudaram), mudaram


def test_sem_titulo_a_capa_leva_o_nome_da_pasta(tmp_path):
    _sistema(tmp_path, "BOMBAS")
    r = lp.criar_lista(lp.varrer(tmp_path)[0], TEMPLATE_PRECOS)
    assert load_workbook(r.arquivo, keep_vba=True)["Capa"]["E27"].value == "BOMBAS" + lp.SUFIXO_TITULO


def test_status_vazio_cria_a_lista_so_com_a_capa(tmp_path):
    _sistema(tmp_path, "VAZIO", status=TEMPLATE_STATUS)
    [sistema] = lp.varrer(tmp_path)
    assert sistema.materiais == 0
    r = lp.criar_lista(sistema, TEMPLATE_PRECOS)
    assert r.situacao == "criada" and r.materiais == 0


def test_nunca_sobrescreve(tmp_path):
    pasta = _sistema(tmp_path, "X")
    existente = pasta / f"{PRECOS}.xlsm"
    existente.write_bytes(b"da pessoa")
    sistema = lp.Sistema(CODIGO, pasta, pasta / f"{CODIGO}_STATUS_PMIB.xlsx")
    r = lp.criar_lista(sistema, TEMPLATE_PRECOS)
    assert r.situacao == "existia" and existente.read_bytes() == b"da pessoa"


def test_criar_listas_loga_e_resume(tmp_path):
    _sistema(tmp_path, "A")
    linhas = []
    lp.criar_listas(lp.varrer(tmp_path), TEMPLATE_PRECOS, log_cb=linhas.append)
    assert linhas[0].startswith("Lista de Preços: 1 sistema")
    assert any(linha.startswith("  ✅ ") for linha in linhas)
    assert "1 criada(s), 0 já existia(m), 0 falha(s)" in linhas[-1]


# ------------------------------------------------------------------ conferir

def _pasta_com_lista(tmp_path) -> Path:
    pasta = _sistema(tmp_path, "GERADOR DIESEL")
    lp.criar_lista(lp.varrer(tmp_path)[0], TEMPLATE_PRECOS)
    return pasta


def _mexer_na_lista(caminho: Path, escritas: dict[str, object]) -> None:
    planilha = PlanilhaXlsx(caminho)
    parte = planilha.parte_da_aba("Lista de Materiais")
    for referencia, valor in escritas.items():
        planilha.escrever(parte, referencia, valor)
    planilha.salvar()


def test_lista_recem_criada_esta_em_dia(tmp_path):
    conferencia = lp.conferir(_pasta_com_lista(tmp_path))
    assert conferencia.em_dia and not conferencia.valorizada


def test_divergencias_falta_sobra_e_diferente(tmp_path):
    pasta = _pasta_com_lista(tmp_path)
    lista = pasta / f"{PRECOS}.xlsm"
    # Linha 5 = 1º item. QTD (B) diferente; CÓDIGO PMIB (H) da 2ª linha trocado: some um e sobra outro.
    _mexer_na_lista(lista, {"B5": 7, "H6": "4500063671.9999"})
    conferencia = lp.conferir(pasta)
    tipos = {(d.tipo, d.item) for d in conferencia.divergencias}
    assert ("diferente", "4500063671.9003") in tipos
    assert ("falta_na_lista", "4500063671.9006") in tipos
    assert ("sobra_na_lista", "4500063671.9999") in tipos
    diferente = next(d for d in conferencia.divergencias if d.tipo == "diferente")
    assert diferente.campo == "QTD." and diferente.no_status == "1" and diferente.na_lista == "7"


def test_pasta_sem_lista_com_preco_e_recusada(tmp_path):
    pasta = _sistema(tmp_path, "X")
    with pytest.raises(lp.ErroListaDePrecos, match="não tem lista com preço"):
        lp.conferir(pasta)


def test_pasta_sem_status_pmib_e_recusada(tmp_path):
    with pytest.raises(lp.ErroListaDePrecos, match="não tem _STATUS_PMIB"):
        lp.conferir(tmp_path)


def test_valorizada_e_atualizar_mantem_os_precos(tmp_path):
    pasta = _pasta_com_lista(tmp_path)
    lista = pasta / f"{PRECOS}.xlsm"
    # Preço no 1º item (I5) e um item a mais que não está no _STATUS_PMIB.
    _mexer_na_lista(lista, {"I5": 123.45, "H6": "4500063671.9999", "I6": 50})
    conferencia = lp.conferir(pasta)
    assert conferencia.valorizada and not conferencia.em_dia
    logs = []
    resultado = lp.atualizar(conferencia, log_cb=logs.append)
    assert resultado.precos_mantidos == 1
    assert resultado.removidos == ["4500063671.9999"] and resultado.novos_sem_preco == ["4500063671.9006"]
    itens = lp.ler_itens(lista, lp.COLUNAS_PRECOS)[0]
    por_pmib = {i.codigo_pmib: i for i in itens}
    assert por_pmib["4500063671.9003"].valor == 123.45      # o preço do item que continua ficou
    assert por_pmib["4500063671.9006"].valor in (None, "")   # o que voltou entra sem preço
    assert "4500063671.9999" not in por_pmib
    assert len(itens) == len(_materiais_do_status())
    assert lp.conferir(pasta).em_dia
    with zipfile.ZipFile(lista) as z, zipfile.ZipFile(TEMPLATE_PRECOS) as t:
        assert z.read("xl/vbaProject.bin") == t.read("xl/vbaProject.bin")
    assert any("saiu da lista" in linha for linha in logs)


def test_item_casa_pelo_codigo_de_material_sem_pmib():
    a = lp.Item(codigo_material="ABC-1", descricao="X")
    b = lp.Item(codigo_material="abc-1", descricao="Y")
    assert a.chave() == b.chave()
    assert [d.campo for d in lp.comparar([a], [b])] == ["DESCRIÇÃO"]

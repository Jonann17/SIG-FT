r"""
Testes de `sigft/core/excel/cirurgico.py` -- o editor que grava no `.xlsx` sem
apagar o que não é dele (T1 do roteiro do Gestão PMIB v2).

Com arquivo de verdade: `lxml` real (o editor) e `openpyxl` real (só para LER o
resultado, como o app lê). As fixtures em `tests/fixtures/status_pmib/` são
`_STATUS_PMIB` sintéticos com 3 comentários em thread; o v1 tem ainda 2 listas
suspensas gravadas como extensão (`x14`). Ver o LEIA-ME de lá.

A seção A é o CONTROLE: prova que o openpyxl apaga exatamente o que as seções
seguintes provam que o editor preserva. Sem ela, um teste de "preservou" poderia
estar passando porque a fixture não tem o que apagar.
"""
from __future__ import annotations

import io
import shutil
import warnings
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("lxml")

from _openpyxl_de_verdade import openpyxl_de_verdade  # noqa: E402

from sigft.core.excel import cirurgico  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "status_pmib"
V1 = FIXTURES / "status_pmib_v1_sintetico.xlsx"
V2 = FIXTURES / "status_pmib_v2_sintetico.xlsx"
ABA = "Lista de Materiais"
COMENTARIOS = ("xl/threadedComments/threadedComment1.xml", "xl/persons/person.xml", "xl/comments1.xml")


def _partes(caminho):
    with zipfile.ZipFile(caminho) as z:
        return {n: z.read(n) for n in z.namelist()}


def _copia(origem, tmp_path, nome=None):
    destino = tmp_path / (nome or origem.name)
    shutil.copyfile(origem, destino)
    return destino


def _ler(caminho):
    """A aba como o app a lê: openpyxl de verdade, sem `data_only`."""
    from openpyxl import load_workbook

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # "Data Validation extension is not supported"
        return load_workbook(caminho)[ABA]


# ===========================================================================
# A. Controle: o openpyxl apaga o que o editor tem de preservar
# ===========================================================================
def test_controle_o_openpyxl_apaga_comentarios_em_thread_e_listas_x14(tmp_path):
    arquivo = _copia(V1, tmp_path)
    with openpyxl_de_verdade():
        from openpyxl import load_workbook

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = load_workbook(arquivo)
        wb.save(arquivo)

    depois = _partes(arquivo)
    assert "xl/threadedComments/threadedComment1.xml" not in depois
    assert b"x14:dataValidation" not in depois["xl/worksheets/sheet1.xml"]


# ===========================================================================
# B. O editor preserva tudo o que não escreveu
# ===========================================================================
def test_partes_nao_tocadas_saem_identicas_byte_a_byte(tmp_path):
    arquivo = _copia(V2, tmp_path)
    antes = _partes(arquivo)

    cirurgico.gravar_celulas(arquivo, ABA, {(6, 11): "COMPLETO"})

    depois = _partes(arquivo)
    assert list(depois) == list(antes)  # mesmas partes, mesma ordem
    alteradas = [n for n in antes if antes[n] != depois[n]]
    assert alteradas == ["xl/worksheets/sheet1.xml"]


def test_comentarios_em_thread_sobrevivem(tmp_path):
    arquivo = _copia(V2, tmp_path)
    antes = _partes(arquivo)

    cirurgico.gravar_celulas(arquivo, ABA, {(6, 11): "COMPLETO", (7, 19): "AGUARDANDO ITAIPU"})

    depois = _partes(arquivo)
    for parte in COMENTARIOS:
        assert depois[parte] == antes[parte], parte


def test_listas_suspensas_x14_sobrevivem(tmp_path):
    arquivo = _copia(V1, tmp_path)

    cirurgico.gravar_celulas(arquivo, ABA, {(5, 11): "COMPLETO"})

    assert _partes(arquivo)["xl/worksheets/sheet1.xml"].count(b"<x14:dataValidation ") == 2


def test_o_valor_e_o_estilo_da_celula(tmp_path):
    arquivo = _copia(V2, tmp_path)
    planilha = cirurgico.PlanilhaXlsx(arquivo)
    parte = planilha.parte_da_aba(ABA)
    estilo_antes = planilha.estilo(parte, "K6")

    cirurgico.gravar_celulas(arquivo, ABA, {(6, 11): "COMPLETO", (6, 20): 4, (6, 24): None})

    assert cirurgico.PlanilhaXlsx(arquivo).estilo(parte, "K6") == estilo_antes
    with openpyxl_de_verdade():
        ws = _ler(arquivo)
        assert ws["K6"].value == "COMPLETO"
        assert ws["T6"].value == 4
        assert ws["X6"].value is None  # era "TEXTO DE TESTE 61"
        assert ws["J6"].value == "FICHA CRIADA"  # vizinha intocada


def test_celula_em_linha_que_nao_existia(tmp_path):
    arquivo = _copia(V2, tmp_path)

    cirurgico.gravar_celulas(arquivo, ABA, {(60, 3): "NOVA"})

    with openpyxl_de_verdade():
        assert _ler(arquivo)["C60"].value == "NOVA"


# ===========================================================================
# C. Número, data e vazio
# ===========================================================================
def test_numero_em_celula_com_formato_de_data_vira_formato_geral(tmp_path):
    # S6 da fixture herdou o formato de data da coluna vizinha (DATA DO EMAIL)
    # -- o mesmo defeito do DIAS DE ATRASO em 33 arquivos reais. Sem a troca
    # de formato, 4 apareceria como 04/01/1900.
    sem_troca = _copia(V2, tmp_path, "sem_troca.xlsx")
    com_troca = _copia(V2, tmp_path, "com_troca.xlsx")

    cirurgico.gravar_celulas(sem_troca, ABA, {(6, 19): 4})
    cirurgico.gravar_celulas(com_troca, ABA, {(6, 19): 4}, formato_geral={(6, 19)})

    with openpyxl_de_verdade():
        assert _ler(sem_troca)["S6"].is_date  # o controle: o problema existe
        celula = _ler(com_troca)["S6"]
        assert not celula.is_date
        assert celula.value == 4
        assert _ler(com_troca)["R6"].number_format == "mm-dd-yy"  # vizinha não muda


def test_o_mesmo_estilo_trocado_duas_vezes_cria_um_estilo_so(tmp_path):
    arquivo = _copia(V2, tmp_path)
    xfs_antes = _partes(arquivo)["xl/styles.xml"].count(b"<xf ")

    cirurgico.gravar_celulas(arquivo, ABA, {(6, 19): 1, (7, 19): 2}, formato_geral={(6, 19), (7, 19)})

    assert _partes(arquivo)["xl/styles.xml"].count(b"<xf ") <= xfs_antes + 1


def test_nan_vira_celula_vazia_e_nao_texto_nan(tmp_path):
    # "nan" dentro de <v> faz o Excel abrir o arquivo em modo de reparo.
    arquivo = _copia(V2, tmp_path)

    cirurgico.gravar_celulas(arquivo, ABA, {(6, 20): float("nan")})

    assert b">nan<" not in _partes(arquivo)["xl/worksheets/sheet1.xml"]
    with openpyxl_de_verdade():
        assert _ler(arquivo)["T6"].value is None


def test_inteiro_do_numpy_vira_numero_e_nao_texto(tmp_path):
    numpy = pytest.importorskip("numpy")
    arquivo = _copia(V2, tmp_path)

    cirurgico.gravar_celulas(arquivo, ABA, {(6, 20): numpy.int64(12)})

    with openpyxl_de_verdade():
        assert _ler(arquivo)["T6"].value == 12


# ===========================================================================
# D. Nome definido
# ===========================================================================
def test_definir_nome_global_e_substituir_o_anterior(tmp_path):
    arquivo = _copia(V2, tmp_path)

    cirurgico.gravar_celulas(arquivo, ABA, {}, nomes={"sigft_calculado_em": '"2026-10-09"'})
    cirurgico.gravar_celulas(arquivo, ABA, {}, nomes={"sigft_calculado_em": '"2026-10-10"'})

    planilha = cirurgico.PlanilhaXlsx(arquivo)
    assert planilha.nome_definido("sigft_calculado_em") == '"2026-10-10"'
    assert _partes(arquivo)["xl/workbook.xml"].count(b'name="sigft_calculado_em"') == 1
    assert planilha.nome_definido("lst_status") is not None  # os da migração ficam


# ===========================================================================
# E. Fórmula e cadeia de cálculo
# ===========================================================================
def _com_cadeia_de_calculo(tmp_path, formula_b1="<f>A1*2</f>"):
    """Arquivo com fórmula em B1:B3 e um `xl/calcChain.xml` -- o openpyxl não
    grava a cadeia, então ela é montada aqui, como o Excel a deixaria."""
    with openpyxl_de_verdade():
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = ABA
        ws["A1"], ws["A2"], ws["A3"] = 1, 2, 3
        ws["B1"], ws["B2"], ws["B3"] = "=A1*2", "=A2*2", "=A3*2"
        bruto = io.BytesIO()
        wb.save(bruto)
    partes = _partes(bruto)
    partes["xl/worksheets/sheet1.xml"] = partes["xl/worksheets/sheet1.xml"].replace(
        b"<f>A1*2</f>", formula_b1.encode())
    partes["xl/calcChain.xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<calcChain xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        b'<c r="B1" i="1"/><c r="B2"/><c r="B3"/></calcChain>')
    partes["[Content_Types].xml"] = partes["[Content_Types].xml"].replace(
        b"</Types>", b'<Override PartName="/xl/calcChain.xml" ContentType="application/'
                     b'vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/></Types>')
    partes["xl/_rels/workbook.xml.rels"] = partes["xl/_rels/workbook.xml.rels"].replace(
        b"</Relationships>", b'<Relationship Id="rIdCalc" Type="http://schemas.openxmlformats.org/'
                             b'officeDocument/2006/relationships/calcChain" Target="calcChain.xml"/>'
                             b"</Relationships>")
    arquivo = tmp_path / "com_formula.xlsx"
    with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in partes.items():
            z.writestr(nome, dados)
    return arquivo


def test_sobrescrever_formula_simples_descarta_a_cadeia_de_calculo(tmp_path):
    # Entrada órfã na cadeia de cálculo é "conteúdo ilegível" para o Excel; a
    # cadeia é opcional e ele a reconstrói ao abrir.
    arquivo = _com_cadeia_de_calculo(tmp_path)

    cirurgico.gravar_celulas(arquivo, ABA, {(1, 2): 5})

    partes = _partes(arquivo)
    assert "xl/calcChain.xml" not in partes
    assert b"calcChain" not in partes["[Content_Types].xml"]
    assert b"calcChain" not in partes["xl/_rels/workbook.xml.rels"]
    with openpyxl_de_verdade():
        ws = _ler(arquivo)
        assert ws["B1"].value == 5
        assert ws["B2"].value == "=A2*2"  # as outras fórmulas continuam


def test_sem_formula_a_cadeia_de_calculo_fica(tmp_path):
    arquivo = _com_cadeia_de_calculo(tmp_path)

    cirurgico.gravar_celulas(arquivo, ABA, {(1, 3): "TEXTO"})

    assert "xl/calcChain.xml" in _partes(arquivo)


def test_mestra_de_formula_compartilhada_e_recusada_sem_tocar_no_arquivo(tmp_path):
    arquivo = _com_cadeia_de_calculo(tmp_path, formula_b1='<f t="shared" ref="B1:B3" si="0">A1*2</f>')
    antes = arquivo.read_bytes()

    with pytest.raises(NotImplementedError, match="B1"):
        cirurgico.gravar_celulas(arquivo, ABA, {(1, 2): 5})

    assert arquivo.read_bytes() == antes


# ===========================================================================
# F. Erros que não podem estragar o arquivo
# ===========================================================================
def test_aba_inexistente_levanta_keyerror_sem_tocar_no_arquivo(tmp_path):
    arquivo = _copia(V2, tmp_path)
    antes = arquivo.read_bytes()

    with pytest.raises(KeyError, match="Aba Que Não Existe"):
        cirurgico.gravar_celulas(arquivo, "Aba Que Não Existe", {(1, 1): "X"})

    assert arquivo.read_bytes() == antes


def test_grava_por_cima_do_mesmo_arquivo(tmp_path):
    # Por cima, e não apaga-e-recria: o Box guarda a versão anterior do MESMO
    # arquivo. O inode igual é a prova, no Linux, de que não houve troca.
    arquivo = _copia(V2, tmp_path)
    inode = arquivo.stat().st_ino

    cirurgico.gravar_celulas(arquivo, ABA, {(6, 11): "COMPLETO"})

    assert arquivo.stat().st_ino == inode

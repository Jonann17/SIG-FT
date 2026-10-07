r"""
T0 do roteiro "Gestão PMIB no tratamento v2" -- o cabeçalho do `_STATUS_PMIB`
desceu para a LINHA 5.

Roteiro: `gestao-sobressalentes/07 - Diagnostico/Tarefa SIG-FT - Calculo e
Gravacao sem Perda.md`, etapa T0.

Desde 04/10/2026 os 47 `_STATUS_PMIB` (e o template) têm o cabeçalho na linha
5: a linha 4 virou a da revisão em uso -- "REVISÃO DA LISTA DE SOBRESSALENTES
ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/09/2026", mesclada e em texto. Quem lia
com `skiprows=3` (cabeçalho fixo na linha 4) passou a tratar essa frase como
cabeçalho: o modo "selecionar códigos" do módulo PDM dizia "Coluna 'CÓDIGO PMIB'
não encontrada", e o passo que cria as pastas das fichas, "Colunas ... não
encontradas no Excel (linha 4)".

Três garantias:
  A. nenhuma leitura da aba "Lista de Materiais" com linha fixa (guarda por AST,
     para a próxima mudança de layout não repetir o defeito);
  B. a leitura acha o cabeçalho nos dois layouts -- v2 (linha 5) e o antigo
     (linha 4), que ainda pode aparecer numa cópia velha;
  C. `config.LINHA_STATUS_PMIB`, o valor de *fallback*, é 5.
"""
from __future__ import annotations

import ast
import pathlib

from _openpyxl_de_verdade import openpyxl_de_verdade
from _pandas_de_verdade import pandas_de_verdade

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TEXTO_REVISAO = "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/09/2026"


# ===========================================================================
# A. Guarda: nenhuma leitura da "Lista de Materiais" com linha fixa
# ===========================================================================
def _e_a_aba_de_materiais(no):
    """`"Lista de Materiais"` literal, ou `config.ABA_LISTA_MATERIAIS`."""
    if isinstance(no, ast.Constant):
        return no.value == "Lista de Materiais"
    if isinstance(no, ast.Attribute):
        return no.attr == "ABA_LISTA_MATERIAIS"
    if isinstance(no, ast.Name):
        return no.id == "ABA_LISTA_MATERIAIS"
    return False


def _leituras_com_linha_fixa(fonte, nome_arquivo):
    achados = []
    for no in ast.walk(ast.parse(fonte, filename=nome_arquivo)):
        if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                and no.func.attr == "read_excel"):
            continue
        argumentos = {k.arg: k.value for k in no.keywords if k.arg}
        aba = argumentos.get("sheet_name")
        if aba is None or not _e_a_aba_de_materiais(aba):
            continue
        for chave in ("skiprows", "header"):
            valor = argumentos.get(chave)
            if isinstance(valor, ast.Constant) and isinstance(valor.value, int) \
                    and not isinstance(valor.value, bool):
                achados.append(f"{nome_arquivo}:{no.lineno} ({chave}={valor.value})")
    return achados


def test_guarda_pega_a_leitura_fixa_que_existia():
    # A guarda tem de acusar o padrão que quebrou -- senão ela passaria por
    # não saber ler, e não por o código estar limpo.
    fonte = 'df = pd.read_excel(arq, sheet_name="Lista de Materiais", skiprows=3)\n'
    assert _leituras_com_linha_fixa(fonte, "x.py") == ["x.py:1 (skiprows=3)"]


def test_guarda_aceita_a_linha_achada_e_ignora_outras_abas():
    fonte = (
        'df = pd.read_excel(arq, sheet_name="Lista de Materiais", skiprows=linha)\n'
        'df = pd.read_excel(arq, sheet_name=config.ABA_LISTA_MATERIAIS, header=None, nrows=30)\n'
        'df = pd.read_excel(arq, sheet_name="Especificações técnicas copiar", header=0)\n'
    )
    assert _leituras_com_linha_fixa(fonte, "x.py") == []


def test_nenhuma_leitura_da_lista_de_materiais_com_linha_fixa():
    achados = []
    for caminho in sorted((RAIZ / "sigft").rglob("*.py")):
        achados += _leituras_com_linha_fixa(
            caminho.read_text(encoding="utf-8"), str(caminho.relative_to(RAIZ)))
    assert achados == [], (
        "Leitura do _STATUS_PMIB com o cabeçalho numa linha FIXA. Desde 04/10/2026 "
        "ele está na linha 5 (a 4 é a da revisão em uso) -- ache a linha com "
        "`core.excel.headers.find_header_row`, como `pdm.ler_lista_materiais`: "
        + ", ".join(achados))


# ===========================================================================
# B. A leitura acha o cabeçalho nos dois layouts (pandas e openpyxl reais)
# ===========================================================================
def _gravar_status_pmib(caminho, linha_cabecalho, com_revisao):
    from openpyxl import Workbook  # o real: só chamado dentro do bloco

    wb = Workbook()
    ws = wb.active
    ws.title = "Lista de Materiais"
    ws["A1"] = "CONTROLE DE FICHAS TÉCNICAS -- DADOS SINTÉTICOS"
    if com_revisao:
        ws.cell(row=linha_cabecalho - 1, column=1, value=TEXTO_REVISAO)
        ws.merge_cells(start_row=linha_cabecalho - 1, start_column=1,
                       end_row=linha_cabecalho - 1, end_column=4)
    for coluna, nome in enumerate(["ITEM", "DESCRIÇÃO", "CÓDIGO PMIB", "PDM usado"], start=1):
        ws.cell(row=linha_cabecalho, column=coluna, value=nome)
    itens = [
        (1, "PARAFUSO SEXTAVADO", "4500063671.0123", "PDM.1001.001"),
        # Número, não texto: perdeu o zero do fim na conversão -- a
        # normalização canônica o devolve (".012" -> ".0120").
        (2, "PORCA SEXTAVADA", 4500063671.012, "PDM.1002.001"),
    ]
    for deslocamento, valores in enumerate(itens, start=1):
        for coluna, valor in enumerate(valores, start=1):
            ws.cell(row=linha_cabecalho + deslocamento, column=coluna, value=valor)
    wb.save(caminho)
    return caminho


def test_ler_lista_materiais_acha_o_cabecalho_na_linha_5_do_layout_v2(tmp_path):
    from sigft.services import pdm

    with openpyxl_de_verdade(), pandas_de_verdade(pdm):
        arquivo = _gravar_status_pmib(tmp_path / "v2_STATUS_PMIB.xlsx", 5, com_revisao=True)
        df = pdm.ler_lista_materiais(arquivo)

        assert list(df.columns)[:4] == ["ITEM", "DESCRIÇÃO", "CÓDIGO PMIB", "PDM usado"]
        assert list(df["DESCRIÇÃO"]) == ["PARAFUSO SEXTAVADO", "PORCA SEXTAVADA"]


def test_ler_lista_materiais_continua_lendo_o_layout_antigo_linha_4(tmp_path):
    from sigft.services import pdm

    with openpyxl_de_verdade(), pandas_de_verdade(pdm):
        arquivo = _gravar_status_pmib(tmp_path / "v1_STATUS_PMIB.xlsx", 4, com_revisao=False)
        df = pdm.ler_lista_materiais(arquivo)

        assert "CÓDIGO PMIB" in df.columns
        assert len(df) == 2


def test_codigos_pmib_da_lista_le_o_v2_e_normaliza(tmp_path):
    # É o que o modo "selecionar códigos" da tela do PDM mostra na janela de
    # seleção -- o ponto exato que quebrou com o layout v2.
    from sigft.services import pdm

    with openpyxl_de_verdade(), pandas_de_verdade(pdm):
        arquivo = _gravar_status_pmib(tmp_path / "v2_STATUS_PMIB.xlsx", 5, com_revisao=True)

        assert pdm.codigos_pmib_da_lista(arquivo) == ["4500063671.0120", "4500063671.0123"]


def test_processar_pastas_fichas_le_o_v2(tmp_path):
    from sigft.services import pdm

    with openpyxl_de_verdade(), pandas_de_verdade(pdm):
        arquivo = _gravar_status_pmib(tmp_path / "v2_STATUS_PMIB.xlsx", 5, com_revisao=True)
        destino = tmp_path / "fichas"
        destino.mkdir()

        criados, mensagem = pdm.processar_pastas_fichas(str(arquivo), str(destino))

    assert [c[0] for c in criados] == ["4500063671.0123", "4500063671.0120"]
    assert mensagem == "2 pastas processados."
    assert (destino / "4500063671.0123").is_dir()


def test_processar_pastas_fichas_explica_quando_falta_coluna(tmp_path):
    # Sem a linha fixa, a mensagem não pode mais citar "(linha 4)": ela diz o
    # que foi procurado e onde.
    from sigft.services import pdm

    with openpyxl_de_verdade(), pandas_de_verdade(pdm):
        from openpyxl import Workbook

        wb = Workbook()
        wb.active.title = "Lista de Materiais"
        wb.active["A5"] = "OUTRA COISA"
        wb.save(tmp_path / "sem_colunas.xlsx")

        criados, mensagem = pdm.processar_pastas_fichas(str(tmp_path / "sem_colunas.xlsx"), str(tmp_path))

    assert criados == []
    assert "CÓDIGO PMIB" in mensagem and "PDM usado" in mensagem
    assert "linha 4" not in mensagem


# ===========================================================================
# C. O fallback
# ===========================================================================
def test_linha_status_pmib_de_fallback_e_5():
    from sigft import config

    assert config.LINHA_STATUS_PMIB == 5

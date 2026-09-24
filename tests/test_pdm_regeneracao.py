r"""Regenerar as pastas From Itaipu e Modificados a partir da planilha, com a
revisão no nome (`services/pdm_regeneracao.py`). Com openpyxl REAL."""
from __future__ import annotations

import os

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade
from sigft.services import pdm, pdm_regeneracao


@pytest.fixture
def openpyxl_real():
    with openpyxl_de_verdade(pdm) as modulo:
        yield modulo


def _linha_mestra(codigo, revisao, caract, *, seq, ajuda=None, titulo, base, modif=""):
    """Uma linha da aba TEMPLATE_PDM, nas colunas REAIS (A=0 ... X=23)."""
    linha = [None] * 24
    linha[0], linha[1] = codigo, codigo.split(".")[1]
    linha[2] = linha[3] = titulo
    linha[4] = linha[5] = base
    linha[6] = linha[7] = modif
    linha[9], linha[13], linha[16], linha[18] = revisao, seq, caract, ajuda
    return linha


def _escrever_mestra(caminho, dados):
    """O layout REAL da planilha de 23/09/2026: título mesclado A1:X1, data da
    exportação em A2/B2, A5:X5 mesclado, cabeçalho na 6, painel congelado em
    A6, autofiltro, largura e altura próprias."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TEMPLATE_PDM"
    ws["A1"] = "TEMPLATE PARA LA IMPORTACIÓN/EXPORTACIÓN DE PDM"
    ws.merge_cells("A1:X1")
    ws["A2"], ws["B2"] = "Exportado el:", "23/09/2026 11:02:02"
    ws["A5"] = "PDM - PADRÓN DESCRIPTIVO DE MATERIALES"
    ws.merge_cells("A5:X5")
    ws["A6"] = "CÓDIGO PDM"
    ws["A6"].font = Font(bold=True)
    ws["A6"].fill = PatternFill("solid", fgColor="FFFF00")
    ws.row_dimensions[1].height = 87
    ws.column_dimensions["A"].width = 17
    ws.freeze_panes = "A6"
    for linha in dados:
        ws.append(linha)
        ws.cell(row=ws.max_row, column=17).font = Font(color="FF0000")
    ws.auto_filter.ref = f"A6:X{ws.max_row}"
    wb.save(caminho)


ACUMULADOR = dict(titulo="ACUMULADOR", base="ACUMULADOR")
EXTENSAO = dict(titulo="EXTENSAO/TRONCO TORRE", base="EXTENSAO", modif="TRONCO TORRE")


@pytest.fixture
def mestra(tmp_path, openpyxl_real):
    caminho = str(tmp_path / "PDMs_SAM-GM.xlsx")
    _escrever_mestra(caminho, [
        _linha_mestra("PDM.1650.001", "2", "DIMENSOES", seq="1", ajuda="Indicar as dimensoes.", **ACUMULADOR),
        _linha_mestra("PDM.1650.001", "2", "PESO", seq="3", **ACUMULADOR),
        _linha_mestra("PDM.1650.001", "2", "MATERIAL", seq="2", ajuda="Indicar o material.", **ACUMULADOR),
        _linha_mestra("PDM.5445.007", "1", "ALTURA", seq="1", ajuda="Indicar a altura.", **EXTENSAO),
    ])
    return caminho


NOVO_ACUMULADOR = "PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx"


# =============================================================================
# A. Pasta Modificados
# =============================================================================
def test_regenera_a_modificados_com_a_revisao_no_nome(mestra, tmp_path):
    pasta = tmp_path / "modificados"

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    assert sorted(os.listdir(pasta)) == [
        NOVO_ACUMULADOR, "PDM_5445_007 - EXTENSAO-TRONCO TORRE - R1_formatado.xlsx"]


def test_o_pdm_formatado_segue_a_secuencia_e_nao_tem_nan(mestra, tmp_path, openpyxl_real):
    pasta = tmp_path / "modificados"

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))
    ws = openpyxl_real.load_workbook(pasta / NOVO_ACUMULADOR).active

    assert [ws.cell(row=i, column=1).value for i in (1, 2, 3)] == [
        "1 - DIMENSOES (Indicar as dimensoes.):",
        "2 - MATERIAL (Indicar o material.):",
        "3 - PESO:",
    ]
    assert {"A1:J1", "K1:T1"} <= {str(r) for r in ws.merged_cells.ranges}
    assert ws["A1"].font.size == 8
    assert ws.row_dimensions[1].height == 32


def test_a_versao_antiga_vai_para_versoes_antigas_sem_ser_apagada(mestra, tmp_path):
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    (pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").write_bytes(b"velho")

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    guardado = pasta / "_versoes_antigas" / "PDM_1650_001 - ACUMULADOR_formatado.xlsx"
    assert guardado.read_bytes() == b"velho"
    assert not (pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").exists()
    assert (pasta / NOVO_ACUMULADOR).exists()


def test_nome_repetido_em_versoes_antigas_ganha_numero(mestra, tmp_path):
    pasta = tmp_path / "modificados"
    (pasta / "_versoes_antigas").mkdir(parents=True)
    (pasta / "_versoes_antigas" / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").write_bytes(b"primeiro")
    (pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").write_bytes(b"segundo")

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    antigas = pasta / "_versoes_antigas"
    assert (antigas / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").read_bytes() == b"primeiro"
    assert (antigas / "PDM_1650_001 - ACUMULADOR_formatado (2).xlsx").read_bytes() == b"segundo"


def test_arquivo_ja_na_revisao_atual_nao_e_regravado(mestra, tmp_path):
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    (pasta / NOVO_ACUMULADOR).write_bytes(b"sentinela")
    logs = []

    resumo = pdm_regeneracao.regenerar_pastas(mestra, str(pasta), log_callback=logs.append)

    assert (pasta / NOVO_ACUMULADOR).read_bytes() == b"sentinela"
    assert "ja em dia (R2)" in "\n".join(logs)
    assert "1 novo(s), 0 atualizado(s), 1 ja em dia, 0 falha(s)" in resumo


def test_ja_em_dia_ainda_move_a_versao_antiga_que_sobrou(mestra, tmp_path):
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    (pasta / NOVO_ACUMULADOR).write_bytes(b"sentinela")
    (pasta / "PDM_1650_001 - ACUMULADOR - R1_formatado.xlsx").write_bytes(b"r1")

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    assert (pasta / NOVO_ACUMULADOR).read_bytes() == b"sentinela"
    assert (pasta / "_versoes_antigas" / "PDM_1650_001 - ACUMULADOR - R1_formatado.xlsx").exists()


def test_nao_mexe_no_arquivo_do_outro_tipo_na_mesma_pasta(mestra, tmp_path):
    """Na Modificados, só o que tem `_formatado` é versão antiga."""
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    (pasta / "PDM_1650_001 - ACUMULADOR.xlsx").write_bytes(b"outro tipo")

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    assert (pasta / "PDM_1650_001 - ACUMULADOR.xlsx").read_bytes() == b"outro tipo"


def test_desistir_do_arquivo_aberto_nao_grava_o_novo(mestra, tmp_path, monkeypatch):
    """Arquivo aberto no Excel: a janela "feche e tente de novo" aparece
    (`retry_lock`). Se o usuário desistir, a pasta NÃO fica com duas versões."""
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    antigo = pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx"
    antigo.write_bytes(b"aberto no Excel")

    def move_travado(origem, destino):
        raise PermissionError("[WinError 32] arquivo em uso")

    monkeypatch.setattr(pdm_regeneracao.shutil, "move", move_travado)
    perguntados = []

    def retry_lock(caminho):
        perguntados.append(caminho)
        return False

    resumo = pdm_regeneracao.regenerar_pastas(mestra, str(pasta), retry_lock=retry_lock)

    assert perguntados == [str(antigo)]
    assert antigo.read_bytes() == b"aberto no Excel"
    assert not (pasta / NOVO_ACUMULADOR).exists()
    assert "1 falha(s)" in resumo


def test_codigo_duplicado_avisa_quem_ficou_de_fora(tmp_path, openpyxl_real):
    caminho = str(tmp_path / "PDMs.xlsx")
    _escrever_mestra(caminho, [
        _linha_mestra("PDM.3010.007", "1", "NORMAS TECNICAS APLICAVEIS", seq="7",
                      titulo="ACOPLAMENTO ROSCADO", base="ACOPLAMENTO", modif="ROSCADO"),
        _linha_mestra("PDM.3010.007", "0", "COMPRIMENTO TOTAL", seq="2",
                      titulo="FIXADOR", base="FIXADOR"),
    ])
    pasta = tmp_path / "modificados"
    logs = []

    pdm_regeneracao.regenerar_pastas(caminho, str(pasta), log_callback=logs.append)
    ws = openpyxl_real.load_workbook(
        pasta / "PDM_3010_007 - ACOPLAMENTO ROSCADO - R1_formatado.xlsx").active

    assert "a planilha traz tambem FIXADOR (R0)" in "\n".join(logs)
    assert ws.cell(row=1, column=1).value == "1 - NORMAS TECNICAS APLICAVEIS:"
    assert ws.cell(row=2, column=1).value is None


# =============================================================================
# B. Pasta From Itaipu (o fatiador que lê a planilha UMA vez)
# =============================================================================
def test_regenera_a_from_itaipu_com_a_revisao_no_nome(mestra, tmp_path):
    pasta = tmp_path / "from_itaipu"

    pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"), str(pasta))

    assert sorted(os.listdir(pasta)) == [
        "PDM_1650_001 - ACUMULADOR - R2.xlsx", "PDM_5445_007 - EXTENSAO-TRONCO TORRE - R1.xlsx"]


def test_a_fatia_tem_o_cabecalho_e_as_linhas_na_ordem_da_secuencia(mestra, tmp_path, openpyxl_real):
    pasta = tmp_path / "from_itaipu"

    pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"), str(pasta))
    wb = openpyxl_real.load_workbook(pasta / "PDM_1650_001 - ACUMULADOR - R2.xlsx")
    ws = wb["TEMPLATE_PDM"]

    assert wb.sheetnames == ["TEMPLATE_PDM"]
    assert ws["A1"].value == "TEMPLATE PARA LA IMPORTACIÓN/EXPORTACIÓN DE PDM"
    assert ws["B2"].value == "23/09/2026 11:02:02"
    assert [ws.cell(row=r, column=17).value for r in (7, 8, 9)] == ["DIMENSOES", "MATERIAL", "PESO"]
    assert ws.max_row == 9


def test_a_fatia_copia_a_formatacao_da_planilha(mestra, tmp_path, openpyxl_real):
    pasta = tmp_path / "from_itaipu"

    pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"), str(pasta))
    ws = openpyxl_real.load_workbook(pasta / "PDM_1650_001 - ACUMULADOR - R2.xlsx")["TEMPLATE_PDM"]

    assert {"A1:X1", "A5:X5"} <= {str(r) for r in ws.merged_cells.ranges}
    assert ws.freeze_panes == "A6"
    assert ws.auto_filter.ref == "A6:X9"
    assert ws.column_dimensions["A"].width == 17
    assert ws.row_dimensions[1].height == 87
    assert ws["A6"].font.bold is True
    assert ws["A6"].fill.fgColor.rgb == "00FFFF00"
    assert ws.cell(row=7, column=17).font.color.rgb == "00FF0000"
    # a 9 reaproveita o estilo ja montado na 7 (ver `_CopiadorDeEstilo`)
    assert ws.cell(row=9, column=17).font.color.rgb == "00FF0000"


def test_a_altura_viaja_com_a_linha_e_nao_com_a_posicao(mestra, tmp_path, openpyxl_real):
    """O "Fatiar" antigo reescrevia a própria aba da planilha depois de um
    `delete_rows`, que não desloca as alturas: cada linha herdava a altura de
    quem ocupava a mesma POSIÇÃO na planilha (conferido em 2026-09-24 nos
    arquivos que ele gerou). Aqui MATERIAL (SECUENCIA 2) sai da linha 9 para a
    8 e leva a altura dela junto."""
    wb = openpyxl_real.load_workbook(mestra)
    for linha, altura in ((7, 20), (8, 40), (9, 60)):
        wb["TEMPLATE_PDM"].row_dimensions[linha].height = altura
    wb.save(mestra)
    pasta = tmp_path / "from_itaipu"

    pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"), str(pasta))
    ws = openpyxl_real.load_workbook(pasta / "PDM_1650_001 - ACUMULADOR - R2.xlsx")["TEMPLATE_PDM"]

    assert [ws.cell(row=r, column=17).value for r in (7, 8, 9)] == ["DIMENSOES", "MATERIAL", "PESO"]
    assert [ws.row_dimensions[r].height for r in (7, 8, 9)] == [20, 60, 40]


# =============================================================================
# C. Entrada que não serve: recusa ANTES de tocar em arquivo
# =============================================================================
def test_as_duas_pastas_iguais_sao_recusadas(mestra, tmp_path):
    pasta = tmp_path / "mesma"

    with pytest.raises(ValueError, match="nao podem ser a mesma"):
        pdm_regeneracao.regenerar_pastas(mestra, str(pasta), str(pasta))

    assert not pasta.exists()


def test_sem_pasta_modificados_e_recusado(mestra):
    with pytest.raises(ValueError, match="Pasta dos PDMs Modificados"):
        pdm_regeneracao.regenerar_pastas(mestra, "")


def test_sem_pasta_from_itaipu_so_a_modificados_e_regenerada(mestra, tmp_path):
    resumo = pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"))

    assert "PDMs From Itaipu: pasta nao informada, nao foi regenerada." in resumo


def test_planilha_no_formato_antigo_e_recusada(tmp_path, openpyxl_real):
    caminho = str(tmp_path / "manipulada.xlsx")
    wb = openpyxl_real.Workbook()
    wb.active.title = "PDMs"
    wb.active.append(["PDM COMPLETO"])
    wb.active.append(["PDM.4820.004 - VALVULA ESFERA"])
    wb.save(caminho)

    with pytest.raises(ValueError, match="TEMPLATE_PDM"):
        pdm_regeneracao.regenerar_pastas(caminho, str(tmp_path / "modificados"))


# =============================================================================
# D. Custo: a planilha e varrida uma vez, nao uma vez por linha
# =============================================================================
class _PlanilhaEspia:
    """Repassa tudo para a aba de verdade e conta o que custa caro: ler
    `max_column`/`max_row` (o openpyxl varre TODAS as celulas para
    responder), `ws[linha]` e `iter_rows` sem os limites (que leem os dois
    por dentro)."""

    def __init__(self, ws):
        self._ws = ws
        self.varreduras = 0

    @property
    def max_column(self):
        self.varreduras += 1
        return self._ws.max_column

    @property
    def max_row(self):
        self.varreduras += 1
        return self._ws.max_row

    def __getitem__(self, chave):
        self.varreduras += 1
        return self._ws[chave]

    def iter_rows(self, *args, **kwargs):
        if kwargs.get("max_col") is None or kwargs.get("max_row") is None:
            self.varreduras += 1
        return self._ws.iter_rows(*args, **kwargs)

    def __getattr__(self, nome):
        return getattr(self._ws, nome)


def test_fatiar_nao_varre_a_planilha_inteira_a_cada_linha(mestra, tmp_path, openpyxl_real):
    """Medido na planilha real (2026-09-24): `ws[linha]` do openpyxl varre as
    ~530 mil celulas para calcular `max_column` A CADA LINHA copiada -- 3,5 s
    por PDM, uns 70 minutos para os 1.199. A varredura acontece uma vez por
    regeneracao (em `regenerar_pastas`), nunca por linha."""
    from sigft.core import pdm_catalogo

    espia = _PlanilhaEspia(openpyxl_real.load_workbook(mestra)["TEMPLATE_PDM"])
    for p in pdm_catalogo.carregar(mestra).pdms:
        pdm_regeneracao._gravar_fatia(p, str(tmp_path / f"{p.codigo}.xlsx"), espia, None,
                                      ultima_coluna=24,
                                      copiador=pdm_regeneracao._CopiadorDeEstilo())

    assert espia.varreduras == 0


def test_cada_estilo_da_planilha_e_copiado_uma_vez_so(mestra, tmp_path, openpyxl_real, monkeypatch):
    """O `copy()` de estilo do openpyxl faz ida e volta em XML (`to_tree` +
    `from_tree`), e atribuir o estilo compara por hash com os que o workbook
    ja tem. Celula a celula, eram 830 ms por PDM na planilha real (uns 16
    minutos para os 1.199); copiando cada estilo de ORIGEM uma vez, 18 ms. A
    planilha real tem 18 estilos distintos."""
    from sigft.core import pdm_catalogo

    copias = []
    copy_de_verdade = pdm_regeneracao.copy
    monkeypatch.setattr(pdm_regeneracao, "copy",
                        lambda objeto: copias.append(objeto) or copy_de_verdade(objeto))
    ws = openpyxl_real.load_workbook(mestra)["TEMPLATE_PDM"]
    copiador = pdm_regeneracao._CopiadorDeEstilo()
    for p in pdm_catalogo.carregar(mestra).pdms:
        pdm_regeneracao._gravar_fatia(p, str(tmp_path / f"{p.codigo}.xlsx"), ws, None,
                                      ultima_coluna=24, copiador=copiador)
    estilos_distintos = {tuple(c._style) for linha in ws.iter_rows(max_col=24)
                         for c in linha if c.has_style}

    # fonte, borda, preenchimento e alinhamento: 4 copias por estilo, no maximo
    assert len(copias) <= 4 * len(estilos_distintos)

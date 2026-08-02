"""Gera a impressão digital semântica da saída ATUAL (pré-otimização) de
`pdm.pdms_fromItaipu_lista_geral` e `pdm.aplicar_templates_fichas`.

Roda FORA do pytest de propósito: assim o `conftest.py` (que troca openpyxl
por um MagicMock) não é carregado e o openpyxl REAL é usado.

Impressão digital = conteúdo + estilo célula a célula. Não dá para comparar
os BYTES do .xlsx: é um ZIP e carrega timestamps, então dois saves do mesmo
conteúdo já diferem. O que importa (e o que o aceite quer dizer com "saída
byte-idêntica") é que nada do conteúdo/formatação mude.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, "/home/user/SIG-FT")

# `pdm.py` importa pandas no topo, mas NENHUMA das 2 funções deste checkpoint
# o usa (ambas são openpyxl puro). Stub só do pandas -- openpyxl fica REAL,
# que é o ponto de rodar isto fora do pytest.
from unittest.mock import MagicMock
sys.modules.setdefault("pandas", MagicMock(name="pandas"))

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from sigft.services import pdm


def impressao_digital(caminho):
    """Conteúdo + estilo de cada célula, em forma comparável e estável."""
    wb = load_workbook(caminho)
    saida = {"abas": wb.sheetnames, "planilhas": {}}
    for nome in wb.sheetnames:
        ws = wb[nome]
        celulas = {}
        for linha in ws.iter_rows():
            for c in linha:
                if c.value is None and not c.has_style:
                    continue
                celulas[c.coordinate] = {
                    "valor": c.value,
                    "fonte_nome": c.font.name,
                    "fonte_tam": c.font.size,
                    "fonte_bold": c.font.bold,
                    "fonte_cor": getattr(c.font.color, "rgb", None) if c.font.color else None,
                    "borda": [
                        getattr(c.border.left, "style", None),
                        getattr(c.border.right, "style", None),
                        getattr(c.border.top, "style", None),
                        getattr(c.border.bottom, "style", None),
                    ],
                    "fill": getattr(c.fill, "fgColor", None) and getattr(c.fill.fgColor, "rgb", None),
                    "num_fmt": c.number_format,
                    "align_wrap": c.alignment.wrap_text,
                    "align_vert": c.alignment.vertical,
                }
        saida["planilhas"][nome] = {
            "celulas": celulas,
            "merges": sorted(str(m) for m in ws.merged_cells.ranges),
            "alturas": {str(k): v.height for k, v in sorted(ws.row_dimensions.items()) if v.height},
            "max_row": ws.max_row,
            "max_col": ws.max_column,
        }
    wb.close()
    return saida


def montar_lista_geral(caminho):
    """Fonte sintética no formato que `pdms_fromItaipu_lista_geral` espera:
    aba TEMPLATE_PDM, 6 linhas de cabeçalho, dados a partir da linha 7,
    código na coluna A e descrição na coluna D."""
    wb = Workbook()
    ws = wb.active
    ws.title = "TEMPLATE_PDM"
    for i in range(1, 7):
        ws.cell(row=i, column=1, value=f"CABECALHO {i}")
        ws.cell(row=i, column=4, value=f"COL D {i}")
        ws.cell(row=i, column=1).font = Font(bold=True, size=11)
        ws.cell(row=i, column=1).fill = PatternFill("solid", fgColor="FFFF00")
    dados = [
        ("PDM.4020.001", "BOMBA CENTRIFUGA"),
        ("PDM.4020.001", "BOMBA CENTRIFUGA"),  # 2 linhas do mesmo codigo
        ("PDM.5895.003", "SWITCH"),
        ("PDM.6720.001", "CAMERA"),
    ]
    borda = Border(left=Side("thin"), right=Side("thin"))
    for j, (cod, desc) in enumerate(dados, start=7):
        ws.cell(row=j, column=1, value=cod).border = borda
        ws.cell(row=j, column=2, value=f"marca-{j}")
        ws.cell(row=j, column=4, value=desc)
        ws.cell(row=j, column=4).alignment = Alignment(wrap_text=True, vertical="top")
    # 2a aba, que a funcao deve REMOVER na saida
    wb.create_sheet("OUTRA_ABA")["A1"] = "nao deve sobrar"
    wb.save(caminho)
    wb.close()


def montar_template_ficha(caminho):
    wb = Workbook()
    ws = wb.active
    ws.title = "Ficha Técnica Padrão"
    ws["B2"] = "FICHA TECNICA"
    ws["B2"].font = Font(bold=True, size=14)
    ws.cell(row=79, column=3, value=None)
    wb.save(caminho)
    wb.close()


def montar_pdm_modificado(caminho):
    wb = Workbook()
    ws = wb.active
    for i, (d, r) in enumerate([("Vazão", "100 m3/h"), ("Pressão", "10 bar"), (None, None), ("Tensão", "440 V")], start=1):
        ws.cell(row=i, column=1, value=d)
        ws.cell(row=i, column=2, value=r)
    wb.save(caminho)
    wb.close()


def main():
    base = tempfile.mkdtemp()
    resultado = {}

    # --- 1. pdms_fromItaipu_lista_geral ---
    origem = os.path.join(base, "lista_geral.xlsx")
    destino = os.path.join(base, "saida_pdms")
    os.makedirs(destino)
    montar_lista_geral(origem)
    msg = pdm.pdms_fromItaipu_lista_geral(origem, destino)
    resultado["lista_geral"] = {
        "mensagem": msg,
        "arquivos": sorted(os.listdir(destino)),
        "conteudo": {f: impressao_digital(os.path.join(destino, f)) for f in sorted(os.listdir(destino))},
    }

    # --- 2. aplicar_templates_fichas ---
    template = os.path.join(base, "template.xlsx")
    pasta_pdms = os.path.join(base, "pdms_mod")
    saida_fichas = os.path.join(base, "fichas")
    os.makedirs(pasta_pdms)
    os.makedirs(saida_fichas)
    montar_template_ficha(template)
    montar_pdm_modificado(os.path.join(pasta_pdms, "PDM_4020_001 - BOMBA.xlsx"))
    lista = [("4500063671.0001", "PDM.4020.001 - BOMBA", saida_fichas)]
    msg2, log2 = pdm.aplicar_templates_fichas(lista, pasta_pdms, template)
    resultado["templates_fichas"] = {
        "mensagem": msg2,
        "log": log2,
        "arquivos": sorted(os.listdir(saida_fichas)),
        "conteudo": {f: impressao_digital(os.path.join(saida_fichas, f)) for f in sorted(os.listdir(saida_fichas))},
    }

    destino_json = "/home/user/SIG-FT/tests/fixtures/pdm_io_baseline.json"
    os.makedirs(os.path.dirname(destino_json), exist_ok=True)
    with open(destino_json, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    print("baseline gravado:", destino_json)
    print("  lista_geral ->", resultado["lista_geral"]["mensagem"])
    print("  arquivos    ->", resultado["lista_geral"]["arquivos"])
    print("  fichas      ->", resultado["templates_fichas"]["mensagem"], resultado["templates_fichas"]["arquivos"])
    shutil.rmtree(base)


if __name__ == "__main__":
    main()

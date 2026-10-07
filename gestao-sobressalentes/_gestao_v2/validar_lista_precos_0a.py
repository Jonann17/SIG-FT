# -*- coding: utf-8 -*-
"""
Confere uma lista de precos 0A GERADA pelo SIG-FT (T6) contra o kit de teste.

    1. gere a lista com os parametros de fixtures/kit_lista_precos/esperado_lista_precos.json
       ("parametros"), a partir de:
         _STATUS_PMIB:  fixtures/kit_lista_precos/status/#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx
         template:      fixtures/kit_lista_precos/Lista de Sobressalentes com preço.xlsm
    2. python validar_lista_precos_0a.py "<pasta>/#ST00=TESTE01&MPB021.xlsm"
       -> confere o PASSO 1 (preenchimento, sem Excel): macro byte a byte, rodape intocado
       python validar_lista_precos_0a.py --com-excel "<arquivo>.xlsm"
       -> depois do PASSO 2 (Excel do trabalho): rodapes feitos pela macro, macro presente
       "LISTA OK" ou o que nao bate (sai com codigo 1)

Requisitos: openpyxl real (nao o dubl e da suite de testes do SIG-FT).
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import pathlib
import sys
import zipfile
from xml.sax.saxutils import escape

import openpyxl

AQUI = pathlib.Path(__file__).resolve().parent
KIT = AQUI / "fixtures" / "kit_lista_precos"
TEMPLATE = KIT / "Lista de Sobressalentes com preço.xlsm"
MACRO = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"


def _txt(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return v.date().isoformat() if isinstance(v, dt.datetime) else v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return None if v in (None, "") else str(v).strip()


def _parte_da_aba(z: zipfile.ZipFile, nome: str) -> str:
    import re
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rid = re.search(rf'<sheet [^>]*name="{re.escape(escape(nome))}"[^>]*r:id="([^"]+)"', wb).group(1)
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    alvo = re.search(rf'Id="{rid}"[^>]*Target="([^"]+)"|Target="([^"]+)"[^>]*Id="{rid}"', rels)
    alvo = alvo.group(1) or alvo.group(2)
    return alvo.lstrip("/") if alvo.startswith("/") else "xl/" + alvo


def validar(gerado: pathlib.Path, com_excel: bool = False) -> list[str]:
    esp = json.loads((KIT / "esperado_lista_precos.json").read_text(encoding="utf-8"))
    erros: list[str] = []
    if gerado.name != esp["saida_nome"]:
        erros.append(f"nome do arquivo {gerado.name!r}, esperado {esp['saida_nome']!r}")
    wb = openpyxl.load_workbook(gerado, keep_vba=True)
    wbv = openpyxl.load_workbook(gerado, keep_vba=True, data_only=True)      # valores em cache (formulas)

    # 1. itens
    ws = wb["Lista de Materiais"]
    lm = esp["lista_de_materiais"]
    for r, cols in lm["linhas"].items():
        for col in "ABCDEFGHIJ":
            if _txt(ws[f"{col}{r}"].value) != _txt(cols[col]):
                erros.append(f"Lista de Materiais {col}{r}: {ws[f'{col}{r}'].value!r}, esperado {cols[col]!r} "
                             f"(linha {cols['origem']} do _STATUS_PMIB)")
    for r in range(lm["linhas_limpas"]["de"], lm["linhas_limpas"]["ate"] + 1):
        sobra = [f"{c}{r}" for c in "ABCDEFGHIJK" if ws[f"{c}{r}"].value not in (None, "")]
        if sobra:
            erros.append(f"linha {r} devia estar vazia (numeração/exemplo do template): {sobra}")
    if ws["K5"].value not in (None, ""):
        erros.append("K5: a instrução do template continua lá")
    area = wb.defined_names.get("_xlnm.Print_Area")  # openpyxl >= 3.1: nomes locais ficam na aba
    area = ws.print_area if area is None else area.attr_text
    alvo = lm["area_de_impressao"].split("!")[1]
    if alvo.replace("$", "") not in str(area).replace("$", ""):
        erros.append(f"área de impressão {area!r}, esperado {lm['area_de_impressao']!r}")
    if com_excel and wbv["Lista de Materiais"]["C2"].value != lm["C2_valor_em_cache"]:   # o Excel recalcula ao salvar
        erros.append(f"Lista de Materiais C2 (cache da fórmula =Capa!E27): {wbv['Lista de Materiais']['C2'].value!r}")
    # 2. capa e contracapa
    for aba, celulas in (("Capa", esp["capa"]), ("Contracapa", esp["contracapa"])):
        for ref, v in celulas.items():
            if _txt(wb[aba][ref].value) != _txt(v):
                erros.append(f"{aba} {ref}: {wb[aba][ref].value!r}, esperado {v!r}")

    with zipfile.ZipFile(gerado) as zg, zipfile.ZipFile(TEMPLATE) as zt:
        # 3. rodapes: quem escreve e a MACRO (passo 2, no Excel); o passo 1 nao toca neles
        import re

        def rodape(z, aba):
            return re.findall(r"<headerFooter.*?</headerFooter>", z.read(_parte_da_aba(z, aba)).decode("utf-8"), re.S)
        for aba in esp["rodapes"]["abas"]:
            if not com_excel:
                if rodape(zg, aba) != rodape(zt, aba):
                    erros.append(f"rodapé de {aba} foi escrito por fora — quem escreve é a macro (passo 2)")
                continue
            xml = "".join(rodape(zg, aba))
            for antigo, novo in esp["rodapes"]["com_excel_o_que_a_macro_deixa"].items():
                if antigo in xml:
                    erros.append(f"rodapé de {aba}: ainda tem {antigo!r} — a macro não rodou")
                if escape(novo) not in xml:
                    erros.append(f"rodapé de {aba}: falta {novo!r}")
        # 4. macro preservada e arquivo continua .xlsm
        if MACRO not in zg.read("[Content_Types].xml").decode("utf-8"):
            erros.append("[Content_Types].xml: o arquivo deixou de ser .xlsm (macro)")
        if "xl/vbaProject.bin" not in zg.namelist():
            erros.append("a macro sumiu (xl/vbaProject.bin)")
        elif com_excel:
            try:
                from oletools.olevba import VBA_Parser
                codigo = "".join(m[-1] for m in VBA_Parser(str(gerado)).extract_macros())
                for nome in ("ConfigurarRodapeCompleto", "Worksheet_Change"):
                    if nome not in codigo:
                        erros.append(f"macro sem {nome}")
            except ImportError:
                pass
        if not com_excel:
            nomes_t = zt.namelist()
            for padrao in esp["partes_byte_a_byte_iguais_sem_excel"]:
                for n in fnmatch.filter(nomes_t, padrao):
                    if n not in zg.namelist() or zg.read(n) != zt.read(n):
                        erros.append(f"parte {n} mudou ou sumiu (tem de sair idêntica ao template)")
        # 5. nada interno vazou
        for n in zg.namelist():
            if n.endswith((".xml", ".rels")) and "NOTA INTERNA" in zg.read(n).decode("utf-8", "ignore"):
                erros.append(f"{n}: OBSERVAÇÕES do _STATUS_PMIB vazou para a lista de preços")
    return erros


def main() -> int:
    com_excel = "--com-excel" in sys.argv
    erros = validar(pathlib.Path([a for a in sys.argv[1:] if a != "--com-excel"][0]), com_excel)
    print("LISTA OK" if not erros else "\n".join(["DIFERENÇAS:"] + erros))
    return 0 if not erros else 1


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
Confere o resultado do Gestao PMIB (SIG-FT) rodado sobre uma COPIA do kit de teste.

    1. copie _gestao_v2/fixtures/kit_gestao_pmib/ para uma pasta temporaria (ex.: /tmp/kit)
    2. rode o Gestao PMIB com hoje = 2026-10-10:
         PMIBManager().executar_fluxo(caminho_api="/tmp/kit/docmanager_sintetico.xlsx",
                                      pasta_raiz_status="/tmp/kit/status",
                                      caminho_gerenciadora="/tmp/kit/mapeadora_sintetica.xlsx",
                                      hoje=date(2026, 10, 10))   # consumir o gerador inteiro
    3. python validar_kit_gestao_pmib.py /tmp/kit
       -> "KIT OK" ou a lista do que nao bate (sai com codigo 1)

    python validar_kit_gestao_pmib.py --referencia
       roda a implementacao de referencia deste pacote (regras_sobressalentes +
       migrar_status_pmib_v2.recalcular_situacao) numa copia e valida — prova que o
       esperado.json e atingivel.

Requisitos: openpyxl (real, nao o dubl e da suite de testes do SIG-FT).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
import sys
import tempfile
import zipfile

import openpyxl

AQUI = pathlib.Path(__file__).resolve().parent
KIT = AQUI / "fixtures" / "kit_gestao_pmib"
T1 = "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"
T2 = "#ST00=TESTE02&MPB020_STATUS_PMIB.xlsx"


def _inteiro(v):
    if isinstance(v, dt.datetime):
        from openpyxl.utils.datetime import to_excel
        return int(to_excel(v))
    try:
        return None if v in (None, "") else int(float(v))
    except (TypeError, ValueError):
        return None


def _partes(caminho: pathlib.Path) -> dict[str, bytes]:
    with zipfile.ZipFile(caminho) as z:
        return {n: z.read(n) for n in z.namelist()}


def validar(pasta: pathlib.Path) -> list[str]:
    esp = json.loads((KIT / "esperado.json").read_text(encoding="utf-8"))
    erros: list[str] = []
    status = pasta / "status"

    # 1. _STATUS_PMIB v2: situacao e dias de atraso, linha a linha
    e1 = esp["status_pmib"]["#ST00=TESTE01&MPB020"]
    ws = openpyxl.load_workbook(status / T1)["Lista de Materiais"]
    for r, v in e1["linhas"].items():
        sit, dias = ws[f"S{r}"].value or "", ws[f"T{r}"]
        if sit != v["situacao"]:
            erros.append(f"TESTE01 linha {r}: SITUAÇÃO {sit!r}, esperado {v['situacao']!r} ({v['por_que']})")
        if _inteiro(dias.value) != v["dias"]:
            erros.append(f"TESTE01 linha {r}: DIAS DE ATRASO {dias.value!r}, esperado {v['dias']!r}")
        if dias.value not in (None, "") and dias.is_date:
            erros.append(f"TESTE01 T{r}: DIAS DE ATRASO com formato de data (apareceria como data no Excel)")
    # 2. nada se perde: comentarios byte a byte, inventario, nome definido
    antes, depois = _partes(KIT / "status" / T1), _partes(status / T1)
    for parte in e1["partes_byte_a_byte_iguais"]:
        if antes.get(parte) != depois.get(parte):
            erros.append(f"TESTE01: parte {parte} mudou (comentários têm de sair idênticos)")
    if set(antes) - set(depois):
        erros.append(f"TESTE01: partes sumiram: {sorted(set(antes) - set(depois))}")
    wb_xml = depois.get("xl/workbook.xml", b"").decode("utf-8", "ignore")
    if "sigft_calculado_em" not in wb_xml:
        erros.append("TESTE01: falta o nome definido sigft_calculado_em")
    if b"x14:dataValidation" in antes.get("xl/worksheets/sheet1.xml", b"") and \
            b"x14:dataValidation" not in depois.get("xl/worksheets/sheet1.xml", b""):
        erros.append("TESTE01: listas suspensas de extensão (x14) sumiram — foi salvo com openpyxl?")
    # 3. layout antigo e isca: intocados
    for rel in (T2, f"testes_autospec/{T1}"):
        if (KIT / "status" / rel).read_bytes() != (status / rel).read_bytes():
            erros.append(f"{rel}: o arquivo foi alterado (não podia)")

    # 4. mapeadora = cadastro: nenhuma coluna nova; SITUAÇÃO NO PMIB, REVISÃO EM USO e link
    wm = openpyxl.load_workbook(pasta / "mapeadora_sintetica.xlsx")["Acompanhamento Sobressalente"]
    nomes = [str(c.value).strip() for c in wm[2] if c.value not in (None, "")]
    if nomes != [n.strip() for n in esp["mapeadora_cabecalho_inalterado"]]:
        erros.append(f"mapeadora: o cabeçalho mudou (nenhuma coluna de contagem pode ser criada): {nomes}")
    cab = {str(c.value).strip(): c.column for c in wm[2] if c.value}
    linhas = {str(wm.cell(r, cab["N° DOCUMENTO ITAIPU"]).value).strip(): r for r in range(3, wm.max_row + 1)
              if wm.cell(r, cab["N° DOCUMENTO ITAIPU"]).value}
    for lista, valores in esp["mapeadora"].items():
        r = linhas.get(lista)
        if r is None:
            erros.append(f"mapeadora: linha {lista} sumiu")
            continue
        for col, v in valores.items():
            atual = str(wm.cell(r, cab[col]).value or "").strip()
            alvo = v.split(" ")[0] if col == "REVISÃO EM USO" else v
            if atual != alvo:
                erros.append(f"mapeadora {lista} · {col}: {atual!r}, esperado {v!r}")
        link = wm.cell(r, cab["LINK DA PLANILHA"]).hyperlink
        destino = ((link.target or "") + "#" + (link.location or "")) if link else ""
        if "testes_autospec" in destino.lower():
            erros.append(f"mapeadora {lista}: o link aponta para a isca em testes_autospec")
        if valores["LINK DA PLANILHA"] and not destino.strip("#"):
            erros.append(f"mapeadora {lista}: 'Abrir Box' sem destino")
    if "VALOR VELHO" in str([[c.value for c in row] for row in wm.iter_rows()]):
        erros.append("mapeadora: SITUAÇÃO NO PMIB não foi recalculada")
    return erros


def referencia(pasta: pathlib.Path) -> None:
    """O que o SIG-FT corrigido deve fazer, pela implementacao de referencia deste pacote."""
    sys.path.insert(0, str(AQUI.parent / "_scripts"))
    sys.path.insert(0, str(AQUI))
    import regras_sobressalentes as R  # noqa: F401
    from migrar_status_pmib_v2 import recalcular_situacao
    from gerar_kit_teste_sigft import HOJE
    from xlsx_cirurgico import PlanilhaXlsx
    t1 = pasta / "status" / T1
    recalcular_situacao(t1, HOJE)                                   # T2 (so arquivos v2; TESTE02 e isca nao)
    p = PlanilhaXlsx(t1)
    p.definir_nome("sigft_calculado_em", f'"{HOJE.isoformat()}"')
    p.salvar()
    wb = openpyxl.load_workbook(pasta / "mapeadora_sintetica.xlsx")   # a sintetica nao tem nada que o openpyxl apague
    ws = wb["Acompanhamento Sobressalente"]
    cab = {str(c.value).strip(): c.column for c in ws[2] if c.value}
    arquivos = {"#ST00=TESTE01&MPB020": t1, "#ST00=TESTE02&MPB020": pasta / "status" / T2}
    for r in range(3, ws.max_row + 1):
        lista = ws.cell(r, cab["N° DOCUMENTO ITAIPU"]).value
        ws.cell(r, cab["SITUAÇÃO NO PMIB"]).value = cascata(arquivos.get(lista), "APROVADO")
        link = ws.cell(r, cab["LINK DA PLANILHA"])
        if lista in arquivos:
            link.value = "Abrir Box"
            link.hyperlink = f"status/{arquivos[lista].name}"
        if lista == "#ST00=TESTE01&MPB020":
            ws.cell(r, cab["REVISÃO EM USO"]).value = "1"                # T3-f: lido da linha de revisao
    wb.save(pasta / "mapeadora_sintetica.xlsx")


def cascata(caminho: pathlib.Path | None, status_revisao: str) -> str:
    """A SITUAÇÃO NO PMIB do pmib_manager (passo 6), reproduzida para a referencia."""
    sys.path.insert(0, str(AQUI))
    from migrar_status_pmib_v2 import cabecalho
    n = {}
    if caminho is not None:
        ws = openpyxl.load_workbook(caminho)["Lista de Materiais"]
        hdr, mapa = cabecalho(ws)
        vistos = set()
        for r in range(hdr + 1, ws.max_row + 1):
            pmib = str(ws.cell(r, mapa["CODIGO PMIB"]).value or "").strip()
            st = str(ws.cell(r, mapa["STATUS"]).value or "").strip().upper()
            if pmib and st != "DUPLICADO" and pmib not in vistos:
                vistos.add(pmib)
                n[st] = n.get(st, 0) + 1
    total = sum(n.values())
    g = lambda k: n.get(k, 0)  # noqa: E731
    ini, cria, forn, elab = g("INICIAR"), g("FICHA CRIADA"), g("COM O FORNECEDOR"), g("EM ELABORAÇÃO")
    ana, corr, aprov, na = g("EM ANÁLISE IB"), g("EM CORREÇÃO"), g("APROVADO"), g("N/A")
    if status_revisao in ("LISTA NÃO EMITIDA", "SEM LISTA"):
        return status_revisao
    if total == 0:
        return "INICIAR"
    for cond, sit in ((ini > 0, "CRIAÇÃO DAS FICHAS EM PROCESSO"), (corr > 0 and elab > 0, "CORREÇÃO / ELABORAÇÃO"),
                      (corr > 0 and aprov > 0, "EM CORREÇÃO / FINALIZADO"), (corr == total, "EM CORREÇÃO"),
                      (ana > 0 and elab > 0, "EM PROCESSO / ANÁLISE ITAIPU"), (ana == total, "EM ANÁLISE ITAIPU"),
                      (forn > 0 and elab > 0, "FORNECEDOR / ELABORAÇÃO"), (elab > 0, "EM PROCESSO DE PREENCHIMENTO"),
                      (forn == total, "FICHAS COM O FORNECEDOR"), (aprov + na == total, "FINALIZADO"),
                      (cria > 0 and forn == elab == ana == corr == aprov == 0, "FICHAS CRIADAS")):
        if cond:
            return sit
    return "EM ANDAMENTO"


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--referencia":
        with tempfile.TemporaryDirectory() as tmp:
            pasta = pathlib.Path(tmp) / "kit"
            shutil.copytree(KIT, pasta)
            referencia(pasta)
            erros = validar(pasta)
    else:
        erros = validar(pathlib.Path(sys.argv[1]))
    print("KIT OK" if not erros else "\n".join(["DIFERENÇAS:"] + erros))
    return 0 if not erros else 1


if __name__ == "__main__":
    sys.exit(main())

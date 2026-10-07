# -*- coding: utf-8 -*-
"""
Levanta o universo de fichas sem Aplicacao LMR, a partir da mapeadora no Box.

Separa em dois grupos, que exigem tratamento diferente:
  A) PASSIVO  — fichas ja emitidas a Itaipu sem LMR completa (em analise > com LMR)
  B) BACKLOG  — fichas criadas, ainda nao emitidas, sem LMR

So le o Box. Escreve em `_gerado/`.

Uso:  python _scripts/levantamento_lmr.py
"""
from __future__ import annotations

import collections
import datetime
import pathlib
import sys

try:
    import openpyxl
except ImportError:
    sys.exit("Falta openpyxl. Rode:  pip install openpyxl")

VAULT = pathlib.Path(__file__).resolve().parent.parent
GERADO = VAULT / "_gerado"
BOX = pathlib.Path.home() / "Box" / "CMI - Consórcio Itaipu" / "11 - Ger. Engenharia" / "15 - PDM"
MAPEADORA = BOX / "SOBRESSALENTES - PMIB" / "Mapeamento Listas de Sobressalentes.xlsx"
ABA = "Acompanhamento Sobressalente"


def achar(cab: list[str], nome: str):
    alvo = nome.upper()
    for i, h in enumerate(cab):
        if alvo in h.upper().replace("\n", " "):
            return i
    return None


def num(v) -> int:
    return int(v) if isinstance(v, (int, float)) else 0


def main() -> int:
    if not MAPEADORA.exists():
        sys.exit(f"Mapeadora nao encontrada:\n  {MAPEADORA}")

    wb = openpyxl.load_workbook(MAPEADORA, data_only=True, read_only=True)
    linhas_ws = list(wb[ABA].iter_rows(values_only=True))
    wb.close()

    cab = [str(c).strip() if c else "" for c in linhas_ws[1]]
    dados = [r for r in linhas_ws[2:] if r and r[0]]

    C = {n: achar(cab, n) for n in (
        "N° DOCUMENTO ITAIPU", "N° DOCUMENTO CMI", "ESPECIFICAÇÃO TÉCNICA", "CAPÍTULO",
        "RESPONSÁVEL", "PROCUREMENT", "SITUAÇÃO NO PMIB", "STATUS REAL",
        "EVENTOS DE PAGAMENTOS", "FICHAS EXISTENTES",
        "FICHAS COM APLICAÇÃO - LMR FINALIZADA", "FICHAS EM ANÁLISE DE ITAIPU",
        "FICHAS APROVADAS", "APTO PARA ENTREGA",
    )}

    def val(r, k, default=""):
        i = C[k]
        if i is None or r[i] is None:
            return default
        return str(r[i]).strip()

    registros = []
    for r in dados:
        existentes = num(r[C["FICHAS EXISTENTES"]]) if C["FICHAS EXISTENTES"] is not None else 0
        if existentes == 0:
            continue
        lmr = num(r[C["FICHAS COM APLICAÇÃO - LMR FINALIZADA"]])
        analise = num(r[C["FICHAS EM ANÁLISE DE ITAIPU"]])
        registros.append({
            "doc": val(r, "N° DOCUMENTO ITAIPU", "-"),
            "cmi": val(r, "N° DOCUMENTO CMI", "-"),
            "et": val(r, "ESPECIFICAÇÃO TÉCNICA", "-"),
            "cap": val(r, "CAPÍTULO", "-"),
            "resp": val(r, "RESPONSÁVEL", "(sem responsavel)"),
            "sit": val(r, "SITUAÇÃO NO PMIB", "-"),
            "ev": val(r, "EVENTOS DE PAGAMENTOS", "-"),
            "existentes": existentes,
            "lmr": lmr,
            "analise": analise,
            "sem_lmr": existentes - lmr,
            "passivo": max(0, analise - lmr),
        })

    tot_ex = sum(x["existentes"] for x in registros)
    tot_lmr = sum(x["lmr"] for x in registros)
    tot_sem = sum(x["sem_lmr"] for x in registros)
    grupo_a = sorted([x for x in registros if x["passivo"] > 0], key=lambda x: -x["passivo"])
    grupo_b = sorted([x for x in registros if x["sem_lmr"] > 0 and x["passivo"] == 0],
                     key=lambda x: -x["sem_lmr"])
    tot_a = sum(x["passivo"] for x in grupo_a)
    tot_b = sum(x["sem_lmr"] for x in grupo_b)

    hoje = datetime.date.today().isoformat()
    L: list[str] = []
    A = L.append

    A("---")
    A("tags: [gerado, lmr, levantamento]")
    A(f"gerado_em: {hoje}")
    A("fonte: Mapeamento Listas de Sobressalentes.xlsx")
    A("---")
    A("")
    A("# Levantamento — Fichas sem Aplicacao LMR")
    A("")
    A("> [!warning] Nota gerada automaticamente")
    A("> Rode `python _scripts/levantamento_lmr.py` para regenerar.")
    A(f"> Dados de **{hoje}**.")
    A("")
    A("## O numero")
    A("")
    A("| | Fichas |")
    A("|---|---:|")
    A(f"| Existentes (em {len(registros)} listas com ficha criada) | **{tot_ex}** |")
    A(f"| Com Aplicacao LMR finalizada | {tot_lmr} ({tot_lmr/tot_ex*100:.1f}%) |")
    A(f"| **Sem Aplicacao LMR** | **{tot_sem}** ({tot_sem/tot_ex*100:.1f}%) |")
    A(f"| → grupo A: **passivo**, ja emitidas a Itaipu | **{tot_a}** em {len(grupo_a)} listas |")
    A(f"| → grupo B: backlog, criadas e nao emitidas | {tot_b} em {len(grupo_b)} listas |")
    A("")
    A("> [!note] Como o passivo e calculado")
    A("> `FICHAS EM ANALISE DE ITAIPU` menos `FICHAS COM APLICACAO - LMR FINALIZADA`,")
    A("> por lista, com piso em zero. E uma **estimativa por agregado** — a mapeadora nao")
    A("> diz *quais* fichas individualmente. Para a lista nominal e preciso abrir cada")
    A("> `_STATUS_PMIB` e cruzar `APLICACAO - LMR` com")
    A("> `DATA DO EMAIL COMUNICANDO ENTREGA`.")
    A("")

    # ---------------- Grupo A
    A("## Grupo A — PASSIVO (urgencia maxima)")
    A("")
    A("Fichas **ja emitidas a Itaipu** sem Aplicacao LMR completa. Sao as que podem")
    A("voltar devolvidas, custando um ciclo de 2 a 3 meses cada.")
    A("")
    A("| Fichas | Doc. Itaipu | Doc. CMI | Capitulo | Responsavel | Evento |")
    A("|---:|---|---|---|---|---|")
    for x in grupo_a:
        A(f"| **{x['passivo']}** | `{x['doc']}` | `{x['cmi']}` | {x['cap'][:44]} | {x['resp']} | {x['ev']} |")
    A(f"| **{tot_a}** | | | **{len(grupo_a)} listas** | | |")
    A("")

    # ---------------- Grupo B
    A("## Grupo B — BACKLOG")
    A("")
    A("Fichas criadas, ainda **nao emitidas**. Fazer a LMR aqui e barato: entra junto do")
    A("preenchimento, antes da emissao, e nao gera devolucao.")
    A("")
    A("| Fichas | Doc. Itaipu | Capitulo | Situacao no PMIB | Responsavel |")
    A("|---:|---|---|---|---|")
    for x in grupo_b:
        A(f"| {x['sem_lmr']} | `{x['doc']}` | {x['cap'][:40]} | {x['sit']} | {x['resp']} |")
    A(f"| **{tot_b}** | | **{len(grupo_b)} listas** | | |")
    A("")

    # ---------------- agregados
    A("## Por Especificacao Tecnica")
    A("")
    agg = collections.defaultdict(lambda: [0, 0, 0, 0])
    for x in registros:
        a = agg[x["et"]]
        a[0] += 1; a[1] += x["existentes"]; a[2] += x["sem_lmr"]; a[3] += x["passivo"]
    A("| Especificacao Tecnica | Listas | Fichas | Sem LMR | Passivo |")
    A("|---|---:|---:|---:|---:|")
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1][2]):
        A(f"| {k} | {v[0]} | {v[1]} | **{v[2]}** | {v[3]} |")
    A("")

    A("## Por responsavel")
    A("")
    agr = collections.defaultdict(lambda: [0, 0, 0])
    for x in registros:
        if x["sem_lmr"] == 0:
            continue
        a = agr[x["resp"]]
        a[0] += 1; a[1] += x["sem_lmr"]; a[2] += x["passivo"]
    A("| Responsavel | Listas | Sem LMR | Passivo |")
    A("|---|---:|---:|---:|")
    for k, v in sorted(agr.items(), key=lambda kv: -kv[1][1]):
        A(f"| {k} | {v[0]} | {v[1]} | {v[2]} |")
    A("")

    A("## Eventos de pagamento atingidos pelo passivo")
    A("")
    evs = sorted({x["ev"] for x in grupo_a if x["ev"] != "-"})
    for e in evs:
        A(f"- `{e}`")
    A("")
    A("---")
    A("")
    A("Base de [[Plano de Acao - Aplicacao LMR]] · voltar para [[Secao - Aplicacao LMR]]")

    GERADO.mkdir(parents=True, exist_ok=True)
    destino = GERADO / "Levantamento - Fichas sem Aplicacao LMR.md"
    destino.write_text("\n".join(L), encoding="utf-8")
    print(f"OK -> {destino}")
    print(f"   {tot_ex} fichas | sem LMR: {tot_sem} | passivo: {tot_a} em {len(grupo_a)} listas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

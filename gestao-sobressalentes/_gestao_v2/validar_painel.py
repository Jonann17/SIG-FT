# -*- coding: utf-8 -*-
"""
Confere o painel HTML gerado pelo SIG-FT (T7 do roteiro) contra a implementacao de referencia
(`_scripts/gerar_prototipo_dashboard.py`), rodada no MESMO kit de teste e na mesma data.

    1. copie _gestao_v2/fixtures/kit_gestao_pmib/ para uma pasta temporaria (ex.: /tmp/kit)
       (pode ser a mesma copia em que o Gestao PMIB ja rodou — a referencia le a pasta como esta)
    2. gere o painel pelo SIG-FT com hoje = 2026-10-10:
         gerar_painel(pasta_pmib="/tmp/kit/status", mapeadora="/tmp/kit/mapeadora_sintetica.xlsx",
                      saida="/tmp/kit/painel.html", hoje=date(2026, 10, 10))
    3. python validar_painel.py /tmp/kit /tmp/kit/painel.html
       -> "PAINEL OK" ou a lista do que nao bate (sai com codigo 1)

    python validar_painel.py --referencia
       gera o painel com a propria referencia numa copia do kit e valida — prova que o
       validador e o kit estao certos.

O que e comparado (os dados embutidos em <script id="dados">, nao o desenho):
  - cada ficha (lista|PMIB): status, com quem, tipo, entregue, apto, situacao da autorizacao,
    dias de atraso, situacao LMR, pendencia, valor, data do e-mail, secoes;
  - cada lista: nome, ET, capitulo, status real, situacao no PMIB;
  - listas de precos, atividades e os achados de qualidade (titulo -> quantidade);
  - a pagina abre sem rede (nenhum script/estilo externo) e tem os filtros de ET e Capitulo.

Requisitos: pandas e openpyxl reais (nao os dubles da suite de testes do SIG-FT).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import shutil
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
KIT = AQUI / "fixtures" / "kit_gestao_pmib"
HOJE = dt.date(2026, 10, 10)
sys.path.insert(0, str(AQUI.parent / "_scripts"))

CAMPOS_FICHA = ("st", "q", "t", "en", "ap", "sa", "du", "sl", "pe", "v", "dt", "ok")
CAMPOS_LISTA = ("nome", "et", "cap", "sr", "sit")
CAMPOS_PRECO = ("geracao", "rev", "situacao", "lista")


def referencia(pasta: pathlib.Path) -> dict:
    import gerar_prototipo_dashboard as G
    return G.limpar(G.montar(HOJE, pasta / "status", pasta / "mapeadora_sintetica.xlsx"))


def dados_do_html(html: str) -> dict:
    m = re.search(r'<script id="dados" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit('o HTML nao tem <script id="dados" type="application/json"> com os dados')
    return json.loads(m.group(1).replace("<\\/", "</"))


def _por(chave, lista: list[dict]) -> dict:
    return {chave(x): x for x in lista}


def comparar(esp: dict, obt: dict, html: str) -> list[str]:
    erros: list[str] = []
    if obt.get("ref") != HOJE.isoformat():
        erros.append(f"data de referencia: esperado {HOJE.isoformat()}, veio {obt.get('ref')!r} (hoje injetavel?)")

    def bloco(nome, chave, campos):
        e = _por(chave, esp[nome])
        o = _por(chave, obt.get(nome) or [])
        for k in sorted(set(e) - set(o), key=str):
            erros.append(f"{nome}: falta {k}")
        for k in sorted(set(o) - set(e), key=str):
            erros.append(f"{nome}: sobra {k}")
        for k in sorted(set(e) & set(o), key=str):
            for c in campos:
                if e[k].get(c) != o[k].get(c):
                    erros.append(f"{nome} {k} · {c}: esperado {e[k].get(c)!r}, veio {o[k].get(c)!r}")

    bloco("itens", lambda x: (x["l"], x["p"]), CAMPOS_FICHA)
    bloco("listas", lambda x: x["l"], CAMPOS_LISTA)
    bloco("precos", lambda x: x["lp"], CAMPOS_PRECO)
    bloco("atividades", lambda x: (x.get("lista"), x.get("atividade")), ("sit", "fim_prev"))
    eq = {q["titulo"]: q["n"] for q in esp["qualidade"]}
    oq = {q["titulo"]: q["n"] for q in obt.get("qualidade") or []}
    if eq != oq:
        erros.append(f"qualidade: esperado {eq}, veio {oq}")

    externos = re.findall(r'<(?:script|link|img)[^>]+(?:src|href)="(?:https?:)?//[^"]+"', html)
    if externos:
        erros.append(f"a pagina depende de rede (tem de abrir offline): {externos[:3]}")
    for id_ in ("f-et", "f-cap", "f-lista"):
        if f'id="{id_}"' not in html:
            erros.append(f'falta o filtro id="{id_}" (ET, Capitulo e Lista, como no Power BI)')
    return erros


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--referencia":
        import gerar_prototipo_dashboard as G
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="kit_painel_"))
        shutil.copytree(KIT, tmp / "kit")
        pasta = tmp / "kit"
        html = G.gerar_html(referencia(pasta))
    elif len(sys.argv) == 3:
        pasta, arq = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
        html = arq.read_text(encoding="utf-8")
    else:
        print(__doc__)
        return 2
    esp = referencia(pasta)
    if not esp["itens"]:
        raise SystemExit(f"a referencia nao achou fichas em {pasta / 'status'} — pasta errada?")
    erros = comparar(esp, dados_do_html(html), html)
    if erros:
        print(f"PAINEL COM DIFERENCAS ({len(erros)}):")
        for e in erros[:60]:
            print("  -", e)
        return 1
    print(f"PAINEL OK — {len(esp['itens'])} fichas, {len(esp['listas'])} listas, "
          f"{len(esp['qualidade'])} achados de qualidade conferidos")
    return 0


if __name__ == "__main__":
    sys.exit(main())

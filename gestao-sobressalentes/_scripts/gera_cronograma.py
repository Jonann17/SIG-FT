# -*- coding: utf-8 -*-
"""
Gera o cronograma visual a partir da aba 'Atividades' da mapeadora.

Le a planilha, calcula os rollups em Python (nao depende do valor em cache das
formulas) e desenha um Gantt em SVG dentro de uma pagina HTML.

Barra clara  = previsto (DATA PREVISTA DE INICIO -> PREVISAO DE TERMINO)
Barra escura = realizado (DATA DE INICIO -> DATA DE TERMINO, ou ate hoje)

Uso:  python gera_cronograma.py [saida.html]
"""
from __future__ import annotations

import datetime
import html
import pathlib
import sys

import openpyxl

BOX = pathlib.Path(r"c:/Users/LCCoz/Box/CMI - Consórcio Itaipu/11 - Ger. Engenharia/15 - PDM/SOBRESSALENTES - PMIB")
ARQ = BOX / "Mapeamento Listas de Sobressalentes - COM ABA ATIVIDADES.xlsx"
ABA = "Atividades"
HOJE = datetime.date.today()

C_NV, C_COD, C_DESC = 1, 2, 3
C_PREV_INI, C_INI, C_PREV_FIM, C_FIM = 7, 8, 9, 10
C_STATUS, C_ALT, C_QUEM, C_CRIT, C_CHECK = 11, 12, 13, 15, 16

CORES = {
    "Não iniciada": ("#8FA6B8", "#42647E"),
    "Em desenvolvimento": ("#E0B678", "#A8501D"),
    "Travada": ("#DE9199", "#8C1D2A"),
    "Concluída": ("#8FC4AB", "#2C6650"),
}
PADRAO = ("#B8C4CE", "#54636F")

LARG_ROTULO = 340
MARGEM_DIR = 28
ALT_SIS = 32
ALT_ATIV = 25
TOPO = 54


def data(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return None


def ler():
    wb = openpyxl.load_workbook(ARQ, data_only=True)
    ws = wb[ABA]
    linhas = []
    for r in range(2, ws.max_row + 1):
        nv = ws.cell(r, C_NV).value
        if nv is None:
            continue
        linhas.append({
            "nv": int(nv),
            "codigo": str(ws.cell(r, C_COD).value or "").strip(),
            "desc": str(ws.cell(r, C_DESC).value or "").strip(),
            "prev_ini": data(ws.cell(r, C_PREV_INI).value),
            "ini": data(ws.cell(r, C_INI).value),
            "prev_fim": data(ws.cell(r, C_PREV_FIM).value),
            "fim": data(ws.cell(r, C_FIM).value),
            "status": str(ws.cell(r, C_STATUS).value or "").strip(),
            "alt": data(ws.cell(r, C_ALT).value),
            "quem": str(ws.cell(r, C_QUEM).value or "").strip(),
            "crit": ws.cell(r, C_CRIT).value,
            "ok": ws.cell(r, C_CHECK).value is True,
        })
    wb.close()

    # rollup calculado aqui, para nao depender do cache das formulas
    for i, li in enumerate(linhas):
        filhas = []
        for lj in linhas[i + 1:]:
            if lj["nv"] <= li["nv"]:
                break
            filhas.append(lj)
        if not filhas:
            continue
        for campo, fn in (("prev_ini", min), ("ini", min), ("prev_fim", max), ("fim", max)):
            vals = [f[campo] for f in filhas if f[campo]]
            li[campo] = fn(vals) if vals else None
        li["n_filhas"] = len([f for f in filhas if f["nv"] == li["nv"] + 1])
        li["n_ok"] = len([f for f in filhas if f["nv"] == li["nv"] + 1 and f["ok"]])
        li["n_trav"] = len([f for f in filhas if f["nv"] == li["nv"] + 1 and f["status"] == "Travada"])
    return linhas


def tem_data(li):
    return any(li[k] for k in ("prev_ini", "ini", "prev_fim", "fim"))


def svg(linhas):
    datadas, sem_data = [], []
    i = 0
    while i < len(linhas):
        li = linhas[i]
        if li["nv"] != 1:
            i += 1
            continue
        bloco = [li]
        j = i + 1
        while j < len(linhas) and linhas[j]["nv"] > 1:
            bloco.append(linhas[j])
            j += 1
        if any(tem_data(x) for x in bloco):
            datadas.append(bloco)
        else:
            sem_data.append(bloco)
        i = j

    todas = [d for bloco in datadas for li in bloco
             for d in (li["prev_ini"], li["ini"], li["prev_fim"], li["fim"]) if d]
    if not todas:
        return "", sem_data, 0
    d0, d1 = min(todas), max(todas)
    d0 -= datetime.timedelta(days=3)
    d1 += datetime.timedelta(days=3)
    if HOJE < d0:
        d0 = HOJE - datetime.timedelta(days=2)
    if HOJE > d1:
        d1 = HOJE + datetime.timedelta(days=2)
    dias = (d1 - d0).days or 1
    px_dia = max(4, min(26, int(1050 / dias)))
    mensal = dias > 45
    larg_tl = dias * px_dia
    larg = LARG_ROTULO + larg_tl + MARGEM_DIR

    corpo = [li for bloco in datadas for li in bloco if tem_data(li) or li["nv"] == 1]
    alt = TOPO + sum(ALT_SIS if li["nv"] == 1 else ALT_ATIV for li in corpo) + 18

    def x(d):
        return LARG_ROTULO + (d - d0).days * px_dia

    p = [f'<svg viewBox="0 0 {larg} {alt}" width="{larg}" height="{alt}" '
         f'role="img" aria-label="Cronograma das atividades">']

    # grade e escala
    MESES = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
    d = d0
    while d <= d1:
        marco = (d.day == 1) if mensal else (d.weekday() == 0)
        if marco:
            xx = x(d)
            p.append(f'<line x1="{xx}" y1="{TOPO-18}" x2="{xx}" y2="{alt-14}" class="grid"/>')
            rot = MESES[d.month-1] if mensal else d.strftime("%d/%m")
            p.append(f'<text x="{xx+4}" y="{TOPO-24}" class="tick">{rot}</text>')
        if d.weekday() >= 5 and px_dia >= 10:
            p.append(f'<rect x="{x(d)}" y="{TOPO-18}" width="{px_dia}" height="{alt-TOPO}" class="fds"/>')
        d += datetime.timedelta(days=1)

    xh = x(HOJE)
    p.append(f'<line x1="{xh}" y1="{TOPO-26}" x2="{xh}" y2="{alt-14}" class="hoje"/>')
    p.append(f'<text x="{xh+5}" y="{TOPO-38}" class="hojelbl">hoje</text>')

    y = TOPO
    for bloco in datadas:
        for li in bloco:
            if li["nv"] != 1 and not tem_data(li):
                continue
            h = ALT_SIS if li["nv"] == 1 else ALT_ATIV
            claro, escuro = CORES.get(li["status"], PADRAO)

            if li["nv"] == 1:
                p.append(f'<rect x="0" y="{y}" width="{larg}" height="{h}" class="faixa"/>')
                rot = html.escape(li["desc"][:44])
                p.append(f'<text x="10" y="{y+h/2+4}" class="lblsis">{rot}</text>')
                n = li.get("n_filhas", 0)
                if n:
                    resumo = f'{li.get("n_ok",0)}/{n}'
                    if li.get("n_trav"):
                        resumo += f' · {li["n_trav"]} travada'
                    p.append(f'<text x="{LARG_ROTULO-12}" y="{y+h/2+4}" class="lblct">{resumo}</text>')
            else:
                ind = 22 if li["nv"] == 2 else 40
                rot = html.escape(li["desc"][:52 - (li["nv"] - 2) * 6])
                p.append(f'<text x="{ind}" y="{y+h/2+4}" class="lblativ">{rot}</text>')
                if li["quem"]:
                    p.append(f'<text x="{LARG_ROTULO-12}" y="{y+h/2+4}" class="lblquem">'
                             f'{html.escape(li["quem"][:12])}</text>')

            pi, pf = li["prev_ini"], li["prev_fim"]
            if pi and pf:
                x1, x2 = x(pi), x(pf) + px_dia
                if li["nv"] == 1:
                    yb, hb = y + h / 2 - 4, 8
                    p.append(f'<rect x="{x1}" y="{yb}" width="{max(x2-x1,4)}" height="{hb}" '
                             f'rx="1" fill="{escuro}" opacity="0.30"/>')
                    p.append(f'<path d="M{x1},{yb} l0,{hb+5} l5,-5 z" fill="{escuro}"/>')
                    p.append(f'<path d="M{x2},{yb} l0,{hb+5} l-5,-5 z" fill="{escuro}"/>')
                else:
                    yb, hb = y + h / 2 - 7, 14
                    p.append(f'<rect x="{x1}" y="{yb}" width="{max(x2-x1,4)}" height="{hb}" '
                             f'rx="2" fill="{claro}" stroke="{escuro}" stroke-width="1"/>')
                    ri, rf = li["ini"], li["fim"]
                    if ri:
                        rx2 = x(rf) + px_dia if rf else xh
                        p.append(f'<rect x="{x(ri)}" y="{yb+4}" width="{max(rx2-x(ri),3)}" '
                                 f'height="{hb-8}" rx="1" fill="{escuro}"/>')
                    dias_txt = f'{(pf - pi).days + 1}d'
                    if li["status"] == "Travada" and li["alt"]:
                        dias_txt += f' · parada ha {(HOJE - li["alt"]).days}d'
                    p.append(f'<text x="{x2+7}" y="{y+h/2+4}" class="dur">{dias_txt}</text>')
            y += h

    p.append("</svg>")
    return "\n".join(p), sem_data, len(datadas)


def main() -> int:
    saida = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("cronograma.html")
    linhas = ler()
    grafico, sem_data, n_com = svg(linhas)

    n_ativ = len([l for l in linhas if l["nv"] >= 2])
    n_datadas = len([l for l in linhas if l["nv"] >= 2 and tem_data(l)])

    blocos_html = []
    for bloco in sem_data:
        sis = bloco[0]
        itens = "".join(f"<li>{html.escape(a['desc'])}</li>" for a in bloco[1:])
        blocos_html.append(
            f'<div class="sd"><h3>{html.escape(sis["desc"])}'
            f'<span class="cod">{html.escape(sis["codigo"])}</span></h3><ul>{itens}</ul></div>')

    legenda = "".join(
        f'<span class="lg"><i style="background:{c};border-color:{e}"></i>{html.escape(k)}</span>'
        for k, (c, e) in CORES.items())

    doc = TEMPLATE.format(
        hoje=HOJE.strftime("%d/%m/%Y"),
        n_ativ=n_ativ, n_datadas=n_datadas, n_sem=n_ativ - n_datadas, n_sis=n_com,
        legenda=legenda, grafico=grafico, sem_data="".join(blocos_html),
    )
    saida.write_text(doc, encoding="utf-8")
    print("gerado -> %s" % saida)
    print("  sistemas com data: %d | atividades com data: %d de %d" % (n_com, n_datadas, n_ativ))
    return 0


TEMPLATE = """<title>Cronograma Sobressalentes</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{{
  --ground:#E9EDF1;--surface:#FFFFFF;--surface-2:#F4F6F9;
  --ink:#16212D;--ink-2:#54636F;--ink-3:#7D8B96;
  --rule:#C9D2DA;--rule-soft:#DDE4EA;--accent:#A8501D;
  --faixa:#DCE4EA;--fds:#EFF3F6;
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
  --cond:"IBM Plex Sans Condensed","IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
  --ground:#111922;--surface:#19232E;--surface-2:#1F2B37;
  --ink:#E3EAF0;--ink-2:#9BAAB7;--ink-3:#74848F;
  --rule:#2E3D4A;--rule-soft:#26333E;--accent:#DE8C55;
  --faixa:#243140;--fds:#1C2731;
}}}}
:root[data-theme="dark"]{{
  --ground:#111922;--surface:#19232E;--surface-2:#1F2B37;
  --ink:#E3EAF0;--ink-2:#9BAAB7;--ink-3:#74848F;
  --rule:#2E3D4A;--rule-soft:#26333E;--accent:#DE8C55;
  --faixa:#243140;--fds:#1C2731;
}}
*{{box-sizing:border-box}}
body{{background:var(--ground);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.6}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 24px 72px}}
header{{border-bottom:2px solid var(--ink);padding:40px 0 20px;margin-bottom:26px}}
.eyebrow{{font-family:var(--mono);font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink-3);display:flex;flex-wrap:wrap;gap:6px 20px;margin-bottom:16px}}
h1{{font-family:var(--cond);font-weight:700;font-size:clamp(2rem,5vw,3rem);line-height:1.03;
  letter-spacing:-.015em;margin:0 0 12px}}
.dek{{font-size:16px;color:var(--ink-2);max-width:62ch;margin:0}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;
  background:var(--rule);border:1px solid var(--rule);margin-bottom:26px}}
.stat{{background:var(--surface);padding:16px 18px}}
.stat b{{display:block;font-family:var(--cond);font-weight:700;font-size:2rem;line-height:1;
  font-variant-numeric:tabular-nums;margin-bottom:4px}}
.stat span{{font-family:var(--mono);font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--ink-3);display:block;line-height:1.4}}
.stat.acc b{{color:var(--accent)}}
.legenda{{display:flex;flex-wrap:wrap;gap:6px 20px;margin-bottom:14px;
  font-family:var(--mono);font-size:11px;color:var(--ink-2)}}
.lg{{display:inline-flex;align-items:center;gap:7px}}
.lg i{{width:15px;height:11px;border-radius:2px;border:1px solid;display:inline-block}}
.quadro{{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);padding:8px 0 4px}}
svg{{display:block}}
.grid{{stroke:var(--rule-soft);stroke-width:1}}
.fds{{fill:var(--fds)}}
.hoje{{stroke:var(--accent);stroke-width:1.5;stroke-dasharray:3 3}}
.hojelbl{{font-family:var(--mono);font-size:10px;fill:var(--accent);letter-spacing:.06em}}
.tick{{font-family:var(--mono);font-size:9.5px;fill:var(--ink-3)}}
.faixa{{fill:var(--faixa)}}
.lblsis{{font-family:var(--cond);font-size:13.5px;font-weight:700;fill:var(--ink)}}
.lblativ{{font-family:var(--sans);font-size:11.5px;fill:var(--ink-2)}}
.lblct{{font-family:var(--mono);font-size:10px;fill:var(--ink-3);text-anchor:end}}
.lblquem{{font-family:var(--mono);font-size:9.5px;fill:var(--ink-3);text-anchor:end}}
.dur{{font-family:var(--mono);font-size:9.5px;fill:var(--ink-3)}}
h2{{font-family:var(--cond);font-weight:700;font-size:1.4rem;margin:38px 0 6px;
  border-bottom:1px solid var(--ink);padding-bottom:7px}}
.nota{{color:var(--ink-2);font-size:14px;max-width:68ch;margin:10px 0 20px}}
.sdgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}}
.sd{{background:var(--surface);border:1px solid var(--rule);border-left:3px solid var(--rule);padding:13px 16px}}
.sd h3{{font-family:var(--cond);font-weight:700;font-size:1rem;margin:0 0 8px;
  display:flex;flex-direction:column;gap:2px}}
.sd .cod{{font-family:var(--mono);font-size:9.5px;font-weight:400;color:var(--ink-3);word-break:break-all}}
.sd ul{{margin:0;padding-left:17px;display:flex;flex-direction:column;gap:5px}}
.sd li{{font-size:13px;color:var(--ink-2);line-height:1.45}}
footer{{border-top:1px solid var(--rule);margin-top:44px;padding-top:18px;
  font-family:var(--mono);font-size:11px;color:var(--ink-3);display:flex;flex-wrap:wrap;gap:8px 24px}}
</style>
<div class="wrap">
<header>
  <div class="eyebrow"><span>Consórcio Modernização de Itaipu</span><span>Contrato 4500063671</span><span>{hoje}</span></div>
  <h1>Cronograma<br>Sobressalentes</h1>
  <p class="dek">Gerado a partir da aba <strong>Atividades</strong> da planilha de mapeamento. Barra clara é o previsto; barra escura, o realizado.</p>
</header>
<div class="stats">
  <div class="stat acc"><b>{n_datadas}</b><span>Atividades<br>com prazo</span></div>
  <div class="stat"><b>{n_sem}</b><span>Sem prazo<br>definido</span></div>
  <div class="stat"><b>{n_ativ}</b><span>Atividades<br>no plano</span></div>
  <div class="stat"><b>{n_sis}</b><span>Sistemas<br>no quadro</span></div>
</div>
<div class="legenda">{legenda}</div>
<div class="quadro">{grafico}</div>
<h2>Sem prazo definido</h2>
<p class="nota">Atividades ainda sem data. Conforme as datas forem preenchidas na planilha, elas migram para o quadro acima.</p>
<div class="sdgrid">{sem_data}</div>
<footer><span>CMI · Gerência de Engenharia · PDM</span><span>Fonte: aba Atividades</span><span>Rascunho — não emitido</span></footer>
</div>
"""

if __name__ == "__main__":
    raise SystemExit(main())

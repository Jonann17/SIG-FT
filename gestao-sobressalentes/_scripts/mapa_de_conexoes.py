# -*- coding: utf-8 -*-
"""Gera o Mapa de Conexoes do cofre + corrige os arquivos de planejamento."""
import collections
import pathlib

V = pathlib.Path(r"C:/Users/LCCoz/OneDrive/Documents/Obsidian/Sobressalentes-Itaipu")
BS = chr(92)

notas = {p.stem: p for p in V.rglob("*.md")}
saida = collections.defaultdict(set)   # quem aponta para quem
entrada = collections.defaultdict(set)

for stem, p in notas.items():
    txt = p.read_text(encoding="utf-8")
    for chunk in txt.split("[[")[1:]:
        fim = chunk.find("]]")
        if fim < 0:
            continue
        alvo = chunk[:fim]
        for sep in ("|", "#", BS):
            alvo = alvo.split(sep)[0]
        alvo = alvo.strip().split("/")[-1]
        if alvo and alvo in notas and alvo != stem:
            saida[stem].add(alvo)
            entrada[alvo].add(stem)

grau = {s: len(saida[s]) + len(entrada[s]) for s in notas}
hubs = sorted(grau.items(), key=lambda kv: -kv[1])

# pastas, para colorir a leitura
def secao(stem):
    p = notas[stem]
    rel = p.relative_to(V)
    return rel.parts[0] if len(rel.parts) > 1 else "(raiz)"

L = []
A = L.append
A("---")
A("tags: [gerado, mapa]")
A("gerado_em: 2026-08-31")
A("---")
A("")
A("# Mapa de Conexoes")
A("")
A("> [!warning] Nota gerada automaticamente")
A("> Rode `python _scripts/mapa_de_conexoes.py` para regenerar.")
A("")
A(f"**{len(notas)} notas**, **{sum(len(v) for v in saida.values())} ligacoes** entre elas.")
A("")
A("## Os nos centrais")
A("")
A("As notas com mais ligacoes. Se uma delas estiver errada, o erro se espalha —")
A("sao as que merecem revisao mais cuidadosa.")
A("")
A("| # | Nota | Secao | Aponta para | Apontada por | Grau |")
A("|---:|---|---|---:|---:|---:|")
for i, (stem, g) in enumerate(hubs[:15], 1):
    A(f"| {i} | [[{stem}]] | {secao(stem)} | {len(saida[stem])} | {len(entrada[stem])} | **{g}** |")
A("")

# notas pouco conectadas
orfas = [s for s, g in hubs if g <= 2]
if orfas:
    A("## Notas pouco conectadas")
    A("")
    A("Grau <= 2. Ou sao folhas legitimas, ou faltou amarrar no resto do cofre.")
    A("")
    for s in sorted(orfas):
        A(f"- [[{s}]] — grau {grau[s]} ({secao(s)})")
    A("")

# ligacoes entre secoes
A("## Como as secoes conversam")
A("")
pares = collections.Counter()
for origem, alvos in saida.items():
    for alvo in alvos:
        a, b = secao(origem), secao(alvo)
        if a != b:
            pares[(a, b)] += 1
A("| De | Para | Ligacoes |")
A("|---|---|---:|")
for (a, b), n in pares.most_common(18):
    A(f"| {a} | {b} | {n} |")
A("")
A("## Grafo das secoes")
A("")
A("```mermaid")
A("graph LR")
apelido = {}
for i, s in enumerate(sorted({secao(x) for x in notas})):
    apelido[s] = f"S{i}"
    A(f'    {apelido[s]}["{s}"]')
for (a, b), n in pares.most_common(14):
    A(f"    {apelido[a]} -->|{n}| {apelido[b]}")
A("```")
A("")
A("---")
A("")
A("Voltar para [[00 - Inicio]]")

(V / "_gerado").mkdir(exist_ok=True)
(V / "_gerado" / "Mapa de Conexoes.md").write_text("\n".join(L), encoding="utf-8")

print("Mapa gerado.")
print("Top 8 hubs:")
for stem, g in hubs[:8]:
    print(f"   {g:3d}  {stem}")
print(f"\n{len(notas)} notas, {sum(len(v) for v in saida.values())} ligacoes")

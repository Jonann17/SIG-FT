# -*- coding: utf-8 -*-
"""
Leva a mapeadora (Mapeamento Listas de Sobressalentes.xlsx, aba "Acompanhamento
Sobressalente") para o tratamento v2 do _STATUS_PMIB — sem perder nada.

O que muda (pedido do Luan em 05/10/2026):
  1. Tres colunas INSERIDAS no bloco PMIB (como "Inserir coluna" do Excel):
       ... FICHAS APROVADAS | FICHAS DE ENTREGA FÍSICA | APTO PARA ENTREGA |
           AGUARDANDO AUTORIZAÇÃO ITAIPU | ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU |
           MAIOR ATRASO ITAIPU (DIAS) | EQUIPAMENTOS ENTREGUES ...
     Nenhuma coluna existente muda de nome — o Sobressalentes - Dashboard.pbix atual usa
     "APTO PARA ENTREGA" pelo nome.
  2. Regra nova nas contagens de autorizacao (as mesmas que o Gestao PMIB passa a gravar):
     so ficha FISICA E DOCUMENTAL precisa de autorizacao de Itaipu; prazo de 15 dias uteis.
       FICHAS DE ENTREGA FÍSICA      fichas com TIPO DE ENTREGA = FISICA E DOCUMENTAL
       APTO PARA ENTREGA             SITUACAO = AUTORIZADO, nao entregue, tipo nao DOCUMENTAL/TITULO
       AGUARDANDO AUTORIZAÇÃO ITAIPU SITUACAO = AGUARDANDO ITAIPU
       ATRASO DE AUTORIZAÇÃO ...     SITUACAO = ATRASADO ITAIPU (era 14 dias corridos)
       MAIOR ATRASO ITAIPU (DIAS)    maior DIAS DE ATRASO entre as atrasadas
     "Ficha" = codigo PMIB valido e distinto, sem as linhas DUPLICADO (mesma base do SIG-FT).
     Lista sem _STATUS_PMIB: zeros (como o SIG-FT faz).
  3. Mensagens (ao clicar) nos cabecalhos dessas colunas e na coluna REVISÃO EM USO, que
     passa a vir da linha de revisao do _STATUS_PMIB (o Gestao PMIB copia — tarefa T3).

Edicao cirurgica (xlsx_cirurgico): links "Abrir Box", formulas, formatacao condicional
(G<>C), filtro, painel e as outras abas saem intactos.

MODOS
  python atualizar_mapeadora_v2.py --simular        copia local, confere, nao toca no Box
  python atualizar_mapeadora_v2.py --aplicar        grava por cima no Box (backup antes)
Rodar de novo atualiza so os numeros (as colunas ja existem).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import shutil
import sys
import tempfile
import warnings

import openpyxl

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "_scripts"))
sys.path.insert(0, str(AQUI))
import regras_sobressalentes as R  # noqa: E402
from xlsx_cirurgico import PlanilhaXlsx, Deslocamento, col_letras, q  # noqa: E402
from migrar_status_pmib_v2 import _igual, abre_no_libreoffice  # noqa: E402

MAPEADORA = R.PASTA_PMIB / "Mapeamento Listas de Sobressalentes.xlsx"
ABA = "Acompanhamento Sobressalente"
LINHA_CAB = 2
C_DOC, C_REV = "N° DOCUMENTO ITAIPU", "REVISÃO EM USO"
C_APTO, C_ATRASO, C_ENTREGUES = "APTO PARA ENTREGA", "ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU", "EQUIPAMENTOS ENTREGUES"
C_FISICAS, C_AGUARDANDO, C_MAIOR = "FICHAS DE ENTREGA FÍSICA", "AGUARDANDO AUTORIZAÇÃO ITAIPU", "MAIOR ATRASO ITAIPU (DIAS)"
NOVAS_ANTES_DE = {C_APTO: C_FISICAS, C_ATRASO: C_AGUARDANDO, C_ENTREGUES: C_MAIOR}   # nova entra ANTES da chave
# AGUARDANDO entra antes do ATRASO; MAIOR ATRASO antes de EQUIPAMENTOS ENTREGUES
LARGURAS = {C_FISICAS: 17, C_AGUARDANDO: 22, C_MAIOR: 18}
MENSAGENS = {
    C_FISICAS: "Fichas com TIPO DE ENTREGA = FÍSICA E DOCUMENTAL — as únicas que precisam de autorização de Itaipu. Gestão PMIB.",
    C_APTO: "Fichas autorizadas por Itaipu (SITUAÇÃO = AUTORIZADO) e ainda não entregues. Não conta DOCUMENTAL/TÍTULO. Gestão PMIB.",
    C_AGUARDANDO: "Fichas físicas com e-mail de intenção enviado, dentro do prazo de 15 dias úteis. Gestão PMIB.",
    C_ATRASO: "Fichas físicas além do prazo de 15 dias úteis do e-mail, sem autorização (SITUAÇÃO = ATRASADO ITAIPU). Gestão PMIB.",
    C_MAIOR: "Maior DIAS DE ATRASO (dias corridos além do prazo) entre as fichas atrasadas da lista. Gestão PMIB.",
}
MSG_REVISAO = ("Vem da linha 'REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO' do _STATUS_PMIB. "
               "Para mudar, atualize lá — o Gestão PMIB copia para cá.")


def contagens(hoje: dt.date) -> dict[str, dict]:
    """Por lista, a partir dos _STATUS_PMIB (mesma regra que o SIG-FT grava)."""
    itens = R.ler_itens(hoje=hoje)
    tipo_col = [R.TIPO_CANONICO.get(R.normalizar(v)) for v in itens["TIPO DE ENTREGA"]]
    itens = itens.assign(TIPO_COL=tipo_col)
    fichas = itens[itens["E_FICHA"]].drop_duplicates(["LISTA", "PMIB"], keep="first")
    saida = {}
    for lista, f in fichas.groupby("LISTA"):
        atras = f[f["SITUACAO_AUT"] == "ATRASADO ITAIPU"]
        saida[lista] = {
            C_FISICAS: int((f["TIPO_COL"] == "FÍSICA E DOCUMENTAL").sum()),
            C_APTO: int(((f["SITUACAO_AUT"] == "AUTORIZADO") & ~f["ENTREGUE"]
                         & ~f["TIPO_COL"].isin(["DOCUMENTAL", "TÍTULO"])).sum()),
            C_AGUARDANDO: int((f["SITUACAO_AUT"] == "AGUARDANDO ITAIPU").sum()),
            C_ATRASO: int(len(atras)),
            C_MAIOR: int(max([d for d in atras["DIAS_ATRASO"] if d is not None] or [0])),
        }
    for lista in itens["LISTA"].unique():                     # lista com arquivo mas sem ficha
        saida.setdefault(lista, {k: 0 for k in (C_FISICAS, C_APTO, C_AGUARDANDO, C_ATRASO, C_MAIOR)})
    return saida


def revisoes() -> dict[str, str]:
    """Revisao em uso lida da linha acima do cabecalho de cada _STATUS_PMIB."""
    out = {}
    for p in R.listar_status_pmib():
        ws = openpyxl.load_workbook(p, read_only=True)["Lista de Materiais"]
        for row in ws.iter_rows(min_row=1, max_row=8, max_col=4, values_only=True):
            for v in row:
                t = R.normalizar(v)
                if t.startswith("REVISAO DA LISTA") and "EM USO:" in t:
                    rev = t.split("EM USO:", 1)[1].split(" - DATA")[0].strip()
                    if rev and rev not in ("—", "-"):
                        out[p.name[: -len("_STATUS_PMIB.xlsx")]] = str(v).split(":", 1)[1].split(" - DATA")[0].strip()
    return out


def atualizar(caminho: pathlib.Path, hoje: dt.date) -> dict:
    ws = openpyxl.load_workbook(caminho)[ABA]
    cab = {str(c.value).strip(): c.column for c in ws[LINHA_CAB] if c.value not in (None, "")}
    for obrig in (C_DOC, C_REV, C_APTO, C_ATRASO, C_ENTREGUES):
        if obrig not in cab:
            raise ValueError(f"coluna '{obrig}' não encontrada na linha {LINHA_CAB} da aba {ABA}")
    resumo = {"colunas_inseridas": 0, "linhas": 0, "revisao_alterada": 0, "_d": None}
    cab0 = dict(cab)
    p = PlanilhaXlsx(caminho)
    L = p.parte_da_aba(ABA)

    # 1. colunas novas (so na primeira vez)
    if C_FISICAS not in cab:
        d = Deslocamento({cab[chave]: 1 for chave in NOVAS_ANTES_DE})
        p.deslocar(ABA, d)
        novas = {nova: d.col(cab[chave]) - 1 for chave, nova in NOVAS_ANTES_DE.items()}
        p.formatar_como_a_esquerda(L, list(novas.values()))
        for nome, c in novas.items():
            p.escrever(L, f"{col_letras(c)}{LINHA_CAB}", nome)
            p.largura(L, c, LARGURAS[nome])
        cab = {nome: d.col(c) for nome, c in cab.items()} | novas
        resumo["colunas_inseridas"] = len(novas)
        resumo["_d"] = d
        # mensagens ao clicar: cabecalhos das contagens de autorizacao e a coluna da revisao
        for nome, msg in MENSAGENS.items():
            p.adicionar_validacao(L, f"{col_letras(cab[nome])}{LINHA_CAB}", "none", titulo="Gestão PMIB (SIG-FT)", mensagem=msg)
        ult = ws.max_row + 50
        p.adicionar_validacao(L, f"{col_letras(cab[C_REV])}{LINHA_CAB + 1}:{col_letras(cab[C_REV])}{ult}", "none",
                              titulo="Revisão em uso", mensagem=MSG_REVISAO)
    resumo["_cab"] = cab

    # 2. numeros (regra nova) e revisao em uso vinda dos arquivos
    cont, revs = contagens(hoje), revisoes()
    for r in range(LINHA_CAB + 1, ws.max_row + 1):               # ws = arquivo ANTES da insercao: le por cab0
        doc = ws.cell(r, cab0[C_DOC]).value
        if not doc:
            continue
        doc = str(doc).strip()
        valores = cont.get(doc, {k: 0 for k in (C_FISICAS, C_APTO, C_AGUARDANDO, C_ATRASO, C_MAIOR)})
        for nome, v in valores.items():
            p.escrever(L, f"{col_letras(cab[nome])}{r}", v)
        if doc in revs:
            atual = ws.cell(r, cab0[C_REV]).value
            if str(atual or "").strip() != revs[doc]:
                p.escrever(L, f"{col_letras(cab[C_REV])}{r}", revs[doc])
                resumo["revisao_alterada"] += 1
        resumo["linhas"] += 1
    p.salvar()
    resumo["partes_alteradas"] = ", ".join(sorted(p.partes_modificadas))
    return resumo


def conferir(original: pathlib.Path, novo: pathlib.Path, resumo: dict) -> list[str]:
    """Toda celula do original no lugar novo; so as contagens de autorizacao e a revisao podem mudar."""
    d, cab = resumo["_d"] or Deslocamento(), resumo["_cab"]
    problemas = []
    po, pn = PlanilhaXlsx(original), PlanilhaXlsx(novo)
    L = po.parte_da_aba(ABA)
    if list(po._bytes) != list(pn._bytes):
        problemas.append("lista de partes do arquivo mudou")
    problemas += [f"parte alterada sem querer: {n}" for n in po._bytes
                  if n not in (L, "xl/workbook.xml", "xl/calcChain.xml") and po._bytes[n] != pn._bytes.get(n)]
    wa, wn = openpyxl.load_workbook(original)[ABA], openpyxl.load_workbook(novo)[ABA]
    pode_mudar = {cab[n] for n in (C_APTO, C_ATRASO, C_REV)}
    for row in wa.iter_rows():
        for c in row:
            if c.value in (None, ""):
                continue
            nc, nr = d.col(c.column), c.row
            if nc in pode_mudar and nr > LINHA_CAB:
                continue
            esperado = "=" + d.formula(c.value[1:], ABA, True) if isinstance(c.value, str) and c.value.startswith("=") else c.value
            if not _igual(wn.cell(nr, nc).value, esperado):
                problemas.append(f"{col_letras(nc)}{nr}: esperado {esperado!r}, ficou {wn.cell(nr, nc).value!r}")
                if len(problemas) > 10:
                    return problemas
    if [d.faixa(h.get("ref")) for h in po.raiz(L).iter(q("hyperlink"))] != [h.get("ref") for h in pn.raiz(L).iter(q("hyperlink"))]:
        problemas.append("links não acompanharam")
    if sorted(d.sqref(m.get("ref")) for m in po.mesclagens(L)) != sorted(m.get("ref") for m in pn.mesclagens(L)):
        problemas.append("mesclagens não acompanharam")
    cf = lambda p, f: sorted((f(e.get("sqref")), len(list(e))) for e in p.raiz(L).iter(q("conditionalFormatting")))  # noqa: E731
    if cf(po, d.sqref) != cf(pn, lambda s: s):
        problemas.append("formatação condicional não acompanhou")
    nomes_cab = [str(c.value).strip() for c in wn[LINHA_CAB] if c.value not in (None, "")]
    i = nomes_cab.index("FICHAS APROVADAS")
    if nomes_cab[i: i + 7] != ["FICHAS APROVADAS", C_FISICAS, C_APTO, C_AGUARDANDO, C_ATRASO, C_MAIOR, C_ENTREGUES]:
        problemas.append(f"ordem do cabeçalho: {nomes_cab[i: i + 7]}")
    for aba in ("Dropbox", "Lista de preços Follow-up", "Atividades"):
        if po._bytes[po.parte_da_aba(aba)] != pn._bytes[pn.parte_da_aba(aba)]:
            problemas.append(f"aba {aba} mudou")
    return problemas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--simular", action="store_true")
    g.add_argument("--aplicar", action="store_true")
    ap.add_argument("--confirmo", action="store_true")
    ap.add_argument("--backup", type=pathlib.Path,
                    default=pathlib.Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Sobressalentes-v2")
    args = ap.parse_args()
    hoje = dt.date.today()
    if args.aplicar:
        if not args.confirmo and input("Vai ALTERAR a mapeadora NO BOX. Digite APLICAR: ").strip() != "APLICAR":
            return 1
        pasta = args.backup / f"backup_mapeadora_{dt.datetime.now():%Y%m%d-%H%M}"
        pasta.mkdir(parents=True, exist_ok=True)
        referencia, alvo = pasta / MAPEADORA.name, MAPEADORA
        shutil.copy2(MAPEADORA, referencia)
        print(f"Backup em {referencia}")
    else:
        pasta = pathlib.Path(tempfile.gettempdir()) / "mapeadora_v2_simulacao"
        pasta.mkdir(parents=True, exist_ok=True)
        referencia, alvo = MAPEADORA, pasta / MAPEADORA.name
        shutil.copy2(MAPEADORA, alvo)
    res = atualizar(alvo, hoje)
    prob = conferir(referencia, alvo, res)
    print({k: v for k, v in res.items() if not k.startswith("_")})
    print("Conferência:", "; ".join(prob) or "nenhuma perda")
    if not args.aplicar:
        print("LibreOffice:", "abre" if abre_no_libreoffice(alvo) else "NÃO ABRE", "|", alvo)
    return 0 if not prob else 2


if __name__ == "__main__":
    sys.exit(main())

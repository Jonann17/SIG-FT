# -*- coding: utf-8 -*-
"""
Migra planilhas _STATUS_PMIB para o layout v2 — sem perder nada.

Layout v2 (definido pelo Luan em 04/10/2026), da APLICACAO - LMR em diante:

  ... | APLICAÇÃO - LMR | TIPO DE ENTREGA | DATA DO EMAIL COMUNICANDO ENTREGA |
        SITUAÇÃO DA AUTORIZAÇÃO | DIAS DE ATRASO | EQUIPAMENTO ENTREGUE |
        [colunas extras da lista] | FORNECEDOR | PROCUREMENT | OBSERVAÇÕES | [extras]

  e, acima do cabecalho, a linha
  "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: dd/mm/aaaa"

  - TIPO DE ENTREGA, DIAS DE ATRASO, FORNECEDOR e PROCUREMENT sao colunas INSERIDAS
    (como "Inserir coluna" do Excel: o que esta a direita anda, formulas e referencias acompanham).
  - SITUAÇÃO DA AUTORIZAÇÃO SUBSTITUI a APTO PARA ENTREGA, na mesma coluna: SIM vira
    AUTORIZADO; o resto e calculado pela regra dos 15 dias uteis (AGUARDANDO / ATRASADO
    ITAIPU). Depois disso, quem atualiza e o SIG-FT, quando roda.
  - DIAS DE ATRASO: dias corridos alem do prazo de 15 dias uteis do e-mail (SIG-FT grava).
  - A linha da revisao em uso e INSERIDA (o cabecalho desce uma linha) nas listas que ainda
    nao a tem; a revisao vem da coluna REVISAO EM USO da mapeadora. A partir dai quem mantem
    e o _STATUS_PMIB, e o Gestao PMIB do SIG-FT passa a ler dali para a mapeadora.
  - Lista que ja tinha uma coluna "Fornecedor" a direita de OBSERVACOES: os valores vao para
    a FORNECEDOR nova e a coluna antiga fica vazia.

Como: edicao "cirurgica" do .xlsx (`xlsx_cirurgico.py`) — nada de openpyxl para gravar.
Comentarios (em thread e anotacoes), listas suspensas, formatacao condicional, filtro,
painel congelado e o resto andam junto com as celulas; partes nao relacionadas saem
identicas, byte a byte. Nenhuma formula e criada.

MODOS
  python migrar_status_pmib_v2.py --simular [--libreoffice]
      Copia os _STATUS_PMIB do Box para uma pasta LOCAL (%TEMP%), migra as COPIAS e confere
      cada uma contra o original. Nao toca no Box.
  python migrar_status_pmib_v2.py --template ORIGEM DESTINO
      Gera o template v2 a partir de uma copia do template atual.
  python migrar_status_pmib_v2.py --aplicar [--so TEXTO] [--confirmo]
      Migra OS ARQUIVOS DO BOX, gravando por cima do mesmo arquivo (o Box guarda a versao
      anterior), depois de copiar cada original para %LOCALAPPDATA%\\Sobressalentes-v2\\backup_*.
      >>> SO COM AUTORIZACAO EXPLICITA DO LUAN (dada em 04/10/2026 para os 47). <<<

CONFERENCIA (automatica, por arquivo): toda celula, formula, mesclagem, formatacao condicional,
comentario e nome definido do original esta no lugar novo esperado; nada a mais alem das
colunas/linha novas; a ordem do cabecalho e a do layout v2; partes nao relacionadas identicas;
o SIG-FT ainda acha o cabecalho; as listas suspensas sobrevivem a um save do openpyxl; com
--libreoffice, o arquivo abre no LibreOffice.

Requisitos: openpyxl, pandas, lxml
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
import zipfile

import openpyxl
import pandas as pd
from lxml import etree

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "_scripts"))
sys.path.insert(0, str(AQUI))
import regras_sobressalentes as R  # noqa: E402
from xlsx_cirurgico import (NS_XM, PlanilhaXlsx, Deslocamento, REL_COMENTARIOS, REL_DESENHO,  # noqa: E402
                            REL_THREADED, REL_VML, col_letras, limites, q)

ABA, ABA_LISTAS = "Lista de Materiais", "Checklist"
C_LMR, C_EMAIL, C_APTO = "APLICAÇÃO - LMR", "DATA DO EMAIL COMUNICANDO ENTREGA", "APTO PARA ENTREGA"
C_ENT, C_OBS = "EQUIPAMENTO ENTREGUE", "OBSERVAÇÕES"
C_TIPO, C_SIT, C_DIAS = "TIPO DE ENTREGA", "SITUAÇÃO DA AUTORIZAÇÃO", "DIAS DE ATRASO"
C_FORN, C_PROC = "FORNECEDOR", "PROCUREMENT"
NOVAS = [C_TIPO, C_DIAS, C_FORN, C_PROC]
LARGURAS = {C_TIPO: 20, C_SIT: 22, C_DIAS: 10, C_FORN: 18, C_PROC: 18}
TEXTO_REVISAO = "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: {rev} - DATA DE ALTERAÇÃO: {data}"
VERSAO_LAYOUT = '"v2"'

LISTAS = {
    "lst_status": ["FICHA CRIADA", "DUPLICADO", "COM O FORNECEDOR", "EM ELABORAÇÃO", "EM CORREÇÃO",
                   "EM ANÁLISE IB", "APROVADO", "INICIAR", "N/A"],
    "lst_secao": ["COMPLETO", "INCOMPLETO", "N/A"],
    "lst_simnao": ["SIM", "NÃO"],
    "lst_tipo_entrega": ["FÍSICA E DOCUMENTAL", "DOCUMENTAL", "TÍTULO"],
    # alerta "aviso": aceita nome novo. Tirada da mapeadora.
    "lst_procurement": ["BRUNA", "DOUGLAS COSTA", "FLAVIA SANTOS", "JULLY CARVALHO", "LEILA MEDEIROS",
                        "LYVIA MACHADO", "MARCELO MENDES", "SUELEN BRUM"],
    "lst_situacao": R.SITUACOES_AUTORIZACAO,
}
SECOES_COL = ["INFO. GERAIS", "CARACT. TECNICAS", "DOCUMENTOS E IMAGENS", "CONDICOES", "VALORIZACAO", "APLICACAO - LMR"]
FOLGA_LINHAS = 50          # validacoes vao alem da ultima linha com dado
N = R.normalizar


# --------------------------------------------------------------------------
# Leitura da estrutura (openpyxl so le; quem grava e o xlsx_cirurgico)
# --------------------------------------------------------------------------
def cabecalho(ws) -> tuple[int, dict[str, int]]:
    for linha in range(1, 15):
        nomes = {}
        for c in range(1, 80):
            v = ws.cell(linha, c).value
            if v not in (None, ""):
                nomes.setdefault(N(v), c)
        if "DESCRICAO" in nomes:
            return linha, nomes
    raise ValueError("cabeçalho com DESCRIÇÃO não encontrado nas 14 primeiras linhas")


def ultima_linha_com_dado(ws, hdr: int, col_desc: int) -> int:
    fim = hdr
    for r in range(hdr + 1, ws.max_row + 1):
        if ws.cell(r, col_desc).value not in (None, ""):
            fim = r
    return fim


def linha_revisao(ws, hdr: int) -> int | None:
    for r in range(1, hdr):
        for c in range(1, 6):
            if N(ws.cell(r, c).value).startswith("REVISAO DA LISTA"):
                return r
    return None


def para_data(v) -> dt.date | None:
    if isinstance(v, str) and re.fullmatch(r"\s*\d{1,2}/\d{1,2}/\d{4}\s*", v):
        return dt.datetime.strptime(v.strip(), "%d/%m/%Y").date()
    return R._para_data(v)


def inventario(caminho: pathlib.Path) -> dict[str, int]:
    """O que existe no arquivo e nao pode sumir (medido no proprio .xlsx)."""
    with zipfile.ZipFile(caminho) as z:
        nomes = z.namelist()
        ler = lambda prefixo: "".join(z.read(n).decode("utf-8", "ignore") for n in nomes if n.startswith(prefixo))  # noqa: E731
        folhas, desenho = ler("xl/worksheets/sheet"), ler("xl/drawings/drawing")
        return {
            "comentarios_thread": ler("xl/threadedComments/").count("<threadedComment "),
            "anotacoes": ler("xl/comments").count("<comment "),
            "formatacao_condicional": folhas.count("<conditionalFormatting "),
            "desenhos": sum(desenho.count(f"<xdr:{a}") for a in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor")),
        }


# --------------------------------------------------------------------------
# Migracao de um arquivo
# --------------------------------------------------------------------------
def garantir_listas(p: PlanilhaXlsx, parte: str) -> None:
    """Vocabularios na aba Checklist, a direita do que ja existe, + nomes definidos."""
    atual = p.nome_definido("lst_status")
    if atual and atual.startswith(f"{ABA_LISTAS}!"):
        inicio = limites(atual.split("!")[1])[0]               # ja tem: reescreve no mesmo lugar
    else:
        inicio = p.ultima_coluna_com_valor(parte) + 2
    for j, (nome, valores) in enumerate(LISTAS.items()):
        col = col_letras(inicio + j)
        p.escrever(parte, f"{col}2", nome)
        for i, v in enumerate(valores, start=3):
            p.escrever(parte, f"{col}{i}", v)
        p.largura(parte, inicio + j, 24)
        p.definir_nome(nome, f"{ABA_LISTAS}!${col}$3:${col}${2 + len(valores)}")


def planejar(ws) -> dict:
    """Le a estrutura e decide o que inserir (coordenadas ORIGINAIS)."""
    hdr, mapa = cabecalho(ws)
    if N(C_SIT) in mapa:
        return {"ja_migrado": True, "hdr": hdr, "mapa": mapa}
    faltam = [c for c in (C_LMR, C_EMAIL, C_APTO, C_ENT, C_OBS, "CÓDIGO PMIB", "STATUS") if N(c) not in mapa]
    if faltam:
        raise ValueError(f"colunas esperadas ausentes: {', '.join(faltam)}")
    c = lambda nome: mapa[N(nome)]  # noqa: E731
    insercoes: dict[int, list[str]] = {}
    insercoes.setdefault(c(C_LMR) + 1, []).append(C_TIPO)
    insercoes.setdefault(c(C_APTO) + 1, []).append(C_DIAS)
    insercoes.setdefault(c(C_OBS), []).extend([C_FORN, C_PROC])
    forn_antigo = mapa.get("FORNECEDOR")
    if forn_antigo and forn_antigo < c(C_OBS):
        raise ValueError("já existe FORNECEDOR antes de OBSERVAÇÕES — tratar à mão")
    rev = linha_revisao(ws, hdr)
    d = Deslocamento({pos: len(n) for pos, n in insercoes.items()}, {} if rev else {hdr: 1})
    novas = {}
    for pos, nomes in insercoes.items():
        base = d.col(pos) - len(nomes)
        for k, nome in enumerate(nomes):
            novas[nome] = base + k
    return {"ja_migrado": False, "hdr": hdr, "mapa": mapa, "d": d, "insercoes": insercoes, "novas": novas,
            "tem_revisao": rev is not None, "forn_antigo": forn_antigo,
            "fim": ultima_linha_com_dado(ws, hdr, mapa["DESCRICAO"])}


def migrar_planilha(caminho: pathlib.Path, prefill_tipo: dict[str, str], prefill_proc: str | None,
                    revisao: str | None, folga: int = FOLGA_LINHAS, hoje: dt.date | None = None) -> dict:
    hoje = hoje or dt.date.today()
    resumo = {"arquivo": caminho.name, "aviso": "", "linha_revisao": "", "tipo_preenchido": 0,
              "procurement_preenchido": 0, "autorizado": 0, "aguardando": 0, "atrasado": 0,
              "autorizado_por_entregue": 0, "fornecedor_movido": 0}
    ws = openpyxl.load_workbook(caminho)[ABA]                   # leitura
    plano = planejar(ws)
    resumo["_plano"] = plano
    if plano["ja_migrado"]:
        resumo.update(ok=True, aviso="já estava no layout v2 — nada feito")
        return resumo
    hdr, mapa, d, novas, fim = plano["hdr"], plano["mapa"], plano["d"], plano["novas"], plano["fim"]
    col = lambda nome: mapa[N(nome)]  # noqa: E731

    p = PlanilhaXlsx(caminho)
    L, C = p.parte_da_aba(ABA), p.parte_da_aba(ABA_LISTAS)

    # comentario preso a coluna Fornecedor antiga impede mover (ficaria preso a celula vazia)
    forn_antigo = plano["forn_antigo"]
    if forn_antigo:
        refs = []
        for parte in p._partes_ligadas(L).get(REL_COMENTARIOS, []):
            refs += re.findall(r'<comment\b[^>]*?\sref="([^"]+)"', p._texto(parte))
        if any(limites(r)[0] == forn_antigo for r in refs):
            forn_antigo = None
            resumo["aviso"] += "coluna Fornecedor antiga tem comentário: não movida. "
        plano["forn_movido"] = forn_antigo

    # 1. inserir as colunas (e a linha da revisao) — tudo o que referencia celula acompanha
    p.deslocar(ABA, d)
    H = d.lin(hdr)
    F = d.lin(fim) if fim > hdr else H
    p.formatar_como_a_esquerda(L, list(novas.values()))
    for nome, c in novas.items():
        p.escrever(L, f"{col_letras(c)}{H}", nome)
        p.largura(L, c, LARGURAS[nome])
    c_sit = d.col(col(C_APTO))
    p.escrever(L, f"{col_letras(c_sit)}{H}", C_SIT)
    p.largura(L, c_sit, LARGURAS[C_SIT])
    plano["c_sit"] = c_sit

    # 2. SITUACAO DA AUTORIZACAO (no lugar do APTO) e DIAS DE ATRASO — valores, nao formulas
    for r in range(hdr + 1, fim + 1):
        status = N(ws.cell(r, col("STATUS")).value)
        apto = ws.cell(r, col(C_APTO)).value
        entregue = ws.cell(r, col(C_ENT)).value
        tipo = prefill_tipo.get(R.normalizar_pmib(ws.cell(r, col("CÓDIGO PMIB")).value) or "")
        sit, _, dias = R.situacao_autorizacao(para_data(ws.cell(r, col(C_EMAIL)).value), apto, entregue, hoje, tipo=tipo)
        if status == "DUPLICADO" and N(apto) != "SIM":       # a situacao vale pela linha da ficha
            sit, dias = "", None
        ref_sit = f"{col_letras(c_sit)}{d.lin(r)}"
        if sit or p.tem_valor(L, ref_sit):
            p.escrever(L, ref_sit, sit or None)
        if dias is not None:
            p.escrever(L, f"{col_letras(novas[C_DIAS])}{d.lin(r)}", dias)
        if sit == "AUTORIZADO":
            resumo["autorizado"] += 1
            resumo["autorizado_por_entregue"] += N(apto) != "SIM"
        resumo["aguardando"] += sit == "AGUARDANDO ITAIPU"
        resumo["atrasado"] += sit == "ATRASADO ITAIPU"
        resumo["documental"] = resumo.get("documental", 0) + (sit == "N/A")

    # 3. linha da revisao em uso, acima do cabecalho, com o estilo da linha de cima
    if not plano["tem_revisao"]:
        r_rev, r_cima = hdr, hdr - 1                         # (o cabecalho desceu para hdr + 1)
        faixa_cima = next((limites(m.get("ref")) for m in p.mesclagens(L)
                           if limites(m.get("ref"))[1] == r_cima == limites(m.get("ref"))[3]), None)
        c1, c2 = (faixa_cima[0], faixa_cima[2]) if faixa_cima else (min(mapa.values()), d.col(max(mapa.values())))
        nova, cima = p.linha_xml(L, r_rev, criar=True), p.linha_xml(L, r_cima)
        if cima is not None:
            for a in ("ht", "customHeight"):
                if cima.get(a):
                    nova.set(a, cima.get(a))
        texto = TEXTO_REVISAO.format(rev=revisao or "—", data="—")
        for c in range(c1, c2 + 1):
            p.escrever(L, f"{col_letras(c)}{r_rev}", texto if c == c1 else None, p.estilo(L, f"{col_letras(c)}{r_cima}"))
        if c2 > c1:
            p.mesclar(L, f"{col_letras(c1)}{r_rev}:{col_letras(c2)}{r_rev}")
        resumo["linha_revisao"] = f"inserida ({revisao or '—'})"
        plano["revisao"] = (r_rev, c1, c2, texto)
    else:
        resumo["linha_revisao"] = "já existia"

    # 4. Fornecedor antigo (a direita de OBSERVACOES) -> FORNECEDOR nova
    if forn_antigo:
        c_old = d.col(forn_antigo)
        for r in range(hdr, fim + 1):
            v = ws.cell(r, forn_antigo).value
            if v in (None, ""):
                continue
            if r > hdr:
                p.escrever(L, f"{col_letras(novas[C_FORN])}{d.lin(r)}", v)
                resumo["fornecedor_movido"] += 1
            p.escrever(L, f"{col_letras(c_old)}{d.lin(r)}", None)
        resumo["aviso"] += f"coluna Fornecedor antiga ({col_letras(c_old)}) movida para {col_letras(novas[C_FORN])}. "

    # 5. listas suspensas por NOME DEFINIDO (sobrevivem ao openpyxl do SIG-FT)
    garantir_listas(p, C)
    primeira, ultima = H + 1, max(F, H + 1) + folga
    regras = {d.col(col("STATUS")): ("lst_status", "warning", "", "")}
    for s in SECOES_COL:
        if s in mapa:
            regras[d.col(mapa[s])] = ("lst_secao", "warning", "", "")
    regras[c_sit] = ("lst_situacao", "warning", "Preenchido pelo SIG-FT",
                     "Atualizado pelo SIG-FT: 15 dias úteis a partir do e-mail de intenção. AUTORIZADO pode ser marcado à mão.")
    regras[d.col(col(C_ENT))] = ("lst_simnao", "warning", "", "")
    regras[novas[C_TIPO]] = ("lst_tipo_entrega", "stop", "Tipo de entrega",
                             "FÍSICA E DOCUMENTAL (sai na nota fiscal) · DOCUMENTAL (componente, só ficha) · TÍTULO (conjunto)")
    regras[novas[C_PROC]] = ("lst_procurement", "warning", "Procurement", "Escolha da lista ou digite um nome novo.")
    p.remover_validacoes(L, set(regras) | {novas[C_DIAS]}, primeira)
    faixa = lambda c: f"{col_letras(c)}{primeira}:{col_letras(c)}{ultima}"  # noqa: E731
    for c, (nome, alerta, titulo, msg) in sorted(regras.items()):
        p.adicionar_validacao(L, faixa(c), "list", nome, alerta=alerta, titulo=titulo, mensagem=msg)
    p.adicionar_validacao(L, faixa(novas[C_DIAS]), "none", titulo="Preenchido pelo SIG-FT",
                          mensagem="Dias corridos além do prazo de 15 dias úteis do e-mail. Congela quando Itaipu autoriza. Não digitar.")

    # 6. pre-preenchimento — so celula vazia, so linha com PMIB valido
    for r in range(hdr + 1, fim + 1):
        pmib = R.normalizar_pmib(ws.cell(r, col("CÓDIGO PMIB")).value)
        if not pmib:
            continue
        for nome, valor, chave in ((C_TIPO, prefill_tipo.get(pmib), "tipo_preenchido"),
                                   (C_PROC, prefill_proc, "procurement_preenchido")):
            ref = f"{col_letras(novas[nome])}{d.lin(r)}"
            if valor and not p.tem_valor(L, ref):
                p.escrever(L, ref, valor)
                resumo[chave] += 1

    p.definir_nome("versao_layout_status_pmib", VERSAO_LAYOUT)
    p.salvar()
    resumo["partes_alteradas"] = ", ".join(sorted(p.partes_modificadas))
    resumo["ok"] = True
    return resumo


# --------------------------------------------------------------------------
# Recalculo da situacao num arquivo ja no v2 (o que o SIG-FT fara a cada rodada — T2)
# --------------------------------------------------------------------------
def recalcular_situacao(caminho: pathlib.Path, hoje: dt.date, apenas_documental: bool = False) -> dict:
    """Regrava SITUAÇÃO DA AUTORIZAÇÃO e DIAS DE ATRASO pela regra. AUTORIZADO nunca e desfeito.
    `apenas_documental`: so as linhas que passam a N/A (TIPO DE ENTREGA = DOCUMENTAL) — sem mexer
    nos dias de atraso que andaram desde a ultima gravacao. Salva so se alguma celula mudou."""
    resumo = {"arquivo": caminho.name, "alteradas": 0, "aviso": ""}
    ws = openpyxl.load_workbook(caminho)[ABA]
    hdr, mapa = cabecalho(ws)
    if N(C_SIT) not in mapa:
        resumo["aviso"] = "sem layout v2 — nada feito"
        return resumo
    col = lambda nome: mapa[N(nome)]  # noqa: E731
    fim = ultima_linha_com_dado(ws, hdr, mapa["DESCRICAO"])
    p = PlanilhaXlsx(caminho)
    L = p.parte_da_aba(ABA)
    for r in range(hdr + 1, fim + 1):
        atual, dias = ws.cell(r, col(C_SIT)).value, ws.cell(r, col(C_DIAS)).value
        sit, _, novo_dias = R.situacao_autorizacao(
            para_data(ws.cell(r, col(C_EMAIL)).value), atual, ws.cell(r, col(C_ENT)).value, hoje, dias,
            ws.cell(r, col(C_TIPO)).value)
        if N(ws.cell(r, col("STATUS")).value) == "DUPLICADO" and sit != "AUTORIZADO":
            sit, novo_dias = "", None                       # a situacao vale pela linha da ficha
        if apenas_documental and sit != "N/A":
            continue
        if N(sit) != N(atual):
            p.escrever(L, f"{col_letras(col(C_SIT))}{r}", sit or None)
            resumo["alteradas"] += 1
        if novo_dias != R._inteiro(dias):
            p.escrever(L, f"{col_letras(col(C_DIAS))}{r}", novo_dias)
            resumo["alteradas"] += 1
    if resumo["alteradas"]:
        p.salvar()
    resumo["_cols"] = {col(C_SIT), col(C_DIAS)}
    resumo["_hdr"] = hdr
    return resumo


def conferir_recalculo(original: pathlib.Path, novo: pathlib.Path, colunas: set[int], hdr: int) -> list[str]:
    """So SITUAÇÃO e DIAS DE ATRASO (linhas de dados) podem ter mudado; o resto do arquivo, nada."""
    problemas = []
    po, pn = PlanilhaXlsx(original), PlanilhaXlsx(novo)
    L = po.parte_da_aba(ABA)
    if list(po._bytes) != list(pn._bytes):
        problemas.append("lista de partes do arquivo mudou")
    problemas += [f"parte alterada sem querer: {n}" for n in po._bytes if n != L and po._bytes[n] != pn._bytes.get(n)]
    wa, wb = openpyxl.load_workbook(original)[ABA], openpyxl.load_workbook(novo)[ABA]
    for r in range(1, max(wa.max_row, wb.max_row) + 1):
        for c in range(1, max(wa.max_column, wb.max_column) + 1):
            if (c in colunas and r > hdr) or _igual(wa.cell(r, c).value, wb.cell(r, c).value):
                continue
            problemas.append(f"{col_letras(c)}{r} mudou")
            if len(problemas) > 10:
                return problemas
    ia, ib = inventario(original), inventario(novo)
    return problemas + [f"{k}: {ia[k]} -> {ib[k]}" for k in ia if ib[k] != ia[k]]


# --------------------------------------------------------------------------
# Conferencia: tudo o que existia esta no lugar novo; nada a mais
# --------------------------------------------------------------------------
def _igual(x, y) -> bool:
    if isinstance(x, float) and isinstance(y, float):
        return math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)
    return x == y


def _sem_posicoes(t: str) -> str:
    t = re.sub(r'(\sref=")[^"]*(")', r"\1\2", t)
    for tag in ("x:Row", "x:Column", "x:Anchor", "xdr:col", "xdr:row"):
        t = re.sub(rf"(<{tag}>).*?(</{tag}>)", r"\1\2", t, flags=re.S)
    return t


def conferir(original: pathlib.Path, migrado: pathlib.Path, plano: dict, libreoffice: bool = False) -> list[str]:
    problemas: list[str] = []
    if plano.get("ja_migrado"):
        return problemas
    d, novas, hdr = plano["d"], plano["novas"], plano["hdr"]
    po, pm = PlanilhaXlsx(original), PlanilhaXlsx(migrado)
    L = po.parte_da_aba(ABA)
    ligadas = po._partes_ligadas(L)
    texto_pos = [p for t in (REL_COMENTARIOS, REL_THREADED, REL_VML, REL_DESENHO) for p in ligadas.get(t, [])]
    editaveis = {L, po.parte_da_aba(ABA_LISTAS), "xl/workbook.xml", "xl/calcChain.xml", *texto_pos}

    # 1. partes: as mesmas; as nao relacionadas identicas; as de posicao so mudam numeros de posicao
    if list(po._bytes) != list(pm._bytes):
        problemas.append("lista de partes do arquivo mudou")
    for n in po._bytes:
        if n not in editaveis and po._bytes[n] != pm._bytes.get(n):
            problemas.append(f"parte alterada sem querer: {n}")
    for n in texto_pos:
        if _sem_posicoes(po._texto(n)) != _sem_posicoes(pm._texto(n)):
            problemas.append(f"{n}: mudou além das posições")

    # 2. celulas: cada uma do original no lugar novo, com o mesmo valor (ou a formula deslocada)
    wa = openpyxl.load_workbook(original)[ABA]
    wbm = openpyxl.load_workbook(migrado)
    wm = wbm[ABA]
    c_apto, c_sit = plano["mapa"][N(C_APTO)], plano["c_sit"]
    forn = plano.get("forn_movido")
    esperado: dict[tuple[int, int], object] = {}
    for row in wa.iter_rows():
        for c in row:
            if c.value in (None, ""):
                continue
            v = c.value
            alvo = (d.col(c.column), d.lin(c.row))
            if isinstance(v, str) and v.startswith("="):
                v = "=" + d.formula(v[1:], ABA, True)
            if c.column == c_apto:
                v = C_SIT if c.row == hdr else ("AUTORIZADO" if N(v) == "SIM" else v)
            if forn and c.column == forn:
                if c.row == hdr:
                    continue
                alvo = (novas[C_FORN], d.lin(c.row))
            esperado[alvo] = v
    for (cc, rr), v in esperado.items():
        atual = wm.cell(rr, cc).value
        if not _igual(atual, v):
            problemas.append(f"{col_letras(cc)}{rr}: esperado {v!r}, ficou {atual!r}")
            if len(problemas) > 12:
                break
    livres = set(novas.values()) | {c_sit}
    r_rev = plano.get("revisao", (None,))[0]
    extras = [c.coordinate for row in wm.iter_rows() for c in row
              if c.value not in (None, "") and (c.column, c.row) not in esperado
              and c.column not in livres and c.row != r_rev]
    if extras:
        problemas.append(f"{len(extras)} célula(s) inesperada(s): {', '.join(extras[:5])}")

    # 3. cabecalho na ordem do layout v2
    H = d.lin(hdr)
    nomes = [N(wm.cell(H, c).value) for c in range(1, wm.max_column + 1) if wm.cell(H, c).value not in (None, "")]
    i = nomes.index(N(C_LMR))
    seq = nomes[i: nomes.index(N(C_OBS)) + 1]
    if seq[:6] != [N(x) for x in (C_LMR, C_TIPO, C_EMAIL, C_SIT, C_DIAS, C_ENT)] or seq[-3:] != [N(x) for x in (C_FORN, C_PROC, C_OBS)]:
        problemas.append(f"ordem do cabeçalho: {' | '.join(seq)}")
    if plano.get("revisao"):
        r, c1, _, texto = plano["revisao"]
        if wm.cell(r, c1).value != texto:
            problemas.append("linha da revisão não encontrada")

    # 4. mesclagens, formatacao condicional, nomes definidos: o original deslocado, mais o novo
    mo = {d.sqref(m.get("ref")) for m in po.mesclagens(L)}
    mm = {m.get("ref") for m in pm.mesclagens(L)}
    novas_m = {f"{col_letras(plano['revisao'][1])}{plano['revisao'][0]}:{col_letras(plano['revisao'][2])}{plano['revisao'][0]}"} \
        if plano.get("revisao") and plano["revisao"][2] > plano["revisao"][1] else set()
    if mm != mo | novas_m:
        problemas.append(f"mesclagens: faltam {sorted(mo - mm)[:3]} sobram {sorted(mm - mo - novas_m)[:3]}")
    caixas = [limites(m) for m in mm]
    for a in range(len(caixas)):
        for b in range(a + 1, len(caixas)):
            x, y = caixas[a], caixas[b]
            if x[0] <= y[2] and y[0] <= x[2] and x[1] <= y[3] and y[1] <= x[3]:
                problemas.append("mesclagens sobrepostas")
    cf = lambda p, desl: sorted((desl(el.get("sqref")), tuple(desl(f.text or "", True) for f in el.iter(q("formula"))))  # noqa: E731
                                for el in p.raiz(L).iter(q("conditionalFormatting")))
    if cf(po, lambda s, f=False: d.formula(s, ABA, True) if f else d.sqref(s)) != cf(pm, lambda s, f=False: s):
        problemas.append("formatação condicional não acompanhou")
    dn = lambda p: {(n.get("name"), n.get("localSheetId")): n.text for n in p.raiz("xl/workbook.xml").iter(q("definedName"))}  # noqa: E731
    no, nm = dn(po), dn(pm)
    for k, v in no.items():
        if k[0] in LISTAS or k[0] == "versao_layout_status_pmib":
            continue
        if nm.get(k) != d.formula(v or "", ABA, False):
            problemas.append(f"nome definido {k[0]}: {nm.get(k)!r}")

    # 5. comentarios no lugar novo (anotacao e thread) e cadeia de calculo apontando para formula
    def refs(p: PlanilhaXlsx, tipo: str, tag: str) -> list[str]:
        return [r for n in p._partes_ligadas(L).get(tipo, []) for r in re.findall(rf'<{tag}\b[^>]*?\sref="([^"]+)"', p._texto(n))]
    for tipo, tag in ((REL_COMENTARIOS, "comment"), (REL_THREADED, "threadedComment")):
        if [d.faixa(r) for r in refs(po, tipo, tag)] != refs(pm, tipo, tag):
            problemas.append(f"{tag}: posições não acompanharam")
    if "xl/calcChain.xml" in pm._bytes:
        sid = next(s.get("sheetId") for s in pm.raiz("xl/workbook.xml").iter(q("sheet")) if s.get("name") == ABA)
        com_formula = {c.get("r") for c in pm.raiz(L).iter(q("c")) if c.find(q("f")) is not None}
        atual = None
        for m in re.finditer(r"<c\b([^>]*?)/?>", pm._texto("xl/calcChain.xml")):
            mi = re.search(r'\si="(\d+)"', m.group(1))
            atual = mi.group(1) if mi else atual
            r = re.search(r'\sr="([^"]+)"', m.group(1))
            if atual == sid and r and r.group(1) not in com_formula:
                problemas.append(f"calcChain aponta {r.group(1)} sem fórmula")
                break

    # 6. ordem das linhas/celulas no XML (o Excel exige crescente)
    ult_r = 0
    for row in pm.raiz(L).find(q("sheetData")).iterchildren(q("row")):
        r = int(row.get("r"))
        cols = [limites(c.get("r"))[0] for c in row.iterchildren(q("c"))]
        if r <= ult_r or cols != sorted(set(cols)):
            problemas.append(f"linha {r}: ordem de linhas/células inválida")
            break
        ult_r = r

    # 7. o SIG-FT acha o cabecalho (CÓDIGO DO MATERIAL nas 10 primeiras linhas, via pandas)
    prev = pd.read_excel(migrado, sheet_name=ABA, header=None, nrows=10, na_filter=False)
    linha = next((i for i, row in enumerate(prev.values.tolist())
                  if any(str(v).strip().upper() == "CÓDIGO DO MATERIAL" for v in row)), None)
    if linha is None:
        problemas.append("SIG-FT não acharia o cabeçalho (CÓDIGO DO MATERIAL)")
    else:
        colunas = {str(c).strip().upper() for c in pd.read_excel(migrado, sheet_name=ABA, skiprows=linha, nrows=1).columns}
        faltam = {x for x in (C_SIT, C_DIAS, C_TIPO, C_FORN, C_PROC, "CÓDIGO PMIB", C_EMAIL, C_ENT)} - colunas
        if faltam:
            problemas.append(f"leitura pelo SIG-FT não vê: {', '.join(sorted(faltam))}")

    # 8. listas suspensas sobrevivem a um save do openpyxl (o que o SIG-FT faz hoje)
    tmp = migrado.with_name(migrado.stem + ".roundtrip.xlsx")
    wbm.save(tmp)
    dvs = [dv.formula1 for dv in openpyxl.load_workbook(tmp)[ABA].data_validations.dataValidation]
    tmp.unlink()
    for nome in ("lst_tipo_entrega", "lst_status", "lst_situacao"):
        if not any(f and nome in f for f in dvs):
            problemas.append(f"validação {nome} não sobrevive a um save do openpyxl")

    ia, ib = inventario(original), inventario(migrado)
    problemas += [f"{k}: {ia[k]} -> {ib[k]}" for k in ia if ib[k] != ia[k]]
    if libreoffice and not abre_no_libreoffice(migrado):
        problemas.append("LibreOffice não conseguiu abrir o arquivo")
    return problemas


SOFFICE = pathlib.Path(r"C:\Program Files\LibreOffice\program\soffice.exe")


def abre_no_libreoffice(caminho: pathlib.Path) -> bool:
    """Teste extra de integridade: o LibreOffice abre e reconverte o arquivo."""
    if not SOFFICE.exists():
        return True
    with tempfile.TemporaryDirectory() as d:
        perfil = pathlib.Path(d, "perfil").as_uri()
        subprocess.run([str(SOFFICE), f"-env:UserInstallation={perfil}", "--headless", "--calc", "--convert-to", "xlsx",
                        "--outdir", d, str(caminho)], capture_output=True, timeout=240)
        return any(pathlib.Path(d).glob("*.xlsx"))


# --------------------------------------------------------------------------
def fontes() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Pre-preenchimento (tipo pela lista de precos, procurement pela mapeadora) e revisao em uso."""
    precos, _ = R.ler_listas_precos()
    tipo = {p: t for p, t in zip(precos["PMIB"], precos["TIPO"]) if p and isinstance(t, str)}
    listas = R.ler_mapeadora()["listas"]
    nomes = {N(n): n for n in LISTAS["lst_procurement"]}
    proc = {str(l).strip(): nomes[N(n)] for l, n in zip(listas["N DOCUMENTO ITAIPU"], listas["PROCUREMENT"])
            if N(n) in nomes}
    rev = {str(l).strip(): str(v).strip() for l, v in zip(listas["N DOCUMENTO ITAIPU"], listas["REVISAO EM USO"])
           if str(v).strip() not in ("", "nan", "None")}
    return tipo, proc, rev


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--simular", action="store_true")
    g.add_argument("--aplicar", action="store_true")
    g.add_argument("--template", nargs=2, metavar=("ORIGEM", "DESTINO"))
    ap.add_argument("--saida", type=pathlib.Path, default=pathlib.Path(tempfile.gettempdir()) / "status_pmib_v2_simulacao")
    ap.add_argument("--backup", type=pathlib.Path,
                    default=pathlib.Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Sobressalentes-v2")
    ap.add_argument("--so", help="migra só arquivos cujo nome contém este texto")
    ap.add_argument("--confirmo", action="store_true", help="no --aplicar, dispensa a pergunta (autorização já dada)")
    ap.add_argument("--libreoffice", action="store_true", help="na conferência, abre cada arquivo no LibreOffice")
    ap.add_argument("--recalcular", action="store_true",
                    help="arquivos já no v2: regrava SITUAÇÃO e DIAS DE ATRASO pela regra (com --simular ou --aplicar)")
    ap.add_argument("--apenas-documental", action="store_true",
                    help="com --recalcular: só as linhas DOCUMENTAL (passam a N/A)")
    args = ap.parse_args()

    if args.template:
        origem, destino = map(pathlib.Path, args.template)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
        res = migrar_planilha(destino, {}, None, None, folga=400)
        print({k: v for k, v in res.items() if not k.startswith("_")})
        print("Conferência:", "; ".join(conferir(origem, destino, res["_plano"], args.libreoffice)) or "nenhuma perda")
        return 0

    tipo, proc, rev = fontes()
    arquivos = R.listar_status_pmib()
    if args.so:
        arquivos = [a for a in arquivos if args.so.upper() in a.name.upper()]

    alvos = []                                    # (referencia intocada, arquivo que sera migrado)
    if args.aplicar:
        if not args.confirmo and input(f"Vai ALTERAR {len(arquivos)} arquivos NO BOX. Digite APLICAR: ").strip() != "APLICAR":
            print("Cancelado.")
            return 1
        pasta = args.backup / f"backup_{dt.datetime.now():%Y%m%d-%H%M}"
        pasta.mkdir(parents=True, exist_ok=True)
        for a in arquivos:                    # estrutura plana: o caminho completo estoura os 260 caracteres
            copia = pasta / a.name
            shutil.copy2(a, copia)
            alvos.append((copia, a))
        print(f"Backup em {pasta}")
    else:
        pasta = args.saida
        if pasta.exists():
            shutil.rmtree(pasta)
        pasta.mkdir(parents=True)
        for a in arquivos:
            copia = pasta / a.name
            shutil.copy2(a, copia)
            alvos.append((a, copia))

    if args.recalcular:
        total = 0
        for referencia, alvo in alvos:
            try:
                res = recalcular_situacao(alvo, dt.date.today(), args.apenas_documental)
                prob = "; ".join(conferir_recalculo(referencia, alvo, res["_cols"], res["_hdr"])) if res["alteradas"] else ""
            except PermissionError:
                res, prob = {"alteradas": 0, "aviso": "arquivo aberto (Excel) — não alterado"}, ""
            total += res["alteradas"]
            if res["alteradas"] or res["aviso"] or prob:
                print(f"{alvo.name[:52]:52s} células alteradas {res['alteradas']:3d} {res['aviso']} {'!! ' + prob if prob else ''}")
        print(f"\nTotal de células alteradas: {total}")
        return 0

    resumos = []
    for referencia, alvo in alvos:
        lista = alvo.name[: -len("_STATUS_PMIB.xlsx")]
        try:
            res = migrar_planilha(alvo, tipo, proc.get(lista), rev.get(lista))
            res["problemas"] = "; ".join(conferir(referencia, alvo, res["_plano"], args.libreoffice)) or "—"
        except PermissionError:
            res = {"arquivo": alvo.name, "ok": False, "erro": "arquivo aberto (Excel) — não migrado"}
        except Exception as e:  # noqa: BLE001 — registra e segue
            res = {"arquivo": alvo.name, "ok": False, "erro": f"{type(e).__name__}: {e}"}
        res.pop("_plano", None)
        res["lista"] = lista
        res["caminho_no_box"] = str((alvo if args.aplicar else referencia).relative_to(R.PASTA_PMIB))
        resumos.append(res)
        print(f"{'OK  ' if res.get('ok') else 'ERRO'} {alvo.name[:52]:52s} rev {res.get('linha_revisao', ''):22s} "
              f"aut {res.get('autorizado', 0):3d} agu {res.get('aguardando', 0):3d} atr {res.get('atrasado', 0):3d} "
              f"tipo {res.get('tipo_preenchido', 0):3d} proc {res.get('procurement_preenchido', 0):3d} "
              f"{res.get('aviso', '')}{res.get('erro', '')} {'' if res.get('problemas', '—') == '—' else '!! ' + res['problemas']}")
    df = pd.DataFrame(resumos)
    relatorio = pasta / "relatorio_migracao.csv"
    df.to_csv(relatorio, index=False, encoding="utf-8-sig", sep=";")
    ruins = df[df.get("problemas", pd.Series(dtype=str)).fillna("—") != "—"]
    soma = lambda c: int(df.get(c, pd.Series([0])).fillna(0).sum())  # noqa: E731
    print(f"\n{int(df['ok'].fillna(False).sum())} de {len(df)} migrados | SITUAÇÃO: {soma('autorizado')} autorizado "
          f"({soma('autorizado_por_entregue')} só pelo ENTREGUE), {soma('aguardando')} aguardando, {soma('atrasado')} atrasado | "
          f"TIPO pré-preenchido: {soma('tipo_preenchido')} | PROCUREMENT: {soma('procurement_preenchido')}")
    print("Conferencia:", "nenhuma perda" if ruins.empty else f"{len(ruins)} arquivo(s) com diferença")
    print(f"Relatorio: {relatorio}")
    return 0 if df["ok"].fillna(False).all() and ruins.empty else 2


if __name__ == "__main__":
    sys.exit(main())

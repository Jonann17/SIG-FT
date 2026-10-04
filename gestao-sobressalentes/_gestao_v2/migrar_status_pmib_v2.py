# -*- coding: utf-8 -*-
"""
Migra planilhas _STATUS_PMIB para o layout v2 — sem perder nada.

Como: edicao "cirurgica" do .xlsx (`xlsx_cirurgico.py`). So tres partes do
arquivo sao alteradas — a aba "Lista de Materiais", a aba "Checklist" e a
lista de nomes definidos (xl/workbook.xml). Todo o resto (comentarios em
thread, anotacoes, desenhos, estilos, impressao...) sai identico, byte a byte.
O openpyxl so e usado para LER (achar cabecalho, ultima linha, valores).

O que muda no arquivo (nada que ja existe muda de lugar ou de nome):
  1. Bloco novo A DIREITA da tabela:
       TIPO DE ENTREGA | FORNECEDOR | PROCUREMENT | DATA DA AUTORIZACAO ITAIPU |
       PRAZO AUTORIZACAO ITAIPU (15 D.U.) | SITUACAO DA AUTORIZACAO | DIAS UTEIS DE ATRASO
     As tres ultimas sao VALORES gravados pelo SIG-FT quando roda (nada de
     formula no Excel). Nascem vazias — ou preenchidas uma vez com --calcular.
  2. Vocabularios das listas suspensas na aba Checklist (a direita do que ja
     existe) + nomes definidos lst_status, lst_secao, lst_simnao,
     lst_tipo_entrega, lst_procurement.
  3. Listas suspensas recriadas POR NOME DEFINIDO em STATUS, secoes, APTO,
     EQUIPAMENTO ENTREGUE e nas colunas novas. As atuais apontam para outra aba
     e sao gravadas como extensao — o openpyxl do SIG-FT as apaga ao salvar.
     Por nome definido, sobrevivem.
  4. Pre-preenchimento, so em celula vazia: TIPO DE ENTREGA pela lista de
     precos (PMIB) e PROCUREMENT pela mapeadora (lista com uma pessoa so).

MODOS
  python migrar_status_pmib_v2.py --simular [--libreoffice]
      Copia os _STATUS_PMIB do Box para uma pasta LOCAL (%TEMP%), migra as
      COPIAS e confere cada uma contra o original. Nao toca no Box.
  python migrar_status_pmib_v2.py --template ORIGEM DESTINO
      Gera o template v2 a partir de uma copia do template atual.
  python migrar_status_pmib_v2.py --aplicar [--so TEXTO] [--confirmo]
      Migra OS ARQUIVOS DO BOX, gravando por cima do mesmo arquivo (o Box guarda
      a versao anterior), depois de copiar cada original para
      %LOCALAPPDATA%\\Sobressalentes-v2\\backup_AAAAMMDD-HHMM.
      >>> SO RODAR COM AUTORIZACAO EXPLICITA DO LUAN. <<<

CONFERENCIA (automatica, por arquivo): partes nao editadas identicas; nenhuma
celula existente alterada; comentarios, anotacoes, formatacao condicional e
desenhos na mesma quantidade; o SIG-FT ainda acha o cabecalho; as listas
suspensas sobrevivem a um save do openpyxl. Com --libreoffice, abre cada
arquivo no LibreOffice como teste extra de integridade.

Requisitos: openpyxl, pandas, lxml
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import warnings
import zipfile

import openpyxl
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "_scripts"))
sys.path.insert(0, str(AQUI))
import regras_sobressalentes as R  # noqa: E402
from xlsx_cirurgico import PlanilhaXlsx, col_letras, limites  # noqa: E402

C_TIPO, C_FORN, C_PROC = "TIPO DE ENTREGA", "FORNECEDOR", "PROCUREMENT"
C_DT_AUT = "DATA DA AUTORIZAÇÃO ITAIPU"
C_PRAZO, C_SIT, C_DIAS = "PRAZO AUTORIZAÇÃO ITAIPU (15 D.U.)", "SITUAÇÃO DA AUTORIZAÇÃO", "DIAS ÚTEIS DE ATRASO"
BLOCO = [C_TIPO, C_FORN, C_PROC, C_DT_AUT, C_PRAZO, C_SIT, C_DIAS]
DO_SIGFT = {C_PRAZO, C_SIT, C_DIAS}                 # valores gravados pelo SIG-FT, nao formulas
COLUNAS_DATA = {C_DT_AUT, C_PRAZO}
LARGURAS = {C_TIPO: 20, C_FORN: 18, C_PROC: 18, C_DT_AUT: 15, C_PRAZO: 15, C_SIT: 24, C_DIAS: 11}

LISTAS = {
    "lst_status": ["FICHA CRIADA", "DUPLICADO", "COM O FORNECEDOR", "EM ELABORAÇÃO", "EM CORREÇÃO",
                   "EM ANÁLISE IB", "APROVADO", "INICIAR", "N/A"],
    "lst_secao": ["COMPLETO", "INCOMPLETO", "N/A"],
    "lst_simnao": ["SIM", "NÃO"],
    "lst_tipo_entrega": ["FÍSICA E DOCUMENTAL", "DOCUMENTAL", "TÍTULO"],
    # alerta "aviso": aceita nome novo. Tirada da mapeadora.
    "lst_procurement": ["BRUNA", "DOUGLAS COSTA", "FLAVIA SANTOS", "JULLY CARVALHO", "LEILA MEDEIROS",
                        "LYVIA MACHADO", "MARCELO MENDES", "SUELEN BRUM"],
}
VALIDACOES_EXISTENTES = {
    "STATUS": "lst_status", "INFO. GERAIS": "lst_secao", "CARACT. TECNICAS": "lst_secao",
    "DOCUMENTOS E IMAGENS": "lst_secao", "CONDICOES": "lst_secao", "VALORIZACAO": "lst_secao",
    "APLICACAO - LMR": "lst_secao", "APTO PARA ENTREGA": "lst_simnao", "EQUIPAMENTO ENTREGUE": "lst_simnao",
}
FOLGA_LINHAS = 50          # validacoes vao alem da ultima linha com dado
ABA, ABA_LISTAS = "Lista de Materiais", "Checklist"


# --------------------------------------------------------------------------
# Leitura da estrutura (openpyxl so le; quem grava e o xlsx_cirurgico)
# --------------------------------------------------------------------------
def cabecalho(ws) -> tuple[int, dict[str, int]]:
    for linha in range(1, 15):
        nomes = {}
        for c in range(1, 80):
            v = ws.cell(linha, c).value
            if v not in (None, ""):
                nomes.setdefault(R.normalizar(v), c)
        if "DESCRICAO" in nomes:
            return linha, nomes
    raise ValueError("cabeçalho com DESCRIÇÃO não encontrado nas 14 primeiras linhas")


def ultima_linha_com_dado(ws, hdr: int, col_desc: int) -> int:
    fim = hdr
    for r in range(hdr + 1, ws.max_row + 1):
        if ws.cell(r, col_desc).value not in (None, ""):
            fim = r
    return fim


def ultima_coluna_usada(ws, desde_linha: int) -> int:
    fim = 0
    for row in ws.iter_rows(min_row=desde_linha):
        for c in row:
            if c.value not in (None, ""):
                fim = max(fim, c.column)
    return fim


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
        inicio = limites(atual.split("!")[1])[0]               # ja migrado: reescreve no mesmo lugar
    else:
        inicio = p.ultima_coluna_com_valor(parte) + 2
    for j, (nome, valores) in enumerate(LISTAS.items()):
        col = col_letras(inicio + j)
        p.escrever(parte, f"{col}2", nome)
        for i, v in enumerate(valores, start=3):
            p.escrever(parte, f"{col}{i}", v)
        p.largura(parte, inicio + j, 24)
        p.definir_nome(nome, f"{ABA_LISTAS}!${col}$3:${col}${2 + len(valores)}")


def migrar_planilha(caminho: pathlib.Path, prefill_tipo: dict[str, str], prefill_proc: str | None,
                    folga: int = FOLGA_LINHAS, calcular: bool = False, hoje: dt.date | None = None) -> dict:
    resumo = {"arquivo": caminho.name, "colunas_inseridas": 0, "inicio_bloco": "", "aviso": "",
              "tipo_preenchido": 0, "procurement_preenchido": 0, "calculados": 0}
    ws = openpyxl.load_workbook(caminho)[ABA]                   # leitura
    hdr, mapa = cabecalho(ws)
    ultimo_cab = max(mapa.values())
    fim_dados = ultima_linha_com_dado(ws, hdr, mapa["DESCRICAO"])
    primeira, ultima = hdr + 1, max(fim_dados, hdr + 1) + folga

    p = PlanilhaXlsx(caminho)
    L, C = p.parte_da_aba(ABA), p.parte_da_aba(ABA_LISTAS)
    col_email = col_letras(mapa["DATA DO EMAIL COMUNICANDO ENTREGA"])

    # 1. bloco novo: logo apos o cabecalho, ou apos anotacoes soltas a direita
    faltam = [c for c in BLOCO if R.normalizar(c) not in mapa]
    pos = {R.normalizar(c): mapa[R.normalizar(c)] for c in BLOCO if R.normalizar(c) in mapa}
    if faltam:
        usada = ultima_coluna_usada(ws, hdr)
        inicio = ultimo_cab + 1 if usada <= ultimo_cab else usada + 2
        if usada > ultimo_cab:
            resumo["aviso"] = (f"anotações soltas em {col_letras(ultimo_cab + 1)}:{col_letras(usada)} — "
                               f"bloco v2 começa em {col_letras(inicio)}")
        est_cab = p.estilo(L, f"{col_letras(ultimo_cab)}{hdr}")
        for k, nome in enumerate(faltam):
            col = inicio + k
            p.escrever(L, f"{col_letras(col)}{hdr}", nome, est_cab)
            p.largura(L, col, LARGURAS[nome])
            pos[R.normalizar(nome)] = col
            resumo["colunas_inseridas"] += 1
        # celulas de dados com o estilo da linha (bordas); colunas de data com o estilo da data do e-mail
        for r in range(primeira, fim_dados + 1):
            est, est_data = p.estilo(L, f"{col_letras(ultimo_cab)}{r}"), p.estilo(L, f"{col_email}{r}")
            for nome in faltam:
                ref = f"{col_letras(pos[R.normalizar(nome)])}{r}"
                e = est_data if nome in COLUNAS_DATA else est
                if e is not None and not p.tem_valor(L, ref):
                    p.escrever(L, ref, None, e)
        # titulo mesclado acompanha a tabela, se o bloco estiver colado nela
        if inicio == ultimo_cab + 1:
            fim_bloco = inicio + len(faltam) - 1
            for m in p.mesclagens(L):
                c1, _, c2, r2 = limites(m.get("ref"))
                if r2 < hdr and c2 == ultimo_cab and c1 <= 2:
                    p.estender_mesclagem(L, m, fim_bloco)
        resumo["inicio_bloco"] = col_letras(inicio)
    else:
        resumo["inicio_bloco"] = col_letras(pos[R.normalizar(C_TIPO)])
    letra = {nome: col_letras(pos[R.normalizar(nome)]) for nome in BLOCO}

    # 2. vocabularios e 3. listas suspensas por nome definido
    garantir_listas(p, C)
    existentes = {mapa[k]: v for k, v in VALIDACOES_EXISTENTES.items() if k in mapa}
    p.remover_validacoes(L, set(existentes) | {pos[R.normalizar(n)] for n in BLOCO}, primeira)
    faixa = lambda col: f"{col}{primeira}:{col}{ultima}"  # noqa: E731
    for col, nome in existentes.items():
        p.adicionar_validacao(L, faixa(col_letras(col)), "list", nome, alerta="warning")
    p.adicionar_validacao(L, faixa(letra[C_TIPO]), "list", "lst_tipo_entrega", titulo="Tipo de entrega",
                          mensagem="FÍSICA E DOCUMENTAL (sai na nota fiscal) · DOCUMENTAL (componente, só ficha) · TÍTULO (conjunto)")
    p.adicionar_validacao(L, faixa(letra[C_PROC]), "list", "lst_procurement", alerta="warning",
                          titulo="Procurement", mensagem="Escolha da lista ou digite um nome novo.")
    p.adicionar_validacao(L, faixa(letra[C_DT_AUT]), "date", "DATE(2024,1,1)", "DATE(2030,12,31)", "between",
                          alerta="warning", titulo="Data", mensagem="Data em que Itaipu autorizou a entrega.")
    for nome in (C_PRAZO, C_SIT, C_DIAS):
        p.adicionar_validacao(L, faixa(letra[nome]), "none", titulo="Preenchido pelo SIG-FT",
                              mensagem="Calculado pelo SIG-FT quando roda (15 dias úteis do e-mail de intenção). Não digitar.")

    # 4. pre-preenchimento — so celula vazia, so linha com PMIB valido
    c_pmib = mapa["CODIGO PMIB"]
    for r in range(primeira, fim_dados + 1):
        pmib = R.normalizar_pmib(ws.cell(r, c_pmib).value)
        if not pmib:
            continue
        est = p.estilo(L, f"{col_letras(ultimo_cab)}{r}")
        for nome, valor, chave in ((C_TIPO, prefill_tipo.get(pmib), "tipo_preenchido"),
                                   (C_PROC, prefill_proc, "procurement_preenchido")):
            ref = f"{letra[nome]}{r}"
            if valor and not p.tem_valor(L, ref):
                p.escrever(L, ref, valor, p.estilo(L, ref) or est)
                resumo[chave] += 1

    # 5. opcional: a primeira rodada do calculo que depois e do SIG-FT
    if calcular:
        resumo["calculados"] = gravar_calculos(p, L, ws, mapa, letra, primeira, fim_dados, hoje or dt.date.today())

    p.definir_nome("versao_layout_status_pmib", '"v2"')
    p.salvar()
    resumo["partes_alteradas"] = ", ".join(sorted(p.partes_modificadas))
    resumo["ok"] = True
    return resumo


def gravar_calculos(p: PlanilhaXlsx, L: str, ws, mapa: dict, letra: dict, primeira: int, fim: int, hoje: dt.date) -> int:
    """Prazo, situacao e atraso como VALORES — o que o SIG-FT passa a fazer a cada execucao.
    Linha DUPLICADO fica em branco (a situacao vale pela linha da ficha)."""
    n = 0
    col = lambda nome: mapa.get(R.normalizar(nome))  # noqa: E731
    for r in range(primeira, fim + 1):
        status = R.normalizar(ws.cell(r, mapa["STATUS"]).value) if "STATUS" in mapa else ""
        email = ws.cell(r, col("DATA DO EMAIL COMUNICANDO ENTREGA")).value
        aut = ws.cell(r, col(C_DT_AUT)).value if col(C_DT_AUT) else None
        apto = ws.cell(r, col("APTO PARA ENTREGA")).value if col("APTO PARA ENTREGA") else None
        entregue = ws.cell(r, col("EQUIPAMENTO ENTREGUE")).value if col("EQUIPAMENTO ENTREGUE") else None
        d_email = email.date() if isinstance(email, dt.datetime) else None
        d_aut = aut.date() if isinstance(aut, dt.datetime) else None
        sit, prazo, du = R.situacao_autorizacao(d_email, apto, d_aut, entregue, hoje)
        vazio = status == "DUPLICADO" or sit == "SEM PEDIDO"
        p.escrever(L, f"{letra[C_PRAZO]}{r}", None if vazio else prazo, p.estilo(L, f"{letra[C_PRAZO]}{r}"))
        p.escrever(L, f"{letra[C_SIT]}{r}", None if vazio else sit, p.estilo(L, f"{letra[C_SIT]}{r}"))
        p.escrever(L, f"{letra[C_DIAS]}{r}", None if vazio else du, p.estilo(L, f"{letra[C_DIAS]}{r}"))
        n += not vazio
    return n


# --------------------------------------------------------------------------
# Conferencia: nada do que existia pode mudar
# --------------------------------------------------------------------------
def conferir(original: pathlib.Path, migrado: pathlib.Path, libreoffice: bool = False) -> list[str]:
    problemas = []
    po = PlanilhaXlsx(original)
    editaveis = {po.parte_da_aba(ABA), po.parte_da_aba(ABA_LISTAS), "xl/workbook.xml"}
    with zipfile.ZipFile(original) as za, zipfile.ZipFile(migrado) as zb:
        if za.namelist() != zb.namelist():
            problemas.append("lista de partes do arquivo mudou")
        for n in za.namelist():
            if n not in editaveis and n in zb.namelist() and za.read(n) != zb.read(n):
                problemas.append(f"parte alterada sem querer: {n}")
    a = R.ler_tabela(original, ABA, max_col=80)
    b = R.ler_tabela(migrado, ABA, max_col=80)
    if len(a) != len(b):
        problemas.append(f"linhas com dado mudaram: {len(a)} -> {len(b)}")
    problemas += [f"coluna nova ausente: {c}" for c in (R.normalizar(x) for x in BLOCO) if c not in b.columns]
    # toda celula preenchida do original (valor ou formula) continua igual, no mesmo lugar
    wa = openpyxl.load_workbook(original)[ABA]
    wbk = openpyxl.load_workbook(migrado)
    wm = wbk[ABA]

    def igual(x, y) -> bool:
        if isinstance(x, float) and isinstance(y, float):
            return math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)
        return x == y
    mudaram = [c.coordinate for row in wa.iter_rows() for c in row
               if c.value not in (None, "") and not igual(wm[c.coordinate].value, c.value)]
    if mudaram:
        problemas.append(f"{len(mudaram)} célula(s) existentes mudaram: {', '.join(mudaram[:5])}")
    # o SIG-FT acha o cabecalho por 'CÓDIGO DO MATERIAL' nas 10 primeiras linhas (pandas)
    if not any(any(str(c).strip().upper() == "CÓDIGO DO MATERIAL" for c in
                   pd.read_excel(migrado, sheet_name=ABA, skiprows=i, nrows=1, na_filter=False).columns)
               for i in range(10)):
        problemas.append("SIG-FT não acharia o cabeçalho (CÓDIGO DO MATERIAL)")
    # as listas suspensas precisam sobreviver a um save do openpyxl (o que o SIG-FT faz hoje)
    tmp = migrado.with_name(migrado.stem + ".roundtrip.xlsx")
    wbk.save(tmp)
    dvs = [dv.formula1 for dv in openpyxl.load_workbook(tmp)[ABA].data_validations.dataValidation]
    tmp.unlink()
    for nome in ("lst_tipo_entrega", "lst_status"):
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
        subprocess.run([str(SOFFICE), "--headless", "--calc", "--convert-to", "xlsx", "--outdir", d, str(caminho)],
                       capture_output=True, timeout=180)
        return any(pathlib.Path(d).glob("*.xlsx"))


# --------------------------------------------------------------------------
def fontes_prefill() -> tuple[dict[str, str], dict[str, str]]:
    precos, _ = R.ler_listas_precos()
    tipo = {p: t for p, t in zip(precos["PMIB"], precos["TIPO"]) if p and isinstance(t, str)}
    listas = R.ler_mapeadora()["listas"]
    nomes = {R.normalizar(n): n for n in LISTAS["lst_procurement"]}
    proc = {str(l).strip(): nomes[R.normalizar(n)] for l, n in zip(listas["N DOCUMENTO ITAIPU"], listas["PROCUREMENT"])
            if R.normalizar(n) in nomes}
    return tipo, proc


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
    ap.add_argument("--calcular", action="store_true",
                    help="grava já uma vez prazo/situação/atraso (o que depois é papel do SIG-FT)")
    ap.add_argument("--libreoffice", action="store_true", help="na conferência, abre cada arquivo no LibreOffice")
    args = ap.parse_args()

    if args.template:
        origem, destino = map(pathlib.Path, args.template)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
        print(migrar_planilha(destino, {}, None, folga=400))
        return 0

    tipo, proc = fontes_prefill()
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

    resumos = []
    for referencia, alvo in alvos:
        lista = alvo.name[: -len("_STATUS_PMIB.xlsx")]
        try:
            res = migrar_planilha(alvo, tipo, proc.get(lista), calcular=args.calcular)
            res["problemas"] = "; ".join(conferir(referencia, alvo, args.libreoffice)) or "—"
        except PermissionError:
            res = {"arquivo": alvo.name, "ok": False, "erro": "arquivo aberto (Excel) — não migrado"}
        except Exception as e:  # noqa: BLE001 — registra e segue
            res = {"arquivo": alvo.name, "ok": False, "erro": f"{type(e).__name__}: {e}"}
        res["lista"] = lista
        res["caminho_no_box"] = str((alvo if args.aplicar else referencia).relative_to(R.PASTA_PMIB))
        resumos.append(res)
        print(f"{'OK  ' if res.get('ok') else 'ERRO'} {alvo.name[:58]:58s} bloco {res.get('inicio_bloco', ''):3s} "
              f"tipo {res.get('tipo_preenchido', 0):3d} proc {res.get('procurement_preenchido', 0):3d} "
              f"{res.get('aviso', '')} {res.get('erro', '')} {'' if res.get('problemas', '—') == '—' else '!! ' + res['problemas']}")
    df = pd.DataFrame(resumos)
    relatorio = pasta / "relatorio_migracao.csv"
    df.to_csv(relatorio, index=False, encoding="utf-8-sig", sep=";")
    ruins = df[df.get("problemas", pd.Series(dtype=str)).fillna("—") != "—"]
    print(f"\n{int(df['ok'].fillna(False).sum())} de {len(df)} migrados | TIPO DE ENTREGA pré-preenchido: "
          f"{int(df.get('tipo_preenchido', pd.Series([0])).fillna(0).sum())} | PROCUREMENT: "
          f"{int(df.get('procurement_preenchido', pd.Series([0])).fillna(0).sum())}")
    print("Conferencia:", "nenhuma perda" if ruins.empty else f"{len(ruins)} arquivo(s) com diferença")
    print(f"Relatorio: {relatorio}")
    return 0 if df["ok"].fillna(False).all() and ruins.empty else 2


if __name__ == "__main__":
    sys.exit(main())

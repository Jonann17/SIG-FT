# -*- coding: utf-8 -*-
"""
Migra planilhas _STATUS_PMIB para o layout v2.

O que muda no arquivo (nada que ja existe muda de lugar ou de nome — o
SIG-FT e o Power BI leem por nome, e a equipe nao perde a referencia):

  1. Bloco novo de colunas A DIREITA da tabela:
       TIPO DE ENTREGA | FORNECEDOR | PROCUREMENT |
       PRAZO AUTORIZACAO ITAIPU (15 D.U.) [formula] | DATA DA AUTORIZACAO ITAIPU |
       SITUACAO DA AUTORIZACAO [formula] | DIAS UTEIS DE ATRASO [formula] | DATA DA ENTREGA
     Se ha anotacoes soltas logo a direita da tabela, o bloco comeca depois
     delas (e o relatorio avisa).
  2. Aba `Feriados` (nome definido `Feriados`) — o calendario dos 15 d.u.
  3. Aba `Listas` com os vocabularios e nomes definidos (lst_status,
     lst_secao, lst_simnao, lst_tipo_entrega, lst_procurement).
  4. Listas suspensas recriadas por NOME DEFINIDO em STATUS, secoes, APTO,
     EQUIPAMENTO ENTREGUE e nas colunas novas. Motivo: as atuais apontam
     para outra aba (Checklist!$A$3:$A$8), sao gravadas como "extensao" e o
     openpyxl — que o SIG-FT usa para salvar — APAGA esse tipo. Por nome
     definido, sobrevivem.
  5. Formatacao condicional da situacao da autorizacao.
  6. Pre-preenchimento, so em celula vazia: TIPO DE ENTREGA pela lista de
     precos (PMIB) e PROCUREMENT pela mapeadora (lista com uma pessoa so).

PROTECAO: o openpyxl APAGA comentarios em thread (autor, data, respostas). Arquivo
que tem esse tipo de comentario e PULADO, intocado — migrar pelo Excel (ver
"Plano - Reestruturacao do STATUS_PMIB"), ou rodar com --aceitar-perda-de-comentarios
se a perda for aceita. A conferencia compara, antes e depois, celulas, anotacoes,
comentarios, formatacao condicional e desenhos.

MODOS
  python migrar_status_pmib_v2.py --simular
      Copia os _STATUS_PMIB do Box para uma pasta LOCAL (%TEMP%, nao
      sincronizada), migra as COPIAS e confere cada uma contra o original.
      Nao toca no Box.
  python migrar_status_pmib_v2.py --template ORIGEM DESTINO
      Gera o template v2 a partir de uma copia do template atual.
  python migrar_status_pmib_v2.py --aplicar [--confirmo]
      Migra OS ARQUIVOS DO BOX, no lugar, depois de copiar cada original para
      %LOCALAPPDATA%\\Sobressalentes-v2\\backup_AAAAMMDD-HHMM (fora do Box e do
      OneDrive). Pula arquivo aberto no Excel.
      >>> SO RODAR COM AUTORIZACAO EXPLICITA DO LUAN. <<<

Requisitos: openpyxl, pandas
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import math
import os
import pathlib
import shutil
import sys
import tempfile
import warnings
import zipfile

import openpyxl
import pandas as pd
from openpyxl.comments import Comment
from openpyxl.formatting.formatting import ConditionalFormattingList
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.cell_range import MultiCellRange
from openpyxl.worksheet.datavalidation import DataValidation

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "_scripts"))
import regras_sobressalentes as R  # noqa: E402

C_TIPO, C_FORN, C_PROC = "TIPO DE ENTREGA", "FORNECEDOR", "PROCUREMENT"
C_PRAZO = "PRAZO AUTORIZAÇÃO ITAIPU (15 D.U.)"
C_DT_AUT, C_SIT, C_DIAS = "DATA DA AUTORIZAÇÃO ITAIPU", "SITUAÇÃO DA AUTORIZAÇÃO", "DIAS ÚTEIS DE ATRASO"
C_DT_ENT = "DATA DA ENTREGA"
BLOCO = [C_TIPO, C_FORN, C_PROC, C_PRAZO, C_DT_AUT, C_SIT, C_DIAS, C_DT_ENT]
LARGURAS = {C_TIPO: 20, C_FORN: 18, C_PROC: 18, C_PRAZO: 14, C_DT_AUT: 14, C_SIT: 24, C_DIAS: 10, C_DT_ENT: 14}
CALCULADAS = {C_PRAZO, C_SIT, C_DIAS}

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
# coluna existente -> lista (as colunas novas sao tratadas a parte)
VALIDACOES_EXISTENTES = {
    "STATUS": "lst_status", "INFO. GERAIS": "lst_secao", "CARACT. TECNICAS": "lst_secao",
    "DOCUMENTOS E IMAGENS": "lst_secao", "CONDICOES": "lst_secao", "VALORIZACAO": "lst_secao",
    "APLICACAO - LMR": "lst_secao", "APTO PARA ENTREGA": "lst_simnao", "EQUIPAMENTO ENTREGUE": "lst_simnao",
}

NOTAS = {
    C_TIPO: "FÍSICA E DOCUMENTAL: item faturável (sai na nota fiscal) e entregue fisicamente.\n"
            "DOCUMENTAL: componente explodido — só a ficha; vai dentro do item pai, não sai na NF.\n"
            "TÍTULO: linha de conjunto, sem ficha própria.",
    C_FORN: "Empresa que vendeu o item ao CMI (não o fabricante). Ajuda a cobrar datasheet e a achar o Procurement.",
    C_PROC: "Pessoa do Procurement responsável pelo pedido deste item.",
    C_PRAZO: "CALCULADO — não digitar. DIATRABALHO(data do e-mail; 15; Feriados).",
    C_DT_AUT: "Data em que Itaipu autorizou a entrega (e-mail de autorização ou export de sobressalentes autorizados).",
    C_SIT: "CALCULADO — não digitar.\nAGUARDANDO ITAIPU · ATRASADO ITAIPU · AUTORIZADO NO PRAZO · "
           "AUTORIZADO COM ATRASO · AUTORIZADO (sem data registrada).",
    C_DIAS: "CALCULADO — não digitar. Dias úteis além do prazo de 15 d.u. (até hoje, ou até a data da autorização).",
    C_DT_ENT: "Data da entrega física no almoxarifado de Itaipu. Registra com data o SIM de EQUIPAMENTO ENTREGUE.",
}

CORES_SITUACAO = {  # (fundo, fonte)
    "ATRASADO ITAIPU": ("FFC7CE", "9C0006"),
    "AGUARDANDO ITAIPU": ("FFEB9C", "9C6500"),
    "AUTORIZADO COM ATRASO": ("FCD5B4", "974706"),
    "AUTORIZADO NO PRAZO": ("C6EFCE", "006100"),
    "AUTORIZADO": ("C6EFCE", "006100"),
}
FOLGA_LINHAS = 50          # formulas e validacoes vao alem da ultima linha com dado
FMT_DATA = "dd/mm/yyyy"


# --------------------------------------------------------------------------
# Auxiliares
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


def definir_nome(wb, nome: str, ref: str) -> None:
    if nome in wb.defined_names:
        del wb.defined_names[nome]
    wb.defined_names[nome] = DefinedName(nome, attr_text=ref)


def aba_listas(wb) -> None:
    ws = wb["Listas"] if "Listas" in wb.sheetnames else wb.create_sheet("Listas")
    ws.cell(1, 1, "Vocabulários das listas suspensas do _STATUS_PMIB (layout v2). Para acrescentar um "
                  "nome de Procurement, escreva abaixo da lista e estenda o nome definido lst_procurement.")
    for j, (nome, valores) in enumerate(LISTAS.items(), start=1):
        col = get_column_letter(j)
        ws.cell(3, j, nome).font = Font(bold=True)
        for i, v in enumerate(valores, start=4):
            ws.cell(i, j, v)
        ws.column_dimensions[col].width = 24
        definir_nome(wb, nome, f"Listas!${col}$4:${col}${3 + len(valores)}")


def aba_feriados(wb) -> None:
    if "Feriados" in wb.sheetnames:
        del wb["Feriados"]
    ws = wb.create_sheet("Feriados")
    ws.cell(1, 1, "DATA").font = Font(bold=True)
    ws.cell(1, 2, "FERIADO — os 15 dias úteis de Itaipu pulam estas datas").font = Font(bold=True)
    datas = sorted(R.FERIADOS)
    for i, d in enumerate(datas, start=2):
        ws.cell(i, 1, d).number_format = FMT_DATA
        ws.cell(i, 2, R.FERIADOS[d])
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 44
    definir_nome(wb, "Feriados", f"Feriados!$A$2:$A${len(datas) + 1}")


def _toca(rng: str, colunas: set[int], linha_ini: int) -> bool:
    min_c, _, max_c, max_r = range_boundaries(rng)
    return any(min_c <= c <= max_c for c in colunas) and (max_r or linha_ini) >= linha_ini


def remover_validacoes(ws, colunas: set[int], linha_ini: int) -> None:
    """Tira das validacoes existentes as faixas das colunas que vao ganhar validacao nova."""
    manter = []
    for dv in ws.data_validations.dataValidation:
        sobra = [rng for rng in str(dv.sqref).split() if not _toca(rng, colunas, linha_ini)]
        if sobra:
            dv.sqref = MultiCellRange(" ".join(sobra))
            manter.append(dv)
    ws.data_validations.dataValidation = manter


def remover_formatacao(ws, colunas: set[int], linha_ini: int) -> None:
    """Tira a formatacao condicional das colunas do bloco v2 (para a migracao poder rodar de novo)."""
    nova = ConditionalFormattingList()
    for cf in ws.conditional_formatting:
        if any(_toca(rng, colunas, linha_ini) for rng in str(cf.sqref).split()):
            continue
        for regra in cf.rules:
            nova.add(str(cf.sqref), regra)
    ws.conditional_formatting = nova


def validacao_lista(ws, faixa: str, nome: str, rigida: bool, titulo: str, msg: str) -> None:
    dv = DataValidation(type="list", formula1=f"={nome}", allow_blank=True,
                        errorStyle="stop" if rigida else "warning", showErrorMessage=True,
                        showInputMessage=bool(msg), promptTitle=titulo[:32], prompt=msg[:255])
    dv.add(faixa)
    ws.add_data_validation(dv)


def validacao_data(ws, faixa: str, msg: str) -> None:
    dv = DataValidation(type="date", operator="between", formula1="DATE(2024,1,1)", formula2="DATE(2030,12,31)",
                        allow_blank=True, errorStyle="warning", showErrorMessage=True,
                        showInputMessage=True, promptTitle="Data", prompt=msg[:255])
    dv.add(faixa)
    ws.add_data_validation(dv)


# --------------------------------------------------------------------------
# Inventario do que o openpyxl NAO preserva — medido no proprio .xlsx (zip)
# --------------------------------------------------------------------------
def inventario(caminho: pathlib.Path) -> dict[str, int]:
    """Conta o que existe no arquivo: comentarios em thread (o openpyxl APAGA), anotacoes,
    validacoes padrao e de extensao (x14, o openpyxl APAGA), formatacao condicional, desenhos."""
    with zipfile.ZipFile(caminho) as z:
        nomes = z.namelist()
        ler = lambda prefixo: "".join(z.read(n).decode("utf-8", "ignore") for n in nomes if n.startswith(prefixo))  # noqa: E731
        folhas, thread, notas = ler("xl/worksheets/sheet"), ler("xl/threadedComments/"), ler("xl/comments")
        desenho = ler("xl/drawings/drawing")   # formas, imagens e graficos; contêiner vazio nao conta
        return {
            "comentarios_thread": thread.count("<threadedComment "),
            "anotacoes": notas.count("<comment "),
            "validacoes": folhas.count("<dataValidation "),
            "validacoes_extensao": folhas.count("<x14:dataValidation "),
            "formatacao_condicional": folhas.count("<conditionalFormatting "),
            "desenhos": sum(desenho.count(f"<xdr:{a}") for a in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor")),
        }


# --------------------------------------------------------------------------
# Migracao de um arquivo
# --------------------------------------------------------------------------
class PuladoParaPreservar(Exception):
    """O openpyxl destruiria algo que nao pode ser perdido; o arquivo fica intocado."""


def migrar_planilha(caminho: pathlib.Path, prefill_tipo: dict[str, str], prefill_proc: str | None,
                    folga: int = FOLGA_LINHAS, aceitar_perda_comentarios: bool = False) -> dict:
    resumo = {"arquivo": caminho.name, "colunas_inseridas": 0, "inicio_bloco": "", "aviso": "",
              "tipo_preenchido": 0, "procurement_preenchido": 0}
    antes = inventario(caminho)
    if antes["comentarios_thread"] and not aceitar_perda_comentarios:
        # o openpyxl transforma comentario em thread em anotacao comum: perde autor, data e respostas
        raise PuladoParaPreservar(f"{antes['comentarios_thread']} comentário(s) em thread — migrar pelo Excel "
                                  f"(ver Plano - Reestruturacao do STATUS_PMIB, motor Excel)")
    wb = openpyxl.load_workbook(caminho)
    ws = wb["Lista de Materiais"]
    hdr, mapa = cabecalho(ws)
    ultimo_cab = max(mapa.values())
    col_desc = mapa["DESCRICAO"]
    fim_dados = ultima_linha_com_dado(ws, hdr, col_desc)
    primeira, ultima = hdr + 1, max(fim_dados, hdr + 1) + folga

    # 1. posicao do bloco: logo apos o cabecalho, ou apos anotacoes soltas a direita
    faltam = [c for c in BLOCO if R.normalizar(c) not in mapa]
    if faltam:
        usada = ultima_coluna_usada(ws, hdr)
        inicio = ultimo_cab + 1 if usada <= ultimo_cab else usada + 2
        if usada > ultimo_cab:
            resumo["aviso"] = (f"anotações soltas em {get_column_letter(ultimo_cab + 1)}:{get_column_letter(usada)} — "
                               f"bloco v2 começa em {get_column_letter(inicio)}")
        ref = ws.cell(hdr, ultimo_cab)
        ref_dado = ws.cell(primeira, ultimo_cab)
        for k, nome in enumerate(faltam):
            col = inicio + k
            cel = ws.cell(hdr, col, nome)
            cel.font, cel.border, cel.fill = copy.copy(ref.font), copy.copy(ref.border), copy.copy(ref.fill)
            cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cel.comment = Comment(NOTAS[nome], "Gestão v2", width=300, height=110)
            ws.column_dimensions[get_column_letter(col)].width = LARGURAS[nome]
            for r in range(primeira, ultima + 1):
                c = ws.cell(r, col)
                c.border = copy.copy(ref_dado.border)
                c.font = Font(name=ref_dado.font.name, size=ref_dado.font.sz,
                              color="595959" if nome in CALCULADAS else None, italic=nome in CALCULADAS)
            resumo["colunas_inseridas"] += 1
        resumo["inicio_bloco"] = get_column_letter(inicio)
        hdr, mapa = cabecalho(ws)
        # titulo mesclado acompanha a tabela, se o espaco estiver livre
        fim_bloco = max(mapa.values())
        for m in list(ws.merged_cells.ranges):
            if m.max_row < hdr and m.max_col == ultimo_cab and m.min_col <= 2 and inicio == ultimo_cab + 1:
                livres = all(ws.cell(m.min_row, c).value in (None, "") for c in range(m.max_col + 1, fim_bloco + 1))
                if livres:
                    ws.unmerge_cells(str(m))
                    ws.merge_cells(start_row=m.min_row, start_column=m.min_col, end_row=m.max_row, end_column=fim_bloco)
    else:
        resumo["inicio_bloco"] = get_column_letter(mapa[R.normalizar(C_TIPO)])

    aba_listas(wb)
    aba_feriados(wb)

    L = {R.normalizar(k): get_column_letter(v) for k, v in mapa.items()}
    col = lambda nome: L[R.normalizar(nome)]  # noqa: E731
    E, A, EN = col("DATA DO EMAIL COMUNICANDO ENTREGA"), col("APTO PARA ENTREGA"), col("EQUIPAMENTO ENTREGUE")
    P, DA, S, D = col(C_PRAZO), col(C_DT_AUT), col(C_SIT), col(C_DIAS)

    # 2. formulas (texto em ingles; o Excel mostra DIATRABALHO / DIATRABALHOTOTAL)
    for r in range(primeira, ultima + 1):
        aut = f'OR(ISNUMBER({DA}{r}),UPPER(TRIM({A}{r}))="SIM",UPPER(TRIM({EN}{r}))="SIM")'
        ws[f"{P}{r}"] = f'=IF(ISNUMBER({E}{r}),WORKDAY({E}{r},15,Feriados),"")'
        ws[f"{S}{r}"] = (f'=IF({aut},IF(AND(ISNUMBER({DA}{r}),ISNUMBER({P}{r})),'
                         f'IF({DA}{r}>{P}{r},"AUTORIZADO COM ATRASO","AUTORIZADO NO PRAZO"),"AUTORIZADO"),'
                         f'IF(ISNUMBER({P}{r}),IF(TODAY()>{P}{r},"ATRASADO ITAIPU","AGUARDANDO ITAIPU"),""))')
        ws[f"{D}{r}"] = (f'=IF(NOT(ISNUMBER({P}{r})),"",IF(ISNUMBER({DA}{r}),MAX(0,NETWORKDAYS({P}{r},{DA}{r},Feriados)-1),'
                         f'IF({aut},"",MAX(0,NETWORKDAYS({P}{r},TODAY(),Feriados)-1))))')
        for c in (P, DA, col(C_DT_ENT)):
            ws[f"{c}{r}"].number_format = FMT_DATA
        ws[f"{D}{r}"].number_format = "0"

    # 3. listas suspensas por nome definido (sobrevivem ao openpyxl do SIG-FT)
    alvo = {mapa[k]: v for k, v in VALIDACOES_EXISTENTES.items() if k in mapa}
    novas = {mapa[R.normalizar(C_TIPO)]: "lst_tipo_entrega", mapa[R.normalizar(C_PROC)]: "lst_procurement"}
    datas = {mapa[R.normalizar(C_DT_AUT)]: "Data em que Itaipu autorizou a entrega.",
             mapa[R.normalizar(C_DT_ENT)]: "Data da entrega física no almoxarifado de Itaipu."}
    remover_validacoes(ws, set(alvo) | set(novas) | set(datas), primeira)
    for c, nome in {**alvo, **novas}.items():
        faixa = f"{get_column_letter(c)}{primeira}:{get_column_letter(c)}{ultima}"
        if nome == "lst_tipo_entrega":
            validacao_lista(ws, faixa, nome, True, "Tipo de entrega",
                            "FÍSICA E DOCUMENTAL (sai na NF) · DOCUMENTAL (só ficha) · TÍTULO (conjunto)")
        elif nome == "lst_procurement":
            validacao_lista(ws, faixa, nome, False, "Procurement", "Escolha da lista ou digite um nome novo.")
        else:
            validacao_lista(ws, faixa, nome, False, "", "")
    for c, msg in datas.items():
        validacao_data(ws, f"{get_column_letter(c)}{primeira}:{get_column_letter(c)}{ultima}", msg)

    # 4. formatacao condicional
    remover_formatacao(ws, {mapa[R.normalizar(c)] for c in BLOCO}, primeira)
    for valor, (fundo, fonte) in CORES_SITUACAO.items():
        ws.conditional_formatting.add(f"{S}{primeira}:{S}{ultima}", CellIsRule(
            operator="equal", formula=[f'"{valor}"'], fill=PatternFill("solid", start_color=fundo, end_color=fundo),
            font=Font(color=fonte, bold=valor == "ATRASADO ITAIPU")))
    ws.conditional_formatting.add(f"{D}{primeira}:{D}{ultima}", CellIsRule(
        operator="greaterThan", formula=["0"], font=Font(color="9C0006", bold=True)))
    T = col(C_TIPO)
    ws.conditional_formatting.add(f"{T}{primeira}:{T}{ultima}", CellIsRule(
        operator="equal", formula=['"DOCUMENTAL"'], font=Font(color="767676", italic=True)))

    # 5. pre-preenchimento — so celula vazia, so linha com PMIB valido
    c_pmib, c_tipo, c_proc = mapa["CODIGO PMIB"], mapa[R.normalizar(C_TIPO)], mapa[R.normalizar(C_PROC)]
    for r in range(primeira, fim_dados + 1):
        p = R.normalizar_pmib(ws.cell(r, c_pmib).value)
        if not p:
            continue
        if ws.cell(r, c_tipo).value in (None, "") and prefill_tipo.get(p):
            ws.cell(r, c_tipo, prefill_tipo[p])
            resumo["tipo_preenchido"] += 1
        if ws.cell(r, c_proc).value in (None, "") and prefill_proc:
            ws.cell(r, c_proc, prefill_proc)
            resumo["procurement_preenchido"] += 1

    # 6. cabecalho sempre a vista
    if not ws.freeze_panes:
        ws.freeze_panes = f"A{hdr + 1}"
    definir_nome(wb, "versao_layout_status_pmib", '"v2"')
    wb.calculation.fullCalcOnLoad = True     # o Excel recalcula as formulas ao abrir
    wb.save(caminho)
    resumo["ok"] = True
    return resumo


# --------------------------------------------------------------------------
# Conferencia: a migracao nao pode mudar nenhum dado que ja existia
# --------------------------------------------------------------------------
def conferir(original: pathlib.Path, migrado: pathlib.Path) -> list[str]:
    problemas = []
    a = R.ler_tabela(original, "Lista de Materiais", max_col=80)
    b = R.ler_tabela(migrado, "Lista de Materiais", max_col=80)
    if len(a) != len(b):
        problemas.append(f"linhas com dado mudaram: {len(a)} -> {len(b)}")
    problemas += [f"coluna nova ausente: {c}" for c in (R.normalizar(x) for x in BLOCO) if c not in b.columns]
    # toda celula preenchida do original (valor ou formula) continua igual, no mesmo lugar
    wa = openpyxl.load_workbook(original)["Lista de Materiais"]
    wbk = openpyxl.load_workbook(migrado)
    wm = wbk["Lista de Materiais"]
    def igual(x, y) -> bool:   # float regravado pode mudar na 17a casa — nao e mudanca de dado
        if isinstance(x, float) and isinstance(y, float):
            return math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)
        return x == y
    mudaram = [c.coordinate for row in wa.iter_rows() for c in row
               if c.value not in (None, "") and not igual(wm[c.coordinate].value, c.value)]
    if mudaram:
        problemas.append(f"{len(mudaram)} célula(s) existentes mudaram: {', '.join(mudaram[:5])}")
    # o SIG-FT acha o cabecalho por 'CÓDIGO DO MATERIAL' nas 10 primeiras linhas (pandas)
    if not any(any(str(c).strip().upper() == "CÓDIGO DO MATERIAL" for c in
                   pd.read_excel(migrado, sheet_name="Lista de Materiais", skiprows=i, nrows=1, na_filter=False).columns)
               for i in range(10)):
        problemas.append("SIG-FT não acharia o cabeçalho (CÓDIGO DO MATERIAL)")
    # a validacao precisa sobreviver a um novo save do openpyxl (o que o SIG-FT faz)
    tmp = migrado.with_name(migrado.stem + ".roundtrip.xlsx")
    wbk.save(tmp)
    dvs = [dv.formula1 for dv in openpyxl.load_workbook(tmp)["Lista de Materiais"].data_validations.dataValidation]
    tmp.unlink()
    for nome in ("lst_tipo_entrega", "lst_status"):
        if not any(f and nome in f for f in dvs):
            problemas.append(f"validação {nome} não sobrevive a um save do openpyxl")
    # nada do que existia pode sumir: anotacoes, comentarios em thread, desenhos, formatacao condicional
    a_inv, b_inv = inventario(original), inventario(migrado)
    for k in ("anotacoes", "comentarios_thread", "desenhos"):
        if b_inv[k] < a_inv[k]:
            problemas.append(f"{k}: {a_inv[k]} -> {b_inv[k]}")
    if b_inv["formatacao_condicional"] < a_inv["formatacao_condicional"]:
        problemas.append(f"formatação condicional: {a_inv['formatacao_condicional']} -> {b_inv['formatacao_condicional']}")
    return problemas


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
    ap.add_argument("--aceitar-perda-de-comentarios", action="store_true",
                    help="migra também arquivos com comentário em thread (vira anotação comum: perde autor, data e respostas)")
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
            res = migrar_planilha(alvo, tipo, proc.get(lista), aceitar_perda_comentarios=args.aceitar_perda_de_comentarios)
            res["problemas"] = "; ".join(conferir(referencia, alvo)) or "—"
        except PuladoParaPreservar as e:
            res = {"arquivo": alvo.name, "ok": False, "pulado": True, "erro": f"PULADO (intocado): {e}"}
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
    pulados = int(df.get("pulado", pd.Series(dtype=bool)).fillna(False).sum())
    if pulados:
        print(f"\n{pulados} arquivo(s) PULADOS para não perder comentários em thread — ficaram intocados.")
    print(f"\n{int(df['ok'].fillna(False).sum())} de {len(df)} migrados | TIPO DE ENTREGA pré-preenchido: "
          f"{int(df.get('tipo_preenchido', pd.Series([0])).fillna(0).sum())} | PROCUREMENT: "
          f"{int(df.get('procurement_preenchido', pd.Series([0])).fillna(0).sum())}")
    print("Conferência:", "nenhum dado existente mudou" if ruins.empty else f"{len(ruins)} arquivo(s) com diferença")
    print(f"Relatório: {relatorio}")
    return 0 if df["ok"].fillna(False).all() and ruins.empty else 2


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
Gera o KIT DE TESTE do Gestao PMIB (SIG-FT) — tudo sintetico, sem texto real do Box.

Para a sessao do SIG-FT na nuvem conferir, de ponta a ponta, que o pmib_manager corrigido
faz exatamente o que foi projetado. Saida em _gestao_v2/fixtures/kit_gestao_pmib/:

  status/#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx   layout v2 com os 13 casos da regra (linhas 6-18)
                                                 + 3 comentarios em thread (nao podem sumir)
  status/#ST00=TESTE02&MPB020_STATUS_PMIB.xlsx   layout ANTIGO (APTO PARA ENTREGA): so le, nao grava
  status/testes_autospec/#ST00=TESTE01&...xlsx   ISCA: copia de teste com outros numeros — tem de ser ignorada
  mapeadora_sintetica.xlsx                       aba Acompanhamento no layout v2 (+ abas vazias)
  docmanager_sintetico.xlsx                      export do DocManager com as 3 listas
  esperado.json                                  o resultado certo para hoje = 2026-10-10

O esperado e calculado pela implementacao de referencia (regras_sobressalentes.situacao_autorizacao
e recalcular_situacao) — e os casos foram conferidos a mao (ver CASOS).

Uso:  python _gestao_v2/gerar_kit_teste_sigft.py
"""
from __future__ import annotations

import datetime as dt
import json
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
from xlsx_cirurgico import PlanilhaXlsx  # noqa: E402
from migrar_status_pmib_v2 import recalcular_situacao, cabecalho, inventario  # noqa: E402

HOJE = dt.date(2026, 10, 10)
FIX = AQUI / "fixtures"
KIT = FIX / "kit_gestao_pmib"
F, D, T = "FÍSICA E DOCUMENTAL", "DOCUMENTAL", "TÍTULO"
E1, E2, E3 = dt.date(2026, 9, 15), dt.date(2026, 10, 1), dt.date(2026, 9, 4)

# linha: (TIPO, DATA EMAIL, SITUACAO antes, DIAS antes, ENTREGUE, STATUS, PMIB, o que se espera e por que)
CASOS = {
    6:  (F, E1, None, None, None, None, None, "ATRASADO ITAIPU, 4 dias — prazo 06/10, hoje 10/10"),
    7:  (F, E2, None, None, None, None, None, "AGUARDANDO ITAIPU — prazo 23/10"),
    8:  (F, E1, "AUTORIZADO", 2, None, None, None, "AUTORIZADO, 2 dias — marcação de fato e dias congelados"),
    9:  (F, None, None, None, None, None, None, "em branco — sem e-mail"),
    10: (D, E1, None, None, None, None, None, "N/A — DOCUMENTAL não precisa de autorização"),
    11: (T, E1, None, None, None, None, None, "N/A — TÍTULO não precisa de autorização"),
    12: (None, E1, None, None, None, None, None, "em branco — TIPO vazio não conta"),
    13: (F, E1, None, None, "SIM", None, None, "AUTORIZADO — entregue implica autorizado"),
    14: (F, E1, None, None, None, "DUPLICADO", "4500063671.9003", "em branco — DUPLICADO (repete a ficha da linha 6)"),
    15: (D, None, "AUTORIZADO", None, None, None, None, "AUTORIZADO — marcação de fato vale mesmo em DOCUMENTAL"),
    16: (F, E3, None, None, None, None, None, "ATRASADO ITAIPU — 04/09 + 15 d.u. pula o feriado de 07/09"),
    17: (F, E2, "ATRASADO ITAIPU", 30, None, None, None, "AGUARDANDO ITAIPU, dias em branco — estado calculado é recalculado"),
    18: (D, None, "AGUARDANDO ITAIPU", None, None, None, None, "N/A — estado calculado antigo é corrigido"),
}
COL = {"PMIB": "H", "STATUS": "J", "TIPO": "Q", "EMAIL": "R", "SIT": "S", "DIAS": "T", "ENT": "U"}


def montar_status_v2(destino: pathlib.Path) -> None:
    shutil.copy2(FIX / "status_pmib_v2_sintetico.xlsx", destino)
    p = PlanilhaXlsx(destino)
    L = p.parte_da_aba("Lista de Materiais")
    for r, (tipo, email, sit, dias, ent, status, pmib, _) in CASOS.items():
        for chave, valor in (("TIPO", tipo), ("EMAIL", email), ("SIT", sit), ("DIAS", dias), ("ENT", ent)):
            if valor is not None:
                p.escrever(L, f"{COL[chave]}{r}", valor)
        if status:
            p.escrever(L, f"{COL['STATUS']}{r}", status)
        if pmib:
            p.escrever(L, f"{COL['PMIB']}{r}", pmib)
    p.salvar()


def montar_isca(destino: pathlib.Path) -> None:
    """Mesmo codigo de lista, numeros bem diferentes: se o SIG-FT ler esta, o teste falha."""
    shutil.copy2(FIX / "status_pmib_v2_sintetico.xlsx", destino)
    p = PlanilhaXlsx(destino)
    L = p.parte_da_aba("Lista de Materiais")
    for r in range(6, 23):
        p.escrever(L, f"J{r}", "APROVADO")                 # lida por engano -> SITUAÇÃO NO PMIB = FINALIZADO
        p.escrever(L, f"Q{r}", F)
        p.escrever(L, f"S{r}", "AUTORIZADO")
    p.salvar()


def montar_status_v1(destino: pathlib.Path) -> None:
    shutil.copy2(FIX / "status_pmib_v1_sintetico.xlsx", destino)
    p = PlanilhaXlsx(destino)
    L = p.parte_da_aba("Lista de Materiais")
    p.escrever(L, "Q5", E1); p.escrever(L, "R5", "SIM")                 # apto, nao entregue -> conta
    p.escrever(L, "Q6", E1); p.escrever(L, "R6", "SIM"); p.escrever(L, "S6", "SIM")   # entregue -> nao conta
    p.escrever(L, "Q7", E1)                                             # sem TIPO no v1: nao conta atraso
    p.salvar()


CAB_MAPEADORA = [
    "N° DOCUMENTO ITAIPU", "N° DOCUMENTO CMI", "ÚLTIMA REVISÃO EMITIDA", "STATUS DA REVISÃO", "DATA DE ATUALIZAÇÃO",
    "STATUS REAL", "REVISÃO EM USO", "DESCRIÇÃO", "ESPECIFICAÇÃO TÉCNICA", "CAPÍTULO", "RESPONSÁVEL", "PROCUREMENT",
    "ELABORADOR DO DOCUMENTO", "ORIGEM FORNECEDOR", "ENTREGA", "OBSERVAÇÃO", "EVENTOS DE PAGAMENTOS\nRELACIONADOS",
    "SITUAÇÃO NO PMIB", "LINK DA PLANILHA", 'CAMPO "CÓDIGO DO PROJETO PARA O PMIB"']   # mapeadora = cadastro (05/10)
LISTAS = {  # codigo: (doc CMI, ultima revisao emitida, revisao em uso ANTES, tracking id)
    "#ST00=TESTE01&MPB020": ("TESTE-CMI-01", "1", "0", "TRK-001"),
    "#ST00=TESTE02&MPB020": ("TESTE-CMI-02", "0B", "0B", "TRK-002"),
    "#ST00=TESTE03&MPB020": ("TESTE-CMI-03", "0", "0", "TRK-003"),
}


def montar_mapeadora(destino: pathlib.Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Acompanhamento Sobressalente"
    ws["A1"], ws["Q1"], ws["R1"] = "GERAL", "FINANCEIRO", "PMIB"
    ws.merge_cells("A1:P1")
    ws.merge_cells(f"R1:{openpyxl.utils.get_column_letter(len(CAB_MAPEADORA))}1")
    for c, nome in enumerate(CAB_MAPEADORA, start=1):
        ws.cell(2, c, nome)
    col = {n: i + 1 for i, n in enumerate(CAB_MAPEADORA)}
    for r, (cod, (cmi, ult, emuso, _)) in enumerate(LISTAS.items(), start=3):
        ws.cell(r, col["N° DOCUMENTO ITAIPU"], cod)
        ws.cell(r, col["N° DOCUMENTO CMI"], cmi)
        ws.cell(r, col["ÚLTIMA REVISÃO EMITIDA"], ult)
        ws.cell(r, col["REVISÃO EM USO"], emuso)
        ws.cell(r, col["DESCRIÇÃO"], f"TEXTO DE TESTE - LISTA DE SOBRESSALENTES {r - 2}")
        ws.cell(r, col["SITUAÇÃO NO PMIB"], "VALOR VELHO")       # tem de ser substituido pela cascata
        ws.cell(r, col['CAMPO "CÓDIGO DO PROJETO PARA O PMIB"'], f'=I{r} & " / " & J{r} & " | " & A{r} & " / " & B{r}')
    d = wb.create_sheet("Dropbox")
    d["C1"] = "STATUS DA ATIVIDADE"
    lp = wb.create_sheet("Lista de preços Follow-up")
    for c, n in enumerate(["N° DOCUMENTO ITAIPU", "N° DOCUMENTO CMI", "ÚLTIMA REVISÃO EMITIDA", "STATUS DA REVISÃO",
                           "DATA DE ATUALIZAÇÃO", "DESCRIÇÃO", "ESPECIFICAÇÃO TÉCNICA", "CAPÍTULO",
                           "LISTA DE SOBRESSALENTES", "ALERTA RDS-PP", "AÇÃO", "OBSERVAÇÕES"], start=1):
        lp.cell(1, c, n)
    at = wb.create_sheet("Atividades")
    for c, n in enumerate(["NV", "CÓDIGO ITAIPU", "DESCRIÇÃO", "ATIVIDADES", "CONCLUÍDAS", "TRAVADAS",
                           "DATA PREVISTA DE INÍCIO", "DATA DE INÍCIO", "PREVISÃO DE TÉRMINO", "DATA DE TÉRMINO",
                           "STATUS", "ALTERAÇÃO DO STATUS", "COM QUEM ESTÁ", "DETALHE", "CRITICIDADE", "CONCLUÍDA"], start=1):
        at.cell(1, c, n)
    wb.save(destino)


def montar_docmanager(destino: pathlib.Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    cab = ["No. do Documento", "Tracking ID", "Current", "Título", "Controle do Emissor", "Revisão", "Status",
           "Data de Alteração", "Especialidade", "Subespecialidade"]
    ws.append(cab)
    for i, (cod, (cmi, ult, _, trk)) in enumerate(LISTAS.items(), start=1):
        ws.append([cod, trk, "True", f"TEXTO DE TESTE - LISTA DE SOBRESSALENTES {i}", cmi, ult, "Aprovado",
                   "01/10/2026", "TEXTO DE TESTE", "TEXTO DE TESTE"])
    wb.save(destino)


# --------------------------------------------------------------------------
# Esperado (implementacao de referencia)
# --------------------------------------------------------------------------
def contar(caminho: pathlib.Path) -> dict:
    """O que o Gestao PMIB deve gravar na mapeadora para esta lista (arquivo ja recalculado)."""
    ws = openpyxl.load_workbook(caminho)["Lista de Materiais"]
    hdr, mapa = cabecalho(ws)
    c = lambda n: mapa.get(R.normalizar(n))  # noqa: E731
    vistos, fis, apto, agu, atr, maior, entregues = set(), 0, 0, 0, 0, 0, 0
    v2 = c("SITUAÇÃO DA AUTORIZAÇÃO") is not None
    for r in range(hdr + 1, ws.max_row + 1):
        pmib = R.normalizar_pmib(ws.cell(r, c("CÓDIGO PMIB")).value)
        if not pmib or R.normalizar(ws.cell(r, c("STATUS")).value) == "DUPLICADO" or pmib in vistos:
            continue
        vistos.add(pmib)
        ent = R.normalizar(ws.cell(r, c("EQUIPAMENTO ENTREGUE")).value) == "SIM"
        entregues += ent
        if v2:
            tipo = R.TIPO_CANONICO.get(R.normalizar(ws.cell(r, c("TIPO DE ENTREGA")).value))
            sit = R.normalizar(ws.cell(r, c("SITUAÇÃO DA AUTORIZAÇÃO")).value)
            dias = R._inteiro(ws.cell(r, c("DIAS DE ATRASO")).value)
            fis += tipo == F
            apto += sit == "AUTORIZADO" and not ent and tipo not in (D, T)
            agu += sit == "AGUARDANDO ITAIPU"
            if sit == "ATRASADO ITAIPU":
                atr += 1
                maior = max(maior, dias or 0)
        else:                                                   # layout antigo: so o APTO conta
            apto += R.normalizar(ws.cell(r, c("APTO PARA ENTREGA")).value) == "SIM" and not ent
    return {"FICHAS EXISTENTES": len(vistos), "FICHAS DE ENTREGA FÍSICA": fis, "APTO PARA ENTREGA": apto,
            "AGUARDANDO AUTORIZAÇÃO ITAIPU": agu, "ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU": atr,
            "MAIOR ATRASO ITAIPU (DIAS)": maior, "EQUIPAMENTOS ENTREGUES": entregues}


def main() -> None:
    if KIT.exists():
        shutil.rmtree(KIT)
    (KIT / "status" / "testes_autospec").mkdir(parents=True)
    t1 = KIT / "status" / "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"
    t2 = KIT / "status" / "#ST00=TESTE02&MPB020_STATUS_PMIB.xlsx"
    montar_status_v2(t1)
    montar_status_v1(t2)
    montar_isca(KIT / "status" / "testes_autospec" / t1.name)
    montar_mapeadora(KIT / "mapeadora_sintetica.xlsx")
    montar_docmanager(KIT / "docmanager_sintetico.xlsx")

    # referencia: recalcula uma COPIA do TESTE01 com HOJE fixo e le o resultado
    with tempfile.TemporaryDirectory() as tmp:
        copia = pathlib.Path(tmp) / t1.name
        shutil.copy2(t1, copia)
        recalcular_situacao(copia, HOJE)
        ws = openpyxl.load_workbook(copia)["Lista de Materiais"]
        linhas = {str(r): {"situacao": ws[f"S{r}"].value or "", "dias": ws[f"T{r}"].value, "por_que": CASOS[r][7]}
                  for r in CASOS}
        linhas.update({str(r): {"situacao": ws[f"S{r}"].value or "", "dias": ws[f"T{r}"].value,
                                "por_que": "em branco — sem tipo, sem e-mail"} for r in range(19, 23)})
        partes_intocadas = [n for n in PlanilhaXlsx(t1)._bytes if n.startswith(("xl/threadedComments/", "xl/persons/", "xl/comments"))]
    esperado = {
        "hoje": HOJE.isoformat(),
        "regra": "só FÍSICA E DOCUMENTAL precisa de autorização; prazo = e-mail + 15 dias úteis (np.busday_offset, "
                 "roll='backward', FERIADOS); dias de atraso = dias corridos além do prazo",
        "status_pmib": {
            "#ST00=TESTE01&MPB020": {
                "colunas": {"situacao": "S (SITUAÇÃO DA AUTORIZAÇÃO)", "dias": "T (DIAS DE ATRASO)"},
                "linhas": linhas,
                "inventario_igual": inventario(t1),
                "partes_byte_a_byte_iguais": partes_intocadas,
                "nome_definido_novo": "sigft_calculado_em (data do cálculo)",
            },
            "#ST00=TESTE02&MPB020": {"arquivo_inalterado": True, "log": "arquivo sem layout v2 (sem SITUAÇÃO DA AUTORIZAÇÃO)"},
            "testes_autospec/#ST00=TESTE01&MPB020": {"arquivo_inalterado": True, "ignorado": True},
        },
        "mapeadora": {   # so cadastro: o SIG-FT nao grava contagem (decisao do Luan, 05/10/2026)
            "#ST00=TESTE01&MPB020": {"SITUAÇÃO NO PMIB": "FICHAS CRIADAS", "REVISÃO EM USO": "1",
                                     "LINK DA PLANILHA": "Abrir Box"},
            "#ST00=TESTE02&MPB020": {"SITUAÇÃO NO PMIB": "FICHAS CRIADAS",
                                     "REVISÃO EM USO": "0B (sem linha de revisão: não mexer)",
                                     "LINK DA PLANILHA": "Abrir Box"},
            "#ST00=TESTE03&MPB020": {"SITUAÇÃO NO PMIB": "INICIAR", "REVISÃO EM USO": "0 (sem arquivo: não mexer)",
                                     "LINK DA PLANILHA": ""},
        },
        "mapeadora_cabecalho_inalterado": CAB_MAPEADORA,
        "isca": "a isca em testes_autospec tem todas as fichas APROVADO: se for lida, a SITUAÇÃO NO PMIB de TESTE01 "
                "sai FINALIZADO e o link aponta para testes_autospec",
    }
    (KIT / "esperado.json").write_text(json.dumps(esperado, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(esperado["mapeadora"], ensure_ascii=False, indent=1))
    for r, v in linhas.items():
        print(r, v["situacao"], v["dias"], "—", v["por_que"])


if __name__ == "__main__":
    main()

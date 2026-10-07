# -*- coding: utf-8 -*-
"""
Monta o Power BI v2 como PROJETO do Power BI (.pbip): um modelo semantico em TMDL e dois
relatorios (Interno e Itaipu) no formato PBIR, a partir das consultas (*.pq) e das medidas
(05 - Medidas.dax) deste pacote — uma fonte so: mudou a consulta, roda de novo.

    python montar_pbip.py                       # PastaPMIB vazio: cada maquina acha a pasta do Box sozinha
    python montar_pbip.py --pasta "C:\\...\\SOBRESSALENTES - PMIB" --saida DIR

Abrir: Power BI Desktop > Arquivo > Abrir > "Sobressalentes v2 - Interno.pbip" (ou "- Itaipu").
Primeira vez: Pagina Inicial > Atualizar. Para um arquivo unico: Arquivo > Salvar como > .pbix.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
import uuid

import relatorios_v2 as R

AQUI = pathlib.Path(__file__).resolve().parent
NOME = "Sobressalentes v2"

TABELAS = ["Calendario", "PrecosAconex", "Itens", "Listas", "Atividades", "Eventos", "ListaEvento"]
S, I, D, DT, B, P = "string", "int64", "double", "dateTime", "boolean", "pct"
ESQUEMA = {   # coluna, tipo — a consulta e "fechada" com SelectColumns + TransformColumnTypes nestes tipos
    "Calendario": [("Data", DT), ("Ano", I), ("Mes", I), ("Mes Ano", S), ("Inicio do Mes", DT), ("Inicio da Semana", DT)],
    "PrecosAconex": [("Lista de Precos", S), ("Documento CMI", S), ("Revisao", S), ("Status Aconex", S), ("Data Aconex", DT),
                     ("Lista", S), ("Alerta RDS-PP", S), ("Acao", S), ("Observacoes", S), ("Geracao", S), ("Situacao Preco", S)],
    "Itens": [(c, S) for c in ("Lista", "Area", "Sistema", "Caminho", "Revisao no Arquivo", "ITEM", "QTD.", "UNID.", "DESCRICAO",
                               "CODIGO DO MATERIAL", "CODIGO CMI", "MARCA/MODELO", "FORNECEDOR", "PROCUREMENT", "PDM USADO",
                               "INFO. GERAIS", "CARACT. TECNICAS", "DOCUMENTOS E IMAGENS", "CONDICOES", "VALORIZACAO",
                               "APLICACAO - LMR", "OBSERVACOES", "PMIB", "Status", "PMIB Original", "Chave Ficha", "Etapa Cliente",
                               "Com Quem", "Codigo GE Preco", "Lista de Precos", "Tipo de Entrega", "Origem do Tipo",
                               "Situacao Autorizacao", "Situacao LMR", "Pendencia")]
             + [("Data Email", DT), ("Data Referencia", DT)]
             + [(c, B) for c in ("E Ficha", "Duplicada de Outro Sistema", "Emitida", "Info Gerais OK", "Caract Tecnicas OK",
                                 "Documentos OK", "Condicoes OK", "Valorizacao OK", "LMR OK", "Info Fornecedor OK", "Entregue",
                                 "Ficha Entregue", "Apto")]
             + [("Etapa", S), ("Ordem Etapa", I), ("Ordem Etapa Cliente", I), ("Dias de Atraso", I), ("Dias desde Email", I)]
             + [("Valor Unitario USD", D), ("Qtd", D), ("Valor Linha USD", D)],
    "Listas": [(c, S) for c in ("Lista", "Documento CMI", "Ultima Revisao", "Status da Revisao", "Status Real",
                                "Revisao em Uso (mapeadora)", "Descricao", "Especificacao Tecnica", "Capitulo", "Responsavel",
                                "Procurement (lista)", "Elaborador", "Origem Fornecedor", "Entrega (texto)", "Observacao", "Eventos",
                                "Situacao PMIB (mapeadora)", "Origem Cadastro", "Area (pasta)", "Nome", "Area Final",
                                "Revisao no Arquivo", "Revisao em Uso")]
              + [("Tem Responsavel", B), ("Revisao Desatualizada", B)],
    "Atividades": [(c, S) for c in ("Lista", "Frente", "Atividade", "Status Atividade", "Com Quem Esta", "Detalhe", "Situacao")]
                  + [(c, DT) for c in ("Inicio Previsto", "Inicio Real", "Termino Previsto", "Termino Real", "Alteracao do Status")]
                  + [("Criticidade", I), ("Concluida", B)],
    "Eventos": [("Evento", S), ("Grupo", S), ("Tipo Evento", S), ("Percentual", P), ("Descricao Evento", S), ("Mes de Referencia", S)],
    "ListaEvento": [("Lista", S), ("Evento", S)],
}
TIPO_M = {S: "type text", I: "Int64.Type", D: "type number", DT: "type date", B: "type logical", P: "Percentage.Type"}
TIPO_TMDL = {S: "string", I: "int64", D: "double", DT: "dateTime", B: "boolean", P: "double"}
FORMATO = {DT: "dd/mm/yyyy", D: "#,##0.00", P: "0%", I: "0"}
ORDENAR_POR = {("Itens", "Etapa"): "Ordem Etapa", ("Itens", "Etapa Cliente"): "Ordem Etapa Cliente",
               ("Calendario", "Mes Ano"): "Inicio do Mes"}
OCULTAS = {("Itens", "Ordem Etapa"), ("Itens", "Ordem Etapa Cliente"), ("Itens", "Chave Ficha"), ("Itens", "Caminho")}
TIPO_EXPRESSAO = {"PastaPMIBEfetiva": "Text", "DataReferencia": "Date"}
RELACOES = [("Itens", "Lista", "Listas", "Lista", False), ("Atividades", "Lista", "Listas", "Lista", False),
            ("PrecosAconex", "Lista", "Listas", "Lista", False), ("ListaEvento", "Lista", "Listas", "Lista", True),
            ("ListaEvento", "Evento", "Eventos", "Evento", False), ("Itens", "Data Email", "Calendario", "Data", False)]


# --------------------------------------------------------------------------
# Leitura das consultas e medidas do pacote
# --------------------------------------------------------------------------
def ler_consultas() -> dict[str, str]:
    consultas: dict[str, str] = {}
    for arq in sorted(AQUI.glob("0*.pq")):
        atual, corpo, cabecalho = None, [], False
        for ln in arq.read_text(encoding="utf-8").splitlines() + ["// ===="]:
            m = re.match(r"^// CONSULTA: (\w+)", ln)
            if m:
                atual, corpo, cabecalho = m.group(1), [], True
                continue
            if atual is None:
                continue
            if cabecalho and ln.startswith("//"):
                continue
            cabecalho = False
            if ln.startswith("// ====") or ln.startswith("// ----"):
                while corpo and (not corpo[-1].strip() or corpo[-1].startswith("//")):
                    corpo.pop()
                consultas[atual] = "\n".join(corpo)
                atual = None
                continue
            corpo.append(ln)
    return consultas


def ler_medidas() -> list[dict]:
    medidas, pasta = [], "Geral"
    texto = (AQUI / "05 - Medidas.dax").read_text(encoding="utf-8")
    texto = texto.split("DEFINE", 1)[1].split("EVALUATE", 1)[0]
    for ln in texto.splitlines():
        m = re.match(r"^\s*// -+ (.+?) -+\s*$", ln)
        if m:
            pasta = m.group(1).strip()
            continue
        m = re.match(r"^\s*MEASURE\s+(\w+)\[(.+?)\]\s*=\s*(.*)$", ln)
        if m:
            medidas.append({"tabela": m.group(1), "nome": m.group(2), "expr": [m.group(3)] if m.group(3).strip() else [],
                            "pasta": pasta})
        elif medidas:
            medidas[-1]["expr"].append(ln)
    for md in medidas:
        linhas = [l.rstrip() for l in md["expr"] if l.strip()]
        while linhas and linhas[-1].lstrip().startswith("//"):
            linhas.pop()
        base = min((len(l) - len(l.lstrip()) for l in linhas), default=0)
        md["expr"] = [l[base:] for l in linhas]
        n = md["nome"]
        md["formato"] = ("0%" if n.startswith("%") or n.startswith("Taxa") else "#,##0" if "USD" in n
                         else None if n in ("Atualizado em", "Rótulo Atraso Itaipu") or "(texto)" in n else "#,##0")
    return medidas


# --------------------------------------------------------------------------
# TMDL
# --------------------------------------------------------------------------
def nome(n: str) -> str:
    return n if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n) else "'" + n.replace("'", "''") + "'"


def tag() -> str:
    return str(uuid.uuid4())


def recuo(texto: str, nivel: int) -> str:
    return "\n".join("\t" * nivel + l for l in texto.splitlines() if l.strip())


def m_texto(t: str) -> str:
    """Literal de texto do Power Query: aspas dobradas, barra invertida literal."""
    return '"' + t.replace('"', '""') + '"'


def m_da_tabela(m: str, colunas: list[tuple[str, str]]) -> str:
    sel = ", ".join(m_texto(c) for c, _ in colunas)
    tipos = ", ".join("{%s, %s}" % (m_texto(c), TIPO_M[t]) for c, t in colunas)
    corpo = "\n".join("        " + l for l in m.splitlines() if l.strip())
    return (f"let\n    Consulta =\n{corpo},\n"
            f"    Colunas = Table.SelectColumns(Consulta, {{{sel}}}, MissingField.UseNull),\n"
            f"    Tipada = Table.TransformColumnTypes(Colunas, {{{tipos}}})\nin\n    Tipada")


def escrever_modelo(raiz: pathlib.Path, consultas: dict[str, str], medidas: list[dict], pasta_pmib: str) -> None:
    d = raiz / "definition"
    (d / "tables").mkdir(parents=True)
    (raiz / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}}, indent=2), encoding="utf-8")
    (raiz / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NOME}, "config": {"version": "2.0", "logicalId": tag()}},
        indent=2), encoding="utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n", encoding="utf-8")
    ordem = [n for n in consultas]
    modelo = ["model Model", "\tculture: pt-BR", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
              "\tsourceQueryCulture: pt-BR", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull",
              "\t\tfastCombine", "",
              "annotation __PBI_TimeIntelligenceEnabled = 0", "",
              f"annotation PBI_QueryOrder = {json.dumps(ordem, ensure_ascii=False)}", "",
              'annotation PBI_ProTooling = ["DevMode"]', ""]
    for i, g in enumerate(("Parametros", "Funcoes", "Apoio")):
        modelo += [f"queryGroup {g}", "", f"	annotation PBI_QueryGroupOrder = {i}", ""]
    modelo += [f"ref table {nome(t)}" for t in TABELAS]
    (d / "model.tmdl").write_text("\n".join(modelo) + "\n", encoding="utf-8")

    exp = []
    for n, m in consultas.items():
        if n in TABELAS:
            continue
        if n == "PastaPMIB":
            valor = m_texto(pasta_pmib)
            exp += [f'expression PastaPMIB = {valor} meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=false]',
                    f"\tlineageTag: {tag()}", "\tqueryGroup: Parametros", "", "\tannotation PBI_ResultType = Text", ""]
            continue
        tipo = "Function" if m.lstrip().startswith("(") else TIPO_EXPRESSAO.get(n, "Table")
        exp += [f"expression {nome(n)} =", recuo(m, 2), f"\tlineageTag: {tag()}",
                f"\tqueryGroup: {'Funcoes' if tipo == 'Function' else 'Apoio'}", "",
                f"\tannotation PBI_ResultType = {tipo}", ""]
    (d / "expressions.tmdl").write_text("\n".join(exp) + "\n", encoding="utf-8")

    for t in TABELAS:
        linhas = [f"table {nome(t)}", f"\tlineageTag: {tag()}"]
        if t == "Calendario":
            linhas.append("\tdataCategory: Time")
        linhas.append("")
        for md in (x for x in medidas if x["tabela"] == t):
            linhas += [f"\tmeasure {nome(md['nome'])} =", "\n".join("\t\t\t" + l for l in md["expr"])]
            if md["formato"]:
                linhas.append(f"\t\tformatString: {md['formato']}")
            if md.get("oculta"):
                linhas.append("\t\tisHidden")
            linhas += [f"\t\tdisplayFolder: {md['pasta']}", f"\t\tlineageTag: {tag()}", ""]
        for c, tipo in ESQUEMA[t]:
            linhas += [f"\tcolumn {nome(c)}", f"\t\tdataType: {TIPO_TMDL[tipo]}"]
            if tipo in FORMATO:
                linhas.append(f"\t\tformatString: {FORMATO[tipo]}")
            if t == "Calendario" and c == "Data":
                linhas.append("\t\tisKey")
            if (t, c) in ORDENAR_POR:
                linhas.append(f"\t\tsortByColumn: {nome(ORDENAR_POR[(t, c)])}")
            if (t, c) in OCULTAS:
                linhas.append("\t\tisHidden")
            linhas += [f"\t\tlineageTag: {tag()}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {c}", "",
                       "\t\tannotation SummarizationSetBy = User", ""]
        linhas += [f"\tpartition {nome(t)} = m", "\t\tmode: import", "\t\tsource =",
                   recuo(m_da_tabela(consultas[t], ESQUEMA[t]), 4), "", "\tannotation PBI_ResultType = Table", ""]
        (d / "tables" / f"{t}.tmdl").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    rel = []
    for de_t, de_c, para_t, para_c, ambos in RELACOES:
        rel += [f"relationship {tag()}"]
        if ambos:
            rel.append("\tcrossFilteringBehavior: bothDirections")
        rel += [f"\tfromColumn: {nome(de_t)}.{nome(de_c)}", f"\ttoColumn: {nome(para_t)}.{nome(para_c)}", ""]
    (d / "relationships.tmdl").write_text("\n".join(rel) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Relatorios (PBIR) — o desenho fica em relatorios_v2.py; tema e logotipos em recursos/
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", default="", help="valor do parâmetro PastaPMIB (vazio = cada máquina acha a sua)")
    ap.add_argument("--saida", type=pathlib.Path, default=AQUI / "pbip")
    args = ap.parse_args()
    if args.saida.exists():
        shutil.rmtree(args.saida)
    args.saida.mkdir(parents=True)
    consultas, medidas = ler_consultas(), ler_medidas()
    faltam = [t for t in TABELAS if t not in consultas]
    if faltam:
        raise SystemExit(f"consultas não encontradas nos .pq: {faltam}")
    relatorios = (("Interno", R.relatorio_interno()), ("Itaipu", R.relatorio_itaipu()))
    base = {(m["tabela"], m["nome"]): m for m in medidas}
    for (t, n), copia in sorted(R.CARTOES.items()):      # medidas dos cartoes: vazio vira 0
        medidas.append({"tabela": t, "nome": copia, "expr": [f"COALESCE ( [{n}], 0 )"], "pasta": "Cartões",
                        "formato": base[(t, n)]["formato"] or "#,##0", "oculta": True})
    escrever_modelo(args.saida / f"{NOME}.SemanticModel", consultas, medidas, args.pasta)
    total = 0
    for sufixo, paginas in relatorios:
        nome_rel = f"{NOME} - {sufixo}"
        R.escrever_relatorio(args.saida / f"{nome_rel}.Report", paginas, nome_rel, NOME)
        (args.saida / f"{nome_rel}.pbip").write_text(json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0", "artifacts": [{"report": {"path": f"{nome_rel}.Report"}}],
            "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
        total += sum(len(p.visuais) for p in paginas)
    print(f"OK: {args.saida} — {len(consultas)} consultas, {len(medidas)} medidas, {total} visuais")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
Monta o Power BI v2 como PROJETO do Power BI (.pbip): um modelo semantico em TMDL e dois
relatorios (Interno e Itaipu) no formato PBIR, a partir das consultas (*.pq) e das medidas
(05 - Medidas.dax) deste pacote — uma fonte so: mudou a consulta, roda de novo.

    python montar_pbip.py                       # parametro PastaPMIB = caminho do Box no trabalho
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
import zipfile

AQUI = pathlib.Path(__file__).resolve().parent
NOME = "Sobressalentes v2"
PASTA_TRABALHO = r"C:\Users\560083605\Box\CMI - Consórcio Itaipu\11 - Ger. Engenharia\15 - PDM\SOBRESSALENTES - PMIB"
PBIX_ANTIGO = "Sobressalentes - Dashboard.pbix"           # de onde vem o tema e os logotipos

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
             + [("Ordem Etapa", I), ("Dias de Atraso", I), ("Dias desde Email", I)]
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
                         else None if n in ("Atualizado em", "Rótulo Atraso Itaipu") else "0")
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
            exp += [f'expression PastaPMIB = {valor} meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                    f"\tlineageTag: {tag()}", "\tqueryGroup: Parametros", "", "\tannotation PBI_ResultType = Text", ""]
            continue
        tipo = "Function" if m.lstrip().startswith("(") else ("Table" if n.startswith("Precos") else "Date")
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
            linhas += [f"\t\tdisplayFolder: {md['pasta']}", f"\t\tlineageTag: {tag()}", ""]
        for c, tipo in ESQUEMA[t]:
            linhas += [f"\tcolumn {nome(c)}", f"\t\tdataType: {TIPO_TMDL[tipo]}"]
            if tipo in FORMATO:
                linhas.append(f"\t\tformatString: {FORMATO[tipo]}")
            if t == "Calendario" and c == "Data":
                linhas.append("\t\tisKey")
            if t == "Calendario" and c == "Mes Ano":
                linhas.append("\t\tsortByColumn: 'Inicio do Mes'")
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
# Relatorio (PBIR)
# --------------------------------------------------------------------------
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
VC = f"{SCH}/visualContainer/2.12.0/schema.json"
COR = {"azul": "#2a78d6", "laranja": "#eb6834", "verde": "#1baf7a", "amarelo": "#eda100", "vermelho": "#d03b3b",
       "cinza": "#898781", "titulo": "#0e1a77"}


def lit(v) -> dict:
    if isinstance(v, bool):
        v = "true" if v else "false"
    elif isinstance(v, (int, float)):
        v = f"{v}D"
    else:
        v = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": v}}}


def cor(hexa: str) -> dict:
    return {"solid": {"color": lit(hexa)}}


class Campo:
    def __init__(self, tabela: str, prop: str, medida: bool = False, rotulo: str | None = None):
        self.t, self.p, self.m, self.rotulo = tabela, prop, medida, rotulo

    def expr(self) -> dict:
        k = "Measure" if self.m else "Column"
        return {k: {"Expression": {"SourceRef": {"Entity": self.t}}, "Property": self.p}}

    def proj(self, ativo: bool = False) -> dict:
        p = {"field": self.expr(), "queryRef": f"{self.t}.{self.p}", "nativeQueryRef": self.rotulo or self.p}
        if self.rotulo:
            p["displayName"] = self.rotulo
        if ativo:
            p["active"] = True
        return p


def M(p, rotulo=None):  # medida de Itens (a maioria)
    return Campo("Itens", p, True, rotulo)


class Pagina:
    def __init__(self, nome_exibicao: str):
        self.id = uuid.uuid4().hex[:20]
        self.nome = nome_exibicao
        self.visuais: list[dict] = []

    def _add(self, tipo: str, x, y, w, h, query=None, objetos=None, titulo=None, filtros=None, extra=None):
        z = (len(self.visuais) + 1) * 1000
        v = {"visualType": tipo}
        if query:
            v["query"] = query
        if objetos:
            v["objects"] = objetos
        if titulo is not None:
            v["visualContainerObjects"] = {"title": [{"properties": {"show": lit(True), "text": lit(titulo),
                                                                     "fontColor": cor(COR["titulo"]), "bold": lit(True)}}]}
        v["drillFilterOtherVisuals"] = True
        nm = uuid.uuid4().hex[:20]
        cont = {"$schema": VC, "name": nm,
                "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": v}
        if filtros:
            cont["filterConfig"] = {"filters": filtros}
        if extra:
            cont.update(extra)
        self.visuais.append(cont)

    def texto(self, x, y, w, h, linhas: list[tuple[str, str]]):
        par = [{"textRuns": [{"value": t, "textStyle": {"fontWeight": "bold" if i == 0 else "normal",
                                                          "fontSize": tam, "color": COR["titulo"]}}]}
               for i, (t, tam) in enumerate(linhas)]
        self._add("textbox", x, y, w, h, objetos={"general": [{"properties": {"paragraphs": par}}]})

    def logo(self, x, y, w, h, item: str):
        self._add("image", x, y, w, h, objetos={"general": [{"properties": {"imageUrl": {"expr": {"ResourcePackageItem": {
            "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": item}}}}}]})

    def cartao(self, x, y, w, h, campo: Campo, cor_valor: str = COR["titulo"], tamanho: int = 24):
        self._add("card", x, y, w, h, query={"queryState": {"Values": {"projections": [campo.proj()]}}},
                  objetos={"labels": [{"properties": {"color": cor(cor_valor), "fontSize": lit(tamanho),
                                                      "labelDisplayUnits": lit(1)}}],
                           "categoryLabels": [{"properties": {"show": lit(True), "fontSize": lit(9)}}]})

    def barras(self, x, y, w, h, categoria: Campo, valores: list[Campo], titulo: str, serie: Campo | None = None,
               tipo: str = "clusteredBarChart", filtros=None, ordenar: Campo | None = None):
        qs = {"Category": {"projections": [categoria.proj(ativo=True)]}, "Y": {"projections": [v.proj() for v in valores]}}
        if serie:
            qs["Series"] = {"projections": [serie.proj()]}
        q = {"queryState": qs}
        if ordenar:
            q["sortDefinition"] = {"sort": [{"field": ordenar.expr(), "direction": "Descending"}]}
        self._add(tipo, x, y, w, h, query=q, titulo=titulo, filtros=filtros,
                  objetos={"labels": [{"properties": {"show": lit(True)}}]})

    def tabela(self, x, y, w, h, campos: list[Campo], titulo: str, filtros=None, ordenar: Campo | None = None,
               crescente: bool = False):
        q = {"queryState": {"Values": {"projections": [c.proj() for c in campos]}}}
        if ordenar:
            q["sortDefinition"] = {"sort": [{"field": ordenar.expr(), "direction": "Ascending" if crescente else "Descending"}]}
        self._add("tableEx", x, y, w, h, query=q, titulo=titulo, filtros=filtros,
                  objetos={"columnHeaders": [{"properties": {"bold": lit(True), "wordWrap": lit(True)}}],
                           "total": [{"properties": {"totals": lit(False)}}]})

    def segmentacao(self, x, y, w, h, campo: Campo, titulo: str):
        self._add("slicer", x, y, w, h, query={"queryState": {"Values": {"projections": [campo.proj(ativo=True)]}}},
                  objetos={"data": [{"properties": {"mode": lit("Dropdown")}}],
                           "header": [{"properties": {"show": lit(True), "text": lit(titulo), "bold": lit(True),
                                                      "fontColor": cor(COR["titulo"])}}]})


def filtro(campo: Campo, valores: list[str], negar: bool = False) -> dict:
    cond = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": campo.p}}],
                   "Values": [[{"Literal": {"Value": "'" + v.replace("'", "''") + "'"}}] for v in valores]}}
    if negar:
        cond = {"Not": {"Expression": cond}}
    return {"name": uuid.uuid4().hex[:20], "field": campo.expr(), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "f", "Entity": campo.t, "Type": 0}], "Where": [{"Condition": cond}]}}


def cabecalho(pg: Pagina, titulo: str, subtitulo: str, logos: dict):
    pg.logo(10, 8, 150, 56, logos["ib"])
    pg.texto(170, 6, 760, 60, [(titulo, "14pt"), (subtitulo, "9pt")])
    pg.cartao(940, 12, 200, 50, M("Atualizado em", "Atualização"), COR["cinza"], tamanho=11)
    pg.logo(1150, 8, 120, 56, logos["cmi"])


def relatorio_interno(logos) -> list[Pagina]:
    sub = "Visão interna CMI — conta item a item nos _STATUS_PMIB. Ficha = PMIB distinto sem DUPLICADO."
    p1 = Pagina("Painel")
    cabecalho(p1, "GESTÃO DOS SOBRESSALENTES — PAINEL", sub, logos)
    for i, (c, k) in enumerate([("Fichas", "titulo"), ("Fichas Emitidas", "azul"), ("% Emitidas", "azul"),
                                ("Fichas Aprovadas", "verde"), ("Autorizações Atrasadas Itaipu", "vermelho"),
                                ("LMR Fora do Compromisso", "vermelho"), ("Pendências CMI", "laranja"),
                                ("Valor Físico USD", "titulo"), ("Valor Entregue USD", "verde")]):
        p1.cartao(10 + i * 140, 76, 132, 70, M(c), COR[k])
    p1.barras(10, 156, 620, 300, Campo("Itens", "Area"), [M("Fichas")], "Fichas por área e com quem está",
              serie=Campo("Itens", "Com Quem"), tipo="hundredPercentStackedBarChart")
    p1.barras(640, 156, 630, 300, Campo("Itens", "Etapa Cliente", rotulo="Etapa"), [M("Fichas")], "Fichas por etapa")
    p1.barras(10, 466, 620, 246, Campo("Itens", "Tipo de Entrega"), [M("Fichas")], "Fichas por tipo de entrega")
    p1.barras(640, 466, 630, 246, Campo("Itens", "Pendencia", rotulo="Pendência"), [M("Fichas")], "Fila: a próxima coisa que falta",
              filtros=[filtro(Campo("Itens", "Pendencia"), ["—"], negar=True)])

    p2 = Pagina("Entrega")
    cabecalho(p2, "TRILHA LOGÍSTICA — AUTORIZAÇÃO DE ITAIPU (15 DIAS ÚTEIS)",
              "Só FÍSICA E DOCUMENTAL precisa de autorização. Situação e dias de atraso gravados pelo SIG-FT.", logos)
    for i, (c, k) in enumerate([("Pedidos de Autorização", "titulo"), ("Aguardando Itaipu no Prazo", "amarelo"),
                                ("Autorizações Atrasadas Itaipu", "vermelho"), ("Maior Atraso Itaipu (dias)", "vermelho"),
                                ("Autorizadas", "verde"), ("Aptas Aguardando Entrega", "azul"),
                                ("Itens Físicos Entregues", "verde"), ("Fichas que Não Precisam de Autorização", "cinza")]):
        p2.cartao(10 + i * 157, 76, 150, 70, M(c), COR[k])
    p2.barras(10, 156, 560, 556, Campo("Listas", "Nome", rotulo="Lista"),
              [M("Aguardando Itaipu no Prazo"), M("Autorizações Atrasadas Itaipu")], "Pedidos por lista",
              tipo="barChart", ordenar=M("Autorizações Atrasadas Itaipu"),
              filtros=[filtro(Campo("Itens", "Situacao Autorizacao"), ["AGUARDANDO ITAIPU", "ATRASADO ITAIPU"])])
    p2.tabela(580, 156, 690, 556, [Campo("Itens", "Lista"), Campo("Itens", "PMIB"), Campo("Itens", "DESCRICAO", rotulo="Descrição"),
                                   Campo("Itens", "Data Email", rotulo="E-mail de intenção"),
                                   Campo("Itens", "Dias de Atraso"), Campo("Itens", "Situacao Autorizacao", rotulo="Situação")],
              "Pauta da cobrança — atrasadas", ordenar=Campo("Itens", "Dias de Atraso"),
              filtros=[filtro(Campo("Itens", "Situacao Autorizacao"), ["ATRASADO ITAIPU"])])

    p3 = Pagina("Documental")
    cabecalho(p3, "TRILHA DOCUMENTAL — SEÇÕES DA FICHA E APLICAÇÃO LMR",
              "Compromisso CMI: Aplicação LMR em até 3 meses do e-mail de intenção.", logos)
    for i, (c, k) in enumerate([("% Info Fornecedor", "cinza"), ("% Valorização", "azul"), ("% LMR", "azul"),
                                ("LMR Fora do Compromisso", "vermelho"), ("LMR em Atenção", "amarelo"),
                                ("Maior Atraso LMR (dias)", "vermelho")]):
        p3.cartao(10 + i * 210, 76, 200, 70, M(c), COR[k])
    p3.barras(10, 156, 620, 556, Campo("Listas", "Nome", rotulo="Lista"),
              [M("% Info Fornecedor"), M("% Valorização"), M("% LMR")], "Seções completas por lista")
    p3.barras(640, 156, 630, 556, Campo("Listas", "Nome", rotulo="Lista"), [M("Fichas")], "Situação da LMR por lista",
              serie=Campo("Itens", "Situacao LMR"), tipo="barChart",
              filtros=[filtro(Campo("Itens", "Situacao LMR"), ["SEM PEDIDO"], negar=True)])

    p4 = Pagina("Fila de trabalho")
    cabecalho(p4, "FILA DE TRABALHO — O QUE FALTA EM CADA FICHA",
              "Pendência = a primeira coisa que falta para a ficha andar.", logos)
    p4.segmentacao(10, 76, 300, 60, Campo("Itens", "Pendencia"), "Pendência")
    p4.segmentacao(320, 76, 300, 60, Campo("Itens", "PROCUREMENT"), "Procurement")
    p4.segmentacao(630, 76, 300, 60, Campo("Itens", "Area"), "Área")
    p4.cartao(940, 76, 330, 60, M("Pendências CMI"), COR["laranja"])
    p4.tabela(10, 146, 1260, 566, [Campo("Itens", "Pendencia", rotulo="Pendência"), Campo("Itens", "Lista"), Campo("Itens", "ITEM"),
                                   Campo("Itens", "PMIB"), Campo("Itens", "DESCRICAO", rotulo="Descrição"), Campo("Itens", "Status"),
                                   Campo("Itens", "Tipo de Entrega"), Campo("Itens", "PROCUREMENT", rotulo="Procurement"),
                                   Campo("Itens", "Dias de Atraso"), Campo("Itens", "Dias desde Email", rotulo="Dias desde o e-mail")],
              "Fichas com pendência", ordenar=Campo("Itens", "Dias de Atraso"),
              filtros=[filtro(Campo("Itens", "Pendencia"), ["—"], negar=True)])

    p5 = Pagina("Listas, preços e plano")
    cabecalho(p5, "LISTAS, LISTAS DE PREÇOS E PLANO DE AÇÃO", "Cadastro da mapeadora + estado no Aconex + aba Atividades.", logos)
    for i, (c, k) in enumerate([(Campo("Listas", "Listas", True), "titulo"),
                                (Campo("Listas", "Listas com Revisão Desatualizada", True), "vermelho"),
                                (Campo("Listas", "Listas sem Responsável", True), "laranja"),
                                (Campo("PrecosAconex", "Listas de Preços no Código Antigo", True), "amarelo"),
                                (Campo("Atividades", "Atividades Atrasadas", True), "vermelho"),
                                (Campo("Atividades", "Atividades Travadas", True), "laranja")]):
        p5.cartao(10 + i * 210, 76, 200, 70, c, COR[k])
    p5.tabela(10, 156, 760, 300, [Campo("Listas", "Nome", rotulo="Lista"), Campo("Listas", "Status Real"),
                                  Campo("Listas", "Revisao em Uso", rotulo="Revisão em uso"),
                                  Campo("Listas", "Ultima Revisao", rotulo="Última emitida"),
                                  Campo("Listas", "Responsavel", rotulo="Responsável"), M("Fichas"), M("% Aprovadas")],
              "Listas", ordenar=M("Fichas"))
    p5.tabela(780, 156, 490, 300, [Campo("PrecosAconex", "Lista de Precos", rotulo="Lista de preços"),
                                   Campo("PrecosAconex", "Geracao", rotulo="Geração"),
                                   Campo("PrecosAconex", "Situacao Preco", rotulo="Situação"),
                                   Campo("PrecosAconex", "Revisao", rotulo="Rev.")], "Listas de preços no Aconex")
    p5.tabela(10, 466, 1260, 246, [Campo("Atividades", "Frente"), Campo("Atividades", "Atividade"),
                                   Campo("Atividades", "Situacao", rotulo="Situação"),
                                   Campo("Atividades", "Termino Previsto", rotulo="Término previsto"),
                                   Campo("Atividades", "Com Quem Esta", rotulo="Com quem está"),
                                   Campo("Atividades", "Criticidade")], "Plano de ação — em aberto",
              filtros=[filtro(Campo("Atividades", "Situacao"), ["CONCLUÍDA"], negar=True)],
              ordenar=Campo("Atividades", "Termino Previsto"), crescente=True)
    return [p1, p2, p3, p4, p5]


def relatorio_itaipu(logos) -> list[Pagina]:
    sub = "Avanço das fichas técnicas de sobressalentes no PMIB e das entregas — contrato 4500063671."
    p1 = Pagina("Panorama")
    cabecalho(p1, "SOBRESSALENTES — PANORAMA", sub, logos)
    for i, (c, k, r) in enumerate([("Fichas", "titulo", "Fichas técnicas"), ("Fichas Emitidas", "azul", "Enviadas a Itaipu"),
                                   ("Fichas em Análise IB", "azul", "Em análise Itaipu"), ("Fichas Aprovadas", "verde", "Aprovadas"),
                                   ("Itens Físicos Entregues", "verde", "Material entregue"),
                                   ("Pedidos de Autorização Pendentes", "amarelo", "Autorizações pendentes")]):
        p1.cartao(10 + i * 210, 76, 200, 70, M(c, r), COR[k])
    p1.barras(10, 156, 1260, 556, Campo("Itens", "Area", rotulo="Área"), [M("Fichas", "Fichas")], "Fichas por área e etapa",
              serie=Campo("Itens", "Etapa Cliente", rotulo="Etapa"), tipo="hundredPercentStackedBarChart")

    p2 = Pagina("Pendências e listas")
    cabecalho(p2, "SOBRESSALENTES — PENDÊNCIAS E LISTAS", sub, logos)
    p2.tabela(10, 76, 1260, 330, [Campo("Listas", "Nome", rotulo="Lista"), M("Fichas", "Fichas"),
                                  M("Fichas Emitidas", "Enviadas"), M("Fichas em Análise IB", "Em análise"),
                                  M("Fichas Aprovadas", "Aprovadas"), M("Itens Físicos Entregues", "Entregues"),
                                  M("Aguardando Itaipu no Prazo", "Autorização no prazo"),
                                  M("Autorizações Atrasadas Itaipu", "Autorização além de 15 d.u.")],
              "Situação por lista", ordenar=M("Fichas"))
    p2.tabela(10, 416, 760, 296, [Campo("Itens", "Lista"), Campo("Itens", "PMIB"), Campo("Itens", "DESCRICAO", rotulo="Descrição"),
                                  Campo("Itens", "Data Email", rotulo="Pedido em"), Campo("Itens", "Dias de Atraso", rotulo="Dias além do prazo")],
              "Pedidos de autorização de entrega além de 15 dias úteis", ordenar=Campo("Itens", "Dias de Atraso"),
              filtros=[filtro(Campo("Itens", "Situacao Autorizacao"), ["ATRASADO ITAIPU"])])
    p2.tabela(780, 416, 490, 296, [Campo("PrecosAconex", "Lista de Precos", rotulo="Lista de preços"),
                                   Campo("PrecosAconex", "Revisao", rotulo="Rev."),
                                   Campo("PrecosAconex", "Data Aconex", rotulo="Emitida em")],
              "Listas de preços aguardando a SM.DT", filtros=[filtro(Campo("PrecosAconex", "Situacao Preco"), ["EMITIDA"])])
    return [p1, p2]


def escrever_relatorio(raiz: pathlib.Path, paginas: list[Pagina], antigo: zipfile.ZipFile, logos: dict, exibicao: str) -> None:
    d = raiz / "definition"
    (d / "pages").mkdir(parents=True)
    (raiz / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}}}, indent=2), encoding="utf-8")
    (raiz / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": exibicao}, "config": {"version": "2.0", "logicalId": tag()}},
        indent=2), encoding="utf-8")
    (d / "version.json").write_bytes(antigo.read("Report/definition/version.json"))
    rep = json.loads(antigo.read("Report/definition/report.json"))
    tema = {"name": "Sobressalentes v2", "dataColors": [COR[k] for k in ("azul", "laranja", "verde", "amarelo")]
            + ["#86b6ef", "#104281", COR["vermelho"], COR["cinza"]],
            "background": "#fcfcfb", "foreground": "#0b0b0b", "tableAccent": COR["azul"]}
    rep["themeCollection"]["customTheme"] = {"name": "SobressalentesV2.json",
                                             "reportVersionAtImport": rep["themeCollection"]["baseTheme"]["reportVersionAtImport"],
                                             "type": "RegisteredResources"}
    for pac in rep["resourcePackages"]:
        if pac["name"] == "RegisteredResources":
            pac["items"].append({"name": "SobressalentesV2.json", "path": "SobressalentesV2.json", "type": "CustomTheme"})
    (d / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    st = raiz / "StaticResources"
    for n in antigo.namelist():
        if n.startswith("Report/StaticResources/"):
            alvo = st / n.split("Report/StaticResources/", 1)[1]
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(antigo.read(n))
    (st / "RegisteredResources" / "SobressalentesV2.json").write_text(json.dumps(tema, indent=2), encoding="utf-8")
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": f"{SCH}/pagesMetadata/1.1.0/schema.json", "pageOrder": [p.id for p in paginas],
        "activePageName": paginas[0].id}, indent=2), encoding="utf-8")
    for pg in paginas:
        pd = d / "pages" / pg.id
        (pd / "visuals").mkdir(parents=True)
        (pd / "page.json").write_text(json.dumps({"$schema": f"{SCH}/page/2.1.0/schema.json", "name": pg.id,
                                                  "displayName": pg.nome, "displayOption": "FitToPage",
                                                  "height": 720, "width": 1280}, ensure_ascii=False, indent=2), encoding="utf-8")
        for v in pg.visuais:
            (pd / "visuals" / v["name"]).mkdir()
            (pd / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", default=PASTA_TRABALHO, help="valor do parâmetro PastaPMIB")
    ap.add_argument("--saida", type=pathlib.Path, default=AQUI / "pbip")
    ap.add_argument("--pbix-antigo", type=pathlib.Path, help="de onde copiar tema e logotipos (o .pbix atual)")
    args = ap.parse_args()
    antigo_caminho = args.pbix_antigo or pathlib.Path(args.pasta) / PBIX_ANTIGO
    antigo = zipfile.ZipFile(antigo_caminho)
    logos = {"ib": next(n.rsplit("/", 1)[1] for n in antigo.namelist() if "LOGO_IB" in n),
             "cmi": next(n.rsplit("/", 1)[1] for n in antigo.namelist() if "CMI_LOGO" in n)}
    if args.saida.exists():
        shutil.rmtree(args.saida)
    args.saida.mkdir(parents=True)
    consultas, medidas = ler_consultas(), ler_medidas()
    faltam = [t for t in TABELAS if t not in consultas]
    if faltam:
        raise SystemExit(f"consultas não encontradas nos .pq: {faltam}")
    escrever_modelo(args.saida / f"{NOME}.SemanticModel", consultas, medidas, args.pasta)
    for sufixo, paginas in (("Interno", relatorio_interno(logos)), ("Itaipu", relatorio_itaipu(logos))):
        nome_rel = f"{NOME} - {sufixo}"
        escrever_relatorio(args.saida / f"{nome_rel}.Report", paginas, antigo, logos, nome_rel)
        (args.saida / f"{nome_rel}.pbip").write_text(json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0", "artifacts": [{"report": {"path": f"{nome_rel}.Report"}}],
            "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    print(f"OK: {args.saida} — {len(consultas)} consultas, {len(medidas)} medidas, "
          f"{sum(len(p.visuais) for p in relatorio_interno(logos))} visuais (Interno)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

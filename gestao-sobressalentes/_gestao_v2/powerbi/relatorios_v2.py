# -*- coding: utf-8 -*-
"""
Desenho dos relatorios do Power BI v2 (PBIR) — "executivo": tema proprio no estilo do prototipo
HTML (fundo claro, cartoes brancos com borda fina, numeros grandes, barras horizontais simples,
poucas cores), filtros de Especificacao Tecnica e Capitulo sincronizados em todas as paginas.
Nada de barra empilhada em porcentagem.

Usado por montar_pbip.py.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import uuid

AQUI = pathlib.Path(__file__).resolve().parent
RECURSOS = AQUI / "recursos"
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
VC = f"{SCH}/visualContainer/2.12.0/schema.json"
COR = {"azul": "#2A78D6", "laranja": "#EB6834", "verde": "#1BAF7A", "ambar": "#EDA100", "vermelho": "#D03B3B",
       "cinza": "#898781", "tinta": "#0B0B0B", "tinta2": "#52514E", "borda": "#E4E3DD", "fundo": "#F4F4F1",
       "cartao": "#FFFFFF", "azul_claro": "#86B6EF", "azul_escuro": "#104281", "linha": "#ECEBE6"}
W, H, MARGEM, VAO = 1280, 720, 24, 16
LOGO_CMI, LOGO_IB = "CMI_LOGO5666199698605043.png", "LOGO_IB_Colorido6911759159194111.png"


def tema() -> dict:
    s = lambda c: {"solid": {"color": c}}  # noqa: E731
    return {
        "name": "Sobressalentes v2",
        "dataColors": [COR["azul"], COR["laranja"], COR["verde"], COR["ambar"], COR["azul_claro"], COR["azul_escuro"],
                       COR["vermelho"], COR["cinza"]],
        "background": COR["cartao"], "foreground": COR["tinta"], "tableAccent": COR["azul"],
        "good": "#0CA30C", "neutral": COR["ambar"], "bad": COR["vermelho"],
        "textClasses": {
            "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": COR["tinta"]},
            "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": COR["tinta"]},
            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": COR["tinta"]},
            "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": COR["tinta2"]},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": s(COR["cartao"]), "transparency": 0}],
                "border": [{"show": True, "color": s(COR["borda"]), "radius": 10}],
                "dropShadow": [{"show": False}],
                "title": [{"show": True, "fontColor": s(COR["tinta"]), "fontSize": 11, "fontFamily": "Segoe UI Semibold",
                           "alignment": "left"}],
                "padding": [{"top": 10, "bottom": 10, "left": 14, "right": 14}],
            }},
            "page": {"*": {"background": [{"color": s(COR["fundo"]), "transparency": 0}],
                          "outspace": [{"color": s(COR["fundo"]), "transparency": 0}]}},
            "card": {"*": {"labels": [{"color": s(COR["tinta"]), "fontSize": 24, "fontFamily": "Segoe UI Semibold",
                                       "labelDisplayUnits": 1}],
                           "categoryLabels": [{"show": True, "color": s(COR["tinta2"]), "fontSize": 10,
                                               "fontFamily": "Segoe UI"}],
                           "title": [{"show": False}]}},
            "clusteredBarChart": {"*": {
                "valueAxis": [{"show": False, "showAxisTitle": False, "gridlineShow": False}],
                "categoryAxis": [{"show": True, "showAxisTitle": False, "fontSize": 10, "labelColor": s(COR["tinta2"]),
                                  "maxMarginFactor": 45, "innerPadding": 35}],
                "labels": [{"show": True, "fontSize": 10, "color": s(COR["tinta2"]), "labelDisplayUnits": 1}],
                "legend": [{"show": False}],
                "dataPoint": [{"fill": s(COR["azul"])}]}},
            "tableEx": {"*": {
                "grid": [{"gridVertical": False, "gridHorizontal": True, "gridHorizontalColor": s(COR["linha"]),
                          "rowPadding": 4, "outlineColor": s(COR["cartao"])}],
                "columnHeaders": [{"fontColor": s(COR["tinta2"]), "backColor": s(COR["cartao"]),
                                   "fontFamily": "Segoe UI Semibold", "fontSize": 9, "wordWrap": True}],
                "values": [{"fontColorPrimary": s(COR["tinta"]), "backColorPrimary": s(COR["cartao"]),
                            "fontColorSecondary": s(COR["tinta"]), "backColorSecondary": s(COR["cartao"]),
                            "fontSize": 9}],
                "total": [{"totals": False}]}},
            "slicer": {"*": {"header": [{"show": True, "fontColor": s(COR["tinta2"]), "fontSize": 9}],
                             "items": [{"fontSize": 10, "fontColor": s(COR["tinta"])}],
                             "padding": [{"top": 4, "bottom": 4, "left": 10, "right": 10}]}},
            "textbox": {"*": {"background": [{"show": False}], "border": [{"show": False}]}},
            "image": {"*": {"background": [{"show": False}], "border": [{"show": False}]}},
        },
    }


# --------------------------------------------------------------------------
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


def M(p, rotulo=None):
    return Campo("Itens", p, True, rotulo)


def L(p, rotulo=None):
    return Campo("Listas", p, True, rotulo)


def PR(p, rotulo=None):
    return Campo("PrecosAconex", p, True, rotulo)


CARTOES: dict[tuple[str, str], str] = {}   # (tabela, medida) -> medida "(cartão)" criada pelo montar_pbip.py


def para_cartao(campo: Campo) -> Campo:
    """Cartao mostra 0, nao "(Em branco)": usa uma copia da medida com COALESCE(..., 0). A medida original
    continua vazia onde nao ha dado, para as tabelas nao listarem linhas zeradas."""
    if not campo.m or "(texto)" in campo.p or campo.p == "Atualizado em":
        return campo
    nome = f"{campo.p} (cartão)"
    CARTOES[(campo.t, campo.p)] = nome
    return Campo(campo.t, nome, True, campo.rotulo or campo.p)


def filtro(campo: Campo, valores: list[str], negar: bool = False) -> dict:
    cond = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": campo.p}}],
                   "Values": [[{"Literal": {"Value": "'" + v.replace("'", "''") + "'"}}] for v in valores]}}
    if negar:
        cond = {"Not": {"Expression": cond}}
    return {"name": uuid.uuid4().hex[:20], "field": campo.expr(), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "f", "Entity": campo.t, "Type": 0}], "Where": [{"Condition": cond}]}}


class Pagina:
    def __init__(self, nome_exibicao: str):
        self.id = uuid.uuid4().hex[:20]
        self.nome = nome_exibicao
        self.visuais: list[dict] = []

    def _add(self, tipo, x, y, w, h, query=None, objetos=None, titulo=None, filtros=None, sem_caixa=False,
             extra=None):
        z = (len(self.visuais) + 1) * 1000
        v = {"visualType": tipo}
        if query:
            v["query"] = query
        if objetos:
            v["objects"] = objetos
        vco = {}
        if titulo is not None:
            vco["title"] = [{"properties": {"show": lit(True), "text": lit(titulo)}}]
        if sem_caixa:
            vco["background"] = [{"properties": {"show": lit(False)}}]
            vco["border"] = [{"properties": {"show": lit(False)}}]
            vco["padding"] = [{"properties": {"top": lit(0), "bottom": lit(0), "left": lit(0), "right": lit(0)}}]
        if vco:
            v["visualContainerObjects"] = vco
        if extra:
            v.update(extra)
        v["drillFilterOtherVisuals"] = True
        cont = {"$schema": VC, "name": uuid.uuid4().hex[:20],
                "position": {"x": round(x, 2), "y": y, "z": z, "height": h, "width": round(w, 2), "tabOrder": z},
                "visual": v}
        if filtros:
            cont["filterConfig"] = {"filters": filtros}
        self.visuais.append(cont)

    def titulo(self, x, y, w, h, titulo, subtitulo):
        par = [{"textRuns": [{"value": titulo, "textStyle": {"fontWeight": "bold", "fontSize": "15pt",
                                                             "color": COR["tinta"], "fontFamily": "Segoe UI"}}]},
               {"textRuns": [{"value": subtitulo, "textStyle": {"fontSize": "9pt", "color": COR["tinta2"],
                                                                "fontFamily": "Segoe UI"}}]}]
        self._add("textbox", x, y, w, h, objetos={"general": [{"properties": {"paragraphs": par}}]}, sem_caixa=True)

    def logo(self, x, y, w, h, item):
        self._add("image", x, y, w, h, sem_caixa=True, objetos={
            "general": [{"properties": {"imageUrl": {"expr": {"ResourcePackageItem": {
                "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": item}}}}}],
            "imageScaling": [{"properties": {"imageScalingType": lit("Fit")}}]})

    def kpi(self, x, y, w, h, campo: Campo, cor_valor: str | None = None):
        campo = para_cartao(campo)
        objetos = {}
        if cor_valor:
            objetos["labels"] = [{"properties": {"color": cor(cor_valor)}}]
        self._add("card", x, y, w, h, query={"queryState": {"Values": {"projections": [campo.proj()]}}},
                  objetos=objetos or None)

    def nota(self, x, y, w, h, campo: Campo):
        """Texto pequeno vindo de medida (data de atualizacao)."""
        self._add("card", x, y, w, h, query={"queryState": {"Values": {"projections": [campo.proj()]}}}, sem_caixa=True,
                  objetos={"labels": [{"properties": {"fontSize": lit(9), "color": cor(COR["tinta2"]),
                                                      "fontFamily": lit("Segoe UI")}}],
                           "categoryLabels": [{"properties": {"show": lit(False)}}]})

    def barras(self, x, y, w, h, categoria: Campo, valor: Campo, titulo: str, ordem: str = "valor",
               cor_unica: str | None = None, cores: dict | None = None, filtros=None, margem: int = 45):
        q = {"queryState": {"Category": {"projections": [categoria.proj(ativo=True)]},
                            "Y": {"projections": [valor.proj()]}}}
        q["sortDefinition"] = {"sort": [{"field": categoria.expr() if ordem == "categoria" else valor.expr(),
                                         "direction": "Ascending" if ordem == "categoria" else "Descending"}],
                               "isDefaultSort": False}
        pontos = []
        if cor_unica:
            pontos.append({"properties": {"fill": cor(cor_unica)}})
        for valor_cat, hexa in (cores or {}).items():
            pontos.append({"properties": {"fill": cor(hexa)}, "selector": {"data": [{"scopeId": {"Comparison": {
                "ComparisonKind": 0, "Left": categoria.expr(),
                "Right": {"Literal": {"Value": "'" + valor_cat.replace("'", "''") + "'"}}}}}]}})
        objetos = {"valueAxis": [{"properties": {"show": lit(False), "showAxisTitle": lit(False)}}],
                   "categoryAxis": [{"properties": {"showAxisTitle": lit(False), "maxMarginFactor": lit(margem)}}]}
        if pontos:
            objetos["dataPoint"] = pontos
        self._add("clusteredBarChart", x, y, w, h, query=q, titulo=titulo, filtros=filtros, objetos=objetos)

    def tabela(self, x, y, w, h, campos: list[Campo], titulo: str, filtros=None, ordenar: Campo | None = None,
               crescente: bool = False, pesos: list[float] | None = None, total: bool = False):
        """pesos = largura relativa de cada coluna (Power BI nao estica coluna sozinho)."""
        q = {"queryState": {"Values": {"projections": [c.proj() for c in campos]}}}
        if ordenar:
            q["sortDefinition"] = {"sort": [{"field": ordenar.expr(), "direction": "Ascending" if crescente else "Descending"}]}
        pesos = pesos or [1] * len(campos)
        util = (w - 28 - 22) * 1.0          # padding + barra de rolagem
        larguras = [{"properties": {"value": lit(round(util * pz / sum(pesos)))},
                     "selector": {"metadata": f"{c.t}.{c.p}"}} for c, pz in zip(campos, pesos)]
        objetos = {"columnWidth": larguras, "total": [{"properties": {"totals": lit(total)}}],
                   "values": [{"properties": {"wordWrap": lit(True)}}]}
        self._add("tableEx", x, y, w, h, query=q, titulo=titulo, filtros=filtros, objetos=objetos)

    def segmentacao(self, x, y, w, h, campo: Campo, titulo: str, grupo: str | None = None):
        extra = {"syncGroup": {"groupName": grupo, "fieldChanges": True, "filterChanges": True}} if grupo else None
        self._add("slicer", x, y, w, h, query={"queryState": {"Values": {"projections": [campo.proj(ativo=True)]}}},
                  objetos={"data": [{"properties": {"mode": lit("Dropdown")}}],
                           "header": [{"properties": {"text": lit(titulo)}}]}, extra=extra)


def cabecalho(pg: Pagina, titulo: str, subtitulo: str, itaipu: bool = False) -> None:
    x = MARGEM
    if itaipu:
        pg.logo(MARGEM, 18, 104, 44, LOGO_IB)
        x += 116
    pg.titulo(x, 4, 640 - x, 62, titulo, subtitulo)
    pg.nota(x - 6, 64, 128, 28, M("Atualizado em"))
    pg.segmentacao(680, 14, 236, 64, Campo("Listas", "Especificacao Tecnica"), "Especificação técnica", "ET")
    pg.segmentacao(928, 14, 236, 64, Campo("Listas", "Capitulo"), "Capítulo", "Capitulo")
    pg.logo(1176, 16, 80, 60, LOGO_CMI)


def linha_kpis(pg: Pagina, y: int, itens: list[tuple[Campo, str | None]], h: int = 92) -> None:
    n = len(itens)
    w = (W - 2 * MARGEM - (n - 1) * VAO) / n
    for i, (campo, c) in enumerate(itens):
        pg.kpi(MARGEM + i * (w + VAO), y, w, h, campo, c)


ATRASADO = lambda: filtro(Campo("Itens", "Situacao Autorizacao"), ["ATRASADO ITAIPU"])  # noqa: E731
COM_PENDENCIA = lambda: filtro(Campo("Itens", "Pendencia"), ["—"], negar=True)  # noqa: E731
NOME_LISTA = lambda: Campo("Listas", "Nome", rotulo="Lista")  # noqa: E731


def filtro_medida_positiva(campo: Campo) -> dict:
    """Filtro de visual 'medida > 0' (ex.: so as listas sem lista de precos)."""
    return {"name": uuid.uuid4().hex[:20], "field": campo.expr(), "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": "m", "Entity": campo.t, "Type": 0}],
                       "Where": [{"Condition": {"Comparison": {
                           "ComparisonKind": 1,
                           "Left": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": campo.p}},
                           "Right": {"Literal": {"Value": "0L"}}}}}]}}


COR_COM_QUEM = {"CMI": COR["azul"], "Fornecedor": COR["laranja"], "Itaipu": COR["ambar"], "Concluída": COR["verde"],
                "Sem status": COR["cinza"]}


def relatorio_interno() -> list[Pagina]:
    p1 = Pagina("Visão geral")
    cabecalho(p1, "Sobressalentes — visão geral", "Fichas técnicas no PMIB, contadas item a item nos _STATUS_PMIB")
    linha_kpis(p1, 100, [(M("Fichas", "Fichas técnicas"), None),
                         (M("Enviadas a Itaipu (texto)", "Enviadas a Itaipu"), None),
                         (M("Aprovadas (texto)", "Aprovadas por Itaipu"), COR["verde"]),
                         (M("Autorizações Atrasadas Itaipu", "Autorizações atrasadas"), COR["vermelho"]),
                         (M("Itens Físicos Entregues", "Material entregue"), None),
                         (M("Pendências CMI", "Com pendência do CMI"), COR["laranja"])])
    p1.barras(MARGEM, 208, 608, 262, Campo("Itens", "Etapa"), M("Fichas"), "Em que etapa estão as fichas",
              ordem="categoria", cor_unica=COR["azul"], margem=30)
    p1.barras(648, 208, 608, 262, Campo("Itens", "Com Quem"), M("Fichas"), "Com quem estão", cores=COR_COM_QUEM, margem=25)
    p1.tabela(MARGEM, 486, 1232, 210, [Campo("Listas", "Especificacao Tecnica", rotulo="Especificação técnica"),
                                       M("Fichas"), M("Fichas Emitidas", "Enviadas"), M("Fichas em Análise IB", "Em análise"),
                                       M("Fichas Aprovadas", "Aprovadas"), M("% Aprovadas", "% aprovadas"),
                                       M("Itens Físicos Entregues", "Entregues"),
                                       M("Autorizações Atrasadas Itaipu", "Autorização atrasada"),
                                       M("Pendências CMI", "Com pendência do CMI")],
              "Por especificação técnica", ordenar=M("Fichas"), pesos=[3, 1, 1, 1, 1, 1, 1, 1.3, 1.4], total=True)

    p2 = Pagina("Listas de sobressalentes")
    cabecalho(p2, "Listas de sobressalentes", "Situação de cada lista no Aconex e no PMIB (cadastro da mapeadora)")
    linha_kpis(p2, 100, [(L("Listas", "Listas de sobressalentes"), None),
                         (L("Listas Aprovadas EN.DT", "Aprovadas no Aconex"), COR["verde"]),
                         (L("Listas com Revisão Desatualizada", "Revisão em uso desatualizada"), COR["vermelho"]),
                         (L("Listas sem Responsável", "Sem responsável"), COR["laranja"]),
                         (L("Listas sem Lista de Preços", "Sem lista de preços"), COR["ambar"])])
    p2.barras(MARGEM, 208, 500, 230, Campo("Listas", "Status Real", rotulo="Situação"), L("Listas"), "Situação no Aconex",
              cores={"APROVADO": COR["verde"], "NÃO APROVADO": COR["vermelho"], "EM PROCESSO": COR["ambar"],
                     "NÃO EMITIDO": COR["cinza"], "SEM LISTA": COR["cinza"]}, margem=30)
    p2.barras(540, 208, 716, 230, Campo("Listas", "Situacao PMIB (mapeadora)", rotulo="Situação"), L("Listas"),
              "Situação das fichas no PMIB", cor_unica=COR["azul"], margem=45)
    p2.tabela(MARGEM, 454, 1232, 242, [NOME_LISTA(), Campo("Listas", "Status Real", rotulo="Aconex"),
                                       Campo("Listas", "Revisao em Uso", rotulo="Rev. em uso"),
                                       Campo("Listas", "Ultima Revisao", rotulo="Últ. emitida"),
                                       Campo("Listas", "Situacao PMIB (mapeadora)", rotulo="Situação no PMIB"),
                                       M("Fichas"), M("% Aprovadas", "% aprovadas"),
                                       Campo("Listas", "Responsavel", rotulo="Responsável")],
              "Listas", ordenar=M("Fichas"), pesos=[4.2, 1.3, 0.8, 0.8, 2.2, 0.7, 0.9, 1.8])

    p3 = Pagina("Listas de preços")
    cabecalho(p3, "Listas de preços", "Estado de cada lista de preços no Aconex (aba Lista de preços Follow-up)")
    linha_kpis(p3, 100, [(PR("Listas de Preços Emitidas", "Listas de preços emitidas"), None),
                         (PR("Listas de Preços Aprovadas SM.DT", "Aprovadas pela SM.DT"), COR["verde"]),
                         (PR("Listas de Preços Aguardando SM.DT", "Aguardando a SM.DT"), COR["ambar"]),
                         (PR("Listas de Preços Não Aprovadas", "Não aprovadas"), COR["vermelho"]),
                         (PR("Listas de Preços no Código Antigo", "No código antigo"), COR["cinza"]),
                         (L("Listas sem Lista de Preços", "Listas sem lista de preços"), COR["laranja"])])
    p3.barras(MARGEM, 208, 440, 200, Campo("PrecosAconex", "Situacao Preco", rotulo="Situação"),
              PR("Listas de Preços Emitidas", "Listas"), "Situação no Aconex",
              cores={"APROVADA SM.DT": COR["verde"], "EMITIDA": COR["ambar"], "NÃO APROVADA": COR["vermelho"],
                     "CANCELADA": COR["cinza"]}, margem=35)
    p3.tabela(MARGEM, 424, 440, 272, [NOME_LISTA(), M("Fichas")], "Listas com fichas e sem lista de preços",
              filtros=[filtro_medida_positiva(L("Listas sem Lista de Preços"))], ordenar=M("Fichas"), pesos=[4, 1])
    p3.tabela(480, 208, 776, 488, [Campo("Listas", "Nome", rotulo="Lista de sobressalentes"),
                                   Campo("PrecosAconex", "Lista de Precos", rotulo="Lista de preços"),
                                   Campo("PrecosAconex", "Revisao", rotulo="Rev."),
                                   Campo("PrecosAconex", "Situacao Preco", rotulo="Situação"),
                                   Campo("PrecosAconex", "Data Aconex", rotulo="Data no Aconex")],
              "Listas de preços no Aconex", ordenar=Campo("PrecosAconex", "Data Aconex"), pesos=[3, 3, 0.6, 1.4, 1.1])

    p4 = Pagina("Autorização e entrega")
    cabecalho(p4, "Autorização de entrega e material",
              "Prazo de Itaipu: 15 dias úteis do e-mail de intenção · só FÍSICA E DOCUMENTAL precisa")
    linha_kpis(p4, 100, [(M("Pedidos de Autorização Pendentes", "Pedidos pendentes"), None),
                         (M("Aguardando Itaipu no Prazo", "Dentro do prazo"), COR["ambar"]),
                         (M("Autorizações Atrasadas Itaipu", "Além de 15 dias úteis"), COR["vermelho"]),
                         (M("Maior Atraso Itaipu (dias)", "Maior atraso (dias)"), COR["vermelho"]),
                         (M("Aptas Aguardando Entrega", "Autorizadas, a entregar"), COR["azul"]),
                         (M("Itens Físicos Entregues", "Material entregue"), COR["verde"])])
    p4.barras(MARGEM, 208, 500, 488, NOME_LISTA(), M("Autorizações Atrasadas Itaipu", "Atrasadas"),
              "Autorizações atrasadas por lista", cor_unica=COR["vermelho"], margem=60)
    p4.tabela(540, 208, 716, 488, [NOME_LISTA(), Campo("Itens", "PMIB"), Campo("Itens", "DESCRICAO", rotulo="Descrição"),
                                   Campo("Itens", "Data Email", rotulo="Pedido em"),
                                   Campo("Itens", "Dias de Atraso", rotulo="Dias de atraso")],
              "Pauta da cobrança — além de 15 dias úteis", filtros=[ATRASADO()], ordenar=Campo("Itens", "Dias de Atraso"),
              pesos=[2.2, 1.3, 3, 1, 0.8])

    p5 = Pagina("Fila de trabalho")
    cabecalho(p5, "Fila de trabalho do CMI", "A primeira coisa que falta para cada ficha andar")
    p5.segmentacao(MARGEM, 100, 300, 84, Campo("Itens", "Pendencia"), "Pendência")
    p5.segmentacao(340, 100, 300, 84, Campo("Itens", "PROCUREMENT"), "Procurement")
    p5.segmentacao(656, 100, 300, 84, Campo("Itens", "Area"), "Área")
    p5.kpi(972, 100, 284, 84, M("Pendências CMI", "Fichas com pendência"), COR["laranja"])
    p5.barras(MARGEM, 200, 400, 496, Campo("Itens", "Pendencia", rotulo="Pendência"), M("Fichas"), "Pendências por tipo",
              cor_unica=COR["laranja"], filtros=[COM_PENDENCIA()], margem=50)
    p5.tabela(440, 200, 816, 496, [Campo("Itens", "Pendencia", rotulo="Pendência"), NOME_LISTA(), Campo("Itens", "PMIB"),
                                   Campo("Itens", "DESCRICAO", rotulo="Descrição"),
                                   Campo("Itens", "PROCUREMENT", rotulo="Procurement"),
                                   Campo("Itens", "Dias de Atraso", rotulo="Dias de atraso")],
              "Fichas com pendência", filtros=[COM_PENDENCIA()], ordenar=Campo("Itens", "Dias de Atraso"),
              pesos=[1.8, 2, 1.4, 2.8, 1.1, 0.7])
    return [p1, p2, p3, p4, p5]


def relatorio_itaipu() -> list[Pagina]:
    p1 = Pagina("Panorama")
    cabecalho(p1, "Sobressalentes — panorama", "Fichas técnicas no PMIB e entregas · contrato 4500063671", itaipu=True)
    linha_kpis(p1, 100, [(M("Fichas", "Fichas técnicas"), None), (M("Fichas Emitidas", "Enviadas a Itaipu"), None),
                         (M("Fichas em Análise IB", "Em análise por Itaipu"), None),
                         (M("Fichas Aprovadas", "Aprovadas"), COR["verde"]),
                         (M("Itens Físicos Entregues", "Material entregue"), COR["verde"]),
                         (M("Pedidos de Autorização Pendentes", "Autorizações pendentes"), COR["ambar"])])
    p1.barras(MARGEM, 208, 440, 236, Campo("Itens", "Etapa Cliente", rotulo="Etapa"), M("Fichas"), "Fichas por etapa",
              ordem="categoria", cores={"Em preparação (CMI)": COR["azul_claro"], "Em análise Itaipu": COR["azul"],
                                        "Aprovada": COR["azul_escuro"]}, margem=35)
    p1.barras(MARGEM, 460, 440, 236, Campo("Listas", "Especificacao Tecnica", rotulo="Especificação técnica"), M("Fichas"),
              "Fichas por especificação técnica", cor_unica=COR["azul"], margem=55)
    p1.tabela(480, 208, 776, 488, [NOME_LISTA(), M("Fichas"), M("Fichas Emitidas", "Enviadas"),
                                   M("Fichas em Análise IB", "Em análise"), M("Fichas Aprovadas", "Aprovadas"),
                                   M("Itens Físicos Entregues", "Entregues")],
              "Por lista de sobressalentes", ordenar=M("Fichas"), pesos=[4, 1, 1, 1, 1, 1], total=True)

    p2 = Pagina("Pendências")
    cabecalho(p2, "Sobressalentes — pendências", "O que aguarda decisão de Itaipu", itaipu=True)
    linha_kpis(p2, 100, [(M("Pedidos de Autorização Pendentes", "Autorizações de entrega pendentes"), COR["ambar"]),
                         (M("Autorizações Atrasadas Itaipu", "Além de 15 dias úteis"), COR["vermelho"]),
                         (PR("Listas de Preços Aguardando SM.DT", "Listas de preços aguardando a SM.DT"), COR["ambar"])])
    p2.tabela(MARGEM, 208, 760, 488, [NOME_LISTA(), Campo("Itens", "PMIB"), Campo("Itens", "DESCRICAO", rotulo="Descrição"),
                                      Campo("Itens", "Data Email", rotulo="Pedido em"),
                                      Campo("Itens", "Dias de Atraso", rotulo="Dias além do prazo")],
              "Pedidos de autorização de entrega além de 15 dias úteis", filtros=[ATRASADO()],
              ordenar=Campo("Itens", "Dias de Atraso"), pesos=[2.2, 1.3, 3, 1, 0.9])
    p2.tabela(800, 208, 456, 488, [Campo("PrecosAconex", "Lista de Precos", rotulo="Lista de preços"),
                                   Campo("PrecosAconex", "Revisao", rotulo="Rev."),
                                   Campo("PrecosAconex", "Data Aconex", rotulo="Emitida em")],
              "Listas de preços aguardando a SM.DT",
              filtros=[filtro(Campo("PrecosAconex", "Situacao Preco"), ["EMITIDA"])], pesos=[3, 0.6, 1.1])
    return [p1, p2]


def escrever_relatorio(raiz: pathlib.Path, paginas: list[Pagina], exibicao: str, modelo: str) -> None:
    d = raiz / "definition"
    (d / "pages").mkdir(parents=True)
    (raiz / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{modelo}.SemanticModel"}}}, indent=2), encoding="utf-8")
    (raiz / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": exibicao}, "config": {"version": "2.0", "logicalId": str(uuid.uuid4())}},
        indent=2), encoding="utf-8")
    shutil.copy2(RECURSOS / "version.json", d / "version.json")
    rep = json.loads((RECURSOS / "report.json").read_text(encoding="utf-8"))
    rep["themeCollection"]["customTheme"] = {"name": "SobressalentesV2.json",
                                             "reportVersionAtImport": rep["themeCollection"]["baseTheme"]["reportVersionAtImport"],
                                             "type": "RegisteredResources"}
    for pac in rep["resourcePackages"]:
        if pac["name"] == "RegisteredResources":
            pac["items"] = [i for i in pac["items"] if i["type"] != "CustomTheme"] + [
                {"name": "SobressalentesV2.json", "path": "SobressalentesV2.json", "type": "CustomTheme"}]
    rep.setdefault("objects", {}).pop("outspacePane", None)
    (d / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    st = raiz / "StaticResources"
    (st / "SharedResources" / "BaseThemes").mkdir(parents=True)
    (st / "RegisteredResources").mkdir(parents=True)
    shutil.copy2(RECURSOS / "CY24SU10.json", st / "SharedResources" / "BaseThemes" / "CY24SU10.json")
    for logo in (LOGO_CMI, LOGO_IB):
        shutil.copy2(RECURSOS / logo, st / "RegisteredResources" / logo)
    (st / "RegisteredResources" / "SobressalentesV2.json").write_text(json.dumps(tema(), ensure_ascii=False, indent=2),
                                                                      encoding="utf-8")
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": f"{SCH}/pagesMetadata/1.1.0/schema.json", "pageOrder": [p.id for p in paginas],
        "activePageName": paginas[0].id}, indent=2), encoding="utf-8")
    for pg in paginas:
        pd = d / "pages" / pg.id
        (pd / "visuals").mkdir(parents=True)
        (pd / "page.json").write_text(json.dumps({"$schema": f"{SCH}/page/2.1.0/schema.json", "name": pg.id,
                                                  "displayName": pg.nome, "displayOption": "FitToPage",
                                                  "height": H, "width": W}, ensure_ascii=False, indent=2), encoding="utf-8")
        for v in pg.visuais:
            (pd / "visuals" / v["name"]).mkdir()
            (pd / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, ensure_ascii=False, indent=2),
                                                                     encoding="utf-8")

# -*- coding: utf-8 -*-
"""
Edicao "cirurgica" de .xlsx: altera so os trechos de XML necessarios e regrava
TODO o resto do arquivo exatamente como estava.

Por que existe: o openpyxl reescreve o arquivo inteiro com o que ele entende e
APAGA o que nao entende — comentarios em thread (autor, data, respostas),
validacoes gravadas como extensao (as listas suspensas que apontam para outra
aba). Aqui, cada parte do pacote que nao foi tocada sai identica, byte a byte.

Uso:
    p = PlanilhaXlsx(caminho)
    aba = p.parte_da_aba("Lista de Materiais")
    p.escrever(aba, "U5", "TIPO DE ENTREGA", estilo=p.estilo(aba, "T5"))
    p.salvar()   # grava no MESMO arquivo: o Box registra versao nova e guarda a anterior

Serve para a migracao do _STATUS_PMIB v2 e e o modelo de como o SIG-FT deve
gravar nos _STATUS_PMIB para nao apagar mais nada.

Requisitos: lxml
"""
from __future__ import annotations

import copy
import datetime as dt
import io
import pathlib
import re
import zipfile

from lxml import etree

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
NS_XM = "http://schemas.microsoft.com/office/excel/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


# ordem dos filhos de <worksheet> e <workbook> (ECMA-376): elemento novo entra no lugar certo
ORDEM_WORKSHEET = ["sheetPr", "dimension", "sheetViews", "sheetFormatPr", "cols", "sheetData", "sheetCalcPr",
                   "sheetProtection", "protectedRanges", "scenarios", "autoFilter", "sortState", "dataConsolidate",
                   "customSheetViews", "mergeCells", "phoneticPr", "conditionalFormatting", "dataValidations",
                   "hyperlinks", "printOptions", "pageMargins", "pageSetup", "headerFooter", "rowBreaks", "colBreaks",
                   "customProperties", "cellWatches", "ignoredErrors", "smartTags", "drawing", "legacyDrawing",
                   "legacyDrawingHF", "drawingHF", "picture", "oleObjects", "controls", "webPublishItems",
                   "tableParts", "extLst"]
ORDEM_WORKBOOK = ["fileVersion", "fileSharing", "workbookPr", "workbookProtection", "bookViews", "sheets",
                  "functionGroups", "externalReferences", "definedNames", "calcPr", "oleSize",
                  "customWorkbookViews", "pivotCaches", "smartTagPr", "smartTagTypes", "webPublishing",
                  "fileRecoveryPr", "webPublishObjects", "extLst"]


# --------------------------------------------------------------------------
# Referencias de celula
# --------------------------------------------------------------------------
def col_numero(letras: str) -> int:
    n = 0
    for ch in letras.upper():
        n = n * 26 + ord(ch) - 64
    return n


def col_letras(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def separar(ref: str) -> tuple[int, int]:
    m = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", ref.upper())
    if not m:
        raise ValueError(f"referência inválida: {ref}")
    return col_numero(m.group(1)), int(m.group(2))


def limites(faixa: str) -> tuple[int, int, int, int]:
    """'J5:J61' -> (col1, lin1, col2, lin2); aceita 'J5', 'J:J', '5:5'."""
    partes = faixa.upper().replace("$", "").split(":")
    def um(p, fim):
        m = re.fullmatch(r"([A-Z]*)(\d*)", p)
        c = col_numero(m.group(1)) if m.group(1) else (16384 if fim else 1)
        r = int(m.group(2)) if m.group(2) else (1048576 if fim else 1)
        return c, r
    c1, r1 = um(partes[0], False)
    c2, r2 = um(partes[-1], True) if len(partes) > 1 else (c1, r1)
    return c1, r1, c2, r2


def faixa(c1: int, r1: int, c2: int, r2: int) -> str:
    a, b = f"{col_letras(c1)}{r1}", f"{col_letras(c2)}{r2}"
    return a if a == b else f"{a}:{b}"


def subtrair(fx: str, colunas: set[int], linha_ini: int) -> list[str]:
    """Tira de uma faixa as celulas das `colunas` a partir de `linha_ini`; devolve o que sobra."""
    c1, r1, c2, r2 = limites(fx)
    if not any(c1 <= c <= c2 for c in colunas) or r2 < linha_ini:
        return [fx]
    sobra, inicio = [], None
    for c in range(c1, c2 + 2):
        livre = c <= c2 and c not in colunas
        if livre and inicio is None:
            inicio = c
        if not livre and inicio is not None:
            sobra.append(faixa(inicio, r1, c - 1, r2))
            inicio = None
    for c in sorted(x for x in colunas if c1 <= x <= c2):   # parte acima de linha_ini continua
        if r1 < linha_ini:
            sobra.append(faixa(c, r1, c, linha_ini - 1))
    return sobra


def serial_excel(d: dt.date) -> int:
    return (d - dt.date(1899, 12, 30)).days


# --------------------------------------------------------------------------
class PlanilhaXlsx:
    def __init__(self, caminho: pathlib.Path | str):
        self.caminho = pathlib.Path(caminho)
        with zipfile.ZipFile(self.caminho) as z:
            self._infos = z.infolist()
            self._bytes = {i.filename: z.read(i.filename) for i in self._infos}
        self._arvores: dict[str, etree._Element] = {}
        self._modificadas: set[str] = set()
        self._indice_linhas: dict[str, dict[int, etree._Element]] = {}

    # ---------------- partes ----------------
    def raiz(self, parte: str) -> etree._Element:
        if parte not in self._arvores:
            parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, huge_tree=True)
            self._arvores[parte] = etree.fromstring(self._bytes[parte], parser)
        return self._arvores[parte]

    def _mudou(self, parte: str) -> None:
        self._modificadas.add(parte)

    @property
    def partes_modificadas(self) -> set[str]:
        return set(self._modificadas)

    def parte_da_aba(self, nome: str) -> str:
        rid = None
        for s in self.raiz("xl/workbook.xml").iter(q("sheet")):
            if s.get("name") == nome:
                rid = s.get(f"{{{NS_R}}}id")
        if rid is None:
            raise KeyError(f"aba não encontrada: {nome}")
        for rel in etree.fromstring(self._bytes["xl/_rels/workbook.xml.rels"]):
            if rel.get("Id") == rid:
                alvo = rel.get("Target")
                return alvo.lstrip("/") if alvo.startswith("/") else "xl/" + alvo
        raise KeyError(f"relação {rid} não encontrada")

    def salvar(self, destino: pathlib.Path | str | None = None) -> None:
        """Regrava o pacote: partes modificadas serializadas, o resto byte a byte como estava.
        Escreve POR CIMA do mesmo arquivo (sem apagar/renomear): o Box guarda a versao anterior."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for info in self._infos:
                dados = self._bytes[info.filename]
                if info.filename in self._modificadas:
                    dados = etree.tostring(self._arvores[info.filename], xml_declaration=True,
                                           encoding="UTF-8", standalone=True)
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                z.writestr(zi, dados)
        destino = pathlib.Path(destino or self.caminho)
        modo = "r+b" if destino.exists() else "wb"
        with open(destino, modo) as fh:
            fh.seek(0)
            fh.write(buf.getvalue())
            fh.truncate()

    def _inserir_em_ordem(self, pai: etree._Element, novo: etree._Element, ordem: list[str]) -> None:
        idx = ordem.index(etree.QName(novo).localname)
        for filho in pai:
            if not isinstance(filho.tag, str):
                continue
            nome = etree.QName(filho)
            if nome.namespace == NS and nome.localname in ordem and ordem.index(nome.localname) > idx:
                filho.addprevious(novo)
                return
        pai.append(novo)

    # ---------------- celulas ----------------
    def _linhas(self, parte: str) -> dict[int, etree._Element]:
        if parte not in self._indice_linhas:
            sd = self.raiz(parte).find(q("sheetData"))
            self._indice_linhas[parte] = {int(r.get("r")): r for r in sd.iterchildren(q("row"))}
        return self._indice_linhas[parte]

    def _linha(self, parte: str, r: int, criar: bool) -> etree._Element | None:
        idx = self._linhas(parte)
        if r in idx or not criar:
            return idx.get(r)
        sd = self.raiz(parte).find(q("sheetData"))
        nova = etree.Element(q("row"))
        nova.set("r", str(r))
        seguinte = min((n for n in idx if n > r), default=None)
        if seguinte is None:
            sd.append(nova)
        else:
            idx[seguinte].addprevious(nova)
        idx[r] = nova
        return nova

    def celula(self, parte: str, ref: str, criar: bool = True) -> etree._Element | None:
        col, r = separar(ref)
        linha = self._linha(parte, r, criar)
        if linha is None:
            return None
        for c in linha.iterchildren(q("c")):
            if c.get("r") is None:
                raise ValueError(f"linha {r} tem célula sem referência — arquivo fora do padrão")
            cc = separar(c.get("r"))[0]
            if cc == col:
                return c
            if cc > col:
                if not criar:
                    return None
                nova = etree.Element(q("c"))
                nova.set("r", f"{col_letras(col)}{r}")
                c.addprevious(nova)
                self._ajustar_spans(linha, col)
                return nova
        if not criar:
            return None
        nova = etree.Element(q("c"))
        nova.set("r", f"{col_letras(col)}{r}")
        ext = linha.find(q("extLst"))
        if ext is not None:
            ext.addprevious(nova)
        else:
            linha.append(nova)
        self._ajustar_spans(linha, col)
        return nova

    @staticmethod
    def _ajustar_spans(linha: etree._Element, col: int) -> None:
        sp = linha.get("spans")
        if sp and re.fullmatch(r"\d+:\d+", sp):
            a, b = map(int, sp.split(":"))
            linha.set("spans", f"{min(a, col)}:{max(b, col)}")

    def estilo(self, parte: str, ref: str) -> str | None:
        c = self.celula(parte, ref, criar=False)
        return None if c is None else c.get("s")

    def tem_valor(self, parte: str, ref: str) -> bool:
        c = self.celula(parte, ref, criar=False)
        return c is not None and (c.find(q("v")) is not None or c.find(q("is")) is not None or c.find(q("f")) is not None)

    def escrever(self, parte: str, ref: str, valor, estilo: str | None = None) -> None:
        """Valor texto (inline), numero, data (serial) ou None (celula vazia, so estilo)."""
        c = self.celula(parte, ref)
        for filho in list(c):
            c.remove(filho)
        c.attrib.pop("t", None)
        if estilo is not None:
            c.set("s", str(estilo))
        if valor is None or valor == "":
            pass
        elif isinstance(valor, bool):
            c.set("t", "b")
            etree.SubElement(c, q("v")).text = "1" if valor else "0"
        elif isinstance(valor, (int, float)):
            etree.SubElement(c, q("v")).text = repr(valor) if isinstance(valor, float) else str(valor)
        elif isinstance(valor, dt.date):
            etree.SubElement(c, q("v")).text = str(serial_excel(valor if not isinstance(valor, dt.datetime) else valor.date()))
        else:
            c.set("t", "inlineStr")
            t = etree.SubElement(etree.SubElement(c, q("is")), q("t"))
            t.text = str(valor)
            if t.text != t.text.strip():
                t.set(XML_SPACE, "preserve")
        self._ajustar_dimensao(parte, *separar(ref))
        self._mudou(parte)

    def _ajustar_dimensao(self, parte: str, col: int, r: int) -> None:
        d = self.raiz(parte).find(q("dimension"))
        if d is None or not d.get("ref"):
            return
        c1, r1, c2, r2 = limites(d.get("ref"))
        if col > c2 or r > r2:
            d.set("ref", faixa(min(c1, col), min(r1, r), max(c2, col), max(r2, r)))

    # ---------------- colunas ----------------
    def largura(self, parte: str, col: int, largura: float) -> None:
        """Largura de uma coluna; divide faixas <col> existentes e tira 'oculta' da coluna."""
        ws = self.raiz(parte)
        cols = ws.find(q("cols"))
        if cols is None:
            cols = etree.Element(q("cols"))
            self._inserir_em_ordem(ws, cols, ORDEM_WORKSHEET)
        novo = None
        for c in list(cols):
            mn, mx = int(c.get("min")), int(c.get("max"))
            if mn <= col <= mx:
                pedacos = []
                if mn < col:
                    a = copy.deepcopy(c)
                    a.set("max", str(col - 1))
                    pedacos.append(a)
                novo = copy.deepcopy(c)
                novo.set("min", str(col))
                novo.set("max", str(col))
                pedacos.append(novo)
                if col < mx:
                    b = copy.deepcopy(c)
                    b.set("min", str(col + 1))
                    pedacos.append(b)
                for p in pedacos:
                    c.addprevious(p)
                cols.remove(c)
                break
        if novo is None:
            novo = etree.Element(q("col"))
            novo.set("min", str(col))
            novo.set("max", str(col))
            seguinte = next((c for c in cols if int(c.get("min")) > col), None)
            if seguinte is None:
                cols.append(novo)
            else:
                seguinte.addprevious(novo)
        for a in ("hidden", "outlineLevel", "collapsed"):
            novo.attrib.pop(a, None)
        novo.set("width", str(largura))
        novo.set("customWidth", "1")
        self._mudou(parte)

    # ---------------- mesclagens ----------------
    def mesclagens(self, parte: str) -> list[etree._Element]:
        mc = self.raiz(parte).find(q("mergeCells"))
        return [] if mc is None else list(mc.iterchildren(q("mergeCell")))

    def estender_mesclagem(self, parte: str, elemento: etree._Element, ate_col: int) -> None:
        c1, r1, _, r2 = limites(elemento.get("ref"))
        elemento.set("ref", faixa(c1, r1, ate_col, r2))
        self._mudou(parte)

    # ---------------- validacoes ----------------
    def remover_validacoes(self, parte: str, colunas: set[int], linha_ini: int) -> int:
        """Tira das validacoes (padrao e de extensao x14) as faixas das `colunas` a partir de
        `linha_ini`. Devolve quantas faixas foram mexidas."""
        ws, mexidas = self.raiz(parte), 0
        dvs = ws.find(q("dataValidations"))
        if dvs is not None:
            for dv in list(dvs.iterchildren(q("dataValidation"))):
                antes = dv.get("sqref", "").split()
                depois = [s for fx in antes for s in subtrair(fx, colunas, linha_ini)]
                if depois != antes:
                    mexidas += 1
                    if depois:
                        dv.set("sqref", " ".join(depois))
                    else:
                        dvs.remove(dv)
            if len(dvs):
                dvs.set("count", str(len(dvs)))
            else:
                ws.remove(dvs)
        ext_lst = ws.find(q("extLst"))
        if ext_lst is not None:
            for x14dvs in list(ext_lst.iter(f"{{{NS_X14}}}dataValidations")):
                for dv in list(x14dvs.iterchildren(f"{{{NS_X14}}}dataValidation")):
                    sq = dv.find(f"{{{NS_XM}}}sqref")
                    antes = (sq.text or "").split()
                    depois = [s for fx in antes for s in subtrair(fx, colunas, linha_ini)]
                    if depois != antes:
                        mexidas += 1
                        if depois:
                            sq.text = " ".join(depois)
                        else:
                            x14dvs.remove(dv)
                if len(x14dvs):
                    x14dvs.set("count", str(len(x14dvs)))
                else:
                    ext = x14dvs.getparent()
                    ext.getparent().remove(ext)
            if len(ext_lst) == 0:
                ws.remove(ext_lst)
        if mexidas:
            self._mudou(parte)
        return mexidas

    def adicionar_validacao(self, parte: str, sqref: str, tipo: str = "list", formula1: str | None = None,
                            formula2: str | None = None, operador: str | None = None, alerta: str = "stop",
                            titulo: str = "", mensagem: str = "") -> None:
        """tipo: list | date | none (none = so mensagem de entrada, sem restricao).
        Lista por NOME DEFINIDO (formula1='lst_status') e gravada no formato padrao — sobrevive ao openpyxl."""
        ws = self.raiz(parte)
        dvs = ws.find(q("dataValidations"))
        if dvs is None:
            dvs = etree.Element(q("dataValidations"))
            self._inserir_em_ordem(ws, dvs, ORDEM_WORKSHEET)
        dv = etree.SubElement(dvs, q("dataValidation"))
        if tipo != "none":
            dv.set("type", tipo)
        if alerta != "stop":
            dv.set("errorStyle", alerta)
        if operador:
            dv.set("operator", operador)
        dv.set("allowBlank", "1")
        dv.set("showInputMessage", "1" if mensagem else "0")
        dv.set("showErrorMessage", "0" if tipo == "none" else "1")
        if titulo:
            dv.set("promptTitle", titulo[:32])
        if mensagem:
            dv.set("prompt", mensagem[:255])
        dv.set("sqref", sqref)
        if formula1:
            etree.SubElement(dv, q("formula1")).text = formula1
        if formula2:
            etree.SubElement(dv, q("formula2")).text = formula2
        dvs.set("count", str(len(dvs)))
        self._mudou(parte)

    # ---------------- nomes definidos ----------------
    def nome_definido(self, nome: str) -> str | None:
        dn = self.raiz("xl/workbook.xml").find(q("definedNames"))
        if dn is None:
            return None
        for d in dn.iterchildren(q("definedName")):
            if d.get("name") == nome and d.get("localSheetId") is None:
                return d.text
        return None

    def definir_nome(self, nome: str, ref: str) -> None:
        wb = self.raiz("xl/workbook.xml")
        dn = wb.find(q("definedNames"))
        if dn is None:
            dn = etree.Element(q("definedNames"))
            self._inserir_em_ordem(wb, dn, ORDEM_WORKBOOK)
        for d in list(dn.iterchildren(q("definedName"))):
            if d.get("name") == nome and d.get("localSheetId") is None:
                dn.remove(d)
        novo = etree.SubElement(dn, q("definedName"))
        novo.set("name", nome)
        novo.text = ref
        self._mudou("xl/workbook.xml")

    def ultima_coluna_com_valor(self, parte: str) -> int:
        fim = 0
        for c in self.raiz(parte).find(q("sheetData")).iter(q("c")):
            if c.get("r") and (c.find(q("v")) is not None or c.find(q("is")) is not None or c.find(q("f")) is not None):
                fim = max(fim, separar(c.get("r"))[0])
        return fim

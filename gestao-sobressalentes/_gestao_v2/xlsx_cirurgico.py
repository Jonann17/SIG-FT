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
# Deslocamento: inserir linhas e colunas como o Excel faz
# --------------------------------------------------------------------------
MAX_COL, MAX_LIN = 16384, 1048576

# referencia dentro de formula: [aba!]celula|faixa|colunas|linhas — fora de texto entre aspas
_RE_REF_FORMULA = re.compile(r"""
    (?<![\w.$\]'"!\#])                                   # nao e pedaco de nome, numero ou outra referencia
    (?:(?P<aba>'(?:[^']|'')+'|(?:\[\d+\])?[^\W\d][\w.]*|\[\d+\][\w.]*)!)?
    (?P<ref>\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?
          |\$?[A-Za-z]{1,3}:\$?[A-Za-z]{1,3}
          |\$?\d+:\$?\d+)
    (?![\w(!.\[$])                                       # nao e funcao (LOG10() nem nome de aba
    """, re.X)
_RE_TEXTO_FORMULA = re.compile(r'("(?:[^"]|"")*")')


class Deslocamento:
    """Insercoes em coordenadas ORIGINAIS. colunas={17: 1} insere 1 coluna antes da Q (a Q e as
    seguintes andam para a direita); linhas={4: 1} insere 1 linha antes da 4. Uma faixa que
    contem o ponto de insercao cresce (A2:T2 vira A2:X2), como no Excel."""

    def __init__(self, colunas: dict[int, int] | None = None, linhas: dict[int, int] | None = None):
        self.colunas = sorted((colunas or {}).items())
        self.linhas = sorted((linhas or {}).items())

    @staticmethod
    def _mover(x: int, insercoes: list[tuple[int, int]], maximo: int) -> int:
        if x >= maximo:                                  # faixa "ate o fim" (A:A, 1:1) continua ate o fim
            return x
        return min(maximo, x + sum(n for p, n in insercoes if x >= p))

    def col(self, c: int) -> int:
        return self._mover(c, self.colunas, MAX_COL)

    def lin(self, r: int) -> int:
        return self._mover(r, self.linhas, MAX_LIN)

    def col0(self, c0: int) -> int:                      # 0-based (VML, desenhos)
        return self.col(c0 + 1) - 1

    def lin0(self, r0: int) -> int:
        return self.lin(r0 + 1) - 1

    # ---------------- texto de referencia ----------------
    def _ponta(self, s: str) -> str:
        """Uma ponta de faixa: 'A1', '$A$1', 'A' (coluna inteira) ou '5' (linha inteira)."""
        m = re.fullmatch(r"(\$?)([A-Za-z]{1,3})?(\$?)(\d+)?", s)
        if not m or not (m.group(2) or m.group(4)):
            raise ValueError(f"referência inválida: {s}")
        d1, letras, d2, num = m.groups()
        c = self.col(col_numero(letras)) if letras else None
        r = self.lin(int(num)) if num else None
        if (letras is None or c == col_numero(letras)) and (num is None or r == int(num)):
            return s                                     # nao andou: texto intocado
        return f"{d1}{col_letras(c) if letras else ''}{d2}{r if num else ''}"

    def faixa(self, fx: str) -> str:
        return ":".join(self._ponta(p) for p in fx.split(":"))

    def sqref(self, s: str) -> str:
        novo = " ".join(self.faixa(x) for x in s.split())
        return s if novo == " ".join(s.split()) else novo

    def formula(self, texto: str, nome_aba: str, local: bool) -> str:
        """Desloca as referencias de uma formula. `local`: a formula mora na propria aba
        (referencia sem nome de aba aponta para ela). Referencia a outra aba ou a outro
        arquivo ([1]...) nao anda."""
        def troca(m: re.Match) -> str:
            aba = m.group("aba")
            if aba:
                nome = aba[1:-1].replace("''", "'") if aba.startswith("'") else aba
                if nome.startswith("[") or nome.casefold() != nome_aba.casefold():
                    return m.group(0)
            elif not local:
                return m.group(0)
            return m.group(0)[: m.start("ref") - m.start(0)] + self.faixa(m.group("ref"))
        partes = _RE_TEXTO_FORMULA.split(texto)
        for i in range(0, len(partes), 2):
            partes[i] = _RE_REF_FORMULA.sub(troca, partes[i])
        return "".join(partes)


# filhos de <worksheet> que o deslocamento sabe tratar; outro qualquer = recusa (falha ruidosa)
_ABA_SUPORTADA = {"sheetPr", "dimension", "sheetViews", "sheetFormatPr", "cols", "sheetData", "sheetCalcPr",
                  "sheetProtection", "protectedRanges", "autoFilter", "sortState", "mergeCells", "phoneticPr",
                  "conditionalFormatting", "dataValidations", "hyperlinks", "printOptions", "pageMargins",
                  "pageSetup", "headerFooter", "ignoredErrors", "drawing", "legacyDrawing", "legacyDrawingHF",
                  "extLst"}
REL_COMENTARIOS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
REL_THREADED = "http://schemas.microsoft.com/office/2017/10/relationships/threadedComment"
REL_VML = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
REL_DESENHO = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"


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
                if info.filename in self._modificadas and info.filename in self._arvores:
                    dados = etree.tostring(self._arvores[info.filename], xml_declaration=True,
                                           encoding="UTF-8", standalone=True)
                # (parte editada como texto — comentarios, VML, desenho, calcChain — ja esta em _bytes)
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

    # ---------------- inserir linhas e colunas ----------------
    def _texto(self, parte: str) -> str:
        return self._bytes[parte].decode("utf-8")

    def _trocar_texto(self, parte: str, novo: str) -> None:
        if novo != self._texto(parte):
            self._bytes[parte] = novo.encode("utf-8")
            self._mudou(parte)

    def _partes_ligadas(self, parte: str) -> dict[str, list[str]]:
        """Partes ligadas a uma aba (ou desenho) pelo .rels dela: {tipo: [partes]}."""
        pasta, nome = parte.rsplit("/", 1)
        rels = f"{pasta}/_rels/{nome}.rels"
        if rels not in self._bytes:
            return {}
        saida: dict[str, list[str]] = {}
        for rel in etree.fromstring(self._bytes[rels]):
            if rel.get("TargetMode") == "External":
                continue
            alvo = rel.get("Target")
            alvo = alvo.lstrip("/") if alvo.startswith("/") else f"{pasta}/{alvo}"
            partes: list[str] = []
            for p in alvo.split("/"):                         # resolve '..'
                if p == "..":
                    partes.pop()
                else:
                    partes.append(p)
            saida.setdefault(rel.get("Type"), []).append("/".join(partes))
        return saida

    def deslocar(self, aba: str, d: Deslocamento) -> None:
        """Insere linhas/colunas na aba como o Excel: celulas, formulas, mesclagens, validacoes,
        formatacao condicional, filtro, painel congelado, nomes definidos, comentarios (anotacao,
        thread e a caixa VML), desenhos e cadeia de calculo andam juntos. O que nao souber
        deslocar, recusa com erro — nunca desloca pela metade."""
        parte = self.parte_da_aba(aba)
        ws = self.raiz(parte)
        for filho in ws:
            if isinstance(filho.tag, str) and etree.QName(filho).localname not in _ABA_SUPORTADA:
                raise NotImplementedError(f"'{etree.QName(filho).localname}' na aba {aba}: deslocamento não suportado")
        ligadas = self._partes_ligadas(parte)
        for p in ligadas.get(REL_DESENHO, []):
            if self._partes_ligadas(p):
                raise NotImplementedError(f"desenho {p} tem gráfico/imagem ligada — não suportado")
        f_local = lambda t: d.formula(t, aba, True)  # noqa: E731

        # 1. celulas, linhas e formulas. Formula compartilhada: o Excel guarda so a da primeira
        #    celula e deduz as outras; confere a deducao depois de deslocar e, se nao bater,
        #    grava a formula explicita em cada celula.
        sd = ws.find(q("sheetData"))
        compartilhadas = self._formulas_compartilhadas(sd)
        esperado: dict[tuple[str, str], str] = {}
        if compartilhadas:
            from openpyxl.formula.translate import Translator
            for si, (mestre, deps) in compartilhadas.items():
                base = mestre.find(q("f")).text or ""
                for dep in deps:
                    t = Translator("=" + base, origin=mestre.get("r")).translate_formula(dep.get("r"))[1:]
                    esperado[(si, dep.get("r"))] = f_local(t)
        antigo = {}
        for row in sd.iterchildren(q("row")):
            row.set("r", str(d.lin(int(row.get("r")))))
            sp = row.get("spans")
            if sp and re.fullmatch(r"\d+:\d+", sp):
                a, b = map(int, sp.split(":"))
                row.set("spans", f"{d.col(a)}:{d.col(b)}")
            for c in row.iterchildren(q("c")):
                ref = c.get("r")
                c.set("r", d.faixa(ref))
                antigo[c] = ref
                f = c.find(q("f"))
                if f is None:
                    continue
                if f.get("t") == "dataTable":
                    raise NotImplementedError(f"tabela de dados em {ref}: não suportado")
                if f.get("ref"):
                    f.set("ref", d.sqref(f.get("ref")))
                if f.text:
                    f.text = f_local(f.text)
        if compartilhadas:
            for si, (mestre, deps) in compartilhadas.items():
                base = mestre.find(q("f")).text or ""
                deduz = lambda dep: Translator("=" + base, origin=mestre.get("r")).translate_formula(dep.get("r"))[1:]  # noqa: E731
                if any(deduz(dep) != esperado[(si, antigo[dep])] for dep in deps):
                    for dep in deps:
                        f = dep.find(q("f"))
                        f.attrib.clear()
                        f.text = esperado[(si, antigo[dep])]
                    fm = mestre.find(q("f"))
                    for a in ("t", "ref", "si"):
                        fm.attrib.pop(a, None)
        self._indice_linhas.pop(parte, None)

        # 2. dimensao, vistas, colunas
        dim = ws.find(q("dimension"))
        if dim is not None and dim.get("ref"):
            dim.set("ref", d.sqref(dim.get("ref")))
        for sv in ws.iter(q("sheetView")):
            if sv.get("topLeftCell"):
                sv.set("topLeftCell", d.faixa(sv.get("topLeftCell")))
            for pane in sv.iter(q("pane")):
                if pane.get("topLeftCell"):
                    pane.set("topLeftCell", d.faixa(pane.get("topLeftCell")))
                if pane.get("state") in ("frozen", "frozenSplit"):     # congelado: split = n de linhas/colunas
                    if pane.get("ySplit"):
                        pane.set("ySplit", str(d.lin(int(float(pane.get("ySplit"))) + 1) - 1))
                    if pane.get("xSplit"):
                        pane.set("xSplit", str(d.col(int(float(pane.get("xSplit"))) + 1) - 1))
            for sel in sv.iter(q("selection")):
                if sel.get("activeCell"):
                    sel.set("activeCell", d.faixa(sel.get("activeCell")))
                if sel.get("sqref"):
                    sel.set("sqref", d.sqref(sel.get("sqref")))
        cols = ws.find(q("cols"))
        if cols is not None:
            for c in cols.iterchildren(q("col")):
                c.set("min", str(d.col(int(c.get("min")))))
                c.set("max", str(d.col(int(c.get("max")))))

        # 3. filtro e ordenacao
        for af in ws.iter(q("autoFilter")):
            ref = af.get("ref")
            if ref:
                c1 = limites(ref)[0]
                for fc in af.iterchildren(q("filterColumn")):
                    fc.set("colId", str(d.col(c1 + int(fc.get("colId"))) - d.col(c1)))
                af.set("ref", d.sqref(ref))
        for ss in ws.iter(q("sortState")):
            if ss.get("ref"):
                ss.set("ref", d.sqref(ss.get("ref")))
            for sc in ss.iterchildren(q("sortCondition")):
                if sc.get("ref"):
                    sc.set("ref", d.sqref(sc.get("ref")))

        # 4. mesclagens, formatacao condicional, validacoes, links, faixas protegidas, erros ignorados
        for tag, attr in (("mergeCell", "ref"), ("conditionalFormatting", "sqref"), ("dataValidation", "sqref"),
                          ("hyperlink", "ref"), ("protectedRange", "sqref"), ("ignoredError", "sqref")):
            for el in ws.iter(q(tag)):
                if el.get(attr):
                    el.set(attr, d.sqref(el.get(attr)))
        for tag in ("formula", "formula1", "formula2"):
            for el in ws.iter(q(tag)):
                if el.text:
                    el.text = f_local(el.text)
        ext = ws.find(q("extLst"))
        if ext is not None:                                          # x14: validacoes e formatacao por extensao
            for el in ext.iter(f"{{{NS_XM}}}sqref"):
                el.text = d.sqref(el.text or "")
            for el in ext.iter(f"{{{NS_XM}}}f"):
                if el.text:
                    el.text = f_local(el.text)
        self._mudou(parte)

        # 5. nomes definidos e formulas de outras abas que apontam para esta
        wb = self.raiz("xl/workbook.xml")
        dn = wb.find(q("definedNames"))
        if dn is not None:
            for n in dn.iterchildren(q("definedName")):
                if n.text:
                    novo = d.formula(n.text, aba, False)
                    if novo != n.text:
                        n.text = novo
                        self._mudou("xl/workbook.xml")
        for s in wb.iter(q("sheet")):
            outra = s.get("name")
            if outra == aba:
                continue
            p_outra = self.parte_da_aba(outra)
            if p_outra not in self._bytes or aba.encode("utf-8") not in self._bytes[p_outra]:
                continue
            raiz = self.raiz(p_outra)
            for tag in (q("f"), q("formula"), q("formula1"), q("formula2"), f"{{{NS_XM}}}f"):
                for el in raiz.iter(tag):
                    if el.text:
                        novo = d.formula(el.text, aba, False)
                        if novo != el.text:
                            el.text = novo
                            self._mudou(p_outra)

        # 6. comentarios (anotacao + thread + caixa VML) e desenhos — editados como texto:
        #    so os numeros de posicao mudam, o resto da parte fica byte a byte
        sub_ref = lambda tag: (lambda t: re.sub(rf'(<{tag}\b[^>]*?\sref=")([^"]+)(")',  # noqa: E731
                                                lambda m: m.group(1) + d.faixa(m.group(2)) + m.group(3), t))
        for p in ligadas.get(REL_COMENTARIOS, []):
            self._trocar_texto(p, sub_ref("comment")(self._texto(p)))
        for p in ligadas.get(REL_THREADED, []):
            self._trocar_texto(p, sub_ref("threadedComment")(self._texto(p)))
        for p in ligadas.get(REL_VML, []):
            t = self._texto(p)
            t = re.sub(r"(<x:Row>)\s*(\d+)\s*(</x:Row>)", lambda m: f"{m.group(1)}{d.lin0(int(m.group(2)))}{m.group(3)}", t)
            t = re.sub(r"(<x:Column>)\s*(\d+)\s*(</x:Column>)", lambda m: f"{m.group(1)}{d.col0(int(m.group(2)))}{m.group(3)}", t)

            def ancora(m: re.Match) -> str:
                pedacos = re.split(r"(\d+)", m.group(2))
                nums = pedacos[1::2]
                if len(nums) != 8:
                    raise ValueError(f"âncora VML inesperada em {p}: {m.group(2)!r}")
                for i, f in ((0, d.col0), (2, d.lin0), (4, d.col0), (6, d.lin0)):
                    nums[i] = str(f(int(nums[i])))
                pedacos[1::2] = nums
                return m.group(1) + "".join(pedacos) + m.group(3)
            self._trocar_texto(p, re.sub(r"(<x:Anchor>)(.*?)(</x:Anchor>)", ancora, t, flags=re.S))
        for p in ligadas.get(REL_DESENHO, []):
            t = self._texto(p)
            if t.count("<xdr:col>") != t.count("<xdr:row>") or (re.search(r"<xdr:(?:two|one)CellAnchor\b", t)
                                                                and "<xdr:col>" not in t):
                raise NotImplementedError(f"desenho {p} fora do padrão esperado")
            t = re.sub(r"(<xdr:col>)(\d+)(</xdr:col>)", lambda m: f"{m.group(1)}{d.col0(int(m.group(2)))}{m.group(3)}", t)
            t = re.sub(r"(<xdr:row>)(\d+)(</xdr:row>)", lambda m: f"{m.group(1)}{d.lin0(int(m.group(2)))}{m.group(3)}", t)
            self._trocar_texto(p, t)

        # 7. cadeia de calculo: entradas desta aba (i = sheetId; ausente = o da entrada anterior)
        if "xl/calcChain.xml" in self._bytes:
            sid = next(s.get("sheetId") for s in wb.iter(q("sheet")) if s.get("name") == aba)
            atual = [None]

            def entrada(m: re.Match) -> str:
                attrs = m.group(1)
                mi = re.search(r'\si="(\d+)"', attrs)
                if mi:
                    atual[0] = mi.group(1)
                if atual[0] != sid:
                    return m.group(0)
                return "<c" + re.sub(r'(\sr=")([^"]+)(")', lambda x: x.group(1) + d.faixa(x.group(2)) + x.group(3),
                                     attrs) + m.group(2)
            self._trocar_texto("xl/calcChain.xml", re.sub(r"<c\b([^>]*?)(/?>)", entrada, self._texto("xl/calcChain.xml")))

    @staticmethod
    def _formulas_compartilhadas(sd: etree._Element) -> dict[str, tuple[etree._Element, list[etree._Element]]]:
        grupos: dict[str, list] = {}
        for c in sd.iter(q("c")):
            f = c.find(q("f"))
            if f is not None and f.get("t") == "shared" and f.get("si") is not None:
                g = grupos.setdefault(f.get("si"), [None, []])
                if f.get("ref") is not None:
                    g[0] = c
                else:
                    g[1].append(c)
        return {si: (m, deps) for si, (m, deps) in grupos.items() if m is not None and deps}

    def formatar_como_a_esquerda(self, parte: str, colunas: list[int], desde_linha: int = 1) -> int:
        """Celula vazia nas `colunas` com o estilo da celula a esquerda, em cada linha — o que o
        Excel faz ao inserir coluna ('mesma formatação da esquerda'). Devolve quantas criou."""
        n = 0
        for r in sorted(self._linhas(parte)):
            if r < desde_linha:
                continue
            for col in sorted(colunas):
                viz = self.celula(parte, f"{col_letras(col - 1)}{r}", criar=False) if col > 1 else None
                if viz is not None and viz.get("s") and self.celula(parte, f"{col_letras(col)}{r}", criar=False) is None:
                    self.celula(parte, f"{col_letras(col)}{r}").set("s", viz.get("s"))
                    n += 1
        if n:
            self._mudou(parte)
        return n

    def mesclar(self, parte: str, ref: str) -> None:
        ws = self.raiz(parte)
        mc = ws.find(q("mergeCells"))
        if mc is None:
            mc = etree.Element(q("mergeCells"))
            self._inserir_em_ordem(ws, mc, ORDEM_WORKSHEET)
        etree.SubElement(mc, q("mergeCell")).set("ref", ref)
        mc.set("count", str(len(mc)))
        self._mudou(parte)

    def linha_xml(self, parte: str, r: int, criar: bool = False) -> etree._Element | None:
        return self._linha(parte, r, criar)

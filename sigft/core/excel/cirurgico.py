r"""
sigft/core/excel/cirurgico.py — gravar em `.xlsx` sem apagar o que não é nosso.

T1 do roteiro "Gestão PMIB no tratamento v2" (`gestao-sobressalentes/07 -
Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`). Porte de
`gestao-sobressalentes/_gestao_v2/xlsx_cirurgico.py`, o editor que migrou os 47
`_STATUS_PMIB` para o layout v2 em 04/10/2026 sem perder nada.

Por que existe
--------------
O openpyxl regrava o arquivo INTEIRO com o que ele entende e apaga o resto:

  - **comentários em thread** (Revisão > Novo Comentário: autor, data,
    respostas) viram uma anotação "[Threaded comment] Your version of Excel..."
    -- em 04/10/2026, 16 dos 47 `_STATUS_PMIB` tinham esse tipo de comentário,
    e cada gravação do SIG-FT os destruía;
  - **validações gravadas como extensão** (`x14:dataValidation`, as listas
    suspensas que apontam para outra aba) somem com o aviso "Data Validation
    extension is not supported and will be removed" -- foi assim que o
    vocabulário da coluna STATUS saiu do controle (21 de 47 ainda tinham a
    lista em 01/10).

Aqui só os trechos de XML que precisam mudar são reescritos -- a aba editada e,
se for o caso, `xl/workbook.xml` (nome definido) e `xl/styles.xml` (formato de
número). **Toda outra parte do pacote sai idêntica, byte a byte.**

O que este módulo NÃO faz
-------------------------
Ler. A leitura continua com openpyxl/pandas, que entendem fórmula, data e
string compartilhada; quem grava é este módulo. Também não insere linha nem
coluna (o `Deslocamento` do original serviu à migração e ficou no cofre).

Uso
---
    gravar_celulas(caminho, "Lista de Materiais",
                   {(6, 19): "ATRASADO ITAIPU", (6, 20): 4},
                   nomes={"sigft_calculado_em": '"2026-10-10"'},
                   formato_geral={(6, 20)})

ou, peça a peça, `PlanilhaXlsx(caminho)` / `.escrever(...)` / `.salvar()`.

A gravação é POR CIMA do mesmo arquivo (abre em `r+b`, sem apagar nem
renomear): o Box registra versão nova e guarda a anterior. Com o arquivo aberto
no Excel, o `open` levanta `PermissionError` antes de escrever qualquer byte --
é o que o retry de `core.excel.locking` espera.
"""
from __future__ import annotations

import copy
import datetime as dt
import io
import math
import numbers
import pathlib
import re
import zipfile
from typing import Any, Iterable, Mapping

from lxml import etree

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

PARTE_WORKBOOK = "xl/workbook.xml"
PARTE_RELS_WORKBOOK = "xl/_rels/workbook.xml.rels"
PARTE_ESTILOS = "xl/styles.xml"
PARTE_CALC_CHAIN = "xl/calcChain.xml"
PARTE_TIPOS = "[Content_Types].xml"


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


# Ordem dos filhos de <workbook> (ECMA-376): um elemento novo entra no lugar
# certo, senão o Excel recusa o arquivo.
ORDEM_WORKBOOK = ["fileVersion", "fileSharing", "workbookPr", "workbookProtection", "bookViews", "sheets",
                  "functionGroups", "externalReferences", "definedNames", "calcPr", "oleSize",
                  "customWorkbookViews", "pivotCaches", "smartTagPr", "smartTagTypes", "webPublishing",
                  "fileRecoveryPr", "webPublishObjects", "extLst"]


# --------------------------------------------------------------------------
# Referências de célula
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


def ref(linha: int, coluna: int) -> str:
    """(6, 19) -> 'S6'."""
    return f"{col_letras(coluna)}{linha}"


def separar(referencia: str) -> tuple[int, int]:
    """'S6' -> (coluna, linha) = (19, 6)."""
    m = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", referencia.upper())
    if not m:
        raise ValueError(f"referência inválida: {referencia}")
    return col_numero(m.group(1)), int(m.group(2))


def limites(faixa_ref: str) -> tuple[int, int, int, int]:
    """'J5:J61' -> (col1, lin1, col2, lin2); aceita 'J5', 'J:J', '5:5'."""
    partes = faixa_ref.upper().replace("$", "").split(":")

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


def serial_excel(d: dt.date) -> int:
    return (d - dt.date(1899, 12, 30)).days


# --------------------------------------------------------------------------
class PlanilhaXlsx:
    """O pacote `.xlsx` inteiro em memória: partes que não forem tocadas são
    regravadas exatamente como foram lidas."""

    def __init__(self, caminho: pathlib.Path | str):
        self.caminho = pathlib.Path(caminho)
        with zipfile.ZipFile(self.caminho) as z:
            self._infos = z.infolist()
            self._bytes = {i.filename: z.read(i.filename) for i in self._infos}
        self._arvores: dict[str, Any] = {}
        self._modificadas: set[str] = set()
        self._indice_linhas: dict[str, dict[int, Any]] = {}
        self._cache_geral: dict[str | None, str] = {}

    # ---------------- partes ----------------
    def raiz(self, parte: str):
        if parte not in self._arvores:
            # `resolve_entities=False`: o arquivo vem de fora -- nada de
            # expandir entidade externa (XXE) ao ler.
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
        for s in self.raiz(PARTE_WORKBOOK).iter(q("sheet")):
            if s.get("name") == nome:
                rid = s.get(f"{{{NS_R}}}id")
        if rid is None:
            raise KeyError(f"aba não encontrada: {nome}")
        for rel in self.raiz(PARTE_RELS_WORKBOOK):
            if rel.get("Id") == rid:
                alvo = rel.get("Target")
                return alvo.lstrip("/") if alvo.startswith("/") else "xl/" + alvo
        raise KeyError(f"relação {rid} não encontrada")

    def salvar(self, destino: pathlib.Path | str | None = None) -> None:
        """Regrava o pacote: partes modificadas serializadas, o resto byte a
        byte. Escreve POR CIMA do mesmo arquivo (sem apagar/renomear): o Box
        guarda a versão anterior.

        O pacote novo é montado inteiro em memória ANTES de abrir o destino:
        com o arquivo aberto no Excel, o `PermissionError` sai do `open`, sem
        nenhum byte escrito."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for info in self._infos:
                dados = self._bytes[info.filename]
                if info.filename in self._modificadas and info.filename in self._arvores:
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

    def _inserir_em_ordem(self, pai, novo, ordem: list[str]) -> None:
        idx = ordem.index(etree.QName(novo).localname)
        for filho in pai:
            if not isinstance(filho.tag, str):
                continue
            nome = etree.QName(filho)
            if nome.namespace == NS and nome.localname in ordem and ordem.index(nome.localname) > idx:
                filho.addprevious(novo)
                return
        pai.append(novo)

    # ---------------- células ----------------
    def _linhas(self, parte: str) -> dict[int, Any]:
        if parte not in self._indice_linhas:
            sd = self.raiz(parte).find(q("sheetData"))
            self._indice_linhas[parte] = {int(r.get("r")): r for r in sd.iterchildren(q("row"))}
        return self._indice_linhas[parte]

    def _linha(self, parte: str, r: int, criar: bool):
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

    def celula(self, parte: str, referencia: str, criar: bool = True):
        col, r = separar(referencia)
        linha = self._linha(parte, r, criar)
        if linha is None:
            return None
        for c in linha.iterchildren(q("c")):
            if c.get("r") is None:
                raise ValueError(f"linha {r} tem célula sem referência: arquivo fora do padrão")
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
    def _ajustar_spans(linha, col: int) -> None:
        sp = linha.get("spans")
        if sp and re.fullmatch(r"\d+:\d+", sp):
            a, b = map(int, sp.split(":"))
            linha.set("spans", f"{min(a, col)}:{max(b, col)}")

    def estilo(self, parte: str, referencia: str) -> str | None:
        c = self.celula(parte, referencia, criar=False)
        return None if c is None else c.get("s")

    def tem_valor(self, parte: str, referencia: str) -> bool:
        c = self.celula(parte, referencia, criar=False)
        return c is not None and (c.find(q("v")) is not None or c.find(q("is")) is not None
                                  or c.find(q("f")) is not None)

    def escrever(self, parte: str, referencia: str, valor, estilo: str | None = None) -> None:
        """Valor texto (inline), número, booleano, data (serial) ou vazio
        (`None`/`""`/NaN: a célula fica só com o estilo). O estilo da célula
        é mantido, salvo se `estilo` for passado."""
        c = self.celula(parte, referencia)
        formula = c.find(q("f"))
        if formula is not None:
            self._liberar_formula(referencia, formula)
        for filho in list(c):
            c.remove(filho)
        c.attrib.pop("t", None)
        if estilo is not None:
            c.set("s", str(estilo))
        if isinstance(valor, numbers.Real) and not isinstance(valor, bool) and not math.isfinite(valor):
            # NaN/infinito: é o "vazio" do pandas. Gravado como texto, "nan"
            # dentro de <v> faz o Excel abrir o arquivo em modo de reparo.
            valor = None
        if valor is None or valor == "":
            pass
        elif isinstance(valor, bool):
            c.set("t", "b")
            etree.SubElement(c, q("v")).text = "1" if valor else "0"
        elif isinstance(valor, numbers.Integral):
            # `numbers`, e não `int`: o `numpy.int64` que sai de uma coluna do
            # pandas não é `int` e viraria TEXTO "4" na planilha.
            etree.SubElement(c, q("v")).text = str(int(valor))
        elif isinstance(valor, numbers.Real):
            etree.SubElement(c, q("v")).text = repr(float(valor))
        elif isinstance(valor, dt.date):
            dia = valor.date() if isinstance(valor, dt.datetime) else valor
            etree.SubElement(c, q("v")).text = str(serial_excel(dia))
        else:
            c.set("t", "inlineStr")
            t = etree.SubElement(etree.SubElement(c, q("is")), q("t"))
            t.text = str(valor)
            if t.text != t.text.strip():
                t.set(XML_SPACE, "preserve")
        self._ajustar_dimensao(parte, *separar(referencia))
        self._mudou(parte)

    def _liberar_formula(self, referencia: str, formula) -> None:
        """Sobrescrever célula com fórmula: só a fórmula simples, e ela deixa
        de constar da cadeia de cálculo.

        Mestra de fórmula compartilhada ou de matriz é RECUSADA: as vizinhas
        dependem dela, e apagá-la corromperia o arquivo -- falha ruidosa, com
        o arquivo intocado, é melhor que o Excel abrindo em modo de reparo.

        A cadeia de cálculo (`xl/calcChain.xml`) lista as células com fórmula,
        e o Excel trata entrada órfã como conteúdo ilegível. Em vez de editar
        a cadeia (as entradas herdam a aba da anterior), ela é descartada: é
        opcional, e o Excel a reconstrói ao abrir -- o mesmo que acontece com
        todo arquivo salvo pelo openpyxl, que nunca a grava."""
        if formula.get("t") in ("shared", "array") and formula.get("ref"):
            raise NotImplementedError(
                f"{referencia} é a célula-mestra de uma fórmula {formula.get('t')} "
                "(sobrescrevê-la quebraria as células que dependem dela)")
        self._descartar_cadeia_de_calculo()

    def _descartar_cadeia_de_calculo(self) -> None:
        if PARTE_CALC_CHAIN not in self._bytes:
            return
        self._infos = [i for i in self._infos if i.filename != PARTE_CALC_CHAIN]
        del self._bytes[PARTE_CALC_CHAIN]
        tipos = self.raiz(PARTE_TIPOS)
        for override in list(tipos.iterchildren(f"{{{NS_CT}}}Override")):
            if override.get("PartName") == "/" + PARTE_CALC_CHAIN:
                tipos.remove(override)
                self._mudou(PARTE_TIPOS)
        rels = self.raiz(PARTE_RELS_WORKBOOK)
        for rel in list(rels.iterchildren(f"{{{NS_PKG_REL}}}Relationship")):
            if rel.get("Target", "").lstrip("/").removeprefix("xl/") == "calcChain.xml":
                rels.remove(rel)
                self._mudou(PARTE_RELS_WORKBOOK)

    def _ajustar_dimensao(self, parte: str, col: int, r: int) -> None:
        d = self.raiz(parte).find(q("dimension"))
        if d is None or not d.get("ref"):
            return
        c1, r1, c2, r2 = limites(d.get("ref"))
        if col > c2 or r > r2:
            d.set("ref", faixa(min(c1, col), min(r1, r), max(c2, col), max(r2, r)))

    # ---------------- nomes definidos ----------------
    def nome_definido(self, nome: str) -> str | None:
        dn = self.raiz(PARTE_WORKBOOK).find(q("definedNames"))
        if dn is None:
            return None
        for d in dn.iterchildren(q("definedName")):
            if d.get("name") == nome and d.get("localSheetId") is None:
                return d.text
        return None

    def definir_nome(self, nome: str, referencia: str) -> None:
        """Nome definido GLOBAL (sem `localSheetId`). `referencia` é a fórmula
        do nome: `'Checklist'!$A$3:$A$8`, ou uma constante de texto com as
        aspas: `'"2026-10-10"'`."""
        wb = self.raiz(PARTE_WORKBOOK)
        dn = wb.find(q("definedNames"))
        if dn is None:
            dn = etree.Element(q("definedNames"))
            self._inserir_em_ordem(wb, dn, ORDEM_WORKBOOK)
        for d in list(dn.iterchildren(q("definedName"))):
            if d.get("name") == nome and d.get("localSheetId") is None:
                dn.remove(d)
        novo = etree.SubElement(dn, q("definedName"))
        novo.set("name", nome)
        novo.text = referencia
        self._mudou(PARTE_WORKBOOK)

    # ---------------- estilos ----------------
    def estilo_formato_geral(self, s: str | None) -> str:
        """Índice de um estilo igual a `s`, mas com formato de número Geral
        (criado no `styles.xml` se preciso). Para coluna de NÚMERO que herdou
        formato de data da vizinha: sem isso, 4 dias aparece como 04/01/1900."""
        xfs = self.raiz(PARTE_ESTILOS).find(q("cellXfs"))
        lista = list(xfs.iterchildren(q("xf")))
        base = lista[int(s or 0)]
        if base.get("numFmtId", "0") == "0":
            return s or "0"
        if s not in self._cache_geral:
            novo = copy.deepcopy(base)
            novo.set("numFmtId", "0")
            novo.set("applyNumberFormat", "1")
            lista[-1].addnext(novo)
            xfs.set("count", str(len(lista) + 1))
            self._mudou(PARTE_ESTILOS)
            self._cache_geral[s] = str(len(lista))
        return self._cache_geral[s]


# --------------------------------------------------------------------------
def gravar_celulas(
    caminho: pathlib.Path | str,
    aba: str,
    escritas: Mapping[tuple[int, int], Any],
    *,
    nomes: Mapping[str, str] | None = None,
    formato_geral: Iterable[tuple[int, int]] = (),
) -> None:
    """Abre `caminho`, escreve `escritas` (`{(linha, coluna): valor}`, 1-based)
    na `aba`, define os `nomes` e regrava por cima.

    Cada célula mantém o estilo que tinha; as de `formato_geral` ganham a
    versão do estilo com formato de número Geral (ver `estilo_formato_geral`).
    É o que `StatusPMIB.salvar()` chama a cada tentativa -- relendo o arquivo
    do disco, para não regravar por cima de algo que a pessoa salvou no Excel
    entre uma tentativa e outra."""
    planilha = PlanilhaXlsx(caminho)
    parte = planilha.parte_da_aba(aba)
    geral = set(formato_geral)
    for (linha, coluna), valor in escritas.items():
        alvo = ref(linha, coluna)
        estilo = None
        if (linha, coluna) in geral:
            estilo = planilha.estilo_formato_geral(planilha.estilo(parte, alvo))
        planilha.escrever(parte, alvo, valor, estilo=estilo)
    for nome, referencia in (nomes or {}).items():
        planilha.definir_nome(nome, referencia)
    planilha.salvar()

r"""Os documentos de uma ficha, INTEIROS -- e o que vai para a IA como PDF.

POR QUE ESTE MODULO EXISTE (2026-09-24)
------------------------------------------------------------------------
O usuario comparou o AutoSpec com o AMP, a IA corporativa da GE Vernova
(Gemini flash-lite recebendo o PDF inteiro), em quatro fichas reais. O AMP
achou 78 informacoes; o AutoSpec, 43. A primeira suspeita foi o OCR -- e nao
era: os PDFs tinham camada de texto e o PyMuPDF lia 100% das paginas.

O que perdia a informacao era o caminho entre a leitura e a IA:

    4500063671.0094.pdf: 166 pagina(s), 166 lida(s) (100%), 177273 chars
    Contexto recortado: 19 de 61 trecho(s), 23259 de 60041 chars

Lido inteiro, cortado em 60 mil caracteres antes de qualquer busca, e
recortado de novo para 23 mil: 87% do manual nunca chegou a IA.

O desenho novo tem duas pontas, e as duas moram aqui:

1. **O documento e lido e guardado INTEIRO, pagina a pagina.** A pagina e o
   que a IA cita como prova e o que o engenheiro abre para conferir.
2. **Quando o modelo le PDF, o proprio arquivo vai para ele** (`Anexo`), e o
   modelo ve o desenho cotado, a tabela com a unidade so no cabecalho e a
   curva do ventilador. `planejar_envio` decide o que cabe numa chamada; o
   resto vai como texto, na mesma chamada.

O texto extraido continua existindo mesmo quando o PDF vai inteiro: e contra
ele que a prova devolvida pela IA e conferida (`autospec_evidencia`).

Sem Tk, sem SDK de IA, sem Excel: so arquivo e texto.
"""
import os
import re
from dataclasses import dataclass, field

from sigft.core.llm.client import Anexo

# Por chamada, SOMADOS. 15 MB de arquivo viram ~20 MB em base64, que e o teto
# de requisicao com dado em linha do Gemini; 500 paginas e metade do que ele
# aceita. O que nao cabe vai como texto -- a ficha nao fica sem o documento.
LIMITE_BYTES_ANEXOS = 15 * 1024 * 1024
LIMITE_PAGINAS_ANEXOS = 500

# Caminho de TEXTO: ate aqui o documento vai inteiro; acima, o recorte por
# relevancia (`autospec_rag`) volta a agir. 300 mil caracteres sao ~75 mil
# tokens -- cabe em qualquer modelo atual com folga para a resposta, e so um
# manual de centenas de paginas passa disso. Era 24 mil ate 2026-09-24.
TETO_TEXTO_INTEIRO = 300_000

# Abaixo disto a pagina conta como "sem texto" (capa, numero solto ou pagina
# escaneada). Mesmo valor que o leitor de PDF do `autospec` sempre usou.
MIN_CHARS_PAGINA_UTIL = 40

# O que o modelo consegue LER como arquivo. TIFF fica de fora: quase nenhum
# modelo aceita, e vai pelo OCR/texto como sempre foi.
_MIMES_NATIVOS = {"application/pdf", "image/png", "image/jpeg", "image/webp"}

_MIME_POR_EXTENSAO = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".htm": "text/html",
    ".html": "text/html",
}


def mime_do_arquivo(caminho):
    extensao = os.path.splitext(str(caminho or ""))[1].lower()
    return _MIME_POR_EXTENSAO.get(extensao, "")


@dataclass
class Documento:
    """Um documento da ficha: o texto de cada pagina e, quando da, o arquivo.

    `paginado=False` quando o texto nao veio por pagina (pagina HTML, OCR em
    bloco): ai o texto vai sem marcador de pagina, porque "pagina 1" seria
    mentira.
    """

    nome: str
    origem: str = "LOCAL"
    paginas: list = field(default_factory=list)
    url: str = ""
    caminho: str = ""
    mime: str = ""
    dados: bytes | None = None
    metodo: str = ""
    paginado: bool = True

    @property
    def texto(self):
        return "\n".join(p for p in self.paginas if str(p or "").strip())

    @property
    def paginas_sem_texto(self):
        return [i for i, p in enumerate(self.paginas, start=1)
                if len(str(p or "").strip()) < MIN_CHARS_PAGINA_UTIL]

    def texto_marcado(self):
        """O documento como ele entra no contexto de texto.

        O cabecalho e o MESMO de sempre (`--- LOCAL DOC: nome ---`, e a linha
        `URL:` nos da web): `autospec_rag` e `origens_do_contexto` leem os
        dois. A novidade e o `[página N]` antes de cada pagina.
        """
        cabecalho = f"--- {self.origem} DOC: {self.nome} ---"
        if self.url:
            cabecalho += f"\nURL: {self.url}"
        if not self.paginado:
            return f"{cabecalho}\n{self.texto}"
        corpo = "\n".join(
            f"[página {numero}]\n{pagina}"
            for numero, pagina in enumerate(self.paginas, start=1)
            if str(pagina or "").strip()
        )
        return f"{cabecalho}\n{corpo}"

    @property
    def pode_ir_como_anexo(self):
        return self.mime in _MIMES_NATIVOS and (self.dados is not None or bool(self.caminho))

    def tamanho(self):
        """Bytes do arquivo, ou `None` se nao ha arquivo legivel."""
        if self.dados is not None:
            return len(self.dados)
        try:
            return os.path.getsize(self.caminho)
        except (OSError, TypeError):
            return None

    def anexo(self):
        dados = self.dados
        if dados is None:
            with open(self.caminho, "rb") as arquivo:
                dados = arquivo.read()
        # Documento da web tem o TITULO como nome ("Datasheet X - Fabricante").
        # Alguns provedores deduzem o tipo pela extensao do nome do arquivo;
        # com o `.pdf` no fim, ninguem precisa deduzir. O nome continua
        # contendo o titulo, e a conferencia de fonte casa por trecho.
        nome = self.nome
        if self.mime == "application/pdf" and not nome.lower().endswith(".pdf"):
            nome = f"{nome}.pdf"
        return Anexo(nome=nome, mime=self.mime, dados=dados)


def ler_documento(caminho, leitor, origem="LOCAL", nome=None, url="",
                  callbacks=None, guardar_bytes=False):
    """Le `caminho` pagina a pagina (`leitor.ler_paginas`) e devolve o
    `Documento`.

    `guardar_bytes=True` e para o arquivo TEMPORARIO da web, que e apagado
    logo depois da leitura: os bytes ficam na memoria para poderem ir como
    anexo. O arquivo local fica no disco e e lido so na hora de anexar.
    """
    paginas, metodo = leitor.ler_paginas(
        caminho, callbacks=callbacks, nome_exibicao=url or None)
    mime = mime_do_arquivo(caminho)
    dados = None
    if guardar_bytes and mime in _MIMES_NATIVOS:
        try:
            if os.path.getsize(caminho) <= LIMITE_BYTES_ANEXOS:
                with open(caminho, "rb") as arquivo:
                    dados = arquivo.read()
        except OSError:
            dados = None
    return Documento(
        nome=nome or os.path.basename(str(caminho)),
        origem=origem,
        paginas=list(paginas or []),
        url=url,
        caminho="" if guardar_bytes else str(caminho),
        mime=mime,
        dados=dados,
        metodo=metodo or "",
        paginado=str(metodo or "").startswith("PyMuPDF"),
    )


def planejar_envio(documentos, aceita_pdf, limite_bytes=LIMITE_BYTES_ANEXOS,
                   limite_paginas=LIMITE_PAGINAS_ANEXOS):
    """`(vao_como_arquivo, vao_como_texto)`, na ordem original.

    Os primeiros que couberem vao como arquivo -- LOCAL vem antes de WEB na
    lista, e e a prioridade certa: o manual que o usuario anexou vale mais
    que o que a busca achou. O que nao couber (ou nao for PDF/imagem) vai
    como texto.
    """
    if not aceita_pdf:
        return [], list(documentos or [])
    como_arquivo, como_texto = [], []
    bytes_usados = paginas_usadas = 0
    for documento in documentos or []:
        tamanho = documento.tamanho() if documento.pode_ir_como_anexo else None
        paginas = max(1, len(documento.paginas))
        cabe = (
            tamanho is not None
            and bytes_usados + tamanho <= limite_bytes
            and paginas_usadas + paginas <= limite_paginas
        )
        if cabe:
            como_arquivo.append(documento)
            bytes_usados += tamanho
            paginas_usadas += paginas
        else:
            como_texto.append(documento)
    return como_arquivo, como_texto


def descrever_anexos(documentos):
    """O trecho do prompt que diz a IA quais arquivos vieram junto."""
    linhas = []
    for documento in documentos:
        paginas = f"{len(documento.paginas)} página(s)" if documento.paginas else "arquivo"
        origem = f", de {documento.url}" if documento.url else ""
        linhas.append(f"- {documento.nome} ({paginas}{origem})")
    return (
        "DOCUMENTOS ANEXADOS A ESTA MENSAGEM. Leia cada um por inteiro, inclusive "
        "tabelas, desenhos cotados e gráficos, e cite-os pelo nome exato abaixo:\n"
        + "\n".join(linhas)
    )


# =============================================================================
# O fabricante escrito no PDF anexado (2026-09-24)
# =============================================================================
# Nas fichas 0084, 0086 e 0088 a planilha nao trazia fabricante e a busca web
# era pulada por falta de ancora -- com o nome do fabricante escrito no manual
# que o usuario anexou. Duas formas, as duas vistas nos PDFs reais:
#
#   Primary brand                        (ficha de distribuidor, 0086_b)
#   Georg Fischer / GF Piping Systems
#
#   © Georg Fischer Signet LLC           (rodape do datasheet, 0084)
#
# So documento LOCAL: o da web pode ser do concorrente, e e exatamente isso
# que a ancora existe para filtrar. Regex e nao IA: roda antes da busca, de
# graca, e o que nao reconhece devolve "" -- o comportamento de antes.
_RE_ROTULO_FABRICANTE = re.compile(
    r"^[ \t]*(?:manufacturer|fabricante|hersteller|fabricant|primary brand|brand|marca)"
    r"[ \t]*(?::[ \t]*(?P<mesma>[^\n]+)|\n[ \t]*(?P<seguinte>[^\n]+))",
    re.IGNORECASE | re.MULTILINE,
)
_RE_COPYRIGHT = re.compile(
    r"(?:©|\(c\)|copyright)\s*(?:\d{4}(?:\s*-\s*\d{4})?\s*)?(?P<nome>[A-Z][^\n,•|]{1,60})"
)
_SUFIXOS_SOCIETARIOS = re.compile(
    r"[\s,]+(?:LLC|Inc\.?|Corp\.?|GmbH|AG|SE|S\.?A\.?|Ltd\.?|Ltda\.?|S\.?p\.?A\.?|B\.?V\.?|Co\.?"
    r"|All rights reserved)(?![a-z])",
    re.IGNORECASE,
)


def _limpar_nome(bruto):
    nome = str(bruto or "").split(" / ")[0].strip(" .:-\t")
    # Corta no sufixo societario e em tudo depois dele: `Georg Fischer Signet
    # LLC  2019` (manual real da 0086) tinha o ano do copyright no fim.
    nome = _SUFIXOS_SOCIETARIOS.split(nome)[0]
    return re.sub(r"\s+\d{4}$", "", nome).strip(" .,:-\t")


def fabricante_dos_documentos(documentos):
    """O fabricante que o PDF anexado declara, ou `""`.

    Rotulo explicito primeiro (e o que o documento DIZ que e o fabricante),
    copyright depois. Olha as 3 primeiras e a ultima pagina de cada documento
    LOCAL -- e onde marca e rodape moram.
    """
    from sigft.services.autospec import _FABRICANTE_GENERICO  # preguicoso: evita ciclo

    locais = [d for d in documentos or () if d.origem == "LOCAL"]
    for padrao in ("rotulo", "copyright"):
        for documento in locais:
            paginas = documento.paginas[:3] + documento.paginas[-1:]
            for pagina in paginas:
                texto = str(pagina or "")
                if padrao == "rotulo":
                    achados = [m.group("mesma") or m.group("seguinte")
                               for m in _RE_ROTULO_FABRICANTE.finditer(texto)]
                else:
                    achados = [m.group("nome") for m in _RE_COPYRIGHT.finditer(texto)]
                for bruto in achados:
                    nome = _limpar_nome(bruto)
                    chave = nome.lower()
                    if (2 <= len(nome) <= 60 and re.search(r"[a-zA-Z]{2}", nome)
                            and chave not in _FABRICANTE_GENERICO):
                        return nome
    return ""

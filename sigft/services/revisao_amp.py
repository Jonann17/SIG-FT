"""A revisão das listas pelo AMP: monta o pedido de cada lista com divergência e roda as listas
uma a uma no workflow do n8n da GE (`amp/revisao_de_listas/`).

Para cada lista vão o texto do PDF da revisão em uso, o do PDF da revisão atual (cada página
marcada, para o agente citar a página) e o `_STATUS_PMIB` separado por tabulação. Os arquivos não
vão: o nó de modelo do n8n trabalha com texto, e o n8n não precisa ler o Box. Desenho:
`docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from sigft import config
from sigft.core.aconex.status_real import revisoes_iguais
from sigft.core.excel import headers
from sigft.services import status_pmib_arquivos
from sigft.services.conferencia_revisoes import (
    Conferencia,
    Download,
    ItemConferencia,
    nome_do_pdf,
    resolver_status_pmib,
)

CHAVE_DO_CABECALHO = "CÓDIGO DO MATERIAL"
LINHAS_PARA_O_CABECALHO = 10


@dataclass(frozen=True)
class TextoPdf:
    paginas: int
    texto: str


@dataclass(frozen=True)
class TabelaStatus:
    aba: str
    linha_de_revisao: str
    linhas: int          # linhas de dados, sem o cabeçalho
    tsv: str             # o cabeçalho e as linhas, colunas separadas por tabulação
    codigos_material: list[str]


@dataclass(frozen=True)
class ListaParaAmp:
    item: ItemConferencia
    status_pmib: Path | None
    pdf_em_uso: Path | None
    pdf_atual: Path | None
    revisao_atual: str
    falta: str = ""


def texto_do_pdf(caminho: Path, *, abrir=None) -> TextoPdf:
    """O texto de cada página, precedido de `--- página N ---`. PDF sem texto em nenhuma
    página (só imagem) é `ValueError`: é falha da lista, e Itaipu pede revisão."""
    if abrir is None:
        import fitz  # PyMuPDF, o mesmo que o instalador já leva

        abrir = fitz.open
    partes, com_texto = [], 0
    with abrir(str(caminho)) as documento:
        for numero, pagina in enumerate(documento, start=1):
            texto = (pagina.get_text("text") or "").strip()
            com_texto += bool(texto)
            partes.append(f"--- página {numero} ---\n{texto}")
    if not com_texto:
        raise ValueError("PDF sem texto (só imagem)")
    return TextoPdf(len(partes), "\n".join(partes))


def _celula(valor) -> str:
    """A célula como o Excel a mostraria numa colagem: inteiro sem `.0`, data dd/mm/aaaa,
    sem tabulação nem quebra de linha dentro (elas quebrariam a tabela)."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, (datetime, date)):
        valor = valor.strftime("%d/%m/%Y")
    return " ".join(str(valor).split())


def _vazia(linha) -> bool:
    return all(_celula(c) == "" for c in linha)


def status_pmib_em_tsv(caminho: Path) -> TabelaStatus:
    """A aba "Lista de Materiais" do `_STATUS_PMIB`: a linha de revisão (acima do cabeçalho)
    e, do cabeçalho até a última linha com valor, todas as colunas separadas por tabulação.
    Sem a aba ou sem o cabeçalho, `ValueError` com o motivo."""
    wb = load_workbook(caminho, read_only=True, data_only=True)
    try:
        aba = next((a for a in config.ABA_LISTA_MATERIAIS_VARIANTES if a in wb.sheetnames), None)
        if aba is None:
            raise ValueError(f"o _STATUS_PMIB não tem a aba {config.ABA_LISTA_MATERIAIS}")
        linhas = [list(linha) for linha in wb[aba].iter_rows(values_only=True)]
    finally:
        wb.close()
    indice = headers.find_header_row(linhas[:LINHAS_PARA_O_CABECALHO], CHAVE_DO_CABECALHO)
    if indice is None:
        raise ValueError(f"o _STATUS_PMIB não tem o cabeçalho ({CHAVE_DO_CABECALHO}) "
                         f"nas {LINHAS_PARA_O_CABECALHO} primeiras linhas")
    linha_de_revisao = next((_celula(c) for linha in linhas[:indice] for c in linha
                             if status_pmib_arquivos.revisao_do_texto(_celula(c)) is not None), "")
    tabela = linhas[indice:]
    while tabela and _vazia(tabela[-1]):
        tabela.pop()
    largura = max((max((i + 1 for i, c in enumerate(linha) if _celula(c)), default=0) for linha in tabela),
                  default=0)
    texto = [[_celula(c) for c in (linha + [None] * largura)[:largura]] for linha in tabela]
    coluna = texto[0].index(CHAVE_DO_CABECALHO) if CHAVE_DO_CABECALHO in texto[0] else None
    codigos = [linha[coluna] for linha in texto[1:] if coluna is not None and linha[coluna]]
    return TabelaStatus(aba, linha_de_revisao, len(texto) - 1, "\n".join("\t".join(linha) for linha in texto),
                        codigos)


def _existe(caminho: Path) -> Path | None:
    return caminho if caminho.is_file() else None


def listas_para_amp(conferencia: Conferencia, downloads: list[Download], pasta_mapeadora: Path,
                    pasta_raiz: Path | None) -> list[ListaParaAmp]:
    """As listas da conferência que têm pasta, na ordem das categorias, com os arquivos de
    cada uma. A revisão atual é a do download desta sessão (a que o Aconex devolveu); sem
    download, a ÚLTIMA REVISÃO EMITIDA da mapeadora, pelo nome do padrão na pasta."""
    baixados: dict[str, list[Download]] = {}
    for download in downloads:
        if download.caminho is not None and download.situacao in ("baixado", "ja_existia"):
            baixados.setdefault(download.codigo, []).append(download)
    levantamento: dict = {}
    resultado = []
    for itens in conferencia.por_categoria().values():
        for item in itens:
            if item.pasta is None:
                continue
            lista = item.lista
            status = (resolver_status_pmib(lista.link, pasta_mapeadora, lista.codigo, pasta_raiz,
                                           levantamento=levantamento) if lista.link else None)
            atual = next((d for d in baixados.get(lista.codigo, [])
                          if not revisoes_iguais(d.revisao, lista.revisao_em_uso)), None)
            revisao_atual = atual.revisao if atual is not None else lista.ultima_revisao
            pdf_atual = atual.caminho if atual is not None else _existe(
                item.pasta / nome_do_pdf(lista.codigo, lista.ultima_revisao))
            pdf_em_uso = (_existe(item.pasta / nome_do_pdf(lista.codigo, lista.revisao_em_uso))
                          if lista.revisao_em_uso else None)
            if status is None:
                falta = "falta: _STATUS_PMIB"
            elif pdf_atual is None:
                falta = "falta: PDF da revisão atual"
            elif lista.revisao_em_uso and pdf_em_uso is None:
                falta = "falta: PDF da revisão em uso"
            else:
                falta = ""
            resultado.append(ListaParaAmp(item, status, pdf_em_uso, pdf_atual, revisao_atual, falta))
    return resultado


def montar_pedido(lista: ListaParaAmp, versao_sigft: str, *, ler_pdf=texto_do_pdf,
                  ler_status=status_pmib_em_tsv) -> dict:
    """O JSON do modo `revisar` (§4 do desenho). Erro de leitura (`ValueError`, `OSError`)
    sobe: quem roda a lista o transforma em "falta"."""
    dados = lista.item.lista
    em_uso = None
    if lista.pdf_em_uso is not None:
        texto = ler_pdf(lista.pdf_em_uso)
        em_uso = {"arquivo": lista.pdf_em_uso.name, "paginas": texto.paginas, "texto": texto.texto}
    texto = ler_pdf(lista.pdf_atual)
    tabela = ler_status(lista.status_pmib)
    return {
        "modo": "revisar",
        "lista": {"codigo": dados.codigo, "revisao_em_uso": dados.revisao_em_uso,
                  "revisao_atual": lista.revisao_atual, "status_real": dados.status_real,
                  "status_da_revisao": dados.status_da_revisao, "categoria": lista.item.categoria},
        "revisao_em_uso": em_uso,
        "revisao_atual": {"arquivo": lista.pdf_atual.name, "paginas": texto.paginas, "texto": texto.texto},
        "status_pmib": {"arquivo": lista.status_pmib.name, "aba": tabela.aba,
                        "linha_de_revisao": tabela.linha_de_revisao, "linhas": tabela.linhas, "tsv": tabela.tsv},
        "origem": {"sigft": versao_sigft},
    }

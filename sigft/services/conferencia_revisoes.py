"""A Conferência de Revisões: a partir do que o último Gestão PMIB deixou na mapeadora,
aponta as listas cuja REVISÃO EM USO ficou para trás da ÚLTIMA REVISÃO EMITIDA,
separadas pelo STATUS REAL, e baixa do Aconex os PDFs para a pasta do `_STATUS_PMIB`.

A mapeadora é só lida, e o download nunca sobrescreve nem apaga nada. Desenho:
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §5.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from openpyxl import load_workbook

from sigft.core.aconex.cliente import ClienteAconex, ErroAconex, Versao
from sigft.core.aconex.status_real import ORDEM_DAS_CATEGORIAS, Categoria, categoria, revisoes_iguais
from sigft.services import status_pmib_arquivos
from sigft.services.pmib_manager import COLUNA_CHAVE_SOBRESSALENTES, NOME_ABA_SOBRESSALENTES, achar_aba

COL_ULTIMA_REVISAO = "ÚLTIMA REVISÃO EMITIDA"
COL_STATUS_DA_REVISAO = "STATUS DA REVISÃO"
COL_STATUS_REAL = "STATUS REAL"
COL_REVISAO_EM_USO = "REVISÃO EM USO"
COL_LINK = "LINK DA PLANILHA"
COLUNAS = (COLUNA_CHAVE_SOBRESSALENTES, COL_ULTIMA_REVISAO, COL_STATUS_DA_REVISAO,
           COL_STATUS_REAL, COL_REVISAO_EM_USO, COL_LINK)

MOTIVO_SEM_REVISAO = "sem revisão emitida no Aconex"
MOTIVO_SEM_PASTA = "_STATUS_PMIB não encontrado"
_RESERVADOS = re.compile(r'[<>:"/\\|?*]')


@dataclass(frozen=True)
class ListaNaMapeadora:
    codigo: str
    ultima_revisao: str
    status_da_revisao: str
    status_real: str
    revisao_em_uso: str
    link: str | None   # o destino do hyperlink de LINK DA PLANILHA, relativo à pasta da mapeadora


@dataclass(frozen=True)
class Mapeadora:
    caminho: Path
    salva_em: datetime   # o mtime: a conferência usa o que o último Gestão PMIB deixou
    listas: list[ListaNaMapeadora]


@dataclass(frozen=True)
class ItemConferencia:
    lista: ListaNaMapeadora
    categoria: Categoria
    pasta: Path | None
    motivo: str = ""


@dataclass
class Conferencia:
    itens: list[ItemConferencia]   # só as listas com divergência
    em_dia: int
    sem_status_pmib: int

    def por_categoria(self) -> dict[Categoria, list[ItemConferencia]]:
        """Os itens de cada categoria, na ordem da §5.2 (aprovadas primeiro), com as vazias."""
        return {c: [i for i in self.itens if i.categoria == c] for c in ORDEM_DAS_CATEGORIAS}


@dataclass(frozen=True)
class Download:
    codigo: str
    revisao: str | None
    caminho: Path | None
    situacao: Literal["baixado", "ja_existia", "falhou"]
    detalhe: str = ""


def _texto(valor) -> str:
    """O valor da célula como texto; a revisão numérica 1.0 vira '1'."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def ler_mapeadora(caminho: str | Path) -> Mapeadora:
    """As listas da aba de sobressalentes (cabeçalho na linha 2). Sem `read_only`: o
    hyperlink do LINK DA PLANILHA só vem com a planilha carregada inteira."""
    caminho = Path(caminho)
    wb = load_workbook(caminho, data_only=True)
    try:
        ws, motivo = achar_aba(wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)
        if ws is None:
            raise ValueError(f"A mapeadora não tem a aba de sobressalentes: {motivo}")
        indices = {str(c.value).strip(): i for i, c in enumerate(ws[2]) if c.value}
        faltam = [c for c in COLUNAS if c not in indices]
        if faltam:
            raise ValueError("A mapeadora não tem as colunas: " + ", ".join(faltam))
        listas = []
        for linha in ws.iter_rows(min_row=3):
            codigo = _texto(linha[indices[COLUNA_CHAVE_SOBRESSALENTES]].value)
            if not codigo:
                continue
            hyperlink = linha[indices[COL_LINK]].hyperlink
            listas.append(ListaNaMapeadora(
                codigo,
                _texto(linha[indices[COL_ULTIMA_REVISAO]].value),
                _texto(linha[indices[COL_STATUS_DA_REVISAO]].value),
                _texto(linha[indices[COL_STATUS_REAL]].value),
                _texto(linha[indices[COL_REVISAO_EM_USO]].value),
                (hyperlink.target or None) if hyperlink is not None else None))
    finally:
        wb.close()
    return Mapeadora(caminho, datetime.fromtimestamp(caminho.stat().st_mtime), listas)


def resolver_pasta(link: str, pasta_mapeadora: Path, codigo: str, pasta_raiz: Path | None,
                   *, levantamento: dict | None = None) -> Path | None:
    """A pasta do `_STATUS_PMIB` da lista: a do arquivo do link, se ele existir; senão a
    do `_STATUS_PMIB` vivo com esse código na pasta raiz; senão `None`.

    `levantamento` guarda a varredura da pasta raiz entre chamadas: ela só acontece no
    primeiro link quebrado, e uma vez por conferência."""
    alvo = Path(pasta_mapeadora) / link
    if alvo.is_file():
        return alvo.parent
    if pasta_raiz is None:
        return None
    if levantamento is None:
        levantamento = {}
    if "vivos" not in levantamento:
        levantamento["vivos"] = {cod.strip().upper(): Path(caminho)
                                 for cod, caminho in status_pmib_arquivos.listar(pasta_raiz).vivos}
    achado = levantamento["vivos"].get(codigo.strip().upper())
    return achado.parent if achado is not None else None


def conferir(mapeadora: Mapeadora, pasta_raiz: Path | None) -> Conferencia:
    """A regra da §5.2, nesta ordem: sem link conta em "Sem _STATUS_PMIB"; sem última
    revisão vai para "outros"; revisões iguais contam em "Em dia"; o resto entra pela
    categoria do STATUS REAL, ou em "outros" quando a pasta não é achada."""
    pasta_mapeadora = mapeadora.caminho.parent
    levantamento: dict = {}
    itens, em_dia, sem_status_pmib = [], 0, 0
    for lista in mapeadora.listas:
        if not lista.link:
            sem_status_pmib += 1
            continue
        pasta = resolver_pasta(lista.link, pasta_mapeadora, lista.codigo, pasta_raiz, levantamento=levantamento)
        if not lista.ultima_revisao:
            itens.append(ItemConferencia(lista, "outros", pasta, MOTIVO_SEM_REVISAO))
        elif revisoes_iguais(lista.revisao_em_uso, lista.ultima_revisao):
            em_dia += 1
        elif pasta is None:
            itens.append(ItemConferencia(lista, "outros", None, MOTIVO_SEM_PASTA))
        else:
            itens.append(ItemConferencia(lista, categoria(lista.status_real), pasta))
    return Conferencia(itens, em_dia, sem_status_pmib)


def nome_do_pdf(codigo: str, revisao: str) -> str:
    """`<código>[<revisão>].pdf`, o padrão das pastas. Só os reservados do Windows viram
    `_`; o `#`, o `&` e o `=` do código ficam."""
    return _RESERVADOS.sub("_", f"{codigo}[{revisao}]") + ".pdf"


def _gravar(cliente: ClienteAconex, pasta: Path, codigo: str, versao: Versao, detalhe: str, log_cb) -> Download:
    """Baixa a versão para a pasta com o nome do padrão. O arquivo que já existe fica
    como está: o botão nunca sobrescreve."""
    destino = pasta / nome_do_pdf(codigo, versao.revisao)
    if destino.exists():
        log_cb(f"  = {codigo}: {destino.name} já estava na pasta")
        return Download(codigo, versao.revisao, destino, "ja_existia", detalhe)
    try:
        conteudo = cliente.baixar(versao.document_id)
        with open(destino, "xb") as arquivo:   # "x": nunca sobrescreve
            arquivo.write(conteudo)
    except FileExistsError:
        return Download(codigo, versao.revisao, destino, "ja_existia", detalhe)
    except (ErroAconex, OSError) as erro:
        log_cb(f"  ✗ {codigo} [{versao.revisao}]: {erro}")
        return Download(codigo, versao.revisao, None, "falhou", str(erro))
    log_cb(f"  ✓ {codigo} → {destino.name}" + (f" ({detalhe})" if detalhe else ""))
    return Download(codigo, versao.revisao, destino, "baixado", detalhe)


def _revisao_em_uso(cliente: ClienteAconex, pasta: Path, lista: ListaNaMapeadora, log_cb) -> list[Download]:
    """O PDF da revisão em uso, se faltar na pasta (a peça 2 compara a anterior com a
    nova). O `DocumentId` sai do histórico do código; fora do histórico, avisa e segue."""
    existente = pasta / nome_do_pdf(lista.codigo, lista.revisao_em_uso)
    if existente.exists():
        return [Download(lista.codigo, lista.revisao_em_uso, existente, "ja_existia")]
    try:
        anterior = cliente.versao(lista.codigo, lista.revisao_em_uso)
    except ErroAconex as erro:
        log_cb(f"  ✗ {lista.codigo} [{lista.revisao_em_uso}]: {erro}")
        return [Download(lista.codigo, lista.revisao_em_uso, None, "falhou", str(erro))]
    if anterior is None:
        log_cb(f"  ! {lista.codigo}: a revisão em uso {lista.revisao_em_uso} não aparece no histórico do Aconex")
        return []
    return [_gravar(cliente, pasta, lista.codigo, anterior, "revisão em uso", log_cb)]


def baixar(conferencia: Conferencia, cliente: ClienteAconex, *, log_cb, progress_cb=None,
           cancelado_cb=None) -> list[Download]:
    """Para cada lista com pasta, a versão vigente, com o nome da revisão que o Aconex
    devolveu, e o PDF da revisão em uso, se faltar. `ErroAconex` vira a linha "falhou"
    e o resto continua; `cancelado_cb()` verdadeiro para o laço."""
    alvos = [(item.lista, item.pasta) for item in conferencia.itens if item.pasta is not None]
    downloads: list[Download] = []
    log_cb(f"Baixando {len(alvos)} lista(s) com divergência...")
    for n, (lista, pasta) in enumerate(alvos):
        if cancelado_cb is not None and cancelado_cb():
            log_cb("Download cancelado pelo usuário.")
            break
        if progress_cb:
            progress_cb(min(0.05 + n / len(alvos) * 0.9, 0.95))
        try:
            vigente = cliente.versao_vigente(lista.codigo)
        except ErroAconex as erro:
            log_cb(f"  ✗ {lista.codigo}: {erro}")
            downloads.append(Download(lista.codigo, None, None, "falhou", str(erro)))
            continue
        if vigente is None:
            log_cb(f"  ✗ {lista.codigo}: não encontrado no Aconex")
            downloads.append(Download(lista.codigo, None, None, "falhou", "não encontrado no Aconex"))
            continue
        detalhe = ("" if revisoes_iguais(vigente.revisao, lista.ultima_revisao)
                   else f"mapeadora desatualizada: o Aconex está na {vigente.revisao}")
        downloads.append(_gravar(cliente, pasta, lista.codigo, vigente, detalhe, log_cb))
        if lista.revisao_em_uso and not revisoes_iguais(lista.revisao_em_uso, vigente.revisao):
            downloads.extend(_revisao_em_uso(cliente, pasta, lista, log_cb))
    if progress_cb:
        progress_cb(1.0)
    return downloads

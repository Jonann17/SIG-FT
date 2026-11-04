"""Sugestões: o rascunho de e-mail da seção "Sugestões" da Configuração (2026-10-30).

Pedido do Jonathan: uma aba de sugestões, com o texto indo para um RASCUNHO do
Outlook -- nunca enviado pelo SIG-FT. Quem manda é a pessoa, e é ela quem
escolhe para quem: o "Para" sai vazio, e nenhum endereço mora no repositório
(que é público).

Dois caminhos, nesta ordem:

1. **Outlook (COM)**: `win32com.client.Dispatch("Outlook.Application")`,
   `CreateItem(0)` e `Display()`. O `pywin32` já vai no `.exe` (dependência do
   `xlwings`). Com "Anexar o log", vai uma CÓPIA do `sigft.log` feita na pasta
   temporária: o log vivo continua sendo escrito pelo app, e o Outlook o
   prenderia.
2. **`mailto:`** (sem Outlook, sem COM, ou fora do Windows): o programa de
   e-mail padrão abre com assunto e texto. O `mailto:` não leva anexo; quem
   chama mostra o caminho do log para a pessoa anexar à mão.

Sem Qt: a janela chama `abrir_rascunho` numa thread (o Outlook pode levar
segundos para subir) e mostra o `Resultado`.
"""
from __future__ import annotations

import platform
import shutil
import tempfile
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from sigft.core.dados_usuario import pasta_logs

ARQUIVO_LOG = "sigft.log"
# `olMailItem`, o item de e-mail do `CreateItem`.
OL_MAIL_ITEM = 0
# O `mailto:` passa por linha de comando e pelo registro do Windows: o Outlook
# corta o que passar de uns 2 mil caracteres. O texto que não couber fica com
# a pessoa (ela ainda o tem na caixa da Configuração).
LIMITE_CORPO_MAILTO = 1800


class SemOutlook(RuntimeError):
    """O Outlook não pôde ser aberto pelo COM (sem `pywin32`, sem Outlook, ou
    o COM recusou). Quem chama cai no `mailto:`."""


@dataclass(frozen=True)
class Rascunho:
    assunto: str
    corpo: str
    anexo: Path | None = None


@dataclass(frozen=True)
class Resultado:
    """`via` é "outlook" ou "mailto". Com `mailto` e o log pedido, `log` é o
    arquivo que a pessoa anexa à mão."""
    via: str
    log: Path | None = None


def caminho_do_log() -> Path:
    """O `Documentos\\SIG-FT\\logs\\sigft.log` (`core/saida_log.py`)."""
    return Path(pasta_logs()) / ARQUIVO_LOG


def copiar_log(origem: Path | None = None, destino: Path | None = None) -> Path | None:
    """Uma cópia do log na pasta temporária, para anexar. `None` se não há log
    (o app rodando fora do `.exe` não o escreve) ou se a cópia falhar."""
    origem = Path(origem) if origem is not None else caminho_do_log()
    if not origem.is_file():
        return None
    pasta = Path(destino) if destino is not None else Path(tempfile.gettempdir()) / "SIG-FT_Sugestoes"
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        copia = pasta / f"sigft_{time.strftime('%Y%m%d_%H%M%S')}.log"
        shutil.copyfile(origem, copia)
        return copia
    except OSError:
        return None


def montar(texto: str, *, versao: str, idioma: str, sistema: str | None = None,
           anexo: Path | None = None) -> Rascunho:
    """O assunto e o corpo do e-mail. O fim do corpo diz versão, idioma e
    sistema: é o que se pergunta primeiro a quem sugere."""
    sistema = sistema if sistema is not None else f"{platform.system()} {platform.release()}".strip()
    corpo = (f"{texto.strip()}\n\n"
             f"--\n"
             f"SIG-FT v{versao} | idioma: {idioma} | {sistema}")
    return Rascunho(assunto=f"SIG-FT v{versao} - sugestão", corpo=corpo, anexo=anexo)


def link_mailto(rascunho: Rascunho) -> str:
    """O `mailto:` sem destinatário, com assunto e corpo codificados."""
    corpo = rascunho.corpo
    if len(corpo) > LIMITE_CORPO_MAILTO:
        corpo = corpo[:LIMITE_CORPO_MAILTO].rstrip() + "\n(...)"
    return f"mailto:?subject={quote(rascunho.assunto)}&body={quote(corpo)}"


def _com_padrao():
    """`(win32com.client, pythoncom)`, ou `SemOutlook`."""
    try:
        import pythoncom
        import win32com.client
    except ImportError as erro:
        raise SemOutlook(f"pywin32 indisponivel: {erro}") from erro
    return win32com.client, pythoncom


def abrir_no_outlook(rascunho: Rascunho, *, com: Callable | None = None) -> None:
    """Abre o rascunho no Outlook (`Display`, nunca `Send`). Roda numa thread,
    então inicia o COM nela. Levanta `SemOutlook` em qualquer falha."""
    cliente, pythoncom = (com or _com_padrao)()
    pythoncom.CoInitialize()
    try:
        try:
            outlook = cliente.Dispatch("Outlook.Application")
            item = outlook.CreateItem(OL_MAIL_ITEM)
            item.Subject = rascunho.assunto
            item.Body = rascunho.corpo
            if rascunho.anexo is not None:
                item.Attachments.Add(str(rascunho.anexo))
            item.Display(False)
        except Exception as erro:  # noqa: BLE001 -- qualquer recusa do COM vira o mailto
            raise SemOutlook(f"o Outlook nao abriu o rascunho: {erro}") from erro
    finally:
        pythoncom.CoUninitialize()


def abrir_rascunho(texto: str, *, versao: str, idioma: str, anexar_log: bool,
                   log_cb: Callable[[str], None] = print,
                   com: Callable | None = None,
                   abrir_link: Callable[[str], object] = webbrowser.open,
                   origem_do_log: Path | None = None,
                   pasta_temporaria: Path | None = None) -> Resultado:
    """O caminho inteiro: copia o log (se pedido), tenta o Outlook e cai no
    `mailto:`. Levanta só se nem o `mailto:` abrir."""
    anexo = copiar_log(origem_do_log, pasta_temporaria) if anexar_log else None
    if anexar_log and anexo is None:
        log_cb("[sugestoes] sem sigft.log para anexar")
    rascunho = montar(texto, versao=versao, idioma=idioma, anexo=anexo)
    try:
        abrir_no_outlook(rascunho, com=com)
        log_cb("[sugestoes] rascunho aberto no Outlook")
        return Resultado(via="outlook")
    except SemOutlook as erro:
        log_cb(f"[sugestoes] {erro}; vai o mailto")
    if not abrir_link(link_mailto(rascunho)):
        raise RuntimeError("nenhum programa de e-mail abriu o rascunho")
    log_cb("[sugestoes] rascunho aberto pelo mailto")
    log = Path(origem_do_log) if origem_do_log is not None else caminho_do_log()
    return Resultado(via="mailto", log=log if anexar_log and log.is_file() else None)

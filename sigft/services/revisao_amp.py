"""A revisão das listas pelo AMP: o pedido de cada lista com divergência (os arquivos como estão
e a mensagem) e a rodada, uma lista por vez, no workflow do n8n da GE (`amp/revisao_de_listas/`).

Desde 2026-11-03 o agente (o "Spare Parts Document Reviewer", criado no AMP) recebe os dois PDFs
e o `_STATUS_PMIB` como estão, como o Luan fazia no chat do AMP: o SIG-FT não lê mais o conteúdo
deles. A rodada escreve no log o que vai e o que voltou de cada lista, com o número da execução do
n8n, e um batimento enquanto o agente trabalha (o Luan, em 03/11: "precisamos ver o que está
acontecendo"). Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`.
"""
from __future__ import annotations

import json
import re
import textwrap
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from sigft.core import dados_usuario
from sigft.core.aconex.status_real import revisoes_iguais
from sigft.core.amp.cliente import RespostaAmp
from sigft.services.conferencia_revisoes import (
    Conferencia,
    Download,
    ItemConferencia,
    nome_do_pdf,
    resolver_status_pmib,
)

CORPO_NO_DIAGNOSTICO = 1500   # caracteres do corpo da resposta que o diagnóstico mostra
ERRO_NO_DIAGNOSTICO = 300     # o erro do workflow, cortado: ele pode repetir a saída do agente
BATIMENTO = 30.0              # segundos entre as linhas de "esperando o AMP"
CAMPOS_DO_WORKFLOW = ("ok", "modo", "etapa", "erro", "execucao", "versao_workflow", "arquivos")
CAMPO_EM_USO, CAMPO_ATUAL, CAMPO_STATUS = "revisao_em_uso", "revisao_atual", "status_pmib"
ARQUIVOS_DO_REPOSITORIO = (
    ("sigft/services/revisao_amp.py", "a rodada, o pedido e este diagnóstico"),
    ("sigft/core/amp/cliente.py", "a chamada ao webhook"),
    ("amp/revisao_de_listas/agente.md", "o agente no AMP (cópia do goal e do system prompt)"),
    ("amp/revisao_de_listas/workflow_revisao_de_listas.json", "o workflow do n8n (gerado por gerar_workflow.py)"),
    ("docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md", "o desenho"),
)
_RESERVADOS = re.compile(r'[<>:"/\\|?*]')   # os mesmos de conferencia_revisoes.nome_do_pdf
_TEM_HTML = re.compile(r"<html|<table", re.IGNORECASE)


@dataclass(frozen=True)
class ListaParaAmp:
    item: ItemConferencia
    status_pmib: Path | None
    pdf_em_uso: Path | None
    pdf_atual: Path | None
    revisao_atual: str
    falta: str = ""


@dataclass(frozen=True)
class PedidoAmp:
    """O que vai ao workflow: os campos do formulário (`modo` e `mensagem`) e os arquivos, por
    campo: `revisao_em_uso` (só quando a lista tem revisão em uso), `revisao_atual` e
    `status_pmib`."""
    campos: dict[str, str]
    arquivos: dict[str, Path]


@dataclass(frozen=True)
class ResultadoAmp:
    lista: ListaParaAmp
    situacao: Literal["pronto", "falhou", "falta", "parado"]
    html: Path | None
    detalhe: str
    diagnostico: str = ""   # só na falha: o texto para colar numa conversa nova


def _mm_ss(segundos: float) -> str:
    inteiro = int(segundos)
    return f"{inteiro // 60}:{inteiro % 60:02d}"


def _duracao(segundos: float) -> str:
    """`0,8 s` abaixo de um minuto; `3:12` daí para cima."""
    return f"{segundos:.1f} s".replace(".", ",") if segundos < 60 else _mm_ss(segundos)


def _tamanho(caminho: Path) -> str:
    """`412 KB`, `1,8 MB`; o arquivo que não se lê diz isso."""
    try:
        bytes_ = caminho.stat().st_size
    except OSError:
        return "tamanho não lido"
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{round(bytes_ / 1024)} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB".replace(".", ",")


def _curto(texto, limite: int) -> str:
    texto = str(texto or "")
    return texto if len(texto) <= limite else f"{texto[:limite]}… (+{len(texto) - limite} caracteres)"


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


def mensagem_da_lista(lista: ListaParaAmp, *, hoje: date | None = None) -> str:
    """A mensagem que o agente recebe com os arquivos: a lista, as revisões, o nome de cada
    arquivo e a data de hoje (a linha de revisão nova leva a DATA DE ALTERAÇÃO, e o agente não
    sabe que dia é). É o texto do teste de 03/11 (§5.2 do desenho)."""
    dados = lista.item.lista
    if lista.pdf_em_uso is not None:
        em_uso = f"Revisão em uso: {dados.revisao_em_uso} (arquivo {lista.pdf_em_uso.name})."
    else:
        em_uso = ("Revisão em uso: nenhuma (a lista ainda não tem revisão em uso: compare só a revisão "
                  "atual com o controle).")
    return (f"Lista: {dados.codigo}. {em_uso} Revisão atual: {lista.revisao_atual} "
            f"(arquivo {lista.pdf_atual.name}). Controle: {lista.status_pmib.name}. "
            f"Data de hoje: {(hoje or date.today()):%d/%m/%Y}. Faça a revisão.")


def montar_pedido(lista: ListaParaAmp, *, hoje: date | None = None) -> PedidoAmp:
    """Os arquivos como estão na pasta da lista e a mensagem. Nada é lido dos arquivos."""
    arquivos: dict[str, Path] = {}
    if lista.pdf_em_uso is not None:
        arquivos[CAMPO_EM_USO] = lista.pdf_em_uso
    arquivos[CAMPO_ATUAL] = lista.pdf_atual
    arquivos[CAMPO_STATUS] = lista.status_pmib
    return PedidoAmp({"modo": "revisar", "mensagem": mensagem_da_lista(lista, hoje=hoje)}, arquivos)


def nome_do_html(codigo: str, em_uso: str, atual: str) -> str:
    """`<código>[<em uso>-<atual>] revisao AMP.html`; sem revisão em uso, `[-<atual>]`. Só os
    reservados do Windows viram `_`."""
    return _RESERVADOS.sub("_", f"{codigo}[{em_uso}-{atual}] revisao AMP") + ".html"


def gravar_html(pasta: Path, nome: str, html: str) -> Path:
    """Grava num arquivo novo; se o nome existir, acrescenta " (2)", " (3)"... O `"x"` do
    `open` garante que nada é sobrescrito, nem o que alguém gravou no meio do caminho."""
    base = Path(nome)
    numero = 1
    while True:
        destino = pasta / (nome if numero == 1 else f"{base.stem} ({numero}){base.suffix}")
        try:
            with open(destino, "x", encoding="utf-8", newline="") as arquivo:
                arquivo.write(html)
            return destino
        except FileExistsError:
            numero += 1


# ------------------------------------------------------------------ o diagnóstico

def _corpo(resposta: RespostaAmp) -> str:
    """Do JSON do workflow, só os campos dele (o `erro` cortado): o `html` pode repetir o
    documento, e dele vai o tamanho. De outra coisa (a página de um proxy), o texto como veio."""
    try:
        dados = json.loads(resposta.corpo)
    except ValueError:
        dados = None
    if not isinstance(dados, dict):
        return resposta.corpo

    def campo(chave, valor):
        if chave not in CAMPOS_DO_WORKFLOW:
            return f"<{len(str(valor))} caracteres, fora daqui>"
        return _curto(valor, ERRO_NO_DIAGNOSTICO) if chave == "erro" else valor

    return json.dumps({chave: campo(chave, valor) for chave, valor in dados.items()}, ensure_ascii=False)


def _numeros_do_pedido(pedido: PedidoAmp | None) -> list[str]:
    if pedido is None:
        return ["  nada: o pedido não chegou a ser montado"]
    linhas = [f"  {campo}: {caminho.name}, {_tamanho(caminho)}" for campo, caminho in pedido.arquivos.items()]
    linhas.append(f"  mensagem: {len(pedido.campos.get('mensagem', ''))} caracteres")
    return linhas


def _numeros_da_resposta(resposta: RespostaAmp | None) -> list[str]:
    if resposta is None:
        return ["  nenhuma: a lista não chegou a ser mandada"]
    http = f"HTTP {resposta.http}" if resposta.http is not None else "sem resposta HTTP"
    linhas = [f"  {http} em {_duracao(resposta.segundos)}"]
    if resposta.execucao:
        linhas.append(f"  execução do n8n: {resposta.execucao}")
    if resposta.arquivos:
        linhas.append(f"  arquivos que chegaram ao agente: {', '.join(resposta.arquivos)}")
    if resposta.erro:
        linhas.append(f"  erro: {_curto(resposta.erro, ERRO_NO_DIAGNOSTICO)}")
    corpo = _corpo(resposta)[:CORPO_NO_DIAGNOSTICO]
    linhas.append(f"  corpo (até {CORPO_NO_DIAGNOSTICO} caracteres):")
    linhas.append(textwrap.indent(corpo, "    ") if corpo.strip() else "    (vazio)")
    return linhas


def diagnostico(lista: ListaParaAmp, pedido: PedidoAmp | None, resposta: RespostaAmp | None, *, url: str,
                chave_posta: bool, versao_sigft: str, erro: str = "") -> str:
    """O texto para colar numa conversa nova (o Claude na web, no PC da GE, com o repositório do
    SIG-FT), §5.4 do desenho: do que foi mandado, os nomes e os tamanhos; da resposta, o corpo
    cortado e só os campos do workflow; o endereço, sem a chave. Nunca vai conteúdo de documento."""
    dados = lista.item.lista
    linhas = [
        "SIG-FT · Revisão no AMP · diagnóstico",
        f"SIG-FT {versao_sigft} · {datetime.now():%d/%m/%Y %H:%M:%S}",
        "",
        f"Lista: {dados.codigo} ({lista.item.categoria})",
        f"  revisão em uso: {dados.revisao_em_uso or 'nenhuma'} · revisão atual: {lista.revisao_atual}",
        f"  STATUS REAL: {dados.status_real or '(vazio)'} · STATUS DA REVISÃO: {dados.status_da_revisao or '(vazio)'}",
        "",
        "Chamada",
        f"  endereço: {url or '(não configurado)'}",
        f"  chave: {'posta' if chave_posta else 'não posta'}",
        "",
        "O que foi mandado (os nomes e os tamanhos: o conteúdo dos documentos fica fora daqui)",
        *_numeros_do_pedido(pedido),
        "",
        "Resposta",
        *_numeros_da_resposta(resposta),
    ]
    if erro:
        linhas += ["", "Erro no SIG-FT", textwrap.indent(erro, "  ")]
    linhas += ["", "Onde está o código (repositório luanccozer/SIG-FT)",
               *(f"  {caminho}: {papel}" for caminho, papel in ARQUIVOS_DO_REPOSITORIO)]
    return "\n".join(linhas) + "\n"


# ------------------------------------------------------------------ a rodada

def _com_batimento(acao, log_cb, intervalo: float):
    """Roda `acao()` e, enquanto ela não volta, escreve uma linha a cada `intervalo` segundos:
    o agente leva minutos, e o console mudo parece travado (§5.6 do desenho)."""
    if not intervalo or intervalo <= 0:
        return acao()
    parar = threading.Event()
    inicio = time.monotonic()

    def bater() -> None:
        while not parar.wait(intervalo):
            log_cb(f"    … {_mm_ss(time.monotonic() - inicio)} esperando o AMP")

    fio = threading.Thread(target=bater, name="amp-batimento", daemon=True)
    fio.start()
    try:
        return acao()
    finally:
        parar.set()
        fio.join(timeout=2)


def _revisoes(lista: ListaParaAmp) -> str:
    em_uso = lista.item.lista.revisao_em_uso
    return (f"em uso {em_uso} → atual {lista.revisao_atual}" if em_uso
            else f"sem revisão em uso → atual {lista.revisao_atual}")


def _linha_da_resposta(resposta: RespostaAmp) -> str:
    http = f"HTTP {resposta.http}" if resposta.http is not None else "sem resposta HTTP"
    partes = [f"{http} em {_duracao(resposta.segundos)}"]
    if resposta.execucao:
        partes.append(f"execução {resposta.execucao}")
    if resposta.arquivos:
        partes.append(f"o workflow recebeu {len(resposta.arquivos)} arquivo(s)")
    return "    resposta: " + " · ".join(partes)


def _detalhe(resposta: RespostaAmp) -> str:
    etapa = resposta.dados.get("etapa")
    erro = resposta.erro or "falha sem mensagem"
    return f"{erro} (etapa {etapa})" if etapa else erro


def _falhou(lista: ListaParaAmp, pedido: PedidoAmp | None, resposta: RespostaAmp | None, detalhe: str, log_cb, *,
            erro: str = "", **contexto) -> ResultadoAmp:
    detalhe = detalhe or "falha sem mensagem"
    log_cb(f"    ✗ falhou: {detalhe}")
    return ResultadoAmp(lista, "falhou", None, detalhe, diagnostico(lista, pedido, resposta, erro=erro, **contexto))


def _revisar(lista: ListaParaAmp, cliente, montar, log_cb, batimento: float, **contexto) -> ResultadoAmp:
    dados = lista.item.lista
    if lista.falta:
        log_cb(f"    - {lista.falta}")
        return ResultadoAmp(lista, "falta", None, lista.falta)
    try:
        pedido = montar(lista)
    except Exception as erro:  # noqa: BLE001 -- defeito do SIG-FT: vira diagnóstico, e as outras seguem
        return _falhou(lista, None, None, f"ao montar o pedido: {type(erro).__name__}: {erro}", log_cb,
                       erro="".join(traceback.format_exception(erro)).rstrip(), **contexto)
    log_cb("    vai: " + ", ".join(f"{caminho.name} ({_tamanho(caminho)})" for caminho in pedido.arquivos.values()))
    log_cb("    enviado; o agente está lendo (costuma levar alguns minutos)")
    resposta = _com_batimento(lambda: cliente.enviar(pedido.campos, pedido.arquivos), log_cb, batimento)
    log_cb(_linha_da_resposta(resposta))
    if not resposta.ok:
        return _falhou(lista, pedido, resposta, _detalhe(resposta), log_cb, **contexto)
    if not _TEM_HTML.search(resposta.html):
        return _falhou(lista, pedido, resposta, "o agente não devolveu HTML", log_cb, **contexto)
    if resposta.arquivos and len(resposta.arquivos) < len(pedido.arquivos):
        return _falhou(lista, pedido, resposta,
                       f"o workflow recebeu {len(resposta.arquivos)} de {len(pedido.arquivos)} arquivo(s)",
                       log_cb, **contexto)
    nome = nome_do_html(dados.codigo, dados.revisao_em_uso, lista.revisao_atual)
    try:
        caminho = gravar_html(lista.item.pasta, nome, resposta.html)
    except OSError as erro:
        return _falhou(lista, pedido, resposta, f"o HTML não foi gravado: {erro}", log_cb,
                       erro=f"o HTML não foi gravado: {erro}", **contexto)
    log_cb(f"    ✓ HTML gravado: {caminho.name} ({_tamanho(caminho)})")
    return ResultadoAmp(lista, "pronto", caminho, caminho.name)


def _gravar_diagnostico(resultado: ResultadoAmp, log_cb) -> None:
    """Em `logs\\amp\\<AAAAMMDD-HHMMSS> <código>.txt`. Não gravar não para a rodada."""
    nome = _RESERVADOS.sub("_", f"{datetime.now():%Y%m%d-%H%M%S} {resultado.lista.item.lista.codigo}") + ".txt"
    try:
        pasta = dados_usuario.pasta_logs() / "amp"
        pasta.mkdir(parents=True, exist_ok=True)
        log_cb(f"    diagnóstico em {gravar_html(pasta, nome, resultado.diagnostico)}")
    except OSError as erro:
        log_cb(f"    ! o diagnóstico não foi gravado: {erro}")


def _cabecalho(listas, desmarcadas: list[str], com_falta: list[str], url: str, chave_posta: bool) -> list[str]:
    linhas = [f"Revisão no AMP: {len(listas)} lista(s) marcada(s)"]
    if desmarcadas:
        linhas.append(f"  desmarcadas, ficam fora: {len(desmarcadas)} ({', '.join(desmarcadas)})")
    if com_falta:
        linhas.append(f"  com falta, ficam fora: {len(com_falta)} ({', '.join(com_falta)})")
    linhas.append(f"Webhook: {url or '(não configurado)'} · chave {'posta' if chave_posta else 'não posta'}")
    return linhas


def _ping_falhou(listas, ping: RespostaAmp, log_cb, resultado_cb, gravar_diagnostico: bool,
                 **contexto) -> list[ResultadoAmp]:
    """Sem ping, nada vai: cada lista volta "falhou" com o motivo, e o diagnóstico vai só na
    primeira (são todos iguais)."""
    log_cb(f"FALHOU  Ping: {ping.erro}")
    log_cb("Nada foi mandado: confira o webhook (botão Webhook…) e o Testar conexão.")
    resultados = []
    for n, lista in enumerate(listas):
        texto = diagnostico(lista, None, ping, **contexto) if n == 0 else ""
        resultado = ResultadoAmp(lista, "falhou", None, f"o ping falhou: {ping.erro}", texto)
        if texto and gravar_diagnostico:
            _gravar_diagnostico(resultado, log_cb)
        resultados.append(resultado)
        if resultado_cb is not None:
            resultado_cb(resultado)
    return resultados


def revisar_listas(listas: list[ListaParaAmp], cliente, *, versao_sigft: str, url: str, chave_posta: bool, log_cb,
                   progress_cb=None, cancelado_cb=None, resultado_cb=None, gravar_diagnostico: bool = True,
                   montar=montar_pedido, desmarcadas=(), com_falta=(), batimento: float = BATIMENTO
                   ) -> list[ResultadoAmp]:
    """Uma lista por vez (§5 do desenho). Antes, o `ping`: falhando, nada é mandado. A lista com
    falta não é chamada; a falha de uma não para as outras e deixa o diagnóstico em
    `logs\\amp\\`; `cancelado_cb()` é lido entre as listas, e as que sobram ficam "parado".
    `resultado_cb(resultado)` recebe cada lista assim que ela acaba. `desmarcadas` e `com_falta`
    (os códigos que ficaram fora) só vão para o começo do log."""
    contexto = {"versao_sigft": versao_sigft, "url": url, "chave_posta": chave_posta}
    inicio = time.monotonic()
    for linha in _cabecalho(listas, list(desmarcadas), list(com_falta), url, chave_posta):
        log_cb(linha)
    ping = cliente.ping()
    if not ping.ok:
        resultados = _ping_falhou(listas, ping, log_cb, resultado_cb, gravar_diagnostico, **contexto)
        if progress_cb:
            progress_cb(1.0)
        return resultados
    log_cb(f"Ping: workflow {ping.versao_workflow or '(sem versão)'} ({_duracao(ping.segundos)}, "
           f"execução {ping.execucao or '?'})")
    resultados: list[ResultadoAmp] = []
    parado = False
    for n, lista in enumerate(listas):
        if not parado and cancelado_cb is not None and cancelado_cb():
            parado = True
            log_cb("Revisão no AMP parada pelo usuário.")
        if parado:
            resultado = ResultadoAmp(lista, "parado", None, "parado antes de ir ao AMP")
        else:
            if progress_cb:
                progress_cb(min(0.05 + n / len(listas) * 0.9, 0.95))
            log_cb(f"[{n + 1}/{len(listas)}] {lista.item.lista.codigo} · {_revisoes(lista)}")
            resultado = _revisar(lista, cliente, montar, log_cb, batimento, **contexto)
            if resultado.diagnostico and gravar_diagnostico:
                _gravar_diagnostico(resultado, log_cb)
        resultados.append(resultado)
        if resultado_cb is not None:
            resultado_cb(resultado)
    if progress_cb:
        progress_cb(1.0)
    contagem = {s: sum(r.situacao == s for r in resultados) for s in ("pronto", "falhou", "falta", "parado")}
    log_cb(f"Fim: {contagem['pronto']} HTML pronto(s), {contagem['falhou']} falha(s), {contagem['falta']} com falta, "
           f"{contagem['parado']} parada(s), em {_mm_ss(time.monotonic() - inicio)}")
    return resultados


def diagnosticos_para_copiar(resultados: list[ResultadoAmp]) -> str:
    """O texto do "Copiar diagnóstico": uma abertura para a conversa nova (o Claude na web, com o
    repositório do SIG-FT) e o diagnóstico de cada lista que falhou. Sem falha, vazio."""
    falhas = [r.diagnostico for r in resultados if r.diagnostico]
    if not falhas:
        return ""
    abertura = (f"SIG-FT · Revisão no AMP: {len(falhas)} lista(s) falharam nesta rodada.\n"
                "Cole este texto numa conversa nova com o Claude, com o repositório luanccozer/SIG-FT, e peça "
                "para achar a causa. Não vai texto de documento nem a chave do webhook.\n")
    separador = "\n" + "=" * 72 + "\n\n"
    return abertura + separador + separador.join(falhas)


def _linha(marca: str, nome: str, detalhe: str) -> str:
    """No formato do diagnóstico do Aconex: `OK      Ping: workflow 2026-11-03`."""
    return f"{marca:<8}{nome}: {detalhe}"


def testar_conexao(cliente) -> list[str]:
    """As linhas do "Testar conexão com o AMP": o `ping` vê a rede, a chave e o workflow
    publicado, sem chamar o agente e sem mandar documento."""
    ping = cliente.ping()
    if not ping.ok:
        return [_linha("FALHOU", "Ping", f"{ping.erro} ({_duracao(ping.segundos)})")]
    http = f"HTTP {ping.http}" if ping.http is not None else "sem resposta HTTP"
    return [_linha("OK", "Ping", f"workflow {ping.versao_workflow or '(sem versão)'} "
                                 f"({http}, {_duracao(ping.segundos)}, execução {ping.execucao or '?'})")]

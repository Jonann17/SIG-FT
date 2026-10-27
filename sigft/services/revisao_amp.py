"""A revisão das listas pelo AMP: monta o pedido de cada lista com divergência e roda as listas
uma a uma no workflow do n8n da GE (`amp/revisao_de_listas/`).

Para cada lista vão o texto do PDF da revisão em uso, o do PDF da revisão atual (cada página
marcada, para o agente citar a página) e o `_STATUS_PMIB` separado por tabulação. Os arquivos não
vão: o nó de modelo do n8n trabalha com texto, e o n8n não precisa ler o Box. Desenho:
`docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`.
"""
from __future__ import annotations

import json
import re
import textwrap
import traceback
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from openpyxl import load_workbook

from sigft import config
from sigft.core import dados_usuario
from sigft.core.aconex.status_real import revisoes_iguais
from sigft.core.amp.cliente import RespostaAmp
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
CORPO_NO_DIAGNOSTICO = 1500   # caracteres do corpo da resposta que o diagnóstico mostra
MATERIAIS_NO_ECO = 10
TRECHO_MINIMO = 20            # linha do documento que o diagnóstico procura no que o AMP devolveu
CAMPOS_DO_WORKFLOW = ("ok", "modo", "etapa", "erro", "execucao", "versao_workflow")
ARQUIVOS_DO_REPOSITORIO = (
    ("sigft/services/revisao_amp.py", "a rodada, o pedido e este diagnóstico"),
    ("sigft/core/amp/cliente.py", "a chamada ao webhook"),
    ("amp/revisao_de_listas/pedido.md", "o pedido ao agente"),
    ("amp/revisao_de_listas/workflow_revisao_de_listas.json", "o workflow do n8n (gerado por gerar_workflow.py)"),
    ("docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md", "o desenho"),
)
_RESERVADOS = re.compile(r'[<>:"/\\|?*]')   # os mesmos de conferencia_revisoes.nome_do_pdf


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


@dataclass(frozen=True)
class ResultadoAmp:
    lista: ListaParaAmp
    situacao: Literal["pronto", "falhou", "falta", "parado"]
    html: Path | None
    detalhe: str
    diagnostico: str = ""   # só na falha: o texto para colar numa conversa nova


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


def _trechos_do_documento(pedido: dict | None) -> list[str]:
    """As linhas dos PDFs e as células do `_STATUS_PMIB` que foram no pedido, a partir de
    `TRECHO_MINIMO` caracteres e das mais longas para as mais curtas: o que o diagnóstico
    procura e tira do que o AMP devolveu (o erro do nó de modelo pode repetir o documento)."""
    if not pedido:
        return []
    textos = [str((pedido.get(chave) or {}).get("texto") or "") for chave in ("revisao_em_uso", "revisao_atual")]
    status = pedido.get("status_pmib") or {}
    textos += [str(status.get("linha_de_revisao") or ""), *str(status.get("tsv") or "").split("\t")]
    trechos = {linha.strip() for texto in textos for linha in texto.splitlines()}
    return sorted((t for t in trechos if len(t) >= TRECHO_MINIMO), key=len, reverse=True)


def _sem_trechos(texto: str, trechos: list[str]) -> str:
    for trecho in trechos:
        if trecho in texto:
            texto = texto.replace(trecho, "<trecho do documento>")
    return texto


def _corpo(resposta: RespostaAmp) -> str:
    """Do JSON do workflow, só os campos dele: o `html` e o `texto` podem repetir o documento,
    e deles vai o tamanho. De outra coisa (a página de um proxy), o texto como veio."""
    try:
        dados = json.loads(resposta.corpo)
    except ValueError:
        dados = None
    if not isinstance(dados, dict):
        return resposta.corpo
    return json.dumps({chave: valor if chave in CAMPOS_DO_WORKFLOW else f"<{len(str(valor))} caracteres, fora daqui>"
                       for chave, valor in dados.items()}, ensure_ascii=False)


def _numeros_do_pedido(pedido: dict | None) -> list[str]:
    if not pedido:
        return ["  nada: o pedido não chegou a ser montado"]
    linhas = []
    for chave, rotulo in (("revisao_em_uso", "revisão em uso"), ("revisao_atual", "revisão atual")):
        parte = pedido.get(chave)
        linhas.append(f"  {rotulo}: {parte['arquivo']}, {parte['paginas']} páginas, {len(str(parte['texto']))} "
                      "caracteres" if parte else f"  {rotulo}: nenhuma")
    status = pedido.get("status_pmib") or {}
    linhas.append(f"  _STATUS_PMIB: {status.get('arquivo')}, aba {status.get('aba')}, {status.get('linhas')} linhas, "
                  f"{len(str(status.get('tsv') or ''))} caracteres")
    linhas.append(f"  o pedido inteiro: {len(json.dumps(pedido, ensure_ascii=False))} caracteres")
    return linhas


def _numeros_da_resposta(resposta: RespostaAmp | None, trechos: list[str]) -> list[str]:
    if resposta is None:
        return ["  nenhuma: a lista não chegou a ser mandada"]
    http = f"HTTP {resposta.http}" if resposta.http is not None else "sem resposta HTTP"
    linhas = [f"  {http} em {resposta.segundos:.1f} s"]
    if resposta.execucao:
        linhas.append(f"  execução do n8n: {resposta.execucao}")
    if resposta.erro:
        linhas.append(f"  erro: {_sem_trechos(resposta.erro, trechos)}")
    corpo = _sem_trechos(_corpo(resposta), trechos)[:CORPO_NO_DIAGNOSTICO]
    linhas.append(f"  corpo (até {CORPO_NO_DIAGNOSTICO} caracteres):")
    linhas.append(textwrap.indent(corpo, "    ") if corpo.strip() else "    (vazio)")
    return linhas


def diagnostico(lista: ListaParaAmp, pedido: dict | None, resposta: RespostaAmp | None, *, url: str,
                chave_posta: bool, versao_sigft: str, erro: str = "") -> str:
    """O texto para colar numa conversa nova (o Claude na web, no PC da GE, com o repositório
    do SIG-FT), §8 do desenho: do que foi mandado, só os números; da resposta, o corpo cortado
    e só os campos do workflow; o endereço, sem a chave. Nunca vai texto de documento."""
    dados = lista.item.lista
    trechos = _trechos_do_documento(pedido)
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
        "O que foi mandado (só os números: o texto dos documentos fica fora daqui)",
        *_numeros_do_pedido(pedido),
        "",
        "Resposta",
        *_numeros_da_resposta(resposta, trechos),
    ]
    if erro:
        linhas += ["", "Erro no SIG-FT", textwrap.indent(_sem_trechos(erro, trechos), "  ")]
    linhas += ["", "Onde está o código (repositório luanccozer/SIG-FT)",
               *(f"  {caminho}: {papel}" for caminho, papel in ARQUIVOS_DO_REPOSITORIO)]
    return "\n".join(linhas) + "\n"


def _resumo_do_pedido(pedido: dict) -> str:
    paginas = [str(parte["paginas"]) for parte in (pedido.get("revisao_em_uso"), pedido.get("revisao_atual")) if parte]
    linhas = (pedido.get("status_pmib") or {}).get("linhas")
    return f"{' + '.join(paginas)} página(s), {linhas} linha(s) do _STATUS_PMIB"


def _falhou(lista: ListaParaAmp, pedido: dict | None, resposta: RespostaAmp | None, detalhe: str, log_cb, *,
            erro: str = "", **contexto) -> ResultadoAmp:
    detalhe = _sem_trechos(detalhe, _trechos_do_documento(pedido)) or "falha sem mensagem"
    log_cb(f"  ✗ {lista.item.lista.codigo}: {detalhe}")
    return ResultadoAmp(lista, "falhou", None, detalhe, diagnostico(lista, pedido, resposta, erro=erro, **contexto))


def _revisar(lista: ListaParaAmp, cliente, montar, log_cb, **contexto) -> ResultadoAmp:
    dados = lista.item.lista
    if lista.falta:
        log_cb(f"  - {dados.codigo}: {lista.falta}")
        return ResultadoAmp(lista, "falta", None, lista.falta)
    try:
        pedido = montar(lista, contexto["versao_sigft"])
    except (ValueError, OSError, zipfile.BadZipFile) as erro:
        log_cb(f"  - {dados.codigo}: falta: {erro}")
        return ResultadoAmp(lista, "falta", None, f"falta: {erro}")
    except Exception as erro:  # noqa: BLE001 -- PDF corrompido (o PyMuPDF levanta RuntimeError) ou defeito
        return _falhou(lista, None, None, f"ao montar o pedido: {type(erro).__name__}: {erro}", log_cb,
                       erro="".join(traceback.format_exception(erro)).rstrip(), **contexto)
    log_cb(f"  → {dados.codigo}: no AMP ({_resumo_do_pedido(pedido)})...")
    resposta = cliente.revisar(pedido)
    if not resposta.ok:
        return _falhou(lista, pedido, resposta, resposta.erro, log_cb, **contexto)
    nome = nome_do_html(dados.codigo, dados.revisao_em_uso, lista.revisao_atual)
    try:
        caminho = gravar_html(lista.item.pasta, nome, resposta.html)
    except OSError as erro:
        return _falhou(lista, pedido, resposta, f"o HTML não foi gravado: {erro}", log_cb,
                       erro=f"o HTML não foi gravado: {erro}", **contexto)
    log_cb(f"  ✓ {dados.codigo} → {caminho.name} ({resposta.segundos:.0f} s)")
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


def revisar_listas(listas: list[ListaParaAmp], cliente, *, versao_sigft: str, url: str, chave_posta: bool, log_cb,
                   progress_cb=None, cancelado_cb=None, gravar_diagnostico: bool = True,
                   montar=montar_pedido) -> list[ResultadoAmp]:
    """Uma lista por vez (§7 do desenho). A que tem falta, ou cujo arquivo não se lê, não é
    chamada; a falha de uma não para as outras e deixa o diagnóstico em `logs\\amp\\`;
    `cancelado_cb()` é lido entre as listas, e as que sobram ficam "parado"."""
    contexto = {"versao_sigft": versao_sigft, "url": url, "chave_posta": chave_posta}
    log_cb(f"Revisando {len(listas)} lista(s) no AMP, uma por vez...")
    resultados: list[ResultadoAmp] = []
    parado = False
    for n, lista in enumerate(listas):
        if not parado and cancelado_cb is not None and cancelado_cb():
            parado = True
            log_cb("Revisão no AMP parada pelo usuário.")
        if parado:
            resultados.append(ResultadoAmp(lista, "parado", None, "parado antes de ir ao AMP"))
            continue
        if progress_cb:
            progress_cb(min(0.05 + n / len(listas) * 0.9, 0.95))
        resultado = _revisar(lista, cliente, montar, log_cb, **contexto)
        if resultado.diagnostico and gravar_diagnostico:
            _gravar_diagnostico(resultado, log_cb)
        resultados.append(resultado)
    if progress_cb:
        progress_cb(1.0)
    contagem = {s: sum(r.situacao == s for r in resultados) for s in ("pronto", "falhou", "falta", "parado")}
    log_cb(f"AMP: {contagem['pronto']} HTML pronto(s), {contagem['falhou']} falha(s), "
           f"{contagem['falta']} com falta, {contagem['parado']} parada(s).")
    return resultados


def codigos_para_eco(listas: list[ListaParaAmp], *, ler_status=status_pmib_em_tsv) -> list[str]:
    """Os códigos das listas e até `MATERIAIS_NO_ECO` CÓDIGOS DO MATERIAL do primeiro
    `_STATUS_PMIB` que se lê e tem algum: os campos que a LMR temia ver mascarados (§10)."""
    codigos = [lista.item.lista.codigo for lista in listas]
    for lista in listas:
        if lista.status_pmib is None:
            continue
        try:
            materiais = ler_status(lista.status_pmib).codigos_material
        except (ValueError, OSError, zipfile.BadZipFile):
            continue
        if materiais:
            return codigos + materiais[:MATERIAIS_NO_ECO]
    return codigos


def _linha(marca: str, nome: str, detalhe: str) -> str:
    """No formato do diagnóstico do Aconex: `OK      Ping: workflow 2026-10-27`."""
    return f"{marca:<8}{nome}: {detalhe}"


def testar_conexao(cliente, listas: list[ListaParaAmp], *, ler_status=status_pmib_em_tsv) -> list[str]:
    """As linhas do "Testar conexão com o AMP". O `ping` vê a rede, a chave e o workflow
    publicado; passando, o `eco` manda os códigos e passa quando todos voltam iguais."""
    ping = cliente.ping()
    if not ping.ok:
        return [_linha("FALHOU", "Ping", ping.erro)]
    linhas = [_linha("OK", "Ping", f"workflow {ping.versao_workflow or '(sem versão)'} "
                                   f"({ping.segundos:.1f} s, execução {ping.execucao or '?'})")]
    codigos = codigos_para_eco(listas, ler_status=ler_status)
    if not codigos:
        return linhas + [_linha("--", "Eco", "não mandado: nenhuma lista na conferência "
                                             "(rode a Conferência de Revisões e teste de novo)")]
    eco = cliente.eco(codigos)
    if not eco.ok:
        return linhas + [_linha("FALHOU", "Eco", eco.erro)]
    faltando = [codigo for codigo in codigos if codigo not in eco.texto]
    if faltando:
        return linhas + [_linha("FALHOU", "Eco", f"{len(faltando)} de {len(codigos)} códigos não voltaram iguais "
                                                 f"(mascarado pelo AMP?): {', '.join(faltando[:3])}")]
    return linhas + [_linha("OK", "Eco", f"os {len(codigos)} códigos voltaram iguais "
                                         f"({eco.segundos:.1f} s, execução {eco.execucao or '?'})")]

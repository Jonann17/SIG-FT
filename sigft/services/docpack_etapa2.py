"""DocPack, Etapa 2 -- o conteúdo do dossiê: os materiais do PDF da lista de sobressalentes,
lidos pelo AMP, no `_STATUS_PMIB`.

A Etapa 1 (`services/docpack.py`) monta a pasta com os templates vazios. Esta etapa, para
cada dossiê que ainda está vazio:

1. baixa do Aconex a revisão vigente do PDF da lista, com o nome do padrão
   (`<código>[<revisão>].pdf`), pela MESMA rotina da Conferência de Revisões
   (`conferencia_revisoes._gravar`: o `open(..., "xb")` nunca sobrescreve);
2. manda o PDF e o `_STATUS_PMIB` em branco do dossiê ao workflow da **Criação do
   _STATUS_PMIB** do Luan (`amp/criacao_status_pmib/`, o agente "Spare Parts Control Sheet
   Builder"), pelo MESMO cliente da Revisão no AMP (`core/amp/cliente.py`): um workflow e um
   agente só para "criar o controle de uma lista nova", e não um paralelo. O agente devolve um
   HTML com a tabela no formato exato do template; o HTML fica na pasta, para conferir;
3. lê a tabela do HTML (`ler_tabela`) e, com o "sim", grava as colunas que vêm da lista no
   `_STATUS_PMIB`, no XML (`core/excel/cirurgico.py`): o resto do pacote sai byte a byte.

[2026-11-05] A lista com preço saiu daqui (pedido do Jonathan: o agente não olha para ela). É o
módulo Lista de Preços (`services/lista_precos_arquivo.py`), que a cria e a preenche a partir
do `_STATUS_PMIB` -- depois desta etapa, por exemplo.

Regras que não se negociam (pedido do Luan, 04/11):

* **Preço nunca se inventa.** A lista de sobressalentes (PB020) não tem preço; coluna com cara
  de preço na tabela do agente é ignorada, com aviso, e o VALOR UNITÁRIO fica vazio.
* **Só as colunas que vêm da lista** são escritas (`COLUNAS_STATUS`): as de andamento da
  equipe e as fórmulas do template não são tocadas, venha o que vier na tabela.
* **Só em planilha vazia.** A aba com qualquer material já escrito é recusada -- e a
  conferência se repete na hora de gravar, porque a pessoa pode ter mexido no Excel entre a
  consulta e o "sim".
* **O cabeçalho se acha pelo texto**, nunca por linha fixa (convenção do projeto): a linha
  que tem ITEM e DESCRIÇÃO, nas 15 primeiras -- na planilha e na tabela do HTML.

Desenho: `docs/base-conhecimento/15b-docpack-etapa2.md`.
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

from sigft.core.aconex.cliente import ErroAconex
from sigft.core.excel.cirurgico import PlanilhaXlsx, ref
from sigft.services import status_pmib_arquivos
from sigft.services.conferencia_revisoes import Download, _gravar, nome_do_pdf
from sigft.services.revisao_amp import _TEM_HTML, BATIMENTO, PedidoAmp, _com_batimento, _duracao, gravar_html

ABA = "Lista de Materiais"
# O pedido do workflow da criação do _STATUS_PMIB (`amp/criacao_status_pmib/LEIA-ME.md`).
MODO = "criar"
CAMPO_LISTA, CAMPO_TEMPLATE = "lista", "template"
LINHAS_PARA_ACHAR_CABECALHO = 15
SUFIXO_RESPOSTA = " criacao AMP"
# O que se reconhece como preço num cabeçalho da tabela do agente (e se ignora).
_CABECALHOS_DE_PRECO = ("VALOR", "PRECO", "CUSTO")

# Cabeçalho (já normalizado por `_normalizar`) -> campo do material, por planilha. As colunas
# fora daqui (PDM usado, STATUS, datas...) não são tocadas.
COLUNAS_STATUS = {"ITEM": "item", "QTD.": "qtd", "UNID.": "unid", "DESCRICAO": "descricao",
                  "CODIGO DO MATERIAL": "codigo_material", "CODIGO CMI": "codigo_cmi",
                  "MARCA/MODELO": "fabricante_modelo", "TIPO DE ENTREGA": "tipo_entrega"}
# As colunas que dizem "esta planilha já tem material": as escritas, menos ITEM (o template já
# vem numerado) e TIPO DE ENTREGA (o template traz exemplos), mais as que só a pessoa
# preenche.
_SO_DO_TEMPLATE = {"ITEM", "TIPO DE ENTREGA"}
_DA_PESSOA = {"CODIGO PMIB", "VALOR UNITARIO"}

TIPOS_DE_ENTREGA = {"FISICA E DOCUMENTAL": "FÍSICA E DOCUMENTAL", "DOCUMENTAL": "DOCUMENTAL",
                    "TITULO": "TITULO"}


class ErroEtapa2(RuntimeError):
    """O dossiê não pode receber o conteúdo (planilha já preenchida, cabeçalho não achado)."""


# ------------------------------------------------------------------ os dossiês

@dataclass(frozen=True)
class Dossie:
    codigo: str
    pasta: Path
    status_pmib: Path


@dataclass(frozen=True)
class Varredura:
    vazios: list[Dossie]
    com_materiais: list[str]     # os códigos cujo _STATUS_PMIB já tem material: ficam fora
    ilegiveis: list[tuple[str, str]] = field(default_factory=list)   # (código, motivo)


def _normalizar(texto) -> str:
    sem = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sem.upper().split())


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _ler_aba(caminho: Path):
    """As linhas da aba, como valores (openpyxl, só leitura)."""
    from openpyxl import load_workbook

    livro = load_workbook(caminho, read_only=True, data_only=True)
    try:
        if ABA not in livro.sheetnames:
            raise ErroEtapa2(f"{caminho.name} não tem a aba '{ABA}'")
        return [tuple(linha) for linha in livro[ABA].iter_rows(values_only=True)]
    finally:
        livro.close()


def achar_cabecalho(linhas, mapa: dict[str, str]) -> tuple[int, dict[str, int]]:
    """(número da linha do cabeçalho, 1-based; {cabeçalho normalizado: coluna 1-based}) da
    primeira linha com ITEM e DESCRIÇÃO. Só os cabeçalhos de `mapa` e os da pessoa."""
    for numero, linha in enumerate(linhas[:LINHAS_PARA_ACHAR_CABECALHO], start=1):
        textos = {_normalizar(valor): coluna for coluna, valor in enumerate(linha, start=1) if not _vazio(valor)}
        if "ITEM" in textos and "DESCRICAO" in textos:
            return numero, {nome: col for nome, col in textos.items() if nome in mapa or nome in _DA_PESSOA}
    raise ErroEtapa2(f"a aba '{ABA}' não tem a linha de cabeçalho (ITEM e DESCRIÇÃO)")


def planilha_vazia(caminho: Path, mapa: dict[str, str]) -> bool:
    """Nenhum material escrito abaixo do cabeçalho (ver `_SO_DO_TEMPLATE` e `_DA_PESSOA`)."""
    linhas = _ler_aba(caminho)
    numero, colunas = achar_cabecalho(linhas, mapa)
    olhar = [col for nome, col in colunas.items() if nome not in _SO_DO_TEMPLATE]
    for linha in linhas[numero:]:
        for col in olhar:
            if col <= len(linha) and not _vazio(linha[col - 1]):
                return False
    return True


def procurar_dossies(raiz: str | Path) -> Varredura:
    """Os `_STATUS_PMIB` vivos da raiz cuja lista de materiais está vazia (os da Etapa 1)."""
    vazios, com_materiais, ilegiveis = [], [], []
    for codigo, caminho in status_pmib_arquivos.listar(raiz).vivos:
        status = Path(caminho)
        try:
            if not planilha_vazia(status, COLUNAS_STATUS):
                com_materiais.append(codigo)
                continue
        except Exception as erro:  # noqa: BLE001 -- planilha do usuário: fica fora, com o motivo
            ilegiveis.append((codigo, str(erro)))
            continue
        vazios.append(Dossie(codigo, status.parent, status))
    return Varredura(vazios, com_materiais, ilegiveis)


# ------------------------------------------------------------------ o Aconex

def baixar_vigente(cliente, dossie: Dossie, log_cb) -> Download:
    """A revisão vigente da lista na pasta do dossiê, com o nome do padrão. O arquivo que já
    está lá fica como está (`_gravar` da Conferência de Revisões)."""
    try:
        vigente = cliente.versao_vigente(dossie.codigo)
    except ErroAconex as erro:
        log_cb(f"  ✗ {dossie.codigo}: {erro}")
        return Download(dossie.codigo, None, None, "falhou", str(erro))
    if vigente is None:
        log_cb(f"  ✗ {dossie.codigo}: não encontrado no Aconex")
        return Download(dossie.codigo, None, None, "falhou", "não encontrado no Aconex")
    return _gravar(cliente, dossie.pasta, dossie.codigo, vigente, "", log_cb)


_PDF_DA_LISTA = re.compile(r"\[(?P<rev>[^\]]+)\]\.pdf$", re.IGNORECASE)


def pdf_na_pasta(dossie: Dossie) -> tuple[Path, str] | None:
    """Sem Aconex: o PDF da lista que já está na pasta (`<código>[<rev>].pdf`), o mais novo."""
    prefixo = nome_do_pdf(dossie.codigo, "")[: -len("[].pdf")]
    achados = []
    for arquivo in dossie.pasta.glob("*.pdf"):
        casou = _PDF_DA_LISTA.search(arquivo.name)
        if casou and arquivo.name[: casou.start()] == prefixo:
            achados.append((arquivo.stat().st_mtime, arquivo, casou.group("rev")))
    if not achados:
        return None
    _mtime, arquivo, revisao = max(achados)
    return arquivo, revisao


# ------------------------------------------------------------------ o pedido e a resposta

def mensagem(dossie: Dossie, pdf: Path, revisao: str, *, hoje: date | None = None) -> str:
    """A mensagem do workflow da criação, no formato do LEIA-ME dele."""
    return (f"Lista: {dossie.codigo}. Revisão: {revisao} (arquivo {pdf.name}). Template: "
            f"{dossie.status_pmib.name}. Data de hoje: {(hoje or date.today()):%d/%m/%Y}. Crie o controle.")


def montar_pedido(dossie: Dossie, pdf: Path, revisao: str, *, hoje: date | None = None) -> PedidoAmp:
    """O PDF da lista e o `_STATUS_PMIB` em branco do próprio dossiê, como estão."""
    return PedidoAmp({"modo": MODO, "mensagem": mensagem(dossie, pdf, revisao, hoje=hoje)},
                     {CAMPO_LISTA: pdf, CAMPO_TEMPLATE: dossie.status_pmib})


@dataclass(frozen=True)
class Material:
    item: int | float | str = ""
    qtd: int | float | str = ""
    unid: str = ""
    descricao: str = ""
    fabricante_modelo: str = ""
    codigo_material: str = ""
    codigo_ge: str = ""
    tipo_entrega: str = ""
    codigo_cmi: str = ""


def _numero(valor):
    """`2` -> 2, `"2,5"` -> 2.5; o resto como texto (`"1 jogo"`)."""
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, (int, float)):
        return int(valor) if float(valor).is_integer() else float(valor)
    texto = str(valor or "").strip()
    try:
        numero = float(texto.replace(",", "."))
    except ValueError:
        return texto
    return int(numero) if numero.is_integer() else numero


def _item(valor):
    """O ITEM como está na lista: o número inteiro vira número (`12`), o resto fica como texto
    (`3.10`, `3.4`). [2026-11-09] Na lista com o lado contratual e o fornecido, o ITEM das linhas
    fornecidas é o número do item contratual, e `_numero` fazia de "3.10" o 3,1 -- outro item.
    ITEM é rótulo, não quantidade."""
    texto = str(valor if valor is not None else "").strip()
    return int(texto) if texto.isascii() and texto.isdigit() else texto


def _texto(valor) -> str:
    return "" if valor is None else " ".join(str(valor).split())


def _tipo_de_entrega(valor) -> str:
    return TIPOS_DE_ENTREGA.get(_normalizar(valor), "")


class _Tabelas(HTMLParser):
    """As tabelas do HTML, como listas de linhas de textos (`<th>` e `<td>`)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabelas: list[list[list[str]]] = []
        self._linha: list[str] | None = None
        self._celula: list[str] | None = None
        self._dentro = 0   # tabelas abertas (uma tabela dentro de outra conta na de fora)

    def handle_starttag(self, tag, _attrs):
        if tag == "table":
            self._dentro += 1
            if self._dentro == 1:
                self.tabelas.append([])
        elif tag == "tr" and self._dentro:
            self._linha = []
        elif tag in ("td", "th") and self._linha is not None:
            self._celula = []
        elif tag == "br" and self._celula is not None:
            self._celula.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celula is not None and self._linha is not None:
            self._linha.append(_texto("".join(self._celula)))
            self._celula = None
        elif tag == "tr" and self._linha is not None and self.tabelas:
            self.tabelas[-1].append(self._linha)
            self._linha = None
        elif tag == "table" and self._dentro:
            self._dentro -= 1

    def handle_data(self, data):
        if self._celula is not None:
            self._celula.append(data)


def ler_tabela(html: str) -> tuple[list[dict[str, str]], list[str]]:
    """As linhas do controle no HTML do agente: a tabela cujo cabeçalho tem ITEM e DESCRIÇÃO
    (a primeira coluna, a da página, não tem nome do template e fica de fora pelo nome), como
    {cabeçalho normalizado: texto}. Devolve também os avisos."""
    leitor = _Tabelas()
    leitor.feed(html or "")
    for tabela in leitor.tabelas:
        for n, linha in enumerate(tabela[:LINHAS_PARA_ACHAR_CABECALHO]):
            nomes = [_normalizar(c) for c in linha]
            if "ITEM" in nomes and "DESCRICAO" in nomes:
                avisos = []
                preco = [c for c in nomes if any(p in c for p in _CABECALHOS_DE_PRECO)]
                if preco:
                    avisos.append(f"a tabela do AMP tem coluna de preço ({', '.join(preco)}): ignorada, "
                                  f"o VALOR UNITÁRIO fica vazio")
                linhas = [{nome: valor for nome, valor in zip(nomes, celulas) if nome}
                          for celulas in tabela[n + 1:]]
                return linhas, avisos
    return [], ["o HTML do AMP não traz a tabela do controle (cabeçalho com ITEM e DESCRIÇÃO)"]


def materiais_da_tabela(linhas: list[dict[str, str]]) -> tuple[list[Material], list[str]]:
    """Um `Material` por linha com descrição; as colunas vêm pelos nomes do template do
    `_STATUS_PMIB` (`COLUNAS_STATUS`). Linha sem descrição (repetição do cabeçalho, totais)
    fica de fora, com aviso."""
    materiais, sem_descricao = [], 0
    for linha in linhas:
        dados = {campo: linha.get(nome, "") for nome, campo in COLUNAS_STATUS.items()}
        if not dados["descricao"]:
            if any(dados.values()):   # a coluna da página, sozinha, não conta
                sem_descricao += 1
            continue
        item = _item(dados["item"])
        materiais.append(Material(
            item=item if item != "" else len(materiais) + 1, qtd=_numero(dados["qtd"]), unid=dados["unid"],
            descricao=dados["descricao"], fabricante_modelo=dados["fabricante_modelo"],
            codigo_material=dados["codigo_material"], codigo_cmi=dados["codigo_cmi"],
            tipo_entrega=_tipo_de_entrega(dados["tipo_entrega"])))
    avisos = [f"{sem_descricao} linha(s) da tabela sem descrição ficaram de fora"] if sem_descricao else []
    return materiais, avisos


def ler_materiais(html: str) -> tuple[list[Material], list[str]]:
    """Do HTML do agente aos materiais: `ler_tabela` + `materiais_da_tabela`."""
    linhas, avisos = ler_tabela(html)
    materiais, mais = materiais_da_tabela(linhas)
    return materiais, avisos + mais


# ------------------------------------------------------------------ a gravação

def escritas(materiais: list[Material], linha_cabecalho: int, colunas: dict[str, int],
             mapa: dict[str, str]) -> dict[str, object]:
    """{referência: valor} de cada material, uma linha por material logo abaixo do cabeçalho."""
    saida: dict[str, object] = {}
    for n, material in enumerate(materiais, start=1):
        for nome, coluna in colunas.items():
            campo = mapa.get(nome)
            if campo is not None:
                saida[ref(linha_cabecalho + n, coluna)] = getattr(material, campo)
    return saida


def gravar_planilha(caminho: Path, materiais: list[Material], mapa: dict[str, str]) -> int:
    """Confere de novo que a aba está vazia e grava os materiais no XML. Devolve as linhas
    escritas. `PermissionError` (aberto no Excel) sobe para quem chama."""
    linhas = _ler_aba(caminho)
    numero, colunas = achar_cabecalho(linhas, mapa)
    if not planilha_vazia(caminho, mapa):
        raise ErroEtapa2(f"{caminho.name} já tem materiais: nada foi escrito")
    planilha = PlanilhaXlsx(caminho)
    parte = planilha.parte_da_aba(ABA)
    for referencia, valor in escritas(materiais, numero, colunas, mapa).items():
        planilha.escrever(parte, referencia, valor)
    planilha.salvar()
    return len(materiais)


# ------------------------------------------------------------------ a rodada

@dataclass(frozen=True)
class Proposta:
    dossie: Dossie
    situacao: Literal["pronta", "falhou", "parado"]
    detalhe: str
    pdf: Path | None = None
    revisao: str = ""
    materiais: tuple[Material, ...] = ()
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gravacao:
    dossie: Dossie
    situacao: Literal["gravado", "parcial", "recusado", "falhou"]
    detalhe: str


def _consultar_uma(dossie: Dossie, aconex, amp, log_cb, batimento: float) -> Proposta:
    if aconex is not None:
        download = baixar_vigente(aconex, dossie, log_cb)
        if download.caminho is None:
            return Proposta(dossie, "falhou", f"Aconex: {download.detalhe}")
        pdf, revisao = download.caminho, download.revisao or ""
    else:
        achado = pdf_na_pasta(dossie)
        if achado is None:
            return Proposta(dossie, "falhou", "sem Aconex e sem o PDF da lista na pasta")
        pdf, revisao = achado
        log_cb(f"    PDF da pasta: {pdf.name}")
    pedido = montar_pedido(dossie, pdf, revisao)
    log_cb(f"    vai ao AMP: {pdf.name} e {dossie.status_pmib.name}; o agente está lendo (costuma levar "
           f"alguns minutos)")
    resposta = _com_batimento(lambda: amp.enviar(pedido.campos, pedido.arquivos), log_cb, batimento)
    if not resposta.ok:
        return Proposta(dossie, "falhou", f"AMP: {resposta.erro or 'falha sem mensagem'}", pdf, revisao)
    if not _TEM_HTML.search(resposta.html):
        return Proposta(dossie, "falhou", "o AMP não devolveu HTML", pdf, revisao)
    nome = nome_do_pdf(dossie.codigo, revisao)[: -len(".pdf")] + SUFIXO_RESPOSTA + ".html"
    try:
        guardado = gravar_html(dossie.pasta, nome, resposta.html)
        log_cb(f"    HTML do AMP em {guardado.name} ({_duracao(resposta.segundos)}, execução "
               f"{resposta.execucao or '?'})")
    except OSError as erro:
        log_cb(f"    ⚠️ o HTML do AMP não foi guardado na pasta: {erro}")
    materiais, avisos = ler_materiais(resposta.html)
    for aviso in avisos:
        log_cb(f"    ⚠️ {aviso}")
    if not materiais:
        return Proposta(dossie, "falhou", "o AMP não devolveu nenhum material", pdf, revisao, (), tuple(avisos))
    return Proposta(dossie, "pronta", f"{len(materiais)} material(is)", pdf, revisao, tuple(materiais),
                    tuple(avisos))


def consultar(dossies: list[Dossie], aconex, amp, *, log_cb, progress_cb=None, cancelado_cb=None,
              batimento: float = BATIMENTO) -> list[Proposta]:
    """Para cada dossiê: o PDF vigente (do Aconex, ou o da pasta sem Aconex) e a lista de
    materiais do AMP. Nada é escrito nas planilhas aqui: é a proposta que a pessoa confirma.
    Antes, o `ping` do AMP: falhando, nada vai."""
    inicio = time.monotonic()
    log_cb(f"DocPack · Etapa 2: {len(dossies)} dossiê(s)" + ("" if aconex is not None else " (sem Aconex)"))
    ping = amp.ping()
    if not ping.ok:
        log_cb(f"❌ Ping do AMP: {ping.erro}. Nada foi mandado.")
        return [Proposta(d, "falhou", f"o ping falhou: {ping.erro}") for d in dossies]
    propostas: list[Proposta] = []
    parado = False
    for n, dossie in enumerate(dossies):
        if not parado and cancelado_cb is not None and cancelado_cb():
            parado = True
            log_cb("Etapa 2 parada pelo usuário.")
        if parado:
            propostas.append(Proposta(dossie, "parado", "parado antes de ir ao AMP"))
            continue
        if progress_cb:
            progress_cb(min(0.05 + n / len(dossies) * 0.9, 0.95))
        log_cb(f"[{n + 1}/{len(dossies)}] {dossie.codigo}")
        try:
            proposta = _consultar_uma(dossie, aconex, amp, log_cb, batimento)
        except Exception as erro:  # noqa: BLE001 -- a falha de um não para os outros
            proposta = Proposta(dossie, "falhou", f"{type(erro).__name__}: {erro}")
        marca = "✅" if proposta.situacao == "pronta" else "❌"
        log_cb(f"    {marca} {proposta.detalhe}")
        propostas.append(proposta)
    if progress_cb:
        progress_cb(1.0)
    prontas = sum(p.situacao == "pronta" for p in propostas)
    log_cb(f"Fim da consulta: {prontas} pronta(s), {sum(p.situacao == 'falhou' for p in propostas)} falha(s), "
           f"{sum(p.situacao == 'parado' for p in propostas)} parada(s), em {_duracao(time.monotonic() - inicio)}")
    return propostas


def _gravar_uma(proposta: Proposta, log_cb) -> Gravacao:
    dossie, materiais = proposta.dossie, list(proposta.materiais)
    try:
        gravar_planilha(dossie.status_pmib, materiais, COLUNAS_STATUS)
    except ErroEtapa2 as erro:
        return Gravacao(dossie, "recusado", str(erro))
    except PermissionError:
        return Gravacao(dossie, "falhou", f"{dossie.status_pmib.name} está aberto no Excel: feche e tente de novo")
    log_cb(f"    ✅ {dossie.status_pmib.name}: {len(materiais)} linha(s)")
    return Gravacao(dossie, "gravado", f"{len(materiais)} material(is) no _STATUS_PMIB")


def gravar(propostas: list[Proposta], *, log_cb, progress_cb=None) -> list[Gravacao]:
    """Escreve as propostas prontas. Cada planilha é conferida vazia de novo antes."""
    prontas = [p for p in propostas if p.situacao == "pronta"]
    log_cb(f"Gravando {len(prontas)} dossiê(s)...")
    resultados = []
    for n, proposta in enumerate(prontas):
        if progress_cb:
            progress_cb(min(0.05 + n / max(len(prontas), 1) * 0.9, 0.95))
        log_cb(f"[{n + 1}/{len(prontas)}] {proposta.dossie.codigo}")
        try:
            resultado = _gravar_uma(proposta, log_cb)
        except Exception as erro:  # noqa: BLE001 -- a falha de um não para os outros
            resultado = Gravacao(proposta.dossie, "falhou", f"{type(erro).__name__}: {erro}")
        if resultado.situacao != "gravado":
            marca = "⚠️" if resultado.situacao == "parcial" else "❌"
            log_cb(f"    {marca} {resultado.detalhe}")
        resultados.append(resultado)
    if progress_cb:
        progress_cb(1.0)
    contagem = {s: sum(r.situacao == s for r in resultados) for s in ("gravado", "parcial", "recusado", "falhou")}
    log_cb(f"Fim: {contagem['gravado']} completo(s), {contagem['parcial']} parcial(is), "
           f"{contagem['recusado']} recusado(s), {contagem['falhou']} falha(s). Confira no Excel antes de usar.")
    return resultados


def resumo_da_proposta(propostas: list[Proposta], *, amostra: int = 3) -> str:
    """O texto da confirmação: por lista pronta, quantos materiais e os primeiros."""
    linhas = []
    for proposta in propostas:
        if proposta.situacao != "pronta":
            continue
        primeiros = "; ".join(m.descricao for m in proposta.materiais[:amostra])
        mais = len(proposta.materiais) - amostra
        linhas.append(f"{proposta.dossie.codigo} [{proposta.revisao}]: {len(proposta.materiais)} material(is) "
                      f"({primeiros}{f'; +{mais}' if mais > 0 else ''})")
    return "\n".join(linhas)


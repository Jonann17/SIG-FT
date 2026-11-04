"""DocPack: monta a pasta (o "dossiê") de cada lista de sobressalentes que ainda não
tem `_STATUS_PMIB`, com os templates que ela vai precisar.

Pedido do Jonathan (2026-11-03). A lista sai da mapeadora (as que não têm LINK DA
PLANILHA e cujo código não tem `_STATUS_PMIB` vivo na pasta raiz); a pessoa escolhe
quais, onde, e o nome da pasta final (o subsistema: difícil de deduzir, por isso
digitado, com uma sugestão da IA a pedido). Cada dossiê:

    <raiz>/<capítulo>/[<sistema>/]<pasta>/
        <código>_STATUS_PMIB.xlsx            -- do template, com A3 e A4 preenchidos
        <código PB021>.xlsm                  -- a lista com preço, Capa F37 e E27
        LMR/Aplicação LMR - <pasta>.xlsx     -- o template da Aplicação LMR
        IMAGENS/
        DATASHEETS/

Regras que não se negociam:

* **Nunca sobrescreve.** Arquivo que já existe fica como está (aviso); lista com
  `_STATUS_PMIB` vivo em qualquer lugar da raiz é pulada.
* **O template é copiado byte a byte e editado no XML** (`core/excel/cirurgico.py`):
  o openpyxl apagaria as validações em extensão do `_STATUS_PMIB` e o VBA da lista
  com preço.
* **A mapeadora não é gravada.** Quem liga o `_STATUS_PMIB` novo a ela é o Gestão
  PMIB, na rodada seguinte.

Desenho: `docs/superpowers/specs/2026-11-03-docpack-design.md`.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from sigft import config
from sigft.core.excel.cirurgico import PlanilhaXlsx
from sigft.core.llm import prompts
from sigft.services import status_pmib_arquivos
from sigft.services.conferencia_revisoes import ListaNaMapeadora, Mapeadora

Log = Callable[[str], None]

ABA_STATUS = "Lista de Materiais"
ABA_CAPA = "Capa"
ABA_LMR = "DOCS DE REFERENCIA"
CELULA_TITULO_STATUS = "A3"
CELULA_REVISAO_STATUS = "A4"
CELULA_CODIGO_PRECO = "F37"
CELULA_TITULO_PRECO = "E27"
SUFIXO_TITULO_PRECO = " - LISTA DE SOBRESSALENTE COM PREÇO"
SUBPASTAS = ("LMR", "IMAGENS", "DATASHEETS")

# Os nomes dos templates na pasta Templates do Box (`prefs` "templates_ficha"). O da
# Aplicação LMR aparece com dois nomes na documentação: vale o que existir.
NOMES_TEMPLATE = {
    "status_pmib": ("codigo_itaipu_STATUS_PMIB.xlsx",),
    "lista_precos": ("Lista de Sobressalentes com preço.xlsm",),
    "aplicacao_lmr": ("Aplicação LMR - Sistema.xlsx", "APLICACAO LMR - SOBRESSALENTES_template.xlsx"),
}

# Os rótulos da aba DOCS DE REFERENCIA do template da Aplicação LMR (sem acento,
# maiúsculas): o valor vai na célula logo à direita do rótulo.
ROTULO_LISTA = "LISTA DE SOBRESSALENTE:"
ROTULO_ET = "ESPECIFICACAO TECNICA / CAPITULO:"
ROTULO_SUBSISTEMA = "SUBSISTEMA:"

_RESERVADOS = re.compile(r'[<>:"/\\|?*]')
_PB020 = re.compile(r"PB020(-0\d)?$", re.IGNORECASE)


class ErroDocPack(ValueError):
    """Um destino ou um código que não dá para usar."""


def _sem_acento(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).upper().split())


# --------------------------------------------------------------------------
# Quais listas
# --------------------------------------------------------------------------
def e_lista_sem_preco(lista: ListaNaMapeadora) -> bool:
    """Uma lista de sobressalentes da mapeadora: PB020 no código (com ou sem o `-0x` do
    SMF) e sem PREÇO no título. A regra do `pmib_manager.e_lista_de_sobressalentes`
    também pede SOBRESSALENTES no título, mas ela escolhe o que ENTRA na mapeadora (as
    linhas do DocManager); aqui a lista já está nela, e o título pode vir vazio."""
    return bool(_PB020.search(lista.codigo.strip())) and "PRECO" not in _sem_acento(lista.descricao)


def listas_sem_status_pmib(mapeadora: Mapeadora, raiz: str | Path | None) -> list[ListaNaMapeadora]:
    """As listas sem LINK DA PLANILHA e sem `_STATUS_PMIB` vivo (pelo código) na raiz."""
    vivos = set()
    if raiz:
        vivos = {codigo.strip().upper() for codigo, _ in status_pmib_arquivos.listar(raiz).vivos}
    return [lista for lista in mapeadora.listas
            if e_lista_sem_preco(lista) and not lista.link and lista.codigo.strip().upper() not in vivos]


def codigo_lista_de_precos(codigo: str) -> str:
    """O código da lista com preço: o mesmo, com o DCC PB021 no lugar do PB020. O `-0x`
    do formato antigo (`...PB020-01`) sai: a lista com preço de hoje é `...PB021`
    (`gestao-sobressalentes/03 - Processo/Lista de Precos.md`)."""
    codigo = str(codigo or "").strip()
    if not _PB020.search(codigo):
        raise ErroDocPack(f"o código {codigo!r} não termina em PB020")
    return _PB020.sub("PB021", codigo)


def revisao_da_lista(lista: ListaNaMapeadora) -> str:
    """A revisão em uso; sem ela, a última emitida; sem as duas, ``""``."""
    return lista.revisao_em_uso or lista.ultima_revisao


def texto_do_titulo(lista: ListaNaMapeadora, subsistema: str) -> str:
    """A linha 3 do `_STATUS_PMIB`, no formato do template
    ("ET / CAPÍTULO / SUBSISTEMA | CÓDIGO ITAIPU / CÓDIGO INTERNO | Eventos"), que é o da
    coluna T da mapeadora com o subsistema. O que está vazio sai, com o separador."""
    esquerda = " / ".join(p for p in (lista.especificacao, lista.capitulo, subsistema) if p)
    meio = " / ".join(p for p in (lista.codigo, lista.codigo_cmi) if p)
    return " | ".join(p for p in (esquerda, meio, lista.eventos) if p)


def texto_da_revisao(revisao: str, dia: date) -> str:
    """A linha 4 do `_STATUS_PMIB`, a que `status_pmib_arquivos.revisao_do_texto` lê."""
    return (f"{config.TEXTO_LINHA_REVISAO} ATUAL EM USO: {revisao} - "
            f"DATA DE ALTERAÇÃO: {dia.strftime('%d/%m/%Y')}")


# --------------------------------------------------------------------------
# Onde
# --------------------------------------------------------------------------
@dataclass
class Destino:
    """Onde vai o dossiê: `<raiz>/<capitulo>/[<sistema>/]<pasta>`."""
    capitulo: str = ""
    sistema: str = ""
    pasta: str = ""


def _nome_de_pasta(nome: str, campo: str, *, obrigatorio: bool) -> str:
    nome = " ".join(str(nome or "").split())
    if not nome:
        if obrigatorio:
            raise ErroDocPack(f"falta a {campo}")
        return ""
    if _RESERVADOS.search(nome) or nome in (".", "..") or nome.endswith("."):
        raise ErroDocPack(f"a {campo} {nome!r} tem caractere que o Windows não aceita")
    return nome


def pasta_do_dossie(raiz: str | Path, destino: Destino) -> Path:
    """O caminho do dossiê, ou `ErroDocPack` se falta o capítulo ou a pasta final."""
    partes = [_nome_de_pasta(destino.capitulo, "pasta do capítulo", obrigatorio=True),
              _nome_de_pasta(destino.sistema, "pasta do sistema", obrigatorio=False),
              _nome_de_pasta(destino.pasta, "pasta final", obrigatorio=True)]
    return Path(raiz).joinpath(*[p for p in partes if p])


def pastas_existentes(raiz: str | Path | None) -> dict[str, list[str]]:
    """As pastas de dois níveis da raiz: `{capítulo: [subpastas]}`, sem as escondidas
    nem as que o levantamento ignora (obsoleto, testes, backup)."""
    if not raiz or not os.path.isdir(raiz):
        return {}

    def filhas(pasta: Path) -> list[str]:
        try:
            return sorted(p.name for p in pasta.iterdir()
                          if p.is_dir() and not p.name.startswith((".", "~"))
                          and status_pmib_arquivos.motivo_para_ignorar(f"{p.name}\\x") is None)
        except OSError:
            return []

    raiz = Path(raiz)
    return {nome: filhas(raiz / nome) for nome in filhas(raiz)}


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
@dataclass
class Templates:
    status_pmib: str = ""
    lista_precos: str = ""
    aplicacao_lmr: str = ""


def achar_templates(pasta: str | Path | None) -> Templates:
    """Os templates com os nomes conhecidos (`NOMES_TEMPLATE`) na pasta; o que não
    estiver lá fica vazio."""
    achados = Templates()
    if not pasta or not os.path.isdir(pasta):
        return achados
    for campo, nomes in NOMES_TEMPLATE.items():
        caminho = next((Path(pasta) / n for n in nomes if (Path(pasta) / n).is_file()), None)
        if caminho is not None:
            setattr(achados, campo, str(caminho))
    return achados


def nome_da_aplicacao_lmr(template: str | Path, pasta: str) -> str:
    """`Aplicação LMR - <pasta>.<ext do template>`."""
    return f"Aplicação LMR - {pasta}{Path(template).suffix.lower() or '.xlsx'}"


# --------------------------------------------------------------------------
# O plano e a criação
# --------------------------------------------------------------------------
@dataclass
class Passo:
    caminho: Path
    tipo: str          # "pasta" ou "arquivo"
    existe: bool


@dataclass
class Resultado:
    codigo: str
    situacao: str                      # "criado", "aviso", "falhou"
    pasta: Path | None = None
    criados: list[Path] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    motivo: str = ""


def planejar(lista: ListaNaMapeadora, raiz: str | Path, destino: Destino, templates: Templates) -> list[Passo]:
    """O que `criar_dossie` faria, sem tocar no disco: as pastas e os arquivos, cada
    um dizendo se já existe. Levanta `ErroDocPack` para destino ou código inválido."""
    pasta = pasta_do_dossie(raiz, destino)
    passos = []
    # As pastas que faltam no caminho, a partir da raiz.
    atual = Path(raiz)
    for parte in pasta.relative_to(raiz).parts:
        atual = atual / parte
        passos.append(Passo(atual, "pasta", atual.is_dir()))
    arquivos = [pasta / f"{lista.codigo.strip()}{status_pmib_arquivos.SUFIXO}.xlsx"]
    if templates.lista_precos:
        arquivos.append(pasta / f"{codigo_lista_de_precos(lista.codigo)}{Path(templates.lista_precos).suffix}")
    for sub in SUBPASTAS:
        passos.append(Passo(pasta / sub, "pasta", (pasta / sub).is_dir()))
    if templates.aplicacao_lmr:
        arquivos.append(pasta / "LMR" / nome_da_aplicacao_lmr(templates.aplicacao_lmr, destino.pasta.strip()))
    for nome in arquivos:
        if _RESERVADOS.search(nome.name):
            raise ErroDocPack(f"o nome {nome.name!r} tem caractere que o Windows não aceita")
    passos.extend(Passo(a, "arquivo", a.exists()) for a in arquivos)
    return passos


def _copiar(origem: str | Path, destino: Path) -> bool:
    """Copia byte a byte; `False` (e nada muda) se o destino já existe."""
    dados = Path(origem).read_bytes()
    try:
        with open(destino, "xb") as saida:   # "x": nunca sobrescreve
            saida.write(dados)
    except FileExistsError:
        return False
    return True


def _escrever(caminho: Path, aba: str, valores: dict[str, str]) -> None:
    planilha = PlanilhaXlsx(caminho)
    parte = planilha.parte_da_aba(aba)
    for referencia, valor in valores.items():
        planilha.escrever(parte, referencia, valor)
    planilha.salvar()


def _celulas_da_aplicacao_lmr(caminho: Path, valores: dict[str, str]) -> tuple[str | None, dict[str, str], list[str]]:
    """(nome real da aba, {célula: valor}, rótulos não achados): a célula à direita de
    cada rótulo da aba DOCS DE REFERENCIA (comparados sem acento). Lê com openpyxl;
    quem grava é o `cirurgico`."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    wb = load_workbook(caminho, read_only=False, data_only=True)
    try:
        ws = next((wb[n] for n in wb.sheetnames if _sem_acento(n) == ABA_LMR), None)
        if ws is None:
            return None, {}, list(valores)
        fim_da_mesclagem = {}
        for faixa in ws.merged_cells.ranges:
            for linha in range(faixa.min_row, faixa.max_row + 1):
                fim_da_mesclagem[(linha, faixa.min_col)] = faixa.max_col
        escritas, faltaram = {}, []
        for rotulo, valor in valores.items():
            celula = next((c for linha in ws.iter_rows() for c in linha
                           if c.value is not None and _sem_acento(c.value) == rotulo), None)
            if celula is None:
                faltaram.append(rotulo)
                continue
            coluna = fim_da_mesclagem.get((celula.row, celula.column), celula.column) + 1
            escritas[f"{get_column_letter(coluna)}{celula.row}"] = valor
        return ws.title, escritas, faltaram
    finally:
        wb.close()


def criar_dossie(lista: ListaNaMapeadora, raiz: str | Path, destino: Destino, templates: Templates, *,
                 vivos: set[str] | None = None, hoje: date | None = None, log_cb: Log = print) -> Resultado:
    """Cria o dossiê da lista. Nunca levanta por arquivo: o problema vira `Resultado`
    ("falhou" quando nada útil saiu, "aviso" quando saiu com ressalva).

    `vivos`: os códigos (maiúsculas) com `_STATUS_PMIB` vivo na raiz, do
    levantamento feito uma vez por rodada; com o da lista entre eles, nada é criado."""
    hoje = hoje or date.today()
    codigo = lista.codigo.strip()
    if vivos is not None and codigo.upper() in vivos:
        return Resultado(codigo, "falhou", motivo="já existe um _STATUS_PMIB com esse código na pasta raiz")
    if not templates.status_pmib or not os.path.isfile(templates.status_pmib):
        return Resultado(codigo, "falhou", motivo="falta o template do _STATUS_PMIB")
    try:
        passos = planejar(lista, raiz, destino, templates)
    except ErroDocPack as erro:
        return Resultado(codigo, "falhou", motivo=str(erro))

    pasta = pasta_do_dossie(raiz, destino)
    resultado = Resultado(codigo, "criado", pasta)
    ignorado = status_pmib_arquivos.motivo_para_ignorar(
        str(pasta.relative_to(raiz) / f"{codigo}{status_pmib_arquivos.SUFIXO}.xlsx"))
    if ignorado:
        resultado.avisos.append(f"nesta pasta o _STATUS_PMIB não conta como vivo: {ignorado}")
    try:
        for passo in passos:
            if passo.tipo == "pasta" and not passo.existe:
                passo.caminho.mkdir(parents=True, exist_ok=True)
                resultado.criados.append(passo.caminho)
        arquivos = [p.caminho for p in passos if p.tipo == "arquivo"]
        # 1. O _STATUS_PMIB, com o título e a revisão.
        status = arquivos[0]
        if _copiar(templates.status_pmib, status):
            revisao = revisao_da_lista(lista)
            valores = {CELULA_TITULO_STATUS: texto_do_titulo(lista, destino.pasta.strip())}
            if revisao:
                valores[CELULA_REVISAO_STATUS] = texto_da_revisao(revisao, hoje)
            else:
                resultado.avisos.append("sem revisão na mapeadora: a linha 4 ficou a do template")
            _escrever(status, ABA_STATUS, valores)
            resultado.criados.append(status)
        else:
            resultado.avisos.append(f"{status.name} já existia: ficou como estava")
        # 2. A lista com preço.
        if templates.lista_precos:
            preco = next(a for a in arquivos if a.name.startswith(codigo_lista_de_precos(codigo)))
            if _copiar(templates.lista_precos, preco):
                titulo = (lista.descricao or codigo) + SUFIXO_TITULO_PRECO
                _escrever(preco, ABA_CAPA, {CELULA_CODIGO_PRECO: codigo_lista_de_precos(codigo),
                                            CELULA_TITULO_PRECO: titulo})
                resultado.criados.append(preco)
            else:
                resultado.avisos.append(f"{preco.name} já existia: ficou como estava")
        else:
            resultado.avisos.append("sem o template da lista com preço: ela não foi criada")
        # 3. A Aplicação LMR.
        if templates.aplicacao_lmr:
            lmr = arquivos[-1]
            if _copiar(templates.aplicacao_lmr, lmr):
                resultado.criados.append(lmr)
                valores = {ROTULO_LISTA: codigo,
                           ROTULO_ET: " / ".join(p for p in (lista.especificacao, lista.capitulo) if p),
                           ROTULO_SUBSISTEMA: destino.pasta.strip()}
                aba, escritas, faltaram = _celulas_da_aplicacao_lmr(lmr, valores)
                if escritas:
                    _escrever(lmr, aba, escritas)
                if faltaram:
                    resultado.avisos.append("Aplicação LMR sem o rótulo " + ", ".join(faltaram)
                                            + ": preencha à mão")
            else:
                resultado.avisos.append(f"{lmr.name} já existia: ficou como estava")
        else:
            resultado.avisos.append("sem o template da Aplicação LMR: a pasta LMR ficou vazia")
    except (OSError, KeyError, ValueError) as erro:
        resultado.situacao = "falhou"
        resultado.motivo = str(erro)
        return resultado
    if resultado.avisos:
        resultado.situacao = "aviso"
    return resultado


def criar_dossies(pedidos: list[tuple[ListaNaMapeadora, Destino]], raiz: str | Path, templates: Templates, *,
                  log_cb: Log = print, progress_cb: Callable[[float], None] | None = None,
                  cancelado_cb: Callable[[], bool] | None = None) -> list[Resultado]:
    """Um dossiê por pedido, com o log do padrão (início, uma linha por lista, resumo)."""
    log_cb(f"DocPack: {len(pedidos)} lista(s) em {raiz}")
    vivos = {c.strip().upper() for c, _ in status_pmib_arquivos.listar(raiz).vivos}
    resultados: list[Resultado] = []
    for n, (lista, destino) in enumerate(pedidos):
        if cancelado_cb is not None and cancelado_cb():
            log_cb("Parada pedida: as listas que faltam ficaram para depois.")
            break
        resultado = criar_dossie(lista, raiz, destino, templates, vivos=vivos, log_cb=log_cb)
        resultados.append(resultado)
        if resultado.situacao == "falhou":
            log_cb(f"  ❌ {resultado.codigo}: {resultado.motivo}")
        else:
            marca = "✅" if resultado.situacao == "criado" else "⚠️"
            log_cb(f"  {marca} {resultado.codigo} → {resultado.pasta}")
            for aviso in resultado.avisos:
                log_cb(f"      ⚠️ {aviso}")
        if progress_cb:
            progress_cb((n + 1) / len(pedidos))
    feitos = sum(r.situacao == "criado" for r in resultados)
    com_aviso = sum(r.situacao == "aviso" for r in resultados)
    falhas = sum(r.situacao == "falhou" for r in resultados)
    log_cb(f"DocPack: {feitos} criado(s), {com_aviso} com aviso, {falhas} falha(s).")
    if feitos or com_aviso:
        log_cb("Rode o Gestão PMIB para ligar os _STATUS_PMIB novos à mapeadora (LINK DA PLANILHA).")
    return resultados


# --------------------------------------------------------------------------
# A sugestão da IA
# --------------------------------------------------------------------------
TAREFA_IA = "docpack_pasta"


def ler_sugestao(dados) -> Destino | None:
    """O `{capitulo, sistema|subsistema, pasta}` que a IA devolveu, ou `None`. Aceita
    texto (com prosa ou cerca de código em volta) ou o JSON já lido."""
    if isinstance(dados, str):
        from sigft.core.llm.client import _NADA, _json_tolerante
        lido = _json_tolerante(dados)
        dados = None if lido is _NADA else lido
    if isinstance(dados, list) and dados:
        dados = dados[0]
    if not isinstance(dados, dict):
        return None
    destino = Destino(str(dados.get("capitulo") or "").strip(),
                      str(dados.get("sistema") or dados.get("subsistema_intermediario") or "").strip(),
                      str(dados.get("pasta") or dados.get("subsistema") or "").strip())
    return destino if destino.capitulo and destino.pasta else None


def sugerir_destino(lista: ListaNaMapeadora, existentes: dict[str, list[str]], llm) -> tuple[Destino | None, str]:
    """(sugestão, motivo) da IA para onde vai o dossiê. Nunca levanta: falha vira
    `(None, motivo da falha)`. A sugestão só preenche os campos; quem confirma é a pessoa."""
    prompt = prompts.montar_docpack_pasta(
        codigo=lista.codigo, titulo=lista.descricao, especificacao=lista.especificacao,
        capitulo=lista.capitulo, pastas_existentes=json.dumps(existentes, ensure_ascii=False, indent=1))
    try:
        resposta = llm.generate(prompt, json_mode=True, tags={"modulo": "docpack", "tarefa": TAREFA_IA})
    except Exception as erro:  # noqa: BLE001 -- a IA é um atalho; sem ela, digita-se
        return None, f"a IA não respondeu: {erro}"
    dados = getattr(resposta, "parsed_json", None)
    destino = ler_sugestao(dados if dados is not None else getattr(resposta, "text", ""))
    if destino is None:
        return None, "a IA respondeu sem capítulo ou pasta"
    motivo = dados.get("motivo", "") if isinstance(dados, dict) else ""
    return destino, str(motivo or "")

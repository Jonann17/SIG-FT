"""DocPack: monta a pasta (o "dossiê") de cada lista de sobressalentes que ainda não
tem `_STATUS_PMIB`, com os templates que ela vai precisar.

Pedido do Jonathan (2026-11-03). A lista sai da mapeadora (as que não têm LINK DA
PLANILHA e cujo código não tem `_STATUS_PMIB` vivo na pasta raiz); a pessoa escolhe
quais, onde, e o nome da pasta final (o subsistema: difícil de deduzir, por isso
digitado, com uma sugestão da IA a pedido). Cada dossiê:

    <raiz>/<capítulo>/[<sistema>/]<pasta>/
        <código>_STATUS_PMIB.xlsx            -- do template, com A3 e A4 preenchidos
        LMR/Aplicação LMR - <pasta>.xlsx     -- o template da Aplicação LMR
        IMAGENS/
        DATASHEETS/

Regras que não se negociam:

* **Nunca sobrescreve.** Arquivo que já existe fica como está (aviso); lista com
  `_STATUS_PMIB` vivo em qualquer lugar da raiz é pulada.
* **O template é copiado byte a byte e editado no XML** (`core/excel/cirurgico.py`):
  o openpyxl apagaria as validações em extensão do `_STATUS_PMIB`.
* **Lista com preço não é daqui** (2026-11-05): o agente do webhook não olha para ela,
  e ela ganhou o módulo próprio (`services/lista_precos_arquivo.py`, tela Lista de
  Preços).
* **Da mapeadora, só o LINK DA PLANILHA vazio** (2026-11-05, `gravar_links`): o
  dossiê criado já entra com o "Abrir Box", para a Conferência de Listas achá-lo. O
  resto da mapeadora continua sendo do Gestão PMIB.

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
ABA_LMR = "DOCS DE REFERENCIA"
CELULA_TITULO_STATUS = "A3"
CELULA_REVISAO_STATUS = "A4"
SUBPASTAS = ("LMR", "IMAGENS", "DATASHEETS")

# Os nomes dos templates na pasta Templates do Box (`prefs` "templates_ficha"). O da
# Aplicação LMR aparece com dois nomes na documentação: vale o que existir.
NOMES_TEMPLATE = {
    "status_pmib": ("codigo_itaipu_STATUS_PMIB.xlsx",),
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
    """Onde vai o dossiê: `<raiz>/<ET>/<capítulo>/<sistema>/<subsistema>/<pasta final>`.

    [2026-11-04, pedido do Luan] A hierarquia das pastas é a da ET: a primeira pasta é a
    ET (`03 - EBOP`, `05 - UNIDADE GERADORA`), dentro dela o capítulo, e no capítulo o
    sistema e o subsistema. Só a ET é obrigatória, e mais um nível qualquer abaixo
    dela; nível vazio é pulado (nem toda ET tem sistema). Um nível pode levar MAIS UMA
    pasta, separada por `/` (`MANCAIS/GUIA`): é a pasta extra que alguns passos pedem.
    O dossiê é a última pasta do caminho."""
    et: str = ""
    capitulo: str = ""
    sistema: str = ""
    subsistema: str = ""
    pasta: str = ""

    def niveis(self) -> list[tuple[str, str]]:
        return [(nivel, getattr(self, nivel)) for nivel in NIVEIS]


# A ordem dos níveis do caminho, e o nome de cada um nas mensagens.
NIVEIS = ("et", "capitulo", "sistema", "subsistema", "pasta")
NOMES_DOS_NIVEIS = {"et": "ET", "capitulo": "pasta do capítulo", "sistema": "pasta do sistema",
                    "subsistema": "pasta do subsistema", "pasta": "pasta final"}
_SEPARADOR_DE_PASTA = re.compile(r"\s*[/\\]\s*")


def _nome_de_pasta(nome: str, campo: str, *, obrigatorio: bool) -> str:
    nome = " ".join(str(nome or "").split())
    if not nome:
        if obrigatorio:
            raise ErroDocPack(f"falta a {campo}")
        return ""
    if _RESERVADOS.search(nome) or nome in (".", "..") or nome.endswith("."):
        raise ErroDocPack(f"a {campo} {nome!r} tem caractere que o Windows não aceita")
    return nome


def partes_do_nivel(valor: str, campo: str = "pasta") -> list[str]:
    """As pastas de um nível: uma, ou mais separadas por `/` (a pasta extra daquele
    passo). Cada uma conferida como nome de pasta do Windows."""
    texto = " ".join(str(valor or "").split())
    if not texto:
        return []
    return [_nome_de_pasta(parte, campo, obrigatorio=True)
            for parte in _SEPARADOR_DE_PASTA.split(texto.strip("/\\ ")) if parte.strip()]


def partes_do_caminho(destino: Destino) -> list[str]:
    """As pastas, da ET ao dossiê; `ErroDocPack` se falta a ET ou um nível abaixo dela."""
    partes = []
    for nivel, valor in destino.niveis():
        campo = NOMES_DOS_NIVEIS[nivel]
        if nivel == "et" and not str(valor or "").strip():
            raise ErroDocPack(f"falta a {campo}")
        partes.extend(partes_do_nivel(valor, campo))
    if len(partes) < 2:
        raise ErroDocPack("falta a pasta do dossiê abaixo da ET (capítulo, sistema, subsistema ou pasta final)")
    return partes


def pasta_do_dossie(raiz: str | Path, destino: Destino) -> Path:
    """O caminho do dossiê, ou `ErroDocPack` se falta a ET ou o que vem abaixo dela."""
    return Path(raiz).joinpath(*partes_do_caminho(destino))


def nome_do_subsistema(destino: Destino) -> str:
    """O subsistema do dossiê, para a linha 3 do `_STATUS_PMIB` e a Aplicação LMR: a
    pasta do subsistema; sem ela, a pasta final; sem as duas, a última pasta do caminho."""
    for nivel in ("subsistema", "pasta"):
        partes = partes_do_nivel(getattr(destino, nivel))
        if partes:
            return partes[-1]
    partes = partes_do_caminho(destino)
    return partes[-1]


def arvore_existente(raiz: str | Path | None, profundidade: int = 4) -> dict:
    """As pastas que já existem sob a raiz, até `profundidade` níveis:
    `{nome: {subpasta: {...}}}`, sem as escondidas nem as que o levantamento ignora
    (obsoleto, testes, backup, DATASHEETS)."""
    if not raiz or not os.path.isdir(raiz):
        return {}

    def filhas(pasta: Path, nivel: int) -> dict:
        if nivel >= profundidade:
            return {}
        try:
            nomes = sorted(p.name for p in pasta.iterdir()
                           if p.is_dir() and not p.name.startswith((".", "~"))
                           and p.name.upper() not in SUBPASTAS
                           and status_pmib_arquivos.motivo_para_ignorar(f"{p.name}\\x") is None)
        except OSError:
            return {}
        return {nome: filhas(pasta / nome, nivel + 1) for nome in nomes}

    return filhas(Path(raiz), 0)


def opcoes_do_nivel(arvore: dict, destino: Destino, nivel: str) -> list[str]:
    """As pastas que já existem para `nivel`, dentro das pastas escolhidas nos níveis
    de cima (os vazios abaixo da ET são pulados). Sem a ET, ou com pasta nova em cima,
    não há sugestão embaixo."""
    if nivel != "et" and not str(destino.et or "").strip():
        return []   # sem a ET, não há onde procurar
    galho = arvore
    for acima, valor in destino.niveis():
        if acima == nivel:
            break
        try:
            partes = partes_do_nivel(valor)
        except ErroDocPack:
            return []
        for parte in partes:
            galho = next((filhos for nome, filhos in galho.items() if nome.upper() == parte.upper()), None)
            if galho is None:
                return []
    return sorted(galho)


def pastas_existentes(raiz: str | Path | None) -> dict:
    """Compatibilidade: a árvore com os dois primeiros níveis, `{ET: {capítulo: {}}}`."""
    return arvore_existente(raiz, profundidade=2)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
@dataclass
class Templates:
    status_pmib: str = ""
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
    for sub in SUBPASTAS:
        passos.append(Passo(pasta / sub, "pasta", (pasta / sub).is_dir()))
    if templates.aplicacao_lmr:
        arquivos.append(pasta / "LMR" / nome_da_aplicacao_lmr(templates.aplicacao_lmr, nome_do_subsistema(destino)))
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
            valores = {CELULA_TITULO_STATUS: texto_do_titulo(lista, nome_do_subsistema(destino))}
            if revisao:
                valores[CELULA_REVISAO_STATUS] = texto_da_revisao(revisao, hoje)
            else:
                resultado.avisos.append("sem revisão na mapeadora: a linha 4 ficou a do template")
            _escrever(status, ABA_STATUS, valores)
            resultado.criados.append(status)
        else:
            resultado.avisos.append(f"{status.name} já existia: ficou como estava")
        # 2. A Aplicação LMR.
        if templates.aplicacao_lmr:
            lmr = arquivos[-1]
            if _copiar(templates.aplicacao_lmr, lmr):
                resultado.criados.append(lmr)
                valores = {ROTULO_LISTA: codigo,
                           ROTULO_ET: " / ".join(p for p in (lista.especificacao, lista.capitulo) if p),
                           ROTULO_SUBSISTEMA: nome_do_subsistema(destino)}
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
        log_cb("O link de cada dossiê vai para a mapeadora agora (LINK DA PLANILHA vazio); SITUAÇÃO e "
               "REVISÃO EM USO o Gestão PMIB atualiza na próxima rodada.")
    return resultados


# --------------------------------------------------------------------------
# O link na mapeadora (2026-11-05)
# --------------------------------------------------------------------------
TEXTO_DO_LINK = "Abrir Box"   # o mesmo do Gestão PMIB (`pmib_manager._gravar_na_mestra`)


def arquivo_status_do_dossie(resultado: Resultado) -> Path | None:
    """O `_STATUS_PMIB` que o dossiê tem, ou `None`."""
    if resultado.situacao == "falhou" or resultado.pasta is None:
        return None
    caminho = Path(resultado.pasta) / f"{resultado.codigo}_STATUS_PMIB.xlsx"
    return caminho if caminho.exists() else None


def gravar_links(caminho_mapeadora: str | Path, resultados: list[Resultado], *,
                 log_cb: Log = print, retry_lock: Callable[[object], bool] | None = None) -> int:
    """[2026-11-05] Pedido do Jonathan: o dossiê novo já entra na mapeadora com o
    LINK DA PLANILHA ("Abrir Box", relativo à pasta da mapeadora, como o Gestão
    PMIB grava), para a Conferência de Listas achá-lo sem esperar o próximo Gestão
    PMIB. **Só preenche link VAZIO**: link que já existe (de outro `_STATUS_PMIB`)
    não é trocado. Devolve quantos links gravou."""
    from openpyxl import load_workbook

    from sigft.core.excel.locking import salvar_perguntando
    from sigft.services.pmib_manager import COLUNA_CHAVE_SOBRESSALENTES, NOME_ABA_SOBRESSALENTES, achar_aba

    alvos = {r.codigo.strip().upper(): a for r in resultados if (a := arquivo_status_do_dossie(r))}
    if not alvos:
        return 0
    pasta_mapeadora = os.path.dirname(os.path.abspath(caminho_mapeadora))
    wb = load_workbook(caminho_mapeadora)
    try:
        ws, motivo = achar_aba(wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)
        if ws is None:
            log_cb(f"⚠️ Link na mapeadora: não achei a aba de sobressalentes ({motivo}).")
            return 0
        colunas = {c.value: i + 1 for i, c in enumerate(ws[2]) if c.value}
        col_doc, col_link = colunas.get(COLUNA_CHAVE_SOBRESSALENTES), colunas.get("LINK DA PLANILHA")
        if not col_doc or not col_link:
            log_cb("⚠️ Link na mapeadora: falta a coluna N° DOCUMENTO ITAIPU ou LINK DA PLANILHA.")
            return 0
        gravados = []
        for linha in range(3, ws.max_row + 1):
            codigo = str(ws.cell(row=linha, column=col_doc).value or "").strip().upper()
            if codigo not in alvos:
                continue
            celula = ws.cell(row=linha, column=col_link)
            if celula.hyperlink is not None and getattr(celula.hyperlink, "target", None):
                log_cb(f"   ⏭️ {codigo}: a mapeadora já tem link, ficou o que estava.")
                continue
            celula.value = TEXTO_DO_LINK
            celula.hyperlink = os.path.relpath(alvos[codigo], start=pasta_mapeadora)
            gravados.append(codigo)
        if not gravados:
            return 0
        try:
            salvar_perguntando(wb, caminho_mapeadora, retry_lock=retry_lock)
        except PermissionError:
            log_cb("❌ Link na mapeadora: o arquivo está aberto no Excel; os links não foram gravados. "
                   "Rode o Gestão PMIB depois para ligá-los.")
            return 0
        for codigo in gravados:
            log_cb(f"   🔗 {codigo}: link gravado na mapeadora.")
        return len(gravados)
    finally:
        wb.close()


# --------------------------------------------------------------------------
# A sugestão da IA
# --------------------------------------------------------------------------
TAREFA_IA = "docpack_pasta"


def ler_sugestao(dados) -> Destino | None:
    """O `{et, capitulo, sistema, subsistema, pasta}` que a IA devolveu, ou `None`.
    Aceita texto (com prosa ou cerca de código em volta) ou o JSON já lido.

    Sem a chave `et` é a resposta do formato de antes (2026-11-03), em que a primeira
    pasta se chamava "capitulo" e a final "pasta" (ou "subsistema"): ela é lida no
    vocabulário novo (a primeira pasta é a ET, o "sistema" de antes é o capítulo, e a
    pasta final de antes é o subsistema)."""
    if isinstance(dados, str):
        from sigft.core.llm.client import _NADA, _json_tolerante
        lido = _json_tolerante(dados)
        dados = None if lido is _NADA else lido
    if isinstance(dados, list) and dados:
        dados = dados[0]
    if not isinstance(dados, dict):
        return None

    def campo(*nomes) -> str:
        return next((str(dados[n]).strip() for n in nomes if str(dados.get(n) or "").strip()), "")

    if "et" in dados:
        destino = Destino(campo("et"), campo("capitulo"), campo("sistema"), campo("subsistema"), campo("pasta"))
    else:
        destino = Destino(campo("capitulo"), campo("sistema", "subsistema_intermediario"), "",
                          campo("pasta", "subsistema"), "")
    try:
        partes_do_caminho(destino)
    except ErroDocPack:
        return None
    return destino


def _arvore_para_a_ia(arvore: dict) -> dict | list:
    """A árvore em JSON curto: o galho sem filhos vira lista de nomes, para o prompt
    não crescer à toa."""
    if not isinstance(arvore, dict):
        return arvore
    if all(not filhos for filhos in arvore.values()):
        return sorted(arvore)
    return {nome: _arvore_para_a_ia(filhos) for nome, filhos in arvore.items()}


def sugerir_destino(lista: ListaNaMapeadora, existentes: dict, llm) -> tuple[Destino | None, str]:
    """(sugestão, motivo) da IA para onde vai o dossiê. Nunca levanta: falha vira
    `(None, motivo da falha)`. A sugestão só preenche os campos; quem confirma é a pessoa."""
    prompt = prompts.montar_docpack_pasta(
        codigo=lista.codigo, titulo=lista.descricao, especificacao=lista.especificacao,
        capitulo=lista.capitulo, pastas_existentes=json.dumps(_arvore_para_a_ia(existentes), ensure_ascii=False,
                                                              indent=1))
    try:
        resposta = llm.generate(prompt, json_mode=True, tags={"modulo": "docpack", "tarefa": TAREFA_IA})
    except Exception as erro:  # noqa: BLE001 -- a IA é um atalho; sem ela, digita-se
        return None, f"a IA não respondeu: {erro}"
    dados = getattr(resposta, "parsed_json", None)
    destino = ler_sugestao(dados if dados is not None else getattr(resposta, "text", ""))
    if destino is None:
        return None, "a IA respondeu sem a ET ou sem uma pasta abaixo dela"
    motivo = dados.get("motivo", "") if isinstance(dados, dict) else ""
    return destino, str(motivo or "")

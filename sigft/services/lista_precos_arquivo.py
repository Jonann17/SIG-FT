"""Lista de Preços — o arquivo da lista com preço de cada sistema (2026-11-05).

Pedido do Jonathan: o DocPack deixou de mexer com lista de preços (o agente do
webhook não olha para isso), e ela virou um módulo à parte, com duas partes:

* **Criar / preencher** (varredura da pasta raiz): para cada sistema com
  `_STATUS_PMIB` vivo, diz se há lista com preço na pasta; onde não há, copia o
  template como `<código PB021>.xlsm` (Capa F37 = código, E27 = título) e, se o
  `_STATUS_PMIB` já tem materiais, copia-os para a aba "Lista de Materiais".
* **Conferir** (UMA pasta, escolhida): compara os itens da lista com preço com os
  do `_STATUS_PMIB` e lista as divergências; "Atualizar" reescreve os materiais da
  lista a partir do `_STATUS_PMIB`. **Lista já valorizada** (algum VALOR
  UNITÁRIO preenchido): o app avisa, e a atualização mantém o preço de cada item
  que continua (o casado pelo CÓDIGO PMIB, ou pelo código de material, ou pela
  descrição); item novo entra sem preço, e o que saiu vai para o log.

Regras que não se negociam:

* **Nunca inventa preço.** VALOR UNITÁRIO só sai daqui se já estava na lista.
* **Nunca sobrescreve arquivo** na criação (`open(..., "xb")`).
* **Escrita no XML** (`core/excel/cirurgico.py`): o openpyxl apagaria o VBA do
  `.xlsm` e as validações do template. O openpyxl só LÊ.

Este é o ARQUIVO da lista com preço. O pareamento das listas no Aconex (que lista
de sobressalentes cada lista de preços copia) é `lista_precos.py`; a aba
"Lista de preços Follow-up" da mapeadora é `lista_precos_planilha.py`.

Desenho: `docs/superpowers/specs/2026-11-05-lista-de-precos-design.md`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from sigft.core.excel import pmib_codes
from sigft.core.excel.cirurgico import PlanilhaXlsx, ref
from sigft.services import status_pmib_arquivos
from sigft.services.docpack_etapa2 import (
    ABA,
    _ler_aba,
    _normalizar,
    _numero,
    _texto,
    _vazio,
    achar_cabecalho,
)

Log = Callable[[str], None]

NOME_TEMPLATE = "Lista de Sobressalentes com preço.xlsm"
ABA_CAPA = "Capa"
CELULA_CODIGO = "F37"
CELULA_TITULO = "E27"
SUFIXO_TITULO = " - LISTA DE SOBRESSALENTE COM PREÇO"

_PB020 = re.compile(r"PB020(-0\d)?$", re.IGNORECASE)
# O nome de um arquivo de lista com preço: PB021 (vigente) ou PB020-0x (legado), nunca
# o `_STATUS_PMIB` (a mesma regra do `painel.ler_listas_precos`).
_ARQUIVO_DE_PRECO = re.compile(r"PB021|PB020-0\d", re.IGNORECASE)

# Cabeçalho (normalizado: sem acento, maiúsculas) -> campo do `Item`, por planilha.
COLUNAS_PRECOS = {"ITEM": "item", "QTD.": "qtd", "UNID.": "unid", "DESCRICAO": "descricao",
                  "FABRICANTE / MODELO": "fabricante_modelo", "CODIGO DE MATERIAL": "codigo_material",
                  "CODIGO GE": "codigo_ge", "CODIGO PMIB": "codigo_pmib", "VALOR UNITARIO": "valor",
                  "TIPO DE ENTREGA": "tipo_entrega"}
COLUNAS_STATUS = {"ITEM": "item", "QTD.": "qtd", "UNID.": "unid", "DESCRICAO": "descricao",
                  "CODIGO DO MATERIAL": "codigo_material", "MARCA/MODELO": "fabricante_modelo",
                  "CODIGO PMIB": "codigo_pmib", "TIPO DE ENTREGA": "tipo_entrega"}
# Colunas que não dizem "há material nesta linha": o template já vem com ITEM numerado
# e com exemplos de TIPO DE ENTREGA.
_SO_DO_TEMPLATE = {"item", "tipo_entrega"}
# O que a conferência compara, além de presença.
CAMPOS_CONFERIDOS = (("qtd", "QTD."), ("unid", "UNID."), ("descricao", "DESCRIÇÃO"))


class ErroListaDePrecos(ValueError):
    """Código ou planilha que não dá para usar."""


def codigo_lista_de_precos(codigo: str) -> str:
    """O código da lista com preço: o mesmo, com o DCC PB021 no lugar do PB020. O `-0x`
    do formato antigo (`...PB020-01`) sai: a lista com preço de hoje é `...PB021`
    (`gestao-sobressalentes/03 - Processo/Lista de Precos.md`)."""
    codigo = str(codigo or "").strip()
    if not _PB020.search(codigo):
        raise ErroListaDePrecos(f"o código {codigo!r} não termina em PB020")
    return _PB020.sub("PB021", codigo)


def e_arquivo_de_lista_de_precos(nome: str) -> bool:
    nome = str(nome)
    return (bool(_ARQUIVO_DE_PRECO.search(nome)) and "STATUS_PMIB" not in nome.upper()
            and Path(nome).suffix.lower() in (".xlsm", ".xlsx"))


# ------------------------------------------------------------------ os itens

@dataclass(frozen=True)
class Item:
    item: object = ""
    qtd: object = ""
    unid: str = ""
    descricao: str = ""
    fabricante_modelo: str = ""
    codigo_material: str = ""
    codigo_ge: str = ""
    codigo_pmib: str = ""
    valor: object = None
    tipo_entrega: str = ""

    def chave(self) -> str:
        """Com que o item casa entre as duas planilhas: o CÓDIGO PMIB; sem ele, o código
        de material; sem os dois, a descrição."""
        pmib = pmib_codes.normalize_pmib(self.codigo_pmib) if self.codigo_pmib else ""
        if pmib:
            return f"PMIB:{pmib}"
        if self.codigo_material:
            return f"MAT:{_normalizar(self.codigo_material)}"
        return f"DESC:{_normalizar(self.descricao)}"

    def rotulo(self) -> str:
        return self.codigo_pmib or self.codigo_material or self.descricao or "?"


def _valor_da_celula(campo: str, valor):
    if campo in ("qtd", "valor", "item"):
        return None if _vazio(valor) else _numero(valor)
    return _texto(valor)


def ler_itens(caminho: str | Path, mapa: dict[str, str]) -> tuple[list[Item], int, dict[str, int]]:
    """(itens, linha do cabeçalho, {cabeçalho: coluna}) da aba "Lista de Materiais". Linha
    sem nada além de ITEM/TIPO DE ENTREGA (as do template) não é item."""
    linhas = _ler_aba(Path(caminho))
    numero, colunas = achar_cabecalho(linhas, mapa)
    colunas = {nome: col for nome, col in colunas.items() if nome in mapa}
    itens = []
    for linha in linhas[numero:]:
        dados = {}
        for nome, col in colunas.items():
            bruto = linha[col - 1] if col <= len(linha) else None
            dados[mapa[nome]] = _valor_da_celula(mapa[nome], bruto)
        if all(_vazio(v) for campo, v in dados.items() if campo not in _SO_DO_TEMPLATE):
            continue
        itens.append(Item(**{k: ("" if v is None and k != "valor" else v) for k, v in dados.items()}))
    return itens, numero, colunas


def valorizada(itens: list[Item]) -> bool:
    return any(not _vazio(i.valor) for i in itens)


# ------------------------------------------------------------------ os sistemas

@dataclass(frozen=True)
class Sistema:
    codigo: str
    pasta: Path
    status_pmib: Path
    lista: Path | None = None
    legado: bool = False
    materiais: int = 0               # itens no _STATUS_PMIB
    erro: str = ""                   # o _STATUS_PMIB não pôde ser lido


def achar_lista(pasta: Path, codigo: str) -> tuple[Path | None, bool]:
    """(arquivo da lista com preço na pasta, se é do formato legado PB020-0x). Primeiro o
    `<código PB021>`; senão, qualquer arquivo de lista com preço da pasta."""
    try:
        esperado = codigo_lista_de_precos(codigo)
    except ErroListaDePrecos:
        esperado = ""
    candidatos = sorted(p for p in Path(pasta).iterdir() if p.is_file() and e_arquivo_de_lista_de_precos(p.name))
    for p in candidatos:
        if esperado and p.stem.upper().startswith(esperado.upper()):
            return p, False
    if candidatos:
        return candidatos[0], "PB021" not in candidatos[0].name.upper()
    return None, False


def varrer(raiz: str | Path) -> list[Sistema]:
    """Um `Sistema` por `_STATUS_PMIB` vivo da raiz, com a lista com preço da mesma pasta."""
    sistemas = []
    for codigo, caminho in status_pmib_arquivos.listar(raiz).vivos:
        status = Path(caminho)
        lista, legado = achar_lista(status.parent, codigo)
        try:
            materiais, erro = len(ler_itens(status, COLUNAS_STATUS)[0]), ""
        except Exception as e:  # noqa: BLE001 -- planilha do usuário: vira motivo na tela
            materiais, erro = 0, str(e)
        sistemas.append(Sistema(codigo, status.parent, status, lista, legado, materiais, erro))
    return sistemas


def sistema_da_pasta(pasta: str | Path) -> Sistema:
    """O `Sistema` de UMA pasta: o `_STATUS_PMIB` dela (o único) e a lista com preço."""
    pasta = Path(pasta)
    status = sorted(p for p in pasta.iterdir() if p.is_file() and status_pmib_arquivos.codigo_do_arquivo(p.name))
    if not status:
        raise ErroListaDePrecos(f"a pasta {pasta.name} não tem _STATUS_PMIB")
    if len(status) > 1:
        raise ErroListaDePrecos(f"a pasta {pasta.name} tem {len(status)} _STATUS_PMIB: escolha a pasta de um sistema só")
    codigo = status_pmib_arquivos.codigo_do_arquivo(status[0].name)
    lista, legado = achar_lista(pasta, codigo)
    return Sistema(codigo, pasta, status[0], lista, legado)


# ------------------------------------------------------------------ a escrita

def _escrever_itens(caminho: Path, itens: list[Item], linha_cabecalho: int, colunas: dict[str, int],
                    linhas_antigas: int, *, capa: dict[str, str] | None = None) -> None:
    """Escreve `itens` logo abaixo do cabeçalho e limpa as linhas antigas que sobram
    (menos o ITEM, que o template traz numerado). Tudo no XML."""
    planilha = PlanilhaXlsx(caminho)
    parte = planilha.parte_da_aba(ABA)
    for n in range(1, max(len(itens), linhas_antigas) + 1):
        material = itens[n - 1] if n <= len(itens) else None
        for nome, coluna in colunas.items():
            campo = COLUNAS_PRECOS[nome]
            if material is None:
                if campo == "item":
                    continue
                valor = None
            else:
                valor = getattr(material, campo)
                if campo == "item":
                    valor = n
            planilha.escrever(parte, ref(linha_cabecalho + n, coluna), valor)
    if capa:
        parte_capa = planilha.parte_da_aba(ABA_CAPA)
        for referencia, valor in capa.items():
            planilha.escrever(parte_capa, referencia, valor)
    planilha.salvar()


def _para_a_lista(materiais: list[Item]) -> list[Item]:
    """Os itens do `_STATUS_PMIB` como itens da lista com preço: sem preço."""
    return [replace(m, valor=None) for m in materiais]


@dataclass
class Criacao:
    codigo: str
    situacao: str                    # "criada", "existia", "falhou"
    arquivo: Path | None = None
    materiais: int = 0
    motivo: str = ""


def criar_lista(sistema: Sistema, template: str | Path, *, titulo: str = "") -> Criacao:
    """Copia o template como `<código PB021>.xlsm` na pasta do sistema, com a Capa e os
    materiais do `_STATUS_PMIB`. Nunca sobrescreve: arquivo existente fica."""
    codigo = sistema.codigo
    try:
        nome = codigo_lista_de_precos(codigo) + (Path(template).suffix or ".xlsm")
    except ErroListaDePrecos as erro:
        return Criacao(codigo, "falhou", motivo=str(erro))
    destino = sistema.pasta / nome
    dados = Path(template).read_bytes()
    try:
        with open(destino, "xb") as saida:   # "x": nunca sobrescreve
            saida.write(dados)
    except FileExistsError:
        return Criacao(codigo, "existia", destino, motivo=f"{nome} já existia: ficou como estava")
    try:
        materiais = ler_itens(sistema.status_pmib, COLUNAS_STATUS)[0]
        _, numero, colunas = ler_itens(destino, COLUNAS_PRECOS)
        capa = {CELULA_CODIGO: codigo_lista_de_precos(codigo),
                CELULA_TITULO: (titulo or sistema.pasta.name) + SUFIXO_TITULO}
        # As linhas do template (ITEM numerado, exemplos de TIPO DE ENTREGA) são limpas
        # até onde os materiais chegam; o resto do template fica.
        _escrever_itens(destino, _para_a_lista(materiais), numero, colunas, len(materiais), capa=capa)
    except Exception as erro:  # noqa: BLE001 -- o arquivo criado pela metade sai: nada fica torto
        destino.unlink(missing_ok=True)
        return Criacao(codigo, "falhou", motivo=f"{type(erro).__name__}: {erro}")
    return Criacao(codigo, "criada", destino, len(materiais))


def criar_listas(sistemas: list[Sistema], template: str | Path, *, titulos: dict[str, str] | None = None,
                 log_cb: Log = print, progress_cb: Callable[[float], None] | None = None,
                 cancelado_cb: Callable[[], bool] | None = None) -> list[Criacao]:
    """Uma lista com preço por sistema, com o log do padrão (início, uma linha por
    sistema, resumo)."""
    titulos = titulos or {}
    log_cb(f"Lista de Preços: {len(sistemas)} sistema(s)")
    resultados = []
    for n, sistema in enumerate(sistemas):
        if cancelado_cb is not None and cancelado_cb():
            log_cb("Parada pedida: os sistemas que faltam ficaram para depois.")
            break
        r = criar_lista(sistema, template, titulo=titulos.get(sistema.codigo.strip().upper(), ""))
        resultados.append(r)
        if r.situacao == "criada":
            log_cb(f"  ✅ {r.codigo}: {r.arquivo.name}, {r.materiais} material(is), VALOR UNITÁRIO vazio")
        elif r.situacao == "existia":
            log_cb(f"  ⚠️ {r.codigo}: {r.motivo}")
        else:
            log_cb(f"  ❌ {r.codigo}: {r.motivo}")
        if progress_cb:
            progress_cb((n + 1) / max(len(sistemas), 1))
    contagem = {s: sum(r.situacao == s for r in resultados) for s in ("criada", "existia", "falhou")}
    log_cb(f"Lista de Preços: {contagem['criada']} criada(s), {contagem['existia']} já existia(m), "
           f"{contagem['falhou']} falha(s).")
    return resultados


# ------------------------------------------------------------------ a conferência

@dataclass(frozen=True)
class Divergencia:
    tipo: str                        # "falta_na_lista", "sobra_na_lista", "diferente"
    item: str                        # o rótulo do item (código PMIB, material ou descrição)
    campo: str = ""
    no_status: str = ""
    na_lista: str = ""


@dataclass
class Conferencia:
    sistema: Sistema
    itens_status: list[Item] = field(default_factory=list)
    itens_lista: list[Item] = field(default_factory=list)
    divergencias: list[Divergencia] = field(default_factory=list)

    @property
    def valorizada(self) -> bool:
        return valorizada(self.itens_lista)

    @property
    def em_dia(self) -> bool:
        return not self.divergencias


def _comparavel(campo: str, valor) -> str:
    if campo == "qtd":
        numero = _numero(valor)
        return "" if _vazio(numero) else str(numero)
    return _normalizar(valor)


def comparar(itens_status: list[Item], itens_lista: list[Item]) -> list[Divergencia]:
    da_lista = {i.chave(): i for i in itens_lista}
    do_status = {i.chave(): i for i in itens_status}
    divergencias = []
    for chave, s in do_status.items():
        lista = da_lista.get(chave)
        if lista is None:
            divergencias.append(Divergencia("falta_na_lista", s.rotulo(), no_status=s.descricao))
            continue
        for campo, rotulo in CAMPOS_CONFERIDOS:
            a, b = getattr(s, campo), getattr(lista, campo)
            if _comparavel(campo, a) != _comparavel(campo, b):
                divergencias.append(Divergencia("diferente", s.rotulo(), rotulo, _texto(a), _texto(b)))
    for chave, lista in da_lista.items():
        if chave not in do_status:
            divergencias.append(Divergencia("sobra_na_lista", lista.rotulo(), na_lista=lista.descricao))
    return divergencias


def conferir(pasta: str | Path) -> Conferencia:
    """Compara a lista com preço da pasta com o `_STATUS_PMIB` dela."""
    sistema = sistema_da_pasta(pasta)
    if sistema.lista is None:
        raise ErroListaDePrecos(f"a pasta {Path(pasta).name} não tem lista com preço: crie-a na aba Criar / preencher")
    itens_status = ler_itens(sistema.status_pmib, COLUNAS_STATUS)[0]
    itens_lista = ler_itens(sistema.lista, COLUNAS_PRECOS)[0]
    return Conferencia(sistema, itens_status, itens_lista, comparar(itens_status, itens_lista))


@dataclass
class Atualizacao:
    escritos: int
    precos_mantidos: int
    novos_sem_preco: list[str]
    removidos: list[str]


def atualizar(conferencia: Conferencia, *, log_cb: Log = print) -> Atualizacao:
    """Reescreve os materiais da lista com preço a partir do `_STATUS_PMIB`. O VALOR
    UNITÁRIO (e o CÓDIGO GE e o TIPO DE ENTREGA, que só a lista tem) de cada item que
    continua é MANTIDO; item novo entra sem preço; o que saiu do `_STATUS_PMIB` sai da
    lista e vai para o log. `PermissionError` (aberto no Excel) sobe."""
    sistema = conferencia.sistema
    antigos, numero, colunas = ler_itens(sistema.lista, COLUNAS_PRECOS)
    por_chave = {i.chave(): i for i in antigos}
    novos, mantidos, sem_preco = [], 0, []
    for material in conferencia.itens_status:
        anterior = por_chave.get(material.chave())
        if anterior is not None:
            item = replace(material, valor=anterior.valor,
                           codigo_ge=anterior.codigo_ge or material.codigo_ge,
                           tipo_entrega=anterior.tipo_entrega or material.tipo_entrega)
            if not _vazio(anterior.valor):
                mantidos += 1
        else:
            item = replace(material, valor=None)
            sem_preco.append(material.rotulo())
        novos.append(item)
    chaves_novas = {m.chave() for m in conferencia.itens_status}
    removidos = [i.rotulo() for i in antigos if i.chave() not in chaves_novas]
    _escrever_itens(sistema.lista, novos, numero, colunas, len(antigos))
    for rotulo in sem_preco:
        log_cb(f"   ➕ {rotulo}: item novo, sem VALOR UNITÁRIO")
    for rotulo in removidos:
        log_cb(f"   ➖ {rotulo}: saiu da lista (não está no _STATUS_PMIB)")
    log_cb(f"Lista atualizada: {len(novos)} item(ns), {mantidos} preço(s) mantido(s), "
           f"{len(sem_preco)} sem preço, {len(removidos)} removido(s).")
    return Atualizacao(len(novos), mantidos, sem_preco, removidos)

r"""As regras da montagem da ficha a partir da PLANILHA de PDMs (módulo 2).

POR QUE EXISTE
------------------------------------------------------------------------
Até 2026-09-24 a ficha só nascia da pasta *PDMs Modificados*, que o próprio
app gerava em dois passos (fatiar, formatar) e que PULAVA o que já existia:
revisado um PDM, a pasta não se atualizava. Rodando o fluxo antigo na planilha
de 23/09/2026 apareceram ainda o `(nan)` no lugar da ajuda vazia (78 PDMs), a
ordem do arquivo no lugar da SECUENCIA (1.140 PDMs) e dois códigos com PDMs
diferentes misturados numa ficha só.

Aqui mora o que decide, para cada material, QUAIS perguntas entram na ficha e
o que avisar: funções puras sobre o catálogo (`core/pdm_catalogo.py`),
testáveis sem Excel. Quem escreve a ficha é `services/pdm.py`; quem regenera
as pastas é `services/pdm_regeneracao.py`.

As regras numeradas (1 a 9) são as da seção 5 de
`docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md`.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Any

from sigft.core import pdm_catalogo
# As duas leituras do texto que o PORTAL devolve para o PDM
# ("CODIGO - NOME BASE, MODIFICADOR, R<n>") moram em `cria_fichas`, e
# `correcao_pdm_planilha.py` já importa de lá do mesmo jeito: uma segunda
# cópia seria o começo de duas regras divergindo.
from sigft.services.cria_fichas import codigo_do_pdm, revisao_do_pdm

# Os dois sentidos da divergência de revisão (regras 4 e 5).
PORTAL_ATRAS = "portal_atras"
PLANILHA_ATRAS = "planilha_atras"

MSG_SEM_CARACTERISTICAS = (
    "Esta planilha nao traz as caracteristicas dos PDMs (e o formato antigo, "
    "com as abas 'PDMs' e 'Instrucoes PDMs'). Use a exportacao da Itaipu, com "
    "a aba TEMPLATE_PDM."
)

# O texto que o `str()` do pandas produz para célula vazia. O passo antigo
# "Formatar" lê o PDM com o pandas, e era daí que vinha o "(nan)" na ficha.
_AJUDA_VAZIA = {"", "NAN", "NONE"}

# ", R<n>" no fim do "PDM usado": a mesma forma que `cria_fichas.revisao_do_pdm`
# lê. Aqui ela só é RETIRADA, para sobrar o título.
_RE_REVISAO_NO_FIM = re.compile(r",\s*R\d+\s*$", re.IGNORECASE)
_RE_CODIGO = re.compile(r"PDM\.\d{4}\.\d{3}", re.IGNORECASE)

# `\ / : * ? " < > |` não entram em nome de arquivo no Windows. Três títulos da
# planilha de 23/09/2026 têm "/" (`EXTENSAO/TRONCO TORRE`...), e é por eles que
# o fatiamento antigo falha: a barra vira separador de pasta.
_PROIBIDOS_NO_NOME = re.compile(r'[\\/:*?"<>|]')

# " - R<n>" no fim do nome, antes da extensão ou do "_formatado".
_RE_REVISAO_NO_NOME = re.compile(r" - R(\d+)(?:_formatado)?\.[A-Za-z]+$", re.IGNORECASE)


class PDMRecusado(ValueError):
    """A ficha deste material NÃO pode ser montada pela planilha. A mensagem
    diz por quê e já vem pronta para o log."""


@dataclass(frozen=True)
class PerguntasDoPDM:
    """As perguntas de UM material, e a conferência de revisão com o portal."""

    pdm: Any                      # `pdm_catalogo.PDM`
    linhas: tuple[str, ...]       # "N - NOME (AJUDA):", já numeradas
    # "" quando as revisões batem ou não há como comparar (regra 9);
    # PORTAL_ATRAS (regra 4) ou PLANILHA_ATRAS (regra 5) quando divergem.
    divergencia: str = ""
    causa: str = ""
    consequencia: str = ""


# =============================================================================
# O texto da pergunta (regra 3)
# =============================================================================
def _texto_de_ajuda(ajuda) -> str:
    if ajuda is None:
        return ""
    if isinstance(ajuda, float) and math.isnan(ajuda):
        return ""
    texto = str(ajuda).strip()
    return "" if texto.upper() in _AJUDA_VAZIA else texto


def montar_pergunta(numero, nome, ajuda) -> str:
    """`"N - NOME (AJUDA):"`, ou `"N - NOME:"` quando não há ajuda.

    Sem os parênteses vazios de propósito: o Tradutor (4.2) corta a pergunta no
    primeiro "(" e tira o ":" do fim, então os dois formatos viram o mesmo
    `"N - NOME"` lá, e é esse nome que o Upload Specs (4.3) casa com o Master.
    Nome e ajuda saem como vieram, só sem espaço nas pontas: o casamento do
    4.3 é por igualdade."""
    nome = "" if nome is None else str(nome).strip()
    ajuda = _texto_de_ajuda(ajuda)
    if ajuda:
        return f"{numero} - {nome} ({ajuda}):"
    return f"{numero} - {nome}:"


# =============================================================================
# O catálogo inteiro (regra 8) e a linha de início do log
# =============================================================================
def conferir_catalogo(catalogo) -> None:
    """Levanta `PDMRecusado` quando a planilha não traz característica
    nenhuma: o formato manipulado antigo, que só tem o título dos PDMs."""
    if not any(p.caracteristicas_em_ordem for p in catalogo.pdms):
        raise PDMRecusado(MSG_SEM_CARACTERISTICAS)


def descrever_catalogo(catalogo) -> str:
    """A linha de início do lote. A data da exportação é o que torna visível,
    no log, uma planilha velha."""
    nome = os.path.basename(catalogo.origem) if catalogo.origem else "(sem nome)"
    quando = f", exportada em {catalogo.exportado_em}" if catalogo.exportado_em else ""
    return f"Planilha de PDMs: {nome}{quando}: {len(catalogo)} PDM(s)."


# =============================================================================
# O código com mais de um nome base (regra 6)
# =============================================================================
def titulo_do_pdm_usado(texto) -> str:
    """O título do "PDM usado", sem código, sem revisão e sem vírgula.

    `"PDM.3010.007 - ACOPLAMENTO, ROSCADO, R1"` -> `"ACOPLAMENTO ROSCADO"`;
    `"PDM.4120.000 - UNIDADE EVAPORADORA, , R1"` -> `"UNIDADE EVAPORADORA"`
    (a vírgula dupla é o modificador vazio, formato medido em 2026-09-23)."""
    bruto = str(texto or "")
    achado = _RE_CODIGO.search(bruto)
    if achado:
        bruto = bruto[achado.end():]
    bruto = _RE_REVISAO_NO_FIM.sub("", bruto)
    return pdm_catalogo.normalizar(bruto.replace(",", " ").strip(" -"))


def outras_identidades(pdm) -> list:
    """As identidades do código cujo NOME BASE não é o da revisão vigente.

    Vazia no PDM comum. Cheia nos dois códigos da planilha de 23/09/2026 que
    trazem PDMs diferentes (`PDM.3010.007`: ACOPLAMENTO ROSCADO e FIXADOR). É
    pelo nome base, e não pelo título, que isso se separa do histórico
    legítimo de revisão, em que só o modificador muda (`SERVIDOR CONSOLE`
    virou `SERVIDOR`)."""
    base = pdm_catalogo.normalizar(pdm.nome_base)
    return [i for i in pdm.identidades if pdm_catalogo.normalizar(i.nome_base) != base]


def descrever_identidades(identidades) -> str:
    """`"ACOPLAMENTO ROSCADO (R1), FIXADOR (R0)"`."""
    return ", ".join(
        f"{i.titulo} (R{'?' if i.revisao is None else i.revisao})" for i in identidades
    )


def _comeca_pelo_nome_base(titulo, nome_base) -> bool:
    base = pdm_catalogo.normalizar(str(nome_base or "").replace(",", " "))
    return bool(base) and (titulo == base or titulo.startswith(base + " "))


# =============================================================================
# As perguntas de um material (regras 1 a 7 e 9)
# =============================================================================
def perguntas_do_pdm(catalogo, pdm_usado) -> PerguntasDoPDM:
    """As perguntas do PDM que o `_STATUS_PMIB` associa ao material.

    Levanta `PDMRecusado` quando a ficha não pode ser montada (regras 6 e 7).
    Revisão diferente da do portal NÃO recusa (decisão do usuário,
    2026-09-23): a ficha sai com a revisão da planilha, e o resultado diz o
    sentido da divergência para o lote avisar."""
    texto = str(pdm_usado or "").strip()
    codigo = codigo_do_pdm(texto)
    if not codigo:
        raise PDMRecusado(f"o 'PDM usado' esta vazio ou sem codigo de PDM: '{texto}'")

    pdm = catalogo.por_codigo(codigo)
    if pdm is None:
        quando = f" (exportada em {catalogo.exportado_em})" if catalogo.exportado_em else ""
        raise PDMRecusado(f"{codigo} nao esta na planilha de PDMs{quando}")
    if not pdm.caracteristicas_em_ordem:
        raise PDMRecusado(f"{codigo} nao tem nenhuma caracteristica na planilha")

    if outras_identidades(pdm):
        pedido = titulo_do_pdm_usado(texto)
        if not _comeca_pelo_nome_base(pedido, pdm.nome_base):
            raise PDMRecusado(
                f"{codigo} aparece na planilha com mais de um nome base: "
                f"{descrever_identidades(pdm.identidades)}. O STATUS pede "
                f"'{pedido}'. Confira com a Itaipu; a ficha nao foi gerada."
            )

    linhas = tuple(
        montar_pergunta(numero, c.nome, c.ajuda)
        for numero, c in enumerate(pdm.caracteristicas_em_ordem, start=1)
    )

    no_portal = revisao_do_pdm(texto)
    if no_portal is None or pdm.revisao is None or no_portal == pdm.revisao:
        return PerguntasDoPDM(pdm=pdm, linhas=linhas)
    if no_portal < pdm.revisao:
        return PerguntasDoPDM(
            pdm=pdm, linhas=linhas, divergencia=PORTAL_ATRAS,
            causa=f"{codigo} esta na R{no_portal} no portal e na R{pdm.revisao} na planilha",
            consequencia=f"a ficha saiu com a R{pdm.revisao}; o PDM precisa subir de revisao no portal",
        )
    return PerguntasDoPDM(
        pdm=pdm, linhas=linhas, divergencia=PLANILHA_ATRAS,
        causa=f"{codigo} esta na R{no_portal} no portal, mas a planilha so tem a R{pdm.revisao}",
        consequencia=f"a ficha saiu com a R{pdm.revisao}; exporte uma planilha nova da Itaipu",
    )


# =============================================================================
# Nome de arquivo com a revisão (regeneração das pastas e método antigo)
# =============================================================================
def nome_de_arquivo(pdm, sufixo="") -> str:
    """`"PDM_1650_001 - ACUMULADOR - R2" + sufixo + ".xlsx"`.

    O código vem primeiro, na forma que o método antigo procura
    (`PDM_1650_001`), seguido de " - ": é o que as guardas antigas de "já
    existe" esperam. Sem revisão legível, fica sem o " - R<n>"."""
    base = f"{pdm.codigo.replace('.', '_')} - {pdm.titulo}"
    if pdm.revisao is not None:
        base += f" - R{pdm.revisao}"
    base = " ".join(_PROIBIDOS_NO_NOME.sub("-", base).split()).rstrip(". ")
    return f"{base}{sufixo}.xlsx"


def revisao_no_nome(nome_arquivo) -> int | None:
    """O `n` de `" - R<n>"` no fim do nome (antes da extensão ou do
    `_formatado`), ou `None` quando o nome não traz revisão."""
    achado = _RE_REVISAO_NO_NOME.search(os.path.basename(str(nome_arquivo or "")))
    return int(achado.group(1)) if achado else None

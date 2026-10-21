"""O resumo do fim do lote, sem Qt (2026-10-21, etapa 1b).

A janela de resumo (`app_qt/widgets/resumo_lote.py`) e o aviso do Windows leem
daqui: agrupar as linhas de erro e aviso pela ficha (o código PMIB da linha), o
texto do "Copiar lista", as frases e o arquivo do "Abrir log". Não depende de
cada serviço devolver um resultado (a maioria não devolve): lê o que já se loga,
com o nível de `niveis_log`.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sigft.app import niveis_log
from sigft.core.log_execucao import nome_de_arquivo

# Os testes desligam a janela (tests/conftest.py): dezenas de testes de tela rodam
# tarefa com erro DE PROPÓSITO, e cada um deixaria uma janela por cima do seguinte.
ENV_DESLIGAR = "SIGFT_SEM_RESUMO_DO_LOTE"
SEM_CODIGO = "Sem código PMIB"

# O código PMIB completo da linha. Local, e não `pmib_codes.find_pmib_code_in_text`:
# aquele acha o fim de um número mais longo ("12345678901.5" dava "2345678901.5");
# aqui o código não pode vir colado a outro dígito (revisão de 2026-10-21).
_CODIGO_PMIB = re.compile(r"(?<!\d)\d{10}\.\d+")

# A duração que o `RelatorioLote` cola no fim da linha do item
# (`core/relatorio_lote.formatar_duracao`: "1,2s", "3min 04s", "1h 02min").
# O resumo do fim do lote repete a falha SEM ela; para não contar a mesma falha
# duas vezes, a comparação ignora esse final (revisão de 2026-10-21).
_DURACAO_NO_FIM = re.compile(r"\s*\((\d+,\d+s|\d+min \d+s|\d+h \d+min)\)$")

# O começo "Módulo:" de alguns títulos de tela, que no título da janela daria
# "Resumo: Módulo: Cópia..." (revisão de 2026-10-21).
_PREFIXO_MODULO = re.compile(r"^\s*módulo\s*:\s*", re.IGNORECASE)


@dataclass(frozen=True)
class Grupo:
    codigo: str                              # "" = as linhas sem código PMIB
    linhas: tuple[tuple[str, str], ...]      # (texto, nível)

    @property
    def rotulo(self) -> str:
        return self.codigo or SEM_CODIGO


def nome_da_tela(titulo: str) -> str:
    """O título da tela sem o "Módulo:" do começo."""
    return _PREFIXO_MODULO.sub("", str(titulo)).strip() or str(titulo).strip()


def codigo_pmib(texto: str) -> str:
    """O primeiro código PMIB completo de `texto`, ou ""."""
    achado = _CODIGO_PMIB.search(texto)
    return achado.group(0) if achado else ""


def ligado() -> bool:
    return not os.environ.get(ENV_DESLIGAR)


def contagem(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def frase_da_contagem(erros: int, avisos: int) -> str:
    partes = []
    if erros:
        partes.append(contagem(erros, "erro", "erros"))
    if avisos:
        partes.append(contagem(avisos, "aviso", "avisos"))
    return " e ".join(partes) if partes else "nenhum erro nem aviso"


def frase_do_fim(titulo: str, erros: int, avisos: int, *, falhou: bool = False) -> str:
    """A frase do aviso do Windows no fim da tarefa."""
    if falhou:
        return f"{titulo} parou com erro. Veja o console."
    if erros or avisos:
        return f"{titulo} terminou com {frase_da_contagem(erros, avisos)}."
    return f"{titulo} terminou sem erro nem aviso."


def agrupar(pares: Iterable[tuple[str, str]]) -> list[Grupo]:
    """As linhas de erro e aviso de `pares` (texto, nível), por código PMIB, na
    ordem em que cada código apareceu; as sem código no fim. Linha repetida no
    mesmo grupo entra uma vez, comparada sem a duração do fim: o resumo do
    `RelatorioLote` repete as falhas sem ela. Fica o texto da primeira."""
    por_codigo: dict[str, list[tuple[str, str]]] = {}
    vistos: set[tuple[str, str]] = set()
    for texto, nivel in pares:
        if nivel not in (niveis_log.ERRO, niveis_log.AVISO):
            continue
        texto = str(texto).strip()
        codigo = codigo_pmib(texto)
        chave = (codigo, _DURACAO_NO_FIM.sub("", texto))
        if chave in vistos:
            continue
        vistos.add(chave)
        por_codigo.setdefault(codigo, []).append((texto, nivel))
    grupos = [Grupo(codigo, tuple(linhas)) for codigo, linhas in por_codigo.items() if codigo]
    if "" in por_codigo:
        grupos.append(Grupo("", tuple(por_codigo[""])))
    return grupos


def contar(grupos: Iterable[Grupo]) -> tuple[int, int]:
    """(erros, avisos) dos grupos."""
    niveis = [nivel for grupo in grupos for _texto, nivel in grupo.linhas]
    return niveis.count(niveis_log.ERRO), niveis.count(niveis_log.AVISO)


def texto_para_copiar(titulo: str, grupos: list[Grupo]) -> str:
    erros, avisos = contar(grupos)
    linhas = [f"{titulo}: {frase_da_contagem(erros, avisos)}", ""]
    for grupo in grupos:
        linhas.append(grupo.rotulo)
        linhas += [f"  {texto}" for texto, _nivel in grupo.linhas]
        linhas.append("")
    return "\n".join(linhas).rstrip("\n") + "\n"


def gravar_log(titulo: str, pares, pasta, agora: datetime) -> Path:
    """Tudo o que o lote escreveu no console, num arquivo em `pasta` (criada se
    faltar), com o nome de `log_execucao.nome_de_arquivo`."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome_de_arquivo(titulo, agora)
    corpo = [f"{titulo}: {agora:%d/%m/%Y %H:%M:%S}", ""] + [f"> {texto}" for texto, _nivel in pares]
    caminho.write_text("\n".join(corpo) + "\n", encoding="utf-8")
    return caminho

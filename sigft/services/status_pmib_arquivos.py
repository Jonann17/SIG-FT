r"""
sigft/services/status_pmib_arquivos.py — quais `_STATUS_PMIB` são controle VIVO,
e a linha da revisão em uso.

T3-a e T3-f do roteiro "Gestão PMIB no tratamento v2" (`gestao-sobressalentes/07
- Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`). Usado pelo
Gestão PMIB, pelo export de autorizados e pelo painel -- os três têm de
enxergar os MESMOS arquivos, senão os números não batem.

Pastas e cópias que não são controle (T3-a)
-------------------------------------------
Defeito encontrado em 05/10/2026: o `os.walk` do Gestão PMIB entrava também em
`testes_autospec/`. Para `#ST00=B01BMU10&EPB020`, o link "Abrir Box" da
mapeadora apontava para a cópia de teste, e a contagem podia vir dela -- a
última encontrada sobrescrevia, em silêncio. As exclusões abaixo são as mesmas
de `IGNORAR_PASTAS`/`IGNORAR_ARQUIVOS` em `regras_sobressalentes.py` (cofre),
que o Power BI v2 também segue. Comparadas sem acento e sem caixa.

Dois arquivos VIVOS com o mesmo código: fica o modificado por último, e o
levantamento DIZ que havia outro -- nunca em silêncio.

A revisão em uso (T3-f)
-----------------------
No layout v2, a linha acima do cabeçalho diz qual revisão da lista está em uso:
"REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO:
03/09/2026". O Gestão PMIB a leva para a coluna REVISÃO EM USO da mapeadora.
Achada pelo TEXTO, nunca pela coordenada; sem a linha, ou sem revisão ("—"),
a mapeadora não é tocada.

Só stdlib.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from sigft import config
from sigft.services.autorizacao import normalizar

IGNORAR_PASTAS = ("00 - OBSOLETO", "10- TESTES", "TESTES_AUTOSPEC", "\\DATASHEETS\\", "BACKUP", "OBSOLETO")
IGNORAR_ARQUIVOS = ("~$", " - COPY", "- CÓPIA", "COPIA", "COMENT", "RESPOSTA")

SUFIXO = "_STATUS_PMIB"
EXTENSOES = (".xlsx", ".xls")


def motivo_para_ignorar(caminho_relativo: str) -> str | None:
    """Por que este arquivo NÃO é controle vivo -- ou `None` se é.

    `caminho_relativo`: relativo à pasta raiz (as exclusões olham as pastas
    DENTRO dela, não o caminho até ela). Aceita `/` e `\\`.
    """
    partes = re.split(r"[\\/]+", str(caminho_relativo).strip("\\/"))
    nome = normalizar(partes[-1])
    # "\" na frente e entre as partes: "\DATASHEETS\" só casa uma PASTA com
    # esse nome, inclusive a primeira.
    texto = "\\" + "\\".join(normalizar(p) for p in partes)
    for padrao in IGNORAR_PASTAS:
        if normalizar(padrao) in texto:
            return f"pasta de teste, cópia ou obsoleta ('{padrao.strip(chr(92))}')"
    for padrao in IGNORAR_ARQUIVOS:
        if normalizar(padrao) in nome:
            return f"nome de cópia ou temporário ('{padrao.strip()}')"
    return None


def codigo_do_arquivo(nome: str) -> str | None:
    """`#ST00=X&MPB020_STATUS_PMIB.xlsx` -> `#ST00=X&MPB020`; outro nome -> `None`."""
    base, extensao = os.path.splitext(nome)
    if extensao.lower() not in EXTENSOES or not base.upper().endswith(SUFIXO):
        return None
    codigo = base[: -len(SUFIXO)].strip()
    return codigo or None


@dataclass
class Levantamento:
    """O que `listar` achou. Caminhos absolutos, em texto."""

    vivos: list[tuple[str, str]] = field(default_factory=list)            # (código, caminho)
    ignorados: list[tuple[str, str]] = field(default_factory=list)        # (caminho, motivo)
    repetidos: list[tuple[str, str, list[str]]] = field(default_factory=list)  # (código, escolhido, descartados)


def listar(pasta_raiz) -> Levantamento:
    """Todos os `*_STATUS_PMIB.xlsx/.xls` da pasta (e subpastas), separados em
    vivos e ignorados (com o motivo). Os vivos saem ordenados pelo caminho."""
    levantamento = Levantamento()
    raiz = str(pasta_raiz)
    if not os.path.isdir(raiz):
        return levantamento

    por_codigo: dict[str, list[str]] = {}
    for pasta, _subpastas, nomes in os.walk(raiz):
        for nome in nomes:
            codigo = codigo_do_arquivo(nome)
            if codigo is None:
                continue
            caminho = os.path.join(pasta, nome)
            motivo = motivo_para_ignorar(os.path.relpath(caminho, raiz))
            if motivo:
                levantamento.ignorados.append((caminho, motivo))
            else:
                por_codigo.setdefault(codigo, []).append(caminho)

    for codigo, caminhos in por_codigo.items():
        # O modificado por último; empate (mesmo instante) desempata pelo nome,
        # para o resultado não depender da ordem do `os.walk`.
        caminhos.sort(key=lambda c: (os.path.getmtime(c), c), reverse=True)
        levantamento.vivos.append((codigo, caminhos[0]))
        if len(caminhos) > 1:
            levantamento.repetidos.append((codigo, caminhos[0], caminhos[1:]))

    levantamento.vivos.sort(key=lambda item: item[1])
    levantamento.ignorados.sort()
    levantamento.repetidos.sort()
    return levantamento


# --------------------------------------------------------------------------
# A linha da revisão em uso
# --------------------------------------------------------------------------
_RE_REVISAO = re.compile(r"EM USO:\s*(.+?)\s*-\s*DATA DE ALTERA", re.IGNORECASE)
_SEM_REVISAO = {"", "-", "—", "–"}


def revisao_do_texto(texto) -> str | None:
    """A revisão escrita na linha "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM
    USO: <rev> - DATA DE ALTERAÇÃO: ...", ou `None` (outra linha, ou revisão em
    branco/"—"). Pode ser "SEM LISTA"."""
    if texto is None or not normalizar(texto).startswith(normalizar(config.TEXTO_LINHA_REVISAO)):
        return None
    # Sobre o texto ORIGINAL (só caixa e espaços): normalizar tiraria o "—",
    # que é justamente o que diz "sem revisão".
    m = _RE_REVISAO.search(re.sub(r"\s+", " ", str(texto).upper()).replace("ALTERAÇÃO", "ALTERACAO"))
    if not m:
        return None
    revisao = m.group(1).strip()
    return None if revisao in _SEM_REVISAO else revisao


def revisao_acima_do_cabecalho(linhas: Iterable[Sequence[object]], linha_cabecalho: int) -> str | None:
    """Procura, nas linhas ACIMA do cabeçalho (1-based, como no Excel), a célula
    com o texto da revisão em uso. `linhas[0]` é a linha 1 da planilha."""
    for numero, linha in enumerate(linhas, start=1):
        if numero >= linha_cabecalho:
            break
        for valor in linha:
            revisao = revisao_do_texto(valor)
            if revisao is not None:
                return revisao
    return None

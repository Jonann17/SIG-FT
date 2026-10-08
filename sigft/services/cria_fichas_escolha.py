r"""A escolha de PDM em duas passadas: as regras puras (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md

Este módulo não chama IA e não conhece tkinter nem pandas: recebe listas e
dicionários e devolve listas e dicionários. Quem chama a IA é o
`GeminiCategorizer` (`services/cria_fichas.py`); quem mostra é a tela.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sigft.core.pdm_catalogo import normalizar, tokenizar

# A resposta da IA quando nenhum PDM serve. Mora aqui, e `services/cria_fichas`
# a importa: as regras da revisão (rótulo, ordem) também precisam dela, e um
# conceito tem uma definição só.
PDM_NENHUM = "NENHUM"

MAX_SINONIMOS = 4


@dataclass(frozen=True)
class Interpretacao:
    """O que a passada 1 diz de UM item: o que ele é, por quais outros nomes
    é conhecido, e a que equipamento serve (quando a descrição diz)."""

    e: str
    sinonimos: tuple[str, ...] = ()
    serve: str = ""

    def como_dict(self) -> dict:
        return {"e": self.e, "sinonimos": list(self.sinonimos), "serve": self.serve}


def texto_da_celula(valor) -> str:
    """Texto limpo de uma célula: `None` e `NaN` do pandas viram vazio."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def itens_para_interpretar(linhas) -> str:
    """O bloco `### ITEM N` da passada 1: descrição e marca, nada mais."""
    partes = []
    for posicao, linha in enumerate(linhas, start=1):
        partes.append(
            f"### ITEM {posicao}\n"
            f"- Descrição: {texto_da_celula(linha.get('DESCRIÇÃO'))}\n"
            f"- Marca/Modelo: {texto_da_celula(linha.get('MARCA/MODELO'))}"
        )
    return "\n\n".join(partes)


def ler_interpretacoes(res_json, total) -> list:
    """Casa a resposta da passada 1 com os itens PELO número (`item`).

    Devolve `total` posições, com `None` onde a resposta faltou ou veio sem
    um `e` utilizável: esse item segue com a busca de hoje. Mesma régua de
    `cria_fichas.alinhar_resposta` -- casar por posição fazia um item pulado
    deslocar todos os seguintes."""
    alinhado = [None] * total
    for bruto in res_json if isinstance(res_json, list) else []:
        if not isinstance(bruto, dict):
            continue
        try:
            numero = int(bruto.get("item"))
        except (TypeError, ValueError):
            continue
        if not 1 <= numero <= total:
            continue
        e = texto_da_celula(bruto.get("e"))
        if not e:
            continue
        sinonimos = bruto.get("sinonimos")
        if not isinstance(sinonimos, list):
            sinonimos = []
        limpos = tuple(s for s in (texto_da_celula(x) for x in sinonimos) if s)
        alinhado[numero - 1] = Interpretacao(
            e=e, sinonimos=limpos[:MAX_SINONIMOS], serve=texto_da_celula(bruto.get("serve")))
    return alinhado


def consulta_da_interpretacao(interpretacao) -> str:
    """A consulta da frente A: o que a peça é, mais os sinônimos. O `serve`
    fica de fora de propósito -- era ele que puxava as válvulas para a vaga
    da plaqueta."""
    if interpretacao is None:
        return ""
    return " ".join((interpretacao.e,) + interpretacao.sinonimos)


# =============================================================================
# A resposta da passada 2: confiança, alternativas e sinais (spec §4.4-4.5)
# =============================================================================
CONFIANCAS = ("ALTA", "MEDIA", "BAIXA")
MAX_ALTERNATIVAS = 2

_RE_PREFIXO_NUMERICO = re.compile(r"^\d+\s*-\s*")


def normalizar_confianca(valor) -> str:
    """ALTA, MEDIA ou BAIXA. O que não for um dos três vira BAIXA: na dúvida,
    o item vai para o topo da revisão, que é o lado seguro."""
    texto = normalizar(valor) if isinstance(valor, str) else ""
    return texto if texto in CONFIANCAS else "BAIXA"


def alternativas_validas(item, catalogo, escolhido) -> tuple:
    """O 2º e o 3º lugar que a IA sugeriu, conferidos no catálogo.

    Devolve `(validas, recusadas)`. Válida é `{"pdm": completo, "motivo": str}`,
    com o PDM canônico do catálogo. Recusada é o texto que não existe no
    catálogo -- a mesma guarda do `pdm_escolhido`. Repetida, ou igual à
    escolhida, só sai (não é erro da IA, é redundância)."""
    brutas = (item or {}).get("alternativas")
    if not isinstance(brutas, list):
        return [], []
    vistos = {escolhido.codigo} if escolhido is not None else set()
    validas, recusadas = [], []
    for bruta in brutas:
        if isinstance(bruta, dict):
            texto, motivo = bruta.get("pdm"), bruta.get("motivo")
        else:
            texto, motivo = bruta, ""
        texto = str(texto or "").strip()
        if not texto:
            continue
        pdm = catalogo.resolver(texto)
        if pdm is None:
            recusadas.append(texto)
            continue
        if pdm.codigo in vistos:
            continue
        vistos.add(pdm.codigo)
        validas.append({"pdm": pdm.completo, "motivo": str(motivo or "").strip()})
        if len(validas) >= MAX_ALTERNATIVAS:
            break
    return validas, recusadas


def _nome_base_bate(pdm, interpretacao) -> bool:
    """Toda palavra do nome base aparece no "é" ou num sinônimo? Comparação
    pelo `tokenizar` do catálogo: sem acento, com singular."""
    if pdm is None or interpretacao is None:
        return False
    consulta = tokenizar(consulta_da_interpretacao(interpretacao))
    palavras = [w for w in normalizar(pdm.nome_base or pdm.titulo).split() if tokenizar(w)]
    return bool(palavras) and all(tokenizar(w) & consulta for w in palavras)


def _sem_prefixo(nome) -> str:
    """`normalizar` mais o corte de um código na frente ("5279 - NOME"): é
    como o portal mostra a característica, e a IA pode copiar assim."""
    return _RE_PREFIXO_NUMERICO.sub("", normalizar(nome))


def _citadas_limpas(citadas) -> list:
    if not isinstance(citadas, list):
        return []
    return [str(c).strip() for c in citadas if str(c or "").strip()]


def caracteristicas_inexistentes(pdm, citadas) -> list:
    """As características citadas que o PDM escolhido NÃO tem (revisão
    vigente incluída), no texto em que a IA as escreveu."""
    if pdm is None:
        return []
    do_pdm = {_sem_prefixo(c) for c in pdm.caracteristicas}
    do_pdm |= {_sem_prefixo(c.nome) for c in pdm.caracteristicas_em_ordem}
    return [c for c in _citadas_limpas(citadas) if _sem_prefixo(c) not in do_pdm]


def _caracteristicas_existem(pdm, citadas) -> bool:
    """Ao menos uma citada, e todas existem no PDM."""
    if pdm is None or not _citadas_limpas(citadas):
        return False
    return not caracteristicas_inexistentes(pdm, citadas)


def calcular_sinais(escolhido, candidatos, interpretacao, citadas) -> dict:
    """As três conferências que o CÓDIGO faz da escolha da IA (spec §4.5)."""
    codigos = {p.codigo for p in candidatos or []}
    return {
        "na_busca": escolhido is not None and escolhido.codigo in codigos,
        "nome_base": _nome_base_bate(escolhido, interpretacao),
        "caracteristicas": _caracteristicas_existem(escolhido, citadas),
    }


def confianca_final(confianca, sinais) -> tuple:
    """ALTA só continua ALTA com pelo menos 2 de 3 sinais; senão vira MEDIA,
    rebaixada. Um ALTA que nada confirma é o erro mais caro: é o que se
    aprova sem olhar."""
    if confianca == "ALTA" and sum(bool(v) for v in sinais.values()) < 2:
        return "MEDIA", True
    return confianca, False

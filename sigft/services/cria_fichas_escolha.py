r"""A escolha de PDM em duas passadas: as regras puras (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md

Este módulo não chama IA e não conhece tkinter nem pandas: recebe listas e
dicionários e devolve listas e dicionários. Quem chama a IA é o
`GeminiCategorizer` (`services/cria_fichas.py`); quem mostra é a tela.
"""
from __future__ import annotations

from dataclasses import dataclass

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

"""O nível de cada linha do console: erro, aviso ou informação (2026-10-21, etapa 1b).

UM lugar só para as marcas. O filtro do console (Tudo / Avisos / Erros) e a
janela de resumo do fim do lote leem daqui.

De onde vem o nível, nesta ordem:
1. o `nivel` do protocolo de log (`core/callbacks.py`) quando o serviço o manda:
   "error" e "warn" (os que os serviços usam) e os sinônimos. "info" é o padrão
   do protocolo, e não se distingue de "não mandou": cai na regra 2;
2. a MARCA que abre a linha ("[Erro] ...", "❌ ...", "Falha ao ..."). Só no
   começo: o resumo do `RelatorioLote` ("✅ 3 sucesso(s) · ❌ 0 falha(s)") tem um
   ❌ no meio e não é erro.

Sem Qt. `tests/test_niveis_log.py` trava as marcas com linhas reais dos serviços
e reprova tag nova de serviço sem nível decidido.
"""
from __future__ import annotations

import re

ERRO = "erro"
AVISO = "aviso"
INFO = "info"

NIVEL_DO_PROTOCOLO = {
    "error": ERRO, "erro": ERRO, "critical": ERRO,
    "warn": AVISO, "warning": AVISO, "aviso": AVISO,
}

# Comparadas sem caixa, no começo da linha. Marca que termina em letra só vale
# como palavra inteira: "Falha ao salvar" é erro; "Falhas:" (título do resumo do
# lote) não. "[erro" sem o colchete de fechar pega "[Erro Estrutural]" e
# "[ERRO FATAL AO SALVAR]".
MARCAS_DE_ERRO = ("[erro", "❌", "falha")
MARCAS_DE_AVISO = ("[aviso]", "[!]", "[autoconferência]", "[atenção]", "aviso:", "⚠")

# O que pode vir antes da marca: recuo, o "->" das telas, seta e marcador.
_ABERTURA = re.compile(r"^[\s>\-→•]+")


def _abre_com(texto: str, marca: str) -> bool:
    if not texto.startswith(marca):
        return False
    if marca[-1].isalpha():
        return not texto[len(marca):len(marca) + 1].isalpha()
    return True


def nivel_da_marca(msg: object) -> str:
    """O nível pela marca que abre a PRIMEIRA linha de `msg`."""
    texto = str(msg if msg is not None else "").strip()
    primeira = texto.splitlines()[0] if texto else ""
    primeira = _ABERTURA.sub("", primeira).casefold()
    if any(_abre_com(primeira, marca) for marca in MARCAS_DE_ERRO):
        return ERRO
    if any(_abre_com(primeira, marca) for marca in MARCAS_DE_AVISO):
        return AVISO
    return INFO


def classificar(msg: object, nivel: object = "info") -> str:
    """O nível da linha: o do protocolo quando ele diz erro ou aviso, senão o da marca."""
    do_protocolo = NIVEL_DO_PROTOCOLO.get(str(nivel).casefold())
    return do_protocolo or nivel_da_marca(msg)

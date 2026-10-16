"""Confere a versão do Python ANTES de qualquer import do SIG-FT.

Com Python 3.9 o app abria pela metade: três módulos falhavam na splash com
"unsupported operand type(s) for |" e a pessoa não tinha como saber que o
problema era a versão (aconteceu num Mac com o Python 3.9.6 que vem no sistema).

Este arquivo tem de compilar em Python antigo: sem `X | None`, sem `match`.
Há teste travando isso (`tests/test_python_minimo.py`).
"""
import sys

MINIMO = (3, 10)

MENSAGEM = (
    "O SIG-FT precisa do Python 3.10 ou mais novo, e este é o {atual}.\n"
    "Instale um Python novo em https://www.python.org/downloads/ "
    "(no Windows, marque \"Add python.exe to PATH\") e abra de novo."
)

# Versões com defeito conhecido que ATINGE o SIG-FT, mas não impede de abrir.
# 3.12.0: o gancho de importação do PySide6 quebra no `six.moves` (que o
# pandas usa pelo `dateutil`), e as telas Qt que usam pandas não abrem.
# Corrigido no 3.12.1 (PENDENCIAS de 2026-10-14).
COM_DEFEITO = {
    (3, 12, 0): (
        "Atenção: este é o Python 3.12.0, que tem um defeito que impede algumas "
        "telas do SIG-FT de abrir (as que leem planilhas). Instale um Python "
        "3.12 mais novo ou o 3.13 em https://www.python.org/downloads/ e abra "
        "de novo."
    ),
}


def exigir_python_minimo(versao=None, sair=sys.exit, avisar=print):
    """Avisa e encerra com código 1 se o Python for menor que `MINIMO`; numa
    versão de `COM_DEFEITO`, só avisa e deixa abrir."""
    if versao is None:
        versao = sys.version_info
    if tuple(versao[:2]) >= MINIMO:
        aviso = COM_DEFEITO.get(tuple(versao[:3]))
        if aviso:
            avisar(aviso)
        return
    atual = ".".join(str(parte) for parte in versao[:3])
    avisar(MENSAGEM.format(atual=atual))
    sair(1)

"""Leitura de propriedade dinâmica do Qt sem roubar a referência do `None`.

No PySide6 6.12.0, `QObject.property(nome)` de uma propriedade que não existe
devolve `None` sem incrementar a contagem de referências dele: cada leitura
"gasta" uma. No Python 3.12+ o `None` é imortal e nada acontece; no 3.10/3.11
(o mínimo do `SIG-FT.bat` é o 3.10) a contagem chega a zero e o processo morre
com "Fatal Python error: none_dealloc: deallocating None" (CI de 2026-10-22,
achado pelo vigia da `letra`, que lê uma propriedade a cada peça que nasce).

Por isso toda leitura passa por aqui: se a propriedade não está posta, o
`property` nem é chamado. `tests/test_propriedades.py` trava que nenhum outro
arquivo chame `.property(` direto.
"""
from __future__ import annotations


def ler(objeto, nome: str, padrao=None):
    """O valor da propriedade dinâmica `nome` de `objeto`, ou `padrao` se ela
    não estiver posta."""
    if nome.encode() not in objeto.dynamicPropertyNames():
        return padrao
    return objeto.property(nome)

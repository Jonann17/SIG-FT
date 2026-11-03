"""Callback de filho que não segura a tela dona (2026-10-30).

Um filho que guarda `tela.metodo` (callback de clique, de escolha, de fila)
segura a tela, e a tela segura o filho: um ciclo. Solta pelo dono, a tela só
morre quando o coletor de lixo do Python passar -- num momento qualquer,
inclusive DENTRO do `paintEvent` de uma peça dela, que foi o access violation
do `MenuDeOpcoes.paintEvent` (PENDENCIAS, 2026-10-26;
`tests/test_qt_tela_morre_sem_coletor.py`).

`chamada_fraca(tela.metodo)` devolve uma função que chama o método pela
`weakref.WeakMethod`: a tela morre na hora em que o dono a solta, e o clique
que chegar depois disso não faz nada. Função comum (lambda, função de módulo)
passa como veio.
"""
from __future__ import annotations

import inspect
import weakref


def chamada_fraca(funcao):
    """`funcao`, sem segurar o dono dela quando é um método ligado."""
    if not inspect.ismethod(funcao):
        return funcao
    ref = weakref.WeakMethod(funcao)

    def chamar(*args, **kwargs):
        metodo = ref()
        if metodo is not None:
            return metodo(*args, **kwargs)
        return None

    return chamar

"""Tela solta morre na hora, sem esperar o coletor de lixo (2026-10-30).

O access violation do `MenuDeOpcoes.paintEvent` (Release, 2026-10-26; caiu
também no CI do Ubuntu) era um ciclo de referências: a barrinha do console
(`PuxadorDoConsole`) segurava a tela pelo `_tela`, e a tela segura a barrinha.
Solta pelo dono, a tela não morria: ficava esperando o coletor do Python, que
passa num momento qualquer -- inclusive DENTRO do `paintEvent` de uma peça
dela, alocando um `QPen`. Ali ele destruía a janela inteira no meio da pintura,
e o pintor seguinte escrevia em memória já liberada.

O teste não provoca a queda (derrubaria o worker): confere a causa. Com o
coletor desligado, a tela tem de sumir assim que a última referência sai.
"""
from __future__ import annotations

import gc
import weakref

import pytest
from PySide6.QtWidgets import QWidget

from sigft.app_qt import main as qmain

# As telas que morrem sozinhas: todas menos o AutoSpec, que ainda tem um ciclo
# próprio (closure; tela do Rafael, ver o PENDENCIAS.md, 2026-10-30). Callback
# de filho que aponta para a tela usa `widgets/fraco.chamada_fraca`.
SEM_CICLO = ["Home", "Translator", "LMR", "CriaFichas", "PDM", "Analyzer", "UploadConditions",
             "UploadSpecs", "CorrecaoPDM", "CopiaFichas",
             "PMIBManager", "SearchPMIB", "UploadFotos", "ListaPrecos"]


class _Controlador:
    def __getattr__(self, _nome):
        return lambda *a, **k: None


def _morre_sem_coletor(fabrica) -> bool:
    pai = QWidget()
    tela = fabrica(pai)
    tela.setParent(None)
    ref = weakref.ref(tela)
    ligado = gc.isenabled()
    gc.disable()
    try:
        del tela
        return ref() is None
    finally:
        if ligado:
            gc.enable()
        pai.deleteLater()


@pytest.mark.parametrize("nome", SEM_CICLO)
def test_tela_solta_morre_sem_o_coletor(qt_interface, nome):
    assert _morre_sem_coletor(lambda pai: qmain.TELAS[nome](pai, _Controlador())), (
        f"{nome}: a tela só morre quando o coletor passar -- e ele pode passar no "
        f"meio de um paintEvent (ver a docstring deste arquivo)")


def test_a_busca_pmib_do_teste_que_caia_morre_sem_o_coletor(qt_interface):
    from sigft.app_qt.views import busca_pmib

    assert _morre_sem_coletor(lambda _pai: busca_pmib.ModuloBuscaPMIB())

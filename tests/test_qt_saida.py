"""A SAÍDA do pytest não pode derrubar o processo depois dos testes verdes.

CI do PR #5 (2026-10-14): 6610 testes passaram e o processo morreu na saída,
em uma de quatro rodadas, com "QObject: shared QObject was deleted directly"
e "malloc_consolidate(): unaligned fastbin chunk detected" (código 134).

A pilha (gdb no CI) e a miniatura abaixo mostram o mecanismo. Na saída, o
PySide apaga cada objeto Qt "do Python" ainda vivo, numa ordem qualquer.
Uma tela VAZADA -- um `lambda` que guarda `self` ligado ao sinal de um filho
é um ciclo que passa pelo C++, e o GC não o vê -- às vezes tem o FILHO
apagado antes: o `lambda` morre junto, leva a tela, e a tela apaga de novo o
filho que já estava sendo apagado. O filho é "do Python" mesmo tendo pai no
Qt porque entrou numa linha (`QHBoxLayout`) que ainda não tinha pai: o padrão
das telas do SIG-FT.

O app não passa por isso: ele termina com `os._exit` (`instancia.encerrar`),
que pula a faxina do PySide. Quem passa é o processo do pytest, no CI e no
passo de testes do Release.

O subprocesso roda o `tests/conftest.py` de verdade e força o pior caso: um
`atexit` (que roda ANTES da faxina do PySide) apaga o filho primeiro se a
tela ainda estiver viva. Sem a faxina do conftest, cai sempre; com ela, a
tela já morreu de cima para baixo, e o processo sai com zero.
"""
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

_TESTE_QUE_VAZA = '''
import atexit

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from shiboken6 import Shiboken


class TelaQueVaza(QWidget):
    def __init__(self):
        super().__init__()
        corpo = QVBoxLayout(self)
        linha = QHBoxLayout()               # sem pai ainda
        self.botao = QPushButton("b")
        linha.addWidget(self.botao)
        corpo.addLayout(linha)              # o botao ganha pai no Qt e segue "do Python"
        self.botao.clicked.connect(lambda: self.close())   # o lambda guarda a tela


def test_deixa_uma_tela_vazada(qapp):
    botao = TelaQueVaza().botao
    assert isinstance(botao.parent(), TelaQueVaza)
    # No PySide6 6.12 o filho segue "do Python" (o caso perigoso que este teste
    # monta); no 6.11 (o do Python < 3.12, ver o requirements.txt) o Qt fica
    # com ele e o caso nem se forma. A saída tem de ser limpa nos dois.
    import PySide6
    if tuple(int(x) for x in PySide6.__version__.split(".")[:2]) >= (6, 12):
        assert Shiboken.ownedByPython(botao)

    def apagar_o_filho_primeiro():
        if Shiboken.isValid(botao):
            Shiboken.delete(botao)

    atexit.register(apagar_o_filho_primeiro)
'''


def test_sessao_que_vaza_uma_tela_sai_com_zero(tmp_path):
    (tmp_path / "test_vaza.py").write_text(_TESTE_QUE_VAZA, encoding="utf-8")
    ambiente = {**os.environ,
                "PYTHONPATH": os.pathsep.join([str(RAIZ / "tests"), str(RAIZ)]),
                "QT_QPA_PLATFORM": "offscreen"}

    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "-p", "conftest", "test_vaza.py"],
        cwd=tmp_path, env=ambiente, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180)

    saida = (r.stdout + r.stderr)[-3000:]
    assert "1 passed" in r.stdout, saida
    assert r.returncode == 0, f"o processo caiu na saída (código {r.returncode}):\n{saida}"

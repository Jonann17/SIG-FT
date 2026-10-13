import ast
import threading
from pathlib import Path

from sigft.app_qt.widgets import console as qconsole

# Caminho a partir deste arquivo, não do cwd: outro teste da suíte faz os.chdir
# (test_llm_comparacao.py) sem restaurar, e o cwd não é a raiz quando este roda.
RAIZ = Path(__file__).resolve().parents[1]


def test_prefixo_igual_ao_da_interface_atual():
    arvore = ast.parse((RAIZ / "sigft/app/widgets/console.py").read_text(encoding="utf-8"))
    atual = next(n.value.value for n in arvore.body
                 if isinstance(n, ast.Assign) and n.targets[0].id == "PREFIXO_LINHA")
    assert qconsole.PREFIXO_LINHA == atual


def test_linhas_de_thread_chegam_em_ordem(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)

    def worker():
        for i in range(500):
            c.log(f"linha {i}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join()
    qtbot.waitUntil(lambda: c.blockCount() >= 500, timeout=3000)
    linhas = c.toPlainText().splitlines()
    assert linhas[0] == "> linha 0" and linhas[-1] == "> linha 499" and len(linhas) == 500


def test_aceita_qualquer_objeto(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.log(ValueError("x"))
    c.log(42)
    qtbot.waitUntil(lambda: c.blockCount() >= 2, timeout=2000)
    assert c.toPlainText().splitlines() == ["> x", "> 42"]


def test_somente_leitura_e_altura(qt_interface, qtbot):
    c = qconsole.ConsoleFrame(altura=120)
    qtbot.addWidget(c)
    assert c.isReadOnly() and c.height() == 120
    livre = qconsole.ConsoleFrame(altura=None)
    qtbot.addWidget(livre)
    assert livre.maximumHeight() > 120


def test_widget_destruido_nao_derruba_o_worker(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    c.log("antes")
    c.deleteLater()
    qtbot.wait(100)
    c.log("depois")  # não pode levantar

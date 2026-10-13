"""O corte (E6.1): `python frontend.py` abre a interface Qt; `--ctk`, a antiga.

`frontend.py` e o que o `SIG-FT.spec` empacota e o que o `SIG-FT.bat` (e, no
Mac, o `SIG-FT.command`) roda: trocar a interface oficial e trocar o despacho
dele. O que se cobra aqui:

1. sem `--ctk`, ele entrega a linha de comando a Qt e NAO segue adiante -- o
   modo Qt nao importa tkinter nem CustomTkinter (no Mac com o Python do
   Homebrew nem ha Tk), e nao cai no CTk nem se a Qt voltar;
2. `--smoke` pelo ponto de entrada do bundle grava o relatorio da Qt, que e o
   que o passo do Release le;
3. com `--ctk`, tudo como antes, inclusive `--ctk --smoke`;
4. `import frontend` continua dando os nomes do CustomTkinter (os reexports).
"""
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
FRONTEND = RAIZ / "frontend.py"

# Roda o `frontend.py` como `__main__` num interpretador limpo (o conftest dubla
# o Tk NESTE processo), com tkinter/customtkinter bloqueados por um finder: se
# o despacho chegar aos imports do CTk, o import estoura aqui.
_RODAR_SEM_TK = r"""
import importlib.abc, runpy, sys, types
sys.path.insert(0, {raiz!r})

class _SemTk(importlib.abc.MetaPathFinder):
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split('.')[0] in ('tkinter', '_tkinter', 'customtkinter'):
            raise ImportError('Tk bloqueado pelo teste: ' + nome)

sys.meta_path.insert(0, _SemTk())

if {qt_falsa!r}:
    # A Qt de mentira VOLTA normalmente: o frontend tem de sair mesmo assim.
    import sigft.app_qt
    falsa = types.ModuleType('sigft.app_qt.main')
    falsa.executar_da_linha_de_comando = lambda: print('QT ABRIU COM', sys.argv[1:])
    sys.modules['sigft.app_qt.main'] = falsa
    sigft.app_qt.main = falsa

sys.argv = [{frontend!r}, *{argumentos!r}]
try:
    runpy.run_path({frontend!r}, run_name='__main__')
    print('VOLTOU SEM SAIR')
finally:
    print('TK NO PROCESSO:', sorted(m for m in sys.modules
                                    if m.split('.')[0] in ('tkinter', 'customtkinter')))
"""


def _rodar_sem_tk(argumentos, cwd, *, qt_falsa):
    codigo = _RODAR_SEM_TK.format(raiz=str(RAIZ), frontend=str(FRONTEND),
                                  argumentos=list(argumentos), qt_falsa=qt_falsa)
    ambiente = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
                "SIGFT_DADOS_DIR": str(Path(cwd) / "dados")}
    return subprocess.run([sys.executable, "-c", codigo], cwd=str(cwd), env=ambiente,
                          capture_output=True, text=True, timeout=180)


@pytest.mark.parametrize("argumentos", [[], ["--smoke"]])
def test_sem_ctk_entrega_a_linha_de_comando_a_qt_e_nao_toca_no_tk(tmp_path, argumentos):
    resultado = _rodar_sem_tk(argumentos, tmp_path, qt_falsa=True)

    assert "Tk bloqueado" not in resultado.stderr, (
        "o frontend.py chegou aos imports do CustomTkinter sem `--ctk`:\n"
        + resultado.stderr[-1500:])
    assert f"QT ABRIU COM {argumentos}" in resultado.stdout, resultado.stderr[-1500:]
    assert "VOLTOU SEM SAIR" not in resultado.stdout, (
        "a Qt voltou e o frontend.py seguiu em frente (cairia nos imports do CTk)")
    assert "TK NO PROCESSO: []" in resultado.stdout
    assert resultado.returncode == 0, resultado.stderr[-1500:]


def test_smoke_pelo_ponto_de_entrada_grava_o_relatorio_da_qt(tmp_path):
    """O passo do Release, com a Qt de verdade: `SIG-FT.exe --smoke` le o
    `conferencia-da-janela.txt`. Com o Tk bloqueado, so a Qt consegue grava-lo.

    O codigo de saida nao e cobrado: ele depende das dependencias pesadas
    deste ambiente (backend que nao carrega so vira aviso). O que se prova e o
    caminho: ponto de entrada -> smoke da Qt -> relatorio em arquivo.
    """
    resultado = _rodar_sem_tk(["--smoke"], tmp_path, qt_falsa=False)

    assert "Tk bloqueado" not in resultado.stderr, resultado.stderr[-1500:]
    relatorio = tmp_path / "conferencia-da-janela.txt"
    assert relatorio.is_file(), (
        f"o --smoke nao gravou o relatorio.\ncodigo: {resultado.returncode}\n"
        f"stdout: {resultado.stdout[-800:]}\nstderr: {resultado.stderr[-1500:]}")
    assert "[smoke]" in relatorio.read_text(encoding="utf-8")


# -- `--ctk` e `import frontend`: o CustomTkinter de antes ----------------------
# Neste processo o conftest dubla o Tk, entao o `frontend.py` roda inteiro; os
# dois despachantes sao trocados por anotadores.

@pytest.fixture
def despachos(monkeypatch):
    from sigft.app import main as ctk
    from sigft.app_qt import main as qt

    chamados = []
    monkeypatch.setattr(ctk, "executar_da_linha_de_comando", lambda: chamados.append("ctk"))
    monkeypatch.setattr(qt, "executar_da_linha_de_comando", lambda: chamados.append("qt"))
    return chamados


@pytest.mark.parametrize("argumentos", [["--ctk"], ["--ctk", "--smoke"]])
def test_com_ctk_abre_a_interface_antiga(despachos, monkeypatch, argumentos):
    # `--ctk --smoke`: quem trata o `--smoke` e o despachante do CTk, que o
    # `tests/test_ponto_de_entrada.py` cobre.
    monkeypatch.setattr(sys, "argv", [str(FRONTEND), *argumentos])

    runpy.run_path(str(FRONTEND), run_name="__main__")

    assert despachos == ["ctk"]


def _requisitos(nome):
    return [linha.split(";")[0].strip().lower()
            for linha in (RAIZ / nome).read_text(encoding="utf-8").splitlines()
            if linha.strip() and not linha.strip().startswith("#")]


def test_requirements_de_producao_instala_o_pyside6():
    """Sem ele, quem abre pelo `SIG-FT.bat` (ou pelo `SIG-FT.command`) cai num
    `ModuleNotFoundError` na abertura: o CI nunca instala o `requirements.txt`,
    entao so este teste ve. `>=6.9` porque `sigft/app_qt/estilo.py` usa
    `QFontDatabase.setApplicationEmojiFontFamilies`, que so existe dali em
    diante. (No `requirements-dev.txt` ele tambem esta, mas la a falta ja
    quebraria a suite Qt inteira sozinha.)"""
    assert "pyside6-essentials>=6.9" in _requisitos("requirements.txt")


def test_import_frontend_continua_dando_os_nomes_do_customtkinter(despachos, monkeypatch):
    from sigft.app import main as ctk

    monkeypatch.setattr(sys, "argv", ["pytest"])

    nomes = runpy.run_path(str(FRONTEND), run_name="frontend")

    assert despachos == [], "importar o frontend abriu uma interface"
    assert nomes["SIG_FT_App"] is ctk.SIG_FT_App
    assert nomes["main"] is ctk.main

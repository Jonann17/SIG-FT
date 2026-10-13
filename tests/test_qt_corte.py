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
4. `import frontend` continua dando os nomes do CustomTkinter (os reexports);
5. a Qt que nao abre (PySide6 ausente ou quebrado, ou falha na partida): com
   `--smoke`, grava o motivo e sai com 1, sem cair em interface nenhuma; sem
   ele, avisa no console e abre a antiga no mesmo processo (transicao).
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

class _QtQuebrada(importlib.abc.MetaPathFinder):
    # O PySide6 instalado que nao carrega, como no Windows quando falta a DLL.
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split('.')[0] in ('PySide6', 'shiboken6'):
            raise ImportError('DLL load failed while importing QtCore: '
                              'Nao foi possivel encontrar o modulo especificado.')

if {qt_quebrada!r}:
    sys.meta_path.insert(0, _QtQuebrada())

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


def _rodar_sem_tk(argumentos, cwd, *, qt_falsa, qt_quebrada=False):
    codigo = _RODAR_SEM_TK.format(raiz=str(RAIZ), frontend=str(FRONTEND),
                                  argumentos=list(argumentos), qt_falsa=qt_falsa,
                                  qt_quebrada=qt_quebrada)
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
    # "telas visitadas" e do smoke da Qt; o do CTk nao tem essa linha.
    assert "telas visitadas" in relatorio.read_text(encoding="utf-8")


def test_smoke_com_a_qt_quebrada_grava_o_motivo_e_sai_com_1(tmp_path):
    """O PySide6 que nao carrega estoura no import, ANTES do `_smoke`. No `.exe`
    sem console isso virava a caixa de traceback do PyInstaller, e o
    `Start-Process -Wait` do Release esperava ate o limite do passo, sem
    relatorio. Tem de gravar o motivo, sair com 1 e NAO cair no CustomTkinter:
    o Release tem de reprovar, nao passar com a interface errada."""
    resultado = _rodar_sem_tk(["--smoke"], tmp_path, qt_falsa=False, qt_quebrada=True)

    relatorio = tmp_path / "conferencia-da-janela.txt"
    assert relatorio.is_file(), (
        f"codigo: {resultado.returncode}\nstderr: {resultado.stderr[-1500:]}")
    texto = relatorio.read_text(encoding="utf-8")
    assert "DLL load failed while importing QtCore" in texto
    assert "Traceback" in texto, "sem a pilha nao da para saber o que faltou"
    assert resultado.returncode == 1
    assert "TK NO PROCESSO: []" in resultado.stdout, "caiu no CustomTkinter"


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


# -- a Qt que nao abre (transicao) ------------------------------------------------

def _qt_que_nao_importa(monkeypatch):
    # `None` em sys.modules faz o `from sigft.app_qt.main import ...` levantar
    # ImportError -- o mesmo efeito do PySide6 ausente ou com a DLL quebrada.
    monkeypatch.setitem(sys.modules, "sigft.app_qt.main", None)


def _qt_que_nao_sobe(monkeypatch):
    from sigft.app_qt import main as qt

    def quebra():
        raise RuntimeError("a Qt nao subiu")

    monkeypatch.setattr(qt, "executar_da_linha_de_comando", quebra)


QUEBRAS_DA_QT = [
    pytest.param(_qt_que_nao_importa, "import of sigft.app_qt.main halted", id="import"),
    pytest.param(_qt_que_nao_sobe, "a Qt nao subiu", id="partida"),
]


@pytest.mark.parametrize(("quebrar", "motivo"), QUEBRAS_DA_QT)
def test_sem_smoke_a_qt_que_falha_avisa_e_abre_a_antiga(despachos, monkeypatch, capsys,
                                                        quebrar, motivo):
    """Decisao da transicao: a pessoa continua trabalhando, na interface antiga,
    e a janela preta diz o que falhou e o comando para abrir a antiga direto."""
    quebrar(monkeypatch)
    monkeypatch.setattr(sys, "argv", [str(FRONTEND)])

    runpy.run_path(str(FRONTEND), run_name="__main__")

    assert despachos == ["ctk"]
    texto = "".join(capsys.readouterr())
    assert motivo in texto
    assert "interface antiga" in texto
    assert f'"{sys.executable}" "{FRONTEND}" --ctk' in texto


@pytest.mark.parametrize(("quebrar", "motivo"), QUEBRAS_DA_QT)
def test_smoke_com_a_qt_que_falha_grava_o_motivo_e_nao_cai_na_antiga(
        despachos, monkeypatch, tmp_path, quebrar, motivo):
    monkeypatch.chdir(tmp_path)
    quebrar(monkeypatch)
    monkeypatch.setattr(sys, "argv", [str(FRONTEND), "--smoke"])

    with pytest.raises(SystemExit) as saida:
        runpy.run_path(str(FRONTEND), run_name="__main__")

    assert saida.value.code == 1
    assert despachos == [], "o --smoke caiu numa interface"
    texto = (tmp_path / "conferencia-da-janela.txt").read_text(encoding="utf-8")
    assert motivo in texto and "Traceback" in texto


def test_no_executavel_o_comando_da_antiga_e_o_proprio_exe(despachos, monkeypatch, capsys):
    """No `.exe` nao ha `frontend.py` para passar ao interpretador."""
    _qt_que_nao_importa(monkeypatch)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", [str(FRONTEND)])

    runpy.run_path(str(FRONTEND), run_name="__main__")

    texto = "".join(capsys.readouterr())
    assert f'"{sys.executable}" --ctk' in texto
    assert f'"{sys.executable}" "{FRONTEND}" --ctk' not in texto


def test_o_sig_ft_bat_repassa_os_argumentos_ao_frontend():
    """`SIG-FT.bat --ctk` tem de chegar ao `frontend.py` (e o que o README manda
    usar). Sem cmd.exe aqui para rodar o .bat, confere-se a linha que chama o
    `frontend.py`."""
    linhas = [linha for linha in (RAIZ / "SIG-FT.bat").read_text(encoding="utf-8").splitlines()
              if "frontend.py" in linha
              and not linha.lstrip().lower().startswith(("rem", "echo"))]
    assert linhas, "o SIG-FT.bat nao chama mais o frontend.py?"
    assert all(linha.rstrip().endswith("%*") for linha in linhas), linhas


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

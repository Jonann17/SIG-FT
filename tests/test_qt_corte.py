"""O ponto de entrada: `python frontend.py` abre a interface Qt, e só ela.

`frontend.py` e o que o `SIG-FT.spec` empacota e o que o `SIG-FT.bat` (e, no
Mac, o `SIG-FT.command`) roda. Desde 2026-10-15 a interface antiga saiu do
SIG-FT, com o `--ctk` e a queda para ela. O que se cobra aqui:

1. ele entrega a linha de comando a Qt e NAO segue adiante -- nem se a Qt
   voltar --, sem nenhuma biblioteca Tk no processo;
2. `--smoke` pelo ponto de entrada do bundle grava o relatorio da Qt, que e o
   que o passo do Release le;
3. a Qt que nao abre (PySide6 ausente ou quebrado, falha na partida, ou o
   erro FATAL do Qt, como o plugin de plataforma que falta): com `--smoke`,
   grava o motivo e sai com 1, sem caixa; sem ele, o motivo vai para o
   `sigft.log`, para a saida de erro e para uma caixa do sistema, e sai com 1;
4. `import frontend` nao abre nada e nao traz mais os nomes da interface
   antiga;
5. os lancadores repassam os argumentos e nao mandam mais para o `--ctk`.
"""
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

# As bibliotecas da interface antiga, bloqueadas no subprocesso. A lista tem um
# dono so: tests/test_sem_tkinter.py, a trava do repositorio inteiro.
from test_sem_tkinter import MODULOS_PROIBIDOS

RAIZ = Path(__file__).resolve().parent.parent
FRONTEND = RAIZ / "frontend.py"

# Roda o `frontend.py` como `__main__` num interpretador limpo, com as
# bibliotecas Tk bloqueadas por um finder: se algo no caminho as importar, o
# import estoura aqui.
_RODAR_SEM_TK = r"""
import importlib.abc, runpy, sys, types
sys.path.insert(0, {raiz!r})
PROIBIDOS = {proibidos!r}

class _SemTk(importlib.abc.MetaPathFinder):
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split('.')[0] in PROIBIDOS:
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
                                    if m.split('.')[0] in PROIBIDOS))
"""


def _rodar_sem_tk(argumentos, cwd, *, qt_falsa, qt_quebrada=False, ambiente_extra=None):
    codigo = _RODAR_SEM_TK.format(raiz=str(RAIZ), frontend=str(FRONTEND),
                                  argumentos=list(argumentos), qt_falsa=qt_falsa,
                                  qt_quebrada=qt_quebrada,
                                  proibidos=tuple(sorted(MODULOS_PROIBIDOS)))
    ambiente = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
                "SIGFT_DADOS_DIR": str(Path(cwd) / "dados"), **(ambiente_extra or {})}
    return subprocess.run([sys.executable, "-c", codigo], cwd=str(cwd), env=ambiente,
                          capture_output=True, text=True, timeout=180)


@pytest.mark.parametrize("argumentos", [[], ["--smoke"]])
def test_entrega_a_linha_de_comando_a_qt_e_nao_toca_no_tk(tmp_path, argumentos):
    resultado = _rodar_sem_tk(argumentos, tmp_path, qt_falsa=True)

    assert "Tk bloqueado" not in resultado.stderr, resultado.stderr[-1500:]
    assert f"QT ABRIU COM {argumentos}" in resultado.stdout, resultado.stderr[-1500:]
    assert "VOLTOU SEM SAIR" not in resultado.stdout, "a Qt voltou e o frontend.py seguiu em frente"
    assert "TK NO PROCESSO: []" in resultado.stdout
    assert resultado.returncode == 0, resultado.stderr[-1500:]


def test_smoke_pelo_ponto_de_entrada_grava_o_relatorio_da_qt(tmp_path):
    """O passo do Release, com a Qt de verdade: `SIG-FT.exe --smoke` le o
    `conferencia-da-janela.txt`.

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
    assert "telas visitadas" in relatorio.read_text(encoding="utf-8")


def test_smoke_com_a_qt_quebrada_grava_o_motivo_e_sai_com_1(tmp_path):
    """O PySide6 que nao carrega estoura no import, ANTES do `_smoke`. No `.exe`
    sem console isso virava a caixa de traceback do PyInstaller, e o
    `Start-Process -Wait` do Release esperava ate o limite do passo, sem
    relatorio. Tem de gravar o motivo e sair com 1."""
    resultado = _rodar_sem_tk(["--smoke"], tmp_path, qt_falsa=False, qt_quebrada=True)

    relatorio = tmp_path / "conferencia-da-janela.txt"
    assert relatorio.is_file(), f"codigo: {resultado.returncode}\nstderr: {resultado.stderr[-1500:]}"
    texto = relatorio.read_text(encoding="utf-8")
    assert "DLL load failed while importing QtCore" in texto
    assert "Traceback" in texto, "sem a pilha nao da para saber o que faltou"
    assert resultado.returncode == 1
    assert "TK NO PROCESSO: []" in resultado.stdout
    assert "nao conseguiu abrir a janela" not in resultado.stderr.lower(), "o --smoke avisou como gente"


def test_sem_smoke_a_qt_quebrada_avisa_com_o_motivo_e_o_log_e_sai_com_1(tmp_path):
    """Decisao de 2026-10-15: sem interface antiga para cair, a pessoa recebe o
    motivo e o caminho do `sigft.log` (que fica com a pilha), e o processo sai
    com 1 -- o `SIG-FT.bat` mostra "Encerrado com erro" e espera."""
    resultado = _rodar_sem_tk([], tmp_path, qt_falsa=False, qt_quebrada=True)

    assert resultado.returncode == 1, resultado.stderr[-1500:]
    assert "TK NO PROCESSO: []" in resultado.stdout
    log = tmp_path / "dados" / "logs" / "sigft.log"
    assert "O SIG-FT não conseguiu abrir a janela." in resultado.stderr
    assert "DLL load failed while importing QtCore" in resultado.stderr
    assert str(log) in resultado.stderr
    texto_log = log.read_text(encoding="utf-8")
    assert "DLL load failed while importing QtCore" in texto_log and "Traceback" in texto_log
    assert "--ctk" not in resultado.stderr + resultado.stdout


def _rodar_qt_de_verdade(argumentos, cwd, plataforma):
    ambiente = {**os.environ, "QT_QPA_PLATFORM": plataforma,
                "SIGFT_DADOS_DIR": str(Path(cwd) / "dados")}
    return subprocess.run([sys.executable, str(FRONTEND), *argumentos], cwd=str(cwd),
                          env=ambiente, capture_output=True, text=True, timeout=180)


def test_erro_fatal_do_qt_vira_aviso_e_sai_com_1(tmp_path):
    """O plugin de plataforma que falta nao levanta excecao: o Qt avisa e
    ABORTA o processo (codigo 134), e no `.exe` sem console a pessoa via o app
    simplesmente nao abrir. O aviso fatal vira o mesmo aviso da Qt que nao
    importa."""
    resultado = _rodar_qt_de_verdade([], tmp_path, "inexistente")

    assert resultado.returncode == 1, (resultado.returncode, resultado.stderr[-1500:])
    assert "O SIG-FT não conseguiu abrir a janela." in resultado.stderr
    texto_log = (tmp_path / "dados" / "logs" / "sigft.log").read_text(encoding="utf-8")
    assert "inexistente" in texto_log and "Qt platform plugin" in texto_log


def test_erro_fatal_do_qt_no_smoke_grava_o_relatorio(tmp_path):
    resultado = _rodar_qt_de_verdade(["--smoke"], tmp_path, "inexistente")

    assert resultado.returncode == 1, (resultado.returncode, resultado.stderr[-1500:])
    texto = (tmp_path / "conferencia-da-janela.txt").read_text(encoding="utf-8")
    assert "FALHOU" in texto and "inexistente" in texto


# -- no mesmo processo: a Qt que nao importa ou nao sobe ---------------------------

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


@pytest.fixture
def caixas(monkeypatch):
    """As caixas do sistema que o aviso abriria, anotadas em vez de abertas.
    (O `sigft.log` cai na pasta de dados isolada pelo conftest.)"""
    from sigft.core import erro_de_abertura

    abertas = []
    monkeypatch.setattr(erro_de_abertura, "mostrar_caixa",
                        lambda texto, **_: abertas.append(texto) or "anotada")
    return abertas


@pytest.mark.parametrize(("quebrar", "motivo"), QUEBRAS_DA_QT)
def test_sem_smoke_a_qt_que_falha_mostra_a_caixa_e_sai_com_1(caixas, monkeypatch, capsys,
                                                             quebrar, motivo):
    quebrar(monkeypatch)
    monkeypatch.setattr(sys, "argv", [str(FRONTEND)])

    with pytest.raises(SystemExit) as saida:
        runpy.run_path(str(FRONTEND), run_name="__main__")

    assert saida.value.code == 1
    assert len(caixas) == 1 and motivo in caixas[0] and "sigft.log" in caixas[0]
    from sigft.core.erro_de_abertura import caminho_do_log

    assert motivo in capsys.readouterr().err
    assert caminho_do_log() in caixas[0]
    assert motivo in Path(caminho_do_log()).read_text(encoding="utf-8")


@pytest.mark.parametrize(("quebrar", "motivo"), QUEBRAS_DA_QT)
def test_smoke_com_a_qt_que_falha_grava_o_motivo_sem_caixa(caixas, monkeypatch, tmp_path,
                                                           quebrar, motivo):
    monkeypatch.chdir(tmp_path)
    quebrar(monkeypatch)
    monkeypatch.setattr(sys, "argv", [str(FRONTEND), "--smoke"])

    with pytest.raises(SystemExit) as saida:
        runpy.run_path(str(FRONTEND), run_name="__main__")

    assert saida.value.code == 1
    assert caixas == [], "o --smoke abriu uma caixa (o Release ficaria esperando o OK)"
    texto = (tmp_path / "conferencia-da-janela.txt").read_text(encoding="utf-8")
    assert motivo in texto and "Traceback" in texto


def test_import_frontend_nao_abre_nada_e_nao_traz_a_interface_antiga(monkeypatch):
    from sigft.app_qt import main as qt

    chamados = []
    monkeypatch.setattr(qt, "executar_da_linha_de_comando", lambda: chamados.append("qt"))
    monkeypatch.setattr(sys, "argv", ["pytest"])

    nomes = runpy.run_path(str(FRONTEND), run_name="frontend")

    assert chamados == [], "importar o frontend abriu a interface"
    for antigo in ("SIG_FT_App", "SplashScreen", "COLORS", "ModuloAutoSpec", "main"):
        assert antigo not in nomes, antigo


# -- os lancadores -------------------------------------------------------------------

def test_o_sig_ft_bat_repassa_os_argumentos_ao_frontend():
    """`SIG-FT.bat --smoke` (e qualquer outra flag) tem de chegar ao
    `frontend.py`. Sem cmd.exe aqui para rodar o .bat, confere-se a linha que
    chama o `frontend.py`."""
    linhas = [linha for linha in (RAIZ / "SIG-FT.bat").read_text(encoding="utf-8").splitlines()
              if "frontend.py" in linha
              and not linha.lstrip().lower().startswith(("rem", "echo"))]
    assert linhas, "o SIG-FT.bat nao chama mais o frontend.py?"
    assert all(linha.rstrip().endswith("%*") for linha in linhas), linhas


@pytest.mark.parametrize("lancador", ["SIG-FT.bat", "SIG-FT.command", "SIG-FT Itaipu.bat",
                                      "scripts/_bootstrap_venv.bat",
                                      "scripts/_bootstrap_venv.sh"])
def test_nenhum_lancador_manda_para_a_interface_antiga(lancador):
    texto = (RAIZ / lancador).read_text(encoding="utf-8")
    assert "--ctk" not in texto
    assert "interface antiga" not in texto.lower()


def test_o_erro_do_sig_ft_bat_diz_onde_esta_o_log():
    """Depois de um pip que falhou ou de uma Qt que nao abriu, o bloco `:erro`
    e a unica coisa que a pessoa le: ele diz onde esta o `sigft.log`."""
    texto = (RAIZ / "SIG-FT.bat").read_text(encoding="utf-8")
    bloco = texto[texto.index("\n:erro"):]
    assert any(linha.lstrip().lower().startswith("echo") and "sigft.log" in linha
               for linha in bloco.splitlines()), bloco
    assert "pause" in bloco


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


def test_o_bootstrap_bat_segue_com_a_instalacao_anterior_quando_o_pip_falha():
    """Sem cmd.exe aqui: confere-se que o ramo de falha do `pip install -r`
    olha o carimbo anterior antes de sair com 1, e que ele so e gravado no
    caminho que deu certo."""
    texto = (RAIZ / "scripts" / "_bootstrap_venv.bat").read_text(encoding="utf-8")
    rotina = texto[texto.index("\n:_instalar\n"):texto.index("\n:_instalar_navegador")]
    falha = rotina[rotina.index("if errorlevel 1 ("):]
    assert "_hash_ant" in falha.split("exit /b 1")[0], falha
    assert "SEGUINDO" in falha
    assert rotina.count('>"%_stamp%"') == 1

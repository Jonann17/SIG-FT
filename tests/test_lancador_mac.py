"""O lancador do Mac: `SIG-FT.command` + `scripts/_bootstrap_venv.sh` (E6.1).

Mesmo papel do `SIG-FT.bat` + `scripts/_bootstrap_venv.bat`, no que vale no Mac:
Python 3.10+, venv em `<raiz>/.venv` (ou em `~/Library/Application Support`
quando a pasta e de servico de sincronizacao), `requirements.txt` instalado so
quando muda (carimbo com o hash), navegador do Playwright uma vez, e a janela
do Terminal aberta com a mensagem quando algo da errado.

Os testes rodam os scripts DE VERDADE, com um "python" de mentira que anota o
que lhe pedem: provam a logica do lancador, nao o pip.
"""
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
COMMAND = RAIZ / "SIG-FT.command"
BOOTSTRAP = RAIZ / "scripts" / "_bootstrap_venv.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(sys.platform == "win32" or BASH is None,
                                reason="lancador do Mac: precisa de bash num sistema POSIX")

# Anota "diretorio-fisico|argumentos" e responde com o codigo que o teste pedir.
_PYTHON_DE_MENTIRA = """#!/bin/sh
printf '%s\\n' "$(pwd -P)|$*" >> "$SIGFT_TESTE_REGISTRO"
case "$*" in
  *frontend.py*) exit "${SIGFT_TESTE_CODIGO_APP:-0}" ;;
  *" -r "*) exit "${SIGFT_TESTE_CODIGO_PIP:-0}" ;;
esac
exit 0
"""


def _executavel(caminho: Path, conteudo: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return caminho


@pytest.fixture
def venv(tmp_path):
    """Um venv de mentira: `bin/python` e o python que anota."""
    pasta = tmp_path / "venv"
    _executavel(pasta / "bin" / "python", _PYTHON_DE_MENTIRA)
    return pasta


def _ambiente(tmp_path, **extra):
    ambiente = {k: v for k, v in os.environ.items()
                if not k.startswith(("SIGFT_", "PIP_"))}
    ambiente.update(HOME=str(tmp_path / "home"),
                    SIGFT_TESTE_REGISTRO=str(tmp_path / "registro.txt"))
    ambiente.update({k: str(v) for k, v in extra.items()})
    return ambiente


def _bash(trecho, tmp_path, **extra):
    """Roda `trecho` num bash que acabou de fazer `source` do bootstrap."""
    script = f'source "{BOOTSTRAP}" || exit 99\n{trecho}'
    return subprocess.run([BASH, "-c", script], env=_ambiente(tmp_path, **extra),
                          cwd=str(tmp_path), capture_output=True, text=True, timeout=60)


def _registro(tmp_path):
    arquivo = tmp_path / "registro.txt"
    return arquivo.read_text(encoding="utf-8").splitlines() if arquivo.exists() else []


# -- os dois arquivos ------------------------------------------------------------

@pytest.mark.parametrize("script", [COMMAND, BOOTSTRAP], ids=lambda p: p.name)
def test_sintaxe_do_script(script):
    resultado = subprocess.run([BASH, "-n", str(script)], capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr


def _git(*argumentos):
    """Saida do `git` na raiz -- ou PULA o teste sem git, ou fora de um
    repositorio (o ZIP do GitHub), onde nao ha o que conferir."""
    try:
        resultado = subprocess.run(["git", *argumentos], cwd=str(RAIZ),
                                   capture_output=True, text=True)
    except FileNotFoundError:
        pytest.skip("sem o git nesta maquina: nao ha o que conferir")
    if resultado.returncode != 0:
        pytest.skip("fora de um repositorio git (ZIP): nao ha o que conferir")
    return resultado.stdout


def test_sem_git_os_testes_do_git_pulam(monkeypatch):
    def sem_git(*_a, **_k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", sem_git)
    with pytest.raises(pytest.skip.Exception):
        _git("status")


@pytest.mark.parametrize("script", [COMMAND, BOOTSTRAP], ids=lambda p: p.name)
def test_bit_de_execucao_gravado_no_git(script):
    """Sem o bit, o clique duplo no Finder recusa o arquivo. E e o modo gravado
    no git que chega a quem baixa o ZIP ou clona -- nao o do disco de quem
    commitou."""
    relativo = script.relative_to(RAIZ).as_posix()
    saida = _git("ls-files", "-s", "--", relativo)
    assert saida.strip(), f"{relativo} nao esta no git"
    assert saida.split()[0] == "100755", (
        f"{relativo} esta no git sem o bit de execucao: git update-index --chmod=+x {relativo}")


@pytest.mark.parametrize("script", [COMMAND, BOOTSTRAP], ids=lambda p: p.name)
def test_git_entrega_os_scripts_com_lf(script):
    """Num checkout do Windows (`core.autocrlf=true`) o git os converteria para
    CRLF, e uma pasta copiada ou zipada de la morreria no Mac ja na primeira
    linha (`/bin/bash^M: bad interpreter`). O `.gitattributes` fixa LF, como
    fixa CRLF no `.bat`."""
    relativo = script.relative_to(RAIZ).as_posix()
    assert _git("check-attr", "eol", "--", relativo).strip() == f"{relativo}: eol: lf"


# -- o carimbo: so instala quando o requirements muda -------------------------------

def test_instala_na_primeira_vez_e_de_novo_so_quando_o_arquivo_muda(tmp_path, venv):
    requisitos = tmp_path / "requirements.txt"
    requisitos.write_text("pandas\n", encoding="utf-8")

    resultado = _bash(
        f'_sigft_instalar "{requisitos}" requirements; echo "rc=$?"\n'
        f'_sigft_instalar "{requisitos}" requirements; echo "rc=$?"\n'
        f'echo openpyxl >> "{requisitos}"\n'
        f'_sigft_instalar "{requisitos}" requirements; echo "rc=$?"\n',
        tmp_path, SIGFT_VENV_DIR=venv, SIGFT_PY=venv / "bin" / "python",
        SIGFT_PIP_ARGS_EFETIVO="--isolated")

    assert resultado.stdout.count("rc=0") == 3, resultado.stdout + resultado.stderr
    instalacoes = [linha for linha in _registro(tmp_path) if f"-r {requisitos}" in linha]
    assert len(instalacoes) == 2, _registro(tmp_path)
    assert all("--isolated" in linha for linha in instalacoes)
    assert (venv / ".sigft-requirements.stamp").is_file()


def test_pip_que_falha_nao_grava_o_carimbo_e_tenta_de_novo(tmp_path, venv):
    requisitos = tmp_path / "requirements.txt"
    requisitos.write_text("pandas\n", encoding="utf-8")
    comum = dict(SIGFT_VENV_DIR=venv, SIGFT_PY=venv / "bin" / "python",
                 SIGFT_PIP_ARGS_EFETIVO="--isolated")

    falhou = _bash(f'_sigft_instalar "{requisitos}" requirements; echo "rc=$?"',
                   tmp_path, SIGFT_TESTE_CODIGO_PIP=1, **comum)

    assert "rc=0" not in falhou.stdout
    assert "[ERRO]" in falhou.stdout
    assert not (venv / ".sigft-requirements.stamp").exists()

    de_novo = _bash(f'_sigft_instalar "{requisitos}" requirements; echo "rc=$?"',
                    tmp_path, **comum)

    assert "rc=0" in de_novo.stdout
    assert len([linha for linha in _registro(tmp_path) if " -r " in linha]) == 2


def test_pip_que_falha_com_instalacao_anterior_segue_e_tenta_de_novo(tmp_path, venv):
    """Revisao final: o `requirements.txt` mudou (PySide6, ~80 MB) e o pip
    falhou. O ambiente antigo continua inteiro (o pip baixa tudo antes de
    instalar), entao o app abre com ele -- inclusive `--ctk`. O carimbo velho
    fica, para a proxima abertura tentar de novo."""
    requisitos = tmp_path / "requirements.txt"
    requisitos.write_text("pandas\nPySide6-Essentials\n", encoding="utf-8")
    carimbo = venv / ".sigft-requirements.stamp"
    carimbo.write_text("hash-da-instalacao-anterior\n", encoding="utf-8")
    comum = dict(SIGFT_VENV_DIR=venv, SIGFT_PY=venv / "bin" / "python",
                 SIGFT_PIP_ARGS_EFETIVO="--isolated")

    falhou = _bash(f'_sigft_instalar "{requisitos}" requirements; echo "rc=$?"',
                   tmp_path, SIGFT_TESTE_CODIGO_PIP=1, **comum)

    assert "rc=0" in falhou.stdout, falhou.stdout + falhou.stderr
    assert "SEGUINDO" in falhou.stdout
    assert carimbo.read_text(encoding="utf-8") == "hash-da-instalacao-anterior\n"

    de_novo = _bash(f'_sigft_instalar "{requisitos}" requirements; echo "rc=$?"',
                    tmp_path, **comum)

    assert "rc=0" in de_novo.stdout
    assert len([linha for linha in _registro(tmp_path) if " -r " in linha]) == 2
    assert carimbo.read_text(encoding="utf-8") != "hash-da-instalacao-anterior\n"


# -- onde fica o venv ----------------------------------------------------------------

@pytest.mark.parametrize(("caminho", "sincronizada"), [
    ("/Users/ana/Library/Mobile Documents/com~apple~CloudDocs/SIG-FT", True),   # iCloud Drive
    ("/Users/ana/Library/CloudStorage/OneDrive-GEVernova/SIG-FT", True),
    ("/Users/ana/Library/CloudStorage/GoogleDrive-ana@ge.com/Meu Drive/SIG-FT", True),
    ("/Users/ana/OneDrive - GE Vernova/SIG-FT", True),
    ("/Users/ana/Dropbox/SIG-FT", True),
    ("/Users/ana/Google Drive/SIG-FT", True),
    ("/Users/ana/Box Sync/SIG-FT", True),
    ("/Users/ana/Downloads/SIG-FT-main", False),
    ("/Users/ana/Projetos/dropboxer/SIG-FT", False),
])
def test_reconhece_pasta_de_servico_de_sincronizacao(tmp_path, caminho, sincronizada):
    resultado = _bash(f'_sigft_pasta_sincronizada "{caminho}" && echo SIM || echo NAO', tmp_path)
    assert resultado.stdout.strip() == ("SIM" if sincronizada else "NAO"), resultado.stderr


@pytest.mark.parametrize(("dentro_da_casa", "sincronizada"), [
    ("Desktop/SIG-FT", True),
    ("Documents/SIG-FT", True),
    ("Documents/Projetos/SIG-FT-main", True),
    ("documents/SIG-FT", True),        # o disco do Mac nao diferencia maiusculas
    ("Projetos/SIG-FT", False),
    ("DocumentsVelhos/SIG-FT", False),
])
def test_mesa_e_documentos_contam_sempre_como_sincronizadas(tmp_path, dentro_da_casa,
                                                             sincronizada):
    """O iCloud "Mesa e Documentos" sincroniza ~/Desktop e ~/Documents NO LUGAR,
    sem pista confiavel de que esta ligado. Errar para "sincronizada" nao custa
    nada (o venv vai para Application Support); errar para o outro lado poria
    dezenas de milhares de arquivos do venv no iCloud."""
    projeto = tmp_path / "home" / dentro_da_casa

    resultado = _bash(f'_sigft_pasta_sincronizada "{projeto}" && echo SIM || echo NAO',
                      tmp_path)

    assert resultado.stdout.strip() == ("SIM" if sincronizada else "NAO"), resultado.stderr


def test_venv_fica_fora_da_pasta_sincronizada(tmp_path):
    raiz = tmp_path / "Dropbox" / "SIG-FT"
    raiz.mkdir(parents=True)

    resultado = _bash('_sigft_escolher_venv; echo "VENV=$SIGFT_VENV_DIR"', tmp_path,
                      SIGFT_RAIZ=raiz)

    suporte = tmp_path / "home" / "Library" / "Application Support" / "SIG-FT" / "venv"
    assert f"VENV={suporte}" in resultado.stdout, resultado.stdout + resultado.stderr


def test_venv_fica_na_raiz_fora_de_pasta_sincronizada(tmp_path):
    raiz = tmp_path / "Projetos" / "SIG-FT"
    raiz.mkdir(parents=True)

    resultado = _bash('_sigft_escolher_venv; echo "VENV=$SIGFT_VENV_DIR"', tmp_path,
                      SIGFT_RAIZ=raiz)

    assert f"VENV={raiz / '.venv'}" in resultado.stdout, resultado.stdout + resultado.stderr


def test_sigft_venv_manda_no_lugar_do_venv(tmp_path):
    raiz = tmp_path / "Dropbox" / "SIG-FT"
    raiz.mkdir(parents=True)

    resultado = _bash('_sigft_escolher_venv; echo "VENV=$SIGFT_VENV_DIR"', tmp_path,
                      SIGFT_RAIZ=raiz, SIGFT_VENV=tmp_path / "meu-venv")

    assert f"VENV={tmp_path / 'meu-venv'}" in resultado.stdout


# -- o Python ----------------------------------------------------------------------

def test_escolhe_o_primeiro_python_que_serve(tmp_path):
    # O de mentira nao interpreta nada: responde a conferencia de versao com o
    # codigo de saida (1 = antigo demais).
    velho = _executavel(tmp_path / "py" / "python-velho", "#!/bin/sh\nexit 1\n")
    novo = _executavel(tmp_path / "py" / "python-novo", "#!/bin/sh\nexit 0\n")
    outro = _executavel(tmp_path / "py" / "python-outro", "#!/bin/sh\nexit 0\n")

    resultado = _bash(f'_sigft_achar_python "{velho}" "{novo}" "{outro}"; '
                      f'echo "BASE=$SIGFT_PY_BASE"', tmp_path)

    assert f"BASE={novo}" in resultado.stdout, resultado.stdout + resultado.stderr


def test_a_conferencia_de_versao_aceita_um_python_de_verdade(tmp_path):
    """O Python de mentira so devolve codigo; este prova que o trecho que o
    lancador manda ao interpretador (`-c ...`) e Python valido e aceita 3.10+."""
    resultado = _bash(f'_sigft_python_serve "{sys.executable}" && echo SERVE', tmp_path)
    assert ("SERVE" in resultado.stdout) == (sys.version_info >= (3, 10)), resultado.stderr


def test_sem_python_explica_e_da_o_link(tmp_path):
    resultado = _bash('_sigft_achar_python() { SIGFT_PY_BASE=""; }\n'
                      '_sigft_criar_venv; echo "rc=$?"', tmp_path,
                      SIGFT_VENV_DIR=tmp_path / "venv-novo")

    assert "rc=1" in resultado.stdout
    assert "python.org" in resultado.stdout
    assert "3.10" in resultado.stdout


def test_primeira_abertura_cria_o_venv_na_raiz_e_instala(tmp_path, venv):
    """O caminho de quem acabou de baixar: sem venv, acha um Python 3.10+, cria
    `<raiz>/.venv` com ele e instala o `requirements.txt` com o python do venv."""
    raiz = tmp_path / "Projetos" / "SIG-FT"
    raiz.mkdir(parents=True)
    (raiz / "requirements.txt").write_text("pandas\n", encoding="utf-8")
    # O "Python do sistema": confere a versao (exit 0) e, no `-m venv DIR`,
    # monta DIR com o python que anota.
    _executavel(tmp_path / "bin" / "python3.12", (
        "#!/bin/sh\n"
        "printf '%s\\n' \"BASE|$*\" >> \"$SIGFT_TESTE_REGISTRO\"\n"
        "if [ \"$1\" = -m ] && [ \"$2\" = venv ]; then\n"
        f"  mkdir -p \"$3/bin\" && cp \"{venv / 'bin' / 'python'}\" \"$3/bin/python\"\n"
        "fi\n"
        "exit 0\n"))

    resultado = _bash('sigft_bootstrap; echo "rc=$?"; echo "PY=$SIGFT_PY"', tmp_path,
                      SIGFT_RAIZ=raiz, SIGFT_SEM_NAVEGADOR=1,
                      PATH=f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")

    assert "rc=0" in resultado.stdout, resultado.stdout + resultado.stderr
    assert f"PY={raiz / '.venv' / 'bin' / 'python'}" in resultado.stdout
    registro = _registro(tmp_path)
    assert f"BASE|-m venv {raiz / '.venv'}" in registro, registro
    assert any(f"-r {raiz / 'requirements.txt'}" in linha and not linha.startswith("BASE|")
               for linha in registro), registro


# -- o SIG-FT.command inteiro ----------------------------------------------------------

@pytest.mark.parametrize("argumentos", [[], ["--ctk"]])
def test_command_roda_o_frontend_da_raiz_com_o_python_do_venv(tmp_path, venv, argumentos):
    resultado = subprocess.run(
        [str(COMMAND), *argumentos], input="", capture_output=True, text=True, timeout=60,
        cwd=str(tmp_path), env=_ambiente(tmp_path, SIGFT_VENV=venv, SIGFT_SEM_NAVEGADOR=1))

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    esperado = f"{RAIZ}|{RAIZ / 'frontend.py'}" + "".join(f" {a}" for a in argumentos)
    assert esperado in _registro(tmp_path), _registro(tmp_path)


@pytest.mark.parametrize("falha", ["SIGFT_TESTE_CODIGO_APP", "SIGFT_TESTE_CODIGO_PIP"])
def test_command_com_erro_deixa_a_mensagem_na_tela_ate_o_enter(tmp_path, venv, falha):
    processo = subprocess.Popen(
        [str(COMMAND)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, cwd=str(tmp_path),
        env=_ambiente(tmp_path, SIGFT_VENV=venv, SIGFT_SEM_NAVEGADOR=1, **{falha: 3}))
    try:
        time.sleep(1.5)
        assert processo.poll() is None, "fechou sem esperar a pessoa ler o erro"
        saida, _ = processo.communicate("\n", timeout=30)
    finally:
        if processo.poll() is None:
            processo.kill()

    assert processo.returncode == 1
    assert "Encerrado com erro" in saida
    assert f'"{COMMAND}" --ctk' in saida, "sem o caminho para a interface antiga"

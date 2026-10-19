"""O Release instala versões EXATAS (2026-10-19).

Até aqui cada Release pegava a versão mais nova de cada dependência: na
1.2.1-rc.5 entrou o PyMuPDF 2.0 sem ninguém pedir, e ele montava mal o texto
das tabelas. O arquivo de versões é passado com `-c` a cada `pip install` do
Release, e cada linha dele fixa uma versão com `==`.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSOES = RAIZ / "empacotamento" / "versoes-do-release.txt"


def _linhas():
    return [l.strip() for l in VERSOES.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def test_cada_pip_install_do_release_usa_o_arquivo_de_versoes():
    texto = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    passo = texto[texto.index("- name: Instalar dependencias"):]
    passo = passo[:passo.index("- name:", 1)]
    instalacoes = [l for l in passo.splitlines() if "pip install" in l and "--upgrade pip" not in l]

    assert instalacoes and all("-c empacotamento/versoes-do-release.txt" in l for l in instalacoes)


def test_cada_linha_fixa_uma_versao_exata():
    assert all("==" in l and l.count("==") == 1 for l in _linhas())


def test_as_dependencias_que_ja_mudaram_sozinhas_estao_fixadas():
    nomes = {l.split("==")[0].lower() for l in _linhas()}
    assert {"pymupdf", "pyside6-essentials", "pandas", "numpy", "pyinstaller"} <= nomes


def test_nenhuma_dependencia_direta_do_requirements_ficou_sem_versao():
    """Uma dependência nova no `requirements.txt` sem linha aqui entraria na
    versão mais nova do dia -- exatamente o que este arquivo existe para evitar."""
    import re

    fixadas = {re.sub(r"[-_.]+", "-", l.split("==")[0].lower()) for l in _linhas()}
    for linha in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha or linha.startswith("-"):
            continue
        nome = re.split(r"[<>=!~\[; ]", linha, maxsplit=1)[0]
        assert re.sub(r"[-_.]+", "-", nome.lower()) in fixadas, f"{nome} sem versão fixada"


def test_o_pyinstaller_do_release_roda_com_o_hash_fixo():
    """Sem `PYTHONHASHSEED=0`, o `base_library.zip` sai diferente a cada build
    (a ordem das entradas vem de um `set`) e entra em toda atualização pequena."""
    texto = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    passo = texto[texto.index("- name: Gerar o executavel (PyInstaller)"):]
    passo = passo[:passo.index("- name:", 1)]

    assert 'PYTHONHASHSEED: "0"' in passo

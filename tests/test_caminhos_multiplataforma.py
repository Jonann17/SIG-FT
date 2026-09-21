# -*- coding: utf-8 -*-
"""Comparar caminho de arquivo entre sistemas -- o defeito que derrubou o Release.

O QUE ACONTECEU (2026-09-21, run #1 do Release)
------------------------------------------------
Os guards de `tests/` comparam o caminho de cada arquivo do pacote contra uma
lista de excecoes:

    relativo = str(arquivo.relative_to(RAIZ))     # <- aqui
    if relativo in FORA_DO_RECORTE:
        pytest.skip(...)

`str(Path)` usa o separador DO SISTEMA. No Linux sai
`"sigft/services/autospec.py"` e casa com a lista. No Windows sai
`"sigft\\services\\autospec.py"` e NAO CASA -- entao as listas de excecao
ficavam INERTES no Windows, e todo arquivo que deveria ser pulado era testado.

Nove testes reprovaram no primeiro Release, incluindo
`duplicadas_condicoes.py`, que e um dos dois lugares onde o travessao e DADO e
nao pontuacao. A suite passava em Linux (3831) porque em Linux as barras
casam: nenhum CI nosso podia ver isso.

E o ESPELHO EXATO do defeito que a Frente 0 consertou -- la o
`os.path.basename` nao cortava `\\` no POSIX. Mesma familia: tratamento de
caminho que depende do sistema onde o codigo roda.

Estes testes rodam em QUALQUER sistema: eles usam `PureWindowsPath`, que
existe no Linux, em vez de depender de estar num Windows de verdade.
"""
import pathlib

import pytest

from _caminhos import relativo_posix

RAIZ = pathlib.Path(__file__).resolve().parent.parent


# =============================================================================
# A. O helper, nos dois sistemas
# =============================================================================

def test_caminho_do_WINDOWS_sai_com_barra_normal():
    """O caso que quebrou. Roda no Linux gracas ao `PureWindowsPath`."""
    raiz = pathlib.PureWindowsPath(r"D:\a\SIG-FT\SIG-FT")
    arquivo = pathlib.PureWindowsPath(r"D:\a\SIG-FT\SIG-FT\sigft\services\autospec.py")

    assert relativo_posix(arquivo, raiz) == "sigft/services/autospec.py"


def test_caminho_do_LINUX_continua_igual():
    raiz = pathlib.PurePosixPath("/repo")
    arquivo = pathlib.PurePosixPath("/repo/sigft/services/autospec.py")

    assert relativo_posix(arquivo, raiz) == "sigft/services/autospec.py"


def test_os_dois_sistemas_dao_A_MESMA_chave():
    """E a propriedade que importa: a lista de excecoes vale nos dois."""
    do_windows = relativo_posix(
        pathlib.PureWindowsPath(r"C:\x\sigft\core\rede.py"),
        pathlib.PureWindowsPath(r"C:\x"))
    do_linux = relativo_posix(
        pathlib.PurePosixPath("/x/sigft/core/rede.py"),
        pathlib.PurePosixPath("/x"))

    assert do_windows == do_linux == "sigft/core/rede.py"


def test_str_cru_NAO_serve_e_e_por_isso_que_o_helper_existe():
    """A prova de que o helper nao e cerimonia.

    Se este teste um dia falhar, e porque o `pathlib` passou a normalizar
    sozinho -- e ai o helper pode sair.
    """
    arquivo = pathlib.PureWindowsPath(r"D:\x\sigft\services\autospec.py")
    raiz = pathlib.PureWindowsPath(r"D:\x")

    assert str(arquivo.relative_to(raiz)) != "sigft/services/autospec.py"
    assert relativo_posix(arquivo, raiz) == "sigft/services/autospec.py"


# =============================================================================
# B. Os guards usam o helper -- e nao voltam ao `str()`
# =============================================================================

# Os arquivos que COMPARAM caminho contra uma lista. Os que so usam
# `relative_to` para montar mensagem de erro nao entram: exibir com barra
# invertida no Windows e o certo.
GUARDS_QUE_COMPARAM = [
    "tests/test_texto_da_ui.py",
    "tests/test_rede_integracao.py",
]


@pytest.mark.parametrize("arquivo", GUARDS_QUE_COMPARAM)
def test_o_guard_usa_o_helper(arquivo):
    fonte = (RAIZ / arquivo).read_text(encoding="utf-8")

    assert "relativo_posix" in fonte, (
        f"{arquivo} compara caminho contra uma lista de excecoes e precisa do "
        f"`relativo_posix` -- com `str(...)` a lista fica inerte no Windows, e "
        f"nenhum CI em Linux consegue ver isso."
    )


@pytest.mark.parametrize("arquivo", GUARDS_QUE_COMPARAM)
def test_as_listas_de_excecao_usam_barra_normal(arquivo):
    """Uma entrada com `\\` nunca casaria, em sistema nenhum."""
    import ast

    arvore = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"))

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
            continue
        if not no.value.endswith(".py"):
            continue
        assert "\\" not in no.value, (
            f"{arquivo}:{no.lineno} tem `{no.value}` com barra invertida. "
            f"As listas de excecao sao comparadas em formato posix."
        )

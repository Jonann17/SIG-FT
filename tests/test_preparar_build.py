# -*- coding: utf-8 -*-
"""O carimbo do build: versao vinda da TAG e o token que nunca entra no Git.

`tools/preparar_build.py` roda no workflow ANTES do PyInstaller. Ele faz duas
coisas, e as duas tem um modo de falhar caro:

1. reescreve `sigft/_build_info.py` com a versao da tag -- se errar, o
   executavel se declara na versao errada e oferece a mesma atualizacao para
   sempre;
2. grava `sigft/_update_auth.py` com o token de leitura ofuscado -- se esse
   arquivo escapar para o Git, o token vaza.

Nada aqui roda o PyInstaller nem precisa do Windows: e manipulacao de texto.
"""
import ast
import importlib.util
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "tools" / "preparar_build.py"


def _carregar_script():
    """Importa `tools/preparar_build.py` como modulo, sem rodar o `main()`."""
    spec = importlib.util.spec_from_file_location("preparar_build", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def script():
    return _carregar_script()


@pytest.fixture
def raiz_falsa(tmp_path):
    """Uma arvore minima com o `_build_info.py` de verdade copiado."""
    (tmp_path / "sigft").mkdir()
    (tmp_path / "sigft" / "_build_info.py").write_text(
        (RAIZ / "sigft" / "_build_info.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


# =============================================================================
# A. Ofuscacao -- ida e volta
# =============================================================================

def test_o_token_volta_inteiro_depois_de_ofuscar():
    from sigft._ofuscacao import desofuscar, ofuscar

    token = "github_pat_11ABCDEFG_umTokenDeMentiraComTamanhoRealista123456"

    assert desofuscar(ofuscar(token)) == token


def test_o_token_ofuscado_nao_contem_o_texto_claro():
    """O objetivo unico: nao aparecer num `strings SIG-FT.exe`."""
    from sigft._ofuscacao import ofuscar

    token = "github_pat_11ABCDEFG"

    assert token not in ofuscar(token)


def test_token_vazio_nao_estoura():
    from sigft._ofuscacao import desofuscar, ofuscar

    assert ofuscar("") == ""
    assert desofuscar("") == ""


def test_ofuscacao_aguenta_caractere_fora_do_ascii():
    from sigft._ofuscacao import desofuscar, ofuscar

    assert desofuscar(ofuscar("chave-com-acentuação-ç")) == "chave-com-acentuação-ç"


def test_o_modulo_de_ofuscacao_nao_importa_nada_do_pacote():
    """Ele e usado pelas DUAS pontas e nao pode arrastar dependencia.

    O `tools/preparar_build.py` roda no CI, antes de o pacote estar montado;
    o `updater` roda dentro do .exe. Se este modulo importasse, digamos,
    `sigft.config`, o script de build passaria a depender de `python-dotenv`.
    """
    fonte = (RAIZ / "sigft" / "_ofuscacao.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and (no.module or "").startswith("sigft"):
            pytest.fail(f"_ofuscacao.py importa do pacote: {ast.unparse(no)}")
        if isinstance(no, ast.Import):
            for alias in no.names:
                assert not alias.name.startswith("sigft"), (
                    f"_ofuscacao.py importa do pacote: {ast.unparse(no)}"
                )


# =============================================================================
# B. Validacao da versao
# =============================================================================

@pytest.mark.parametrize("versao", ["1.0.0", "0.1.0", "10.20.30", "1.0.0-rc.1",
                                    "1.0.0-beta.2", "2.0.0-alpha"])
def test_versoes_validas(script, versao):
    assert script.SEMVER.match(versao), f"{versao} deveria ser aceita"


@pytest.mark.parametrize("versao", ["1.0", "1", "v1.0.0", "1.0.0.0", "abc",
                                    "", "1.0.0-rc 1"])
def test_versoes_invalidas(script, versao):
    assert not script.SEMVER.match(versao), f"{versao} deveria ser recusada"


def test_o_v_da_tag_e_removido_antes_de_validar(script, raiz_falsa):
    """A tag e `v1.0.0`; a versao e `1.0.0`. Quem corta o `v` e o script."""
    script.escrever_build_info("1.0.0", "github-actions", "abc1234", raiz=raiz_falsa)

    assert 'VERSAO = "1.0.0"' in (raiz_falsa / "sigft" / "_build_info.py").read_text(
        encoding="utf-8")


# =============================================================================
# C. O carimbo em `_build_info.py`
# =============================================================================

def test_carimba_os_quatro_campos(script, raiz_falsa):
    script.escrever_build_info("2.3.4", "github-actions", "a1b2c3d4e5f6",
                               raiz=raiz_falsa, hoje="2026-10-01")

    texto = (raiz_falsa / "sigft" / "_build_info.py").read_text(encoding="utf-8")

    assert 'VERSAO = "2.3.4"' in texto
    assert 'ORIGEM = "github-actions"' in texto
    assert 'DATA_BUILD = "2026-10-01"' in texto


def test_o_commit_e_cortado_em_7_caracteres(script, raiz_falsa):
    """SHA inteiro numa barra de titulo nao cabe e nao ajuda."""
    script.escrever_build_info("1.0.0", "github-actions",
                               "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
                               raiz=raiz_falsa)

    texto = (raiz_falsa / "sigft" / "_build_info.py").read_text(encoding="utf-8")

    assert 'COMMIT = "a1b2c3d"' in texto


def test_o_arquivo_carimbado_continua_sendo_python_valido(script, raiz_falsa):
    script.escrever_build_info("1.2.3", "github-actions", "abc1234", raiz=raiz_falsa)

    ast.parse((raiz_falsa / "sigft" / "_build_info.py").read_text(encoding="utf-8"))


def _atribuicoes_de(fonte: str, nome: str) -> list[str]:
    """Os valores atribuidos a `nome` no NIVEL DO MODULO, via AST.

    Contar ocorrencias do texto `VERSAO = ` no arquivo nao serve: o docstring
    do `_build_info.py` mostra `VERSAO = "1.0.0"` como EXEMPLO, justamente
    para explicar de onde a versao vem. Uma contagem textual reprovaria a
    explicacao, nao a duplicacao.
    """
    return [
        ast.literal_eval(no.value)
        for no in ast.parse(fonte).body
        if isinstance(no, ast.Assign)
        and any(isinstance(a, ast.Name) and a.id == nome for a in no.targets)
        and isinstance(no.value, ast.Constant)
    ]


def test_o_carimbo_e_idempotente(script, raiz_falsa):
    """Rodar duas vezes nao duplica a atribuicao nem acumula versao."""
    script.escrever_build_info("1.0.0", "local", "aaaaaaa", raiz=raiz_falsa)
    script.escrever_build_info("2.0.0", "github-actions", "bbbbbbb", raiz=raiz_falsa)

    fonte = (raiz_falsa / "sigft" / "_build_info.py").read_text(encoding="utf-8")

    assert _atribuicoes_de(fonte, "VERSAO") == ["2.0.0"]


def test_o_carimbo_acerta_a_ATRIBUICAO_e_nao_o_docstring(script, raiz_falsa):
    """A substituicao e ancorada em inicio de linha, e isso importa.

    O `_build_info.py` cita `VERSAO = "1.0.0"` dentro do proprio docstring. Se
    a expressao regular nao exigisse comeco de linha, o carimbo trocaria o
    EXEMPLO e deixaria a atribuicao de verdade intacta -- o build sairia com a
    versao antiga, e o unico sintoma seria o app oferecendo a mesma
    atualizacao para sempre.
    """
    script.escrever_build_info("7.7.7", "github-actions", "abc1234", raiz=raiz_falsa)

    caminho = raiz_falsa / "sigft" / "_build_info.py"
    fonte = caminho.read_text(encoding="utf-8")

    assert _atribuicoes_de(fonte, "VERSAO") == ["7.7.7"]
    # e o exemplo do docstring continua dizendo o que dizia
    assert 'VERSAO = "1.0.0"' in ast.get_docstring(ast.parse(fonte))


def test_arquivo_sem_a_linha_esperada_FALHA_em_vez_de_seguir(script, tmp_path):
    """Se o `_build_info.py` for reescrito e perder a linha, o build PARA.

    O modo silencioso seria pior: o build seguiria com a versao antiga
    embutida, e o executavel publicado como 2.0.0 se declararia 1.0.0.
    """
    (tmp_path / "sigft").mkdir()
    (tmp_path / "sigft" / "_build_info.py").write_text("# vazio\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        script.escrever_build_info("1.0.0", "local", "abc", raiz=tmp_path)


# =============================================================================
# D. O token: entra no build, nunca no Git
# =============================================================================

def test_sem_variavel_de_ambiente_o_token_sai_vazio(script, raiz_falsa):
    """Build local nao tem o segredo -- e simplesmente nao checa atualizacao."""
    script.escrever_token("", raiz=raiz_falsa)

    texto = (raiz_falsa / "sigft" / "_update_auth.py").read_text(encoding="utf-8")

    assert 'TOKEN_OFUSCADO = ""' in texto


def test_com_token_o_arquivo_sai_ofuscado_e_legivel_de_volta(script, raiz_falsa):
    from sigft._ofuscacao import desofuscar

    script.escrever_token("github_pat_umSegredo", raiz=raiz_falsa)
    texto = (raiz_falsa / "sigft" / "_update_auth.py").read_text(encoding="utf-8")

    assert "github_pat_umSegredo" not in texto

    espaco = {}
    exec(compile(texto, "_update_auth.py", "exec"), espaco)  # noqa: S102
    assert desofuscar(espaco["TOKEN_OFUSCADO"]) == "github_pat_umSegredo"


def test_update_auth_esta_no_gitignore():
    """A trava que impede o token de chegar ao repositorio.

    Sem ela, um `git add -A` numa maquina que rodou o preparar_build com o
    segredo definido comita o token. Nao ha como despublicar isso.
    """
    ignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")

    assert "_update_auth.py" in ignore, (
        "sigft/_update_auth.py precisa estar no .gitignore -- e ele que carrega "
        "o token do build."
    )


def test_o_update_auth_nao_esta_versionado():
    """Cinto e suspensorio: o .gitignore pode ter sido acrescentado DEPOIS."""
    saida = subprocess.run(
        [sys.executable, "-c", "pass"], capture_output=True)  # noqa: S603
    assert saida.returncode == 0  # sanidade do ambiente

    rastreados = subprocess.run(  # noqa: S603
        ["git", "ls-files", "sigft/_update_auth.py"],
        cwd=RAIZ, capture_output=True, text=True,
    )
    assert rastreados.stdout.strip() == "", (
        "sigft/_update_auth.py esta rastreado pelo git. Remova com "
        "`git rm --cached sigft/_update_auth.py` e ROTACIONE o token."
    )


# =============================================================================
# E. A armadilha do cp1252 (armadilha n. 1 do usuario)
# =============================================================================

def test_o_script_forca_utf8_na_saida():
    """No Windows o Python escreve no console em cp1252.

    Um `print` com acento derruba o passo com UnicodeEncodeError -- o build
    morre por causa de uma MENSAGEM, depois de lint e testes ja terem passado.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")

    assert "reconfigure" in fonte and "utf-8" in fonte, (
        "preparar_build.py precisa forcar UTF-8 em stdout/stderr"
    )


def test_forcar_utf8_nao_estoura_com_saida_substituida(script):
    """Sob pytest, `sys.stdout` e um objeto sem `.reconfigure`."""
    script._saida_utf8()  # nao deve levantar

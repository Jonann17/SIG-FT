# -*- coding: utf-8 -*-
"""A identidade do BUILD: de onde sai a versao do SIG-FT.

Ate aqui o projeto nao tinha versao nenhuma -- `sigft/__init__.py` dizia
`__version__ = "0.0.0"` e ninguem lia. Com o Release pelo GitHub Actions a
versao passa a ser a pergunta central: e ela que o verificador de atualizacao
compara com o ultimo Release publicado.

O que estes testes travam e a ARMADILHA que o DocManager pagou na v3.0.0: a
versao NAO pode vir de arquivo do usuario (`.env`, `api_config.json`). Esses
arquivos sobrevivem a atualizacao; se a versao viesse de la, o app recem
atualizado continuaria se declarando na versao velha e ofereceria a mesma
atualizacao para sempre. Versao e caracteristica do BINARIO.
"""
import ast
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent


# =============================================================================
# A. `descricao()` -- a linha de diagnostico
# =============================================================================

def test_descricao_junta_origem_commit_e_data():
    from sigft import _build_info

    assert _build_info.descricao.__doc__  # a funcao existe e e documentada


def test_descricao_com_todos_os_campos_preenchidos(monkeypatch):
    from sigft import _build_info

    monkeypatch.setattr(_build_info, "VERSAO", "1.2.3")
    monkeypatch.setattr(_build_info, "ORIGEM", "github-actions")
    monkeypatch.setattr(_build_info, "COMMIT", "a1b2c3d")
    monkeypatch.setattr(_build_info, "DATA_BUILD", "2026-09-18")

    assert _build_info.descricao() == "1.2.3 (github-actions - a1b2c3d - 2026-09-18)"


def test_descricao_de_build_local_nao_inventa_parenteses_vazio(monkeypatch):
    """Sem commit nem data, a descricao e so a versao -- nao `1.2.3 ()`."""
    from sigft import _build_info

    monkeypatch.setattr(_build_info, "VERSAO", "1.2.3")
    monkeypatch.setattr(_build_info, "ORIGEM", "")
    monkeypatch.setattr(_build_info, "COMMIT", "")
    monkeypatch.setattr(_build_info, "DATA_BUILD", "")

    assert _build_info.descricao() == "1.2.3"


# =============================================================================
# B. Fonte UNICA -- o teste que impede a divergencia
# =============================================================================

def test_sigft_version_deriva_do_build_info():
    """`sigft.__version__` e `_build_info.VERSAO` sao o MESMO valor.

    Duas constantes de versao em dois arquivos divergem na primeira pressa, e
    a divergencia e invisivel: o app mostra uma na tela e compara a outra com
    o Release.
    """
    import sigft
    from sigft import _build_info

    assert sigft.__version__ == _build_info.VERSAO


def test_o_init_NAO_tem_a_versao_escrita_a_mao():
    """`sigft/__init__.py` nao pode carregar um literal de versao proprio.

    Se alguem reescrever `__version__ = "1.3.0"` la, o teste acima continua
    passando enquanto os dois numeros forem iguais -- e para de passar so
    quando ja for tarde. Aqui a regra e estrutural: o valor tem de VIR do
    `_build_info`, nao ser copiado dele.
    """
    fonte = (RAIZ / "sigft" / "__init__.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        nomes = {a.id for a in no.targets if isinstance(a, ast.Name)}
        if "__version__" not in nomes:
            continue
        assert not isinstance(no.value, ast.Constant), (
            "`__version__` esta escrito a mao em sigft/__init__.py. "
            "Ele tem de vir de `_build_info.VERSAO`, que e o que o CI carimba "
            "a partir da tag."
        )


# =============================================================================
# C. A versao NUNCA vem de arquivo do usuario
# =============================================================================

def test_build_info_nao_le_env_nem_api_config():
    """A armadilha da v3.0.0 do DocManager, travada estruturalmente.

    `.env` e `api_config.json` sao arquivos do USUARIO: sobrevivem a
    atualizacao. Versao que sai de la fica congelada na hora da instalacao.

    A checagem e sobre CODIGO, via AST, e nao por busca de texto no fonte: o
    modulo EXPLICA a armadilha no docstring (e deve mesmo -- e o que impede
    alguem de reintroduzi-la), e uma busca por substring reprovaria a propria
    explicacao. Pior: uma busca por `"os.getenv"` tambem nao pegaria
    `from os import getenv`, que e a forma que passaria batida.
    """
    fonte = (RAIZ / "sigft" / "_build_info.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    # Nenhum import: este modulo e literal puro (o `__future__` nao conta,
    # porque nao traz nada para o tempo de execucao).
    importados = [
        no for no in ast.walk(arvore)
        if isinstance(no, (ast.Import, ast.ImportFrom))
        and getattr(no, "module", None) != "__future__"
    ]
    assert not importados, (
        "_build_info.py importa algo. Ele tem de ser literal puro -- qualquer "
        "import e a porta por onde a leitura de arquivo do usuario volta: "
        + ", ".join(ast.unparse(no) for no in importados)
    )

    # E nenhuma chamada de funcao no nivel do modulo (`VERSAO = alguma_coisa()`
    # seria versao calculada em tempo de execucao, que e o defeito).
    for no in arvore.body:
        if isinstance(no, (ast.Assign, ast.AnnAssign)) and no.value is not None:
            assert isinstance(no.value, ast.Constant), (
                f"`{ast.unparse(no)}` nao e um literal. A versao tem de ser "
                f"carimbada pelo CI, nao calculada na abertura do app."
            )


def test_versao_atual_e_semver_valido():
    from sigft import _build_info

    assert re.match(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$", _build_info.VERSAO), (
        f"VERSAO = {_build_info.VERSAO!r} nao e MAJOR.MINOR.PATCH"
    )


# =============================================================================
# D. A versao APARECE para o usuario
# =============================================================================
#
# Sem isto, nada do resto se ve: a pessoa atualiza e nao tem como saber em que
# versao esta -- e quando ela relata um problema, ninguem sabe contra qual
# build. E tambem a prova de que a atualizacao funcionou.

def test_a_barra_de_titulo_mostra_a_versao():
    """O titulo da janela principal carrega a versao do build."""
    fonte = (RAIZ / "sigft" / "app_qt" / "main.py").read_text(encoding="utf-8")

    titulos = re.findall(r"self\.setWindowTitle\((.+?)\)\n", fonte)
    principal = [t for t in titulos if "SIG-FT" in t]

    assert principal, "nao achei o titulo da janela principal"
    assert any("VERSAO" in t or "_build_info" in t or "versao" in t.lower()
               for t in principal), (
        f"o titulo nao mostra a versao: {principal}. Sem ela, a pessoa nao tem "
        f"como saber em que build esta -- nem para relatar um problema, nem "
        f"para confirmar que a atualizacao pegou."
    )

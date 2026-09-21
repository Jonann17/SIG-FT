# -*- coding: utf-8 -*-
"""Quem decide a versao e se o release e pre-lancamento.

Por que isto virou um script Python, e nao 5 linhas de shell no YAML
--------------------------------------------------------------------
Porque a primeira versao ficou no YAML e tinha um defeito que ninguem podia
ver: `git tag v1.0.0-rc.1` publicava um release NORMAL. O bloco so marcava
pre-lancamento quando o disparo vinha do BOTAO:

    if [ "$evento" = "workflow_dispatch" ]; then
      prerelease="${{ inputs.prerelease }}"
    else
      prerelease=false        # <- aqui
    fi

E o efeito e o pior tipo: `/releases/latest` ignora pre-lancamentos, mas so os
MARCADOS como tal -- o sufixo `-rc.1` no nome nao significa nada para o GitHub.
Entao o candidato a lancamento viraria a versao "mais recente" e seria oferecido
como atualizacao para todo mundo, que e exatamente o contrario do que um
`-rc` existe para fazer.

Logica em YAML nao tem teste. Mesma razao do `tools/gerar_manifesto.py`.
"""
import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "tools" / "versao_do_release.py"
WORKFLOW = RAIZ / ".github" / "workflows" / "release.yml"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("versao_do_release", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# =============================================================================
# A. O defeito que originou o arquivo
# =============================================================================

def test_tag_com_sufixo_SAI_como_pre_lancamento(script):
    """O conserto. `v1.0.0-rc.1` nao pode virar a versao mais recente.

    `/releases/latest` ignora pre-lancamentos, mas so os MARCADOS. O sufixo
    no nome nao diz nada ao GitHub -- quem marca e a flag.
    """
    d = script.decidir(evento="push", ref_name="v1.0.0-rc.1")

    assert d["prerelease"] is True


def test_tag_sem_sufixo_SAI_como_release_normal(script):
    d = script.decidir(evento="push", ref_name="v1.0.0")

    assert d["prerelease"] is False


@pytest.mark.parametrize("ref", ["v1.0.0-rc.1", "v2.3.4-beta.2", "v1.0.0-alpha"])
def test_qualquer_sufixo_conta_como_pre_lancamento(script, ref):
    assert script.decidir(evento="push", ref_name=ref)["prerelease"] is True


# =============================================================================
# B. A versao
# =============================================================================

def test_o_v_da_tag_e_removido(script):
    assert script.decidir(evento="push", ref_name="v1.0.0")["versao"] == "1.0.0"


def test_tag_sem_v_tambem_funciona(script):
    assert script.decidir(evento="push", ref_name="1.0.0")["versao"] == "1.0.0"


def test_a_tag_devolvida_tem_o_v(script):
    assert script.decidir(evento="push", ref_name="1.0.0")["tag"] == "v1.0.0"


# =============================================================================
# C. A versao BINARIA -- armadilha n. 2 do usuario
# =============================================================================

def test_a_versao_binaria_corta_o_sufixo(script):
    """`VersionInfoVersion` do Inno so aceita DIGITOS: "1.0.0-rc.1" faz o
    compilador ABORTAR."""
    d = script.decidir(evento="push", ref_name="v1.0.0-rc.1")

    assert d["numerica"] == "1.0.0"
    assert d["versao"] == "1.0.0-rc.1", "a de EXIBICAO mantem o sufixo"


def test_a_versao_binaria_e_so_digitos_e_pontos(script):
    import re

    for ref in ("v1.0.0", "v1.0.0-rc.1", "v10.20.30-beta.5"):
        numerica = script.decidir(evento="push", ref_name=ref)["numerica"]
        assert re.match(r"^\d+(\.\d+)*$", numerica), (
            f"{numerica!r} tem caractere que o Inno recusa"
        )


# =============================================================================
# D. O botao (workflow_dispatch)
# =============================================================================

def test_pelo_botao_a_escolha_da_caixa_manda(script):
    """Marcou a caixa, e pre-lancamento. Desmarcou, e publicacao de verdade."""
    assert script.decidir(evento="workflow_dispatch", entrada_versao="1.0.0",
                          entrada_prerelease=True)["prerelease"] is True
    assert script.decidir(evento="workflow_dispatch", entrada_versao="1.0.0",
                          entrada_prerelease=False)["prerelease"] is False


def test_pelo_botao_o_sufixo_NAO_forca_pre_lancamento(script):
    """Escolha explicita da pessoa ganha da deducao.

    Quem digitou `1.0.0-rc.1` e DESMARCOU a caixa quis publicar de verdade --
    talvez para testar o proprio fluxo de atualizacao. Forcar aqui seria
    decidir por ela.
    """
    d = script.decidir(evento="workflow_dispatch", entrada_versao="1.0.0-rc.1",
                       entrada_prerelease=False)

    assert d["prerelease"] is False


@pytest.mark.parametrize("valor, esperado", [
    ("true", True), ("false", False), ("True", True), ("", False),
    (True, True), (False, False),
])
def test_a_caixa_chega_como_TEXTO_do_github(script, valor, esperado):
    """O `inputs.prerelease` chega como a STRING "true"/"false".

    Em Python, `bool("false")` e True -- e o release sairia sempre marcado
    como pre-lancamento, nunca sendo oferecido a ninguem. Silencioso.
    """
    d = script.decidir(evento="workflow_dispatch", entrada_versao="1.0.0",
                       entrada_prerelease=valor)

    assert d["prerelease"] is esperado


# =============================================================================
# E. Versao invalida PARA o build
# =============================================================================

@pytest.mark.parametrize("ruim", ["v1.0", "abc", "", "1.0.0.0", "v"])
def test_versao_invalida_levanta(script, ruim):
    """Melhor parar aqui do que 20 minutos depois, no Inno Setup."""
    with pytest.raises(SystemExit):
        script.decidir(evento="push", ref_name=ruim)


# =============================================================================
# F. O workflow usa o script
# =============================================================================

def test_o_workflow_chama_o_script():
    """Sem isto, o script existe e o YAML continua com a logica antiga."""
    texto = WORKFLOW.read_text(encoding="utf-8")

    assert "tools/versao_do_release.py" in texto


def test_o_workflow_NAO_decide_pre_lancamento_sozinho():
    """O bloco antigo nao pode ter sobrado.

    A checagem e sobre a ESCRITA NO GITHUB_OUTPUT, e nao sobre o texto
    `prerelease=false` em qualquer lugar: o passo que publica usa
    `gh release create --prerelease=false`, que e legitimo e diferente. Foi a
    terceira vez nesta frente que escrevi um guard medindo texto em vez da
    coisa -- vale como lembrete.
    """
    texto = WORKFLOW.read_text(encoding="utf-8")

    decisoes = [
        linha.strip() for linha in texto.splitlines()
        if "prerelease=" in linha and "GITHUB_OUTPUT" in linha
    ]

    assert not decisoes, (
        "o YAML voltou a decidir o pre-lancamento por conta propria -- era "
        "isso que publicava um -rc.1 como release normal:\n  "
        + "\n  ".join(decisoes)
    )

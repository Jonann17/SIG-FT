r"""A tela do módulo 2 com a fonte "planilha de PDMs" e a regeneração das pastas.

Por AST: `views/pdm.py` importa customtkinter e exige um root Tk (o mesmo
recurso de `test_pdm_montador_idioma.py`)."""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

VIEW = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app" / "views" / "pdm.py"


def _arvore():
    return ast.parse(VIEW.read_text(encoding="utf-8"))


def _metodo(nome):
    for no in ast.walk(_arvore()):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloPDM":
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == nome:
                    return item
    pytest.fail(f"metodo {nome} nao existe na tela do PDM")


def _chamadas(raiz, nome_funcao):
    return [no for no in ast.walk(raiz) if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute) and no.func.attr == nome_funcao]


def _textos(raiz):
    return [no.value for no in ast.walk(raiz)
            if isinstance(no, ast.Constant) and isinstance(no.value, str)]


def test_a_fonte_padrao_das_perguntas_e_a_planilha():
    init = _metodo("__init__")
    assert "fonte_perguntas" in ast.dump(init)
    assert any(k.arg == "value" and getattr(k.value, "value", None) == "planilha"
               for chamada in _chamadas(init, "StringVar") for k in chamada.keywords)


def test_a_aba_2_oferece_as_duas_fontes():
    textos = _textos(_metodo("_build_tab2"))
    assert "planilha" in textos
    assert "pasta" in textos


def test_planilha_com_ingles_e_recusado_antes_de_comecar():
    """A ficha em inglês precisa das perguntas TRADUZIDAS, que só existem na
    pasta. Pela planilha sairia ficha em inglês com perguntas em português, o
    erro que não se denuncia sozinho."""
    assert any("A ficha em inglês usa a pasta traduzida" in t
               for t in _textos(_metodo("_op2_executar")))


def test_a_aba_2_carrega_o_catalogo_e_chama_o_montador_da_planilha():
    metodo = _metodo("_op2_executar")
    assert _chamadas(metodo, "carregar")
    assert _chamadas(metodo, "aplicar_templates_fichas_da_planilha")


def test_a_aba_1_tem_a_regeneracao_e_ela_chama_o_servico():
    assert "_op1_regenerar" in ast.dump(_metodo("_build_tab1"))
    assert _chamadas(_metodo("_op1_regenerar"), "regenerar_pastas")


def test_o_seletor_da_planilha_fica_no_painel_de_cima():
    """As duas abas usam a planilha: o seletor subiu da aba 1 para o painel."""
    assert "_sel_sam_gm" in ast.dump(_metodo("_build_ui"))
    assert "_sel_sam_gm" not in ast.dump(_metodo("_build_tab1"))


def test_a_tela_nao_decide_pergunta_revisao_nem_nome_de_arquivo():
    """Princípio nº 2 do CLAUDE.md: regra de negócio mora no serviço."""
    fonte = VIEW.read_text(encoding="utf-8")
    for proibido in ("montar_pergunta", "perguntas_do_pdm", "revisao_do_pdm",
                     "nome_de_arquivo", "shutil"):
        assert proibido not in fonte, proibido


def test_as_chamadas_aos_servicos_batem_com_a_assinatura():
    """Um `log_callback=` que virasse `callback=` no serviço só quebraria no
    clique; os serviços são importáveis, então dá para conferir aqui."""
    from sigft.core import pdm_catalogo
    from sigft.services import pdm, pdm_regeneracao

    alvos = {
        "aplicar_templates_fichas_da_planilha": pdm.aplicar_templates_fichas_da_planilha,
        "aplicar_templates_fichas": pdm.aplicar_templates_fichas,
        "regenerar_pastas": pdm_regeneracao.regenerar_pastas,
        "carregar": pdm_catalogo.carregar,
    }
    problemas = []
    for nome, funcao in alvos.items():
        for chamada in _chamadas(_arvore(), nome):
            try:
                inspect.signature(funcao).bind(*chamada.args,
                                               **{k.arg: None for k in chamada.keywords})
            except TypeError as erro:
                problemas.append(f"{nome}: {erro}")
    assert not problemas, "\n".join(problemas)

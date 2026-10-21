r"""A tela do módulo 2: as fichas saem da planilha de PDMs (a única fonte desde
2026-10-21, quando a pasta de PDMs Modificados e a regeneração sairam).

Por AST, sobre a tela Qt (`sigft/app_qt/views/pdm.py`; a interface antiga
saiu em 2026-10-15). Na Qt o clique valida e o trabalho roda numa tarefa
(`_tarefa_*`), então a chamada ao serviço mora na tarefa."""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

VIEW = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app_qt" / "views" / "pdm.py"


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


def test_nao_ha_escolha_de_fonte_nem_pasta_de_pdms_modificados():
    """A fonte das características é sempre a planilha do painel de cima."""
    fonte = VIEW.read_text(encoding="utf-8")
    for proibido in ("fonte_perguntas", "entry_dest.", "entry_dest =", "aplicar_templates_fichas(",
                     "pdm_regeneracao", "traduzir_pasta", "logica_excluir_duplicados"):
        assert proibido not in fonte, proibido


def test_a_criacao_carrega_o_catalogo_e_chama_o_montador_da_planilha():
    assert "self._tarefa_fichas" in ast.unparse(_metodo("_op2_executar"))
    metodo = _metodo("_tarefa_fichas")
    assert _chamadas(metodo, "carregar")
    assert _chamadas(metodo, "aplicar_templates_fichas_da_planilha")


def test_o_seletor_da_planilha_fica_no_painel_de_cima():
    assert "_painel_global" in ast.dump(_metodo("_build_ui"))
    assert "_sel_sam_gm" in ast.dump(_metodo("_painel_global"))
    assert "_sel_sam_gm" not in ast.dump(_metodo("_build_fichas"))


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
    from sigft.services import pdm

    alvos = {
        "aplicar_templates_fichas_da_planilha": pdm.aplicar_templates_fichas_da_planilha,
        "processar_pastas_fichas": pdm.processar_pastas_fichas,
        "codigos_pmib_da_lista": pdm.codigos_pmib_da_lista,
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

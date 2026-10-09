r"""A tela do Cria Fichas não tem mais a regra da revisão (2026-10-08).

Lida por AST: as telas não podem ser importadas neste ambiente.
"""
from __future__ import annotations

import ast
import pathlib

TELA = pathlib.Path(__file__).resolve().parent.parent / "sigft" / "app" / "views" / "cria_fichas.py"


def _chamadas():
    nomes = set()
    for no in ast.walk(ast.parse(TELA.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            nomes.add(no.func.attr)
    return nomes


def test_a_tela_nao_confere_pdm_sozinha():
    """A guarda contra PDM inventado mora em `preparar_para_revisao`."""
    assert "conferir_pdm" not in _chamadas()


def test_a_tela_delega_as_duas_passadas_ao_servico():
    assert "classificar_para_revisao" in _chamadas()


JANELAS = TELA.parent / "janelas.py"


def _classe(nome):
    for no in ast.walk(ast.parse(JANELAS.read_text(encoding="utf-8"))):
        if isinstance(no, ast.ClassDef) and no.name == nome:
            return no
    raise AssertionError(nome)


def _chamadas_em(no):
    return {c.func.attr for c in ast.walk(no)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}


def test_o_seletor_aceita_sugestoes():
    init = next(f for f in _classe("JanelaEscolherPDM").body
                if isinstance(f, ast.FunctionDef) and f.name == "__init__")
    assert "sugestoes" in [a.arg for a in init.args.args + init.args.kwonlyargs]


def test_a_revisao_usa_as_regras_do_servico_para_exibir():
    chamadas = _chamadas_em(_classe("JanelaRevisaoPDM"))
    for regra in ("ordem_para_revisao", "rotulo_de_confianca",
                  "texto_do_porque", "sugestoes_da_linha"):
        assert regra in chamadas, regra


def test_a_revisao_nao_ordena_por_conta_propria():
    nomes = {c.func.id for c in ast.walk(_classe("JanelaRevisaoPDM"))
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "sorted" not in nomes


def test_a_revisao_tem_a_coluna_confianca():
    textos = {no.value for no in ast.walk(_classe("JanelaRevisaoPDM"))
              if isinstance(no, ast.Constant) and isinstance(no.value, str)}
    assert "Confiança" in textos


def test_a_tela_grava_a_calibracao_ao_confirmar_a_revisao():
    for no in ast.walk(ast.parse(TELA.read_text(encoding="utf-8"))):
        if isinstance(no, ast.FunctionDef) and no.name == "_pos_revisao_concluida":
            assert "gravar_calibracao" in _chamadas_em(no)
            return
    raise AssertionError("_pos_revisao_concluida sumiu")

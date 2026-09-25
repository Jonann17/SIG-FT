r"""Tela 4.2 (`views/translator.py`), lida por AST: ela importa customtkinter
e exige um root Tk (mesmo recurso de `test_pdm_tela_layout.py`).

O que se segura aqui:

* **o backend nasce no primeiro clique**, não no `__init__`. PENDENCIAS
  2026-09-24: `TechnicalTranslator()` no `__init__` derrubava a janela
  principal inteira quando o backend não carregava (faltou `unidecode`,
  `xlwings`...), contra a promessa de `backends.carregar_todos` de deixar
  "UMA tela sem funcionar, não o aplicativo inteiro";
* **o lote vai inteiro ao serviço** (`processar_arquivos`): um Excel e um
  modelo para todas as fichas, em vez de um laço de `processar_arquivo`;
* o "ABORTADO" (modelo ausente) vira mensagem de erro, não "Sucesso";
* o botão "Abrir glossário" existe e abre o arquivo do usuário.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

VIEW = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app" / "views" / "translator.py"
ARVORE = ast.parse(VIEW.read_text(encoding="utf-8"))


def _metodo(nome):
    for no in ast.walk(ARVORE):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloTranslator":
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == nome:
                    return item
    pytest.fail(f"ModuloTranslator.{nome} nao existe")


def _chamadas(no):
    return [ast.unparse(c.func) for c in ast.walk(no) if isinstance(c, ast.Call)]


def _textos(no):
    return [c.value for c in ast.walk(no) if isinstance(c, ast.Constant) and isinstance(c.value, str)]


def test_o_backend_nao_nasce_no_init():
    assert not any("TechnicalTranslator" in c for c in _chamadas(_metodo("__init__")))


def test_o_backend_nasce_no_primeiro_uso_e_avisa_se_o_modulo_nao_carregou():
    metodo = _metodo("_backend")
    assert any("TechnicalTranslator" in c for c in _chamadas(metodo))
    assert any("showerror" in c for c in _chamadas(metodo))


def test_o_lote_vai_inteiro_ao_servico():
    chamadas = _chamadas(_metodo("_worker"))
    assert any(c.endswith("processar_arquivos") for c in chamadas)
    assert not any(c.endswith("processar_arquivo") for c in chamadas)


def test_abortado_vira_erro_na_tela():
    metodo = _metodo("_worker")
    assert "ABORTADO" in _textos(metodo)
    assert any("showerror" in c for c in _chamadas(metodo))


def test_o_worker_nao_mostra_as_palavras_de_status():
    assert any("STATUS" in c for c in [ast.unparse(n) for n in ast.walk(_metodo("_worker"))
                                        if isinstance(n, ast.Attribute)])


def test_botao_abrir_glossario():
    textos = _textos(_metodo("_build_ui"))
    assert any("glossário" in t.lower() for t in textos)
    assert any("abrir_no_sistema" in c for c in _chamadas(_metodo("abrir_glossario")))


def test_a_tela_diz_que_a_traducao_e_local():
    assert any("computador" in t for t in _textos(_metodo("_build_ui")))


def test_a_tela_nao_importa_excel_nem_modelo():
    importados = set()
    for no in ast.walk(ARVORE):
        if isinstance(no, ast.Import):
            importados |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom):
            importados.add(no.module or "")
    proibidos = {"xlwings", "openpyxl", "ctranslate2", "sentencepiece"}
    assert not importados & proibidos

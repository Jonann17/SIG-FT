r"""A tela do Gestão PMIB pergunta pelos arquivos travados do jeito novo
(`docs/superpowers/specs/2026-10-06-gravacao-com-retry-design.md`).

O guarda é por AST, como o de `tests/test_tela_correcao_pdm.py`, sobre a tela
Qt (`sigft/app_qt/views/pmib_manager.py`; a interface antiga saiu em
2026-10-15). O que ele prova:

  - a tela adota o mixin das janelas de espera (`DialogosDeEspera`, pelo
    `ModuleFrame`) e passa
    `perguntar_arquivos_travados` como `callback_travados` aos DOIS fluxos --
    sem isso, o serviço segue sem perguntar nada, e a pessoa só descobre no
    resumo do fim;
  - a pergunta antiga, um `askretrycancel` por arquivo no meio da etapa, saiu.

A janela de verdade é conferida em `tests/test_qt_tela_pmib_manager.py`.
"""
from __future__ import annotations

import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TELA = RAIZ / "sigft" / "app_qt" / "views" / "pmib_manager.py"


def _arvore():
    return ast.parse(TELA.read_text(encoding="utf-8"))


def _classe(arvore, nome):
    return next(no for no in ast.walk(arvore) if isinstance(no, ast.ClassDef) and no.name == nome)


def _keywords_das_chamadas(arvore, atributo):
    """`{keyword: ast.unparse(valor)}` de cada chamada `<algo>.<atributo>(...)`."""
    chamadas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and no.func.attr == atributo:
            chamadas.append({k.arg: ast.unparse(k.value) for k in no.keywords})
    return chamadas


def test_a_tela_adota_as_janelas_de_espera():
    from sigft.app_qt.widgets.espera import DialogosDeEspera
    from sigft.app_qt.widgets.module_frame import ModuleFrame

    classe = _classe(_arvore(), "ModuloPMIBManager")
    bases = [ast.unparse(b) for b in classe.bases]
    assert bases == ["ModuleFrame"], bases
    assert issubclass(ModuleFrame, DialogosDeEspera)


def test_os_dois_fluxos_recebem_a_pergunta_dos_travados():
    arvore = _arvore()
    for atributo in ("executar_fluxo", "executar"):
        chamadas = _keywords_das_chamadas(arvore, atributo)
        assert chamadas, atributo
        for keywords in chamadas:
            assert keywords.get("callback_travados") == "self.perguntar_arquivos_travados", (atributo, keywords)
            assert "callback_retry_lock" not in keywords


def test_a_pergunta_por_arquivo_no_meio_da_etapa_saiu():
    fonte = TELA.read_text(encoding="utf-8")
    assert "askretrycancel" not in fonte
    assert "_perguntar_arquivo_aberto" not in fonte

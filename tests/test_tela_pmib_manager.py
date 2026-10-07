r"""A tela do Gestão PMIB pergunta pelos arquivos travados do jeito novo
(`docs/superpowers/specs/2026-10-06-gravacao-com-retry-design.md`).

As telas não são importadas na suíte: o guarda é por AST, como o de
`tests/test_tela_correcao_pdm.py`. O que ele prova:

  - a tela adota o mixin das janelas de espera (`DialogosDeEspera`) e passa
    `perguntar_arquivos_travados` como `callback_travados` aos DOIS fluxos --
    sem isso, o serviço segue sem perguntar nada, e a pessoa só descobre no
    resumo do fim;
  - a pergunta antiga, um `askretrycancel` por arquivo no meio da etapa, saiu.

A janela de verdade é conferida abrindo o app (sob Xvfb no contêiner).
"""
from __future__ import annotations

import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TELA = RAIZ / "sigft" / "app" / "views" / "pmib_manager.py"


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
    classe = _classe(_arvore(), "ModuloPMIBManager")
    bases = [ast.unparse(b) for b in classe.bases]
    assert bases[0] == "DialogosDeEspera", bases  # antes do CTkFrame: o __init__ passa por ele


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

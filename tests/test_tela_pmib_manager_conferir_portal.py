r"""O botão CONFERIR NO PORTAL do Gestão PMIB (2026-10-14).

O guarda é por AST, como o de tests/test_tela_pmib_manager.py, sobre a tela Qt
(a interface antiga saiu em 2026-10-15). O que ele prova é a ordem que evita os
defeitos caros:

  - o navegador abre, o portal carrega e a tela PAUSA para o login ANTES de a
    conferência começar -- sem a pausa, o robô pesquisaria numa tela de login;
  - o navegador fecha no `finally`, dê certo ou errado;
  - o botão novo trava junto com os outros enquanto algo roda.

A pergunta dos arquivos travados (`callback_travados`) é conferida pelo guarda
de test_tela_pmib_manager.py, que cobre toda chamada a `executar`.
"""
from __future__ import annotations

import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TELA = RAIZ / "sigft" / "app_qt" / "views" / "pmib_manager.py"


def _metodo(nome):
    arvore = ast.parse(TELA.read_text(encoding="utf-8"))
    classe = next(no for no in ast.walk(arvore) if isinstance(no, ast.ClassDef) and no.name == "ModuloPMIBManager")
    return next(no for no in classe.body if isinstance(no, ast.FunctionDef) and no.name == nome)


def _chamadas_em_ordem(no):
    chamadas = [c for c in ast.walk(no) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)]
    return [c.func.attr for c in sorted(chamadas, key=lambda c: (c.lineno, c.col_offset))]


def test_conferir_abre_o_portal_e_pausa_para_o_login_antes_de_conferir():
    ordem = _chamadas_em_ordem(_metodo("_worker_conferir_portal"))

    passos = ["iniciar_navegador", "abrir_portal", "pausar_e_esperar", "executar"]
    posicoes = [ordem.index(passo) for passo in passos]
    assert posicoes == sorted(posicoes), ordem


def test_o_navegador_da_conferencia_fecha_no_finally():
    worker = _metodo("_worker_conferir_portal")
    blocos = [no for no in ast.walk(worker) if isinstance(no, ast.Try) and no.finalbody]

    assert any("fechar_navegador" in _chamadas_em_ordem(ast.Module(body=b.finalbody, type_ignores=[]))
               for b in blocos)


def test_o_botao_conferir_trava_junto_com_os_outros():
    metodo = _metodo("_travar_botoes")
    botoes = next(no for no in ast.walk(metodo) if isinstance(no, ast.For)).iter

    assert "self.btn_conferir" in ast.unparse(botoes)
    assert "setEnabled" in ast.unparse(metodo)

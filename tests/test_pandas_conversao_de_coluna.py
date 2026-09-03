# -*- coding: utf-8 -*-
"""`.loc[:, coluna] = ` não serve para CONVERTER o tipo de uma coluna.

Defeito real (2026-09-03), que derrubou o PMIB Manager na máquina do usuário
com a mensagem::

    Invalid value '<DatetimeArray> ['NaT', 'NaT', ...]
    Length: 15, dtype: datetime64[s]' for dtype 'str'

A linha culpada era::

    df.loc[:, 'DATA INFORME'] = pd.to_datetime(df['DATA INFORME'], errors='coerce')

A diferença que importa:

* ``df.loc[:, col] = valores`` escreve DENTRO da coluna que já existe e
  **preserva o dtype dela**;
* ``df[col] = valores`` **substitui** a coluna, dtype novo junto.

A coluna vinha de ``read_excel(..., na_filter=False)``, então célula vazia
virou ``''`` e o dtype era ``str``. Até a pandas 2 encaixar datas ali dava
uma conversão silenciosa para ``object``; na **pandas 3** virou ``TypeError``.
Ou seja: o mesmo código roda na minha máquina e morre na do usuário, conforme
a versão da pandas. É o tipo de defeito que não aparece em teste nenhum e
aparece em produção.

Por que este teste é ESTRUTURAL e não funcional: a suíte stuba a pandas
(`tests/conftest.py`), então um teste que montasse um DataFrame de verdade
receberia o dublê e não provaria nada. Olhar o código-fonte prova.
"""
import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Funções que MUDAM o dtype. São elas que não podem entrar por `.loc`.
CONVERSORAS = {"to_datetime", "to_numeric", "to_timedelta"}


def _arquivos_python():
    return sorted((RAIZ / "sigft").rglob("*.py"))


def _nome_da_funcao(no):
    if isinstance(no, ast.Attribute):
        return no.attr
    if isinstance(no, ast.Name):
        return no.id
    return None


def _eh_alvo_loc_de_coluna(alvo):
    """`df.loc[:, 'X']` — fatia de linhas inteira com uma coluna nomeada."""
    if not isinstance(alvo, ast.Subscript):
        return False
    if not (isinstance(alvo.value, ast.Attribute) and alvo.value.attr == "loc"):
        return False
    indice = alvo.slice
    if not (isinstance(indice, ast.Tuple) and len(indice.elts) == 2):
        return False
    linhas = indice.elts[0]
    return isinstance(linhas, ast.Slice) and linhas.lower is None and linhas.upper is None


@pytest.mark.parametrize("caminho", _arquivos_python(), ids=lambda p: p.name)
def test_conversao_de_dtype_nao_passa_por_loc(caminho):
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    infracoes = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        if not isinstance(no.value, ast.Call):
            continue
        if _nome_da_funcao(no.value.func) not in CONVERSORAS:
            continue
        for alvo in no.targets:
            if _eh_alvo_loc_de_coluna(alvo):
                infracoes.append(
                    f"linha {no.lineno}: use `df['coluna'] = ...` no lugar de `df.loc[:, 'coluna'] = ...`"
                )

    assert not infracoes, (
        f"{caminho.name} converte o tipo de uma coluna por `.loc`, que PRESERVA o dtype antigo "
        f"e estoura TypeError na pandas 3:\n  " + "\n  ".join(infracoes)
    )

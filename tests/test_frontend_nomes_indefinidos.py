r"""A rede que faltava para `frontend.py`.

⚠️ ESTE ARQUIVO EXISTE POR CAUSA DE UM ERRO CONCRETO, em 2026-08-25. O CP 5.5
removeu de `ModuloCopiaFichas` um frame (`f_novo`) que segurava o botão do robô
antigo -- e deixou para trás um `CTkSwitch` que ainda era filho dele. O
aplicativo passou a morrer na abertura:

    NameError: name 'f_novo' is not defined

E nada pegou. `compileall` compila para bytecode e nunca executa o módulo, então
`NameError` passa batido. A suíte não importa `frontend.py` (ele abre janela
real). O resultado foi 2625 testes verdes com o app quebrado -- a mesma classe
de falsa segurança que este projeto já pagou caro no RPA.

`pyflakes` fecha o buraco porque analisa a ÁRVORE SINTÁTICA sem executar nada:
ele enxerga que `f_novo` não está definido naquele escopo. É a única checagem
que consegue olhar `frontend.py` de verdade neste ambiente.

O teste falha em nome indefinido NOVO, não no total de avisos: `pyflakes` também
reclama de import não usado e coisas do gênero, e transformar isso em erro
travaria o trabalho normal por ruído. Nome indefinido é diferente -- é sempre um
`NameError` esperando a linha ser executada.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = RAIZ / "frontend.py"

# ⚠️ DÍVIDA CONHECIDA, e não desculpa. Este é anterior à refatoração: um
# `except Exception as e:` cujo `e` é usado dentro de um `lambda` passado ao
# `after()` do tkinter. O Python apaga o nome ao sair do `except`, então o
# lambda dispara depois com o nome já morto -- só quebra quando aquele erro
# acontece, que é justamente quando o usuário mais precisa da mensagem.
#
# Fica na lista para o teste poder proteger o RESTO do arquivo hoje, em vez de
# esperar alguém arrumar coragem para mexer num módulo de 5,5 mil linhas.
# Quando for corrigido, tire daqui -- o teste avisa se a lista tiver linha
# sobrando.
INDEFINIDOS_CONHECIDOS = {"e"}


def _pyflakes(caminho: pathlib.Path) -> list[str]:
    resultado = subprocess.run(
        [sys.executable, "-m", "pyflakes", str(caminho)],
        capture_output=True, text=True,
    )
    return [linha for linha in resultado.stdout.splitlines() if linha.strip()]


def _indefinidos(linhas: list[str]) -> set[str]:
    """Os NOMES indefinidos que o pyflakes achou.

    Formato da saída: `caminho:linha:coluna undefined name 'x'`.

    Só o nome entra. O número da linha fica de fora de propósito -- ele muda a
    cada edição do arquivo, e uma lista de conhecidos que precisa ser
    reajustada a cada commit é uma lista que alguém desliga na terceira vez. O
    caminho também: no Windows ele começa com `C:`, e a primeira versão deste
    parser cortava em `:` e ficava com a letra do drive como "nome do arquivo"
    -- os dois testes falharam no arquivo LIMPO até isso aparecer.
    """
    achados = set()
    for linha in linhas:
        if "undefined name" not in linha:
            continue
        achados.add(linha.split("undefined name", 1)[1].strip().strip("'\""))
    return achados


@pytest.fixture(scope="module")
def saida_do_pyflakes():
    pytest.importorskip("pyflakes", reason="pyflakes e dev-only; ver requirements-dev.txt")
    assert FRONTEND.exists(), FRONTEND
    return _pyflakes(FRONTEND)


def test_frontend_nao_tem_nome_indefinido_novo(saida_do_pyflakes):
    """Um `NameError` em `frontend.py` só aparece quando a tela é construída --
    ou seja, na cara do usuário, e derrubando o aplicativo inteiro na abertura.
    """
    novos = _indefinidos(saida_do_pyflakes) - INDEFINIDOS_CONHECIDOS
    assert novos == set(), (
        f"nome(s) indefinido(s) em frontend.py: {sorted(novos)}. "
        f"Isso vira NameError quando a linha rodar -- normalmente na abertura "
        f"do app. Rode: python -m pyflakes frontend.py"
    )


def test_a_lista_de_conhecidos_nao_tem_linha_sobrando(saida_do_pyflakes):
    """Conhecido que já foi corrigido tem de sair da lista.

    Sem isto a lista só cresce, e uma lista que só cresce deixa de ser dívida
    registrada para virar dívida escondida.
    """
    ainda_existem = _indefinidos(saida_do_pyflakes)
    sobrando = INDEFINIDOS_CONHECIDOS - ainda_existem
    assert sobrando == set(), (
        f"{sorted(sobrando)} não aparece(m) mais no pyflakes -- foi corrigido. "
        f"Tire de INDEFINIDOS_CONHECIDOS."
    )

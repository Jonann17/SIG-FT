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

# [CP 7.3] Esta rede nasceu para o `frontend.py`, quando as 12 telas moravam
# lá. Agora o `frontend.py` é um shim de 90 linhas e a UI vive em
# `sigft/app/` -- se o guard continuasse olhando só o shim, ele passaria a
# vigiar o arquivo onde já não há risco nenhum, e largaria justamente os
# arquivos que são editados. Foi o que aconteceu de fato: o `undefined name
# 'e'` sumiu do frontend porque mudou de casa junto com a tela dona dele.
ARQUIVOS_VIGIADOS = [RAIZ / "frontend.py"] + sorted(
    (RAIZ / "sigft" / "app").rglob("*.py")
)

# ⚠️ DÍVIDA CONHECIDA, e não desculpa. Este é anterior à refatoração: um
# `except Exception as e:` cujo `e` é usado dentro de um `lambda` passado ao
# `after()` do tkinter. O Python apaga o nome ao sair do `except`, então o
# lambda dispara depois com o nome já morto -- só quebra quando aquele erro
# acontece, que é justamente quando o usuário mais precisa da mensagem.
#
# Fica na lista para o teste poder proteger o RESTO do código hoje. O motivo
# original ("ninguém quer mexer num módulo de 5,5 mil linhas") caducou com o
# CP 7.3: ele mora agora em `sigft/app/views/pmib_manager.py`, um arquivo de
# ~250 linhas. Continua registrado em PENDENCIAS, e corrigi-lo deixou de ser
# assustador. Quando for corrigido, tire daqui -- o teste avisa se a lista
# tiver linha sobrando.
INDEFINIDOS_CONHECIDOS = {"e"}


def _pyflakes(*caminhos: pathlib.Path) -> list[str]:
    resultado = subprocess.run(
        [sys.executable, "-m", "pyflakes", *(str(c) for c in caminhos)],
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
    assert ARQUIVOS_VIGIADOS, "nenhum arquivo para vigiar -- caminho errado?"
    for caminho in ARQUIVOS_VIGIADOS:
        assert caminho.exists(), caminho
    return _pyflakes(*ARQUIVOS_VIGIADOS)


def test_frontend_nao_tem_nome_indefinido_novo(saida_do_pyflakes):
    """Um `NameError` na UI só aparece quando a tela é construída -- ou seja,
    na cara do usuário, e derrubando o aplicativo inteiro na abertura.

    [CP 7.3] Vigia `frontend.py` E toda a árvore `sigft/app/`.
    """
    novos = _indefinidos(saida_do_pyflakes) - INDEFINIDOS_CONHECIDOS
    assert novos == set(), (
        f"nome(s) indefinido(s) na UI: {sorted(novos)}. "
        f"Isso vira NameError quando a linha rodar -- normalmente na abertura "
        f"do app. Rode: python -m pyflakes frontend.py sigft/app/**/*.py"
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

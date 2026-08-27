"""O tema novo e o `COLORS` do `frontend.py` não podem divergir — CP 7.1.

Enquanto a Fase 7 não termina, a paleta existe em DOIS lugares: o dict
`COLORS` do `frontend.py` (que as 10 telas ainda não migradas usam) e o
`sigft/app/theme.py` (que as migradas usam). Duas fontes para o mesmo dado é
exatamente o problema que a refatoração combate — aqui ela é temporária e
deliberada, mas só é segura ENQUANTO as duas concordarem.

Este teste é o que garante isso. Se alguém mexer numa cor de um lado só, a
tela migrada e a não-migrada passam a ter aparências diferentes — e num app
de 12 telas ninguém percebe isso olhando.

Quando o CP 7.3 terminar e o `COLORS` do `frontend.py` sumir, este arquivo
perde o motivo de existir e deve ser apagado junto.

Leitura por AST: `frontend.py` NÃO pode ser importado neste ambiente (importa
customtkinter/tkinter e o bloco `__main__` abre uma janela real) — é a mesma
razão pela qual ele fica fora do smoke de importação do CP 0.2. `ast.parse`
lê sem executar nada.
"""
from __future__ import annotations

import ast
import os

import pytest

from sigft.app import theme

CAMINHO_FRONTEND = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend.py")


def _colors_do_frontend() -> dict[str, str]:
    """Extrai o dict `COLORS` de `frontend.py` sem importar o módulo."""
    with open(CAMINHO_FRONTEND, encoding="utf-8") as arquivo:
        arvore = ast.parse(arquivo.read())

    for no in arvore.body:
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            if isinstance(alvo, ast.Name) and alvo.id == "COLORS":
                return ast.literal_eval(no.value)

    raise AssertionError("dict COLORS não encontrado no frontend.py")


def test_frontend_ainda_tem_o_dict_colors():
    """Sentinela: quando isto falhar, o CP 7.3 terminou e o arquivo sai."""
    assert _colors_do_frontend()


def test_as_duas_paletas_tem_exatamente_as_mesmas_chaves():
    assert set(_colors_do_frontend()) == set(theme.COLORS)


@pytest.mark.parametrize("chave", sorted(theme.COLORS))
def test_cada_cor_tem_o_mesmo_valor_nos_dois_lugares(chave):
    do_frontend = _colors_do_frontend()
    assert theme.COLORS[chave] == do_frontend[chave], (
        f"A cor '{chave}' divergiu: frontend.py diz {do_frontend[chave]}, "
        f"sigft/app/theme.py diz {theme.COLORS[chave]}. "
        "Mudou de propósito? Mude nos DOIS até o CP 7.3 aposentar o COLORS."
    )


def test_a_ordem_das_chaves_tambem_e_a_mesma():
    # Não muda pixel nenhum, mas mantém o diff legível quando alguém comparar
    # os dois arquivos lado a lado -- que é o que se faz ao migrar uma tela.
    assert list(_colors_do_frontend()) == list(theme.COLORS)

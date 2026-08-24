r"""
O recorte do HTML capturado (`scripts/auditar_seletores.py --capturar`).

Contexto (2026-08-18). O usuário perguntou se dava para trocar o "copiar caixa
por caixa no inspecionar elemento" por alguma ferramenta. Dava, e quase toda
ela já existia: `auditar_seletores.py` abre o portal com o perfil persistente
(login valendo) e é somente-leitura. Faltava só despejar o `outerHTML`.

O que dá para testar aqui é a parte PURA -- o recorte. O resto exige navegador
e portal, e é justamente o que a sessão real cobre.

⚠️ O recorte precisa AVISAR. Um corte silencioso faria o leitor concluir que o
elemento acaba ali e procurar, do lado do código, o resto de um markup que
estava só truncado -- exatamente o tipo de erro que este projeto já pagou caro
(ver a armadilha do contador de anexos, §8.2 dos seletores).
"""
import importlib.util
import pathlib

import pytest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "auditar_seletores.py"


@pytest.fixture(scope="module")
def aud():
    spec = importlib.util.spec_from_file_location("auditar_seletores", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_html_menor_que_o_limite_sai_inteiro(aud):
    assert aud.recortar_html("<div>oi</div>", 100) == "<div>oi</div>"


def test_html_no_limite_exato_nao_e_recortado(aud):
    texto = "x" * 50
    assert aud.recortar_html(texto, 50) == texto


def test_html_maior_que_o_limite_e_cortado_E_AVISA(aud):
    saida = aud.recortar_html("x" * 500, 100)

    assert saida.startswith("x" * 100)
    assert "RECORTADO" in saida, "corte silencioso engana quem lê"


def test_o_aviso_diz_QUANTO_faltou(aud):
    """"Faltou alguma coisa" não ajuda; "faltam 400" diz se vale aumentar o
    limite ou se o XPath está pegando a página inteira."""
    saida = aud.recortar_html("x" * 500, 100)

    assert "faltam 400" in saida


def test_limite_desligado_devolve_tudo(aud):
    for desligado in (0, None, -1):
        assert aud.recortar_html("x" * 500, desligado) == "x" * 500


def test_entrada_vazia_ou_None_nao_levanta(aud):
    assert aud.recortar_html(None) == ""
    assert aud.recortar_html("") == ""


def test_a_captura_e_somente_leitura(aud):
    """O script pode rodar numa ficha real. Se um dia alguém acrescentar
    `click`/`fill` aqui, esta promessa (escrita na docstring e no .bat) deixa
    de valer sem ninguém perceber."""
    fonte = SCRIPT.read_text(encoding="utf-8")

    for proibido in (".click(", ".fill(", "safe_click", "safe_fill", "press("):
        assert proibido not in fonte, f"o script deixou de ser somente-leitura: {proibido}"

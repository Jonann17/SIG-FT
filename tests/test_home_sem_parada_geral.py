r"""O botão "Interromper tudo" saiu da home a pedido do usuário (2026-09-24).

Ele tinha entrado em 2026-09-23, também a pedido. Depois o usuário pediu a
remoção em outra sessão, e o botão ficou: este teste existe para que ele não
volte sem alguém decidir de novo.

Saiu o recurso inteiro, e não só o botão: o `parar_tudo` do app, o
`sigft/app/parada.py` e o `interromper_tudo()` das telas só existiam para ele.
Sem o botão, sobraria código que ninguém chama. O "Parar" de cada tela
continua onde sempre esteve.

[2026-10-15] A interface é a Qt (a antiga saiu do SIG-FT): o guarda olha
`sigft/app_qt/`.
"""
from __future__ import annotations

import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1]
APP = RAIZ / "sigft" / "app_qt"


def _fonte(caminho):
    return caminho.read_text(encoding="utf-8")


def test_a_home_nao_tem_o_botao_de_parada_geral():
    fonte = _fonte(APP / "views" / "home.py")

    assert "Interromper tudo" not in fonte
    assert "parar_tudo" not in fonte


def test_o_app_nao_tem_mais_a_parada_geral():
    assert "parar_tudo" not in _fonte(APP / "main.py")
    assert "parada" not in _fonte(APP / "main.py").split("class ")[0]
    assert not (APP / "parada.py").exists()

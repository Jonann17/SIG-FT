"""Toda tela cabe num notebook 1366x768 (2026-10-31).

Maximizada num 1366x768, a janela tem uns 690 px de altura útil: 768 menos a
barra de tarefas do Windows 11 (48) e a barra de título (~30). Upload
Condições, Upload Specs e Correção de PDM pediam 728-733 px (PENDENCIAS,
2026-10-28) e a janela passava da tela: o console, com altura fixa de 150 px,
ficava cortado embaixo. Agora o console cede até o mínimo do puxador em janela
baixa (`ModuleFrame`). Este teste mede o mínimo que a JANELA pede em cada tela e
cada aba, com o "Como funciona" fechado (como ela abre), na letra normal e na
grande.
"""
from __future__ import annotations

import pytest

from sigft.app_qt import catalogo, letra

# Altura útil de um 1366x768 maximizado (ver o cabeçalho) e a largura da tela.
ALTURA_UTIL_1366 = 690
LARGURA_1366 = 1366


@pytest.fixture
def letra_temporaria(qt_interface, tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "user_prefs.json")
    yield qt_interface
    letra.aplicar(qt_interface, "normal", gravar=False)


def _minimos(janela, qtbot) -> dict[str, tuple[int, int]]:
    """`{tela ou tela/aba: (largura, altura)}` mínimas da janela inteira."""
    from sigft.app_qt.widgets.abas import Abas

    medidas = {}
    modulos = [m[0] for m in catalogo.MODULOS if m[0] not in catalogo.TELAS_BLOQUEADAS]
    for alvo in modulos:
        janela.show_frame(alvo)
        qtbot.wait(20)
        tela = janela.telas[alvo]
        dica = tela.minimumSizeHint()
        medidas[alvo] = (dica.width(), dica.height())
        for abas in tela.findChildren(Abas):
            antes = abas.get()
            for nome in abas.abas:
                abas.set(nome)
                qtbot.wait(10)
                dica = tela.minimumSizeHint()
                medidas[f"{alvo}/{nome}"] = (dica.width(), dica.height())
            abas.set(antes)
    # A janela soma o menu lateral e a pilha, que pede o maior mínimo das telas.
    dica = janela.minimumSizeHint()
    medidas["(janela)"] = (dica.width(), dica.height())
    return medidas


@pytest.mark.parametrize("tamanho", ["normal", "grande"])
def test_toda_tela_cabe_num_notebook_1366x768(letra_temporaria, qtbot, tmp_path, monkeypatch, tamanho):
    from sigft.app_qt import main as qmain

    monkeypatch.delenv("SIGFT_SEM_COMO_FUNCIONA", raising=False)   # com o bloco, como no app
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    letra.aplicar(letra_temporaria, tamanho, gravar=False)
    janela = qmain.SIG_FT_App()
    janela.fechar_sem_perguntar = True
    qtbot.addWidget(janela)
    janela.resize(LARGURA_1366, ALTURA_UTIL_1366)
    janela.show()
    qtbot.waitExposed(janela)

    medidas = _minimos(janela, qtbot)

    altas = {alvo: a for alvo, (_, a) in medidas.items() if a > ALTURA_UTIL_1366}
    largas = {alvo: l for alvo, (l, _) in medidas.items() if l > LARGURA_1366}
    assert altas == {} and largas == {}

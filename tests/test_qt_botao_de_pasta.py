"""O botão "Abrir Pasta" numa célula de tabela (`dialogos_selecao.botao_de_pasta`), usado na
Conferência de Revisões e na Revisão no AMP (pedido do Luan, 2026-11-04): ir direto à pasta da
lista para ver o HTML e os outros arquivos."""
from __future__ import annotations

from pathlib import Path

from sigft.app_qt.widgets import dialogos_selecao


def test_o_botao_abre_a_pasta_da_linha(qt_interface, qtbot):
    tabela = dialogos_selecao.tabela_ttk([("Código", 100, "w"), ("Pasta", 90, "w")])
    qtbot.addWidget(tabela)
    item = dialogos_selecao.linha_ttk(tabela, ("#A", ""))
    abertas = []
    botao = dialogos_selecao.botao_de_pasta(tabela, item, 1, Path("/x/lista"), abertas.append)
    assert tabela.itemWidget(item, 1) is botao and botao.text() == "Abrir Pasta"
    botao.click()
    assert abertas == [Path("/x/lista")]


def test_sem_pasta_nao_ha_botao(qt_interface, qtbot):
    tabela = dialogos_selecao.tabela_ttk([("Código", 100, "w"), ("Pasta", 90, "w")])
    qtbot.addWidget(tabela)
    item = dialogos_selecao.linha_ttk(tabela, ("#A", ""))
    assert dialogos_selecao.botao_de_pasta(tabela, item, 1, None, print) is None
    assert tabela.itemWidget(item, 1) is None

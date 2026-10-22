"""Cada parte convertida da interface, montada em espanhol e em inglês (2026-10-22).

`ainda_em_portugues` (tests/_idioma.py) acusa o texto à vista que tem, no
catálogo, uma tradução diferente dele mesmo: a constante marcada (`marcar`) que
chegou à tela sem `t()`, que a guarda estática não vê. Cada tarefa do plano
`docs/superpowers/plans/2026-10-22-configuracao-e-idioma.md` acrescenta as suas.
"""
import threading

import pytest

from _idioma import ainda_em_portugues, em_idioma

IDIOMAS = ["es", "en"]


def _sem_conteudo(_pai):
    pass


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_pecas_compartilhadas(qt_interface, qtbot, codigo):
    from sigft.app_qt.widgets import atividade, console, dialogos_selecao, dialogs, painel_janela, pickers
    from sigft.app_qt.widgets import resumo_lote as janela_resumo

    with em_idioma(codigo):
        pecas = [
            console.ConsoleFrame(),
            janela_resumo.JanelaResumoDoLote(None, "Upload duplicadas", [
                ("4500063671.0001: [Erro] ficha não encontrada", "erro"),
                ("[Aviso] tabela vazia", "aviso")]),
            dialogs.PausaLoginDialog(None, mensagem="x", evento_espera=threading.Event()),
            dialogs.RetryLockDialog(None, evento_espera=threading.Event(), resultado={}),
            dialogos_selecao.SelecaoMultiplaDialog(None, itens=["A", "B"], com_selecionar_todos=True),
            pickers.FileQueueList(chave="t.fila"),
            atividade.FaixaDeAtividade(),
            painel_janela.JanelaPainel(None, titulo="x", montar=_sem_conteudo),
        ]
        for peca in pecas:
            qtbot.addWidget(peca)
            assert ainda_em_portugues(peca, codigo) == set(), type(peca).__name__


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_frases_do_resumo_e_dicas_no_idioma(codigo):
    from sigft.app import idioma, resumo_lote, textos_dicas

    with em_idioma(codigo):
        traducoes = idioma.catalogo(codigo)
        erros, juncao, aviso = idioma.t("{n} erros", n=2), idioma.t(" e "), idioma.t("{n} aviso", n=1)
        assert resumo_lote.frase_da_contagem(2, 1) == erros + juncao + aviso
        assert resumo_lote.frase_da_contagem(2, 1) != "2 erros e 1 aviso"
        dicas = textos_dicas.dicas_da_classe(type("ModuloCopiaFichas", (), {}))
        assert "{portal}" not in dicas["btn_robo_novo"]
        assert traducoes[textos_dicas.PORTAL] in dicas["btn_robo_novo"]

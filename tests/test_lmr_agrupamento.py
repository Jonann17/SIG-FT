r"""
Agrupamento por CÓDIGO LMR — a regra que o usuário fixou em 2026-08-21.

> *"Se o código LMR for X na linha 1 e na linha 2 Y e na linha 3 X, ele tem que
> identificar que são 1 código e 2 tags distintas, contando 2 quantidades
> instaladas no código X."*
>
> *"Se aparece com a mesma tag não tem problema, são 2 distintos. Quem manda é
> o código: o código LMR repetido significa que está em determinado lugar, e
> daí a quantidade de TAG (independentemente distinta ou não) determina a
> quantidade instalada naquele código LMR."*

A versão anterior juntava só TAGs CONSECUTIVAS, ou seja, exigia a planilha
ordenada por código -- e não avisava nada quando não estava.
"""
from sigft.services.lmr import agrupar_por_codigo


def test_codigo_espalhado_vira_UM_grupo():
    """O caso exato do usuário: X, Y, X."""
    grupos = agrupar_por_codigo([("X", "T1"), ("Y", "T2"), ("X", "T3")])

    assert grupos == [("X", ["T1", "T3"]), ("Y", ["T2"])]


def test_a_quantidade_e_o_numero_de_TAGS_do_codigo():
    grupos = dict(agrupar_por_codigo([("X", "T1"), ("Y", "T2"), ("X", "T3")]))

    assert len(grupos["X"]) == 2      # 2 instaladas no código X
    assert len(grupos["Y"]) == 1


def test_tag_REPETIDA_conta_de_novo():
    """"Se aparece com a mesma tag não tem problema, são 2 distintos." Trocar a
    lista por um `set` aqui perderia unidade instalada em silêncio -- e o
    portal receberia quantidade 1 onde são 2."""
    grupos = dict(agrupar_por_codigo([("X", "T1"), ("X", "T1")]))

    assert grupos["X"] == ["T1", "T1"]
    assert len(grupos["X"]) == 2


def test_a_ordem_de_saida_e_a_da_PRIMEIRA_aparicao():
    """Estável, para o log e a retomada por linha inicial fazerem sentido entre
    duas execuções da mesma planilha."""
    grupos = agrupar_por_codigo([("B", "1"), ("A", "2"), ("B", "3"), ("C", "4")])

    assert [codigo for codigo, _tags in grupos] == ["B", "A", "C"]


def test_espaco_em_volta_do_codigo_nao_cria_grupo_novo():
    """Planilha preenchida por gente tem espaço sobrando; dois grupos para o
    mesmo lugar mandariam duas quantidades ao portal, a segunda apagando a
    primeira."""
    grupos = agrupar_por_codigo([(" X ", "T1"), ("X", "T2")])

    assert grupos == [("X", ["T1", "T2"])]


def test_linha_sem_codigo_e_descartada():
    """Não há aplicação de LMR sem lugar onde ela está instalada; mandá-la ao
    portal escreveria num campo em branco."""
    grupos = agrupar_por_codigo([("", "T1"), (None, "T2"), ("  ", "T3"), ("X", "T4")])

    assert grupos == [("X", ["T4"])]


def test_tag_vazia_CONTA_como_unidade():
    """A quantidade é o número de LINHAS do código. Uma tag em branco é uma
    linha de planilha mal preenchida, não uma unidade a menos -- e descartá-la
    mudaria a quantidade sem ninguém pedir."""
    grupos = dict(agrupar_por_codigo([("X", "T1"), ("X", "")]))

    assert len(grupos["X"]) == 2


def test_planilha_vazia_nao_estoura():
    assert agrupar_por_codigo([]) == []

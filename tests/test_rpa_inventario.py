r"""
Inventário de seletores (`sigft.core.rpa.inventario`).

A pergunta que ele existe para responder: "o portal vai ser atualizado; o que
exatamente quebra?". Hoje não há resposta barata -- os seletores estão
espalhados por 7 módulos e a maioria nem é constante nomeada.

Estes testes travam o que a coleta promete, e um deles é deliberadamente um
TERMÔMETRO: se alguém nomear os seletores que hoje estão soltos, ele avisa que
o número mudou. Não é um teste que "quebra"; é o marcador de progresso de uma
dívida conhecida.
"""
from sigft.core.rpa import inventario


def test_coleta_encontra_seletores_dos_modulos_de_rpa():
    achados = inventario.coletar()

    assert achados
    modulos = {modulo for modulo, _n, _s, _r in achados}
    # Estes três são os que hoje têm seletor nomeado de verdade.
    assert "sigft.services.cria_fichas" in modulos
    assert "sigft.services.tech_specs" in modulos
    assert "sigft.services.lmr" in modulos


def test_todo_seletor_coletado_parece_um_xpath():
    for modulo, nome, seletor, _rel in inventario.coletar():
        assert seletor.strip().startswith(("//", "(", ".")), f"{modulo}.{nome} = {seletor!r}"


def test_constante_que_nao_e_seletor_nao_entra():
    # `XPATH_...` é o critério de nome, mas o VALOR também é conferido: uma
    # constante de texto qualquer chamada XPATH_ALGO não pode virar seletor.
    assert inventario._e_seletor("XPATH_BOTAO", '//button[@id="x"]')
    assert not inventario._e_seletor("PAUSA_FOCO", 1)
    assert not inventario._e_seletor("XPATH_ALGO", "não é xpath")
    assert not inventario._e_seletor("BOTAO_SALVAR", '//button')


def test_relativos_vem_marcados():
    """Os `XPATH_REL_*` são pedaços de seletor (o resto vem da linha da
    tabela). Conferir `//textarea[...]` sozinho contra a página casaria a
    textarea de QUALQUER linha e daria um "existe" que não prova nada."""
    achados = inventario.coletar()
    relativos = [(n, s) for _m, n, s, rel in achados if rel]

    assert relativos, "tech_specs tem XPATH_REL_*; a marcação sumiu?"
    for nome, _seletor in relativos:
        assert nome.startswith(inventario.PREFIXO_RELATIVO)


def test_a_ordem_e_estavel_para_o_diff_funcionar():
    # O uso previsto é rodar antes e depois da atualização do portal e
    # comparar com `diff`. Ordem instável tornaria o diff inútil.
    assert inventario.coletar() == sorted(inventario.coletar(), key=lambda l: (l[0], l[1]))


def test_modulo_que_nao_importa_nao_derruba_o_inventario():
    achados = inventario.coletar(
        ("sigft.services.cria_fichas", "sigft.modulo.que.nao.existe")
    )

    assert achados  # o módulo bom continua sendo coletado


def test_resumo_por_modulo_soma_o_total():
    achados = inventario.coletar()

    assert sum(inventario.resumo_por_modulo(achados).values()) == len(achados)


def test_duplicados_aponta_o_mesmo_seletor_em_dois_lugares():
    falsos = [
        ("mod.a", "XPATH_X", "//button[@id='b']", False),
        ("mod.b", "XPATH_Y", "//button[@id='b']", False),
        ("mod.c", "XPATH_Z", "//outro", False),
    ]

    repetidos = inventario.duplicados(falsos)

    assert list(repetidos) == ["//button[@id='b']"]
    assert repetidos["//button[@id='b']"] == ["mod.a.XPATH_X", "mod.b.XPATH_Y"]


# ---------------------------------------------------------------------------
# Termômetro da dívida
# ---------------------------------------------------------------------------
def test_quantos_seletores_ja_sao_alcancaveis_por_ferramenta():
    """Em 2026-08-11: 36 constantes nomeadas de ~176 seletores no projeto.

    `apagar_lmr` e `ficha_duplicada` contribuem ZERO -- têm tudo inline --, e
    `upload_conditions` entra com 2 de ~56. Enquanto for assim, nenhuma
    ferramenta de auditoria enxerga a maior parte do que quebraria numa
    atualização do portal.

    Este número deve SUBIR. Se ele cair, alguém desfez a nomeação de algum
    seletor -- e aí a auditoria passou a enxergar menos que antes.
    """
    assert len(inventario.coletar()) >= 36

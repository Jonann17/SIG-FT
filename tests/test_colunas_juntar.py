"""Colunas lembradas (2026-10-26): a regra de juntar a preferência com as colunas
de agora (função pura, sem tabela nenhuma) e a seção `colunas` do `prefs`."""
from sigft.app_qt.widgets.colunas import Coluna, descrever, juntar
from sigft.core import prefs

COLUNAS = ("descricao", "original", "alvo")


def test_nada_guardado_vale_o_padrao():
    assert juntar(None, COLUNAS) is None


def test_preferencia_estragada_vale_o_padrao():
    assert juntar("lixo", COLUNAS) is None
    assert juntar({"chave": "alvo"}, COLUNAS) is None
    assert juntar([1, "x", {"chave": 3}, {"sem": "chave"}], COLUNAS) is None


def test_ordem_largura_e_visibilidade_voltam():
    guardado = [{"chave": "alvo", "largura": 90, "visivel": True},
                {"chave": "descricao", "largura": 300, "visivel": False},
                {"chave": "original", "largura": 120, "visivel": True}]
    assert juntar(guardado, COLUNAS) == [Coluna("alvo", 90, True), Coluna("descricao", 300, False),
                                         Coluna("original", 120, True)]


def test_coluna_que_sumiu_e_ignorada_e_a_nova_entra_no_fim_visivel():
    guardado = [{"chave": "velha", "largura": 50, "visivel": True},
                {"chave": "alvo", "largura": 90, "visivel": False}]
    assert juntar(guardado, COLUNAS) == [Coluna("alvo", 90, False), Coluna("descricao", None, True),
                                         Coluna("original", None, True)]


def test_repetida_e_largura_invalida():
    guardado = [{"chave": "alvo", "largura": -5}, {"chave": "alvo", "largura": 80},
                {"chave": "descricao", "largura": True, "visivel": "sim"},
                {"chave": "original", "largura": "120"}]
    assert juntar(guardado, COLUNAS) == [Coluna("alvo", None, True), Coluna("descricao", None, True),
                                         Coluna("original", None, True)]


def test_todas_escondidas_a_primeira_volta_a_aparecer():
    guardado = [{"chave": c, "largura": 100, "visivel": False} for c in COLUNAS]
    assert [c.visivel for c in juntar(guardado, COLUNAS)] == [True, False, False]


def test_descrever_e_o_que_juntar_le():
    lista = [Coluna("alvo", 90, True), Coluna("descricao", None, False), Coluna("original", 120, True)]
    assert juntar(descrever(lista), COLUNAS) == lista


def test_prefs_guarda_por_tabela_e_apaga_com_none(tmp_path):
    arquivo = tmp_path / "prefs.json"
    assert prefs.ler_colunas("selecao", config_path=arquivo) is None
    prefs.gravar_colunas("selecao", [{"chave": "a", "largura": 10, "visivel": True}], config_path=arquivo)
    prefs.gravar_colunas("resumo", [{"chave": "b", "largura": None, "visivel": False}], config_path=arquivo)
    prefs.set_opcao("outra", True, config_path=arquivo)   # a seção sobrevive a outra gravação
    assert prefs.ler_colunas("selecao", config_path=arquivo) == [{"chave": "a", "largura": 10, "visivel": True}]
    prefs.gravar_colunas("selecao", None, config_path=arquivo)
    assert prefs.ler_colunas("selecao", config_path=arquivo) is None
    assert prefs.ler_colunas("resumo", config_path=arquivo) == [{"chave": "b", "largura": None, "visivel": False}]

r"""
Leitura da planilha de LMR (`lmr._mapear_colunas_lmr` / `lmr.localizar_aba_lmr`).

Pedido do usuário em 2026-08-11: cabeçalhos que digam o que a coluna é
("FICHA PMIB", "CÓDIGO LMR", "TAG LMR" no lugar de "PMIB", "Código_PMIB",
"TAG_PMIB" — que confundiam código de ficha com código de LMR), e a aba
ESCOLHIDA por um seletor na tela -- não adivinhada (a 1ª versão varria as abas
atrás das colunas, e o usuário recusou).

O ponto delicado, e o que estes testes seguram: os nomes NOVOS passam a ser os
preferidos **sem quebrar as planilhas já em uso** com os antigos. Renomear
cabeçalho de um arquivo que alguém está usando no meio de um lote é pior do
que não renomear.

`pandas` é stub nesta suíte (tests/conftest.py), então o que se testa aqui é a
REGRA: `_mapear_colunas_lmr` é função pura sobre uma lista de nomes de coluna,
e `listar_abas`/`carregar_dados_excel` recebem o pandas injetado. Nenhum .xlsx é escrito
-- o que também deixa o teste instantâneo.
"""
import pytest

from sigft import config
from sigft.services import lmr

_NOVOS = ["FICHA PMIB", "CÓDIGO LMR", "TAG LMR"]
_ANTIGOS = ["PMIB", "Código_PMIB", "TAG_PMIB"]


# ===========================================================================
# A regra de casamento de coluna
# ===========================================================================
def test_cabecalho_novo_e_reconhecido():
    assert lmr._mapear_colunas_lmr(_NOVOS) == {
        "pmib": "FICHA PMIB", "codigo": "CÓDIGO LMR", "tag": "TAG LMR",
    }


def test_cabecalho_antigo_continua_funcionando():
    """As planilhas em uso hoje têm o cabeçalho velho. Quebrar uma delas para
    estrear um nome melhor seria o pior negócio possível."""
    mapa = lmr._mapear_colunas_lmr(_ANTIGOS)

    assert mapa == {"pmib": "PMIB", "codigo": "Código_PMIB", "tag": "TAG_PMIB"}


def test_cabecalho_misturado_funciona():
    # Planilha meio migrada é o estado mais provável durante a transição.
    assert lmr._mapear_colunas_lmr(["FICHA PMIB", "Código_PMIB", "TAG LMR"]) is not None


@pytest.mark.parametrize("grafia", ["tag lmr", "TAG LMR ", " Tag Lmr", "TAG lmr"])
def test_caixa_acento_e_espaco_nao_reprovam(grafia):
    # Planilha preenchida à mão traz as três grafias com igual frequência.
    assert lmr._mapear_colunas_lmr(["ficha pmib", "codigo lmr", grafia]) is not None


def test_acento_ausente_no_codigo_e_aceito():
    assert lmr._mapear_colunas_lmr(["FICHA PMIB", "CODIGO LMR", "TAG LMR"]) is not None


def test_coluna_faltando_devolve_none():
    assert lmr._mapear_colunas_lmr(["FICHA PMIB", "CÓDIGO LMR"]) is None


def test_colunas_extras_nao_atrapalham():
    mapa = lmr._mapear_colunas_lmr(["Obs", *_NOVOS, "Responsável"])

    assert mapa is not None and mapa["tag"] == "TAG LMR"


def test_o_nome_novo_vence_quando_os_dois_estao_na_mesma_aba():
    """Planilha migrada pela metade pode ter as duas colunas. A preferência
    declarada em `config.LMR_COLUNAS` é que decide -- não a ordem do arquivo."""
    mapa = lmr._mapear_colunas_lmr(["PMIB", "FICHA PMIB", "CÓDIGO LMR", "TAG LMR"])

    assert mapa["pmib"] == "FICHA PMIB"


# ===========================================================================
# A aba é ESCOLHIDA, não adivinhada
# ===========================================================================
# A 1ª versão disto varria as abas atrás das colunas. O usuário recusou, com
# razão: adivinhar aba funciona nove vezes e, na décima, cadastra o lote a
# partir da planilha errada sem ninguém notar. Agora `listar_abas` alimenta um
# seletor na tela e a aba escolhida é passada explicitamente.
class _PandasFalso:
    """Duplo mínimo: `ExcelFile(...).sheet_names` e `read_excel(...).columns`."""

    def __init__(self, abas):
        self._abas = abas
        self.lidas = []

    def ExcelFile(self, _caminho):
        return type("_X", (), {"sheet_names": list(self._abas)})()

    def read_excel(self, _caminho, sheet_name=None, nrows=None, **_kw):
        self.lidas.append(sheet_name)
        return type("_D", (), {"columns": list(self._abas[sheet_name])})()


def _com_pandas(monkeypatch, abas):
    falso = _PandasFalso(abas)
    monkeypatch.setattr(lmr, "pd", falso)
    return falso


def test_listar_abas_devolve_os_nomes_na_ordem_do_arquivo(monkeypatch):
    # É o que popula o seletor da tela; reordenar confundiria quem conhece a
    # própria planilha.
    _com_pandas(monkeypatch, {"Capa": ["X"], "LMR": _NOVOS, "Rascunho": []})

    assert lmr.listar_abas("x.xlsx") == ["Capa", "LMR", "Rascunho"]


def test_carregar_le_exatamente_a_aba_pedida(monkeypatch):
    """Nem a preferida, nem a primeira que serve: a que o usuário escolheu."""
    falso = _com_pandas(monkeypatch, {"LMR": _NOVOS, "Backup": _NOVOS})

    lmr.LMRAutomation().carregar_dados_excel("x.xlsx", "Backup")

    assert "Backup" in falso.lidas
    assert "LMR" not in falso.lidas


def test_sem_aba_escolhida_nao_adivinha_e_diz_quais_existem(monkeypatch):
    _com_pandas(monkeypatch, {"Capa": ["X"], "LMR": _NOVOS})

    ok, _df, _p, mensagem = lmr.LMRAutomation().carregar_dados_excel("x.xlsx", None)

    assert ok is False
    assert "Nenhuma aba escolhida" in mensagem
    assert "Capa" in mensagem and "LMR" in mensagem


def test_aba_escolhida_sem_as_colunas_manda_escolher_outra(monkeypatch):
    """Antes era um `KeyError` cru do pandas, que não diz o que fazer."""
    _com_pandas(monkeypatch, {"Capa": ["Título"]})

    ok, _df, _p, mensagem = lmr.LMRAutomation().carregar_dados_excel("x.xlsx", "Capa")

    assert ok is False
    assert "'Capa'" in mensagem
    assert "FICHA PMIB" in mensagem      # o que era esperado
    assert "outra aba" in mensagem       # e o que fazer


def test_nao_existe_mais_varredura_automatica_de_abas():
    """Marca da decisão: se alguém reintroduzir a adivinhação, este teste cai.

    O ganho de conveniência não paga o risco de cadastrar a partir da aba
    errada -- e o erro é silencioso, porque uma aba errada com as colunas
    certas carrega e processa normalmente.
    """
    assert not hasattr(lmr, "localizar_aba_lmr")


def test_config_declara_os_nomes_novos_como_preferidos():
    for papel, esperado in (("pmib", "FICHA PMIB"), ("codigo", "CÓDIGO LMR"), ("tag", "TAG LMR")):
        assert config.LMR_COLUNAS[papel][0] == esperado, (
            f"o nome novo tem de ser o PRIMEIRO de {papel} -- é ele que a UI e a "
            "documentação passam a ensinar"
        )


def test_a_lista_de_abas_conhecidas_serve_so_de_sugestao():
    """`LMR_ABAS` deixou de escolher aba: sobrou como sugestão de nome para a
    documentação e para o gerador de dados de teste. Se voltar a ser usada
    para SELECIONAR, o teste acima (`test_nao_existe_mais_varredura...`) cai
    junto."""
    assert config.LMR_ABAS[0] == "LMR"
    assert "GERAL" in config.LMR_ABAS

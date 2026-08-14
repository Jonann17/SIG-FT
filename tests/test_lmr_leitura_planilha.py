r"""
Leitura da planilha de LMR (`lmr._mapear_colunas_lmr` / `lmr.localizar_aba_lmr`).

Pedido do usuário em 2026-08-11: cabeçalhos que digam o que a coluna é
("FICHA PMIB", "CÓDIGO LMR", "TAG LMR" no lugar de "PMIB", "Código_PMIB",
"TAG_PMIB" — que confundiam código de ficha com código de LMR), nome de aba
livre e leitura automática.

O ponto delicado, e o que estes testes seguram: os nomes NOVOS passam a ser os
preferidos **sem quebrar as planilhas já em uso** com os antigos. Renomear
cabeçalho de um arquivo que alguém está usando no meio de um lote é pior do
que não renomear.

`pandas` é stub nesta suíte (tests/conftest.py), então o que se testa aqui é a
REGRA: `_mapear_colunas_lmr` é função pura sobre uma lista de nomes de coluna,
e `localizar_aba_lmr` recebe o pandas injetado. Nenhum arquivo .xlsx é escrito
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
# A escolha da aba
# ===========================================================================
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


def test_aba_com_nome_inesperado_e_encontrada_pelas_colunas(monkeypatch):
    # A "leitura automática": não ter de acertar o nome da aba.
    _com_pandas(monkeypatch, {"Planilha1": _NOVOS})

    abas, aba, mapa = lmr.localizar_aba_lmr("x.xlsx")

    assert (abas, aba) == (["Planilha1"], "Planilha1")
    assert mapa is not None


def test_a_aba_preferida_vence_outra_que_tambem_serve(monkeypatch):
    """Com duas abas válidas, a escolha não pode depender da ordem interna do
    arquivo -- vale a preferência de `config.LMR_ABAS`."""
    falso = _com_pandas(monkeypatch, {"Rascunho": _NOVOS, "LMR": _NOVOS})

    _abas, aba, _mapa = lmr.localizar_aba_lmr("x.xlsx")

    assert aba == "LMR"
    assert falso.lidas[0] == "LMR"  # nem chegou a olhar a outra


def test_aba_sem_as_colunas_e_pulada_e_a_seguinte_e_usada(monkeypatch):
    _com_pandas(monkeypatch, {"Capa": ["Título"], "Dados": _ANTIGOS})

    _abas, aba, mapa = lmr.localizar_aba_lmr("x.xlsx")

    assert aba == "Dados" and mapa is not None


def test_nenhuma_aba_serve_devolve_none_em_vez_de_estourar(monkeypatch):
    _com_pandas(monkeypatch, {"Capa": ["Título"], "Notas": ["A", "B"]})

    abas, aba, mapa = lmr.localizar_aba_lmr("x.xlsx")

    assert aba is None and mapa is None
    assert abas == ["Capa", "Notas"]  # devolve as abas para a mensagem de erro


def test_config_declara_os_nomes_novos_como_preferidos():
    for papel, esperado in (("pmib", "FICHA PMIB"), ("codigo", "CÓDIGO LMR"), ("tag", "TAG LMR")):
        assert config.LMR_COLUNAS[papel][0] == esperado, (
            f"o nome novo tem de ser o PRIMEIRO de {papel} -- é ele que a UI e a "
            "documentação passam a ensinar"
        )


def test_a_aba_LMR_e_a_primeira_preferida():
    assert config.LMR_ABAS[0] == "LMR"
    assert "GERAL" in config.LMR_ABAS  # a antiga continua na lista

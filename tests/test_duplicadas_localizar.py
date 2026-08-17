r"""
Identificação das fichas duplicadas no `_STATUS_PMIB` (CP 6.2).

É a primeira pergunta da Fase 6 -- "quais fichas são duplicadas, e o que a
planilha sabe sobre cada uma?" -- e tudo o que vem depois é construído em cima
dela. Se errar aqui, erra em cima, e o erro só apareceria com o navegador
aberto no meio de um lote.

`pandas` é stub nesta suíte, então a leitura é injetada. O que se testa é a
MONTAGEM: quais linhas viram ficha, o que entra em cada campo, e o que separa
uma ficha pronta de uma impedida.
"""
import pytest

from sigft import config
from sigft.services import duplicadas


_PDM_DUP = "PDM.9900.000 - FICHA PMIB, DUPLICADA, R0"
_PDM_NORMAL = "PDM.4320.002 - MOTOBOMBA"


class _DataFrameFalso:
    """Duplo mínimo do que `localizar_duplicadas` usa de um DataFrame:
    `.columns` e `.iterrows()`."""

    def __init__(self, colunas, linhas):
        self.columns = list(colunas)
        self._linhas = linhas

    def iterrows(self):
        return enumerate(self._linhas)

    @property
    def values(self):
        return self

    def tolist(self):
        return [self.columns]


class _PandasFalso:
    def __init__(self, colunas, linhas, abas=("Lista de Materiais",)):
        self._df = _DataFrameFalso(colunas, linhas)
        self._abas = list(abas)

    def ExcelFile(self, _caminho):
        return type("_X", (), {"sheet_names": list(self._abas)})()

    def read_excel(self, _caminho, sheet_name=None, header=None, nrows=None, dtype=None):
        return self._df


def _com_planilha(monkeypatch, colunas, linhas, abas=("Lista de Materiais",)):
    monkeypatch.setattr(duplicadas, "pd", _PandasFalso(colunas, linhas, abas))
    # A busca de cabeçalho lê a prévia; com o duplo, devolve a linha 0.
    monkeypatch.setattr(duplicadas.headers, "find_header_row", lambda *_a, **_k: 0)


_COLUNAS = [
    config.COL_CODIGO_PMIB, config.COL_DESCRICAO, "PDM usado",
    "CÓDIGO DO MATERIAL", "CÓDIGO CMI", "OBSERVAÇÕES",
]


def _linha(pmib, pdm, material="2904616", cmi="CMI-1", obs="4500063671.1471"):
    return {
        config.COL_CODIGO_PMIB: pmib, config.COL_DESCRICAO: "FONTE, ALIMENTACAO",
        "PDM usado": pdm, "CÓDIGO DO MATERIAL": material,
        "CÓDIGO CMI": cmi, "OBSERVAÇÕES": obs,
    }


# ===========================================================================
# Quais linhas viram ficha
# ===========================================================================
def test_so_as_linhas_com_o_pdm_de_duplicacao_entram(monkeypatch):
    _com_planilha(monkeypatch, _COLUNAS, [
        _linha("4500063671.0001", _PDM_NORMAL),
        _linha("4500063671.1418", _PDM_DUP),
        _linha("4500063671.0002", _PDM_NORMAL),
        _linha("4500063671.1419", _PDM_DUP),
    ])

    fichas, mensagem = duplicadas.localizar_duplicadas("x.xlsx")

    assert [f.pmib for f in fichas] == ["4500063671.1418", "4500063671.1419"]
    assert "2 ficha(s)" in mensagem


def test_planilha_sem_duplicadas_devolve_lista_vazia_sem_erro(monkeypatch):
    _com_planilha(monkeypatch, _COLUNAS, [_linha("4500063671.0001", _PDM_NORMAL)])

    fichas, mensagem = duplicadas.localizar_duplicadas("x.xlsx")

    assert fichas == []
    assert "0 ficha(s)" in mensagem


def test_a_linha_reportada_e_a_do_excel(monkeypatch):
    """O número tem de bater com a barra lateral do Excel -- é o que o usuário
    usa para achar a linha e corrigir."""
    _com_planilha(monkeypatch, _COLUNAS, [
        _linha("4500063671.0001", _PDM_NORMAL),
        _linha("4500063671.1418", _PDM_DUP),
    ])

    fichas, _m = duplicadas.localizar_duplicadas("x.xlsx")

    assert fichas[0].linha == 3  # índice 1 + cabeçalho na linha 1 + base 1


# ===========================================================================
# O que entra em cada campo
# ===========================================================================
def test_os_campos_saem_das_colunas_certas(monkeypatch):
    _com_planilha(monkeypatch, _COLUNAS, [
        _linha("4500063671.1418", _PDM_DUP, material="2904616",
               cmi="CMI-99", obs="Duplicada da 4500063671.1471"),
    ])

    ficha = duplicadas.localizar_duplicadas("x.xlsx")[0][0]

    assert ficha.codigo_material == "2904616"
    assert ficha.codigo_fornecedor == "CMI-99"
    assert ficha.ficha_original == "4500063671.1471"  # extraído do meio do texto


def test_codigo_ge_serve_no_lugar_de_codigo_cmi(monkeypatch):
    colunas = [c if c != "CÓDIGO CMI" else "CÓDIGO GE" for c in _COLUNAS]
    linha = _linha("4500063671.1418", _PDM_DUP)
    linha["CÓDIGO GE"] = linha.pop("CÓDIGO CMI")
    _com_planilha(monkeypatch, colunas, [linha])

    ficha = duplicadas.localizar_duplicadas("x.xlsx")[0][0]

    assert ficha.codigo_fornecedor == "CMI-1"


def test_celula_nan_do_pandas_vira_vazio_e_nao_o_texto_nan(monkeypatch):
    _com_planilha(monkeypatch, _COLUNAS, [
        _linha("4500063671.1418", _PDM_DUP, cmi="nan"),
    ])

    ficha = duplicadas.localizar_duplicadas("x.xlsx")[0][0]

    assert ficha.codigo_fornecedor == ""


# ===========================================================================
# Pronta x impedida
# ===========================================================================
def test_sem_ficha_original_a_duplicada_fica_impedida(monkeypatch):
    """Sem a original não há de onde copiar. Melhor descobrir na tela de
    seleção do que no meio do lote, com o navegador aberto."""
    _com_planilha(monkeypatch, _COLUNAS, [
        _linha("4500063671.1418", _PDM_DUP, obs=""),
    ])

    ficha = duplicadas.localizar_duplicadas("x.xlsx")[0][0]

    assert ficha.pronta_para_duplicar is False
    assert "OBSERVAÇÕES" in ficha.motivo_de_impedimento


def test_sem_codigo_do_material_a_duplicada_fica_impedida(monkeypatch):
    _com_planilha(monkeypatch, _COLUNAS, [
        _linha("4500063671.1418", _PDM_DUP, material=""),
    ])

    ficha = duplicadas.localizar_duplicadas("x.xlsx")[0][0]

    assert ficha.pronta_para_duplicar is False
    assert "CÓDIGO DO MATERIAL" in ficha.motivo_de_impedimento


def test_fornecedor_vazio_NAO_impede(monkeypatch):
    """"Se estiver vazio, só ignorar" -- palavra do usuário. Tratar como
    impedimento tiraria da fila fichas perfeitamente processáveis."""
    _com_planilha(monkeypatch, _COLUNAS, [
        _linha("4500063671.1418", _PDM_DUP, cmi=""),
    ])

    ficha = duplicadas.localizar_duplicadas("x.xlsx")[0][0]

    assert ficha.pronta_para_duplicar is True


def test_as_impedidas_continuam_na_lista(monkeypatch):
    """Esconder aqui faria a ficha sumir sem explicação. Quem decide o que
    fazer é a tela de seleção."""
    _com_planilha(monkeypatch, _COLUNAS, [
        _linha("4500063671.1418", _PDM_DUP),
        _linha("4500063671.1419", _PDM_DUP, obs=""),
    ])

    fichas, mensagem = duplicadas.localizar_duplicadas("x.xlsx")

    assert len(fichas) == 2
    assert "2 ficha(s)" in mensagem and "1 pronta(s)" in mensagem


# ===========================================================================
# Erros de planilha, com mensagem que resolve
# ===========================================================================
def test_sem_a_coluna_do_pdm_a_mensagem_diz_o_que_faltou(monkeypatch):
    _com_planilha(monkeypatch, ["A", "B"], [{"A": 1}])

    fichas, mensagem = duplicadas.localizar_duplicadas("x.xlsx")

    assert fichas == []
    assert "PDM usado" in mensagem
    assert "A, B" in mensagem  # as colunas que EXISTEM


def test_sem_a_aba_de_materiais_a_mensagem_lista_as_abas(monkeypatch):
    _com_planilha(monkeypatch, _COLUNAS, [], abas=("Capa", "Resumo"))

    fichas, mensagem = duplicadas.localizar_duplicadas("x.xlsx")

    assert fichas == []
    assert "Capa" in mensagem and "Resumo" in mensagem


def test_coluna_de_material_ausente_avisa_mas_nao_aborta(monkeypatch):
    """A ficha entra marcada como impedida; abortar esconderia de quantas
    fichas se está falando."""
    colunas = [c for c in _COLUNAS if c != "CÓDIGO DO MATERIAL"]
    linha = _linha("4500063671.1418", _PDM_DUP)
    linha.pop("CÓDIGO DO MATERIAL")
    _com_planilha(monkeypatch, colunas, [linha])
    logs = []

    fichas, _m = duplicadas.localizar_duplicadas("x.xlsx", callback_log=logs.append)

    assert len(fichas) == 1
    assert fichas[0].pronta_para_duplicar is False
    assert any("referência do fabricante" in linha_log for linha_log in logs)


@pytest.mark.parametrize("variante", ["PDM usado", "PDMs usados", "PDM USADO"])
def test_as_grafias_da_coluna_do_pdm_sao_aceitas(monkeypatch, variante):
    colunas = [c if c != "PDM usado" else variante for c in _COLUNAS]
    linha = _linha("4500063671.1418", _PDM_DUP)
    linha[variante] = linha.pop("PDM usado")
    _com_planilha(monkeypatch, colunas, [linha])

    fichas, _m = duplicadas.localizar_duplicadas("x.xlsx")

    assert len(fichas) == 1

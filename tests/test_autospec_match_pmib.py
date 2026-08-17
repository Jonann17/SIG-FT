r"""
Testes do casamento de código PMIB em `AutoSpecCore.get_pmib_data` —
bug encontrado na revisão do módulo em 2026-08-11.

Até esta data a comparação era `if code_suffix in val_pmib`: substring do
sufixo de 4 dígitos contra o código INTEIRO, prefixo de contrato incluído.
Como `config.PREFIXO_CONTRATO` (`"4500063671"`) contém ele mesmo sequências
de 4 dígitos, 7 sufixos casavam com QUALQUER linha da planilha — e a função
devolvia descrição e código de material da PRIMEIRA linha, de um material
diferente. Silenciosamente.

Por que importa mais que um bug comum: o retorno alimenta o contexto RAG e
as queries de busca web, então a IA pesquisa e preenche a ficha inteira com
base no material errado. É exatamente o cenário que o documento de regras de
negócio classifica como pior que campo vazio.
"""
import pytest

import autospec_backend
from sigft import config


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json")
    )


@pytest.fixture
def sufixo_de():
    """`AutoSpecCore._sufixo_pmib_da_celula` é estático — não precisa de
    instância nem de chave de IA para ser exercitado."""
    return autospec_backend.AutoSpecCore._sufixo_pmib_da_celula


# =============================================================================
# A. Os falsos positivos que motivaram a correção
# =============================================================================
SUFIXOS_DENTRO_DO_PREFIXO = ["0006", "0063", "0636", "3671", "4500", "5000", "6367"]


def test_o_prefixo_de_contrato_realmente_contem_esses_sufixos():
    """Trava a premissa do bug: se o prefixo mudar e deixar de conter estes
    sufixos, este teste avisa que o cenário virou outro."""
    for suf in SUFIXOS_DENTRO_DO_PREFIXO:
        assert suf in config.PREFIXO_CONTRATO


@pytest.mark.parametrize("sufixo_buscado", SUFIXOS_DENTRO_DO_PREFIXO)
def test_sufixo_contido_no_prefixo_nao_casa_com_linha_de_outro_material(
    sufixo_de, sufixo_buscado
):
    """O caso do bug: buscar '0006' não pode casar com a linha do 0105."""
    linha_de_outro_material = f"{config.PREFIXO_CONTRATO}.0105"
    assert sufixo_buscado in linha_de_outro_material  # a substring de antes casava
    assert sufixo_de(linha_de_outro_material) != sufixo_buscado  # agora não


def test_sufixo_contido_no_prefixo_ainda_casa_com_a_propria_linha(sufixo_de):
    """A correção não pode jogar fora o casamento legítimo: 0006 continua
    casando com a linha do 0006."""
    assert sufixo_de(f"{config.PREFIXO_CONTRATO}.0006") == "0006"


# =============================================================================
# B. Casamentos legítimos preservados
# =============================================================================
@pytest.mark.parametrize(
    "valor_celula,esperado,caso",
    [
        (f"{config.PREFIXO_CONTRATO}.0105", "0105", "código completo"),
        (f"'{config.PREFIXO_CONTRATO}.0105", "0105", "apóstrofo de texto do Excel"),
        (f"  {config.PREFIXO_CONTRATO}.0105  ", "0105", "espaços em volta"),
        ("0105", "0105", "coluna guarda só o sufixo"),
        (f"{config.PREFIXO_CONTRATO}.0105 - BOMBA CENTRIFUGA", "0105", "código no meio de texto"),
    ],
)
def test_formatos_de_celula_que_devem_continuar_casando(
    sufixo_de, valor_celula, esperado, caso
):
    assert sufixo_de(valor_celula) == esperado, caso


def test_codigo_guardado_como_float_volta_a_casar(sufixo_de):
    """FALSO NEGATIVO consertado de quebra: o Excel guarda 4500063671.1050
    como número, o zero à direita some no float, e a comparação por substring
    falhava. `normalize_pmib` restaura o zero."""
    como_float = float(f"{config.PREFIXO_CONTRATO}.1050")
    assert "1050" not in str(como_float)  # o zero sumiu mesmo
    assert sufixo_de(como_float) == "1050"


@pytest.mark.parametrize("vazio", [None, "", "   ", "BOMBA SEM CODIGO"])
def test_celulas_sem_codigo_nao_casam_com_nada(sufixo_de, vazio):
    resultado = sufixo_de(vazio)
    assert resultado == "" or resultado != "0105"


def test_material_diferente_continua_nao_casando(sufixo_de):
    assert sufixo_de(f"{config.PREFIXO_CONTRATO}.0200") != "0105"


# =============================================================================
# C. Ponta a ponta: get_pmib_data devolve a linha CERTA
# =============================================================================
class _CelulaFake:
    def __init__(self, value):
        self.value = value


class _WorksheetFake:
    """Planilha mínima no formato que `get_pmib_data` consome: cabeçalho na
    linha 1 e as linhas de dados em seguida.

    Precisa de `max_row`/`max_column`/`cell()` (usados por
    `headers.rows_from_worksheet`, dentro de `find_header_columns`) e de
    `iter_rows()` (usado pelo laço do próprio `get_pmib_data`)."""

    def __init__(self, linhas):
        self._linhas = linhas
        self.max_row = len(linhas)
        self.max_column = max(len(l) for l in linhas) if linhas else 0

    def cell(self, row, column):
        linha = self._linhas[row - 1]
        valor = linha[column - 1] if column - 1 < len(linha) else None
        return _CelulaFake(valor)

    def iter_rows(self, min_row=1):
        for i, linha in enumerate(self._linhas, start=1):
            if i >= min_row:
                yield [_CelulaFake(v) for v in linha]


def _montar_status_pmib(monkeypatch, linhas_dados):
    """Monta uma worksheet fake e faz `openpyxl.load_workbook` devolvê-la."""
    cabecalho = [config.COL_CODIGO_PMIB, config.COL_DESCRICAO, "CÓDIGO MATERIAL"]
    ws = _WorksheetFake([cabecalho] + linhas_dados)

    class _WbFake:
        active = ws

    monkeypatch.setattr(
        autospec_backend.openpyxl, "load_workbook", lambda *a, **k: _WbFake()
    )
    return ws


def _core(monkeypatch):
    return autospec_backend.AutoSpecCore(
        gemini_key="chave-fake",
        llama_key=None,
        google_search_key=None,
        google_cse_id=None,
        selecao_resolvida={"provider": config.PROVIDER_GEMINI, "model": "m"},
    )


def test_get_pmib_data_nao_devolve_material_errado(monkeypatch):
    """O bug ponta a ponta: ficha `.0006`, planilha cujo PRIMEIRO material é
    o `.0105`. Antes da correção voltava a BOMBA."""
    _montar_status_pmib(
        monkeypatch,
        [
            [f"{config.PREFIXO_CONTRATO}.0105", "BOMBA CENTRIFUGA", "MAT-BOMBA"],
            [f"{config.PREFIXO_CONTRATO}.0006", "VALVULA GAVETA", "MAT-VALVULA"],
        ],
    )
    core = _core(monkeypatch)
    desc, mat, _marca = core.get_pmib_data("qualquer.xlsx", "0006")
    assert (desc, mat) == ("VALVULA GAVETA", "MAT-VALVULA")


def test_get_pmib_data_devolve_vazio_quando_o_material_nao_esta_na_planilha(monkeypatch):
    """Sem correspondência, `("", "")` — e não a primeira linha por acidente."""
    _montar_status_pmib(
        monkeypatch,
        [[f"{config.PREFIXO_CONTRATO}.0105", "BOMBA CENTRIFUGA", "MAT-BOMBA"]],
    )
    core = _core(monkeypatch)
    assert core.get_pmib_data("qualquer.xlsx", "0006") == ("", "", "")

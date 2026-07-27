r"""
Testes do Checkpoint 1.2 — `sigft/core/excel/headers.py`.

`find_header_row()` e `find_columns()` são funções PURAS (operam sobre listas
Python, nunca sobre DataFrame/openpyxl diretamente — ver docstring do
módulo) — testadas aqui com listas puras, cobrindo os padrões usados pelos
~11 consumidores migrados no CP 1.2:

  find_header_row (0-based, mode="cell"/"text", require="all"/"any"):
    - DataManager.carregar_planilha_inteligente (múltiplas keywords, "all")
    - upload_conditions.carregar_lookup_status (1 keyword)
    - upload_tech_specs.encontrar_header (1 keyword)
    - GerenciadorFilaPMIB._encontrar_cabecalho (1 keyword, dentre uma lista
      maior declarada mas não usada no original — só "CÓDIGO PMIB" importa)
    - pmib_manager._ler_status_pmib (1 keyword)
    - search_pmib_backend._encontrar_e_formatar_dataframe (mode="text",
      require="any", 2 grafias alternativas "DESCRIÇÃO"/"DESCRICAO")

  find_columns (1-based, required subset, aliases):
    - analyzer._find_header_columns / DataManager.atualizar_excel_final
      (todas as chaves obrigatórias)
    - autospec.find_header_columns (chave opcional "CÓDIGO MATERIAL")
    - AtualizadorStatusPMIB (só uma chave-âncora obrigatória, resto
      oportunista)
    - alias de grafia (ex.: "PDM USADO"/"PDM" -> mesma chave "PDM usado")

Mais os utilitários `_default_normalize` (indiretamente) e
`rows_from_worksheet()` (com uma worksheet falsa "duck-typed", sem
openpyxl).
"""
from sigft.core.excel.headers import find_columns, find_header_row, rows_from_worksheet


# ===========================================================================
# find_header_row — mode="cell", require="all" (o caso mais comum)
# ===========================================================================

def test_encontra_linha_com_todas_as_keywords_desejadas():
    # Padrão de DataManager.carregar_planilha_inteligente.
    rows = [
        ["Projeto XYZ", None],
        ["ITEM", "DESCRIÇÃO", "CÓDIGO PMIB", "MARCA/MODELO"],
        [1, "Bomba", "1234"],
    ]
    assert find_header_row(rows, ["DESCRIÇÃO", "CÓDIGO PMIB"]) == 1


def test_nao_encontra_quando_falta_uma_keyword():
    rows = [["DESCRIÇÃO", "OUTRA COISA"]]
    assert find_header_row(rows, ["DESCRIÇÃO", "CÓDIGO PMIB"]) is None


def test_single_keyword_string_funciona_sem_precisar_de_lista():
    # Padrão de upload_conditions.carregar_lookup_status /
    # upload_tech_specs.encontrar_header / pmib_manager._ler_status_pmib
    # (uma única palavra-chave, passada como string).
    rows = [["x"], ["CÓDIGO PMIB", "y"], ["z"]]
    assert find_header_row(rows, "CÓDIGO PMIB") == 1


def test_max_rows_limita_a_varredura():
    rows = [["a"], ["b"], ["CÓDIGO PMIB"]]
    assert find_header_row(rows, "CÓDIGO PMIB", max_rows=2) is None
    assert find_header_row(rows, "CÓDIGO PMIB", max_rows=3) == 2


def test_lista_de_keywords_declarada_mas_so_uma_e_realmente_exigida():
    # Padrão de GerenciadorFilaPMIB._encontrar_cabecalho: o original declara
    # colunas_chave = ["CÓDIGO PMIB", "PDM usado", "OBSERVAÇÕES"] mas só
    # verifica "CÓDIGO PMIB" -- migrado passando SÓ essa keyword.
    rows = [["CÓDIGO PMIB", "outra coluna qualquer"]]
    assert find_header_row(rows, ["CÓDIGO PMIB"]) == 0


def test_normalizacao_e_case_insensitive_e_ignora_espacos():
    rows = [["  código pmib  "]]
    assert find_header_row(rows, "CÓDIGO PMIB") == 0


def test_celula_none_nunca_casa_com_keyword_normal():
    rows = [[None, None], ["CÓDIGO PMIB"]]
    assert find_header_row(rows, "CÓDIGO PMIB") == 1


def test_valor_numerico_de_celula_nao_quebra_normalizacao():
    rows = [[123, 45.6], ["CÓDIGO PMIB"]]
    assert find_header_row(rows, "CÓDIGO PMIB") == 1


# ===========================================================================
# find_header_row — mode="text", require="any" (search_pmib_backend)
# ===========================================================================

def test_mode_text_casa_por_substring_na_linha_concatenada():
    # Uma célula com "DESCRIÇÃO DO ITEM" deve casar por conter "DESCRIÇÃO"
    # como substring (busca não é por igualdade exata de célula).
    rows = [["Código", "DESCRIÇÃO DO ITEM", "Unidade"]]
    assert find_header_row(rows, ["DESCRIÇÃO", "DESCRICAO"], mode="text", require="any") == 0


def test_mode_text_aceita_grafia_alternativa_sem_acento():
    rows = [["CODIGO", "DESCRICAO"]]
    assert find_header_row(rows, ["DESCRIÇÃO", "DESCRICAO"], mode="text", require="any") == 0


def test_mode_text_require_any_nao_precisa_das_duas_grafias():
    rows = [["nada a ver aqui"], ["tem DESCRIÇÃO nesta linha"]]
    assert find_header_row(rows, ["DESCRIÇÃO", "DESCRICAO"], mode="text", require="any") == 1


def test_mode_cell_nao_casa_substring_so_igualdade():
    # Contraste com mode="text": em mode="cell" (default), uma célula
    # "DESCRIÇÃO DO ITEM" NÃO é igual a "DESCRIÇÃO" -> não casa.
    rows = [["Código", "DESCRIÇÃO DO ITEM"]]
    assert find_header_row(rows, "DESCRIÇÃO") is None


# ===========================================================================
# find_columns — required=None (todas obrigatórias), 1-based
# ===========================================================================

def test_find_columns_retorna_indices_1_based_e_linha_1_based():
    rows = [
        ["CÓDIGO PMIB", "DESCRIÇÃO"],
        ["1234", "Bomba"],
    ]
    col_map, header_row = find_columns(rows, {"CÓDIGO PMIB": "CÓDIGO PMIB", "DESCRIÇÃO": "DESCRIÇÃO"})
    assert col_map == {"CÓDIGO PMIB": 1, "DESCRIÇÃO": 2}
    assert header_row == 1


def test_find_columns_localiza_colunas_fora_de_ordem_e_com_offset():
    rows = [
        [None, None, None],
        [None, "DESCRIÇÃO", "CÓDIGO PMIB"],
    ]
    col_map, header_row = find_columns(rows, {"CÓDIGO PMIB": "CÓDIGO PMIB", "DESCRIÇÃO": "DESCRIÇÃO"})
    assert col_map == {"DESCRIÇÃO": 2, "CÓDIGO PMIB": 3}
    assert header_row == 2


def test_find_columns_completa_apenas_quando_todas_as_keywords_aparecem_cumulativamente():
    # "CÓDIGO PMIB" na linha 1, "DESCRIÇÃO" só na linha 3 -- o header_row
    # registrado é o da linha em que a exigência fica satisfeita (3), não a
    # primeira ocorrência isolada.
    rows = [
        ["CÓDIGO PMIB"],
        ["irrelevante"],
        ["x", "DESCRIÇÃO"],
    ]
    col_map, header_row = find_columns(rows, {"CÓDIGO PMIB": "CÓDIGO PMIB", "DESCRIÇÃO": "DESCRIÇÃO"})
    assert col_map == {"CÓDIGO PMIB": 1, "DESCRIÇÃO": 2}
    assert header_row == 3


def test_find_columns_none_quando_nunca_satisfaz_dentro_do_max_rows():
    rows = [["CÓDIGO PMIB"], ["ainda nada"], ["DESCRIÇÃO aqui"]]
    col_map, header_row = find_columns(
        rows, {"CÓDIGO PMIB": "CÓDIGO PMIB", "DESCRIÇÃO": "DESCRIÇÃO"}, max_rows=2
    )
    assert header_row is None
    # col_map preserva o que foi encontrado até a parada (uso "best effort"
    # do chamador, ex.: autospec.find_header_columns).
    assert col_map == {"CÓDIGO PMIB": 1}


# ===========================================================================
# find_columns — required parcial (chave âncora + chaves opcionais)
# ===========================================================================

def test_find_columns_required_subconjunto_ignora_chaves_faltantes_fora_dele():
    # Padrão de autospec.find_header_columns: "CÓDIGO MATERIAL" é opcional.
    rows = [["CÓDIGO PMIB", "DESCRIÇÃO"]]
    keywords = {
        "CÓDIGO PMIB": "CÓDIGO PMIB",
        "DESCRIÇÃO": "DESCRIÇÃO",
        "CÓDIGO MATERIAL": ["CÓDIGO MATERIAL", "MATERIAL"],
    }
    col_map, header_row = find_columns(rows, keywords, required=["CÓDIGO PMIB", "DESCRIÇÃO"])
    assert header_row == 1
    assert col_map == {"CÓDIGO PMIB": 1, "DESCRIÇÃO": 2}  # sem CÓDIGO MATERIAL


def test_find_columns_required_subconjunto_coleta_chave_opcional_quando_presente():
    rows = [["CÓDIGO PMIB", "DESCRIÇÃO", "MATERIAL"]]
    keywords = {
        "CÓDIGO PMIB": "CÓDIGO PMIB",
        "DESCRIÇÃO": "DESCRIÇÃO",
        "CÓDIGO MATERIAL": ["CÓDIGO MATERIAL", "MATERIAL"],
    }
    col_map, header_row = find_columns(rows, keywords, required=["CÓDIGO PMIB", "DESCRIÇÃO"])
    assert col_map == {"CÓDIGO PMIB": 1, "DESCRIÇÃO": 2, "CÓDIGO MATERIAL": 3}


def test_find_columns_apenas_chave_ancora_obrigatoria():
    # Padrão de AtualizadorStatusPMIB.atualizar_ficha_concluida: só "CÓDIGO
    # PMIB" é obrigatória; as chaves de `secoes_concluidas` (dinâmicas) são
    # oportunistas.
    rows = [["CÓDIGO PMIB", "INFO. GERAIS"]]
    keywords = {"CÓDIGO PMIB": "CÓDIGO PMIB", "INFO. GERAIS": "INFO. GERAIS", "CONDIÇÕES": "CONDIÇÕES"}
    col_map, header_row = find_columns(rows, keywords, required=["CÓDIGO PMIB"])
    assert header_row == 1
    assert col_map == {"CÓDIGO PMIB": 1, "INFO. GERAIS": 2}  # sem CONDIÇÕES (não apareceu)


# ===========================================================================
# find_columns — aliases (múltiplas grafias -> mesma chave de saída)
# ===========================================================================

def test_find_columns_aceita_grafia_alternativa_pdm_usado():
    rows = [["DESCRIÇÃO", "CÓDIGO PMIB", "PDM"]]
    keywords = {
        "DESCRIÇÃO": "DESCRIÇÃO",
        "CÓDIGO PMIB": "CÓDIGO PMIB",
        "PDM usado": ["PDM USADO", "PDM"],
    }
    col_map, header_row = find_columns(rows, keywords)
    assert col_map["PDM usado"] == 3
    assert header_row == 1


def test_find_columns_aceita_a_outra_grafia_alternativa_tambem():
    rows = [["DESCRIÇÃO", "CÓDIGO PMIB", "PDM USADO"]]
    keywords = {
        "DESCRIÇÃO": "DESCRIÇÃO",
        "CÓDIGO PMIB": "CÓDIGO PMIB",
        "PDM usado": ["PDM USADO", "PDM"],
    }
    col_map, _ = find_columns(rows, keywords)
    assert col_map["PDM usado"] == 3


def test_find_columns_max_rows_limita_a_varredura():
    rows = [["irrelevante"], ["CÓDIGO PMIB"]]
    col_map, header_row = find_columns(rows, {"CÓDIGO PMIB": "CÓDIGO PMIB"}, max_rows=1)
    assert header_row is None
    assert col_map == {}


def test_find_columns_ocorrencia_mais_recente_vence_na_mesma_varredura():
    # Réplica da semântica original (sobrescrita simples, sem checagem de
    # "primeira ocorrência"): se a keyword aparecer 2x antes da parada, a
    # última coluna encontrada é a que fica.
    rows = [["CÓDIGO PMIB", "CÓDIGO PMIB"]]
    col_map, _ = find_columns(rows, {"CÓDIGO PMIB": "CÓDIGO PMIB"})
    assert col_map["CÓDIGO PMIB"] == 2


# ===========================================================================
# rows_from_worksheet — adaptador openpyxl (duck-typed, sem importar openpyxl)
# ===========================================================================

class _FakeCell:
    def __init__(self, value):
        self.value = value


class _FakeWorksheet:
    """Worksheet mínima o suficiente para exercitar `rows_from_worksheet`
    sem depender do pacote openpyxl (ausente no ambiente de teste)."""

    def __init__(self, grid):
        self._grid = grid
        self.max_row = len(grid)
        self.max_column = max((len(r) for r in grid), default=0)

    def cell(self, row, column):
        try:
            return _FakeCell(self._grid[row - 1][column - 1])
        except IndexError:
            return _FakeCell(None)


def test_rows_from_worksheet_usa_dimensoes_reais_por_padrao():
    ws = _FakeWorksheet([["a", "b"], ["c", "d", "e"]])
    rows = list(rows_from_worksheet(ws))
    assert rows == [["a", "b", None], ["c", "d", "e"]]


def test_rows_from_worksheet_respeita_max_row_e_max_col_explicitos():
    ws = _FakeWorksheet([["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]])
    rows = list(rows_from_worksheet(ws, max_row=2, max_col=2))
    assert rows == [["a", "b"], ["d", "e"]]


def test_rows_from_worksheet_planilha_vazia_nao_gera_linhas():
    ws = _FakeWorksheet([])
    assert list(rows_from_worksheet(ws)) == []


def test_rows_from_worksheet_encadeia_com_find_columns():
    ws = _FakeWorksheet([["CÓDIGO PMIB", "DESCRIÇÃO"], ["1234", "Bomba"]])
    col_map, header_row = find_columns(
        rows_from_worksheet(ws), {"CÓDIGO PMIB": "CÓDIGO PMIB", "DESCRIÇÃO": "DESCRIÇÃO"}
    )
    assert col_map == {"CÓDIGO PMIB": 1, "DESCRIÇÃO": 2}
    assert header_row == 1

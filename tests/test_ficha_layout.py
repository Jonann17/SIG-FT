r"""
Testes do Checkpoint 2.4 — `sigft/core/rpa/ficha_layout.py` (`CONFIG_MAP`/
`VARIAVEIS_SPECS` unificados).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.4. Critério de
aceite do plano: "`CONFIG_MAP` definido uma única vez; teste de equivalência
com os dois mapas antigos (guardados como fixture)".

As fixtures `_OLD_ANALYZER_CONFIG_MAP`/`_OLD_AUTOSPEC_CONFIG_MAP`/
`_OLD_ANALYZER_VARIAVEIS_SPECS`/`_OLD_AUTOSPEC_VARIAVEIS_SPECS` abaixo são
cópias CONGELADAS, byte a byte, do que `analyzer_backend.py` (linhas 25-57) e
`autospec_backend.py` (linhas 34-66) continham ANTES da migração deste
checkpoint — não são re-derivadas nem "melhoradas": servem de referência
imutável para provar que `ficha_layout.CONFIG_MAP`/`VARIAVEIS_SPECS` é a
UNIÃO fiel dos dois, sem perder nem inventar informação.

Cobertura (numeração espelha o plano de teste do checkpoint):
  1. Estrutura: as 25 chaves batem nos 3 mapas.
  2. Equivalência por chave: type/validation/weight/cells idênticos; range
     completo (analyzer) x primeira célula (autospec).
  3. error_target: só presente onde o analyzer original tinha.
  4. desc: só presente onde o autospec original tinha.
  5. VARIAVEIS_SPECS: as 4 chaves antigas preservadas + start_row via
     `sigft.config.LINHA_SPECS_FICHA`.
  6. Fonte única de verdade: `analyzer_backend.CONFIG_MAP is
     ficha_layout.CONFIG_MAP` (idem autospec/VARIAVEIS_SPECS) — identidade de
     objeto, não só igualdade.
  7. `DatasheetAnalyzer._find_variable_specs_start_row`: fallback nomeado.
  8. `AutoSpecCore.analyze_sheet`: as 2 linhas corrigidas (`.split(":")[0]`)
     continuam lendo a célula certa com o range agora completo.
  9. `AutoSpecCore.fill_save`: continua robusto a um `ref` com range
     completo vindo do `missing[...]` novo.
"""
import analyzer_backend
import autospec_backend
import pytest

import sigft.config as sigft_config
from sigft.core.rpa import ficha_layout

# =============================================================================
# Fixtures — os dois CONFIG_MAP/VARIAVEIS_SPECS ORIGINAIS, congelados tal
# qual existiam antes da migração deste checkpoint (ver docstring do módulo).
# =============================================================================

_OLD_ANALYZER_CONFIG_MAP = {
    "texto_breve_material": {"range": "H6:P6", "type": "cell", "validation": "simple", "weight": 1},
    "unidade": {"range": "H8:J8", "type": "cell", "validation": "simple", "weight": 1},
    "tipo_fabricacao": {"cells": ["F10", "F12"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["F10", "F12"]},
    "fabricante": {"range": "L10:N10", "type": "cell", "validation": "simple", "weight": 1},
    "origem": {"cells": ["S6", "S8"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["S6", "S8"]},
    "tipo": {"cells": ["S10", "S12"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["S10", "S12"]},
    "comprimento_embalagem": {"range": "H17:K17", "type": "cell", "validation": "simple", "weight": 1},
    "largura_embalagem": {"range": "H19:K19", "type": "cell", "validation": "simple", "weight": 1},
    "altura_embalagem": {"range": "H21:K21", "type": "cell", "validation": "simple", "weight": 1},
    "peso_liquido": {"range": "P17:Q17", "type": "cell", "validation": "simple", "weight": 1},
    "peso_bruto": {"range": "P19:Q19", "type": "cell", "validation": "simple", "weight": 1},
    "sujeito_intemperies": {"cells": ["Q21", "S21"], "type": "checkbox", "validation": "simple", "weight": 1, "error_target": "U21"},
    "posicao_armazenamento": {"cells": ["G25", "G27", "G29"], "type": "checkbox", "validation": "simple", "weight": 3, "error_target": "J27"},
    "protecao": {"cells": ["S25", "S27", "S29"], "type": "checkbox", "validation": "simple", "weight": 3, "error_target": "O27"},
    "nocivo": {"cells": ["E31", "E33"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": "L31"},
    "empilhamento": {"range": "J35:L35", "type": "cell", "validation": "simple", "weight": 2},
    "embalagem_transporte": {"range": "M42:V44", "type": "cell", "validation": "ai", "weight": 7},
    "transporte": {"range": "M45:V47", "type": "cell", "validation": "ai", "weight": 3},
    "preservacao": {"range": "M52:V53", "type": "cell", "validation": "ai", "weight": 6},
    "metodo_limpeza": {"range": "M54:V55", "type": "cell", "validation": "ai", "weight": 3},
    "ferramentas_para_preservacao": {"range": "M56:V58", "type": "cell", "validation": "ai", "weight": 1},
    "tipo_legislacao": {"range": "M63:V64", "type": "cell", "validation": "ai", "weight": 4},
    "tipo_descarte": {"range": "M65:V66", "type": "cell", "validation": "ai", "weight": 2},
    "classificacao_periculosidade": {"cells": ["E69", "J69"], "type": "checkbox", "validation": "simple", "weight": 2},
    "logistica_reversa": {"cells": ["P69", "T69"], "type": "checkbox", "validation": "simple", "weight": 2},
}

_OLD_ANALYZER_VARIAVEIS_SPECS = {
    "start_row": 79,
    "pergunta_range": "C:L",
    "resposta_range": "M:V",
}

_OLD_AUTOSPEC_CONFIG_MAP = {
    "texto_breve_material": {"range": "H6", "type": "cell", "validation": "simple", "weight": 1},
    "unidade": {"range": "H8", "type": "cell", "validation": "simple", "weight": 1},
    "tipo_fabricacao": {"cells": ["F10", "F12"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "F10: Série, F12: Especial/Sob Pedido"},
    "fabricante": {"range": "L10", "type": "cell", "validation": "simple", "weight": 1},
    "origem": {"cells": ["S6", "S8"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "S6: BR/PY, S8: Outros"},
    "tipo": {"cells": ["S10", "S12"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "S10: Reparável, S12: Não Reparável"},
    "comprimento_embalagem": {"range": "H17", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm"},
    "largura_embalagem": {"range": "H19", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm"},
    "altura_embalagem": {"range": "H21", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm"},
    "peso_liquido": {"range": "P17", "type": "cell", "validation": "simple", "weight": 1, "desc": "kg"},
    "peso_bruto": {"range": "P19", "type": "cell", "validation": "simple", "weight": 1, "desc": "kg"},
    "sujeito_intemperies": {"cells": ["Q21", "S21"], "type": "checkbox", "validation": "simple", "weight": 1, "desc": "Q21: Sim, S21: Não"},
    "posicao_armazenamento": {"cells": ["G25", "G27", "G29"], "type": "checkbox", "validation": "simple", "weight": 3, "desc": "G25: Vertical, G27: Horizontal, G29: Indiferente"},
    "protecao": {"cells": ["S25", "S27", "S29"], "type": "checkbox", "validation": "simple", "weight": 3, "desc": "S25: Nenhuma, S27: UV, S29: Eletrostática"},
    "nocivo": {"cells": ["E31", "E33"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "E31: Não Nocivo, E33: Nocivo"},
    "empilhamento": {"range": "J35", "type": "cell", "validation": "simple", "weight": 2, "desc": "Qtd Max Caixas"},
    "embalagem_transporte": {"range": "M42", "type": "cell", "validation": "ai", "weight": 7, "desc": "Tipo e cuidados embalagem transporte"},
    "transporte": {"range": "M45", "type": "cell", "validation": "ai", "weight": 3, "desc": "Procedimento elevação/transporte"},
    "preservacao": {"range": "M52", "type": "cell", "validation": "ai", "weight": 6, "desc": "Cuidados preservação"},
    "metodo_limpeza": {"range": "M54", "type": "cell", "validation": "ai", "weight": 3, "desc": "Métodos limpeza/secagem"},
    "ferramentas_para_preservacao": {"range": "M56", "type": "cell", "validation": "ai", "weight": 1, "desc": "Ferramentas recomendadas"},
    "tipo_legislacao": {"range": "M63", "type": "cell", "validation": "ai", "weight": 4, "desc": "Legislação aplicada"},
    "tipo_descarte": {"range": "M65", "type": "cell", "validation": "ai", "weight": 2, "desc": "Tipo descarte/Melhores práticas"},
    "classificacao_periculosidade": {"cells": ["E69", "J69"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "E69: Classe 1 (Perigoso), J69: Classe 2 (Não Perigoso)"},
    "logistica_reversa": {"cells": ["P69", "T69"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "P69: Não se aplica, T69: Aplica-se"},
}

_OLD_AUTOSPEC_VARIAVEIS_SPECS = {
    "start_row": 79,
    "pergunta_col_idx": 3,
    "resposta_col_idx": 13,
}

# Listas derivadas das fixtures (não do módulo novo) — usadas para
# parametrizar os testes abaixo.
_TODAS_AS_CHAVES = sorted(_OLD_ANALYZER_CONFIG_MAP)
_CHAVES_CELL = sorted(k for k, v in _OLD_ANALYZER_CONFIG_MAP.items() if v["type"] == "cell")
_CHAVES_CHECKBOX = sorted(k for k, v in _OLD_ANALYZER_CONFIG_MAP.items() if v["type"] == "checkbox")
_CHAVES_COM_ERROR_TARGET = sorted(k for k, v in _OLD_ANALYZER_CONFIG_MAP.items() if "error_target" in v)
_CHAVES_SEM_ERROR_TARGET = sorted(k for k in _OLD_ANALYZER_CONFIG_MAP if k not in _CHAVES_COM_ERROR_TARGET)
_CHAVES_COM_DESC = sorted(k for k, v in _OLD_AUTOSPEC_CONFIG_MAP.items() if "desc" in v)
_CHAVES_SEM_DESC = sorted(k for k in _OLD_AUTOSPEC_CONFIG_MAP if k not in _CHAVES_COM_DESC)


# =============================================================================
# 1. Estrutura — as 25 chaves batem nos 3 mapas.
# =============================================================================

def test_25_chaves_sem_perder_nem_inventar_nenhuma():
    assert set(ficha_layout.CONFIG_MAP) == set(_OLD_ANALYZER_CONFIG_MAP) == set(_OLD_AUTOSPEC_CONFIG_MAP)
    assert len(ficha_layout.CONFIG_MAP) == 25


def test_9_checkbox_16_cell_conferido_contra_a_fixture():
    # Confere a própria fixture/derivação usada para parametrizar os testes
    # abaixo (25 = 16 "cell" + 9 "checkbox", conferido no CP 2.4).
    assert len(_CHAVES_CELL) == 16
    assert len(_CHAVES_CHECKBOX) == 9


# =============================================================================
# 2. Equivalência por chave: type/validation/weight/cells/range.
# =============================================================================

@pytest.mark.parametrize("chave", _TODAS_AS_CHAVES)
def test_type_validation_weight_identicos_aos_2_originais(chave):
    novo = ficha_layout.CONFIG_MAP[chave]
    velho_analyzer = _OLD_ANALYZER_CONFIG_MAP[chave]
    velho_autospec = _OLD_AUTOSPEC_CONFIG_MAP[chave]

    assert novo["type"] == velho_analyzer["type"] == velho_autospec["type"]
    assert novo["validation"] == velho_analyzer["validation"] == velho_autospec["validation"]
    assert novo["weight"] == velho_analyzer["weight"] == velho_autospec["weight"]


@pytest.mark.parametrize("chave", _CHAVES_CHECKBOX)
def test_cells_identico_aos_2_originais_em_checkbox(chave):
    novo = ficha_layout.CONFIG_MAP[chave]["cells"]
    assert novo == _OLD_ANALYZER_CONFIG_MAP[chave]["cells"] == _OLD_AUTOSPEC_CONFIG_MAP[chave]["cells"]


@pytest.mark.parametrize("chave", _CHAVES_CELL)
def test_range_e_o_span_completo_do_analyzer_cuja_1a_celula_bate_com_autospec(chave):
    range_unificado = ficha_layout.CONFIG_MAP[chave]["range"]

    # Canônico = o range COMPLETO do analyzer (decisão do CP 2.4), não o de
    # célula única do autospec.
    assert range_unificado == _OLD_ANALYZER_CONFIG_MAP[chave]["range"]

    # A 1a célula do range completo bate com o valor único que o autospec
    # original guardava — equivalência funcional confirmada célula a célula.
    assert range_unificado.split(":")[0] == _OLD_AUTOSPEC_CONFIG_MAP[chave]["range"]


# =============================================================================
# 3. error_target — só presente onde o analyzer original tinha.
# =============================================================================

@pytest.mark.parametrize("chave", _CHAVES_COM_ERROR_TARGET)
def test_error_target_presente_e_igual_ao_analyzer_original(chave):
    assert ficha_layout.CONFIG_MAP[chave]["error_target"] == _OLD_ANALYZER_CONFIG_MAP[chave]["error_target"]


@pytest.mark.parametrize("chave", _CHAVES_SEM_ERROR_TARGET)
def test_error_target_ausente_quando_analyzer_original_nao_tinha(chave):
    assert "error_target" not in ficha_layout.CONFIG_MAP[chave]


def test_classificacao_periculosidade_e_logistica_reversa_continuam_sem_error_target():
    # Citadas explicitamente no plano de teste do checkpoint: são checkbox
    # mas NUNCA tiveram error_target (nem no analyzer original).
    assert "classificacao_periculosidade" not in _CHAVES_COM_ERROR_TARGET
    assert "logistica_reversa" not in _CHAVES_COM_ERROR_TARGET
    assert "error_target" not in ficha_layout.CONFIG_MAP["classificacao_periculosidade"]
    assert "error_target" not in ficha_layout.CONFIG_MAP["logistica_reversa"]


def test_7_chaves_com_error_target_conferido_contra_a_fixture():
    assert len(_CHAVES_COM_ERROR_TARGET) == 7


# =============================================================================
# 4. desc — só presente onde o autospec original tinha.
# =============================================================================

@pytest.mark.parametrize("chave", _CHAVES_COM_DESC)
def test_desc_presente_e_igual_ao_autospec_original(chave):
    assert ficha_layout.CONFIG_MAP[chave]["desc"] == _OLD_AUTOSPEC_CONFIG_MAP[chave]["desc"]


@pytest.mark.parametrize("chave", _CHAVES_SEM_DESC)
def test_desc_ausente_quando_autospec_original_nao_tinha(chave):
    assert "desc" not in ficha_layout.CONFIG_MAP[chave]


def test_texto_breve_unidade_fabricante_continuam_sem_desc():
    # Citadas explicitamente no plano de teste do checkpoint.
    assert set(_CHAVES_SEM_DESC) == {"texto_breve_material", "unidade", "fabricante"}
    for chave in ("texto_breve_material", "unidade", "fabricante"):
        assert "desc" not in ficha_layout.CONFIG_MAP[chave]


# =============================================================================
# 5. VARIAVEIS_SPECS — as 4 chaves antigas preservadas + start_row via config.
# =============================================================================

def test_variaveis_specs_preserva_pergunta_e_resposta_range_do_analyzer():
    assert ficha_layout.VARIAVEIS_SPECS["pergunta_range"] == _OLD_ANALYZER_VARIAVEIS_SPECS["pergunta_range"] == "C:L"
    assert ficha_layout.VARIAVEIS_SPECS["resposta_range"] == _OLD_ANALYZER_VARIAVEIS_SPECS["resposta_range"] == "M:V"


def test_variaveis_specs_preserva_pergunta_e_resposta_col_idx_do_autospec():
    assert ficha_layout.VARIAVEIS_SPECS["pergunta_col_idx"] == _OLD_AUTOSPEC_VARIAVEIS_SPECS["pergunta_col_idx"] == 3
    assert ficha_layout.VARIAVEIS_SPECS["resposta_col_idx"] == _OLD_AUTOSPEC_VARIAVEIS_SPECS["resposta_col_idx"] == 13


def test_variaveis_specs_start_row_e_79_e_vem_de_linha_specs_ficha():
    assert _OLD_ANALYZER_VARIAVEIS_SPECS["start_row"] == 79
    assert _OLD_AUTOSPEC_VARIAVEIS_SPECS["start_row"] == 79
    assert ficha_layout.VARIAVEIS_SPECS["start_row"] == 79
    assert ficha_layout.VARIAVEIS_SPECS["start_row"] == sigft_config.LINHA_SPECS_FICHA


def test_variaveis_specs_tem_exatamente_as_5_chaves_esperadas():
    # 4 chaves disjuntas dos 2 originais + start_row deduplicado.
    assert set(ficha_layout.VARIAVEIS_SPECS) == {
        "start_row", "pergunta_range", "resposta_range", "pergunta_col_idx", "resposta_col_idx",
    }


# =============================================================================
# 6. Fonte única de verdade — identidade de objeto (não só igualdade).
# =============================================================================

def test_analyzer_backend_importa_o_mesmo_objeto_config_map_e_variaveis_specs():
    assert analyzer_backend.CONFIG_MAP is ficha_layout.CONFIG_MAP
    assert analyzer_backend.VARIAVEIS_SPECS is ficha_layout.VARIAVEIS_SPECS


def test_autospec_backend_importa_o_mesmo_objeto_config_map_e_variaveis_specs():
    assert autospec_backend.CONFIG_MAP is ficha_layout.CONFIG_MAP
    assert autospec_backend.VARIAVEIS_SPECS is ficha_layout.VARIAVEIS_SPECS


def test_analyzer_e_autospec_compartilham_o_mesmo_objeto_entre_si():
    # Consequência direta dos 2 testes acima, mas verificada explicitamente:
    # não são 2 cópias coincidentemente iguais, é o MESMO dict em memória.
    assert analyzer_backend.CONFIG_MAP is autospec_backend.CONFIG_MAP
    assert analyzer_backend.VARIAVEIS_SPECS is autospec_backend.VARIAVEIS_SPECS


# =============================================================================
# 7. DatasheetAnalyzer._find_variable_specs_start_row — fallback nomeado.
# =============================================================================

class _FakeCellEspecificacoes:
    def __init__(self, value, row):
        self.value = value
        self.row = row


class _FakeWorksheetSemEspecificacoes:
    """Worksheet cujo `iter_rows` NUNCA encontra o texto-alvo "ESPECIFICAÇÕES
    TÉCNICAS..." na faixa 50-150 (simula uma ficha sem esse cabeçalho) — só
    para exercitar o FALLBACK de `_find_variable_specs_start_row`."""

    def iter_rows(self, min_row, max_row, min_col, max_col):
        for r in range(min_row, max_row + 1):
            yield (_FakeCellEspecificacoes(None, r),)


class _FakeWorksheetComEspecificacoes:
    """Worksheet cujo `iter_rows` ACHA o texto-alvo na linha `linha_alvo` —
    para confirmar que o caminho "encontrou dinamicamente" continua
    funcionando (não é exigido explicitamente pelo checkpoint, mas cobre o
    contraste com o fallback acima)."""

    _ALVO = "ESPECIFICAÇÕES TÉCNICAS - INDIQUE AS ESPECIFICAÇÕES TÉCNICAS NO ESPAÇO LIVRE ABAIXO"

    def __init__(self, linha_alvo):
        self._linha_alvo = linha_alvo

    def iter_rows(self, min_row, max_row, min_col, max_col):
        for r in range(min_row, max_row + 1):
            valor = self._ALVO if r == self._linha_alvo else None
            yield (_FakeCellEspecificacoes(valor, r),)


def _make_analyzer():
    return analyzer_backend.DatasheetAnalyzer.__new__(analyzer_backend.DatasheetAnalyzer)


def test_find_variable_specs_start_row_fallback_devolve_linha_specs_ficha():
    analyzer = _make_analyzer()
    ws = _FakeWorksheetSemEspecificacoes()

    resultado = analyzer._find_variable_specs_start_row(ws)

    assert resultado == 79
    assert resultado == sigft_config.LINHA_SPECS_FICHA


def test_find_variable_specs_start_row_encontra_dinamicamente_quando_o_texto_existe():
    analyzer = _make_analyzer()
    ws = _FakeWorksheetComEspecificacoes(linha_alvo=75)

    assert analyzer._find_variable_specs_start_row(ws) == 75 + 4


# =============================================================================
# 8. AutoSpecCore.analyze_sheet — as 2 linhas corrigidas (.split(":")[0]).
# =============================================================================

def test_mecanica_de_resolucao_da_celula_bate_com_o_valor_unico_do_autospec_original():
    # Isolamento mínimo pedido pelo checkpoint: a expressão
    # `CONFIG_MAP[chave]["range"].split(":")[0]` (agora necessária nas 2
    # linhas de analyze_sheet) resolve para o MESMO endereço de célula que o
    # autospec original guardava direto em "range".
    for chave in ("texto_breve_material", "fabricante"):
        resolvido = ficha_layout.CONFIG_MAP[chave]["range"].split(":")[0]
        assert resolvido == _OLD_AUTOSPEC_CONFIG_MAP[chave]["range"]

    assert ficha_layout.CONFIG_MAP["texto_breve_material"]["range"].split(":")[0] == "H6"
    assert ficha_layout.CONFIG_MAP["fabricante"]["range"].split(":")[0] == "L10"


class _FakeCellAutospec:
    def __init__(self, value=None):
        self.value = value


class _FakeWorksheetAnalyzeSheet:
    """Worksheet mínima para rodar `AutoSpecCore.analyze_sheet` DE VERDADE
    (via `openpyxl.load_workbook` monkeypatchado), sem o pacote openpyxl
    real. `max_row` fica ABAIXO de `VARIAVEIS_SPECS["start_row"]` (79) de
    propósito, para que o loop de variáveis dinâmicas (fora do escopo deste
    checkpoint) nem comece — só o "Mapeamento Estático" (CONFIG_MAP) roda.

    `__getitem__` LEVANTA se chamado com um endereço de RANGE (contém ":")
    -- é o canário desta suíte: se as 2 linhas de `analyze_sheet` alguma
    vez pararem de fazer `.split(":")[0]` antes de indexar a worksheet
    (regressão do fix do CP 2.4), este fake denuncia imediatamente, em vez
    de silenciosamente devolver algo incorreto."""

    def __init__(self, valores, max_row=10):
        self._valores = valores
        self.max_row = max_row

    def __getitem__(self, coordinate):
        if ":" in coordinate:
            raise AssertionError(
                f"ws[{coordinate!r}] chamado com um RANGE completo — "
                "esperava-se .split(':')[0] antes de indexar a worksheet "
                "(mecânica corrigida no CP 2.4)."
            )
        return _FakeCellAutospec(self._valores.get(coordinate))


class _FakeWorkbookAnalyzeSheet:
    def __init__(self, ws):
        self.sheetnames = ["Ficha Técnica Padrão"]
        self._ws = ws

    def __getitem__(self, nome_aba):
        assert nome_aba == "Ficha Técnica Padrão"
        return self._ws


def _make_autospec_core():
    return autospec_backend.AutoSpecCore.__new__(autospec_backend.AutoSpecCore)


def test_analyze_sheet_le_texto_breve_material_e_fabricante_com_range_completo(monkeypatch):
    ws = _FakeWorksheetAnalyzeSheet({"H6": "Motor elétrico trifásico", "L10": "Fabricante XYZ"})
    wb = _FakeWorkbookAnalyzeSheet(ws)

    def _fake_load_workbook(caminho, **kwargs):
        return wb

    monkeypatch.setattr(autospec_backend.openpyxl, "load_workbook", _fake_load_workbook)

    core = _make_autospec_core()
    wb_retornado, missing, txt_brv, fab, desc_comp, cod_mat = core.analyze_sheet(
        "qualquer/pasta/4500063671.1234_ficha.xlsx", status_pmib_path=None
    )

    assert txt_brv == "Motor elétrico trifásico"
    assert fab == "Fabricante XYZ"
    assert wb_retornado is wb
    assert desc_comp == "" and cod_mat == ""  # status_pmib_path=None -> get_pmib_data não chamado


def test_analyze_sheet_trata_texto_breve_e_fabricante_vazios_como_faltantes(monkeypatch):
    # Nenhum valor nas células H6/L10 -> "texto_breve_material"/"fabricante"
    # entram em missing (mesma mecânica de is_empty já existente).
    ws = _FakeWorksheetAnalyzeSheet({})
    wb = _FakeWorkbookAnalyzeSheet(ws)
    monkeypatch.setattr(autospec_backend.openpyxl, "load_workbook", lambda caminho, **kw: wb)

    core = _make_autospec_core()
    _, missing, txt_brv, fab, _, _ = core.analyze_sheet("ficha_sem_dados.xlsx", status_pmib_path=None)

    assert txt_brv == "" and fab == ""
    assert "texto_breve_material" in missing
    assert "fabricante" in missing
    assert missing["texto_breve_material"]["ref"] == "H6:P6"  # ref guardado é o range COMPLETO
    assert missing["fabricante"]["ref"] == "L10:N10"


# =============================================================================
# 9. AutoSpecCore.fill_save — robusto ao `ref` com range completo.
# =============================================================================

class _FakeCellFillSave:
    def __init__(self):
        self.value = None
        self.font = None


class _FakeWorksheetFillSave:
    def __init__(self):
        self.cells_tocadas = {}

    def __getitem__(self, coordinate):
        if coordinate not in self.cells_tocadas:
            self.cells_tocadas[coordinate] = _FakeCellFillSave()
        return self.cells_tocadas[coordinate]


class _FakeWorkbookFillSave:
    def __init__(self, ws):
        self._ws = ws
        self.paths_salvos = []

    def __getitem__(self, nome_aba):
        assert nome_aba == "Ficha Técnica Padrão"
        return self._ws

    def save(self, path):
        self.paths_salvos.append(path)


def test_fill_save_escreve_na_primeira_celula_quando_ref_e_o_range_completo(tmp_path):
    # info['ref'] vem de missing[...]["ref"], que agora guarda cfg["range"]
    # CRU (o range completo do CONFIG_MAP novo) para campos "text" -- ver
    # analyze_sheet, "Mapeamento Estático". fill_save já fazia
    # `info['ref'].split(':')[0]` antes deste checkpoint (linha inalterada);
    # este teste confirma que continua resolvendo a célula certa.
    ws = _FakeWorksheetFillSave()
    wb = _FakeWorkbookFillSave(ws)
    core = _make_autospec_core()

    ref_range_completo = ficha_layout.CONFIG_MAP["embalagem_transporte"]["range"]
    assert ref_range_completo == "M42:V44"  # sanity check da fixture usada

    missing = {
        "embalagem_transporte": {
            "type": "text",
            "desc": ficha_layout.CONFIG_MAP["embalagem_transporte"]["desc"],
            "ref": ref_range_completo,
        }
    }
    ai_data = {"embalagem_transporte": "Caixa de madeira reforçada, uso interno"}

    caminho = str(tmp_path / "4500063671.1234_ficha.xlsx")
    novo_caminho = core.fill_save(wb, caminho, ai_data, missing)

    assert ws["M42"].value == "Caixa de madeira reforçada, uso interno"
    assert ws["M42"].font is not None
    assert "V44" not in ws.cells_tocadas  # nenhuma escrita fora da 1a célula do range
    assert novo_caminho == str(tmp_path / "4500063671.1234_ficha_completed.xlsx")
    assert wb.paths_salvos == [novo_caminho]


def test_fill_save_trata_campo_empilhamento_com_regex_e_ref_de_range_completo(tmp_path):
    # 'empilhamento' tem tratamento especial (extrai só o número via regex)
    # -- confirma que o `ref` de range completo também funciona nesse ramo.
    ws = _FakeWorksheetFillSave()
    wb = _FakeWorkbookFillSave(ws)
    core = _make_autospec_core()

    missing = {
        "empilhamento": {
            "type": "text",
            "desc": ficha_layout.CONFIG_MAP["empilhamento"]["desc"],
            "ref": ficha_layout.CONFIG_MAP["empilhamento"]["range"],  # "J35:L35"
        }
    }
    ai_data = {"empilhamento": "no máximo 12 caixas por pilha"}

    core.fill_save(wb, str(tmp_path / "f.xlsx"), ai_data, missing)

    assert ws["J35"].value == 12
    assert "L35" not in ws.cells_tocadas

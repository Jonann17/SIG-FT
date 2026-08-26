r"""Analyzer: a planilha que ele lê, e os buracos por onde ela escapava.

Todos os casos aqui foram MEDIDOS antes de virar teste, com `.xlsx` de
verdade (openpyxl real, fora da suíte — aqui a suíte stuba o openpyxl, então
a planilha é falsa e o comportamento medido é o mesmo). O que a medição
mostrou:

| Sonda | Medido no código de 2026-08-26 |
|---|---|
| aba ativa não é a da ficha | a MESMA ficha: **100% → 0%** |
| código PMIB gravado como número | descrição nunca encontrada |
| linha em branco no meio das specs | 5 perguntas viram 2, e os pontos por spec INFLAM |
| buraco no meio do `_STATUS_PMIB` | tudo depois do buraco fica invisível |
| nome `a.xlsx.b.xlsx` | vira `a_100%.xlsx.b_100%.xlsx` |

Nenhum deles é hipótese: todos saíram de uma planilha construída e lida.
"""
import re

import pytest

from sigft.core.excel import pmib_codes
from sigft.services import analyzer as analyzer_mod
from sigft.services.analyzer import DatasheetAnalyzer


def _coluna(indice):
    """1 -> 'A'. Sem openpyxl.utils, que está stubado na suíte."""
    letras = ""
    while indice > 0:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _indice(letras):
    n = 0
    for c in letras:
        n = n * 26 + (ord(c) - 64)
    return n


class FakeCell:
    def __init__(self, value=None, row=1, column=1):
        self.value = value
        self.row = row
        self.column = column
        self.font = None


class FakeWorksheet:
    """Duck-type do que o analyzer usa: `ws[ref]`, `iter_rows`, `cell`,
    `max_row`, `max_column`."""

    def __init__(self, title="Ficha", valores=None):
        self.title = title
        self._celulas = {}
        for ref, valor in (valores or {}).items():
            self[ref].value = valor

    def __getitem__(self, ref):
        casamento = re.fullmatch(r"([A-Z]+)(\d+)", ref)
        if not casamento:
            raise KeyError(ref)
        col, linha = casamento.group(1), int(casamento.group(2))
        if ref not in self._celulas:
            self._celulas[ref] = FakeCell(None, linha, _indice(col))
        return self._celulas[ref]

    def cell(self, row, column):
        return self[f"{_coluna(column)}{row}"]

    @property
    def max_row(self):
        return max([c.row for c in self._celulas.values() if c.value is not None] or [1])

    @property
    def max_column(self):
        return max([c.column for c in self._celulas.values() if c.value is not None] or [1])

    def iter_rows(self, min_row=1, max_row=None, min_col=1, max_col=1):
        for r in range(min_row, (self.max_row if max_row is None else max_row) + 1):
            yield tuple(self[f"{_coluna(c)}{r}"] for c in range(min_col, max_col + 1))


class FakeWorkbook:
    def __init__(self, abas, ativa=0):
        self.worksheets = list(abas)
        self._ativa = ativa

    @property
    def active(self):
        return self.worksheets[self._ativa]

    def save(self, caminho):
        self.salvo_em = caminho


def _analyzer():
    return DatasheetAnalyzer.__new__(DatasheetAnalyzer)


TITULO_SPECS = ("ESPECIFICAÇÕES TÉCNICAS - INDIQUE AS ESPECIFICAÇÕES TÉCNICAS "
                "NO ESPAÇO LIVRE ABAIXO")


def _aba_de_ficha(titulo="Ficha", n_specs=3, buraco=None, linha_titulo=60):
    from sigft.core.rpa.ficha_layout import CONFIG_MAP, VARIAVEIS_SPECS

    valores = {}
    for chave, cfg in CONFIG_MAP.items():
        if cfg["type"] == "cell":
            valores[cfg["range"].split(":")[0]] = f"valor de {chave}"
        else:
            valores[cfg["cells"][0]] = "X"
    valores[f"B{linha_titulo}"] = TITULO_SPECS
    inicio = linha_titulo + 4
    col_p = VARIAVEIS_SPECS["pergunta_range"].split(":")[0]
    col_r = VARIAVEIS_SPECS["resposta_range"].split(":")[0]
    for i in range(n_specs):
        if buraco is not None and i == buraco:
            continue
        valores[f"{col_p}{inicio + i}"] = f"Pergunta {i + 1}?"
        valores[f"{col_r}{inicio + i}"] = f"Resposta {i + 1}"
    return FakeWorksheet(titulo, valores)


# =============================================================================
# A. Qual aba o analyzer lê
# =============================================================================
def test_aba_ativa_errada_nao_faz_a_ficha_valer_zero():
    """MEDIDO: a mesma ficha caía de 100% para 0% só porque o usuário salvou
    o arquivo com outra aba selecionada. Todo campo era marcado 'FORNECER'
    numa aba vazia, e a ficha ia para FT_bad."""
    ficha = _aba_de_ficha("FICHA")
    instrucoes = FakeWorksheet("Instruções", {"A1": "Leia antes de preencher"})
    wb = FakeWorkbook([instrucoes, ficha], ativa=0)

    assert _analyzer()._aba_da_ficha(wb) is ficha


def test_aba_unica_continua_sendo_a_escolhida():
    ficha = _aba_de_ficha()
    assert _analyzer()._aba_da_ficha(FakeWorkbook([ficha])) is ficha


def test_ficha_em_branco_cai_na_aba_ativa_como_sempre():
    """Um template ainda não preenchido não 'parece ficha' por nenhum sinal.
    Aí o comportamento tem de ser o de hoje — nunca pior."""
    vazia_a = FakeWorksheet("A")
    vazia_b = FakeWorksheet("B")
    wb = FakeWorkbook([vazia_a, vazia_b], ativa=1)
    assert _analyzer()._aba_da_ficha(wb) is vazia_b


def test_workbook_sem_worksheets_nao_quebra():
    class Estranho:
        active = "a-aba-ativa"
    assert _analyzer()._aba_da_ficha(Estranho()) == "a-aba-ativa"


def test_empate_prefere_a_aba_ativa():
    """Duas abas igualmente preenchidas: a escolha do usuário desempata."""
    a, b = _aba_de_ficha("Copia"), _aba_de_ficha("Original")
    assert _analyzer()._aba_da_ficha(FakeWorkbook([a, b], ativa=1)) is b


# =============================================================================
# B. Achar a descrição no _STATUS_PMIB
# =============================================================================
def _status_pmib(linhas):
    valores = {"A1": "CÓDIGO PMIB", "B1": "DESCRIÇÃO"}
    for i, (codigo, desc) in enumerate(linhas, start=2):
        if codigo is not None:
            valores[f"A{i}"] = codigo
        if desc is not None:
            valores[f"B{i}"] = desc
    return FakeWorksheet("STATUS", valores)


def test_codigo_gravado_como_NUMERO_encontra_a_descricao():
    """MEDIDO: o Excel guarda `4500063671.1050` como float e devolve
    `4500063671.105` — o zero à direita evapora, e a busca por '1050'
    falhava. `normalize_pmib` (implementação única do CP 1.2) restaura."""
    ws = _status_pmib([(4500063671.1050, "ACOPLADOR MODBUS TCP")])
    assert _analyzer()._find_pmib_description("1050", ws) == "ACOPLADOR MODBUS TCP"


def test_apostrofo_do_excel_nao_atrapalha():
    ws = _status_pmib([("'4500063671.0071", "VALVULA DE RETENCAO")])
    assert _analyzer()._find_pmib_description("0071", ws) == "VALVULA DE RETENCAO"


def test_coluna_so_com_o_sufixo_continua_funcionando():
    ws = _status_pmib([("0071", "SO O SUFIXO")])
    assert _analyzer()._find_pmib_description("0071", ws) == "SO O SUFIXO"


def test_buraco_no_meio_do_status_pmib_nao_esconde_o_resto():
    """MEDIDO: `if not c_desc.value: break` parava na primeira linha sem
    descrição. Uma linha de separação no meio tornava invisível TODO o
    resto da planilha — e o analyzer dizia 'PMIB não encontrado'."""
    ws = _status_pmib([
        ("4500063671.0001", "PRIMEIRO"),
        (None, None),
        ("4500063671.0071", "DEPOIS DO BURACO"),
    ])
    assert _analyzer()._find_pmib_description("0071", ws) == "DEPOIS DO BURACO"


def test_codigo_que_nao_existe_continua_devolvendo_nada():
    ws = _status_pmib([("4500063671.0001", "PRIMEIRO")])
    assert _analyzer()._find_pmib_description("9999", ws) is None


def test_o_fim_de_verdade_da_lista_encerra_a_busca():
    """Tolerar buraco não pode virar varrer a planilha inteira: depois de
    muitas linhas vazias seguidas, a lista acabou mesmo."""
    ws = _status_pmib([("4500063671.0001", "PRIMEIRO")])
    # Um rodapé lá embaixo: sem ele `max_row` seria 2 e o teste passaria
    # sozinho, medindo nada.
    ws["A9000"].value = "Gerado em 26/08/2026"
    chamadas = []
    original = ws.iter_rows

    def contando(*a, **k):
        for linha in original(*a, **k):
            chamadas.append(linha[0].row)
            yield linha

    ws.iter_rows = contando
    _analyzer()._find_pmib_description("9999", ws)
    assert max(chamadas) < 500, f"varreu ate a linha {max(chamadas)}"


# =============================================================================
# C. Contar as especificações técnicas
# =============================================================================
def test_pergunta_em_branco_no_meio_nao_trunca_a_lista():
    """MEDIDO: 5 perguntas em 6 linhas viravam 2. As outras 3 sumiam da
    análise — e ninguém era avisado."""
    ws = _aba_de_ficha(n_specs=6, buraco=2)
    perguntas = _analyzer()._ler_specs(ws, 64)
    assert len(perguntas) == 5


def test_os_pontos_por_spec_nao_inflam_por_causa_do_buraco():
    """A metade perversa do bug anterior: com menos specs contadas, cada uma
    valia MAIS. A ficha com buraco ficava mais fácil de aprovar que a
    completa."""
    completa = _analyzer()._ler_specs(_aba_de_ficha(n_specs=6), 64)
    com_buraco = _analyzer()._ler_specs(_aba_de_ficha(n_specs=6, buraco=2), 64)
    assert len(completa) == 6
    assert len(com_buraco) == 5


def test_o_fim_da_lista_de_specs_e_respeitado():
    """Depois das specs a planilha continua (rodapé, assinaturas). Tolerar
    buraco não pode fazer o analyzer inventar perguntas."""
    ws = _aba_de_ficha(n_specs=3)
    assert len(_analyzer()._ler_specs(ws, 64)) == 3


def test_spec_sem_resposta_entra_na_lista_marcada_como_vazia():
    """Pergunta sem resposta é justamente o que o analyzer existe para
    apontar — ela não pode ser filtrada fora."""
    from sigft.core.rpa.ficha_layout import VARIAVEIS_SPECS
    col_r = VARIAVEIS_SPECS["resposta_range"].split(":")[0]
    ws = _aba_de_ficha(n_specs=3)
    ws[f"{col_r}65"].value = None
    specs = _analyzer()._ler_specs(ws, 64)
    assert len(specs) == 3
    assert specs[1]["resposta"] is None


# =============================================================================
# D. O nome do arquivo de saída
# =============================================================================
@pytest.mark.parametrize("entrada,esperado", [
    ("4500063671.0071.xlsx", "4500063671.0071_87%.xlsx"),
    ("ficha.xlsx.revisao.xlsx", "ficha.xlsx.revisao_87%.xlsx"),
    ("sem_extensao", "sem_extensao_87%.xlsx"),
])
def test_so_a_extensao_final_vira_o_nome_com_a_nota(entrada, esperado):
    """MEDIDO: `.replace('.xlsx', ...)` trocava TODAS as ocorrências —
    `ficha.xlsx.revisao.xlsx` saía como `ficha_87%.xlsx.revisao_87%.xlsx`."""
    assert analyzer_mod.nome_com_a_nota(entrada, 87) == esperado


# =============================================================================
# E. O erro da IA deixa de morrer na janela preta
# =============================================================================
def test_erro_da_ia_fica_registrado_para_a_tela_ver():
    """Hoje o motivo da falha vai para `print`, que no app empacotado não tem
    para onde ir. A tela mostrava só a nota inflada."""
    an = _analyzer()

    class LLMQuebrado:
        def generate(self, *a, **k):
            raise RuntimeError("401 chave invalida")

    an._llm = LLMQuebrado()
    assert an._call_gemini_api("prompt") is None
    assert "401 chave invalida" in (an.ultimo_erro_ia or "")


# =============================================================================
# F. A aba do _STATUS_PMIB
# =============================================================================
def test_status_pmib_com_aba_ativa_errada_ainda_acha_os_cabecalhos():
    """Mesmo bug do `wb.active` da ficha, do outro lado: o frontend fazia
    `pmib_sheet = wb.active`. Com a aba errada, `_find_header_columns` não
    acha as colunas e TODA ficha do lote perde o enriquecimento de descrição
    -- silenciosamente, com um '[AVISO] PMIB não encontrado' por ficha que
    parece problema da planilha do usuário."""
    capa = FakeWorksheet("Capa", {"A1": "Relatorio gerado automaticamente"})
    dados = _status_pmib([("4500063671.0071", "VALVULA")])
    wb = FakeWorkbook([capa, dados], ativa=0)

    assert analyzer_mod.aba_do_status_pmib(wb) is dados


def test_status_pmib_de_uma_aba_so_continua_igual():
    dados = _status_pmib([("4500063671.0071", "VALVULA")])
    assert analyzer_mod.aba_do_status_pmib(FakeWorkbook([dados])) is dados


def test_status_pmib_sem_cabecalho_nenhum_cai_na_ativa():
    a = FakeWorksheet("A", {"A1": "nada a ver"})
    b = FakeWorksheet("B", {"A1": "tambem nao"})
    assert analyzer_mod.aba_do_status_pmib(FakeWorkbook([a, b], ativa=1)) is b


# =============================================================================
# G. Dois defeitos achados pela sonda de .xlsx real, não pela suíte
# =============================================================================
def _rodar(an, ws, **kw):
    wb = FakeWorkbook([ws])
    kw.setdefault("pmib_sheet", None)
    import sigft.services.analyzer as mod
    original = mod.openpyxl.load_workbook
    mod.openpyxl.load_workbook = lambda *a, **k: wb
    try:
        return list(an.processar_planilha(
            input_filepath="x.xlsx", root_output_dir="/tmp/naosalva",
            subfolder_name="s", original_filename="x.xlsx",
            score_threshold=0, custom_weights=None,
            max_variable_points=45.0, callback_manual_desc=None, **kw))
    finally:
        mod.openpyxl.load_workbook = original


def test_analyzer_criado_por_new_nao_quebra_no_meio_da_ficha():
    """`DatasheetAnalyzer.__new__(...)` é o idioma dos testes deste repositório
    (ver test_ficha_layout.py) — e era o que a sonda usava. Ler
    `self.ultimo_erro_ia` direto rebentava com AttributeError no meio do
    processamento, depois de a ficha já ter sido marcada."""
    an = _analyzer()
    an._call_gemini_api = lambda prompt: None
    linhas = _rodar(an, _aba_de_ficha())
    assert any("Nota Normalizada" in l for l in linhas)


def test_ficha_sem_nada_para_a_IA_nao_leva_susto_de_nota_inflada():
    """`ai_res` nasce None. Quando não há NADA para a IA validar, o código
    caía no mesmo `if not ai_res:` e gritava 'a IA NÃO respondeu / nota
    INFLADA' — um susto falso, na ficha que está mais correta."""
    an = _analyzer()
    chamou = []
    an._call_gemini_api = lambda prompt: chamou.append(1)

    from sigft.core.rpa.ficha_layout import CONFIG_MAP
    ws = _aba_de_ficha(n_specs=0)
    for chave, cfg in CONFIG_MAP.items():          # esvazia os campos de IA
        if cfg.get("validation") == "ai":
            ws[cfg["range"].split(":")[0]].value = None

    linhas = _rodar(an, ws)
    assert not chamou, "a IA nem devia ter sido consultada"
    assert any("Nada para validar" in l for l in linhas)
    assert not any("INFLADA" in l for l in linhas)


def test_quando_a_IA_FOI_consultada_e_falhou_o_aviso_continua():
    """O contrário do teste acima: o aviso é essencial e não pode sumir."""
    an = _analyzer()
    an._call_gemini_api = lambda prompt: None
    linhas = _rodar(an, _aba_de_ficha())
    assert any("INFLADA" in l for l in linhas)

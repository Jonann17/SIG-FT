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
    # O ponto do teste é chegar INTEIRO ao fim do ramo de falha de IA — é lá
    # que mora o acesso a `ultimo_erro_ia`, que rebentava. Depois da decisão
    # de 2026-08-26 esse ramo termina abortando a ficha, então o marcador de
    # "chegou ao fim" é a mensagem de PULADA, não mais a nota.
    assert any("PULADA" in l for l in linhas)


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


# =============================================================================
# H. As quatro decisões do usuário (2026-08-26)
# =============================================================================
def _rodar2(an, ws_gravavel, ws_valores=None, **kw):
    """Como `_rodar`, mas devolve workbooks DIFERENTES conforme `data_only` —
    é assim que o Excel se comporta, e é o ponto da decisão nº 1."""
    import sigft.services.analyzer as mod
    wb_grav = FakeWorkbook([ws_gravavel])
    wb_val = FakeWorkbook([ws_valores if ws_valores is not None else ws_gravavel])
    original = mod.openpyxl.load_workbook
    mod.openpyxl.load_workbook = (
        lambda *a, **k: wb_val if k.get("data_only") else wb_grav)
    kw.setdefault("pmib_sheet", None)
    kw.setdefault("callback_manual_desc", None)
    # 101 de propósito: força o ramo `wb.save`, que o FakeWorkbook registra.
    # Com threshold baixo o ramo é `shutil.copy2` de um arquivo que não
    # existe, e o teste "não salvou" passaria pelo motivo errado.
    kw.setdefault("score_threshold", 101)
    try:
        linhas = list(an.processar_planilha(
            input_filepath="4500063671.0071.xlsx", root_output_dir="/tmp/naosalva",
            subfolder_name="s", original_filename="4500063671.0071.xlsx",
            custom_weights=None, max_variable_points=45.0, **kw))
        return linhas, wb_grav
    finally:
        mod.openpyxl.load_workbook = original


def _nota(linhas):
    return next((int(l.split("Nota Normalizada: ")[1].split("%")[0])
                 for l in linhas if "Nota Normalizada" in l), None)


# --- Decisão 1: fórmula lida pelo VALOR -------------------------------------
def test_formula_chega_a_IA_como_valor_e_nao_como_texto_da_formula():
    """MEDIDO antes: o campo `fabricante` com `=1+1` fazia a IA receber a
    string `'=1+1'` como nome do fabricante."""
    from sigft.core.rpa.ficha_layout import CONFIG_MAP
    alvo = CONFIG_MAP["fabricante"]["range"].split(":")[0]

    grav = _aba_de_ficha()
    grav[alvo].value = "=CONCATENAR(A1;B1)"
    valores = _aba_de_ficha()
    valores[alvo].value = "WAGO"

    an = _analyzer()
    visto = {}
    an._build_gemini_prompt = lambda ctx, f, v: visto.update(ctx=ctx) or "prompt"
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    _rodar2(an, grav, valores)
    assert visto["ctx"]["fabricante"] == "WAGO"


def test_formula_SEM_valor_calculado_avisa_em_vez_de_decidir_sozinho():
    """`data_only=True` devolve o valor em CACHE. Ficha nunca aberta no Excel
    não tem cache, e aí o valor é `None` — tratar como vazio marcaria
    'FORNECER' por cima de uma fórmula que o usuário escreveu. Avisa, e
    mantém o comportamento de hoje."""
    from sigft.core.rpa.ficha_layout import CONFIG_MAP
    alvo = CONFIG_MAP["fabricante"]["range"].split(":")[0]

    grav = _aba_de_ficha()
    grav[alvo].value = "=CONCATENAR(A1;B1)"
    valores = _aba_de_ficha()
    valores[alvo].value = None            # sem cache

    an = _analyzer()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    linhas, _ = _rodar2(an, grav, valores)
    assert any("formula" in l.lower() and "Excel" in l for l in linhas)
    assert grav[alvo].value == "=CONCATENAR(A1;B1)", "nao pode escrever por cima"


def test_a_marcacao_FORNECER_vai_no_workbook_QUE_SERA_SALVO():
    """A armadilha da leitura dupla: se 'FORNECER' for escrito no workbook
    `data_only`, o arquivo salvo sai **sem marcação nenhuma** — e o módulo
    inteiro perde o sentido."""
    from sigft.core.rpa.ficha_layout import CONFIG_MAP
    alvo = next(c["range"].split(":")[0] for c in CONFIG_MAP.values()
                if c["type"] == "cell" and c.get("validation") == "simple")

    grav, valores = _aba_de_ficha(), _aba_de_ficha()
    grav[alvo].value = None
    valores[alvo].value = None

    an = _analyzer()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    _rodar2(an, grav, valores)
    assert grav[alvo].value == "FORNECER"


# --- Decisão 2: renormalizar quando não há specs ----------------------------
def test_ficha_sem_specs_com_tudo_preenchido_chega_a_100():
    """MEDIDO antes: teto de 55%, porque os 45 pontos das variáveis entravam
    no denominador mesmo não existindo variável nenhuma."""
    an = _analyzer()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    linhas, _ = _rodar2(an, _aba_de_ficha(n_specs=0))
    assert _nota(linhas) == 100


def test_o_console_avisa_que_renormalizou():
    an = _analyzer()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    linhas, _ = _rodar2(an, _aba_de_ficha(n_specs=0))
    assert any("sem especificacoes" in l.lower() or "sem especificações" in l.lower()
               for l in linhas)


def test_ficha_COM_specs_continua_normalizando_sobre_o_total_de_sempre():
    an = _analyzer()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    linhas, _ = _rodar2(an, _aba_de_ficha(n_specs=3))
    assert _nota(linhas) == 100
    assert any("100.0/100.0" in l for l in linhas)


# --- Decisão 3: a IA fora do ar ABORTA a ficha ------------------------------
def test_ia_fora_do_ar_nao_gera_arquivo_nenhum():
    """Decisão do usuário: sem julgamento da IA não há nota confiável, e um
    arquivo com nota que não vale é pior que arquivo nenhum."""
    an = _analyzer()
    an._call_gemini_api = lambda p: None
    linhas, wb = _rodar2(an, _aba_de_ficha())
    assert not hasattr(wb, "salvo_em")
    assert not any("Salvo" in l for l in linhas)


def test_ia_fora_do_ar_devolve_False_para_quem_chamou():
    an = _analyzer()
    an._call_gemini_api = lambda p: None
    ger = an.processar_planilha  # noqa: F841  (documenta a intenção)

    import sigft.services.analyzer as mod
    wb = FakeWorkbook([_aba_de_ficha()])
    original = mod.openpyxl.load_workbook
    mod.openpyxl.load_workbook = lambda *a, **k: wb
    try:
        it = an.processar_planilha(
            input_filepath="x.xlsx", root_output_dir="/tmp/naosalva",
            subfolder_name="s", original_filename="x.xlsx", pmib_sheet=None,
            score_threshold=0, custom_weights=None, max_variable_points=45.0,
            callback_manual_desc=None)
        resultado = "nao terminou"
        while True:
            try:
                next(it)
            except StopIteration as fim:
                resultado = fim.value
                break
    finally:
        mod.openpyxl.load_workbook = original
    assert resultado is False


def test_ia_fora_do_ar_diz_o_motivo_e_que_a_ficha_foi_pulada():
    an = _analyzer()

    class LLMQuebrado:
        def generate(self, *a, **k):
            raise RuntimeError("429 cota diaria estourada")

    an._llm = LLMQuebrado()
    an.ultimo_erro_ia = None
    linhas, _ = _rodar2(an, _aba_de_ficha())
    texto = "\n".join(linhas)
    assert "429 cota diaria estourada" in texto
    assert "pulada" in texto.lower() or "nao foi analisada" in texto.lower()


def test_ia_respondendo_continua_salvando_como_sempre():
    an = _analyzer()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    linhas, wb = _rodar2(an, _aba_de_ficha())
    assert any("Salvo" in l for l in linhas)
    assert hasattr(wb, "salvo_em")


# --- Decisão 4: o callback de descrição manual deixa de ser morto ----------
def test_callback_manual_desc_e_chamado_quando_o_pmib_nao_esta_na_planilha():
    an = _analyzer()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    perguntado = []
    linhas, _ = _rodar2(
        an, _aba_de_ficha(),
        pmib_sheet=_status_pmib([("4500063671.9999", "OUTRO MATERIAL")]),
        callback_manual_desc=lambda arquivo, codigo: (
            perguntado.append((arquivo, codigo)) or "VALVULA INFORMADA A MAO"),
    )
    assert perguntado, "o callback existe para ser usado"


# =============================================================================
# I. A caixa de diálogo da descrição manual (tela — por AST)
# =============================================================================
import ast
import pathlib

FRONTEND = pathlib.Path(__file__).resolve().parents[1] / "frontend.py"


def _classe_analyzer():
    arvore = ast.parse(FRONTEND.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloAnalyzer":
            return no
    pytest.fail("class ModuloAnalyzer sumiu do frontend.py")


def _metodo_analyzer(nome):
    for no in _classe_analyzer().body:
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    pytest.fail(f"metodo {nome} nao existe em ModuloAnalyzer")


def test_a_tela_passa_um_callback_de_VERDADE_e_nao_um_lambda_morto():
    """Era `callback_manual_desc=lambda f, c: None` — o parâmetro existia, era
    chamado, e nunca fazia nada."""
    metodo = _metodo_analyzer("_run_backend")
    assert "_perguntar_descricao" in ast.dump(metodo)
    # Nenhum lambda que devolve `None` fixo continua sendo passado ali. Olha
    # a ÁRVORE do método, e não o texto do arquivo: a string
    # "lambda f, c: None" ainda aparece no docstring de
    # `_perguntar_descricao`, contando de onde isto veio.
    for no in ast.walk(metodo):
        if isinstance(no, ast.Lambda):
            corpo = no.body
            assert not (isinstance(corpo, ast.Constant) and corpo.value is None), \
                "voltou o callback morto"


def test_o_dialogo_abre_na_THREAD_DA_UI_e_nao_na_do_processamento():
    """`_run_backend` roda em `threading.Thread`. Abrir janela tkinter de
    fora da thread principal é o caminho curto para travar o app. O projeto
    já tem o padrão certo em `_worker_web`: `self.after(0, ...)` para abrir e
    um `Event` para esperar."""
    fonte = ast.dump(_metodo_analyzer("_perguntar_descricao"))
    assert "'after'" in fonte or '"after"' in fonte, "a janela precisa abrir via self.after"
    assert "Event" in fonte, "a thread do backend precisa esperar a resposta"


def test_cancelar_para_de_perguntar_no_resto_do_lote():
    """Um lote de 50 fichas com PMIB desconhecido não pode virar 50 caixas de
    diálogo obrigatórias. Cancelar é a saída."""
    fonte = ast.dump(_metodo_analyzer("_perguntar_descricao"))
    assert "_parar_de_perguntar_desc" in fonte

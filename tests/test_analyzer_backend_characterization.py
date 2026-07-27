r"""
Teste de caracterização (CP 0.1) — analyzer_backend.DatasheetAnalyzer.extract_pmib_code
(analyzer_backend.py:105-107 ATÉ o CP 1.2).

    def extract_pmib_code(self, filename):
        match = re.search(r"\d{10}\.(\d{4})", filename)
        return match.group(1) if match else None

Instância criada via `__new__` para não rodar `__init__` (que chamaria
`genai.configure(...)` se `api_key` fosse truthy).

ATUALIZAÇÃO INTENCIONAL (CP 1.2): a partir do Checkpoint 1.2 do plano de
refatoração, `DatasheetAnalyzer.extract_pmib_code` passou a DELEGAR para
`sigft.core.excel.pmib_codes.extract_pmib_code` (`return
pmib_codes.extract_pmib_code(filename)`), que aplica `os.path.basename()`
ANTES do regex — o comportamento que já era correto em
`autospec_backend.AutoSpecCore.extract_pmib_code` (autospec_backend.py:178-181,
caracterizado em tests/test_autospec_backend_characterization.py). Isso
CORRIGE o bug latente registrado no CP 0.1 (regex rodando sobre o caminho
inteiro, "vazando" um match do DIRETÓRIO em vez do ARQUIVO) — decisão do
arquiteto documentada em docs/refatoracao/PLANO_REFATORACAO.md (Fase 1 ->
CP 1.2) e docs/refatoracao/PENDENCIAS.md. O teste
`test_regex_aplicado_no_caminho_inteiro_nao_so_no_basename` (que
caracterizava o BUG) foi substituído abaixo por
`test_regex_usa_basename_bug_do_diretorio_foi_corrigido_no_cp_1_2` (que
caracteriza a CORREÇÃO) — mesmo cenário de entrada, resultado esperado
diferente. Todos os outros testes deste arquivo permanecem inalterados: são
a prova de que a migração para `pmib_codes.extract_pmib_code` preserva o
comportamento em todo o resto do domínio de entrada (a única saída que muda
é a deste um cenário, que era precisamente o bug).
"""
from analyzer_backend import DatasheetAnalyzer


def _make_analyzer():
    return DatasheetAnalyzer.__new__(DatasheetAnalyzer)


def test_extrai_4_ultimos_digitos_do_codigo_pmib():
    analyzer = _make_analyzer()
    nome = "4500063671.1234_STATUS_PMIB.xlsx"
    assert analyzer.extract_pmib_code(nome) == "1234"


def test_retorna_none_sem_padrao_pmib():
    analyzer = _make_analyzer()
    assert analyzer.extract_pmib_code("ficha_sem_codigo.xlsx") is None


def test_retorna_none_para_string_vazia():
    analyzer = _make_analyzer()
    assert analyzer.extract_pmib_code("") is None


def test_decimal_com_menos_de_4_digitos_nao_casa():
    analyzer = _make_analyzer()
    assert analyzer.extract_pmib_code("4500063671.12_curto.xlsx") is None


def test_decimal_com_mais_de_4_digitos_usa_so_os_4_primeiros():
    # Peculiaridade: \d{4} captura EXATAMENTE 4 dígitos; dígitos extras depois
    # do 4º são ignorados pelo match (o grupo não é ganancioso além de {4}).
    analyzer = _make_analyzer()
    resultado = analyzer.extract_pmib_code("4500063671.123456_longo.xlsx")
    assert resultado == "1234"


def test_regex_usa_basename_bug_do_diretorio_foi_corrigido_no_cp_1_2():
    # ANTES do CP 1.2 (bug latente, caracterizado pelo CP 0.1 sob o nome
    # `test_regex_aplicado_no_caminho_inteiro_nao_so_no_basename`): o regex
    # rodava sobre o CAMINHO INTEIRO recebido, sem normalizar para basename.
    # Como o CAMINHO (não só o nome do arquivo) contém outro trecho no
    # formato \d{10}\.\d{4} (o nome da subpasta), o analyzer extraía o
    # código ERRADO (do diretório, não do arquivo).
    #
    # A PARTIR DO CP 1.2: `extract_pmib_code` delega para
    # `sigft.core.excel.pmib_codes.extract_pmib_code`, que aplica
    # `os.path.basename()` ANTES do regex (decisão do arquiteto — ver
    # docstring do topo deste arquivo) — o bug está CORRIGIDO: o código
    # retornado agora é o do ARQUIVO. Ver confirmação cruzada (convergência)
    # em
    # test_autospec_backend_characterization.py::test_convergiu_com_o_analyzer_apos_o_fix_do_cp_1_2.
    analyzer = _make_analyzer()
    caminho = "pasta_saida/9999999999.8888/4500063671.1234_STATUS_PMIB.xlsx"
    assert analyzer.extract_pmib_code(caminho) == "1234"  # correto: código do ARQUIVO, não do diretório

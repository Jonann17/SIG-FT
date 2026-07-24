r"""
Teste de caracterização (CP 0.1) — analyzer_backend.DatasheetAnalyzer.extract_pmib_code
(analyzer_backend.py:105-107).

    def extract_pmib_code(self, filename):
        match = re.search(r"\d{10}\.(\d{4})", filename)
        return match.group(1) if match else None

Instância criada via `__new__` para não rodar `__init__` (que chamaria
`genai.configure(...)` se `api_key` fosse truthy).

Há uma 2ª variante em autospec_backend.AutoSpecCore.extract_pmib_code
(autospec_backend.py:178-181), caracterizada em
tests/test_autospec_backend_characterization.py, com uma divergência real
registrada no teste `test_regex_aplicado_no_caminho_inteiro_nao_so_no_basename`
abaixo.
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


def test_regex_aplicado_no_caminho_inteiro_nao_so_no_basename():
    # PECULIARIDADE / DIVERGÊNCIA vs autospec_backend.AutoSpecCore.extract_pmib_code
    # (autospec_backend.py:178-181): lá o código faz
    # `os.path.basename(input_filepath)` ANTES do regex; aqui
    # (analyzer_backend.py:105-107) o regex roda direto sobre o argumento
    # recebido, sem normalizar para basename. Se o CAMINHO (não só o nome do
    # arquivo) contiver outro trecho no formato \d{10}\.\d{4}, o analyzer
    # pode extrair o código ERRADO (do diretório, não do arquivo). Ver
    # confirmação cruzada em
    # test_autospec_backend_characterization.py::test_diverge_do_analyzer_ao_receber_caminho_com_pmib_no_diretorio.
    analyzer = _make_analyzer()
    caminho = "pasta_saida/9999999999.8888/4500063671.1234_STATUS_PMIB.xlsx"
    assert analyzer.extract_pmib_code(caminho) == "8888"  # !! pega do diretório, não do arquivo

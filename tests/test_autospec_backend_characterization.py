r"""
Teste de caracterização (CP 0.1) — autospec_backend.AutoSpecCore.extract_pmib_code
(autospec_backend.py:178-181).

    def extract_pmib_code(self, input_filepath):
        filename = os.path.basename(input_filepath)
        match = re.search(r"\d{10}\.(\d{4})", filename)
        return match.group(1) if match else None

Esta é a 2ª variante de `extract_pmib_code` mencionada no CP 0.1 (a 1ª é
`analyzer_backend.DatasheetAnalyzer.extract_pmib_code`, caracterizada em
tests/test_analyzer_backend_characterization.py). A diferença -- fazer
`os.path.basename()` antes do regex -- é real e testada explicitamente abaixo.

Instância criada via `__new__`: `AutoSpecCore.__init__` levanta `ValueError` se
`gemini_key` for falsy e, de qualquer forma, instancia `ChatGoogleGenerativeAI`
/ `WebSearcher` / `PDFProcessor` (efeitos colaterais que o teste evita).
"""
from analyzer_backend import DatasheetAnalyzer
from autospec_backend import AutoSpecCore


def _make_autospec():
    return AutoSpecCore.__new__(AutoSpecCore)


def test_extrai_4_ultimos_digitos_do_codigo_pmib():
    autospec = _make_autospec()
    resultado = autospec.extract_pmib_code("4500063671.1234_STATUS_PMIB.xlsx")
    assert resultado == "1234"


def test_retorna_none_sem_padrao_pmib():
    autospec = _make_autospec()
    assert autospec.extract_pmib_code("ficha_sem_codigo.xlsx") is None


def test_usa_basename_do_caminho_recebido():
    autospec = _make_autospec()
    caminho = "C:/pasta/qualquer/4500063671.1234_STATUS_PMIB.xlsx"
    assert autospec.extract_pmib_code(caminho) == "1234"


def test_diverge_do_analyzer_ao_receber_caminho_com_pmib_no_diretorio():
    # DIVERGÊNCIA REGISTRADA (candidato a unificação no CP 1.2):
    # AutoSpecCore.extract_pmib_code faz os.path.basename() ANTES do regex
    # (autospec_backend.py:179), então ignora qualquer trecho \d{10}\.\d{4}
    # que esteja no DIRETÓRIO do caminho -- diferente de
    # DatasheetAnalyzer.extract_pmib_code (analyzer_backend.py:105-107), que
    # roda o regex sobre a string inteira recebida e pode "vazar" um match
    # vindo do diretório em vez do nome do arquivo.
    autospec = _make_autospec()
    analyzer = DatasheetAnalyzer.__new__(DatasheetAnalyzer)
    caminho = "pasta_saida/9999999999.8888/4500063671.1234_STATUS_PMIB.xlsx"

    assert autospec.extract_pmib_code(caminho) == "1234"  # correto: código do ARQUIVO
    assert analyzer.extract_pmib_code(caminho) == "8888"  # captura o do DIRETÓRIO (bug latente)
    assert autospec.extract_pmib_code(caminho) != analyzer.extract_pmib_code(caminho)

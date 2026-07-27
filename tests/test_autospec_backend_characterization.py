r"""
Teste de caracterização (CP 0.1) — autospec_backend.AutoSpecCore.extract_pmib_code
(autospec_backend.py:178-181 ATÉ o CP 1.2).

    def extract_pmib_code(self, input_filepath):
        filename = os.path.basename(input_filepath)
        match = re.search(r"\d{10}\.(\d{4})", filename)
        return match.group(1) if match else None

Esta é a 2ª variante de `extract_pmib_code` mencionada no CP 0.1 (a 1ª é
`analyzer_backend.DatasheetAnalyzer.extract_pmib_code`, caracterizada em
tests/test_analyzer_backend_characterization.py). A diferença -- fazer
`os.path.basename()` antes do regex -- era real até o CP 1.2 (ver
ATUALIZAÇÃO INTENCIONAL abaixo).

Instância criada via `__new__`: `AutoSpecCore.__init__` levanta `ValueError` se
`gemini_key` for falsy e, de qualquer forma, instancia `ChatGoogleGenerativeAI`
/ `WebSearcher` / `PDFProcessor` (efeitos colaterais que o teste evita).

ATUALIZAÇÃO INTENCIONAL (CP 1.2): `AutoSpecCore.extract_pmib_code` passou a
DELEGAR para `sigft.core.excel.pmib_codes.extract_pmib_code` (`return
pmib_codes.extract_pmib_code(input_filepath)`) — o comportamento observável
NÃO muda para este lado (já fazia basename antes do regex; era o lado
"correto" da divergência, escolhido como canônico). O que muda é o
`DatasheetAnalyzer.extract_pmib_code` do analyzer (ver
tests/test_analyzer_backend_characterization.py), que também passou a
delegar para a mesma função e, com isso, CONVERGE para o mesmo resultado do
autospec em todo cenário — inclusive no que antes divergia (PMIB no nome do
diretório). O teste `test_diverge_do_analyzer_ao_receber_caminho_com_pmib_no_diretorio`
(que caracterizava a DIVERGÊNCIA) foi substituído abaixo por
`test_convergiu_com_o_analyzer_apos_o_fix_do_cp_1_2` (que caracteriza a
CONVERGÊNCIA). Os demais testes deste arquivo permanecem inalterados.
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


def test_convergiu_com_o_analyzer_apos_o_fix_do_cp_1_2():
    # ATÉ O CP 1.2 (divergência real, registrada no CP 0.1):
    # AutoSpecCore.extract_pmib_code fazia os.path.basename() ANTES do regex
    # (autospec_backend.py:179), então ignorava qualquer trecho \d{10}\.\d{4}
    # que estivesse no DIRETÓRIO do caminho -- diferente de
    # DatasheetAnalyzer.extract_pmib_code (analyzer_backend.py:105-107), que
    # rodava o regex sobre a string inteira recebida e podia "vazar" um
    # match vindo do diretório em vez do nome do arquivo.
    #
    # A PARTIR DO CP 1.2: as duas variantes DELEGAM para a mesma
    # `sigft.core.excel.pmib_codes.extract_pmib_code` (basename-first), então
    # CONVERGEM para o mesmo resultado -- o código do ARQUIVO, não do
    # diretório -- em qualquer entrada, incluindo este cenário antes
    # divergente. Ver test_analyzer_backend_characterization.py::
    # test_regex_usa_basename_bug_do_diretorio_foi_corrigido_no_cp_1_2.
    autospec = _make_autospec()
    analyzer = DatasheetAnalyzer.__new__(DatasheetAnalyzer)
    caminho = "pasta_saida/9999999999.8888/4500063671.1234_STATUS_PMIB.xlsx"

    assert autospec.extract_pmib_code(caminho) == "1234"
    assert analyzer.extract_pmib_code(caminho) == "1234"  # antes: "8888" (bug corrigido)
    assert autospec.extract_pmib_code(caminho) == analyzer.extract_pmib_code(caminho)

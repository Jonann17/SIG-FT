"""
Teste de caracterização (CP 0.1) — PMIBSearcher._limpar_texto_parrudo
(search_pmib_backend.py:13-23).

Método "puro" (não usa nenhum atributo de `self`); a instância é criada via
`__new__` para não rodar `__init__` (que aqui é inofensivo, mas seguimos o
padrão do checkpoint de nunca depender de construtores).

ATENÇÃO (stub de pandas): este método chama `pd.isna(texto)`. O
`tests/conftest.py` substitui `pandas.isna` por uma implementação mínima
equivalente (None/NaN -> True, resto -> False) — ver seção 3 do conftest.
"""
from search_pmib_backend import PMIBSearcher


def _make_searcher():
    return PMIBSearcher.__new__(PMIBSearcher)


def test_remove_acentos_espacos_e_pontuacao():
    searcher = _make_searcher()
    assert searcher._limpar_texto_parrudo("Código-ABC-123") == "CODIGOABC123"


def test_texto_ja_limpo_permanece_igual():
    searcher = _make_searcher()
    assert searcher._limpar_texto_parrudo("ABC123") == "ABC123"


def test_none_retorna_string_vazia():
    searcher = _make_searcher()
    assert searcher._limpar_texto_parrudo(None) == ""


def test_nan_float_retorna_string_vazia():
    searcher = _make_searcher()
    assert searcher._limpar_texto_parrudo(float("nan")) == ""


def test_string_vazia_retorna_string_vazia():
    searcher = _make_searcher()
    assert searcher._limpar_texto_parrudo("") == ""


def test_numero_inteiro_e_convertido_normalmente_nao_e_tratado_como_vazio():
    # Peculiaridade: pd.isna(123) é False (não é None nem NaN), então o
    # número segue o fluxo normal e vira string "123".
    searcher = _make_searcher()
    assert searcher._limpar_texto_parrudo(123) == "123"


def test_frase_com_acentos_e_multiplas_palavras():
    searcher = _make_searcher()
    resultado = searcher._limpar_texto_parrudo("Válvula de Retenção nº 5")
    assert resultado == "VALVULADERETENCAON5"


def test_caracteres_sem_decomposicao_canonica_sao_descartados_sem_substituto():
    # Peculiaridade relevante para o CP 1.2: caracteres como 'Ø' e 'º' não têm
    # decomposição CANÔNICA (NFD) — só decomposição de COMPATIBILIDADE (NFKD).
    # Como o método usa unicodedata.normalize('NFD', ...), esses caracteres
    # não se separam em base+diacrítico; o encode('ascii', 'ignore') que vem
    # depois simplesmente os DESCARTA (não viram "O", somem do resultado).
    searcher = _make_searcher()
    resultado = searcher._limpar_texto_parrudo("Peça C/ Furo (Ø 10mm)")
    assert resultado == "PECACFURO10MM"

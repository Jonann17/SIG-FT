r"""O marcador de campo faltante, no idioma da ficha (2026-09-08).

**O pedido.** O `analyzer` escreve `FORNECER` em vermelho nos campos que
faltam ou estão inválidos. Numa ficha em inglês — que existe justamente para
ser devolvida a um fornecedor estrangeiro — essa palavra chega em português.
O usuário pediu para traduzi-la quando o idioma for inglês.

**A armadilha que isto tem.** `FORNECER` não é só decoração: o AutoSpec o LÊ
de volta (`AutoSpecCore.is_empty`) para saber que aquele campo continua vazio
e precisa ser preenchido pela IA. Traduzir só o lado que ESCREVE faria o
AutoSpec, numa ficha em inglês, achar que `PROVIDE` é uma resposta de verdade
— e pular exatamente os campos que o analyzer marcou como faltantes.

É a mesma família do defeito da auditoria de 03/09 (o nome da aba fixo em três
lugares): quem escreve e quem lê precisam concordar, e a concordância tem de
morar num lugar só.

**Como o idioma é descoberto.** Do próprio documento, não de um parâmetro: o
título da seção de especificações (B75) já é conhecido nos dois idiomas
(`ficha_layout.TITULOS_DAS_SPECS`, usado pelo analyzer desde 03/09). Um
parâmetro a mais seria mais uma coisa para esquecer de passar — e ficha
marcada no idioma errado não se denuncia sozinha.
"""
import pytest

from sigft.core.rpa import ficha_layout


# =============================================================================
# A. Os marcadores, e onde eles moram
# =============================================================================
def test_o_marcador_em_portugues_continua_sendo_FORNECER():
    """Regressão pura: a ficha PT-BR não pode mudar de marcador."""
    assert ficha_layout.marcador_de_faltante("pt") == "FORNECER"


def test_existe_marcador_em_INGLES_e_ele_nao_e_o_portugues():
    marcador = ficha_layout.marcador_de_faltante("en")
    assert marcador and marcador != "FORNECER"
    assert marcador.isupper(), "o marcador é escrito em caixa alta, como o PT"


def test_idioma_desconhecido_cai_no_PORTUGUES():
    """Não sei o idioma é diferente de é inglês. O padrão histórico vence."""
    for idioma in (None, "", "fr", "xx"):
        assert ficha_layout.marcador_de_faltante(idioma) == "FORNECER"


# =============================================================================
# B. Descobrir o idioma da ficha, pelo próprio documento
# =============================================================================
class _AbaFalsa:
    """Só o suficiente para `idioma_da_ficha`: `iter_rows` sobre a coluna B."""

    def __init__(self, titulo, linha=75):
        self._titulo, self._linha = titulo, linha

    def iter_rows(self, min_row, max_row, min_col, max_col):
        class _Celula:
            def __init__(self, value, row):
                self.value, self.row = value, row
        for r in range(min_row, max_row + 1):
            yield (_Celula(self._titulo if r == self._linha else None, r),)


TITULO_PT = "ESPECIFICAÇÕES TÉCNICAS - INDIQUE AS ESPECIFICAÇÕES TÉCNICAS NO ESPAÇO LIVRE ABAIXO"
TITULO_EN = "TECHNICAL SPECIFICATIONS - INDICATE TECHNICAL SPECIFICATIONS IN THE FREE SPACE BELOW"


def test_a_ficha_com_titulo_em_ingles_e_reconhecida_como_EN():
    assert ficha_layout.idioma_da_ficha(_AbaFalsa(TITULO_EN)) == "en"


def test_a_ficha_com_titulo_em_portugues_e_reconhecida_como_PT():
    assert ficha_layout.idioma_da_ficha(_AbaFalsa(TITULO_PT)) == "pt"


def test_ficha_sem_titulo_nenhum_e_tratada_como_PORTUGUES():
    """A ficha que o app processa há dois anos é PT-BR. Na dúvida, ela."""
    assert ficha_layout.idioma_da_ficha(_AbaFalsa(None)) == "pt"


def test_aba_que_nao_sabe_iterar_nao_derruba_a_analise():
    """`idioma_da_ficha` é conveniência; nunca pode ser o motivo de uma ficha
    não ser analisada."""
    class _Quebrada:
        def iter_rows(self, **kwargs):
            raise RuntimeError("aba estranha")

    assert ficha_layout.idioma_da_ficha(_Quebrada()) == "pt"


# =============================================================================
# C. O analyzer ESCREVE no idioma certo
# =============================================================================
class _Celula:
    def __init__(self):
        self.value = None
        self.font = None


def _analyzer(idioma):
    from sigft.services import analyzer
    an = analyzer.DatasheetAnalyzer.__new__(analyzer.DatasheetAnalyzer)
    an._idioma_da_ficha = idioma
    return an


@pytest.mark.parametrize("idioma,esperado", [("pt", "FORNECER"), ("en", "PROVIDE")])
def test_campo_vazio_recebe_o_marcador_do_idioma(idioma, esperado):
    celula = _Celula()
    _analyzer(idioma).set_blank_error(celula)
    assert celula.value == esperado


@pytest.mark.parametrize("idioma,esperado", [("pt", "FORNECER"), ("en", "PROVIDE")])
def test_campo_invalido_preserva_o_valor_antigo_no_idioma_certo(idioma, esperado, monkeypatch):
    """`FORNECER (valor antigo tachado)` — o valor do fornecedor continua
    visível, para ele ver o que foi recusado.

    `CellRichText`/`TextBlock` são do openpyxl, que a suíte stuba: o valor que
    sobra na célula é um MagicMock que não dá para inspecionar. Então o teste
    observa o que foi MONTADO — que é onde a decisão de idioma mora."""
    from sigft.services import analyzer

    blocos = []
    monkeypatch.setattr(analyzer, "TextBlock",
                        lambda text, font=None: blocos.append(text) or text)
    monkeypatch.setattr(analyzer, "CellRichText", list)

    celula = _Celula()
    _analyzer(idioma).set_invalid_error(celula, "abc")

    assert blocos[0] == esperado + " (", blocos
    assert "abc" in blocos, blocos


def test_analyzer_construido_sem_idioma_escreve_em_PORTUGUES():
    """O idioma é atributo de instância. Quem constrói via `__new__` (o idioma
    dos testes deste repositório) não o tem — e não pode quebrar."""
    from sigft.services import analyzer
    an = analyzer.DatasheetAnalyzer.__new__(analyzer.DatasheetAnalyzer)
    celula = _Celula()
    an.set_blank_error(celula)
    assert celula.value == "FORNECER"


# =============================================================================
# D. O AutoSpec LÊ os dois — a metade que faria o conserto virar defeito
# =============================================================================
def _autospec():
    from sigft.services.autospec import AutoSpecCore
    return AutoSpecCore.__new__(AutoSpecCore)


@pytest.mark.parametrize("marcado", [
    "FORNECER", "fornecer", "FORNECER (aço 316)",
    "PROVIDE", "provide", "PROVIDE (steel 316)",
])
def test_o_autospec_enxerga_campo_marcado_nos_DOIS_idiomas(marcado):
    """Sem isto, numa ficha em inglês o AutoSpec trataria `PROVIDE` como
    resposta do fornecedor e pularia justamente os campos que faltam."""
    assert _autospec().is_empty(marcado) is True


@pytest.mark.parametrize("resposta", [
    "Aço inox 316", "Stainless steel 316", "Provided by supplier on request",
])
def test_resposta_de_VERDADE_nao_e_confundida_com_marcador(resposta):
    """O risco de afrouxar o reconhecimento: engolir resposta legítima.
    'Provided by...' começa com as mesmas letras e É uma resposta."""
    assert _autospec().is_empty(resposta) is False


def test_os_marcadores_do_autospec_saem_da_MESMA_fonte_do_analyzer():
    """Princípio nº 1. Duas listas de marcadores é o caminho para elas
    divergirem — e a divergência aqui é silenciosa nos dois sentidos."""
    import ast
    import inspect
    import textwrap

    from sigft.services.autospec import AutoSpecCore
    fonte = inspect.getsource(AutoSpecCore.is_empty)
    assert "marcador" in fonte.lower()

    # O CÓDIGO, sem a docstring: a prosa pode citar `FORNECER` à vontade — e
    # cita, para explicar o que mudou. O que não pode é a comparação depender
    # do literal. Sem esta separação o teste reprovava o próprio comentário
    # que documenta o conserto.
    corpo = ast.parse(textwrap.dedent(fonte)).body[0]
    literais = [no.value for no in ast.walk(corpo)
                if isinstance(no, ast.Constant) and isinstance(no.value, str)]
    if literais and literais[0] is ast.get_docstring(corpo):
        literais.pop(0)
    assert "FORNECER" not in literais, f"marcador literal de volta no codigo: {literais}"


def test_todo_marcador_conhecido_e_reconhecido_pelo_autospec():
    """A garantia que sobrevive a um marcador novo: seja qual for o idioma
    acrescentado amanhã, o AutoSpec o enxerga."""
    for marcador in ficha_layout.MARCADORES_DE_FALTANTE.values():
        assert _autospec().is_empty(marcador) is True

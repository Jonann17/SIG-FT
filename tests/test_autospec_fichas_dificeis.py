r"""Modos de falha que OUTRAS fichas vão encontrar (2026-08-12).
Ver `docs/superpowers/specs/2026-08-12-fichas-dificeis-design.md`.

A ficha 4500063671.1188 (sensor HYDAC) passou a funcionar. Ela é o caso
FÁCIL: fabricante conhecido, código de peça limpo, datasheet público. Este
arquivo cobre o que o `_STATUS_PMIB` real também tem — e que só apareceria
quebrado na frente do usuário.

Cada teste aqui nasceu de um caso REPRODUZIDO contra o código, não de
especulação: rodou-se a cascata e o filtro com entradas realistas e
anotou-se o que saiu errado.

O mais grave, e o motivo de o arquivo existir: **material sem fabricante e
sem código fazia o filtro anti-intruso aceitar QUALQUER documento**. A
proteção §4.3 falhava aberta, em silêncio, exatamente na ficha em que menos
se pode confiar no resultado.
"""
import pytest

from sigft.services.autospec import AutoSpecCore as Core
from sigft.services import autospec


# =============================================================================
# A. O filtro não pode falhar ABERTO
# =============================================================================
def test_sem_ancora_nenhuma_o_intruso_NAO_passa():
    """Reproduzido: `_termos_do_filtro('', '', '')` devolvia `[]`, e lista
    vazia significa "aceita tudo". Ficha sem fabricante nem código aceitava
    o catálogo de qualquer concorrente."""
    assert Core._tem_ancora_confiavel("", "", "") is False


def test_identificador_sozinho_JA_e_ancora():
    """Sem fabricante, mas com código de peça, dá para verificar."""
    assert Core._tem_ancora_confiavel("", "", "BOMBA PVF100-4") is True


def test_fabricante_sozinho_JA_e_ancora():
    assert Core._tem_ancora_confiavel("KSB", "", "CONJUNTO DE REPARO") is True


def test_sem_ancora_a_busca_web_nem_acontece():
    """Buscar sem âncora produz lixo E não dá para conferir o que voltou.
    Melhor campo vazio que campo preenchido com dado de outra peça."""
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append((nivel, str(msg)))

    core = Core.__new__(Core)
    core.google_key, core.cse_id = "chave", "cse"
    core.searcher = None  # se tentar buscar, estoura -- e é o que se quer provar
    texto, fontes = Core.retrieve_context(
        core, "", "", "", [], callbacks=_CB()
    )
    assert fontes == []
    assert any("ancora" in m.lower() or "âncora" in m.lower() for _, m in registro)


# =============================================================================
# B. Fabricante que não é fabricante
# =============================================================================
@pytest.mark.parametrize(
    "generico",
    ["DIVERSOS", "diversos", "N/A", "NA", "SEM MARCA", "VARIOS", "NACIONAL", "-"],
)
def test_fabricante_generico_nao_vira_ancora(generico):
    """O `_STATUS_PMIB` real traz esses no lugar do fabricante. Ancorar o
    filtro em `DIVERSOS` aprova qualquer página que diga "diversos"."""
    assert Core._nome_curto_fabricante(generico) == ""


def test_razao_social_so_de_ruido_nao_vira_termo_de_filtro():
    """Reproduzido: `INDUSTRIA E COMERCIO LTDA` virava os termos
    ['INDUSTRIA','COMERCIO','LTDA'] — e QUALQUER página industrial
    brasileira contém "industria"."""
    termos = Core._termos_do_filtro("INDUSTRIA E COMERCIO LTDA", "", "BOMBA X1234")
    assert not any("industria" in t.lower() for t in termos)
    assert not any("comercio" in t.lower() for t in termos)


def test_mas_a_QUERY_ainda_pode_usar_o_nome_original():
    """Para BUSCAR, um nome ruim é melhor que nenhum; para FILTRAR, não.
    São decisões diferentes e agora usam funções diferentes."""
    qs = Core._montar_queries_busca("BOMBA X1234", "INDUSTRIA E COMERCIO LTDA", "")
    assert qs, "ficou sem query nenhuma"


# =============================================================================
# C. O que é e o que não é código de peça
# =============================================================================
@pytest.mark.parametrize(
    "texto,esperado,caso",
    [
        ("VALVULA ESFERA 1/2 POL", [], "fracao de polegada NAO e codigo de peca"),
        ("TUBO 3/4 NPT", [], "outra fracao"),
        ("MOTOR 110 V", [], "tensao de 3 digitos nao e codigo"),
        ("PARAFUSO M8 X 20", [], "M8 e curto, 20 e curto"),
        ("BOMBA 3527528", ["3527528"], "numero longo E codigo de material"),
        ("ROLAMENTO 6205", ["6205"], "4 digitos ja e codigo plausivel"),
        ("SENSOR CS1320-A-0-0-0-1/-000", ["CS1320-A-0-0-0-1/-000"], "letra+digito sempre vale"),
        ("MOTOR 5CV 380V IP55", ["5CV", "380V", "IP55"], "regressao: continua valendo"),
    ],
)
def test_identificadores_ignoram_medida_e_pegam_codigo(texto, esperado, caso):
    assert Core._identificadores(texto) == esperado, caso


def test_fracao_nao_vira_a_primeira_query():
    """Reproduzido: `VALVULA ESFERA 1/2 POL` gerava `1/2 datasheet
    filetype:pdf` como PRIMEIRA tentativa — uma query que não significa
    nada, gastando cota da CSE."""
    qs = Core._montar_queries_busca("VALVULA ESFERA 1/2 POL", "", "")
    assert not any(q.strip().startswith("1/2") for q in qs)


# =============================================================================
# D. Termo numérico não pode virar coringa
# =============================================================================
def test_numero_curto_nao_casa_no_meio_de_outro_numero():
    """Reproduzido: o termo `123` casava com `123456` em página
    irrelevante, porque a comparação era substring pura."""
    assert not autospec._resultado_e_relevante(
        ["123"], "Catalogo generico de pecas 123456", "", "https://loja.com/p/1234"
    )


def test_numero_continua_casando_quando_e_ELE_mesmo():
    assert autospec._resultado_e_relevante(
        ["3332066"], "Part Number 3332066, CS1320 On HYDAC", "", "https://x/3332066"
    )


def test_codigo_alfanumerico_continua_casando_por_substring():
    """A regra estrita vale só para termo 100% numérico: `CS1320` tem de
    continuar casando dentro de `CS1320-A-0-0-0-1`."""
    assert autospec._resultado_e_relevante(
        ["CS1320"], "CS1320-A-0-0-0-1/-000 * | HYDAC", "", "https://x"
    )


# =============================================================================
# E. Download que pode derrubar a máquina do usuário
# =============================================================================
def test_download_gigante_e_abortado():
    """`response.content` carregava o corpo INTEIRO na memória, sem teto.
    Um catálogo de fabricante de 300 MB (existem) travaria o app na
    máquina do usuário, sem mensagem nenhuma."""
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append(str(msg))

    class _RespostaEnorme:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}

        def iter_content(self, chunk_size=None):
            # 1 MB por pedaço, muito além do teto
            for _ in range(int(autospec.TETO_DOWNLOAD_BYTES / (1024 * 1024)) + 5):
                yield b"x" * 1024 * 1024

        def close(self):
            pass

    buscador = autospec.WebSearcher("k", "c")
    caminho = buscador._download_file(
        "https://x/gigante.pdf", callbacks=_CB(), _get=lambda *a, **k: _RespostaEnorme()
    )
    assert caminho is None
    assert any("grande" in m.lower() or "teto" in m.lower() for m in registro)


def test_download_normal_continua_funcionando():
    class _RespostaOk:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}

        def iter_content(self, chunk_size=None):
            yield b"%PDF-1.4 conteudo pequeno"

        def close(self):
            pass

    buscador = autospec.WebSearcher("k", "c")
    caminho = buscador._download_file(
        "https://x/ok.pdf", _get=lambda *a, **k: _RespostaOk()
    )
    assert caminho and caminho.endswith(".pdf")


def test_403_do_fabricante_explica_o_que_houve():
    """Aconteceu de verdade com `hydac.com/shop` no teste de 2026-08-12.
    Vai se repetir: site de fabricante bloqueia robô. A mensagem tem de
    dizer que foi bloqueio, não parecer erro do app."""
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append(str(msg))

    class _Bloqueado:
        status_code = 403
        headers = {}

        def close(self):
            pass

    buscador = autospec.WebSearcher("k", "c")
    buscador._download_file(
        "https://www.hydac.com/shop/en/x", callbacks=_CB(), _get=lambda *a, **k: _Bloqueado()
    )
    assert any("bloque" in m.lower() for m in registro)


# =============================================================================
# F. O console precisa dizer o nome do documento, não o do temporário
# =============================================================================
def test_log_de_leitura_usa_nome_legivel_e_nao_o_temporario(tmp_path):
    """No teste real saiu `tmp1wgju9r5.pdf: 6 pagina(s)...`. O usuário não
    tem como saber QUAL documento foi esse."""
    pymupdf = pytest.importorskip("pymupdf")
    caminho = tmp_path / "tmpABC123.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Especificacao tecnica do equipamento " * 5)
    doc.save(str(caminho))
    doc.close()

    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append(str(msg))

    autospec.PDFProcessor(None).extract_text(
        str(caminho), callbacks=_CB(), nome_exibicao="https://site.com/datasheet.pdf"
    )
    assert any("https://site.com/datasheet.pdf" in m for m in registro)
    assert not any("tmpABC123" in m for m in registro)

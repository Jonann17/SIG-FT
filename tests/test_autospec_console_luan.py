r"""Achados no console de 10 fichas reais (2026-08-13).
Ver `docs/AUTOSPEC_MELHORIAS.md`, R-25.

O Luan processou 10 fichas do escopo SFC HF-01/HF-02 e mandou o terminal
inteiro. Ele mostrou três problemas que nenhum teste sintético pegaria.
"""
import pytest

from sigft.services import autospec
from sigft.services.autospec import AutoSpecCore as Core


def _cb():
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append((nivel, str(msg)))

    return _CB(), registro


# =============================================================================
# A. REGRESSÃO MINHA: o lastro bloqueava campo que não é especificação
# =============================================================================
@pytest.mark.parametrize(
    "campo,exige",
    [
        ("var_row_79", True),
        ("var_row_100", True),
        ("texto_breve_material", False),
        ("fabricante", False),
        ("origem", False),
        ("tipo_fabricacao", False),
        ("nocivo", False),
        ("classificacao_periculosidade", False),
        ("logistica_reversa", False),
        ("peso_liquido", False),
        ("empilhamento", False),
    ],
)
def test_o_lastro_so_vale_para_a_tabela_de_especificacoes(campo, exige):
    """No console das 10 fichas, 7 dos 9 campos barrados numa ficha eram
    identificação e classificação — `fabricante = WAGO`, `origem = Outros`,
    `logistica_reversa = Aplica`. Nenhum deles sai de datasheet: saem da
    planilha e de julgamento. Exigir prova documental deles é exigir prova
    de algo que nunca foi para ser provado assim."""
    assert autospec._exige_lastro(campo) is exige


def test_fabricante_WAGO_nao_e_mais_bloqueado():
    """O caso literal do console: `fabricante -> a IA respondeu 'WAGO'` /
    `motivo: nao ha medida para recalcular`."""
    core = Core.__new__(Core)
    core.ultimas_fontes_por_campo = {}
    cb, _ = _cb()
    campos = {"fabricante": {"type": "text", "desc": "fabricante", "ref": "H8"}}
    assert core._filtrar_por_lastro({"fabricante": "WAGO"}, campos, "", cb) == {
        "fabricante": "WAGO"
    }


def test_especificacao_tecnica_continua_protegida():
    core = Core.__new__(Core)
    core.ultimas_fontes_por_campo = {}
    cb, _ = _cb()
    campos = {"var_row_84": {"type": "text", "desc": "13 - GRAU DE PROTECAO", "ref": "M84"}}
    doc = "--- LOCAL DOC: x.pdf ---\nProtection class IP67."
    assert core._filtrar_por_lastro({"var_row_84": "IP65"}, campos, doc, cb) == {}


# =============================================================================
# B. As listas do console têm de contar a MESMA história
# =============================================================================
def test_campo_bloqueado_some_da_lista_de_ORIGENS():
    """No console, `texto_breve_material` aparecia ao mesmo tempo em "Origem
    dos dados" e em "a IA não respondeu". É o tipo de contradição que faz o
    usuário parar de ler o log."""
    core = Core.__new__(Core)
    core.exigir_lastro = True
    core.ultimas_fontes_por_campo = {"var_row_84": "x.pdf", "fabricante": "planilha"}
    cb, _ = _cb()
    campos = {
        "var_row_84": {"type": "text", "desc": "PRESSAO", "ref": "M84"},
        "fabricante": {"type": "text", "desc": "fabricante", "ref": "H8"},
    }
    aprovados = core._conferir_e_filtrar(
        {"var_row_84": "999 bar", "fabricante": "WAGO"}, campos, "Pressure 350 bar.", cb
    )
    assert "var_row_84" not in aprovados
    assert "var_row_84" not in core.ultimas_fontes_por_campo
    assert "fabricante" in core.ultimas_fontes_por_campo


# =============================================================================
# C. A camiseta da Minnie — três destinos em vez de dois
# =============================================================================
FAB_WAGO = Core._tokens_ancora_fabricante("WAGO")
IDS_0071 = ["750-362", "1000325606"]


@pytest.mark.parametrize(
    "titulo,link,destino,caso",
    [
        ("Data sheet | Item number: 750-362 Fieldbus Coupler Modbus TCP",
         "https://pim.galco.com/Manufacturer/Wago/TechDocument/750-362_dat.pdf",
         "certo", "fabricante E codigo"),
        ("Fieldbus Coupler Modbus TCP (750-362) | WAGO",
         "https://www.wago.com/global/p/750-362", "certo", "site oficial"),
        ("Fieldbus Coupler Modbus TCP (750-513) | WAGO",
         "https://www.wago.com/br/p/750-513", "duvidoso", "OUTRO produto da mesma marca"),
        ("Women's Disney Minnie Mouse Oversized Graphic T-Shirt",
         "https://www.target.com/p/x/-/A-1000325606", "duvidoso", "a camiseta do console"),
        ("Elemental Cost Report 030414",
         "https://www.scribd.com/doc/216825746/x", "descartado", "lixo puro"),
    ],
)
def test_classificacao_dos_resultados_reais(titulo, link, destino, caso):
    """A camiseta da Minnie no Target entrou como contexto numa ficha real
    porque a URL continha o código do material. Com dois destinos não havia
    como recusá-la sem recusar junto o datasheet de distribuidor."""
    assert autospec.classificar_resultado(
        FAB_WAGO, IDS_0071, titulo, "", link
    ) == destino, caso


def test_duvidoso_NAO_vira_contexto():
    """Melhor um campo vazio que o engenheiro preenche do que um campo
    preenchido com a camiseta."""
    buscador = autospec.WebSearcher("k", "c")
    buscador._download_file = lambda url, callbacks=None: "/tmp/x"
    cb, _ = _cb()
    itens = [{
        "title": "Women's Disney Minnie Mouse T-Shirt",
        "link": "https://www.target.com/p/x/-/A-1000325606",
        "snippet": "",
    }]
    resultados = buscador._baixar_resultados(
        itens, callbacks=cb, fabricante=FAB_WAGO, identificadores=IDS_0071
    )
    assert resultados == []
    assert len(buscador.duvidosos) == 1
    assert "target.com" in buscador.duvidosos[0]["url"]


def test_o_duvidoso_e_ANUNCIADO_no_console():
    buscador = autospec.WebSearcher("k", "c")
    buscador._download_file = lambda url, callbacks=None: "/tmp/x"
    cb, registro = _cb()
    buscador._baixar_resultados(
        [{"title": "T-Shirt", "link": "https://target.com/A-1000325606", "snippet": ""}],
        callbacks=cb, fabricante=FAB_WAGO, identificadores=IDS_0071,
    )
    assert any("DUVIDOSO" in m.upper() for _n, m in registro)


# =============================================================================
# D. Código com hífen não é número puro
# =============================================================================
@pytest.mark.parametrize(
    "termo,puro",
    [
        ("1000325606", True),
        ("750-362", False),
        ("IE-3200-8T2S-E", False),
        ("6205", True),
        ("CS1320", False),
    ],
)
def test_codigo_com_hifen_nao_e_numero_puro(termo, puro):
    """Bug real: `750-362` compactava para `750362`, virava "numérico puro",
    e a busca por fronteira procurava `750362` no alvo NÃO compactado — onde
    está escrito `750-362`. Nunca casava. **Todos** os códigos WAGO, CISCO e
    NIDEC da planilha do SFC têm hífen."""
    assert autospec._e_termo_puramente_numerico(termo) is puro


def test_o_codigo_WAGO_casa_com_o_titulo_do_datasheet():
    assert autospec._resultado_e_relevante(
        ["750-362"], "Data sheet | Item number: 750-362 Fieldbus Coupler", "", "http://x"
    )

r"""Coluna G do `_STATUS_PMIB` como guia da busca (2026-08-13).

**Causa raiz das fichas WAGO que voltaram com ZERO características técnicas.**
O Luan processou 4 fichas do escopo "Conversores Estáticos de Frequência"
(0071, 0072, 0073, 0154) e nenhuma teve a tabela de especificações preenchida —
0/23, 0/16, 0/16, 0/6 — apesar de o site da WAGO com o datasheet ser achável à
mão em segundos.

Medido nas fichas reais: `texto_breve_material` e `fabricante` estavam **vazios
na própria ficha** — é o AutoSpec que vai preenchê-los. Sem eles, a busca ia
com o `cod_mat` da coluna E, que é o código **interno da Itaipu**
(`1000325606`, 10 dígitos) e não existe na internet. O programa buscava com a
única informação que ninguém publica.

A planilha sabia a resposta o tempo todo, na coluna **G — `MARCA/MODELO`**:
`WAGO / 750-362`. Medido: `WAGO 750-362 datasheet` devolve 10 datasheets
reais, incluindo o oficial do fabricante.
"""
import pytest

from sigft.services.autospec import AutoSpecCore as Core


# =============================================================================
# A. Separar marca de modelo
# =============================================================================
@pytest.mark.parametrize(
    "bruto,marca,modelo",
    [
        ("WAGO / 750-362", "WAGO", "750-362"),
        ("CISCO / IE-3200-8T2S-E", "CISCO", "IE-3200-8T2S-E"),
        ("NIDEC / MOD SVTN 3K6 W33", "NIDEC", "MOD SVTN 3K6 W33"),
        ("NIDEC / GAAPA", "NIDEC", "GAAPA"),
        ("WAGO", "WAGO", ""),
        ("", "", ""),
        (None, "", ""),
    ],
)
def test_separar_marca_modelo(bruto, marca, modelo):
    assert Core.separar_marca_modelo(bruto) == (marca, modelo)


def test_barra_dentro_do_modelo_nao_parte_o_codigo():
    """`750-362/000-001` é uma variante do mesmo código. Quebrar em todas as
    barras partiria o código de peça ao meio."""
    assert Core.separar_marca_modelo("WAGO / 750-362/000-001") == (
        "WAGO", "750-362/000-001"
    )


# =============================================================================
# B. O modelo da coluna G é identificador POR DEFINIÇÃO
# =============================================================================
def test_modelo_SEM_DIGITO_ainda_ancora_o_filtro():
    """`NIDEC / GAAPA` — `GAAPA` é o nome do cartão e não tem número. A
    heurística de `_identificadores` exige dígito e nunca o reconheceria; a
    planilha, porém, o DECLARA como modelo."""
    termos = Core._termos_do_filtro("NIDEC", "1000080550", "GAAPA cartao", modelo="GAAPA")
    assert "GAAPA" in termos


def test_modelo_entra_na_query_mesmo_sem_digito():
    queries = Core._montar_queries_busca("GAAPA cartao", "NIDEC", "1000080550", modelo="GAAPA")
    assert queries[0] == "NIDEC GAAPA datasheet filetype:pdf"


# =============================================================================
# C. O modelo vem ANTES do código interno da Itaipu
# =============================================================================
def test_a_primeira_query_usa_o_modelo_do_fabricante():
    """O `cod_mat` da coluna E costuma ser o código interno (`1000325606`) —
    gastava a primeira consulta da cascata garantidamente à toa."""
    queries = Core._montar_queries_busca(
        "750-362 Acoplador Modbus TCP", "WAGO", "1000325606", modelo="750-362"
    )
    assert queries[0] == "WAGO 750-362 datasheet filetype:pdf"
    posicao_codigo = next(i for i, q in enumerate(queries) if "1000325606" in q)
    assert posicao_codigo > 0, "o codigo interno nao pode ser a 1a tentativa"


def test_sem_modelo_a_cascata_continua_como_antes():
    """Planilha antiga, sem a coluna G: nada muda."""
    queries = Core._montar_queries_busca("BOMBA PVF100-4", "HYDAC", "3332066")
    assert queries[0] == '"3332066" HYDAC datasheet'


# =============================================================================
# D. O caso real, ponta a ponta
# =============================================================================
CASOS_REAIS = [
    ("WAGO / 750-362", "1000325606", "WAGO", "750-362"),
    ("WAGO / 750-626", "1000089694", "WAGO", "750-626"),
    ("WAGO / 750-430", "1000075587", "WAGO", "750-430"),
    ("WAGO / 750-513", "1000112177", "WAGO", "750-513"),
    ("CISCO / IE-3200-8T2S-E", "1000393813", "CISCO", "IE-3200-8T2S-E"),
    ("NIDEC / GAAPA", "1000080550", "NIDEC", "GAAPA"),
]


@pytest.mark.parametrize("coluna_g,cod_mat,marca,modelo", CASOS_REAIS)
def test_linhas_reais_do_status_pmib(coluna_g, cod_mat, marca, modelo):
    """Os valores são os da planilha real do escopo SFC HF-01/HF-02."""
    assert Core.separar_marca_modelo(coluna_g) == (marca, modelo)
    termos = Core._termos_do_filtro(marca, cod_mat, modelo, modelo=modelo)
    assert marca in termos and modelo in termos
    queries = Core._montar_queries_busca(modelo, marca, cod_mat, modelo=modelo)
    assert queries[0] == f"{marca} {modelo} datasheet filetype:pdf"


def test_a_ficha_tem_PRECEDENCIA_sobre_a_planilha():
    """Se o engenheiro já escreveu o fabricante na ficha, é ele que vale — a
    planilha só entra no vazio. É o contrato do módulo: a ficha é a fonte, o
    `_STATUS_PMIB` é a rede."""
    import inspect

    from sigft.services import autospec

    fonte = inspect.getsource(autospec.AutoSpecCore.analyze_sheet)
    assert "if not fab and marca_status" in fonte
    assert "if not txt_brv" in fonte

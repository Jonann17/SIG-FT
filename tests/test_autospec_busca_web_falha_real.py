r"""Regressão da falha REAL de 2026-08-12: ficha 4500063671.1188 sem PDF anexado.
Ver `docs/superpowers/specs/2026-08-12-busca-web-datasheet-design.md`.

**O que aconteceu.** O Luan rodou o AutoSpec no sensor HYDAC
`CS1320-A-0-0-0-1/-000` sem manual anexado, com dois modelos diferentes. Da
tabela de 22 especificações técnicas:

    minimax  ->  3 de 22 preenchidos (e os 3 vieram do conhecimento do modelo,
                 não de documento nenhum)
    grok     ->  0 de 22

O grok é o modelo mais forte dos dois. Preencher ZERO não foi burrice dele: foi
**obediência**. O prompt manda não inventar, e ele não recebeu contexto nenhum
para responder. O erro estava antes da IA.

**Duas causas raiz, medidas — não deduzidas.**

D1. O filtro anti-intruso (regra de negócio §4.3) exigia a string INTEIRA do
    fabricante como substring do título/snippet/link. A planilha traz a razão
    social brasileira, `HYDAC TECNOLOGIA LTDA`; as páginas reais dizem `HYDAC`
    ou `HYDAC Technology Corporation`. Nenhuma diz `HYDAC TECNOLOGIA LTDA`.
    Medido contra os 4 primeiros resultados reais do Google: **0 de 4
    sobreviviam**. O filtro era uma guilhotina, e nada era baixado.

D2. A cascata só procurava o código de CONFIGURAÇÃO completo
    (`CS1320-A-0-0-0-1/-000`), que é o que identifica um SKU de loja. O
    datasheet é publicado para a FAMÍLIA (`CS 1000 Series` / `CS1320`).
    Medido: família + `filetype:pdf` devolve 10 datasheets reais; o código de
    configuração devolve página de e-commerce em HTML.

Bônus medido no caminho: a razão social também DEGRADA a busca (1 resultado
relevante de 7, contra 10 de 10 sem ela) — não a quebra, mas piora muito o
ranking. Por isso a limpeza do nome vale para a query, não só para o filtro.
"""
import pytest

from sigft.services.autospec import AutoSpecCore
from sigft.services import autospec


# Os 4 primeiros resultados REAIS do Google para este material (2026-08-12).
RESULTADOS_REAIS = [
    {
        "title": "Part Number 3332066, CS1320-A-0-0-0-1/-000 On HYDAC Technology Corporation",
        "link": "https://catalog.hydac.com/item/contamination-sensors/contamination-monitors---cs-1000-series/3332066",
        "snippet": "CS1320-A-0-0-0-1/-000 contamination sensor",
    },
    {
        "title": "CS1320-A-0-0-0-1/-000 * | HYDAC",
        "link": "https://www.hydac.com/shop/en/3332066",
        "snippet": "Product information and operating instructions",
    },
    {
        "title": "ContaminationSensor CS 1000 Series - HYDAC",
        "link": "https://www.hydac.com.au/media/productattach/e/_/e.7.958.4.02.15.pdf",
        "snippet": "The ContaminationSensor CS 1000 series is an online fluid sensor",
    },
    {
        "title": "ContaminationSensor CS 1000 Series",
        "link": "https://www.leaderhydraulics.com/wp-content/uploads/2019/03/CS-1000-Series-Datasheet.pdf",
        "snippet": "CS1320 measuring range ISO 4406 flow 50-400 ml/min",
    },
]

FAB_RAZAO_SOCIAL = "HYDAC TECNOLOGIA LTDA"
TXT_BRV = "CS1320-A-0-0-0-1/-000"
COD_PMIB = "3527900"  # código INTERNO do PMIB, não existe na internet


# =============================================================================
# D1 — o filtro não pode mais ser uma guilhotina
# =============================================================================
def test_a_falha_real_nao_se_repete_o_filtro_deixa_passar():
    """O caso exato que produziu 0 de 22. Se este teste falhar, voltou."""
    termos = AutoSpecCore._termos_do_filtro(FAB_RAZAO_SOCIAL, COD_PMIB, TXT_BRV)
    passaram = [
        r for r in RESULTADOS_REAIS
        if autospec._resultado_e_relevante(termos, r["title"], r["snippet"], r["link"])
    ]
    assert len(passaram) == len(RESULTADOS_REAIS), (
        f"o filtro descartou {len(RESULTADOS_REAIS) - len(passaram)} resultado(s) corretos"
    )


def test_razao_social_vira_o_nome_que_o_datasheet_usa():
    assert AutoSpecCore._nome_curto_fabricante("HYDAC TECNOLOGIA LTDA") == "HYDAC"


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("HYDAC TECNOLOGIA LTDA", "HYDAC"),
        ("3M DO BRASIL LTDA", "3M"),
        ("PARKER HANNIFIN IND E COM LTDA", "PARKER HANNIFIN"),
        ("KSB", "KSB"),
        ("Bosch Rexroth AG", "Bosch Rexroth"),
        ("SKF DO BRASIL LTDA.", "SKF"),
    ],
)
def test_limpeza_do_nome_do_fabricante(bruto, esperado):
    assert AutoSpecCore._nome_curto_fabricante(bruto) == esperado


def test_nome_que_e_SO_ruido_nao_vira_vazio():
    """Preferir o nome original a nenhum nome: sem fabricante na query, o
    filtro anti-intruso perde a âncora e volta a barrar tudo."""
    assert AutoSpecCore._nome_curto_fabricante("INDUSTRIA E COMERCIO LTDA")
    assert AutoSpecCore._nome_curto_fabricante("") == ""


def test_o_filtro_continua_barrando_o_concorrente():
    """A regra §4.3 existe por um motivo: catálogo de concorrente não pode
    virar contexto. Afrouxar o filtro não pode custar isso."""
    termos = AutoSpecCore._termos_do_filtro(FAB_RAZAO_SOCIAL, COD_PMIB, TXT_BRV)
    intruso = {
        "title": "Parker Sensor de Contaminacao - catalogo geral",
        "link": "https://www.parker.com/br/sensores",
        "snippet": "Sensores de contaminacao para sistemas hidraulicos",
    }
    assert not autospec._resultado_e_relevante(
        termos, intruso["title"], intruso["snippet"], intruso["link"]
    )


def test_casamento_ignora_separador_no_codigo_de_peca():
    """`CS 1000 Series` no título e `CS1000` no termo são a mesma coisa —
    fabricante escreve o código com espaço, hífen ou nada, sem critério."""
    assert autospec._resultado_e_relevante(
        ["CS1000"], "ContaminationSensor CS 1000 Series", "", "http://x/y.pdf"
    )


def test_casamento_ignora_acento_e_caixa():
    assert autospec._resultado_e_relevante(
        ["válvula"], "VALVULA de controle", "", "http://x"
    )


def test_sem_termo_nenhum_nada_e_barrado():
    """Material sem fabricante nem código: filtrar por nada barraria tudo."""
    assert autospec._resultado_e_relevante([], "qualquer coisa", "", "http://x")


# =============================================================================
# D2 — a cascata precisa procurar a FAMÍLIA, e precisa pedir PDF
# =============================================================================
@pytest.mark.parametrize(
    "identificador,familia",
    [
        ("CS1320-A-0-0-0-1/-000", "CS1320"),
        ("PVF100-4", "PVF100"),
        ("3527528", ""),  # número puro não tem família: seria ele mesmo
        ("ABC", ""),      # sem dígito, não é código de peça
    ],
)
def test_familia_do_identificador(identificador, familia):
    assert AutoSpecCore._familia_do_identificador(identificador) == familia


def test_a_cascata_procura_a_familia_do_produto():
    queries = AutoSpecCore._montar_queries_busca(TXT_BRV, FAB_RAZAO_SOCIAL, COD_PMIB)
    assert any("CS1320 " in q or q.endswith("CS1320") for q in queries), (
        "sem a familia, so se acha pagina de loja do SKU -- nao o datasheet"
    )


def test_a_cascata_pede_PDF_em_alguma_etapa():
    queries = AutoSpecCore._montar_queries_busca(TXT_BRV, FAB_RAZAO_SOCIAL, COD_PMIB)
    assert any("filetype:pdf" in q for q in queries)


def test_a_query_usa_o_nome_curto_do_fabricante():
    """Medido: com a razao social, 1 de 7 resultados relevantes; sem ela,
    10 de 10. Nao quebra a busca -- degrada muito o ranking."""
    queries = AutoSpecCore._montar_queries_busca(TXT_BRV, FAB_RAZAO_SOCIAL, COD_PMIB)
    assert all("TECNOLOGIA" not in q.upper() for q in queries)
    assert all("LTDA" not in q.upper() for q in queries)
    assert all("HYDAC" in q.upper() for q in queries), "o fabricante ancora o filtro"


def test_o_especifico_vem_antes_do_generico():
    """A cascata para na primeira query que rende documento. Se a familia
    viesse antes do codigo exato, o datasheet da familia errada ganharia."""
    queries = AutoSpecCore._montar_queries_busca(TXT_BRV, FAB_RAZAO_SOCIAL, COD_PMIB)
    pos_id = next(i for i, q in enumerate(queries) if TXT_BRV in q)
    pos_familia = next(i for i, q in enumerate(queries) if "CS1320 " in q or q.endswith("CS1320"))
    assert pos_id < pos_familia


def test_material_sem_identificador_continua_caindo_na_prosa():
    """Regressão: nem todo material tem código de peça. A prosa é o único
    caminho para esses, e não pode sumir."""
    queries = AutoSpecCore._montar_queries_busca(
        "CONJUNTO DE REPARO GENERICO", "KSB", None
    )
    assert queries, "material sem identificador ficou sem query nenhuma"


def test_nao_repete_query():
    queries = AutoSpecCore._montar_queries_busca(TXT_BRV, FAB_RAZAO_SOCIAL, COD_PMIB)
    assert len(queries) == len(set(queries))


# =============================================================================
# C — o diagnóstico que teria poupado a investigação inteira
# =============================================================================
def test_filtro_que_descarta_TUDO_grita_no_console():
    """Custou uma investigação inteira descobrir que o filtro comia 100% dos
    resultados. O log dizia `descartou 10 de 10` no meio de outras linhas,
    como se fosse rotina. Descartar TUDO nunca é rotina."""
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append((nivel, str(msg)))

    buscador = autospec.WebSearcher("chave", "cse")
    buscador._download_file = lambda url, callbacks=None: None
    buscador._baixar_resultados(
        RESULTADOS_REAIS, required_terms=["TERMO QUE NAO CASA COM NADA"], callbacks=_CB()
    )

    graves = [msg for nivel, msg in registro if nivel in ("warn", "error")]
    assert graves, "descartar 100% dos resultados passou em silencio"
    assert any("todos" in m.lower() or "100%" in m for m in graves)

r"""Documento que cobre VÁRIOS modelos, e a busca que não achava a família.

Duas frentes pedidas pelo usuário em 2026-09-14, e elas são o mesmo eixo: o
aplicativo não tinha noção de *"este documento fala de vários produtos — qual
deles é o meu?"*.

FRENTE 1 — o lastro conferia PRESENÇA, não PERTINÊNCIA
------------------------------------------------------------------------
O datasheet `UCSC CONTROLLERS.pdf` cobre quatro variantes:

    UCSCH1, UCSCH2, UCSCS2: 168 x 150 x 55 mm (...)
    UCECH1: 168 x 150 x 85 mm (...)

A resposta `168 x 150 x 85 mm` mistura altura e profundidade de um modelo com
a largura de outro — e passava, porque os três números estão no documento. O
lastro não sabia qual variante a ficha queria.

FRENTE 2 — o caso CISCO IE-3200-8T2S-E
------------------------------------------------------------------------
O usuário achou as especificações à mão em segundos; o AutoSpec não. Não era
falta de busca web (ela existe) nem de leitura de HTML (existe também). Eram
dois filtros apertados demais:

- `_familia_do_identificador("IE-3200-8T2S-E")` devolvia `""`, porque cortava
  no PRIMEIRO hífen e `IE` tem 2 letras. A família real é `IE-3200`, que são
  os dois primeiros segmentos — e é por família que fabricante publica
  datasheet (a URL que o usuário mandou é `cat-ie3200-rugged-series-ds.html`);
- a página da família caía em **duvidosos** quando o trecho do Google não
  trazia o código exato, e duvidoso não vira contexto: vai para a conferência
  humana. A ficha ficava vazia com a resposta na mão.
"""
import pytest

from sigft.services import autospec
from sigft.services.autospec import AutoSpecCore


# =============================================================================
# FRENTE 1 — fatiar o documento pelo modelo
# =============================================================================
DATASHEET = """Dimensions (H x D x W)
UCSCH1, UCSCH2, UCSCS2: 168 x 150 x 55 mm (6.61 x 5.90 x 2.17 in)
UCSCH1, UCSCH2, UCSCS2 with mounting: 204 x 152 x 55 mm (8.03 x 5.99 x 2.17 in)
UCECH1: 168 x 150 x 85 mm (6.61 x 5.91 x 3.35 in)
UCECH1 with mounting: 204 x 153 x 85 mm (8.03 x 6.02 x 3.35 in)
Operating temperature: -40 to 70 °C
Certificate: ABNT NBR IEC 60749-1"""


def test_a_linha_do_MEU_modelo_fica():
    recorte = autospec.contexto_do_modelo(DATASHEET, "UCSCH1")
    assert "168 x 150 x 55 mm" in recorte


def test_a_linha_de_OUTRO_modelo_sai():
    """É o defeito do usuário: o `85` só existe na linha do UCECH1."""
    recorte = autospec.contexto_do_modelo(DATASHEET, "UCSCH1")
    assert "85 mm" not in recorte, recorte


def test_a_linha_SEM_modelo_nenhum_fica():
    """Spec compartilhada vale para todas as variantes — temperatura, norma,
    cabeçalho de seção. Cortá-la esvaziaria a ficha."""
    recorte = autospec.contexto_do_modelo(DATASHEET, "UCSCH1")
    assert "-40 to 70" in recorte
    assert "ABNT NBR IEC 60749-1" in recorte
    assert "Dimensions (H x D x W)" in recorte


def test_rotulo_que_nao_e_modelo_nao_engana():
    """`Certificate:` e `Operating temperature:` também têm dois-pontos. O que
    marca uma linha como de-um-modelo é o lado esquerdo parecer CÓDIGO —
    letra e dígito juntos."""
    recorte = autospec.contexto_do_modelo(DATASHEET, "UCSCH1")
    assert "Certificate" in recorte


def test_sem_modelo_informado_nada_e_cortado():
    """A ficha nem sempre traz o modelo. Sem ele, o comportamento é o de
    sempre — recortar por um modelo que não existe cegaria o lastro."""
    assert autospec.contexto_do_modelo(DATASHEET, "") == DATASHEET
    assert autospec.contexto_do_modelo(DATASHEET, None) == DATASHEET


def test_documento_de_UM_modelo_so_passa_inteiro():
    """Nada a decidir: se nenhuma linha se declara de um modelo, o documento
    inteiro serve."""
    doc = "Working pressure: 350 bar\nWeight: 41 kg"
    assert autospec.contexto_do_modelo(doc, "PVF100-4") == doc


def test_o_meu_modelo_e_reconhecido_mesmo_escrito_diferente():
    """`IE-3200-8T2S-E` na planilha, `IE3200-8T2S-E` no documento. Hífen não
    pode decidir se o dado entra na ficha."""
    doc = "IE3200-8T2S-E: 24 VDC\nIE3300-8T2S-E: 48 VDC"
    recorte = autospec.contexto_do_modelo(doc, "IE-3200-8T2S-E")
    assert "24 VDC" in recorte
    assert "48 VDC" not in recorte


def test_o_lastro_reprova_a_mistura_de_dois_modelos():
    """O teste que fecha o pedido, pelo caminho que o usuário percorreu."""
    core = AutoSpecCore.__new__(AutoSpecCore)
    core._modelo_do_item = "UCSCH1"
    missing = {"var_row_18": {"desc": "18 - DIMENSOES (Indicar o dimensional em mm.)"}}

    aprovados = core._filtrar_por_lastro(
        {"var_row_18": "168 x 150 x 85 mm"}, missing, DATASHEET)
    assert not aprovados.get("var_row_18"), \
        f"a mistura de modelos entrou como {aprovados.get('var_row_18')!r}"


def test_o_lastro_aprova_a_dimensao_do_modelo_CERTO():
    """A contraprova: o recorte não pode custar o caminho feliz."""
    core = AutoSpecCore.__new__(AutoSpecCore)
    core._modelo_do_item = "UCSCH1"
    missing = {"var_row_18": {"desc": "18 - DIMENSOES (Indicar o dimensional em mm.)"}}

    aprovados = core._filtrar_por_lastro(
        {"var_row_18": "168 x 150 x 55 mm"}, missing, DATASHEET)
    assert aprovados.get("var_row_18") == "168 x 150 x 55 mm"


def test_sem_modelo_no_core_o_lastro_se_comporta_como_antes():
    """Regressão: o atributo é novo, e quem constrói o core com `__new__` (o
    idioma dos testes deste repositório) não o tem."""
    core = AutoSpecCore.__new__(AutoSpecCore)
    missing = {"var_row_18": {"desc": "18 - DIMENSOES"}}
    aprovados = core._filtrar_por_lastro(
        {"var_row_18": "168 x 150 x 55 mm"}, missing, DATASHEET)
    assert aprovados.get("var_row_18") == "168 x 150 x 55 mm"


# =============================================================================
# FRENTE 2 — a família com hífen dentro do nome
# =============================================================================
@pytest.mark.parametrize("identificador,familia", [
    # O caso do usuário: a família são os DOIS primeiros segmentos.
    ("IE-3200-8T2S-E", "IE-3200"),
    ("NSD-100-A", "NSD-100"),
    # Regressões: tudo que já funcionava continua igual.
    ("CS1320-A-0-0-0-1/-000", "CS1320"),
    ("PVF100-4", "PVF100"),
    ("750-362", "750"),
    ("1756-L71", "1756"),
    ("3527528", ""),   # número puro: a família seria ele mesmo
    ("ABC", ""),       # sem dígito, não é código de peça
    ("S7-1200", ""),   # a família É o código inteiro; não há o que encurtar
])
def test_familia_do_identificador(identificador, familia):
    assert AutoSpecCore._familia_do_identificador(identificador) == familia


def test_a_cascata_passa_a_procurar_a_serie_IE_3200():
    """Sem isto, o datasheet da série — que é como a Cisco publica — nunca é
    procurado."""
    queries = AutoSpecCore._montar_queries_busca(
        "SWITCH ETHERNET INDUSTRIAL IE-3200-8T2S-E", "CISCO", "1000325606",
        modelo="IE-3200-8T2S-E")
    assert any("IE-3200 datasheet" in q for q in queries), queries


# =============================================================================
# FRENTE 2 — a página do próprio fabricante não é "duvidosa"
# =============================================================================
URL_CISCO = ("https://www.cisco.com/c/en/us/products/collateral/switches/"
             "catalyst-ie3200-rugged-series/cat-ie3200-rugged-series-ds.html")


def test_pagina_no_site_do_FABRICANTE_e_confiavel():
    """`cisco.com` falando de produto Cisco não é a camiseta da Minnie no
    Target. O domínio do fabricante É a evidência que faltava."""
    destino = autospec.classificar_resultado(
        ["CISCO"], ["IE-3200-8T2S-E"],
        "Cisco Catalyst IE3200 Rugged Series Data Sheet",
        "Cisco Catalyst IE3200 Rugged Series.", URL_CISCO)
    assert destino == "certo"


def test_loja_com_o_codigo_na_url_continua_duvidosa():
    """A guarda que não pode afrouxar: foi uma camiseta entrando por uma URL
    que continha o código do material que motivou os três destinos."""
    destino = autospec.classificar_resultado(
        ["CISCO"], ["IE-3200-8T2S-E"],
        "Camiseta infantil", "Produto em promoção",
        "https://www.target.com/p/IE-3200-8T2S-E")
    assert destino in ("duvidoso", "descartado")


def test_site_de_OUTRO_fabricante_nao_vira_confiavel():
    """O concorrente falando do meu código é exatamente o intruso que o
    filtro existe para pegar."""
    destino = autospec.classificar_resultado(
        ["CISCO"], ["IE-3200-8T2S-E"],
        "Industrial switches", "Compare models",
        "https://www.moxa.com/en/products/industrial-switches")
    assert destino != "certo"


def test_dominio_do_fabricante_com_sufixo_de_pais():
    """`cisco.com.br`, `siemens.de` — o fabricante é o mesmo."""
    destino = autospec.classificar_resultado(
        ["CISCO"], ["IE-3200-8T2S-E"], "Switches industriais", "",
        "https://www.cisco.com.br/produtos/switches.html")
    assert destino == "certo"


def test_OUTRO_produto_do_mesmo_fabricante_nao_e_promovido():
    """O erro que a suíte pegou quando escrevi a regra do domínio.

    `wago.com/br/p/750-513` está no site da WAGO — mas o item é o `750-362`.
    Aceitar isso seria criar, dentro do filtro, exatamente o defeito de
    modelo-errado que esta rodada existe para fechar.
    """
    destino = autospec.classificar_resultado(
        ["WAGO"], ["750-362"], "Fieldbus Coupler Modbus TCP (750-513)",
        "WAGO", "https://www.wago.com/br/p/750-513")
    assert destino != "certo", destino


def test_grau_de_protecao_no_titulo_nao_bloqueia_a_promocao():
    """O contraponto: `IP67` também é letra+dígito, mas não começa pela
    família do meu código — não é irmão, e não pode virar motivo de recusa."""
    destino = autospec.classificar_resultado(
        ["CISCO"], ["IE-3200-8T2S-E"],
        "Cisco Catalyst IE3200 Rugged Series Data Sheet — IP67 rated",
        "Rugged switches.", URL_CISCO)
    assert destino == "certo"


# =============================================================================
# A 2ª PASSADA (documentos conferidos) também recorta pelo modelo [2026-10-19]
# =============================================================================
# `_modelo_do_item` só era definido em `retrieve_context`, e
# `processar_conferidos` não passa por ele (usa `contexto_das_urls`). Na 2ª
# passada o lastro conferia contra o documento INTEIRO -- ou, pior, contra o
# modelo do ÚLTIMO item da 1ª passada, que ficava esquecido na instância.
def _core_2a_passada(modelo_na_planilha, gravados):
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.usar_navegador_ultimo_recurso = False
    missing = {"var_row_18": {"type": "text",
                              "desc": "18 - DIMENSOES (Indicar o dimensional em mm.)",
                              "ref": "M18"}}

    def _analyze(ficha, status):
        base = (object(), missing, "CONTROLADOR", "FAB", "desc", "cod")
        return base + ((modelo_na_planilha,) if modelo_na_planilha is not None else ())

    core.analyze_sheet = _analyze
    core.contexto_das_urls = lambda urls, refs=(), callbacks=None: DATASHEET
    # A IA dublada responde a MISTURA; o lastro de verdade decide.
    core._resposta_da_ia = "168 x 150 x 85 mm"
    core.generate_ai_response = lambda txt, fab, desc, falt, ctx, callbacks=None: (
        core._filtrar_por_lastro({"var_row_18": core._resposta_da_ia}, falt, ctx, callbacks))

    def _fill(wb, ficha, valores, campos, callbacks=None):
        gravados.append(dict(valores))
        return f"{ficha}_completed.xlsx"

    core.fill_save = _fill
    return core


def test_a_2a_passada_reprova_a_mistura_de_dois_modelos():
    gravados = []
    core = _core_2a_passada("UCSCH1", gravados)
    list(core.processar_conferidos({"A.xlsx": ["https://x/ds.pdf"]}, None))
    assert gravados, "a ficha nem chegou a ser salva"
    assert not gravados[0].get("var_row_18"), \
        f"a mistura de modelos entrou na 2a passada como {gravados[0].get('var_row_18')!r}"


def test_a_2a_passada_nao_herda_o_modelo_do_item_anterior():
    """Item sem modelo na planilha depois de uma 1ª passada que terminou num
    item UCECH1: o recorte não pode usar o modelo de OUTRA ficha."""
    gravados = []
    core = _core_2a_passada(None, gravados)
    core._modelo_do_item = "UCECH1"          # sobra da 1a passada
    core._resposta_da_ia = "168 x 150 x 55 mm"
    list(core.processar_conferidos({"A.xlsx": ["https://x/ds.pdf"]}, None))
    assert gravados and gravados[0].get("var_row_18") == "168 x 150 x 55 mm"

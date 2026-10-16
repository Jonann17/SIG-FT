r"""As guardas da escolha de PDM no módulo *cria fichas* (2026-09-22).

Cada teste aqui corresponde a uma falha SILENCIOSA que o fluxo tinha: nenhuma
delas dava erro, log ou aviso -- todas terminavam com um PDM errado gravado na
planilha e digitado no portal.

  A. **Casamento por posição.** A view fazia `res_json[i]` -> `df.iloc[i]`.
     Se a IA pulasse ou reordenasse um item, TODA linha seguinte recebia o PDM
     de outro material. E a numeração nem batia: `_formatar_itens` rotulava
     `index + 1` com o índice ORIGINAL da planilha (a seleção não fazia
     `reset_index`), enquanto o contrato de JSON pedia 1, 2, 3...
  B. **Nenhuma validação de pertinência.** IA -> revisão de texto livre ->
     digitado no portal, sem nunca conferir se o PDM existe no catálogo.
  C. **Lote inteiro numa chamada, sem retry.** Uma falha da API derrubava os
     40 itens juntos.
"""
from __future__ import annotations

import pytest

from sigft.core import pdm_catalogo
from sigft.services import cria_fichas


VALVULA = pdm_catalogo.PDM(
    codigo="PDM.4820.004", classe="4820", titulo="VALVULA ESFERA",
    nome_base="VALVULA", modificador="ESFERA",
    caracteristicas=("TIPO DE PASSAGEM", "NUMERO DE VIAS"),
)
BOMBA = pdm_catalogo.PDM(
    codigo="PDM.4320.007", classe="4320", titulo="BOMBA",
    nome_base="BOMBA", modificador="", caracteristicas=("VAZAO",),
)
CATALOGO = pdm_catalogo.CatalogoPDM(
    pdms=[VALVULA, BOMBA],
    classes=[
        pdm_catalogo.ClasseFSC(numero="4820", descricao="VALVULAS",
                               inclui="VALVULAS DE RETENCAO"),
        pdm_catalogo.ClasseFSC(numero="4320", descricao="BOMBAS"),
    ],
)


# =============================================================================
# A. Casamento da resposta com o item, por `item_processado`
# =============================================================================
def test_alinhar_usa_o_numero_do_item_e_nao_a_ordem_da_resposta():
    """A IA respondeu fora de ordem. Antes, o item 1 receberia o PDM do 2."""
    resposta = [
        {"item_processado": 2, "pdm_escolhido": "PDM.4320.007 - BOMBA"},
        {"item_processado": 1, "pdm_escolhido": "PDM.4820.004 - VALVULA ESFERA"},
    ]

    alinhado = cria_fichas.alinhar_resposta(resposta, total=2)

    assert alinhado[0]["pdm_escolhido"] == "PDM.4820.004 - VALVULA ESFERA"
    assert alinhado[1]["pdm_escolhido"] == "PDM.4320.007 - BOMBA"


def test_alinhar_deixa_buraco_quando_a_ia_pula_um_item():
    """O caso que mais dói: a IA devolve 2 objetos para 3 itens. Por posição,
    o item 3 herdava silenciosamente o PDM do item 2 -- ou sumia. Um buraco
    explícito (`None`) é o que permite a UI marcar o item para revisão."""
    resposta = [
        {"item_processado": 1, "pdm_escolhido": "PDM.4820.004 - VALVULA ESFERA"},
        {"item_processado": 3, "pdm_escolhido": "PDM.4320.007 - BOMBA"},
    ]

    alinhado = cria_fichas.alinhar_resposta(resposta, total=3)

    assert alinhado[0] is not None
    assert alinhado[1] is None
    assert alinhado[2]["pdm_escolhido"] == "PDM.4320.007 - BOMBA"


def test_alinhar_ignora_numero_de_item_fora_do_lote():
    resposta = [{"item_processado": 99, "pdm_escolhido": "X"}]

    assert cria_fichas.alinhar_resposta(resposta, total=2) == [None, None]


def test_alinhar_cai_para_a_ordem_quando_a_ia_nao_manda_o_numero():
    """Modelo que ignora a instrução não pode derrubar o lote: sem NENHUM
    `item_processado` utilizável, a ordem da resposta é o melhor palpite
    disponível -- é o comportamento de antes, e aqui ele é o último recurso
    em vez do único caminho."""
    resposta = [{"pdm_escolhido": "A"}, {"pdm_escolhido": "B"}]

    alinhado = cria_fichas.alinhar_resposta(resposta, total=2)

    assert [x["pdm_escolhido"] for x in alinhado] == ["A", "B"]


# =============================================================================
# B. Pertinência do PDM escolhido
# =============================================================================
def test_conferir_pdm_aceita_o_que_existe():
    item = {"pdm_escolhido": "PDM.4820.004 - VALVULA ESFERA"}

    ok, motivo = cria_fichas.conferir_pdm(item, CATALOGO)

    assert ok is True
    assert motivo == ""


def test_conferir_pdm_recusa_codigo_inventado():
    item = {"pdm_escolhido": "PDM.9999.999 - INVENTADO"}

    ok, motivo = cria_fichas.conferir_pdm(item, CATALOGO)

    assert ok is False
    assert "PDM.9999.999" in motivo


def test_conferir_pdm_conserta_o_titulo_errado_pelo_codigo():
    """O código está certo e o título tem uma vírgula a mais -- o caso que o
    prompt antigo ensinava. Canonizar é melhor que reprovar: a vírgula é o
    que o filtro do portal não casaria."""
    item = {"pdm_escolhido": "PDM.4820.004 - VALVULA, ESFERA"}

    ok, _motivo = cria_fichas.conferir_pdm(item, CATALOGO)

    assert ok is True
    assert item["pdm_escolhido"] == "PDM.4820.004 - VALVULA ESFERA"


def test_conferir_pdm_aceita_nenhum_sem_reclamar():
    """"NENHUM" é resposta legítima: `processar_item_individual` a trata como
    PULAR."""
    ok, _motivo = cria_fichas.conferir_pdm({"pdm_escolhido": "NENHUM"}, CATALOGO)

    assert ok is True


def test_conferir_pdm_recusa_item_vazio():
    ok, motivo = cria_fichas.conferir_pdm({}, CATALOGO)

    assert ok is False
    assert motivo


def test_conferir_pdm_sem_catalogo_nao_reprova_nada():
    """Sem catálogo (o modo "Pular IA" lê PDM direto da planilha), a guarda
    não tem com o que comparar. Reprovar tudo aí seria trocar uma falha
    silenciosa por uma barulhenta e errada."""
    ok, _motivo = cria_fichas.conferir_pdm({"pdm_escolhido": "QUALQUER"}, None)

    assert ok is True


# =============================================================================
# C. Os candidatos chegam ao prompt
# =============================================================================
class _DataFrameFalso:
    """Um `iterrows` mínimo -- a suíte roda sem pandas real (conftest stuba)."""

    def __init__(self, linhas):
        self._linhas = linhas

    def iterrows(self):
        return enumerate(self._linhas)

    def __len__(self):
        return len(self._linhas)


def _df_um_item(descricao="VALVULA ESFERA DN50"):
    return _DataFrameFalso([{
        "DESCRIÇÃO": descricao,
        "MARCA/MODELO": "GENERICA",
        "CÓDIGO DO MATERIAL": "123",
        "UNID.": "PC",
    }])


def test_formatar_itens_numera_a_partir_de_um():
    """Antes era `index + 1` com o índice ORIGINAL da planilha: selecionar as
    linhas 50-52 produzia "### ITEM 51/52/53" enquanto o contrato de JSON
    pedia 1, 2, 3."""
    cat = cria_fichas.GeminiCategorizer("")
    texto = cat._formatar_itens(_df_um_item())

    assert "### ITEM 1" in texto


def test_formatar_itens_inclui_os_candidatos_com_classe_e_caracteristica():
    cat = cria_fichas.GeminiCategorizer("")
    texto = cat._formatar_itens(_df_um_item(), catalogo=CATALOGO)

    assert "PDM.4820.004 - VALVULA ESFERA" in texto
    assert "4820" in texto
    assert "TIPO DE PASSAGEM" in texto


def test_formatar_itens_avisa_quando_nao_ha_candidato():
    """Medido contra o arquivo real: descrições como "IE4010 w/ 12GE SFP
    uplink ports" não têm palavra que nomeie o equipamento, e a pré-seleção
    volta vazia. Silêncio ali faria o modelo achar que a lista de candidatos
    é a lista completa."""
    cat = cria_fichas.GeminiCategorizer("")
    texto = cat._formatar_itens(_df_um_item("XJ-9000 ZZZZ"), catalogo=CATALOGO)

    assert "nenhum candidato" in texto.lower()


def test_formatar_itens_sem_catalogo_nao_fala_de_candidatos():
    cat = cria_fichas.GeminiCategorizer("")
    texto = cat._formatar_itens(_df_um_item())

    assert "CANDIDATOS" not in texto


class _CatalogoQueAnota:
    """Guarda a consulta que a busca recebeu."""

    def __init__(self):
        self.consultas = []

    def candidatos(self, texto, *a, **k):
        self.consultas.append(texto)
        return []


def _df_sem_marca():
    return _DataFrameFalso([{
        "DESCRIÇÃO": "PLAQUETA DE IDENTIFICACAO",
        "MARCA/MODELO": float("nan"),   # célula vazia lida com dtype=str
        "CÓDIGO DO MATERIAL": "123",
        "UNID.": "PC",
    }])


def test_item_sem_marca_nao_vai_ao_prompt_como_nan():
    """Pendência de 2026-10-09: `read_excel(dtype=str)` não preenche vazio, e
    a célula sem marca chegava à IA como "- Marca/Modelo: nan"."""
    cat = cria_fichas.GeminiCategorizer("")
    texto = cat._formatar_itens(_df_sem_marca())

    assert "- Marca/Modelo: \n" in texto
    assert "nan" not in texto.lower()


def test_item_sem_marca_nao_poe_nan_na_busca_do_catalogo():
    """O mesmo "nan" entrava na consulta da busca (frente crua e o bloco de
    candidatos), como se fosse uma palavra da descrição."""
    catalogo = _CatalogoQueAnota()
    cat = cria_fichas.GeminiCategorizer("")
    cat._formatar_itens(_df_sem_marca(), catalogo=catalogo)
    linha = next(iter(_df_sem_marca().iterrows()))[1]
    cria_fichas.GeminiCategorizer._candidatos_do_item(linha, None, catalogo)

    assert catalogo.consultas, "a busca nem foi chamada"
    assert all("nan" not in c.lower() for c in catalogo.consultas), catalogo.consultas
    assert all(c.strip() == "PLAQUETA DE IDENTIFICACAO" for c in catalogo.consultas)


# =============================================================================
# D. O lote é fatiado
# =============================================================================
class _LLMQueContaChamadas:
    provider_name = "falso"
    model = "falso-1"

    def __init__(self, por_chamada):
        self.por_chamada = por_chamada
        self.prompts = []

    def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        indice = len(self.prompts) - 1

        class Resposta:
            parsed_json = self.por_chamada[indice]

        return Resposta()


def test_processar_lote_fatia_em_blocos(monkeypatch):
    """40 itens numa chamada, com `max_retries=0`, era tudo ou nada."""
    monkeypatch.setattr(cria_fichas, "ITENS_POR_BLOCO", 2)
    df = _DataFrameFalso([
        {"DESCRIÇÃO": f"ITEM {i}", "MARCA/MODELO": "", "CÓDIGO DO MATERIAL": "",
         "UNID.": ""}
        for i in range(5)
    ])
    cat = cria_fichas.GeminiCategorizer("chave")
    cat._llm = _LLMQueContaChamadas([
        [{"item_processado": 1, "pdm_escolhido": "NENHUM"},
         {"item_processado": 2, "pdm_escolhido": "NENHUM"}],
        [{"item_processado": 1, "pdm_escolhido": "NENHUM"},
         {"item_processado": 2, "pdm_escolhido": "NENHUM"}],
        [{"item_processado": 1, "pdm_escolhido": "NENHUM"}],
    ])

    resultado = cat.processar_lote(df, CATALOGO)

    assert len(cat._llm.prompts) == 3
    assert len(resultado) == 5


def test_processar_lote_sem_api_key_levanta_antes_de_chamar_a_ia():
    cat = cria_fichas.GeminiCategorizer("")

    with pytest.raises(ValueError, match="API Key"):
        cat.processar_lote(_df_um_item(), CATALOGO)


# =============================================================================
# E. Conferência do que o portal gravou
# =============================================================================
def test_codigo_do_pdm_extrai_o_codigo_da_string_completa():
    assert cria_fichas.codigo_do_pdm(
        "PDM.4820.004 - VALVULA ESFERA"
    ) == "PDM.4820.004"


def test_codigo_do_pdm_acha_o_codigo_no_tooltip_do_portal():
    """O valor que volta do portal é o `data-tooltip` do combo, e ele traz a
    revisão junto -- não é a mesma string que foi digitada."""
    assert cria_fichas.codigo_do_pdm(
        "PDM.4820.004 - VALVULA ESFERA - Rev. 2"
    ) == "PDM.4820.004"


def test_codigo_do_pdm_devolve_vazio_quando_nao_ha_codigo():
    assert cria_fichas.codigo_do_pdm("VERIFICAR (PULADO)") == ""
    assert cria_fichas.codigo_do_pdm(None) == ""


# =============================================================================
# F. A REVISÃO do PDM (2026-09-23, relatório de recomendações da Itaipu)
# =============================================================================
# O relatório `28_Fichas_Recomendaciones_a_CMI_Sala_Segura` (82 páginas, 28
# fichas) NÃO pediu nenhuma troca de PDM: as 25 menções a PDM são três códigos,
# e todas dizem a mesma coisa -- "emplear el PDM X en su nueva revisión".
#
# O portal exibe o PDM como `CODIGO - NOME BASE, MODIFICADOR, R<revisao>`
# (a vírgula dupla de `PDM.4120.000 - UNIDADE EVAPORADORA, , R1`, com
# modificador vazio, é a prova do formato). Ou seja: a revisão vem junto no
# que o robô já captura do portal e grava na coluna "PDM usado" -- e ninguém
# olhava para ela.
def test_revisao_do_pdm_le_o_sufixo_que_o_portal_grava():
    assert cria_fichas.revisao_do_pdm(
        "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R1"
    ) == 1


def test_revisao_do_pdm_le_revisao_zero():
    """R0 é revisão de verdade, e `0` é falsy -- confundir com "não tem" faria
    a conferência calar justamente no caso mais desatualizado."""
    assert cria_fichas.revisao_do_pdm(
        "PDM.5925.008 - DISPARADOR, DISJUNTOR BAIXA TENSAO, R0"
    ) == 0


def test_revisao_do_pdm_devolve_none_quando_o_texto_nao_traz():
    """Nem toda linha tem revisão: `PDM.5836.000 - CAMERA, VIDEO` aparece sem
    ela na planilha real."""
    assert cria_fichas.revisao_do_pdm("PDM.5836.000 - CAMERA, VIDEO") is None
    assert cria_fichas.revisao_do_pdm("") is None


def test_revisao_do_pdm_nao_confunde_o_R_de_uma_palavra():
    """"R" seguido de dígito, no fim, precedido de vírgula -- e não qualquer
    R no meio do título."""
    assert cria_fichas.revisao_do_pdm("PDM.1234.001 - ROTOR, R2 PLUS") is None


# =============================================================================
# A troca de PDM na revisão (JanelaRevisaoPDM.editar_pdm) -- 2026-09-25
# =============================================================================
# O sintoma, do usuário: "seleciono e uso o PDM, mas ele não atualiza" (a
# revisão lia a escolha antes de a janela de escolha fechar). Os dois testes
# daqui usavam a janela da interface antiga, que saiu em 2026-10-15; a mesma
# garantia, na Qt, está em `tests/test_qt_janelas.py`:
#   - test_revisao_pdm_editar_com_catalogo_usa_a_janela_de_escolha (a escolha
#     chega ao dado e à tabela);
#   - test_revisao_pdm_troca_manual_marca_manual_na_confianca (a confiança
#     vira MANUAL);
#   - test_revisao_pdm_uma_linha_leva_o_2o_e_3o_lugar_ao_seletor.

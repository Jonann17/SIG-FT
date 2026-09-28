r"""
LISTA é UMA opção só -- `sigft/services/tech_specs.py` (2026-09-28).

O caso real, relatado pelo usuário. No PDM SAM, a característica TIPO:

    TIPO DE CARACTERÍSTICA: LISTA
    VALORES PT: "Proteção contra descargas atmosféricas, etc., para pulsos
                 pequenos, proteção contra pulsos residuais"
    VALORES ES: "Protección contra rayos, etc, para pequeños pulsos,
                 protección contra pulsos residuales"

A IA respondeu `"Protecao contra descargas atmosfericas, etc."` -- DUAS opções
numa resposta só. O `<select>` do portal aceita UMA; nenhuma opção casou e o
campo ficou para a pessoa preencher.

*"Cada vírgula ali no campo da resposta mapeado pelo excel PDM SAM é um
separador do que aparecerá na lista de opções [...] não pode ter duas
respostas quando a opção é LISTA."*

A causa estava no PROMPT (ver `tests/test_prompt_tech_specs_lista.py`): ele
mandava separar "múltiplos itens" de LISTA com ponto e vírgula e dizia que a
vírgula era "exclusiva para decimais" -- justamente o separador que o Master
usa entre as opções. Estes testes prendem a GARANTIA em código, que não
depende de o modelo obedecer:

  - resposta = UMA opção -> reescrita com o texto do Master, sem acento (PT e
    ES pela mesma posição);
  - resposta com duas opções, ou com nenhuma -> a IA é perguntada de novo, só
    sobre essas características, e responde pelo NÚMERO da opção;
  - se nem assim vier uma opção válida, a resposta fica como veio (a pessoa
    escolhe no portal). Adivinhar escreveria na ficha um valor plausível e
    errado; e nunca vira REMOVER.
"""
from __future__ import annotations

import inspect

import pytest

from sigft.services import tech_specs
from sigft.services.tech_specs import (
    conferir_listas,
    opcoes_da_lista,
    opcoes_na_resposta,
)

VALORES_PT = ("Proteção contra descargas atmosféricas, etc., para pulsos pequenos, "
              "proteção contra pulsos residuais")
VALORES_ES = ("Protección contra rayos, etc, para pequeños pulsos, "
              "protección contra pulsos residuales")

OPCOES_PT = [
    "Proteção contra descargas atmosféricas",
    "etc.",
    "para pulsos pequenos",
    "proteção contra pulsos residuais",
]
OPCOES_ES = [
    "Protección contra rayos",
    "etc",
    "para pequeños pulsos",
    "protección contra pulsos residuales",
]


def _contexto_tipo(**extra):
    """A linha do Master, como `preparar_dados_ia` a monta para a IA."""
    entrada = {
        "CARACTERISTICA_DESC_PT": "TIPO",
        "TEXTO_AJUDA": ("Proteção contra descargas atmosféricas, proteção contra pulsos "
                        "residuais, para pulsos pequenos, etc."),
        "TIPO_DADO": "LISTA",
        "VALORES_POSSIVEIS_MASTER": VALORES_PT,
        "VALORES_POSSIVEIS_ES": VALORES_ES,
        "CASAS_DECIMAIS": "nan",
        "SIMBOLO_UNIDADE": "AD",
        "RESPOSTA_CRUA_PT": "Protetor de surto para descargas atmosféricas",
        "RESPOSTA_CRUA_ES": "Protector de sobretensión para rayos",
    }
    entrada.update(extra)
    return entrada


def _resposta_do_relato(**extra):
    """O item EXATO que a IA devolveu no relato do usuário."""
    item = {
        "CARACTERISTICA_CHAVE": "TIPO",
        "TIPO": "LISTA",
        "VALORES_PT": "Protecao contra descargas atmosfericas, etc.",
        "SUBTIPO_INTERVALO": None,
        "RESPOSTA_PT_FINAL": "Protecao contra descargas atmosfericas, etc.",
        "RESPOSTA_ES_FINAL": "Proteccion contra rayos, etc",
        "SIMBOLO": "AD",
        "ACAO": "PREENCHER",
    }
    item.update(extra)
    return item


# =============================================================================
# 1. As opções, lidas do Master
# =============================================================================
def test_cada_virgula_do_master_separa_uma_opcao():
    assert opcoes_da_lista(VALORES_PT) == OPCOES_PT
    assert opcoes_da_lista(VALORES_ES) == OPCOES_ES


def test_a_virgula_DECIMAL_nao_separa_opcao():
    """Numa LISTA de medidas, "1,5 mm" é UMA opção. A vírgula só separa
    quando não está entre dois algarismos."""
    assert opcoes_da_lista("1,5 mm, 2,5 mm, 10 mm") == ["1,5 mm", "2,5 mm", "10 mm"]


@pytest.mark.parametrize("vazio", ["", "   ", "nan", "NaN", "None", None])
def test_coluna_vazia_do_master_nao_tem_opcao(vazio):
    # `preparar_dados_ia` faz `str(row_m.get('VALORES PT', ''))`: a célula vazia
    # do pandas chega aqui como a string "nan".
    assert opcoes_da_lista(vazio) == []


# =============================================================================
# 2. Quantas opções a resposta traz
# =============================================================================
def test_a_resposta_do_relato_junta_DUAS_opcoes():
    assert opcoes_na_resposta(
        "Protecao contra descargas atmosfericas, etc.", OPCOES_PT) == [0, 1]


def test_uma_opcao_sem_acento_e_em_outra_caixa_e_reconhecida():
    # O prompt manda a IA não acentuar; a conferência não pode reprovar por isso.
    assert opcoes_na_resposta("PROTECAO CONTRA DESCARGAS ATMOSFERICAS", OPCOES_PT) == [0]


def test_etc_com_e_sem_ponto_e_a_mesma_opcao():
    # No relato, o PT tem "etc." e o ES tem "etc".
    assert opcoes_na_resposta("etc", OPCOES_PT) == [1]
    assert opcoes_na_resposta("etc.", OPCOES_ES) == [1]


def test_ponto_e_virgula_tambem_junta_opcoes():
    # Era o separador que o prompt antigo mandava usar para "vários itens".
    assert opcoes_na_resposta("para pulsos pequenos; etc.", OPCOES_PT) == [2, 1]


def test_texto_que_nao_e_opcao_nao_casa_com_nenhuma():
    assert opcoes_na_resposta("Protecao contra raios", OPCOES_PT) == []
    assert opcoes_na_resposta("", OPCOES_PT) == []
    assert opcoes_na_resposta(None, OPCOES_PT) == []


def test_a_mesma_opcao_repetida_conta_uma_vez():
    assert opcoes_na_resposta("etc., etc.", OPCOES_PT) == [1]


# =============================================================================
# 3. A conferência da resposta inteira
# =============================================================================
def test_uma_opcao_e_reescrita_com_o_texto_do_master_sem_acento_em_pt_e_es():
    """O texto do Master conserta caixa e pontuação ("etc" -> "etc."), e o ES
    vem da MESMA posição. SEM acento: se o portal estiver noutra revisão e a
    linha tiver virado CHAR, o robô recua e escreve este texto num campo que
    recusa acento ("Caracter inválido!")."""
    dado = _resposta_do_relato(RESPOSTA_PT_FINAL="PROTECAO CONTRA DESCARGAS ATMOSFERICAS",
                               RESPOSTA_ES_FINAL="Proteccion contra rayos")

    ajustados, problemas = conferir_listas([dado], [_contexto_tipo()])

    assert problemas == []
    assert ajustados[0]["RESPOSTA_PT_FINAL"] == "Protecao contra descargas atmosfericas"
    assert ajustados[0]["RESPOSTA_ES_FINAL"] == "Proteccion contra rayos"


def test_o_es_vem_da_posicao_do_pt_mesmo_que_a_ia_erre_o_es():
    dado = _resposta_do_relato(RESPOSTA_PT_FINAL="para pulsos pequenos",
                               RESPOSTA_ES_FINAL="para pulsos chicos")

    ajustados, _ = conferir_listas([dado], [_contexto_tipo()])

    assert ajustados[0]["RESPOSTA_ES_FINAL"] == "para pequenos pulsos"


def test_duas_opcoes_viram_problema_e_a_resposta_fica_intacta():
    """Escolher UMA das duas em código seria adivinhar -- e o palpite errado é
    invisível: a ficha sai com um valor plausível."""
    dado = _resposta_do_relato()

    ajustados, problemas = conferir_listas([dado], [_contexto_tipo()])

    assert ajustados == [dado]
    assert [p["CARACTERISTICA_CHAVE"] for p in problemas] == ["TIPO"]
    assert "2 opções" in problemas[0]["MOTIVO"]
    assert problemas[0]["RESPOSTA_RECUSADA"] == "Protecao contra descargas atmosfericas, etc."


def test_resposta_que_nao_e_opcao_tambem_vira_problema():
    dado = _resposta_do_relato(RESPOSTA_PT_FINAL="Protecao contra raios")

    _, problemas = conferir_listas([dado], [_contexto_tipo()])

    assert "nenhuma" in problemas[0]["MOTIVO"]


def test_so_confere_o_que_o_master_diz_que_e_LISTA():
    """Vírgula em CHAR é texto, não separador."""
    char = {"CARACTERISTICA_CHAVE": "MATERIAL", "TIPO": "CHAR", "ACAO": "PREENCHER",
            "RESPOSTA_PT_FINAL": "Aco, inox", "RESPOSTA_ES_FINAL": "Acero, inox"}
    contexto = [{"CARACTERISTICA_DESC_PT": "MATERIAL", "TIPO_DADO": "CHAR",
                 "VALORES_POSSIVEIS_MASTER": "nan", "VALORES_POSSIVEIS_ES": "nan"}]

    assert conferir_listas([char], contexto) == ([char], [])


def test_remover_nao_e_conferido():
    remover = {"CARACTERISTICA_CHAVE": "TIPO", "ACAO": "REMOVER"}

    assert conferir_listas([remover], [_contexto_tipo()]) == ([remover], [])


def test_lista_sem_opcoes_no_master_fica_como_veio():
    """Sem as opções não há o que conferir -- e recusar por isso trocaria uma
    resposta possivelmente certa por um campo em branco."""
    dado = _resposta_do_relato()
    contexto = [_contexto_tipo(VALORES_POSSIVEIS_MASTER="nan", VALORES_POSSIVEIS_ES="nan")]

    assert conferir_listas([dado], contexto) == ([dado], [])


def test_caracteristica_fora_do_contexto_fica_como_veio():
    dado = _resposta_do_relato(CARACTERISTICA_CHAVE="OUTRA")

    assert conferir_listas([dado], [_contexto_tipo()]) == ([dado], [])


def test_o_nome_da_caracteristica_casa_sem_acento():
    """O prompt manda a IA não acentuar; o Master acentua. "TENSÃO" e
    "TENSAO" são a mesma característica."""
    dado = _resposta_do_relato(CARACTERISTICA_CHAVE="TENSAO DE OPERACAO",
                               RESPOSTA_PT_FINAL="etc", RESPOSTA_ES_FINAL="etc")
    contexto = [_contexto_tipo(CARACTERISTICA_DESC_PT="TENSÃO DE OPERAÇÃO")]

    ajustados, problemas = conferir_listas([dado], contexto)

    assert problemas == []
    assert ajustados[0]["RESPOSTA_PT_FINAL"] == "etc."


def test_es_desencontrado_do_pt_nao_e_pareado_por_posicao():
    """Com 4 opções em PT e 3 em ES, a posição não serve de ponte: vale o ES
    da IA, quando ele for UMA opção do ES."""
    contexto = [_contexto_tipo(VALORES_POSSIVEIS_ES="Protección contra rayos, etc, otra")]
    dado = _resposta_do_relato(RESPOSTA_PT_FINAL="para pulsos pequenos",
                               RESPOSTA_ES_FINAL="OTRA")

    ajustados, _ = conferir_listas([dado], contexto)

    assert ajustados[0]["RESPOSTA_PT_FINAL"] == "para pulsos pequenos"
    assert ajustados[0]["RESPOSTA_ES_FINAL"] == "otra"


def test_os_outros_itens_passam_intactos_e_na_mesma_ordem():
    num = {"CARACTERISTICA_CHAVE": "TENSAO NOMINAL", "TIPO": "NUM", "ACAO": "PREENCHER",
           "RESPOSTA_PT_FINAL": "440", "RESPOSTA_ES_FINAL": "440", "SIMBOLO": "V"}
    dado = _resposta_do_relato(RESPOSTA_PT_FINAL="etc.")

    ajustados, _ = conferir_listas([num, dado], [_contexto_tipo()])

    assert ajustados[0] is num
    assert ajustados[1]["CARACTERISTICA_CHAVE"] == "TIPO"


# =============================================================================
# 4. A segunda pergunta à IA -- só sobre as LISTA com problema, pelo NÚMERO
# =============================================================================
class _LLMFalso:
    """Duplo de `LLMClient`: devolve as respostas na ordem configurada e guarda
    os prompts recebidos."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.prompts = []

    def generate(self, prompt, **_kw):
        self.prompts.append(prompt)
        valor = self.respostas.pop(0)
        if isinstance(valor, Exception):
            raise valor
        return type("_Resp", (), {"parsed_json": valor})()


def _processor(respostas):
    proc = tech_specs.TechSpecsProcessor.__new__(tech_specs.TechSpecsProcessor)
    proc._llm = _LLMFalso(respostas)
    return proc


def test_duas_opcoes_pedem_a_ia_de_novo_e_ela_responde_pelo_NUMERO():
    logs = []
    proc = _processor([[{"CARACTERISTICA_CHAVE": "TIPO", "NUMERO_DA_OPCAO": 1}]])

    dados = proc.garantir_uma_opcao_por_lista(
        [_resposta_do_relato()], [_contexto_tipo()], logs.append)

    assert dados[0]["RESPOSTA_PT_FINAL"] == "Protecao contra descargas atmosfericas"
    assert dados[0]["RESPOSTA_ES_FINAL"] == "Proteccion contra rayos"
    assert len(proc._llm.prompts) == 1
    assert any("TIPO" in linha and "2 opções" in linha for linha in logs), logs


def test_o_pedido_leva_as_opcoes_numeradas_e_a_resposta_recusada():
    proc = _processor([[{"CARACTERISTICA_CHAVE": "TIPO", "NUMERO_DA_OPCAO": 4}]])

    dados = proc.garantir_uma_opcao_por_lista([_resposta_do_relato()], [_contexto_tipo()])

    pedido = proc._llm.prompts[0]
    assert "Protecao contra descargas atmosfericas, etc." in pedido  # o que foi recusado
    for opcao in OPCOES_PT + OPCOES_ES:
        assert opcao in pedido
    assert "NUMERO_DA_OPCAO" in pedido
    assert dados[0]["RESPOSTA_PT_FINAL"] == "protecao contra pulsos residuais"


def test_a_resposta_certa_de_primeira_nao_gasta_chamada():
    proc = _processor([])
    dado = _resposta_do_relato(RESPOSTA_PT_FINAL="etc.", RESPOSTA_ES_FINAL="etc")

    dados = proc.garantir_uma_opcao_por_lista([dado], [_contexto_tipo()])

    assert proc._llm.prompts == []
    assert dados[0]["RESPOSTA_PT_FINAL"] == "etc."


def test_o_pedido_vai_so_com_as_listas_com_problema():
    modo = _contexto_tipo(CARACTERISTICA_DESC_PT="MODO",
                          VALORES_POSSIVEIS_MASTER="Manual, Automatico",
                          VALORES_POSSIVEIS_ES="Manual, Automatico")
    certa = _resposta_do_relato(CARACTERISTICA_CHAVE="MODO", RESPOSTA_PT_FINAL="Manual",
                                RESPOSTA_ES_FINAL="Manual")
    proc = _processor([[{"CARACTERISTICA_CHAVE": "TIPO", "NUMERO_DA_OPCAO": 1}]])

    proc.garantir_uma_opcao_por_lista([certa, _resposta_do_relato()], [modo, _contexto_tipo()])

    pedido = proc._llm.prompts[0]
    assert '"CARACTERISTICA_CHAVE": "TIPO"' in pedido
    assert '"CARACTERISTICA_CHAVE": "MODO"' not in pedido


def test_numero_fora_da_lista_mantem_a_resposta_e_avisa():
    logs = []
    proc = _processor([[{"CARACTERISTICA_CHAVE": "TIPO", "NUMERO_DA_OPCAO": 7}]])
    dado = _resposta_do_relato()

    dados = proc.garantir_uma_opcao_por_lista([dado], [_contexto_tipo()], logs.append)

    assert dados == [dado]              # nunca vira REMOVER, nunca um palpite
    assert any("à mão" in linha for linha in logs), logs


def test_ia_que_insiste_nas_duas_opcoes_tambem_fica_para_a_pessoa():
    proc = _processor([[{"CARACTERISTICA_CHAVE": "TIPO", "NUMERO_DA_OPCAO": "1, 2"}]])
    dado = _resposta_do_relato()

    assert proc.garantir_uma_opcao_por_lista([dado], [_contexto_tipo()]) == [dado]


def test_erro_de_rede_na_segunda_pergunta_nao_derruba_a_ficha():
    logs = []
    proc = _processor([ConnectionError("Connection aborted.")])
    dado = _resposta_do_relato()

    dados = proc.garantir_uma_opcao_por_lista([dado], [_contexto_tipo()], logs.append)

    assert dados == [dado]
    assert any("Connection aborted" in linha for linha in logs), logs


def test_envelope_e_numero_em_texto_na_resposta_da_correcao_sao_aceitos():
    # Mesma tolerância de formato da 1ª resposta (`normalizar_resposta_specs`).
    proc = _processor([{"itens": [{"CARACTERISTICA_CHAVE": "Tipo", "NUMERO_DA_OPCAO": "2"}]}])

    dados = proc.garantir_uma_opcao_por_lista([_resposta_do_relato()], [_contexto_tipo()])

    assert dados[0]["RESPOSTA_PT_FINAL"] == "etc."
    assert dados[0]["RESPOSTA_ES_FINAL"] == "etc"


# =============================================================================
# 5. No portal: a opção IGUAL (sem acento) vence a que só a contém
# =============================================================================
class _SelectDoPortal:
    """`<select>` cujas opções têm acento: o exato nunca casa com a resposta
    sem acento, e a regra do serviço decide pelo índice."""

    def __init__(self, opcoes):
        self._opcoes = list(opcoes)
        self.escolhida = None

    def opcoes(self, _seletor):
        return list(self._opcoes)

    def selecionar_por_texto(self, _seletor, texto):
        if texto not in self._opcoes:
            raise ValueError(texto)
        self.escolhida = texto

    def selecionar_por_indice(self, _seletor, indice):
        self.escolhida = self._opcoes[indice]


def _automacao_sobre(select):
    automacao = tech_specs.TechSpecsAutomation()
    automacao.engine = select
    return automacao


def test_no_portal_a_opcao_IGUAL_sem_acento_vence_a_que_so_a_contem():
    """A substring pegaria a PRIMEIRA opção que contém a resposta: "Aco"
    casaria "Aço inox", que vem antes de "Aço" nesta tela."""
    select = _SelectDoPortal(["Aço inox", "Aço"])

    assert _automacao_sobre(select).selecionar_dropdown_lista("//select", "Aco") is True
    assert select.escolhida == "Aço"


def test_no_portal_a_opcao_do_relato_sem_acento_e_selecionada():
    select = _SelectDoPortal(OPCOES_PT)

    assert _automacao_sobre(select).selecionar_dropdown_lista(
        "//select", "Protecao contra descargas atmosfericas",
        alternativas=("Proteccion contra rayos",)) is True
    assert select.escolhida == "Proteção contra descargas atmosféricas"


def test_no_portal_a_resposta_do_relato_nao_casa_com_nenhuma_opcao():
    """O erro relatado, reproduzido: duas opções numa resposta não são
    nenhuma das opções da tela."""
    select = _SelectDoPortal(OPCOES_PT)
    logs = []

    assert _automacao_sobre(select).selecionar_dropdown_lista(
        "//select", "Protecao contra descargas atmosfericas, etc.",
        alternativas=("Proteccion contra rayos, etc",),
        nome_campo="TIPO", callback_log=logs.append) is False
    assert any("nenhuma opção casou" in linha for linha in logs), logs


def test_preparar_dados_ia_passa_pela_garantia_antes_de_gravar_o_resultado():
    """`preparar_dados_ia` lê Excel de verdade (pandas), então não roda aqui.
    O que se prende é a ORDEM: a garantia vem logo depois da resposta da IA e
    antes de o resultado virar o JSON que o robô lê."""
    fonte = inspect.getsource(tech_specs.TechSpecsProcessor.preparar_dados_ia)

    chamada_da_ia = fonte.index("self._chamar_gemini_specs(")
    garantia = fonte.index("self.garantir_uma_opcao_por_lista(")
    resultado = fonte.index("resultados_processados.append(")
    assert chamada_da_ia < garantia < resultado

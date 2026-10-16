"""As regras do portal conferidas ANTES de abrir o navegador (R2 de
`docs/PMIB_ENGENHARIA_REVERSA.md` §8).

Um teste por regra, com o caso que passa e o que não passa. As regras saem da
§5 e do Apêndice D; o que o robô de cada tela PULA (status desligado, "NENHUM")
não é conferido.
"""
import dataclasses

import pytest

from sigft.core import pmib_regras as r


def _so(problemas, interno):
    return [p for p in problemas if p.interno == interno]


# =============================================================================
# Problema e utilidades
# =============================================================================
def test_problema_e_congelado():
    p = r.Problema(ficha="X", campo="C", interno="I", valor="v", regra="R", mensagem="M")
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.ficha = "Y"


def test_valor_encurtado_a_60():
    linhas = [{"descricao_original": "A", "descricao_curta": "A" * 100, "codigo_projeto": "P"}]
    (p,) = r.conferir_cria_fichas(linhas)
    assert len(p.valor) <= 60 and p.valor.endswith("…")


def test_fichas_com_erro_e_resumo():
    linhas = [
        {"descricao_original": "A", "descricao_curta": "OK", "codigo_projeto": "P"},
        {"descricao_original": "B", "descricao_curta": "", "codigo_projeto": ""},
        {"descricao_original": "C", "descricao_curta": "Ç", "codigo_projeto": "P"},
    ]
    problemas = r.conferir_cria_fichas(linhas)
    assert r.fichas_com_erro(problemas) == {1, 2}
    assert r.resumo(problemas, 3) == "3 problema(s) em 2 ficha(s) de 3"


def test_linha_do_console_diz_o_que_e_onde():
    (p,) = r.conferir_cria_fichas([{"descricao_original": "VALVULA", "descricao_curta": "A" * 52,
                                    "codigo_projeto": "P"}])
    linha = r.linha_do_console(p)
    assert "VALVULA" in linha and "Texto breve do material" in linha
    assert "Input_ShortText" in linha and "tem 52 caracteres; o portal aceita até 40" in linha


# =============================================================================
# 1. Criação de Fichas
# =============================================================================
def _cf(**campos):
    base = {"descricao_original": "VALVULA ESFERA", "pdm_escolhido": "PDM.1.1 - VALVULA",
            "descricao_curta": "VALVULA ESFERA 2POL", "codigo_projeto": "PRJ-1"}
    base.update(campos)
    return [base]


def test_cf_linha_boa_nao_tem_problema():
    assert r.conferir_cria_fichas(_cf()) == []


def test_cf_texto_breve_ate_40_depois_do_strip():
    assert r.conferir_cria_fichas(_cf(descricao_curta="  " + "A" * 40 + "  ")) == []
    (p,) = r.conferir_cria_fichas(_cf(descricao_curta="A" * 41))
    assert p.interno == "Input_ShortText" and p.campo == "Texto breve do material"
    assert p.mensagem == "tem 41 caracteres; o portal aceita até 40"
    assert p.ficha == "VALVULA ESFERA"


def test_cf_texto_breve_obrigatorio():
    for vazio in ("", "   ", None, float("nan")):
        (p,) = r.conferir_cria_fichas(_cf(descricao_curta=vazio))
        assert p.interno == "Input_ShortText" and "vazio" in p.mensagem


def test_cf_texto_breve_sem_acento_nem_cedilha():
    (p,) = r.conferir_cria_fichas(_cf(descricao_curta="VÁLVULA CONEXÃO"))
    assert "Á" in p.mensagem and "Ã" in p.mensagem
    (p,) = r.conferir_cria_fichas(_cf(descricao_curta="ACO ç"))
    assert "ç" in p.mensagem


def test_cf_texto_breve_caracteres_aceitos():
    assert r.conferir_cria_fichas(_cf(descricao_curta="Parafuso M8 1.5,x-2/3_(A)")) == []


def test_cf_texto_breve_comeca_com_letra():
    (p,) = r.conferir_cria_fichas(_cf(descricao_curta="8 PARAFUSOS"))
    assert "letra" in p.mensagem
    (p,) = r.conferir_cria_fichas(_cf(descricao_curta="(A) PARAFUSO"))
    assert "letra" in p.mensagem


def test_cf_minuscula_nao_e_problema():
    assert r.conferir_cria_fichas(_cf(descricao_curta="valvula esfera")) == []


def test_cf_codigo_projeto_obrigatorio_e_ate_1000():
    (p,) = r.conferir_cria_fichas(_cf(codigo_projeto=""))
    assert p.interno == "TextArea_ProjectCode" and "vazio" in p.mensagem
    (p,) = r.conferir_cria_fichas(_cf(codigo_projeto="X" * 1001))
    assert p.mensagem == "tem 1001 caracteres; o portal aceita até 1000"
    assert r.conferir_cria_fichas(_cf(codigo_projeto="X" * 1000)) == []


def test_cf_nenhum_nao_e_conferido():
    assert r.conferir_cria_fichas(_cf(pdm_escolhido="NENHUM", descricao_curta="", codigo_projeto="")) == []


def test_cf_ficha_sem_descricao_original_usa_o_texto_breve_ou_o_numero():
    (p,) = r.conferir_cria_fichas(_cf(descricao_original="", codigo_projeto=""))
    assert p.ficha == "VALVULA ESFERA 2POL"
    (p,) = r.conferir_cria_fichas(_cf(descricao_original=None, descricao_curta=""))
    assert p.ficha == "Item 1"


def test_cf_nao_mexe_na_entrada():
    linhas = _cf(descricao_curta="  valvula  ")
    r.conferir_cria_fichas(linhas)
    assert linhas[0]["descricao_curta"] == "  valvula  "


# =============================================================================
# 2. Upload Condições
# =============================================================================
def _cond(**mudar):
    ficha = {
        "pmib_codigo": "4500.0001",
        "dimensoes": {"comprimento": "10", "largura": "20", "altura": "30"},
        "controle_temperatura": {
            "necessidade": "SIM",
            "climatizacao": {"ativo": True, "temp_max": "40", "temp_min": "-10"},
            "umidade": {"ativo": True, "hr_max": "80", "hr_min": "20"},
        },
        "posicao_armazenamento": "Vertical",
        "nocivo": {"status": "Nocivo", "cuidado_es": "cuidado", "cuidado_pt": "cuidado"},
        "peso": {"liquido": "1,5", "bruto": "2"},
        "protecao": ["UV"],
        "empilhamento": "3",
        "outros_cuidados": {"status": "SIM", "cuidado_es": "otro", "cuidado_pt": "outro"},
        "embalagem_transp_es": "caja", "embalagem_transp_pt": "caixa",
        "posicao_icagem_es": "N/A", "posicao_icagem_pt": "N/A",
        "cuidad_preserv_es": "x", "cuidad_preserv_pt": "x",
        "limpeza_secagem_es": "x", "limpeza_secagem_pt": "x",
        "ferramentas_es": "x", "ferramentas_pt": "x",
        "legislacao_es": "ley", "legislacao_pt": "lei",
        "perigoso_10004": "NÃO",
        "descarte_es": "reciclaje", "descarte_pt": "reciclagem",
        "logistica_reversa": {"status": "SIM", "logistica_reversa_es": "si", "logistica_reversa_pt": "sim"},
    }
    for caminho, valor in mudar.items():
        alvo = ficha
        partes = caminho.split("__")
        for parte in partes[:-1]:
            alvo = alvo[parte]
        alvo[partes[-1]] = valor
    return [ficha]


def test_cond_ficha_boa_nao_tem_problema():
    assert r.conferir_condicoes(_cond()) == []


def test_cond_numericos_ate_30():
    (p,) = r.conferir_condicoes(_cond(dimensoes__largura="1" * 31))
    assert p.interno == "Input_PackagingWidth" and p.ficha == "4500.0001"
    assert p.mensagem == "tem 31 caracteres; o portal aceita até 30"
    for caminho, interno in (("dimensoes__comprimento", "Input_PackingLength"),
                             ("dimensoes__altura", "Input_PackagingHeight"),
                             ("controle_temperatura__climatizacao__temp_max", "Input_MaximumTemperature"),
                             ("controle_temperatura__climatizacao__temp_min", "Input_MinimumTemperature"),
                             ("controle_temperatura__umidade__hr_max", "Input_MaxHR"),
                             ("controle_temperatura__umidade__hr_min", "Input_MinHR"),
                             ("peso__liquido", "Input_LiquidWeight"),
                             ("peso__bruto", "Input_GrossWeight"),
                             ("empilhamento", "Input_Stacking")):
        (p,) = r.conferir_condicoes(_cond(**{caminho: "9" * 31}))
        assert p.interno == interno


def test_cond_sem_negativo_em_dimensao_peso_e_umidade():
    for caminho, interno in (("dimensoes__altura", "Input_PackagingHeight"),
                             ("peso__bruto", "Input_GrossWeight"),
                             ("controle_temperatura__umidade__hr_min", "Input_MinHR")):
        (p,) = r.conferir_condicoes(_cond(**{caminho: "-5"}))
        assert p.interno == interno and "negativo" in p.mensagem


def test_cond_temperatura_pode_ser_negativa():
    assert r.conferir_condicoes(_cond(controle_temperatura__climatizacao__temp_max="-2")) == []


def test_cond_numero_de_verdade_e_texto_na_sao_aceitos():
    assert r.conferir_condicoes(_cond(dimensoes__altura=12.5, peso__bruto="N/A")) == []
    (p,) = r.conferir_condicoes(_cond(peso__liquido=-1))
    assert p.interno == "Input_LiquidWeight"


def test_cond_temperatura_e_umidade_so_quando_o_robo_preenche():
    sem = r.conferir_condicoes(_cond(controle_temperatura__necessidade="NÃO",
                                     controle_temperatura__umidade__hr_min="-5"))
    assert sem == []
    desligada = r.conferir_condicoes(_cond(controle_temperatura__umidade__ativo=False,
                                           controle_temperatura__umidade__hr_min="-5"))
    assert desligada == []


def test_cond_cuidados_ate_500():
    (p,) = r.conferir_condicoes(_cond(nocivo__cuidado_pt="x" * 501))
    assert p.interno == "TextArea_StorageCarePT"
    assert p.mensagem == "tem 501 caracteres; o portal aceita até 500"
    (p,) = r.conferir_condicoes(_cond(outros_cuidados__cuidado_es="x" * 501))
    assert p.interno == "TextArea_OtherCareES"


def test_cond_cuidados_es_e_pt_juntos():
    (p,) = r.conferir_condicoes(_cond(nocivo__cuidado_pt=""))
    assert p.interno == "TextArea_StorageCarePT" and "os dois idiomas" in p.mensagem
    (p,) = r.conferir_condicoes(_cond(nocivo__cuidado_es=" "))
    assert p.interno == "TextArea_StorageCareES" and "os dois idiomas" in p.mensagem
    (p,) = r.conferir_condicoes(_cond(outros_cuidados__cuidado_es=""))
    assert p.interno == "TextArea_OtherCareES"
    # nenhum dos dois: o portal aceita
    assert r.conferir_condicoes(_cond(nocivo__cuidado_es="", nocivo__cuidado_pt="")) == []


def test_cond_cuidados_so_quando_o_status_liga():
    assert r.conferir_condicoes(_cond(nocivo__status="Não nocivo", nocivo__cuidado_pt="x" * 900)) == []
    assert r.conferir_condicoes(_cond(outros_cuidados__status="NÃO", outros_cuidados__cuidado_es="")) == []


def test_cond_transporte_e_manutencao_ate_1000():
    for chave, interno in (("embalagem_transp_es", "TextArea_TransportPackagingES"),
                           ("posicao_icagem_pt", "TextArea_PositionCarePT"),
                           ("cuidad_preserv_es", "TextArea_PreservationCareES"),
                           ("limpeza_secagem_pt", "TextArea_CleaningMethodPT"),
                           ("ferramentas_es", "TextArea_ToolPreservationES")):
        (p,) = r.conferir_condicoes(_cond(**{chave: "x" * 1001}))
        assert p.interno == interno
    assert r.conferir_condicoes(_cond(embalagem_transp_es="x" * 1000)) == []


def test_cond_descarte_obrigatorio_e_ate_1000():
    for chave, interno in (("legislacao_es", "TextArea_TypeLegislationES"),
                           ("legislacao_pt", "TextArea_TypeLegislationPT"),
                           ("descarte_es", "TextArea_DiscardTypeES"),
                           ("descarte_pt", "TextArea_DiscardTypePT")):
        (p,) = r.conferir_condicoes(_cond(**{chave: ""}))
        assert p.interno == interno and "vazio" in p.mensagem
        (p,) = r.conferir_condicoes(_cond(**{chave: "x" * 1001}))
        assert p.interno == interno


def test_cond_descarte_ausente_e_o_vazio_que_o_robo_escreveria():
    (ficha,) = _cond()
    del ficha["legislacao_pt"]
    (p,) = r.conferir_condicoes([ficha])
    assert p.interno == "TextArea_TypeLegislationPT"


def test_cond_logistica_reversa_aplica_exige_texto():
    (p,) = r.conferir_condicoes(_cond(logistica_reversa__logistica_reversa_pt=""))
    assert p.interno == "TextArea_ReserveLogisticPT"
    assert r.conferir_condicoes(_cond(logistica_reversa__status="NÃO",
                                      logistica_reversa__logistica_reversa_pt="")) == []


def test_cond_ficha_incompleta_nao_quebra():
    # O robô mesmo derruba a seção com KeyError; a conferência não pode cair.
    problemas = r.conferir_condicoes([{"pmib_codigo": "X"}])
    assert {p.interno for p in problemas} == {
        "TextArea_TypeLegislationES", "TextArea_TypeLegislationPT",
        "TextArea_DiscardTypeES", "TextArea_DiscardTypePT"}


# =============================================================================
# 3. Upload Tech Specs
# =============================================================================
def _ts(*itens, pmib="4500.0002"):
    return [{"METADATA": {"PMIB": pmib, "PDM": "PDM.X"}, "DADOS_TRATADOS": list(itens)}]


def _item(tipo, pt, es="", acao="PREENCHER", chave="DIAMETRO"):
    return {"CARACTERISTICA_CHAVE": chave, "ACAO": acao, "TIPO": tipo,
            "RESPOSTA_PT_FINAL": pt, "RESPOSTA_ES_FINAL": es}


def test_ts_char_ate_1000_nos_dois_idiomas():
    assert r.conferir_tech_specs(_ts(_item("CHAR", "x" * 1000, "y" * 1000))) == []
    (p,) = r.conferir_tech_specs(_ts(_item("CHAR", "x" * 1001, "y")))
    assert p.interno == "TextArea_ValuePT" and p.campo == "DIAMETRO" and p.ficha == "4500.0002"
    (p,) = r.conferir_tech_specs(_ts(_item("CHAR", "x", "y" * 1001)))
    assert p.interno == "TextArea_ValueES"


def test_ts_num_ate_15():
    assert r.conferir_tech_specs(_ts(_item("NUM", "123456789012345"))) == []
    (p,) = r.conferir_tech_specs(_ts(_item("NUM", "1234567890123456")))
    assert p.interno == "NumberValue_Input"
    assert p.mensagem == "tem 16 caracteres; o portal aceita até 15"


def test_ts_int_min_e_max():
    assert r.conferir_tech_specs(_ts(_item("INT", "10 / 20"))) == []
    (p,) = r.conferir_tech_specs(_ts(_item("INT", "10")))
    assert p.interno == "MaxValue_Input" and "vazio" in p.mensagem
    (p,) = r.conferir_tech_specs(_ts(_item("INT", " / 20")))
    assert p.interno == "MinValue_Input"
    (p,) = r.conferir_tech_specs(_ts(_item("INT", "1234567890123456 / 2")))
    assert p.interno == "MinValue_Input" and "15" in p.mensagem


def test_ts_so_preencher_e_tipo_conhecido():
    assert r.conferir_tech_specs(_ts(_item("CHAR", "x" * 2000, acao="REMOVER"))) == []
    assert r.conferir_tech_specs(_ts(_item("LISTA", "x" * 2000))) == []
    (p,) = r.conferir_tech_specs(_ts(_item(" num ", "1" * 16, acao=" preencher ")))
    assert p.interno == "NumberValue_Input"


def test_ts_numero_de_verdade():
    assert r.conferir_tech_specs(_ts(_item("NUM", 12.5))) == []


# =============================================================================
# 4. Upload LMR
# =============================================================================
def test_lmr_codigo_ate_200_tag_ate_150_e_nao_vazia():
    assert r.conferir_lmr([("4500.3", [("EQ-1", ["T1", "T2"])])]) == []
    (p,) = r.conferir_lmr([("4500.3", [("E" * 201, ["T1"])])])
    assert p.interno == "Input_EquipmentCode" and p.ficha == "4500.3"
    (p,) = r.conferir_lmr([("4500.3", [("EQ-1", ["T" * 151])])])
    assert p.interno == "Input_Tag"
    assert p.mensagem == "tem 151 caracteres; o portal aceita até 150"
    (p,) = r.conferir_lmr([("4500.3", [("EQ-1", ["T1", ""])])])
    assert p.interno == "Input_Tag" and "vazi" in p.mensagem


def test_lmr_tag_nan_e_celula_vazia():
    (p,) = r.conferir_lmr([("4500.3", [("EQ-1", ["nan"])])])
    assert p.interno == "Input_Tag" and "nan" in p.mensagem


def test_lmr_quantidade_ate_10_digitos():
    assert r.MAX_DIGITOS_QUANTIDADE == 10
    assert r.conferir_lmr([("4500.3", [("EQ-1", ["T"] * 3)])]) == []


def test_lmr_indice_e_a_posicao_da_ficha():
    problemas = r.conferir_lmr([("A", [("EQ", ["T"])]), ("B", [("EQ", [""])])])
    assert r.fichas_com_erro(problemas) == {1}


def test_lmr_tag_so_com_espaco_mostra_o_valor_vazio():
    (p,) = r.conferir_lmr([("A", [("EQ", [" "])])])
    assert p.valor == ""

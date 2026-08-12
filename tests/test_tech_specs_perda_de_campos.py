r"""
Os 16 campos que sumiam entre a IA e o portal.

Caso REAL de 2026-08-11, ficha 4500063671.1471 (PDM.4320.002): a IA devolveu
**37 PREENCHER — exatamente os 37 campos que o fornecedor preencheu na
ficha** — e só 21 chegaram ao portal. A leitura natural foi "o modelo é
fraco". Não era: os outros 16 foram apagados pelo nosso próprio código, e
ainda por cima viraram EXCLUSÃO de linha no portal.

A cadeia inteira:

  1. o Master (SAM) é filtrado só por CÓDIGO PDM, e guarda uma linha por
     característica POR REVISÃO -- 106 linhas em 3 revisões para 51
     características reais;
  2. o contexto enviado à IA levava as 106, então a IA respondia a mesma
     característica 2-3 vezes: PREENCHER (revisão vigente) e REMOVER
     (revisões antigas, que não têm resposta do fornecedor);
  3. o RPA montava o índice com um dict comprehension, onde o ÚLTIMO vence --
     e o último era sempre o REMOVER da revisão velha.

Duas correções independentes, e as duas precisam existir: deduplicar o
contexto ataca a causa, e a precedência no índice é a rede para quando um
modelo repetir chave por conta própria.
"""
import pytest

from sigft.services.tech_specs import deduplicar_contexto, indexar_por_caracteristica


def _norm(texto):
    return str(texto).strip().upper()


# ===========================================================================
# Índice: PREENCHER vence REMOVER
# ===========================================================================
def test_remover_depois_de_preencher_nao_apaga_a_resposta():
    """A ORDEM do caso real: a revisão vigente vem primeiro, as antigas
    depois. Com "o último vence", o REMOVER da revisão velha ganhava."""
    dados = [
        {"CARACTERISTICA_CHAVE": "TENSAO NOMINAL", "ACAO": "PREENCHER",
         "TIPO": "NUM", "RESPOSTA_PT_FINAL": "440"},
        {"CARACTERISTICA_CHAVE": "TENSAO NOMINAL", "ACAO": "REMOVER"},
    ]

    indice = indexar_por_caracteristica(dados, _norm)

    assert indice["TENSAO NOMINAL"]["ACAO"] == "PREENCHER"
    assert indice["TENSAO NOMINAL"]["RESPOSTA_PT_FINAL"] == "440"


def test_preencher_depois_de_remover_tambem_vence():
    # A ordem inversa não pode depender da sorte: o critério é a AÇÃO, não a
    # posição.
    dados = [
        {"CARACTERISTICA_CHAVE": "VAZAO", "ACAO": "REMOVER"},
        {"CARACTERISTICA_CHAVE": "VAZAO", "ACAO": "PREENCHER",
         "TIPO": "NUM", "RESPOSTA_PT_FINAL": "145"},
    ]

    assert indexar_por_caracteristica(dados, _norm)["VAZAO"]["RESPOSTA_PT_FINAL"] == "145"


def test_dois_preencher_na_mesma_chave_fica_o_primeiro():
    # No Master a revisão vigente vem antes; ela é a que tem o TIPO e a ajuda
    # corretos.
    dados = [
        {"CARACTERISTICA_CHAVE": "X", "ACAO": "PREENCHER", "TIPO": "NUM", "RESPOSTA_PT_FINAL": "vigente"},
        {"CARACTERISTICA_CHAVE": "X", "ACAO": "PREENCHER", "TIPO": "CHAR", "RESPOSTA_PT_FINAL": "antiga"},
    ]

    assert indexar_por_caracteristica(dados, _norm)["X"]["RESPOSTA_PT_FINAL"] == "vigente"


def test_so_remover_continua_removendo():
    """A correção não pode transformar exclusão legítima em preenchimento:
    característica sem resposta do fornecedor TEM de sair da ficha."""
    dados = [
        {"CARACTERISTICA_CHAVE": "FATOR DE POTENCIA", "ACAO": "REMOVER"},
        {"CARACTERISTICA_CHAVE": "FATOR DE POTENCIA", "ACAO": "REMOVER"},
    ]

    assert indexar_por_caracteristica(dados, _norm)["FATOR DE POTENCIA"]["ACAO"] == "REMOVER"


def test_a_normalizacao_da_chave_continua_sendo_a_do_chamador():
    # O casamento com a tela usa `normalizar_texto` do processador; o índice
    # não pode ter uma segunda regra de normalização.
    dados = [{"CARACTERISTICA_CHAVE": "  tensao nominal  ", "ACAO": "REMOVER"}]

    assert list(indexar_por_caracteristica(dados, _norm)) == ["TENSAO NOMINAL"]


def test_o_caso_real_recupera_os_16_campos():
    """Reprodução do JSON real (resumida): 3 características que existem em
    mais de uma revisão do PDM."""
    dados = []
    for chave, valor in [("TENSAO NOMINAL", "440"), ("VAZAO", "145"), ("GRAU DE PROTECAO", "IP65")]:
        dados.append({"CARACTERISTICA_CHAVE": chave, "ACAO": "PREENCHER",
                      "TIPO": "CHAR", "RESPOSTA_PT_FINAL": valor})
    # ... e as revisões antigas, todas REMOVER, DEPOIS.
    for chave in ("TENSAO NOMINAL", "VAZAO", "GRAU DE PROTECAO", "TENSAO NOMINAL"):
        dados.append({"CARACTERISTICA_CHAVE": chave, "ACAO": "REMOVER"})

    indice = indexar_por_caracteristica(dados, _norm)

    preenchidos = [k for k, v in indice.items() if v["ACAO"] == "PREENCHER"]
    assert sorted(preenchidos) == ["GRAU DE PROTECAO", "TENSAO NOMINAL", "VAZAO"]


# ===========================================================================
# Contexto: uma característica por nome
# ===========================================================================
def _linha(nome, tipo="NUM", ajuda="ajuda boa"):
    return {"CARACTERISTICA_DESC_PT": nome, "TIPO_DADO": tipo, "TEXTO_AJUDA": ajuda}


def test_contexto_manda_cada_caracteristica_uma_vez():
    contexto = [_linha("TENSAO NOMINAL"), _linha("VAZAO"), _linha("TENSAO NOMINAL")]

    assert [e["CARACTERISTICA_DESC_PT"] for e in deduplicar_contexto(contexto)] == [
        "TENSAO NOMINAL", "VAZAO",
    ]


def test_fica_a_linha_da_revisao_vigente_que_vem_primeiro():
    """As revisões antigas trazem TIPO_DADO e ajuda DEGRADADOS -- na revisão 0
    do PDM.4320.002 tudo é "CHAR" e a ajuda é vazia. Ficar com a errada
    empurraria a IA para o tipo errado."""
    contexto = [
        _linha("TENSAO NOMINAL", tipo="NUM", ajuda="Indique a tensão nominal em (V)"),
        _linha("TENSAO NOMINAL", tipo="CHAR", ajuda=""),
    ]

    unico = deduplicar_contexto(contexto)[0]
    assert unico["TIPO_DADO"] == "NUM"
    assert unico["TEXTO_AJUDA"]


def test_comparacao_ignora_espaco_e_caixa():
    contexto = [_linha("Tensao Nominal"), _linha("  TENSAO NOMINAL  ")]

    assert len(deduplicar_contexto(contexto)) == 1


def test_contexto_sem_repeticao_atravessa_intacto():
    contexto = [_linha("A"), _linha("B"), _linha("C")]

    assert deduplicar_contexto(contexto) == contexto


def test_contexto_vazio_nao_levanta():
    assert deduplicar_contexto([]) == []


@pytest.mark.parametrize("faltando", [{}, {"CARACTERISTICA_DESC_PT": ""}])
def test_entrada_sem_nome_nao_derruba_a_deduplicacao(faltando):
    # Master com célula vazia existe; virar exceção aqui mataria a ficha
    # inteira por causa de uma linha.
    assert len(deduplicar_contexto([faltando, _linha("A")])) == 2

r"""
Contrato da resposta da IA do módulo de Características Técnicas
(`tech_specs.normalizar_resposta_specs`).

Nasceu de um caso REAL (2026-08-11): o 1º lote rodado num modelo que não é o
Gemini. O prompt pede uma LISTA de objetos no nível raiz; o MiniMax M3
devolveu `{"items": [...]}` e renomeou quase todo campo. O sintoma na tela do
usuário foi `TypeError: string indices must be integers, not 'str'`, 13
segundos depois de o robô já estar dentro do portal -- uma mensagem que não
fala de IA, de JSON nem de modelo.

Os dois níveis do estrago, que estes testes separam:

  1. o ENVELOPE (`{"items": [...]}`) fazia `for d in dados` iterar as CHAVES,
     então `d` virava a string "items";
  2. corrigido só o envelope, os NOMES DE CAMPO trocados passariam batido --
     o RPA lê com `dado.get("RESPOSTA_PT_FINAL", "")` e escreveria a ficha
     inteira em BRANCO, reportando sucesso. É o motivo de a validação de
     chaves existir, e de ela NÃO traduzir nomes.
"""
import json

import pytest

from sigft.services.tech_specs import normalizar_resposta_specs


# --- o formato certo atravessa intacto -------------------------------------

_ITEM_OK = {
    "CARACTERISTICA_CHAVE": "TENSAO NOMINAL",
    "TIPO": "NUM",
    "RESPOSTA_PT_FINAL": "440",
    "RESPOSTA_ES_FINAL": "440",
    "SIMBOLO": "V",
    "SUBTIPO_INTERVALO": None,
    "ACAO": "PREENCHER",
}


def test_lista_no_formato_do_prompt_passa_sem_alteracao():
    lista = [dict(_ITEM_OK)]

    assert normalizar_resposta_specs(lista) == lista


def test_item_de_remover_nao_precisa_dos_campos_de_preenchimento():
    # No JSON real, os REMOVER vêm só com chave/ação/justificativa -- exigir
    # TIPO/RESPOSTA deles reprovaria uma resposta correta.
    lista = [{"CARACTERISTICA_CHAVE": "RECALQUE", "ACAO": "REMOVER",
              "JUSTIFICATIVA": "Resposta nao fornecida (nan)."}]

    assert normalizar_resposta_specs(lista) == lista


def test_lista_vazia_e_valida():
    assert normalizar_resposta_specs([]) == []


# --- o envelope é desembrulhado --------------------------------------------

@pytest.mark.parametrize("nome_do_envelope", ["items", "itens", "dados", "caracteristicas", "qualquer"])
def test_envelope_de_uma_chave_e_desembrulhado(nome_do_envelope):
    # O nome não importa: o que identifica o envelope é ser um objeto de UMA
    # chave só. Amarrar a uma lista de nomes conhecidos só adiaria o problema
    # para o próximo modelo.
    assert normalizar_resposta_specs({nome_do_envelope: [dict(_ITEM_OK)]}) == [_ITEM_OK]


def test_envelope_aninhado_tambem_e_desembrulhado():
    assert normalizar_resposta_specs({"resultado": {"items": [dict(_ITEM_OK)]}}) == [_ITEM_OK]


# --- o que a IA do caso real devolveu --------------------------------------

_RESPOSTA_MINIMAX = {
    "items": [
        {"CARACTERISTICA_CHAVE": "NORMAS TECNICAS APLICAVEIS", "ACAO": "REMOVER",
         "JUSTIFICATIVA": "Resposta nao fornecida (nan)."},
        {"CARACTERISTICA_CHAVE": "TENSAO NOMINAL", "ACAO": "PREENCHER",
         "TIPO_DADO": "NUM", "RESPOSTA_NORMALIZADA_PT": "440 V",
         "RESPOSTA_NORMALIZADA_ES": "440 V", "SIMBOLO_UNIDADE": "V"},
    ]
}


def test_a_resposta_real_do_minimax_e_recusada_com_mensagem_acionavel():
    with pytest.raises(ValueError) as erro:
        normalizar_resposta_specs(_RESPOSTA_MINIMAX)

    mensagem = str(erro.value)
    # Diz o que falta...
    assert "TIPO" in mensagem and "RESPOSTA_PT_FINAL" in mensagem
    # ...o que veio no lugar (é isso que faz o usuário entender na hora)...
    assert "RESPOSTA_NORMALIZADA_PT" in mensagem
    # ...e o que fazer a respeito.
    assert "Modelos de IA" in mensagem


def test_o_item_de_remover_do_minimax_sozinho_seria_aceito():
    """Contraste que prova que a recusa acima é pelos CAMPOS, não pelo
    envelope: o mesmo envelope, com só o item REMOVER, passa."""
    so_remover = {"items": [_RESPOSTA_MINIMAX["items"][0]]}

    assert normalizar_resposta_specs(so_remover) == [_RESPOSTA_MINIMAX["items"][0]]


# --- formatos que não dá para salvar ---------------------------------------

def test_none_e_recusado():
    with pytest.raises(ValueError, match="não devolveu resposta"):
        normalizar_resposta_specs(None)


def test_texto_solto_e_recusado_dizendo_o_que_veio():
    with pytest.raises(ValueError) as erro:
        normalizar_resposta_specs("desculpe, não consegui processar")

    assert "LISTA" in str(erro.value)
    assert "desculpe" in str(erro.value)


def test_lista_com_string_dentro_e_recusada():
    # É EXATAMENTE o que produzia o TypeError original: algo iterável cujos
    # elementos são strings.
    with pytest.raises(ValueError, match="não um objeto JSON"):
        normalizar_resposta_specs(["items"])


def test_dicionario_de_varias_chaves_nao_e_confundido_com_envelope():
    with pytest.raises(ValueError, match="LISTA"):
        normalizar_resposta_specs({"CARACTERISTICA_CHAVE": "X", "ACAO": "PREENCHER"})


def test_envelope_auto_referente_nao_trava():
    # JSON malformado pode aninhar envelopes sem fim; o teto de
    # desembrulhamento existe para o app não pendurar.
    fundo = {"a": {"b": {"c": {"d": [dict(_ITEM_OK)]}}}}

    with pytest.raises(ValueError, match="LISTA"):
        normalizar_resposta_specs(fundo)


def test_a_mensagem_de_erro_nao_despeja_o_json_inteiro_no_log():
    # O contexto de uma ficha tem dezenas de características; jogar tudo no
    # console esconde a mensagem que importa.
    gigante = json.dumps([{"lixo": "x" * 5000}])

    with pytest.raises(ValueError) as erro:
        normalizar_resposta_specs(gigante)

    assert len(str(erro.value)) < 400


def test_simbolo_ausente_e_legitimo_e_nao_reprova():
    """Característica sem unidade é caso NORMAL, não erro.

    O RPA faz `simb = dado.get("SIMBOLO"); if simb:` -- ausência significa
    "não mexe no dropdown de unidade". A 1ª versão desta validação exigia
    `SIMBOLO` e reprovou 4 testes de `processar_lista` que estavam certos;
    este teste é a marca daquele erro, para ele não voltar.
    """
    sem_simbolo = [{"CARACTERISTICA_CHAVE": "MATERIAL", "TIPO": "CHAR",
                    "RESPOSTA_PT_FINAL": "ACO INOX", "ACAO": "PREENCHER"}]

    assert normalizar_resposta_specs(sem_simbolo) == sem_simbolo


def test_tipo_ausente_reprova_porque_o_rpa_pularia_a_linha_calado():
    with pytest.raises(ValueError, match="TIPO"):
        normalizar_resposta_specs(
            [{"CARACTERISTICA_CHAVE": "X", "RESPOSTA_PT_FINAL": "1", "ACAO": "PREENCHER"}]
        )


def test_resposta_ausente_reprova_porque_o_rpa_escreveria_vazio_no_portal():
    with pytest.raises(ValueError, match="RESPOSTA_PT_FINAL"):
        normalizar_resposta_specs(
            [{"CARACTERISTICA_CHAVE": "X", "TIPO": "NUM", "ACAO": "PREENCHER"}]
        )

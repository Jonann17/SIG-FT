r"""
O prompt do Upload de Características Técnicas e a LISTA (2026-09-28).

A causa do erro relatado estava no TEXTO do prompt. Ele mandava separar
"múltiplos itens selecionados" de LISTA com PONTO E VÍRGULA e dizia que a
vírgula era "exclusiva para decimais". Só que, no PDM SAM, a VÍRGULA é
justamente o que separa uma opção da outra em VALORES PT/ES. A IA leu

    "Proteção contra descargas atmosféricas, etc., para pulsos pequenos, ..."

como texto corrido e devolveu "Protecao contra descargas atmosfericas, etc."
-- duas opções num campo que aceita uma.

As fixtures de snapshot foram regeradas junto (ver a 4ª regeração em
tests/test_llm_prompts_snapshot.py). Uma fixture regerada não pode se
auto-aprovar: o que ela não prova sobre si mesma -- o CONTEÚDO da regra -- é o
que estes testes checam. A garantia em código, que não depende de o modelo
obedecer, está em tests/test_tech_specs_lista_uma_opcao.py.
"""
from sigft.core.llm import prompts

_TUDO = prompts.SYSTEM_TECH_SPECS + prompts.CONTRATO_SAIDA_TECH_SPECS


def test_o_prompt_nao_pede_mais_varias_opcoes_numa_lista():
    assert "múltiplos itens selecionados" not in _TUDO
    assert "múltiplos valores devem ser separados" not in _TUDO
    assert "NUNCA use vírgula para separar itens" not in _TUDO


def test_o_system_prompt_diz_que_a_virgula_separa_as_opcoes():
    assert "cada VÍRGULA separa uma opção" in prompts.SYSTEM_TECH_SPECS


def test_o_system_prompt_diz_que_a_resposta_e_UMA_opcao():
    assert "UMA opção só" in prompts.SYSTEM_TECH_SPECS
    assert "NUNCA junte duas opções" in prompts.SYSTEM_TECH_SPECS


def test_o_contrato_repete_a_regra_no_fim_do_prompt():
    """O fim do prompt é a posição de maior peso -- é onde o contrato de saída
    mora desde 2026-08-11."""
    contrato = prompts.CONTRATO_SAIDA_TECH_SPECS

    assert "separadas por VIRGULA" in contrato
    assert "UMA so" in contrato
    assert '"Nylon, etc."' in contrato     # a forma do erro do relato, com outro dado


def test_o_exemplo_nao_usa_o_dado_do_relato():
    """Um exemplo com a característica real ("descargas atmosféricas")
    empurraria a IA para essa opção em toda ficha de protetor de surto. O
    exemplo mostra a FORMA do erro com um dado neutro."""
    assert "descargas" not in _TUDO.lower()
    assert "Nylon" in prompts.SYSTEM_TECH_SPECS
    assert "Nylon" in prompts.CONTRATO_SAIDA_TECH_SPECS


def test_a_virgula_continua_sendo_o_separador_DECIMAL_de_NUM_e_INT():
    # A regra que existia e está certa -- só não vale para as opções da LISTA.
    assert "SEPARADOR DECIMAL" in prompts.SYSTEM_TECH_SPECS


def test_o_pedido_de_correcao_da_lista_pede_o_NUMERO_e_leva_os_dados():
    texto = prompts.montar_tech_specs_lista_unica('[{"CARACTERISTICA_CHAVE": "TIPO"}]')

    assert '[{"CARACTERISTICA_CHAVE": "TIPO"}]' in texto
    assert "NUMERO_DA_OPCAO" in texto
    assert "UMA" in texto
    # O formato fecha o prompt, como no contrato de saída.
    assert texto.rstrip().endswith("]")


def test_o_exemplo_do_pedido_de_correcao_e_json_valido():
    """Exemplo inválido ensinaria o modelo a errar -- e ninguém perceberia até
    rodar (mesmo cuidado de `test_o_exemplo_do_contrato_e_json_valido...`)."""
    import json
    import re

    texto = prompts.montar_tech_specs_lista_unica("[]")
    exemplo = json.loads(re.sub(r"\s+", " ", texto[texto.rindex("["):]).strip())

    assert exemplo == [{"CARACTERISTICA_CHAVE": "NOME DA CARACTERISTICA", "NUMERO_DA_OPCAO": 2}]

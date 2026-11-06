"""AutoSpec: o número do modelo do item não é medida deduzida (2026-11-06).

Rodada da 1.4.0-rc.5 pelo Workflow AMP, acoplador WAGO 750-362: APLICACAO e FUNCAO ficaram
vazias com "a IA DEDUZIU um valor com numero", e o único número dos dois era o 750 de "sistema
WAGO I/O 750" -- a série do próprio modelo do item (`750-362`, da coluna MARCA/MODELO do
_STATUS_PMIB). Número que faz parte do modelo e não leva unidade é NOME, não medida. A regra
de sempre continua: medida deduzida não entra.
"""
from __future__ import annotations

from sigft.services import autospec_evidencia as ev
from sigft.services.autospec import AutoSpecCore

APLICACAO = ("Acoplador de barramento de campo Modbus TCP para o sistema WAGO I/O 750, ligando os "
             "módulos de E/S à rede Ethernet")
FUNCAO = "Acoplamento de módulos de E/S do sistema WAGO I/O 750 à rede Modbus TCP/UDP"
PERGUNTA_APLICACAO = ("12 - APLICACAO (Indicar a aplicação do item. Nota: mencionar o equipamento "
                      "(tipo, modelo))")
PERGUNTA_FUNCAO = "20 - FUNCAO (Indicar a função básica do item ex.: Distribuição de fonte de alimentação de dados.)"
DOC = ("--- LOCAL DOC: Data sheet 750-362.pdf ---\n[página 1]\n"
       "Fieldbus Coupler Modbus TCP; 4th generation\n")


# -- a regra --------------------------------------------------------------------------------

def test_o_numero_da_serie_do_modelo_nao_bloqueia_a_deducao():
    assert ev.deducao_permitida(FUNCAO, modelo="750-362")
    assert ev.deducao_permitida(APLICACAO, modelo="750-362")


def test_o_codigo_inteiro_do_modelo_tambem_e_nome():
    assert ev.deducao_permitida("Acoplador 750-362 para rede Modbus TCP", modelo="750-362")


def test_sem_o_modelo_o_numero_continua_bloqueando():
    assert not ev.deducao_permitida(FUNCAO)


def test_o_numero_do_modelo_com_unidade_e_medida():
    assert not ev.deducao_permitida("Motor de 750 W", modelo="750-362")


def test_numero_que_nao_e_do_modelo_continua_bloqueando():
    assert not ev.deducao_permitida("Até 250 módulos no sistema WAGO I/O 750", modelo="750-362")


def test_algarismo_solto_do_modelo_nao_libera_uma_contagem():
    """`3K6` tem um 3, e `3 polos` continua sendo um número deduzido."""
    assert not ev.deducao_permitida("Motor de 3 polos", modelo="MOD SVTN 3K6 W")


# -- a rodada da rc.5 -----------------------------------------------------------------------

def test_aplicacao_e_funcao_da_rodada_entram_como_deducao():
    core = AutoSpecCore.__new__(AutoSpecCore)
    core._modelo_do_item = "750-362"
    core.ultimas_evidencias_por_campo = {
        "var_row_90": ev.Evidencia(tipo="deducao", fonte="conhecimento tecnico",
                                   justificativa="Aplicação típica do acoplador 750-362."),
        "var_row_98": ev.Evidencia(tipo="deducao", fonte="Data sheet 750-362.pdf", pagina=1,
                                   trecho="Fieldbus Coupler Modbus TCP; 4th generation",
                                   justificativa="Função básica de um acoplador de barramento de campo."),
    }
    aprovados = core._filtrar_por_lastro(
        {"var_row_90": APLICACAO, "var_row_98": FUNCAO},
        {"var_row_90": {"desc": PERGUNTA_APLICACAO}, "var_row_98": {"desc": PERGUNTA_FUNCAO}}, DOC)
    assert aprovados == {"var_row_90": APLICACAO, "var_row_98": FUNCAO}
    assert "deducao tecnica" in core.notas_por_campo["var_row_90"]

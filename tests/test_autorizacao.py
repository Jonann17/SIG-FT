r"""
A regra da autorização de entrega de Itaipu (T2 do roteiro "Gestão PMIB no
tratamento v2") -- `sigft/services/autorizacao.py`.

Fonte: `gestao-sobressalentes/07 - Diagnostico/Tarefa SIG-FT - Calculo e
Gravacao sem Perda.md`, seção 2.1 (decisões do Luan, 04-05/10/2026), e a
implementação de referência `situacao_autorizacao()` de
`gestao-sobressalentes/_scripts/regras_sobressalentes.py`.

Os 13 CASOS são os mesmos do kit de teste (`_gestao_v2/gerar_kit_teste_sigft.py`,
linhas 6-18 do `_STATUS_PMIB` sintético), com hoje = 2026-10-10 e o resultado
de `esperado.json`. Se um deles mudar, muda também lá -- o Power BI v2 e o
painel HTML contam a partir do que esta regra grava.

Só stdlib: a suíte roda com pandas/numpy de mentira (`tests/conftest.py`).
"""
from __future__ import annotations

import datetime as dt

import pytest

from sigft import config
from sigft.services import autorizacao as aut

HOJE = dt.date(2026, 10, 10)
F, D, T = "FÍSICA E DOCUMENTAL", "DOCUMENTAL", "TÍTULO"
E1, E2, E3 = dt.date(2026, 9, 15), dt.date(2026, 10, 1), dt.date(2026, 9, 4)

# linha do kit: (TIPO, DATA DO EMAIL, SITUAÇÃO antes, DIAS antes, ENTREGUE, STATUS,
#                SITUAÇÃO esperada, DIAS esperados, por quê)
CASOS = {
    6: (F, E1, None, None, None, None, "ATRASADO ITAIPU", 4, "prazo 06/10, hoje 10/10"),
    7: (F, E2, None, None, None, None, "AGUARDANDO ITAIPU", None, "prazo 23/10"),
    8: (F, E1, "AUTORIZADO", 2, None, None, "AUTORIZADO", 2, "marcação de fato e dias congelados"),
    9: (F, None, None, None, None, None, "", None, "sem e-mail"),
    10: (D, E1, None, None, None, None, "N/A", None, "DOCUMENTAL não precisa de autorização"),
    11: (T, E1, None, None, None, None, "N/A", None, "TÍTULO não precisa de autorização"),
    12: (None, E1, None, None, None, None, "", None, "TIPO vazio não conta"),
    13: (F, E1, None, None, "SIM", None, "AUTORIZADO", None, "entregue implica autorizado"),
    14: (F, E1, None, None, None, "DUPLICADO", "", None, "DUPLICADO repete a ficha de outra linha"),
    15: (D, None, "AUTORIZADO", None, None, None, "AUTORIZADO", None, "marcação de fato vale mesmo em DOCUMENTAL"),
    16: (F, E3, None, None, None, None, "ATRASADO ITAIPU", 12, "04/09 + 15 d.u. pula o feriado de 07/09"),
    17: (F, E2, "ATRASADO ITAIPU", 30, None, None, "AGUARDANDO ITAIPU", None, "estado calculado é recalculado"),
    18: (D, None, "AGUARDANDO ITAIPU", None, None, None, "N/A", None, "estado calculado antigo é corrigido"),
}


# ===========================================================================
# A. Os 13 casos do kit
# ===========================================================================
@pytest.mark.parametrize("linha", sorted(CASOS))
def test_os_13_casos_do_kit(linha):
    tipo, email, situacao, dias, entregue, status, sit_esp, dias_esp, por_que = CASOS[linha]

    resultado = aut.situacao_autorizacao(email, situacao, entregue, HOJE, dias, tipo, status)

    assert resultado == (sit_esp, dias_esp), f"linha {linha}: {por_que}"


# ===========================================================================
# B. Prazo = e-mail + 15 dias úteis (o WORKDAY do Excel)
# ===========================================================================
@pytest.mark.parametrize("email, prazo", [
    (dt.date(2026, 9, 15), dt.date(2026, 10, 6)),
    (dt.date(2026, 9, 4), dt.date(2026, 9, 28)),    # 07/09 é feriado
    (dt.date(2026, 10, 1), dt.date(2026, 10, 23)),  # 12/10 é feriado
])
def test_os_tres_prazos_do_roteiro(email, prazo):
    assert aut.prazo_autorizacao(email) == prazo
    assert aut.somar_dias_uteis(email, 15) == prazo


def test_um_dia_util_depois_de_sexta_antes_do_feriado_e_terca():
    # README do cofre, D2: 04/09/2026 (sexta) + 1 d.u. = 08/09 (07/09 é feriado).
    assert aut.somar_dias_uteis(dt.date(2026, 9, 4), 1) == dt.date(2026, 9, 8)


def test_email_no_fim_de_semana_nao_ganha_dia_a_mais():
    # Sábado + 1 d.u. = segunda (o WORKDAY conta a partir do dia seguinte).
    assert aut.somar_dias_uteis(dt.date(2026, 9, 19), 1) == dt.date(2026, 9, 21)
    assert aut.somar_dias_uteis(dt.date(2026, 9, 19), 15) == aut.somar_dias_uteis(dt.date(2026, 9, 18), 15)


def test_o_prazo_e_15_dias_uteis():
    assert config.PRAZO_AUTORIZACAO_DIAS_UTEIS == 15


def test_bate_com_o_busday_offset_do_numpy_em_1500_datas():
    # O README do cofre conferiu `np.busday_offset(datas, 15, roll="backward",
    # holidays=FERIADOS)` contra o DIATRABALHO do Excel em 1.500 datas
    # seguidas. A regra aqui é só stdlib; a conferência usa o numpy de verdade.
    numpy = pytest.importorskip("numpy")
    if not hasattr(numpy, "busday_offset") or "Mock" in type(numpy).__name__:
        pytest.skip("numpy real não disponível")
    feriados = numpy.array(sorted(config.FERIADOS), dtype="datetime64[D]")
    inicio = dt.date(2024, 1, 1)
    for i in range(1500):
        email = inicio + dt.timedelta(days=i)
        if email.year > 2027 and email.month > 10:
            break  # perto do fim da tabela de feriados
        esperado = numpy.busday_offset(numpy.datetime64(email, "D"), 15, roll="backward", holidays=feriados)
        assert numpy.datetime64(aut.somar_dias_uteis(email, 15), "D") == esperado, email


# ===========================================================================
# C. Feriados num lugar só
# ===========================================================================
def test_feriados_moram_no_config_e_cobrem_2024_a_2028():
    anos = {d.year for d in config.FERIADOS}
    assert anos == {2024, 2025, 2026, 2027, 2028}
    assert dt.date(2026, 9, 7) in config.FERIADOS
    assert dt.date(2026, 10, 12) in config.FERIADOS
    assert dt.date(2026, 2, 16) in config.FERIADOS  # Carnaval
    assert dt.date(2026, 6, 4) in config.FERIADOS   # Corpus Christi


def test_feriados_podem_ser_trocados_por_quem_chama():
    # Sem o 07/09, 04/09 + 1 d.u. cai no próprio 07/09.
    sem_independencia = {d: n for d, n in config.FERIADOS.items() if d != dt.date(2026, 9, 7)}
    assert aut.somar_dias_uteis(dt.date(2026, 9, 4), 1, feriados=sem_independencia) == dt.date(2026, 9, 7)


# ===========================================================================
# D. Normalização do texto da planilha
# ===========================================================================
@pytest.mark.parametrize("escrito, canonico", [
    ("FÍSICA E DOCUMENTAL", F), ("FISICA E DOCUMENTAL", F), ("física  e documental", F),
    ("FÍSICO E DOCUMENTAL", F), ("DOCUMENTAL", D), ("APENAS DOCUMENTAL", D), ("TÍTULO", T),
    ("TITULO", T), ("CONJUNTO", T), ("CONJUNTO (TÍTULO)", T), (None, None), ("", None),
    ("OUTRA COISA", None),
])
def test_tipo_de_entrega_canonico(escrito, canonico):
    assert aut.tipo_canonico(escrito) == canonico


def test_normalizar_tira_acento_caixa_e_espaco_extra():
    assert aut.normalizar("  Situação   da  autorização ") == "SITUACAO DA AUTORIZACAO"
    assert aut.normalizar(None) == ""
    assert aut.normalizar(float("nan")) == ""


def test_sim_do_layout_antigo_vale_como_autorizado():
    # Arquivo antigo: APTO PARA ENTREGA = SIM virou AUTORIZADO na migração.
    assert aut.situacao_autorizacao(E1, "SIM", None, HOJE, None, F) == ("AUTORIZADO", None)
    assert aut.situacao_autorizacao(E1, " autorizado ", None, HOJE, 3, F) == ("AUTORIZADO", 3)


def test_entregue_em_minusculas_e_com_espaco_vale():
    assert aut.situacao_autorizacao(E1, None, " sim ", HOJE, None, F) == ("AUTORIZADO", None)


def test_duplicado_autorizado_continua_autorizado():
    # A regra 1 só vale quando a linha DUPLICADO não está AUTORIZADA.
    assert aut.situacao_autorizacao(E1, "AUTORIZADO", None, HOJE, 5, F, "DUPLICADO") == ("AUTORIZADO", 5)


def test_duplicado_com_material_entregue_fica_autorizado():
    # A regra 1 vale DEPOIS do cálculo, como na referência (`recalcular_situacao`)
    # e no Power BI v2: entregue é fato de autorização, mesmo numa linha
    # DUPLICADO. (A tabela do roteiro a lista primeiro; ver PENDENCIAS.md.)
    assert aut.situacao_autorizacao(None, None, "SIM", HOJE, None, None, "DUPLICADO") == ("AUTORIZADO", None)
    assert aut.situacao_autorizacao(E1, None, "SIM", HOJE, 3, F, "DUPLICADO") == ("AUTORIZADO", 3)
    # ...mas DOCUMENTAL entregue é N/A antes de ser AUTORIZADO, e o DUPLICADO apaga.
    assert aut.situacao_autorizacao(E1, None, "SIM", HOJE, None, D, "DUPLICADO") == ("", None)


def test_status_duplicado_com_acento_ou_caixa_diferente():
    assert aut.situacao_autorizacao(E1, None, None, HOJE, None, F, " duplicado ") == ("", None)


def test_no_dia_do_prazo_ainda_esta_aguardando():
    prazo = aut.prazo_autorizacao(E1)
    assert aut.situacao_autorizacao(E1, None, None, prazo, None, F) == ("AGUARDANDO ITAIPU", None)
    um_dia_depois = prazo + dt.timedelta(days=1)
    assert aut.situacao_autorizacao(E1, None, None, um_dia_depois, None, F) == ("ATRASADO ITAIPU", 1)


def test_atraso_conta_dias_corridos_e_nao_uteis():
    # Prazo 06/10 (terça); 12/10 é feriado e 10-11/10 são fim de semana --
    # e mesmo assim são 7 dias de atraso em 13/10.
    assert aut.situacao_autorizacao(E1, None, None, dt.date(2026, 10, 13), None, F) == ("ATRASADO ITAIPU", 7)


# ===========================================================================
# E. O que vem das células: data e dias
# ===========================================================================
def test_data_do_email_em_todos_os_formatos_que_a_planilha_entrega():
    assert aut.para_data(dt.datetime(2026, 9, 15, 0, 0)) == E1
    assert aut.para_data(E1) == E1
    assert aut.para_data("15/09/2026") == E1
    assert aut.para_data(" 2026-09-15 ") == E1
    assert aut.para_data("") is None
    assert aut.para_data(None) is None
    assert aut.para_data(float("nan")) is None
    assert aut.para_data("A CONFIRMAR") is None
    assert aut.para_data("15/9/2026") == E1


def test_data_do_email_como_numero_de_serie_como_no_power_bi():
    # O `fxData` do Power BI v2 (o painel oficial) lê número entre 40000 e
    # 60000 como data -- célula de data que perdeu o formato. Quem grava a
    # situação e quem a mostra têm de ler a mesma data.
    assert aut.para_data(46280) == E1
    assert aut.para_data(46280.0) == E1
    assert aut.para_data(4) is None       # não é data: é o DIAS DE ATRASO de alguém
    assert aut.para_data(60000) is None
    assert aut.para_data(True) is None


def test_nat_do_pandas_e_vazio():
    # `pd.NaT` é "verdadeiro" num `if` e quebra em `.date()`; ele tem a marca
    # de todo vazio do pandas: é diferente de si mesmo.
    class _NaTFalso(dt.datetime):
        def __ne__(self, outro):
            return True

        def __eq__(self, outro):
            return False

        __hash__ = dt.datetime.__hash__

    assert aut.para_data(_NaTFalso(2026, 1, 1)) is None


@pytest.mark.parametrize("valor, dias", [
    (4, 4), (4.0, 4), ("4", 4), (None, None), ("", None), (float("nan"), None), ("abc", None),
    # DIAS DE ATRASO com formato de data herdado da vizinha: o openpyxl entrega
    # a data que o número representa (04/01/1900 = 4). Volta ao número.
    (dt.datetime(1900, 1, 4), 4), (dt.datetime(1900, 2, 28), 59), (dt.datetime(1900, 3, 1), 61),
    (dt.datetime(1900, 4, 9), 100), (dt.date(1900, 1, 12), 12),
])
def test_dias_da_celula(valor, dias):
    assert aut.dias_da_celula(valor) == dias


def test_dias_da_celula_e_o_inverso_do_openpyxl_de_verdade():
    from _openpyxl_de_verdade import openpyxl_de_verdade

    with openpyxl_de_verdade():
        from openpyxl.utils.datetime import from_excel

        # Sem o 60: é o "29/02/1900" que o Excel inventou, e o openpyxl o lê
        # como 28/02/1900 -- a mesma data do 59. Não há como distinguir.
        for numero in [n for n in range(1, 400) if n != 60] + [1000, 30000, 45000]:
            assert aut.dias_da_celula(from_excel(numero)) == numero, numero


# ===========================================================================
# F. Atraso congelado na hora da autorização (export de autorizados, T4)
# ===========================================================================
def test_atraso_na_autorizacao():
    # prazo de E1 = 06/10
    assert aut.dias_de_atraso_na_autorizacao(E1, dt.date(2026, 10, 6)) is None  # no prazo
    assert aut.dias_de_atraso_na_autorizacao(E1, dt.date(2026, 10, 9)) == 3
    assert aut.dias_de_atraso_na_autorizacao(None, dt.date(2026, 10, 9)) is None


def test_estados_e_constantes():
    assert aut.AUTORIZADO == "AUTORIZADO"
    assert set(aut.SITUACOES) == {"AGUARDANDO ITAIPU", "ATRASADO ITAIPU", "AUTORIZADO", "N/A"}

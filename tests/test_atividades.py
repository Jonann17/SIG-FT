"""`services/atividades.py` — a hierarquia e os totais da aba Atividades.

As regras aqui NÃO foram inventadas: saíram das fórmulas reais da planilha,
lidas em 2026-09-03. A que mais importa é a de `DATA DE TÉRMINO` — ela só
preenche quando TODAS as filhas estão concluídas, e um grupo com uma atividade
em aberto não pode ganhar data de término, senão a planilha diz que o trabalho
acabou quando ele não acabou.

A estrutura real: `NV=1` é grupo, `NV=2` atividade, `NV=3` subatividade. Os
totais contam as filhas DIRETAS (nível N+1), não todos os descendentes — como
`COUNTIFS($A22:$A25,2)` fazia.
"""
from __future__ import annotations

from sigft.services import atividades as at


def linha(nv=None, concluida=False, status=None, **datas):
    base = {
        "nv": nv,
        "concluida": concluida,
        "status": status,
        "data_prevista_inicio": "",
        "data_inicio": "",
        "previsao_termino": "",
        "data_termino": "",
    }
    base.update(datas)
    return base


# =============================================================================
# A. A hierarquia
# =============================================================================

def test_filhas_diretas_sao_as_de_nivel_seguinte():
    linhas = [linha(1), linha(2), linha(2), linha(1)]

    assert at.filhas_diretas(linhas, 0) == [1, 2]


def test_netos_nao_contam_como_filhas_diretas():
    """`COUNTIFS($A22:$A25,2)` contava só o nível 2, não o 3."""
    linhas = [linha(1), linha(2), linha(3), linha(3), linha(2)]

    assert at.filhas_diretas(linhas, 0) == [1, 4]


def test_a_hierarquia_para_no_proximo_grupo():
    linhas = [linha(1), linha(2), linha(1), linha(2)]

    assert at.filhas_diretas(linhas, 0) == [1]


def test_uma_atividade_folha_nao_tem_filhas():
    linhas = [linha(1), linha(2), linha(1)]

    assert at.filhas_diretas(linhas, 1) == []


def test_nivel_2_tambem_agrega_seus_netos():
    """Há linhas NV=2 com fórmulas: elas agregam as NV=3 abaixo."""
    linhas = [linha(1), linha(2), linha(3), linha(3), linha(2)]

    assert at.filhas_diretas(linhas, 1) == [2, 3]


def test_linha_sem_nv_e_ignorada():
    linhas = [linha(1), linha(None), linha(2)]

    assert at.filhas_diretas(linhas, 0) == [2]


def test_linhas_de_grupo_sao_as_de_nivel_1():
    linhas = [linha(1), linha(2), linha(1), linha(3)]

    assert at.linhas_de_grupo(linhas) == [0, 2]


# =============================================================================
# B. As contagens
# =============================================================================

def test_conta_atividades_concluidas_e_travadas():
    linhas = [
        linha(1),
        linha(2, concluida=True),
        linha(2, status="Travada"),
        linha(2),
    ]

    totais = at.agregar(linhas, 0)

    assert totais["atividades"] == 3
    assert totais["concluidas"] == 1
    assert totais["travadas"] == 1


def test_travada_ignora_caixa_e_espaco():
    linhas = [linha(1), linha(2, status="  travada  ")]

    assert at.agregar(linhas, 0)["travadas"] == 1


def test_concluida_aceita_booleano_e_texto():
    linhas = [
        linha(1),
        linha(2, concluida=True),
        linha(2, concluida="VERDADEIRO"),
        linha(2, concluida="TRUE"),
        linha(2, concluida=False),
        linha(2, concluida=""),
    ]

    assert at.agregar(linhas, 0)["concluidas"] == 3


def test_linha_sem_filhas_nao_gera_totais():
    """Escrever zeros numa atividade-folha seria pior que não escrever."""
    linhas = [linha(1), linha(2)]

    assert at.agregar(linhas, 1) is None


# =============================================================================
# C. As datas
# =============================================================================

def test_inicio_e_a_MENOR_data_das_filhas():
    linhas = [
        linha(1),
        linha(2, data_inicio="2026-08-10"),
        linha(2, data_inicio="2026-08-05"),
    ]

    assert at.agregar(linhas, 0)["data_inicio"] == "2026-08-05"


def test_previsao_de_termino_e_a_MAIOR():
    linhas = [
        linha(1),
        linha(2, previsao_termino="2026-09-01"),
        linha(2, previsao_termino="2026-09-15"),
    ]

    assert at.agregar(linhas, 0)["previsao_termino"] == "2026-09-15"


def test_data_vazia_nao_entra_no_calculo():
    linhas = [linha(1), linha(2, data_inicio=""), linha(2, data_inicio="2026-08-10")]

    assert at.agregar(linhas, 0)["data_inicio"] == "2026-08-10"


def test_sem_nenhuma_data_o_total_fica_vazio():
    linhas = [linha(1), linha(2), linha(2)]

    assert at.agregar(linhas, 0)["data_inicio"] == ""


# =============================================================================
# D. DATA DE TÉRMINO — a regra que não pode mentir
# =============================================================================

def test_termino_so_existe_com_TODAS_as_filhas_concluidas():
    linhas = [
        linha(1),
        linha(2, concluida=True, data_termino="2026-08-20"),
        linha(2, concluida=True, data_termino="2026-08-25"),
    ]

    assert at.agregar(linhas, 0)["data_termino"] == "2026-08-25"


def test_uma_filha_em_aberto_zera_a_data_de_termino():
    """O grupo NÃO terminou. Preencher a data diria que o trabalho acabou."""
    linhas = [
        linha(1),
        linha(2, concluida=True, data_termino="2026-08-20"),
        linha(2, concluida=False, data_termino="2026-08-25"),
    ]

    assert at.agregar(linhas, 0)["data_termino"] == ""


def test_todas_concluidas_mas_sem_data_registrada():
    linhas = [linha(1), linha(2, concluida=True), linha(2, concluida=True)]

    assert at.agregar(linhas, 0)["data_termino"] == ""


# =============================================================================
# E. recalcular() — a aba inteira
# =============================================================================

def test_recalcular_pega_so_quem_tem_filhas():
    linhas = [
        linha(1),                       # 0 grupo, tem filhas
        linha(2, concluida=True),       # 1 folha
        linha(2),                       # 2 tem filha
        linha(3),                       # 3 folha
        linha(1),                       # 4 grupo sem filhas
    ]

    totais = at.recalcular(linhas)

    assert set(totais) == {0, 2}
    assert totais[0]["atividades"] == 2   # as duas NV=2
    assert totais[2]["atividades"] == 1   # a NV=3


def test_recalcular_em_aba_vazia_nao_quebra():
    assert at.recalcular([]) == {}


def test_as_colunas_calculadas_nao_incluem_as_do_usuario():
    """STATUS, COM QUEM ESTÁ, DETALHE e CRITICIDADE são do usuário: o app lê,
    mas nunca escreve."""
    assert at.COL_STATUS not in at.COLUNAS_CALCULADAS
    assert at.COL_COM_QUEM not in at.COLUNAS_CALCULADAS
    assert at.COL_DETALHE not in at.COLUNAS_CALCULADAS
    assert at.COL_CRITICIDADE not in at.COLUNAS_CALCULADAS
    assert at.COL_DESCRICAO not in at.COLUNAS_CALCULADAS


def test_o_modulo_nao_depende_de_excel():
    import ast
    import inspect

    arvore = ast.parse(inspect.getsource(at))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])

    assert "openpyxl" not in importados
    assert "pandas" not in importados


# =============================================================================
# F. Tipos misturados na coluna de data
# =============================================================================
# Encontrado na PRIMEIRA execução contra a planilha real: quase toda célula de
# data é `datetime`, mas alguma traz texto onde devia haver data. O `min()`
# entre `str` e `datetime` levanta TypeError, e o lote inteiro morria por causa
# de uma célula. Os testes sintéticos não pegaram porque usavam só strings.

def test_texto_no_meio_de_datas_nao_derruba_o_calculo():
    from datetime import datetime

    linhas = [
        linha(1),
        linha(2, data_inicio=datetime(2026, 8, 10)),
        linha(2, data_inicio="anotação onde devia haver data"),
        linha(2, data_inicio=datetime(2026, 8, 5)),
    ]

    totais = at.agregar(linhas, 0)  # não pode levantar

    assert totais["data_inicio"] == datetime(2026, 8, 5)


def test_havendo_datas_o_texto_e_descartado():
    """A coluna é de data: a data manda."""
    from datetime import datetime

    linhas = [
        linha(1),
        linha(2, previsao_termino="zzz texto que ordenaria por último"),
        linha(2, previsao_termino=datetime(2026, 9, 1)),
    ]

    assert at.agregar(linhas, 0)["previsao_termino"] == datetime(2026, 9, 1)


def test_coluna_so_de_texto_ainda_funciona():
    linhas = [linha(1), linha(2, data_inicio="2026-08-10"), linha(2, data_inicio="2026-08-05")]

    assert at.agregar(linhas, 0)["data_inicio"] == "2026-08-05"


def test_data_como_date_puro_tambem_conta():
    from datetime import date

    linhas = [linha(1), linha(2, data_inicio=date(2026, 8, 10))]

    assert at.agregar(linhas, 0)["data_inicio"] == date(2026, 8, 10)


# =============================================================================
# G. O mural — agrupado por TEMPO
# =============================================================================
# Agrupa por tempo, não por status: a pergunta que o usuário faz ao abrir é
# "o que é para fazer hoje?", e status é atributo da atividade, não relação
# com a data de hoje. Uma primeira versão agrupava por status e não respondia
# essa pergunta.

from datetime import date, datetime  # noqa: E402

HOJE = date(2026, 9, 3)


def ativ(nv=2, **kw):
    base = linha(nv)
    base["criticidade"] = kw.pop("criticidade", 0)
    base["descricao"] = kw.pop("descricao", "uma atividade")
    base.update(kw)
    return base


def faixa_de(a, hoje=HOJE):
    return at.classificar(a, hoje)[0]


# --- concluídas saem do mural ---------------------------------------------

def test_concluida_pela_caixa_sai():
    assert faixa_de(ativ(concluida=True)) is None


def test_concluida_pelo_STATUS_tambem_sai():
    """As duas colunas divergem na planilha real (2 x 1). Exigir as duas
    deixaria uma atividade terminada no mural para sempre."""
    assert faixa_de(ativ(status="Concluída")) is None


# --- as cinco faixas -------------------------------------------------------

def test_atrasada_quando_a_previsao_de_termino_passou():
    a = ativ(previsao_termino=datetime(2026, 8, 30))

    faixa, dias = at.classificar(a, HOJE)

    assert faixa == at.ATRASADA
    assert dias == -4


def test_deveria_ter_comecado():
    a = ativ(status="Não iniciada", data_prevista_inicio=datetime(2026, 9, 1))

    faixa, dias = at.classificar(a, HOJE)

    assert faixa == at.DEVERIA_TER_COMECADO
    assert dias == -2


def test_em_andamento():
    a = ativ(status="Em desenvolvimento", previsao_termino=datetime(2026, 9, 10))

    faixa, dias = at.classificar(a, HOJE)

    assert faixa == at.EM_ANDAMENTO
    assert dias == 7


def test_comeca_hoje():
    a = ativ(status="Não iniciada", data_prevista_inicio=datetime(2026, 9, 3))

    assert at.classificar(a, HOJE) == (at.COMECA_HOJE, 0)


def test_proximos_dias_dentro_do_horizonte():
    a = ativ(status="Não iniciada", data_prevista_inicio=datetime(2026, 9, 8))

    faixa, dias = at.classificar(a, HOJE)

    assert faixa == at.PROXIMOS_DIAS
    assert dias == 5


def test_alem_do_horizonte_fica_de_fora():
    """O horizonte é 7 dias, decisão do usuário. Mais que isso vira ruído."""
    a = ativ(status="Não iniciada", data_prevista_inicio=datetime(2026, 9, 20))

    assert faixa_de(a) is None


def test_o_horizonte_e_configuravel():
    a = ativ(status="Não iniciada", data_prevista_inicio=datetime(2026, 9, 20))

    assert at.classificar(a, HOJE, horizonte=30)[0] == at.PROXIMOS_DIAS


# --- a ordem das checagens é a ordem da urgência ---------------------------

def test_atraso_vence_em_andamento():
    """Atrasada E em desenvolvimento aparece como ATRASADA: o atraso é o que
    exige decisão."""
    a = ativ(status="Em desenvolvimento", previsao_termino=datetime(2026, 8, 20))

    assert faixa_de(a) == at.ATRASADA


def test_em_andamento_vence_deveria_ter_comecado():
    """Se já está em desenvolvimento, não faz sentido dizer que devia começar."""
    a = ativ(status="Em desenvolvimento", data_prevista_inicio=datetime(2026, 8, 1))

    assert faixa_de(a) == at.EM_ANDAMENTO


def test_travada_sem_data_ainda_aparece():
    """Trabalho parado sem data é justamente o que se perde de vista."""
    a = ativ(status="Travada")

    faixa, dias = at.classificar(a, HOJE)

    assert faixa == at.DEVERIA_TER_COMECADO
    assert dias is None


def test_sem_data_e_sem_status_fica_fora():
    assert faixa_de(ativ(status="Não iniciada")) is None


# --- o mural inteiro -------------------------------------------------------

def test_mural_ignora_linhas_de_grupo_e_agregadoras():
    linhas = [
        ativ(nv=1, previsao_termino=datetime(2026, 8, 1)),   # grupo
        ativ(nv=2, previsao_termino=datetime(2026, 8, 1)),   # tem filha
        ativ(nv=3, previsao_termino=datetime(2026, 8, 1)),   # atividade
    ]

    assert at.total_do_mural(at.mural(linhas, HOJE)) == 1


def test_mural_ordena_por_urgencia_e_depois_criticidade():
    linhas = [
        ativ(previsao_termino=datetime(2026, 9, 1), criticidade=1),   # -2
        ativ(previsao_termino=datetime(2026, 8, 20), criticidade=1),  # -14
        ativ(previsao_termino=datetime(2026, 9, 1), criticidade=5),   # -2, mais crítica
    ]

    atrasadas = at.mural(linhas, HOJE)[at.ATRASADA]

    assert [a["_dias"] for a in atrasadas] == [-14, -2, -2]
    assert atrasadas[1]["criticidade"] == 5


def test_cada_item_leva_a_faixa_e_os_dias():
    """A tela não deve precisar reclassificar."""
    linhas = [ativ(previsao_termino=datetime(2026, 8, 30))]

    item = at.mural(linhas, HOJE)[at.ATRASADA][0]

    assert item["_faixa"] == at.ATRASADA
    assert item["_dias"] == -4


def test_mural_vazio_quando_esta_tudo_em_dia():
    assert at.total_do_mural(at.mural([ativ(concluida=True)], HOJE)) == 0


def test_texto_na_coluna_de_data_nao_quebra():
    a = ativ(status="Não iniciada", data_prevista_inicio="a combinar")

    assert faixa_de(a) is None


# --- as frases de prazo ----------------------------------------------------

def test_frases_do_passado():
    assert at.frase_do_prazo(at.ATRASADA, -1) == "venceu ontem"
    assert at.frase_do_prazo(at.ATRASADA, -4) == "venceu há 4 dias"
    assert at.frase_do_prazo(at.DEVERIA_TER_COMECADO, -1) == "era para começar ontem"


def test_frases_do_futuro():
    assert at.frase_do_prazo(at.COMECA_HOJE, 0) == "começa hoje"
    assert at.frase_do_prazo(at.PROXIMOS_DIAS, 1) == "começa amanhã"
    assert at.frase_do_prazo(at.PROXIMOS_DIAS, 5) == "começa em 5 dias"


def test_frase_sem_data():
    assert at.frase_do_prazo(at.DEVERIA_TER_COMECADO, None) == "sem data"

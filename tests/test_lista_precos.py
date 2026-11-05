"""`services/lista_precos.py` — o pareamento da lista de preços.

Ver `docs/superpowers/specs/2026-09-03-lista-precos-followup-design.md`.

Os casos aqui NÃO são inventados: cada um reproduz uma situação medida no
histórico real do Aconex em 2026-09-03 (86.789 linhas, 16 listas de preços
vigentes). Os códigos são os de verdade, para que um teste vermelho aponte
para um documento que existe.

O caso que mais importa é o `test_lista_com_titulo_sem_a_palavra_sobressalentes`:
ele reproduz o defeito da PRIMEIRA versão do algoritmo, que procurava o par
entre os documentos com "SOBRESSALENTES" no título e declarava órfã uma lista
que existia, vigente, com a raiz idêntica.
"""
from __future__ import annotations

from sigft.services import lista_precos as lp


def doc(codigo, titulo, tracking, current=True):
    """Uma linha do export do Aconex, com só o que o módulo lê."""
    return {
        lp.COL_DOC: codigo,
        lp.COL_TITULO: titulo,
        lp.COL_TRACKING: tracking,
        lp.COL_CURRENT: current,
    }


TITULO_LISTA = "ATUALIZAÇÃO TECNOLÓGICA - LISTA DE SOBRESSALENTES"
TITULO_PRECOS = "ATUALIZAÇÃO TECNOLÓGICA - LISTA DE SOBRESSALENTES COM PREÇOS"


# =============================================================================
# A. raiz() — tirar o sequencial
# =============================================================================

def test_raiz_tira_o_sequencial_de_dois_digitos():
    assert lp.raiz("#ITA0=A01AAM10&EPB020-02") == "#ITA0=A01AAM10&EPB020"


def test_raiz_tira_o_sequencial_de_um_digito():
    assert lp.raiz("#ST00=Q01GDB00&MPB020-1") == "#ST00=Q01GDB00&MPB020"


def test_raiz_de_codigo_sem_sequencial_devolve_ele_mesmo():
    assert lp.raiz("#ITA0=C01CUC01&EPB020") == "#ITA0=C01CUC01&EPB020"


def test_raiz_nao_confunde_hifen_do_meio_com_sequencial():
    """Há códigos com hífen no meio: `#ST00=B01BDV10-MS000UC004&EPB020`.
    Cortar ali destruiria o código."""
    codigo = "#ST00=B01BDV10-MS000UC004&EPB020"
    assert lp.raiz(codigo) == codigo


def test_raiz_de_codigo_com_hifen_no_meio_E_sequencial_no_fim():
    assert (
        lp.raiz("#ST00=Q01PAC01GP030-GP900&MPB020-01")
        == "#ST00=Q01PAC01GP030-GP900&MPB020"
    )


def test_raiz_tolera_vazio_e_none():
    assert lp.raiz(None) == ""
    assert lp.raiz("  ") == ""


def test_raiz_da_lista_com_preco_PB021_e_a_da_lista_PB020():
    """Formato vigente (ITAIPU-REF-0013): a lista com preço é a de
    sobressalentes com o DCC PB021 no lugar do PB020, sem sequencial."""
    assert lp.raiz("#ST00=U01&MPB021") == "#ST00=U01&MPB020"


def test_raiz_PB021_com_sequencial_tambem_vira_PB020():
    assert lp.raiz("#ST00=U01&MPB021-01") == "#ST00=U01&MPB020"


def test_raiz_so_troca_PB021_no_fim_do_codigo():
    codigo = "#ST00=PB021X&MPB020"
    assert lp.raiz(codigo) == codigo


# =============================================================================
# B. Quem é lista de preços
# =============================================================================

def test_o_titulo_e_quem_diz_se_e_lista_de_precos():
    assert lp.eh_lista_de_precos(TITULO_PRECOS)
    assert not lp.eh_lista_de_precos(TITULO_LISTA)


def test_reconhece_preco_no_singular():
    assert lp.eh_lista_de_precos("LISTA DE SOBRESSALENTES COM PREÇO")


def test_o_sequencial_NAO_decide_se_e_lista_de_precos():
    """Medido: há par em que a LISTA também tem sequencial (`-01`) e a de
    preços é `-02`. Se o sequencial decidisse, a lista viraria 'preços'."""
    assert not lp.eh_lista_de_precos(TITULO_LISTA)


# =============================================================================
# C. Pareamento — os quatro desfechos reais
# =============================================================================

def test_par_direto_quando_a_lista_nao_tem_sequencial():
    """O caso comum: 11 das 16 no histórico real."""
    precos = doc("#ITA0=C01CUC01&EPB020-01", TITULO_PRECOS, "trk-precos")
    hist = [precos, doc("#ITA0=C01CUC01&EPB020", TITULO_LISTA, "trk-lista")]

    par = lp.parear(precos, hist)

    assert par["desfecho"] == lp.PAR_ENCONTRADO
    assert par["lista"] == "#ITA0=C01CUC01&EPB020"
    assert par["alerta"] == lp.ALERTA_VAZIO


def test_par_quando_AS_DUAS_tem_sequencial():
    """Medido: `#ITA0=A01AAM10&EPB020-01` (lista) e `-02` (preços).

    É o caso que quebrava a regra original ("sem sequencial = a lista"), e o
    motivo de o sequencial ser tirado dos DOIS lados.
    """
    precos = doc("#ITA0=A01AAM10&EPB020-02", TITULO_PRECOS, "trk-precos")
    hist = [precos, doc("#ITA0=A01AAM10&EPB020-01", TITULO_LISTA, "trk-lista")]

    par = lp.parear(precos, hist)

    assert par["desfecho"] == lp.PAR_ENCONTRADO
    assert par["lista"] == "#ITA0=A01AAM10&EPB020-01"


def test_lista_com_titulo_sem_a_palavra_sobressalentes():
    """O defeito da PRIMEIRA versão do algoritmo.

    `#ST00=B04BMA10TB020&EPB020` existe, está vigente e tem a raiz idêntica —
    mas o título dela não contém "SOBRESSALENTES". A versão antiga procurava o
    par só entre os títulos com essa palavra e a declarava órfã.

    O título serve para saber QUAL família é a de preços; nunca para achar o
    par.
    """
    precos = doc("#ST00=B04BMA10TB020&EPB020-01", TITULO_PRECOS, "trk-precos")
    hist = [
        precos,
        doc(
            "#ST00=B04BMA10TB020&EPB020",
            "ATUALIZAÇÃO TECNOLÓGICA - ENG. ELÉTRICA - CASA DE FORÇA",
            "trk-lista",
        ),
    ]

    par = lp.parear(precos, hist)

    assert par["desfecho"] == lp.PAR_ENCONTRADO
    assert par["lista"] == "#ST00=B04BMA10TB020&EPB020"


def test_rdspp_mudou_acha_pelo_tracking_da_revisao_antiga():
    """Medido: `#ST00=Q01GDB00&MPB020` virou `#ST00=B01BDV10&MPB020`.

    A raiz que a lista de preços aponta não é mais vigente — existe só como
    revisão antiga. É por ali que se chega ao código de hoje.
    """
    precos = doc("#ST00=Q01GDB00&MPB020-01", TITULO_PRECOS, "trk-precos")
    hist = [
        precos,
        doc("#ST00=Q01GDB00&MPB020", TITULO_LISTA, "trk-lista", current=False),
        doc("#ST00=B01BDV10&MPB020", TITULO_LISTA, "trk-lista", current=True),
    ]

    par = lp.parear(precos, hist)

    assert par["desfecho"] == lp.RDSPP_MUDOU
    assert par["lista"] == "#ST00=B01BDV10&MPB020"
    assert par["alerta"] == lp.ALERTA_ATUALIZAR


def test_orfa_quando_a_raiz_so_tem_a_familia_de_precos():
    """Medido: `#ST00=U01UUA&MPB020-01`. A raiz só tem o tracking da própria
    lista de preços — não há lista de sobressalentes correspondente."""
    precos = doc("#ST00=U01UUA&MPB020-01", TITULO_PRECOS, "trk-precos")
    hist = [
        precos,
        doc("#ST00=U01UUA&MPB020-01", TITULO_PRECOS, "trk-precos", current=False),
    ]

    par = lp.parear(precos, hist)

    assert par["desfecho"] == lp.ORFA
    assert par["lista"] is None
    assert par["alerta"] == lp.ALERTA_SEM_LISTA


def test_familia_sem_revisao_vigente_nao_serve_de_par():
    """Histórico morto: a lista existiu e nenhuma revisão dela está vigente."""
    precos = doc("#X=A&B-01", TITULO_PRECOS, "trk-precos")
    hist = [precos, doc("#X=A&B", TITULO_LISTA, "trk-lista", current=False)]

    assert lp.parear(precos, hist)["desfecho"] == lp.ORFA


def test_a_propria_familia_de_precos_nunca_e_o_par():
    """A lista de preços tem várias revisões, todas do mesmo tracking. Nenhuma
    delas pode ser confundida com a lista que ela copia."""
    precos = doc("#X=A&B-01", TITULO_PRECOS, "trk-precos")
    hist = [
        precos,
        doc("#X=A&B-01", TITULO_PRECOS, "trk-precos", current=False),
        doc("#X=A&B", TITULO_PRECOS, "trk-precos", current=False),
    ]

    assert lp.parear(precos, hist)["desfecho"] == lp.ORFA


def test_entre_duas_familias_vigentes_escolhe_a_que_nao_e_de_precos():
    precos = doc("#X=A&B-02", TITULO_PRECOS, "trk-precos")
    hist = [
        precos,
        doc("#X=A&B-03", TITULO_PRECOS, "outra-de-precos"),
        doc("#X=A&B-01", TITULO_LISTA, "trk-lista"),
    ]

    par = lp.parear(precos, hist)

    assert par["desfecho"] == lp.PAR_ENCONTRADO
    assert par["lista"] == "#X=A&B-01"


# =============================================================================
# D. levantar() — o follow-up inteiro
# =============================================================================

def test_levantar_pega_so_as_listas_de_precos_vigentes():
    hist = [
        doc("#A=1&X-01", TITULO_PRECOS, "p1"),
        doc("#A=1&X", TITULO_LISTA, "l1"),
        doc("#B=2&X-01", TITULO_PRECOS, "p2", current=False),  # não vigente
        doc("#C=3&X", "DOCUMENTO QUALQUER", "outro"),          # não é lista
    ]

    levantado = lp.levantar(hist)

    assert len(levantado) == 1
    assert levantado[0]["precos"][lp.COL_DOC] == "#A=1&X-01"
    assert levantado[0]["desfecho"] == lp.PAR_ENCONTRADO


def test_levantar_classifica_os_tres_desfechos_juntos():
    hist = [
        # par direto
        doc("#A=1&X-01", TITULO_PRECOS, "p1"),
        doc("#A=1&X", TITULO_LISTA, "l1"),
        # rds-pp mudou
        doc("#B=2&X-01", TITULO_PRECOS, "p2"),
        doc("#B=2&X", TITULO_LISTA, "l2", current=False),
        doc("#B=9&X", TITULO_LISTA, "l2", current=True),
        # órfã
        doc("#C=3&X-01", TITULO_PRECOS, "p3"),
    ]

    por_codigo = {e["precos"][lp.COL_DOC]: e for e in lp.levantar(hist)}

    assert por_codigo["#A=1&X-01"]["desfecho"] == lp.PAR_ENCONTRADO
    assert por_codigo["#B=2&X-01"]["desfecho"] == lp.RDSPP_MUDOU
    assert por_codigo["#B=2&X-01"]["lista"] == "#B=9&X"
    assert por_codigo["#C=3&X-01"]["desfecho"] == lp.ORFA


def test_levantar_em_historico_vazio_nao_quebra():
    assert lp.levantar([]) == []


# =============================================================================
# E. O texto que vai para OBSERVAÇÕES
# =============================================================================

def test_observacao_do_rdspp_nomeia_os_dois_codigos():
    par = {
        "desfecho": lp.RDSPP_MUDOU,
        "raiz_apontada": "#ST00=Q01GDB00&MPB020",
        "lista": "#ST00=B01BDV10&MPB020",
    }

    texto = lp.texto_de_observacao(par, "03/09")

    assert "[SIG-FT 03/09]" in texto
    assert "#ST00=Q01GDB00&MPB020" in texto
    assert "#ST00=B01BDV10&MPB020" in texto


def test_observacao_da_orfa_diz_o_que_faltou():
    par = {"desfecho": lp.ORFA, "raiz_apontada": "#X=1&Y", "lista": None}

    texto = lp.texto_de_observacao(par, "03/09")

    assert "[SIG-FT 03/09]" in texto
    assert "não achei lista" in texto


def test_par_encontrado_nao_gera_observacao():
    """Sem novidade, o app não escreve nada. Uma linha por execução numa
    coluna do usuário a tornaria ilegível em poucas rodadas."""
    par = {"desfecho": lp.PAR_ENCONTRADO, "raiz_apontada": "#X=1&Y", "lista": "#X=1&Y"}

    assert lp.texto_de_observacao(par, "03/09") is None


# =============================================================================
# F. O módulo não pode depender de planilha
# =============================================================================

def test_o_modulo_nao_importa_pandas_nem_openpyxl():
    """É o que o torna testável sem Excel, sem Aconex e sem rede."""
    import ast
    import inspect

    arvore = ast.parse(inspect.getsource(lp))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])

    assert "pandas" not in importados
    assert "openpyxl" not in importados


# =============================================================================
# PB021 — a lista com preço do formato vigente
# =============================================================================

def test_lista_PB021_acha_a_lista_PB020_correspondente():
    """O defeito relatado em 2026-11-04: a lista `...MPB021` saía órfã porque
    a raiz dela era ela mesma -- não há sequencial a tirar. Trocando o 1 final
    por 0 acha-se a lista de sobressalentes `...MPB020`."""
    precos = doc("#ST00=U01&MPB021", TITULO_PRECOS, "T-PRECO")
    historico = [
        doc("#ST00=U01&MPB020", TITULO_LISTA, "T-LISTA"),
        precos,
    ]
    par = lp.parear(precos, historico)
    assert par["desfecho"] == lp.PAR_ENCONTRADO
    assert par["lista"] == "#ST00=U01&MPB020"
    assert par["alerta"] == lp.ALERTA_VAZIO


def test_lista_PB021_com_rdspp_mudado_aponta_o_codigo_novo():
    precos = doc("#ST00=U01&MPB021", TITULO_PRECOS, "T-PRECO")
    historico = [
        doc("#ST00=U01&MPB020", TITULO_LISTA, "T-LISTA", current=False),
        doc("#ST00=U02&MPB020", TITULO_LISTA, "T-LISTA"),
        precos,
    ]
    par = lp.parear(precos, historico)
    assert par["desfecho"] == lp.RDSPP_MUDOU
    assert par["lista"] == "#ST00=U02&MPB020"

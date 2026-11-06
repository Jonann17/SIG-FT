"""AutoSpec: um valor com vários itens grava os que o trecho prova (2026-11-06, pedido do Luan).

Rodada da 1.4.0-rc.5 pelo Workflow AMP, acoplador WAGO 750-362. O agente respondeu as normas e
as aprovações certas, com um trecho de prova por lugar do documento, e os dois campos ficaram
vazios: um item só (duas normas, a UL61010-2-201) não estava nos trechos citados, e a
conferência reprovava o campo inteiro. Decisão do Luan: "o correto a se fazer então seria
deixar os [itens] que ele conseguiu listar". O item sem prova fica de fora, e o console e a
nota da célula dizem qual.

Os valores e os trechos são os da resposta real do agente; o documento é montado com as linhas
que ele citou, quebradas como o PyMuPDF as extraiu (ver o motivo no console da rodada). O nome
do PDF foi trocado: o repositório é público.
"""
from __future__ import annotations

from sigft.services import autospec_evidencia as ev
from sigft.services.autospec import AutoSpecCore

_OUTRA_SECAO = ("Technical data. The fieldbus coupler connects the WAGO I/O System to the fieldbus. "
                "It detects all connected I/O modules and creates a local process image, which may "
                "include analog, digital and specialty modules arranged in any order on the node.\n")
DOC = (
    "--- LOCAL DOC: Data sheet 750-362.pdf ---\n"
    "[página 3]\n"
    "Environmental requirements\n"
    "EMC immunity to interference\nper EN 61000-6-2\n"
    "EMC emission of interference\nper EN 61000-6-3\n"
    + _OUTRA_SECAO +
    "Shock resistance\n15g per IEC 60068-2-27\n"
    + _OUTRA_SECAO +
    "Vibration resistance\n4g per IEC 60068-2-6\n"
    "[página 4]\n"
    "Approvals\n"
    "TUEV14ATEX148929X (II 3\nG Ex ec IIC T4 Gc)\n"
    + _OUTRA_SECAO +
    "IECEx TUN 14.0035 X (Ex ec\nIIC T4 Gc)\n"
    + _OUTRA_SECAO +
    "BR-Ex_TÜV 12.1297 X\n"
    + _OUTRA_SECAO +
    "UL 121201\n"
)

PERGUNTA_NORMAS = "6 - NORMAS TECNICAS APLICAVEIS (Indicar quais as normas técnicas aplicáveis ao item.)"
NORMAS = "EN 61000-6-2; EN 61000-6-3; IEC 61131-2; EN 50173; IEC 60068-2-6; IEC 60068-2-27"
TRECHOS_NORMAS = (
    "EMC immunity to interference per EN 61000-6-2",
    "EMC emission of interference per EN 61000-6-3",
    "Shock resistance 15g per IEC 60068-2-27",
    "Vibration resistance 4g per IEC 60068-2-6",
)

PERGUNTA_CERTIFICADO = ("14 - CERTIFICADO (Indicar o tipo de certificado necessário: Selo de Certificação "
                        "Ambiental, Eficiência Energética, Calibração, outros)")
ITEM_UL = "UL (locais ordinários UL61010-2-201 e locais perigosos UL 121201 Cl I Div 2)"
CERTIFICADO = (f"CE; {ITEM_UL}; ATEX (TÜV 14 ATEX 148929 X); IECEx (IECEx TUN 14.0035 X); "
               "INMETRO (BR-Ex_TÜV 12.1297 X); marítimas: ABS, DNV, PRS")
TRECHOS_CERTIFICADO = (
    "TUEV14ATEX148929X (II 3 G Ex ec IIC T4 Gc)",
    "IECEx TUN 14.0035 X (Ex ec IIC T4 Gc)",
    "BR-Ex_TÜV 12.1297 X",
    "UL 121201",
)


def _core(evidencias):
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.ultimas_evidencias_por_campo = evidencias
    core._modelo_do_item = ""
    return core


def _logs():
    linhas = []

    class _Cb:
        def log(self, msg, nivel="info", contexto=None):
            linhas.append((nivel, str(msg)))

    return _Cb(), linhas


def _filtrar(campo, valor, pergunta, trechos):
    core = _core({campo: ev.Evidencia(trechos=trechos, fonte="Data sheet 750-362.pdf", pagina=3)})
    cb, linhas = _logs()
    aprovados = core._filtrar_por_lastro({campo: valor}, {campo: {"desc": pergunta}}, DOC, cb)
    return core, aprovados, [mensagem for _nivel, mensagem in linhas]


# -- os itens de um valor -------------------------------------------------------------------

def test_os_itens_sao_separados_pelo_ponto_e_virgula_fora_dos_parenteses():
    assert ev.itens_do_valor("CE; UL (UL 121201; UL 61010-2-201); ATEX") == [
        "CE", "UL (UL 121201; UL 61010-2-201)", "ATEX"]


def test_valor_sem_ponto_e_virgula_e_um_item_so():
    assert ev.itens_do_valor("24 VDC (-25 … +30 %)") == ["24 VDC (-25 … +30 %)"]
    assert ev.itens_do_valor("A;; B; ") == ["A", "B"]


# -- a rodada da rc.5 -----------------------------------------------------------------------

def test_normas_grava_as_que_os_trechos_provam():
    core, aprovados, _logs_ = _filtrar("var_row_84", NORMAS, PERGUNTA_NORMAS, TRECHOS_NORMAS)
    assert aprovados == {"var_row_84": "EN 61000-6-2; EN 61000-6-3; IEC 60068-2-6; IEC 60068-2-27"}


def test_normas_o_console_e_a_nota_dizem_o_que_ficou_de_fora():
    core, _aprovados, logs = _filtrar("var_row_84", NORMAS, PERGUNTA_NORMAS, TRECHOS_NORMAS)
    assert any("IEC 61131-2; EN 50173" in linha for linha in logs)
    assert not any("ficaram VAZIOS" in linha for linha in logs)
    assert "IEC 61131-2; EN 50173" in core.notas_por_campo["var_row_84"]


def test_certificado_grava_as_aprovacoes_provadas_e_deixa_a_ul_de_fora():
    core, aprovados, logs = _filtrar("var_row_92", CERTIFICADO, PERGUNTA_CERTIFICADO, TRECHOS_CERTIFICADO)
    assert aprovados == {"var_row_92": (
        "CE; ATEX (TÜV 14 ATEX 148929 X); IECEx (IECEx TUN 14.0035 X); "
        "INMETRO (BR-Ex_TÜV 12.1297 X); marítimas: ABS, DNV, PRS")}
    assert ITEM_UL in core.notas_por_campo["var_row_92"]


def test_nenhum_item_provado_continua_reprovado():
    _core_, aprovados, logs = _filtrar("var_row_84", "IEC 61131-2; EN 50173", PERGUNTA_NORMAS, TRECHOS_NORMAS)
    assert aprovados == {}
    assert any("ficaram VAZIOS" in linha for linha in logs)


def test_trecho_nao_achado_os_itens_dos_outros_trechos_ficam():
    """Um dos trechos não está no documento: os itens que os OUTROS provam ficam."""
    core = _core({"var_row_92": ev.Evidencia(
        trechos=("UL 121201", "KEMA 99ATEX1234"), fonte="Data sheet 750-362.pdf", pagina=4)})
    cb, linhas = _logs()
    aprovados = core._filtrar_por_lastro(
        {"var_row_92": "UL (UL 121201); ATEX (KEMA 99ATEX1234)"},
        {"var_row_92": {"desc": PERGUNTA_CERTIFICADO}}, DOC, cb)
    assert aprovados == {"var_row_92": "UL (UL 121201)"}
    assert "ATEX (KEMA 99ATEX1234)" in core.notas_por_campo["var_row_92"]

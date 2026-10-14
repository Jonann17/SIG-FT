r"""
O que as telas do PMIB recebem do servidor -- `sigft/core/rpa/respostas.py`
(2026-10-14).

As respostas abaixo foram montadas a partir do código das telas do portal
(docs/PMIB_ENGENHARIA_REVERSA.md): a forma de lista do OutSystems
(`{"List": [...]}`, com `"EmptyListItem"` quando vazia), a de consulta
(`{"List": ..., "Count": N}`) e os nomes de campo de cada registro
(`DSNumber`, `DSNumberSec`, `StockCodeSAP`, `RequestStatus`...).

⚠️ `scripts/check.sh` verde não é prova de portal: a forma real é conferida na
primeira execução com login (roteiro no CHANGELOG da 1.2.0).
"""
from __future__ import annotations

from sigft.core.rpa import respostas

VERSAO = {"hasModuleVersionChanged": False, "hasApiVersionChanged": False}


def _linha(ident, ds, sec, nome="CHAVE SECCIONADORA"):
    return {"CreateBy": 18, "Id": ident, "DatasheetCode": "", "MDSCode": "PDM.0458.001",
            "NameES": nome, "NamePT": nome, "NameToSort": nome, "ProjectCode": "ST00",
            "DSNumber": ds, "UpdateOn": "2026-10-01T13:00:00Z", "WasInApproval": False,
            "DSNumberSec": sec}


def _aba(*linhas):
    if linhas:
        return {"versionInfo": VERSAO, "data": {"List": {"List": list(linhas)}, "Count": str(len(linhas))}}
    return {"versionInfo": VERSAO,
            "data": {"List": {"List": [], "EmptyListItem": _linha("0", "0", 0, nome="")}, "Count": "0"}}


def _codificacao(*solicitacoes):
    if solicitacoes:
        return {"versionInfo": VERSAO, "data": {"List": {"List": list(solicitacoes)}, "Count": str(len(solicitacoes))}}
    vazia = _solicitacao("", "", ident="0")
    return {"versionInfo": VERSAO, "data": {"List": {"List": [], "EmptyListItem": vazia}, "Count": "0"}}


def _solicitacao(codigo_sap, status_pt, ident="991", status_es=None):
    return {"RequestStatus": {"DescriptionEs": status_es if status_es is not None else status_pt,
                              "DescriptionPt": status_pt},
            "CodificationRequest": {"Id": ident, "RequestNumberSAP": "10023456" if codigo_sap else "",
                                    "SAPSendInProgress": False, "StockCodeSAP": codigo_sap}}


# ---------------------------------------------------------------------------
# A ficha na lista: uma pesquisa recarrega as SETE abas, uma por status
# ---------------------------------------------------------------------------
def test_acha_o_id_da_ficha_em_qualquer_uma_das_abas():
    abas = [_aba(), _aba(_linha("40001", "4500063671", 12)), _aba(_linha("48213", "4500063671", 71))]

    assert respostas.id_da_ficha(abas, "4500063671.0071") == "48213"


def test_casa_o_codigo_vindo_como_numero_ou_como_texto():
    abas = [_aba(_linha(48213, 4500063671, "71"))]

    assert respostas.id_da_ficha(abas, "4500063671.0071") == "48213"


def test_casa_o_pmib_que_perdeu_o_zero_do_fim_na_planilha():
    abas = [_aba(_linha("50120", "4500063671", 1650))]

    assert respostas.id_da_ficha(abas, "4500063671.165") == "50120"


def test_ficha_que_nao_aparece_em_nenhuma_aba_nao_tem_id():
    abas = [_aba(), _aba(_linha("40001", "4500063671", 12))]

    assert respostas.id_da_ficha(abas, "4500063671.0071") is None


def test_resposta_de_erro_da_lista_nao_tem_id():
    erro = {"versionInfo": VERSAO, "exception": {"name": "SecurityException", "message": "Sessão expirada"}}

    assert respostas.id_da_ficha([erro], "4500063671.0071") is None


# ---------------------------------------------------------------------------
# O código SAP de recebimento, no cabeçalho da ficha
# ---------------------------------------------------------------------------
def test_solicitacao_com_codigo_de_recebimento_devolve_o_codigo():
    resposta = _codificacao(_solicitacao("721164", "Aprovado", status_es="Aprobado"))

    assert respostas.codigo_sap(resposta) == "721164"


def test_ficha_sem_solicitacao_de_codificacao_nao_tem_codigo():
    assert respostas.codigo_sap(_codificacao()) is None


def test_solicitacao_que_ainda_nao_recebeu_o_codigo_nao_autoriza():
    resposta = _codificacao(_solicitacao("", "Em elaboração", status_es="En elaboración"))

    assert respostas.codigo_sap(resposta) is None


def test_solicitacao_cancelada_nao_autoriza_mesmo_com_codigo():
    # A consulta da Itaipu (aba "SQL" do export de autorizados) também
    # descarta a solicitação cancelada: `requeststatusid <> 7`.
    resposta = _codificacao(_solicitacao("721164", "Cancelado", status_es="Cancelado"))

    assert respostas.codigo_sap(resposta) is None


def test_vale_a_solicitacao_com_codigo_quando_ha_uma_cancelada_antes():
    resposta = _codificacao(_solicitacao("700001", "Cancelado"),
                            _solicitacao("721164", "Aprovado", ident="992"))

    assert respostas.codigo_sap(resposta) == "721164"


def test_codigo_com_espacos_volta_limpo():
    assert respostas.codigo_sap(_codificacao(_solicitacao(" 721164 ", "Aprovado"))) == "721164"


def test_resposta_de_erro_do_servidor_nao_tem_codigo():
    erro = {"versionInfo": VERSAO, "exception": {"name": "SecurityException", "message": "Acesso negado"}}

    assert respostas.codigo_sap(erro) is None


# ---------------------------------------------------------------------------
# Gravação: a resposta da ação de salvar
# ---------------------------------------------------------------------------
def test_gravacao_aceita_devolve_o_id_gravado():
    resposta = {"versionInfo": VERSAO, "data": {"ApplicationMRLId": "5501"}}

    assert respostas.resultado_da_gravacao(resposta, "ApplicationMRLId") == (True, "5501")


def test_gravacao_recusada_devolve_a_mensagem_do_servidor():
    resposta = {"versionInfo": VERSAO,
                "exception": {"name": "ServerException", "message": "The value does not match the number of tags added"}}

    assert respostas.resultado_da_gravacao(resposta, "ApplicationMRLId") == (
        False, "The value does not match the number of tags added")


def test_resposta_sem_o_id_esperado_nao_decide_nada():
    for resposta in ({"versionInfo": VERSAO, "data": {}},
                     {"versionInfo": VERSAO, "data": {"ApplicationMRLId": "0"}},
                     {"versionInfo": VERSAO}):
        assert respostas.resultado_da_gravacao(resposta, "ApplicationMRLId") == (None, "")


# ---------------------------------------------------------------------------
# Endereço da ficha
# ---------------------------------------------------------------------------
def test_a_ficha_abre_direto_pela_tela_de_visualizacao():
    assert respostas.url_da_ficha("48213") == (
        "https://apps.itaipu.gov.br/PMIB/PMIB_DataSheetView?PMIB_DataSheetId=48213")

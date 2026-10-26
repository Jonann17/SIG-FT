"""O cliente do Aconex: token OAuth, busca paginada, versões de um código e download.

Copiado do DocManager (`docmanager/aconex_backend.py`) e ligado ao `sigft/core/rede.py`.
Nenhum teste toca a rede: o `abrir` é um dublê que guarda cada chamada e devolve
respostas sintéticas, no formato que o Aconex devolve. O segredo e o token nunca
aparecem numa mensagem de erro.
"""
from __future__ import annotations

import base64

import pytest

from _pandas_de_verdade import pandas_de_verdade
from sigft.core import rede
from sigft.core.aconex import cliente as cl
from sigft.core.aconex.credenciais import PerfilAconex

PERFIL = PerfilAconex("Luan Cozer", "SCP_LUAN", "1208560183", "s3gr3d0")


class _Resposta:
    def __init__(self, status_code=200, content=b"", dados=None):
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", "replace")
        self._dados = dados

    def json(self):
        return self._dados


class _Aconex:
    """Dublê do `rede.abrir`: guarda cada chamada e responde da fila, na ordem."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, url, **kw):
        self.chamadas.append({"url": url, **kw})
        resposta = self.respostas.pop(0)
        if isinstance(resposta, BaseException):
            raise resposta
        return None, resposta


def _token(valor="tok1"):
    return _Resposta(200, b"{}", {"access_token": valor})


def _doc(document_id, numero, revisao, versao, current):
    campos = {"DocumentNumber": numero, "Revision": revisao, "VersionNumber": str(versao),
              "Current": "true" if current else "false"}
    corpo = "".join(f"<{k}>{v}</{k}>" for k, v in campos.items())
    return f'<Document DocumentId="{document_id}">{corpo}</Document>'


def _pagina(*docs):
    xml = "<RegisterSearch><SearchResults>" + "".join(docs) + "</SearchResults></RegisterSearch>"
    return _Resposta(200, xml.encode("utf-8"))


FIM = _Resposta(400, b"<Error>fim da paginacao</Error>")


def test_token_vai_no_formulario_e_volta_no_bearer():
    aconex = _Aconex(_token("tok1"), _pagina(_doc("1", "#IT-1", "0", 1, True)), FIM)
    cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=True)
    token, busca = aconex.chamadas[0], aconex.chamadas[1]
    assert token["url"] == cl.AUTH_URL and token["metodo"] == "POST"
    assert token["headers"]["Authorization"] == "Basic " + base64.b64encode(b"SCP_LUAN:s3gr3d0").decode()
    assert token["data"] == {"grant_type": "client_credentials", "user_id": "1208560183",
                             "user_site": "https://us1.aconex.com"}
    assert busca["url"] == "https://us1.aconex.com/api/projects/1207975853/register"
    assert busca["headers"]["Authorization"] == "Bearer tok1"
    assert busca["headers"]["Accept"] == "application/xml"
    assert busca["params"]["search_query"] == '"#IT-1"'
    assert busca["params"]["show_document_history"] == "true"
    assert busca["params"]["page_number"] == 1


def test_sem_historico_nao_pede_o_historico():
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)), FIM)
    cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=False)
    assert aconex.chamadas[1]["params"]["show_document_history"] == "false"


def test_buscar_pagina_ate_o_400_do_fim():
    aconex = _Aconex(_token(),
                     _pagina(_doc("1", "#IT-1", "0", 1, False), _doc("2", "#IT-1", "0A", 2, True)),
                     _pagina(_doc("3", "#IT-2", "0", 1, True)), FIM)
    registros = cl.ClienteAconex(PERFIL, abrir=aconex).buscar("", historico=True)
    assert [r["DocumentNumber"] for r in registros] == ["#IT-1", "#IT-1", "#IT-2"]
    assert [c["params"]["page_number"] for c in aconex.chamadas[1:]] == [1, 2, 3]


def test_pagina_vazia_tambem_encerra():
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)), _pagina())
    registros = cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=False)
    assert len(registros) == 1
    assert len(aconex.chamadas) == 3


def test_401_renova_o_token_uma_vez():
    aconex = _Aconex(_token("tok1"), _Resposta(401), _token("tok2"), _pagina(_doc("1", "#IT-1", "0", 1, True)), FIM)
    registros = cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=True)
    assert len(registros) == 1
    assert aconex.chamadas[3]["headers"]["Authorization"] == "Bearer tok2"


def test_401_duas_vezes_vira_erro_sem_segredo():
    aconex = _Aconex(_token("tok1"), _Resposta(401), _token("tok2"), _Resposta(401))
    with pytest.raises(cl.ErroAconex) as erro:
        cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=True)
    texto = str(erro.value)
    assert "401" in texto
    assert "s3gr3d0" not in texto and "tok1" not in texto and "tok2" not in texto


def test_token_recusado_vira_erro_sem_segredo():
    aconex = _Aconex(_Resposta(401, b'{"error": "invalid_client"}', {"error": "invalid_client"}))
    with pytest.raises(cl.ErroAconex) as erro:
        cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=True)
    assert "s3gr3d0" not in str(erro.value)


def test_503_espera_e_tenta_de_novo():
    esperas = []
    aconex = _Aconex(_token(), _Resposta(503), _Resposta(503), _pagina(_doc("1", "#IT-1", "0", 1, True)), FIM)
    registros = cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append).buscar('"#IT-1"', historico=True)
    assert len(registros) == 1
    assert esperas == [5, 15]


def test_503_quatro_vezes_vira_erro():
    esperas = []
    aconex = _Aconex(_token(), *[_Resposta(503) for _ in range(4)])
    with pytest.raises(cl.ErroAconex):
        cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append).buscar('"#IT-1"', historico=True)
    assert esperas == [5, 15, 45]


def test_falha_de_rede_vira_erro_aconex():
    aconex = _Aconex(rede.FalhaDeRede("nenhuma rota respondeu"))
    with pytest.raises(cl.ErroAconex):
        cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=True)


def test_versao_vigente_escolhe_a_current():
    aconex = _Aconex(_token(), _pagina(_doc("111", "#IT-1", "0A", 1, False), _doc("222", "#IT-1", "0B", 2, True)), FIM)
    assert cl.ClienteAconex(PERFIL, abrir=aconex).versao_vigente("#IT-1") == cl.Versao("222", "#IT-1", "0B", 2, True)


def test_versao_vigente_sem_current_devolve_none():
    aconex = _Aconex(_token(), _pagina(_doc("111", "#IT-1", "0A", 1, False)), FIM)
    assert cl.ClienteAconex(PERFIL, abrir=aconex).versao_vigente("#IT-1") is None


def test_versao_por_revisao_normalizada_pega_a_maior_versao():
    aconex = _Aconex(_token(), _pagina(_doc("111", "#IT-1", "0A", 1, False), _doc("112", "#IT-1", "0A", 2, False),
                                       _doc("222", "#IT-1", "0B", 3, True)), FIM)
    assert cl.ClienteAconex(PERFIL, abrir=aconex).versao("#IT-1", "0a") == cl.Versao("112", "#IT-1", "0A", 2, False)


def test_baixar_usa_markedup_e_devolve_bytes():
    aconex = _Aconex(_token(), _Resposta(200, b"%PDF-1.7 conteudo"))
    assert cl.ClienteAconex(PERFIL, abrir=aconex).baixar("222") == b"%PDF-1.7 conteudo"
    assert aconex.chamadas[1]["url"] == "https://us1.aconex.com/api/projects/1207975853/register/222/markedup"
    assert aconex.chamadas[1]["timeout"] == 180


def test_baixar_com_erro_vira_erro_aconex():
    aconex = _Aconex(_token(), _Resposta(404))
    with pytest.raises(cl.ErroAconex):
        cl.ClienteAconex(PERFIL, abrir=aconex).baixar("999")


def test_token_e_reaproveitado_entre_chamadas():
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)), FIM, _Resposta(200, b"%PDF"))
    cliente = cl.ClienteAconex(PERFIL, abrir=aconex)
    cliente.versao_vigente("#IT-1")
    cliente.baixar("1")
    assert sum(1 for c in aconex.chamadas if c["url"] == cl.AUTH_URL) == 1


def _registro(revisao, versao, current):
    return {"DocumentNumber": "#IT-1", "ControlDelEmisor_singleLineText": "CMI-1", "TrackingId": "T1",
            "Revision": revisao, "DateModified": "2026-09-01T10:00:00.000Z", "DocumentStatus": "Aprovado",
            "Title": "LISTA DE SOBRESSALENTES", "DocumentType": "Lista", "Especialidad_singleSelect": "E",
            "Subespecialidad_singleSelect": "S", "TipoDeDocumentoDcc_singleSelect": "T", "Dcc_singleSelect": "PB020",
            "ReviewSource": "WF-1", "ReviewStatus": "Aprovado", "VersionNumber": str(versao),
            "Current": "true" if current else "false", "Idioma_singleSelect": "PT",
            "ControlCmi_singleLineText": "C", "Disciplina_singleSelect": "D"}


def test_tabela_tem_as_colunas_do_extrato():
    with pandas_de_verdade(cl):
        df = cl.tabela([_registro("0A", 2, True), _registro("0", 1, False)])
        assert list(df.columns) == cl.ORDEM_COLUNAS
        assert df["Current"].tolist() == [True, False]
        assert df["Data de Alteração"].iloc[0] == "01/09/2026"
        assert df["Tipo de Tramitação"].iloc[0] == "Fluxo"


def test_conectar_pede_o_token_uma_vez():
    aconex = _Aconex(_token("tok1"), _pagina(_doc("1", "#IT-1", "0", 1, True)), FIM)
    cliente = cl.ClienteAconex(PERFIL, abrir=aconex)
    cliente.conectar()
    cliente.versao_vigente("#IT-1")
    assert [c["url"] for c in aconex.chamadas].count(cl.AUTH_URL) == 1


def test_conectar_com_credencial_recusada_vira_erro():
    aconex = _Aconex(_Resposta(401, b"{}", {}))
    with pytest.raises(cl.ErroAconex):
        cl.ClienteAconex(PERFIL, abrir=aconex).conectar()

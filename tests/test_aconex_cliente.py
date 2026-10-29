"""O cliente do Aconex: token OAuth, busca paginada, versões de um código e download.

Copiado do DocManager (`docmanager/aconex_backend.py`) e ligado ao `sigft/core/rede.py`.
A navegação entre as páginas é a do DocManager: `_baixar_pagina`, o laço do
`extrair_base` e a busca exata do `_buscar_doc_atual`. Nenhum teste toca a rede: o
`abrir` é um dublê que guarda cada chamada e devolve respostas sintéticas, no formato
que o Aconex devolve. O segredo e o token nunca aparecem numa mensagem de erro.
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


def _pagina(*docs, total=None):
    atributo = f' TotalResults="{total}"' if total is not None else ""
    xml = f"<RegisterSearch{atributo}><SearchResults>" + "".join(docs) + "</SearchResults></RegisterSearch>"
    return _Resposta(200, xml.encode("utf-8"))


FIM = _Resposta(400, b"<Error>fim da paginacao</Error>")


def _buscas(aconex):
    return [c for c in aconex.chamadas if c["url"] != cl.AUTH_URL]


def test_token_vai_no_formulario_e_volta_no_bearer():
    aconex = _Aconex(_token("tok1"), _pagina(_doc("1", "#IT-1", "0", 1, True)))
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
    assert busca["params"]["page_number"] == 1 and busca["params"]["page_size"] == 500
    assert busca["params"]["sort_field"] == "docno" and busca["params"]["sort_direction"] == "ASC"


def test_sem_historico_nao_manda_o_parametro():
    """Como na busca exata do DocManager: sem `show_document_history`, só a versão corrente."""
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)))
    cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=False)
    assert "show_document_history" not in aconex.chamadas[1]["params"]


def test_buscar_para_na_pagina_curta():
    """A página com menos itens que o `page_size` é a última: a seguinte nem é pedida."""
    aconex = _Aconex(_token(),
                     _pagina(_doc("1", "#IT-1", "0", 1, False), _doc("2", "#IT-1", "0A", 2, True)),
                     _pagina(_doc("3", "#IT-2", "0", 1, True)))
    registros = cl.ClienteAconex(PERFIL, abrir=aconex).buscar("", historico=True, page_size=2)
    assert [r["DocumentNumber"] for r in registros] == ["#IT-1", "#IT-1", "#IT-2"]
    assert [c["params"]["page_number"] for c in _buscas(aconex)] == [1, 2]


def test_buscar_para_no_400_do_fim():
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)), _pagina(_doc("2", "#IT-2", "0", 1, True)), FIM)
    registros = cl.ClienteAconex(PERFIL, abrir=aconex).buscar("", historico=True, page_size=1)
    assert len(registros) == 2
    assert [c["params"]["page_number"] for c in _buscas(aconex)] == [1, 2, 3]


def test_pagina_vazia_tambem_encerra():
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)), _pagina())
    registros = cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=False, page_size=1)
    assert len(registros) == 1
    assert len(_buscas(aconex)) == 2


def test_401_renova_o_token_sem_gastar_tentativa():
    esperas = []
    aconex = _Aconex(_token("tok1"), _Resposta(401), _token("tok2"), _pagina(_doc("1", "#IT-1", "0", 1, True)))
    registros = cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append).buscar('"#IT-1"', historico=True)
    assert len(registros) == 1
    assert aconex.chamadas[3]["headers"]["Authorization"] == "Bearer tok2"
    assert esperas == []


def test_401_que_nao_passa_vira_erro_sem_segredo():
    """Três renovações sem gastar tentativa; depois o 401 gasta as cinco, como no DocManager."""
    esperas = []
    respostas = [_token("tok1")]
    for i in range(cl.RENOVACOES_POR_PAGINA):
        respostas += [_Resposta(401), _token(f"tok{i + 2}")]
    respostas += [_Resposta(401) for _ in range(cl.TENTATIVAS_POR_PAGINA)]
    aconex = _Aconex(*respostas)
    with pytest.raises(cl.ErroAconex) as erro:
        cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append).buscar('"#IT-1"', historico=True)
    texto = str(erro.value)
    assert "401" in texto and "5 tentativas" in texto
    assert "s3gr3d0" not in texto and not any(f"tok{i}" in texto for i in range(1, 5))
    assert esperas == [5, 15, 30, 60]


def test_token_recusado_vira_erro_sem_segredo():
    aconex = _Aconex(_Resposta(401, b'{"error": "invalid_client"}', {"error": "invalid_client"}))
    with pytest.raises(cl.ErroAconex) as erro:
        cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=True)
    assert "s3gr3d0" not in str(erro.value)


def test_503_espera_e_tenta_de_novo():
    esperas = []
    aconex = _Aconex(_token(), _Resposta(503), _Resposta(503), _pagina(_doc("1", "#IT-1", "0", 1, True)))
    registros = cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append).buscar('"#IT-1"', historico=True)
    assert len(registros) == 1
    assert esperas == [5, 15]


def test_cinco_falhas_viram_erro_e_nada_parcial_volta():
    """A falha no meio da paginação não devolve a base truncada como completa (KB §28 do DocManager)."""
    esperas = []
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)), *[_Resposta(503) for _ in range(5)])
    with pytest.raises(cl.ErroAconex) as erro:
        cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append).buscar("", historico=True, page_size=1)
    assert "página 2" in str(erro.value) and "5 tentativas" in str(erro.value)
    assert esperas == [5, 15, 30, 60]


def test_tentativas_menores_desistem_antes_e_esperam_menos():
    """[2026-10-27] O diagnostico pede menos tentativas: o 500 deterministico do
    `docno:*PB020*` custava 4 esperas (110 s) numa sonda so, no log do Luan."""
    esperas = []
    aconex = _Aconex(_token(), _Resposta(500), _Resposta(500))
    with pytest.raises(cl.ErroAconex) as erro:
        cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append,
                         tentativas=2).primeira_pagina("x", historico=False)
    assert "2 tentativas" in str(erro.value) and "HTTP 500" in str(erro.value)
    assert esperas == [5]
    assert len(aconex.chamadas) == 3


def test_xml_truncado_tenta_de_novo():
    esperas = []
    aconex = _Aconex(_token(), _Resposta(200, b"<RegisterSearch><Search"), _pagina(_doc("1", "#IT-1", "0", 1, True)))
    registros = cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append).buscar('"#IT-1"', historico=True)
    assert len(registros) == 1 and esperas == [5]


def test_falha_de_rede_na_pagina_tenta_de_novo():
    esperas = []
    aconex = _Aconex(_token(), rede.FalhaDeRede("nenhuma rota respondeu"), _pagina(_doc("1", "#IT-1", "0", 1, True)))
    registros = cl.ClienteAconex(PERFIL, abrir=aconex, esperar=esperas.append).buscar('"#IT-1"', historico=True)
    assert len(registros) == 1 and esperas == [5]


def test_falha_de_rede_no_token_vira_erro_aconex():
    aconex = _Aconex(rede.FalhaDeRede("nenhuma rota respondeu"))
    with pytest.raises(cl.ErroAconex):
        cl.ClienteAconex(PERFIL, abrir=aconex).buscar('"#IT-1"', historico=True)


def test_versao_vigente_usa_a_busca_exata_do_docmanager():
    aconex = _Aconex(_token(), _pagina(_doc("111", "#IT-1", "0B", 2, True)))
    cl.ClienteAconex(PERFIL, abrir=aconex).versao_vigente("#IT-1")
    assert aconex.chamadas[1]["params"] == {
        "search_query": '"#IT-1"', "return_fields": "docno,current,filename,revision,versionnumber",
        "search_type": "PAGED", "page_size": 25, "page_number": 1}
    assert len(aconex.chamadas) == 2


def test_versao_vigente_escolhe_a_current():
    aconex = _Aconex(_token(), _pagina(_doc("111", "#IT-1", "0A", 1, False), _doc("222", "#IT-1", "0B", 2, True)))
    assert cl.ClienteAconex(PERFIL, abrir=aconex).versao_vigente("#IT-1") == cl.Versao("222", "#IT-1", "0B", 2, True)


def test_versao_vigente_sem_current_fica_com_a_primeira():
    aconex = _Aconex(_token(), _pagina(_doc("111", "#IT-1", "0A", 1, False)))
    assert cl.ClienteAconex(PERFIL, abrir=aconex).versao_vigente("#IT-1") == cl.Versao("111", "#IT-1", "0A", 1, False)


def test_versao_vigente_de_codigo_que_nao_existe_devolve_none():
    aconex = _Aconex(_token(), _pagina())
    assert cl.ClienteAconex(PERFIL, abrir=aconex).versao_vigente("#NADA") is None


def test_versao_por_revisao_normalizada_pega_a_maior_versao():
    aconex = _Aconex(_token(), _pagina(_doc("111", "#IT-1", "0A", 1, False), _doc("112", "#IT-1", "0A", 2, False),
                                       _doc("222", "#IT-1", "0B", 3, True)))
    assert cl.ClienteAconex(PERFIL, abrir=aconex).versao("#IT-1", "0a") == cl.Versao("112", "#IT-1", "0A", 2, False)
    assert aconex.chamadas[1]["params"]["show_document_history"] == "true"


def test_primeira_pagina_traz_o_total_do_register():
    """Como a sonda do DocManager: a página 1 de 25 e o `TotalResults`, sem paginar."""
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True), total=1234))
    pagina = cl.ClienteAconex(PERFIL, abrir=aconex).primeira_pagina("title:SOBRESSALENTES", historico=False)
    assert pagina.total == 1234 and len(pagina.registros) == 1
    assert aconex.chamadas[1]["params"]["page_number"] == 1 and aconex.chamadas[1]["params"]["page_size"] == 25
    assert len(aconex.chamadas) == 2


def test_primeira_pagina_sem_total_devolve_none():
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)))
    assert cl.ClienteAconex(PERFIL, abrir=aconex).primeira_pagina("", historico=False).total is None


def test_baixar_usa_markedup_e_devolve_bytes():
    aconex = _Aconex(_token(), _Resposta(200, b"%PDF-1.7 conteudo"))
    assert cl.ClienteAconex(PERFIL, abrir=aconex).baixar("222") == b"%PDF-1.7 conteudo"
    assert aconex.chamadas[1]["url"] == "https://us1.aconex.com/api/projects/1207975853/register/222/markedup"
    assert aconex.chamadas[1]["timeout"] == 180


def test_baixar_renova_o_token_no_401():
    aconex = _Aconex(_token("tok1"), _Resposta(401), _token("tok2"), _Resposta(200, b"%PDF"))
    assert cl.ClienteAconex(PERFIL, abrir=aconex).baixar("222") == b"%PDF"
    assert aconex.chamadas[3]["headers"]["Authorization"] == "Bearer tok2"


def test_baixar_com_erro_vira_erro_aconex():
    aconex = _Aconex(_token(), _Resposta(404))
    with pytest.raises(cl.ErroAconex):
        cl.ClienteAconex(PERFIL, abrir=aconex).baixar("999")


def test_token_e_reaproveitado_entre_chamadas():
    aconex = _Aconex(_token(), _pagina(_doc("1", "#IT-1", "0", 1, True)), _Resposta(200, b"%PDF"))
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
    aconex = _Aconex(_token("tok1"), _pagina(_doc("1", "#IT-1", "0", 1, True)))
    cliente = cl.ClienteAconex(PERFIL, abrir=aconex)
    cliente.conectar()
    cliente.versao_vigente("#IT-1")
    assert [c["url"] for c in aconex.chamadas].count(cl.AUTH_URL) == 1


def test_conectar_com_credencial_recusada_vira_erro():
    aconex = _Aconex(_Resposta(401, b"{}", {}))
    with pytest.raises(cl.ErroAconex):
        cl.ClienteAconex(PERFIL, abrir=aconex).conectar()

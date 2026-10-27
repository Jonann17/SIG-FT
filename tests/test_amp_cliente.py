"""O cliente do webhook do AMP (`sigft/core/amp/cliente.py`): a chave vai no cabeçalho, cada
modo tem o seu tempo, e nenhuma falha levanta exceção, todas voltam com um erro legível. Nenhum
teste toca a rede: o `abrir` é um dublê. Desenho:
`docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §7 e §8.
"""
from __future__ import annotations

import json

import pytest
import requests

from sigft.core import rede
from sigft.core.amp import cliente as am

URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CHAVE = "chave-secreta-123"
PING = {"ok": True, "modo": "ping", "versao_workflow": "2026-10-27", "execucao": "41"}
HTML = "<!doctype html><html><body><table><tr><td>ITEM</td></tr></table></body></html>"


class _Resposta:
    def __init__(self, status=200, dados=None, texto=None):
        self.status_code = status
        self._dados = dados
        self.text = texto if texto is not None else (json.dumps(dados) if dados is not None else "")

    def json(self):
        if self._dados is None:
            raise ValueError("não é JSON")
        return self._dados


class _Abrir:
    """Dublê do `rede.abrir`: guarda cada chamada e responde da fila. Devolve, como o de
    verdade, a sessão da rota que respondeu; o que vai por ela entra na mesma fila."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def _responder(self, chamada):
        self.chamadas.append(chamada)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, BaseException):
            raise resposta
        return resposta

    def __call__(self, url, **kw):
        return _Sessao(self), self._responder({"via": "abrir", "url": url, **kw})


class _Sessao:
    def __init__(self, abrir):
        self._abrir = abrir

    def request(self, metodo, url, **kw):
        return self._abrir._responder({"via": "sessao", "metodo": metodo, "url": url, **kw})


def _relogio(*instantes):
    seguintes = iter(instantes)
    return lambda: next(seguintes)


def _cliente(*respostas, relogio=None):
    abrir = _Abrir(*respostas)
    extra = {"relogio": relogio} if relogio else {}
    return am.ClienteAmp(URL, CHAVE, abrir=abrir, **extra), abrir


def _revisando(*respostas, relogio=None):
    """A revisão acha a rota com um ping antes: ele vem primeiro na fila."""
    return _cliente(_Resposta(200, PING), *respostas, relogio=relogio)


def test_a_chave_vai_no_cabecalho_e_nao_no_corpo():
    cliente, abrir = _cliente(_Resposta(200, PING))
    cliente.ping()
    chamada = abrir.chamadas[0]
    assert (chamada["url"], chamada["metodo"]) == (URL, "POST")
    assert chamada["headers"][am.CABECALHO_CHAVE] == CHAVE
    assert chamada["json"] == {"modo": "ping"}
    assert CHAVE not in json.dumps(chamada["json"])


def test_ping_le_a_versao_e_a_execucao():
    cliente, _abrir = _cliente(_Resposta(200, PING), relogio=_relogio(10.0, 10.4))
    resposta = cliente.ping()
    assert (resposta.ok, resposta.modo, resposta.http) == (True, "ping", 200)
    assert (resposta.versao_workflow, resposta.execucao) == ("2026-10-27", "41")
    assert resposta.segundos == pytest.approx(0.4)


def test_revisar_com_html_passa():
    cliente, _abrir = _revisando(_Resposta(200, {"ok": True, "modo": "revisar", "html": HTML, "execucao": "9"}))
    resposta = cliente.revisar({"modo": "revisar"})
    assert resposta.ok and resposta.html == HTML


def test_resposta_que_nao_e_json_vira_erro_com_o_corpo():
    cliente, _abrir = _revisando(_Resposta(200, None, "<html><body>Login do proxy</body></html>"))
    resposta = cliente.revisar({"modo": "revisar"})
    assert not resposta.ok
    assert resposta.erro == "o AMP não respondeu JSON (HTTP 200)"
    assert "Login do proxy" in resposta.corpo


def test_502_do_agente_traz_etapa_e_erro():
    dados = {"ok": False, "modo": "revisar", "etapa": "agente", "erro": "model timeout", "execucao": "77"}
    cliente, _abrir = _revisando(_Resposta(502, dados))
    resposta = cliente.revisar({"modo": "revisar"})
    assert (resposta.ok, resposta.http, resposta.erro, resposta.execucao) == (False, 502, "model timeout", "77")


def test_200_sem_html_e_falha():
    cliente, _abrir = _revisando(_Resposta(200, {"ok": True, "modo": "revisar", "html": "Não consegui ler.", "execucao": "5"}))
    resposta = cliente.revisar({"modo": "revisar"})
    assert (resposta.ok, resposta.erro) == (False, "o agente não devolveu HTML")


@pytest.mark.parametrize("status", [401, 403])
def test_chave_recusada(status):
    cliente, _abrir = _cliente(_Resposta(status, None, "Authorization data is wrong!"))
    resposta = cliente.ping()
    assert (resposta.ok, resposta.erro) == (False, f"o AMP recusou a chave (HTTP {status})")


def test_webhook_inexistente():
    cliente, _abrir = _cliente(_Resposta(404, {"code": 404, "message": "The requested webhook is not registered."}))
    resposta = cliente.ping()
    assert not resposta.ok
    assert resposta.erro.startswith("o webhook não existe (HTTP 404)")


def test_falha_de_rede_nao_levanta():
    cliente, _abrir = _cliente(rede.FalhaDeRede("nenhuma rota respondeu"))
    resposta = cliente.ping()
    assert (resposta.ok, resposta.http) == (False, None)
    assert resposta.erro.startswith("Sem conexão com o AMP:")


def test_tempo_por_modo():
    cliente, abrir = _cliente(_Resposta(200, PING), _Resposta(200, {"ok": True, "modo": "eco", "texto": "A"}),
                              _Resposta(200, {"ok": True, "modo": "revisar", "html": HTML}))
    cliente.ping()
    cliente.eco(["A"])
    cliente.revisar({"modo": "revisar"})
    assert [c["timeout"] for c in abrir.chamadas] == [30, 120, 900]
    assert abrir.chamadas[1]["json"] == {"modo": "eco", "codigos": ["A"]}


def test_erro_nao_mostra_a_chave():
    cliente, _abrir = _revisando(_Resposta(500, None, f"erro interno {CHAVE}"))
    resposta = cliente.revisar({"modo": "revisar"})
    assert CHAVE not in resposta.erro


# --- a revisão vai uma vez só (revisão final do ramo, 2026-10-27) -------------------------
# A cascata do `rede.abrir` manda de novo pela rota seguinte quando o tempo esgota ou a
# conexão cai. Na revisão, cada repetição seria uma execução nova do agente no AMP.

def test_revisar_vai_uma_vez_so_pela_rota_do_ping():
    cliente, abrir = _revisando(_Resposta(200, {"ok": True, "modo": "revisar", "html": HTML}))
    assert cliente.revisar({"modo": "revisar", "lista": {"codigo": "X"}}).ok
    assert [(c["via"], c["json"]["modo"]) for c in abrir.chamadas] == [("abrir", "ping"), ("sessao", "revisar")]
    revisao = abrir.chamadas[1]
    assert (revisao["metodo"], revisao["url"], revisao["timeout"]) == ("POST", URL, 900)
    assert revisao["headers"][am.CABECALHO_CHAVE] == CHAVE


def test_a_segunda_revisao_usa_a_mesma_rota_sem_outro_ping():
    cliente, abrir = _revisando(_Resposta(200, {"ok": True, "modo": "revisar", "html": HTML}),
                                _Resposta(200, {"ok": True, "modo": "revisar", "html": HTML}))
    cliente.revisar({"modo": "revisar"})
    cliente.revisar({"modo": "revisar"})
    assert [c["via"] for c in abrir.chamadas] == ["abrir", "sessao", "sessao"]


def test_tempo_esgotado_na_revisao_nao_repete():
    cliente, abrir = _revisando(requests.exceptions.ReadTimeout("read timed out"),
                                relogio=_relogio(0.0, 0.1, 5.0, 905.0))
    resposta = cliente.revisar({"modo": "revisar"})
    assert (resposta.ok, resposta.modo, resposta.http) == (False, "revisar", None)
    assert resposta.erro.startswith("o AMP não respondeu em 15 min")
    assert len(abrir.chamadas) == 2


def test_conexao_que_cai_no_meio_diz_quanto_tempo_passou():
    cliente, abrir = _revisando(requests.exceptions.ConnectionError("Connection aborted."),
                                relogio=_relogio(0.0, 0.1, 5.0, 65.0))
    resposta = cliente.revisar({"modo": "revisar"})
    assert resposta.erro.startswith("a conexão com o AMP caiu depois de 60 s")
    assert len(abrir.chamadas) == 2


def test_revisar_com_o_ping_recusado_nao_manda_a_lista():
    cliente, abrir = _cliente(_Resposta(403, None, "Authorization data is wrong!"))
    resposta = cliente.revisar({"modo": "revisar"})
    assert (resposta.ok, resposta.modo, resposta.erro) == (False, "revisar", "o AMP recusou a chave (HTTP 403)")
    assert len(abrir.chamadas) == 1

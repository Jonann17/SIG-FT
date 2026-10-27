"""O cliente do webhook do AMP (`sigft/core/amp/cliente.py`): a chave vai no cabeçalho, cada
modo tem o seu tempo, e nenhuma falha levanta exceção, todas voltam com um erro legível. Nenhum
teste toca a rede: o `abrir` é um dublê. Desenho:
`docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §7 e §8.
"""
from __future__ import annotations

import json

import pytest

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
    """Dublê do `rede.abrir`: guarda cada chamada e responde da fila."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, url, **kw):
        self.chamadas.append({"url": url, **kw})
        resposta = self.respostas.pop(0)
        if isinstance(resposta, BaseException):
            raise resposta
        return None, resposta


def _relogio(*instantes):
    seguintes = iter(instantes)
    return lambda: next(seguintes)


def _cliente(*respostas, relogio=None):
    abrir = _Abrir(*respostas)
    extra = {"relogio": relogio} if relogio else {}
    return am.ClienteAmp(URL, CHAVE, abrir=abrir, **extra), abrir


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
    cliente, _abrir = _cliente(_Resposta(200, {"ok": True, "modo": "revisar", "html": HTML, "execucao": "9"}))
    resposta = cliente.revisar({"modo": "revisar"})
    assert resposta.ok and resposta.html == HTML


def test_resposta_que_nao_e_json_vira_erro_com_o_corpo():
    cliente, _abrir = _cliente(_Resposta(200, None, "<html><body>Login do proxy</body></html>"))
    resposta = cliente.revisar({"modo": "revisar"})
    assert not resposta.ok
    assert resposta.erro == "o AMP não respondeu JSON (HTTP 200)"
    assert "Login do proxy" in resposta.corpo


def test_502_do_agente_traz_etapa_e_erro():
    dados = {"ok": False, "modo": "revisar", "etapa": "agente", "erro": "model timeout", "execucao": "77"}
    cliente, _abrir = _cliente(_Resposta(502, dados))
    resposta = cliente.revisar({"modo": "revisar"})
    assert (resposta.ok, resposta.http, resposta.erro, resposta.execucao) == (False, 502, "model timeout", "77")


def test_200_sem_html_e_falha():
    cliente, _abrir = _cliente(_Resposta(200, {"ok": True, "modo": "revisar", "html": "Não consegui ler.", "execucao": "5"}))
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
    cliente, _abrir = _cliente(_Resposta(500, None, f"erro interno {CHAVE}"))
    resposta = cliente.revisar({"modo": "revisar"})
    assert CHAVE not in resposta.erro

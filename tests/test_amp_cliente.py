"""O cliente dos workflows do AMP (`sigft/core/amp/cliente.py`): a chave vai no cabeçalho, o
`enviar` manda campos e arquivos em multipart, uma vez só, e nenhuma falha levanta exceção, todas
voltam com um erro legível. Nenhum teste toca a rede: o `abrir` é um dublê. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.3 e §5.5.
"""
from __future__ import annotations

import json

import pytest
import requests

from sigft.core import rede
from sigft.core.amp import cliente as am

URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CHAVE = "chave-secreta-123"
PING = {"ok": True, "modo": "ping", "versao_workflow": "2026-11-03", "execucao": "41"}
HTML = "<!doctype html><html><body><table><tr><td>ITEM</td></tr></table></body></html>"
CAMPOS = {"modo": "revisar", "mensagem": "Lista: X. Faça a revisão."}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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
        # Os arquivos são lidos AQUI, ainda abertos, como o `requests` faria; os objetos ficam em
        # `abertos` para o teste ver que foram fechados depois.
        arquivos = kw.pop("files", None) or {}
        kw["abertos"] = [aberto for _nome, aberto, _tipo in arquivos.values()]
        kw["files"] = {campo: (nome, aberto.read(), tipo) for campo, (nome, aberto, tipo) in arquivos.items()}
        return self._abrir._responder({"via": "sessao", "metodo": metodo, "url": url, **kw})


def _relogio(*instantes):
    seguintes = iter(instantes)
    return lambda: next(seguintes)


def _cliente(*respostas, relogio=None):
    abrir = _Abrir(*respostas)
    extra = {"relogio": relogio} if relogio else {}
    return am.ClienteAmp(URL, CHAVE, abrir=abrir, **extra), abrir


def _enviando(*respostas, relogio=None):
    """O envio acha a rota com um ping antes: ele vem primeiro na fila."""
    return _cliente(_Resposta(200, PING), *respostas, relogio=relogio)


def _arquivos(tmp_path):
    pdf = tmp_path / "#ITA0=Y01TF001&BPB020[0B].pdf"
    pdf.write_bytes(b"%PDF-1.7 atual")
    planilha = tmp_path / "#ITA0=Y01TF001&BPB020_STATUS_PMIB.xlsx"
    planilha.write_bytes(b"PK planilha")
    return {"revisao_atual": pdf, "status_pmib": planilha}


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
    assert (resposta.versao_workflow, resposta.execucao) == ("2026-11-03", "41")
    assert resposta.segundos == pytest.approx(0.4)


def test_enviar_manda_os_campos_e_os_arquivos_em_multipart(tmp_path):
    cliente, abrir = _enviando(_Resposta(200, {"ok": True, "modo": "revisar", "html": HTML, "execucao": "9"}))
    resposta = cliente.enviar(CAMPOS, _arquivos(tmp_path))
    assert (resposta.ok, resposta.modo, resposta.html) == (True, "revisar", HTML)
    envio = abrir.chamadas[1]
    assert envio["data"] == CAMPOS and "json" not in envio
    assert envio["files"] == {
        "revisao_atual": ("#ITA0=Y01TF001&BPB020[0B].pdf", b"%PDF-1.7 atual", "application/pdf"),
        "status_pmib": ("#ITA0=Y01TF001&BPB020_STATUS_PMIB.xlsx", b"PK planilha", XLSX),
    }
    assert envio["headers"][am.CABECALHO_CHAVE] == CHAVE
    assert CHAVE not in json.dumps(envio["data"])


def test_os_arquivos_ficam_fechados_depois(tmp_path):
    cliente, abrir = _enviando(_Resposta(200, {"ok": True, "html": HTML}))
    cliente.enviar(CAMPOS, _arquivos(tmp_path))
    abertos = abrir.chamadas[1]["abertos"]
    assert len(abertos) == 2 and all(arquivo.closed for arquivo in abertos)


def test_arquivo_que_nao_abre_vira_erro_sem_mandar(tmp_path):
    cliente, abrir = _enviando()
    resposta = cliente.enviar(CAMPOS, {"revisao_atual": tmp_path / "nao-existe.pdf"})
    assert (resposta.ok, resposta.modo) == (False, "revisar")
    assert resposta.erro.startswith("não consegui abrir um arquivo para mandar")
    assert [c["via"] for c in abrir.chamadas] == ["abrir"]


def test_resposta_lista_os_arquivos_recebidos(tmp_path):
    cliente, _abrir = _enviando(_Resposta(200, {"ok": True, "html": HTML, "arquivos": ["a.pdf", "b.xlsx"]}))
    assert cliente.enviar(CAMPOS, _arquivos(tmp_path)).arquivos == ["a.pdf", "b.xlsx"]
    assert am.RespostaAmp(True, "ping", 200, 0.1, "{}", {"arquivos": "x"}).arquivos == []
    assert am.RespostaAmp(True, "ping", 200, 0.1, "{}").arquivos == []


def test_o_cliente_nao_julga_o_conteudo():
    # Se veio HTML é o serviço da revisão que diz: o cliente serve a qualquer workflow.
    cliente, _abrir = _enviando(_Resposta(200, {"ok": True, "html": "Não consegui ler."}))
    resposta = cliente.enviar(CAMPOS, {})
    assert (resposta.ok, resposta.html) == (True, "Não consegui ler.")


def test_resposta_que_nao_e_json_vira_erro_com_o_corpo():
    cliente, _abrir = _enviando(_Resposta(200, None, "<html><body>Login do proxy</body></html>"))
    resposta = cliente.enviar(CAMPOS, {})
    assert not resposta.ok
    assert resposta.erro == "o AMP não respondeu JSON (HTTP 200)"
    assert "Login do proxy" in resposta.corpo


def test_502_do_agente_traz_etapa_e_erro():
    dados = {"ok": False, "modo": "revisar", "etapa": "agente", "erro": "model timeout", "execucao": "77"}
    cliente, _abrir = _enviando(_Resposta(502, dados))
    resposta = cliente.enviar(CAMPOS, {})
    assert (resposta.ok, resposta.http, resposta.erro, resposta.execucao) == (False, 502, "model timeout", "77")
    assert resposta.dados["etapa"] == "agente"


def test_400_sem_os_arquivos_traz_a_etapa():
    dados = {"ok": False, "modo": "revisar", "etapa": "arquivos", "execucao": "78",
             "erro": "os arquivos não chegaram ao agente: o workflow recebeu 0 arquivo(s)"}
    cliente, _abrir = _enviando(_Resposta(400, dados))
    resposta = cliente.enviar(CAMPOS, {})
    assert (resposta.ok, resposta.http) == (False, 400)
    assert resposta.erro.startswith("os arquivos não chegaram ao agente")


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


def test_tempo_do_ping_e_do_envio():
    cliente, abrir = _enviando(_Resposta(200, {"ok": True, "html": HTML}))
    cliente.enviar(CAMPOS, {})
    assert [c["timeout"] for c in abrir.chamadas] == [30, 2700]


def test_erro_nao_mostra_a_chave():
    cliente, _abrir = _enviando(_Resposta(500, None, f"erro interno {CHAVE}"))
    resposta = cliente.enviar(CAMPOS, {})
    assert CHAVE not in resposta.erro and CHAVE not in resposta.corpo


# --- o envio vai uma vez só (revisão final do ramo, 2026-10-27) ---------------------------
# A cascata do `rede.abrir` manda de novo pela rota seguinte quando o tempo esgota ou a
# conexão cai. No envio, cada repetição seria uma execução nova do agente no AMP.

def test_enviar_vai_uma_vez_so_pela_rota_do_ping():
    cliente, abrir = _enviando(_Resposta(200, {"ok": True, "modo": "revisar", "html": HTML}))
    assert cliente.enviar(CAMPOS, {}).ok
    assert [c["via"] for c in abrir.chamadas] == ["abrir", "sessao"]
    assert abrir.chamadas[0]["json"] == {"modo": "ping"}
    envio = abrir.chamadas[1]
    assert (envio["metodo"], envio["url"], envio["timeout"]) == ("POST", URL, 2700)
    assert envio["headers"][am.CABECALHO_CHAVE] == CHAVE


def test_o_segundo_envio_usa_a_mesma_rota_sem_outro_ping():
    cliente, abrir = _enviando(_Resposta(200, {"ok": True, "html": HTML}), _Resposta(200, {"ok": True, "html": HTML}))
    cliente.enviar(CAMPOS, {})
    cliente.enviar(CAMPOS, {})
    assert [c["via"] for c in abrir.chamadas] == ["abrir", "sessao", "sessao"]


def test_tempo_esgotado_no_envio_nao_repete():
    cliente, abrir = _enviando(requests.exceptions.ReadTimeout("read timed out"),
                               relogio=_relogio(0.0, 0.1, 5.0, 905.0))
    resposta = cliente.enviar(CAMPOS, {})
    assert (resposta.ok, resposta.modo, resposta.http) == (False, "revisar", None)
    assert resposta.erro.startswith("o AMP não respondeu em 45 min")
    assert len(abrir.chamadas) == 2


def test_conexao_que_cai_no_meio_diz_quanto_tempo_passou():
    cliente, abrir = _enviando(requests.exceptions.ConnectionError("Connection aborted."),
                               relogio=_relogio(0.0, 0.1, 5.0, 65.0))
    resposta = cliente.enviar(CAMPOS, {})
    assert resposta.erro.startswith("a conexão com o AMP caiu depois de 60 s")
    assert len(abrir.chamadas) == 2


def test_enviar_com_o_ping_recusado_nao_manda():
    cliente, abrir = _cliente(_Resposta(403, None, "Authorization data is wrong!"))
    resposta = cliente.enviar(CAMPOS, {})
    assert (resposta.ok, resposta.modo, resposta.erro) == (False, "revisar", "o AMP recusou a chave (HTTP 403)")
    assert len(abrir.chamadas) == 1

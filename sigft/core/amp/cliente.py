"""O cliente do webhook do workflow "Revisão das listas" no n8n da GE (`amp/revisao_de_listas/`).

Três modos: `ping` (rede, chave e workflow publicado, sem chamar o modelo), `eco` (o modelo
devolve os códigos que recebeu, para ver se o AMP os mascara) e `revisar` (uma lista). A chave
vai no cabeçalho `X-SIGFT-Chave`, nunca no corpo, no log ou numa mensagem. Nenhuma falha levanta
exceção: volta uma `RespostaAmp` com `ok` falso e um `erro` legível, que o diagnóstico usa.

A revisão vai uma vez só, pela rota que o `ping` achou: a cascata do `rede.abrir` manda a
requisição de novo pela rota seguinte quando o tempo esgota ou a conexão cai, e cada repetição
seria uma execução nova do agente no AMP (revisão final do ramo, 2026-10-27). Desenho: `docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §7 e §8.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace

from sigft.core import rede

CABECALHO_CHAVE = "X-SIGFT-Chave"
TEMPOS = {"ping": 30, "eco": 120, "revisar": 900}   # segundos de limite por chamada
_TEM_HTML = re.compile(r"<html|<table", re.IGNORECASE)


@dataclass(frozen=True)
class RespostaAmp:
    ok: bool
    modo: str
    http: int | None
    segundos: float
    corpo: str            # a resposta como veio (o diagnóstico mostra o começo)
    dados: dict = field(default_factory=dict)
    erro: str = ""

    @property
    def html(self) -> str:
        return str(self.dados.get("html") or "")

    @property
    def texto(self) -> str:
        return str(self.dados.get("texto") or "")

    @property
    def execucao(self) -> str:
        return str(self.dados.get("execucao") or "")

    @property
    def versao_workflow(self) -> str:
        return str(self.dados.get("versao_workflow") or "")


class ClienteAmp:
    """Chama o webhook em nome do SIG-FT. `abrir` e `relogio` são injetáveis (testes)."""

    def __init__(self, url: str, chave: str, *, abrir=None, relogio=time.monotonic, log_cb=lambda _m: None):
        self._url = url
        self._chave = chave
        self._abrir = abrir or rede.abrir
        self._relogio = relogio
        self._log = log_cb
        self._sessao = None      # a sessão da rota que já respondeu (o `rede.abrir` a devolve)

    def ping(self) -> RespostaAmp:
        return self._chamar({"modo": "ping"})

    def eco(self, codigos: list[str]) -> RespostaAmp:
        return self._chamar({"modo": "eco", "codigos": list(codigos)})

    def revisar(self, pedido: dict) -> RespostaAmp:
        """Uma lista, numa requisição só, pela rota do `ping` (na primeira vez, o ping vai antes).
        Tempo esgotado ou conexão cortada vira erro, e não outra tentativa: o agente pode estar
        rodando no AMP."""
        if self._sessao is None:
            ping = self.ping()
            if not ping.ok:
                return replace(ping, modo="revisar")
        inicio = self._relogio()
        try:
            resposta = self._sessao.request("POST", self._url, json=pedido, timeout=TEMPOS["revisar"],
                                            headers=self._cabecalhos())
        except Exception as erro:  # noqa: BLE001 -- vira diagnóstico, sem repetir
            segundos = self._relogio() - inicio
            return RespostaAmp(False, "revisar", None, segundos, "",
                               erro=self._sem_chave(_falha_da_revisao(erro, segundos)))
        return self._interpretar("revisar", resposta, self._relogio() - inicio)

    def _sem_chave(self, texto: str) -> str:
        return texto.replace(self._chave, "***") if self._chave else texto

    def _cabecalhos(self) -> dict:
        return {CABECALHO_CHAVE: self._chave, "Accept": "application/json"}

    def _chamar(self, corpo: dict) -> RespostaAmp:
        modo = str(corpo.get("modo") or "revisar")
        inicio = self._relogio()
        try:
            sessao, resposta = self._abrir(self._url, metodo="POST", json=corpo, timeout=TEMPOS[modo],
                                           headers=self._cabecalhos(), status_ok=None, log_cb=self._log)
        except rede.FalhaDeRede as erro:
            return RespostaAmp(False, modo, None, self._relogio() - inicio, "",
                               erro=self._sem_chave(f"Sem conexão com o AMP: {rede.resumo_erro(erro)}"))
        except Exception as erro:  # noqa: BLE001 -- o cliente não levanta: a falha vira diagnóstico
            return RespostaAmp(False, modo, None, self._relogio() - inicio, "",
                               erro=self._sem_chave(f"Falha ao chamar o AMP: {type(erro).__name__}: {erro}"))
        self._sessao = sessao
        return self._interpretar(modo, resposta, self._relogio() - inicio)

    def _interpretar(self, modo: str, resposta, segundos: float) -> RespostaAmp:
        status = getattr(resposta, "status_code", None)
        texto = self._sem_chave(str(getattr(resposta, "text", "") or ""))
        try:
            dados = resposta.json()
        except Exception:  # noqa: BLE001 -- página de proxy, de login, texto do n8n
            dados = None
        if status in (401, 403):
            return RespostaAmp(False, modo, status, segundos, texto, erro=f"o AMP recusou a chave (HTTP {status})")
        if status == 404:
            return RespostaAmp(False, modo, status, segundos, texto,
                               erro="o webhook não existe (HTTP 404): o workflow está publicado e o endereço é "
                                    "a Production URL?")
        if not isinstance(dados, dict):
            return RespostaAmp(False, modo, status, segundos, texto, erro=f"o AMP não respondeu JSON (HTTP {status})")
        if (status or 0) >= 400 or not dados.get("ok"):
            erro = self._sem_chave(str(dados.get("erro") or f"HTTP {status}"))
            return RespostaAmp(False, modo, status, segundos, texto, dados, erro)
        if modo == "revisar" and not _TEM_HTML.search(str(dados.get("html") or "")):
            return RespostaAmp(False, modo, status, segundos, texto, dados, "o agente não devolveu HTML")
        return RespostaAmp(True, modo, status, segundos, texto, dados)


def _falha_da_revisao(erro: BaseException, segundos: float) -> str:
    """A revisão que não voltou, sem repetir: o tempo esgotado e a conexão que caiu no meio
    (um proxy que corta chamada longa) dizem quanto tempo passou."""
    import requests

    if isinstance(erro, requests.exceptions.ReadTimeout):
        return (f"o AMP não respondeu em {TEMPOS['revisar'] // 60} min; a execução pode seguir no n8n "
                "(veja em Executions)")
    if isinstance(erro, requests.exceptions.ConnectionError):
        return (f"a conexão com o AMP caiu depois de {segundos:.0f} s ({rede.resumo_erro(erro)}): "
                "um proxy que corta chamada longa?")
    return f"Falha ao chamar o AMP: {type(erro).__name__}: {erro}"

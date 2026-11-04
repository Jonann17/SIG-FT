"""O cliente dos workflows do AMP, a IA interna da GE, pelo n8n.

Genérico desde 2026-11-03: sabe fazer o `ping` (rede, chave e workflow publicado, sem chamar o
agente) e o `enviar` (campos e arquivos num POST multipart). O que vai em cada workflow é de quem
chama: a revisão das listas monta o dela em `services/revisao_amp.py`, e um módulo novo, com
outro agente, monta o seu. A chave vai no cabeçalho `X-SIGFT-Chave`, nunca no corpo, no log ou
numa mensagem. Nenhuma falha levanta exceção: volta uma `RespostaAmp` com `ok` falso e um `erro`
legível, que o diagnóstico usa.

O `enviar` vai uma vez só, pela rota que o `ping` achou: a cascata do `rede.abrir` manda a
requisição de novo pela rota seguinte quando o tempo esgota ou a conexão cai, e cada repetição
seria uma execução nova do agente no AMP (revisão final do ramo, 2026-10-27). Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.3 e §5.5.
"""
from __future__ import annotations

import time
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from pathlib import Path

from sigft.core import rede

CABECALHO_CHAVE = "X-SIGFT-Chave"
# 45 min por envio (2026-11-04): uma lista levou 17 min no AMP, e o limite de 15 a cortava.
TEMPOS = {"ping": 30, "enviar": 2700, "buscar": 60}   # segundos de limite por chamada
TIPOS = {".pdf": "application/pdf",
         ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


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
    def execucao(self) -> str:
        return str(self.dados.get("execucao") or "")

    @property
    def versao_workflow(self) -> str:
        return str(self.dados.get("versao_workflow") or "")

    @property
    def estado(self) -> str:
        """`aceito` (o envio entrou e o agente começou), `pendente`, `pronto` ou `erro` (a
        busca); vazio na resposta de um workflow que devolve o HTML na mesma chamada."""
        return str(self.dados.get("estado") or "")

    @property
    def pedido(self) -> str:
        """O número do pedido para a busca: a execução do n8n que roda o agente."""
        return str(self.dados.get("pedido") or "")

    @property
    def arquivos(self) -> list[str]:
        """Os nomes dos arquivos que chegaram ao agente, como o workflow os listou."""
        nomes = self.dados.get("arquivos")
        return [str(nome) for nome in nomes] if isinstance(nomes, list) else []


def tipo_do_arquivo(caminho: Path) -> str:
    return TIPOS.get(caminho.suffix.lower(), "application/octet-stream")


class ClienteAmp:
    """Chama um webhook do AMP em nome do SIG-FT. `abrir` e `relogio` são injetáveis (testes)."""

    def __init__(self, url: str, chave: str, *, abrir=None, relogio=time.monotonic, log_cb=lambda _m: None):
        self._url = url
        self._chave = chave
        self._abrir = abrir or rede.abrir
        self._relogio = relogio
        self._log = log_cb
        self._sessao = None      # a sessão da rota que já respondeu (o `rede.abrir` a devolve)

    def ping(self) -> RespostaAmp:
        """Rede, chave e workflow publicado, sem chamar o agente. Acha a rota que o `enviar` usa."""
        inicio = self._relogio()
        try:
            sessao, resposta = self._abrir(self._url, metodo="POST", json={"modo": "ping"}, timeout=TEMPOS["ping"],
                                           headers=self._cabecalhos(), status_ok=None, log_cb=self._log)
        except rede.FalhaDeRede as erro:
            return RespostaAmp(False, "ping", None, self._relogio() - inicio, "",
                               erro=self._sem_chave(f"Sem conexão com o AMP: {rede.resumo_erro(erro)}"))
        except Exception as erro:  # noqa: BLE001 -- o cliente não levanta: a falha vira diagnóstico
            return RespostaAmp(False, "ping", None, self._relogio() - inicio, "",
                               erro=self._sem_chave(f"Falha ao chamar o AMP: {type(erro).__name__}: {erro}"))
        self._sessao = sessao
        return self._interpretar("ping", resposta, self._relogio() - inicio)

    def enviar(self, campos: dict[str, str], arquivos: dict[str, Path]) -> RespostaAmp:
        """Os `campos` e os `arquivos` (campo do formulário -> arquivo) num POST multipart, numa
        requisição só, pela rota do `ping` (na primeira vez, o ping vai antes). Cada arquivo vai com
        o próprio nome e é fechado logo depois. Tempo esgotado ou conexão cortada vira erro, e não
        outra tentativa: o agente pode estar rodando no AMP."""
        modo = str(campos.get("modo") or "enviar")
        if self._sessao is None:
            ping = self.ping()
            if not ping.ok:
                return replace(ping, modo=modo)
        inicio = self._relogio()
        with ExitStack() as abertos:
            try:
                partes = {campo: (caminho.name, abertos.enter_context(open(caminho, "rb")), tipo_do_arquivo(caminho))
                          for campo, caminho in arquivos.items()}
            except OSError as erro:
                return RespostaAmp(False, modo, None, 0.0, "",
                                   erro=f"não consegui abrir um arquivo para mandar: {erro}")
            try:
                resposta = self._sessao.request("POST", self._url, data=dict(campos), files=partes,
                                                timeout=TEMPOS["enviar"], headers=self._cabecalhos())
            except Exception as erro:  # noqa: BLE001 -- vira diagnóstico, sem repetir
                segundos = self._relogio() - inicio
                return RespostaAmp(False, modo, None, segundos, "",
                                   erro=self._sem_chave(_falha_do_envio(erro, segundos)))
        return self._interpretar(modo, resposta, self._relogio() - inicio)

    def buscar(self, pedido: str) -> RespostaAmp:
        """Pergunta pelo resultado do `pedido` (a busca não chama o agente: só lê o que o workflow
        guardou). Pela rota do `ping`; sem rota ainda, o ping vai antes. Pode repetir à vontade."""
        if self._sessao is None:
            ping = self.ping()
            if not ping.ok:
                return replace(ping, modo="buscar")
        inicio = self._relogio()
        try:
            resposta = self._sessao.request("POST", self._url, json={"modo": "buscar", "pedido": str(pedido)},
                                            timeout=TEMPOS["buscar"], headers=self._cabecalhos())
        except Exception as erro:  # noqa: BLE001 -- vira erro legível; a próxima busca tenta de novo
            return RespostaAmp(False, "buscar", None, self._relogio() - inicio, "",
                               erro=self._sem_chave(f"Falha ao perguntar ao AMP: {type(erro).__name__}: {erro}"))
        return self._interpretar("buscar", resposta, self._relogio() - inicio)

    def _sem_chave(self, texto: str) -> str:
        return texto.replace(self._chave, "***") if self._chave else texto

    def _cabecalhos(self) -> dict:
        return {CABECALHO_CHAVE: self._chave, "Accept": "application/json"}

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
        return RespostaAmp(True, modo, status, segundos, texto, dados)


def _falha_do_envio(erro: BaseException, segundos: float) -> str:
    """O envio que não voltou, sem repetir: o tempo esgotado e a conexão que caiu no meio (um
    proxy que corta chamada longa) dizem quanto tempo passou."""
    import requests

    if isinstance(erro, requests.exceptions.ReadTimeout):
        return (f"o AMP não respondeu em {TEMPOS['enviar'] // 60} min; a execução pode seguir no n8n "
                "(veja em Executions)")
    if isinstance(erro, requests.exceptions.ConnectionError):
        return (f"a conexão com o AMP caiu depois de {segundos:.0f} s ({rede.resumo_erro(erro)}): "
                "um proxy que corta chamada longa?")
    return f"Falha ao chamar o AMP: {type(erro).__name__}: {erro}"

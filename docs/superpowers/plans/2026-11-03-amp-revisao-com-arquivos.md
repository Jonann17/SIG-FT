# Peça 2 v2 (o agente do AMP recebe os arquivos): plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O SIG-FT passa a mandar ao agente do AMP os dois PDFs e o `_STATUS_PMIB` como estão, só
das listas marcadas, com o webhook configurado dentro da aba e um log que mostra cada passo.

**Architecture:**
- **O cliente** (`core/amp/cliente.py`) fica genérico: `ping` e `enviar(campos, arquivos)` em
  multipart.
- **O serviço** (`services/revisao_amp.py`):
  - monta o pedido de cada lista (a mensagem e os arquivos);
  - roda a rodada com o ping antes;
  - escreve o log de cada lista, com o batimento da espera;
  - gera o diagnóstico.
- **A aba** (`app_qt/views/revisao_amp.py`):
  - mostra as listas marcáveis;
  - guarda o webhook com nomes próprios (`app_qt/widgets/webhook_amp.py`);
  - grava o log em arquivo com o `LogDeExecucao`.
- **O workflow do n8n** (`amp/revisao_de_listas/`) passa a ser gerado igual ao que foi colado e
  testado na GE em 03/11.

**Tech Stack:** Python 3.10+, PySide6 (pytest-qt, offscreen), `requests` (multipart), n8n (JSON gerado).

**Desenho:** `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md` (a autoridade).

## Global Constraints

- **Português e commits.** Código, comentários, docs e commits em português. Mensagem de commit sem
  acento, terminada pelas linhas `Co-Authored-By` e `Claude-Session` desta sessão.
- **Verde antes de cada commit:** `bash scripts/check.sh` (compileall + pytest), `python -m ruff
  check .` e `python -m pyflakes frontend.py`. A suíte roda sem rede: o AMP só existe na GE.
- **Texto de interface** vai em `t("...")` ou `marcar("...")` (`sigft/app/idioma.py`), com tradução
  em `sigft/app/idiomas/es.json` e `en.json`.
  - Toda chave nova tem tradução; nenhuma tradução sobra; tradução sem travessão (— ou –).
  - O catálogo fica na forma do `python tools/textos_da_interface.py --arrumar`.
  - O **log de console continua em português, sem `t()`**.
  - Arquivo de tela novo entra em `CONVERTIDOS`, em `tests/test_textos_da_interface.py`.
- **"Como funciona"** (`sigft/app/como_funciona.py`): de 3 a 6 itens; nenhum item, nem a frase, passa
  de 140 caracteres em pt, es e en.
- **A chave do webhook** nunca vai para a tela, o console, o log em arquivo ou o diagnóstico. Só se
  diz `chave posta` ou `chave não posta`.
- **O diagnóstico** nunca leva conteúdo de documento: o `html` vai só como tamanho, e o `erro` do
  workflow vai cortado em 300 caracteres.
- **UI sem regra de negócio, serviço sem Qt** (CLAUDE.md, princípio 2).
- **Abrir o app depois de mexer em tela:** `QT_QPA_PLATFORM=offscreen python frontend.py --smoke`.
- **Nomes do webhook neste workflow:** `AMP_REVISAO_LISTAS_URL` e `AMP_REVISAO_LISTAS_CHAVE`; os
  antigos `AMP_WEBHOOK_URL` e `AMP_WEBHOOK_CHAVE` são adotados uma vez. Variáveis de ambiente:
  `SIGFT_AMP_REVISAO_LISTAS_URL` e `SIGFT_AMP_REVISAO_LISTAS_CHAVE`.
- **`versao_workflow`:** `2026-11-03`. O agente no AMP: `Spare Parts Document Reviewer`, modelo
  `bedrock-claude-sonnet-5.5`.

## Mapa dos arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `sigft/core/amp/cliente.py` | reescrever | `ClienteAmp` genérico (`ping`, `enviar`) e `RespostaAmp` (`arquivos`) |
| `sigft/services/revisao_amp.py` | reescrever | `PedidoAmp`, a mensagem, a rodada com log e batimento, o diagnóstico e o teste de conexão |
| `sigft/app_qt/widgets/webhook_amp.py` | criar | `ChavesDoWebhook`, `ler`/`gravar` (com a adoção dos nomes antigos), `problema_do_endereco` e `JanelaDoWebhook` |
| `sigft/app_qt/views/revisao_amp.py` | reescrever | a aba: listas marcáveis, botão Webhook…, log em arquivo |
| `sigft/config.py` | editar | `ENV_VAR_POR_CHAVE`: os nomes do webhook deste workflow |
| `sigft/app_qt/views/home.py` | editar | `CHAVES_API` sem os dois campos do AMP |
| `sigft/app/textos_dicas.py`, `sigft/app/como_funciona.py` | editar | as dicas e o "Como funciona" da aba |
| `sigft/app/idiomas/es.json`, `en.json` | editar | as traduções novas, sem as que sobraram |
| `amp/revisao_de_listas/gerar_workflow.py` | reescrever | gera o workflow de 03/11 |
| `amp/revisao_de_listas/workflow_revisao_de_listas.json` | regenerar | o arquivo para importar no n8n |
| `amp/revisao_de_listas/agente.md` | criar | a cópia do agente no AMP |
| `amp/revisao_de_listas/pedido.md` | apagar | o pedido agora mora no agente |
| `amp/revisao_de_listas/LEIA-ME.md` | reescrever | ligar o agente e o workflow; testar; sintomas |
| `tests/test_amp_cliente.py`, `tests/test_revisao_amp_pedido.py`, `tests/test_revisao_amp_rodada.py`, `tests/test_qt_tela_revisao_amp.py`, `tests/test_amp_workflow.py` | reescrever | os testes de cada peça |
| `tests/test_qt_webhook_amp.py` | criar | o webhook do módulo |
| `tests/test_config.py`, `tests/test_qt_home_paineis.py`, `tests/test_textos_da_interface.py` | editar | os nomes novos, os campos que saíram, o `CONVERTIDOS` |
| `docs/base-conhecimento/14-aconex-e-conferencia-de-revisoes.md`, `docs/ROTEIRO_DE_TESTE.md`, `docs/ACONEX_AO_VIVO.md`, `CLAUDE.md`, `docs/refatoracao/PENDENCIAS.md` | editar | a documentação da peça 2 v2 |

**Log na aba:** a chamada que escreve no console e no arquivo se chama `log` (o `envolver` do `LogDeExecucao`): a guarda de textos da interface (`tools/textos_da_interface.py`) não cobra `t()` do que vai para `log(...)`, e cobraria de um `registrar(...)`.

**Ordem e dependências:**
- A Tarefa 1 muda `revisar` para `enviar`. O serviço só passa a usar o `enviar` na Tarefa 2: entre
  as duas, a suíte fica verde, porque o serviço é testado com dublês, mas a revisão real não roda.
- A Tarefa 2 muda a assinatura de `testar_conexao` e de `revisar_listas`. A aba só se ajusta na
  Tarefa 4.
- O app só fica coerente de novo depois da Tarefa 4. Não se lança versão antes da Tarefa 6.

---

### Task 1: O cliente genérico do AMP

**Files:**
- Modify: `sigft/core/amp/cliente.py` (reescrever inteiro)
- Test: `tests/test_amp_cliente.py` (reescrever inteiro)

**Interfaces:**
- Produces:
  - `ClienteAmp(url: str, chave: str, *, abrir=None, relogio=time.monotonic, log_cb=...)`;
  - `ClienteAmp.ping() -> RespostaAmp`;
  - `ClienteAmp.enviar(campos: dict[str, str], arquivos: dict[str, Path]) -> RespostaAmp`;
  - `RespostaAmp(ok, modo, http, segundos, corpo, dados={}, erro="")`, com as propriedades `html`,
    `execucao`, `versao_workflow` e `arquivos: list[str]`;
  - `CABECALHO_CHAVE = "X-SIGFT-Chave"` e `TEMPOS = {"ping": 30, "enviar": 900}`.
- Sai: `ClienteAmp.revisar`, `ClienteAmp.eco`, `RespostaAmp.texto`. O cliente também deixa de julgar
  se a resposta tem HTML: isso passa para o serviço (Tarefa 2).

- [ ] **Step 1: Escrever os testes novos do cliente**

Substitua `tests/test_amp_cliente.py` por:

```python
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
    assert [c["timeout"] for c in abrir.chamadas] == [30, 900]


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
    assert (envio["metodo"], envio["url"], envio["timeout"]) == ("POST", URL, 900)
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
    assert resposta.erro.startswith("o AMP não respondeu em 15 min")
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_amp_cliente.py -q`
Expected: FAIL (`AttributeError: 'ClienteAmp' object has no attribute 'enviar'` e `RespostaAmp` sem `arquivos`).

- [ ] **Step 3: Reescrever o cliente**

Substitua `sigft/core/amp/cliente.py` por:

```python
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
TEMPOS = {"ping": 30, "enviar": 900}   # segundos de limite por chamada
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_amp_cliente.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Suíte, ruff e commit**

Run: `bash scripts/check.sh && python -m ruff check .`
Expected: `TUDO OK` e `All checks passed!`.

```bash
git add sigft/core/amp/cliente.py tests/test_amp_cliente.py
git commit -m "Cliente do AMP generico: ping e enviar campos + arquivos em multipart"
```

Em todo commit deste plano, o corpo diz o que muda e por quê e termina com as linhas de atribuição da sessão.

---

### Task 2: O serviço: o pedido com os arquivos, a rodada com o log e o diagnóstico

**Files:**
- Modify: `sigft/services/revisao_amp.py` (reescrever inteiro)
- Test: `tests/test_revisao_amp_pedido.py` (reescrever inteiro)
- Test: `tests/test_revisao_amp_rodada.py` (reescrever inteiro)

**Interfaces:**
- Consumes: `ClienteAmp.ping()`, `ClienteAmp.enviar(campos, arquivos)` e `RespostaAmp.arquivos` (Tarefa 1).
- Produces:
  - `PedidoAmp(campos: dict[str, str], arquivos: dict[str, Path])`;
  - `mensagem_da_lista(lista: ListaParaAmp, *, hoje: date | None = None) -> str`;
  - `montar_pedido(lista: ListaParaAmp, *, hoje: date | None = None) -> PedidoAmp`;
  - `revisar_listas(listas, cliente, *, versao_sigft, url, chave_posta, log_cb, progress_cb=None, cancelado_cb=None, resultado_cb=None, gravar_diagnostico=True, montar=montar_pedido, desmarcadas=(), com_falta=(), batimento=BATIMENTO) -> list[ResultadoAmp]`;
  - `testar_conexao(cliente) -> list[str]`;
  - `diagnostico(lista, pedido: PedidoAmp | None, resposta: RespostaAmp | None, *, url, chave_posta, versao_sigft, erro="") -> str`.
- Ficam como estão: `ListaParaAmp`, `ResultadoAmp`, `listas_para_amp`, `nome_do_html`,
  `gravar_html` e `diagnosticos_para_copiar`.
- Saem: `texto_do_pdf`, `TextoPdf`, `TabelaStatus`, `status_pmib_em_tsv`, `codigos_para_eco`,
  `_celula`, `_trechos_do_documento`, `_sem_trechos` e `MATERIAIS_NO_ECO`.

- [ ] **Step 1: Reescrever `tests/test_revisao_amp_pedido.py`**

```python
"""O pedido de cada lista para o AMP: os arquivos como estão na pasta e a mensagem que o SIG-FT
monta sozinho, e quais listas têm o que precisa. O SIG-FT não lê mais o conteúdo dos arquivos.
Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.2.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

CODIGO = "#ITA0=Y01TF001&BPB020"
HOJE = date(2026, 11, 3)


def _lista(codigo=CODIGO, ultima="0B", em_uso="0A", status_real="Aprovado"):
    return cr.ListaNaMapeadora(codigo, ultima, "Em Processo", status_real, em_uso,
                               f"Lista {codigo[-3:]}/{codigo}_STATUS_PMIB.xlsx")


def _pasta(raiz: Path, codigo=CODIGO, pdfs=(), com_status=True) -> Path:
    pasta = raiz / f"Lista {codigo[-3:]}"
    pasta.mkdir(parents=True, exist_ok=True)
    if com_status:
        (pasta / f"{codigo}_STATUS_PMIB.xlsx").write_bytes(b"planilha")
    for revisao in pdfs:
        (pasta / cr.nome_do_pdf(codigo, revisao)).write_bytes(b"%PDF")
    return pasta


def _conferencia(*itens):
    return cr.Conferencia(list(itens), em_dia=0, sem_status_pmib=0)


def _uma_lista(tmp_path, *, em_uso="0A", ultima="0B"):
    pasta = _pasta(tmp_path, pdfs=(em_uso, ultima) if em_uso else (ultima,))
    item = cr.ItemConferencia(_lista(ultima=ultima, em_uso=em_uso), "aprovada", pasta)
    [lista] = ra.listas_para_amp(_conferencia(item), [], tmp_path, None)
    return lista


# ------------------------------------------------------------------ quais listas vão

def test_listas_usam_os_pdfs_baixados_na_sessao(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0A",))
    baixado = pasta / cr.nome_do_pdf(CODIGO, "0C")
    baixado.write_bytes(b"%PDF")
    downloads = [cr.Download(CODIGO, "0C", baixado, "baixado", "mapeadora desatualizada: o Aconex está na 0C"),
                 cr.Download(CODIGO, "0A", pasta / cr.nome_do_pdf(CODIGO, "0A"), "ja_existia")]
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(), "aprovada", pasta)),
                                 downloads, tmp_path, None)
    assert (lista.revisao_atual, lista.pdf_atual, lista.falta) == ("0C", baixado, "")
    assert lista.pdf_em_uso == pasta / cr.nome_do_pdf(CODIGO, "0A")
    assert lista.status_pmib == pasta / f"{CODIGO}_STATUS_PMIB.xlsx"


def test_listas_sem_download_procuram_pelo_nome(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0A", "0B"))
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(), "aprovada", pasta)), [], tmp_path, None)
    assert (lista.revisao_atual, lista.pdf_atual.name, lista.pdf_em_uso.name, lista.falta) == (
        "0B", cr.nome_do_pdf(CODIGO, "0B"), cr.nome_do_pdf(CODIGO, "0A"), "")


def test_lista_sem_revisao_em_uso_nao_exige_esse_pdf(tmp_path):
    lista = _uma_lista(tmp_path, em_uso="", ultima="0")
    assert (lista.pdf_em_uso, lista.falta) == (None, "")


def test_o_que_falta_aparece_e_a_ordem_e_a_das_categorias(tmp_path):
    outro = "#ST00=X01MPB020&MPB020"
    pasta_ok = _pasta(tmp_path, outro, pdfs=("0A", "0B"))
    pasta_sem = _pasta(tmp_path, pdfs=("0A",))
    pasta_sem_status = _pasta(tmp_path / "s", "#ZZ00=1&MPB020", pdfs=("0A", "0B"), com_status=False)
    listas = ra.listas_para_amp(_conferencia(
        cr.ItemConferencia(_lista(outro, status_real="Em Processo"), "em_processo", pasta_ok),
        cr.ItemConferencia(_lista(), "aprovada", pasta_sem),
        cr.ItemConferencia(_lista("#ZZ00=1&MPB020"), "outros", pasta_sem_status)), [], tmp_path, None)
    assert [(lst.item.lista.codigo, lst.falta) for lst in listas] == [
        (CODIGO, "falta: PDF da revisão atual"),
        (outro, ""),
        ("#ZZ00=1&MPB020", "falta: _STATUS_PMIB"),
    ]


def test_lista_sem_pasta_fica_de_fora(tmp_path):
    item = cr.ItemConferencia(_lista(), "outros", None, cr.MOTIVO_SEM_PASTA)
    assert ra.listas_para_amp(_conferencia(item), [], tmp_path, None) == []


# ------------------------------------------------------------------ a mensagem e o pedido

def test_mensagem_tem_a_lista_as_revisoes_os_arquivos_e_a_data(tmp_path):
    lista = _uma_lista(tmp_path)
    assert ra.mensagem_da_lista(lista, hoje=HOJE) == (
        f"Lista: {CODIGO}. Revisão em uso: 0A (arquivo {cr.nome_do_pdf(CODIGO, '0A')}). "
        f"Revisão atual: 0B (arquivo {cr.nome_do_pdf(CODIGO, '0B')}). "
        f"Controle: {CODIGO}_STATUS_PMIB.xlsx. Data de hoje: 03/11/2026. Faça a revisão.")


def test_mensagem_sem_revisao_em_uso(tmp_path):
    mensagem = ra.mensagem_da_lista(_uma_lista(tmp_path, em_uso="", ultima="0"), hoje=HOJE)
    assert ("Revisão em uso: nenhuma (a lista ainda não tem revisão em uso: compare só a revisão atual "
            "com o controle).") in mensagem
    assert f"Revisão atual: 0 (arquivo {cr.nome_do_pdf(CODIGO, '0')})." in mensagem


def test_pedido_leva_os_arquivos_como_estao_e_a_mensagem(tmp_path):
    lista = _uma_lista(tmp_path)
    pedido = ra.montar_pedido(lista, hoje=HOJE)
    assert pedido.campos == {"modo": "revisar", "mensagem": ra.mensagem_da_lista(lista, hoje=HOJE)}
    assert pedido.arquivos == {"revisao_em_uso": lista.pdf_em_uso, "revisao_atual": lista.pdf_atual,
                               "status_pmib": lista.status_pmib}
    assert list(pedido.arquivos) == ["revisao_em_uso", "revisao_atual", "status_pmib"]


def test_pedido_sem_revisao_em_uso_vai_com_dois_arquivos(tmp_path):
    pedido = ra.montar_pedido(_uma_lista(tmp_path, em_uso="", ultima="0"), hoje=HOJE)
    assert list(pedido.arquivos) == ["revisao_atual", "status_pmib"]


def test_o_sigft_nao_le_mais_o_conteudo():
    for nome in ("texto_do_pdf", "status_pmib_em_tsv", "TextoPdf", "TabelaStatus", "codigos_para_eco"):
        assert not hasattr(ra, nome), nome
```

- [ ] **Step 2: Reescrever `tests/test_revisao_amp_rodada.py`**

```python
"""A rodada da revisão no AMP: o ping antes, uma lista por vez, o log de cada uma (o que vai,
o que voltou, a execução do n8n e o batimento da espera), o HTML gravado sem sobrescrever, a
falha de uma lista que não para as outras e o diagnóstico que pode ir para o Claude na web: sem
conteúdo de documento e sem a chave. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.3, §5.4 e §5.6.
"""
from __future__ import annotations

import json
import time

from sigft.core import dados_usuario
from sigft.core.amp.cliente import RespostaAmp
from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

CODIGO = "#ITA0=Y01TF001&BPB020"
OUTRO = "#ST00=X01MPB020&MPB020"
URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CHAVE = "chave-que-nao-pode-aparecer"
DOCUMENTO = "CONTEUDO_DO_DOCUMENTO_QUE_NAO_PODE_SAIR"
HTML = f"<!doctype html><html><table><tr><td>{DOCUMENTO}</td></tr></table></html>"


def _lista(tmp_path, codigo=CODIGO, falta="", em_uso="0A"):
    pasta = tmp_path / codigo[-6:]
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in (("a.pdf", b"%PDF" + b"a" * 2044), ("b.pdf", b"%PDF"), ("s.xlsx", b"PK")):
        (pasta / nome).write_bytes(conteudo)
    dados = cr.ListaNaMapeadora(codigo, "0B", "Em Processo", "Aprovado", em_uso, "x")
    return ra.ListaParaAmp(cr.ItemConferencia(dados, "aprovada", pasta), pasta / "s.xlsx",
                           pasta / "a.pdf" if em_uso else None, pasta / "b.pdf", "0B", falta)


def _ping_ok():
    return RespostaAmp(True, "ping", 200, 0.8, "{}", {"ok": True, "versao_workflow": "2026-11-03", "execucao": "100"})


class _Cliente:
    def __init__(self, *respostas, ping=None):
        self.respostas = list(respostas)
        self.envios = []
        self._ping = ping or _ping_ok()

    def ping(self):
        return self._ping

    def enviar(self, campos, arquivos):
        self.envios.append((dict(campos), dict(arquivos)))
        return self.respostas.pop(0)


def _ok(html=HTML, arquivos=None, execucao="101"):
    dados = {"ok": True, "modo": "revisar", "html": html, "execucao": execucao}
    if arquivos is not None:
        dados["arquivos"] = arquivos
    return RespostaAmp(True, "revisar", 200, 192.4, json.dumps(dados), dados)


def _falha(erro="model timeout", http=502, dados=None):
    dados = dados if dados is not None else {"ok": False, "modo": "revisar", "etapa": "agente", "erro": erro,
                                             "execucao": "77"}
    return RespostaAmp(False, "revisar", http, 47.2, json.dumps(dados), dados, erro)


def _rodar(listas, cliente, linhas=None, **kw):
    kw.setdefault("batimento", 0)
    log = linhas.append if linhas is not None else (lambda _m: None)
    return ra.revisar_listas(listas, cliente, versao_sigft="1.3.3-rc.1", url=URL, chave_posta=True, log_cb=log, **kw)


# ------------------------------------------------------------------ o HTML

def test_html_gravado_com_o_nome_do_padrao(tmp_path):
    lista = _lista(tmp_path)
    [resultado] = _rodar([lista], _Cliente(_ok("<html><table>OK</table></html>")))
    assert resultado.situacao == "pronto"
    assert resultado.html == lista.item.pasta / f"{CODIGO}[0A-0B] revisao AMP.html"
    assert resultado.html.read_text(encoding="utf-8") == "<html><table>OK</table></html>"


def test_nunca_sobrescreve(tmp_path):
    lista = _lista(tmp_path)
    existente = lista.item.pasta / f"{CODIGO}[0A-0B] revisao AMP.html"
    existente.write_text("antigo", encoding="utf-8")
    [resultado] = _rodar([lista], _Cliente(_ok()))
    assert resultado.html.name == f"{CODIGO}[0A-0B] revisao AMP (2).html"
    assert existente.read_text(encoding="utf-8") == "antigo"


def test_nome_do_html():
    assert ra.nome_do_html(CODIGO, "", "0") == f"{CODIGO}[-0] revisao AMP.html"
    assert ra.nome_do_html('A/B:C', "0", "1") == "A_B_C[0-1] revisao AMP.html"


# ------------------------------------------------------------------ o que vai e o que volta

def test_cada_lista_manda_a_mensagem_e_os_arquivos(tmp_path):
    lista = _lista(tmp_path)
    cliente = _Cliente(_ok())
    _rodar([lista], cliente)
    [(campos, arquivos)] = cliente.envios
    assert campos["modo"] == "revisar" and campos["mensagem"].endswith("Faça a revisão.")
    assert arquivos == {"revisao_em_uso": lista.pdf_em_uso, "revisao_atual": lista.pdf_atual,
                        "status_pmib": lista.status_pmib}


def test_falta_nao_chama(tmp_path):
    cliente = _Cliente()
    [resultado] = _rodar([_lista(tmp_path, falta="falta: PDF da revisão atual")], cliente)
    assert (resultado.situacao, resultado.detalhe) == ("falta", "falta: PDF da revisão atual")
    assert cliente.envios == []


def test_defeito_ao_montar_vira_falha_e_as_outras_seguem(tmp_path):
    def defeito(lista):
        if lista.item.lista.codigo == CODIGO:
            raise RuntimeError("defeito do SIG-FT")
        return ra.montar_pedido(lista)

    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], _Cliente(_ok()), montar=defeito)
    assert [r.situacao for r in resultados] == ["falhou", "pronto"]
    assert "RuntimeError: defeito do SIG-FT" in resultados[0].diagnostico


def test_ping_falho_nao_manda_nada(tmp_path):
    falho = RespostaAmp(False, "ping", 403, 0.2, "", {}, "o AMP recusou a chave (HTTP 403)")
    cliente = _Cliente(ping=falho)
    linhas = []
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], cliente, linhas)
    assert [r.situacao for r in resultados] == ["falhou", "falhou"]
    assert resultados[0].detalhe == "o ping falhou: o AMP recusou a chave (HTTP 403)"
    assert resultados[0].diagnostico and resultados[1].diagnostico == ""
    assert cliente.envios == []
    assert "FALHOU  Ping: o AMP recusou a chave (HTTP 403)" in linhas


def test_falha_de_rede_numa_lista_e_as_outras_seguem(tmp_path):
    rede = RespostaAmp(False, "revisar", None, 30.0, "", {}, "Sem conexão com o AMP: nenhuma rota respondeu")
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], _Cliente(rede, _ok()))
    assert [r.situacao for r in resultados] == ["falhou", "pronto"]
    assert "Sem conexão com o AMP: nenhuma rota respondeu" in resultados[0].diagnostico


def test_sem_html_e_falha(tmp_path):
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_ok(html="Não consegui ler.")))
    assert (resultado.situacao, resultado.detalhe) == ("falhou", "o agente não devolveu HTML")


def test_workflow_que_recebeu_menos_arquivos_e_falha(tmp_path):
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_ok(arquivos=["b.pdf"])))
    assert (resultado.situacao, resultado.detalhe) == ("falhou", "o workflow recebeu 1 de 3 arquivo(s)")


# ------------------------------------------------------------------ o log

def test_o_log_diz_o_que_vai_e_o_que_voltou(tmp_path):
    linhas = []
    _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO, falta="falta: PDF da revisão atual")],
           _Cliente(_ok(arquivos=["a.pdf", "b.pdf", "s.xlsx"])), linhas, desmarcadas=["#AAA"], com_falta=["#DDD"])
    assert linhas[:4] == ["Revisão no AMP: 2 lista(s) marcada(s)", "  desmarcadas, ficam fora: 1 (#AAA)",
                          "  com falta, ficam fora: 1 (#DDD)", f"Webhook: {URL} · chave posta"]
    assert "Ping: workflow 2026-11-03 (0,8 s, execução 100)" in linhas
    assert f"[1/2] {CODIGO} · em uso 0A → atual 0B" in linhas
    assert "    vai: a.pdf (2 KB), b.pdf (4 B), s.xlsx (2 B)" in linhas
    assert "    enviado; o agente está lendo (costuma levar alguns minutos)" in linhas
    assert "    resposta: HTTP 200 em 3:12 · execução 101 · o workflow recebeu 3 arquivo(s)" in linhas
    assert any(linha.startswith(f"    ✓ HTML gravado: {CODIGO}[0A-0B] revisao AMP.html (") for linha in linhas)
    assert f"[2/2] {OUTRO} · em uso 0A → atual 0B" in linhas
    assert "    - falta: PDF da revisão atual" in linhas
    assert linhas[-1].startswith("Fim: 1 HTML pronto(s), 0 falha(s), 1 com falta, 0 parada(s), em 0:0")
    texto = "\n".join(linhas)
    assert DOCUMENTO not in texto and CHAVE not in texto


def test_falha_no_log_traz_o_http_a_etapa_e_a_execucao(tmp_path):
    linhas = []
    _rodar([_lista(tmp_path)], _Cliente(_falha()), linhas, gravar_diagnostico=False)
    assert "    resposta: HTTP 502 em 47,2 s · execução 77" in linhas
    assert "    ✗ falhou: model timeout (etapa agente)" in linhas


def test_lista_sem_revisao_em_uso_no_log(tmp_path):
    linhas = []
    _rodar([_lista(tmp_path, em_uso="")], _Cliente(_ok()), linhas)
    assert f"[1/1] {CODIGO} · sem revisão em uso → atual 0B" in linhas
    assert "    vai: b.pdf (4 B), s.xlsx (2 B)" in linhas


def test_a_espera_tem_batimento(tmp_path):
    class _Lento(_Cliente):
        def enviar(self, campos, arquivos):
            time.sleep(0.25)
            return super().enviar(campos, arquivos)

    linhas = []
    _rodar([_lista(tmp_path)], _Lento(_ok()), linhas, batimento=0.05)
    batidas = [linha for linha in linhas if linha.endswith("esperando o AMP")]
    assert len(batidas) >= 2 and batidas[0] == "    … 0:00 esperando o AMP"
    # O batimento para quando a resposta chega: nada dele depois da linha da resposta.
    resposta = next(i for i, linha in enumerate(linhas) if linha.startswith("    resposta:"))
    assert not any(linha.endswith("esperando o AMP") for linha in linhas[resposta:])


# ------------------------------------------------------------------ o diagnóstico

def test_diagnostico_sem_documento_e_sem_chave(tmp_path):
    dados = {"ok": False, "modo": "revisar", "html": f"Não consegui: {DOCUMENTO}", "execucao": "77",
             "erro": "o agente não devolveu HTML"}
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_falha("o agente não devolveu HTML", 200, dados)))
    texto = resultado.diagnostico
    assert DOCUMENTO not in texto and CHAVE not in texto
    assert "SIG-FT · Revisão no AMP · diagnóstico" in texto
    assert "1.3.3-rc.1" in texto and CODIGO in texto and URL in texto and "chave: posta" in texto
    assert "  revisao_em_uso: a.pdf, 2 KB" in texto
    assert "  revisao_atual: b.pdf, 4 B" in texto and "  status_pmib: s.xlsx, 2 B" in texto
    assert "  mensagem: " in texto and " caracteres" in texto
    assert "HTTP 200" in texto and "execução do n8n: 77" in texto
    assert "o agente não devolveu HTML" in texto
    assert "amp/revisao_de_listas/agente.md" in texto


def test_erro_longo_vai_cortado(tmp_path):
    erro = "Could not parse output: " + "y" * 1000
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_falha(erro)))
    assert "Could not parse output" in resultado.diagnostico
    assert "y" * 400 not in resultado.diagnostico


def test_corpo_que_nao_e_json_aparece_cortado(tmp_path):
    pagina = "<html>login do proxy</html>" + "x" * 5000
    resposta = RespostaAmp(False, "revisar", 200, 1.0, pagina, {}, "o AMP não respondeu JSON (HTTP 200)")
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(resposta))
    assert "login do proxy" in resultado.diagnostico
    assert "x" * 1501 not in resultado.diagnostico


def test_diagnostico_vai_para_a_pasta_de_logs(tmp_path):
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_falha()))
    arquivos = list((dados_usuario.pasta_logs() / "amp").glob("*.txt"))
    assert len(arquivos) == 1
    assert arquivos[0].read_text(encoding="utf-8") == resultado.diagnostico


# ------------------------------------------------------------------ o ritmo

def test_cancelar_entre_as_listas(tmp_path):
    pedidos = iter([False, True])
    cliente = _Cliente(_ok())
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], cliente, cancelado_cb=lambda: next(pedidos))
    assert [r.situacao for r in resultados] == ["pronto", "parado"]
    assert len(cliente.envios) == 1


def test_cada_resultado_sai_antes_da_proxima_lista(tmp_path):
    # A tela mostra cada lista quando ela volta: são até 15 minutos por lista.
    vistos, ja_vistos_na_chamada = [], []
    cliente = _Cliente(_ok(), _falha())
    enviar = cliente.enviar

    def espiar(campos, arquivos):
        ja_vistos_na_chamada.append(len(vistos))
        return enviar(campos, arquivos)

    cliente.enviar = espiar
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], cliente, resultado_cb=vistos.append,
                        gravar_diagnostico=False)
    assert vistos == resultados and ja_vistos_na_chamada == [0, 1]


def test_diagnosticos_para_copiar_juntam_so_as_falhas(tmp_path):
    terceira = _lista(tmp_path / "c", "#ST00=Z01MPB020&MPB020")
    resultados = _rodar([_lista(tmp_path), terceira, _lista(tmp_path, OUTRO)],
                        _Cliente(_falha("model timeout"), _ok(), _falha("o AMP recusou a chave (HTTP 403)")),
                        gravar_diagnostico=False)
    texto = ra.diagnosticos_para_copiar(resultados)
    assert texto.startswith("SIG-FT · Revisão no AMP: 2 lista(s) falharam nesta rodada.")
    assert "conversa nova com o Claude" in texto and "luanccozer/SIG-FT" in texto
    assert texto.index(resultados[0].diagnostico) < texto.index(resultados[2].diagnostico)
    assert ra.diagnosticos_para_copiar([resultados[1]]) == ""


# ------------------------------------------------------------------ o teste de conexão

def test_testar_conexao_ok():
    assert ra.testar_conexao(_Cliente()) == ["OK      Ping: workflow 2026-11-03 (HTTP 200, 0,8 s, execução 100)"]


def test_testar_conexao_falha():
    falho = RespostaAmp(False, "ping", 403, 0.2, "", {}, "o AMP recusou a chave (HTTP 403)")
    assert ra.testar_conexao(_Cliente(ping=falho)) == ["FALHOU  Ping: o AMP recusou a chave (HTTP 403) (0,2 s)"]
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `python -m pytest tests/test_revisao_amp_pedido.py tests/test_revisao_amp_rodada.py -q`
Expected: FAIL (`mensagem_da_lista` não existe; `revisar_listas` chama `cliente.revisar`).

- [ ] **Step 4: Reescrever o serviço**

Substitua `sigft/services/revisao_amp.py` por:

```python
"""A revisão das listas pelo AMP: o pedido de cada lista com divergência (os arquivos como estão
e a mensagem) e a rodada, uma lista por vez, no workflow do n8n da GE (`amp/revisao_de_listas/`).

Desde 2026-11-03 o agente (o "Spare Parts Document Reviewer", criado no AMP) recebe os dois PDFs
e o `_STATUS_PMIB` como estão, como o Luan fazia no chat do AMP: o SIG-FT não lê mais o conteúdo
deles. A rodada escreve no log o que vai e o que voltou de cada lista, com o número da execução do
n8n, e um batimento enquanto o agente trabalha (o Luan, em 03/11: "precisamos ver o que está
acontecendo"). Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`.
"""
from __future__ import annotations

import json
import re
import textwrap
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from sigft.core import dados_usuario
from sigft.core.aconex.status_real import revisoes_iguais
from sigft.core.amp.cliente import RespostaAmp
from sigft.services.conferencia_revisoes import (
    Conferencia,
    Download,
    ItemConferencia,
    nome_do_pdf,
    resolver_status_pmib,
)

CORPO_NO_DIAGNOSTICO = 1500   # caracteres do corpo da resposta que o diagnóstico mostra
ERRO_NO_DIAGNOSTICO = 300     # o erro do workflow, cortado: ele pode repetir a saída do agente
BATIMENTO = 30.0              # segundos entre as linhas de "esperando o AMP"
CAMPOS_DO_WORKFLOW = ("ok", "modo", "etapa", "erro", "execucao", "versao_workflow", "arquivos")
CAMPO_EM_USO, CAMPO_ATUAL, CAMPO_STATUS = "revisao_em_uso", "revisao_atual", "status_pmib"
ARQUIVOS_DO_REPOSITORIO = (
    ("sigft/services/revisao_amp.py", "a rodada, o pedido e este diagnóstico"),
    ("sigft/core/amp/cliente.py", "a chamada ao webhook"),
    ("amp/revisao_de_listas/agente.md", "o agente no AMP (cópia do goal e do system prompt)"),
    ("amp/revisao_de_listas/workflow_revisao_de_listas.json", "o workflow do n8n (gerado por gerar_workflow.py)"),
    ("docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md", "o desenho"),
)
_RESERVADOS = re.compile(r'[<>:"/\\|?*]')   # os mesmos de conferencia_revisoes.nome_do_pdf
_TEM_HTML = re.compile(r"<html|<table", re.IGNORECASE)


@dataclass(frozen=True)
class ListaParaAmp:
    item: ItemConferencia
    status_pmib: Path | None
    pdf_em_uso: Path | None
    pdf_atual: Path | None
    revisao_atual: str
    falta: str = ""


@dataclass(frozen=True)
class PedidoAmp:
    """O que vai ao workflow: os campos do formulário (`modo` e `mensagem`) e os arquivos, por
    campo: `revisao_em_uso` (só quando a lista tem revisão em uso), `revisao_atual` e
    `status_pmib`."""
    campos: dict[str, str]
    arquivos: dict[str, Path]


@dataclass(frozen=True)
class ResultadoAmp:
    lista: ListaParaAmp
    situacao: Literal["pronto", "falhou", "falta", "parado"]
    html: Path | None
    detalhe: str
    diagnostico: str = ""   # só na falha: o texto para colar numa conversa nova


def _mm_ss(segundos: float) -> str:
    inteiro = int(segundos)
    return f"{inteiro // 60}:{inteiro % 60:02d}"


def _duracao(segundos: float) -> str:
    """`0,8 s` abaixo de um minuto; `3:12` daí para cima."""
    return f"{segundos:.1f} s".replace(".", ",") if segundos < 60 else _mm_ss(segundos)


def _tamanho(caminho: Path) -> str:
    """`412 KB`, `1,8 MB`; o arquivo que não se lê diz isso."""
    try:
        bytes_ = caminho.stat().st_size
    except OSError:
        return "tamanho não lido"
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{round(bytes_ / 1024)} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB".replace(".", ",")


def _curto(texto, limite: int) -> str:
    texto = str(texto or "")
    return texto if len(texto) <= limite else f"{texto[:limite]}… (+{len(texto) - limite} caracteres)"


def _existe(caminho: Path) -> Path | None:
    return caminho if caminho.is_file() else None


def listas_para_amp(conferencia: Conferencia, downloads: list[Download], pasta_mapeadora: Path,
                    pasta_raiz: Path | None) -> list[ListaParaAmp]:
    # (copiar sem mudança a função atual, docstring incluída)
    ...


def mensagem_da_lista(lista: ListaParaAmp, *, hoje: date | None = None) -> str:
    """A mensagem que o agente recebe com os arquivos: a lista, as revisões, o nome de cada
    arquivo e a data de hoje (a linha de revisão nova leva a DATA DE ALTERAÇÃO, e o agente não
    sabe que dia é). É o texto do teste de 03/11 (§5.2 do desenho)."""
    dados = lista.item.lista
    if lista.pdf_em_uso is not None:
        em_uso = f"Revisão em uso: {dados.revisao_em_uso} (arquivo {lista.pdf_em_uso.name})."
    else:
        em_uso = ("Revisão em uso: nenhuma (a lista ainda não tem revisão em uso: compare só a revisão "
                  "atual com o controle).")
    return (f"Lista: {dados.codigo}. {em_uso} Revisão atual: {lista.revisao_atual} "
            f"(arquivo {lista.pdf_atual.name}). Controle: {lista.status_pmib.name}. "
            f"Data de hoje: {(hoje or date.today()):%d/%m/%Y}. Faça a revisão.")


def montar_pedido(lista: ListaParaAmp, *, hoje: date | None = None) -> PedidoAmp:
    """Os arquivos como estão na pasta da lista e a mensagem. Nada é lido dos arquivos."""
    arquivos: dict[str, Path] = {}
    if lista.pdf_em_uso is not None:
        arquivos[CAMPO_EM_USO] = lista.pdf_em_uso
    arquivos[CAMPO_ATUAL] = lista.pdf_atual
    arquivos[CAMPO_STATUS] = lista.status_pmib
    return PedidoAmp({"modo": "revisar", "mensagem": mensagem_da_lista(lista, hoje=hoje)}, arquivos)


def nome_do_html(codigo: str, em_uso: str, atual: str) -> str:
    # (copiar sem mudança)
    ...


def gravar_html(pasta: Path, nome: str, html: str) -> Path:
    # (copiar sem mudança)
    ...


# ------------------------------------------------------------------ o diagnóstico

def _corpo(resposta: RespostaAmp) -> str:
    """Do JSON do workflow, só os campos dele (o `erro` cortado): o `html` pode repetir o
    documento, e dele vai o tamanho. De outra coisa (a página de um proxy), o texto como veio."""
    try:
        dados = json.loads(resposta.corpo)
    except ValueError:
        dados = None
    if not isinstance(dados, dict):
        return resposta.corpo

    def campo(chave, valor):
        if chave not in CAMPOS_DO_WORKFLOW:
            return f"<{len(str(valor))} caracteres, fora daqui>"
        return _curto(valor, ERRO_NO_DIAGNOSTICO) if chave == "erro" else valor

    return json.dumps({chave: campo(chave, valor) for chave, valor in dados.items()}, ensure_ascii=False)


def _numeros_do_pedido(pedido: PedidoAmp | None) -> list[str]:
    if pedido is None:
        return ["  nada: o pedido não chegou a ser montado"]
    linhas = [f"  {campo}: {caminho.name}, {_tamanho(caminho)}" for campo, caminho in pedido.arquivos.items()]
    linhas.append(f"  mensagem: {len(pedido.campos.get('mensagem', ''))} caracteres")
    return linhas


def _numeros_da_resposta(resposta: RespostaAmp | None) -> list[str]:
    if resposta is None:
        return ["  nenhuma: a lista não chegou a ser mandada"]
    http = f"HTTP {resposta.http}" if resposta.http is not None else "sem resposta HTTP"
    linhas = [f"  {http} em {_duracao(resposta.segundos)}"]
    if resposta.execucao:
        linhas.append(f"  execução do n8n: {resposta.execucao}")
    if resposta.arquivos:
        linhas.append(f"  arquivos que chegaram ao agente: {', '.join(resposta.arquivos)}")
    if resposta.erro:
        linhas.append(f"  erro: {_curto(resposta.erro, ERRO_NO_DIAGNOSTICO)}")
    corpo = _corpo(resposta)[:CORPO_NO_DIAGNOSTICO]
    linhas.append(f"  corpo (até {CORPO_NO_DIAGNOSTICO} caracteres):")
    linhas.append(textwrap.indent(corpo, "    ") if corpo.strip() else "    (vazio)")
    return linhas


def diagnostico(lista: ListaParaAmp, pedido: PedidoAmp | None, resposta: RespostaAmp | None, *, url: str,
                chave_posta: bool, versao_sigft: str, erro: str = "") -> str:
    """O texto para colar numa conversa nova (o Claude na web, no PC da GE, com o repositório do
    SIG-FT), §5.4 do desenho: do que foi mandado, os nomes e os tamanhos; da resposta, o corpo
    cortado e só os campos do workflow; o endereço, sem a chave. Nunca vai conteúdo de documento."""
    dados = lista.item.lista
    linhas = [
        "SIG-FT · Revisão no AMP · diagnóstico",
        f"SIG-FT {versao_sigft} · {datetime.now():%d/%m/%Y %H:%M:%S}",
        "",
        f"Lista: {dados.codigo} ({lista.item.categoria})",
        f"  revisão em uso: {dados.revisao_em_uso or 'nenhuma'} · revisão atual: {lista.revisao_atual}",
        f"  STATUS REAL: {dados.status_real or '(vazio)'} · STATUS DA REVISÃO: {dados.status_da_revisao or '(vazio)'}",
        "",
        "Chamada",
        f"  endereço: {url or '(não configurado)'}",
        f"  chave: {'posta' if chave_posta else 'não posta'}",
        "",
        "O que foi mandado (os nomes e os tamanhos: o conteúdo dos documentos fica fora daqui)",
        *_numeros_do_pedido(pedido),
        "",
        "Resposta",
        *_numeros_da_resposta(resposta),
    ]
    if erro:
        linhas += ["", "Erro no SIG-FT", textwrap.indent(erro, "  ")]
    linhas += ["", "Onde está o código (repositório luanccozer/SIG-FT)",
               *(f"  {caminho}: {papel}" for caminho, papel in ARQUIVOS_DO_REPOSITORIO)]
    return "\n".join(linhas) + "\n"


# ------------------------------------------------------------------ a rodada

def _com_batimento(acao, log_cb, intervalo: float):
    """Roda `acao()` e, enquanto ela não volta, escreve uma linha a cada `intervalo` segundos:
    o agente leva minutos, e o console mudo parece travado (§5.6 do desenho)."""
    if not intervalo or intervalo <= 0:
        return acao()
    parar = threading.Event()
    inicio = time.monotonic()

    def bater() -> None:
        while not parar.wait(intervalo):
            log_cb(f"    … {_mm_ss(time.monotonic() - inicio)} esperando o AMP")

    fio = threading.Thread(target=bater, name="amp-batimento", daemon=True)
    fio.start()
    try:
        return acao()
    finally:
        parar.set()
        fio.join(timeout=2)


def _revisoes(lista: ListaParaAmp) -> str:
    em_uso = lista.item.lista.revisao_em_uso
    return (f"em uso {em_uso} → atual {lista.revisao_atual}" if em_uso
            else f"sem revisão em uso → atual {lista.revisao_atual}")


def _linha_da_resposta(resposta: RespostaAmp) -> str:
    http = f"HTTP {resposta.http}" if resposta.http is not None else "sem resposta HTTP"
    partes = [f"{http} em {_duracao(resposta.segundos)}"]
    if resposta.execucao:
        partes.append(f"execução {resposta.execucao}")
    if resposta.arquivos:
        partes.append(f"o workflow recebeu {len(resposta.arquivos)} arquivo(s)")
    return "    resposta: " + " · ".join(partes)


def _detalhe(resposta: RespostaAmp) -> str:
    etapa = resposta.dados.get("etapa")
    erro = resposta.erro or "falha sem mensagem"
    return f"{erro} (etapa {etapa})" if etapa else erro


def _falhou(lista: ListaParaAmp, pedido: PedidoAmp | None, resposta: RespostaAmp | None, detalhe: str, log_cb, *,
            erro: str = "", **contexto) -> ResultadoAmp:
    detalhe = detalhe or "falha sem mensagem"
    log_cb(f"    ✗ falhou: {detalhe}")
    return ResultadoAmp(lista, "falhou", None, detalhe, diagnostico(lista, pedido, resposta, erro=erro, **contexto))


def _revisar(lista: ListaParaAmp, cliente, montar, log_cb, batimento: float, **contexto) -> ResultadoAmp:
    dados = lista.item.lista
    if lista.falta:
        log_cb(f"    - {lista.falta}")
        return ResultadoAmp(lista, "falta", None, lista.falta)
    try:
        pedido = montar(lista)
    except Exception as erro:  # noqa: BLE001 -- defeito do SIG-FT: vira diagnóstico, e as outras seguem
        return _falhou(lista, None, None, f"ao montar o pedido: {type(erro).__name__}: {erro}", log_cb,
                       erro="".join(traceback.format_exception(erro)).rstrip(), **contexto)
    log_cb("    vai: " + ", ".join(f"{caminho.name} ({_tamanho(caminho)})" for caminho in pedido.arquivos.values()))
    log_cb("    enviado; o agente está lendo (costuma levar alguns minutos)")
    resposta = _com_batimento(lambda: cliente.enviar(pedido.campos, pedido.arquivos), log_cb, batimento)
    log_cb(_linha_da_resposta(resposta))
    if not resposta.ok:
        return _falhou(lista, pedido, resposta, _detalhe(resposta), log_cb, **contexto)
    if not _TEM_HTML.search(resposta.html):
        return _falhou(lista, pedido, resposta, "o agente não devolveu HTML", log_cb, **contexto)
    if resposta.arquivos and len(resposta.arquivos) < len(pedido.arquivos):
        return _falhou(lista, pedido, resposta,
                       f"o workflow recebeu {len(resposta.arquivos)} de {len(pedido.arquivos)} arquivo(s)",
                       log_cb, **contexto)
    nome = nome_do_html(dados.codigo, dados.revisao_em_uso, lista.revisao_atual)
    try:
        caminho = gravar_html(lista.item.pasta, nome, resposta.html)
    except OSError as erro:
        return _falhou(lista, pedido, resposta, f"o HTML não foi gravado: {erro}", log_cb,
                       erro=f"o HTML não foi gravado: {erro}", **contexto)
    log_cb(f"    ✓ HTML gravado: {caminho.name} ({_tamanho(caminho)})")
    return ResultadoAmp(lista, "pronto", caminho, caminho.name)


def _gravar_diagnostico(resultado: ResultadoAmp, log_cb) -> None:
    # (copiar sem mudança)
    ...


def _cabecalho(listas, desmarcadas: list[str], com_falta: list[str], url: str, chave_posta: bool) -> list[str]:
    linhas = [f"Revisão no AMP: {len(listas)} lista(s) marcada(s)"]
    if desmarcadas:
        linhas.append(f"  desmarcadas, ficam fora: {len(desmarcadas)} ({', '.join(desmarcadas)})")
    if com_falta:
        linhas.append(f"  com falta, ficam fora: {len(com_falta)} ({', '.join(com_falta)})")
    linhas.append(f"Webhook: {url or '(não configurado)'} · chave {'posta' if chave_posta else 'não posta'}")
    return linhas


def _ping_falhou(listas, ping: RespostaAmp, log_cb, resultado_cb, gravar_diagnostico: bool,
                 **contexto) -> list[ResultadoAmp]:
    """Sem ping, nada vai: cada lista volta "falhou" com o motivo, e o diagnóstico vai só na
    primeira (são todos iguais)."""
    log_cb(f"FALHOU  Ping: {ping.erro}")
    log_cb("Nada foi mandado: confira o webhook (botão Webhook…) e o Testar conexão.")
    resultados = []
    for n, lista in enumerate(listas):
        texto = diagnostico(lista, None, ping, **contexto) if n == 0 else ""
        resultado = ResultadoAmp(lista, "falhou", None, f"o ping falhou: {ping.erro}", texto)
        if texto and gravar_diagnostico:
            _gravar_diagnostico(resultado, log_cb)
        resultados.append(resultado)
        if resultado_cb is not None:
            resultado_cb(resultado)
    return resultados


def revisar_listas(listas: list[ListaParaAmp], cliente, *, versao_sigft: str, url: str, chave_posta: bool, log_cb,
                   progress_cb=None, cancelado_cb=None, resultado_cb=None, gravar_diagnostico: bool = True,
                   montar=montar_pedido, desmarcadas=(), com_falta=(), batimento: float = BATIMENTO
                   ) -> list[ResultadoAmp]:
    """Uma lista por vez (§5 do desenho). Antes, o `ping`: falhando, nada é mandado. A lista com
    falta não é chamada; a falha de uma não para as outras e deixa o diagnóstico em
    `logs\\amp\\`; `cancelado_cb()` é lido entre as listas, e as que sobram ficam "parado".
    `resultado_cb(resultado)` recebe cada lista assim que ela acaba. `desmarcadas` e `com_falta`
    (os códigos que ficaram fora) só vão para o começo do log."""
    contexto = {"versao_sigft": versao_sigft, "url": url, "chave_posta": chave_posta}
    inicio = time.monotonic()
    for linha in _cabecalho(listas, list(desmarcadas), list(com_falta), url, chave_posta):
        log_cb(linha)
    ping = cliente.ping()
    if not ping.ok:
        resultados = _ping_falhou(listas, ping, log_cb, resultado_cb, gravar_diagnostico, **contexto)
        if progress_cb:
            progress_cb(1.0)
        return resultados
    log_cb(f"Ping: workflow {ping.versao_workflow or '(sem versão)'} ({_duracao(ping.segundos)}, "
           f"execução {ping.execucao or '?'})")
    resultados: list[ResultadoAmp] = []
    parado = False
    for n, lista in enumerate(listas):
        if not parado and cancelado_cb is not None and cancelado_cb():
            parado = True
            log_cb("Revisão no AMP parada pelo usuário.")
        if parado:
            resultado = ResultadoAmp(lista, "parado", None, "parado antes de ir ao AMP")
        else:
            if progress_cb:
                progress_cb(min(0.05 + n / len(listas) * 0.9, 0.95))
            log_cb(f"[{n + 1}/{len(listas)}] {lista.item.lista.codigo} · {_revisoes(lista)}")
            resultado = _revisar(lista, cliente, montar, log_cb, batimento, **contexto)
            if resultado.diagnostico and gravar_diagnostico:
                _gravar_diagnostico(resultado, log_cb)
        resultados.append(resultado)
        if resultado_cb is not None:
            resultado_cb(resultado)
    if progress_cb:
        progress_cb(1.0)
    contagem = {s: sum(r.situacao == s for r in resultados) for s in ("pronto", "falhou", "falta", "parado")}
    log_cb(f"Fim: {contagem['pronto']} HTML pronto(s), {contagem['falhou']} falha(s), {contagem['falta']} com falta, "
           f"{contagem['parado']} parada(s), em {_mm_ss(time.monotonic() - inicio)}")
    return resultados


def diagnosticos_para_copiar(resultados: list[ResultadoAmp]) -> str:
    # (copiar sem mudança)
    ...


def _linha(marca: str, nome: str, detalhe: str) -> str:
    """No formato do diagnóstico do Aconex: `OK      Ping: workflow 2026-11-03`."""
    return f"{marca:<8}{nome}: {detalhe}"


def testar_conexao(cliente) -> list[str]:
    """As linhas do "Testar conexão com o AMP": o `ping` vê a rede, a chave e o workflow
    publicado, sem chamar o agente e sem mandar documento."""
    ping = cliente.ping()
    if not ping.ok:
        return [_linha("FALHOU", "Ping", f"{ping.erro} ({_duracao(ping.segundos)})")]
    http = f"HTTP {ping.http}" if ping.http is not None else "sem resposta HTTP"
    return [_linha("OK", "Ping", f"workflow {ping.versao_workflow or '(sem versão)'} "
                                 f"({http}, {_duracao(ping.segundos)}, execução {ping.execucao or '?'})")]
```

Onde o bloco diz "copiar sem mudança", copie o corpo atual da função, inteiro, do arquivo de hoje:
`listas_para_amp`, `nome_do_html`, `gravar_html`, `_gravar_diagnostico` e
`diagnosticos_para_copiar`. Não sobra `...` no arquivo final.

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_revisao_amp_pedido.py tests/test_revisao_amp_rodada.py -q`
Expected: PASS.

- [ ] **Step 6: Suíte, ruff e commit**

Run: `bash scripts/check.sh && python -m ruff check .`
Expected: verde. O `tests/test_qt_tela_revisao_amp.py` continua verde, porque troca o serviço por
dublês.

```bash
git add sigft/services/revisao_amp.py tests/test_revisao_amp_pedido.py tests/test_revisao_amp_rodada.py
git commit -m "Revisao no AMP: manda os arquivos e a mensagem, com log de cada passo"
```

---

### Task 3: O webhook dentro do módulo

**Files:**
- Create: `sigft/app_qt/widgets/webhook_amp.py`
- Create: `tests/test_qt_webhook_amp.py`
- Modify: `sigft/config.py:538-542` (`ENV_VAR_POR_CHAVE`)
- Modify: `sigft/app_qt/views/home.py:91-93` (`CHAVES_API`)
- Modify: `tests/test_config.py` (os nomes do AMP), `tests/test_qt_home_paineis.py:180` e
  `tests/test_textos_da_interface.py` (`CONVERTIDOS`)
- Modify: `sigft/app/idiomas/es.json` e `en.json`

**Interfaces:**
- Produces:
  - `ChavesDoWebhook(url: str, chave: str, antigas: tuple[str, str] | None = None)`;
  - `ler(controller, chaves) -> tuple[str, str]`;
  - `gravar(controller, chaves, url: str, chave: str) -> None`;
  - `problema_do_endereco(url: str) -> str`;
  - `JanelaDoWebhook(parent, *, titulo: str, url: str = "", chave: str = "")`, com os atributos
    `campo_url`, `campo_chave`, `lbl_problema`, `botao_salvar` e `botao_cancelar`, e o método
    `valores() -> tuple[str, str]`.

- [ ] **Step 1: Escrever `tests/test_qt_webhook_amp.py`**

```python
"""O webhook de um workflow do AMP dentro do módulo (`sigft/app_qt/widgets/webhook_amp.py`): os
nomes de cada módulo no `api_config.json`, a adoção dos nomes antigos e a janela que confere o
endereço. Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.5.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLineEdit

from sigft.app_qt.widgets import webhook_amp

URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CHAVES = webhook_amp.ChavesDoWebhook("AMP_REVISAO_LISTAS_URL", "AMP_REVISAO_LISTAS_CHAVE",
                                     antigas=("AMP_WEBHOOK_URL", "AMP_WEBHOOK_CHAVE"))


class _Controller:
    def __init__(self, **chaves):
        self.chaves = dict(chaves)
        self.gravadas = []

    def get_key(self, nome):
        return self.chaves.get(nome) or ""

    def save_keys(self, novas):
        self.gravadas.append(dict(novas))
        self.chaves.update(novas)


def test_le_os_nomes_do_modulo():
    controller = _Controller(AMP_REVISAO_LISTAS_URL=URL, AMP_REVISAO_LISTAS_CHAVE=" segredo ")
    assert webhook_amp.ler(controller, CHAVES) == (URL, "segredo")
    assert controller.gravadas == []


def test_adota_os_nomes_antigos_uma_vez():
    controller = _Controller(AMP_WEBHOOK_URL=URL, AMP_WEBHOOK_CHAVE="segredo")
    assert webhook_amp.ler(controller, CHAVES) == (URL, "segredo")
    assert controller.gravadas == [{"AMP_REVISAO_LISTAS_URL": URL, "AMP_REVISAO_LISTAS_CHAVE": "segredo"}]
    assert webhook_amp.ler(controller, CHAVES) == (URL, "segredo")
    assert len(controller.gravadas) == 1


def test_nada_configurado():
    assert webhook_amp.ler(_Controller(), CHAVES) == ("", "")
    assert webhook_amp.ler(None, CHAVES) == ("", "")


def test_gravar_tira_os_espacos():
    controller = _Controller()
    webhook_amp.gravar(controller, CHAVES, f" {URL} ", " segredo\n")
    assert controller.gravadas == [{"AMP_REVISAO_LISTAS_URL": URL, "AMP_REVISAO_LISTAS_CHAVE": "segredo"}]


def test_endereco_precisa_de_https_e_nao_pode_ser_o_de_teste():
    assert webhook_amp.problema_do_endereco(URL) == ""
    assert webhook_amp.problema_do_endereco("http://x/webhook/a") == "O endereço precisa começar por https://."
    assert webhook_amp.problema_do_endereco("") == "O endereço precisa começar por https://."
    assert "Production URL" in webhook_amp.problema_do_endereco("https://x/webhook-test/sigft-revisao-listas")


def test_janela_salva_os_valores(qt_interface, qtbot):
    janela = webhook_amp.JanelaDoWebhook(None, titulo="Webhook da Revisão no AMP")
    qtbot.addWidget(janela)
    assert janela.windowTitle() == "Webhook da Revisão no AMP"
    assert janela.campo_chave.echoMode() == QLineEdit.EchoMode.Password
    janela.campo_url.setText(f"  {URL} ")
    janela.campo_chave.setText(" segredo ")
    janela.botao_salvar.click()
    assert janela.result() == QDialog.DialogCode.Accepted
    assert janela.valores() == (URL, "segredo")


def test_janela_nao_salva_endereco_ruim(qt_interface, qtbot):
    janela = webhook_amp.JanelaDoWebhook(None, titulo="x", url="https://x/webhook-test/a", chave="s")
    qtbot.addWidget(janela)
    janela.botao_salvar.click()
    assert janela.result() != QDialog.DialogCode.Accepted
    assert "Production URL" in janela.lbl_problema.text()


def test_janela_comeca_com_o_que_ja_existe(qt_interface, qtbot):
    janela = webhook_amp.JanelaDoWebhook(None, titulo="x", url=URL, chave="segredo")
    qtbot.addWidget(janela)
    assert (janela.campo_url.text(), janela.campo_chave.text()) == (URL, "segredo")


def test_cancelar_nao_aceita(qt_interface, qtbot):
    janela = webhook_amp.JanelaDoWebhook(None, titulo="x", url=URL, chave="segredo")
    qtbot.addWidget(janela)
    janela.botao_cancelar.click()
    assert janela.result() == QDialog.DialogCode.Rejected
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_qt_webhook_amp.py -q`
Expected: FAIL (`ImportError: cannot import name 'webhook_amp'`).

- [ ] **Step 3: Criar `sigft/app_qt/widgets/webhook_amp.py`**

```python
"""O webhook de um workflow do AMP, dentro do módulo que o usa (2026-11-03).

Cada workflow do AMP (o n8n da GE) tem o seu endereço e a sua chave: a Revisão no AMP usa o da
revisão de listas, e os próximos módulos, os deles (o Luan, em 03/11). Os dois ficam no
`api_config.json` (`controller.get_key`/`save_keys`), com os nomes que o módulo escolhe
(`ChavesDoWebhook`). A janela mostra a chave mascarada e confere o endereço antes de salvar.
Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.5.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from sigft.app.idioma import marcar, t
from sigft.app_qt.widgets import blocos

EXPLICACAO = marcar("Cada workflow do AMP tem o seu endereço e a sua chave. Eles ficam neste computador, "
                    "em Documentos\\SIG-FT, e a chave nunca aparece no log.")
ROTULO_ENDERECO = marcar("Endereço (a Production URL do webhook no n8n):")
ROTULO_CHAVE = marcar("Chave (o valor da credencial X-SIGFT-Chave):")
ENDERECO_SEM_HTTPS = marcar("O endereço precisa começar por https://.")
ENDERECO_DE_TESTE = marcar("Esse é o endereço de teste (/webhook-test/), que só funciona com o n8n "
                           "escutando. Use a Production URL (/webhook/).")
TEXTO_SALVAR = marcar("Salvar")
TEXTO_CANCELAR = marcar("Cancelar")


@dataclass(frozen=True)
class ChavesDoWebhook:
    """Os nomes do endereço e da chave no `api_config.json`; `antigas`, os de antes, adotados
    uma vez (`ler`)."""
    url: str
    chave: str
    antigas: tuple[str, str] | None = None


def _valor(controller, nome: str) -> str:
    return (controller.get_key(nome) or "").strip()


def gravar(controller, chaves: ChavesDoWebhook, url: str, chave: str) -> None:
    controller.save_keys({chaves.url: url.strip(), chaves.chave: chave.strip()})


def ler(controller, chaves: ChavesDoWebhook) -> tuple[str, str]:
    """(endereço, chave). Com os nomes do módulo vazios e os antigos postos, adota os antigos e
    os grava nos nomes do módulo: na próxima leitura, eles já estão lá."""
    if controller is None:
        return "", ""
    url, chave = _valor(controller, chaves.url), _valor(controller, chaves.chave)
    if url or chave or not chaves.antigas:
        return url, chave
    url_antiga, chave_antiga = (_valor(controller, nome) for nome in chaves.antigas)
    if url_antiga or chave_antiga:
        gravar(controller, chaves, url_antiga, chave_antiga)
    return url_antiga, chave_antiga


def problema_do_endereco(url: str) -> str:
    """O que impede salvar o endereço (já traduzido), ou "" quando ele está bom."""
    url = url.strip()
    if not url.startswith("https://"):
        return t(ENDERECO_SEM_HTTPS)
    if "/webhook-test/" in url:
        return t(ENDERECO_DE_TESTE)
    return ""


class JanelaDoWebhook(QDialog):
    """Endereço e chave (mascarada), "Salvar" e "Cancelar". Não grava nada: quem abre lê
    `valores()` quando ela volta aceita."""

    def __init__(self, parent=None, *, titulo: str, url: str = "", chave: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(6)
        lay.addWidget(blocos.rotulo(t(EXPLICACAO), alinhar="esquerda", papel="legenda"))
        lay.addSpacing(8)
        lay.addWidget(blocos.rotulo(t(ROTULO_ENDERECO), alinhar="esquerda"))
        self.campo_url = QLineEdit(url)
        self.campo_url.setMinimumWidth(520)
        self.campo_url.returnPressed.connect(self._salvar)
        lay.addWidget(self.campo_url)
        lay.addWidget(blocos.rotulo(t(ROTULO_CHAVE), alinhar="esquerda"))
        self.campo_chave = QLineEdit(chave)
        self.campo_chave.setEchoMode(QLineEdit.EchoMode.Password)
        # O caractere da máscara é o asterisco, como nas chaves da Configuração.
        self.campo_chave.setStyleSheet("lineedit-password-character: 42;")
        self.campo_chave.returnPressed.connect(self._salvar)
        lay.addWidget(self.campo_chave)
        self.lbl_problema = blocos.rotulo("", alinhar="esquerda", papel="erro")
        lay.addWidget(self.lbl_problema)
        lay.addSpacing(10)
        botoes = QHBoxLayout()
        botoes.setSpacing(10)
        botoes.addStretch()
        self.botao_cancelar = blocos.botao(t(TEXTO_CANCELAR), variante="secundario", largura=120)
        self.botao_cancelar.clicked.connect(self.reject)
        self.botao_salvar = blocos.botao(t(TEXTO_SALVAR), variante="primario", largura=120, negrito=True)
        self.botao_salvar.clicked.connect(self._salvar)
        botoes.addWidget(self.botao_cancelar)
        botoes.addWidget(self.botao_salvar)
        lay.addLayout(botoes)
        self.campo_url.setFocus()

    def _salvar(self) -> None:
        problema = problema_do_endereco(self.campo_url.text())
        if problema:
            self.lbl_problema.setText(problema)
            return
        self.accept()

    def valores(self) -> tuple[str, str]:
        return self.campo_url.text().strip(), self.campo_chave.text().strip()
```

- [ ] **Step 4: Os nomes do webhook em `config.py`, e os campos que saem da Configuração**

Em `sigft/config.py`, troque o bloco final de `ENV_VAR_POR_CHAVE`:

```python
    # 2026-10-27: o webhook do workflow "Revisão das listas" no n8n da GE (o AMP),
    # `amp/revisao_de_listas/`. A chave vai no cabeçalho X-SIGFT-Chave, nunca no log.
    "AMP_WEBHOOK_URL": "SIGFT_AMP_WEBHOOK_URL",
    "AMP_WEBHOOK_CHAVE": "SIGFT_AMP_WEBHOOK_CHAVE",
```

por:

```python
    # 2026-11-03: o webhook do workflow "Revisão das listas" no n8n da GE (o AMP),
    # `amp/revisao_de_listas/`. Configura-se na própria aba (botão Webhook…): cada workflow
    # do AMP tem os seus nomes. A chave vai no cabeçalho X-SIGFT-Chave, nunca no log.
    "AMP_REVISAO_LISTAS_URL": "SIGFT_AMP_REVISAO_LISTAS_URL",
    "AMP_REVISAO_LISTAS_CHAVE": "SIGFT_AMP_REVISAO_LISTAS_CHAVE",
```

Em `tests/test_config.py`, troque os nomes em todo o arquivo:

```bash
sed -i 's/SIGFT_AMP_WEBHOOK_URL/SIGFT_AMP_REVISAO_LISTAS_URL/g; s/SIGFT_AMP_WEBHOOK_CHAVE/SIGFT_AMP_REVISAO_LISTAS_CHAVE/g; s/"AMP_WEBHOOK_URL"/"AMP_REVISAO_LISTAS_URL"/g; s/"AMP_WEBHOOK_CHAVE"/"AMP_REVISAO_LISTAS_CHAVE"/g; s/# 2026-10-27: o webhook do workflow "Revisão das listas" no n8n da GE (o AMP)./# 2026-11-03: o webhook do workflow "Revisão das listas", configurado na aba./' tests/test_config.py
```

Em `sigft/app_qt/views/home.py`, apague de `CHAVES_API` estas três linhas:

```python
    # [2026-10-27] O webhook da Revisão no AMP (aba do PMIB Manager).
    ("AMP_WEBHOOK_URL", marcar("AMP Webhook (URL):")),
    ("AMP_WEBHOOK_CHAVE", marcar("AMP Webhook (chave):")),
```

e ponha no lugar delas:

```python
    # [2026-11-03] O webhook da Revisão no AMP saiu daqui: cada workflow do AMP tem o seu,
    # configurado na própria aba (botão Webhook…, `widgets/webhook_amp.py`).
```

Em `tests/test_qt_home_paineis.py`, apague a linha
`("AMP_WEBHOOK_URL", "AMP Webhook (URL):"), ("AMP_WEBHOOK_CHAVE", "AMP Webhook (chave):"),` da
lista esperada de `CHAVES_API`.

Em `tests/test_textos_da_interface.py`, acrescente `"sigft/app_qt/widgets/webhook_amp.py",` à tupla
`CONVERTIDOS`, logo depois de `"sigft/app_qt/widgets/dialogs.py",`.

- [ ] **Step 5: As traduções**

Rode, da raiz do repositório:

```bash
python - <<'PY'
import importlib.util, json, pathlib
spec = importlib.util.spec_from_file_location("textos", "tools/textos_da_interface.py")
textos = importlib.util.module_from_spec(spec); spec.loader.exec_module(textos)
NOVAS = {
    "Cada workflow do AMP tem o seu endereço e a sua chave. Eles ficam neste computador, em Documentos\\SIG-FT, e a chave nunca aparece no log.": {
        "es": "Cada workflow del AMP tiene su dirección y su clave. Quedan en esta computadora, en Documentos\\SIG-FT, y la clave nunca aparece en el log.",
        "en": "Each AMP workflow has its own address and key. They stay on this computer, in Documentos\\SIG-FT, and the key never shows in the log."},
    "Endereço (a Production URL do webhook no n8n):": {
        "es": "Dirección (la Production URL del webhook en n8n):",
        "en": "Address (the webhook Production URL in n8n):"},
    "Chave (o valor da credencial X-SIGFT-Chave):": {
        "es": "Clave (el valor de la credencial X-SIGFT-Chave):",
        "en": "Key (the value of the X-SIGFT-Chave credential):"},
    "O endereço precisa começar por https://.": {
        "es": "La dirección debe empezar por https://.",
        "en": "The address must start with https://."},
    "Esse é o endereço de teste (/webhook-test/), que só funciona com o n8n escutando. Use a Production URL (/webhook/).": {
        "es": "Esa es la dirección de prueba (/webhook-test/), que solo funciona con n8n escuchando. Use la Production URL (/webhook/).",
        "en": "That is the test address (/webhook-test/), which only works while n8n is listening. Use the Production URL (/webhook/)."},
}
for codigo in ("es", "en"):
    caminho = pathlib.Path(f"sigft/app/idiomas/{codigo}.json")
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    for chave in textos.sobrando(codigo):
        dados.pop(chave)
    for chave, traducao in NOVAS.items():
        dados[chave] = traducao[codigo]
    caminho.write_text(json.dumps(dict(sorted(dados.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(codigo, "faltando:", textos.faltando(codigo))
PY
```

Expected: `es faltando: []` e `en faltando: []`. Os dois rótulos que saíram da Configuração
(`AMP Webhook (URL):` e `AMP Webhook (chave):`) estavam em `sobrando` e são apagados aqui.

- [ ] **Step 6: Rodar e ver passar**

Run: `python -m pytest tests/test_qt_webhook_amp.py tests/test_config.py tests/test_qt_home_paineis.py tests/test_textos_da_interface.py -q`
Expected: PASS.

- [ ] **Step 7: Suíte, ruff e commit**

Run: `bash scripts/check.sh && python -m ruff check .`

```bash
git add sigft/app_qt/widgets/webhook_amp.py tests/test_qt_webhook_amp.py sigft/config.py sigft/app_qt/views/home.py tests/test_config.py tests/test_qt_home_paineis.py tests/test_textos_da_interface.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json
git commit -m "Webhook do AMP dentro do modulo: janela, nomes por workflow e adocao dos antigos"
```

---

### Task 4: A aba Revisão no AMP: listas marcáveis, botão Webhook… e log em arquivo

**Files:**
- Modify: `sigft/app_qt/views/revisao_amp.py` (reescrever inteiro)
- Modify: `sigft/app/textos_dicas.py` (bloco `"ModuloRevisaoAmp"`)
- Modify: `sigft/app/como_funciona.py` (bloco `"PMIBManager.amp"`)
- Modify: `sigft/app/idiomas/es.json`, `en.json`
- Test: `tests/test_qt_tela_revisao_amp.py` (reescrever inteiro)

**Interfaces:**
- Consumes:
  - `revisao_amp_svc.listas_para_amp`;
  - `revisao_amp_svc.revisar_listas(..., desmarcadas=, com_falta=)`;
  - `revisao_amp_svc.testar_conexao(cliente)`;
  - `revisao_amp_svc.diagnosticos_para_copiar`;
  - `webhook_amp.ChavesDoWebhook`, `ler`, `gravar` e `JanelaDoWebhook`;
  - `log_execucao.LogDeExecucao(modulo, pasta=..., contexto=...)` e `.envolver(log)`, `.caminho`,
    `.fechar()`.
- Produces:
  - `ModuloRevisaoAmp.atualizar_listas()`;
  - `ModuloRevisaoAmp.marcadas() -> list[ListaParaAmp]`;
  - os botões `btn_amp`, `btn_testar_amp`, `btn_webhook`, `btn_copiar_diag`, `btn_parar`,
    `btn_marcar` e `btn_desmarcar`.

- [ ] **Step 1: Reescrever `tests/test_qt_tela_revisao_amp.py`**

```python
"""A aba "Revisão no AMP" do PMIB Manager (Qt): as listas marcáveis (todas marcadas; a que tem
falta, sem caixa), o webhook dentro da aba e o log em arquivo. O serviço e o cliente são dublês:
a rodada tem os testes dela em `test_revisao_amp_rodada.py`. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from sigft.app_qt.views import revisao_amp as tela_mod
from sigft.app_qt.views.conferencia_revisoes import UltimaConferencia
from sigft.core import dados_usuario
from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CHAVE = "segredo-do-webhook"
CODIGO = "#ITA0=Y01TF001&BPB020"
OUTRO = "#ST00=X01MPB020&MPB020"
TERCEIRO = "#ST00=Z01MPB020&MPB020"
TITULO = "Revisão no AMP"
AVISO_SEM_CHAVE = "Configure o endereço e a chave do webhook no botão Webhook…, nesta aba."
AVISO_TABELA_REFEITA = ("A conferência mudou: a tabela foi refeita com as listas dela. Confira as marcas e "
                        "clique em Revisar no AMP de novo.")


class _Controller:
    def __init__(self, url=URL, chave=CHAVE, **outras):
        self.chaves = {"AMP_REVISAO_LISTAS_URL": url, "AMP_REVISAO_LISTAS_CHAVE": chave, **outras}
        self.gravadas = []

    def get_key(self, nome):
        return self.chaves.get(nome) or ""

    def save_keys(self, novas):
        self.gravadas.append(dict(novas))
        self.chaves.update(novas)


class _ClienteAmp:
    def __init__(self, url, chave, **_kw):
        self.url, self.chave = url, chave


def _lista(tmp_path, codigo, falta=""):
    pasta = tmp_path / codigo[-6:]
    pasta.mkdir(parents=True, exist_ok=True)
    dados = cr.ListaNaMapeadora(codigo, "0B", "Em Processo", "Aprovado", "0A", "x")
    return ra.ListaParaAmp(cr.ItemConferencia(dados, "aprovada", pasta), pasta / "s.xlsx", pasta / "a.pdf",
                           pasta / "b.pdf", "0B", falta)


@pytest.fixture
def ultima(tmp_path):
    mapeadora = cr.Mapeadora(tmp_path / "mapa" / "Mapeamento.xlsx", datetime.now(), [])
    return UltimaConferencia(mapeadora, cr.Conferencia([], em_dia=0, sem_status_pmib=0), [], tmp_path / "raiz")


@pytest.fixture
def servico(monkeypatch, tmp_path):
    """Dublê do serviço: as listas, a rodada e o teste. Guarda o que a tela pediu."""
    falso = SimpleNamespace(listas=[_lista(tmp_path, CODIGO), _lista(tmp_path, OUTRO, "falta: PDF da revisão atual"),
                                    _lista(tmp_path, TERCEIRO)],
                            resultados=None, chamadas=[], testes=[], cancelado=None, rodada=None)

    def listas_para_amp(conferencia, downloads, pasta_mapeadora, pasta_raiz):
        falso.chamadas.append(("listas", pasta_mapeadora, pasta_raiz))
        return falso.listas

    def revisar_listas(listas, cliente, *, versao_sigft, url, chave_posta, log_cb, progress_cb=None,
                       cancelado_cb=None, resultado_cb=None, desmarcadas=(), com_falta=(), **_kw):
        falso.rodada = SimpleNamespace(listas=list(listas), desmarcadas=list(desmarcadas),
                                       com_falta=list(com_falta), url=cliente.url, chave=cliente.chave,
                                       chave_posta=chave_posta)
        falso.cancelado = cancelado_cb
        log_cb("linha da rodada")
        resultados = falso.resultados if falso.resultados is not None else [
            ra.ResultadoAmp(lista, "pronto", lista.item.pasta / "x.html", "x.html") for lista in listas]
        for resultado in resultados:
            resultado_cb(resultado)
        return list(resultados)

    def testar_conexao(cliente):
        falso.testes.append((cliente.url, cliente.chave))
        return ["OK      Ping: workflow 2026-11-03 (HTTP 200, 0,3 s, execução 4)"]

    monkeypatch.setattr(tela_mod.revisao_amp_svc, "listas_para_amp", listas_para_amp)
    monkeypatch.setattr(tela_mod.revisao_amp_svc, "revisar_listas", revisar_listas)
    monkeypatch.setattr(tela_mod.revisao_amp_svc, "testar_conexao", testar_conexao)
    monkeypatch.setattr(tela_mod, "ClienteAmp", _ClienteAmp)
    return falso


@pytest.fixture
def avisos(monkeypatch):
    """Os QMessageBox.warning do clique (thread da interface)."""
    lista = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: lista.append(a[1:])))
    return lista


def _tela(qtbot, *, controller=None, ultima=None, rodando=False):
    fonte = SimpleNamespace(ultima=ultima, rodando=lambda: rodando)
    tela = tela_mod.ModuloRevisaoAmp(controller=controller or _Controller(), fonte=fonte)
    qtbot.addWidget(tela)
    return tela


def _carregada(tela, qtbot):
    tela.atualizar_listas()
    qtbot.waitUntil(lambda: tela.tabela.topLevelItemCount() > 0 and not tela.rodando(), timeout=5000)
    return tela


def _caixas(tela):
    """O estado da caixa de cada linha: True ou False, ou None quando a linha não tem caixa."""
    estados = []
    for i in range(tela.tabela.topLevelItemCount()):
        item = tela.tabela.topLevelItem(i)
        tem_caixa = bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        estados.append(item.checkState(0) == Qt.CheckState.Checked if tem_caixa else None)
    return estados


def _coluna_amp(tela):
    return [tela.tabela.topLevelItem(i).text(4) for i in range(tela.tabela.topLevelItemCount())]


def _revisar(tela, qtbot, n):
    tela.btn_amp.click()
    qtbot.waitUntil(lambda: tela.btn_amp.isEnabled() and len(tela.resultados_amp) == n and not tela.rodando(),
                    timeout=5000)


def _no_console(tela, qtbot, texto):
    qtbot.waitUntil(lambda: texto in tela.console.toPlainText(), timeout=5000)


# ------------------------------------------------------------------ as listas

def test_listas_aparecem_todas_marcadas_e_a_com_falta_sem_caixa(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    assert _caixas(tela) == [True, None, True]
    assert _coluna_amp(tela)[1] == "falta: PDF da revisão atual"
    assert servico.chamadas == [("listas", ultima.mapeadora.caminho.parent, ultima.pasta_raiz)]
    _no_console(tela, qtbot, "3 lista(s) na conferência; 2 podem ir ao AMP, 1 com falta")


def test_marcar_e_desmarcar_todas(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.btn_desmarcar.click()
    assert _caixas(tela) == [False, None, False]
    tela.btn_marcar.click()
    assert _caixas(tela) == [True, None, True]


def test_a_tabela_nao_enche_com_a_conferencia_rodando(qt_interface, qtbot, servico, ultima):
    tela = _tela(qtbot, ultima=ultima, rodando=True)
    tela.atualizar_listas()
    assert servico.chamadas == [] and tela.tabela.topLevelItemCount() == 0


# ------------------------------------------------------------------ a rodada

def test_so_as_marcadas_vao(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.tabela.topLevelItem(2).setCheckState(0, Qt.CheckState.Unchecked)
    _revisar(tela, qtbot, 1)
    assert [lista.item.lista.codigo for lista in servico.rodada.listas] == [CODIGO]
    assert (servico.rodada.desmarcadas, servico.rodada.com_falta) == ([TERCEIRO], [OUTRO])
    assert (servico.rodada.url, servico.rodada.chave, servico.rodada.chave_posta) == (URL, CHAVE, True)


def test_nenhuma_marcada_avisa_e_nao_chama(qt_interface, qtbot, servico, avisos, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.btn_desmarcar.click()
    tela.btn_amp.click()
    assert avisos == [(TITULO, "Marque ao menos uma lista para mandar ao AMP.")]
    assert servico.rodada is None


def test_a_pronta_e_desmarcada_ao_fim(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    assert _caixas(tela) == [False, None, False]
    assert _coluna_amp(tela) == ["HTML pronto: x.html", "falta: PDF da revisão atual", "HTML pronto: x.html"]
    assert not tela.btn_copiar_diag.isEnabled()


def test_a_que_falhou_continua_marcada_e_liga_o_copiar(qt_interface, qtbot, servico, ultima):
    a, _b, c = servico.listas
    servico.resultados = [ra.ResultadoAmp(a, "falhou", None, "model timeout (etapa agente)", "DIAGNOSTICO-A\n"),
                          ra.ResultadoAmp(c, "pronto", c.item.pasta / "x.html", "x.html")]
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    assert _caixas(tela) == [True, None, False]
    assert _coluna_amp(tela)[0] == "falhou: model timeout (etapa agente)"
    assert tela.btn_copiar_diag.isEnabled()
    tela.btn_copiar_diag.click()
    texto = QApplication.clipboard().text()
    assert texto == ra.diagnosticos_para_copiar(tela.resultados_amp) and "DIAGNOSTICO-A" in texto


def test_conferencia_nova_refaz_a_tabela_e_nao_manda(qt_interface, qtbot, servico, avisos, ultima, tmp_path):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.fonte.ultima = UltimaConferencia(ultima.mapeadora, ultima.conferencia, [], tmp_path / "outra")
    tela.btn_amp.click()
    assert avisos == [(TITULO, AVISO_TABELA_REFEITA)]
    assert servico.rodada is None
    qtbot.waitUntil(lambda: len(servico.chamadas) == 2 and not tela.rodando(), timeout=5000)
    assert _caixas(tela) == [True, None, True]


def test_parar_vale_para_a_rodada(qt_interface, qtbot, servico, ultima):
    servico.resultados = [ra.ResultadoAmp(servico.listas[0], "parado", None, "parado antes de ir ao AMP")]
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 1)
    assert servico.cancelado() is False
    tela.btn_parar.click()
    assert servico.cancelado() is True
    assert _coluna_amp(tela)[0] == "parado"


def test_dois_cliques_abrem_o_html(qt_interface, qtbot, servico, ultima, monkeypatch):
    abertos = []
    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", abertos.append)
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    tela.tabela.itemDoubleClicked.emit(tela.tabela.topLevelItem(0), 0)
    tela.tabela.itemDoubleClicked.emit(tela.tabela.topLevelItem(1), 0)
    assert abertos == [servico.listas[0].item.pasta / "x.html"]


def test_conferencia_rodando_avisa_e_nao_chama(qt_interface, qtbot, servico, avisos, ultima):
    tela = _tela(qtbot, ultima=ultima, rodando=True)
    tela.btn_amp.click()
    assert avisos == [(TITULO, "A conferência ainda está rodando: espere ela terminar.")]
    assert servico.rodada is None


def test_sem_conferencia_avisa(qt_interface, qtbot, servico, avisos):
    tela = _tela(qtbot, ultima=None)
    tela.btn_amp.click()
    assert avisos == [(TITULO, "Confira as revisões antes.")]
    assert servico.rodada is None


def test_rodada_grava_o_log_em_arquivo(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    [arquivo] = list((dados_usuario.pasta_logs() / "amp").glob("amp_revisao_*.log"))
    texto = arquivo.read_text(encoding="utf-8")
    assert "linha da rodada" in texto and URL in texto and CHAVE not in texto
    _no_console(tela, qtbot, f"Log em arquivo: {arquivo}")
    assert CHAVE not in tela.console.toPlainText()


# ------------------------------------------------------------------ o webhook

@pytest.mark.parametrize("url, chave", [("", "segredo"), (URL, ""), ("", "")])
def test_sem_webhook_avisa_e_nao_chama(qt_interface, qtbot, servico, avisos, ultima, url, chave):
    tela = _tela(qtbot, controller=_Controller(url, chave), ultima=ultima)
    tela.btn_amp.click()
    tela.btn_testar_amp.click()
    assert avisos == [(TITULO, AVISO_SEM_CHAVE)] * 2
    assert servico.rodada is None and servico.testes == []


def test_mostra_o_endereco_e_nunca_a_chave(qt_interface, qtbot, ultima):
    tela = _tela(qtbot, ultima=ultima)
    assert URL in tela.lbl_webhook.text() and CHAVE not in tela.lbl_webhook.text()
    sem = _tela(qtbot, controller=_Controller("", ""), ultima=ultima)
    assert sem.lbl_webhook.text() == "Webhook do AMP não configurado: clique em Webhook…, nesta aba."


def test_adota_o_webhook_de_antes(qt_interface, qtbot, ultima):
    controller = _Controller("", "", AMP_WEBHOOK_URL=URL, AMP_WEBHOOK_CHAVE=CHAVE)
    tela = _tela(qtbot, controller=controller, ultima=ultima)
    assert URL in tela.lbl_webhook.text()
    assert controller.gravadas == [{"AMP_REVISAO_LISTAS_URL": URL, "AMP_REVISAO_LISTAS_CHAVE": CHAVE}]


class _Janela:
    """Dublê da `JanelaDoWebhook`: guarda como foi aberta e responde o que o teste pôs."""
    resposta = QDialog.DialogCode.Accepted
    valores_novos = ("https://ampworkflow.gevernova.net/webhook/outro", "nova-chave")
    aberta = None

    def __init__(self, parent, *, titulo, url="", chave=""):
        type(self).aberta = (titulo, url, chave)

    def exec(self):
        return type(self).resposta

    def valores(self):
        return type(self).valores_novos


def test_janela_do_webhook_grava_no_modulo(qt_interface, qtbot, ultima, monkeypatch):
    monkeypatch.setattr(tela_mod.webhook_amp, "JanelaDoWebhook", _Janela)
    monkeypatch.setattr(_Janela, "resposta", QDialog.DialogCode.Accepted)
    controller = _Controller()
    tela = _tela(qtbot, controller=controller, ultima=ultima)
    tela.btn_webhook.click()
    assert _Janela.aberta == ("Webhook da Revisão no AMP", URL, CHAVE)
    assert controller.gravadas == [{"AMP_REVISAO_LISTAS_URL": "https://ampworkflow.gevernova.net/webhook/outro",
                                    "AMP_REVISAO_LISTAS_CHAVE": "nova-chave"}]
    assert "webhook/outro" in tela.lbl_webhook.text()
    _no_console(tela, qtbot, "Webhook da Revisão no AMP salvo: https://ampworkflow.gevernova.net/webhook/outro "
                             "· chave posta")
    assert "nova-chave" not in tela.console.toPlainText()


def test_janela_cancelada_nao_grava(qt_interface, qtbot, ultima, monkeypatch):
    monkeypatch.setattr(tela_mod.webhook_amp, "JanelaDoWebhook", _Janela)
    monkeypatch.setattr(_Janela, "resposta", QDialog.DialogCode.Rejected)
    controller = _Controller()
    tela = _tela(qtbot, controller=controller, ultima=ultima)
    tela.btn_webhook.click()
    assert controller.gravadas == []


# ------------------------------------------------------------------ o teste de conexão

def test_testar_conexao_escreve_e_grava(qt_interface, qtbot, servico):
    tela = _tela(qtbot, ultima=None)
    tela.btn_testar_amp.click()
    _no_console(tela, qtbot, "OK      Ping: workflow 2026-11-03")
    assert f"Testando o AMP: {URL} · chave posta" in tela.console.toPlainText()
    assert servico.testes == [(URL, CHAVE)]
    qtbot.waitUntil(lambda: not tela.rodando(), timeout=5000)
    [arquivo] = list((dados_usuario.pasta_logs() / "amp").glob("amp_teste_*.log"))
    texto = arquivo.read_text(encoding="utf-8")
    assert "OK      Ping" in texto and CHAVE not in texto
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_qt_tela_revisao_amp.py -q`
Expected: FAIL (`atualizar_listas`, `btn_marcar` e `btn_webhook` não existem).

- [ ] **Step 3: Reescrever `sigft/app_qt/views/revisao_amp.py`**

```python
"""Aba "Revisão no AMP" do PMIB Manager: manda ao AMP (o n8n da GE) as listas marcadas da
última conferência, uma por vez, e mostra o que voltou de cada uma.

A tela é fina: a rodada, o pedido e o diagnóstico estão em `services/revisao_amp.py`, e a
chamada em `core/amp/cliente.py`. As listas saem da última conferência da aba ao lado
(`fonte.ultima`, a `UltimaConferencia` da Conferência de Revisões) e aparecem assim que a aba
abre, todas marcadas: o Luan desmarca as que não quer. O endereço e a chave do webhook moram
nesta aba (botão Webhook…, `widgets/webhook_amp.py`), com nomes deste workflow; a chave nunca
aparece na tela nem no log. Cada rodada e cada teste de conexão gravam as linhas do console em
`logs\\amp\\` (`core/log_execucao.py`).
Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout

from sigft import __version__
from sigft.app.idioma import marcar, t
from sigft.app_qt import interface
from sigft.app_qt.widgets import blocos, dialogos_selecao, webhook_amp
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import dados_usuario, log_execucao, plataforma
from sigft.core.amp.cliente import ClienteAmp
from sigft.services import revisao_amp as revisao_amp_svc

# Os nomes deste workflow no `api_config.json`. Os antigos (Configuração → Chaves de API, até
# 2026-11-03) são adotados uma vez.
CHAVES_DO_WEBHOOK = webhook_amp.ChavesDoWebhook("AMP_REVISAO_LISTAS_URL", "AMP_REVISAO_LISTAS_CHAVE",
                                                antigas=("AMP_WEBHOOK_URL", "AMP_WEBHOOK_CHAVE"))

TITULO = marcar("Revisão no AMP")
TITULO_DO_WEBHOOK = marcar("Webhook da Revisão no AMP")
AVISO_SEM_CONFERENCIA = marcar("Confira as revisões antes.")
AVISO_CONFERENCIA_RODANDO = marcar("A conferência ainda está rodando: espere ela terminar.")
AVISO_SEM_CHAVE = marcar("Configure o endereço e a chave do webhook no botão Webhook…, nesta aba.")
AVISO_NENHUMA_MARCADA = marcar("Marque ao menos uma lista para mandar ao AMP.")
AVISO_TABELA_REFEITA = marcar("A conferência mudou: a tabela foi refeita com as listas dela. Confira as "
                              "marcas e clique em Revisar no AMP de novo.")
WEBHOOK_NAO_CONFIGURADO = marcar("Webhook do AMP não configurado: clique em Webhook…, nesta aba.")
EXPLICACAO = marcar("Manda ao AMP, uma por vez, as listas marcadas da última conferência (aba Conferência "
                    "de Revisões). Cada uma volta como um HTML na pasta do _STATUS_PMIB, com o que mudou e as "
                    "ações no controle: nada é aplicado no Excel. Dois cliques numa lista abrem o HTML.")

# O que a coluna "AMP" diz de cada lista. A falta vem pronta do serviço ("falta: ...").
NA_FILA = marcar("na fila")
PRONTO = marcar("HTML pronto: {nome}")
FALHOU = marcar("falhou: {erro}")
PARADO = marcar("parado")

# Os nomes vão em `marcar` e são traduzidos onde a tabela é montada (`t(c)`). As larguras
# somam 850: cabem na aba a 1280x850 (as colunas esticam, mas não encolhem).
COLUNAS = (
    (marcar("Código"), 180),
    (marcar("Revisão em uso"), 100),
    (marcar("Revisão atual"), 100),
    (marcar("STATUS REAL"), 110),
    (marcar("AMP"), 360),
)
COLUNA_AMP = len(COLUNAS) - 1


def _linha(*widgets) -> QHBoxLayout:
    linha_ = QHBoxLayout()
    linha_.setSpacing(15)
    for widget in widgets:
        linha_.addWidget(widget)
    linha_.addStretch()
    return linha_


def _texto_amp(resultado) -> str:
    if resultado.situacao == "pronto":
        return t(PRONTO, nome=resultado.html.name)
    if resultado.situacao == "falhou":
        return t(FALHOU, erro=resultado.detalhe)
    if resultado.situacao == "parado":
        return t(PARADO)
    return resultado.detalhe


def _chave(chave: str) -> str:
    return "posta" if chave else "não posta"  # nao-e-interface: vai só para o log


class ModuloRevisaoAmp(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, fonte=None, embutida=False, console_externo=None,
                 progresso_externo=None) -> None:
        self.fonte = fonte                          # a aba Conferência de Revisões (`fonte.ultima`)
        self.resultados_amp: list[revisao_amp_svc.ResultadoAmp] = []
        self._listas_na_tabela: list = []           # uma ListaParaAmp por linha, na ordem da tabela
        self._conferencia_na_tabela = None          # a `UltimaConferencia` que a tabela mostra
        self._carregando = False
        self._linha_da_lista: dict[int, int] = {}   # id(ListaParaAmp) -> linha da tabela
        self._resultado_na_linha: list = []
        self._cancelado = threading.Event()
        super().__init__(parent, controller, titulo=t(TITULO), com_progresso=True, embutida=embutida,
                         console_externo=console_externo, progresso_externo=progresso_externo)

    # -- montagem ----------------------------------------------------------
    def _build_ui(self) -> None:
        lay = self.content_layout
        cartao = blocos.cartao(lay)
        self.lbl_explicacao = blocos.rotulo(t(EXPLICACAO), alinhar="esquerda", papel="legenda")
        cartao.addWidget(self.lbl_explicacao)
        self.lbl_webhook = blocos.rotulo("", alinhar="esquerda", elidir=True)
        cartao.addWidget(self.lbl_webhook)

        self.btn_amp = blocos.botao(t("Revisar no AMP"), variante="primario", largura_minima=180, negrito=True)
        self.btn_amp.clicked.connect(self._revisar)
        self.btn_testar_amp = blocos.botao(t("Testar conexão com o AMP"), variante="cinza", largura_minima=200)
        self.btn_testar_amp.clicked.connect(self._testar_conexao)
        self.btn_webhook = blocos.botao(t("Webhook…"), variante="cinza", largura_minima=110)
        self.btn_webhook.clicked.connect(self._configurar_webhook)
        self.btn_copiar_diag = blocos.botao(t("Copiar diagnóstico"), variante="cinza", largura_minima=160)
        self.btn_copiar_diag.clicked.connect(self._copiar_diagnostico)
        self.btn_copiar_diag.setEnabled(False)      # só com alguma falha na rodada
        self.btn_parar = blocos.botao(t("Parar"), variante="perigo", largura_minima=90)
        self.btn_parar.clicked.connect(self._parar)
        cartao.addLayout(_linha(self.btn_amp, self.btn_testar_amp, self.btn_webhook, self.btn_copiar_diag,
                                self.btn_parar))

        self.btn_marcar = blocos.botao(t("Marcar todas"), variante="cinza", largura_minima=140)
        self.btn_marcar.clicked.connect(lambda _marcado=False: self._marcar_todas(True))
        self.btn_desmarcar = blocos.botao(t("Desmarcar todas"), variante="cinza", largura_minima=140)
        self.btn_desmarcar.clicked.connect(lambda _marcado=False: self._marcar_todas(False))
        lay.addLayout(_linha(self.btn_marcar, self.btn_desmarcar))

        # Sem barra de lado: as colunas esticam até a largura da tela (`EsticaColunas`).
        self.tabela = dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in COLUNAS],
                                                  barra_horizontal=False)
        self.tabela.itemDoubleClicked.connect(self._abrir_html)
        lay.addWidget(self.tabela, 1)
        self._mostrar_webhook()

    def showEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # O webhook pode ter mudado, e a Conferência pode ter rodado de novo, com a aba já montada.
        self._mostrar_webhook()
        self.atualizar_listas()
        super().showEvent(evento)

    # -- o webhook ---------------------------------------------------------
    def _webhook(self) -> tuple[str, str]:
        """(endereço, chave) deste workflow (`CHAVES_DO_WEBHOOK`)."""
        return webhook_amp.ler(self.controller, CHAVES_DO_WEBHOOK)

    def _mostrar_webhook(self) -> None:
        url, chave = self._webhook()
        if not url:
            self.lbl_webhook.setText(t(WEBHOOK_NAO_CONFIGURADO))
        elif chave:
            self.lbl_webhook.setText(t("Webhook do AMP: {url} · chave posta", url=url))
        else:
            self.lbl_webhook.setText(t("Webhook do AMP: {url} · sem chave", url=url))

    def _webhook_ou_aviso(self) -> tuple[str, str] | None:
        """O endereço e a chave; faltando um deles, o aviso, e nada é chamado."""
        url, chave = self._webhook()
        if not url or not chave:
            self.avisar(t(TITULO), t(AVISO_SEM_CHAVE), "aviso")
            return None
        return url, chave

    def _configurar_webhook(self) -> None:
        url, chave = self._webhook()
        janela = webhook_amp.JanelaDoWebhook(self, titulo=t(TITULO_DO_WEBHOOK), url=url, chave=chave)
        if janela.exec() != QDialog.DialogCode.Accepted:
            return
        novo_url, nova_chave = janela.valores()
        if self.controller is not None:
            webhook_amp.gravar(self.controller, CHAVES_DO_WEBHOOK, novo_url, nova_chave)
        self._mostrar_webhook()
        self.log(f"Webhook da Revisão no AMP salvo: {novo_url} · chave {_chave(nova_chave)}")

    def _log_em_arquivo(self, nome: str, url: str, chave: str):
        """O log em `logs\\amp\\` (as linhas do console, com a hora) e o callback que escreve nos
        dois. A chave não vai: só se ela está posta."""
        arquivo = log_execucao.LogDeExecucao(nome, pasta=str(dados_usuario.pasta_logs() / "amp"),
                                             contexto={"SIG-FT": __version__, "webhook": url,
                                                       "chave": _chave(chave)})
        log = arquivo.envolver(self.log)
        log(f"Log em arquivo: {arquivo.caminho}")
        return arquivo, log

    # -- as listas ---------------------------------------------------------
    def _listas(self, ultima) -> list:
        """As listas da conferência, com os arquivos de cada uma. Na thread do worker: o
        levantamento da pasta raiz pode demorar."""
        if ultima is None:
            return []
        return revisao_amp_svc.listas_para_amp(ultima.conferencia, ultima.downloads,
                                               ultima.mapeadora.caminho.parent, ultima.pasta_raiz)

    def atualizar_listas(self) -> None:
        """Enche a tabela com as listas da última conferência, se ela ainda não as mostra. Não
        mexe com a Conferência rodando nem no meio de uma rodada."""
        ultima = getattr(self.fonte, "ultima", None)
        if ultima is None or ultima is self._conferencia_na_tabela or self._carregando or self.rodando():
            return
        if getattr(self.fonte, "rodando", lambda: False)():
            return
        self._carregando = True
        self.iniciar_tarefa(self._worker_carregar, ultima)

    def _worker_carregar(self, ultima) -> None:
        listas = None
        try:
            listas = self._listas(ultima)
            podem = sum(1 for lista in listas if not lista.falta)
            self.log(f"Revisão no AMP: {len(listas)} lista(s) na conferência; {podem} podem ir ao AMP, "
                     f"{len(listas) - podem} com falta.")
        finally:
            interface.na_interface(self._mostrar_listas, listas, ultima)

    def _mostrar_listas(self, listas, ultima) -> None:
        self._carregando = False
        if listas is None:          # o erro já foi para o console (`iniciar_tarefa`)
            return
        self.tabela.clear()
        self._listas_na_tabela = list(listas)
        self._conferencia_na_tabela = ultima
        self._linha_da_lista = {id(lista): i for i, lista in enumerate(listas)}
        self._resultado_na_linha = [None] * len(listas)
        for lista in listas:
            dados = lista.item.lista
            item = dialogos_selecao.linha_ttk(self.tabela, (dados.codigo, dados.revisao_em_uso, lista.revisao_atual,
                                                            dados.status_real, lista.falta))
            if not lista.falta:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)

    def _itens_com_caixa(self):
        for i, lista in enumerate(self._listas_na_tabela):
            if not lista.falta:
                yield lista, self.tabela.topLevelItem(i)

    def _marcar_todas(self, marcada: bool) -> None:
        estado = Qt.CheckState.Checked if marcada else Qt.CheckState.Unchecked
        for _lista, item in self._itens_com_caixa():
            item.setCheckState(0, estado)

    def marcadas(self) -> list:
        return [lista for lista, item in self._itens_com_caixa() if item.checkState(0) == Qt.CheckState.Checked]

    def _travar_caixas(self, travar: bool) -> None:
        """Durante a rodada as caixas não mudam: a tabela diz o que foi mandado."""
        for _lista, item in self._itens_com_caixa():
            flags = item.flags()
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsUserCheckable if travar
                          else flags | Qt.ItemFlag.ItemIsUserCheckable)
        self.btn_marcar.setEnabled(not travar)
        self.btn_desmarcar.setEnabled(not travar)

    # -- a revisão ---------------------------------------------------------
    def _revisar(self) -> None:
        # Com a Conferência ainda baixando, a última conferência está sem os downloads, e
        # um PDF pode estar pela metade.
        if getattr(self.fonte, "rodando", lambda: False)():
            self.avisar(t(TITULO), t(AVISO_CONFERENCIA_RODANDO), "aviso")
            return
        ultima = getattr(self.fonte, "ultima", None)
        if ultima is None:
            self.avisar(t(TITULO), t(AVISO_SEM_CONFERENCIA), "aviso")
            return
        webhook = self._webhook_ou_aviso()
        if webhook is None:
            return
        if ultima is not self._conferencia_na_tabela:
            self.atualizar_listas()
            self.avisar(t(TITULO), t(AVISO_TABELA_REFEITA), "aviso")
            return
        listas = self.marcadas()
        if not listas:
            self.avisar(t(TITULO), t(AVISO_NENHUMA_MARCADA), "aviso")
            return
        vao = {id(lista) for lista in listas}
        desmarcadas = [lista.item.lista.codigo for lista, _item in self._itens_com_caixa() if id(lista) not in vao]
        com_falta = [lista.item.lista.codigo for lista in self._listas_na_tabela if lista.falta]
        self._cancelado.clear()
        self.resultados_amp = []
        self.btn_copiar_diag.setEnabled(False)
        self._travar_caixas(True)
        for lista in listas:
            self.tabela.topLevelItem(self._linha_da_lista[id(lista)]).setText(COLUNA_AMP, t(NA_FILA))
        self.iniciar_tarefa(self._worker_revisar, listas, desmarcadas, com_falta, *webhook, botao=self.btn_amp)

    def _worker_revisar(self, listas, desmarcadas, com_falta, url: str, chave: str) -> None:
        resultados: list = []
        arquivo, log = self._log_em_arquivo("amp_revisao", url, chave)
        try:
            resultados = revisao_amp_svc.revisar_listas(
                listas, ClienteAmp(url, chave, log_cb=log), versao_sigft=__version__, url=url,
                chave_posta=bool(chave), log_cb=log, progress_cb=self._progresso,
                cancelado_cb=self._cancelado.is_set, desmarcadas=desmarcadas, com_falta=com_falta,
                resultado_cb=lambda resultado: interface.na_interface(self._mostrar_resultado, resultado))
        finally:
            arquivo.fechar()
            interface.na_interface(self._terminar, resultados)

    def _mostrar_resultado(self, resultado) -> None:
        indice = self._linha_da_lista.get(id(resultado.lista))
        if indice is None:
            return
        self._resultado_na_linha[indice] = resultado
        self.tabela.topLevelItem(indice).setText(COLUNA_AMP, _texto_amp(resultado))

    def _terminar(self, resultados) -> None:
        self.resultados_amp = list(resultados)
        self._travar_caixas(False)
        # A lista que voltou com HTML se desmarca: um segundo clique manda só as que faltaram.
        for resultado in self.resultados_amp:
            indice = self._linha_da_lista.get(id(resultado.lista))
            if resultado.situacao == "pronto" and indice is not None:
                self.tabela.topLevelItem(indice).setCheckState(0, Qt.CheckState.Unchecked)
        falhas = sum(1 for r in self.resultados_amp if r.situacao == "falhou")
        self.btn_copiar_diag.setEnabled(any(r.diagnostico for r in self.resultados_amp))
        if falhas:
            self.log(f"[AVISO] {falhas} lista(s) falharam. \"Copiar diagnóstico\" copia o texto de cada uma, "
                     "sem conteúdo de documento e sem a chave, para colar numa conversa nova com o Claude.")

    def _progresso(self, fracao: float) -> None:
        if self.progress_bar is not None:
            interface.na_interface(blocos.definir_progresso, self.progress_bar, fracao)

    def _parar(self) -> None:
        self._cancelado.set()
        self.log("Parada pedida: termino a lista que está no AMP e paro.")

    def _copiar_diagnostico(self) -> None:
        texto = revisao_amp_svc.diagnosticos_para_copiar(self.resultados_amp)
        if not texto:
            return
        QApplication.clipboard().setText(texto)
        self.log("Diagnóstico copiado. Cole numa conversa nova com o Claude, com o repositório do SIG-FT.")

    def _abrir_html(self, item, _coluna=0) -> None:
        indice = self.tabela.indexOfTopLevelItem(item)
        resultado = self._resultado_na_linha[indice] if 0 <= indice < len(self._resultado_na_linha) else None
        if resultado is None or resultado.html is None:
            return
        try:
            plataforma.abrir_no_sistema(resultado.html)
        except OSError as erro:
            self.log(f"[AVISO] Não consegui abrir {resultado.html.name}: {erro}")

    # -- o teste de conexão ------------------------------------------------
    def _testar_conexao(self) -> None:
        webhook = self._webhook_ou_aviso()
        if webhook is None:
            return
        self.iniciar_tarefa(self._worker_testar, *webhook, botao=self.btn_testar_amp)

    def _worker_testar(self, url: str, chave: str) -> None:
        arquivo, log = self._log_em_arquivo("amp_teste", url, chave)
        try:
            log(f"Testando o AMP: {url} · chave {_chave(chave)}")
            for linha in revisao_amp_svc.testar_conexao(ClienteAmp(url, chave, log_cb=log)):
                log(linha)
        finally:
            arquivo.fechar()
```

- [ ] **Step 4: As dicas e o "Como funciona"**

Em `sigft/app/textos_dicas.py`, troque o bloco `"ModuloRevisaoAmp"` por:

```python
    "ModuloRevisaoAmp": {
        "btn_amp": marcar("Manda ao AMP, uma por vez, as listas marcadas. Cada uma volta como um HTML na "
                          "pasta dela; nada é aplicado no Excel."),
        "btn_testar_amp": marcar("Confere a rede, a chave e o workflow publicado (ping). Não manda documento e "
                                 "não chama o agente."),
        "btn_webhook": marcar("O endereço e a chave do workflow da revisão de listas no AMP. A chave fica "
                              "mascarada."),
        "btn_copiar_diag": marcar("Copia o diagnóstico das listas que falharam, sem texto de documento e sem a "
                                  "chave, para colar numa conversa nova com o Claude."),
        "btn_parar": marcar("Para depois da lista que está no AMP. As que já voltaram ficam."),
        "btn_marcar": marcar("Marca todas as listas que podem ir ao AMP."),
        "btn_desmarcar": marcar("Desmarca todas as listas."),
    },
```

Em `sigft/app/como_funciona.py`, troque o `Texto` de `"PMIBManager.amp"` por:

```python
    "PMIBManager.amp": Texto(
        marcar("Manda ao AMP, uma por vez, as listas marcadas da última conferência e guarda o que mudou "
               "num HTML."),
        (
            marcar("Pede uma conferência feita nesta sessão e o webhook do workflow, no botão Webhook… "
                   "desta aba."),
            marcar("As listas vêm todas marcadas; a que tem falta fica sem caixa. As que voltam com HTML se "
                   "desmarcam sozinhas."),
            marcar("O agente do AMP recebe os dois PDFs e o _STATUS_PMIB como estão e devolve o que mudou e as "
                   "ações no controle."),
            marcar("O HTML vai para a pasta da lista, sem sobrescrever. Nada muda no Excel: você confere e "
                   "aplica."),
            marcar("O console mostra cada passo, e o log de cada rodada fica em Documentos\\SIG-FT\\logs\\amp."),
            marcar("Falhou? Copiar diagnóstico leva o detalhe técnico, sem o texto dos documentos."),
        ),
    ),
```

- [ ] **Step 5: As traduções da aba**

Rode o mesmo programa do Passo 5 da Tarefa 3, com este `NOVAS`:

```python
NOVAS = {
    "Webhook da Revisão no AMP": {"es": "Webhook de la Revisión en el AMP", "en": "AMP review webhook"},
    "Configure o endereço e a chave do webhook no botão Webhook…, nesta aba.": {
        "es": "Configure la dirección y la clave del webhook en el botón Webhook…, en esta pestaña.",
        "en": "Set the webhook address and key with the Webhook… button on this tab."},
    "Marque ao menos uma lista para mandar ao AMP.": {
        "es": "Marque al menos una lista para enviar al AMP.", "en": "Check at least one list to send to AMP."},
    "A conferência mudou: a tabela foi refeita com as listas dela. Confira as marcas e clique em Revisar no AMP de novo.": {
        "es": "La verificación cambió: la tabla se rehízo con sus listas. Revise las marcas y haga clic en Revisar en el AMP de nuevo.",
        "en": "The check changed: the table was rebuilt with its lists. Review the checkmarks and click Review in AMP again."},
    "Webhook do AMP não configurado: clique em Webhook…, nesta aba.": {
        "es": "Webhook del AMP no configurado: haga clic en Webhook…, en esta pestaña.",
        "en": "AMP webhook not set: click Webhook… on this tab."},
    "Manda ao AMP, uma por vez, as listas marcadas da última conferência (aba Conferência de Revisões). Cada uma volta como um HTML na pasta do _STATUS_PMIB, com o que mudou e as ações no controle: nada é aplicado no Excel. Dois cliques numa lista abrem o HTML.": {
        "es": "Envía al AMP, una a la vez, las listas marcadas de la última verificación (pestaña Verificación de Revisiones). Cada una vuelve como un HTML en la carpeta del _STATUS_PMIB, con lo que cambió y las acciones en el control: nada se aplica en el Excel. Doble clic en una lista abre el HTML.",
        "en": "Sends the checked lists from the last check (Revision Check tab) to AMP, one at a time. Each one comes back as an HTML file in the _STATUS_PMIB folder, with what changed and the actions on the control sheet: nothing is applied to the Excel file. Double-click a list to open the HTML."},
    "Webhook…": {"es": "Webhook…", "en": "Webhook…"},
    "Marcar todas": {"es": "Marcar todas", "en": "Check all"},
    "Desmarcar todas": {"es": "Desmarcar todas", "en": "Uncheck all"},
    "Manda ao AMP, uma por vez, as listas marcadas. Cada uma volta como um HTML na pasta dela; nada é aplicado no Excel.": {
        "es": "Envía al AMP, una a la vez, las listas marcadas. Cada una vuelve como un HTML en su carpeta; nada se aplica en el Excel.",
        "en": "Sends the checked lists to AMP, one at a time. Each one comes back as an HTML file in its folder; nothing is applied to the Excel file."},
    "Confere a rede, a chave e o workflow publicado (ping). Não manda documento e não chama o agente.": {
        "es": "Verifica la red, la clave y el workflow publicado (ping). No envía documentos ni llama al agente.",
        "en": "Checks the network, the key and the published workflow (ping). It sends no document and does not call the agent."},
    "O endereço e a chave do workflow da revisão de listas no AMP. A chave fica mascarada.": {
        "es": "La dirección y la clave del workflow de revisión de listas en el AMP. La clave queda oculta.",
        "en": "The address and key of the list review workflow in AMP. The key stays masked."},
    "Marca todas as listas que podem ir ao AMP.": {
        "es": "Marca todas las listas que pueden ir al AMP.", "en": "Checks every list that can go to AMP."},
    "Desmarca todas as listas.": {"es": "Desmarca todas las listas.", "en": "Unchecks every list."},
    "Manda ao AMP, uma por vez, as listas marcadas da última conferência e guarda o que mudou num HTML.": {
        "es": "Envía al AMP, una por vez, las listas marcadas de la última verificación y guarda lo que cambió en un HTML.",
        "en": "Sends the checked lists of the last check to the AMP, one at a time, and saves what changed in an HTML file."},
    "Pede uma conferência feita nesta sessão e o webhook do workflow, no botão Webhook… desta aba.": {
        "es": "Pide una verificación hecha en esta sesión y el webhook del workflow, en el botón Webhook… de esta pestaña.",
        "en": "Needs a check made in this session and the workflow's webhook, set with this tab's Webhook… button."},
    "As listas vêm todas marcadas; a que tem falta fica sem caixa. As que voltam com HTML se desmarcam sozinhas.": {
        "es": "Las listas vienen todas marcadas; la que tiene una falta queda sin casilla. Las que vuelven con HTML se desmarcan solas.",
        "en": "All lists come checked; one missing a file has no checkbox. Lists that come back with an HTML uncheck themselves."},
    "O agente do AMP recebe os dois PDFs e o _STATUS_PMIB como estão e devolve o que mudou e as ações no controle.": {
        "es": "El agente del AMP recibe los dos PDF y el _STATUS_PMIB tal como están y devuelve lo que cambió y las acciones en el control.",
        "en": "The AMP agent gets both PDFs and the _STATUS_PMIB as they are and returns what changed and the actions on the control sheet."},
    "O console mostra cada passo, e o log de cada rodada fica em Documentos\\SIG-FT\\logs\\amp.": {
        "es": "La consola muestra cada paso, y el log de cada ronda queda en Documentos\\SIG-FT\\logs\\amp.",
        "en": "The console shows each step, and each round's log stays in Documentos\\SIG-FT\\logs\\amp."},
}
```

Expected: `es faltando: []` e `en faltando: []`. Os textos antigos da aba (a explicação, o aviso
de Configuração → Chaves de API, as duas dicas e os três itens do "Como funciona" que saíram)
estavam em `sobrando` e são apagados aqui.

- [ ] **Step 6: Rodar e ver passar**

Run: `python -m pytest tests/test_qt_tela_revisao_amp.py tests/test_qt_tela_gestao_sobressalentes.py tests/test_qt_dicas.py tests/test_como_funciona.py tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py -q`
Expected: PASS.

- [ ] **Step 7: Suíte, ruff, pyflakes, abrir o app e commit**

Run: `bash scripts/check.sh && python -m ruff check . && python -m pyflakes frontend.py && QT_QPA_PLATFORM=offscreen python frontend.py --smoke`
Expected: verde, e o smoke visita todas as telas sem erro.

```bash
git add sigft/app_qt/views/revisao_amp.py tests/test_qt_tela_revisao_amp.py sigft/app/textos_dicas.py sigft/app/como_funciona.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json
git commit -m "Aba Revisao no AMP: listas marcaveis, webhook na aba e log em arquivo"
```

---

### Task 5: O workflow do n8n e a cópia do agente

**Files:**
- Modify: `amp/revisao_de_listas/gerar_workflow.py` (reescrever inteiro)
- Modify: `amp/revisao_de_listas/workflow_revisao_de_listas.json` (regenerar)
- Create: `amp/revisao_de_listas/agente.md`
- Delete: `amp/revisao_de_listas/pedido.md`
- Test: `tests/test_amp_workflow.py` (reescrever inteiro)

**Interfaces:**
- Produces: `gerar_workflow.montar_workflow(versao: str) -> dict`, `VERSAO_WORKFLOW = "2026-11-03"`,
  `CAMINHO_WEBHOOK = "sigft-revisao-listas"` e `NOME_DO_AGENTE = "Spare Parts Document Reviewer"`.

- [ ] **Step 1: Reescrever `tests/test_amp_workflow.py`**

```python
"""O workflow do n8n da revisão das listas (`amp/revisao_de_listas/`).

O `.json` que se importa (ou cola) no n8n da GE é gerado pelo `gerar_workflow.py`. Este teste trava
que os dois não se desencontram e que o contrato com o SIG-FT continua lá:
- o webhook com a chave;
- o ping sem o agente;
- os arquivos conferidos antes do agente (400);
- o AMP Agent com o agente da revisão, e o erro dele em 502;
- a resposta preparada.

As instruções do agente moram no AMP: `agente.md` é a cópia. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §3 e §4.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "amp" / "revisao_de_listas"


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar_workflow", PASTA / "gerar_workflow.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _workflow():
    return json.loads((PASTA / "workflow_revisao_de_listas.json").read_text(encoding="utf-8"))


def _no(workflow, nome):
    return next(n for n in workflow["nodes"] if n["name"] == nome)


def _destinos(workflow, nome, saida=0):
    saidas = workflow["connections"].get(nome, {}).get("main", [])
    return [c["node"] for c in (saidas[saida] if len(saidas) > saida else [])]


def test_o_json_versionado_e_o_que_o_gerador_produz():
    gerador = _gerador()
    assert _workflow() == gerador.montar_workflow(gerador.VERSAO_WORKFLOW)


def test_webhook_com_header_auth_e_resposta_por_no():
    p = _no(_workflow(), "Webhook do SIG-FT")["parameters"]
    assert (p["httpMethod"], p["path"], p["authentication"], p["responseMode"]) == (
        "POST", "sigft-revisao-listas", "headerAuth", "responseNode")


def test_ping_nao_passa_pelo_agente():
    workflow = _workflow()
    assert _destinos(workflow, "Webhook do SIG-FT") == ["É ping?"]
    assert _destinos(workflow, "É ping?", 0) == ["Responde ping"]
    assert _destinos(workflow, "É ping?", 1) == ["Monta a mensagem"]
    assert "'ping'" in _no(workflow, "Responde ping")["parameters"]["responseBody"]


def test_monta_a_mensagem_leva_os_arquivos():
    p = _no(_workflow(), "Monta a mensagem")["parameters"]
    assert p["includeOtherFields"] is True
    [campo] = p["assignments"]["assignments"]
    assert (campo["name"], campo["value"]) == ("chatInput", "={{ $json.body.mensagem }}")


def test_sem_os_arquivos_o_agente_nao_e_chamado():
    workflow = _workflow()
    assert _destinos(workflow, "Chegaram os arquivos?", 0) == ["AMP Agent"]
    assert _destinos(workflow, "Chegaram os arquivos?", 1) == ["Responde sem arquivos"]
    assert _no(workflow, "Responde sem arquivos")["parameters"]["options"]["responseCode"] == 400


def test_o_agente_e_o_da_revisao_e_o_erro_dele_e_502():
    workflow = _workflow()
    agente = _no(workflow, "AMP Agent")
    assert agente["type"] == "CUSTOM.amp" and agente["onError"] == "continueErrorOutput"
    assert agente["parameters"]["agentId"]["cachedResultName"] == "Spare Parts Document Reviewer"
    assert _destinos(workflow, "AMP Agent", 0) == ["Prepara a resposta"]
    assert _destinos(workflow, "AMP Agent", 1) == ["Responde erro"]
    assert _no(workflow, "Responde erro")["parameters"]["options"]["responseCode"] == 502
    assert _destinos(workflow, "Prepara a resposta") == ["Responde"]


def test_a_resposta_corta_a_narracao_e_lista_os_arquivos():
    codigo = _no(_workflow(), "Prepara a resposta")["parameters"]["jsCode"]
    for trecho in ("<!DOCTYPE html|<html", "</html>", "$('Monta a mensagem').first().binary", "arquivos",
                   "o agente não devolveu HTML", "versao_workflow: VERSAO", "'2026-11-03'"):
        assert trecho in codigo, trecho


def test_toda_conexao_aponta_para_no_que_existe():
    workflow = _workflow()
    nomes = {n["name"] for n in workflow["nodes"]}
    for origem, saidas in workflow["connections"].items():
        assert origem in nomes
        for saida in saidas["main"]:
            assert all(c["node"] in nomes for c in saida)


def test_o_pedido_saiu_e_o_agente_tem_copia():
    assert not (PASTA / "pedido.md").exists()
    agente = (PASTA / "agente.md").read_text(encoding="utf-8")
    for termo in ("Spare Parts Document Reviewer", "A fonte é o AMP", "SEM_LISTA_STATUS_PMIB", "DOCUMENTAL",
                  "a conferir", "CRIAR", "EXCLUIR", "SUBSTITUIR", "<tr> e <td>"):
        assert termo in agente, termo
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_amp_workflow.py -q`
Expected: FAIL (`montar_workflow()` ainda pede o pedido; não há nó `AMP Agent`).

- [ ] **Step 3: Reescrever `amp/revisao_de_listas/gerar_workflow.py`**

```python
"""Gera o workflow do n8n da revisão das listas.

    python amp/revisao_de_listas/gerar_workflow.py

Grava `workflow_revisao_de_listas.json` ao lado, para importar (ou colar) no n8n da GE. É o workflow
colado e testado no n8n da GE em 2026-11-03. As instruções do agente moram no AMP (o "Spare Parts
Document Reviewer"; a cópia está em `agente.md`), e o workflow só leva até ele a mensagem e os
arquivos do SIG-FT. `tests/test_amp_workflow.py` trava que o `.json` versionado é o que este gerador
produz. Os ids são fixos, para o arquivo só mudar quando o conteúdo muda. O `agentId` e a credencial
do AMP Agent são os da instância da GE; noutra, escolha-os de novo no nó. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "workflow_revisao_de_listas.json"
VERSAO_WORKFLOW = "2026-11-03"
CAMINHO_WEBHOOK = "sigft-revisao-listas"
NOME_DO_AGENTE = "Spare Parts Document Reviewer"
MODELO_DO_AGENTE = "bedrock-claude-sonnet-5.5"
CREDENCIAL_DO_AMP = {"id": "2GcgH0WxCkNN6bg4", "name": "AMP account 1859"}

WEBHOOK = "Webhook do SIG-FT"
E_PING = "É ping?"
MONTA = "Monta a mensagem"
CHEGARAM = "Chegaram os arquivos?"
AGENTE = "AMP Agent"
PREPARA = "Prepara a resposta"

NOTA = """## SIG-FT · Revisão das listas (AMP)
**Ligar (uma vez):**
1. **Webhook do SIG-FT** → *Credential for Header Auth* → *Create new*: Name `X-SIGFT-Chave`, Value um valor longo e aleatório. O mesmo valor vai no SIG-FT: PMIB Manager → aba Revisão no AMP → **Webhook…** → Chave.
2. **AMP Agent** → escolha o agente *Spare Parts Document Reviewer* → *Add option* → **Timeout**: o máximo.
3. Salve e **publique**.
4. Copie a **Production URL** do webhook para o SIG-FT: **Webhook…** → Endereço.

As instruções do agente moram no AMP: melhore o agente lá, não aqui.
O SIG-FT manda `modo`, `mensagem` e os arquivos `revisao_em_uso`, `revisao_atual` e `status_pmib`. O ping responde sem chamar o agente.
Passo a passo: `amp/revisao_de_listas/LEIA-ME.md`, no repositório do SIG-FT."""

# É o código do nó "Prepara a resposta" colado na GE em 03/11, sem mudança.
JS_PREPARA = r"""// Prepara a resposta ao SIG-FT. As instrucoes do agente moram no AMP, nao aqui.
const VERSAO = '__VERSAO__';
const texto = String($input.first().json.output ?? '');
const binarios = $('__MONTA__').first().binary || {};
const arquivos = Object.values(binarios).map(b => b.fileName || '?');
let html = texto;
const inicio = html.search(/<!DOCTYPE html|<html/i);
if (inicio > 0) html = html.slice(inicio);        // tira a narracao do agente antes do HTML
const fim = html.toLowerCase().lastIndexOf('</html>');
if (fim >= 0) html = html.slice(0, fim + 7);      // e o que vier depois dele
html = html.replace(/\\%/g, '%').trim();          // o agente escreve 100\% no CSS
const ok = /<html|<table/i.test(html);
const resposta = { ok, modo: 'revisar', html, arquivos, versao_workflow: VERSAO, execucao: $execution.id };
if (!ok) resposta.erro = 'o agente não devolveu HTML';
return [{ json: { resposta } }];
"""


def _responde(nome: str, id_: str, corpo: str, posicao: list[int], codigo: int | None = None) -> dict:
    return {"parameters": {"respondWith": "json", "responseBody": corpo,
                           "options": {"responseCode": codigo} if codigo else {}},
            "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": posicao, "id": id_,
            "name": nome}


def _se(nome: str, id_: str, id_condicao: str, esquerda: str, operador: dict, direita, posicao: list[int]) -> dict:
    return {"parameters": {"conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [{"id": id_condicao, "leftValue": esquerda, "rightValue": direita,
                                "operator": operador}],
                "combinator": "and"},
            "options": {"looseTypeValidation": True}},
            "type": "n8n-nodes-base.if", "typeVersion": 2, "position": posicao, "id": id_, "name": nome}


def _liga(*destinos: str) -> dict:
    return {"main": [[{"node": d, "type": "main", "index": 0}] for d in destinos]}


def montar_workflow(versao: str) -> dict:
    """O workflow pronto para importar: webhook → ping, ou mensagem → arquivos? → agente → resposta
    (sem arquivos, 400; erro do agente, 502)."""
    v = f"'{versao}'"
    nos = [
        {"parameters": {"content": NOTA, "height": 330, "width": 640}, "type": "n8n-nodes-base.stickyNote",
         "typeVersion": 1, "position": [-40, -300], "id": "a1c3e5f7-0b2d-4f61-9a83-c5e7091b3d01",
         "name": "Como ligar"},
        {"parameters": {"httpMethod": "POST", "path": CAMINHO_WEBHOOK, "authentication": "headerAuth",
                        "responseMode": "responseNode", "options": {}},
         "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 200],
         "id": "b2d4f608-1c3e-4072-ab94-d6f8102c4e02", "name": WEBHOOK,
         "webhookId": "c3e50719-2d4f-4183-bca5-e709213d5f03"},
        _se(E_PING, "d4f6182a-3e50-4294-8db6-f81a324e6004", "e5072a3b-4f61-43a5-9ec7-0a2b435f7105",
            "={{ $json.body.modo }}", {"type": "string", "operation": "equals"}, "ping", [220, 200]),
        _responde("Responde ping", "f6183b4c-5072-44b6-afd8-1b3c54608206",
                  "={{ JSON.stringify({ ok: true, modo: 'ping', versao_workflow: %s, execucao: $execution.id }) }}" % v,
                  [460, 40]),
        {"parameters": {"assignments": {"assignments": [{"id": "07294c5d-6183-45c7-b0e9-2c4d65719307",
                                                         "name": "chatInput", "value": "={{ $json.body.mensagem }}",
                                                         "type": "string"}]},
                        "includeOtherFields": True, "options": {}},
         "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [460, 300],
         "id": "183a5d6e-7294-46d8-81fa-3d5e76820408", "name": MONTA},
        _se(CHEGARAM, "294b6e7f-83a5-47e9-920b-4e6f87931509", "3a5c7f80-94b6-48fa-a31c-5f7098a4260a",
            "={{ Object.keys($binary || {}).length }}", {"type": "number", "operation": "gte"}, 2, [700, 300]),
        {"parameters": {"agentId": {"__rl": True,
                                    "value": json.dumps({"agentName": NOME_DO_AGENTE, "model": MODELO_DO_AGENTE},
                                                        separators=(",", ":")),
                                    "mode": "list", "cachedResultName": NOME_DO_AGENTE},
                        "options": {}},
         "type": "CUSTOM.amp", "typeVersion": 1, "position": [940, 200],
         "id": "4b6d8091-a5c7-490b-b42d-6081a9b5370b", "name": AGENTE,
         "credentials": {"ampOAuth2Api": dict(CREDENCIAL_DO_AMP)}, "onError": "continueErrorOutput"},
        _responde("Responde sem arquivos", "5c7e91a2-b6d8-4a1c-853e-7192bac6480c",
                  "={{ JSON.stringify({ ok: false, modo: 'revisar', etapa: 'arquivos', erro: 'os arquivos não "
                  "chegaram ao agente: o workflow recebeu ' + Object.keys($binary || {}).length + ' arquivo(s)', "
                  "versao_workflow: %s, execucao: $execution.id }) }}" % v, [940, 440], 400),
        {"parameters": {"jsCode": JS_PREPARA.replace("__VERSAO__", versao).replace("__MONTA__", MONTA)},
         "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1180, 120],
         "id": "6d8fa2b3-c7e9-4b2d-964f-82a3cbd7590d", "name": PREPARA},
        _responde("Responde", "7e90b3c4-d8fa-4c3e-a750-93b4dce86a0e", "={{ JSON.stringify($json.resposta) }}",
                  [1420, 120]),
        _responde("Responde erro", "8fa1c4d5-e90b-4d4f-b861-a4c5edf97b0f",
                  "={{ JSON.stringify({ ok: false, modo: 'revisar', etapa: 'agente', erro: String(($json.error && "
                  "($json.error.message || $json.error)) || 'erro sem mensagem'), versao_workflow: %s, execucao: "
                  "$execution.id }) }}" % v, [1180, 320], 502),
    ]
    conexoes = {
        WEBHOOK: _liga(E_PING),
        E_PING: _liga("Responde ping", MONTA),
        MONTA: _liga(CHEGARAM),
        CHEGARAM: _liga(AGENTE, "Responde sem arquivos"),
        AGENTE: _liga(PREPARA, "Responde erro"),
        PREPARA: _liga("Responde"),
    }
    return {"name": "SIG-FT · Revisão das listas (AMP)", "nodes": nos, "connections": conexoes,
            "settings": {"executionOrder": "v1"}}


def main(argv: list[str] | None = None) -> int:
    ARQUIVO.write_text(json.dumps(montar_workflow(VERSAO_WORKFLOW), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"Gravado: {ARQUIVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Criar `amp/revisao_de_listas/agente.md`, apagar o `pedido.md` e regenerar o `.json`**

`amp/revisao_de_listas/agente.md`:

````markdown
# O agente da revisão das listas, no AMP

**A fonte é o AMP.** Este arquivo é a cópia versionada do agente configurado no AMP, para o
`git log` mostrar o que mudou e quando. Para melhorar o agente:
1. mude no AMP (o agente → Configure);
2. copie o texto novo para cá, num commit que diga o porquê.

O workflow (`workflow_revisao_de_listas.json`) não leva instrução nenhuma: ele chama este agente
pelo nó **AMP Agent**.

> **Cópia de 2026-11-03**, feita do texto combinado na criação do agente, com as duas linhas
> acrescentadas pelo Luan depois do teste 3. Na primeira vez que alguém mexer no agente, confira
> esta cópia contra o AMP. Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §3.

| Campo no AMP | Valor |
|---|---|
| Agent Name | Spare Parts Document Reviewer |
| Model | `bedrock-claude-sonnet-5.5` |
| Tone | professional |
| Data sources | nenhum: os arquivos chegam em cada pedido |

## Description

```text
Compara duas revisões de uma lista de sobressalentes do projeto Itaipu (PDF) com a planilha de controle _STATUS_PMIB (Excel) e devolve o que mudou entre as revisões e as linhas do controle a criar, excluir ou substituir.
```

## Customized Goal

```text
Revisar listas de sobressalentes do projeto Itaipu (Consórcio CMI). Recebo três arquivos: o PDF da revisão em uso da lista, o PDF da revisão atual e a planilha de controle _STATUS_PMIB (Excel). Comparo as duas revisões e aponto o que entrou, saiu ou mudou, citando a página e o item. Comparo a revisão atual com o controle e digo quais linhas criar, excluir ou substituir para que o controle fique idêntico à lista. Preservo o andamento que a equipe já preencheu (código PMIB, status, autorização). O que eu não tiver certeza, marco "a conferir". Não invento.
```

## System Prompt

```text
Você revisa listas de sobressalentes do projeto Itaipu (Consórcio CMI) para a equipe que mantém a planilha de controle de cada lista, a _STATUS_PMIB.

## O que você recebe em cada pedido

Três arquivos anexados e uma mensagem com o código da lista, as revisões e a data de hoje:
1. REVISÃO EM USO: o PDF da revisão que a _STATUS_PMIB reflete hoje. Pode não vir, quando a lista ainda não tem revisão em uso; nesse caso, compare só a revisão atual com a _STATUS_PMIB.
2. REVISÃO ATUAL: o PDF da última revisão emitida.
3. _STATUS_PMIB: a planilha Excel de controle. A tabela está na aba "Lista de Materiais"; o cabeçalho é a linha que contém "CÓDIGO DO MATERIAL", e acima dele fica a linha "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: ...".

Os PDFs se chamam <código da lista>[<revisão>].pdf; a revisão entre colchetes diz qual é qual. Se a mensagem e os nomes não baterem, diga isso no topo da resposta.

## O que fazer

1. Compare a revisão em uso com a revisão atual: os itens que entraram, os que saíram e os que mudaram (quantidade, unidade, descrição, código do material, marca e modelo, código CMI e demais colunas da lista).
2. Compare a revisão atual com a _STATUS_PMIB: o que falta, o que sobra e o que está diferente.
3. Diga, linha a linha, o que fazer na _STATUS_PMIB para que ela fique idêntica à revisão atual.

Para relacionar um item entre a lista e o controle, use o código do material; sem ele, a descrição junto com marca e modelo. Não use só o número do ITEM: a lista pode ter sido renumerada.

## Regras da equipe

- A _STATUS_PMIB fica idêntica à lista.
- O item que sai da lista não é apagado: vai para a aba SEM_LISTA_STATUS_PMIB, com a origem em OBSERVAÇÕES (de qual lista e de qual revisão saiu).
- Linhas a mais na _STATUS_PMIB vindas de entrega DOCUMENTAL são explosão pedida por Itaipu, não erro: mantenha-as e não as liste como divergência.
- Nas linhas que continuam, preserve o que a equipe já preencheu: código PMIB, status, autorização e as demais colunas de andamento. Substituir uma linha é trocar só as colunas que vêm da lista.
- No fim, a linha de revisão passa a "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: <revisão atual> - DATA DE ALTERAÇÃO: <data de hoje>".
- Cite a página do PDF de onde saiu cada mudança. O que não tiver certeza, marque "a conferir". Não invente item, valor nem página.

## O que devolver

Um único documento HTML, só o HTML, sem nada antes ou depois, com:

1. Resumo: a lista, as revisões comparadas e quantas mudanças e ações de cada tipo.
2. Mudanças entre as revisões: uma tabela com tipo (ENTROU, SAIU, MUDOU), item, código do material, campo, valor na revisão em uso, valor na revisão atual e página.
3. Ações na _STATUS_PMIB: uma tabela com ação (CRIAR, EXCLUIR, SUBSTITUIR), linha da planilha (número da linha no Excel; para CRIAR, depois de qual linha entra), item, código do material, coluna, valor atual, valor novo e página da lista. EXCLUIR quer dizer mover para a SEM_LISTA_STATUS_PMIB.
4. As linhas que vão para a SEM_LISTA_STATUS_PMIB, com as mesmas colunas da _STATUS_PMIB e a OBSERVAÇÃO preenchida.
5. A linha de revisão nova.

Cada tabela tem um botão que copia a tabela como texto separado por tabulação, para colar direto no Excel.
Escreva cada linha de cada tabela diretamente no HTML, com <tr> e <td>. Use JavaScript só para o botão de copiar, nunca para montar ou calcular dados das tabelas.
A resposta começa em <!DOCTYPE html> e termina em </html>: não escreva o que está fazendo, nem antes nem depois.
```
````

Depois:

```bash
git rm amp/revisao_de_listas/pedido.md
python amp/revisao_de_listas/gerar_workflow.py
```

- [ ] **Step 5: Conferir o JavaScript do nó com o Node, se houver**

Run: o mesmo dublê de 03/11 (`$input`, `$` e `$execution` de mentira), com o `jsCode` gerado:

```bash
python - <<'PY'
import json, subprocess, shutil
w = json.load(open("amp/revisao_de_listas/workflow_revisao_de_listas.json", encoding="utf-8"))
codigo = next(n for n in w["nodes"] if n["name"] == "Prepara a resposta")["parameters"]["jsCode"]
if shutil.which("node"):
    teste = ("const f = new Function('$input','$','$execution', " + json.dumps(codigo) + ");"
             "const r = f({first: () => ({json: {output: 'Vou ler.<!DOCTYPE html>\\n<html><style>t{width:100\\\\%}</style><table></table></html>\\nfim'}})},"
             " () => ({first: () => ({binary: {a: {fileName: 'a.pdf'}}})}), {id: '7'});"
             "console.log(JSON.stringify(r[0].json.resposta));")
    print(subprocess.run(["node", "-e", teste], capture_output=True, text=True).stdout)
PY
```

Expected: `{"ok":true,...,"html":"<!DOCTYPE html>\n<html><style>t{width:100%}</style><table></table></html>","arquivos":["a.pdf"],...}`.
Sem o `node` na máquina, o passo só imprime nada; o teste de 03/11 já rodou este mesmo código.

- [ ] **Step 6: Rodar e ver passar; suíte; commit**

Run: `python -m pytest tests/test_amp_workflow.py -q && bash scripts/check.sh && python -m ruff check .`

```bash
git add amp/revisao_de_listas tests/test_amp_workflow.py
git commit -m "Workflow do n8n da revisao: AMP Agent com os arquivos e a copia do agente"
```

---

### Task 6: A documentação

**Files:**
- Modify: `amp/revisao_de_listas/LEIA-ME.md` (reescrever inteiro)
- Modify: `docs/base-conhecimento/14-aconex-e-conferencia-de-revisoes.md` (a seção "Peça 2", até o fim)
- Modify: `docs/ROTEIRO_DE_TESTE.md` (a Etapa 5c inteira)
- Modify: `docs/ACONEX_AO_VIVO.md` (a tabela de documentos e "Onde parou a peça 2")
- Modify: `CLAUDE.md` (a linha de `amp/revisao_de_listas/` na tabela de documentação)
- Modify: `docs/refatoracao/PENDENCIAS.md` (a linha de 2026-10-27 do S5, mais uma pendência nova)

- [ ] **Step 1: Reescrever o `LEIA-ME.md`**

Ele cobre, nesta ordem:

1. **O que é:** o workflow que a aba Revisão no AMP chama. Ele leva ao agente *Spare Parts Document
   Reviewer* os dois PDFs e o `_STATUS_PMIB` de cada lista marcada, e devolve um HTML com o que
   mudou e as ações no controle.
2. **Os arquivos:** a tabela com `agente.md`, `gerar_workflow.py` e `workflow_revisao_de_listas.json`.
3. **Ligar, uma vez:**
   1. **O agente no AMP:** os campos, com o texto do `agente.md`. Sem data source.
   2. **O workflow no n8n:**
      - importar o arquivo ou colar o JSON no canvas;
      - a credencial Header Auth `X-SIGFT-Chave`, com o comando de PowerShell que gera o valor;
      - escolher o agente no **AMP Agent**: se ele não aparece, confira se foi salvo no AMP;
        `By ID` é a saída;
      - o Timeout no máximo;
      - salvar e publicar;
      - copiar a Production URL.
   3. **No SIG-FT:** PMIB Manager → aba Revisão no AMP → **Webhook…** → Endereço e Chave →
      Salvar → **Testar conexão com o AMP**, que deve dar `OK      Ping: workflow 2026-11-03`.
4. **Testar sem o SIG-FT (PowerShell):**
   - os comandos de 03/11, com a Production URL, a chave `XXXXXX` e os arquivos copiados para
     `C:\temp\amp`;
   - o ping (`--form-string "modo=ping"`);
   - a revisão (`modo=revisar`, `mensagem`, os três `-F`);
   - extrair o `.html` e abrir.
5. **Melhorar o agente:** no AMP, e depois copiar para o `agente.md`.
6. **O que os testes de 03/11 ensinaram:**
   - o AMP Agent lê o campo `chatInput` ("Prompt is empty...");
   - os arquivos só passam do *Edit Fields* com *Include Other Input Fields = All*;
   - *Listen for test event* dentro do nó roda só aquele nó: o certo é *Execute workflow* no canvas;
   - a Test URL só vale com o n8n escutando, e o SIG-FT usa a Production URL;
   - o agente narra antes do HTML e escreve `100\%` no CSS, e o "Prepara a resposta" corrige.
7. **Se der errado:**
   - o console e o log da rodada (`Documentos\SIG-FT\logs\amp\amp_revisao_*.log`);
   - o "Copiar diagnóstico";
   - o número da execução, que se procura em *Executions*;
   - o texto para a conversa nova (os arquivos a ler: este LEIA-ME, o desenho de 03/11,
     `sigft/core/amp/cliente.py` e `sigft/services/revisao_amp.py`);
   - a tabela de sintomas:

| Sintoma | Onde olhar |
|---|---|
| "Sem conexão com o AMP" | a rede da máquina: ela precisa alcançar `ampworkflow.gevernova.net` |
| HTTP 401 ou 403 | a chave do botão **Webhook…** é diferente da credencial `X-SIGFT-Chave` do workflow |
| HTTP 404 | o workflow não está publicado, ou o endereço é a Test URL (`/webhook-test/`) |
| HTTP 400, etapa `arquivos` | os arquivos não chegaram ao agente: o *Monta a mensagem* precisa de *Include Other Input Fields = All* |
| HTTP 502, etapa `agente` | o agente falhou: veja a execução no n8n; confira se o AMP Agent tem o agente e a credencial |
| "o agente não devolveu HTML" | o agente respondeu texto: melhore o system prompt no AMP |
| "o workflow recebeu N de M arquivo(s)" | algum arquivo se perdeu no caminho: veja a aba Binary do Webhook na execução |
| "o AMP não respondeu JSON" | algo no caminho devolveu uma página (login, proxy): a resposta está no diagnóstico |
| "a conexão com o AMP caiu depois de N s" | algo no caminho corta a chamada longa; o n8n pode ter seguido (veja a execução) |
| "o AMP não respondeu em 15 min" | o agente demorou demais: veja a execução (arquivo muito grande?) |

- [ ] **Step 2: A base de conhecimento**

Em `docs/base-conhecimento/14-aconex-e-conferencia-de-revisoes.md`, reescreva do título
`## Peça 2: revisão no AMP` até o fim do arquivo. Escreva o comportamento das Tarefas 1 a 5:
- **a nota de abertura:** desde a v2, de 2026-11-03, com o desenho novo e este plano;
- **a tabela das camadas:** n8n, core, serviço, widget e tela, com os arquivos novos;
- **o contrato do webhook:**
  - multipart com `modo`, `mensagem` e os três campos de arquivo;
  - o ping em JSON;
  - as respostas e as etapas `arquivos` e `agente`;
- **o envio uma vez só**, pela rota do ping;
- **a mensagem**, com e sem revisão em uso;
- **as listas** (`listas_para_amp`, como antes);
- **a rodada:**
  - o ping antes;
  - o HTML;
  - a conferência dos arquivos recebidos;
  - o que fica "falta";
  - o diagnóstico em `logs\amp\`;
- **o log:** as linhas de cada lista, o batimento de 30 s e o arquivo `amp_revisao_*.log`;
- **o diagnóstico:** os nomes e os tamanhos, o `html` fora, o `erro` cortado em 300;
- **o teste de conexão:** só o ping;
- **a aba:**
  - as listas marcáveis, todas marcadas, a com falta sem caixa;
  - Marcar e Desmarcar todas;
  - a pronta se desmarca;
  - a conferência nova refaz a tabela;
  - o botão **Webhook…** com a janela;
  - os nomes `AMP_REVISAO_LISTAS_*` e a adoção dos antigos;
- **os testes:** os seis arquivos de teste, incluindo `test_qt_webhook_amp.py`.

Na nota do topo do arquivo, troque "a peça 2 (Revisão no AMP) entrou em 2026-10-27, na 1.3.1-rc.2"
por "a peça 2 (Revisão no AMP) entrou em 2026-10-27, na 1.3.1-rc.2, e foi refeita em 2026-11-03
(v2: o agente do AMP recebe os arquivos)".

- [ ] **Step 3: O roteiro de teste**

Em `docs/ROTEIRO_DE_TESTE.md`, troque a Etapa 5c inteira, do título `## Etapa 5c` até a linha
`---` antes da `## Etapa 5d`, pela etapa nova:

- **Título e escopo:**
  - "Etapa 5c — Revisão das listas no AMP (v2, 2026-11-03, sem portal)";
  - a partir da versão de teste que levar estas tarefas (o número entra no lançamento);
  - nenhum arquivo é alterado: o resultado é um HTML novo na pasta de cada lista.
- **Antes de começar:**
  - a versão instalada;
  - o agente e o workflow ligados (LEIA-ME);
  - a 5b.3 feita nesta sessão.
- **5c.1 Webhook e conexão:** **Webhook…** com a Production URL e a chave; **Testar conexão com o
  AMP** deve dar `OK      Ping: workflow 2026-11-03 (HTTP 200, ...)`. Sintomas: 403 é a chave; 404 é
  a publicação ou a Test URL.
- **5c.2 As listas:** a tabela vem cheia ao abrir a aba, todas marcadas, e a com falta sem caixa.
  Desmarque todas e marque **uma**.
- **5c.3 Uma lista:**
  - **Revisar no AMP**: o console mostra o `vai:`, o batimento a cada 30 s e a linha da `resposta:`
    com a execução;
  - o HTML aparece na pasta da lista, e dois cliques abrem;
  - a lista se desmarca;
  - anote o tempo;
  - o log está em `Documentos\SIG-FT\logs\amp\amp_revisao_*.log`.
- **5c.4 Duas ou três listas,** uma desmarcada: a desmarcada não vai, e o começo do log diz isso.
- **5c.5 Conferir o HTML:** cinco mudanças contra as páginas citadas; a tabela de ações numa
  **cópia** do `_STATUS_PMIB`, nunca no original.
- **5c.6 Se falhar:** a coluna AMP diz "falhou: ...", "Copiar diagnóstico" e a conversa nova, com o
  número da execução no n8n.

- [ ] **Step 4: O caderno da frente, o CLAUDE.md e as pendências**

Em `docs/ACONEX_AO_VIVO.md`:
- **Na tabela de documentos:** acrescente as linhas
  `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md | o desenho da peça 2 v2 (o agente do AMP recebe os arquivos)`
  e `docs/superpowers/plans/2026-11-03-amp-revisao-com-arquivos.md | o plano da peça 2 v2: 6 tarefas`.
- **No começo de "Onde parou a peça 2",** acrescente um bloco "**v2 (2026-11-03)**", com três pontos:
  - **o que os testes na GE provaram:** o AMP Agent lê os arquivos, e a rede segura a chamada de
    minutos;
  - **o que a v2 entregou:** as Tarefas 1 a 6 deste plano;
  - **o que falta:**
    - a Etapa 5c com a versão de teste;
    - melhorar o system prompt no AMP: o Luan não gostou do conteúdo de 03/11;
    - o tamanho máximo de arquivo.

No `CLAUDE.md`, troque a linha da tabela de documentação:

```markdown
| `amp/revisao_de_listas/` | o workflow do n8n da Revisão no AMP: o pedido ao agente (`pedido.md`, onde se melhora o agente), o gerador do `.json` e o LEIA-ME (ligar no n8n e o que fazer quando falha) |
```

por:

```markdown
| `amp/revisao_de_listas/` | a Revisão no AMP: o agente mora no AMP (`agente.md` é a cópia; melhora-se lá), o gerador do workflow do n8n e o LEIA-ME (criar o agente, ligar o workflow, testar pelo PowerShell e o que fazer quando falha) |
```

Em `docs/refatoracao/PENDENCIAS.md`:
- **Na linha de 2026-10-27** "Testes de plataforma do AMP...", ponha no começo da descrição:
  `**RESOLVIDO em 2026-11-03 (o S5): o agente do AMP, chamado pelo nó AMP Agent num workflow com webhook, leu os dois PDFs e o _STATUS_PMIB e devolveu o HTML (testes 3, 4 e de produção, desenho da peça 2 v2, §2). Fica aberto o tamanho: ver a linha de 2026-11-03.**`
- **No fim da tabela,** acrescente:
  `| 2026-11-03 | Peça 2 v2 (os arquivos vão ao agente) | **O tamanho máximo dos arquivos não é conhecido.** O n8n aceita 16 MB por pedido no padrão (N8N_PAYLOAD_SIZE_MAX), e o limite do agente do AMP não foi medido; o teste de 03/11 mandou 1,85 MB. Uma lista grande pode falhar com HTTP 413 ou erro do agente; o log diz o tamanho de cada arquivo. | Etapa 5c, com uma lista grande |`

- [ ] **Step 5: A verificação final e o push**

Run:

```bash
bash scripts/check.sh
python -m ruff check .
python -m pyflakes frontend.py
QT_QPA_PLATFORM=offscreen python frontend.py --smoke
grep -rn "pedido.md\|AMP_WEBHOOK_URL\|\.revisar(\|\.eco(" --include=*.py --include=*.md sigft tests amp docs/base-conhecimento docs/ROTEIRO_DE_TESTE.md CLAUDE.md
```

Expected:
- as quatro primeiras ficam verdes;
- o `grep` só acha as menções históricas (o desenho de 27/10 e o plano de 27/10) e a adoção dos
  nomes antigos (`antigas=("AMP_WEBHOOK_URL", ...)` na aba e nos testes).

```bash
git add amp/revisao_de_listas/LEIA-ME.md docs/base-conhecimento/14-aconex-e-conferencia-de-revisoes.md docs/ROTEIRO_DE_TESTE.md docs/ACONEX_AO_VIVO.md CLAUDE.md docs/refatoracao/PENDENCIAS.md
git commit -m "Documentacao da peca 2 v2: LEIA-ME, base de conhecimento, roteiro 5c e pendencias"
git push -u origin claude/busy-euler-2qaydu
```

---

### Task 7: A versão de teste (só com o OK do Luan)

Não se faz sozinho: lançar uma versão de teste publica um Release e chega ao PC da GE pela
atualização automática.

- [ ] **Step 1:** Perguntar ao Luan se pode lançar a versão de teste com a peça 2 v2.
- [ ] **Step 2:** Com o OK, usar a skill `sigft-lancar-versao`. Ela escolhe o número, abre o bloco do
  `CHANGELOG.md`, escrito para quem usa o SIG-FT, e dispara o Release.
- [ ] **Step 3:** No PC da GE, com **Versões de teste** marcada, a Etapa 5c do roteiro.

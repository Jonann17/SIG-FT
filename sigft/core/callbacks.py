r"""
sigft/core/callbacks.py — protocolo UI<->serviço: log estruturado, pause,
ask, progress (Checkpoint 1.4 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.4, diagnóstico
seção 1.4 ("Frontend monolítico" — "console + `log()` thread-safe (3
variantes de implementação!)") e princípio nº 2 da arquitetura-alvo: "UI
nunca contém regra de negócio; serviço nunca importa tkinter. Comunicação só
por callbacks (`log`, `pause`, `ask`, `progress`) definidos em
`core/callbacks.py`."

`UICallbacks` é o contrato ÚNICO que um serviço (`*_backend.py` hoje,
`sigft/services/*` depois do CP 4.1) usa para falar com QUALQUER UI (a UI
CustomTkinter de hoje, ou uma futura) sem conhecer nada dela:

  - `log(msg, nivel="info", contexto=None)`: já nasce ESTRUTURADO (nível +
    contexto opcional), mas a UI de HOJE continua imprimindo exatamente como
    sempre (`> msg`) — nível/contexto ficam disponíveis, sem consumidor
    ainda, para o CP 4.4 (padronização/enriquecimento de logs) e para o
    espelho em arquivo `logs/sigft_YYYYMMDD.log`.
  - `pause(motivo=None)`: bloqueia a automação até a UI liberar. NENHUM dos
    2 pilotos deste checkpoint (`lmr_backend`, `apagar_lmr_backend`) usa
    pause hoje — nasce aqui para uso futuro (ex.: CP 2.2
    `PMIBPortal.aguardar_login_manual`). Já existe um `callback_pause(motivo)`
    de assinatura antiga em `upload_conditions_backend`
    (`processar_lista`/`safe_save_with_pause`) e `upload_tech_specs_backend`
    (`processar_lista`/`executar_pipeline_rpa`) — fora do escopo de migração
    deste checkpoint (só `lmr`/`apagar_lmr` migram agora), mas `from_legacy()`
    abaixo já sabe adaptar esse formato para quando esses módulos migrarem.
  - `ask(pergunta, *, titulo=None) -> bool`: confirmação sim/não. Mapeia 1:1
    com o `callback_ask(titulo, pergunta) -> bool` que já existe em
    `lmr_backend.py` — MESMA informação, ORDEM DIFERENTE: o callback legado é
    posicional `(titulo, pergunta)`; aqui `pergunta` é o 1º argumento
    posicional e `titulo` vira keyword-only opcional.
  - `progress(atual, total, *, item=None)`: sinaliza progresso
    (barra/percentual). Não é exercitado pelos 2 pilotos deste checkpoint —
    opcional, sem equivalente legado hoje em nenhum módulo.

`callback_input` (texto livre — "pergunta X, devolve a string digitada pelo
usuário", usado hoje só por `lmr_backend._processar_ficha_lmr_interna` via
`simpledialog.askstring`) DELIBERADAMENTE NÃO faz parte de `UICallbacks`.
Não é um "ask" (não devolve `bool`) nem um "log"/"pause"/"progress" — é uma
4ª categoria de interação ("pedir texto") que hoje tem exatamente UM
consumidor no sistema inteiro. Inventar um 5º campo (ou generalizar `ask`
com um parâmetro tipo `kind`/`tipo`) para cobrir um único call site seria
especular sobre uma forma ainda não validada por um segundo caso de uso
real — decisão do arquiteto (ver especificação deste checkpoint).
`callback_input` continua sendo repassado CRU, à parte de `callbacks`, por
quem precisa dele — ver `lmr_backend.processar_lista`/
`_processar_ficha_lmr_interna` — e a pendência registrada em
`docs/refatoracao/PENDENCIAS.md` (unificação adiada para quando mais
módulos precisarem "pedir texto ao usuário").

Defaults SEM-OP seguros (via `__post_init__`) — o corpo de um serviço pode
chamar `self.callbacks.log(...)`, `.ask(...)`, `.pause(...)`, `.progress(...)`
INCONDICIONALMENTE, sem nenhum `if callback_x:` espalhado pelo código:
  - `log` é o único campo OBRIGATÓRIO (sem default) — é o mínimo que
    qualquer UI real já fornece hoje (nenhum dos ~12 módulos jamais chamou
    um serviço sem `callback_log`). `from_legacy()` (abaixo) garante um
    `log` no-op mesmo quando nem isso for passado — só ela, não o
    `__post_init__` da dataclass, que mantém `log` genuinamente obrigatório.
  - `ask` sem provedor -> retorna `False`. Reproduz EXATAMENTE o
    comportamento de hoje quando `callback_ask` está ausente: hoje o bloco
    `if callback_ask: ...` inteiro é pulado (nenhum desvio custom
    acontece); com `ask()` sempre-presente devolvendo `False`, qualquer
    `if callbacks.ask(...):` também nunca entra no desvio — mesmo
    resultado final, por um caminho diferente (chamar sempre, em vez de
    checar truthy antes de chamar).
  - `pause`/`progress` sem provedor -> não fazem nada (retornam `None`).

Só stdlib (`dataclasses`, `typing`) — nenhuma dependência de UI (nem
tkinter, nem customtkinter). Importável no ambiente de teste sem stub
nenhum (ver tests/conftest.py) e por qualquer serviço, sem acoplar o
serviço a uma UI concreta — ver tests/test_callbacks.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class UICallbacks:
    """Contrato único de comunicação UI<->serviço (ver docstring do módulo
    para o racional completo de cada campo).

      log(msg, nivel="info", contexto=None) -> None  — OBRIGATÓRIO.
      pause(motivo=None) -> None                      — opcional, no-op.
      ask(pergunta, *, titulo=None) -> bool            — opcional, no-op
        devolve `False`.
      progress(atual, total, *, item=None) -> None     — opcional, no-op.

    `pause`/`ask`/`progress` ausentes (`None`) são substituídos em
    `__post_init__` por implementações no-op seguras — depois de construído,
    um `UICallbacks` NUNCA tem `pause`/`ask`/`progress` valendo `None`; os 4
    campos são sempre chamáveis diretamente.
    """

    log: Callable[..., None]
    pause: Callable[..., None] | None = None
    ask: Callable[..., bool] | None = None
    progress: Callable[..., None] | None = None

    def __post_init__(self) -> None:
        if self.pause is None:
            self.pause = _noop_pause
        if self.ask is None:
            self.ask = _noop_ask
        if self.progress is None:
            self.progress = _noop_progress


# ---------------------------------------------------------------------------
# No-ops usados como default de `pause`/`ask`/`progress` (`__post_init__`
# acima) e como `log` default de `from_legacy()` quando nem `callback_log`
# foi passado. `*args, **kwargs` propositalmente permissivo — um no-op deve
# aceitar QUALQUER forma de chamada que o protocolo documentado permitir,
# sem levantar `TypeError`.
# ---------------------------------------------------------------------------
def _noop_log(*_args: object, **_kwargs: object) -> None:
    return None


def _noop_pause(*_args: object, **_kwargs: object) -> None:
    return None


def _noop_ask(*_args: object, **_kwargs: object) -> bool:
    return False


def _noop_progress(*_args: object, **_kwargs: object) -> None:
    return None


# ---------------------------------------------------------------------------
# Adaptadores: assinatura ANTIGA (callback avulso) -> assinatura NOVA
# (campo de UICallbacks). Cada um fecha sobre o callback legado recebido e
# devolve uma função na forma nova.
# ---------------------------------------------------------------------------
def _adapt_legacy_log(callback_log: Callable[[str], None]) -> Callable[..., None]:
    """`callback_log(txt)` (1 posicional) -> `log(msg, nivel="info",
    contexto=None)`. `nivel`/`contexto` são aceitos mas ainda IGNORADOS — a
    UI de hoje só sabe imprimir `txt` cru (`> {txt}`); ver docstring do
    módulo."""

    def _log(msg: object, nivel: str = "info", contexto: object | None = None) -> None:
        callback_log(msg)

    return _log


def _adapt_legacy_ask(callback_ask: Callable[[str, str], bool]) -> Callable[..., bool]:
    """`callback_ask(titulo, pergunta) -> bool` (posicional, NESTA ordem) ->
    `ask(pergunta, *, titulo=None) -> bool`. Note a INVERSÃO de ordem entre
    as duas assinaturas — é o adaptador que resolve isso; quem chama a
    versão nova nunca precisa pensar na ordem antiga."""

    def _ask(pergunta: object, *, titulo: object | None = None) -> bool:
        return callback_ask(titulo, pergunta)

    return _ask


def _adapt_legacy_pause(callback_pause: Callable[[object], None]) -> Callable[..., None]:
    """`callback_pause(motivo)` (1 posicional obrigatório — convenção já em
    uso por `upload_conditions_backend`/`upload_tech_specs_backend`, fora do
    escopo de migração deste checkpoint) -> `pause(motivo=None)`."""

    def _pause(motivo: object | None = None) -> None:
        callback_pause(motivo)

    return _pause


def from_legacy(
    *,
    callback_log: Callable[[str], None] | None = None,
    callback_ask: Callable[[str, str], bool] | None = None,
    callback_pause: Callable[[object], None] | None = None,
    callback_progress: Callable[..., None] | None = None,
) -> UICallbacks:
    """Constrói um `UICallbacks` a partir dos callbacks avulsos de
    ASSINATURA ANTIGA que os serviços já recebiam antes deste checkpoint —
    os "aliases retrocompatíveis" citados no plano. Uso típico, no topo de
    cada método migrado:

        callbacks = callbacks or from_legacy(
            callback_log=callback_log, callback_ask=callback_ask
        )

    Nenhum parâmetro é obrigatório — `from_legacy()` sem nenhum argumento
    devolve um `UICallbacks` inteiramente no-op e seguro (equivalente a
    todos os `callback_x` estarem ausentes hoje: nada é impresso, `ask`
    sempre devolve `False`, `pause`/`progress` não fazem nada).

    `callback_input` (texto livre) DELIBERADAMENTE NÃO é parâmetro desta
    função — não faz parte de `UICallbacks`; ver docstring do módulo e
    `docs/refatoracao/PENDENCIAS.md`. Continua sendo repassado cru pelo
    chamador, à parte de `callbacks`.

    `callback_pause`/`callback_progress` não são usados pelos 2 pilotos
    deste checkpoint (`lmr_backend`, `apagar_lmr_backend`) — aceitos aqui
    para que esta MESMA função sirva consumidores futuros que já têm (ou
    venham a ter) esses callbacks; ver docstring do módulo.
    """
    return UICallbacks(
        log=_adapt_legacy_log(callback_log) if callback_log is not None else _noop_log,
        pause=_adapt_legacy_pause(callback_pause) if callback_pause is not None else None,
        ask=_adapt_legacy_ask(callback_ask) if callback_ask is not None else None,
        progress=callback_progress,
    )

r"""
sigft/core/excel/locking.py — retry unificado de `PermissionError` ao salvar
planilha (Checkpoint 1.3 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.3, diagnóstico
seção 1.2: "Retry de `PermissionError` (arquivo aberto no Excel) | 4 variantes
de laço, cada uma com UX diferente". Levantamento concreto por grep (7
ocorrências, 4 variantes de UX — mapeamento linha a linha em
docs/refatoracao/PENDENCIAS.md):

  1. INTERATIVO via `callback_ask(motivo) -> bool`: laço SEM limite de
     tentativas enquanto o usuário responder "sim" no popup.
     `upload_conditions_backend.UploadAutomation.atualizar_status_excel`
     (1 ocorrência).
  2. INTERATIVO via `callback_retry_lock() -> bool` (sem argumento — mesmo
     espírito do (1), assinatura de callback diferente).
     `pmib_manager_backend.PMIBManager.executar_fluxo` (2 ocorrências).
  3. AUTO-RETRY com `time.sleep` fixo (5s), SEM limite de tentativas, sem
     callback nenhum.
     `upload_ficha_duplicada.AtualizadorStatusPMIB.atualizar_ficha_concluida`
     (1 ocorrência).
  4. LOG + SAI na primeira falha, SEM nenhuma retentativa.
     `upload_conditions_backend.ConditionsProcessor.anexar_a_arquivo_existente`
     e `cria_fichas_no_pmib_v1_backend.DataManager.atualizar_excel_final`
     (2 ocorrências).

(A 7ª ocorrência de UX "log + sai", em
`upload_ficha_duplicada.GerenciadorFilaPMIB.montar_fila_processamento`, NÃO é
migrada para este módulo: aquele `except PermissionError` protege uma
LEITURA — `pd.read_excel` —, não um `wb.save(path)`; ver nota abaixo e
docs/refatoracao/PENDENCIAS.md.)

Além dos 4 sites acima (que preservam sua UX ORIGINAL exatamente, usando um
`on_locked` sob medida), `upload_tech_specs_backend.executar_pipeline_rpa`
GANHA retry pela primeira vez neste checkpoint (o código original não tinha
NENHUM `except PermissionError` — uma falha de lock caía direto no `except
Exception` genérico, sem nenhuma tentativa de recuperação); ver o comentário
"trate o save dele também" no checkpoint. Esse consumidor usa a política
DEFAULT deste módulo (`on_locked=None`, `logger=callback_log`,
`max_attempts` finito) — comportamento novo, não uma UX preexistente a
preservar.

`save_with_retry()` envolve *apenas* a chamada `wb.save(path)` — é aí que o
lock do Excel realmente morde; `load_workbook()`/`pd.read_excel()` de um
arquivo aberto no Excel geralmente FUNCIONAM (o Excel mantém um arquivo de
lock `~$nome.xlsx` separado; a exclusividade real só é exigida na escrita).
Isso implica uma simplificação de comportamento deliberada e documentada:
os laços originais de `atualizar_status_excel` e `atualizar_ficha_concluida`
recarregavam o workbook INTEIRO (e reaplicavam a busca de cabeçalho/edição de
célula) a cada retentativa, dentro do próprio `while`; a versão migrada
carrega e modifica UMA vez só, e só o `wb.save(path)` retenta. No cenário
real (usuário fecha o Excel e clica "tentar novamente") o resultado
observável é idêntico; a diferença é só teórica — ver
docs/refatoracao/PENDENCIAS.md.

Só stdlib (`time`) — importável no ambiente de teste, que não tem
openpyxl/pandas instalados (ver tests/conftest.py). `wb` é duck-typed: só
precisa responder a `.save(path)`. Funciona com `openpyxl.Workbook` (uso
mais comum) mas também com qualquer adaptador que exponha esse método — ex.:
`anexar_a_arquivo_existente`/`atualizar_excel_final` adaptam
`pandas.DataFrame.to_excel(path, index=False)` a essa interface com um
`types.SimpleNamespace(save=lambda caminho: df.to_excel(caminho, index=False))`.
Testável por design: injete `sleep_fn` (no-op nos testes) e passe um `wb`
falso que levanta `PermissionError` N vezes e depois "salva" de verdade — ver
`tests/test_locking.py`.
"""

from __future__ import annotations

import time
from typing import Any, Callable

# Assinatura do callback de decisão a cada `PermissionError`. Ver contrato
# completo no docstring de `save_with_retry`.
OnLockedCallback = Callable[[int, PermissionError], "bool | None"]
SleepFn = Callable[[float], None]
LoggerFn = Callable[[str], None]

# 5s: o único valor numérico concreto que já existia em produção para esse
# propósito (`AtualizadorStatusPMIB.atualizar_ficha_concluida`, variante 3
# acima) — vira o default deste módulo para os consumidores que não têm (ou
# não precisam de) uma UX própria (ex.: `upload_tech_specs`, que nunca teve
# retry nenhum).
DEFAULT_SLEEP_SECONDS = 5.0


def save_with_retry(
    wb: Any,
    path: Any,
    *,
    on_locked: OnLockedCallback | None = None,
    max_attempts: int | None = None,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    sleep_fn: SleepFn = time.sleep,
    logger: LoggerFn | None = None,
) -> bool:
    r"""Chama `wb.save(path)`, retentando em caso de `PermissionError`
    (arquivo aberto no Excel) conforme a política escolhida por
    `on_locked`/`max_attempts`.

    Parâmetros:
      wb: objeto duck-typed com `.save(path)` (um `openpyxl.Workbook` de
        verdade, ou qualquer adaptador equivalente).
      path: repassado tal qual para `wb.save(path)` a cada tentativa.
      on_locked: `(attempt, exc) -> bool | None`, chamado a cada
        `PermissionError` capturado (ANTES de checar `max_attempts` como
        segurança adicional — ver abaixo). `attempt` é o número (1-based) da
        tentativa que ACABOU de falhar; `exc` é a exceção capturada.
          - Retorna `True`  -> retenta IMEDIATAMENTE (sem chamar `sleep_fn`;
            se o callback quiser pausar, a pausa é responsabilidade DELE —
            ex.: um `callback_ask` que já bloqueia numa caixa de diálogo, ou
            um `time.sleep` explícito dentro do próprio callback antes de
            retornar `True`).
          - Retorna `False` (ou qualquer valor falsy não-`None`) -> ABORTA:
            a última `PermissionError` é RE-LEVANTADA (propagada ao
            chamador). Isto é o que permite que cada call site preserve seu
            `except PermissionError:` ORIGINAL inalterado — `on_locked`
            decide SE retenta; o que acontece na desistência continua sendo
            escolha de quem chamou `save_with_retry`.
          - Retorna `None` (ou `on_locked` não foi passado, isto é,
            `on_locked=None`) -> política DEFAULT: chama `logger(mensagem)`
            (se `logger` foi passado) e depois `sleep_fn(sleep_seconds)`,
            então retenta. Um `on_locked` customizado também pode devolver
            `None` deliberadamente para "fazer seu próprio log e delegar a
            pausa/retentativa para a política default" (ver
            `upload_tech_specs_backend` — usa só `logger`/`max_attempts`,
            sem `on_locked` nenhum).
      max_attempts: teto DURO de tentativas (conta a 1ª chamada de
        `wb.save` como tentativa 1) — verificado ANTES de consultar
        `on_locked`, ou seja, é um limite de segurança que prevalece mesmo
        que `on_locked` continue devolvendo `True`. `max_attempts=1`
        significa "nunca retentar" (equivale à variante 4 do diagnóstico:
        "log + sai" — a 1ª `PermissionError` já esgota o teto e é
        relevantada sem sequer consultar `on_locked`). `max_attempts=None`
        (default) = sem teto, junto com `on_locked=None`
        reproduz a variante 3 do diagnóstico (retry indefinido com sleep
        fixo); junto com um `on_locked` customizado reproduz as variantes 1
        e 2 (retry indefinido enquanto o usuário disser "sim").
      sleep_seconds: segundos passados a `sleep_fn` na política default.
      sleep_fn: função de espera, `(segundos) -> None`; default
        `time.sleep`. Injetável nos testes (passe uma função no-op).
      logger: `(mensagem) -> None` opcional, chamado pela política default
        (quando `on_locked` é `None` OU devolve `None`) antes de dormir.
        Callbacks customizados que já fazem seu PRÓPRIO log (para preservar
        uma mensagem legada específica) tipicamente NÃO precisam deste
        parâmetro — fazem o log dentro do próprio `on_locked`.

    Retorna `True` quando `wb.save(path)` finalmente tem sucesso. Nunca
    retorna `False` — desistência é sempre uma `PermissionError`
    RE-LEVANTADA (ver `on_locked` acima), para que o chamador trate a
    desistência com o `except PermissionError:` que já tinha antes deste
    checkpoint.

    Uma exceção que NÃO seja `PermissionError` levantada por `wb.save`
    propaga imediatamente, sem retry e sem consultar `on_locked` — mesmo
    comportamento de todos os laços originais (só `PermissionError` tinha
    tratamento especial; qualquer outra exceção sempre foi fatal para a
    tentativa de salvamento).
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            wb.save(path)
        except PermissionError as exc:
            if max_attempts is not None and attempt >= max_attempts:
                raise

            decisao = on_locked(attempt, exc) if on_locked is not None else None

            if decisao is None:
                if logger is not None:
                    logger(
                        f"Arquivo Excel bloqueado (tentativa {attempt}); "
                        f"aguardando {sleep_seconds:g}s antes de tentar "
                        "novamente..."
                    )
                sleep_fn(sleep_seconds)
            elif not decisao:
                raise
            # `decisao` truthy (True custom) OU `decisao is None` (política
            # default, já esperou acima): cai para o topo do `while` e
            # tenta salvar de novo.
        else:
            return True


def salvar_perguntando(
    wb: Any,
    path: Any,
    *,
    retry_lock: Callable[..., bool] | None = None,
    logger: LoggerFn | None = None,
) -> bool:
    r"""`save_with_retry` ligado ao canal `retry_lock` do `UICallbacks`.

    [CP D] Existe para que os pontos de gravação não precisem repetir o mesmo
    laço de adaptação. Antes deste checkpoint, 7 lugares em 5 serviços
    chamavam `wb.save(path)` direto: com a planilha aberta no Excel, o
    `PermissionError` subia sem que ninguém perguntasse nada ao usuário, e o
    lote morria sem explicar o motivo.

    `retry_lock(caminho) -> bool` é o canal do CP C: `True` = tentar de novo
    (o usuário fechou o arquivo), `False` = desistir. Ausente, o
    comportamento é EXATAMENTE o de antes — uma tentativa, e o
    `PermissionError` sobe. É o que torna esta mudança segura de aplicar em
    massa: quem não passa o canal não muda de comportamento.

    Devolve `True` se salvou. Deixa o `PermissionError` subir quando o usuário
    escolhe desistir, para que o chamador registre a falha do jeito dele.
    """

    def _on_locked(_tentativa: int, _exc: BaseException) -> bool:
        if retry_lock is None:
            return False
        return bool(retry_lock(path))

    return save_with_retry(wb, path, on_locked=_on_locked, logger=logger)

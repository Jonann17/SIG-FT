r"""
Testes do Checkpoint 4.4 (2ª parte) — `sigft/services/autospec.py`,
`AutoSpecCore.process_queue`, migrado para `RelatorioLote` (padrão único de
log de lote).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.4. `process_queue`
é um GENERATOR consumido por `frontend.py` como `for msg in
core.process_queue(...): self.log(msg)` -- sem nenhum pattern-match em valor
sentinela (diferente de `translator.processar_arquivo`, que por isso NÃO foi
migrado neste checkpoint -- ver PENDENCIAS.md). Isso torna seguro acrescentar
linhas novas (início/resumo do `RelatorioLote`) ao fluxo de `yield` já
existente, sem quebrar o consumidor.

`AutoSpecCore` é instanciado via `__new__` (sem rodar `__init__`, que exige
`gemini_key`/`get_llm(...)`) -- os 4 métodos que `process_queue` chama
(`analyze_sheet`/`retrieve_context`/`generate_ai_response`/`fill_save`) são
substituídos por fakes simples no próprio objeto, isolando o teste de
openpyxl/IA/rede real (mesmo espírito de `tests/test_lmr_indice_except.py`:
testar só o que é NOSSO, sem depender de SDK pesado).
"""
from __future__ import annotations

from sigft.services.autospec import AutoSpecCore


def _core_fake(comportamentos):
    """`comportamentos`: dict nome-do-arquivo -> "completo" | "ok" | Exception.

    `analyze_sheet` decide o comportamento pelo nome do arquivo (item da
    fila); os outros 3 métodos são fakes triviais que só precisam devolver
    algo do formato certo para `process_queue` conseguir prosseguir até o
    `fill_save`."""
    core = AutoSpecCore.__new__(AutoSpecCore)

    def _analyze_sheet(ficha, status_pmib_path):
        comportamento = comportamentos[ficha]
        if comportamento == "completo":
            return "wb-fake", {}, "", "", "", ""
        if isinstance(comportamento, Exception):
            raise comportamento
        return "wb-fake", {"campo_x": {"type": "text", "desc": "Campo X", "ref": "H1"}}, "txt", "fab", "desc", "cod"

    core.analyze_sheet = _analyze_sheet
    core.retrieve_context = lambda *a, **k: ("contexto", [])
    core.generate_ai_response = lambda *a, **k: {"campo_x": "valor"}
    # `**k` tolera os kwargs que os métodos reais ganharam em 2026-08-11
    # (`callbacks=`, para os logs pararem de sumir no stdout) — o stub não
    # precisa usá-los, só não pode recusá-los.
    core.fill_save = lambda wb, ficha, ai_data, missing, **k: ficha.replace(".xlsx", "_completed.xlsx")
    return core


def _fila(*nomes):
    return [{"sheet": nome, "refs": []} for nome in nomes]


# =============================================================================
# Início de lote: total + contexto (exigência nº 1 do CP 4.4)
# =============================================================================

def test_inicio_de_lote_mostra_total_e_status_pmib_no_contexto():
    core = _core_fake({"A.xlsx": "ok"})

    linhas = list(core.process_queue(_fila("A.xlsx"), status_pmib_path="/x/_STATUS_PMIB.xlsx"))
    texto = "\n".join(linhas)

    assert "AutoSpec" in texto
    assert "1 item(ns)" in texto
    assert "status_pmib: /x/_STATUS_PMIB.xlsx" in texto


# =============================================================================
# Por item: identificador aparece na linha (exigência nº 2)
# =============================================================================

def test_ficha_completa_e_pulada_com_motivo():
    core = _core_fake({"A.xlsx": "completo"})

    linhas = list(core.process_queue(_fila("A.xlsx"), status_pmib_path=None))
    texto = "\n".join(linhas)

    assert "⏭️ A.xlsx" in texto
    assert "ficha já completa" in texto


def test_ficha_processada_com_sucesso_mostra_identificador_e_arquivo_salvo():
    core = _core_fake({"B.xlsx": "ok"})

    linhas = list(core.process_queue(_fila("B.xlsx"), status_pmib_path=None))
    texto = "\n".join(linhas)

    assert "✅ B.xlsx" in texto
    assert "B_completed.xlsx" in texto
    # As mensagens de progresso ORIGINAIS continuam aparecendo (nada foi
    # removido, só ganharam vizinhas).
    assert " -> Salvo: B_completed.xlsx" in texto
    # 2026-08-11: a mensagem deixou de citar o provedor. O modelo vem de
    # config.LLM_TASKS/seleção da UI e pode ser OpenRouter ou o endpoint da
    # empresa — mensagem que nomeia "Gemini" envelhece igual à do guard.
    assert " -> Consultando a IA..." in texto
    assert "Gemini" not in texto


# =============================================================================
# Resumo final: contagens + falhas listadas (exigência nº 4) e resiliência
# =============================================================================

def test_item_com_erro_vira_falha_e_nao_derruba_os_outros():
    core = _core_fake(
        {
            "A.xlsx": "completo",
            "B.xlsx": "ok",
            "C.xlsx": RuntimeError("PDM de origem não encontrado"),
        }
    )

    linhas = list(core.process_queue(_fila("A.xlsx", "B.xlsx", "C.xlsx"), status_pmib_path=None))
    texto = "\n".join(linhas)

    # Os 3 itens foram tentados -- a falha do C não impediu B (nem A).
    assert "⏭️ A.xlsx" in texto
    assert "✅ B.xlsx" in texto
    assert "❌ C.xlsx" in texto
    assert "RuntimeError: PDM de origem não encontrado" in texto
    # A mensagem de erro ORIGINAL (` -> ERRO: ...`) continua presente.
    assert " -> ERRO: PDM de origem não encontrado" in texto

    # Resumo final obrigatório, com a falha LISTADA (não só contada).
    assert "── Resumo: AutoSpec — preenchendo fichas técnicas ──" in texto
    assert "1 sucesso(s)" in texto
    assert "1 falha(s)" in texto
    assert "1 pulado(s)" in texto
    assert "Falhas:" in texto
    assert "C.xlsx: RuntimeError: PDM de origem não encontrado" in texto
    assert "Tempo total:" in texto


def test_fila_vazia_nao_quebra_e_ainda_emite_inicio_e_resumo():
    core = _core_fake({})

    linhas = list(core.process_queue([], status_pmib_path=None))
    texto = "\n".join(linhas)

    assert "0 item(ns)" in texto
    assert "0 sucesso(s)" in texto
    assert "── Resumo:" in texto

r"""
Testes do Checkpoint 3.4 — `sigft/core/llm/usage.py` ("UsageTracker":
rastreamento de uso/custo de IA).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.4, e
docs/refatoracao/MODELOS_IA.md §2 (tabela de preços). Cobre, nesta ordem:

  A. `estimar_custo` -- função PURA, a mais testada deste módulo: real vs.
     estimado (aqui só o lado "estimado" -- o "real" é decisão de
     `registrar()`, seção B), casamento de slug (com/sem `"/"`), modelo
     desconhecido, tokens ausentes, tokens zero.
  B. `registrar` -- campos gravados, custo real/estimado, append de várias
     linhas, criação de pasta, `SIGFT_DESABILITAR_USAGE`, e o teste mais
     importante da Decisão 1: falha de escrita NÃO levanta.
  C. `ler_registros` -- arquivo ausente/vazio, tolerância a linha
     corrompida/em branco/não-objeto no meio do arquivo.
  D. `usage_report` -- as 2 perguntas do *Aceite* do plano ("qual modelo
     gasta mais na MESMA tarefa" / "qual módulo do SIG-FT gasta mais"),
     `custo_estimado_parcial`, contagem de falhas, agregação por dia,
     `registros=` injetável (evita I/O).
  E. `formatar_relatorio_texto` -- nunca quebra, mesmo com relatório vazio.
  F. Sanidade de `sigft.config.PASTA_LOGS`/`ARQUIVO_USO_LLM` (CP 3.4,
     aditivos em `sigft/config.py`).

NENHUM teste deste arquivo escreve no `logs/` real do repositório: todo
teste que exercita escrita passa `caminho=` explícito para dentro de
`tmp_path` (nunca usa o default `config.ARQUIVO_USO_LLM`). A suíte inteira
também religa `SIGFT_DESABILITAR_USAGE=1` por padrão via uma fixture
`autouse` em `tests/conftest.py` -- os testes daqui que precisam de escrita
de verdade fazem `monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE,
raising=False)` como a PRIMEIRA linha do próprio corpo do teste (nunca
dentro de uma fixture -- evita depender de ordem de instanciação entre
fixtures de arquivos diferentes; o corpo do teste sempre roda DEPOIS que
toda fixture já terminou o setup, então é 100% determinístico).
"""
import json
import os
from datetime import datetime

import pytest

from sigft import config
from sigft.core.llm import usage


# =============================================================================
# Helper
# =============================================================================
def _registro(**overrides) -> dict:
    """Um registro "de exemplo" completo e internamente consistente, para os
    testes de `usage_report`/`formatar_relatorio_texto` (que não precisam de
    `registrar()`/I/O -- constroem o dict diretamente)."""
    base = {
        "timestamp": "2026-08-01T10:00:00",
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
        "tarefa": "condicoes",
        "modulo": "upload_conditions_backend",
        "tokens_in": 100,
        "tokens_out": 200,
        "custo_usd": 0.01,
        "custo_estimado": False,
        "duracao_s": 1.0,
        "sucesso": True,
        "erro": None,
    }
    base.update(overrides)
    return base


# =============================================================================
# A. estimar_custo
# =============================================================================
def test_modelo_conhecido_exato_calcula_custo_pela_formula(monkeypatch):
    monkeypatch.setitem(config.LLM_PRECOS_USD_POR_1M, "modelo-teste", {"input": 1.0, "output": 2.0})

    custo, estimado = usage.estimar_custo("modelo-teste", 1_000_000, 500_000)

    assert custo == pytest.approx(1.0 * 1.0 + 0.5 * 2.0)
    assert estimado is True


def test_modelo_real_da_tabela_funciona_sem_monkeypatch():
    # Sanidade contra a tabela REAL de `sigft/config.py` (seed do
    # MODELOS_IA.md §2) -- gemini-3-flash-preview: $0,50 input / $3,00 output.
    custo, estimado = usage.estimar_custo("gemini-3-flash-preview", 2_000_000, 1_000_000)

    assert custo == pytest.approx(2.0 * 0.50 + 1.0 * 3.00)
    assert estimado is True


def test_slug_openrouter_grok_com_barra_casa_pela_parte_apos_a_ultima_barra():
    # "x-ai/grok-4.5" -- o MESMO slug de `config.LLM_FAVORITOS` -- precisa
    # casar com a entrada "grok-4.5" da tabela de preços.
    custo, estimado = usage.estimar_custo("x-ai/grok-4.5", 1_000_000, 1_000_000)

    assert custo == pytest.approx(2.00 + 6.00)
    assert estimado is True


def test_slug_openrouter_minimax_com_barra_tambem_casa():
    custo, estimado = usage.estimar_custo("minimax/minimax-m3", 1_000_000, 1_000_000)

    assert custo == pytest.approx(0.30 + 1.20)
    assert estimado is True


def test_modelo_desconhecido_sem_barra_devolve_none_none():
    assert usage.estimar_custo("modelo-que-nao-existe", 100, 100) == (None, None)


def test_modelo_desconhecido_com_barra_e_sufixo_tambem_desconhecido_devolve_none_none():
    assert usage.estimar_custo("acme/modelo-fantasma", 100, 100) == (None, None)


def test_barra_no_final_sem_sufixo_nao_quebra():
    assert usage.estimar_custo("x-ai/", 100, 100) == (None, None)


def test_tokens_in_ausente_devolve_none_none():
    assert usage.estimar_custo("gemini-3-flash-preview", None, 100) == (None, None)


def test_tokens_out_ausente_devolve_none_none():
    assert usage.estimar_custo("gemini-3-flash-preview", 100, None) == (None, None)


def test_tokens_ambos_ausentes_devolve_none_none():
    assert usage.estimar_custo("gemini-3-flash-preview", None, None) == (None, None)


def test_zero_tokens_e_valido_calcula_custo_zero_nao_none():
    # `0` é uma contagem VÁLIDA (não "ausente") -- diferente de `None`.
    custo, estimado = usage.estimar_custo("gemini-3-flash-preview", 0, 0)

    assert custo == 0.0
    assert estimado is True


def test_model_none_devolve_none_none():
    assert usage.estimar_custo(None, 100, 100) == (None, None)


def test_model_string_vazia_devolve_none_none():
    assert usage.estimar_custo("", 100, 100) == (None, None)


# =============================================================================
# B. registrar
# =============================================================================
def test_grava_registro_de_sucesso_com_todos_os_campos_esperados(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"
    momento_fixo = datetime(2026, 8, 1, 10, 30, 0)

    usage.registrar(
        provider="gemini",
        model="gemini-3-flash-preview",
        tarefa="condicoes",
        modulo="upload_conditions_backend",
        tokens_in=120,
        tokens_out=340,
        custo_usd=0.0123,
        duracao_s=1.5,
        sucesso=True,
        caminho=caminho,
        agora_fn=lambda: momento_fixo,
    )

    registros = usage.ler_registros(caminho=caminho)
    assert len(registros) == 1
    assert registros[0] == {
        "timestamp": "2026-08-01T10:30:00",
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
        "tarefa": "condicoes",
        "modulo": "upload_conditions_backend",
        "tokens_in": 120,
        "tokens_out": 340,
        "custo_usd": 0.0123,
        "custo_estimado": False,
        "duracao_s": 1.5,
        "sucesso": True,
        "erro": None,
    }


def test_grava_registro_de_falha_com_erro_e_sucesso_false(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"

    usage.registrar(
        provider="gemini", model="gemini-3.1-pro-preview", tarefa="categorizar_pdm",
        modulo="cria_fichas_no_pmib_v1_backend", tokens_in=None, tokens_out=None,
        custo_usd=None, duracao_s=12.3, sucesso=False,
        erro="RuntimeError: indisponível", caminho=caminho,
    )

    registro = usage.ler_registros(caminho=caminho)[0]
    assert registro["sucesso"] is False
    assert registro["erro"] == "RuntimeError: indisponível"
    assert registro["tokens_in"] is None
    assert registro["tokens_out"] is None
    assert registro["custo_usd"] is None
    assert registro["custo_estimado"] is None


def test_custo_usd_nao_none_e_gravado_como_real_sem_estimar(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"

    usage.registrar(
        provider="openrouter", model="x-ai/grok-4.5", tarefa="categorizar_pdm",
        modulo="cria_fichas_no_pmib_v1_backend", tokens_in=1000, tokens_out=500,
        custo_usd=0.0042, duracao_s=2.0, sucesso=True, caminho=caminho,
    )

    registro = usage.ler_registros(caminho=caminho)[0]
    assert registro["custo_usd"] == 0.0042
    assert registro["custo_estimado"] is False


def test_custo_usd_none_com_tokens_e_modelo_conhecido_estima(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"

    usage.registrar(
        provider="gemini", model="gemini-3-flash-preview", tarefa="tech_specs",
        modulo="upload_tech_specs_backend", tokens_in=1_000_000, tokens_out=1_000_000,
        custo_usd=None, duracao_s=3.0, sucesso=True, caminho=caminho,
    )

    registro = usage.ler_registros(caminho=caminho)[0]
    assert registro["custo_usd"] == pytest.approx(0.50 + 3.00)
    assert registro["custo_estimado"] is True


def test_custo_usd_none_sem_tokens_grava_null_e_estimado_null(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"

    usage.registrar(
        provider="gemini", model="gemini-3-flash-preview", tarefa="tech_specs", modulo=None,
        tokens_in=None, tokens_out=None, custo_usd=None, duracao_s=0.1, sucesso=False,
        erro="TimeoutError: x", caminho=caminho,
    )

    registro = usage.ler_registros(caminho=caminho)[0]
    assert registro["custo_usd"] is None
    assert registro["custo_estimado"] is None


def test_append_de_varias_chamadas_preserva_ordem(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"

    for i in range(3):
        usage.registrar(
            provider="gemini", model="m", tarefa=f"tarefa-{i}", modulo=None,
            tokens_in=1, tokens_out=1, custo_usd=0.0, duracao_s=0.0, sucesso=True, caminho=caminho,
        )

    registros = usage.ler_registros(caminho=caminho)
    assert [r["tarefa"] for r in registros] == ["tarefa-0", "tarefa-1", "tarefa-2"]


def test_cria_pasta_aninhada_se_nao_existir(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "a" / "b" / "c" / "uso.jsonl"
    assert not caminho.parent.exists()

    usage.registrar(
        provider="gemini", model="m", tarefa="t", modulo=None,
        tokens_in=1, tokens_out=1, custo_usd=0.0, duracao_s=0.0, sucesso=True, caminho=caminho,
    )

    assert caminho.exists()
    assert len(usage.ler_registros(caminho=caminho)) == 1


def test_env_var_desabilitar_usage_com_valor_exato_1_nao_grava_nada(tmp_path, monkeypatch):
    monkeypatch.setenv(usage.ENV_DESABILITAR_USAGE, "1")
    caminho = tmp_path / "uso.jsonl"

    usage.registrar(
        provider="gemini", model="m", tarefa="t", modulo=None,
        tokens_in=1, tokens_out=1, custo_usd=0.0, duracao_s=0.0, sucesso=True, caminho=caminho,
    )

    assert not caminho.exists()
    assert usage.ler_registros(caminho=caminho) == []


def test_env_var_com_valor_diferente_de_1_nao_desabilita(tmp_path, monkeypatch):
    monkeypatch.setenv(usage.ENV_DESABILITAR_USAGE, "true")  # só o valor EXATO "1" desliga
    caminho = tmp_path / "uso.jsonl"

    usage.registrar(
        provider="gemini", model="m", tarefa="t", modulo=None,
        tokens_in=1, tokens_out=1, custo_usd=0.0, duracao_s=0.0, sucesso=True, caminho=caminho,
    )

    assert len(usage.ler_registros(caminho=caminho)) == 1


def test_timestamp_usa_relogio_real_quando_agora_fn_ausente(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"

    usage.registrar(
        provider="gemini", model="m", tarefa="t", modulo=None,
        tokens_in=1, tokens_out=1, custo_usd=0.0, duracao_s=0.0, sucesso=True, caminho=caminho,
    )

    registro = usage.ler_registros(caminho=caminho)[0]
    timestamp = datetime.fromisoformat(registro["timestamp"])  # não levanta -- ISO 8601 válido
    assert timestamp.date() == datetime.now().date()


def test_falha_de_escrita_por_caminho_ser_uma_pasta_nao_levanta(tmp_path, monkeypatch):
    # Decisão 1 (a mais importante do checkpoint), teste dedicado: `caminho`
    # aponta para uma PASTA de verdade (não um arquivo) -- `open(caminho,
    # "a")` levanta `IsADirectoryError` de verdade -- `registrar()` precisa
    # ENGOLIR isso silenciosamente, nunca deixar propagar.
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)

    usage.registrar(  # não deve levantar
        provider="gemini", model="m", tarefa="t", modulo=None,
        tokens_in=1, tokens_out=1, custo_usd=0.0, duracao_s=0.0, sucesso=True,
        caminho=str(tmp_path),
    )
    # Chegar até aqui sem exceção já é o teste; nada mais a verificar.


def test_falha_de_serializacao_json_nao_levanta(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"

    class _NaoSerializavel:
        pass

    usage.registrar(  # custo_usd não-serializável -> json.dumps levanta TypeError internamente
        provider="gemini", model="m", tarefa="t", modulo=None,
        tokens_in=1, tokens_out=1, custo_usd=_NaoSerializavel(), duracao_s=0.0, sucesso=True,
        caminho=caminho,
    )

    # Não derrubou a chamada, e nenhuma linha "meio gravada" ficou no arquivo.
    assert usage.ler_registros(caminho=caminho) == []


# =============================================================================
# C. ler_registros
# =============================================================================
def test_ler_registros_arquivo_ausente_devolve_lista_vazia(tmp_path):
    assert usage.ler_registros(caminho=tmp_path / "nao-existe.jsonl") == []


def test_ler_registros_arquivo_vazio_devolve_lista_vazia(tmp_path):
    caminho = tmp_path / "vazio.jsonl"
    caminho.write_text("", encoding="utf-8")

    assert usage.ler_registros(caminho=caminho) == []


def test_ler_registros_le_de_volta_o_que_registrar_gravou(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "uso.jsonl"
    usage.registrar(
        provider="gemini", model="m1", tarefa="t1", modulo="mod1",
        tokens_in=1, tokens_out=2, custo_usd=0.1, duracao_s=1.0, sucesso=True, caminho=caminho,
    )
    usage.registrar(
        provider="gemini", model="m2", tarefa="t2", modulo="mod2",
        tokens_in=3, tokens_out=4, custo_usd=0.2, duracao_s=2.0, sucesso=True, caminho=caminho,
    )

    registros = usage.ler_registros(caminho=caminho)

    assert [r["model"] for r in registros] == ["m1", "m2"]


def test_pula_linha_corrompida_no_meio_sem_derrubar_as_demais(tmp_path):
    caminho = tmp_path / "uso.jsonl"
    linha_valida_1 = json.dumps({"tarefa": "a"})
    linha_valida_2 = json.dumps({"tarefa": "b"})
    caminho.write_text(
        linha_valida_1 + "\n"
        + '{"tarefa": "cortada no meio da escrita' + "\n"  # JSON inválido (escrita interrompida)
        + linha_valida_2 + "\n",
        encoding="utf-8",
    )

    registros = usage.ler_registros(caminho=caminho)

    assert [r["tarefa"] for r in registros] == ["a", "b"]


def test_pula_linhas_em_branco(tmp_path):
    caminho = tmp_path / "uso.jsonl"
    caminho.write_text('\n{"tarefa": "a"}\n\n   \n', encoding="utf-8")

    registros = usage.ler_registros(caminho=caminho)

    assert [r["tarefa"] for r in registros] == ["a"]


def test_pula_linha_json_valida_mas_que_nao_e_um_objeto(tmp_path):
    caminho = tmp_path / "uso.jsonl"
    caminho.write_text('42\n["a", "b"]\n{"tarefa": "a"}\n', encoding="utf-8")

    registros = usage.ler_registros(caminho=caminho)

    assert [r["tarefa"] for r in registros] == ["a"]


# =============================================================================
# D. usage_report
# =============================================================================
def test_aceite_qual_modelo_gasta_mais_na_mesma_tarefa():
    registros = [
        _registro(tarefa="condicoes", model="gemini-3-flash-preview", custo_usd=1.0),
        _registro(tarefa="condicoes", model="grok-4.5", custo_usd=5.0),
        # outra tarefa -- não deve interferir na comparação dentro de "condicoes"
        _registro(tarefa="tech_specs", model="grok-4.5", custo_usd=50.0),
    ]

    relatorio = usage.usage_report(registros=registros)

    por_modelo_na_tarefa = relatorio["por_tarefa_e_modelo"]["condicoes"]
    mais_caro = max(por_modelo_na_tarefa, key=lambda m: por_modelo_na_tarefa[m]["custo_usd"])
    assert mais_caro == "grok-4.5"
    assert por_modelo_na_tarefa["grok-4.5"]["custo_usd"] == pytest.approx(5.0)
    assert por_modelo_na_tarefa["gemini-3-flash-preview"]["custo_usd"] == pytest.approx(1.0)


def test_aceite_qual_modulo_do_sigft_gasta_mais():
    registros = [
        _registro(modulo="upload_conditions_backend", custo_usd=2.0),
        _registro(modulo="upload_tech_specs_backend", custo_usd=9.0),
        _registro(modulo="cria_fichas_no_pmib_v1_backend", custo_usd=1.0),
    ]

    relatorio = usage.usage_report(registros=registros)

    por_modulo = relatorio["por_modulo"]
    mais_caro = max(por_modulo, key=lambda m: por_modulo[m]["custo_usd"])
    assert mais_caro == "upload_tech_specs_backend"


def test_agregacao_por_modelo_junta_tarefas_diferentes():
    registros = [
        _registro(tarefa="condicoes", model="grok-4.5", custo_usd=1.0),
        _registro(tarefa="tech_specs", model="grok-4.5", custo_usd=2.0),
    ]

    relatorio = usage.usage_report(registros=registros)

    assert relatorio["por_modelo"]["grok-4.5"]["chamadas"] == 2
    assert relatorio["por_modelo"]["grok-4.5"]["custo_usd"] == pytest.approx(3.0)


def test_agregacao_por_dia_usa_10_primeiros_caracteres_do_timestamp():
    registros = [
        _registro(timestamp="2026-08-01T09:00:00", custo_usd=1.0),
        _registro(timestamp="2026-08-01T18:00:00", custo_usd=2.0),
        _registro(timestamp="2026-07-31T23:59:59", custo_usd=5.0),
    ]

    relatorio = usage.usage_report(registros=registros)

    assert relatorio["por_dia"]["2026-08-01"]["chamadas"] == 2
    assert relatorio["por_dia"]["2026-08-01"]["custo_usd"] == pytest.approx(3.0)
    assert relatorio["por_dia"]["2026-07-31"]["custo_usd"] == pytest.approx(5.0)


def test_total_soma_todos_os_registros_independente_da_dimensao():
    registros = [_registro(custo_usd=1.0), _registro(custo_usd=2.0, sucesso=False, erro="x")]

    relatorio = usage.usage_report(registros=registros)

    assert relatorio["total"]["chamadas"] == 2
    assert relatorio["total"]["falhas"] == 1
    assert relatorio["total"]["custo_usd"] == pytest.approx(3.0)


def test_custo_estimado_parcial_true_quando_mistura_real_e_estimado():
    registros = [
        _registro(custo_usd=1.0, custo_estimado=False),
        _registro(custo_usd=2.0, custo_estimado=True),
    ]

    relatorio = usage.usage_report(registros=registros)

    assert relatorio["total"]["custo_estimado_parcial"] is True


def test_custo_estimado_parcial_true_quando_tudo_estimado():
    registros = [
        _registro(custo_usd=1.0, custo_estimado=True),
        _registro(custo_usd=2.0, custo_estimado=True),
    ]

    relatorio = usage.usage_report(registros=registros)

    assert relatorio["total"]["custo_estimado_parcial"] is True


def test_custo_estimado_parcial_false_quando_tudo_real():
    registros = [
        _registro(custo_usd=1.0, custo_estimado=False),
        _registro(custo_usd=2.0, custo_estimado=False),
    ]

    relatorio = usage.usage_report(registros=registros)

    assert relatorio["total"]["custo_estimado_parcial"] is False


def test_contagem_de_falhas_por_bucket():
    registros = [
        _registro(modulo="m1", sucesso=True),
        _registro(modulo="m1", sucesso=False, erro="x"),
        _registro(modulo="m1", sucesso=False, erro="y"),
    ]

    relatorio = usage.usage_report(registros=registros)

    assert relatorio["por_modulo"]["m1"]["chamadas"] == 3
    assert relatorio["por_modulo"]["m1"]["falhas"] == 2


def test_registros_injetados_evita_leitura_do_arquivo(tmp_path):
    caminho_inexistente = tmp_path / "nao-existe.jsonl"
    registros = [_registro(custo_usd=1.0)]

    relatorio = usage.usage_report(caminho=caminho_inexistente, registros=registros)

    assert relatorio["total"]["chamadas"] == 1  # usou os registros injetados, não o arquivo


def test_registros_vazio_explicito_e_diferente_de_none_nao_le_o_arquivo(tmp_path):
    caminho = tmp_path / "uso.jsonl"
    caminho.write_text(json.dumps(_registro()) + "\n", encoding="utf-8")

    relatorio = usage.usage_report(caminho=caminho, registros=[])

    assert relatorio["total"]["chamadas"] == 0  # [] != None -- não caiu para ler_registros(caminho)


def test_relatorio_vazio_quando_arquivo_ausente_e_sem_registros_injetados(tmp_path):
    relatorio = usage.usage_report(caminho=tmp_path / "nao-existe.jsonl")

    assert relatorio["total"]["chamadas"] == 0
    assert relatorio["por_modulo"] == {}
    assert relatorio["por_modelo"] == {}
    assert relatorio["por_tarefa_e_modelo"] == {}
    assert relatorio["por_dia"] == {}


def test_tarefa_e_modulo_ausentes_caem_no_balde_desconhecido():
    registros = [
        {
            "timestamp": "2026-08-01T10:00:00", "provider": "gemini", "model": "m",
            "tokens_in": 1, "tokens_out": 1, "custo_usd": 1.0, "custo_estimado": False,
            "duracao_s": 1.0, "sucesso": True, "erro": None,
            # sem "tarefa"/"modulo" nenhum -- registro malformado/antigo
        },
    ]

    relatorio = usage.usage_report(registros=registros)

    assert "sem_tarefa" in relatorio["por_tarefa_e_modelo"]
    assert "desconhecido" in relatorio["por_modulo"]


def test_tokens_ausentes_nao_contribuem_para_soma_mas_nao_quebram():
    registros = [
        _registro(tokens_in=100, tokens_out=200),
        _registro(tokens_in=None, tokens_out=None, custo_usd=None, custo_estimado=None, sucesso=False, erro="x"),
    ]

    relatorio = usage.usage_report(registros=registros)

    assert relatorio["total"]["tokens_in"] == 100
    assert relatorio["total"]["tokens_out"] == 200


# =============================================================================
# E. formatar_relatorio_texto
# =============================================================================
def test_relatorio_vazio_nao_quebra_e_diz_nenhuma_chamada():
    relatorio = usage.usage_report(registros=[])

    assert usage.formatar_relatorio_texto(relatorio) == "Nenhuma chamada de IA registrada ainda."


def test_relatorio_dict_totalmente_vazio_nao_quebra():
    assert usage.formatar_relatorio_texto({}) == "Nenhuma chamada de IA registrada ainda."


def test_relatorio_com_dados_inclui_total_modulo_e_modelo_no_texto():
    registros = [
        _registro(modulo="upload_conditions_backend", model="gemini-3-flash-preview", custo_usd=1.5),
        _registro(modulo="upload_tech_specs_backend", model="grok-4.5", custo_usd=2.5),
    ]
    relatorio = usage.usage_report(registros=registros)

    texto = usage.formatar_relatorio_texto(relatorio)

    assert "Total gasto: US$ 4.0000" in texto
    assert "Chamadas registradas: 2" in texto
    assert "upload_conditions_backend" in texto
    assert "upload_tech_specs_backend" in texto
    assert "gemini-3-flash-preview" in texto
    assert "grok-4.5" in texto


def test_periodo_coberto_usa_o_menor_e_o_maior_dia():
    registros = [
        _registro(timestamp="2026-07-30T08:00:00"),
        _registro(timestamp="2026-08-01T08:00:00"),
    ]
    relatorio = usage.usage_report(registros=registros)

    texto = usage.formatar_relatorio_texto(relatorio)

    assert "Período coberto: 2026-07-30 a 2026-08-01" in texto


def test_marca_inclui_estimativa_quando_parcial():
    registros = [_registro(custo_usd=1.0, custo_estimado=True)]
    relatorio = usage.usage_report(registros=registros)

    texto = usage.formatar_relatorio_texto(relatorio)

    assert "(inclui estimativa)" in texto


# =============================================================================
# F. sigft.config -- PASTA_LOGS / ARQUIVO_USO_LLM (aditivos, CP 3.4)
# =============================================================================
def test_config_pasta_logs_e_arquivo_uso_llm():
    assert config.PASTA_LOGS == "logs"
    assert config.ARQUIVO_USO_LLM == os.path.join("logs", "llm_usage.jsonl")

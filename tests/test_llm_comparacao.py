r"""
Testes de `sigft/core/llm/comparacao.py` e da captura de prompts
(`SIGFT_DUMP_PROMPTS`) em `sigft/core/llm/client.py`.

Ferramenta de VALIDAÇÃO A/B criada para atender o Aceite do CP 3.3
(docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.3: "o usuário valida
a qualidade num punhado de fichas (A/B contra o modelo anterior)"). Ver
`scripts/ab_modelos.py` para o CLI que amarra as duas peças.

A lógica comparada aqui é PURA (sem rede, sem SDK, sem tempo real), então é
testável de verdade — ao contrário do CLI, que só faz fiação.
"""
from __future__ import annotations

import json
import os

import pytest

from sigft.core.llm import client as llm_client
from sigft.core.llm.comparacao import (
    achatar,
    comparar_json,
    montar_relatorio_markdown,
)


# =============================================================================
# A. achatar()
# =============================================================================

def test_achatar_objeto_simples():
    assert achatar({"a": 1, "b": "x"}) == {"a": 1, "b": "x"}


def test_achatar_objeto_aninhado_usa_ponto():
    assert achatar({"campos": {"transporte": {"status": "VALIDO"}}}) == {
        "campos.transporte.status": "VALIDO"
    }


def test_achatar_lista_usa_indice_entre_colchetes():
    assert achatar([{"TIPO": "CHAR"}, {"TIPO": "NUM"}]) == {
        "[0].TIPO": "CHAR",
        "[1].TIPO": "NUM",
    }


def test_achatar_lista_dentro_de_objeto():
    assert achatar({"itens": [10, 20]}) == {"itens[0]": 10, "itens[1]": 20}


def test_achatar_escalar_na_raiz():
    assert achatar("texto") == {"(raiz)": "texto"}


def test_achatar_trata_vazios_como_folha():
    # "o campo virou vazio" precisa aparecer como diferença, não sumir.
    assert achatar({"a": {}, "b": []}) == {"a": {}, "b": []}


def test_achatar_preserva_none_como_valor():
    assert achatar({"subtipo": None}) == {"subtipo": None}


# =============================================================================
# B. comparar_json()
# =============================================================================

def test_comparar_identicos():
    resultado = comparar_json({"a": 1}, {"a": 1})

    assert resultado["iguais"] is True
    assert resultado["total_diferencas"] == 0


def test_comparar_detecta_valor_diferente():
    resultado = comparar_json({"TIPO": "CHAR"}, {"TIPO": "NUM"})

    assert resultado["iguais"] is False
    assert resultado["valores_diferentes"] == [
        {"caminho": "TIPO", "baseline": "CHAR", "candidato": "NUM"}
    ]
    assert resultado["total_diferencas"] == 1


def test_comparar_detecta_campo_que_sumiu():
    resultado = comparar_json({"a": 1, "b": 2}, {"a": 1})

    assert resultado["so_no_baseline"] == ["b"]
    assert resultado["so_no_candidato"] == []
    assert resultado["total_diferencas"] == 1


def test_comparar_detecta_campo_inventado():
    resultado = comparar_json({"a": 1}, {"a": 1, "extra": 9})

    assert resultado["so_no_candidato"] == ["extra"]
    assert resultado["so_no_baseline"] == []


def test_comparar_lista_com_item_a_menos():
    # Caso real de `tech_specs`: modelo mais fraco devolve menos itens.
    resultado = comparar_json(
        [{"CARACTERISTICA_CHAVE": "A"}, {"CARACTERISTICA_CHAVE": "B"}],
        [{"CARACTERISTICA_CHAVE": "A"}],
    )

    assert resultado["so_no_baseline"] == ["[1].CARACTERISTICA_CHAVE"]
    assert resultado["iguais"] is False


def test_comparar_soma_os_3_tipos_de_diferenca():
    resultado = comparar_json({"a": 1, "some": 2}, {"a": 99, "novo": 3})

    assert resultado["total_diferencas"] == 3  # 1 valor + 1 sumiu + 1 novo
    assert resultado["iguais"] is False


def test_comparar_aninhado_reporta_caminho_completo():
    resultado = comparar_json(
        {"logistica_reversa": {"status": "SIM"}},
        {"logistica_reversa": {"status": "NAO"}},
    )

    assert resultado["valores_diferentes"][0]["caminho"] == "logistica_reversa.status"


def test_comparar_tipos_totalmente_diferentes_nao_levanta():
    resultado = comparar_json({"a": 1}, [1, 2, 3])

    assert resultado["iguais"] is False
    assert resultado["total_diferencas"] > 0


# =============================================================================
# C. montar_relatorio_markdown()
# =============================================================================

def _resultado_ok(rotulo, parsed, texto=None, **extras):
    base = {
        "rotulo": rotulo,
        "ok": True,
        "texto": texto if texto is not None else json.dumps(parsed, ensure_ascii=False),
        "parsed": parsed,
        "tokens_in": 100,
        "tokens_out": 50,
        "custo_usd": None,
        "duracao_s": 1.5,
    }
    base.update(extras)
    return base


def test_relatorio_vazio_nao_levanta():
    assert "Nenhum resultado" in montar_relatorio_markdown([])


def test_relatorio_marca_o_primeiro_como_baseline():
    md = montar_relatorio_markdown(
        [_resultado_ok("gemini:a", {"x": 1}), _resultado_ok("openrouter:b", {"x": 1})]
    )

    assert "Baseline (referência de comparação): **gemini:a**" in md
    assert "(baseline)" in md


def test_relatorio_sinaliza_json_identico():
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"x": 1}), _resultado_ok("b", {"x": 1})]
    )

    assert "✅ idêntico" in md


def test_relatorio_conta_diferencas_na_tabela():
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"x": 1, "y": 2}), _resultado_ok("b", {"x": 9, "y": 2})]
    )

    assert "⚠️ 1" in md
    assert "Diferenças em relação ao baseline" in md


def test_relatorio_lista_campos_sumidos_e_extras():
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"mantido": 1, "sumiu": 2}), _resultado_ok("b", {"mantido": 1, "novo": 3})]
    )

    assert "Campos que sumiram" in md
    assert "`sumiu`" in md
    assert "Campos a mais" in md
    assert "`novo`" in md


def test_relatorio_registra_modelo_que_falhou_sem_quebrar():
    md = montar_relatorio_markdown(
        [
            _resultado_ok("a", {"x": 1}),
            {"rotulo": "b", "ok": False, "erro": "HTTPError: 429"},
        ]
    )

    assert "❌ falhou" in md
    assert "## Falhas" in md
    assert "HTTPError: 429" in md


def test_relatorio_marca_json_invalido():
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"x": 1}), _resultado_ok("b", None, texto="isso não é json")]
    )

    # JSON inválido = coluna ❌ e comparação impossível ("n/d"), sem levantar.
    assert "n/d" in md


def test_relatorio_mostra_custo_real_quando_informado():
    md = montar_relatorio_markdown([_resultado_ok("a", {"x": 1}, custo_usd=0.000123)])

    assert "US$ 0.000123" in md


def test_relatorio_mostra_traco_quando_custo_ausente():
    md = montar_relatorio_markdown([_resultado_ok("a", {"x": 1}, custo_usd=None)])

    assert "| — |" in md


def test_relatorio_inclui_contexto_do_prompt():
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"x": 1})], contexto={"Tarefa": "tech_specs"}
    )

    assert "**Tarefa**: tech_specs" in md


def test_relatorio_traz_o_aviso_sobre_o_limite_da_ferramenta():
    # O relatório precisa ser honesto sobre o que NÃO decide sozinho —
    # é o que evita alguém adotar um modelo pior olhando só a contagem.
    md = montar_relatorio_markdown([_resultado_ok("a", {"x": 1})])

    assert "NÃO decide por você" in md
    assert "PT/ES" in md


def test_relatorio_escapa_pipe_para_nao_quebrar_a_tabela():
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"v": "10 | 20"}), _resultado_ok("b", {"v": "30 | 40"})]
    )

    assert "\\|" in md


def test_relatorio_trunca_valor_muito_longo_na_tabela():
    longo_a = "A" * 500
    longo_b = "B" * 500
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"txt": longo_a}), _resultado_ok("b", {"txt": longo_b})]
    )

    assert "…" in md
    assert "A" * 500 not in md.split("## Respostas completas")[0]


def test_relatorio_inclui_respostas_completas_de_todos():
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"x": 1}), _resultado_ok("b", {"x": 2})]
    )

    corpo = md.split("## Respostas completas")[1]
    assert "`a`" in corpo and "`b`" in corpo


# =============================================================================
# D. Captura de prompts (SIGFT_DUMP_PROMPTS) em client.py
# =============================================================================

class _ProviderFake:
    def generate_raw(self, prompt, *, system=None, json_mode=False):
        return llm_client.ProviderResult('{"ok": true}')


def _cliente():
    return llm_client.LLMClient(
        _ProviderFake(), provider_name="gemini", model="modelo-x",
        sleep_fn=lambda _s: None, time_fn=lambda: 0.0,
    )


def test_sem_variavel_de_ambiente_nao_grava_nada(monkeypatch, tmp_path):
    monkeypatch.delenv(llm_client.ENV_DUMP_PROMPTS, raising=False)

    _cliente().generate("meu prompt")

    assert list(tmp_path.iterdir()) == []


def test_com_variavel_grava_o_prompt_real(monkeypatch, tmp_path):
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(tmp_path))

    _cliente().generate(
        "prompt gigante da ficha",
        system="instrucao de sistema",
        json_mode=True,
        tags={"modulo": "upload_tech_specs_backend", "tarefa": "tech_specs"},
    )

    arquivos = list(tmp_path.glob("*.json"))
    assert len(arquivos) == 1
    conteudo = json.loads(arquivos[0].read_text(encoding="utf-8"))
    assert conteudo["prompt"] == "prompt gigante da ficha"
    assert conteudo["system"] == "instrucao de sistema"
    assert conteudo["json_mode"] is True
    assert conteudo["tarefa"] == "tech_specs"
    assert conteudo["modulo"] == "upload_tech_specs_backend"
    assert conteudo["model_na_captura"] == "modelo-x"
    assert conteudo["provider_na_captura"] == "gemini"


def test_nome_do_arquivo_cita_a_tarefa(monkeypatch, tmp_path):
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(tmp_path))

    _cliente().generate("p", tags={"tarefa": "condicoes"})

    assert "condicoes" in list(tmp_path.glob("*.json"))[0].name


def test_chamadas_sucessivas_nao_sobrescrevem_o_mesmo_arquivo(monkeypatch, tmp_path):
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(tmp_path))
    cliente = _cliente()

    for _ in range(3):
        cliente.generate("p", tags={"tarefa": "tech_specs"})

    assert len(list(tmp_path.glob("*.json"))) == 3


def test_pasta_inexistente_e_criada(monkeypatch, tmp_path):
    destino = tmp_path / "nao" / "existe" / "ainda"
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(destino))

    _cliente().generate("p", tags={"tarefa": "autospec"})

    assert len(list(destino.glob("*.json"))) == 1


def test_falha_ao_gravar_nunca_derruba_a_chamada_real(monkeypatch, tmp_path):
    # Um arquivo no lugar da pasta faz `os.makedirs` falhar — a chamada de
    # IA precisa seguir normalmente mesmo assim (diagnóstico nunca derruba
    # produção).
    obstaculo = tmp_path / "obstaculo"
    obstaculo.write_text("sou um arquivo, não uma pasta", encoding="utf-8")
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(obstaculo))

    resposta = _cliente().generate("p", tags={"tarefa": "tech_specs"})

    assert resposta.parsed_json == {"ok": True}


def test_captura_acontece_uma_vez_por_generate_nao_por_tentativa(monkeypatch, tmp_path):
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(tmp_path))

    class _FalhaDuasVezes:
        def __init__(self):
            self.chamadas = 0

        def generate_raw(self, prompt, *, system=None, json_mode=False):
            self.chamadas += 1
            if self.chamadas < 3:
                raise RuntimeError("falha")
            return llm_client.ProviderResult('{"ok": true}')

    provider = _FalhaDuasVezes()
    llm_client.LLMClient(
        provider, provider_name="gemini", model="m", max_retries=2,
        sleep_fn=lambda _s: None, time_fn=lambda: 0.0,
    ).generate("p", tags={"tarefa": "tech_specs"})

    assert provider.chamadas == 3  # houve retry de verdade
    assert len(list(tmp_path.glob("*.json"))) == 1  # mas só 1 captura


@pytest.mark.parametrize("tags", [None, {}, {"modulo": "x"}])
def test_captura_tolera_tags_ausentes_ou_incompletas(monkeypatch, tmp_path, tags):
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(tmp_path))

    _cliente().generate("p", tags=tags)

    conteudo = json.loads(list(tmp_path.glob("*.json"))[0].read_text(encoding="utf-8"))
    assert conteudo["tarefa"] == "sem_tarefa"


def test_arquivo_capturado_tem_as_chaves_que_o_cli_consome(monkeypatch, tmp_path):
    # Contrato entre a captura (client.py) e o consumo (scripts/ab_modelos.py):
    # se uma destas chaves sumir, o CLI quebra.
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(tmp_path))

    _cliente().generate("p", system="s", json_mode=True, tags={"tarefa": "condicoes"})

    conteudo = json.loads(list(tmp_path.glob("*.json"))[0].read_text(encoding="utf-8"))
    for chave in ("prompt", "system", "json_mode", "tarefa", "modulo",
                  "provider_na_captura", "model_na_captura"):
        assert chave in conteudo, chave


def test_variavel_vazia_equivale_a_desligada(monkeypatch, tmp_path):
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, "")
    os.chdir(tmp_path)

    _cliente().generate("p")

    assert list(tmp_path.glob("*.json")) == []


def test_respostas_completas_usam_cerca_de_4_crases():
    # Resposta CRUA de IA quase sempre traz ```json dentro; uma cerca externa
    # de 3 crases quebraria a renderização do markdown.
    md = montar_relatorio_markdown(
        [_resultado_ok("a", {"x": 1}, texto='```json\n{"x": 1}\n```')]
    )

    corpo = md.split("## Respostas completas")[1]
    assert "````" in corpo


# =============================================================================
# E. Fiação do CLI (scripts/ab_modelos.py) — smoke de ponta a ponta com
#    providers FAKE (o CLI em si não tem outra cobertura; a lógica pura já
#    está coberta acima).
# =============================================================================

def test_cli_ab_modelos_ponta_a_ponta(monkeypatch, tmp_path):
    import importlib.util

    caminho_cli = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "ab_modelos.py"
    )
    spec = importlib.util.spec_from_file_location("ab_modelos", caminho_cli)
    ab_modelos = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab_modelos)

    # 1) um prompt capturado de verdade, pelo mecanismo real de dump
    monkeypatch.setenv(llm_client.ENV_DUMP_PROMPTS, str(tmp_path))
    _cliente().generate(
        "prompt da ficha", system="sys", json_mode=True,
        tags={"modulo": "upload_tech_specs_backend", "tarefa": "tech_specs"},
    )
    capturado = str(list(tmp_path.glob("*.json"))[0])

    # 2) providers fake: baseline ok, candidato divergente, terceiro falhando
    respostas = {
        "gemini:base": '[{"TIPO": "NUM"}]',
        "openrouter:cand": '[{"TIPO": "CHAR"}]',
    }

    class _Fake:
        def __init__(self, texto):
            self._texto = texto

        def generate_raw(self, prompt, *, system=None, json_mode=False):
            if self._texto is None:
                raise RuntimeError("429 rate limit")
            return llm_client.ProviderResult(self._texto, 10, 5, 0.0001)

    monkeypatch.setattr(
        ab_modelos, "construir_provider",
        lambda pid, model, chaves, temp: _Fake(respostas.get(f"{pid}:{model}")),
    )

    saida = tmp_path / "rel.md"
    codigo = ab_modelos.main(
        ["--prompt", capturado, "--modelos", "gemini:base", "openrouter:cand",
         "openrouter:falha", "--saida", str(saida)]
    )

    assert codigo == 0
    relatorio = saida.read_text(encoding="utf-8")
    assert "Baseline (referência de comparação): **gemini:base**" in relatorio
    assert "⚠️ 1" in relatorio                      # divergência detectada
    assert "`[0].TIPO`" in relatorio                # no campo certo
    assert "429 rate limit" in relatorio            # falha registrada, sem derrubar
    assert "tech_specs" in relatorio                # contexto do prompt capturado


def test_cli_rejeita_par_sem_dois_pontos(monkeypatch, tmp_path):
    import importlib.util

    caminho_cli = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "ab_modelos.py"
    )
    spec = importlib.util.spec_from_file_location("ab_modelos", caminho_cli)
    ab_modelos = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab_modelos)

    prompt = tmp_path / "p.json"
    prompt.write_text(json.dumps({"prompt": "p"}), encoding="utf-8")

    with pytest.raises(SystemExit):
        ab_modelos.main(["--prompt", str(prompt), "--modelos", "modelo_sem_provider"])

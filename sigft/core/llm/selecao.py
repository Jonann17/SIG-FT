r"""
sigft/core/llm/selecao.py — persistência da SELEÇÃO de modelo de IA feita
pelo usuário no painel "Modelos de IA" da Home (Checkpoint 3.3 do plano de
refatoração, Parte A).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.3, e
docs/refatoracao/MODELOS_IA.md §5 ("Como isto entra na refatoração (sem
downgrade silencioso)"). Módulo PURO (sem Tk/interface antiga, sem
`google.generativeai`/`requests`) que só LÊ e GRAVA a seleção -- a
RESOLUÇÃO em runtime (o que `get_llm()` de fato usa quando não há seleção)
é responsabilidade de `core/llm/client.py:get_llm()` (Parte B do mesmo
checkpoint), NÃO deste módulo: `resolver()` abaixo devolve `None` quando não
há nada salvo -- é `get_llm()` quem decide o FALLBACK embutido
(`config.LLM_MODELOS_HOJE`, por decisão explícita do arquiteto: "sem
downgrade silencioso" -- instalar esta versão não troca o modelo de ninguém
que nunca abriu o painel novo).

Espelha a estrutura/convenções de `sigft/core/prefs.py` (CP 1.5):
`config_path` parametrizável em toda função pública (testável com
`tmp_path`, nunca precisa tocar o `api_config.json` real do cwd) e
tolerância TOTAL a arquivo ausente, JSON corrompido, JSON que não é um
objeto, ou uma sub-seção com tipo inesperado -- nunca levanta por causa
disso, sempre degrada para "sem seleção" (mesmo espírito de
`sigft.config.carregar_chaves`/`sigft.core.prefs`).

Persistência
------------
MESMO arquivo das chaves de API (`sigft.config.CONFIG_FILE`, hoje
"api_config.json") -- não um arquivo próprio, para não multiplicar os
arquivos de config que o usuário precisa saber que existem -- sob a chave de
nível superior RESERVADA `CHAVE_RESERVADA` ("_modelos_ia"). Forma da
sub-árvore:

    {"global": {"provider": "...", "model": "..."} | None,
     "por_tarefa": {"<tarefa>": {"provider": "...", "model": "..."}, ...}}

  - "global": seleção que vale para QUALQUER tarefa sem override específico
    (modo simples do painel). `None` = usuário nunca escolheu nada (ou
    escolheu explicitamente "Padrão do sistema" -- ver `limpar_global`).
  - "por_tarefa": overrides por tarefa (modo avançado do painel), chave =
    nome da tarefa (`"categorizar_pdm"`, `"validar_ficha"`, `"condicoes"`,
    `"tech_specs"`, `"autospec"` -- as mesmas 5 de `config.LLM_MODELOS_HOJE`).
    Uma tarefa AUSENTE deste dict = "usa o global" (ver `limpar_por_tarefa`).

CRÍTICO -- nunca destruir as chaves de API que já moram no MESMO arquivo:
toda escrita aqui é READ-MODIFY-WRITE do JSON INTEIRO (lê o arquivo como
está, altera só a sub-árvore `CHAVE_RESERVADA`, e regrava tudo de volta) --
nunca um `open(..., "w")` só com a seleção. Ver `_salvar_secao` abaixo e
`tests/test_llm_selecao.py` (seção F: prova dedicada nos 2 sentidos --
gravar seleção preserva chaves de API já presentes, e vice-versa: atualizar
chaves de API por um read-modify-write equivalente preserva a seleção já
salva). `frontend.py` (`SIG_FT_App.save_keys`) foi corrigido na Parte C
deste mesmo checkpoint para seguir a MESMA disciplina (antes, sobrescrevia
`CONFIG_FILE` inteiro só com as chaves de API, apagando esta sub-árvore).

Validação de forma (`provider`/`model` não-vazios)
----------------------------------------------------
Uma entrada é considerada válida só se for um `dict` com `"provider"` E
`"model"` como strings NÃO-VAZIAS -- qualquer outra coisa (tipo errado,
chave ausente, string vazia) é tratada como "entrada ausente/malformada" e
IGNORADA silenciosamente (nunca levanta), tanto ao normalizar o que foi lido
do disco (`carregar`) quanto, por consequência, em `resolver` -- mesmo
espírito de `prefs._pasta_valida`.

Validação de `tarefa` (`definir_por_tarefa`/`limpar_por_tarefa`)
------------------------------------------------------------------
Contra `config.LLM_MODELOS_HOJE` (as mesmas 5 tarefas), mesmo padrão de
`core/llm/client.py:get_llm()`/`config.get_task_config()`: tarefa desconhecida
levanta `ValueError` com a lista das válidas na mensagem. `resolver()` NÃO
valida `tarefa` (quem precisa dessa garantia -- `get_llm()` -- já valida
ANTES de chegar aqui); uma tarefa desconhecida simplesmente não tem override
salvo, então cai para a seleção global.

Só stdlib (`json`, `os`) + `from sigft import config` -- importável no
ambiente de teste sem nenhuma dependência pesada (mesmo padrão de
`core/prefs.py`/`core/llm/client.py`). Ver tests/test_llm_selecao.py.
"""

from __future__ import annotations

from typing import Any

import json
import os

from sigft import config

# Chave de nível superior dentro de `config.CONFIG_FILE` (o MESMO arquivo das
# chaves de API), reservada para a seleção de modelo deste checkpoint --
# nenhuma chave de API usa (nem pode passar a usar) este nome.
CHAVE_RESERVADA = "_modelos_ia"


def _estado_vazio() -> dict[str, Any]:
    """Novo estado vazio ("nunca configurou nada") -- usado como fallback
    sempre que a sub-árvore de seleção está ausente ou corrompida (no todo
    ou em parte)."""
    return {"global": None, "por_tarefa": {}}


def _selecao_valida(candidato: Any) -> dict[str, str] | None:
    """`candidato` normalizado para `{"provider": ..., "model": ...}` se for
    um dict com as 2 chaves presentes como strings NÃO-VAZIAS; senão `None`
    ("entrada malformada" -- nunca levanta, só é tratada como ausente)."""
    if not isinstance(candidato, dict):
        return None
    provider = candidato.get("provider")
    model = candidato.get("model")
    if isinstance(provider, str) and provider and isinstance(model, str) and model:
        return {"provider": provider, "model": model}
    return None


def _resolver(config_path):
    """Para onde o `api_config.json` vai DE VERDADE -- ver
    `dados_usuario.resolver_config`, que é o dono da regra.

    Chamado nos DOIS pontos de I/O deste módulo (`_ler_json_bruto` e
    `_salvar_secao`), e não em cada assinatura pública: são 8 delas, mais dois
    pontos de chamada externos que passam `config.CONFIG_FILE` na mão -- um
    deles em `services/autospec.py`, que é da frente do Rafael. Resolvendo
    aqui, o ponto dele passa a funcionar sem que eu encoste no arquivo.
    """
    from sigft.core.dados_usuario import resolver_config

    return resolver_config(config_path, config.CONFIG_FILE)


def _ler_json_bruto(config_path: str | os.PathLike[str]) -> dict[str, Any]:
    """JSON inteiro de `config_path`, tolerante a ausência/corrupção -- `{}`
    para QUALQUER cenário que não seja "existe e é um objeto JSON válido".
    Nunca levanta (mesmo espírito de `config.carregar_chaves`)."""
    config_path = _resolver(config_path)
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as arquivo:
            bruto = json.load(arquivo)
    except Exception:
        return {}
    return bruto if isinstance(bruto, dict) else {}


def carregar(*, config_path: str | os.PathLike[str] = config.CONFIG_FILE) -> dict[str, Any]:
    """Seleção de modelo persistida, NORMALIZADA: sempre com as 2 chaves
    (`"global"`/`"por_tarefa"`), entradas malformadas descartadas em
    silêncio. Nunca levanta -- arquivo ausente/corrompido, JSON que não é um
    objeto, ou `CHAVE_RESERVADA` com tipo inesperado devolvem o mesmo que
    "nunca configurou nada" (`{"global": None, "por_tarefa": {}}`)."""
    secao = _ler_json_bruto(config_path).get(CHAVE_RESERVADA)
    estado = _estado_vazio()
    if not isinstance(secao, dict):
        return estado

    estado["global"] = _selecao_valida(secao.get("global"))

    por_tarefa_bruto = secao.get("por_tarefa")
    if isinstance(por_tarefa_bruto, dict):
        for tarefa, valor in por_tarefa_bruto.items():
            validado = _selecao_valida(valor)
            if validado is not None:
                estado["por_tarefa"][tarefa] = validado
    return estado


def resolver(
    tarefa: str, *, config_path: str | os.PathLike[str] = config.CONFIG_FILE
) -> dict[str, str] | None:
    """Resolve a seleção para `tarefa`: override POR TAREFA > seleção
    GLOBAL > `None` (nenhuma seleção salva -- quem chama, tipicamente
    `core/llm/client.py:get_llm()`, decide o fallback embutido).

    Não valida `tarefa` contra `config.LLM_MODELOS_HOJE` -- ver docstring do
    módulo."""
    estado = carregar(config_path=config_path)
    override = estado["por_tarefa"].get(tarefa)
    if override is not None:
        return override
    return estado["global"]


def _validar_tarefa(tarefa: str) -> None:
    """Mesmo padrão de erro de `core/llm/client.py:get_llm()`/
    `config.get_task_config()`: `ValueError` com a lista de tarefas válidas
    (`config.LLM_MODELOS_HOJE`) na mensagem."""
    if tarefa not in config.LLM_MODELOS_HOJE:
        tarefas_validas = ", ".join(sorted(config.LLM_MODELOS_HOJE))
        raise ValueError(
            f"Tarefa de IA desconhecida: {tarefa!r}. Tarefas configuradas em "
            f"LLM_MODELOS_HOJE: {tarefas_validas}."
        )


def _salvar_secao(secao: dict[str, Any], *, config_path: str | os.PathLike[str]) -> None:
    """READ-MODIFY-WRITE do JSON INTEIRO -- lê `config_path` como está,
    substitui só `bruto[CHAVE_RESERVADA]` e regrava tudo. É o que garante que
    escrever uma seleção nunca apaga as chaves de API (`GEMINI`/`OPENROUTER`/
    etc.) que já estavam no mesmo arquivo -- ver docstring do módulo."""
    config_path = _resolver(config_path)
    bruto = _ler_json_bruto(config_path)
    bruto[CHAVE_RESERVADA] = secao
    with open(config_path, "w", encoding="utf-8") as arquivo:
        json.dump(bruto, arquivo, ensure_ascii=False, indent=2, sort_keys=True)


def definir_global(
    provider: str, model: str, *, config_path: str | os.PathLike[str] = config.CONFIG_FILE
) -> None:
    """Grava `{"provider": provider, "model": model}` como seleção GLOBAL
    (modo simples do painel) -- vale para toda tarefa sem override
    específico. Preserva os overrides por tarefa já salvos (read-modify-write
    da sub-árvore inteira via `carregar()` + `_salvar_secao()`)."""
    estado = carregar(config_path=config_path)
    estado["global"] = {"provider": provider, "model": model}
    _salvar_secao(estado, config_path=config_path)


def limpar_global(*, config_path: str | os.PathLike[str] = config.CONFIG_FILE) -> None:
    """Remove a seleção GLOBAL (volta a `None` -- opção "Padrão do sistema"
    na UI). Preserva os overrides por tarefa já salvos. No-op silencioso se
    não havia seleção global (idempotente)."""
    estado = carregar(config_path=config_path)
    estado["global"] = None
    _salvar_secao(estado, config_path=config_path)


def definir_por_tarefa(
    tarefa: str,
    provider: str,
    model: str,
    *,
    config_path: str | os.PathLike[str] = config.CONFIG_FILE,
) -> None:
    """Grava um override POR TAREFA (modo avançado do painel) -- vence a
    seleção global só para `tarefa`. `ValueError` para tarefa desconhecida
    (ver `_validar_tarefa`) -- protege contra salvar um override para uma
    tarefa que `get_llm()` nunca vai consultar; nada é gravado no disco
    quando a validação falha. Preserva o global e os demais overrides já
    salvos."""
    _validar_tarefa(tarefa)
    estado = carregar(config_path=config_path)
    estado["por_tarefa"][tarefa] = {"provider": provider, "model": model}
    _salvar_secao(estado, config_path=config_path)


def limpar_por_tarefa(
    tarefa: str, *, config_path: str | os.PathLike[str] = config.CONFIG_FILE
) -> None:
    """Remove o override de `tarefa` (volta a "usar o global" -- opção
    correspondente na UI). `ValueError` para tarefa desconhecida, mesmo
    padrão de `definir_por_tarefa`. Remover uma tarefa sem override vigente
    é um no-op silencioso (idempotente)."""
    _validar_tarefa(tarefa)
    estado = carregar(config_path=config_path)
    estado["por_tarefa"].pop(tarefa, None)
    _salvar_secao(estado, config_path=config_path)


def tornar_roteavel(cfg: dict[str, str], *, origem: str) -> dict[str, str]:
    """Traduz um `{"provider", "model"}` recomendado para a forma que
    `core/llm/client.py:get_llm()` consegue de fato construir.

    `config.LLM_DEFAULT`/`LLM_TASKS` expressam a decisão de produto
    (MODELOS_IA.md) em termos do provider NATIVO de cada modelo, e um deles
    (Grok 4.5, em `categorizar_pdm`) usa `config.PROVIDER_XAI` -- que
    `get_llm()` não roteia (só existem os 3 de `config.CHAVE_POR_PROVIDER`,
    ver CP 3.2). Quando o provider já é roteável, devolve `cfg` inalterado;
    quando não é, troca pelo equivalente de `config.MODELO_RECOMENDADO_ROTEAVEL`
    (via OpenRouter, o gateway previsto justamente para isso).

    Levanta `ValueError` -- citando `origem` (ex.: `"LLM_TASKS['categorizar_pdm']"`)
    -- para um provider não roteável SEM equivalente conhecido. Falhar aqui
    é deliberado: o erro aparece no clique do botão "Aplicar recomendados",
    não no meio de um lote de fichas horas depois.
    """
    provider = cfg.get("provider")
    model = cfg.get("model")
    if provider in config.CHAVE_POR_PROVIDER:
        return dict(cfg)

    # `provider`/`model` vem de `.get()` e podem ser None (config incompleta).
    # A tabela so tem chaves de str, entao a busca simplesmente NAO ACHA e cai
    # no `if equivalente is None` logo abaixo -- que e o tratamento certo.
    # O `type: ignore` diz isso ao mypy sem afrouxar a tabela.
    equivalente = config.MODELO_RECOMENDADO_ROTEAVEL.get((provider, model))  # type: ignore[arg-type]
    if equivalente is None:
        roteaveis = ", ".join(sorted(config.CHAVE_POR_PROVIDER))
        raise ValueError(
            f"Modelo recomendado em {origem} usa o provider {provider!r}, que não é "
            f"roteável (suportados: {roteaveis}) e não tem equivalente em "
            f"config.MODELO_RECOMENDADO_ROTEAVEL."
        )
    return dict(equivalente)


def providers_exigidos_pelos_recomendados() -> set[str]:
    """Conjunto de providers que `aplicar_recomendados()` de fato usaria (já
    traduzidos por `tornar_roteavel`). A UI consulta isto ANTES de aplicar,
    para avisar quando falta a chave de algum deles -- ex.: adotar os
    recomendados leva `categorizar_pdm` para o OpenRouter, que não funciona
    sem `OPENROUTER_API_KEY`."""
    cfgs = [(config.LLM_DEFAULT, "LLM_DEFAULT")]
    cfgs += [(cfg, f"LLM_TASKS[{tarefa!r}]") for tarefa, cfg in config.LLM_TASKS.items()]
    return {tornar_roteavel(cfg, origem=origem)["provider"] for cfg, origem in cfgs}


def aplicar_recomendados(*, config_path: str | os.PathLike[str] = config.CONFIG_FILE) -> None:
    """Grava `config.LLM_DEFAULT` como seleção GLOBAL e `config.LLM_TASKS`
    (as 5 tarefas) como overrides POR TAREFA -- é o que o botão "Aplicar
    recomendados" do painel chama (MODELOS_IA.md §3). SUBSTITUI (não
    mescla) qualquer seleção anterior -- é um "resetar para o recomendado"
    deliberado, ação explícita do usuário via clique no botão, não um
    efeito colateral de instalar esta versão (ver docstring do módulo e
    docs/refatoracao/PENDENCIAS.md: o FALLBACK embutido de `get_llm()`
    continua sendo `config.LLM_MODELOS_HOJE` enquanto ninguém clicar aqui --
    "sem downgrade silencioso").

    Cada entrada passa por `tornar_roteavel()` antes de ser gravada, para
    que a seleção resultante seja SEMPRE construível por `get_llm()` -- ver
    o docstring daquela função para o caso concreto (Grok 4.5/`xai` ->
    OpenRouter). Nada é gravado se qualquer entrada for irroteável: a
    `ValueError` sobe antes da escrita, deixando a seleção anterior intacta.
    """
    global_roteavel = tornar_roteavel(config.LLM_DEFAULT, origem="LLM_DEFAULT")
    por_tarefa_roteavel = {
        tarefa: tornar_roteavel(cfg, origem=f"LLM_TASKS[{tarefa!r}]")
        for tarefa, cfg in config.LLM_TASKS.items()
    }

    estado = _estado_vazio()
    estado["global"] = global_roteavel
    estado["por_tarefa"] = por_tarefa_roteavel
    _salvar_secao(estado, config_path=config_path)

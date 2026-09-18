r"""
Catálogo de modelos POR PROVEDOR — "quais modelos esta chave me libera?".

Nasceu do teste real de 2026-08-11. Até aqui a UI oferecia três coisas
sobrepostas para a mesma decisão: uma lista curada que MISTURA provedores
(`config.LLM_FAVORITOS`), um campo de texto livre, e um botão de catálogo que
só existia para o OpenRouter. O usuário resumiu o problema melhor do que
qualquer diagnóstico: *"primeiro você deve escolher se vai trabalhar com a
chave do Gemini, do OpenRouter ou do AMP; quando seleciono o Gemini, deveria
aparecer todos os modelos do Gemini que a chave me libera"*.

Este módulo é a peça que faltava para isso: uma função só, que responde a
pergunta para QUALQUER um dos três provedores, com a mesma forma de resposta.

Decisões que valem registro:

  - **Devolve `list[str]` de ids**, não os dicionários crus do provedor. Cada
    API descreve modelo de um jeito (o OpenRouter manda preço e contexto, o
    Gemini manda `supportedGenerationMethods`, o endpoint OpenAI-compatível
    manda quase nada). O que a UI precisa é do id que vai para `config`, e o
    que o app precisa é não depender do formato de nenhum deles.

  - **Cache em disco por provedor, com TTL**, herdado do desenho que o CP 3.2
    já tinha feito para o OpenRouter. Sem cache, abrir a Home viraria três
    chamadas de rede -- e numa máquina atrás do Zscaler isso é a diferença
    entre a tela abrir e a tela travar.

  - **Nunca levanta.** Falha de rede, chave errada, proxy corporativo
    bloqueando: devolve lista vazia e deixa a UI dizer "não consegui listar".
    O painel de modelos não pode ser o motivo de a Home não abrir -- e o
    campo de digitação manual continua lá como saída.

  - **`http_get` injetável**, como em `providers/openrouter.py`: é o que
    permite testar os três provedores sem rede e sem `requests` instalado
    (que neste ambiente é stub).

O Gemini merece uma nota à parte: o endpoint devolve TODOS os modelos da
conta, incluindo os de embedding e os de contagem de token, que não servem
para gerar ficha nenhuma. O filtro por `generateContent` é o que faz a lista
da UI ser "modelos que dá para usar aqui" em vez de "tudo o que existe".
"""
from __future__ import annotations

import json
import time

from sigft import config
from sigft.core.llm.providers import openrouter

# Um arquivo de cache por provedor. Mesmo padrão de caminho relativo de
# `config.CONFIG_FILE`/`config.OPENROUTER_CATALOGO_CACHE`.
CACHE_POR_PROVIDER = {
    config.PROVIDER_GEMINI: "gemini_models_cache.json",
    config.PROVIDER_OPENROUTER: config.OPENROUTER_CATALOGO_CACHE,
    config.PROVIDER_OPENAI_COMPAT: "empresa_models_cache.json",
}

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

TTL_PADRAO_SEGUNDOS = 86400  # 1 dia, igual ao catálogo do OpenRouter


def caminho_cache(provider: str) -> str:
    """Onde o cache de modelos daquele provedor mora: `Documentos\\SIG-FT\\`.

    Os três caches eram nomes relativos, resolvidos pelo diretório de
    trabalho. Sob `Program Files` a gravação falha, e o efeito seria sutil:
    o catálogo de modelos passaria a ser buscado na rede a CADA abertura,
    porque o cache nunca conseguiria ser escrito.
    """
    from sigft.core.dados_usuario import caminho

    return str(caminho(CACHE_POR_PROVIDER[provider]))


def _http_get_real(url, headers=None, timeout=20):
    """GET pela cascata de rotas de `core.rede`.

    Import PREGUIÇOSO -- o módulo é importado pela UI na montagem da Home, e
    neste ambiente de teste `requests` é stub.

    Passou a sair por `rede.get` em vez de `requests.get` porque, com a VPN da
    empresa ligada, a chamada direta morre por timeout: a rede só publica um
    arquivo PAC, que o `requests` não enxerga. O status continua sendo julgado
    por quem chamou -- `rede.get` não o interpreta.
    """
    from sigft.core import rede

    return rede.get(url, headers=headers or {}, timeout=timeout)


def _ler_cache(caminho, ttl_segundos, agora):
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except Exception:
        return None
    if not isinstance(dados, dict):
        return None
    gravado_em = dados.get("gravado_em")
    modelos = dados.get("modelos")
    if not isinstance(modelos, list) or not isinstance(gravado_em, (int, float)):
        return None
    if agora - gravado_em > ttl_segundos:
        return None
    return [str(m) for m in modelos]


def _gravar_cache(caminho, modelos, agora):
    try:
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump({"gravado_em": agora, "modelos": modelos}, arquivo, indent=2)
    except Exception:
        pass  # cache é conveniência; não poder gravar não é erro do usuário


def _ids_do_gemini(chave, http_get, timeout):
    """`GET /models?key=` — e filtra pelos que sabem `generateContent`.

    Sem o filtro, a lista viria com `embedding-001`, `aqa` e afins: modelos
    que existem na conta mas que fariam a ficha falhar se escolhidos."""
    resposta = http_get(f"{GEMINI_BASE_URL}/models?key={chave}", headers={}, timeout=timeout)
    resposta.raise_for_status()
    corpo = resposta.json() or {}
    ids = []
    for modelo in corpo.get("models") or []:
        if not isinstance(modelo, dict):
            continue
        metodos = modelo.get("supportedGenerationMethods") or []
        if "generateContent" not in metodos:
            continue
        nome = str(modelo.get("name") or "")
        # A API devolve "models/gemini-3-flash"; o app grava e usa o id sem
        # o prefixo, que é como ele aparece em `config.LLM_MODELOS_HOJE`.
        ids.append(nome.split("/", 1)[1] if nome.startswith("models/") else nome)
    return [i for i in ids if i]


def _ids_do_openai_compat(chave, base_url, http_get, timeout):
    """`GET {base_url}/models` — o formato padrão da OpenAI, que é o que um
    endpoint "OpenAI-compatível" (o AMP da empresa) implementa."""
    raiz = str(base_url or "").rstrip("/")
    if not raiz:
        return []
    resposta = http_get(
        f"{raiz}/models", headers={"Authorization": f"Bearer {chave}"}, timeout=timeout
    )
    resposta.raise_for_status()
    corpo = resposta.json() or {}
    return [
        str(m["id"])
        for m in (corpo.get("data") or [])
        if isinstance(m, dict) and m.get("id")
    ]


def listar_modelos(
    provider,
    chaves=None,
    *,
    forcar=False,
    somente_cache=False,
    ttl_segundos=TTL_PADRAO_SEGUNDOS,
    http_get=None,
    time_fn=None,
    timeout=20,
):
    """Ids de modelo que `provider` oferece para as chaves configuradas.

    `forcar=True` ignora o cache (é o que o botão "Atualizar lista" da UI
    usa). `somente_cache=True` NUNCA toca a rede -- é como a Home monta o
    painel: uma tela que abre não pode ficar pendurada em três chamadas
    HTTP, ainda mais atrás de um proxy corporativo. Os dois juntos não fazem
    sentido; `forcar` vence.

    Devolve sempre uma lista ORDENADA, e `[]` em qualquer falha -- nunca
    levanta.
    """
    if provider not in CACHE_POR_PROVIDER:
        return []

    chaves = chaves if chaves is not None else config.carregar_chaves()
    agora = (time_fn or time.time)()
    arquivo_cache = caminho_cache(provider)

    if not forcar:
        do_cache = _ler_cache(arquivo_cache, ttl_segundos, agora)
        if do_cache is not None:
            return do_cache
        if somente_cache:
            return []

    obter = http_get or _http_get_real
    try:
        if provider == config.PROVIDER_GEMINI:
            ids = _ids_do_gemini(chaves.get("GEMINI"), obter, timeout)
        elif provider == config.PROVIDER_OPENROUTER:
            modelos = openrouter.listar_modelos(
                chaves.get("OPENROUTER"),
                ttl_segundos=0 if forcar else ttl_segundos,
                http_get=obter,
                time_fn=time_fn,
            )
            ids = [
                str(m["id"]) for m in modelos if isinstance(m, dict) and m.get("id")
            ]
        else:
            ids = _ids_do_openai_compat(
                chaves.get("EMPRESA_LLM_API_KEY"),
                chaves.get("EMPRESA_LLM_BASE_URL"),
                obter,
                timeout,
            )
    except Exception:
        # Rede fora, chave errada, proxy corporativo barrando: a UI mostra
        # "não consegui listar" e o campo de digitação manual continua lá.
        # Cair aqui NUNCA pode impedir a Home de abrir.
        return []

    ids = sorted(set(ids))
    if ids:
        _gravar_cache(arquivo_cache, ids, agora)
    return ids


def modelos_recomendados(provider):
    """Os favoritos curados (`config.LLM_FAVORITOS`) DESTE provedor.

    A lista curada não some com o catálogo novo -- ela é a única fonte de
    PREÇO e de tier que o app tem, e a que dá um ponto de partida a quem não
    faz ideia de qual dos 300 modelos do OpenRouter escolher. Ela deixa de
    ser a lista inteira e passa a ser o topo dela.
    """
    return [fav for fav in config.LLM_FAVORITOS if fav["provider"] == provider]

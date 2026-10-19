r"""
Catálogo de modelos por provedor (`sigft.core.llm.catalogo`).

Peça que sustenta a UX "escolha o provedor, veja os modelos daquela chave"
pedida pelo usuário em 2026-08-11. Os três provedores respondem em formatos
diferentes; o que este arquivo garante é que a UI recebe sempre a MESMA coisa
(lista de ids, ordenada) e que nada aqui pode impedir a Home de abrir.

Nada de rede: `http_get` é injetado, como em `providers/openrouter.py`.
"""
import json

import pytest

from sigft import config
from sigft.core.llm import catalogo


class _Resposta:
    def __init__(self, corpo, erro=None):
        self._corpo = corpo
        self._erro = erro

    def raise_for_status(self):
        if self._erro:
            raise self._erro

    def json(self):
        return self._corpo


def _get(corpo, erro=None, registro=None):
    def _http_get(url, headers=None, timeout=None):
        if registro is not None:
            registro.append((url, headers))
        return _Resposta(corpo, erro)

    return _http_get


@pytest.fixture(autouse=True)
def _cache_isolado(tmp_path, monkeypatch):
    """Cada teste com o seu próprio cache -- senão o 1º teste que grava
    contamina todos os outros, e o arquivo vaza para o repositório."""
    monkeypatch.setattr(catalogo, "CACHE_POR_PROVIDER", {
        provider: str(tmp_path / f"{provider}.json")
        for provider in (config.PROVIDER_GEMINI, config.PROVIDER_OPENROUTER,
                         config.PROVIDER_OPENAI_COMPAT)
    })


# --- Gemini -----------------------------------------------------------------

_CORPO_GEMINI = {
    "models": [
        {"name": "models/gemini-3-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.1-pro", "supportedGenerationMethods": ["generateContent"]},
        # Existe na conta mas NÃO gera texto -- escolher isto faria a ficha
        # falhar, então não pode aparecer na lista da UI.
        {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/aqa", "supportedGenerationMethods": ["generateAnswer"]},
    ]
}


def test_gemini_lista_so_os_modelos_que_geram_conteudo():
    ids = catalogo.listar_modelos(
        config.PROVIDER_GEMINI, {"GEMINI": "k"}, http_get=_get(_CORPO_GEMINI), time_fn=lambda: 0,
    )

    assert ids == ["gemini-3-flash", "gemini-3.1-pro"]
    assert "embedding-001" not in ids


def test_gemini_tira_o_prefixo_models_do_id():
    # A API devolve "models/x"; o app grava e usa "x" (é a forma que está em
    # config.LLM_MODELOS_HOJE). Guardar com prefixo mandaria um id inválido
    # para a chamada.
    ids = catalogo.listar_modelos(
        config.PROVIDER_GEMINI, {"GEMINI": "k"}, http_get=_get(_CORPO_GEMINI), time_fn=lambda: 0,
    )

    assert not any(i.startswith("models/") for i in ids)


def test_gemini_manda_a_chave_na_url():
    registro = []
    catalogo.listar_modelos(
        config.PROVIDER_GEMINI, {"GEMINI": "chave-secreta"},
        http_get=_get(_CORPO_GEMINI, registro=registro), time_fn=lambda: 0,
    )

    assert "key=chave-secreta" in registro[0][0]


# --- OpenAI-compatível (AMP da empresa) -------------------------------------

def test_empresa_usa_o_endpoint_padrao_de_models_com_bearer():
    registro = []
    ids = catalogo.listar_modelos(
        config.PROVIDER_OPENAI_COMPAT,
        {"EMPRESA_LLM_BASE_URL": "https://amp.empresa/v1/", "EMPRESA_LLM_API_KEY": "tok"},
        http_get=_get({"data": [{"id": "amp-grande"}, {"id": "amp-rapido"}]}, registro=registro),
        time_fn=lambda: 0,
    )

    assert ids == ["amp-grande", "amp-rapido"]
    url, headers = registro[0]
    assert url == "https://amp.empresa/v1/models"  # a barra do fim não duplica
    assert headers["Authorization"] == "Bearer tok"


def test_empresa_sem_base_url_devolve_lista_vazia_sem_chamar_a_rede():
    registro = []
    ids = catalogo.listar_modelos(
        config.PROVIDER_OPENAI_COMPAT, {"EMPRESA_LLM_API_KEY": "tok"},
        http_get=_get({"data": []}, registro=registro), time_fn=lambda: 0,
    )

    assert ids == []
    assert registro == []  # sem URL não há o que chamar


# --- degradação: nada aqui pode derrubar a Home -----------------------------

@pytest.mark.parametrize("provider", [
    config.PROVIDER_GEMINI, config.PROVIDER_OPENROUTER, config.PROVIDER_OPENAI_COMPAT,
])
def test_falha_de_rede_devolve_lista_vazia_em_vez_de_levantar(provider):
    """O painel de modelos não pode ser o motivo de a Home não abrir. Atrás do
    Zscaler, essas três chamadas falham com regularidade."""
    ids = catalogo.listar_modelos(
        provider,
        {"GEMINI": "k", "OPENROUTER": "k", "EMPRESA_LLM_BASE_URL": "https://x", "EMPRESA_LLM_API_KEY": "k"},
        http_get=_get(None, erro=RuntimeError("SSLError: CERTIFICATE_VERIFY_FAILED")),
        time_fn=lambda: 0,
    )

    assert ids == []


def test_provider_desconhecido_devolve_vazio_sem_tentar_nada():
    assert catalogo.listar_modelos("provedor-que-nao-existe", {}) == []


def test_corpo_com_formato_inesperado_nao_levanta():
    ids = catalogo.listar_modelos(
        config.PROVIDER_GEMINI, {"GEMINI": "k"},
        http_get=_get({"models": ["isto era para ser um objeto"]}), time_fn=lambda: 0,
    )

    assert ids == []


# --- cache ------------------------------------------------------------------

def test_a_segunda_chamada_vem_do_cache_sem_tocar_a_rede():
    # Abrir a Home não pode custar 3 chamadas de rede a cada vez.
    registro = []
    http_get = _get(_CORPO_GEMINI, registro=registro)

    primeira = catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                                       http_get=http_get, time_fn=lambda: 100)
    segunda = catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                                      http_get=http_get, time_fn=lambda: 200)

    assert primeira == segunda
    assert len(registro) == 1


def test_forcar_ignora_o_cache():
    # É o que o botão "Atualizar lista" da UI precisa fazer.
    registro = []
    http_get = _get(_CORPO_GEMINI, registro=registro)

    catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                            http_get=http_get, time_fn=lambda: 100)
    catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"}, forcar=True,
                            http_get=http_get, time_fn=lambda: 100)

    assert len(registro) == 2


def test_cache_expirado_busca_de_novo():
    registro = []
    http_get = _get(_CORPO_GEMINI, registro=registro)

    catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                            http_get=http_get, time_fn=lambda: 0)
    catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"}, ttl_segundos=10,
                            http_get=http_get, time_fn=lambda: 999)

    assert len(registro) == 2


def test_lista_vazia_nao_e_gravada_no_cache():
    """Se gravasse, uma falha de rede envenenaria o cache por um dia inteiro e
    o usuário veria a lista vazia sem entender por quê."""
    caminho = catalogo.CACHE_POR_PROVIDER[config.PROVIDER_GEMINI]
    catalogo.listar_modelos(
        config.PROVIDER_GEMINI, {"GEMINI": "k"},
        http_get=_get(None, erro=RuntimeError("sem rede")), time_fn=lambda: 0,
    )

    import os
    assert not os.path.exists(caminho)


def test_cache_corrompido_e_ignorado_e_nao_derruba():
    caminho = catalogo.CACHE_POR_PROVIDER[config.PROVIDER_GEMINI]
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("{isto nao e json")

    ids = catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                                  http_get=_get(_CORPO_GEMINI), time_fn=lambda: 0)

    assert ids == ["gemini-3-flash", "gemini-3.1-pro"]


def test_o_cache_gravado_e_json_legivel_com_a_hora():
    caminho = catalogo.CACHE_POR_PROVIDER[config.PROVIDER_GEMINI]
    catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                            http_get=_get(_CORPO_GEMINI), time_fn=lambda: 1234)

    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    assert dados["gravado_em"] == 1234
    assert dados["modelos"] == ["gemini-3-flash", "gemini-3.1-pro"]


# --- recomendados -----------------------------------------------------------

def test_recomendados_filtra_os_favoritos_do_provedor():
    for provider in (config.PROVIDER_GEMINI, config.PROVIDER_OPENROUTER):
        favoritos = catalogo.modelos_recomendados(provider)
        assert favoritos, f"{provider} sem favorito curado"
        assert all(f["provider"] == provider for f in favoritos)


def test_recomendados_de_provider_sem_favorito_e_vazio_e_nao_levanta():
    # Hoje é o caso do AMP (`openai_compat`): ninguém sabe os ids dele ainda.
    # A UI tem de aguentar isso sem quebrar -- é o que o catálogo ao vivo
    # resolve para esse provedor.
    assert catalogo.modelos_recomendados(config.PROVIDER_OPENAI_COMPAT) == []


# --- somente_cache: a Home nunca bloqueia -----------------------------------

def test_somente_cache_com_cache_frio_devolve_vazio_sem_tocar_a_rede():
    """Como a Home monta o painel. Uma tela que abre não pode ficar pendurada
    em três chamadas HTTP -- atrás do Zscaler isso é a diferença entre abrir e
    travar. A lista chega depois, pelo botão "Atualizar lista"."""
    registro = []

    ids = catalogo.listar_modelos(
        config.PROVIDER_GEMINI, {"GEMINI": "k"}, somente_cache=True,
        http_get=_get(_CORPO_GEMINI, registro=registro), time_fn=lambda: 0,
    )

    assert ids == []
    assert registro == []


def test_somente_cache_com_cache_quente_devolve_a_lista():
    registro = []
    http_get = _get(_CORPO_GEMINI, registro=registro)
    catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                            http_get=http_get, time_fn=lambda: 0)

    ids = catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                                  somente_cache=True, http_get=http_get, time_fn=lambda: 1)

    assert ids == ["gemini-3-flash", "gemini-3.1-pro"]
    assert len(registro) == 1  # só a primeira, que populou o cache


def test_forcar_vence_somente_cache():
    registro = []
    ids = catalogo.listar_modelos(
        config.PROVIDER_GEMINI, {"GEMINI": "k"}, forcar=True, somente_cache=True,
        http_get=_get(_CORPO_GEMINI, registro=registro), time_fn=lambda: 0,
    )

    assert ids == ["gemini-3-flash", "gemini-3.1-pro"]
    assert len(registro) == 1


# --- a lista que já havia não some (pendências de 2026-09-25) ----------------
#
# (b) A Home monta com `somente_cache` e tratava o cache vencido como ausente:
#     um dia depois de baixado, o catálogo sumia. Para EXIBIR, o de ontem
#     serve melhor que nenhum -- e `consultar` diz de quando ele é.
# (a) A falha do "Atualizar lista" era muda: `[]` e nenhum motivo. Agora o
#     motivo volta em `erro`, e a lista que já havia continua.

_DIA = catalogo.TTL_PADRAO_SEGUNDOS


def _baixar_gemini(quando):
    return catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                                   http_get=_get(_CORPO_GEMINI), time_fn=lambda: quando)


def test_somente_cache_com_cache_vencido_devolve_a_lista_de_ontem_sem_tocar_a_rede():
    _baixar_gemini(1000)
    registro = []

    resultado = catalogo.consultar(
        config.PROVIDER_GEMINI, {"GEMINI": "k"}, somente_cache=True,
        http_get=_get(_CORPO_GEMINI, registro=registro), time_fn=lambda: 1000 + _DIA + 1,
    )

    assert resultado.modelos == ["gemini-3-flash", "gemini-3.1-pro"]
    assert resultado.baixado_em == 1000
    assert resultado.vencido is True
    assert resultado.erro is None
    assert registro == []
    assert catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"}, somente_cache=True,
                                   time_fn=lambda: 1000 + _DIA + 1) == resultado.modelos


def test_cache_dentro_do_prazo_nao_e_vencido_e_diz_de_quando_e():
    _baixar_gemini(1000)

    resultado = catalogo.consultar(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                                   somente_cache=True, time_fn=lambda: 1001)

    assert (resultado.baixado_em, resultado.vencido, resultado.erro) == (1000, False, None)


def test_sem_cache_nenhum_consultar_vem_vazio_sem_data():
    resultado = catalogo.consultar(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                                   somente_cache=True, time_fn=lambda: 0)

    assert (resultado.modelos, resultado.baixado_em, resultado.erro) == ([], None, None)


def test_atualizar_que_falha_devolve_o_motivo_e_mantem_a_lista_que_havia(capsys):
    _baixar_gemini(1000)

    resultado = catalogo.consultar(
        config.PROVIDER_GEMINI, {"GEMINI": "k"}, forcar=True,
        http_get=_get(None, erro=RuntimeError("proxy recusou a conexao")),
        time_fn=lambda: 1000 + 2 * _DIA,
    )

    assert resultado.modelos == ["gemini-3-flash", "gemini-3.1-pro"]
    assert resultado.baixado_em == 1000 and resultado.vencido is True
    assert resultado.erro == "RuntimeError: proxy recusou a conexao"
    assert "proxy recusou a conexao" in capsys.readouterr().out, "o motivo vai para o log"


def test_atualizar_que_falha_sem_lista_anterior_devolve_vazio_com_o_motivo():
    resultado = catalogo.consultar(
        config.PROVIDER_OPENROUTER, {"OPENROUTER": "k"}, forcar=True,
        http_get=_get(None, erro=RuntimeError("HTTP 401")), time_fn=lambda: 0,
    )

    assert resultado.modelos == [] and resultado.baixado_em is None
    assert resultado.erro == "RuntimeError: HTTP 401"


def test_o_motivo_nunca_mostra_a_chave(capsys):
    # O Gemini leva a chave NA URL, e o HTTPError do `requests` repete a URL.
    erro = RuntimeError("403 Client Error: Forbidden for url: "
                        "https://generativelanguage.googleapis.com/v1beta/models?key=AIzaSEGREDO")

    resultado = catalogo.consultar(config.PROVIDER_GEMINI, {"GEMINI": "AIzaSEGREDO"}, forcar=True,
                                   http_get=_get(None, erro=erro), time_fn=lambda: 0)

    assert "AIzaSEGREDO" not in resultado.erro
    assert "403 Client Error" in resultado.erro
    assert "AIzaSEGREDO" not in capsys.readouterr().out


def test_lista_vazia_do_provedor_tambem_vira_motivo_e_nao_apaga_a_que_havia():
    _baixar_gemini(1000)

    resultado = catalogo.consultar(config.PROVIDER_GEMINI, {"GEMINI": "k"}, forcar=True,
                                   http_get=_get({"models": []}), time_fn=lambda: 2000)

    assert resultado.modelos == ["gemini-3-flash", "gemini-3.1-pro"]
    assert resultado.erro and "nenhum modelo" in resultado.erro


def test_busca_automatica_com_cache_vencido_que_falha_fica_com_o_de_ontem():
    _baixar_gemini(1000)

    ids = catalogo.listar_modelos(config.PROVIDER_GEMINI, {"GEMINI": "k"},
                                  http_get=_get(None, erro=RuntimeError("sem rede")),
                                  time_fn=lambda: 1000 + _DIA + 1)

    assert ids == ["gemini-3-flash", "gemini-3.1-pro"]

"""A regra da boas-vindas (2026-10-28): só para quem NUNCA usou o SIG-FT.

Desenho: `docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`,
parte 2. A tela está em `tests/test_qt_boas_vindas.py`.

Cada teste tem a pasta de dados própria (o `conftest` aponta `SIGFT_DADOS_DIR`
para uma pasta nova), então "pasta vazia" é o caso de quem acabou de instalar.
"""
from __future__ import annotations

import json

import pytest

from sigft import _build_info
from sigft.app import boas_vindas
from sigft.core import dados_usuario, prefs


@pytest.fixture(autouse=True)
def _ligada(monkeypatch):
    # O conftest desliga a boas-vindas em todo teste que não a testa.
    monkeypatch.delenv(boas_vindas.ENV_DESLIGAR, raising=False)


def _pasta():
    return dados_usuario.pasta_dados()


def _gravar_prefs(dados: dict) -> None:
    (_pasta() / prefs.CONFIG_FILE).write_text(json.dumps(dados), encoding="utf-8")


# --- quem acabou de instalar ---------------------------------------------------

def test_pasta_de_dados_vazia_mostra():
    assert boas_vindas.deve_mostrar_boas_vindas() is True


def test_o_que_a_primeira_abertura_grava_nao_conta_como_uso():
    # Antes da janela: a pergunta do idioma, o diário e o `sigft.log`. Depois:
    # o nome, a versão vista (novidades), tema e letra. Nada disso é USO.
    logs = dados_usuario.pasta_logs()
    for nome in ("sigft.log", "diario.log", "diario.log.1", "diario.trava", "queda.log",
                 "queda.log.anterior"):
        (logs / nome).write_text("x", encoding="utf-8")
    _gravar_prefs({
        "preferencias": {"idioma": "es", "tema": "claro", "letra": "grande", "nome": "Ana",
                         "nome_ja_perguntado": "sim"},
        "novidades": {"ultima_versao_vista": _build_info.VERSAO},
        "opcoes": {"menu_recolhido": True},
        "ultimos": {}, "categorias": {},
    })
    assert boas_vindas.rastros_de_uso() == []
    assert boas_vindas.deve_mostrar_boas_vindas() is True


def test_novidades_de_uma_versao_anterior_e_uso(monkeypatch):
    # A janela de novidades grava a versão DEPOIS da decisão; achar gravada uma
    # versão diferente da atual é de quem abriu uma versão anterior instalada e
    # atualizou (mesmo sem nunca ter aberto um diálogo de arquivo).
    monkeypatch.setattr(_build_info, "VERSAO", "1.4.0")
    _gravar_prefs({"novidades": {"ultima_versao_vista": "1.3.1"}})
    assert boas_vindas.rastros_de_uso() == ["user_prefs.json:novidades (1.3.1)"]
    assert boas_vindas.deve_mostrar_boas_vindas() is False


def test_novidades_desta_versao_nao_e_uso(monkeypatch):
    # A mesma versão: foi esta instalação que abriu antes (e saiu sem escolher).
    monkeypatch.setattr(_build_info, "VERSAO", "1.4.0")
    _gravar_prefs({"novidades": {"ultima_versao_vista": "1.4.0"}})
    assert boas_vindas.deve_mostrar_boas_vindas() is True


def test_sem_chave_de_api_preenchida_nao_conta():
    (_pasta() / "api_config.json").write_text(json.dumps({"GEMINI": "", "OPENROUTER": "  "}),
                                              encoding="utf-8")
    assert boas_vindas.deve_mostrar_boas_vindas() is True


# --- quem já usava e atualiza ----------------------------------------------------

@pytest.mark.parametrize("secao", boas_vindas.SECOES_DE_USO)
def test_preferencia_de_pasta_ou_arquivo_e_uso(secao):
    _gravar_prefs({secao: {"cria_fichas.lista": "C:/Box/listas"}})
    assert boas_vindas.rastros_de_uso() == [f"user_prefs.json:{secao}"]
    assert boas_vindas.deve_mostrar_boas_vindas() is False


def test_log_de_modulo_e_uso():
    (dados_usuario.pasta_logs() / "duplicadas_2026-08-18_14-32-05.log").write_text("x", encoding="utf-8")
    assert boas_vindas.rastros_de_uso() == ["logs/duplicadas_2026-08-18_14-32-05.log"]
    assert boas_vindas.deve_mostrar_boas_vindas() is False


def test_subpasta_de_logs_com_arquivo_e_uso():
    # O resumo do lote e o diagnóstico do AMP vão para subpastas de `logs/`.
    sub = dados_usuario.pasta_logs() / "amp"
    sub.mkdir()
    assert boas_vindas.deve_mostrar_boas_vindas() is True      # pasta vazia não conta
    (sub / "diagnostico.txt").write_text("x", encoding="utf-8")
    assert boas_vindas.rastros_de_uso() == ["logs/amp"]
    assert boas_vindas.deve_mostrar_boas_vindas() is False


def test_chave_de_api_cadastrada_e_uso():
    (_pasta() / "api_config.json").write_text(json.dumps({"OPENROUTER": "sk-123"}), encoding="utf-8")
    assert boas_vindas.rastros_de_uso() == ["api_config.json"]
    assert boas_vindas.deve_mostrar_boas_vindas() is False


def test_preferencias_ilegiveis_contam_como_uso():
    # Alguém usou (o arquivo existe); e mostrar sem conseguir gravar a vista
    # seria mostrar em toda abertura.
    (_pasta() / prefs.CONFIG_FILE).write_text("{ nao e json", encoding="utf-8")
    assert boas_vindas.deve_mostrar_boas_vindas() is False


# --- já vista ------------------------------------------------------------------

def test_vista_nao_mostra_de_novo():
    assert boas_vindas.deve_mostrar_boas_vindas() is True
    boas_vindas.marcar_vista()
    assert prefs.get_opcao(boas_vindas.CHAVE_VISTA, False) is True
    assert boas_vindas.deve_mostrar_boas_vindas() is False


def test_marcar_vista_preserva_o_resto_das_preferencias():
    _gravar_prefs({"preferencias": {"idioma": "en"}})
    boas_vindas.marcar_vista()
    assert prefs.ler_preferencia("idioma", "") == "en"


def test_marcar_vista_nunca_levanta(monkeypatch):
    def _quebra(*_a, **_k):
        raise OSError("disco cheio")

    monkeypatch.setattr(prefs, "set_opcao", _quebra)
    boas_vindas.marcar_vista()     # não levanta


def test_desligada_pela_variavel(monkeypatch):
    monkeypatch.setenv(boas_vindas.ENV_DESLIGAR, "1")
    assert boas_vindas.deve_mostrar_boas_vindas() is False

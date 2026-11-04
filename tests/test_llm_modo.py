"""A IA por módulo: o modo de cada tarefa e o Workflow AMP na hora de rodar (2026-11-04).

Desenho: `docs/superpowers/specs/2026-11-04-ia-por-modulo-design.md`.
"""
from __future__ import annotations

import json

import pytest

from sigft import config
from sigft.core.amp.cliente import RespostaAmp
from sigft.core.llm import modo, selecao
from sigft.core.llm.client import get_llm
from sigft.core.llm.providers.amp_workflow import AmpWorkflowProvider


@pytest.fixture
def arquivo(tmp_path, monkeypatch):
    caminho = tmp_path / "api_config.json"
    caminho.write_text(json.dumps({"OPENROUTER": "sk-or"}), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))
    return caminho


def test_sem_escolha_e_ia_externa(arquivo):
    assert modo.modo_da_tarefa("validar_ficha", config_path=arquivo) == modo.EXTERNA


def test_escolha_antiga_de_qualquer_provedor_continua_externa(arquivo):
    selecao.definir_por_tarefa("validar_ficha", config.PROVIDER_GEMINI, "gemini-x", config_path=arquivo)
    assert modo.modo_da_tarefa("validar_ficha", config_path=arquivo) == modo.EXTERNA


def test_definir_workflow_e_voltar_para_externa(arquivo):
    modo.definir_workflow("condicoes", config_path=arquivo)
    assert modo.modo_da_tarefa("condicoes", config_path=arquivo) == modo.WORKFLOW
    modo.definir_externa("condicoes", "google/gemini-3-flash", config_path=arquivo)
    assert modo.modo_da_tarefa("condicoes", config_path=arquivo) == modo.EXTERNA
    assert selecao.resolver("condicoes", config_path=arquivo) == {
        "provider": config.PROVIDER_OPENROUTER, "model": "google/gemini-3-flash"}


def test_workflow_de_uma_tarefa_nao_mexe_nas_outras_nem_nas_chaves(arquivo):
    modo.definir_workflow("condicoes", config_path=arquivo)
    assert modo.modo_da_tarefa("tech_specs", config_path=arquivo) == modo.EXTERNA
    assert json.loads(arquivo.read_text(encoding="utf-8"))["OPENROUTER"] == "sk-or"


def test_ia_interna_nao_e_selecionavel(arquivo):
    assert modo.EXTERNA in modo.SELECIONAVEIS and modo.WORKFLOW in modo.SELECIONAVEIS
    assert modo.INTERNA not in modo.SELECIONAVEIS
    with pytest.raises(ValueError):
        modo.definir_modo("condicoes", modo.INTERNA, config_path=arquivo)


def test_nomes_do_webhook_por_tarefa():
    assert modo.chaves_do_webhook("validar_ficha") == ("AMP_IA_VALIDAR_FICHA_URL", "AMP_IA_VALIDAR_FICHA_CHAVE")


def test_tarefa_desconhecida_levanta(arquivo):
    with pytest.raises(ValueError):
        modo.definir_workflow("nao_existe", config_path=arquivo)


def test_toda_tarefa_do_painel_tem_rotulo():
    from sigft.app import ia_por_modulo

    for tarefa in config.TAREFAS_DO_PAINEL:
        assert ia_por_modulo.ROTULOS.get(tarefa)


# -- o provedor do workflow ------------------------------------------------------

class _ClienteFalso:
    def __init__(self, resposta):
        self.resposta = resposta
        self.enviados = []

    def enviar(self, campos, arquivos):
        self.enviados.append((dict(campos), dict(arquivos)))
        return self.resposta


def _resposta(ok=True, dados=None, erro=""):
    return RespostaAmp(ok, "ia", 200 if ok else 500, 0.1, "", dados or {}, erro)


def test_provedor_manda_o_prompt_e_devolve_o_texto():
    cliente = _ClienteFalso(_resposta(dados={"ok": True, "texto": '{"a": 1}'}))
    provider = AmpWorkflowProvider("https://amp/webhook/x", "segredo", tarefa="condicoes", cliente=cliente)
    resultado = provider.generate_raw("o prompt", system="sistema", json_mode=True)
    assert resultado.text == '{"a": 1}'
    campos, arquivos = cliente.enviados[0]
    assert campos == {"modo": "ia", "tarefa": "condicoes", "prompt": "o prompt", "system": "sistema", "json": "sim"}
    assert arquivos == {}


def test_provedor_aceita_resposta_no_lugar_de_texto():
    cliente = _ClienteFalso(_resposta(dados={"ok": True, "resposta": "oi"}))
    provider = AmpWorkflowProvider("https://amp/webhook/x", "k", tarefa="t", cliente=cliente)
    assert provider.generate_raw("p").text == "oi"
    assert "system" not in cliente.enviados[0][0] and "json" not in cliente.enviados[0][0]


def test_provedor_falha_com_erro_legivel():
    cliente = _ClienteFalso(_resposta(ok=False, erro="o AMP recusou a chave (HTTP 403)"))
    provider = AmpWorkflowProvider("https://amp/webhook/x", "k", tarefa="t", cliente=cliente)
    with pytest.raises(RuntimeError, match="recusou a chave"):
        provider.generate_raw("p")


def test_provedor_sem_texto_na_resposta_falha():
    cliente = _ClienteFalso(_resposta(dados={"ok": True}))
    provider = AmpWorkflowProvider("https://amp/webhook/x", "k", tarefa="t", cliente=cliente)
    with pytest.raises(RuntimeError, match="texto"):
        provider.generate_raw("p")


def test_provedor_sem_endereco_falha_antes_de_chamar():
    with pytest.raises(ValueError, match="Workflow AMP"):
        AmpWorkflowProvider("", "k", tarefa="condicoes")


# -- get_llm honra o modo -----------------------------------------------------------

def test_get_llm_com_workflow_monta_o_provedor_do_amp_sem_repetir():
    chaves = {"AMP_IA_CONDICOES_URL": "https://amp/webhook/c", "AMP_IA_CONDICOES_CHAVE": "k"}
    cliente = get_llm("condicoes", chaves=chaves,
                      selecao_resolvida={"provider": config.PROVIDER_AMP_WORKFLOW, "model": modo.MODELO_WORKFLOW})
    assert cliente._provider_name == config.PROVIDER_AMP_WORKFLOW
    assert isinstance(cliente._provider, AmpWorkflowProvider)
    assert cliente._max_retries == 0


def test_get_llm_com_workflow_sem_webhook_explica_o_que_falta():
    with pytest.raises(ValueError, match="Configurar IA"):
        get_llm("condicoes", chaves={},
                selecao_resolvida={"provider": config.PROVIDER_AMP_WORKFLOW, "model": modo.MODELO_WORKFLOW})


def test_get_llm_externa_continua_igual():
    cliente = get_llm("condicoes", chaves={"OPENROUTER": "sk"},
                      selecao_resolvida={"provider": config.PROVIDER_OPENROUTER, "model": "m/x"})
    assert cliente._provider_name == config.PROVIDER_OPENROUTER

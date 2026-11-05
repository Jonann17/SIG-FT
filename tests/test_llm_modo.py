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


# -- os anexos (o AutoSpec manda o PDF e as páginas em imagem) -------------------------

def _anexos():
    from sigft.core.llm.client import Anexo

    return [Anexo(nome="Datasheet X.pdf", mime="application/pdf", dados=b"%PDF-1.7"),
            Anexo(nome="manual.pdf - pagina 3.jpg", mime="image/jpeg", dados=b"\xff\xd8")]


def test_provedor_le_pdf():
    """O agente do AMP lê o arquivo anexado, como na revisão das listas: o AutoSpec manda o PDF."""
    provider = AmpWorkflowProvider("https://amp/webhook/x", "k", tarefa="autospec", cliente=_ClienteFalso(None))
    assert provider.aceita_pdf() is True


def test_provedor_manda_os_anexos_como_arquivos_e_diz_quantos():
    cliente = _ClienteFalso(_resposta(dados={"ok": True, "texto": "{}", "arquivos_recebidos": 2}))
    provider = AmpWorkflowProvider("https://amp/webhook/x", "k", tarefa="autospec", cliente=cliente)
    anexos = _anexos()
    assert provider.generate_raw("p", json_mode=True, anexos=anexos).text == "{}"
    campos, arquivos = cliente.enviados[0]
    assert campos == {"modo": "ia", "tarefa": "autospec", "prompt": "p", "json": "sim", "arquivos": "2"}
    assert arquivos == {"anexo_1": anexos[0], "anexo_2": anexos[1]}


def test_provedor_sem_anexo_nao_manda_o_campo_arquivos():
    cliente = _ClienteFalso(_resposta(dados={"ok": True, "texto": "{}"}))
    AmpWorkflowProvider("https://amp/webhook/x", "k", tarefa="t", cliente=cliente).generate_raw("p", anexos=[])
    assert "arquivos" not in cliente.enviados[0][0] and cliente.enviados[0][1] == {}


def test_provedor_falha_se_o_workflow_nao_confirma_os_arquivos():
    """Um workflow que não passa os arquivos ao agente (o do Cria Fichas, por exemplo) não diz
    quantos recebeu: a resposta não vale, porque o agente respondeu sem ver os documentos. O
    AutoSpec refaz a ficha com o texto extraído."""
    cliente = _ClienteFalso(_resposta(dados={"ok": True, "texto": "{}"}))
    provider = AmpWorkflowProvider("https://amp/webhook/x", "k", tarefa="autospec", cliente=cliente)
    with pytest.raises(RuntimeError, match=r"não confirmou que recebeu os arquivos anexados \(2\)"):
        provider.generate_raw("p", anexos=_anexos())


def test_provedor_falha_se_um_arquivo_se_perdeu():
    cliente = _ClienteFalso(_resposta(dados={"ok": True, "texto": "{}", "arquivos_recebidos": 1}))
    provider = AmpWorkflowProvider("https://amp/webhook/x", "k", tarefa="autospec", cliente=cliente)
    with pytest.raises(RuntimeError, match="recebeu 1 de 2 arquivo"):
        provider.generate_raw("p", anexos=_anexos())


def test_o_llmclient_leva_os_anexos_ate_o_workflow_e_le_o_json():
    """O caminho do AutoSpec: `generate(prompt, json_mode=True, anexos=...)` no `LLMClient`."""
    from sigft.core.llm.client import LLMClient

    cliente = _ClienteFalso(_resposta(dados={"ok": True, "texto": '{"ID1": {"valor": "24 V"}}',
                                             "arquivos_recebidos": 2}))
    llm = LLMClient(AmpWorkflowProvider("https://amp/webhook/a", "k", tarefa="autospec", cliente=cliente),
                    provider_name=config.PROVIDER_AMP_WORKFLOW, model=modo.MODELO_WORKFLOW, max_retries=0)
    resposta = llm.generate("o prompt", json_mode=True, anexos=_anexos(), tags={"tarefa": "autospec"})
    assert resposta.parsed_json == {"ID1": {"valor": "24 V"}}
    campos, arquivos = cliente.enviados[0]
    assert campos["arquivos"] == "2" and campos["json"] == "sim"
    assert [a.nome for a in arquivos.values()] == ["Datasheet X.pdf", "manual.pdf - pagina 3.jpg"]


def test_get_llm_com_workflow_le_pdf():
    """É o `LLMClient.aceita_pdf` que o AutoSpec pergunta antes de anexar o PDF."""
    chaves = {"AMP_IA_AUTOSPEC_URL": "https://amp/webhook/a", "AMP_IA_AUTOSPEC_CHAVE": "k"}
    cliente = get_llm("autospec", chaves=chaves,
                      selecao_resolvida={"provider": config.PROVIDER_AMP_WORKFLOW, "model": modo.MODELO_WORKFLOW})
    assert cliente.aceita_pdf is True


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

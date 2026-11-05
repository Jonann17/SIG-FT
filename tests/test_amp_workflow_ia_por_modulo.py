"""Os workflows do n8n da IA por módulo (`amp/ia_por_modulo/`).

O `.json` que se importa no n8n da GE é gerado pelo `gerar_workflow.py`. Este teste trava que os
dois não se desencontram, que o contrato é o do `core/llm/providers/amp_workflow.py` (o mesmo
`modo`, `prompt` e `texto`), que os ids não repetem os dos outros workflows e que o nó "Prepara a
resposta" recorta o JSON da narração do agente (rodando o código do nó no Node, quando há).
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent / "amp"
PASTA = RAIZ / "ia_por_modulo"


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar_workflow_ia_por_modulo", PASTA / "gerar_workflow.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _workflow(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def _no(workflow, nome):
    return next(n for n in workflow["nodes"] if n["name"] == nome)


GERADOR = _gerador()
MODULOS = sorted(GERADOR.MODULOS)


@pytest.mark.parametrize("modulo", MODULOS)
def test_o_json_versionado_e_o_que_o_gerador_produz(modulo):
    versionado = _workflow(GERADOR.arquivo_do_modulo(modulo))
    assert versionado == GERADOR.montar_workflow(modulo, GERADOR.VERSAO_WORKFLOW)


@pytest.mark.parametrize("modulo", MODULOS)
def test_webhook_agente_e_contrato_do_provedor(modulo):
    m = GERADOR.MODULOS[modulo]
    workflow = _workflow(GERADOR.arquivo_do_modulo(modulo))
    p = _no(workflow, "Webhook do SIG-FT")["parameters"]
    assert (p["path"], p["authentication"], p["responseMode"]) == (m["caminho"], "headerAuth", "responseNode")
    agente = _no(workflow, "AMP Agent")
    assert agente["parameters"]["agentId"]["cachedResultName"] == m["agente"]
    assert agente["onError"] == "continueErrorOutput"
    # O AMP Agent só lê o `chatInput`: é o system + o prompt que o provedor manda.
    monta = _no(workflow, "Monta a mensagem")["parameters"]["assignments"]["assignments"]
    assert [(a["name"], a["value"]) for a in monta] == [("chatInput", GERADOR.EXPR_CHAT)]
    assert "$json.body.prompt" in GERADOR.EXPR_CHAT and "$json.body.system" in GERADOR.EXPR_CHAT
    js = _no(workflow, "Prepara a resposta")["parameters"]["jsCode"]
    assert "modo: 'ia'" in js and "texto" in js
    assert _no(workflow, "Responde sem prompt")["parameters"]["options"]["responseCode"] == 400
    assert _no(workflow, "Responde erro")["parameters"]["options"]["responseCode"] == 502


def test_o_provedor_le_o_campo_que_o_workflow_devolve():
    """O `AmpWorkflowProvider` lê `texto` (ou `resposta`); o workflow devolve `texto`."""
    from sigft.core.llm.providers import amp_workflow

    fonte = Path(amp_workflow.__file__).read_text(encoding="utf-8")
    assert 'dados.get("texto")' in fonte
    assert '"modo": "ia"' in fonte


def test_ids_nao_repetem_os_dos_outros_workflows():
    outros = [RAIZ / "revisao_de_listas" / "workflow_revisao_de_listas.json",
              RAIZ / "criacao_status_pmib" / "workflow_criacao_status_pmib.json"]
    vistos_ids, vistos_webhooks, vistos_caminhos = set(), set(), set()
    for caminho in outros + [GERADOR.arquivo_do_modulo(m) for m in MODULOS]:
        workflow = _workflow(caminho)
        ids = {n["id"] for n in workflow["nodes"]}
        assert vistos_ids.isdisjoint(ids), caminho
        vistos_ids |= ids
        webhook = _no(workflow, "Webhook do SIG-FT")
        assert webhook["webhookId"] not in vistos_webhooks, caminho
        assert webhook["parameters"]["path"] not in vistos_caminhos, caminho
        vistos_webhooks.add(webhook["webhookId"])
        vistos_caminhos.add(webhook["parameters"]["path"])


@pytest.mark.parametrize("modulo", MODULOS)
def test_as_tarefas_do_modulo_existem_no_sigft(modulo):
    from sigft.app.ia_por_modulo import ROTULOS

    for tarefa in GERADOR.MODULOS[modulo]["tarefas"]:
        assert tarefa in ROTULOS, tarefa


@pytest.mark.parametrize("modulo", MODULOS)
def test_o_agente_tem_copia(modulo):
    agente = (PASTA / modulo / "agente.md").read_text(encoding="utf-8")
    for termo in (GERADOR.MODULOS[modulo]["agente"], "A fonte é o AMP", "Responda só com o JSON",
                  "Não invente"):
        assert termo in agente, termo


def _prepara(saida: str, *, tarefa="categorizar_pdm", json_pedido="", tmp_path: Path) -> dict:
    workflow = _workflow(GERADOR.arquivo_do_modulo("cria_fichas"))
    js = _no(workflow, "Prepara a resposta")["parameters"]["jsCode"]
    corpo = json.dumps({"tarefa": tarefa, "json": json_pedido})
    programa = (f"const $input={{first:()=>({{json:{{output:{json.dumps(saida)}}}}})}};\n"
                f"const $=(_n)=>({{first:()=>({{json:{{body:{corpo}}}}})}});\n"
                "const $execution={id:'42'};\n"
                f"const r=(function(){{\n{js}\n}})();\n"
                "console.log(JSON.stringify(r[0].json.resposta));\n")
    arquivo = tmp_path / "prepara.js"
    arquivo.write_text(programa, encoding="utf-8")
    saida_node = subprocess.run(["node", str(arquivo)], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(saida_node.stdout)


SEM_NODE = pytest.mark.skipif(shutil.which("node") is None, reason="sem Node para rodar o código do nó")


@SEM_NODE
def test_prepara_recorta_o_json_da_narracao(tmp_path):
    saida = ('Vou analisar os itens [1 a 15] agora.\n```json\n'
             '[{"item": 1, "pdm_escolhido": "PDM.4820.001 - VALVULA"}]\n```\nPronto!')
    resposta = _prepara(saida, tmp_path=tmp_path)
    assert resposta["ok"] is True and resposta["json_valido"] is True
    assert json.loads(resposta["texto"]) == [{"item": 1, "pdm_escolhido": "PDM.4820.001 - VALVULA"}]
    assert (resposta["modo"], resposta["tarefa"], resposta["execucao"]) == ("ia", "categorizar_pdm", "42")


@SEM_NODE
def test_prepara_sem_json_valido_manda_o_texto_todo(tmp_path):
    """Sem JSON válido, o texto vai inteiro: a leitura tolerante do SIG-FT ainda tenta."""
    resposta = _prepara("Não consegui ler [os itens", tmp_path=tmp_path)
    assert resposta["ok"] is True and resposta["json_valido"] is False
    assert resposta["texto"] == "Não consegui ler [os itens"


@SEM_NODE
def test_prepara_resposta_vazia_e_erro(tmp_path):
    resposta = _prepara("", tmp_path=tmp_path)
    assert resposta["ok"] is False and resposta["etapa"] == "agente"

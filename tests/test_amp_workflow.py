"""O workflow do n8n da revisão das listas (`amp/revisao_de_listas/`).

O `.json` que se importa no n8n da GE é gerado a partir do `pedido.md`; este teste trava que os
dois não se desencontram e que o contrato com o SIG-FT (webhook, ping sem modelo, erro em 502)
continua lá. Desenho: `docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §6.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "amp" / "revisao_de_listas"


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar_workflow", PASTA / "gerar_workflow.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _workflow():
    return json.loads((PASTA / "workflow_revisao_de_listas.json").read_text(encoding="utf-8"))


def _nos(workflow, tipo):
    return [n for n in workflow["nodes"] if n["type"] == tipo]


def _destinos(workflow, nome, saida=0):
    saidas = workflow["connections"].get(nome, {}).get("main", [])
    return [c["node"] for c in (saidas[saida] if len(saidas) > saida else [])]


def test_o_json_versionado_e_o_que_o_gerador_produz():
    gerador = _gerador()
    pedido = (PASTA / "pedido.md").read_text(encoding="utf-8")
    assert _workflow() == gerador.montar_workflow(pedido, gerador.VERSAO_WORKFLOW)


def test_webhook_com_header_auth_e_resposta_por_no():
    [webhook] = _nos(_workflow(), "n8n-nodes-base.webhook")
    p = webhook["parameters"]
    assert (p["httpMethod"], p["path"], p["authentication"], p["responseMode"]) == (
        "POST", "sigft-revisao-listas", "headerAuth", "responseNode")


def test_ping_nao_passa_pelo_agente():
    workflow = _workflow()
    [se] = _nos(workflow, "n8n-nodes-base.if")
    [destino] = _destinos(workflow, se["name"], 0)
    tipos = {n["name"]: n["type"] for n in workflow["nodes"]}
    assert tipos[destino] == "n8n-nodes-base.respondToWebhook"


def test_erro_do_agente_responde_502():
    workflow = _workflow()
    [agente] = _nos(workflow, "@n8n/n8n-nodes-langchain.chainLlm")
    assert agente["onError"] == "continueErrorOutput"
    [destino] = _destinos(workflow, agente["name"], 1)
    no = next(n for n in workflow["nodes"] if n["name"] == destino)
    assert no["type"] == "n8n-nodes-base.respondToWebhook"
    assert no["parameters"]["options"]["responseCode"] == 502


def test_toda_conexao_aponta_para_no_que_existe():
    workflow = _workflow()
    nomes = {n["name"] for n in workflow["nodes"]}
    for origem, saidas in workflow["connections"].items():
        assert origem in nomes
        for saida in saidas["main"]:
            assert all(c["node"] in nomes for c in saida)


def test_o_pedido_carrega_as_regras_da_equipe():
    monta = next(n for n in _workflow()["nodes"] if n["name"] == "Monta o pedido")
    codigo = monta["parameters"]["jsCode"]
    for termo in ("SEM_LISTA_STATUS_PMIB", "OBSERVAÇÕES", "DOCUMENTAL", "a conferir", "tabulação"):
        assert termo in codigo


def test_a_data_de_hoje_vai_na_secao_lista():
    # A linha de revisão nova leva a DATA DE ALTERAÇÃO, e o modelo não sabe que dia é hoje.
    codigo = next(n for n in _workflow()["nodes"] if n["name"] == "Monta o pedido")["parameters"]["jsCode"]
    assert "Data de hoje: ${lista.data_de_hoje" in codigo
    assert "data de hoje, que vem na seção LISTA" in codigo

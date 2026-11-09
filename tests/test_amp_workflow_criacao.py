"""O workflow do n8n da criação do _STATUS_PMIB do zero (`amp/criacao_status_pmib/`).

O `.json` que se importa no n8n da GE é gerado pelo `gerar_workflow.py`. Este teste trava que os
dois não se desencontram e que o contrato é o da revisão das listas, com webhook, agente e modo
próprios. Os ids também são outros, porque o webhookId não pode repetir na instância.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "amp"
PASTA = RAIZ / "criacao_status_pmib"


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar_workflow_criacao", PASTA / "gerar_workflow.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _workflow(pasta=PASTA, nome="workflow_criacao_status_pmib.json"):
    return json.loads((pasta / nome).read_text(encoding="utf-8"))


def _no(workflow, nome):
    return next(n for n in workflow["nodes"] if n["name"] == nome)


def test_o_json_versionado_e_o_que_o_gerador_produz():
    gerador = _gerador()
    assert _workflow() == gerador.montar_workflow(gerador.VERSAO_WORKFLOW)


def test_webhook_e_agente_proprios():
    workflow = _workflow()
    p = _no(workflow, "Webhook do SIG-FT")["parameters"]
    assert (p["path"], p["authentication"], p["responseMode"]) == (
        "sigft-criacao-status-pmib", "headerAuth", "responseNode")
    agente = _no(workflow, "AMP Agent")
    assert agente["parameters"]["agentId"]["cachedResultName"] == "Spare Parts Control Sheet Builder"
    assert agente["onError"] == "continueErrorOutput"
    assert "modo: 'criar'" in _no(workflow, "Prepara a resposta")["parameters"]["jsCode"]


def test_ids_diferentes_dos_da_revisao():
    revisao = _workflow(RAIZ / "revisao_de_listas", "workflow_revisao_de_listas.json")
    criacao = _workflow()
    assert {n["id"] for n in revisao["nodes"]}.isdisjoint({n["id"] for n in criacao["nodes"]})
    assert _no(revisao, "Webhook do SIG-FT")["webhookId"] != _no(criacao, "Webhook do SIG-FT")["webhookId"]


def test_mesmo_contrato_da_revisao():
    revisao = _workflow(RAIZ / "revisao_de_listas", "workflow_revisao_de_listas.json")
    criacao = _workflow()
    assert revisao["connections"] == criacao["connections"]
    assert _no(criacao, "Responde sem arquivos")["parameters"]["options"]["responseCode"] == 400
    assert _no(criacao, "Responde erro")["parameters"]["options"]["responseCode"] == 502


def test_o_agente_tem_copia():
    agente = (PASTA / "agente.md").read_text(encoding="utf-8")
    for termo in ("Spare Parts Control Sheet Builder", "A fonte é o AMP", "nem uma a mais, nem uma a menos",
                  "a conferir", "<tr> e <td>", "colunas de andamento da equipe"):
        assert termo in agente, termo


def test_o_agente_le_so_o_lado_fornecido_das_listas_com_duas_partes():
    """2026-11-09 (pedido do Luan, pelo DocPack Etapa 2): na lista com SOBRESSALENTES CONTRATUAIS à
    esquerda e SOBRESSALENTES FORNECIDOS à direita, só o fornecido vira linha do controle, e o ITEM é
    o do item contratual. Guarda da cópia: é o texto que vai para o AMP."""
    agente = (PASTA / "agente.md").read_text(encoding="utf-8")
    for termo in ("SOBRESSALENTES CONTRATUAIS", "SOBRESSALENTES FORNECIDOS", "O lado contratual nunca vira linha",
                  "o número desse item contratual", "nunca as da esquerda", "Não aplicado",
                  "uma linha por material da lista"):
        assert termo in agente, termo


def test_a_copia_leva_so_as_linhas_abaixo_do_cabecalho():
    """2026-11-09 (pedido do Luan): o cabeçalho é o mesmo do template, e colar ele de novo só atrapalha.
    O botão copia só as linhas dos itens; o cabeçalho continua na tabela, porque o SIG-FT (DocPack Etapa
    2, `docpack_etapa2.ler_tabela`) acha a tabela por ele."""
    agente = (PASTA / "agente.md").read_text(encoding="utf-8")
    assert "copia só as linhas dos itens" in agente
    assert "o cabeçalho continua na tabela" in agente
    assert "na linha do cabeçalho do template" not in agente

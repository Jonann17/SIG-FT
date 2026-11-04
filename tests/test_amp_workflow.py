"""O workflow do n8n da revisão das listas (`amp/revisao_de_listas/`).

O `.json` que se importa (ou cola) no n8n da GE é gerado pelo `gerar_workflow.py`. Este teste trava
que os dois não se desencontram e que o contrato com o SIG-FT continua lá:
- o webhook com a chave;
- o ping sem o agente;
- os arquivos conferidos antes do agente (400);
- o AMP Agent com o agente da revisão, e o erro dele em 502;
- a resposta preparada.

As instruções do agente moram no AMP: `agente.md` é a cópia. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §3 e §4.
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


def _no(workflow, nome):
    return next(n for n in workflow["nodes"] if n["name"] == nome)


def _destinos(workflow, nome, saida=0):
    saidas = workflow["connections"].get(nome, {}).get("main", [])
    return [c["node"] for c in (saidas[saida] if len(saidas) > saida else [])]


def test_o_json_versionado_e_o_que_o_gerador_produz():
    gerador = _gerador()
    assert _workflow() == gerador.montar_workflow(gerador.VERSAO_WORKFLOW)


def test_webhook_com_header_auth_e_resposta_por_no():
    p = _no(_workflow(), "Webhook do SIG-FT")["parameters"]
    assert (p["httpMethod"], p["path"], p["authentication"], p["responseMode"]) == (
        "POST", "sigft-revisao-listas", "headerAuth", "responseNode")


def test_ping_nao_passa_pelo_agente():
    workflow = _workflow()
    assert _destinos(workflow, "Webhook do SIG-FT") == ["É ping?"]
    assert _destinos(workflow, "É ping?", 0) == ["Responde ping"]
    assert _destinos(workflow, "É ping?", 1) == ["É busca?"]
    assert "'ping'" in _no(workflow, "Responde ping")["parameters"]["responseBody"]


def test_a_busca_devolve_o_resultado_guardado_sem_chamar_o_agente():
    workflow = _workflow()
    assert _destinos(workflow, "É busca?", 0) == ["Busca o resultado"]
    assert _destinos(workflow, "É busca?", 1) == ["Monta a mensagem"]
    assert _destinos(workflow, "Busca o resultado") == ["Responde a busca"]
    codigo = _no(workflow, "Busca o resultado")["parameters"]["jsCode"]
    assert "$getWorkflowStaticData('global')" in codigo and "estado: 'pendente'" in codigo


def test_monta_a_mensagem_leva_os_arquivos():
    p = _no(_workflow(), "Monta a mensagem")["parameters"]
    assert p["includeOtherFields"] is True
    [campo] = p["assignments"]["assignments"]
    assert (campo["name"], campo["value"]) == ("chatInput", "={{ $json.body.mensagem }}")


def test_sem_os_arquivos_o_agente_nao_e_chamado():
    workflow = _workflow()
    assert _destinos(workflow, "Chegaram os arquivos?", 0) == ["Responde aceito"]
    assert _destinos(workflow, "Chegaram os arquivos?", 1) == ["Responde sem arquivos"]
    assert _no(workflow, "Responde sem arquivos")["parameters"]["options"]["responseCode"] == 400


def test_responde_na_hora_com_o_pedido_e_o_agente_roda_depois():
    # 2026-11-04: uma lista levou 17 min; o SIG-FT busca o resultado depois.
    workflow = _workflow()
    corpo = _no(workflow, "Responde aceito")["parameters"]["responseBody"]
    assert "estado: 'aceito'" in corpo and "pedido: $execution.id" in corpo and "arquivos:" in corpo
    assert _destinos(workflow, "Responde aceito") == ["AMP Agent"]


def test_o_agente_e_o_da_revisao_e_o_resultado_ou_o_erro_ficam_guardados():
    workflow = _workflow()
    agente = _no(workflow, "AMP Agent")
    assert agente["type"] == "CUSTOM.amp" and agente["onError"] == "continueErrorOutput"
    assert agente["parameters"]["agentId"]["cachedResultName"] == "Spare Parts Document Reviewer"
    assert _destinos(workflow, "AMP Agent", 0) == ["Prepara a resposta"]
    assert _destinos(workflow, "AMP Agent", 1) == ["Prepara o erro"]
    assert _destinos(workflow, "Prepara a resposta") == ["Guarda o resultado"]
    assert _destinos(workflow, "Prepara o erro") == ["Guarda o resultado"]
    guarda = _no(workflow, "Guarda o resultado")["parameters"]["jsCode"]
    assert "$getWorkflowStaticData('global')" in guarda and "LIMITE = 30" in guarda and "VIDA = 7 *" in guarda


def test_a_resposta_corta_a_narracao_e_lista_os_arquivos():
    codigo = _no(_workflow(), "Prepara a resposta")["parameters"]["jsCode"]
    for trecho in ("<!DOCTYPE html|<html", "</html>", "$('Monta a mensagem').first().binary", "arquivos",
                   "o agente não devolveu HTML", "versao_workflow: VERSAO", "'2026-11-04'", "modo: 'revisar'"):
        assert trecho in codigo, trecho


def test_toda_conexao_aponta_para_no_que_existe():
    workflow = _workflow()
    nomes = {n["name"] for n in workflow["nodes"]}
    for origem, saidas in workflow["connections"].items():
        assert origem in nomes
        for saida in saidas["main"]:
            assert all(c["node"] in nomes for c in saida)


def test_o_pedido_saiu_e_o_agente_tem_copia():
    assert not (PASTA / "pedido.md").exists()
    agente = (PASTA / "agente.md").read_text(encoding="utf-8")
    for termo in ("Spare Parts Document Reviewer", "A fonte é o AMP", "SEM_LISTA_STATUS_PMIB", "DOCUMENTAL",
                  "a conferir", "CRIAR", "EXCLUIR", "SUBSTITUIR", "<tr> e <td>"):
        assert termo in agente, termo

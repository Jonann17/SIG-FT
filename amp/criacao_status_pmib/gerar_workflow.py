"""Gera o workflow do n8n da criação do _STATUS_PMIB do zero.

    python amp/criacao_status_pmib/gerar_workflow.py

Grava `workflow_criacao_status_pmib.json` ao lado, para importar (ou colar) no n8n da GE. É o mesmo
desenho do workflow da revisão das listas (`amp/revisao_de_listas/`), testado na GE em 2026-11-03,
com outro webhook, outro agente (o "Spare Parts Control Sheet Builder"; a cópia está em `agente.md`)
e dois arquivos: a lista (o PDF da revisão atual) e o template do _STATUS_PMIB em branco.
`tests/test_amp_workflow_criacao.py` trava que o `.json` versionado é o que este gerador produz.
O `agentId` e a credencial do AMP Agent são os da instância da GE: escolha o agente de novo no nó
depois de importar. Os ids são fixos e diferentes dos da revisão (o webhookId é único no n8n).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "workflow_criacao_status_pmib.json"
VERSAO_WORKFLOW = "2026-11-03"
CAMINHO_WEBHOOK = "sigft-criacao-status-pmib"
NOME_DO_AGENTE = "Spare Parts Control Sheet Builder"
MODELO_DO_AGENTE = "bedrock-claude-sonnet-5.5"
CREDENCIAL_DO_AMP = {"id": "2GcgH0WxCkNN6bg4", "name": "AMP account 1859"}

WEBHOOK = "Webhook do SIG-FT"
E_PING = "É ping?"
MONTA = "Monta a mensagem"
CHEGARAM = "Chegaram os arquivos?"
AGENTE = "AMP Agent"
PREPARA = "Prepara a resposta"

NOTA = """## SIG-FT · Criação do _STATUS_PMIB (AMP)
**Ligar (uma vez):**
1. **Webhook do SIG-FT** → *Credential for Header Auth* → *Create new*: Name `X-SIGFT-Chave`, Value um valor longo e aleatório, **diferente** do da revisão das listas.
2. **AMP Agent** → escolha o agente *Spare Parts Control Sheet Builder* → *Add option* → **Timeout**: o máximo.
3. Salve e **publique**.
4. Copie a **Production URL** do webhook.

As instruções do agente moram no AMP: melhore o agente lá, não aqui.
O pedido leva `modo` (`criar`), `mensagem` e os arquivos `lista` (o PDF) e `template` (o _STATUS_PMIB em branco). O ping responde sem chamar o agente.
Passo a passo: `amp/criacao_status_pmib/LEIA-ME.md`, no repositório do SIG-FT."""

# É o código do nó "Prepara a resposta" colado na GE em 03/11, sem mudança.
JS_PREPARA = r"""// Prepara a resposta ao SIG-FT. As instrucoes do agente moram no AMP, nao aqui.
const VERSAO = '__VERSAO__';
const texto = String($input.first().json.output ?? '');
const binarios = $('__MONTA__').first().binary || {};
const arquivos = Object.values(binarios).map(b => b.fileName || '?');
let html = texto;
const inicio = html.search(/<!DOCTYPE html|<html/i);
if (inicio > 0) html = html.slice(inicio);        // tira a narracao do agente antes do HTML
const fim = html.toLowerCase().lastIndexOf('</html>');
if (fim >= 0) html = html.slice(0, fim + 7);      // e o que vier depois dele
html = html.replace(/\\%/g, '%').trim();          // o agente escreve 100\% no CSS
const ok = /<html|<table/i.test(html);
const resposta = { ok, modo: 'criar', html, arquivos, versao_workflow: VERSAO, execucao: $execution.id };
if (!ok) resposta.erro = 'o agente não devolveu HTML';
return [{ json: { resposta } }];
"""


def _responde(nome: str, id_: str, corpo: str, posicao: list[int], codigo: int | None = None) -> dict:
    return {"parameters": {"respondWith": "json", "responseBody": corpo,
                           "options": {"responseCode": codigo} if codigo else {}},
            "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": posicao, "id": id_,
            "name": nome}


def _se(nome: str, id_: str, id_condicao: str, esquerda: str, operador: dict, direita, posicao: list[int]) -> dict:
    return {"parameters": {"conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [{"id": id_condicao, "leftValue": esquerda, "rightValue": direita,
                                "operator": operador}],
                "combinator": "and"},
            "options": {"looseTypeValidation": True}},
            "type": "n8n-nodes-base.if", "typeVersion": 2, "position": posicao, "id": id_, "name": nome}


def _liga(*destinos: str) -> dict:
    return {"main": [[{"node": d, "type": "main", "index": 0}] for d in destinos]}


def montar_workflow(versao: str) -> dict:
    """O workflow pronto para importar: webhook → ping, ou mensagem → arquivos? → agente → resposta
    (sem arquivos, 400; erro do agente, 502)."""
    v = f"'{versao}'"
    nos = [
        {"parameters": {"content": NOTA, "height": 330, "width": 640}, "type": "n8n-nodes-base.stickyNote",
         "typeVersion": 1, "position": [-40, -300], "id": "a0348457-f93d-51b2-aede-7a21f31e1e13",
         "name": "Como ligar"},
        {"parameters": {"httpMethod": "POST", "path": CAMINHO_WEBHOOK, "authentication": "headerAuth",
                        "responseMode": "responseNode", "options": {}},
         "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 200],
         "id": "3e99dd3c-5164-552e-8936-a1fd01281e63", "name": WEBHOOK,
         "webhookId": "81a5ec75-70b3-5b0f-8995-a84564047541"},
        _se(E_PING, "702215f0-6bdf-5863-af6c-d75ce5861524", "7f5f887b-82c2-550b-825c-420087bf91dd",
            "={{ $json.body.modo }}", {"type": "string", "operation": "equals"}, "ping", [220, 200]),
        _responde("Responde ping", "aad30263-7195-5829-a195-d654bff472b0",
                  "={{ JSON.stringify({ ok: true, modo: 'ping', versao_workflow: %s, execucao: $execution.id }) }}" % v,
                  [460, 40]),
        {"parameters": {"assignments": {"assignments": [{"id": "9bed2c62-f617-53c7-9d1f-9b6d68c29213",
                                                         "name": "chatInput", "value": "={{ $json.body.mensagem }}",
                                                         "type": "string"}]},
                        "includeOtherFields": True, "options": {}},
         "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [460, 300],
         "id": "4dd405f3-4241-51c9-9ac5-39187fa6e343", "name": MONTA},
        _se(CHEGARAM, "b50a8b14-7b1b-5794-9b30-780ac38d1610", "3ae5ee91-f741-52f4-b832-3020ae669973",
            "={{ Object.keys($binary || {}).length }}", {"type": "number", "operation": "gte"}, 2, [700, 300]),
        {"parameters": {"agentId": {"__rl": True,
                                    "value": json.dumps({"agentName": NOME_DO_AGENTE, "model": MODELO_DO_AGENTE},
                                                        separators=(",", ":")),
                                    "mode": "list", "cachedResultName": NOME_DO_AGENTE},
                        "options": {}},
         "type": "CUSTOM.amp", "typeVersion": 1, "position": [940, 200],
         "id": "b5513d5e-8f92-5be1-b9f0-077dc0518d1a", "name": AGENTE,
         "credentials": {"ampOAuth2Api": dict(CREDENCIAL_DO_AMP)}, "onError": "continueErrorOutput"},
        _responde("Responde sem arquivos", "50f538da-51ae-5d6c-93c0-e2f0262736b6",
                  "={{ JSON.stringify({ ok: false, modo: 'criar', etapa: 'arquivos', erro: 'os arquivos não "
                  "chegaram ao agente: o workflow recebeu ' + Object.keys($binary || {}).length + ' arquivo(s)', "
                  "versao_workflow: %s, execucao: $execution.id }) }}" % v, [940, 440], 400),
        {"parameters": {"jsCode": JS_PREPARA.replace("__VERSAO__", versao).replace("__MONTA__", MONTA)},
         "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1180, 120],
         "id": "b493f2f5-9a72-5cf6-ac5f-2384b0d56538", "name": PREPARA},
        _responde("Responde", "845ce42b-079b-573c-a195-1e6e1dd94865", "={{ JSON.stringify($json.resposta) }}",
                  [1420, 120]),
        _responde("Responde erro", "bcea339d-b8cb-5e67-80d3-124c8a33a59e",
                  "={{ JSON.stringify({ ok: false, modo: 'criar', etapa: 'agente', erro: String(($json.error && "
                  "($json.error.message || $json.error)) || 'erro sem mensagem'), versao_workflow: %s, execucao: "
                  "$execution.id }) }}" % v, [1180, 320], 502),
    ]
    conexoes = {
        WEBHOOK: _liga(E_PING),
        E_PING: _liga("Responde ping", MONTA),
        MONTA: _liga(CHEGARAM),
        CHEGARAM: _liga(AGENTE, "Responde sem arquivos"),
        AGENTE: _liga(PREPARA, "Responde erro"),
        PREPARA: _liga("Responde"),
    }
    return {"name": "SIG-FT · Criação do _STATUS_PMIB (AMP)", "nodes": nos, "connections": conexoes,
            "settings": {"executionOrder": "v1"}}


def main(argv: list[str] | None = None) -> int:
    ARQUIVO.write_text(json.dumps(montar_workflow(VERSAO_WORKFLOW), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"Gravado: {ARQUIVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

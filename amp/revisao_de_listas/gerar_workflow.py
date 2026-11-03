"""Gera o workflow do n8n da revisão das listas.

    python amp/revisao_de_listas/gerar_workflow.py

Grava `workflow_revisao_de_listas.json` ao lado, para importar (ou colar) no n8n da GE. É o workflow
colado e testado no n8n da GE em 2026-11-03. As instruções do agente moram no AMP (o "Spare Parts
Document Reviewer"; a cópia está em `agente.md`), e o workflow só leva até ele a mensagem e os
arquivos do SIG-FT. `tests/test_amp_workflow.py` trava que o `.json` versionado é o que este gerador
produz. Os ids são fixos, para o arquivo só mudar quando o conteúdo muda. O `agentId` e a credencial
do AMP Agent são os da instância da GE; noutra, escolha-os de novo no nó. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "workflow_revisao_de_listas.json"
VERSAO_WORKFLOW = "2026-11-03"
CAMINHO_WEBHOOK = "sigft-revisao-listas"
NOME_DO_AGENTE = "Spare Parts Document Reviewer"
MODELO_DO_AGENTE = "bedrock-claude-sonnet-5.5"
CREDENCIAL_DO_AMP = {"id": "2GcgH0WxCkNN6bg4", "name": "AMP account 1859"}

WEBHOOK = "Webhook do SIG-FT"
E_PING = "É ping?"
MONTA = "Monta a mensagem"
CHEGARAM = "Chegaram os arquivos?"
AGENTE = "AMP Agent"
PREPARA = "Prepara a resposta"

NOTA = """## SIG-FT · Revisão das listas (AMP)
**Ligar (uma vez):**
1. **Webhook do SIG-FT** → *Credential for Header Auth* → *Create new*: Name `X-SIGFT-Chave`, Value um valor longo e aleatório. O mesmo valor vai no SIG-FT: PMIB Manager → aba Revisão no AMP → **Webhook…** → Chave.
2. **AMP Agent** → escolha o agente *Spare Parts Document Reviewer* → *Add option* → **Timeout**: o máximo.
3. Salve e **publique**.
4. Copie a **Production URL** do webhook para o SIG-FT: **Webhook…** → Endereço.

As instruções do agente moram no AMP: melhore o agente lá, não aqui.
O SIG-FT manda `modo`, `mensagem` e os arquivos `revisao_em_uso`, `revisao_atual` e `status_pmib`. O ping responde sem chamar o agente.
Passo a passo: `amp/revisao_de_listas/LEIA-ME.md`, no repositório do SIG-FT."""

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
const resposta = { ok, modo: 'revisar', html, arquivos, versao_workflow: VERSAO, execucao: $execution.id };
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
         "typeVersion": 1, "position": [-40, -300], "id": "a1c3e5f7-0b2d-4f61-9a83-c5e7091b3d01",
         "name": "Como ligar"},
        {"parameters": {"httpMethod": "POST", "path": CAMINHO_WEBHOOK, "authentication": "headerAuth",
                        "responseMode": "responseNode", "options": {}},
         "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 200],
         "id": "b2d4f608-1c3e-4072-ab94-d6f8102c4e02", "name": WEBHOOK,
         "webhookId": "c3e50719-2d4f-4183-bca5-e709213d5f03"},
        _se(E_PING, "d4f6182a-3e50-4294-8db6-f81a324e6004", "e5072a3b-4f61-43a5-9ec7-0a2b435f7105",
            "={{ $json.body.modo }}", {"type": "string", "operation": "equals"}, "ping", [220, 200]),
        _responde("Responde ping", "f6183b4c-5072-44b6-afd8-1b3c54608206",
                  "={{ JSON.stringify({ ok: true, modo: 'ping', versao_workflow: %s, execucao: $execution.id }) }}" % v,
                  [460, 40]),
        {"parameters": {"assignments": {"assignments": [{"id": "07294c5d-6183-45c7-b0e9-2c4d65719307",
                                                         "name": "chatInput", "value": "={{ $json.body.mensagem }}",
                                                         "type": "string"}]},
                        "includeOtherFields": True, "options": {}},
         "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [460, 300],
         "id": "183a5d6e-7294-46d8-81fa-3d5e76820408", "name": MONTA},
        _se(CHEGARAM, "294b6e7f-83a5-47e9-920b-4e6f87931509", "3a5c7f80-94b6-48fa-a31c-5f7098a4260a",
            "={{ Object.keys($binary || {}).length }}", {"type": "number", "operation": "gte"}, 2, [700, 300]),
        {"parameters": {"agentId": {"__rl": True,
                                    "value": json.dumps({"agentName": NOME_DO_AGENTE, "model": MODELO_DO_AGENTE},
                                                        separators=(",", ":")),
                                    "mode": "list", "cachedResultName": NOME_DO_AGENTE},
                        "options": {}},
         "type": "CUSTOM.amp", "typeVersion": 1, "position": [940, 200],
         "id": "4b6d8091-a5c7-490b-b42d-6081a9b5370b", "name": AGENTE,
         "credentials": {"ampOAuth2Api": dict(CREDENCIAL_DO_AMP)}, "onError": "continueErrorOutput"},
        _responde("Responde sem arquivos", "5c7e91a2-b6d8-4a1c-853e-7192bac6480c",
                  "={{ JSON.stringify({ ok: false, modo: 'revisar', etapa: 'arquivos', erro: 'os arquivos não "
                  "chegaram ao agente: o workflow recebeu ' + Object.keys($binary || {}).length + ' arquivo(s)', "
                  "versao_workflow: %s, execucao: $execution.id }) }}" % v, [940, 440], 400),
        {"parameters": {"jsCode": JS_PREPARA.replace("__VERSAO__", versao).replace("__MONTA__", MONTA)},
         "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1180, 120],
         "id": "6d8fa2b3-c7e9-4b2d-964f-82a3cbd7590d", "name": PREPARA},
        _responde("Responde", "7e90b3c4-d8fa-4c3e-a750-93b4dce86a0e", "={{ JSON.stringify($json.resposta) }}",
                  [1420, 120]),
        _responde("Responde erro", "8fa1c4d5-e90b-4d4f-b861-a4c5edf97b0f",
                  "={{ JSON.stringify({ ok: false, modo: 'revisar', etapa: 'agente', erro: String(($json.error && "
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
    return {"name": "SIG-FT · Revisão das listas (AMP)", "nodes": nos, "connections": conexoes,
            "settings": {"executionOrder": "v1"}}


def main(argv: list[str] | None = None) -> int:
    ARQUIVO.write_text(json.dumps(montar_workflow(VERSAO_WORKFLOW), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"Gravado: {ARQUIVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

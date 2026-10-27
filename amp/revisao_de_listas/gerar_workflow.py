"""Gera o workflow do n8n da revisão das listas a partir do `pedido.md`.

    python amp/revisao_de_listas/gerar_workflow.py

Grava `workflow_revisao_de_listas.json` ao lado, para importar no n8n da GE. O pedido mora no
`pedido.md` e entra no nó "Monta o pedido"; `tests/test_amp_workflow.py` trava que o `.json`
versionado é o que este gerador produz. Os ids são fixos para o arquivo só mudar quando o
conteúdo muda. O GEV LLM Model (nó da GE) não vai no arquivo: é ligado à mão, como diz a nota.
Desenho: `docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §6.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "workflow_revisao_de_listas.json"
VERSAO_WORKFLOW = "2026-10-27"
CAMINHO_WEBHOOK = "sigft-revisao-listas"

MONTA = "Monta o pedido"
AGENTE = "Agente da revisão"

NOTA = """## Para ligar (uma vez)
1. **Credencial:** no nó **Webhook do SIG-FT**, crie uma *Header Auth* com o nome `X-SIGFT-Chave` e um valor longo e aleatório. O mesmo valor vai no SIG-FT: Configuração → Chaves de API → "AMP Webhook (chave)".
2. **Modelo:** no nó **Agente da revisão**, clique em **Model** e ligue um **GEV LLM Model** (sugestão: Claude Sonnet 5.5).
3. **Salve e publique** o workflow.
4. Copie a **Production URL** do webhook para o SIG-FT: "AMP Webhook (URL)".
5. No SIG-FT, PMIB Manager, aba Revisão no AMP: **Testar conexão com o AMP**. O ping e o eco devem passar.

Ver `amp/revisao_de_listas/LEIA-ME.md` no repositório do SIG-FT."""

JS_RESPOSTA = """// Gerado por amp/revisao_de_listas/gerar_workflow.py. Nao edite aqui.
const VERSAO = %(versao)s;
const modo = $('%(monta)s').first().json.modo;
const texto = String($input.first().json.text ?? '');
const execucao = $execution.id;
if (modo === 'eco') {
  return [{ json: { resposta: { ok: true, modo, texto, versao_workflow: VERSAO, execucao } } }];
}
let html = texto.trim();
const cerca = html.match(/```(?:html)?\\s*([\\s\\S]*?)```/i);
if (cerca) html = cerca[1].trim();
const ok = /<html|<table/i.test(html);
const resposta = { ok, modo, html, versao_workflow: VERSAO, execucao };
if (!ok) resposta.erro = 'o agente não devolveu HTML';
return [{ json: { resposta } }];
"""

JS_PEDIDO = """// Gerado por amp/revisao_de_listas/gerar_workflow.py a partir do pedido.md. Nao edite aqui.
const PEDIDO = %(pedido)s;
const corpo = $input.first().json.body || {};
if (corpo.modo === 'eco') {
  const codigos = (corpo.codigos || []).map(String);
  const prompt = 'Repita exatamente, um por linha e na mesma ordem, os códigos abaixo. '
    + 'Não comente, não corrija e não acrescente nada.\\n\\n' + codigos.join('\\n');
  return [{ json: { modo: 'eco', prompt } }];
}
const secao = (titulo, conteudo) => `## ${titulo}\\n\\n${conteudo}\\n`;
const lista = corpo.lista || {};
const emUso = corpo.revisao_em_uso;
const atual = corpo.revisao_atual || {};
const status = corpo.status_pmib || {};
const partes = [
  PEDIDO,
  secao('LISTA', `Código: ${lista.codigo || ''}\\nRevisão em uso: ${lista.revisao_em_uso || '(nenhuma)'}\\n`
    + `Revisão atual: ${lista.revisao_atual || ''}\\nSTATUS REAL: ${lista.status_real || ''}`),
  secao(`REVISÃO EM USO (${emUso ? emUso.arquivo : 'não há'})`,
    emUso ? emUso.texto : 'A lista ainda não tem revisão em uso: compare só a revisão atual com a _STATUS_PMIB.'),
  secao(`REVISÃO ATUAL (${atual.arquivo || ''})`, atual.texto || ''),
  secao(`_STATUS_PMIB (${status.arquivo || ''}, aba ${status.aba || ''})`,
    `${status.linha_de_revisao || ''}\\n\\n${status.tsv || ''}`),
];
return [{ json: { modo: 'revisar', prompt: partes.join('\\n') } }];
"""


def _responde(nome: str, id_: str, corpo: str, posicao: list[int], codigo: int = 200) -> dict:
    return {
        "parameters": {"respondWith": "json", "responseBody": corpo, "options": {"responseCode": codigo}},
        "id": id_, "name": nome, "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
        "position": posicao,
    }


def _liga(*destinos: str) -> dict:
    return {"main": [[{"node": d, "type": "main", "index": 0}] if d else [] for d in destinos]}


def montar_workflow(pedido: str, versao: str) -> dict:
    """O workflow pronto para importar: webhook → ping, ou pedido → agente → resposta (erro em 502)."""
    versao_js = json.dumps(versao)
    nos = [
        {
            "parameters": {"httpMethod": "POST", "path": CAMINHO_WEBHOOK, "authentication": "headerAuth",
                           "responseMode": "responseNode", "options": {}},
            "id": "6f2b1d0e-1c43-4a7e-9a51-1b0c2f6a7e01", "name": "Webhook do SIG-FT",
            "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 300],
            "webhookId": "9b6f3e2a-5d71-4c0b-8f12-3a9d4e6b7c02",
        },
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [{"id": "1d9c7b4e-2f60-4e8a-b3c5-6a7d8e9f0a03",
                                    "leftValue": "={{ $json.body.modo }}", "rightValue": "ping",
                                    "operator": {"type": "string", "operation": "equals"}}],
                    "combinator": "and",
                },
                "options": {},
            },
            "id": "2e8a6c5d-3b74-4f9b-a4d6-7b8e9f0a1b04", "name": "É ping?",
            "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [220, 300],
        },
        _responde("Responde ping", "3f9b7d6e-4c85-4a0c-b5e7-8c9f0a1b2c05",
                  "={{ JSON.stringify({ ok: true, modo: 'ping', versao_workflow: %s, execucao: $execution.id }) }}"
                  % versao_js, [440, 160]),
        {
            "parameters": {"jsCode": JS_PEDIDO % {"pedido": json.dumps(pedido, ensure_ascii=False)}},
            "id": "4a0c8e7f-5d96-4b1d-86f8-9d0a1b2c3d06", "name": MONTA,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [440, 420],
        },
        {
            "parameters": {"promptType": "define", "text": "={{ $json.prompt }}"},
            "id": "5b1d9f8a-6ea7-4c2e-97a9-ae1b2c3d4e07", "name": AGENTE,
            "type": "@n8n/n8n-nodes-langchain.chainLlm", "typeVersion": 1.5, "position": [660, 420],
            "onError": "continueErrorOutput",
        },
        {
            "parameters": {"jsCode": JS_RESPOSTA % {"versao": versao_js, "monta": MONTA}},
            "id": "6c2eaf9b-7fb8-4d3f-a8ba-bf2c3d4e5f08", "name": "Prepara a resposta",
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [900, 340],
        },
        _responde("Responde", "7d3fb0ac-80c9-4e40-b9cb-c03d4e5f6a09",
                  "={{ JSON.stringify($json.resposta) }}", [1120, 340]),
        _responde("Responde erro", "8e40c1bd-91da-4f51-8adc-d14e5f6a7b10",
                  "={{ JSON.stringify({ ok: false, modo: $('%s').first().json.modo, etapa: 'agente', "
                  "erro: String(($json.error && ($json.error.message || $json.error)) || 'erro sem mensagem'), "
                  "execucao: $execution.id }) }}" % MONTA, [900, 520], codigo=502),
        {
            "parameters": {"content": NOTA, "height": 340, "width": 520},
            "id": "9f51d2ce-a2eb-4062-9bed-e25f6a7b8c11", "name": "Como ligar",
            "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [0, -120],
        },
    ]
    conexoes = {
        "Webhook do SIG-FT": _liga("É ping?"),
        "É ping?": _liga("Responde ping", MONTA),
        MONTA: _liga(AGENTE),
        AGENTE: _liga("Prepara a resposta", "Responde erro"),
        "Prepara a resposta": _liga("Responde"),
    }
    return {"name": "SIG-FT · Revisão das listas (AMP)", "nodes": nos, "connections": conexoes,
            "settings": {"executionOrder": "v1"}}


def main(argv: list[str] | None = None) -> int:
    pedido = (PASTA / "pedido.md").read_text(encoding="utf-8")
    ARQUIVO.write_text(json.dumps(montar_workflow(pedido, VERSAO_WORKFLOW), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"Gravado: {ARQUIVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Gera os workflows do n8n da "IA por módulo" (o modo Workflow AMP de cada tela).

    python amp/ia_por_modulo/gerar_workflow.py

Grava, para cada módulo de `MODULOS`, o `workflow_<módulo>.json` na pasta do módulo
(`amp/ia_por_modulo/<módulo>/`), para importar (ou colar) no n8n da GE.

Diferente da revisão das listas, aqui o SIG-FT já manda o PROMPT INTEIRO (o mesmo que vai ao
OpenRouter, de `core/llm/prompts.py`): o agente de cada módulo, no AMP, tem um system prompt
curto, e as regras de negócio continuam num lugar só, no SIG-FT (decisão do Luan, 2026-11-05).

O contrato é o do `core/llm/providers/amp_workflow.py`: o SIG-FT manda `modo` (`ping` ou `ia`),
`tarefa`, `prompt`, `system` (quando há) e `json` (`sim` quando a tarefa espera JSON); o
workflow devolve `{"ok": true, "modo": "ia", "tarefa": ..., "texto": ...}`. Quando a resposta
deve ser JSON, o nó "Prepara a resposta" recorta o JSON do meio da narração do agente.

`tests/test_amp_workflow_ia_por_modulo.py` trava que o `.json` versionado é o que este gerador
produz. Os ids saem de `uuid5` do módulo e do nó: fixos (o arquivo só muda quando o conteúdo
muda) e diferentes entre módulos (o webhookId não pode repetir na instância). O agente e a
credencial do AMP Agent são os da instância da GE: escolha o agente de novo no nó depois de
importar. Desenho: `docs/superpowers/specs/2026-11-04-ia-por-modulo-design.md`.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

PASTA = Path(__file__).resolve().parent
VERSAO_WORKFLOW = "2026-11-05"
MODELO_DO_AGENTE = "bedrock-claude-sonnet-5.5"
CREDENCIAL_DO_AMP = {"id": "2GcgH0WxCkNN6bg4", "name": "AMP account 1859"}
_ESPACO_DOS_IDS = uuid.UUID("5f1c2a9e-3b7d-4e8a-9c61-0d2e4f6a8b10")

# Um workflow (e um agente) por TELA. As tarefas da tela usam o mesmo endereço e a mesma chave.
# `sempre_json`: todas as tarefas da tela respondem JSON (o SIG-FT nem sempre manda `json=sim`).
MODULOS = {
    "cria_fichas": {
        "titulo": "Cria Fichas",
        "caminho": "sigft-ia-cria-fichas",
        "agente": "Spare Parts PDM Classifier",
        "tarefas": ("interpretar_material", "categorizar_pdm"),
        "sempre_json": True,
    },
}

WEBHOOK = "Webhook do SIG-FT"
E_PING = "É ping?"
MONTA = "Monta a mensagem"
TEM_PROMPT = "Chegou o prompt?"
AGENTE = "AMP Agent"
PREPARA = "Prepara a resposta"

NOTA = """## SIG-FT · IA do __TITULO__ (AMP)
**Ligar (uma vez):**
1. **Webhook do SIG-FT** → *Credential for Header Auth* → *Create new*: Name `X-SIGFT-Chave`, Value um valor longo e aleatório, **diferente** do dos outros workflows.
2. **AMP Agent** → escolha o agente *__AGENTE__* → *Add option* → **Timeout**: o máximo.
3. Salve e **publique**.
4. Copie a **Production URL** do webhook. No SIG-FT: __TITULO__ → **Configurar IA** → *Workflow AMP*, em cada tarefa (__TAREFAS__): o mesmo endereço e a mesma chave.

O agente tem só um system prompt curto: as instruções da tarefa vêm do SIG-FT, no `prompt`.
O pedido leva `modo` (`ia`), `tarefa`, `prompt`, `system` e `json`. O ping responde sem chamar o agente.
Passo a passo: `amp/ia_por_modulo/LEIA-ME.md`, no repositório do SIG-FT."""

# O texto que vai ao agente: a instrução de sistema (quando há) antes do prompt.
EXPR_CHAT = ("={{ [$json.body.system, $json.body.prompt].filter(t => t && String(t).trim())"
             ".join('\\n\\n') }}")

JS_PREPARA = r"""// Prepara a resposta ao SIG-FT. As instrucoes da tarefa vem do SIG-FT, no prompt.
const VERSAO = '__VERSAO__';
const SEMPRE_JSON = __SEMPRE_JSON__;
const pedido = $('__WEBHOOK__').first().json.body || {};
const tarefa = String(pedido.tarefa || '');
const querJson = SEMPRE_JSON || String(pedido.json || '') === 'sim';
const bruto = String($input.first().json.output ?? '').trim();

// O primeiro trecho que e JSON valido: de um [ ou { ate o ] ou } que fecha. O agente
// as vezes narra antes ("Vou analisar os itens [1 a 15]...") ou poe ```json em volta.
function recortaJson(texto) {
  const limpo = texto.replace(/```(?:json)?/gi, '');
  let inicios = 0;
  for (let i = 0; i < limpo.length && inicios < 200; i++) {
    const c = limpo[i];
    if (c !== '[' && c !== '{') continue;
    inicios++;
    const fecha = c === '[' ? ']' : '}';
    let fim = limpo.lastIndexOf(fecha);
    for (let tentativas = 0; fim > i && tentativas < 50; tentativas++) {
      const trecho = limpo.slice(i, fim + 1);
      try { JSON.parse(trecho); return trecho; } catch (e) { /* tenta um fecho antes */ }
      fim = limpo.lastIndexOf(fecha, fim - 1);
    }
  }
  return null;
}

let texto = bruto;
let json_valido = null;
if (querJson && bruto) {
  const recorte = recortaJson(bruto);
  json_valido = recorte !== null;
  if (recorte !== null) texto = recorte;   // sem JSON valido, vai o texto todo: o SIG-FT tenta ler
}
const ok = texto.length > 0;
const resposta = { ok, modo: 'ia', tarefa, texto, json_valido, caracteres_do_agente: bruto.length,
                   versao_workflow: VERSAO, execucao: $execution.id };
if (!ok) { resposta.etapa = 'agente'; resposta.erro = 'o agente respondeu vazio'; }
return [{ json: { resposta } }];
"""


def _id(modulo: str, nome: str) -> str:
    return str(uuid.uuid5(_ESPACO_DOS_IDS, f"{modulo}/{nome}"))


def _responde(modulo: str, nome: str, corpo: str, posicao: list[int], codigo: int | None = None) -> dict:
    return {"parameters": {"respondWith": "json", "responseBody": corpo,
                           "options": {"responseCode": codigo} if codigo else {}},
            "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": posicao,
            "id": _id(modulo, nome), "name": nome}


def _se(modulo: str, nome: str, esquerda: str, operador: dict, direita, posicao: list[int]) -> dict:
    return {"parameters": {"conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [{"id": _id(modulo, nome + "/condicao"), "leftValue": esquerda,
                                "rightValue": direita, "operator": operador}],
                "combinator": "and"},
            "options": {"looseTypeValidation": True}},
            "type": "n8n-nodes-base.if", "typeVersion": 2, "position": posicao, "id": _id(modulo, nome),
            "name": nome}


def _liga(*destinos: str) -> dict:
    return {"main": [[{"node": d, "type": "main", "index": 0}] for d in destinos]}


def montar_workflow(modulo: str, versao: str) -> dict:
    """O workflow pronto para importar: webhook → ping, ou mensagem → prompt? → agente → resposta
    (sem prompt, 400; erro do agente, 502)."""
    m = MODULOS[modulo]
    v = f"'{versao}'"
    nota = (NOTA.replace("__TITULO__", m["titulo"]).replace("__AGENTE__", m["agente"])
            .replace("__TAREFAS__", ", ".join(f"`{t}`" for t in m["tarefas"])))
    js = (JS_PREPARA.replace("__VERSAO__", versao).replace("__WEBHOOK__", WEBHOOK)
          .replace("__SEMPRE_JSON__", "true" if m["sempre_json"] else "false"))
    nos = [
        {"parameters": {"content": nota, "height": 360, "width": 680}, "type": "n8n-nodes-base.stickyNote",
         "typeVersion": 1, "position": [-40, -340], "id": _id(modulo, "nota"), "name": "Como ligar"},
        {"parameters": {"httpMethod": "POST", "path": m["caminho"], "authentication": "headerAuth",
                        "responseMode": "responseNode", "options": {}},
         "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 200],
         "id": _id(modulo, WEBHOOK), "name": WEBHOOK, "webhookId": _id(modulo, "webhookId")},
        _se(modulo, E_PING, "={{ $json.body.modo }}", {"type": "string", "operation": "equals"}, "ping",
            [220, 200]),
        _responde(modulo, "Responde ping",
                  "={{ JSON.stringify({ ok: true, modo: 'ping', versao_workflow: %s, execucao: $execution.id }) }}" % v,
                  [460, 40]),
        {"parameters": {"assignments": {"assignments": [{"id": _id(modulo, MONTA + "/chatInput"),
                                                         "name": "chatInput", "value": EXPR_CHAT,
                                                         "type": "string"}]},
                        "options": {}},
         "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [460, 300],
         "id": _id(modulo, MONTA), "name": MONTA},
        _se(modulo, TEM_PROMPT, "={{ $json.chatInput }}",
            {"type": "string", "operation": "notEmpty", "singleValue": True}, "", [700, 300]),
        {"parameters": {"agentId": {"__rl": True,
                                    "value": json.dumps({"agentName": m["agente"], "model": MODELO_DO_AGENTE},
                                                        separators=(",", ":")),
                                    "mode": "list", "cachedResultName": m["agente"]},
                        "options": {}},
         "type": "CUSTOM.amp", "typeVersion": 1, "position": [940, 200],
         "id": _id(modulo, AGENTE), "name": AGENTE,
         "credentials": {"ampOAuth2Api": dict(CREDENCIAL_DO_AMP)}, "onError": "continueErrorOutput"},
        _responde(modulo, "Responde sem prompt",
                  "={{ JSON.stringify({ ok: false, modo: 'ia', etapa: 'prompt', erro: 'o pedido chegou sem "
                  "prompt', versao_workflow: %s, execucao: $execution.id }) }}" % v, [940, 440], 400),
        {"parameters": {"jsCode": js},
         "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1180, 120],
         "id": _id(modulo, PREPARA), "name": PREPARA},
        _responde(modulo, "Responde", "={{ JSON.stringify($json.resposta) }}", [1420, 120]),
        _responde(modulo, "Responde erro",
                  "={{ JSON.stringify({ ok: false, modo: 'ia', etapa: 'agente', erro: String(($json.error && "
                  "($json.error.message || $json.error)) || 'erro sem mensagem'), versao_workflow: %s, execucao: "
                  "$execution.id }) }}" % v, [1180, 320], 502),
    ]
    conexoes = {
        WEBHOOK: _liga(E_PING),
        E_PING: _liga("Responde ping", MONTA),
        MONTA: _liga(TEM_PROMPT),
        TEM_PROMPT: _liga(AGENTE, "Responde sem prompt"),
        AGENTE: _liga(PREPARA, "Responde erro"),
        PREPARA: _liga("Responde"),
    }
    return {"name": f"SIG-FT · IA do {m['titulo']} (AMP)", "nodes": nos, "connections": conexoes,
            "settings": {"executionOrder": "v1"}}


def arquivo_do_modulo(modulo: str) -> Path:
    return PASTA / modulo / f"workflow_{modulo}.json"


def main(argv: list[str] | None = None) -> int:
    for modulo in MODULOS:
        destino = arquivo_do_modulo(modulo)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(montar_workflow(modulo, VERSAO_WORKFLOW), indent=2, ensure_ascii=False)
                           + "\n", encoding="utf-8")
        print(f"Gravado: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

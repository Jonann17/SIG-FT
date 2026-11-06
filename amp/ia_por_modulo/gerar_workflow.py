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

Módulo `com_arquivos` (o AutoSpec, 2026-11-05): o SIG-FT manda também os documentos, em
`anexo_1`, `anexo_2`... e o campo `arquivos` diz quantos. O "Monta a mensagem" leva os arquivos
adiante (*Include Other Input Fields*, a lição da revisão das listas), o workflow confere que
todos chegaram antes de chamar o agente, e a resposta diz quantos ele recebeu
(`arquivos_recebidos`): sem essa confirmação o SIG-FT não aceita a resposta.

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
VERSAO_WORKFLOW = "2026-11-06"
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
        "onde": "Cria Fichas → **Configurar IA**",
        "sempre_json": True,
        "com_arquivos": False,
        # Decisão do Luan (06/11): o workflow do Cria Fichas, validado na GE em 05/11, não muda.
        # O conserto do "\\%" de 06/11 foi só para o AutoSpec (`JS_PREPARA_2026_11_05`).
        "versao": "2026-11-05",
    },
    # O "onde" é a janela central, que vale para todas as telas; o botão "Configurar IA" chegou
    # à tela do AutoSpec depois (2026-11-05), e a nota não mudou para o .json importado continuar
    # igual. As duas chamadas (preencher a ficha e conferir o fornecedor) são a mesma tarefa,
    # `autospec`, e levam os documentos.
    "autospec": {
        "titulo": "AutoSpec",
        "caminho": "sigft-ia-autospec",
        "agente": "Spare Parts Datasheet Reader",
        "tarefas": ("autospec",),
        "onde": "engrenagem da Home → **Modelos de IA** → *AutoSpec (RAG)*",
        "sempre_json": True,
        "com_arquivos": True,
    },
}

WEBHOOK = "Webhook do SIG-FT"
E_PING = "É ping?"
MONTA = "Monta a mensagem"
TEM_PROMPT = "Chegou o prompt?"
TEM_PEDIDO = "Chegou o pedido?"            # com arquivos: o prompt e todos os arquivos
SEM_PROMPT = "Responde sem prompt"
INCOMPLETO = "Responde pedido incompleto"   # com arquivos
AGENTE = "AMP Agent"
PREPARA = "Prepara a resposta"

NOTA = """## SIG-FT · IA do __TITULO__ (AMP)
**Ligar (uma vez):**
1. **Webhook do SIG-FT** → *Credential for Header Auth* → *Create new*: Name `X-SIGFT-Chave`, Value um valor longo e aleatório, **diferente** do dos outros workflows.
2. **AMP Agent** → escolha o agente *__AGENTE__* → *Add option* → **Timeout**: o máximo.
3. Salve e **publique**.
4. Copie a **Production URL** do webhook. No SIG-FT: __ONDE__ → *Workflow AMP*, __TAREFAS__.

O agente tem só um system prompt curto: as instruções da tarefa vêm do SIG-FT, no `prompt`.
O pedido leva `modo` (`ia`), `tarefa`, `prompt`, `system` e `json`__ARQUIVOS_NOTA__. O ping responde sem chamar o agente.
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

// O agente escreve "\%" dentro do JSON (como no HTML da revisao das listas), e o JSON so
// aceita \" \\ \/ \b \f \n \r \t \u: a barra antes de outro caractere sai.
function consertaEscapes(trecho) {
  return trecho.replace(/\\([\s\S])/g, (par, c) => ('"\\/bfnrtu'.includes(c) ? par : c));
}

// Onde fecha o bloco que abre em i ({ ou [), contando as chaves fora das strings; -1 se
// ele nao fecha (resposta cortada) ou fecha com o sinal trocado.
function fimDoBloco(t, i) {
  const pilha = [];
  let emString = false, escape = false;
  for (let j = i; j < t.length; j++) {
    const d = t[j];
    if (emString) {
      if (escape) escape = false;
      else if (d === '\\') escape = true;
      else if (d === '"') emString = false;
      continue;
    }
    if (d === '"') emString = true;
    else if (d === '{' || d === '[') pilha.push(d === '{' ? '}' : ']');
    else if (d === '}' || d === ']') {
      if (pilha.pop() !== d) return -1;
      if (pilha.length === 0) return j;
    }
  }
  return -1;
}

function leJson(trecho) {
  for (const versao of [trecho, consertaEscapes(trecho)]) {
    try { JSON.parse(versao); return versao; } catch (e) { /* tenta o conserto */ }
  }
  return null;
}

// O JSON do meio da resposta: o primeiro bloco { } ou [ ] DE FORA que e JSON, inteiro. O
// agente as vezes narra antes ("Vou analisar os itens [1 a 15]...") ou poe ```json em
// volta. Um bloco que nao e JSON e pulado INTEIRO, sem olhar dentro: em 06/11 o objeto do
// primeiro campo saiu no lugar da ficha. Um bloco que nao fecha encerra a busca.
function recortaJson(texto) {
  const t = texto.replace(/```(?:json)?/gi, '');
  for (let i = 0; i < t.length; i++) {
    if (t[i] !== '{' && t[i] !== '[') continue;
    const fim = fimDoBloco(t, i);
    if (fim < 0) return null;
    const lido = leJson(t.slice(i, fim + 1));
    if (lido !== null) return lido;
    i = fim;
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
__ARQUIVOS__if (!ok) { resposta.etapa = 'agente'; resposta.erro = 'o agente respondeu vazio'; }
return [{ json: { resposta } }];
"""


# Os arquivos que chegaram ao agente (o SIG-FT confere a conta, `arquivos_recebidos`, quando
# mandou anexo). No código de 2026-11-06 vai em todo módulo (sem arquivos, conta zero).
JS_ARQUIVOS = """const binarios = $('__MONTA__').first().binary || {};
resposta.arquivos = Object.values(binarios).map(b => b.fileName || '?');
resposta.arquivos_recebidos = resposta.arquivos.length;
"""

NOTA_ARQUIVOS = (", e os documentos em `anexo_1`, `anexo_2`... (o campo `arquivos` diz quantos). O *Monta a "
                 "mensagem* leva os arquivos ao agente (*Include Other Input Fields*), e o workflow confere que "
                 "todos chegaram antes de chamá-lo")


def nomes_do_modulo(modulo: str) -> dict:
    """Os nomes dos nós que mudam quando o módulo manda arquivos."""
    if MODULOS[modulo]["com_arquivos"]:
        return {"checa": TEM_PEDIDO, "recusa": INCOMPLETO}
    return {"checa": TEM_PROMPT, "recusa": SEM_PROMPT}


# O código do nó como ele foi validado no Cria Fichas em 05/11, sem mudar uma letra. O recorte
# dele desce para dentro do JSON quando o objeto não abre (o `\\%` do agente): é o defeito que o
# `JS_PREPARA` de 2026-11-06 conserta, e que o Luan escolheu não levar para o Cria Fichas.
JS_PREPARA_2026_11_05 = r"""// Prepara a resposta ao SIG-FT. As instrucoes da tarefa vem do SIG-FT, no prompt.
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

# O código do nó de cada versão do workflow; módulo sem "versao" usa a atual (`VERSAO_WORKFLOW`).
CODIGOS_DO_PREPARA = {"2026-11-05": JS_PREPARA_2026_11_05, VERSAO_WORKFLOW: JS_PREPARA}


def _id(modulo: str, nome: str) -> str:
    return str(uuid.uuid5(_ESPACO_DOS_IDS, f"{modulo}/{nome}"))


def _responde(modulo: str, nome: str, corpo: str, posicao: list[int], codigo: int | None = None) -> dict:
    return {"parameters": {"respondWith": "json", "responseBody": corpo,
                           "options": {"responseCode": codigo} if codigo else {}},
            "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": posicao,
            "id": _id(modulo, nome), "name": nome}


def _se(modulo: str, nome: str, esquerda: str, operador: dict, direita, posicao: list[int],
        extras: tuple = ()) -> dict:
    """Um nó If; `extras` são outras condições `(esquerda, operador, direita)`, todas com "e"."""
    condicoes = [{"id": _id(modulo, nome + "/condicao"), "leftValue": esquerda,
                  "rightValue": direita, "operator": operador}]
    condicoes += [{"id": _id(modulo, f"{nome}/condicao{numero}"), "leftValue": e, "rightValue": d, "operator": o}
                  for numero, (e, o, d) in enumerate(extras, start=2)]
    return {"parameters": {"conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": condicoes,
                "combinator": "and"},
            "options": {"looseTypeValidation": True}},
            "type": "n8n-nodes-base.if", "typeVersion": 2, "position": posicao, "id": _id(modulo, nome),
            "name": nome}


def _liga(*destinos: str) -> dict:
    return {"main": [[{"node": d, "type": "main", "index": 0}] for d in destinos]}


def montar_workflow(modulo: str, versao: str | None = None) -> dict:
    """O workflow pronto para importar: webhook → ping, ou mensagem → prompt? → agente → resposta
    (sem prompt, 400; erro do agente, 502)."""
    m = MODULOS[modulo]
    versao = versao or m.get("versao", VERSAO_WORKFLOW)
    v = f"'{versao}'"
    arquivos = m["com_arquivos"]
    nomes = nomes_do_modulo(modulo)
    tarefas = (f"em cada tarefa ({', '.join(f'`{t}`' for t in m['tarefas'])}): o mesmo endereço e a mesma chave"
               if len(m["tarefas"]) > 1 else "o endereço e a chave")
    nota = (NOTA.replace("__TITULO__", m["titulo"]).replace("__AGENTE__", m["agente"])
            .replace("__ONDE__", m["onde"]).replace("__TAREFAS__", tarefas)
            .replace("__ARQUIVOS_NOTA__", NOTA_ARQUIVOS if arquivos else ""))
    js = (CODIGOS_DO_PREPARA[versao].replace("__VERSAO__", versao).replace("__WEBHOOK__", WEBHOOK)
          .replace("__SEMPRE_JSON__", "true" if m["sempre_json"] else "false")
          .replace("__ARQUIVOS__", JS_ARQUIVOS.replace("__MONTA__", MONTA)))
    if arquivos:
        recusa = ("={{ JSON.stringify({ ok: false, modo: 'ia', etapa: $json.chatInput ? 'arquivos' : 'prompt', "
                  "erro: $json.chatInput ? 'os arquivos não chegaram ao agente: o workflow recebeu ' + "
                  "Object.keys($binary || {}).length + ' de ' + ($json.body.arquivos || 0) + ' arquivo(s)' : "
                  "'o pedido chegou sem prompt', versao_workflow: %s, execucao: $execution.id }) }}" % v)
        todos_os_arquivos = (("={{ Object.keys($binary || {}).length }}", {"type": "number", "operation": "gte"},
                              "={{ Number($json.body.arquivos || 0) }}"),)
    else:
        recusa = ("={{ JSON.stringify({ ok: false, modo: 'ia', etapa: 'prompt', erro: 'o pedido chegou sem "
                  "prompt', versao_workflow: %s, execucao: $execution.id }) }}" % v)
        todos_os_arquivos = ()
    monta = {"assignments": {"assignments": [{"id": _id(modulo, MONTA + "/chatInput"), "name": "chatInput",
                                              "value": EXPR_CHAT, "type": "string"}]}}
    if arquivos:
        monta["includeOtherFields"] = True
    monta["options"] = {}
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
        {"parameters": monta,
         "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [460, 300],
         "id": _id(modulo, MONTA), "name": MONTA},
        _se(modulo, nomes["checa"], "={{ $json.chatInput }}",
            {"type": "string", "operation": "notEmpty", "singleValue": True}, "", [700, 300],
            extras=todos_os_arquivos),
        {"parameters": {"agentId": {"__rl": True,
                                    "value": json.dumps({"agentName": m["agente"], "model": MODELO_DO_AGENTE},
                                                        separators=(",", ":")),
                                    "mode": "list", "cachedResultName": m["agente"]},
                        "options": {}},
         "type": "CUSTOM.amp", "typeVersion": 1, "position": [940, 200],
         "id": _id(modulo, AGENTE), "name": AGENTE,
         "credentials": {"ampOAuth2Api": dict(CREDENCIAL_DO_AMP)}, "onError": "continueErrorOutput"},
        _responde(modulo, nomes["recusa"], recusa, [940, 440], 400),
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
        MONTA: _liga(nomes["checa"]),
        nomes["checa"]: _liga(AGENTE, nomes["recusa"]),
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
        destino.write_text(json.dumps(montar_workflow(modulo), indent=2, ensure_ascii=False)
                           + "\n", encoding="utf-8")
        print(f"Gravado: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

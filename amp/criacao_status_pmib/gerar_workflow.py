"""Gera o workflow do n8n da criação do _STATUS_PMIB do zero.

    python amp/criacao_status_pmib/gerar_workflow.py

Grava `workflow_criacao_status_pmib.json` ao lado, para importar (ou colar) no n8n da GE. É o
workflow da revisão das listas (`amp/revisao_de_listas/gerar_workflow.py`, `montar_workflow`), com
a resposta que chega depois (o pedido na hora; o resultado guardado e buscado com `modo=buscar`),
com outro webhook, outro agente (o "Spare Parts Control Sheet Builder"; a cópia está em
`agente.md`), o modo `criar` e dois arquivos: a lista (o PDF da revisão atual) e o template do
_STATUS_PMIB em branco. Os ids saem de uma semente própria: o webhookId não repete na instância.
`tests/test_amp_workflow_criacao.py` trava que o `.json` versionado é o que este gerador produz.
O `agentId` e a credencial do AMP Agent são os da instância da GE: escolha o agente de novo no nó.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "workflow_criacao_status_pmib.json"
CAMINHO_WEBHOOK = "sigft-criacao-status-pmib"
NOME_DO_AGENTE = "Spare Parts Control Sheet Builder"


def _revisao():
    """O gerador da revisão das listas (amp/ não é pacote: carrega pelo caminho)."""
    caminho = PASTA.parent / "revisao_de_listas" / "gerar_workflow.py"
    spec = importlib.util.spec_from_file_location("gerar_workflow_revisao", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_BASE = _revisao()
VERSAO_WORKFLOW = _BASE.VERSAO_WORKFLOW

NOTA = """## SIG-FT · Criação do _STATUS_PMIB (AMP)
**Ligar (uma vez):**
1. **Webhook do SIG-FT** → *Credential for Header Auth* → *Create new*: Name `X-SIGFT-Chave`, Value um valor longo e aleatório, **diferente** do da revisão das listas.
2. **AMP Agent** → escolha o agente *Spare Parts Control Sheet Builder* → *Add option* → **Timeout**: o máximo.
3. Salve e **publique** (o resultado só fica guardado nas execuções de produção).
4. Copie a **Production URL** do webhook.

As instruções do agente moram no AMP: melhore o agente lá, não aqui.
Três modos: `ping` (responde sem chamar o agente); `criar` (os arquivos `lista`, o PDF, e `template`, o _STATUS_PMIB em branco, e a `mensagem`: responde na hora com o pedido, e o agente roda depois); `buscar` (o `pedido`: devolve o resultado guardado, ou `pendente`).
Passo a passo: `amp/criacao_status_pmib/LEIA-ME.md`, no repositório do SIG-FT."""


def montar_workflow(versao: str) -> dict:
    return _BASE.montar_workflow(versao, caminho=CAMINHO_WEBHOOK, agente=NOME_DO_AGENTE, modo="criar",
                                 nome="SIG-FT · Criação do _STATUS_PMIB (AMP)", nota=NOTA,
                                 semente_dos_ids="sigft-criacao-status-pmib")


def main(argv: list[str] | None = None) -> int:
    ARQUIVO.write_text(json.dumps(montar_workflow(VERSAO_WORKFLOW), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"Gravado: {ARQUIVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""O modo de IA de cada módulo: IA Externa, IA Interna (AMP) ou Workflow AMP (2026-11-04).

Pedido do Luan: a escolha da IA é por módulo (por tarefa de `config.TAREFAS_DO_PAINEL`).
Não há campo novo no `api_config.json`: o modo é DERIVADO da seleção por tarefa de
`core/llm/selecao.py` -- o provedor `config.PROVIDER_AMP_WORKFLOW` é o Workflow AMP, e
qualquer outro (o OpenRouter, ou uma escolha antiga de Gemini) é a IA Externa. Assim o
que já estava salvo continua rodando igual, e a central e o botão "Configurar IA" de cada
tela gravam no mesmo lugar.

A IA Interna aparece na tela, mas não é selecionável enquanto o AMP não tiver API.

O webhook de cada módulo fica nas chaves, com os nomes `AMP_IA_<TAREFA>_URL` e
`AMP_IA_<TAREFA>_CHAVE` (o esquema de `app_qt/widgets/webhook_amp.py`).
Desenho: `docs/superpowers/specs/2026-11-04-ia-por-modulo-design.md`.
"""
from __future__ import annotations

import os

from sigft import config
from sigft.core.llm import selecao

EXTERNA = "externa"
INTERNA = "interna"
WORKFLOW = "workflow"
MODOS = (EXTERNA, INTERNA, WORKFLOW)
SELECIONAVEIS = (EXTERNA, WORKFLOW)

# O "modelo" gravado com o Workflow AMP: quem escolhe o modelo é o workflow, no n8n.
MODELO_WORKFLOW = "workflow"


def chaves_do_webhook(tarefa: str) -> tuple[str, str]:
    """Os nomes do endereço e da chave do webhook da `tarefa` no `api_config.json`."""
    base = f"AMP_IA_{tarefa.upper()}"
    return f"{base}_URL", f"{base}_CHAVE"


def modo_da_tarefa(tarefa: str, *, config_path: str | os.PathLike[str] = config.CONFIG_FILE) -> str:
    """`WORKFLOW` se a tarefa está no Workflow AMP; `EXTERNA` em qualquer outro caso."""
    escolha = selecao.resolver(tarefa, config_path=config_path)
    if escolha and escolha.get("provider") == config.PROVIDER_AMP_WORKFLOW:
        return WORKFLOW
    return EXTERNA


def modelo_externo(tarefa: str, *, config_path: str | os.PathLike[str] = config.CONFIG_FILE) -> dict | None:
    """A escolha de IA Externa que vale para a tarefa (a dela, ou a global), ou `None`."""
    escolha = selecao.resolver(tarefa, config_path=config_path)
    if escolha and escolha.get("provider") != config.PROVIDER_AMP_WORKFLOW:
        return escolha
    estado = selecao.carregar(config_path=config_path)
    return estado.get("global")


def definir_externa(tarefa: str, modelo: str, *, provider: str = config.PROVIDER_OPENROUTER,
                    config_path: str | os.PathLike[str] = config.CONFIG_FILE) -> None:
    selecao.definir_por_tarefa(tarefa, provider, modelo, config_path=config_path)


def definir_workflow(tarefa: str, *, config_path: str | os.PathLike[str] = config.CONFIG_FILE) -> None:
    selecao.definir_por_tarefa(tarefa, config.PROVIDER_AMP_WORKFLOW, MODELO_WORKFLOW,
                               config_path=config_path)


def definir_modo(tarefa: str, modo: str, *, modelo: str = "",
                 config_path: str | os.PathLike[str] = config.CONFIG_FILE) -> None:
    """Grava o `modo` da tarefa. A IA Interna não é selecionável (sem API do AMP)."""
    if modo == WORKFLOW:
        definir_workflow(tarefa, config_path=config_path)
    elif modo == EXTERNA and modelo:
        definir_externa(tarefa, modelo, config_path=config_path)
    elif modo == EXTERNA:
        selecao.limpar_por_tarefa(tarefa, config_path=config_path)
    else:
        raise ValueError(f"Modo de IA não selecionável: {modo!r} (selecionáveis: {', '.join(SELECIONAVEIS)}).")

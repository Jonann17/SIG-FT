"""Os textos da IA por módulo, sem biblioteca gráfica (2026-11-04).

`ROTULOS` é o nome de cada tarefa de IA na tela: a central ("Modelos de IA") e o botão
"Configurar IA" de cada módulo usam os mesmos. `TAREFAS_DA_TELA` diz quais tarefas cada
tela configura. Desenho: `docs/superpowers/specs/2026-11-04-ia-por-modulo-design.md`.
"""
from __future__ import annotations

from sigft.app.idioma import marcar
from sigft.core.llm import modo

ROTULOS = {
    "categorizar_pdm": marcar("Categorizar PDM (Cria Fichas):"),
    "validar_ficha": marcar("Validar ficha (Analyzer):"),
    "condicoes": marcar("Condições (Upload Condições):"),
    "tech_specs": marcar("Caract. Técnicas (Upload Specs):"),
    "autospec": marcar("AutoSpec (RAG):"),
    "interpretar_material": marcar("Interpretar material (Cria Fichas):"),
    "traduzir_pdm": marcar("Traduzir PDM (Planilhas PMIB):"),
    "docpack_pasta": marcar("Etapa 1: Estrutura (DocPack):"),
    # [2026-11-05] Módulos que só rodam por um workflow do AMP (`SO_WORKFLOW`).
    "docpack_conteudo": marcar("Etapa 2: Conteúdo (DocPack):"),
    "revisao_amp": marcar("Revisão no AMP (Conferência de Listas):"),
}

# [2026-11-05] Os módulos que NÃO são uma tarefa de LLM: só rodam pelo workflow do AMP, e o
# "Configurar IA" deles é só o webhook. O valor é (nome do endereço, nome da chave, nomes
# antigos adotados uma vez) no `api_config.json` -- os MESMOS que as abas usavam no botão
# "Webhook…" (nada migra).
SO_WORKFLOW = {
    "docpack_conteudo": ("AMP_CRIACAO_STATUS_PMIB_URL", "AMP_CRIACAO_STATUS_PMIB_CHAVE", None),
    "revisao_amp": ("AMP_REVISAO_LISTAS_URL", "AMP_REVISAO_LISTAS_CHAVE",
                    ("AMP_WEBHOOK_URL", "AMP_WEBHOOK_CHAVE")),
}
DICA_SO_WORKFLOW = marcar("Este módulo só roda pelo workflow do AMP.")

# A chave é a classe da tela (o nome em `app_qt/main.TELAS`); o valor, as tarefas dela.
TAREFAS_DA_TELA = {
    "ModuloCriaFichas": ("categorizar_pdm", "interpretar_material"),
    "ModuloAnalyzer": ("validar_ficha",),
    "ModuloUploadConditions": ("condicoes",),
    "ModuloUploadTechSpecs": ("tech_specs",),
    "ModuloPDM": ("traduzir_pdm",),
    # A seção DocPack (abas embutidas, sem cabeçalho): o botão fica no cabeçalho da seção.
    "ModuloDocPackSecao": ("docpack_pasta", "docpack_conteudo"),
    "ModuloConferenciaListas": ("revisao_amp",),
}

NOMES_DOS_MODOS = {
    modo.EXTERNA: marcar("IA Externa"),
    modo.INTERNA: marcar("IA Interna (AMP)"),
    modo.WORKFLOW: marcar("Workflow AMP"),
}

EXPLICACAO_DOS_MODOS = {
    modo.EXTERNA: marcar("O OpenRouter: um modelo do catálogo, com a chave do OpenRouter."),
    modo.INTERNA: marcar("Em breve: o AMP ainda não tem API para escolher um modelo."),
    modo.WORKFLOW: marcar("Um workflow do AMP (n8n) responde por este módulo: endereço e chave do webhook."),
}

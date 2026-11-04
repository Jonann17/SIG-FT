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
    "docpack_pasta": marcar("Sugerir pasta (DocPack):"),
}

# A chave é a classe da tela (o nome em `app_qt/main.TELAS`); o valor, as tarefas dela.
TAREFAS_DA_TELA = {
    "ModuloCriaFichas": ("categorizar_pdm", "interpretar_material"),
    "ModuloAnalyzer": ("validar_ficha",),
    "ModuloUploadConditions": ("condicoes",),
    "ModuloUploadTechSpecs": ("tech_specs",),
    "ModuloPDM": ("traduzir_pdm",),
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

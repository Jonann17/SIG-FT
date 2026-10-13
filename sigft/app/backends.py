"""Registro central dos backends que o splash carrega — Checkpoint 7.3.

O problema que este módulo resolve
----------------------------------
Até aqui, o splash fazia ``globals()[nome] = modulo``, injetando cada backend
no namespace do **`frontend.py`**. Funcionava porque as 12 telas moravam
naquele mesmo arquivo e liam aquelas mesmas globais.

O CP 7.3 move as telas para `sigft/app/views/*.py`. Cada view passa a ter o
seu próprio namespace, e `globals()` do splash deixa de alcançá-las: as telas
enxergariam `None` para sempre.

E esse defeito seria **silencioso do pior jeito**. Não quebra o import, não
quebra o `compileall`, não quebra a suíte (que não importa o `frontend.py`), e
nem sequer quebra a ABERTURA do app — a tela monta normalmente, porque montar
não usa o backend. Só quebra quando o usuário clica em "processar", com um
`AttributeError: 'NoneType' object has no attribute ...`, em 12 telas de uma
vez.

Por que não simplesmente importar o backend no topo de cada view
---------------------------------------------------------------
Porque mataria o splash. Ele existe para mostrar progresso ENQUANTO os
módulos pesados (pandas, playwright, os SDKs de IA) são importados — são eles
que fazem a abertura demorar. Com `from sigft.services import pdm` no topo de
cada view, tudo é importado no instante em que `main.py` importa as views, ou
seja, ANTES de qualquer janela aparecer: a barra de progresso viraria
decoração e o usuário encararia vários segundos de tela preta.

Como funciona
-------------
Um módulo só, importado por todos. O splash preenche os atributos; as views
leem `backends.pdm_backend.alguma_coisa()` **no momento da chamada**, não no
import. Como todos compartilham o mesmo objeto-módulo, quem preenche e quem lê
enxergam a mesma coisa.

A regra prática para quem escreve uma view: **nunca faça
``from sigft.app.backends import pdm_backend``**. Isso copia o valor no
instante do import — que é `None` — e o nome local nunca mais é atualizado.
Sempre `from sigft.app import backends` e depois `backends.pdm_backend`.
Há um teste garantindo isso (`test_app_backends.py`).
"""
from __future__ import annotations

import importlib

# --- Os nomes, começando em None -------------------------------------------
# Mantidos IDÊNTICOS aos que o `frontend.py` usava, para que mover uma tela
# seja trocar `pdm_backend.x` por `backends.pdm_backend.x` e nada mais.
DataManager = None
GeminiCategorizer = None
AutomacaoPMIB = None
pdm_backend = None
analyzer_backend = None
translator_backend = None
upload_conditions_backend = None
upload_tech_specs_backend = None
autospec_backend = None
lmr_backend = None
apagar_lmr_backend = None
pmib_manager_backend = None
search_pmib_backend = None


# [Qt6] O motivo de cada backend que não carregou, por nome de destino
# ("pdm_backend", "mixed_classes"...). Antes a falha só ia para o console da
# splash, e a tela quebrava depois com `AttributeError: 'NoneType'`.
falhas: dict[str, BaseException] = {}


class BackendIndisponivel(RuntimeError):
    """O backend que a tela pediu não carregou. A mensagem é para a pessoa."""


# --- O que carregar, e com que nome aparecer na barra de progresso ----------
# Formato: (módulo, atributo de destino, classes específicas, nome exibido).
# Copiado do `SplashScreen.carregar_modulos`, na mesma ORDEM — a ordem é o que
# o usuário vê na barra, e mudá-la mudaria a aparência da abertura.
MODULOS = [
    (
        "cria_fichas_no_pmib_v1_backend",
        "mixed_classes",
        ["DataManager", "GeminiCategorizer", "AutomacaoPMIB"],
        "Gerador de Fichas",
    ),
    ("pdm_backend", "pdm_backend", None, "Processamento PDM"),
    ("analyzer_backend", "analyzer_backend", None, "Analisador IA"),
    ("translator_backend", "translator_backend", None, "Tradutor Técnico"),
    ("upload_conditions_backend", "upload_conditions_backend", None, "Upload de Condições"),
    ("upload_tech_specs_backend", "upload_tech_specs_backend", None, "Upload de Specs"),
    ("autospec_backend", "autospec_backend", None, "AutoSpec RAG"),
    ("lmr_backend", "lmr_backend", None, "Automação LMR"),
    ("apagar_lmr_backend", "apagar_lmr_backend", None, "Ferramenta de Limpeza"),
    ("pmib_manager_backend", "pmib_manager_backend", None, "Gerenciador PMIB"),
    ("search_pmib_backend", "search_pmib_backend", None, "Search PMIB"),
]


def carregar_um(nome_modulo: str, destino: str, classes=None) -> None:
    """Importa UM backend e guarda no registro.

    `destino="mixed_classes"` reproduz o caso especial do
    `cria_fichas_no_pmib_v1_backend`, de onde o `frontend.py` extraía três
    CLASSES em vez de guardar o módulo.
    """
    modulo = importlib.import_module(nome_modulo)
    globais = globals()

    if destino == "mixed_classes":
        for nome_classe in classes or []:
            globais[nome_classe] = getattr(modulo, nome_classe)
    else:
        globais[destino] = modulo


def carregar_todos(ao_progredir=None, ao_falhar=None, pausa_fn=None) -> None:
    """Carrega os 11 módulos na ordem, avisando o progresso.

    `ao_progredir(nome_exibido, fracao)` é chamado ANTES de cada import (para
    a barra dizer o que está carregando agora) e `ao_falhar(nome_exibido, erro)`
    quando um deles estoura.

    Uma falha NÃO interrompe os demais — era o comportamento do splash, e é o
    certo: um backend quebrado (falta de dependência, por exemplo) deixa UMA
    tela sem funcionar, não o aplicativo inteiro sem abrir.
    """
    total = len(MODULOS)
    for i, (nome_modulo, destino, classes, exibido) in enumerate(MODULOS):
        try:
            if ao_progredir is not None:
                ao_progredir(exibido, (i + 1) / total)
            if pausa_fn is not None:
                pausa_fn()
            carregar_um(nome_modulo, destino, classes)
        except Exception as erro:  # noqa: BLE001 — ver docstring
            falhas[destino] = erro
            if ao_falhar is not None:
                ao_falhar(exibido, erro)


def esta_carregado(nome: str) -> bool:
    """`True` se o backend `nome` já foi carregado (útil em teste e diagnóstico)."""
    return globals().get(nome) is not None


def motivo_da_falha(nome: str) -> str | None:
    erro = falhas.get(nome)
    return None if erro is None else f"{type(erro).__name__}: {erro}"


def exigir(nome: str):
    """O backend `nome`, ou `BackendIndisponivel` com o motivo em português."""
    objeto = globals().get(nome)
    if objeto is not None:
        return objeto
    motivo = motivo_da_falha(nome)
    if motivo is None:
        raise BackendIndisponivel(
            f"O módulo '{nome}' ainda não foi carregado. Espere a abertura terminar.")
    raise BackendIndisponivel(
        f"Este módulo não carregou: {motivo}\n\n"
        "O detalhe está em Documentos\\SIG-FT\\logs\\sigft.log.")

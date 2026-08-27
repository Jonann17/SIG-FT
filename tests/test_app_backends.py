"""Testes de `sigft/app/backends.py` — Checkpoint 7.3 (Fase 7).

Este módulo existe para consertar um defeito que o CP 7.3 CRIARIA se ninguém
pensasse nele: o splash injetava os backends em `globals()` do `frontend.py`,
o que só alcançava as telas enquanto elas moravam naquele arquivo.

O defeito seria silencioso do pior jeito — não quebra import, `compileall`,
suíte, nem a abertura do app. A tela monta (montar não usa backend) e só
estoura quando o usuário clica em processar, com `AttributeError: 'NoneType'`.
Em 12 telas de uma vez.

Por isso o teste que mais importa aqui é o da seção C: provar que quem lê
`backends.X` no momento da chamada ENXERGA o que o splash carregou depois, e
que quem faz `from ... import X` não enxerga.
"""
from __future__ import annotations

import sys
import types

import pytest

from sigft.app import backends


@pytest.fixture(autouse=True)
def registro_limpo():
    """Cada teste começa e termina com o registro zerado.

    O registro é estado de MÓDULO — sem isto, um teste que carrega um backend
    contaminaria os seguintes, e a suíte passaria a depender da ordem.
    """
    nomes = [n for n, _, _, _ in backends.MODULOS if n != "cria_fichas_no_pmib_v1_backend"]
    nomes += ["DataManager", "GeminiCategorizer", "AutomacaoPMIB"]
    antes = {n: getattr(backends, n, None) for n in nomes}
    for n in nomes:
        setattr(backends, n, None)
    yield
    for n, v in antes.items():
        setattr(backends, n, v)


# =============================================================================
# A. A lista — é o que o usuário vê na barra de progresso
# =============================================================================

def test_carrega_os_11_modulos_do_splash():
    assert len(backends.MODULOS) == 11


def test_a_ordem_e_a_do_splash():
    """Mudar a ordem muda o que o usuário lê durante a abertura."""
    esperado = [
        "cria_fichas_no_pmib_v1_backend",
        "pdm_backend",
        "analyzer_backend",
        "translator_backend",
        "upload_conditions_backend",
        "upload_tech_specs_backend",
        "autospec_backend",
        "lmr_backend",
        "apagar_lmr_backend",
        "pmib_manager_backend",
        "search_pmib_backend",
    ]
    assert [m[0] for m in backends.MODULOS] == esperado


def test_nomes_exibidos_sao_amigaveis_nao_nomes_de_arquivo():
    exibidos = [m[3] for m in backends.MODULOS]
    assert "Gerador de Fichas" in exibidos
    assert "Analisador IA" in exibidos
    for nome in exibidos:
        assert "_backend" not in nome, nome


def test_o_caso_especial_das_tres_classes():
    """`cria_fichas_no_pmib_v1_backend` dá 3 CLASSES, não um módulo."""
    modulo, destino, classes, _ = backends.MODULOS[0]
    assert destino == "mixed_classes"
    assert classes == ["DataManager", "GeminiCategorizer", "AutomacaoPMIB"]


def test_todo_nome_do_registro_comeca_none():
    for nome, destino, classes, _ in backends.MODULOS:
        alvos = classes if destino == "mixed_classes" else [destino]
        for alvo in alvos:
            assert hasattr(backends, alvo), alvo
            assert getattr(backends, alvo) is None, alvo


# =============================================================================
# B. carregar_um
# =============================================================================

def _instalar_modulo_falso(nome, **atributos):
    modulo = types.ModuleType(nome)
    for k, v in atributos.items():
        setattr(modulo, k, v)
    sys.modules[nome] = modulo
    return modulo


def test_carregar_um_guarda_o_modulo_no_registro(monkeypatch):
    falso = _instalar_modulo_falso("modulo_falso_x", processar=lambda: "feito")
    monkeypatch.setitem(sys.modules, "modulo_falso_x", falso)

    backends.carregar_um("modulo_falso_x", "pdm_backend")

    assert backends.pdm_backend is falso
    assert backends.pdm_backend.processar() == "feito"


def test_carregar_um_com_mixed_classes_extrai_as_classes(monkeypatch):
    class A: pass
    class B: pass

    falso = _instalar_modulo_falso("modulo_falso_y", DataManager=A, GeminiCategorizer=B)
    monkeypatch.setitem(sys.modules, "modulo_falso_y", falso)

    backends.carregar_um("modulo_falso_y", "mixed_classes", ["DataManager", "GeminiCategorizer"])

    assert backends.DataManager is A
    assert backends.GeminiCategorizer is B


def test_esta_carregado_reflete_o_estado():
    assert not backends.esta_carregado("pdm_backend")
    backends.pdm_backend = object()
    assert backends.esta_carregado("pdm_backend")


# =============================================================================
# C. O ponto do módulo: quem lê `backends.X` vê o que foi carregado DEPOIS
# =============================================================================

def test_uma_view_le_o_backend_carregado_depois_dela_ser_importada():
    """O cenário real: a view é importada com o registro vazio, e só usa o
    backend quando o usuário clica — muito depois de o splash carregar."""

    class TelaFalsa:
        """Como uma view deve ser escrita."""

        def processar(self):
            return backends.pdm_backend.processar()

    tela = TelaFalsa()                      # importada/criada ANTES do splash
    assert backends.pdm_backend is None

    modulo = types.ModuleType("pdm_carregado_depois")
    modulo.processar = lambda: "resultado real"
    backends.pdm_backend = modulo           # o splash carrega

    assert tela.processar() == "resultado real"


def test_from_import_congela_o_None_e_por_isso_e_proibido():
    """Documenta POR QUE a regra existe, com o comportamento medido.

    `from sigft.app.backends import pdm_backend` copia o valor no instante do
    import. Se o splash ainda não rodou — e ele nunca rodou, no import — o
    nome local fica `None` para sempre, mesmo depois de o registro ser
    preenchido.
    """
    from sigft.app.backends import pdm_backend as copia_local

    modulo = types.ModuleType("pdm_novo")
    backends.pdm_backend = modulo

    # O registro enxerga; a cópia local, não. É esta a armadilha.
    assert backends.pdm_backend is modulo
    assert copia_local is None


# =============================================================================
# D. carregar_todos — progresso e tolerância a falha
# =============================================================================

def test_carregar_todos_avisa_o_progresso_de_cada_modulo(monkeypatch):
    vistos = []
    monkeypatch.setattr(backends, "carregar_um", lambda *a, **k: None)

    backends.carregar_todos(ao_progredir=lambda nome, fracao: vistos.append((nome, fracao)))

    assert len(vistos) == 11
    assert vistos[0][0] == "Gerador de Fichas"
    # A fração termina exatamente em 1.0 — barra que para em 0.99 parece travada.
    assert vistos[-1][1] == 1.0


def test_a_fracao_cresce_monotonicamente(monkeypatch):
    fracoes = []
    monkeypatch.setattr(backends, "carregar_um", lambda *a, **k: None)

    backends.carregar_todos(ao_progredir=lambda nome, f: fracoes.append(f))

    assert fracoes == sorted(fracoes)
    assert all(0 < f <= 1.0 for f in fracoes)


def test_um_backend_quebrado_nao_impede_os_outros(monkeypatch):
    """Comportamento do splash, e é o certo: um backend sem dependência deixa
    UMA tela sem funcionar, não o aplicativo inteiro sem abrir."""
    carregados, falhas = [], []

    def carregar_um_falso(nome_modulo, destino, classes=None):
        if nome_modulo == "autospec_backend":
            raise ImportError("faltou uma dependência")
        carregados.append(nome_modulo)

    monkeypatch.setattr(backends, "carregar_um", carregar_um_falso)

    backends.carregar_todos(ao_falhar=lambda nome, erro: falhas.append((nome, str(erro))))

    assert len(carregados) == 10
    assert len(falhas) == 1
    assert falhas[0][0] == "AutoSpec RAG"
    # E os posteriores na lista continuaram.
    assert "search_pmib_backend" in carregados


def test_carregar_todos_funciona_sem_callback_nenhum(monkeypatch):
    monkeypatch.setattr(backends, "carregar_um", lambda *a, **k: None)
    backends.carregar_todos()  # não deve levantar

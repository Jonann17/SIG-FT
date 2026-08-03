r"""
Testes do Checkpoint 5.2 (2ª metade) — `cria_fichas.atualizar_projeto_em_massa`
nos dois motores.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 5 -> CP 5.2: "Migrar
leitura/edição simples: `lmr` e `cria_fichas` (edição em massa)".

`processar_item_individual` NÃO entra aqui: é o CP 5.4, e a guarda que avisa
isso ao usuário tem teste em tests/test_rpa_driver_migration.py.
"""
from __future__ import annotations

import pytest

import sigft.services.cria_fichas as cf
from sigft import config
from sigft.core.rpa.playwright_engine import PlaywrightEngine


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    monkeypatch.setattr(cf.time, "sleep", lambda *_a, **_kw: None)


class _EngineEspiao:
    """Registra a sequência de primitivas. `falhar_em` faz o preenchimento de
    UM seletor específico levantar, para exercitar o caminho de erro."""

    def __init__(self, falhar_em=None):
        self.passos = []
        self.falhar_em = falhar_em

    def goto(self, url):
        self.passos.append(("goto", url))

    def press(self, teclas):
        self.passos.append(("press", teclas))

    def wait_clickable(self, seletor):
        self.passos.append(("wait_clickable", seletor))

    def wait_present(self, seletor):
        self.passos.append(("wait_present", seletor))

    def click_raw(self, seletor):
        self.passos.append(("click_raw", seletor))

    def fill_estrito(self, seletor, texto):
        self.passos.append(("fill_estrito", seletor, texto))
        if seletor == self.falhar_em:
            raise RuntimeError("campo de projeto rejeitou o texto")

    def fill(self, seletor, texto):
        # Presente só para o teste de contraste abaixo poder chamá-la.
        self.passos.append(("fill", seletor, texto))


def _automacao(engine):
    auto = cf.AutomacaoPMIB()
    auto.engine = engine
    return auto


# ===========================================================================
# Caminho feliz
# ===========================================================================
def test_sequencia_completa_de_atualizacao_em_massa():
    engine = _EngineEspiao()

    resultado = _automacao(engine).atualizar_projeto_em_massa("4500063671.0001", "PROJ-NOVO")

    assert resultado == ("SUCESSO", "Salvo.")
    assert engine.passos == [
        ("goto", config.PORTAL_URL),
        ("wait_clickable", cf.XPATH_BUSCA_MASSA),
        ("fill_estrito", cf.XPATH_BUSCA_MASSA, "4500063671.0001"),
        ("press", "ENTER"),
        # Espera a tabela FILTRAR antes de procurar o lápis -- a "espera
        # inteligente" que o código original já fazia.
        ("wait_present", "//tr[contains(., '4500063671.0001')]"),
        ("wait_clickable", cf.XPATH_LAPIS_MASSA.format(pmib="4500063671.0001")),
        ("click_raw", cf.XPATH_LAPIS_MASSA.format(pmib="4500063671.0001")),
        ("wait_clickable", cf.XPATH_CAMPO_PROJETO),
        ("fill_estrito", cf.XPATH_CAMPO_PROJETO, "PROJ-NOVO"),
        ("wait_clickable", cf.XPATH_SALVAR_PROJETO),
        ("click_raw", cf.XPATH_SALVAR_PROJETO),
    ]


def test_espera_a_linha_do_pmib_antes_de_procurar_o_lapis():
    # Sem essa espera, o clique cai na tabela AINDA NÃO FILTRADA e abre a
    # ficha errada -- editando o projeto de outro PMIB.
    engine = _EngineEspiao()

    _automacao(engine).atualizar_projeto_em_massa("4500063671.0001", "P")

    nomes = [p[0] for p in engine.passos]
    assert nomes.index("wait_present") < nomes.index("click_raw")


# ===========================================================================
# Caminho de erro -- a razão de `fill_estrito` existir
# ===========================================================================
def test_falha_ao_preencher_o_projeto_devolve_erro_e_nao_salva():
    engine = _EngineEspiao(falhar_em=cf.XPATH_CAMPO_PROJETO)

    estado, mensagem = _automacao(engine).atualizar_projeto_em_massa("X", "PROJ-NOVO")

    assert estado == "ERRO"
    assert "rejeitou o texto" in mensagem
    assert ("click_raw", cf.XPATH_SALVAR_PROJETO) not in engine.passos


def test_contraste_com_preenchimento_tolerante_salvaria_ficha_errada_como_sucesso():
    """Contraprova permanente da escolha de `fill_estrito` sobre `fill`.

    Este teste NÃO exercita o código de produção: ele reproduz o que
    ACONTECERIA se alguém trocasse `fill_estrito` por `fill` ali, e prova que
    o resultado seria um SUCESSO mentiroso -- a ficha salva sem o código de
    projeto novo, e ninguém confere um SUCESSO. É a diferença entre uma
    falha visível e um dado errado no portal.
    """
    engine = _EngineEspiao(falhar_em=cf.XPATH_CAMPO_PROJETO)
    auto = _automacao(engine)

    # A variante tolerante, simulada: engole a falha do preenchimento.
    def _fill_tolerante(seletor, texto):
        try:
            engine.fill_estrito(seletor, texto)
        except Exception:
            pass

    original = engine.fill_estrito

    def _fill_estrito(seletor, texto):
        if seletor == cf.XPATH_CAMPO_PROJETO:
            return _fill_tolerante(seletor, texto)
        return original(seletor, texto)

    engine.fill_estrito = _fill_estrito

    estado, _ = auto.atualizar_projeto_em_massa("X", "PROJ-NOVO")

    assert estado == "SUCESSO", "a variante tolerante mente sobre o resultado"
    assert ("click_raw", cf.XPATH_SALVAR_PROJETO) in engine.passos, (
        "e pior: salva a ficha sem o código de projeto novo"
    )


# ===========================================================================
# Motor Playwright de verdade (só o browser é duplo)
# ===========================================================================
class _LocatorPW:
    def __init__(self, pagina, seletor):
        self.pagina = pagina
        self.seletor = seletor

    @property
    def first(self):
        return self

    def fill(self, texto):
        self.pagina.acoes.append(("fill", self.seletor, texto))

    def click(self):
        self.pagina.acoes.append(("click", self.seletor))

    def wait_for(self, state):
        self.pagina.acoes.append(("wait_for", self.seletor, state))

    def is_enabled(self):
        return True

    def scroll_into_view_if_needed(self):
        pass


class _KeyboardPW:
    def __init__(self, pagina):
        self.pagina = pagina

    def press(self, tecla):
        self.pagina.acoes.append(("press", tecla))


class _PaginaPW:
    def __init__(self):
        self.acoes = []
        self.url = ""
        self.keyboard = _KeyboardPW(self)

    def locator(self, seletor):
        return _LocatorPW(self, seletor.replace("xpath=", ""))

    def goto(self, url):
        self.url = url
        self.acoes.append(("goto", url))

    def on(self, evento, handler):
        pass


def test_atualizacao_em_massa_roda_sobre_o_playwright_engine_de_verdade():
    auto = cf.AutomacaoPMIB()
    auto.engine = PlaywrightEngine(_PaginaPW())

    resultado = auto.atualizar_projeto_em_massa("4500063671.0001", "PROJ-NOVO")

    assert resultado == ("SUCESSO", "Salvo.")
    acoes = auto.engine.page.acoes
    # O que o portal veria: buscar, ENTER, abrir a ficha, escrever o projeto,
    # salvar.
    assert ("fill", cf.XPATH_BUSCA_MASSA, "4500063671.0001") in acoes
    assert ("press", "Enter") in acoes
    assert ("fill", cf.XPATH_CAMPO_PROJETO, "PROJ-NOVO") in acoes
    assert ("click", cf.XPATH_SALVAR_PROJETO) in acoes
    # E na ordem certa: o projeto é escrito DEPOIS de abrir a ficha.
    assert acoes.index(("click", cf.XPATH_LAPIS_MASSA.format(pmib="4500063671.0001"))) < acoes.index(
        ("fill", cf.XPATH_CAMPO_PROJETO, "PROJ-NOVO")
    )

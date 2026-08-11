r"""
Testes do Checkpoint 5.4 — `cria_fichas.processar_item_individual` nos dois
motores.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 5 -> CP 5.4: "O fluxo por
TAB/active_element é o mais frágil do sistema; reimplementar com seletores
diretos onde o usuário confirmar que o alvo é estável, mantendo a sequência
atual como referência de comportamento."

O que este checkpoint entregou foi o PORTE FIEL: mesmos seletores, mesma
contagem de TABs, mesmos `time.sleep`. A troca por seletores diretos depende
de olhar a tela real e fica para a sessão de validação.

Por isso o teste central aqui é a **sequência exata de teclas e digitação**. É
ela que carrega o fluxo inteiro: cada campo depois do Código do Projeto é
alcançado contando TABs, então um TAB a mais ou a menos escreve o valor no
campo errado -- e o portal aceitaria, sem erro nenhum. Nenhum outro teste
deste projeto pega isso.
"""
from __future__ import annotations

import pytest

import sigft.services.cria_fichas as cf
from sigft.core.rpa.playwright_engine import PlaywrightEngine


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    monkeypatch.setattr(cf.time, "sleep", lambda *_a, **_kw: None)


# ===========================================================================
# Duplo de página
# ===========================================================================
class _Locator:
    def __init__(self, pagina, seletor):
        self.pagina = pagina
        self.seletor = seletor

    @property
    def first(self):
        return self

    def count(self):
        return 1

    def click(self):
        self.pagina.registrar("click", self.seletor)

    def scroll_into_view_if_needed(self):
        pass

    def wait_for(self, state):
        pass

    def is_enabled(self):
        return True

    def text_content(self):
        return self.pagina.textos.get(self.seletor, "")

    def get_attribute(self, nome):
        return self.pagina.atributos.get((self.seletor, nome), "")


class _Keyboard:
    def __init__(self, pagina):
        self.pagina = pagina

    def press(self, tecla):
        self.pagina.registrar("tecla", tecla)

    def type(self, texto):
        self.pagina.registrar("digitou", texto)


class _Pagina:
    def __init__(self):
        self.acoes = []
        self.url = ""
        self.keyboard = _Keyboard(self)
        self.textos = {
            f"xpath={cf.XPATH_CODIGO_PMIB}": "4500063671.0042 - Bomba centrífuga",
        }
        self.atributos = {
            (f"xpath={cf.XPATH_PDM_FINAL}", "data-tooltip"): "  PDM.1234.005  ",
        }

    def registrar(self, *args):
        self.acoes.append(args)

    def locator(self, seletor):
        return _Locator(self, seletor)

    def goto(self, url):
        self.url = url
        self.registrar("goto", url)

    def on(self, evento, handler):
        pass


def _automacao():
    auto = cf.AutomacaoPMIB()
    auto.engine = PlaywrightEngine(_Pagina())
    return auto


_ITEM = {
    "pdm_escolhido": "PDM.1234",
    "descricao_curta": "Bomba centrífuga 3CV",
    "origem": "Nacional",
    "tipo": "Reparável",
    "tipo de fabricação": "Série",
    "codigo_projeto": "PROJ-99",
    "unidade": "peça",
}


def _teclado(auto):
    """Só o que foi para o teclado, na ordem: teclas e textos digitados."""
    return [a for a in auto.engine.page.acoes if a[0] in ("tecla", "digitou")]


# ===========================================================================
# Retorno e captura
# ===========================================================================
def test_pdm_nenhum_pula_sem_tocar_no_browser():
    auto = _automacao()

    assert auto.processar_item_individual({"pdm_escolhido": "NENHUM"}) == (
        "PULAR",
        ("VERIFICAR (PULADO)", "VERIFICAR (PULADO)"),
    )
    assert auto.engine.page.acoes == []


def test_sucesso_devolve_o_codigo_pmib_e_o_pdm_final():
    auto = _automacao()

    estado, (codigo, pdm) = auto.processar_item_individual(dict(_ITEM))

    assert estado == "SUCESSO"
    # O código vem do texto da span, cortado no 1º espaço.
    assert codigo == "4500063671.0042"
    # O PDM vem do atributo `data-tooltip`, só com as pontas aparadas.
    assert pdm == "PDM.1234.005"


def test_volta_para_a_lista_no_fim():
    auto = _automacao()

    auto.processar_item_individual(dict(_ITEM))

    assert auto.engine.page.url == cf.config.PORTAL_URL


def test_falha_no_meio_devolve_erro_sem_levantar():
    # O contrato do chamador é `("ERRO", mensagem)` -- se isto virar exceção,
    # o lote inteiro de criação de fichas cai.
    auto = _automacao()

    def _explode(seletor):
        raise RuntimeError("botão Nova Ficha sumiu")

    auto.engine.wait_clickable = _explode

    estado, mensagem = auto.processar_item_individual(dict(_ITEM))

    assert estado == "ERRO"
    assert "Nova Ficha" in mensagem


# ===========================================================================
# A sequência de TABs — o coração do fluxo
# ===========================================================================
def test_a_sequencia_de_teclas_e_digitacao_e_exatamente_a_do_fluxo_original():
    """Cada campo depois do Código do Projeto é alcançado CONTANDO TABs.

    Um TAB a mais ou a menos escreve o valor no campo errado, e o portal
    aceita sem reclamar -- a ficha sai errada em silêncio. Esta é a asserção
    que segura o CP 5.4 inteiro.
    """
    auto = _automacao()

    auto.processar_item_individual(dict(_ITEM))

    assert _teclado(auto) == [
        # 2. PDM: digita no input que ganhou o foco, confirma.
        ("digitou", "PDM.1234"),
        ("tecla", "Enter"),
        # 3. Contrato: TAB para a opção, ENTER para escolher.
        ("tecla", "Tab"),
        ("tecla", "Enter"),
        # 6. Código do Projeto (o campo foi clicado antes, não tabulado).
        ("digitou", "PROJ-99"),
        # 7. Descrição breve: 1 TAB.
        ("tecla", "Tab"),
        ("digitou", "Bomba centrífuga 3CV"),
        # 8. Origem: 3 TABs, abre o combo, "n" de Nacional, confirma.
        ("tecla", "Tab"),
        ("tecla", "Tab"),
        ("tecla", "Tab"),
        ("tecla", "Enter"),
        ("digitou", "n"),
        ("tecla", "Enter"),
        # 9. Tipo: 1 TAB, abre, "r" de Reparável, confirma.
        ("tecla", "Tab"),
        ("tecla", "Enter"),
        ("digitou", "r"),
        ("tecla", "Enter"),
        # 10. Unidade: 1 TAB, abre, texto da unidade, confirma.
        ("tecla", "Tab"),
        ("tecla", "Enter"),
        ("digitou", "pç"),
        ("tecla", "Enter"),
        # 11. Fabricação: 5 TABs, abre, "s" de Série, confirma.
        ("tecla", "Tab"),
        ("tecla", "Tab"),
        ("tecla", "Tab"),
        ("tecla", "Tab"),
        ("tecla", "Tab"),
        ("tecla", "Enter"),
        ("digitou", "s"),
        ("tecla", "Enter"),
    ]


def test_a_ordem_dos_cliques_segue_os_passos_numerados_do_fluxo():
    auto = _automacao()

    auto.processar_item_individual(dict(_ITEM))

    cliques = [a[1].replace("xpath=", "") for a in auto.engine.page.acoes if a[0] == "click"]
    assert cliques == [
        cf.XPATH_BOTAO_NOVA_FICHA,      # 1
        cf.XPATH_DIV_PESQUISAR_PDM,     # 2 -- a DIV, não o input
        cf.XPATH_DROPDOWN_CONTRATO,     # 3
        cf.XPATH_SALVAR_1,              # 4
        cf.XPATH_CAMPO_PROJETO,         # 6 -- crava o foco antes de digitar
        cf.XPATH_SALVAR_PROJETO,        # 12
    ]


# ===========================================================================
# As escolhas por caractere
# ===========================================================================
@pytest.mark.parametrize(
    "origem, esperado",
    [("Importado", "i"), ("importado", "i"), ("Nacional", "n"), (None, "n"), ("", "n")],
)
def test_origem_escolhe_i_para_importado_e_n_para_o_resto(origem, esperado):
    auto = _automacao()

    auto.processar_item_individual({**_ITEM, "origem": origem})

    digitados = [a[1] for a in _teclado(auto) if a[0] == "digitou"]
    assert digitados[3] == esperado  # PDM, projeto, descrição, ORIGEM


@pytest.mark.parametrize(
    "tipo, esperado",
    [("Não Reparável", "n"), ("não reparável", "n"), ("Reparável", "r"), (None, "r")],
)
def test_tipo_escolhe_n_para_nao_reparavel_e_r_para_o_resto(tipo, esperado):
    auto = _automacao()

    auto.processar_item_individual({**_ITEM, "tipo": tipo})

    digitados = [a[1] for a in _teclado(auto) if a[0] == "digitou"]
    assert digitados[4] == esperado


@pytest.mark.parametrize(
    "fabricacao, esperado", [("Especial", "e"), ("especial", "e"), ("Série", "s"), (None, "s")]
)
def test_fabricacao_escolhe_e_para_especial_e_s_para_o_resto(fabricacao, esperado):
    auto = _automacao()

    auto.processar_item_individual({**_ITEM, "tipo de fabricação": fabricacao})

    digitados = [a[1] for a in _teclado(auto) if a[0] == "digitou"]
    assert digitados[6] == esperado


# ===========================================================================
# Unidade — extraída do fluxo, testável sem browser
# ===========================================================================
@pytest.mark.parametrize(
    "unidade, esperado",
    [
        ("peça", "pç"),
        ("PÇ", "pç"),
        ("peca", "pç"),
        ("metro", "metro - (m)"),
        ("M", "metro - (m)"),
        ("litro", "litro - (l)"),
        ("l", "litro - (l)"),
        ("conjunto", "cj"),
        ("CJ", "cj"),
        ("qualquer outra", "un"),
        (None, "un"),
        ("", "un"),
    ],
)
def test_teclas_da_unidade(unidade, esperado):
    assert cf._teclas_da_unidade(unidade) == esperado


# ===========================================================================
# O seletor CSS que virou XPath
# ===========================================================================
def test_o_xpath_do_pdm_final_casa_a_classe_inteira_e_nao_um_prefixo():
    # Era `div.vscomp-value[data-tooltip^='PDM']`, o ÚNICO seletor CSS do
    # projeto. Em XPath, um `contains(@class, 'vscomp-value')` cru casaria
    # também `vscomp-value-outra-coisa`; o truque do `concat` com espaços
    # exige a classe INTEIRA na lista.
    assert "concat(' ', normalize-space(@class), ' ')" in cf.XPATH_PDM_FINAL
    assert "' vscomp-value '" in cf.XPATH_PDM_FINAL
    assert "starts-with(@data-tooltip, 'PDM')" in cf.XPATH_PDM_FINAL


# ===========================================================================
# O clique tem que levar o FOCO junto (regressão do 1º teste real)
# ===========================================================================
#
# No primeiro teste da Fase 5 contra o PMIB de verdade, a ficha era criada
# até o PDM e MORRIA no Contrato: o campo ficava em branco, o portal marcava
# "Campo obrigatório!" e o robô caía num TimeoutException de mensagem vazia
# (`ERRO no Selenium: Message:`) esperando o Código PMIB que nunca ia
# aparecer, porque o Salvar tinha sido recusado.
#
# Causa: o porte do CP 5.4 trocou os cliques NATIVOS do fluxo original por
# `click_raw`, que no motor Selenium clica por JavaScript
# (`arguments[0].click()`). Um clique sintético dispara o evento mas não
# executa os "focusing steps" do navegador -- o foco não sai do lugar. E
# neste fluxo o clique existe justamente para levar o foco: o que vem depois
# é sempre `digitar_no_foco(...)` ou `press("TAB")`.
#
# Nada disso aparece nos testes de Playwright acima: naquele motor
# `Locator.click()` já é um clique de mouse real. Por isso a regressão só se
# tranca aqui, montando o fluxo sobre o `SeleniumEngine`.
import sigft.core.rpa.selenium_engine as se  # noqa: E402


class _ElSelenium:
    """Elemento do WebDriver: sabe ser clicado nativamente e devolver
    atributos. Registra o clique numa lista COMPARTILHADA, para o teste poder
    contar cliques sem depender de qual instância foi devolvida."""

    def __init__(self, cliques, atributos):
        self._cliques = cliques
        self._atributos = atributos

    def click(self):
        self._cliques.append("nativo")

    def get_attribute(self, nome):
        return self._atributos.get(nome, "")

    def send_keys(self, *args):
        pass


class _WaitSelenium:
    def __init__(self, elemento):
        self.elemento = elemento

    def until(self, condicao):
        return self.elemento


class _DriverSelenium:
    def __init__(self, elemento):
        self.elemento = elemento
        self.scripts = []
        self.urls = []
        self.switch_to = type("_SwitchTo", (), {"active_element": elemento})()

    def execute_script(self, script, *args):
        self.scripts.append(script)

    def get(self, url):
        self.urls.append(url)


def _automacao_selenium():
    cliques = []
    elemento = _ElSelenium(
        cliques,
        {
            "textContent": "4500063671.0042 - Bomba centrífuga",
            "data-tooltip": "  PDM.1234.005  ",
        },
    )
    driver = _DriverSelenium(elemento)
    auto = cf.AutomacaoPMIB()
    auto.engine = se.SeleniumEngine(driver, _WaitSelenium(elemento))
    return auto, driver, cliques


def test_no_selenium_nenhum_clique_do_fluxo_e_feito_por_javascript():
    """A asserção que teria pego o Contrato em branco antes do teste real.

    O fluxo feliz inteiro não tem UM `execute_script` sequer: ler texto e
    atributo é `get_attribute`, digitar é `send_keys` no elemento com foco,
    teclar é `ActionChains`, navegar é `driver.get`. Então qualquer script
    que apareça aqui só pode ser um clique por JS -- e um clique por JS neste
    fluxo é o bug.
    """
    auto, driver, _cliques = _automacao_selenium()

    estado, _ = auto.processar_item_individual(dict(_ITEM))

    assert estado == "SUCESSO"
    assert driver.scripts == [], (
        "clique por JavaScript no fluxo de criação de ficha: o foco não vai "
        f"junto e os TAB/digitação seguintes caem no campo errado -- {driver.scripts}"
    )


def test_no_selenium_os_seis_cliques_do_fluxo_sao_nativos():
    """Contraparte da asserção acima: não basta não ter JS -- os cliques têm
    que ter ACONTECIDO. Sem esta, apagar os cliques passaria no teste
    anterior."""
    auto, _driver, cliques = _automacao_selenium()

    auto.processar_item_individual(dict(_ITEM))

    # Nova Ficha, div do PDM, dropdown do Contrato, Salvar (1º), campo do
    # Código do Projeto, Salvar final -- os mesmos 6 do teste de ordem em
    # Playwright, todos nativos.
    assert cliques == ["nativo"] * 6


# ===========================================================================
# Falha muda vira frase (regressão do 1º teste real)
# ===========================================================================
def _automacao_com_salvar_recusado(tem_marcador_de_obrigatorio):
    """Fluxo onde o Código PMIB NUNCA aparece -- é o que o portal faz quando
    recusa o Salvar por campo em branco."""

    class _LocatorRecusa(_Locator):
        def wait_for(self, state):
            if self.seletor == f"xpath={cf.XPATH_CODIGO_PMIB}":
                # Mensagem VAZIA de propósito: é a assinatura do
                # TimeoutException do Selenium, que foi o que o usuário viu
                # na tela ("ERRO no Selenium: Message:" e mais nada).
                raise RuntimeError("")

        def count(self):
            if self.seletor == f"xpath={cf.XPATH_CAMPO_OBRIGATORIO}":
                return 1 if tem_marcador_de_obrigatorio else 0
            return 1

    class _PaginaRecusa(_Pagina):
        def locator(self, seletor):
            return _LocatorRecusa(self, seletor)

    auto = cf.AutomacaoPMIB()
    auto.engine = PlaywrightEngine(_PaginaRecusa())
    return auto


def test_salvar_recusado_por_campo_obrigatorio_explica_o_que_houve():
    auto = _automacao_com_salvar_recusado(tem_marcador_de_obrigatorio=True)

    estado, mensagem = auto.processar_item_individual(dict(_ITEM))

    assert estado == "ERRO"
    # A frase tem que dizer as duas coisas que faltavam na tela do usuário:
    # que a ficha NÃO foi salva, e onde olhar primeiro.
    assert "nao foi salva" in mensagem
    assert "CONTRATO" in mensagem


def test_sem_marcador_de_obrigatorio_o_erro_original_atravessa_intacto():
    """A sonda é um EXTRA, não um sequestro do erro.

    Se o Código PMIB não apareceu por outro motivo (portal lento, sessão
    caída), quem tem que chegar ao usuário é a falha de verdade -- inventar
    "campo obrigatório" ali mandaria ele procurar no lugar errado.
    """
    auto = _automacao_com_salvar_recusado(tem_marcador_de_obrigatorio=False)

    estado, mensagem = auto.processar_item_individual(dict(_ITEM))

    assert estado == "ERRO"
    assert "obrigat" not in mensagem.lower()


def test_a_sonda_nao_casa_ancestral_e_por_isso_nao_acusa_toda_ficha():
    # `contains(., 'obrigat')` casaria QUALQUER ancestral do texto --
    # inclusive o <body> --, e aí toda ficha que falhasse por qualquer motivo
    # seria diagnosticada como campo obrigatório. `text()` casa só o nó de
    # texto direto.
    assert "text()" in cf.XPATH_CAMPO_OBRIGATORIO
    assert "contains(., " not in cf.XPATH_CAMPO_OBRIGATORIO
    # Sem acento e sem o final da palavra: serve para "obrigatório!",
    # "obrigatória" e "obrigatorio".
    assert "obrigat" in cf.XPATH_CAMPO_OBRIGATORIO
    assert "obrigatório" not in cf.XPATH_CAMPO_OBRIGATORIO

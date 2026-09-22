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

    def is_visible(self):
        """Este dublê representa um portal que ACHA o PDM.

        Desde 2026-09-22 o fluxo confere `XPATH_PDM_NAO_ENCONTRADO` antes de
        apertar ENTER (ver `_buscar_pdm`). "Não encontrado" INVISÍVEL é o que
        significa "o filtro achou" -- que é a premissa de todos os testes
        deste arquivo, cujo assunto é a sequência do caminho feliz. A cascata
        de fallback tem testes próprios, em
        tests/test_cria_fichas_busca_de_pdm.py."""
        return "vscomp-no-search-results" not in self.seletor

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

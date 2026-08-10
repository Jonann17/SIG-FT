r"""
Testes do Checkpoint 5.3 — `sigft/services/tech_specs.py` (a parte de RPA)
rodando sobre os dois motores.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 5 -> CP 5.3: "Migrar uploads:
`upload_conditions` e `upload_tech_specs`. Atenção especial ao
`_preencher_input_com_auditoria` (injeção JS) — em Playwright usar `fill` +
verificação de valor; manter o fallback de aviso de pendência manual."

Este é o módulo que travava a Fase 5: ele passava ELEMENTOS Selenium entre
métodos e fazia buscas relativas a um elemento ("o input DENTRO desta linha"),
coisas que o contrato de `RPAEngine` -- todo por seletor -- não expressa. A
saída escolhida foi XPath INDEXADO: `(//linhas)[3]//input`. Mesmo XPath de
linha, mesmo XPath relativo, só concatenados.

Essa escolha tem um modo de falha próprio e silencioso: **XPath é base 1**.
Um `range` cru geraria `(...)[0]`, que nunca casa com nada -- o robô não
preencheria linha nenhuma e também não daria erro. Vários testes aqui existem
só para prender isso.

Como no CP 5.1/5.2, o serviço roda através das classes de motor DE VERDADE; só
o browser é duplo. O aceite -- a sessão com o usuário no portal real --
continua pendente.
"""
from __future__ import annotations

import pytest

import sigft.services.tech_specs as ts
from sigft.core.rpa.playwright_engine import PlaywrightEngine
from sigft.services.tech_specs import TechSpecsAutomation


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    monkeypatch.setattr(ts.time, "sleep", lambda *_a, **_kw: None)


# ===========================================================================
# Duplo de página: uma tabela com N linhas, cada uma com seus campos
# ===========================================================================
class _LocatorPW:
    def __init__(self, pagina, seletor):
        self.pagina = pagina
        self.seletor = seletor

    @property
    def first(self):
        return self

    def count(self):
        return self.pagina.quantos(self.seletor)

    def fill(self, texto):
        self.pagina.acoes.append(("fill", self.seletor, texto))
        self.pagina.valores[self.seletor] = texto

    def press_sequentially(self, texto):
        self.pagina.acoes.append(("type", self.seletor, texto))
        self.pagina.valores[self.seletor] = texto

    def input_value(self):
        return self.pagina.valores.get(self.seletor, "")

    def text_content(self):
        return self.pagina.textos.get(self.seletor, "")

    def click(self):
        self.pagina.acoes.append(("click", self.seletor))

    def focus(self):
        self.pagina.acoes.append(("focus", self.seletor))

    def scroll_into_view_if_needed(self):
        pass

    def wait_for(self, state):
        pass

    def is_enabled(self):
        return True

    def is_visible(self):
        return True

    def is_checked(self):
        return False

    def select_option(self, **kwargs):
        self.pagina.acoes.append(("select", self.seletor, kwargs))

    def locator(self, sub):
        return _Opcoes(self.pagina, self.seletor)


class _Opcoes:
    def __init__(self, pagina, seletor):
        self.pagina = pagina
        self.seletor = seletor

    def all_text_contents(self):
        return self.pagina.opcoes.get(self.seletor, [])


class _Keyboard:
    def __init__(self, pagina):
        self.pagina = pagina

    def press(self, tecla):
        self.pagina.acoes.append(("press", tecla))

    def type(self, texto):
        self.pagina.acoes.append(("digitar_no_foco", texto))


class _PaginaTabela:
    """Tabela de características com `linhas` linhas.

    `quantos()` responde ao `count()`: devolve o número de linhas para o XPath
    da tabela, e 1 para qualquer campo DENTRO de uma linha que exista. Um
    índice fora da faixa (0, ou maior que o total) devolve 0 -- é assim que o
    duplo detecta o erro de base-1, em vez de deixá-lo passar.
    """

    def __init__(self, linhas):
        self.linhas = linhas
        self.acoes = []
        self.valores = {}
        self.textos = {}
        self.opcoes = {}
        self.paginas_extras = 0
        self.url = ""
        self.keyboard = _Keyboard(self)
        for indice in range(1, linhas + 1):
            self.textos[f"xpath=({ts.XPATH_LINHAS_TABELA})[{indice}]{ts.XPATH_REL_COL_DESCRICAO}"] = (
                f" {indice} - CARACTERISTICA {indice} "
            )

    def quantos(self, seletor):
        if seletor == f"xpath={ts.XPATH_BOTAO_PROXIMA_PAGINA}":
            # Uma página só. Sem isto o duplo diz que o botão "próxima" existe
            # e está habilitado, e o laço de paginação gira para sempre --
            # aconteceu de verdade ao escrever estes testes, e é exatamente o
            # motivo de os testes de laço abaixo terem timeout próprio.
            return self.paginas_extras
        if seletor == f"xpath={ts.XPATH_LINHAS_TABELA}":
            return self.linhas
        if ts.XPATH_LINHAS_TABELA in seletor:
            # `(...)[N]...` -- só existe se N estiver na faixa.
            entre = seletor.split(")[", 1)[1].split("]", 1)[0]
            return 1 if entre.isdigit() and 1 <= int(entre) <= self.linhas else 0
        return 1

    def locator(self, seletor):
        return _LocatorPW(self, seletor)

    def goto(self, url):
        self.url = url

    def on(self, evento, handler):
        pass


def _automacao(linhas):
    auto = TechSpecsAutomation.__new__(TechSpecsAutomation)
    auto.engine = PlaywrightEngine(_PaginaTabela(linhas))
    auto.portal = ts.PMIBPortal(auto.engine)
    return auto


def _linha(indice):
    return f"({ts.XPATH_LINHAS_TABELA})[{indice}]"


# ===========================================================================
# Endereçamento das linhas — o risco central da escolha do CP 5.3
# ===========================================================================
def test_o_seletor_da_primeira_linha_usa_indice_1_e_nao_0():
    # Contraprova viva do erro de base-1: com `[0]` o duplo devolve count 0,
    # nenhum campo é achado e nada seria preenchido -- em silêncio.
    auto = _automacao(linhas=3)

    assert auto.engine.contar(_linha(1) + ts.XPATH_REL_COL_DESCRICAO) == 1
    assert auto.engine.contar(_linha(0) + ts.XPATH_REL_COL_DESCRICAO) == 0


def test_texto_da_linha_e_lido_pelo_seletor_composto():
    auto = _automacao(linhas=2)

    assert auto.engine.texto(_linha(2) + ts.XPATH_REL_COL_DESCRICAO).strip() == "2 - CARACTERISTICA 2"


# ===========================================================================
# _preencher_linha — cada tipo no campo certo, dentro da linha certa
# ===========================================================================
def test_preencher_char_escreve_pt_e_es_na_linha_indicada():
    auto = _automacao(linhas=3)
    seletor_linha = _linha(2)

    ok = auto._preencher_linha(
        seletor_linha,
        {"TIPO": "CHAR", "RESPOSTA_PT_FINAL": "Aço inox", "RESPOSTA_ES_FINAL": "Acero inox"},
    )

    assert ok is True
    escritos = {
        seletor: valor
        for tipo, seletor, valor in [a for a in auto.engine.page.acoes if a[0] in ("fill", "type")]
    }
    assert escritos[f"xpath={seletor_linha}{ts.XPATH_REL_TEXTAREA_PT}"] == "Aço inox"
    assert escritos[f"xpath={seletor_linha}{ts.XPATH_REL_TEXTAREA_ES}"] == "Acero inox"
    # E NADA foi escrito em outra linha.
    assert all(_linha(1) not in seletor and _linha(3) not in seletor for seletor in escritos)


def test_preencher_num_usa_o_input_numerico_da_linha():
    auto = _automacao(linhas=1)

    ok = auto._preencher_linha(_linha(1), {"TIPO": "NUM", "RESPOSTA_PT_FINAL": "42"})

    assert ok is True
    assert auto.engine.get_value(_linha(1) + ts.XPATH_REL_INPUT_NUM) == "42"


def test_preencher_intervalo_separa_minimo_e_maximo_pela_barra():
    auto = _automacao(linhas=1)

    ok = auto._preencher_linha(
        _linha(1), {"TIPO": "INT", "RESPOSTA_PT_FINAL": "10 / 20", "SUBTIPO_INTERVALO": "MINIMO / MAXIMO"}
    )

    assert ok is True
    assert auto.engine.get_value(_linha(1) + ts.XPATH_REL_INPUT_MIN) == "10"
    assert auto.engine.get_value(_linha(1) + ts.XPATH_REL_INPUT_MAX) == "20"


def test_preencher_intervalo_sem_barra_deixa_o_maximo_vazio():
    auto = _automacao(linhas=1)

    auto._preencher_linha(_linha(1), {"TIPO": "INT", "RESPOSTA_PT_FINAL": "10"})

    assert auto.engine.get_value(_linha(1) + ts.XPATH_REL_INPUT_MIN) == "10"


def test_unidade_e_selecionada_pelo_simbolo_entre_parenteses():
    auto = _automacao(linhas=1)
    seletor_unidade = f"xpath={_linha(1)}{ts.XPATH_REL_SELECT_UNIDADE}"
    auto.engine.page.opcoes[seletor_unidade] = ["Metro (M)", "Milímetro (MM)", "Quilo (KG)"]

    auto._preencher_linha(_linha(1), {"TIPO": "CHAR", "RESPOSTA_PT_FINAL": "x", "SIMBOLO": "MM"})

    escolhas = [a for a in auto.engine.page.acoes if a[0] == "select"]
    assert escolhas[-1][2] == {"index": 1}  # "Milímetro (MM)"


# ===========================================================================
# Auditoria — o fallback que o CP 5.3 manda preservar
# ===========================================================================
def test_auditoria_aceita_de_primeira_quando_o_site_guarda_o_valor():
    auto = _automacao(linhas=1)
    seletor = _linha(1) + ts.XPATH_REL_INPUT_NUM

    assert auto._preencher_input_com_auditoria(seletor, "7", None) is True
    assert auto.engine.get_value(seletor) == "7"


def test_auditoria_forca_o_valor_quando_o_site_zera_o_campo():
    """O site rejeita a DIGITAÇÃO e aceita o valor FORÇADO.

    O duplo distingue as duas tentativas contando escritas no campo: a 1ª (a
    digitação de `safe_send_keys_elem`) é zerada, a 2ª (o `forcar_valor`)
    passa.

    Este teste enganou duas vezes antes de ficar de pé, e as duas armadilhas
    estão registradas aqui porque são fáceis de repetir:

      1. zerar só no `press_sequentially` -- nunca disparava, porque
         `safe_send_keys_elem` escreve via `fill`;
      2. contar TODA escrita -- o `engine.clear` do começo também é um `fill`
         (com texto vazio), então a contagem batia sem a 2ª tentativa existir.

    Nas duas versões o teste passava sem exercitar nada: remover o
    `forcar_valor` do código de produção não o derrubava. Daí o filtro por
    texto não-vazio e o `assert` explícito sobre a contagem.
    """
    auto = _automacao(linhas=1)
    seletor = _linha(1) + ts.XPATH_REL_INPUT_NUM
    chave = f"xpath={seletor}"
    escritas = {"n": 0}

    original_fill = _LocatorPW.fill

    def _fill_que_zera_na_primeira(self, texto):
        original_fill(self, texto)
        # Só ESCRITAS de verdade contam -- o `clear` do começo passa por aqui
        # com texto vazio e não é tentativa nenhuma.
        if self.seletor == chave and texto != "":
            escritas["n"] += 1
            if escritas["n"] == 1:
                self.pagina.valores[self.seletor] = "0"

    _LocatorPW.fill = _fill_que_zera_na_primeira
    try:
        resultado = auto._preencher_input_com_auditoria(seletor, "42", None)
    finally:
        _LocatorPW.fill = original_fill

    assert escritas["n"] == 2, "deveria ter havido uma 2ª tentativa (forcar_valor)"
    assert resultado is True, "a 2ª tentativa deveria ter salvado o campo"
    assert auto.engine.get_value(seletor) == "42"


def test_auditoria_devolve_false_quando_o_site_recusa_as_duas_vezes():
    # É este `False` que o chamador transforma na "pendência manual" que o
    # CP 5.3 manda preservar -- sem ele, o usuário não saberia que o campo
    # ficou vazio no portal.
    auto = _automacao(linhas=1)
    seletor = _linha(1) + ts.XPATH_REL_INPUT_NUM
    chave = f"xpath={seletor}"

    original_fill = _LocatorPW.fill

    def _sempre_zera(self, texto):
        original_fill(self, texto)
        if self.seletor == chave and texto != "":
            self.pagina.valores[self.seletor] = "0"

    _LocatorPW.fill = _sempre_zera
    try:
        avisos = []
        resultado = auto._preencher_input_com_auditoria(
            seletor, "42", None, "Tensão", avisos.append
        )
    finally:
        _LocatorPW.fill = original_fill

    assert resultado is False
    assert any("rejeitou" in msg for msg in avisos)


def test_auditoria_nao_mexe_no_campo_quando_o_valor_alvo_e_vazio():
    auto = _automacao(linhas=1)

    assert auto._preencher_input_com_auditoria(_linha(1) + ts.XPATH_REL_INPUT_NUM, "", None) is True
    assert auto.engine.page.acoes == []


# ===========================================================================
# Dropdown — a regra de casamento é do serviço, não do motor
# ===========================================================================
def test_dropdown_cai_no_casamento_normalizado_quando_o_texto_exato_falha():
    auto = _automacao(linhas=1)
    seletor = _linha(1) + ts.XPATH_REL_SELECT_LISTA
    chave = f"xpath={seletor}"
    auto.engine.page.opcoes[chave] = ["Corrente Alternada", "Corrente Contínua"]

    # `select_option(label=...)` do duplo aceita qualquer coisa, então
    # forçamos a 1ª tentativa a falhar para exercitar a 2ª.
    original = _LocatorPW.select_option

    def _so_aceita_indice(self, **kwargs):
        if "label" in kwargs:
            raise ValueError("sem opção com esse texto")
        original(self, **kwargs)

    _LocatorPW.select_option = _so_aceita_indice
    try:
        # Sem acento e em caixa diferente -- só casa depois de normalizar.
        auto.selecionar_dropdown_lista(seletor, "corrente continua")
    finally:
        _LocatorPW.select_option = original

    escolhas = [a for a in auto.engine.page.acoes if a[0] == "select"]
    assert escolhas[-1][2] == {"index": 1}


def test_dropdown_com_texto_vazio_nao_faz_nada():
    auto = _automacao(linhas=1)

    auto.selecionar_dropdown_lista(_linha(1) + ts.XPATH_REL_SELECT_LISTA, "")

    assert auto.engine.page.acoes == []


# ===========================================================================
# processar_lista — o laço de linhas de verdade
#
# Os testes acima chamam `_preencher_linha` direto e por isso NÃO tocam a
# linha que monta o seletor indexado. Uma contraprova mostrou o buraco: trocar
# `[{row_index + 1}]` por `[{row_index}]` não derrubava nada. Estes testes
# exercitam o laço inteiro.
# ===========================================================================
def _rodar_lista(auto, dados, pmib="4500063671.0001"):
    """Roda `processar_lista` numa thread com prazo.

    A falha que estes testes vigiam é um LAÇO QUE NÃO TERMINA -- e um laço
    infinito pendura a suíte inteira em vez de reportar. Já aconteceu duas
    vezes neste projeto (CP 4.2, e ao escrever este arquivo), então o prazo é
    parte do teste, não zelo.
    """
    import threading

    logs = []
    auto.portal.pesquisar_e_abrir = lambda *a, **k: True
    resultado = {}

    def _alvo():
        try:
            resultado["finalizados"] = auto.processar_lista(
                [{"METADATA": {"PMIB": pmib}, "DADOS_TRATADOS": dados}],
                callback_log=logs.append,
            )
        except BaseException as erro:  # noqa: BLE001
            resultado["erro"] = erro

    thread = threading.Thread(target=_alvo, daemon=True)
    thread.start()
    thread.join(timeout=15)

    assert not thread.is_alive(), "processar_lista não terminou -- laço de linhas/paginação preso"
    assert "erro" not in resultado, resultado.get("erro")
    return resultado["finalizados"], "\n".join(logs)


def _dado(chave, valor):
    return {"CARACTERISTICA_CHAVE": chave, "TIPO": "NUM", "RESPOSTA_PT_FINAL": valor, "ACAO": "PREENCHER"}


def test_o_laco_preenche_cada_linha_no_seu_proprio_seletor():
    # A prova contra o erro de base-1: a característica da linha 1 tem de cair
    # no campo da linha 1, e a da linha 3 no da linha 3. Com `[row_index]`, a
    # 1ª viraria `[0]` (não casa com nada) e todas as outras escreveriam na
    # linha ERRADA -- sem erro nenhum aparecendo.
    auto = _automacao(linhas=3)

    _rodar_lista(auto, [_dado("CARACTERISTICA 1", "11"), _dado("CARACTERISTICA 3", "33")])

    assert auto.engine.get_value(_linha(1) + ts.XPATH_REL_INPUT_NUM) == "11"
    assert auto.engine.get_value(_linha(3) + ts.XPATH_REL_INPUT_NUM) == "33"
    # A linha 2 não estava no JSON da IA -- fica intocada.
    assert auto.engine.get_value(_linha(2) + ts.XPATH_REL_INPUT_NUM) == ""


def test_o_laco_percorre_todas_as_linhas_e_para_no_fim():
    # Se a contagem ou o índice estiverem errados, ou o laço não chega no fim
    # (e trava), ou para cedo demais e deixa linha por preencher.
    auto = _automacao(linhas=4)

    _rodar_lista(auto, [_dado(f"CARACTERISTICA {i}", str(i)) for i in range(1, 5)])

    for indice in range(1, 5):
        assert auto.engine.get_value(_linha(indice) + ts.XPATH_REL_INPUT_NUM) == str(indice)


def test_tabela_vazia_encerra_sem_escrever_nada():
    auto = _automacao(linhas=0)

    finalizados, _ = _rodar_lista(auto, [_dado("QUALQUER", "1")])

    assert not any(acao[0] in ("fill", "type") for acao in auto.engine.page.acoes)
    assert finalizados == ["4500063671.0001"]  # a ficha percorreu o fluxo


def test_caracteristica_fora_do_json_da_ia_e_ignorada():
    auto = _automacao(linhas=2)

    _rodar_lista(auto, [_dado("CARACTERISTICA QUE NAO ESTA NA TELA", "99")])

    assert auto.engine.get_value(_linha(1) + ts.XPATH_REL_INPUT_NUM) == ""
    assert auto.engine.get_value(_linha(2) + ts.XPATH_REL_INPUT_NUM) == ""

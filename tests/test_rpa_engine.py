r"""
Testes do Checkpoint 2.1 — `sigft/core/rpa/engine.py` (`RPAEngine`).

`RPAEngine` é uma classe abstrata (`abc.ABC`), só stdlib -- estes testes
confirmam o CONTRATO (não pode ser instanciada diretamente; uma subclasse só
pode ser instanciada quando implementa TODOS os métodos exigidos) sem
depender de Selenium/Playwright nenhum -- por isso este arquivo importa só
`sigft.core.rpa.engine`, nunca `selenium`. As implementações concretas são
testadas em tests/test_selenium_engine.py e tests/test_playwright_engine.py.

O contrato tem duas gerações, e os testes separam as duas:
  - os 10 métodos do CP 2.1, que descrevem a INTENÇÃO do serviço;
  - as 8 primitivas do CP 5.1, acrescentadas para o `PMIBPortal` largar o
    `self.engine.driver`/`.wait` cru -- sem elas, trocar de motor é
    impossível, porque um `PlaywrightEngine` não tem driver nenhum.

Manter as duas listas explícitas (em vez de uma só, somada) é o que faz este
arquivo documentar de onde veio cada exigência.
"""
import pytest

from sigft.core.rpa.engine import RPAEngine

METODOS_CP_2_1 = (
    "goto",
    "click",
    "fill",
    "press",
    "wait_visible",
    "wait_clickable",
    "element_exists",
    "get_value",
    "screenshot",
    "set_download_dir",
)

METODOS_CP_5_1 = (
    "click_estrito",
    "fill_estrito",
    "scroll_to",
    "click_raw",
    "wait_present",
    "clear",
    "type_text",
    "current_url",
    "fechar",
)

METODOS_CP_5_3 = (
    "contar",
    "esta_visivel",
    "esta_habilitado",
    "esta_marcado",
    "forcar_valor",
    # `passar_o_mouse` entra em 2026-08-24, e não é conveniência de navegação:
    # é a única forma de LER o espanhol das Condições. O portal guarda o texto
    # num balão de tooltip (`osui-tooltip--is-hover`) que não existe no DOM até
    # alguém apontar para o gatilho -- ver `PMIBPortal.texto_do_balao`.
    "passar_o_mouse",
    "focar",
    "digitar_no_foco",
    "atributo",
    "texto",
    "opcoes",
    "selecionar_por_texto",
    "selecionar_por_indice",
)

# Acrescentado DEPOIS do 1º teste da Fase 5 no portal real, não por um
# checkpoint: `cria_fichas` precisa de um clique que leve o FOCO junto, e as
# três primitivas de clique do CP 5.1 clicam por JavaScript no motor
# Selenium (o que dispara o evento sem mover o foco). Ver a docstring de
# `click_nativo` em engine.py.
METODOS_DO_TESTE_REAL = ("click_nativo",)

# Acrescentado em 2026-08-18 pelo mesmo motivo do anterior -- uma sessão real,
# não um checkpoint. `upload_conditions` deixou de preencher os controles de
# Condições ao migrar para Playwright: lá `Locator.click()` roda a checagem de
# hit target, e o `<input class="radio-button">` do OutSystems fica coberto
# pelo `<label>` estilizado. No Selenium o clique SEMPRE foi por JavaScript e
# passava por cima disso. `click_dom` devolve essa capacidade ao contrato, em
# vez de deixá-la implícita num motor só. Ver a docstring em engine.py.
METODOS_DA_REGRESSAO_DO_PLAYWRIGHT = ("click_dom",)

# Modo de auditoria (2026-08-18): o robo fotografa a tela para o log de
# execucao, e e assim que uma secao nova do portal e mapeada sem acesso a
# ele. Ver a docstring de `html_do_elemento` em engine.py.
METODOS_DA_AUDITORIA = ("html_do_elemento",)

# CP 6.4 -- COPIAR IMAGEM entre fichas (2026-08-20).
#
# Documento se ASSOCIA (o objeto já existe no portal); imagem não: o arquivo
# tem de sair da ficha original e entrar na nova. E o `src` da imagem no PMIB é
# um `blob:`:
#
#   <img class="custom-img" src="blob:https://apps.itaipu.gov.br/29077935-…">
#
# `blob:` NÃO é endereço HTTP -- é um identificador de objeto válido só dentro
# daquela página, naquela sessão. Não há servidor do outro lado para o
# `requests` conversar; a imagem só pode ser lida de dentro do navegador.
#
# Por que duas primitivas de CONCEITO e não um `executar_js` genérico: a
# mecânica difere de verdade entre os motores (o Playwright espera uma promessa
# sozinho; o Selenium precisa de `execute_async_script` com callback). Expor
# "rode este JS" obrigaria o serviço a escrever os dois scripts e a saber qual
# motor está rodando -- que é exatamente o que o `RPAEngine` existe para
# evitar.
METODOS_DA_COPIA_DE_IMAGEM = ("bytes_da_imagem", "enviar_arquivo")

METODOS_OBRIGATORIOS = (
    METODOS_CP_2_1 + METODOS_CP_5_1 + METODOS_CP_5_3 + METODOS_DO_TESTE_REAL
    + METODOS_DA_REGRESSAO_DO_PLAYWRIGHT + METODOS_DA_AUDITORIA
    + METODOS_DA_COPIA_DE_IMAGEM
)


def test_rpaengine_declara_os_10_metodos_do_cp_2_1():
    for nome in METODOS_CP_2_1:
        assert nome in RPAEngine.__abstractmethods__


def test_rpaengine_declara_as_primitivas_do_cp_5_1():
    for nome in METODOS_CP_5_1:
        assert nome in RPAEngine.__abstractmethods__


def test_rpaengine_declara_as_primitivas_do_cp_5_3():
    for nome in METODOS_CP_5_3:
        assert nome in RPAEngine.__abstractmethods__


def test_rpaengine_declara_o_clique_nativo():
    for nome in METODOS_DO_TESTE_REAL:
        assert nome in RPAEngine.__abstractmethods__


def test_rpaengine_declara_as_primitivas_da_copia_de_imagem():
    for nome in METODOS_DA_COPIA_DE_IMAGEM:
        assert nome in RPAEngine.__abstractmethods__


def test_o_contrato_nao_tem_metodo_a_mais_sem_teste():
    # Trava contra crescimento silencioso: um método abstrato novo obriga a
    # atualizar as listas acima -- e, portanto, a pensar em qual checkpoint o
    # exigiu e o que o motor Playwright vai fazer com ele.
    assert set(RPAEngine.__abstractmethods__) == set(METODOS_OBRIGATORIOS)


def test_nao_pode_instanciar_rpaengine_diretamente():
    with pytest.raises(TypeError):
        RPAEngine()


def _implementacoes_completas():
    return {
        "goto": lambda self, url: None,
        "click": lambda self, seletor: None,
        "bytes_da_imagem": lambda self, seletor: b"",
        "enviar_arquivo": lambda self, seletor, caminho: None,
        "fill": lambda self, seletor, texto: None,
        "press": lambda self, teclas: None,
        "wait_visible": lambda self, seletor: None,
        "wait_clickable": lambda self, seletor: None,
        "element_exists": lambda self, seletor: True,
        "get_value": lambda self, seletor: "",
        "screenshot": lambda self, caminho: None,
        "set_download_dir": lambda self, caminho: None,
        # CP 5.1
        "click_estrito": lambda self, seletor: None,
        "fill_estrito": lambda self, seletor, texto: None,
        "scroll_to": lambda self, seletor: None,
        "click_raw": lambda self, seletor: None,
        "click_nativo": lambda self, seletor: None,
        "click_dom": lambda self, seletor: None,
        "html_do_elemento": lambda self, seletor: "",
        "wait_present": lambda self, seletor: None,
        "clear": lambda self, seletor: None,
        "type_text": lambda self, seletor, texto: None,
        "current_url": lambda self: "",
        "fechar": lambda self: None,
        # CP 5.3
        "contar": lambda self, seletor: 0,
        "esta_visivel": lambda self, seletor: True,
        "esta_habilitado": lambda self, seletor: True,
        "esta_marcado": lambda self, seletor: False,
        "forcar_valor": lambda self, seletor, texto: None,
        "passar_o_mouse": lambda self, seletor: None,
        "focar": lambda self, seletor: None,
        "digitar_no_foco": lambda self, texto: None,
        "atributo": lambda self, seletor, nome: "",
        "texto": lambda self, seletor: "",
        "opcoes": lambda self, seletor: [],
        "selecionar_por_texto": lambda self, seletor, texto: None,
        "selecionar_por_indice": lambda self, seletor, indice: None,
    }


def test_subclasse_que_implementa_todos_os_metodos_pode_ser_instanciada():
    engine_cls = type("_EngineCompleto", (RPAEngine,), _implementacoes_completas())

    engine = engine_cls()

    assert isinstance(engine, RPAEngine)


@pytest.mark.parametrize("metodo_faltando", METODOS_OBRIGATORIOS)
def test_subclasse_que_falta_um_metodo_nao_pode_ser_instanciada(metodo_faltando):
    metodos = _implementacoes_completas()
    del metodos[metodo_faltando]
    engine_cls = type("_EngineIncompleto", (RPAEngine,), metodos)

    with pytest.raises(TypeError):
        engine_cls()

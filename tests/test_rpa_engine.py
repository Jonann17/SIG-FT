r"""
Testes do Checkpoint 2.1 — `sigft/core/rpa/engine.py` (`RPAEngine`).

`RPAEngine` é uma classe abstrata (`abc.ABC`), só stdlib -- estes testes
confirmam o CONTRATO (não pode ser instanciada diretamente; uma subclasse só
pode ser instanciada quando implementa TODOS os 10 métodos exigidos pelo
CP 2.1: `goto`, `click`, `fill`, `press`, `wait_visible`, `wait_clickable`,
`element_exists`, `get_value`, `screenshot`, `set_download_dir`) sem
depender de Selenium/Playwright nenhum -- por isso este arquivo importa só
`sigft.core.rpa.engine`, nunca `selenium`. A implementação concreta de
produção (`SeleniumEngine`) é testada em tests/test_selenium_engine.py.
"""
import pytest

from sigft.core.rpa.engine import RPAEngine

METODOS_OBRIGATORIOS = (
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


def test_rpaengine_declara_os_10_metodos_do_checkpoint():
    for nome in METODOS_OBRIGATORIOS:
        assert nome in RPAEngine.__abstractmethods__


def test_nao_pode_instanciar_rpaengine_diretamente():
    with pytest.raises(TypeError):
        RPAEngine()


def _implementacoes_completas():
    return {
        "goto": lambda self, url: None,
        "click": lambda self, seletor: None,
        "fill": lambda self, seletor, texto: None,
        "press": lambda self, teclas: None,
        "wait_visible": lambda self, seletor: None,
        "wait_clickable": lambda self, seletor: None,
        "element_exists": lambda self, seletor: True,
        "get_value": lambda self, seletor: "",
        "screenshot": lambda self, caminho: None,
        "set_download_dir": lambda self, caminho: None,
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

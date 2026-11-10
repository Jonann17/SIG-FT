"""Fechar o navegador interrompe a fila; não é uma falha recuperável de campo."""
import pytest

from sigft.core.rpa.engine import ErroRPA
from sigft.core.rpa.playwright_engine import PlaywrightEngine
from sigft.core.rpa.portal import PMIBPortal
from sigft.services import duplicadas_condicoes as cond
from sigft.services import duplicadas_imagens as imagens
from sigft.services import duplicadas_robo as robo


class TargetClosedError(Exception):
    """Mesmo tipo emitido pelo SDK; nenhuma dependência de browser no CI."""


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(robo.time, "sleep", lambda _s: None)


class PaginaFechada:
    first = None
    url = "about:blank"

    def __init__(self):
        self.first = self

    def locator(self, _seletor):
        return self

    def count(self):
        raise TargetClosedError("Target page, context or browser has been closed")

    def wait_for(self, **_kwargs):
        self.count()

    def fill(self, *_args, **_kwargs):
        self.count()

    def goto(self, _url):
        self.count()


@pytest.mark.parametrize("acao", [
    lambda p: p.engine.contar("//input"),
    lambda p: p.safe_click("//input"),
    lambda p: p.safe_fill("//input", "40"),
    lambda p: p.valor_se_existir("//input"),
    lambda p: p.check_or_uncheck("//input", True),
    lambda p: p.mensagens_na_tela(),
    lambda p: cond.divergencias_da_subaba(p, "Armazenamento", {"Checkbox4": True}),
    lambda p: cond.autoconferir(p, "Armazenamento", {"Checkbox4": True}),
    lambda p: imagens.fechar_formulario(p),
])
def test_fechamento_nao_vira_sucesso_ou_retentativa(acao):
    portal = PMIBPortal(PlaywrightEngine(PaginaFechada()))
    with pytest.raises(ErroRPA, match="closed"):
        acao(portal)


def test_lote_para_na_primeira_ficha_com_navegador_fechado():
    from types import SimpleNamespace
    portal = PMIBPortal(PlaywrightEngine(PaginaFechada()))
    fichas = [SimpleNamespace(pmib=f"4500063671.{n}", ficha_original="4500063671.0715",
                              descricao="Ângulo de união") for n in range(1667, 1672)]
    linhas = []
    resultados = robo.processar_lote(fichas, portal=portal, callback_log=linhas.append)

    assert len(resultados) == 1, [r.resumo for r in resultados]
    assert not resultados[0].ok
    assert not any(">> 4500063671.1668" in linha for linha in linhas)
    assert any("4" in linha and "não iniciada" in linha for linha in linhas)

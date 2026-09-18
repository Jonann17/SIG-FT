# -*- coding: utf-8 -*-
"""`core/web/robots.py`: a semantica de falha, travada antes de mexer.

Este modulo e da frente do Rafael (TRABALHO_PARALELO.md). Ele nao tinha teste
proprio, e passou a ter porque a migracao para a cascata de rotas
(`core/rede.py`) troca a forma de buscar o `robots.txt` -- e a forma antiga
usava `urllib.error.HTTPError` para distinguir 404 de erro de rede.

Trocar isso sem travar o comportamento seria mexer no arquivo de outra pessoa
no escuro. Os testes abaixo descrevem o que o modulo FAZIA; a migracao os
mantem verdes, e e essa a prova de que nada mudou para quem chama.

A regra que nao pode virar: **nao conseguir ler o robots.txt LIBERA**. Um site
que nao responde nao pode barrar o AutoSpec.
"""
import pytest

from sigft.core import rede
from sigft.core.web import robots


@pytest.fixture(autouse=True)
def _limpar():
    robots.limpar_cache()
    yield
    robots.limpar_cache()


class _Resposta:
    def __init__(self, texto="", status=200):
        self.status_code = status
        self.text = texto

    def close(self):
        pass


def _responde(texto="", status=200):
    return lambda url, **kw: _Resposta(texto, status)


def _estoura(erro):
    def falhar(url, **kw):
        raise erro
    return falhar


# =============================================================================
# A. O robots.txt que diz nao
# =============================================================================

def test_disallow_explicito_barra(monkeypatch):
    monkeypatch.setattr(rede, "get", _responde("User-agent: *\nDisallow: /privado"))

    assert robots.pode_acessar("https://site.com/privado/x.pdf") is False


def test_o_que_nao_esta_no_disallow_passa(monkeypatch):
    monkeypatch.setattr(rede, "get", _responde("User-agent: *\nDisallow: /privado"))

    assert robots.pode_acessar("https://site.com/publico/x.pdf") is True


def test_allow_geral_passa(monkeypatch):
    monkeypatch.setattr(rede, "get", _responde("User-agent: *\nDisallow:"))

    assert robots.pode_acessar("https://site.com/qualquer.pdf") is True


# =============================================================================
# B. Falhar ABERTO -- a regra que nao pode virar
# =============================================================================

def test_404_no_robots_LIBERA(monkeypatch):
    """O site nao publica regra nenhuma. O padrao da web e permitir."""
    monkeypatch.setattr(rede, "get", _responde("nao achei", status=404))

    assert robots.pode_acessar("https://site.com/x.pdf") is True


def test_410_no_robots_LIBERA(monkeypatch):
    monkeypatch.setattr(rede, "get", _responde("", status=410))

    assert robots.pode_acessar("https://site.com/x.pdf") is True


def test_erro_de_rede_LIBERA(monkeypatch):
    """Site fora do ar, DNS caido, VPN bloqueando: nao e um 'nao'."""
    monkeypatch.setattr(rede, "get", _estoura(rede.FalhaDeRede("sem rota")))

    assert robots.pode_acessar("https://site.com/x.pdf") is True


def test_500_no_robots_LIBERA(monkeypatch):
    monkeypatch.setattr(rede, "get", _responde("erro", status=500))

    assert robots.pode_acessar("https://site.com/x.pdf") is True


def test_excecao_inesperada_LIBERA(monkeypatch):
    monkeypatch.setattr(rede, "get", _estoura(ValueError("qualquer coisa")))

    assert robots.pode_acessar("https://site.com/x.pdf") is True


# =============================================================================
# C. URL invalida NAO e duvida sobre permissao
# =============================================================================

@pytest.mark.parametrize("url", ["", "nao-e-url", "ftp://", None])
def test_url_malformada_e_False(url, monkeypatch):
    """Aqui nao ha dominio a consultar: e entrada invalida, nao duvida."""
    monkeypatch.setattr(rede, "get", _responde(""))

    assert robots.pode_acessar(url) is False


# =============================================================================
# D. O cache
# =============================================================================

def test_o_robots_de_um_dominio_e_lido_UMA_vez(monkeypatch):
    """Um lote de 50 fichas nao pode reler o mesmo arquivo 50 vezes."""
    chamadas = []

    def contar(url, **kw):
        chamadas.append(url)
        return _Resposta("User-agent: *\nDisallow:")

    monkeypatch.setattr(rede, "get", contar)

    robots.pode_acessar("https://site.com/a.pdf")
    robots.pode_acessar("https://site.com/b.pdf")
    robots.pode_acessar("https://site.com/c.pdf")

    assert len(chamadas) == 1


def test_dominios_diferentes_sao_lidos_separado(monkeypatch):
    chamadas = []

    def contar(url, **kw):
        chamadas.append(url)
        return _Resposta("User-agent: *\nDisallow:")

    monkeypatch.setattr(rede, "get", contar)

    robots.pode_acessar("https://a.com/x.pdf")
    robots.pode_acessar("https://b.com/x.pdf")

    assert len(chamadas) == 2


# =============================================================================
# E. A migracao em si
# =============================================================================

def test_o_robots_sai_pela_cascata_de_rotas(monkeypatch):
    """O motivo da migracao.

    Antes era `urllib.request.urlopen`, que nao enxerga o PAC: na rede da
    empresa a leitura sempre estourava o timeout de 8s e caia no "libera" --
    ou seja, a checagem de robots estava efetivamente DESLIGADA no trabalho,
    e custava 8 segundos por dominio para nao fazer nada.
    """
    visto = {}

    def falso_get(url, **kw):
        visto["url"] = url
        visto["timeout"] = kw.get("timeout")
        return _Resposta("User-agent: *\nDisallow:")

    monkeypatch.setattr(rede, "get", falso_get)

    robots.pode_acessar("https://site.com/x.pdf")

    assert visto["url"] == "https://site.com/robots.txt"
    assert visto["timeout"] == robots.TIMEOUT_S

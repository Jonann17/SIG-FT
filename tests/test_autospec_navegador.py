r"""Navegador como ÚLTIMO recurso, e o robots.txt como porteiro (2026-08-13).
Ver `sigft/core/web/navegador.py`, `robots.py` e `AutoSpecCore._tentar_navegador`.

**A ordem É a política.** Estes testes existem menos para provar que o
navegador funciona e mais para provar que ele **não é usado antes da hora**:
só depois de o download simples falhar, e só se o site permitir. Um recurso
que contorna bloqueio e um que lê página com JavaScript são o mesmo código —
a diferença está inteiramente em quando ele roda.

O caso que motivou: `hydac.com/shop` devolveu 403 no 1º teste real, e a
mesma loja é uma aplicação JavaScript cujo HTML estático quase não tem
texto. O segundo problema é o pior, porque o documento "chega" vazio e não
parece falha.
"""
import pytest

from sigft.core.web import navegador, robots
from sigft.services.autospec import AutoSpecCore


def _cb():
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append((nivel, str(msg)))

    return _CB(), registro


class _RobotsPermite:
    @staticmethod
    def pode_acessar(url, user_agent="*"):
        return True


class _RobotsProibe:
    @staticmethod
    def pode_acessar(url, user_agent="*"):
        return False


def _navegador_falso(texto):
    class _N:
        @staticmethod
        def disponivel():
            return True

        @staticmethod
        def texto_da_pagina(url, timeout_ms=None):
            return texto

    return _N


def _core():
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.usar_navegador_ultimo_recurso = True
    return core


# =============================================================================
# A. O robots.txt manda
# =============================================================================
def test_robots_proibindo_o_navegador_NAO_e_usado():
    """O núcleo da política: um site que diz 'não' continua recebendo
    'está bem'. Isto não é um contornador de bloqueio."""
    cb, registro = _cb()
    caminho = _core()._tentar_navegador(
        "https://x.com/p", callbacks=cb,
        _robots=_RobotsProibe, _navegador=_navegador_falso("conteudo " * 50),
    )
    assert caminho is None
    assert any("robots" in m.lower() for _, m in registro)


def test_robots_permitindo_o_navegador_e_usado(tmp_path):
    cb, _ = _cb()
    caminho = _core()._tentar_navegador(
        "https://x.com/p", callbacks=cb,
        _robots=_RobotsPermite, _navegador=_navegador_falso("especificacao tecnica " * 20),
    )
    assert caminho and caminho.endswith(".txt")
    with open(caminho, encoding="utf-8") as arquivo:
        assert "especificacao tecnica" in arquivo.read()


def test_robots_ilegivel_e_tratado_como_PROIBIDO(monkeypatch):
    """Falha FECHADA, ao contrário do resto do módulo: a dúvida aqui é sobre
    permissão, e agir sem permissão é o que se quer evitar."""
    robots.limpar_cache()
    monkeypatch.setattr(
        robots.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("rede fora")),
    )
    assert robots.pode_acessar("https://x.com/p") is False


def test_robots_404_libera(monkeypatch):
    """Site sem robots.txt não publicou regra — o padrão da web é permitir."""
    import urllib.error

    robots.limpar_cache()
    monkeypatch.setattr(
        robots.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(
            urllib.error.HTTPError("u", 404, "nao tem", {}, None)
        ),
    )
    assert robots.pode_acessar("https://x.com/p") is True


def test_robots_respeita_o_disallow(monkeypatch):
    robots.limpar_cache()

    class _Resposta:
        def read(self):
            return b"User-agent: *\nDisallow: /shop/\n"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(robots.urllib.request, "urlopen", lambda *a, **k: _Resposta())
    assert robots.pode_acessar("https://x.com/shop/item") is False
    assert robots.pode_acessar("https://x.com/catalogo/item") is True


def test_url_sem_esquema_nao_passa():
    assert robots.pode_acessar("nao-e-url") is False


# =============================================================================
# B. Playwright ausente não pode custar a ficha
# =============================================================================
def test_sem_playwright_segue_sem_navegador():
    class _SemPlaywright:
        @staticmethod
        def disponivel():
            return False

        @staticmethod
        def texto_da_pagina(url, timeout_ms=None):
            raise AssertionError("nao devia ter tentado abrir")

    cb, registro = _cb()
    assert _core()._tentar_navegador(
        "https://x.com/p", callbacks=cb, _robots=_RobotsPermite, _navegador=_SemPlaywright
    ) is None
    assert any("playwright" in m.lower() for _, m in registro)


def test_navegador_que_nao_traz_nada_nao_quebra():
    cb, registro = _cb()
    assert _core()._tentar_navegador(
        "https://x.com/p", callbacks=cb,
        _robots=_RobotsPermite, _navegador=_navegador_falso(None),
    ) is None


def test_da_para_desligar_o_recurso():
    core = _core()
    core.usar_navegador_ultimo_recurso = False
    assert core._tentar_navegador(
        "https://x.com/p", _robots=_RobotsPermite, _navegador=_navegador_falso("x" * 200)
    ) is None


# =============================================================================
# C. Só DEPOIS do download simples — a ordem
# =============================================================================
def test_download_que_da_certo_NAO_aciona_o_navegador(monkeypatch):
    """Se o navegador rodasse sempre, seria lento e seria abusivo. Ele só
    existe para o caso em que o caminho normal falhou."""
    chamou = []

    class _RespostaOk:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}

        def iter_content(self, chunk_size=None):
            yield b"%PDF-1.4 conteudo"

        def close(self):
            pass

    from sigft.services import autospec

    buscador = autospec.WebSearcher("k", "c")
    monkeypatch.setattr(autospec, "tentar_navegador", lambda *a, **k: chamou.append(1))
    buscador._download_file("https://x/ok.pdf", _get=lambda *a, **k: _RespostaOk())
    assert chamou == []


def test_403_aciona_o_navegador(monkeypatch):
    chamou = []

    class _Bloqueado:
        status_code = 403
        headers = {}

        def close(self):
            pass

    from sigft.services import autospec

    buscador = autospec.WebSearcher("k", "c")
    monkeypatch.setattr(
        autospec, "tentar_navegador",
        lambda url, callbacks=None, ligado=True, **k: chamou.append(url),
    )
    cb, _ = _cb()
    buscador._download_file("https://x/bloqueado", callbacks=cb, _get=lambda *a, **k: _Bloqueado())
    assert chamou == ["https://x/bloqueado"]


@pytest.mark.parametrize("status", [404, 500, 503])
def test_outros_erros_NAO_acionam_o_navegador(status, monkeypatch):
    """404 é "não existe", não "não quero". Insistir com navegador seria
    gastar segundos para confirmar o óbvio."""
    chamou = []

    class _Erro:
        status_code = status
        headers = {}

        def close(self):
            pass

    from sigft.services import autospec

    buscador = autospec.WebSearcher("k", "c")
    monkeypatch.setattr(autospec, "tentar_navegador", lambda *a, **k: chamou.append(1))
    buscador._download_file("https://x/e", _get=lambda *a, **k: _Erro())
    assert chamou == []


# =============================================================================
# D. O módulo do navegador em si
# =============================================================================
def test_pagina_curta_demais_e_tratada_como_vazia():
    """Casca de erro ou 'carregando...' não é conteúdo."""
    class _P:
        def goto(self, *a, **k):
            pass

        def wait_for_load_state(self, *a, **k):
            pass

        def inner_text(self, _):
            return "carregando"

    assert navegador.texto_da_pagina(
        "https://x", _sync_playwright=_playwright_falso(_P())
    ) is None


def test_pagina_com_conteudo_volta_inteira():
    conteudo = "Especificacoes tecnicas: pressao 350 bar, peso 41 kg. " * 5

    class _P:
        def goto(self, *a, **k):
            pass

        def wait_for_load_state(self, *a, **k):
            pass

        def inner_text(self, _):
            return conteudo

    assert navegador.texto_da_pagina(
        "https://x", _sync_playwright=_playwright_falso(_P())
    ) == conteudo.strip()


def test_erro_no_navegador_devolve_None_em_vez_de_estourar():
    def _explode():
        raise RuntimeError("navegador nao instalado")

    assert navegador.texto_da_pagina("https://x", _sync_playwright=_explode) is None


def _playwright_falso(pagina):
    class _Contexto:
        def new_page(self):
            return pagina

        def close(self):
            pass

    class _Navegador:
        def new_context(self, **k):
            return _Contexto()

        def close(self):
            pass

    class _Chromium:
        def launch(self, **k):
            return _Navegador()

    class _PW:
        chromium = _Chromium()

        def stop(self):
            pass

    class _Fabrica:
        def start(self):
            return _PW()

    return lambda: _Fabrica()

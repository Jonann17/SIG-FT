# -*- coding: utf-8 -*-
"""Todo HTTPS do SIG-FT sai pela cascata de rotas.

Ter o `core/rede.py` nao adianta nada se um ponto de chamada continuar
mandando `requests.get` direto: e justamente esse ponto que vai falhar com a
VPN ligada, e o sintoma sera "o resto funciona, so essa parte nao" -- o mais
caro de diagnosticar.

Por isso o guard estrutural aqui embaixo: ele reprova um ponto de HTTPS NOVO,
criado meses depois, por alguem que nao leu este arquivo.
"""
import ast
import pathlib

import pytest

from sigft.core import rede

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "sigft"


class _RespostaFalsa:
    def __init__(self, payload=None, status=200):
        self.status_code = status
        self._payload = payload or {}
        self.text = "ok"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload

    def close(self):
        pass


# =============================================================================
# A. Cada ponto de HTTPS, um a um
# =============================================================================

def test_o_catalogo_de_modelos_sai_pela_cascata(monkeypatch):
    from sigft.core.llm import catalogo

    visto = {}

    def falso_get(url, **kw):
        visto["url"] = url
        return _RespostaFalsa({"data": []})

    monkeypatch.setattr(rede, "get", falso_get)

    catalogo._http_get_real("https://exemplo/modelos")

    assert visto["url"] == "https://exemplo/modelos"


def test_o_openrouter_sai_pela_cascata(monkeypatch):
    from sigft.core.llm.providers import openrouter

    visto = {}

    def falso_get(url, **kw):
        visto["url"] = url
        visto["headers"] = kw.get("headers")
        return _RespostaFalsa({"data": [{"id": "m"}]})

    monkeypatch.setattr(rede, "get", falso_get)

    modelos = openrouter._buscar_modelos_da_rede("chave", "https://or.ai/api", None)

    assert modelos == [{"id": "m"}]
    assert visto["url"].endswith("/models")
    assert visto["headers"]["Authorization"] == "Bearer chave"


def test_o_provedor_compativel_com_openai_sai_pela_cascata(monkeypatch):
    from sigft.core.llm.providers import openai_compat

    visto = {}

    def falso_post(url, **kw):
        visto["url"] = url
        visto["json"] = kw.get("json")
        return _RespostaFalsa({
            "choices": [{"message": {"content": "resposta"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        })

    monkeypatch.setattr(rede, "post", falso_post)

    provedor = openai_compat.OpenAICompatProvider(
        "k", "modelo-x", base_url="https://empresa/v1")
    resultado = provedor.generate_raw("oi")

    assert resultado.text == "resposta"
    assert visto["url"] == "https://empresa/v1/chat/completions"
    assert visto["json"]["model"] == "modelo-x"


def test_a_injecao_de_http_continua_ganhando_da_cascata(monkeypatch):
    """Quem passa `http_get=` explicito nao e desviado para a rede.

    E a costura que os testes de todo o pacote ja usam; se a cascata a
    atropelasse, dezenas de testes passariam a fazer rede de verdade.
    """
    from sigft.core.llm.providers import openrouter

    def nao_deveria_ser_chamado(*a, **k):
        pytest.fail("a cascata foi usada mesmo com http_get explicito")

    monkeypatch.setattr(rede, "get", nao_deveria_ser_chamado)

    modelos = openrouter._buscar_modelos_da_rede(
        "chave", "https://or.ai/api",
        lambda url, **kw: _RespostaFalsa({"data": [{"id": "injetado"}]}))

    assert modelos == [{"id": "injetado"}]


def test_a_falha_de_rede_chega_ao_chamador(monkeypatch):
    """`FalhaDeRede` nao pode ser engolida: e ela que traz o diagnostico."""
    from sigft.core.llm import catalogo

    def sempre_falha(url, **kw):
        raise rede.FalhaDeRede("nenhuma rota funcionou")

    monkeypatch.setattr(rede, "get", sempre_falha)

    with pytest.raises(rede.FalhaDeRede):
        catalogo._http_get_real("https://exemplo/modelos")


# =============================================================================
# B. O guard: ninguem chama `requests` direto
# =============================================================================

# `rede.py` E a implementacao da cascata -- e o unico que pode.
_PODEM_CHAMAR_REQUESTS_DIRETO = {
    "sigft/core/rede.py",
}

# Arquivos da frente do Rafael (ver docs/refatoracao/TRABALHO_PARALELO.md).
# Eles saem desta lista conforme forem migrados, e cada saida e um commit
# isolado com aviso no mural -- nunca correcao de carona.
# Vazia: os dois arquivos da frente do Rafael que faziam HTTP
# (`services/autospec.py` e `core/web/robots.py`) foram migrados em
# 2026-09-18, em commit isolado e com aviso no mural do CLAUDE.md.
_PENDENTES_DA_OUTRA_FRENTE: set[str] = set()


_VERBOS = ("get", "post", "put", "delete", "request")


def _chamadas_http_diretas(caminho: pathlib.Path) -> list[str]:
    """Todo uso direto de `requests` ou `urlopen`, chamado OU guardado.

    A segunda metade importa e quase escapou: o `openrouter` nao escrevia
    `requests.get(...)`, escrevia

        get = requests.get
        ...
        resp = get(url, ...)

    Um guard que so olhasse `ast.Call` daria verde nesse arquivo -- e ele e
    justamente um dos que falham com a VPN ligada. Por isso aqui qualquer
    REFERENCIA a `requests.<verbo>` conta, chamada na hora ou guardada para
    depois.
    """
    achados = []
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    for no in ast.walk(arvore):
        # `requests.get`, esteja sendo chamado ou apenas referenciado.
        if (isinstance(no, ast.Attribute)
                and isinstance(no.value, ast.Name) and no.value.id == "requests"
                and no.attr in _VERBOS):
            achados.append(f"L{no.lineno}: {ast.unparse(no)[:70]}")

        # `urllib.request.urlopen(...)`
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                and no.func.attr == "urlopen"):
            achados.append(f"L{no.lineno}: {ast.unparse(no)[:70]}")

    return sorted(set(achados))


@pytest.mark.parametrize(
    "arquivo",
    sorted(PACOTE.rglob("*.py")),
    ids=lambda p: str(p.relative_to(RAIZ)),
)
def test_nenhum_modulo_chama_requests_direto(arquivo):
    """A trava que faz valer o `core/rede.py`.

    Um ponto de HTTPS que escape da cascata funciona em casa e falha na
    empresa -- e falha em SILENCIO, com timeout, sem erro que aponte a causa.
    E o defeito mais caro desta frente inteira, e ele nasce de uma linha
    escrita por quem nao sabia que a cascata existe.
    """
    relativo = str(arquivo.relative_to(RAIZ))
    if relativo in _PODEM_CHAMAR_REQUESTS_DIRETO:
        pytest.skip("e a propria implementacao da cascata")
    if relativo in _PENDENTES_DA_OUTRA_FRENTE:
        pytest.skip("frente do Rafael -- ver TRABALHO_PARALELO.md")

    diretas = _chamadas_http_diretas(arquivo)

    assert not diretas, (
        f"{relativo} chama HTTP direto, fora da cascata de rotas:\n  "
        + "\n  ".join(diretas)
        + "\n\nUse `sigft.core.rede.get(...)` / `rede.post(...)`. Ver o "
          "docstring de sigft/core/rede.py."
    )


def test_a_lista_de_excecoes_nao_tem_arquivo_inexistente():
    """Excecao que sobrevive ao arquivo vira permissao esquecida."""
    for relativo in _PODEM_CHAMAR_REQUESTS_DIRETO | _PENDENTES_DA_OUTRA_FRENTE:
        assert (RAIZ / relativo).is_file(), (
            f"{relativo} esta na lista de excecoes mas nao existe mais -- "
            f"remova a linha."
        )

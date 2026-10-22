"""O idioma da interface: espanhol, português ou inglês (2026-10-22).

Só a INTERFACE muda de idioma: botões, títulos, rótulos, dicas, janelas, caixas
de aviso e de pergunta, Ctrl+K, resumo do lote, aviso do Windows. NÃO mudam o
console (o que serviços e robôs escrevem), o portal PMIB, as planilhas e fichas
geradas, nem o CHANGELOG.

A chave de cada tradução é o próprio texto em português que está no código:
`t("Selecionar Excel")`. O português não tem catálogo (é a chave); `es` e `en`
moram em `sigft/app/idiomas/<codigo>.json` (`{"texto pt": "tradução"}`). Texto
com valores usa `{nome}`: `t("Ficha {atual} de {total}", atual=3, total=8)`.
Sem tradução, ou com uma que não casa com os valores, vale o português: nunca
vazio.

Constante de módulo que é texto de interface vai em `marcar("...")`: o texto
não muda (o import acontece antes de o idioma ser escolhido), mas a ferramenta
`tools/textos_da_interface.py` a reconhece como chave; quem a põe na tela
chama `t(CONSTANTE)`.

A troca vale ao REINICIAR: cada tela lê os textos uma vez, ao ser montada. O
idioma da sessão é `definir`; o guardado nas preferências (chave `idioma`) é
`escolhido`/`guardar`. Sem Qt: serviço e regra nunca conhecem a interface.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)

IDIOMAS = ("es", "pt", "en")
PADRAO = "pt"
CHAVE_PREFERENCIA = "idioma"
# O nome de cada idioma, escrito NO PRÓPRIO idioma: é assim que quem não lê
# português acha o seu.
NOMES = {"es": "Español", "pt": "Português", "en": "English"}
PASTA_CATALOGOS = Path(__file__).resolve().parent / "idiomas"

# Termos que ficam iguais em todos os idiomas: nomes próprios, siglas, nomes de
# módulo que são marca. Um literal IGUAL a um deles não precisa de `t()`
# (`tests/test_textos_da_interface.py`). O glossário inteiro, com os termos que
# se traduzem de um jeito fixo, está em `docs/base-conhecimento/00-frontend.md`.
NAO_SE_TRADUZ = frozenset({
    "SIG-FT", "PMIB", "PDM", "SAM-GM", "STATUS_PMIB", "_STATUS_PMIB", "LMR", "TAG", "TAGs",
    "AutoSpec", "AutoSpec AI (RAG)", "Analyzer", "PMIB Manager", "Search", "Gestão PMIB",
    "Excel", "PDF", "JSON", "RDS-PP", "Aconex", "GE Vernova", "Itaipu", "Gemini", "OpenRouter",
    "LlamaCloud", "Google", "Windows", "OK", "Español", "Português", "English",
})

_atual = PADRAO
_catalogos: dict[str, dict[str, str]] = {}


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta de
    dados. Função para os testes apontarem outro arquivo."""
    return None


def valido(codigo: object) -> str:
    return codigo if codigo in IDIOMAS else PADRAO


def _ler_catalogo(codigo: str) -> dict[str, str] | None:
    """O catálogo do disco, só com pares de texto não vazios; `None` se o arquivo
    não existe ou não é um objeto JSON."""
    try:
        dados = json.loads((PASTA_CATALOGOS / f"{codigo}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict):
        return None
    return {k: v for k, v in dados.items() if isinstance(k, str) and isinstance(v, str) and v}


def catalogo(codigo: str) -> dict[str, str]:
    """As traduções de `codigo` (o português: nenhuma). Lido uma vez por sessão."""
    codigo = valido(codigo)
    if codigo == PADRAO:
        return {}
    if codigo not in _catalogos:
        lido = _ler_catalogo(codigo)
        if lido is None:
            _log.warning("catalogo do idioma %s nao foi lido em %s", codigo, PASTA_CATALOGOS)
        _catalogos[codigo] = lido or {}
    return _catalogos[codigo]


def conferir() -> list[str]:
    """Os idiomas cujo catálogo não se lê. O `--smoke` do Release reprova: um
    catálogo fora do `.exe` deixaria o app em português, em silêncio."""
    return [codigo for codigo in IDIOMAS if codigo != PADRAO and _ler_catalogo(codigo) is None]


def atual() -> str:
    """O idioma desta sessão."""
    return _atual


def definir(codigo: object) -> str:
    """O idioma desta sessão (inválido: português). Devolve o que valeu. Não grava:
    quem lembra a escolha é `guardar`."""
    global _atual
    _atual = valido(codigo)
    catalogo(_atual)
    return _atual


def escolhido() -> str | None:
    """O idioma guardado, ou `None` se a pessoa ainda não escolheu (é o que faz a
    primeira abertura perguntar). Preferência que não se lê vale como português
    escolhido: perguntar a cada abertura sem conseguir lembrar seria pior."""
    from sigft.core import prefs

    try:
        valor = prefs.ler_preferencia(CHAVE_PREFERENCIA, "", config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        _log.warning("nao consegui ler o idioma escolhido", exc_info=True)
        return PADRAO
    return valor if valor in IDIOMAS else None


def guardar(codigo: object) -> str:
    """Lembra o idioma (inválido: português) para a próxima abertura e devolve o
    que gravou. Gravar que falha fica no log: não impede nada."""
    from sigft.core import prefs

    codigo = valido(codigo)
    try:
        prefs.gravar_preferencia(CHAVE_PREFERENCIA, codigo, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- lembrar não pode derrubar a tela
        _log.warning("nao consegui gravar o idioma escolhido", exc_info=True)
    return codigo


def t(texto: str, **valores) -> str:
    """`texto` (em português) no idioma da sessão, com os `{valores}` no lugar."""
    traduzido = catalogo(_atual).get(texto, texto) if _atual != PADRAO else texto
    if not valores:
        return traduzido
    # Qualquer erro do `format` (valor que falta, `{0}`, `{x.y}`, chave solta)
    # cai no português; se nem ele casa, o texto vai sem os valores. Montar a
    # tela vale mais que o texto perfeito: uma linha no log, nunca exceção.
    try:
        return traduzido.format(**valores)
    except Exception:  # noqa: BLE001
        pass
    if traduzido is not texto:
        try:
            resultado = texto.format(**valores)
        except Exception:  # noqa: BLE001
            pass
        else:
            _log.warning("traducao com valores que nao casam com o portugues: %r", texto)
            return resultado
    _log.warning("texto com valores que nao casam (vai sem os valores): %r", texto)
    return texto


def marcar(texto: str) -> str:
    """Marca uma constante de módulo como texto de interface. Devolve o próprio
    texto; quem o mostra chama `t(...)`."""
    return texto

"""Os recursos do app (ícone, logo, .env) têm de ser achados — CP 7.3/8.2.

Por que este arquivo existe
---------------------------
O CP 7.3 moveu o aplicativo do `frontend.py` (que ficava NA RAIZ) para
`sigft/app/main.py`. Todo código que resolvia caminho com
`os.path.dirname(os.path.abspath(__file__))` continuou "funcionando" — só que
passou a apontar para `sigft/app/` em vez da raiz.

O efeito é o pior tipo de defeito: **não quebra nada visivelmente**. O app
abre, a janela aparece, os testes passam, o `compileall` passa. Só que sem
ícone e sem logo, e — se tivesse pegado o `.env` — sem chave de API, como se o
usuário nunca as tivesse configurado. O aviso vai para o console, que ninguém
lê.

Foi exatamente o que aconteceu: o `resource_path` foi corrigido no CP 7.3, mas
DOIS outros pontos do `main.py` montavam o caminho de `assets/` por conta
própria, e passaram despercebidos até alguém ler a saída do app de verdade.

Este teste é a rede para isso não voltar.

[2026-10-15] A interface é a Qt (`sigft/app_qt/`; a antiga saiu do SIG-FT): o
`resource_path` é o de `sigft/app_qt/main.py`, e a raiz é calculada em
`_RAIZ` lá e em `estilo.py` (as fontes: `estilo.PASTA_FONTES` sai do
`__file__`, que no bundle aponta para dentro dele -- ver o `SIG-FT.spec`).
"""
from __future__ import annotations

import ast
import os
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
APP = RAIZ / "sigft" / "app_qt"


def _arquivos_do_app() -> list[pathlib.Path]:
    return sorted(APP.rglob("*.py")) + sorted((RAIZ / "sigft" / "app").rglob("*.py"))


def test_existe_o_pacote_do_app():
    assert APP.is_dir(), APP
    assert _arquivos_do_app()


def test_nenhum_arquivo_do_app_monta_caminho_de_recurso_com_dunder_file():
    """`__file__` dentro de `sigft/app_qt/` dá `sigft/app_qt/`, não a raiz.

    Quem precisa de um arquivo do projeto (ícone, logo, `.env`,
    `api_config.json`) tem de passar por `resource_path` — que sabe achar a
    raiz tanto rodando do `.py` quanto de dentro do `.exe` do PyInstaller
    (`sys._MEIPASS`).

    A única exceção legítima é quem calcula a raiz (`_RAIZ`, em `main.py` e em
    `estilo.py`).
    """
    ofensores = []

    for caminho in _arquivos_do_app():
        fonte = caminho.read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        linhas = fonte.split("\n")

        for no in ast.walk(arvore):
            # Procura `os.path.dirname(os.path.abspath(__file__))`.
            if not isinstance(no, ast.Call):
                continue
            if not (isinstance(no.func, ast.Attribute) and no.func.attr == "dirname"):
                continue
            if "__file__" not in ast.dump(no):
                continue

            # `main.py` e `estilo.py` calculam a raiz UMA vez, em `_RAIZ`. É a
            # exceção, e ela é reconhecida pelo nome da variável que recebe.
            linha_texto = linhas[no.lineno - 1] if no.lineno <= len(linhas) else ""
            if caminho.name in ("main.py", "estilo.py") and linha_texto.startswith("_RAIZ = "):
                continue

            ofensores.append(f"{caminho.relative_to(RAIZ)}:{no.lineno}: {linha_texto.strip()[:80]}")

    assert ofensores == [], (
        "caminho de recurso montado com `__file__` dentro da interface:\n  "
        + "\n  ".join(ofensores)
        + "\n\nIsso aponta para a pasta do módulo, não para a raiz do projeto. Use "
        "`resource_path(...)` de sigft/app_qt/main.py."
    )


def test_resource_path_resolve_para_a_raiz_do_projeto():
    from sigft.app_qt.main import _RAIZ, resource_path

    assert pathlib.Path(_RAIZ).resolve() == RAIZ
    # Um nome qualquer tem de cair na raiz, não em sigft/app_qt/.
    assert pathlib.Path(resource_path("qualquer.txt")).parent.resolve() == RAIZ


@pytest.mark.parametrize("recurso", ["assets", os.path.join("assets", "logo.png")])
def test_os_recursos_que_o_app_carrega_existem_de_fato(recurso):
    """Não basta o caminho apontar para a raiz: o arquivo tem de estar lá.

    `assets/logo.png` é o logo da splash e da barra lateral. Sem ele o app
    abre, mas sem identidade visual nenhuma — e só avisa no console.
    """
    from sigft.app_qt.main import resource_path

    assert os.path.exists(resource_path(recurso)), resource_path(recurso)

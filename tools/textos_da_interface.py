"""Os textos de interface do SIG-FT e os catálogos de tradução (2026-10-22).

A chave de cada tradução é o próprio texto em português, escrito no código
dentro de `t("...")` (traduzido na hora) ou de `marcar("...")` (constante de
módulo, traduzida onde aparece na tela). Ver `sigft/app/idioma.py`.

Esta ferramenta lê o código (sem importá-lo: `ast`) e responde três perguntas:

  * que chaves o código usa, e quais faltam ou sobram em cada catálogo
    (`sigft/app/idiomas/<codigo>.json`);
  * onde há `t(f"...")` ou `marcar(f"...")`: o f-string vira OUTRA chave a cada
    valor, e a tradução nunca casa. O certo é `t("... {nome} ...", nome=...)`;
  * que literais de um arquivo parecem texto de interface e não passam por
    `t()`/`marcar()` (a guarda de `tests/test_textos_da_interface.py`).

A terceira é heurística: um literal "parece texto" quando tem espaço, começa
com maiúscula seguida de minúscula, tem letra acentuada ou termina em ":" ou
"...". Fica de fora o que é identificador (`"primario"`, `"CriaFichas"`,
`"GEMINI"`), folha de estilo, nome de fonte, docstring, e o que vai para log,
`print`, `objectName`, propriedade, chave de dicionário, comparação ou
exceção, e a linha com a marca `# nao-e-interface`. Palavra
única toda em maiúsculas e sem acento ("ATRASADO") escapa: a conferência em
tela (`tests/_idioma.py`) a pega quando a constante está marcada.

Uso:
    python tools/textos_da_interface.py                 # o que falta e sobra em es e en
    python tools/textos_da_interface.py --faltando es   # JSON {"chave": ""} para preencher
    python tools/textos_da_interface.py --literais sigft/app_qt/views/home.py
    python tools/textos_da_interface.py --arrumar       # catálogos em ordem, sem escapar acento
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

RAIZ = Path(__file__).resolve().parent.parent
IDIOMAS_COM_CATALOGO = ("es", "en")
# Fora de `sigft/app_qt`, os módulos sem Qt que guardam texto de interface.
ARQUIVOS_DE_TEXTO = (
    "sigft/app/textos_dialogos.py",
    "sigft/app/textos_dicas.py",
    "sigft/app/atualizacao_textos.py",
    "sigft/app/resumo_lote.py",
)
FUNCOES_DE_TRADUCAO = frozenset({"t", "marcar"})
# `t()`/`marcar()` contam chamados soltos ou pelo módulo (`idioma.t`): um método
# de outro objeto com o mesmo nome (`self.barra.marcar(filtro)`) não é tradução.
DONOS_DA_TRADUCAO = frozenset({None, "idioma", "_idioma"})
# Chamadas cujos argumentos nunca são interface: log, saída, identificadores.
CHAMADAS_SEM_INTERFACE = frozenset({
    "log", "_log", "print", "logar", "setObjectName", "setProperty", "property",
    "findChild", "findChildren", "getattr", "hasattr", "setattr", "startswith", "endswith",
    "removeprefix", "removesuffix", "split", "rsplit", "partition", "replace", "strip",
    "strftime", "strptime", "compile", "match", "search", "sub", "fullmatch", "join", "Path",
    "getenv", "get_opcao", "set_opcao", "ler_preferencia", "gravar_preferencia", "backend",
    "exigir", "setStyleSheet", "folha_fonte_tk", "fonte_tk", "QFont", "QKeySequence",
    "definir_papel", "definir_propriedade", "Arrastavel",
})
DONOS_SEM_INTERFACE = frozenset({"logging", "_log", "logger", "log", "os", "re", "json", "sys"})
ARGUMENTOS_SEM_INTERFACE = frozenset({
    "objectName", "papel", "variante", "alinhar", "papel_cor", "papel_cor_ativo", "encoding",
})
NOMES_DE_FONTE = frozenset({
    "Roboto", "Segoe UI", "Consolas", "Menlo", "DejaVu Sans Mono", "Noto Emoji", "Arial",
    "Cascadia Mono",
})
_IDENTIFICADOR = re.compile(
    r"^[a-z0-9_.:\-/\\*%<>=]+$"           # chave, objectName, caminho, formato (sem espaço:
                                           # "nenhum arquivo selecionado" é texto)
    r"|^\*\.\w+(\s+\*\.\w+)*$"               # padrão de arquivo: "*.xlsx *.xlsm"
    r"|^[A-Z0-9_]+$"                       # constante, chave de API
    r"|^[A-Z][a-z0-9]*[A-Z][A-Za-z0-9]*$"  # CamelCase: nome de tela ou de classe
)
_FOLHA = re.compile(
    r"\b(font|color|background|border|padding|margin|min|max|height|width|text|selection"
    r"|lineedit|line|white)[-a-z]*\s*:\s*[^;]*;"   # propriedade: valor;
    r"|\bQ[A-Z]\w*\s*[\[{:]|#[a-z_]+\s*[{\[]"     # seletor de folha do Qt
)


class Uso(NamedTuple):
    arquivo: str
    linha: int
    texto: str


# Numa f-string, uma palavra minúscula de 3+ letras na parte fixa já é texto,
# mesmo sem espaço nem acento: `f"com {pessoa}"` sobrava, porque "com" sozinho
# parece identificador (revisão da Task 4, 2026-10-22). Colada a ponto, barra,
# hífen ou dois-pontos não conta: extensão (`.xlsx`), caminho, nome de thread
# (`tarefa:{nome}`). Folha de estilo (`_FOLHA`) também não.
_PALAVRA_MINUSCULA = re.compile(r"(?<![\w./\\-])[a-zà-ÿ]{3,}(?![\w./\\:-])")


def parece_texto(valor: str) -> bool:
    """A heurística do "texto de interface" (ver o docstring do módulo)."""
    texto = valor.strip()
    if len(texto) < 2 or not re.search(r"[A-Za-zÀ-ÿ]", texto):
        return False
    if texto in NOMES_DE_FONTE or _IDENTIFICADOR.match(texto) or _FOLHA.search(texto):
        return False
    return bool(" " in texto or re.match(r"^[A-ZÀ-Ý][a-zà-ÿ]", texto)
                or re.search(r"[À-ÿ]", texto) or texto.endswith((":", "...")))


def _nome_da_chamada(no: ast.Call) -> tuple[str | None, str | None]:
    funcao = no.func
    if isinstance(funcao, ast.Name):
        return funcao.id, None
    if isinstance(funcao, ast.Attribute):
        dono = funcao.value
        nome_do_dono = dono.id if isinstance(dono, ast.Name) else getattr(dono, "attr", None)
        return funcao.attr, nome_do_dono
    return None, None


def _docstrings(arvore: ast.AST) -> set[int]:
    achadas = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) \
                and no.body and isinstance(no.body[0], ast.Expr) \
                and isinstance(no.body[0].value, ast.Constant) \
                and isinstance(no.body[0].value.value, str):
            achadas.add(id(no.body[0].value))
    return achadas


def _texto_da_chamada(no: ast.Call) -> ast.expr | None:
    """O texto de um `t()`/`marcar()`: o 1º argumento ou o `texto=`."""
    if no.args:
        return no.args[0]
    return next((k.value for k in no.keywords if k.arg == "texto"), None)


def _montado(no: ast.expr) -> bool:
    """Texto montado na hora (f-string, `+`, `%`, `"...".format`): vira outra
    chave a cada valor, e a tradução nunca casa."""
    if isinstance(no, (ast.JoinedStr, ast.BinOp)):
        return True
    return isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) \
        and isinstance(no.func.value, (ast.Constant, ast.JoinedStr, ast.BinOp))


def chaves_do_codigo(fonte: str, arquivo: str = "") -> tuple[list[Uso], list[Uso]]:
    """`(chaves, ruins)`: o texto literal de cada `t()`/`marcar()` (1º argumento ou
    `texto=`), e as chamadas que não viram chave: `t()` com texto montado
    (`t(f"...")`, `t("A " + x)`, `t("%s" % x)`, `t("{}".format(x))`) e `marcar()`
    com qualquer coisa que não seja um literal. `t(CONSTANTE)` e `t(self.X)` não
    entram em nenhuma das duas: é como se mostra uma constante marcada."""
    chaves_, ruins = [], []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Call):
            continue
        nome, dono = _nome_da_chamada(no)
        if nome not in FUNCOES_DE_TRADUCAO or dono not in DONOS_DA_TRADUCAO:
            continue
        texto = _texto_da_chamada(no)
        if texto is None:
            continue
        if isinstance(texto, ast.Constant) and isinstance(texto.value, str):
            chaves_.append(Uso(arquivo, no.lineno, texto.value))
        elif _montado(texto) or nome == "marcar":
            ruins.append(Uso(arquivo, no.lineno, _texto_do_codigo(texto)))
    return chaves_, ruins


def _parte_do_fstring(parte) -> str:
    if isinstance(parte, ast.Constant):
        return repr(parte.value)[1:-1].replace("{", "{{").replace("}", "}}")
    texto = "{" + ast.unparse(parte.value)
    if parte.conversion != -1:
        texto += "!" + chr(parte.conversion)
    if parte.format_spec is not None:
        texto += ":" + "".join(_parte_do_fstring(p) for p in parte.format_spec.values)
    return texto + "}"


def _texto_do_codigo(no) -> str:
    """O trecho como `ast.unparse` o escrevia até o Python 3.11. No 3.12 (PEP 701)
    a f-string com aspas dentro sai com outras aspas, e `NAO_E_INTERFACE` (que
    guarda esse texto) deixaria de casar conforme a versão (CI de 2026-10-23)."""
    if not isinstance(no, ast.JoinedStr):
        return ast.unparse(no)
    corpo = "".join(_parte_do_fstring(parte) for parte in no.values)
    aspa = '"' if "'" in corpo and '"' not in corpo else "'"
    return "f" + aspa + corpo + aspa


# Marca de linha para o literal que é dado e não interface, quando listá-lo em
# `NAO_E_INTERFACE` seria pior (o mesmo dado repetido, por exemplo). Vale para a
# linha onde está, ou para qualquer linha de um literal que ocupa várias.
MARCA_NAO_E_INTERFACE = "# nao-e-interface"


def literais_soltos(fonte: str, arquivo: str = "") -> list[Uso]:
    """Os literais que parecem texto de interface e não passam por tradução."""
    arvore = ast.parse(fonte)
    pulados = _docstrings(arvore)
    linhas = fonte.splitlines()
    marcadas = {i for i, linha in enumerate(linhas, 1) if MARCA_NAO_E_INTERFACE in linha}
    for no in ast.walk(arvore):
        dentro = []
        if isinstance(no, ast.Call):
            nome, dono = _nome_da_chamada(no)
            if nome in FUNCOES_DE_TRADUCAO or nome in CHAMADAS_SEM_INTERFACE \
                    or dono in DONOS_SEM_INTERFACE:
                dentro += list(no.args) + [k.value for k in no.keywords]
            else:
                dentro += [k.value for k in no.keywords if k.arg in ARGUMENTOS_SEM_INTERFACE]
        elif isinstance(no, ast.Raise) and no.exc is not None:
            dentro.append(no.exc)
        elif isinstance(no, ast.Subscript):
            dentro.append(no.slice)
        elif isinstance(no, ast.Dict):
            dentro += [chave for chave in no.keys if chave is not None]
        elif isinstance(no, ast.Compare):
            dentro += [no.left, *no.comparators]
        elif isinstance(no, ast.JoinedStr):
            pulados.update(id(parte) for parte in no.values)
        for raiz in dentro:
            pulados.update(id(filho) for filho in ast.walk(raiz))
    achados = []
    for no in ast.walk(arvore):
        if id(no) in pulados:
            continue
        if marcadas and hasattr(no, "lineno") \
                and marcadas & set(range(no.lineno, (no.end_lineno or no.lineno) + 1)):
            continue
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and parece_texto(no.value):
            achados.append(Uso(arquivo, no.lineno, no.value))
        elif isinstance(no, ast.JoinedStr):
            fixo = "".join(p.value for p in no.values if isinstance(p, ast.Constant))
            if parece_texto(fixo) or (_PALAVRA_MINUSCULA.search(fixo) and not _FOLHA.search(fixo)):
                achados.append(Uso(arquivo, no.lineno, _texto_do_codigo(no)))
    return sorted(achados, key=lambda u: u.linha)


def arquivos(raiz: Path = RAIZ) -> list[Path]:
    return sorted((raiz / "sigft" / "app_qt").rglob("*.py")) + [raiz / a for a in ARQUIVOS_DE_TEXTO]


def chaves(raiz: Path = RAIZ) -> tuple[dict[str, list[Uso]], list[Uso]]:
    """Todas as chaves do código (`texto -> usos`) e todos os f-strings em `t()`."""
    todas: dict[str, list[Uso]] = {}
    fstrings: list[Uso] = []
    for caminho in arquivos(raiz):
        relativo = caminho.relative_to(raiz).as_posix()
        achadas, ruins = chaves_do_codigo(caminho.read_text(encoding="utf-8"), relativo)
        for uso in achadas:
            todas.setdefault(uso.texto, []).append(uso)
        fstrings += ruins
    return todas, fstrings


def _caminho_do_catalogo(codigo: str, raiz: Path) -> Path:
    return raiz / "sigft" / "app" / "idiomas" / f"{codigo}.json"


def catalogo(codigo: str, raiz: Path = RAIZ) -> dict[str, str]:
    return json.loads(_caminho_do_catalogo(codigo, raiz).read_text(encoding="utf-8"))


def faltando(codigo: str, raiz: Path = RAIZ) -> list[str]:
    usadas, _ = chaves(raiz)
    traducoes = catalogo(codigo, raiz)
    return sorted(c for c in usadas if not traducoes.get(c))


def sobrando(codigo: str, raiz: Path = RAIZ) -> list[str]:
    usadas, _ = chaves(raiz)
    return sorted(c for c in catalogo(codigo, raiz) if c not in usadas)


def arrumar(raiz: Path = RAIZ) -> None:
    """Reescreve os catálogos na forma única: chaves em ordem, `indent=2`, acento
    como acento e linha final (um diff por tradução, sem reordenar o arquivo)."""
    for codigo in IDIOMAS_COM_CATALOGO:
        caminho = _caminho_do_catalogo(codigo, raiz)
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        caminho.write_text(json.dumps(dict(sorted(dados.items())), ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--faltando", metavar="CODIGO", choices=IDIOMAS_COM_CATALOGO)
    parser.add_argument("--literais", nargs="+", metavar="ARQUIVO")
    parser.add_argument("--arrumar", action="store_true")
    args = parser.parse_args(argv)
    if args.arrumar:
        arrumar()
        return 0
    if args.faltando:
        print(json.dumps({c: "" for c in faltando(args.faltando)}, ensure_ascii=False, indent=2))
        return 0
    if args.literais:
        soltos = []
        for nome in args.literais:
            soltos += literais_soltos(Path(nome).read_text(encoding="utf-8"), nome)
        for uso in soltos:
            print(f"{uso.arquivo}:{uso.linha}: {uso.texto!r}")
        return 1 if soltos else 0
    _usadas, fstrings = chaves()
    problemas = 0
    for uso in fstrings:
        print(f"texto montado em t()/marcar(): {uso.arquivo}:{uso.linha}: {uso.texto}")
        problemas += 1
    for codigo in IDIOMAS_COM_CATALOGO:
        falta, sobra = faltando(codigo), sobrando(codigo)
        print(f"{codigo}: {len(falta)} faltando, {len(sobra)} sobrando")
        for chave in falta:
            print(f"  falta: {chave!r}")
        for chave in sobra:
            print(f"  sobra: {chave!r}")
        problemas += len(falta) + len(sobra)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())

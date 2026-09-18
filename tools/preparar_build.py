"""Prepara a árvore para o PyInstaller: carimba a versão e embute o token.

Rodado pelo workflow ANTES do build (e dá para rodar à mão, para testar):

    python tools/preparar_build.py 1.0.0 --origem github-actions --commit a1b2c3d

Escreve dois arquivos:

* **`sigft/_build_info.py`** — a versão do binário, tirada da TAG. É o que o
  verificador de atualização compara com o último Release. Sem este passo, um
  executável continuaria oferecendo "atualizar para a 1.0.0" eternamente.

* **`sigft/_update_auth.py`** — o token de leitura do repositório (privado),
  ofuscado. Está no `.gitignore`: o token entra no build, **nunca** no Git. O
  valor vem da variável de ambiente `SIGFT_UPDATE_TOKEN` (no CI, do segredo
  `UPDATE_TOKEN`); sem ela o arquivo sai vazio e o build simplesmente não
  procura atualizações — que é o certo para um build local.

Ver `docs/BUILD.md` para a rotação do token.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _saida_utf8() -> None:
    """Força UTF-8 no `stdout`/`stderr`.

    No Windows o Python escreve no console em cp1252 (a code page ANSI), e um
    `print` com "versão" ou uma seta morre com `UnicodeEncodeError` — o build
    falha por causa de uma MENSAGEM, depois de já ter rodado lint e testes.
    Acontece tanto no runner do GitHub quanto no `.bat` de qualquer máquina.

    O `except` cobre o caso de a saída ter sido redirecionada ou substituída
    (é o que o pytest faz), onde não existe `.reconfigure`.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_saida_utf8()

sys.path.insert(0, str(RAIZ))

from sigft._ofuscacao import ofuscar  # noqa: E402 — depende do sys.path acima

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")

_CAMPOS = ("VERSAO", "COMMIT", "DATA_BUILD", "ORIGEM")


def escrever_build_info(versao: str, origem: str, commit: str, *,
                        raiz: Path | None = None, hoje: str | None = None) -> Path:
    """Reescreve as quatro linhas de `sigft/_build_info.py`.

    Substituição linha a linha, e não reescrita do arquivo inteiro, para que
    o docstring (que é onde mora a explicação de por que a versão não pode vir
    do `.env`) sobreviva ao carimbo.

    `raiz` e `hoje` são parâmetros para o teste não precisar escrever no
    `_build_info.py` de verdade nem depender da data de hoje.
    """
    destino = (raiz or RAIZ) / "sigft" / "_build_info.py"
    texto = destino.read_text(encoding="utf-8")

    valores = {
        "VERSAO": versao.strip().lstrip("vV"),
        "COMMIT": commit[:7],
        "DATA_BUILD": hoje or date.today().isoformat(),
        "ORIGEM": origem,
    }

    for chave in _CAMPOS:
        texto, n = re.subn(rf'^{chave} = ".*"$', f'{chave} = "{valores[chave]}"',
                           texto, count=1, flags=re.M)
        if n != 1:
            # Parar é o certo. O modo silencioso seria seguir com a versão
            # antiga embutida, e o executável publicado como 2.0.0 se
            # declararia 1.0.0 -- oferecendo a mesma atualização para sempre.
            raise SystemExit(
                f"_build_info.py: nao achei a linha de {chave} para substituir. "
                f"O arquivo foi reescrito? O build PARA aqui de proposito."
            )

    destino.write_text(texto, encoding="utf-8")
    return destino


_CABECALHO_AUTH = '''"""Token de atualizacao embutido no build -- GERADO, nao edite.

Escrito por `tools/preparar_build.py` a partir do segredo `UPDATE_TOKEN` do
repositorio. Esta no `.gitignore` de proposito: assim nenhum token chega ao
Git, nem por engano. Em build local o arquivo nao existe (ou vem vazio) e o
app apenas nao procura atualizacoes.
"""
'''


def escrever_token(token: str, *, raiz: Path | None = None) -> Path:
    """Grava `sigft/_update_auth.py`. Token vazio = build sem atualização."""
    destino = (raiz or RAIZ) / "sigft" / "_update_auth.py"
    destino.write_text(
        f'{_CABECALHO_AUTH}\nTOKEN_OFUSCADO = "{ofuscar(token)}"\n',
        encoding="utf-8",
    )
    return destino


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("versao", help="versao do build, sem o 'v' (ex.: 1.0.0)")
    ap.add_argument("--origem", default="local", help="github-actions | local")
    ap.add_argument("--commit", default="", help="SHA do commit do build")
    args = ap.parse_args()

    versao = args.versao.strip().lstrip("vV")
    if not SEMVER.match(versao):
        raise SystemExit(
            f"Versao invalida: {args.versao!r}. Use MAJOR.MINOR.PATCH "
            f"(ex.: 1.0.0), opcionalmente com -rc.1."
        )

    caminho = escrever_build_info(versao, args.origem, args.commit)
    print(f"versao  -> {caminho}  ({versao})")

    token = os.getenv("SIGFT_UPDATE_TOKEN", "").strip()
    escrever_token(token)
    print("token   -> sigft/_update_auth.py  " + (
        f"({len(token)} caracteres, ofuscado)" if token
        else "(VAZIO -- este build nao tera atualizacao automatica)"
    ))


if __name__ == "__main__":
    main()

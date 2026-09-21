"""Decide a versão de um Release, e se ele é pré-lançamento.

Por que isto é um script, e não cinco linhas de shell no YAML
-------------------------------------------------------------
Porque a primeira versão ficou no YAML, e tinha um defeito que ninguém podia
ver: `git tag v1.0.0-rc.1` publicava um release **normal**. O bloco só marcava
pré-lançamento quando o disparo vinha do botão; um push de tag caía sempre em
`prerelease=false`.

E o efeito é do pior tipo. `/releases/latest` ignora pré-lançamentos, mas **só
os marcados como tal** — o sufixo `-rc.1` no nome não significa nada para o
GitHub. Então o candidato a lançamento viraria a versão "mais recente" e seria
oferecido como atualização para todo mundo, que é exatamente o contrário do que
um `-rc` existe para fazer.

Lógica em YAML não tem teste. Mesma razão que tirou o manifesto de lá.

Uso (no workflow):

    python tools/versao_do_release.py --evento push --ref "$GITHUB_REF_NAME"
    python tools/versao_do_release.py --evento workflow_dispatch \\
        --entrada-versao 1.0.1 --entrada-prerelease true

Escreve as quatro saídas no `$GITHUB_OUTPUT`, e também as imprime.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")


def _saida_utf8() -> None:
    """Mesma proteção dos outros scripts de build — ver `preparar_build.py`."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_saida_utf8()


def _para_bool(valor) -> bool:
    """`inputs.prerelease` chega como a STRING `"true"`/`"false"`.

    E `bool("false")` em Python é `True` — o release sairia sempre marcado
    como pré-lançamento, e nunca seria oferecido a ninguém. Silencioso, e
    daqueles que só aparecem quando alguém pergunta "por que ninguém recebeu
    a atualização?".
    """
    if isinstance(valor, bool):
        return valor
    return str(valor or "").strip().lower() in ("true", "1", "yes", "sim")


def decidir(*, evento: str, ref_name: str = "",
            entrada_versao: str = "", entrada_prerelease=False) -> dict:
    """As quatro decisões do Release, num dicionário.

    * `versao`     — a de EXIBIÇÃO, com o sufixo (`1.0.0-rc.1`);
    * `numerica`   — a BINÁRIA, só dígitos. O `VersionInfoVersion` do Inno
      recusa qualquer outra coisa, e o compilador **aborta** — armadilha nº 2;
    * `tag`        — `v` + versão;
    * `prerelease` — ver abaixo.

    **Num push de tag, o sufixo decide**: `v1.0.0-rc.1` sai marcado como
    pré-lançamento, e por isso não é oferecido como atualização a ninguém.

    **Pelo botão, a caixa decide, e ela ganha da dedução**: quem digitou
    `1.0.0-rc.1` e desmarcou a caixa quis publicar de verdade — talvez para
    testar o próprio fluxo de atualização. Forçar ali seria decidir pela
    pessoa.
    """
    if evento == "workflow_dispatch":
        versao = str(entrada_versao or "").strip().lstrip("vV")
        prerelease = _para_bool(entrada_prerelease)
    else:
        versao = str(ref_name or "").strip().lstrip("vV")
        prerelease = "-" in versao

    if not SEMVER.match(versao):
        # Parar aqui custa segundos. Deixar passar custa os 20 minutos do
        # empacotamento antes de o Inno Setup reclamar -- e a mensagem dele
        # não diz que o problema é o formato da versão.
        raise SystemExit(
            f"Versao invalida: {versao!r} (de {ref_name or entrada_versao!r}). "
            f"Use MAJOR.MINOR.PATCH, opcionalmente com -rc.1."
        )

    return {
        "versao": versao,
        "numerica": versao.split("-")[0],
        "tag": f"v{versao}",
        "prerelease": prerelease,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evento", required=True, help="push | workflow_dispatch")
    ap.add_argument("--ref", default="", help="GITHUB_REF_NAME, num push de tag")
    ap.add_argument("--entrada-versao", default="", help="o campo do botao")
    ap.add_argument("--entrada-prerelease", default="", help="a caixa do botao")
    args = ap.parse_args()

    d = decidir(evento=args.evento, ref_name=args.ref,
                entrada_versao=args.entrada_versao,
                entrada_prerelease=args.entrada_prerelease)

    linhas = [
        f"versao={d['versao']}",
        f"numerica={d['numerica']}",
        f"tag={d['tag']}",
        # minúsculas: é como o shell do passo seguinte compara.
        f"prerelease={str(d['prerelease']).lower()}",
    ]

    if (saida := os.getenv("GITHUB_OUTPUT")):
        with open(saida, "a", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")

    for linha in linhas:
        print(linha)

    rotulo = "PRE-LANCAMENTO (ninguem recebe como atualizacao)" if d["prerelease"] \
        else "publicacao de verdade"
    print(f"-> v{d['versao']} (binario: {d['numerica']}) -- {rotulo}")


if __name__ == "__main__":
    main()

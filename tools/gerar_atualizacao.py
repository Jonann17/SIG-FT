"""Atualização automática só com o que mudou -- a metade do BUILD.

Ver `docs/superpowers/specs/2026-10-07-atualizacao-incremental-design.md`.
Pedido do Luan (2026-10-07): *"sempre que precisa atualizar está precisando
instalar ele completamente do zero, quero tipo uma atualização apenas do que
foi modificado para ser mais rápido"*.

O instalador completo tem centenas de MB (o tradutor sozinho, 218), e entre
duas versões quase tudo é igual: o que muda é o `SIG-FT.exe` (no onedir do
PyInstaller o código Python vai dentro dele) e um ou outro arquivo. Este script,
chamado pelo `.github/workflows/release.yml`:

  manifesto       grava o `arquivos.json`: cada arquivo da pasta instalada, com
                  SHA256 e tamanho. Vai para o Release, e é a BASE da versão
                  seguinte;
  escolher-bases  diz de quais versões anteriores sai um `.zip` de arquivos (as 3
                  mais recentes com `arquivos.json`, e a última normal sempre);
  pacotes         para cada base: a diferença, o `.zip` SÓ COM OS ARQUIVOS que o
                  próprio app aplica, aberto (`sigft/services/pacote_arquivos.py`),
                  e o registro no `latest.json` (chave `arquivos`), que o app lê
                  para escolher o arquivo.

[2026-10-30] Até aqui cada base gerava também um instalador PEQUENO (o
`installer/sigft.iss` em modo atualização, em `.bin`, `.zip` e `.exe`). Saiu:
agora é como no DocManager -- o zip de arquivos, ou o instalador completo.
A entrada do `latest.json` não traz mais `arquivo`/`sha256`: o app até a
1.3.0, que procura o pequeno por elas, não acha nada e baixa o completo. Ver
`docs/superpowers/specs/2026-10-27-atualizacao-como-cmi-design.md`.

Só stdlib e o `pacote_arquivos` (também só stdlib), que mora no pacote do app
porque é ele quem APLICA: uma implementação só do formato.
Escreve UTF-8 sem BOM no JSON (o app lê de volta).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Rodado como script (`python tools/gerar_atualizacao.py`, no release.yml), o
# `sys.path` só tem `tools/`. O mesmo jeito do `tools/gerar_manifesto.py`.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from sigft.services import pacote_arquivos  # noqa: E402 — depende do sys.path acima

ARQUIVO_ARQUIVOS = "arquivos.json"
NOME_CHANGELOG = "CHANGELOG.md"

# Pacote que copia mais que isto do total não compensa: o completo, comprimido
# inteiro, sai quase do mesmo tamanho e não depende da versão instalada.
LIMITE_FRACAO = 0.6

# Quantas versões anteriores viram base, além da última normal.
BASES_RECENTES = 3


def _saida_utf8() -> None:
    """O log do runner no Windows pode estar em cp1252. E a linha termina em
    `\n`, nunca `\r\n`: o `escolher-bases` alimenta um `$(...)` do bash, que
    só corta o fim -- com `\r\n` toda tag menos a última chegava ao
    `gh release download` com um `\r` grudado ("release not found"), e só a
    última base virava atualização pequena (Releases de 1.2.0-rc.5 a 1.2.1-rc.1)."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace", newline="\n")
        except (AttributeError, ValueError):
            pass


# O mesmo SHA256 com que o app confere a pasta depois de aplicar.
sha256 = pacote_arquivos.sha256


# --------------------------------------------------------------------------
# A. O manifesto de arquivos
# --------------------------------------------------------------------------
def manifesto(pasta: Path, changelog: Path | None, versao: str) -> dict:
    """`{"versao", "arquivos": {caminho/relativo: {"sha256", "tamanho"}}}` --
    a pasta instalada como o instalador completo a deixa: a `dist\\SIG-FT\\`
    inteira e o `CHANGELOG.md` na raiz. Caminhos com `/`."""
    arquivos = {}
    for caminho in sorted(Path(pasta).rglob("*")):
        if caminho.is_file():
            arquivos[caminho.relative_to(pasta).as_posix()] = {
                "sha256": sha256(caminho), "tamanho": caminho.stat().st_size}
    if changelog is not None:
        arquivos[NOME_CHANGELOG] = {"sha256": sha256(changelog), "tamanho": Path(changelog).stat().st_size}
    return {"versao": versao, "arquivos": dict(sorted(arquivos.items()))}


# --------------------------------------------------------------------------
# B. A diferença
# --------------------------------------------------------------------------
@dataclass
class Diferenca:
    copiar: list[str]         # novos ou com hash diferente
    remover: list[str]        # estavam na base e sumiram
    bytes_copiar: int
    bytes_total: int


def diferenca(base: dict, novo: dict) -> Diferenca:
    antes, depois = base["arquivos"], novo["arquivos"]
    copiar = sorted(c for c, info in depois.items()
                    if antes.get(c, {}).get("sha256") != info["sha256"])
    remover = sorted(c for c in antes if c not in depois)
    return Diferenca(
        copiar=copiar,
        remover=remover,
        bytes_copiar=sum(depois[c]["tamanho"] for c in copiar),
        bytes_total=sum(info["tamanho"] for info in depois.values()),
    )


# --------------------------------------------------------------------------
# C. Quais versões anteriores viram base
# --------------------------------------------------------------------------
def _tem_manifesto(release: dict) -> bool:
    return any(a.get("name") == ARQUIVO_ARQUIVOS for a in release.get("assets", []))


def escolher_bases(releases: list[dict], tag_atual: str) -> list[str]:
    """Tags das versões anteriores que viram base, na ordem da API (a mais
    nova primeiro): as `BASES_RECENTES` mais recentes com `arquivos.json` e,
    sempre, a última normal com ele -- é nela que está quase todo mundo."""
    candidatas = [r for r in releases
                  if not r.get("draft") and r.get("tag_name") != tag_atual and _tem_manifesto(r)]
    bases = [r["tag_name"] for r in candidatas[:BASES_RECENTES]]
    normal = next((r["tag_name"] for r in candidatas if not r.get("prerelease")), None)
    if normal is not None and normal not in bases:
        bases.append(normal)
    return bases


# --------------------------------------------------------------------------
# D. O registro no latest.json
# --------------------------------------------------------------------------
def registrar(latest: dict, de: str, arquivos: Path) -> dict:
    """Acrescenta o `.zip` de arquivos ao `latest.json`: o app escolhe a
    entrada cujo `de` é a versão instalada e lê a chave `arquivos`.

    [2026-10-30] Só `de` e `arquivos`: sem `arquivo` e `sha256` no topo da
    entrada, o app até a 1.3.0 (que procura ali o instalador pequeno) não
    escolhe nada e fica com o completo."""
    entrada = {"de": de, "arquivos": {"arquivo": Path(arquivos).name, "sha256": sha256(arquivos),
                                      "tamanho": Path(arquivos).stat().st_size}}
    latest.setdefault("atualizacoes", []).append(entrada)
    return latest


# --------------------------------------------------------------------------
# E. A orquestração
# --------------------------------------------------------------------------
def pacotes(novo: dict, bases: Path, *, versao: str, latest: Path, pasta: Path,
            saida: Path, changelog: Path | None = None) -> list[Path]:
    """Um `.zip` de arquivos por base (`pacote_arquivos.montar`, em `saida`).
    Devolve os gerados.

    O que não compensa (nada mudou, ou muda mais de `LIMITE_FRACAO` do total:
    o completo serve igual e não depende da versão instalada) ou não se monta
    fica de fora COM AVISO no log do workflow, sem derrubar o Release.
    """
    manifesto_latest = json.loads(Path(latest).read_text(encoding="utf-8"))
    Path(saida).mkdir(parents=True, exist_ok=True)
    feitos = []
    for arquivo_base in sorted(Path(bases).glob("*.json")):
        base = json.loads(arquivo_base.read_text(encoding="utf-8"))
        de = str(base.get("versao", ""))
        if not de or de == versao:
            continue
        dif = diferenca(base, novo)
        if not dif.copiar and not dif.remover:
            print(f"de {de}: nada mudou -- sem atualizacao por arquivos.")
            continue
        fracao = dif.bytes_copiar / dif.bytes_total if dif.bytes_total else 1.0
        if fracao > LIMITE_FRACAO:
            print(f"::warning::de {de}: os arquivos seriam {fracao:.0%} do pacote -- fica so o completo.")
            continue
        try:
            zipado = pacote_arquivos.montar(
                pasta, dif.copiar, dif.remover, de, versao, Path(saida),
                extras={NOME_CHANGELOG: Path(changelog)} if changelog is not None else None)
        except (OSError, pacote_arquivos.ErroPacote) as erro:
            print(f"::warning::de {de}: o .zip so com os arquivos nao saiu ({erro}) -- fica so o completo.")
            (Path(saida) / pacote_arquivos.nome_pacote(de, versao)).unlink(missing_ok=True)
            continue
        registrar(manifesto_latest, de, zipado)
        feitos.append(zipado)
        print(f"de {de}: {len(dif.copiar)} arquivo(s) a copiar ({dif.bytes_copiar / 1e6:.1f} MB de "
              f"{dif.bytes_total / 1e6:.1f} MB), {len(dif.remover)} a remover -> {zipado.name} "
              f"({zipado.stat().st_size / 1e6:.1f} MB)")
    if feitos:
        Path(latest).write_text(json.dumps(manifesto_latest, indent=2, ensure_ascii=False), encoding="utf-8")
    return feitos


# --------------------------------------------------------------------------
# A linha de comando
# --------------------------------------------------------------------------
def main(argv=None) -> None:
    _saida_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)

    m = sub.add_parser("manifesto")
    m.add_argument("--pasta", required=True, type=Path)
    m.add_argument("--changelog", type=Path)
    m.add_argument("--versao", required=True)
    m.add_argument("--saida", type=Path, default=Path(ARQUIVO_ARQUIVOS))

    b = sub.add_parser("escolher-bases")
    b.add_argument("--releases", required=True, type=Path, help="JSON de GET /repos/.../releases")
    b.add_argument("--tag-atual", required=True)

    p = sub.add_parser("pacotes")
    p.add_argument("--novo", type=Path, default=Path(ARQUIVO_ARQUIVOS))
    p.add_argument("--bases", required=True, type=Path)
    p.add_argument("--versao", required=True)
    p.add_argument("--latest", type=Path, default=Path("latest.json"))
    p.add_argument("--pasta", type=Path, default=Path("dist/SIG-FT"),
                   help="de onde saem os arquivos do .zip so com os arquivos")
    p.add_argument("--changelog", type=Path, default=Path(NOME_CHANGELOG))
    p.add_argument("--saida", type=Path, default=Path("installer/Output"),
                   help="onde os .zip sao gravados (o release.yml publica dali)")

    args = ap.parse_args(argv)
    if args.comando == "manifesto":
        dados = manifesto(args.pasta, args.changelog, args.versao)
        args.saida.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        total = sum(i["tamanho"] for i in dados["arquivos"].values())
        print(f"{args.saida}: {len(dados['arquivos'])} arquivo(s), {total / 1e6:.1f} MB")
    elif args.comando == "escolher-bases":
        releases = json.loads(args.releases.read_text(encoding="utf-8"))
        for tag in escolher_bases(releases, args.tag_atual):
            print(tag)
    else:
        novo = json.loads(args.novo.read_text(encoding="utf-8"))
        feitos = pacotes(novo, args.bases, versao=args.versao, latest=args.latest, pasta=args.pasta,
                         saida=args.saida, changelog=args.changelog)
        print(f"{len(feitos)} atualizacao(oes) por arquivos.")


if __name__ == "__main__":
    main()

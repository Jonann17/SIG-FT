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
  escolher-bases  diz de quais versões anteriores sai um instalador pequeno (as 3
                  mais recentes com `arquivos.json`, e a última normal sempre);
  pacotes         para cada base: a diferença, os includes do Inno, o ISCC em modo
                  atualização (`installer/sigft.iss` com `/DAtualizacao=1`) e o
                  registro no `latest.json`, que o app lê para escolher o arquivo.

O instalador pequeno sai como `.bin`, e não `.exe`: o app 1.1.1 baixa "o
primeiro `.exe` do Release", e não pode pegar um instalador que não serve para
ele. O app novo confere o SHA256 e o renomeia antes de rodar.
[2026-10-19] Vai também em `.zip` e em `.exe` (o tipo verdadeiro, igual byte a
byte), em chaves que só o app novo lê; o `.exe` só sobe em pré-lançamento.

Só stdlib. Escreve UTF-8 sem BOM no JSON (o app lê de volta) e COM BOM nos
includes do Inno, que é como ele reconhece UTF-8 num arquivo `.iss`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

ARQUIVO_ARQUIVOS = "arquivos.json"
NOME_CHANGELOG = "CHANGELOG.md"

# Os includes que o `installer/sigft.iss` lê em modo atualização. Nomes fixos,
# ao lado do `.iss` (o `#include` procura primeiro na pasta dele): gerados a
# cada build, fora do Git.
INCLUDE_ARQUIVOS = "atualizacao_arquivos.iss"
INCLUDE_REMOCOES = "atualizacao_remover.iss"
# O que o ISCC grava em modo atualização (`OutputBaseFilename` do `.iss`).
SAIDA_DO_ISCC = "SIG-FT_Itaipu_Atualizacao.exe"

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


def sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


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
    pastas_vazias: list[str]  # pastas da base que não existem mais (a mais funda primeiro)
    bytes_copiar: int
    bytes_total: int


def _pastas(caminhos) -> set[str]:
    pastas = set()
    for caminho in caminhos:
        pasta = posixpath.dirname(caminho)
        while pasta:
            pastas.add(pasta)
            pasta = posixpath.dirname(pasta)
    return pastas


def diferenca(base: dict, novo: dict) -> Diferenca:
    antes, depois = base["arquivos"], novo["arquivos"]
    copiar = sorted(c for c, info in depois.items()
                    if antes.get(c, {}).get("sha256") != info["sha256"])
    remover = sorted(c for c in antes if c not in depois)
    sumidas = _pastas(antes) - _pastas(depois)
    return Diferenca(
        copiar=copiar,
        remover=remover,
        pastas_vazias=sorted(sumidas, key=lambda p: (-p.count("/"), p)),
        bytes_copiar=sum(depois[c]["tamanho"] for c in copiar),
        bytes_total=sum(info["tamanho"] for info in depois.values()),
    )


# --------------------------------------------------------------------------
# C. Os includes do Inno
# --------------------------------------------------------------------------
def _inno(texto: str) -> str:
    """`{` abre constante no Inno (`{app}`): o literal é `{{`. Aspas dentro de
    um valor entre aspas dobram."""
    return texto.replace("{", "{{").replace('"', '""')


def _windows(caminho: str) -> str:
    return caminho.replace("/", "\\")


def include_arquivos(dif: Diferenca) -> str:
    """O `[Files]` do instalador pequeno. Caminhos relativos ao `.iss`, como
    os do completo (`..\\dist\\SIG-FT\\*` e `..\\CHANGELOG.md`)."""
    linhas = ["; Gerado por tools/gerar_atualizacao.py -- nao editar."]
    for caminho in dif.copiar:
        origem = "..\\CHANGELOG.md" if caminho == NOME_CHANGELOG else "..\\dist\\SIG-FT\\" + _windows(caminho)
        pasta = posixpath.dirname(caminho)
        destino = "{app}" + ("\\" + _inno(_windows(pasta)) if pasta else "")
        linhas.append(f'Source: "{_inno(origem)}"; DestDir: "{destino}"; Flags: ignoreversion')
    return "\n".join(linhas) + "\n"


def include_remocoes(dif: Diferenca) -> str:
    """O `[InstallDelete]` do instalador pequeno: arquivo por arquivo, e as
    pastas só se ficarem vazias. Nunca `{app}` nem `{app}\\_internal` inteiros
    (é o completo que limpa a pasta toda)."""
    linhas = ["; Gerado por tools/gerar_atualizacao.py -- nao editar."]
    linhas += [f'Type: files; Name: "{{app}}\\{_inno(_windows(c))}"' for c in dif.remover]
    linhas += [f'Type: dirifempty; Name: "{{app}}\\{_inno(_windows(p))}"' for p in dif.pastas_vazias]
    return "\n".join(linhas) + "\n"


# --------------------------------------------------------------------------
# D. Quais versões anteriores viram base
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
# E. O registro no latest.json
# --------------------------------------------------------------------------
# O app reconhece o pequeno por este começo de nome e nunca o toma pelo
# instalador completo (`sigft/services/updater.py`, `PREFIXO_DO_PEQUENO`).
PREFIXO_DO_PEQUENO = "SIG-FT_Itaipu_Atualizacao_"


def nome_do_pacote(de: str, para: str) -> str:
    return f"{PREFIXO_DO_PEQUENO}{de}_para_{para}.bin"


def nome_do_zip(de: str, para: str) -> str:
    return f"{PREFIXO_DO_PEQUENO}{de}_para_{para}.zip"


def nome_do_exe(de: str, para: str) -> str:
    return f"{PREFIXO_DO_PEQUENO}{de}_para_{para}.exe"


def nome_do_membro_do_zip(de: str, para: str) -> str:
    return nome_do_exe(de, para)


def copiar_como_exe(pacote: Path, de: str, para: str) -> Path:
    """[2026-10-19] O mesmo instalador pequeno com o nome do tipo que ele é.

    O proxy da empresa deixa passar o completo, que é um `.exe`, e cortou o fim
    do `.bin`. Isto NÃO esconde nada: é o mesmo executável, que o proxy analisa
    como analisa o completo. Cópia, e não renome: o `.bin` segue para o app que
    já está instalado."""
    destino = Path(pacote).parent / nome_do_exe(de, para)
    destino.unlink(missing_ok=True)
    shutil.copyfile(pacote, destino)
    return destino


def zipar(pacote: Path, de: str, para: str) -> Path:
    """O mesmo instalador pequeno dentro de um `.zip` comum, ao lado do `.bin`.

    [2026-10-16] O proxy da empresa cortou o fim do `.bin` 3 de 3 vezes e deixou
    passar o `.exe` completo; o `.zip` é a aposta de outro tipo de arquivo.
    SEM SENHA, de propósito: um zip que o proxy não consegue abrir seria
    contornar a análise da empresa. `ZIP_STORED`: o instalador já vem comprimido
    (LZMA do Inno), comprimir de novo não ganha nada."""
    destino = Path(pacote).parent / nome_do_zip(de, para)
    destino.unlink(missing_ok=True)
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_STORED) as z:
        z.write(pacote, arcname=nome_do_membro_do_zip(de, para))
    return destino


def registrar(latest: dict, de: str, pacote: Path, zipado: Path | None = None,
              exe: Path | None = None) -> dict:
    """Acrescenta o instalador pequeno ao `latest.json`: o app escolhe a
    entrada cujo `de` é a versão instalada. O `.zip`, quando há, vai numa chave
    nova (`zip`) que só o app de 2026-10-16 em diante lê; o app instalado
    continua no `arquivo` (`.bin`) de sempre."""
    entrada = {"de": de, "arquivo": Path(pacote).name, "sha256": sha256(pacote),
               "tamanho": Path(pacote).stat().st_size}
    for chave, outro in (("zip", zipado), ("exe", exe)):
        if outro is not None:
            entrada[chave] = {"arquivo": Path(outro).name, "sha256": sha256(outro),
                              "tamanho": Path(outro).stat().st_size}
    latest.setdefault("atualizacoes", []).append(entrada)
    return latest


# --------------------------------------------------------------------------
# F. A orquestração
# --------------------------------------------------------------------------
def pacotes(novo: dict, bases: Path, *, versao: str, numerica: str, iscc: str, iss: Path,
            latest: Path, executar=subprocess.run) -> list[Path]:
    """Um instalador pequeno por base. Devolve os `.bin` gerados.

    O que não compensa (nada mudou, ou muda mais de `LIMITE_FRACAO` do total) ou
    não compila fica de fora COM AVISO no log do workflow, sem derrubar o
    Release: o instalador completo já está pronto e serve para todo mundo.
    """
    iss = Path(iss)
    saida_iscc = iss.parent / "Output" / SAIDA_DO_ISCC
    manifesto_latest = json.loads(Path(latest).read_text(encoding="utf-8"))
    feitos = []
    for arquivo_base in sorted(Path(bases).glob("*.json")):
        base = json.loads(arquivo_base.read_text(encoding="utf-8"))
        de = str(base.get("versao", ""))
        if not de or de == versao:
            continue
        dif = diferenca(base, novo)
        if not dif.copiar and not dif.remover:
            print(f"de {de}: nada mudou -- sem instalador pequeno.")
            continue
        fracao = dif.bytes_copiar / dif.bytes_total if dif.bytes_total else 1.0
        if fracao > LIMITE_FRACAO:
            print(f"::warning::de {de}: o pequeno copiaria {fracao:.0%} do pacote -- fica so o completo.")
            continue
        (iss.parent / INCLUDE_ARQUIVOS).write_text(include_arquivos(dif), encoding="utf-8-sig")
        (iss.parent / INCLUDE_REMOCOES).write_text(include_remocoes(dif), encoding="utf-8-sig")
        saida_iscc.unlink(missing_ok=True)
        resultado = executar([iscc, "/DAtualizacao=1", f"/DVersaoDe={de}", f"/DMyAppVersion={versao}",
                              f"/DMyVersionInfo={numerica}", str(iss)])
        if resultado.returncode != 0 or not saida_iscc.is_file():
            print(f"::warning::de {de}: o ISCC nao gerou o instalador pequeno (codigo {resultado.returncode}) "
                  "-- fica so o completo.")
            continue
        pacote = saida_iscc.parent / nome_do_pacote(de, versao)
        pacote.unlink(missing_ok=True)
        shutil.move(str(saida_iscc), str(pacote))
        registrar(manifesto_latest, de, pacote, zipar(pacote, de, versao),
                  copiar_como_exe(pacote, de, versao))
        feitos.append(pacote)
        print(f"de {de}: {len(dif.copiar)} arquivo(s) a copiar ({dif.bytes_copiar / 1e6:.1f} MB de "
              f"{dif.bytes_total / 1e6:.1f} MB), {len(dif.remover)} a remover -> {pacote.name} "
              f"({pacote.stat().st_size / 1e6:.1f} MB)")
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
    p.add_argument("--numerica", required=True)
    p.add_argument("--iscc", required=True)
    p.add_argument("--iss", type=Path, default=Path("installer/sigft.iss"))
    p.add_argument("--latest", type=Path, default=Path("latest.json"))

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
        feitos = pacotes(novo, args.bases, versao=args.versao, numerica=args.numerica, iscc=args.iscc,
                         iss=args.iss, latest=args.latest)
        print(f"{len(feitos)} instalador(es) pequeno(s).")


if __name__ == "__main__":
    main()

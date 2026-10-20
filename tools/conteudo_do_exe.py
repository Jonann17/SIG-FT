"""O que vai DENTRO do `SIG-FT.exe`, entrada por entrada, com o hash de cada uma.

Por que existe (2026-10-20): a atualização pequena da 1.2.1-rc.9 levou o
`SIG-FT.exe` inteiro (34 MB) sem nenhuma biblioteca ter mudado. O executável
do PyInstaller é o "bootloader" (o `.exe` de verdade) com um arquivo PKG
grudado no fim, e dentro do PKG vai o PYZ (todo o Python de terceiros).
Comparar o `.exe` inteiro só diz "mudou"; comparar entrada por entrada diz O
QUÊ mudou -- que é o que falta para consertar na origem.

Uso:
    python tools/conteudo_do_exe.py dist/SIG-FT/SIG-FT.exe > conteudo-do-exe.json
    python tools/conteudo_do_exe.py --comparar velho.json novo.json

Precisa do PyInstaller instalado (é ele que sabe ler o próprio formato).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def conteudo(caminho: str) -> dict:
    """`{"exe": sha, "cabecalho": sha, "pkg": {nome: sha}, "pyz": {nome: sha}}`.

    `cabecalho` = os bytes ANTES do PKG: o bootloader, com o cabeçalho PE e os
    recursos (ícone, versão, manifesto). `pkg` = cada entrada do PKG,
    descomprimida. `pyz` = cada módulo do PYZ, cru (o código compilado).
    """
    from PyInstaller.archive.readers import PKG_ITEM_PYZ, CArchiveReader

    with open(caminho, "rb") as arquivo:
        tudo = arquivo.read()
    pkg = CArchiveReader(caminho)
    saida = {
        "exe": _sha(tudo),
        "cabecalho": _sha(tudo[:pkg._start_offset]),
        "pkg": {},
        "pyz": {},
    }
    for nome, (*_, tipo) in sorted(pkg.toc.items()):
        saida["pkg"][nome] = _sha(pkg.extract(nome))
        if tipo == PKG_ITEM_PYZ:
            pyz = pkg.open_embedded_archive(nome)
            for modulo in sorted(pyz.toc):
                bruto = pyz.extract(modulo, raw=True)
                saida["pyz"][modulo] = _sha(bruto) if bruto is not None else ""
    return saida


def comparar(velho: dict, novo: dict) -> list[str]:
    """As linhas do que mudou, uma por entrada; vazio = o `.exe` é o mesmo."""
    linhas = []
    if velho.get("cabecalho") != novo.get("cabecalho"):
        linhas.append("cabecalho (bootloader/recursos PE) mudou")
    for parte in ("pkg", "pyz"):
        a, b = velho.get(parte, {}), novo.get(parte, {})
        for nome in sorted(set(a) | set(b)):
            if nome not in a:
                linhas.append(f"{parte}: + {nome}")
            elif nome not in b:
                linhas.append(f"{parte}: - {nome}")
            elif a[nome] != b[nome]:
                linhas.append(f"{parte}: ~ {nome}")
    return linhas


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("exe", nargs="?", help="o SIG-FT.exe a listar")
    p.add_argument("--comparar", nargs=2, metavar=("VELHO", "NOVO"),
                   help="dois .json desta ferramenta")
    args = p.parse_args(argv)
    if args.comparar:
        with open(args.comparar[0], encoding="utf-8") as a, \
                open(args.comparar[1], encoding="utf-8") as b:
            linhas = comparar(json.load(a), json.load(b))
        print("\n".join(linhas) if linhas else "iguais")
        print(f"({len(linhas)} entrada(s) diferente(s))", file=sys.stderr)
        return 0
    if not args.exe:
        p.error("informe o .exe ou --comparar")
    json.dump(conteudo(args.exe), sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

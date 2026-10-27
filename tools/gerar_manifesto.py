"""Gera o `latest.json` e as notas do Release a partir do instalador pronto.

Por que é um script Python, e não umas linhas de PowerShell no workflow
------------------------------------------------------------------------
Fazer isto direto no YAML tem três armadilhas, todas invisíveis até o build
quebrar — ou, pior, até publicar um manifesto torto:

* **encoding** — o CHANGELOG tem acento. No Windows o Python escreve em cp1252
  por padrão e a saída morre com `UnicodeEncodeError`; e o PowerShell ainda
  releria esse texto com outra tabela, podendo gravar acento trocado no
  manifesto que o app mostra para o usuário;
* **tipo** — a saída de várias linhas do `python` vira um ARRAY no PowerShell,
  e o `ConvertTo-Json` gravaria uma LISTA onde o app espera texto;
* **BOM** — `Set-Content -Encoding utf8` no PowerShell 5 grava BOM, e o
  `json.loads` do app engasga com ele.

Aqui nada disso existe: o mesmo processo lê o CHANGELOG, calcula o hash e grava
os dois arquivos em UTF-8 sem BOM, com os tipos certos. E dá para testar.

Uso (no workflow, depois de o instalador estar pronto):

    python tools/gerar_manifesto.py --instalador installer/Output/Setup.exe \\
        --versao 1.0.0 --tag v1.0.0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _saida_utf8() -> None:
    """Mesma proteção do `preparar_build.py` — ver o docstring de lá."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_saida_utf8()

sys.path.insert(0, str(RAIZ))

from sigft.core.novidades import bloco_de  # noqa: E402 — depende do sys.path acima

# Rodapé fixo das notas do Release. Mora aqui, e não no YAML, porque é texto com
# acento — exatamente o que quebrava no shell do Windows.
COMO_INSTALAR = """
---

### Como instalar

Baixe o `SIG-FT_Itaipu_Setup_*.exe` abaixo e execute. O instalador instala
**só para você** (em AppData), sem pedir senha de administrador, e as
atualizações seguintes rodam sem pedido de permissão do Windows. Quem tinha o
SIG-FT instalado **para todos os usuários** (Program Files) passa para a
instalação só sua: o Windows pede a senha de administrador uma vez, para
remover a cópia antiga. `Documentos\\SIG-FT` (chaves, preferências) não é tocado.

> ### ⚠️ "O Windows protegeu o computador"
>
> Esse aviso vai aparecer, e não é vírus. O SmartScreen reclama de todo programa
> recém-compilado que ainda não tem assinatura digital paga.
>
> Para continuar, clique em **"Mais informações"**. É um link pequeno e cinza,
> logo abaixo do texto, e **só depois dele aparece o botão "Executar assim
> mesmo"** — antes disso a janela só oferece *Não executar*.
>
> Se preferir: botão direito no arquivo, **Propriedades**, marque
> **"Desbloquear"** no rodapé e clique em *Aplicar*.

Quem já tem o SIG-FT **1.1.1 ou mais novo** instalado **não precisa baixar
nada**: ao abrir, o app avisa sozinho e se atualiza com um clique. Quem está na
**1.0.0 ou na 1.1.0** precisa instalar à mão uma vez: aquelas versões não
procuravam atualização.

**Primeiro uso:** quem já usava o SIG-FT não precisa fazer nada — as chaves de
API são importadas sozinhas na primeira abertura. Quem é novo cadastra em
*Configuração de Chaves API*, na tela inicial.

Os módulos que mexem no portal PMIB usam o **Chrome ou o Edge já instalado** na
máquina; o pacote não leva navegador dentro, de propósito.
"""


def sha256(caminho: Path) -> str:
    """Hash do arquivo, lido em blocos (o instalador tem centenas de MB)."""
    digest = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def notas_da_versao(versao: str, changelog: str) -> str:
    """O bloco do CHANGELOG daquela versão, em Markdown."""
    bloco = bloco_de(changelog, versao)
    return bloco.markdown() if bloco else ""


def montar(instalador: Path, versao: str, tag: str, changelog: str,
           hoje: str | None = None) -> dict:
    return {
        "versao": versao,
        "tag": tag,
        "arquivo": instalador.name,
        "sha256": sha256(instalador),
        "tamanho": instalador.stat().st_size,
        "publicado_em": hoje or date.today().isoformat(),
        "notas": notas_da_versao(versao, changelog),
    }


def corpo_do_release(versao: str, notas: str) -> str:
    corpo = notas or "_(esta versao nao trouxe notas no CHANGELOG.md)_"
    return f"## O que mudou na v{versao}\n\n{corpo}\n{COMO_INSTALAR}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instalador", required=True, type=Path)
    ap.add_argument("--versao", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--changelog", type=Path, default=RAIZ / "CHANGELOG.md")
    ap.add_argument("--saida-manifesto", type=Path, default=Path("latest.json"))
    ap.add_argument("--saida-notas", type=Path, default=Path("notas_release.md"))
    args = ap.parse_args()

    if not args.instalador.is_file():
        raise SystemExit(f"Instalador nao encontrado: {args.instalador}")

    changelog = args.changelog.read_text(encoding="utf-8")
    manifesto = montar(args.instalador, args.versao, args.tag, changelog)

    # UTF-8 sem BOM nos dois: é o que o app espera ler de volta.
    args.saida_manifesto.write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")
    args.saida_notas.write_text(
        corpo_do_release(args.versao, manifesto["notas"]), encoding="utf-8")

    # Resumo só em ASCII: este print vai para o log do runner, que no Windows
    # pode estar em cp1252 — não pode ser ele a derrubar o build.
    print(f"manifesto: {args.saida_manifesto}")
    print(f"  versao : {manifesto['versao']} ({manifesto['tag']})")
    print(f"  arquivo: {manifesto['arquivo']}")
    print(f"  sha256 : {manifesto['sha256']}")
    print(f"  tamanho: {manifesto['tamanho']} bytes")
    print(f"  notas  : {len(manifesto['notas'].splitlines())} linha(s)")
    if not manifesto["notas"]:
        print(f"::warning::O CHANGELOG.md nao tem bloco para a versao "
              f"{args.versao} - o Release vai sair SEM notas.")


if __name__ == "__main__":
    main()

"""A atualização só com os arquivos que mudaram, aplicada pelo próprio SIG-FT.

Ver `docs/superpowers/specs/2026-10-27-atualizacao-como-cmi-design.md`. Pedido
do Jonathan (2026-10-27), depois de a atualização pequena da 1.3.1-rc.1 cair
no completo na máquina do Luan: *"copia el mismo método que tiene el cmi suite
para sus actualizaciones"*. Portado do `cmi_suite/core/pacote.py` (e das
regras contra zip-slip do `cmi_suite/core/caminhos.py`).

O mesmo módulo MONTA o pacote (no workflow de Release, via
`tools/gerar_atualizacao.py pacotes`) e o APLICA (na máquina de quem usa). Uma
implementação só do formato: se as duas pontas tivessem cada uma a sua, a
primeira divergência viraria uma instalação quebrada. A DIFERENÇA entre as
versões não mora aqui: é a do `tools/gerar_atualizacao.py` (`diferenca`), a
mesma do instalador pequeno, e chega a `montar` já calculada.

Só stdlib e sem Qt: roda no runner do Release, que chama o script sem o
ambiente do app.

Formato
-------
`arquivos.json` (publicado em todo Release, `tools/gerar_atualizacao.py
manifesto`): a pasta instalada como o instalador completo a deixa -- a
`dist\\SIG-FT\\` inteira e o `CHANGELOG.md` na raiz --, caminhos com `/`:

    {"versao": "1.3.1", "arquivos": {"SIG-FT.exe": {"sha256": ..., "tamanho": ...}, ...}}

`SIG-FT_Itaipu_Arquivos_<de>_para_<para>.zip`:

    manifesto.json                {"de", "para", "alterados": [...], "removidos": [...]}
    arquivos/<caminho relativo>   (cada arquivo novo ou alterado)

O nome não começa com `SIG-FT_Itaipu_Atualizacao_` nem `SIG-FT_Itaipu_Update_`
e não é `.exe`: o app antigo, que escolhe pelo prefixo ou "o primeiro `.exe`",
nunca o pega.

Como aplicar com o programa ABERTO
----------------------------------
O Windows não deixa sobrescrever nem apagar um `.exe` ou uma DLL em uso, mas
deixa RENOMEAR. Então cada arquivo antigo vira `<nome>.sigft-old` e o novo é
escrito no lugar; os removidos também viram `.sigft-old`; os restos são
apagados na abertura seguinte (`limpar_restos`). Se qualquer passo falhar, ou
se a pasta não bater com o `arquivos.json` da versão nova, tudo volta como
estava (`aplicar` desfaz na ordem inversa) e levanta `ErroPacote` -- quem
chama cai para o instalador.

Conferência rápida (2026-10-30)
-------------------------------
`conferir` lê pelo SHA256 só o que o pacote ESCREVEU; o resto da pasta, que
ele não tocou, é conferido pelo TAMANHO. Ler a pasta inteira (centenas de MB,
milhares de arquivos) com o antivírus do Windows abrindo cada um levava
minutos com a barra parada. É o `conferir` do DocManager
(`docmanager/services/pacote.py`), que viu isso na 3.6.0 -> 3.6.1-rc.2. O
tamanho ainda pega a pasta que não é a versão de origem (uma biblioteca de
outra versão quase nunca tem o mesmo tamanho); a entrada sem tamanho (o
formato do CMI) volta ao SHA256.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path, PurePath

__all__ = ["SUFIXO_ANTIGO", "ErroPacote", "nome_pacote", "sha256", "montar",
           "aplicar", "conferir", "limpar_restos"]

SUFIXO_ANTIGO = ".sigft-old"
PREFIXO = "SIG-FT_Itaipu_Arquivos_"
MANIFESTO = "manifesto.json"
PASTA_NO_ZIP = "arquivos/"
_BLOCO = 1024 * 1024


class ErroPacote(RuntimeError):
    """O pacote não serve ou não foi aplicado; a pasta ficou como estava."""


def nome_pacote(de: str, para: str) -> str:
    return f"{PREFIXO}{de}_para_{para}.zip"


def sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as f:
        while bloco := f.read(_BLOCO):
            digest.update(bloco)
    return digest.hexdigest()


def _dentro(base: PurePath, relativo: str) -> Path:
    """`base / relativo`, ou ErroPacote se `relativo` puder sair de `base`.

    Regras do `caminhos.py` do CMI, todas por RECUSA (a revisão de segurança
    dele, de 26/10/2026, achou três nomes que escreviam FORA da pasta no
    Windows: `..\\..\\x.exe`, `C:/Windows/x.dll` e `arquivo.txt:fluxo`): só `/`
    como separador; nada de `\\` nem `:`; nenhuma parte vazia, `.`, `..`, ou
    terminada em ponto ou espaço (o Windows apaga esses finais e `.. ` vira
    `..`)."""
    if (not isinstance(relativo, str) or not relativo or "\\" in relativo
            or ":" in relativo or relativo.startswith("/")):
        raise ErroPacote(f"caminho invalido no pacote: {relativo!r}")
    partes = relativo.split("/")
    for parte in partes:
        if parte in ("", ".", "..") or parte != parte.rstrip(". ") or "\x00" in parte:
            raise ErroPacote(f"caminho invalido no pacote: {relativo!r}")
    return Path(base).joinpath(*partes)


def _tamanho_esperado(info) -> int | None:
    """O `tamanho` da entrada, ou `None` (o formato do CMI não o traz)."""
    if isinstance(info, Mapping) and isinstance(info.get("tamanho"), int):
        return info["tamanho"]
    return None


def _sha_esperado(info) -> str:
    """O `arquivos.json` do SIG-FT traz `{"sha256", "tamanho"}`; o do CMI, o
    SHA puro. Aceita os dois."""
    return info["sha256"] if isinstance(info, Mapping) else str(info)


# --------------------------------------------------------------------------
# Montar (no Release)
# --------------------------------------------------------------------------
def montar(pasta: Path, alterados: Iterable[str], removidos: Iterable[str], de: str, para: str,
           destino: Path, *, extras: Mapping[str, Path] | None = None) -> Path:
    """Grava `destino/<nome_pacote(de, para)>` e devolve o caminho.

    `alterados` e `removidos` são os da `diferenca` do
    `tools/gerar_atualizacao.py` (`Diferenca.copiar` e `.remover`), relativos à
    pasta instalada. Cada alterado sai de `pasta / rel`, a não ser que esteja
    em `extras` (`{"CHANGELOG.md": Path("CHANGELOG.md")}`): é o que o
    instalador completo leva de fora da `dist\\SIG-FT\\`."""
    alterados, removidos = sorted(alterados), sorted(removidos)
    extras = dict(extras or {})
    for rel in alterados + removidos:
        _dentro(Path("."), rel)  # nunca publicar um nome que o app recusaria
    saida = Path(destino) / nome_pacote(de, para)
    saida.unlink(missing_ok=True)
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(MANIFESTO, json.dumps({
            "de": de, "para": para, "alterados": alterados, "removidos": removidos,
        }, ensure_ascii=False, indent=1))
        for rel in alterados:
            origem = extras.get(rel) or _dentro(Path(pasta), rel)
            z.write(origem, PASTA_NO_ZIP + rel)
    return saida


# --------------------------------------------------------------------------
# Aplicar (no app)
# --------------------------------------------------------------------------
def _afastar(caminho: Path, reservados: set | None = None) -> Path:
    """Renomeia o arquivo (em uso ou não) para fora do caminho, e devolve o novo nome.

    Um `.sigft-old` de uma atualização ANTERIOR é apagado para dar lugar; um que
    ESTA rodada criou (`reservados`, comparado sem caixa, como o Windows) nunca:
    ele pode ser a única cópia do original, que o desfazer devolve."""
    reservados = set() if reservados is None else reservados
    alvo = caminho.with_name(caminho.name + SUFIXO_ANTIGO)
    n = 1
    while alvo.exists() or str(alvo).casefold() in reservados:
        if str(alvo).casefold() not in reservados:
            try:
                alvo.unlink()  # resto de uma atualização anterior
                break
            except OSError:  # ainda em uso: escolhe outro nome
                pass
        alvo = caminho.with_name(f"{caminho.name}.{n}{SUFIXO_ANTIGO}")
        n += 1
    caminho.rename(alvo)
    reservados.add(str(alvo).casefold())
    return alvo


def _ler_manifesto(z: zipfile.ZipFile, novo: Mapping) -> dict:
    try:
        info = json.loads(z.read(MANIFESTO))
    except (KeyError, ValueError) as erro:
        raise ErroPacote(f"o pacote nao tem um {MANIFESTO} legivel: {erro}") from erro
    if info.get("para") != novo.get("versao"):
        raise ErroPacote(f"o pacote leva a {info.get('para')}, nao a {novo.get('versao')}")
    for chave in ("alterados", "removidos"):
        if not isinstance(info.get(chave), list):
            raise ErroPacote(f"o {MANIFESTO} do pacote nao tem a lista {chave!r}")
    # [2026-10-27, revisao] Caminhos comparados sem caixa, como o Windows os vê.
    # Dois alterados que são o mesmo arquivo: pacote estragado. Um removido que é
    # um alterado (a troca só de caixa, `PIL/x.pyd` -> `pil/x.pyd`): o arquivo
    # fica, com o conteúdo novo -- removê-lo depois apagaria o que acabou de entrar.
    vistos: set[str] = set()
    for rel in info["alterados"]:
        if str(rel).casefold() in vistos:
            raise ErroPacote(f"o pacote traz duas vezes o mesmo arquivo: {rel!r}")
        vistos.add(str(rel).casefold())
    removidos, ja = [], set()
    for rel in info["removidos"]:
        chave = str(rel).casefold()
        if chave not in vistos and chave not in ja:
            removidos.append(rel)
            ja.add(chave)
    return {**info, "removidos": removidos}


Progresso = Callable[[int, int], None]


def conferir(pasta: Path, novo_manifesto: Mapping, trocados: Iterable[str],
             progresso: Progresso | None = None) -> None:
    """Confere `pasta` contra `novo_manifesto`; ErroPacote no primeiro que não bate.

    Os arquivos que o pacote ESCREVEU (`trocados`, comparados sem caixa, como
    o Windows) vão pelo SHA256; os outros, pelo tamanho -- não foram tocados
    (ver "Conferência rápida" no topo). Entrada sem tamanho volta ao SHA256;
    arquivo que falta falha. `progresso(feitos, total)` a cada arquivo."""
    pasta = Path(pasta)
    trocados = {str(rel).casefold() for rel in trocados}
    versao = novo_manifesto.get("versao")
    itens = list(novo_manifesto["arquivos"].items())
    total = len(itens)
    for feitos, (rel, esperado) in enumerate(itens, 1):
        caminho = _dentro(pasta, rel)
        tamanho = _tamanho_esperado(esperado)
        if not caminho.is_file():
            confere = False
        elif rel.casefold() in trocados or tamanho is None:
            confere = sha256(caminho) == _sha_esperado(esperado)
        else:
            confere = caminho.stat().st_size == tamanho
        if not confere:
            raise ErroPacote(f"{rel} nao confere com a versao {versao}")
        if progresso is not None:
            progresso(feitos, total)


def aplicar(arquivo_zip: Path, pasta: Path, novo_manifesto: Mapping,
            progresso: Progresso | None = None) -> list[str]:
    """Aplica o pacote sobre `pasta` e confere contra `novo_manifesto` (o
    `arquivos.json` da versão nova, já lido), por `conferir` -- que recebe o
    `progresso(feitos, total)`.

    Devolve os caminhos alterados. Em qualquer falha desfaz tudo, na ordem
    inversa, e levanta ErroPacote: a pasta fica como estava (menos os
    `.sigft-old` que não deram para voltar, que `limpar_restos` apaga)."""
    pasta = Path(pasta)
    feitos: list[tuple[Path, Path | None]] = []
    pastas_criadas: list[Path] = []
    reservados: set[str] = set()
    try:
        with zipfile.ZipFile(arquivo_zip) as z:
            info = _ler_manifesto(z, novo_manifesto)
            # Todos os nomes conferidos ANTES de tocar em qualquer arquivo.
            alterados = [(rel, _dentro(pasta, rel)) for rel in info["alterados"]]
            removidos = [(rel, _dentro(pasta, rel)) for rel in info["removidos"]]
            for rel, destino in alterados:
                faltam = [p for p in [destino.parent, *destino.parent.parents]
                          if p != pasta and pasta in p.parents and not p.exists()]
                pastas_criadas.extend(reversed(faltam))  # antes: mkdir pode falhar no meio
                destino.parent.mkdir(parents=True, exist_ok=True)
                antigo = _afastar(destino, reservados) if destino.exists() else None
                feitos.append((destino, antigo))
                with z.open(PASTA_NO_ZIP + rel) as origem, destino.open("wb") as saida:
                    shutil.copyfileobj(origem, saida, _BLOCO)
            for _rel, destino in removidos:
                if destino.is_file():
                    feitos.append((destino, _afastar(destino, reservados)))

        conferir(pasta, novo_manifesto, info["alterados"], progresso)
        return list(info["alterados"])
    except Exception as erro:
        _desfazer(feitos, pastas_criadas)
        if isinstance(erro, ErroPacote):
            raise
        raise ErroPacote(f"atualizacao por arquivos desfeita: {erro}") from erro


def _devolver(antigo: Path, destino: Path) -> None:
    """Põe o original de volta. Se o rename falhar (antivírus segurando o
    `.sigft-old`), COPIA: o `.sigft-old` nunca fica como a única cópia, que o
    `limpar_restos` da próxima abertura apagaria. [2026-10-27, revisao]"""
    try:
        antigo.rename(destino)
    except OSError:
        shutil.copy2(antigo, destino)


def _desfazer(feitos: list[tuple[Path, Path | None]], pastas_criadas: list[Path]) -> None:
    for destino, antigo in reversed(feitos):
        try:
            if destino.exists():
                destino.unlink()
            if antigo is not None:
                _devolver(antigo, destino)
        except OSError:
            continue  # o que der para voltar, volta; o resto o instalador conserta
    for pasta in reversed(pastas_criadas):  # a mais funda primeiro
        try:
            pasta.rmdir()
        except OSError:  # não existe (o mkdir parou antes) ou não está vazia
            continue


def limpar_restos(pasta: Path) -> int:
    """Apaga os `.sigft-old` que a última atualização deixou e devolve quantos.
    O que ainda estiver em uso fica para a próxima abertura. (O desfazer nunca
    deixa um `.sigft-old` como única cópia: ver `_desfazer`.)"""
    apagados = 0
    for resto in Path(pasta).rglob(f"*{SUFIXO_ANTIGO}"):
        try:
            resto.unlink()
            apagados += 1
        except OSError:
            continue
    return apagados

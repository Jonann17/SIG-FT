"""Atualização automática a partir dos Releases do GitHub.

Em uma frase: o app pergunta ao GitHub qual é o último Release, compara com a
versão do próprio binário (`_build_info.VERSAO`) e — se for mais nova — baixa o
instalador, confere o SHA256 e o executa; o app se fecha para que o instalador
possa substituir os arquivos.

═══ Os quatro erros que quebram um auto-update, e o que foi feito de cada ═══

1. **Repositório PRIVADO + `browser_download_url`.** Em repositório privado
   aquela URL só funciona para um **navegador logado**: um `requests.get` nela
   recebe uma página HTML de login, **com status 200**. O download "dá certo" e
   entrega 4 KB de HTML renomeados para `.exe` — que não instala nada e não dá
   erro em lugar nenhum. O jeito certo é o endpoint de API do asset
   (`/releases/assets/{id}`) com `Accept: application/octet-stream` e o token.
   É o que `baixar()` usa, e há a recusa de download pequeno demais como
   segunda linha de defesa.

2. **Zscaler/GlobalProtect.** Sem os certificados do Windows e sem o PAC, todo
   HTTPS falha e o app simplesmente nunca avisa que há versão nova. Tudo aqui
   passa por `core.rede`.

3. **Versão vinda do `.env`.** O `.env` é do usuário e sobrevive à atualização:
   o app novo continuaria se declarando na versão velha e baixaria a mesma
   atualização para sempre. Por isso a versão vem do BUILD (`_build_info.py`),
   e há guard de AST reprovando qualquer leitura de ambiente lá.

4. **Instalar por cima de si mesmo.** O Windows não deixa sobrescrever um
   `.exe` em execução. Por isso o app dispara o instalador e se encerra em
   seguida (`instancia.encerrar`); `/CLOSEAPPLICATIONS` é a rede de
   segurança: o Restart Manager (`CloseApplications=force` no `.iss`) fecha
   o que ainda estiver usando os arquivos. [2026-09-25] O `AppMutex` saiu do
   `.iss`: em modo silencioso ele abortava a instalação, e à mão acusava um
   SIG-FT fantasma (processo sem janela) como "em execução".

═══ E o quinto, que era o maior: ninguém chamava este módulo ═══
Até 2026-09-25 nenhuma linha da interface importava o `updater`. O Release
v1.1.0 saiu, e o `latest.json` dele ficou com ZERO downloads: nenhum app
instalado perguntou. Quem chama agora é `sigft/app_qt/atualizacao.py`, na
abertura da janela principal -- e há teste montando a janela de verdade
(`tests/test_qt_atualizacao.py`) para isso não voltar.

═══ E o sexto: atualizar era reinstalar tudo (2026-10-07) ═══
O instalador completo tem centenas de MB, e entre duas versões quase tudo é
igual. Cada Release traz agora também um instalador PEQUENO por versão de
origem, só com os arquivos que mudaram (`tools/gerar_atualizacao.py`), listado
no `latest.json` (`atualizacoes`). `interpretar_release` escolhe o pequeno
quando o `de` dele é a versão instalada; senão, o completo. O pequeno chega
como `.bin` (o app 1.1.1 baixa "o primeiro `.exe`" e não pode pegá-lo) e vira
`.exe` depois do SHA256. O canal de testes (opção, desligado) faz o app
oferecer também pré-lançamentos. Ver
`docs/superpowers/specs/2026-10-07-atualizacao-incremental-design.md`.

═══ Sobre o token ═══
O repositório é privado, então a consulta exige autenticação. O token é
embutido no build pelo workflow (nunca fica no Git). **Ofuscação não é
segurança**: quem tiver o `.exe` consegue extraí-lo. Por isso ele tem de ser um
PAT *fine-grained*, **somente leitura** (`Contents: Read-only`) e **restrito a
este repositório** — assim o pior caso é alguém conseguir ler o código que essa
pessoa já recebeu. Ver `docs/BUILD.md`, seção "Rotação do token".
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sigft.core import rede

REPO_OWNER = "luanccozer"
REPO_NOME = "SIG-FT"
API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NOME}"

# O manifesto publicado junto do instalador (versão, SHA256 e notas).
ARQUIVO_MANIFESTO = "latest.json"

# [2026-10-07] O canal de testes: ligado, o app oferece também pré-lançamentos.
OPCAO_CANAL_TESTES = "atualizacao.canal_testes"
# Quantos releases o canal de testes olha (os mais recentes primeiro).
RELEASES_NO_CANAL_DE_TESTES = 20

# Um HTML de login tem alguns KB; um instalador do SIG-FT tem centenas de MB.
# O corte é conservador de propósito: ele só precisa separar "página de erro"
# de "binário".
TAMANHO_MINIMO_PLAUSIVEL = 1_000_000

Log = Callable[[str], None]
Progresso = Callable[[float], None]


def _nada(_x) -> None:
    """Log/progresso padrão: silencioso."""


# ─────────────────────────────── versões ────────────────────────────────────

def versao_em_partes(versao: str | None) -> tuple:
    """`v1.10.2-rc.1` -> chave ordenável. Função pura.

    Segue o essencial do SemVer: compara número a número e coloca a pré-versão
    ANTES da versão final (`1.0.0-rc.1` < `1.0.0`). Entrada estranha não
    explode — o que não for número vira 0, porque uma tag digitada errada no
    GitHub não pode derrubar o app de quem está usando.
    """
    texto = str(versao or "").strip().lstrip("vV")
    nucleo, _, pre = texto.partition("-")
    numeros = [int(p) if p.isdigit() else 0 for p in re.split(r"[.+]", nucleo) if p != ""]
    numeros = (numeros + [0, 0, 0])[:3]
    if not pre:
        return (tuple(numeros), (1,))       # sem pré-versão -> vem depois
    partes = tuple((0, int(p), "") if p.isdigit() else (1, 0, p)
                   for p in re.split(r"[.+]", pre) if p != "")
    return (tuple(numeros), (0,) + partes)


def e_mais_nova(remota: str | None, atual: str | None) -> bool:
    """`True` se `remota` for estritamente mais nova que `atual`."""
    try:
        return versao_em_partes(remota) > versao_em_partes(atual)
    except Exception:  # noqa: BLE001 — nunca deixar a comparação derrubar o app
        return False


# ─────────────────────────────── o token ────────────────────────────────────

def caminho_token_externo() -> Path:
    """Arquivo opcional para trocar o token SEM refazer o build.

    Fica na pasta de dados do usuário (`Documentos\\SIG-FT\\`). Útil quando o
    token expira e ninguém quer rodar um release só por isso — ver
    `docs/BUILD.md`.
    """
    from sigft.core.dados_usuario import caminho

    return caminho("update_token.txt")


def token() -> str:
    """O token, nesta ordem: variável de ambiente, arquivo externo, build.

    Devolve `""` quando não há nenhum — que é o caso normal de um build local,
    e significa "este build não procura atualizações".
    """
    if (env := os.getenv("SIGFT_UPDATE_TOKEN", "").strip()):
        return env
    try:
        externo = caminho_token_externo()
        if externo.is_file() and (conteudo := externo.read_text(encoding="utf-8").strip()):
            return conteudo
    except Exception:  # noqa: BLE001
        pass
    try:
        from sigft._ofuscacao import desofuscar
        from sigft._update_auth import TOKEN_OFUSCADO   # gerado pelo CI, fora do Git

        return desofuscar(TOKEN_OFUSCADO) if TOKEN_OFUSCADO else ""
    except Exception:  # noqa: BLE001 — build local não tem o módulo: sem update
        return ""


def _cabecalhos(aceitar: str = "application/vnd.github+json") -> dict:
    h = {"Accept": aceitar, "X-GitHub-Api-Version": "2022-11-28",
         "User-Agent": "SIGFTItaipu"}
    if (tok := token()):
        h["Authorization"] = f"Bearer {tok}"
    return h


# ────────────────────────── o que vem do GitHub ─────────────────────────────

@dataclass(frozen=True)
class Atualizacao:
    """Uma versão nova, pronta para ser mostrada e baixada."""

    versao: str
    notas: str
    nome_arquivo: str
    # Endpoint de API — o ÚNICO que funciona em repositório privado. Ver o
    # item 1 do cabeçalho do módulo.
    url_asset: str
    tamanho: int
    sha256: str             # `""` quando o release não publicou o hash
    url_pagina: str
    publicado_em: str = ""
    # [2026-10-07] O instalador pequeno (só o que mudou desde a versão
    # instalada), e o tamanho do completo, para a janela comparar.
    incremental: bool = False
    tamanho_completo: int = 0
    # Veio pelo canal de testes.
    prerelease: bool = False
    # [2026-10-07] Com o pequeno, o completo do mesmo Release: é nele que o
    # download cai quando o pequeno não chega inteiro (ver `baixar`).
    completo: Atualizacao | None = None
    # [2026-10-16] O pequeno em `.zip`: `sha256` é o do zip, `sha256_dentro` o
    # do instalador que sai dele, e `reserva` o mesmo pequeno em `.bin` -- é
    # nele que o download cai antes de ir ao completo (ver `baixar`).
    sha256_dentro: str = ""
    reserva: Atualizacao | None = None

    @property
    def tamanho_mb(self) -> float:
        return round(self.tamanho / (1024 * 1024), 1) if self.tamanho else 0.0

    @property
    def tamanho_completo_mb(self) -> float:
        return round(self.tamanho_completo / (1024 * 1024), 1) if self.tamanho_completo else 0.0


class SemToken(RuntimeError):
    """Sem token, ou token recusado — checar atualização é impossível."""


class ArquivoInvalido(RuntimeError):
    """O arquivo baixado não pode ser executado (pequeno demais, ou SHA errado)."""


class DownloadInterrompido(RuntimeError):
    """A conexão caiu antes do fim do arquivo. A mensagem diz quanto chegou."""


def _asset(release: dict, nome: str) -> dict | None:
    return next((a for a in release.get("assets", []) if a.get("name") == nome), None)


def _instalador(release: dict) -> dict | None:
    """O asset do instalador: o primeiro `.exe` do release."""
    return next((a for a in release.get("assets", [])
                 if str(a.get("name", "")).lower().endswith(".exe")), None)


def _pacote_pequeno(release: dict, manifesto: dict | None,
                    versao_atual: str | None) -> tuple[dict, dict] | None:
    """O instalador pequeno que serve para `versao_atual`: `(asset, entrada do
    latest.json)`, ou `None`. Só vale com o SHA256 publicado e o arquivo
    presente no Release -- na dúvida, o completo, que serve para todos."""
    atual = str(versao_atual or "").strip().lstrip("vV")
    if not atual or not manifesto:
        return None
    for entrada in manifesto.get("atualizacoes") or []:
        if not isinstance(entrada, dict) or str(entrada.get("de", "")).lstrip("vV") != atual:
            continue
        asset = _asset(release, str(entrada.get("arquivo", "")))
        if asset is not None and str(entrada.get("sha256", "")).strip():
            return asset, entrada
    return None


def _zip_do_pequeno(release: dict, entrada: dict) -> tuple[dict, dict] | None:
    """[2026-10-16] O mesmo pequeno em `.zip` (chave `zip` da entrada do
    `latest.json`): `(asset, dados)`, ou `None` se não veio ou não está no
    Release -- aí fica o `.bin`."""
    dados = entrada.get("zip")
    if not isinstance(dados, dict) or not str(dados.get("sha256", "")).strip():
        return None
    asset = _asset(release, str(dados.get("arquivo", "")))
    return (asset, dados) if asset is not None else None


def interpretar_release(release: dict, manifesto: dict | None = None,
                        versao_atual: str | None = None) -> Atualizacao | None:
    """Monta a `Atualizacao` a partir do JSON do release. Função pura.

    O SHA256 vem, nesta ordem: do `latest.json` publicado junto; senão do campo
    `digest` que a própria API do GitHub devolve; senão fica vazio — e aí o
    download ainda acontece, mas com aviso de que não deu para conferir.

    [2026-10-07] Com `versao_atual`, escolhe o instalador PEQUENO quando o
    `latest.json` traz um feito a partir dela (ver `_pacote_pequeno`).
    """
    asset = _instalador(release)
    if asset is None:
        return None

    sha = ""
    if manifesto:
        sha = str(manifesto.get("sha256", "")).strip().lower()
    if not sha:
        digest = str(asset.get("digest", "") or "")
        if digest.lower().startswith("sha256:"):
            sha = digest.split(":", 1)[1].strip().lower()

    notas = (manifesto or {}).get("notas") or release.get("body") or ""
    comum = dict(
        versao=str(release.get("tag_name", "")).lstrip("vV"),
        notas=str(notas).strip(),
        url_pagina=str(release.get("html_url", "")),
        publicado_em=str(release.get("published_at", "") or "")[:10],
        prerelease=bool(release.get("prerelease")),
    )
    completo = Atualizacao(
        nome_arquivo=str(asset.get("name", "")),
        url_asset=str(asset.get("url", "")),
        tamanho=int(asset.get("size") or 0),
        sha256=sha,
        **comum,
    )
    if (pequeno := _pacote_pequeno(release, manifesto, versao_atual)) is not None:
        asset_pequeno, entrada = pequeno
        bin_ = Atualizacao(
            nome_arquivo=str(asset_pequeno.get("name", "")),
            url_asset=str(asset_pequeno.get("url", "")),
            tamanho=int(asset_pequeno.get("size") or entrada.get("tamanho") or 0),
            sha256=str(entrada["sha256"]).strip().lower(),
            incremental=True,
            tamanho_completo=completo.tamanho,
            completo=completo,
            **comum,
        )
        zipado = _zip_do_pequeno(release, entrada)
        if zipado is None:
            return bin_
        asset_zip, dados_zip = zipado
        return Atualizacao(
            nome_arquivo=str(asset_zip.get("name", "")),
            url_asset=str(asset_zip.get("url", "")),
            tamanho=int(asset_zip.get("size") or dados_zip.get("tamanho") or 0),
            sha256=str(dados_zip["sha256"]).strip().lower(),
            sha256_dentro=bin_.sha256,
            incremental=True,
            tamanho_completo=completo.tamanho,
            completo=completo,
            reserva=bin_,
            **comum,
        )
    return completo


# ─────────────────────────── o canal de testes ──────────────────────────────

def canal_testes_ligado(*, config_path=None) -> bool:
    """`True` se a pessoa pediu para receber também pré-lançamentos. Desligado
    por padrão -- e na dúvida (preferência ilegível), desligado."""
    try:
        from sigft.core import prefs

        return bool(prefs.get_opcao(OPCAO_CANAL_TESTES, False, config_path=config_path))
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return False


def ligar_canal_testes(ligado: bool, *, config_path=None) -> None:
    from sigft.core import prefs

    prefs.set_opcao(OPCAO_CANAL_TESTES, bool(ligado), config_path=config_path)


def _mais_nova(releases) -> dict | None:
    """O release de versão mais alta, pré-lançamento inclusive; rascunho não."""
    validos = [r for r in (releases or []) if isinstance(r, dict) and not r.get("draft")
               and str(r.get("tag_name", "")).strip()]
    return max(validos, key=lambda r: versao_em_partes(r.get("tag_name")), default=None)


def checar(versao_atual: str, *, canal_testes: bool | None = None,
           log_cb: Log = _nada) -> Atualizacao | None:
    """A `Atualizacao` se houver versão mais nova; `None` se já está em dia.

    Levanta `SemToken` (build sem token, ou token recusado) ou
    `rede.FalhaDeRede` (rede/Zscaler). Quem chama decide se mostra o erro ou
    engole — a checagem automática engole, o botão explícito mostra.

    Consulta `/releases/latest`, que **por definição do GitHub ignora
    pré-lançamentos**. É isso que permite publicar um `1.1.0-rc.1` para testar
    sem que ninguém receba. [2026-10-07] Com o canal de testes ligado
    (`canal_testes`; `None` = a preferência salva), consulta `/releases` e fica
    com a versão mais nova, pré-lançamento inclusive.
    """
    if canal_testes is None:
        canal_testes = canal_testes_ligado()
    if not token():
        raise SemToken(
            "Este build nao tem token de atualizacao embutido (build local, ou "
            "segredo ausente no workflow). Baixe a versao nova manualmente pela "
            "pagina de Releases do projeto.")

    log_cb("Procurando atualizacoes...")

    # 401/403/404 são respostas VÁLIDAS do GitHub, não falhas de rota: entram no
    # `status_ok` para virarem mensagem que diz o que fazer, em vez do
    # "nenhuma rota funcionou" genérico — que mandaria a pessoa investigar a
    # rede quando o problema é o token.
    endereco = (f"{API}/releases?per_page={RELEASES_NO_CANAL_DE_TESTES}" if canal_testes
                else f"{API}/releases/latest")
    sessao, resp = rede.abrir(endereco, headers=_cabecalhos(),
                              timeout=20, log_cb=log_cb,
                              status_ok=(200, 401, 403, 404))
    try:
        try:
            if resp.status_code in (401, 403):
                raise SemToken(
                    f"O GitHub recusou o token de atualizacao deste build "
                    f"(HTTP {resp.status_code}). Ele provavelmente expirou ou "
                    f"perdeu o acesso ao repositorio. Baixe a versao nova pela "
                    f"pagina de Releases e avise quem cuida do build.")
            if resp.status_code == 404:
                # Sem release publicado ainda, ou o token não enxerga o
                # repositório: num repo PRIVADO o GitHub responde 404, e não
                # 403, para quem não tem acesso — daí as duas hipóteses.
                log_cb("Nenhum release publicado ainda (ou o token nao tem acesso "
                       "ao repositorio).")
                return None
            release = resp.json()
            if canal_testes:
                release = _mais_nova(release if isinstance(release, list) else [release]) or {}
        finally:
            resp.close()

        versao_remota = str(release.get("tag_name", "")).lstrip("vV")
        if not versao_remota:
            log_cb("O GitHub nao devolveu nenhum release publicado.")
            return None
        if not e_mais_nova(versao_remota, versao_atual):
            log_cb(f"Voce ja esta na versao mais recente (v{versao_atual}).")
            return None

        # O manifesto é opcional: sem ele o SHA256 vem do `digest` da API. A
        # MESMA sessão é reusada de propósito — a rota que funcionou já foi
        # descoberta, e redescobri-la poderia cair numa rota diferente.
        manifesto = None
        if (asset_manifesto := _asset(release, ARQUIVO_MANIFESTO)) is not None:
            try:
                r = sessao.get(asset_manifesto["url"],
                               headers=_cabecalhos("application/octet-stream"),
                               timeout=20)
                if r.status_code == 200:
                    manifesto = json.loads(r.content.decode("utf-8-sig"))  # tolera BOM
                r.close()
            except Exception as e:  # noqa: BLE001 — o manifesto é um extra
                log_cb(f"(nao foi possivel ler o {ARQUIVO_MANIFESTO}: {e})")
    finally:
        sessao.close()

    info = interpretar_release(release, manifesto, versao_atual)
    if info is None:
        log_cb(f"O release v{versao_remota} existe, mas nao tem instalador (.exe) "
               f"publicado. Avise quem cuida do build.")
        return None

    log_cb(f"Nova versao disponivel: v{info.versao} ({info.tamanho_mb} MB"
           + (f", so o que mudou desde a v{versao_atual}" if info.incremental else "")
           + (", versao de teste" if info.prerelease else "") + ").")
    return info


# ──────────────────────────── baixar e instalar ─────────────────────────────

def pasta_download() -> Path:
    p = Path(tempfile.gettempdir()) / "SIG-FT_Update"
    p.mkdir(parents=True, exist_ok=True)
    return p


def baixar(info: Atualizacao, *, progresso_cb: Progresso = _nada,
           log_cb: Log = _nada,
           ao_cair_no_completo: Callable[[Atualizacao], None] = _nada) -> Path:
    """Baixa o instalador e confere o SHA256. Devolve o caminho do arquivo.

    Usa o **endpoint de API do asset**, nunca o `browser_download_url`: em
    repositório privado só ele entrega o binário — ver o item 1 do cabeçalho.

    [2026-10-07] O instalador pequeno é um atalho. Se ele não chega inteiro
    (na rede da empresa, o proxy cortou o fim do da 1.2.0-rc.4, duas vezes)
    ou não confere, baixa o completo do mesmo Release, que serve para qualquer
    versão, e avisa `ao_cair_no_completo`. NÃO remenda o pedaço que faltou: se
    o proxy segurou o fim para analisar o arquivo, pedir só o resto seria
    passar por cima da análise. Erro de disco não troca de arquivo: sem espaço
    para o pequeno, não há para o completo.
    """
    try:
        return _baixar_arquivo(info, progresso_cb=progresso_cb, log_cb=log_cb)
    except (DownloadInterrompido, ArquivoInvalido, rede.FalhaDeRede) as erro:
        if info.reserva is not None:
            # [2026-10-16] O .zip não passou: o mesmo pequeno em .bin, e só
            # depois o completo (a `reserva` traz o `completo` dela).
            log_cb(f"A atualizacao pequena em .zip falhou -- {erro}")
            log_cb("Vai a mesma atualizacao pequena em .bin.")
            progresso_cb(0.0)
            return baixar(info.reserva, progresso_cb=progresso_cb, log_cb=log_cb,
                          ao_cair_no_completo=ao_cair_no_completo)
        if not info.incremental or info.completo is None:
            raise
        log_cb(f"A atualizacao pequena falhou -- {erro}")
        log_cb("Vai o instalador completo, que serve para qualquer versao.")
        ao_cair_no_completo(info.completo)
        progresso_cb(0.0)
        return _baixar_arquivo(info.completo, progresso_cb=progresso_cb, log_cb=log_cb)


def _mb_do_log(n_bytes: int) -> str:
    return f"{n_bytes / (1024 * 1024):.1f}"


def _baixar_arquivo(info: Atualizacao, *, progresso_cb: Progresso,
                    log_cb: Log) -> Path:
    """Um arquivo do Release, conferido. Ver `baixar`."""
    import requests

    nome = info.nome_arquivo
    # O instalador pequeno chega como `.bin` (o app 1.1.1 baixa "o primeiro
    # `.exe` do Release" e não pode pegá-lo); é um instalador como o outro.
    if nome.lower().endswith(".bin"):
        nome = nome[:-len(".bin")] + ".exe"
    destino = pasta_download() / nome
    parcial = destino.with_suffix(destino.suffix + ".part")
    log_cb(f"Baixando {info.nome_arquivo} ({info.tamanho_mb} MB)...")

    sessao, resp = rede.abrir(info.url_asset,
                              headers=_cabecalhos("application/octet-stream"),
                              timeout=60, stream=True, log_cb=log_cb)
    try:
        total = int(resp.headers.get("Content-Length") or info.tamanho or 0)
        baixado = 0
        digest = hashlib.sha256()
        inicio = ultimo_bloco = time.monotonic()
        try:
            with open(parcial, "wb") as f:
                for bloco in resp.iter_content(chunk_size=256 * 1024):
                    if not bloco:
                        continue
                    f.write(bloco)
                    digest.update(bloco)
                    baixado += len(bloco)
                    ultimo_bloco = time.monotonic()
                    if total:
                        progresso_cb(min(baixado / total, 1.0))
        except requests.exceptions.RequestException as erro:
            # O `IncompleteRead` cru não diz nada a quem lê. Os tempos separam
            # um corte seco de um proxy que segurou o fim antes de cortar.
            parcial.unlink(missing_ok=True)
            agora = time.monotonic()
            quanto = (f"chegaram {_mb_do_log(baixado)} de {_mb_do_log(total)} MB "
                      f"(faltaram {total - baixado} bytes)" if total
                      else f"chegaram {_mb_do_log(baixado)} MB")
            raise DownloadInterrompido(
                f"A conexao caiu antes do fim do download: {quanto}, aos "
                f"{agora - inicio:.0f} s, {agora - ultimo_bloco:.0f} s depois do "
                f"ultimo pedaco. Perto do fim, costuma ser o proxy da empresa "
                f"interrompendo o arquivo. Detalhe: {rede.resumo_erro(erro)}") from erro
    finally:
        resp.close()
        sessao.close()

    # A segunda linha de defesa da armadilha nº 4. Um HTML de login tem alguns
    # KB; o instalador tem centenas de MB. Sem esta recusa, o update "dá certo"
    # e o usuário roda uma página de login renomeada para `.exe`.
    tamanho_baixado = parcial.stat().st_size
    if tamanho_baixado < TAMANHO_MINIMO_PLAUSIVEL:
        parcial.unlink(missing_ok=True)
        raise ArquivoInvalido(
            f"O arquivo baixado e pequeno demais para ser o instalador "
            f"({tamanho_baixado} bytes). Isso costuma ser uma pagina de erro no "
            f"lugar do binario -- token de atualizacao invalido ou expirado.")

    obtido = digest.hexdigest()
    if info.sha256:
        if obtido != info.sha256:
            parcial.unlink(missing_ok=True)
            raise ArquivoInvalido(
                f"O instalador baixado nao confere com o publicado.\n"
                f"  esperado: {info.sha256}\n  obtido:   {obtido}\n"
                f"Baixe manualmente pela pagina do Release.")
        log_cb("Integridade conferida (SHA256 confere).")
    else:
        log_cb("[!] O release nao publicou o SHA256 -- nao deu para conferir a "
               "integridade do arquivo.")

    destino.unlink(missing_ok=True)
    parcial.rename(destino)
    if destino.suffix.lower() == ".zip":
        destino = _abrir_zip(destino, info, log_cb=log_cb)
    progresso_cb(1.0)
    log_cb(f"Download concluido: {destino}")
    return destino


def _abrir_zip(zipado: Path, info: Atualizacao, *, log_cb: Log) -> Path:
    """[2026-10-16] Tira o instalador de dentro do `.zip` já conferido e
    confere de novo (`sha256_dentro`). Recusa (`ArquivoInvalido`) zip com mais
    de um arquivo, com pasta no nome ou que não abre; o zip nunca fica para
    trás."""
    import zipfile

    try:
        try:
            with zipfile.ZipFile(zipado) as z:
                membros = [m for m in z.infolist() if not m.is_dir()]
                if len(membros) != 1:
                    raise ArquivoInvalido(
                        f"O .zip da atualizacao deveria ter um arquivo so, e tem {len(membros)}.")
                membro = membros[0]
                nome = membro.filename
                if (Path(nome).name != nome or "\\" in nome or not nome.lower().endswith(".exe")):
                    raise ArquivoInvalido(f"O .zip da atualizacao traz um nome inesperado: {nome!r}.")
                destino = zipado.parent / nome
                parcial = destino.with_suffix(destino.suffix + ".part")
                digest = hashlib.sha256()
                with z.open(membro) as origem, open(parcial, "wb") as saida:
                    for bloco in iter(lambda: origem.read(1024 * 1024), b""):
                        saida.write(bloco)
                        digest.update(bloco)
        except zipfile.BadZipFile as erro:
            raise ArquivoInvalido(f"O .zip da atualizacao nao abre: {erro}") from erro
        if info.sha256_dentro and digest.hexdigest() != info.sha256_dentro:
            parcial.unlink(missing_ok=True)
            raise ArquivoInvalido(
                f"O instalador dentro do .zip nao confere com o publicado.\n"
                f"  esperado: {info.sha256_dentro}\n  obtido:   {digest.hexdigest()}")
        destino.unlink(missing_ok=True)
        parcial.rename(destino)
        log_cb("Instalador tirado do .zip e conferido (SHA256 confere).")
        return destino
    finally:
        zipado.unlink(missing_ok=True)


def empacotado() -> bool:
    """`True` rodando como `.exe` do PyInstaller — fora disso não há o que instalar."""
    return bool(getattr(sys, "frozen", False))


def pasta_instalacao() -> Path | None:
    return Path(sys.executable).parent if empacotado() else None


def precisa_elevacao() -> bool:
    """`True` se a pasta de instalação exigir administrador para ser sobrescrita.

    Testa **escrevendo de verdade**: no Windows, `os.access(..., W_OK)` MENTE
    para `Program Files` — devolve `True` mesmo sem permissão, por causa da
    virtualização de arquivos herdada do XP.
    """
    pasta = pasta_instalacao()
    if pasta is None:
        return False
    try:
        teste = pasta / ".sigft_write_test"
        teste.touch()
        teste.unlink()
        return False
    except Exception:  # noqa: BLE001 — sem permissão, ou pasta somente-leitura
        return True


# Pedido ao instalador para REABRIR o app no fim. Em `/SILENT` a linha do
# `[Run]` que abre o app (`postinstall skipifsilent`) não roda; o `.iss` tem
# uma segunda linha, condicionada a este parâmetro, que reabre o app na conta
# de quem estava usando (`runasoriginaluser`). Os dois lados têm de concordar
# no nome -- há teste lendo o `.iss` (`tests/test_instalador.py`, seção H).
ARG_REABRIR = "/REABRIR=1"

# `/SILENT` mostra só a barra de progresso. `/CLOSEAPPLICATIONS` é a rede de
# segurança: se o app ainda estiver de pé na hora de trocar os arquivos, o
# Restart Manager o fecha. (Até 2026-09-25 havia também
# `/RESTARTAPPLICATIONS`, que dizia reabrir o app -- mas ele só reabre quem se
# registrou com `RegisterApplicationRestart`, e o SIG-FT não se registra.
# Quem reabre é o `ARG_REABRIR`.)
ARGS_INSTALADOR = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                   "/CLOSEAPPLICATIONS", ARG_REABRIR]

# `ERROR_ELEVATION_REQUIRED`: o `CreateProcess` recusa um executável que exige
# administrador no manifesto.
_ERRO_ELEVACAO_NECESSARIA = 740


def instalar(caminho: Path | str, *, log_cb: Log = _nada) -> None:
    """Dispara o instalador e volta -- quem chama deve FECHAR o app em seguida.

    Dois cuidados, e cada um, sozinho, faria "Atualizar agora" fechar o app
    sem atualizar nada (nenhum deles aparecia antes de 2026-09-25 porque esta
    função nunca tinha sido chamada):

    1. **O app pede para ser reaberto** (`ARG_REABRIR`): a linha normal do
       `[Run]` tem `skipifsilent`.
    2. **O instalador sobe SEM elevação**, e o UAC, quando preciso, é pedido
       pelo próprio Inno. Pedir o UAC aqui (`runas`) faria o instalador nascer
       elevado, e aí o `runasoriginaluser` do `.iss` não tem mais as
       credenciais de quem pediu: o app reabriria como administrador -- e, com
       a senha de outra pessoa no UAC, na conta dela, sem as chaves de API.
       O `runas` fica só para o executável que o exigir no manifesto (erro
       740 no `CreateProcess`).

    (Houve um terceiro, soltar o mutex do `AppMutex` antes do disparo: em
    `/SILENT` o Inno que o achava abortava calado. Saiu junto com o próprio
    `AppMutex`, que também travava a instalação manual por causa do SIG-FT
    fantasma -- ver `installer/sigft.iss`.)
    """
    caminho = Path(caminho)
    args = [*ARGS_INSTALADOR, f"/LOG={pasta_download() / 'instalacao.log'}"]

    if precisa_elevacao():
        log_cb("A instalacao vai pedir permissao de administrador (o app esta "
               "instalado para todos os usuarios). Confirme na janela do Windows.")

    try:
        flags = 0
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: o instalador precisa
            # sobreviver ao fechamento do app, que acontece logo em seguida.
            flags = 0x00000008 | 0x00000200
        subprocess.Popen([str(caminho), *args], close_fds=True,  # noqa: S603
                         creationflags=flags)
    except OSError as erro:
        if getattr(erro, "winerror", None) != _ERRO_ELEVACAO_NECESSARIA:
            raise
        _disparar_elevado(caminho, args)

    log_cb("Instalador iniciado. O SIG-FT vai fechar e reabrir atualizado.")


def _disparar_elevado(caminho: Path, args: list[str]) -> None:
    """`ShellExecuteW` com `runas`: o único jeito de um processo pedir o UAC.

    Só para o caso do erro 740 -- ver o item 3 de `instalar`.
    """
    import ctypes

    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", str(caminho), subprocess.list2cmdline(args), None, 1)
    if rc <= 32:   # <=32 é erro em ShellExecute; 5 = o usuário recusou o UAC
        raise RuntimeError(
            f"Nao foi possivel iniciar o instalador com privilegios de "
            f"administrador (codigo {rc}). "
            + ("Voce recusou o pedido do Windows." if rc == 5
               else f"Rode manualmente: {caminho}"))


# ─────────────────── política: quando a abertura pergunta ───────────────────
#
# [2026-09-25] TODA abertura do app instalado pergunta. Até aqui havia um
# intervalo de 6 horas entre consultas, e ele saiu a pedido do usuário: "no
# momento de inicialização ele deve identificar o release". Com o intervalo,
# quem publica um Release e abre o app para conferir só via a versão nova
# horas depois -- para quem olha, igual ao defeito que motivou a mudança. O
# custo de perguntar sempre é uma requisição por abertura, muito abaixo do
# limite de 5000 por hora do token.
#
# A consulta roda numa thread (`sigft/app_qt/atualizacao.py`), então perguntar
# sempre não atrasa a abertura.

def instalado_pelo_instalador() -> bool:
    """`True` se ESTA cópia do app foi instalada pelo instalador do Release.

    O sinal é o desinstalador do Inno (`unins000.exe`) na pasta do `.exe`: o
    `UninstallFilesDir` do Inno tem `{app}` como padrão, e o `.iss` não o muda.
    A pasta do ZIP do Box e a `dist\\` do build não o têm -- e nelas rodar o
    instalador não atualizaria nada: criaria uma SEGUNDA instalação, e a pessoa
    continuaria abrindo a cópia velha.
    """
    pasta = pasta_instalacao()
    if pasta is None:
        return False
    try:
        return any(pasta.glob("unins*.exe"))
    except OSError:
        return False


def motivo_para_nao_verificar() -> str | None:
    """Por que esta cópia NÃO procura atualização; `None` se procura.

    É o que o botão "Atualizações" da Home mostra quando não há o que fazer:
    sem o motivo, "não aconteceu nada" não se distingue de um defeito.
    """
    if not empacotado():
        return ("Este SIG-FT roda pelo codigo-fonte (SIG-FT.bat). Ele se "
                "atualiza pelo git, nao pelo instalador do Release.")
    if not instalado_pelo_instalador():
        return ("Esta copia do SIG-FT nao foi instalada pelo instalador do "
                "Release (veio do ZIP do Box, ou direto da pasta do build). "
                "Ela se atualiza pelo SIG-FT Itaipu.bat.")
    if not token():
        return ("Este build nao tem token de atualizacao embutido (build "
                "local, ou segredo UPDATE_TOKEN ausente no workflow).")
    return None


def deve_verificar() -> bool:
    """`True` se a abertura do app deve perguntar ao GitHub. Ver acima."""
    return motivo_para_nao_verificar() is None

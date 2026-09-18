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
   `.exe` em execução. Por isso o instalador é disparado com
   `/CLOSEAPPLICATIONS` — o Inno acha o app pelo `AppMutex` do `.iss`, que
   `sigft/core/instancia.py` cria ao abrir — e o app se encerra em seguida.

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
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from sigft.core import rede

REPO_OWNER = "luanccozer"
REPO_NOME = "SIG-FT"
API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NOME}"

# O manifesto publicado junto do instalador (versão, SHA256 e notas).
ARQUIVO_MANIFESTO = "latest.json"

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

    @property
    def tamanho_mb(self) -> float:
        return round(self.tamanho / (1024 * 1024), 1) if self.tamanho else 0.0


class SemToken(RuntimeError):
    """Sem token, ou token recusado — checar atualização é impossível."""


class ArquivoInvalido(RuntimeError):
    """O arquivo baixado não pode ser executado (pequeno demais, ou SHA errado)."""


def _asset(release: dict, nome: str) -> dict | None:
    return next((a for a in release.get("assets", []) if a.get("name") == nome), None)


def _instalador(release: dict) -> dict | None:
    """O asset do instalador: o primeiro `.exe` do release."""
    return next((a for a in release.get("assets", [])
                 if str(a.get("name", "")).lower().endswith(".exe")), None)


def interpretar_release(release: dict, manifesto: dict | None = None) -> Atualizacao | None:
    """Monta a `Atualizacao` a partir do JSON do release. Função pura.

    O SHA256 vem, nesta ordem: do `latest.json` publicado junto; senão do campo
    `digest` que a própria API do GitHub devolve; senão fica vazio — e aí o
    download ainda acontece, mas com aviso de que não deu para conferir.
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
    return Atualizacao(
        versao=str(release.get("tag_name", "")).lstrip("vV"),
        notas=str(notas).strip(),
        nome_arquivo=str(asset.get("name", "")),
        url_asset=str(asset.get("url", "")),
        tamanho=int(asset.get("size") or 0),
        sha256=sha,
        url_pagina=str(release.get("html_url", "")),
        publicado_em=str(release.get("published_at", "") or "")[:10],
    )


def checar(versao_atual: str, *, log_cb: Log = _nada) -> Atualizacao | None:
    """A `Atualizacao` se houver versão mais nova; `None` se já está em dia.

    Levanta `SemToken` (build sem token, ou token recusado) ou
    `rede.FalhaDeRede` (rede/Zscaler). Quem chama decide se mostra o erro ou
    engole — a checagem automática engole, o botão explícito mostra.

    Consulta `/releases/latest`, que **por definição do GitHub ignora
    pré-lançamentos**. É isso que permite publicar um `1.1.0-rc.1` para testar
    sem que ninguém receba.
    """
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
    sessao, resp = rede.abrir(f"{API}/releases/latest", headers=_cabecalhos(),
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

    info = interpretar_release(release, manifesto)
    if info is None:
        log_cb(f"O release v{versao_remota} existe, mas nao tem instalador (.exe) "
               f"publicado. Avise quem cuida do build.")
        return None

    log_cb(f"Nova versao disponivel: v{info.versao} ({info.tamanho_mb} MB).")
    return info


# ──────────────────────────── baixar e instalar ─────────────────────────────

def pasta_download() -> Path:
    p = Path(tempfile.gettempdir()) / "SIG-FT_Update"
    p.mkdir(parents=True, exist_ok=True)
    return p


def baixar(info: Atualizacao, *, progresso_cb: Progresso = _nada,
           log_cb: Log = _nada) -> Path:
    """Baixa o instalador e confere o SHA256. Devolve o caminho do arquivo.

    Usa o **endpoint de API do asset**, nunca o `browser_download_url`: em
    repositório privado só ele entrega o binário — ver o item 1 do cabeçalho.
    """
    destino = pasta_download() / info.nome_arquivo
    parcial = destino.with_suffix(destino.suffix + ".part")
    log_cb(f"Baixando {info.nome_arquivo} ({info.tamanho_mb} MB)...")

    sessao, resp = rede.abrir(info.url_asset,
                              headers=_cabecalhos("application/octet-stream"),
                              timeout=60, stream=True, log_cb=log_cb)
    try:
        total = int(resp.headers.get("Content-Length") or info.tamanho or 0)
        baixado = 0
        digest = hashlib.sha256()
        with open(parcial, "wb") as f:
            for bloco in resp.iter_content(chunk_size=256 * 1024):
                if not bloco:
                    continue
                f.write(bloco)
                digest.update(bloco)
                baixado += len(bloco)
                if total:
                    progresso_cb(min(baixado / total, 1.0))
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
    progresso_cb(1.0)
    log_cb(f"Download concluido: {destino}")
    return destino


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


# `/SILENT` mostra só a barra de progresso; `/CLOSEAPPLICATIONS` faz o Inno
# fechar o app pelo `AppMutex`, e `/RESTARTAPPLICATIONS` o reabre atualizado.
ARGS_INSTALADOR = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                   "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]


def instalar(caminho: Path | str, *, log_cb: Log = _nada) -> None:
    """Dispara o instalador e volta — quem chama deve FECHAR o app em seguida.

    Com elevação (instalação em `Program Files`) usa `ShellExecuteW` com o
    verbo `runas`, que é o único jeito de fazer o Windows mostrar o UAC: um
    `subprocess` comum falharia com "acesso negado".
    """
    caminho = Path(caminho)
    args = [*ARGS_INSTALADOR, f"/LOG={pasta_download() / 'instalacao.log'}"]

    if precisa_elevacao():
        log_cb("A instalacao vai pedir permissao de administrador (o app esta em "
               "Program Files). Confirme na janela do Windows.")
        import ctypes

        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", str(caminho), subprocess.list2cmdline(args), None, 1)
        if rc <= 32:   # <=32 é erro em ShellExecute; 5 = o usuário recusou o UAC
            raise RuntimeError(
                f"Nao foi possivel iniciar o instalador com privilegios de "
                f"administrador (codigo {rc}). "
                + ("Voce recusou o pedido do Windows." if rc == 5
                   else f"Rode manualmente: {caminho}"))
    else:
        flags = 0
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: o instalador precisa
            # sobreviver ao fechamento do app, que acontece logo em seguida.
            flags = 0x00000008 | 0x00000200
        subprocess.Popen([str(caminho), *args], close_fds=True,  # noqa: S603
                         creationflags=flags)

    log_cb("Instalador iniciado. O SIG-FT vai fechar e reabrir atualizado.")


# ─────────────────── política: quando checar, o que pular ───────────────────
#
# A checagem automática precisa ser DISCRETA: nunca atrasar a abertura do app,
# nunca insistir numa versão que a pessoa mandou pular, e nunca bater no GitHub
# a cada duplo-clique.

INTERVALO_PADRAO_HORAS = 6


def deve_verificar(*, ultima_verificacao: str | None,
                   ligada: bool = True,
                   intervalo_horas: int = INTERVALO_PADRAO_HORAS) -> bool:
    """`True` se é hora de perguntar ao GitHub (checagem AUTOMÁTICA).

    Desligada, sem token embutido, ou consultada há menos de `intervalo_horas`
    -> `False`. O botão "Procurar atualizações" ignora tudo isto e chama
    `checar()` direto: pedido explícito sempre vale.

    Uma data corrompida devolve `True` — errar para o lado de verificar é bem
    melhor do que travar a verificação para sempre por causa de um arquivo
    estragado.
    """
    if not ligada or not token():
        return False
    if not ultima_verificacao:
        return True
    try:
        ultima = datetime.fromisoformat(str(ultima_verificacao))
    except ValueError:
        return True
    return datetime.now() - ultima >= timedelta(hours=intervalo_horas)


def agora_iso() -> str:
    """O carimbo a guardar depois de uma verificação."""
    return datetime.now().isoformat(timespec="seconds")

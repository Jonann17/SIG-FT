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

═══ E o sexto: atualizar era reinstalar tudo (2026-10-07 a 2026-10-30) ═══
O instalador completo tem centenas de MB, e entre duas versões quase tudo é
igual. De 2026-10-07 a 2026-10-30 cada Release trouxe um instalador Inno
PEQUENO por versão de origem (em `.bin`, `.zip` e `.exe`, por causa do proxy
da empresa). Saiu: era a peça que mais falhava, e o método do DocManager
(abaixo) faz o mesmo sem instalador. O app até a 1.3.0 procura o pequeno no
`latest.json`, não acha e baixa o completo.

═══ E o sétimo: o método do DocManager (2026-10-27; só ele desde 2026-10-30) ═══
Spec: `docs/superpowers/specs/2026-10-27-atualizacao-como-cmi-design.md`.

* **Atualização por arquivos.** Com a pasta do programa gravável (instalação
  "só para mim"), o app nem chama instalador: `aplicar_por_arquivos` baixa o
  `arquivos.json` da versão nova e o `SIG-FT_Itaipu_Arquivos_<de>_para_<para>.zip`
  (chave `arquivos` da entrada do `latest.json`), confere os SHA256, aplica
  com o app aberto (`pacote_arquivos.aplicar`: renomeia, escreve, confere --
  SHA256 no que escreveu, tamanho no resto --, desfaz se falhar), regrava a
  versão no registro e devolve o `.exe` a reabrir (`reabrir`). Qualquer falha
  cai no instalador completo.
* **O instalador avisa que subiu.** `instalar` passa `/SINAL=<arquivo>` e
  espera o `InitializeSetup` do `.iss` criá-lo (até `ESPERA_INSTALADOR_S`);
  se o processo sair antes, `InstaladorNaoIniciou`, e o app fica aberto.
* **Sempre "só para mim".** O instalador é `lowest` sem pergunta, e
  `instalar` passa `/CURRENTUSER`. Quem está em Program Files (pasta sem
  escrita) recebe direto o completo (`checar`): ele instala a cópia da pessoa
  e remove a de Program Files com o desinstalador antigo, elevado.
* **O registro tem de ser desta pasta.** A atualização por arquivos regrava o
  `DisplayVersion` de HKCU; `checar` (no Windows, empacotado) só a oferece
  quando ele já diz a versão que roda -- senão, registro e pasta ficariam em
  versões diferentes, e vai o completo, que acerta os dois.
  `_registrar_versao` só regrava quando o `InstallLocation` é a pasta.

═══ Sobre o token ═══
O repositório é privado, então a consulta exige autenticação. O token é
embutido no build pelo workflow (nunca fica no Git). **Ofuscação não é
segurança**: quem tiver o `.exe` consegue extraí-lo. Por isso ele tem de ser um
PAT *fine-grained*, **somente leitura** (`Contents: Read-only`) e **restrito a
este repositório** — assim o pior caso é alguém conseguir ler o código que essa
pessoa já recebeu. Ver `docs/BUILD.md`, seção "Rotação do token".
"""
from __future__ import annotations

import dataclasses
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
from sigft.services import pacote_arquivos

REPO_OWNER = "luanccozer"
REPO_NOME = "SIG-FT"
API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NOME}"

# O manifesto publicado junto do instalador (versão, SHA256 e notas).
ARQUIVO_MANIFESTO = "latest.json"

# [2026-10-07] O canal de testes: ligado, o app oferece também pré-lançamentos.
OPCAO_CANAL_TESTES = "atualizacao.canal_testes"
# Quantos releases o canal de testes olha (os mais recentes primeiro).
RELEASES_NO_CANAL_DE_TESTES = 20

# [2026-10-27] O manifesto da pasta instalada (cada arquivo com SHA256),
# publicado em todo Release (`tools/gerar_atualizacao.py manifesto`). A
# atualizacao por arquivos confere a pasta contra o da versao NOVA.
ARQUIVOS_DA_VERSAO = "arquivos.json"

# O executavel e o nome do app, como o `installer/sigft.iss` os declara
# (`AppExe`, `AppName`); ha teste lendo o `.iss` (`tests/test_instalador.py`).
EXECUTAVEL = "SIG-FT.exe"
NOME_APP = "SIG-FT Itaipu"
# A chave do desinstalador (`ChaveDesinstalar` no `[Code]` do `.iss`): o Inno
# grava ali `DisplayVersion` (do `AppVersion`) e `DisplayName` (do
# `AppVerName`, "SIG-FT Itaipu <versao>"). A atualizacao por arquivos a
# regrava, e `checar` a confere antes de oferece-la.
CHAVE_DESINSTALAR = ("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
                     "{9F2C4A18-51D7-4E0B-9A3C-5B7E1D6A2C40}_is1")

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
    # Veio pelo canal de testes.
    prerelease: bool = False
    # [2026-10-27] O pacote só com os arquivos (`pacote_arquivos`), que o
    # próprio app aplica, e o `arquivos.json` da versão nova, contra o qual a
    # pasta é conferida depois. Os dois, ou nenhum (ver `_pacote_de_arquivos`).
    # Sem eles, ou se falharem, vai o instalador completo (este objeto).
    arquivos: Atualizacao | None = None
    manifesto_arquivos: Atualizacao | None = None

    @property
    def tamanho_mb(self) -> float:
        return round(self.tamanho / (1024 * 1024), 1) if self.tamanho else 0.0


class SemToken(RuntimeError):
    """Sem token, ou token recusado — checar atualização é impossível."""


class ArquivoInvalido(RuntimeError):
    """O arquivo baixado não pode ser executado (pequeno demais, ou SHA errado)."""


class DownloadInterrompido(RuntimeError):
    """A conexão caiu antes do fim do arquivo. A mensagem diz quanto chegou."""


class InstaladorNaoIniciou(RuntimeError):
    """[2026-10-27] O instalador saiu (ou não respondeu) antes de criar o
    arquivo do `/SINAL`: o app continua aberto. `codigo` é o código de saída
    (`None` no tempo limite) e `log` o `instalacao.log`."""

    def __init__(self, mensagem: str, *, codigo: int | None = None, log: Path | None = None):
        super().__init__(mensagem)
        self.codigo = codigo
        self.log = log


def _asset(release: dict, nome: str) -> dict | None:
    return next((a for a in release.get("assets", []) if a.get("name") == nome), None)


# Como começava o nome do instalador PEQUENO (de 2026-10-07 a 2026-10-30).
# Os Releases daquele tempo, que o canal de testes ainda vê, o trazem em
# `.exe`: ele não pode virar "o instalador", só servia para quem tinha a base.
PREFIXOS_DO_PEQUENO = ("SIG-FT_Itaipu_Atualizacao_", "SIG-FT_Itaipu_Update_")


def _instalador(release: dict) -> dict | None:
    """O asset do instalador completo: o primeiro `.exe` do release que não é
    um instalador pequeno (Releases até a 1.3.1) -- este só servia para quem
    tinha a base dele."""
    return next((a for a in release.get("assets", [])
                 if str(a.get("name", "")).lower().endswith(".exe")
                 and not str(a.get("name", "")).startswith(PREFIXOS_DO_PEQUENO)), None)


def _entrada_da_versao(manifesto: dict | None, versao_atual: str | None) -> dict | None:
    """[2026-10-27] A entrada de `atualizacoes` do `latest.json` feita a partir
    de `versao_atual`, ou `None`."""
    atual = str(versao_atual or "").strip().lstrip("vV")
    if not atual or not manifesto:
        return None
    return next((e for e in manifesto.get("atualizacoes") or []
                 if isinstance(e, dict) and str(e.get("de", "")).lstrip("vV") == atual), None)


def _sub_entrada(release: dict, entrada: dict, chave: str) -> tuple[dict, dict] | None:
    """`(asset, dados)` da chave `chave` da entrada do `latest.json` (hoje só
    `arquivos`), ou `None` se não veio, não tem SHA256 ou não está no Release."""
    dados = entrada.get(chave)
    if not isinstance(dados, dict) or not str(dados.get("sha256", "")).strip():
        return None
    asset = _asset(release, str(dados.get("arquivo", "")))
    return (asset, dados) if asset is not None else None


def _digest_sha256(asset: dict) -> str:
    digest = str(asset.get("digest", "") or "")
    return digest.split(":", 1)[1].strip().lower() if digest.lower().startswith("sha256:") else ""


def _pacote_de_arquivos(release: dict, entrada: dict,
                        comum: dict) -> tuple[Atualizacao, Atualizacao] | None:
    """[2026-10-27] `(zip de arquivos, arquivos.json)` da entrada do
    `latest.json`, ou `None`. Só com os dois assets no Release e o SHA256 do
    zip publicado: sem ele, aplicar seria confiar num arquivo não conferido.
    O SHA256 do `arquivos.json` vem do `digest` da API (vazio se não vier)."""
    if (outro := _sub_entrada(release, entrada, "arquivos")) is None:
        return None
    asset_json = _asset(release, ARQUIVOS_DA_VERSAO)
    if asset_json is None:
        return None
    asset_zip, dados = outro
    zipado = Atualizacao(
        nome_arquivo=str(asset_zip.get("name", "")), url_asset=str(asset_zip.get("url", "")),
        tamanho=int(asset_zip.get("size") or dados.get("tamanho") or 0),
        sha256=str(dados["sha256"]).strip().lower(), **comum)
    manifesto = Atualizacao(
        nome_arquivo=ARQUIVOS_DA_VERSAO, url_asset=str(asset_json.get("url", "")),
        tamanho=int(asset_json.get("size") or 0), sha256=_digest_sha256(asset_json), **comum)
    return zipado, manifesto


def interpretar_release(release: dict, manifesto: dict | None = None,
                        versao_atual: str | None = None) -> Atualizacao | None:
    """Monta a `Atualizacao` a partir do JSON do release. Função pura.

    O SHA256 vem, nesta ordem: do `latest.json` publicado junto; senão do campo
    `digest` que a própria API do GitHub devolve; senão fica vazio — e aí o
    download ainda acontece, mas com aviso de que não deu para conferir.

    [2026-10-27] Com `versao_atual`, anexa o pacote de arquivos quando o
    `latest.json` traz um feito a partir dela (ver `_pacote_de_arquivos`).
    """
    asset = _instalador(release)
    if asset is None:
        return None

    sha = ""
    if manifesto:
        sha = str(manifesto.get("sha256", "")).strip().lower()
    if not sha:
        sha = _digest_sha256(asset)

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
    if ((entrada := _entrada_da_versao(manifesto, versao_atual)) is not None
            and (por_arquivos := _pacote_de_arquivos(release, entrada, comum)) is not None):
        return dataclasses.replace(completo, arquivos=por_arquivos[0],
                                   manifesto_arquivos=por_arquivos[1])
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
           log_cb: Log = _nada,
           ler_registro: Callable[[str], str | None] | None = None) -> Atualizacao | None:
    """A `Atualizacao` se houver versão mais nova; `None` se já está em dia.

    Levanta `SemToken` (build sem token, ou token recusado) ou
    `rede.FalhaDeRede` (rede/Zscaler). Quem chama decide se mostra o erro ou
    engole — a checagem automática engole, o botão explícito mostra.

    Consulta `/releases/latest`, que **por definição do GitHub ignora
    pré-lançamentos**. É isso que permite publicar um `1.1.0-rc.1` para testar
    sem que ninguém receba. [2026-10-07] Com o canal de testes ligado
    (`canal_testes`; `None` = a preferência salva), consulta `/releases` e fica
    com a versão mais nova, pré-lançamento inclusive.

    [2026-10-27] `ler_registro` (costura do teste; padrão
    `_ler_registro_usuario`) lê a chave do desinstalador em HKCU: ver o
    comentário do `DisplayVersion` abaixo.
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

    # [2026-10-27] Pasta do programa sem escrita = a instalação antiga "para
    # todos" (Program Files): os arquivos nem dá para gravar. Vai o completo,
    # que instala só para a pessoa e remove a cópia de Program Files
    # (`MigrarDaInstalacaoParaTodos`).
    para_todos = precisa_elevacao()
    so_completo = para_todos
    if para_todos:
        log_cb("SIG-FT instalado para todos os usuarios: vai o instalador completo, que o "
               "passa para a instalacao so sua.")
    elif _no_windows() and empacotado():
        # [2026-10-27, I2] A atualizacao por arquivos regrava `DisplayVersion`
        # em HKCU. Se ele nao diz a versao que roda (duas copias, registro de
        # outra pasta, ou nenhum), registro e pasta ficariam em versoes
        # diferentes: vai so o completo, que acerta os dois.
        registrada = (ler_registro or _ler_registro_usuario)("DisplayVersion")
        if str(registrada or "").strip().lstrip("vV") != str(versao_atual).strip().lstrip("vV"):
            so_completo = True
            log_cb(f"O registro do Windows (HKCU) diz versao {registrada or '(nenhuma)'}, e o "
                   f"SIG-FT aberto e a v{versao_atual}: vai so o instalador completo.")
    info = interpretar_release(release, manifesto, None if so_completo else versao_atual)
    if info is None:
        log_cb(f"O release v{versao_remota} existe, mas nao tem instalador (.exe) "
               f"publicado. Avise quem cuida do build.")
        return None

    log_cb(f"Nova versao disponivel: v{info.versao} (instalador completo: {info.tamanho_mb} MB"
           + (f"; so os arquivos que mudaram desde a v{versao_atual}: {info.arquivos.tamanho_mb} MB"
              if info.arquivos is not None else "")
           + (", versao de teste" if info.prerelease else "") + ").")
    return info


# ──────────────────────────── baixar e instalar ─────────────────────────────

def _pasta_de_download() -> Path:
    return Path(tempfile.gettempdir()) / "SIG-FT_Update"


def pasta_download() -> Path:
    p = _pasta_de_download()
    p.mkdir(parents=True, exist_ok=True)
    return p


# O que a limpeza apaga: instaladores e downloads pela metade. O
# `instalacao.log` fica -- é o diagnóstico da última instalação.
_EXTENSOES_DE_DOWNLOAD = (".exe", ".bin", ".zip", ".part")


def limpar_downloads(*, log_cb: Log = _nada) -> int:
    """Apaga os instaladores que atualizações anteriores deixaram na pasta de
    download. Devolve quantos bytes liberou.

    [2026-10-19] Cada atualização deixava o instalador lá (326 MB o completo),
    versão após versão. Arquivo em uso (o instalador que acabou de reabrir o
    app ainda pode estar rodando) fica para a próxima vez, sem erro."""
    pasta = _pasta_de_download()
    if not pasta.is_dir():
        return 0
    apagados, liberados = 0, 0
    for arquivo in pasta.iterdir():
        if not arquivo.is_file() or not arquivo.name.lower().endswith(_EXTENSOES_DE_DOWNLOAD):
            continue
        try:
            tamanho = arquivo.stat().st_size
            arquivo.unlink()
        except OSError:
            continue
        apagados += 1
        liberados += tamanho
    if apagados:
        log_cb(f"Limpeza: {apagados} arquivo(s) de atualizacoes anteriores apagados "
               f"({_mb_do_log(liberados)} MB liberados).")
    return liberados


def baixar(info: Atualizacao, *, progresso_cb: Progresso = _nada,
           log_cb: Log = _nada) -> Path:
    """Baixa o instalador completo e confere o SHA256. Devolve o caminho do
    arquivo.

    Usa o **endpoint de API do asset**, nunca o `browser_download_url`: em
    repositório privado só ele entrega o binário — ver o item 1 do cabeçalho.
    [2026-10-19] Antes de baixar, apaga os instaladores de atualizações
    anteriores (`limpar_downloads`).
    """
    limpar_downloads(log_cb=log_cb)
    return _baixar_arquivo(info, progresso_cb=progresso_cb, log_cb=log_cb)


def _mb_do_log(n_bytes: int) -> str:
    return f"{n_bytes / (1024 * 1024):.1f}"


def _baixar_arquivo(info: Atualizacao, *, progresso_cb: Progresso, log_cb: Log,
                    minimo: int = TAMANHO_MINIMO_PLAUSIVEL) -> Path:
    """Um arquivo do Release, conferido. Ver `baixar`.

    [2026-10-27] A atualização por arquivos usa este mesmo download (uma
    implementação só) com `minimo=0`: o `arquivos.json` e o zip de arquivos
    podem ter poucos KB (o SHA256 é quem separa a página de login)."""
    import requests

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
    if tamanho_baixado < minimo:
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
                f"O arquivo baixado ({info.nome_arquivo}) nao confere com o publicado.\n"
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


def _gravavel(pasta: Path) -> bool:
    """Testa **escrevendo de verdade**: no Windows, `os.access(..., W_OK)` MENTE
    para `Program Files` — devolve `True` mesmo sem permissão, por causa da
    virtualização de arquivos herdada do XP."""
    try:
        teste = pasta / ".sigft_write_test"
        teste.touch()
        teste.unlink()
        return True
    except Exception:  # noqa: BLE001 — sem permissão, ou pasta somente-leitura
        return False


def precisa_elevacao() -> bool:
    """`True` se a pasta de instalação exigir administrador para ser sobrescrita."""
    pasta = pasta_instalacao()
    if pasta is None:
        return False
    return not _gravavel(pasta)


# ─────────────────── a atualização por arquivos [2026-10-27] ────────────────

def pode_por_arquivos(info: Atualizacao) -> bool:
    """`True` se esta atualização pode ser aplicada pelo próprio app: há o
    pacote de arquivos, o app está empacotado e a pasta do programa aceita
    escrita de verdade (instalação "só para mim", em `AppData\\Local\\Programs`).
    Program Files fica com o instalador, que pede o UAC."""
    if info.arquivos is None or info.manifesto_arquivos is None or not empacotado():
        return False
    pasta = pasta_instalacao()
    return pasta is not None and _gravavel(pasta)


def _sem_aviso() -> None:
    """`ao_conferir` padrão: silencioso."""


def aplicar_por_arquivos(info: Atualizacao, *, progresso_cb: Progresso = _nada,
                         log_cb: Log = _nada,
                         ao_conferir: Callable[[], None] = _sem_aviso) -> Path:
    """Baixa o `arquivos.json` da versão nova e o zip de arquivos, confere os
    SHA256, aplica com o app ABERTO (`pacote_arquivos.aplicar`), regrava a
    versão no registro e devolve o `.exe` a reabrir.

    A barra (`progresso_cb`) serve primeiro ao download do zip e depois à
    conferência da pasta, que recomeça do zero; `ao_conferir()` avisa quando a
    conferência começa (a janela troca o status). Ver
    `_progresso_da_conferencia`.

    Levanta `ErroPacote`, `ArquivoInvalido`, `DownloadInterrompido` ou
    `rede.FalhaDeRede`; em qualquer caso a pasta fica como estava, e quem
    chama cai no instalador completo (`baixar` + `instalar`)."""
    pasta = pasta_instalacao()
    if pasta is None or info.arquivos is None or info.manifesto_arquivos is None:
        raise pacote_arquivos.ErroPacote("atualizacao por arquivos indisponivel")
    log_cb(f"Atualizacao por arquivos: v{info.versao} sobre {pasta}.")

    # O `arquivos.json` primeiro: sem ele nao ha como conferir a pasta depois,
    # e nao vale baixar o zip.
    caminho_json = _baixar_arquivo(info.manifesto_arquivos, progresso_cb=_nada, log_cb=log_cb,
                                   minimo=0)
    try:
        try:
            novo = json.loads(caminho_json.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as erro:
            raise pacote_arquivos.ErroPacote(
                f"o {ARQUIVOS_DA_VERSAO} da v{info.versao} nao e legivel: {erro}") from erro
    finally:
        caminho_json.unlink(missing_ok=True)
    if (not isinstance(novo, dict) or not isinstance(novo.get("arquivos"), dict)
            or str(novo.get("versao", "")).lstrip("vV") != info.versao):
        raise pacote_arquivos.ErroPacote(
            f"o {ARQUIVOS_DA_VERSAO} baixado nao e o da v{info.versao}")

    zipado = _baixar_arquivo(info.arquivos, progresso_cb=progresso_cb, log_cb=log_cb,
                             minimo=0)
    try:
        log_cb("Aplicando os arquivos com o SIG-FT aberto...")
        progresso_cb(0.0)
        alterados = pacote_arquivos.aplicar(
            zipado, pasta, novo,
            progresso=_progresso_da_conferencia(progresso_cb, log_cb, ao_conferir))
    finally:
        zipado.unlink(missing_ok=True)
    log_cb(f"Atualizacao por arquivos aplicada: {len(alterados)} arquivo(s) trocado(s), "
           f"pasta conferida contra o {ARQUIVOS_DA_VERSAO} da v{info.versao}.")
    _registrar_versao(info.versao, pasta, log_cb=log_cb)
    progresso_cb(1.0)
    return pasta / EXECUTAVEL


def _progresso_da_conferencia(progresso_cb: Progresso, log_cb: Log,
                              ao_conferir: Callable[[], None]) -> Callable[[int, int], None]:
    """`progresso(feitos, total)` para o `pacote_arquivos.aplicar`, como o do
    DocManager (`docmanager/services/updater.py`): a barra só muda quando o
    percentual muda -- milhares de avisos entupiriam a fila da interface. Aqui
    o log ganha UMA linha, no começo, e não uma por percentual; e
    `ao_conferir()` é chamado uma vez, no primeiro arquivo."""
    ultimo = [-1]

    def progresso(feitos: int, total: int) -> None:
        if ultimo[0] < 0:
            ao_conferir()
            log_cb(f"Conferindo os {total} arquivos instalados (SHA256 nos trocados, "
                   "tamanho nos outros)...")
        pct = int(feitos * 100 / total) if total else 100
        if pct == ultimo[0]:
            return
        ultimo[0] = pct
        progresso_cb(pct / 100)

    return progresso


def _no_windows() -> bool:
    return sys.platform == "win32"


def _ler_registro_usuario(nome: str) -> str | None:
    """Um valor da chave do desinstalador em HKCU (`CHAVE_DESINSTALAR`), ou
    `None` (fora do Windows, chave ou valor ausente, erro). Nunca levanta."""
    if not _no_windows():
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_DESINSTALAR, 0,
                            winreg.KEY_READ) as chave:
            valor, _tipo = winreg.QueryValueEx(chave, nome)
    except OSError:
        return None
    return str(valor) if valor not in (None, "") else None


def _pasta_normalizada(pasta: Path | str) -> str:
    """Para comparar pastas do Windows: sem aspas, `/` vira `\\`, sem a barra
    do fim, sem diferença de caixa."""
    texto = os.path.normpath(str(pasta).strip().strip('"')).replace("/", "\\")
    return texto.rstrip("\\").casefold()


def _registrar_versao(versao: str, pasta: Path | str, *, log_cb: Log = _nada,
                      ler: Callable[[str], str | None] | None = None) -> None:
    """Regrava `DisplayVersion` e `DisplayName` do desinstalador, como o Inno
    faria (só a instalação por usuário, HKCU). Melhor esforço, como o
    `_registrar_versao` do CMI Suite: o app se guia pelo `_build_info`, mas o
    instalador PEQUENO seguinte confere a versão instalada AQUI
    (`PrepareToInstall` no `.iss`) -- sem regravar, ele recusaria a próxima.

    [2026-10-27, I2] Só quando a chave de HKCU é DESTA pasta: o
    `InstallLocation` (ou o `Inno Setup: App Path`, que o Inno também grava)
    tem de ser `pasta`. Com duas cópias (Program Files e a do usuário),
    regravar às cegas daria a versão de uma à outra. O resultado (regravado,
    não regravado e por quê, ou falhou) vai para `log_cb`. `ler` é a costura
    do teste (padrão `_ler_registro_usuario`)."""
    if not _no_windows():
        return
    ler = ler or _ler_registro_usuario
    registrada = ler("InstallLocation") or ler("Inno Setup: App Path")
    if not registrada:
        log_cb("DisplayVersion nao regravado: a chave do SIG-FT em HKCU nao tem InstallLocation "
               "(instalacao para todos, ou sem registro).")
        return
    if _pasta_normalizada(registrada) != _pasta_normalizada(pasta):
        log_cb(f"DisplayVersion nao regravado: HKCU aponta para outra pasta ({registrada}); "
               f"a atualizada e {pasta}.")
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_DESINSTALAR, 0,
                            winreg.KEY_SET_VALUE) as chave:
            winreg.SetValueEx(chave, "DisplayVersion", 0, winreg.REG_SZ, versao)
            winreg.SetValueEx(chave, "DisplayName", 0, winreg.REG_SZ, f"{NOME_APP} {versao}")
    except OSError as erro:
        log_cb(f"Regravar DisplayVersion em HKCU falhou: {erro}")
        return
    log_cb(f"DisplayVersion regravado em HKCU: v{versao}.")


def _flags_desacoplado() -> int:
    """DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: o processo sobrevive ao
    fechamento do app, que acontece logo em seguida."""
    return 0x00000008 | 0x00000200 if os.name == "nt" else 0


def reabrir(exe: Path | str) -> None:
    """Abre o `.exe` novo num processo desacoplado (depois da atualização por
    arquivos); quem chama fecha o app em seguida."""
    exe = Path(exe)
    subprocess.Popen([str(exe)], close_fds=True, cwd=str(exe.parent),  # noqa: S603
                     creationflags=_flags_desacoplado())


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

# [2026-10-27] O escopo, explícito como no CMI Suite (`instalador.py`), mas
# só um: o SIG-FT agora se instala sempre por usuário. Quem estava em Program
# Files é migrado pelo próprio instalador completo (`installer/sigft.iss`,
# `MigrarDaInstalacaoParaTodos`): instala a cópia da pessoa e roda elevado o
# desinstalador antigo. Fora do `.exe` não há escopo a passar.
ESCOPO_INSTALADOR = "/CURRENTUSER"

# [2026-10-27] O `/SINAL=<arquivo>`: o `InitializeSetup` do `.iss` cria o
# arquivo logo ao subir, e só então o app fecha (ver `instalar`). O nome do
# parâmetro tem de bater com o do `.iss` (`tests/test_instalador.py`).
PARAM_SINAL = "SINAL"
ARQUIVO_SINAL = "instalador_pronto.txt"
ARQUIVO_LOG_INSTALACAO = "instalacao.log"
# Cobre alguém lendo e confirmando o pedido de administrador.
ESPERA_INSTALADOR_S = 10 * 60
_INTERVALO_SINAL_S = 0.2

# `ERROR_ELEVATION_REQUIRED`: o `CreateProcess` recusa um executável que exige
# administrador no manifesto.
_ERRO_ELEVACAO_NECESSARIA = 740


def caminho_log_instalacao() -> Path:
    """O `/LOG=` que `instalar` passa ao instalador (sem criar a pasta): o
    diário o cita na linha `ATUALIZACAO` (2026-10-27)."""
    return _pasta_de_download() / ARQUIVO_LOG_INSTALACAO


def instalar(caminho: Path | str, *, log_cb: Log = _nada,
             dormir: Callable[[float], None] = time.sleep,
             relogio: Callable[[], float] = time.monotonic,
             espera_s: float = ESPERA_INSTALADOR_S) -> None:
    """Dispara o instalador, ESPERA ele subir e volta -- quem chama deve
    FECHAR o app em seguida.

    [2026-10-27] "Subiu" é o instalador criar o arquivo do `/SINAL` (o
    `InitializeSetup` do `.iss`, como no CMI Suite e no DocManager). Se o
    processo sair antes (antivírus, política da empresa, UAC recusado) ou
    `espera_s` passar, levanta `InstaladorNaoIniciou`, e o app continua
    aberto dizendo por quê -- em vez de fechar sem atualizar nada. No disparo
    elevado (`_disparar_elevado`, `ShellExecute`) não há o processo para
    perguntar se ele saiu: ali só o sinal e o tempo limite contam.

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
       740 no `CreateProcess`). [2026-10-27] Com o instalador sempre por
       usuário (`ESCOPO_INSTALADOR`), o único UAC da corrente é o do
       desinstalador antigo de Program Files, que o próprio `.iss` pede no
       fim (migração) -- o instalador e o app reaberto ficam na conta de quem
       usa.

    (Houve um terceiro, soltar o mutex do `AppMutex` antes do disparo: em
    `/SILENT` o Inno que o achava abortava calado. Saiu junto com o próprio
    `AppMutex`, que também travava a instalação manual por causa do SIG-FT
    fantasma -- ver `installer/sigft.iss`.)
    """
    caminho = Path(caminho)
    pasta = pasta_download()
    log = pasta / ARQUIVO_LOG_INSTALACAO   # = caminho_log_instalacao()
    sinal = pasta / ARQUIVO_SINAL
    sinal.unlink(missing_ok=True)   # o de uma atualização anterior não conta
    args = [*ARGS_INSTALADOR, f"/LOG={log}", f"/{PARAM_SINAL}={sinal}"]
    if empacotado():
        # [2026-10-27] Sempre só para a pessoa (o `.iss` é `lowest`, e o
        # explícito vale mesmo se alguém compilar com outro padrão).
        args.append(ESCOPO_INSTALADOR)

    if precisa_elevacao():
        log_cb("O SIG-FT esta instalado para todos os usuarios: a versao nova vai para a "
               "instalacao so sua, e o Windows pede a senha de administrador uma vez, para "
               "remover a copia antiga. Recusado, a versao nova funciona do mesmo jeito.")

    log_cb(f"Disparando o instalador {caminho.name} (sinal em {sinal}).")
    processo = None
    try:
        # O instalador precisa sobreviver ao fechamento do app.
        processo = subprocess.Popen([str(caminho), *args], close_fds=True,  # noqa: S603
                                    creationflags=_flags_desacoplado())
    except OSError as erro:
        if getattr(erro, "winerror", None) != _ERRO_ELEVACAO_NECESSARIA:
            raise
        log_cb("O Windows exigiu elevacao no disparo: pedindo o UAC (sem o processo, "
               "a espera e so pelo sinal).")
        _disparar_elevado(caminho, args)

    _esperar_sinal(sinal, processo, caminho=caminho, log=log, log_cb=log_cb,
                   dormir=dormir, relogio=relogio, espera_s=espera_s)
    log_cb("Instalador iniciado. O SIG-FT vai fechar e reabrir atualizado.")


def _esperar_sinal(sinal: Path, processo, *, caminho: Path, log: Path, log_cb: Log,
                   dormir: Callable[[float], None], relogio: Callable[[], float],
                   espera_s: float) -> None:
    """Até o arquivo do `/SINAL` existir. `processo=None` (disparo elevado):
    só o tempo limite. Ver `instalar`."""
    inicio = relogio()
    while not sinal.exists():
        if processo is not None and (codigo := processo.poll()) is not None:
            log_cb(f"O instalador saiu antes de ficar pronto (codigo {codigo}).")
            raise InstaladorNaoIniciou(
                f"O instalador terminou antes de comecar (codigo {codigo}). Detalhes em "
                f"{log}. Tambem da para rodar a mao: {caminho}", codigo=codigo, log=log)
        if relogio() - inicio >= espera_s:
            log_cb(f"O instalador nao respondeu em {espera_s:.0f} s.")
            raise InstaladorNaoIniciou(
                f"O instalador nao respondeu a tempo ({espera_s / 60:.0f} min). Se o Windows "
                f"pediu permissao, confirme-a e tente de novo. Detalhes em {log}.", log=log)
        dormir(_INTERVALO_SINAL_S)
    log_cb("O instalador avisou que subiu (sinal recebido).")


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

"""Acesso HTTP que sobrevive à rede da empresa (Zscaler + GlobalProtect).

O problema, e por que este módulo existe
----------------------------------------
Na máquina da CMI, com a VPN ligada, **toda chamada HTTPS do Python falha com
timeout** — a busca de datasheets do AutoSpec, o Gemini, o OpenRouter, o
catálogo de modelos. A pessoa é obrigada a desligar a VPN para trabalhar.

A causa, confirmada no registro do Windows:

    ProxyEnable     REG_DWORD  0x0
    AutoConfigURL   REG_SZ     http://127.0.0.1:9999/4049_gpproxy.pac

**Não existe proxy estático.** Existe só um arquivo **PAC**, servido pelo
próprio agente do GlobalProtect. E o `urllib.request.getproxies()` do Python lê
somente `ProxyEnable`/`ProxyServer`: com `ProxyEnable=0` ele conclui "sem
proxy", o app sai direto, e a VPN descarta os pacotes em silêncio — 20 segundos
de timeout, sem pista nenhuma no log. O navegador funciona porque navegador
executa PAC.

Um PAC é um programa JavaScript (`FindProxyForURL(url, host)`), e a resposta
**muda por destino** — num PAC de VPN, muda também conforme o túnel esteja de
pé (proxy local em `127.0.0.1`) ou não (gateway do Zscaler). Interpretar isso
em Python exigiria embutir um motor de JavaScript. A saída limpa é perguntar ao
**Windows**, que já faz isso o dia inteiro para o navegador.

As três camadas, na ordem em que são tentadas
---------------------------------------------
1. `truststore` injeta os certificados do **Windows** (inclusive a raiz do
   Zscaler, que a TI já instalou lá) na verificação SSL do Python;
2. **cascata de rotas** — proxy do PAC, proxy do sistema, variáveis de
   ambiente, conexão direta — porque qual delas funciona muda com a VPN ligada
   ou desligada;
3. só se TODAS falharem **por certificado**, uma última tentativa sem verificar
   o TLS, com aviso explícito no log. Nunca antes: quem já funciona não é
   rebaixado.

Relação com o `pip-system-certs` do `requirements.txt`
------------------------------------------------------
Ele resolve **metade** do problema — a do certificado — fazendo o Python usar o
repositório de certificados do Windows. A outra metade, a do PAC, ele não toca:
descobrir *por onde sair* não é a mesma pergunta que *em quem confiar*. Era
exatamente a metade que faltava.
"""
from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
from typing import Callable, Iterable

Log = Callable[[str], None]


def _nada(_msg: str) -> None:
    """Log padrão: silencioso."""


class FalhaDeRede(RuntimeError):
    """Nenhuma rota chegou ao destino. A mensagem traz o diagnóstico de cada uma."""


# ────────────────────────── certificados do Windows ─────────────────────────

def injetar_certificados_windows(log_cb: Log = _nada) -> bool:
    """Passa a validar TLS pela loja de certificados do Windows.

    Idempotente: chamar várias vezes não faz mal. Devolve `False` (com aviso no
    log) se o `truststore` não estiver disponível — aí a cascata ainda pode
    salvar, então não é motivo para parar.
    """
    try:
        import truststore

        truststore.inject_into_ssl()
        return True
    except Exception as e:  # noqa: BLE001 — sem truststore ainda dá para tentar
        log_cb(f"(truststore indisponivel: {e} - se o Zscaler inspecionar o SSL, "
               f"a verificacao pode falhar)")
        return False


# ─────────────────── proxy resolvido PELO WINDOWS (arquivo PAC) ─────────────

_WINHTTP_ACCESS_TYPE_NO_PROXY = 1
_AUTOPROXY_AUTO_DETECT = 0x00000001
_AUTOPROXY_CONFIG_URL = 0x00000002
_AUTO_DETECT_DHCP = 0x00000001
_AUTO_DETECT_DNS_A = 0x00000002

# Códigos do WinHTTP que distinguem "esta rede não usa proxy" de "a consulta
# falhou". Sem eles as duas situações viram o mesmo silêncio — e são coisas
# opostas: a primeira é normal, a segunda é defeito.
_ERROS_WINHTTP = {
    12002: "a consulta ao PAC expirou",
    12015: "o proxy exige autenticacao",
    12166: "o arquivo PAC deu erro ao executar",
    12167: "nao foi possivel baixar o arquivo PAC",
    12180: "a rede nao publica WPAD",
}

# (proxies, momento) por URL. O WPAD sozinho custa segundos quando não há PAC
# nenhum, e um lote do AutoSpec faz dezenas de chamadas; mas o cache é CURTO de
# propósito: ligar ou desligar a VPN muda a resposta do PAC, e um valor
# descoberto na abertura do app valeria a sessão inteira — errado.
_VALIDADE_CACHE_S = 60.0
_cache_proxy: dict[str, tuple[list[str], float]] = {}


def esquecer_proxy_descoberto() -> None:
    """Descarta o cache — use ao trocar de rede ou ligar/desligar a VPN."""
    _cache_proxy.clear()


def normalizar_proxies(bruto: str | None) -> list[str]:
    """Resposta do WinHTTP/PAC -> lista de `host:porta`. Função pura.

    O WinHTTP costuma devolver a lista já sem o verbo, mas o formato do PAC
    permite `PROXY host:porta; DIRECT` e `SOCKS host:porta`. Aceitar as duas
    formas custa nada e evita o erro bobo de tratar a palavra "PROXY" como se
    fosse um endereço — e de tentar conectar num proxy chamado "DIRECT".
    """
    saida: list[str] = []
    for pedaco in str(bruto or "").replace(",", ";").split(";"):
        limpo = pedaco.strip()
        if not limpo or limpo.upper().startswith("DIRECT"):
            continue
        partes = limpo.split()
        if partes[0].upper() in ("PROXY", "SOCKS", "HTTP", "HTTPS"):
            # Verbo sem endereço depois não é host nenhum: descarta.
            if len(partes) == 1:
                continue
            limpo = partes[1]
        if limpo and limpo not in saida:
            saida.append(limpo)
    return saida


def _ler_e_liberar(ponteiro) -> str:
    """Lê uma string devolvida pelo WinHTTP e libera a memória (`GlobalFree`).

    Os campos das structs são declarados `c_void_p`, e não `LPWSTR`, justamente
    para isto: com `LPWSTR` o ctypes converteria para `str` na hora e o
    endereço original se perderia — um vazamento de memória a cada consulta,
    numa função que roda a cada chamada HTTP de um lote.
    """
    import ctypes

    if not ponteiro:
        return ""
    try:
        return ctypes.wstring_at(ponteiro)
    finally:
        ctypes.windll.kernel32.GlobalFree(ctypes.c_void_p(ponteiro))


def proxies_do_windows_para(url: str, log_cb: Log = _nada) -> list[str]:
    """Os proxies que o NAVEGADOR usaria para `url`. `[]` = direto ou indisponível.

    Nunca levanta exceção: se o WinHTTP não colaborar, quem chama simplesmente
    segue com as rotas de sempre. Esta via só ACRESCENTA uma tentativa — não
    substitui nem rebaixa nenhuma das que já funcionavam.
    """
    if os.name != "nt":
        return []

    agora = time.monotonic()
    if (achado := _cache_proxy.get(url)) and agora - achado[1] < _VALIDADE_CACHE_S:
        return list(achado[0])

    import ctypes
    from ctypes import wintypes

    class _ConfigIE(ctypes.Structure):
        _fields_ = [("fAutoDetect", wintypes.BOOL),
                    ("lpszAutoConfigUrl", ctypes.c_void_p),
                    ("lpszProxy", ctypes.c_void_p),
                    ("lpszProxyBypass", ctypes.c_void_p)]

    class _Opcoes(ctypes.Structure):
        _fields_ = [("dwFlags", wintypes.DWORD),
                    ("dwAutoDetectFlags", wintypes.DWORD),
                    ("lpszAutoConfigUrl", wintypes.LPCWSTR),
                    ("lpvReserved", ctypes.c_void_p),
                    ("dwReserved", wintypes.DWORD),
                    ("fAutoLogonIfChallenged", wintypes.BOOL)]

    class _InfoProxy(ctypes.Structure):
        _fields_ = [("dwAccessType", wintypes.DWORD),
                    ("lpszProxy", ctypes.c_void_p),
                    ("lpszProxyBypass", ctypes.c_void_p)]

    try:
        # `use_last_error=True`: sem isto o `get_last_error()` não vale nada —
        # qualquer chamada do ctypes entre a falha e a leitura já sobrescreveu
        # o código, e os números de `_ERROS_WINHTTP` viram lixo.
        winhttp = ctypes.WinDLL("winhttp", use_last_error=True)
    except Exception as e:  # noqa: BLE001
        log_cb(f"  (WinHTTP indisponivel: {e})")
        return []

    # `argtypes`/`restype` em TUDO, e isto não é zelo.
    #
    # `HINTERNET` é ponteiro. Sem `restype`, o ctypes assume `c_int` e TRUNCA o
    # handle para 32 bits num Python de 64. O handle sai diferente de zero —
    # parece válido, passa no `if not sessao` — e toda chamada seguinte falha
    # em silêncio. É exatamente o defeito que faz um app relatar "só conexão
    # direta" numa rede que publica PAC.
    winhttp.WinHttpOpen.restype = ctypes.c_void_p
    winhttp.WinHttpOpen.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                    wintypes.LPCWSTR, wintypes.LPCWSTR,
                                    wintypes.DWORD]
    winhttp.WinHttpCloseHandle.restype = wintypes.BOOL
    winhttp.WinHttpCloseHandle.argtypes = [ctypes.c_void_p]
    winhttp.WinHttpGetIEProxyConfigForCurrentUser.restype = wintypes.BOOL
    winhttp.WinHttpGetIEProxyConfigForCurrentUser.argtypes = [
        ctypes.POINTER(_ConfigIE)]
    winhttp.WinHttpGetProxyForUrl.restype = wintypes.BOOL
    winhttp.WinHttpGetProxyForUrl.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                              ctypes.POINTER(_Opcoes),
                                              ctypes.POINTER(_InfoProxy)]

    def _guardar(lista: list[str]) -> list[str]:
        _cache_proxy[url] = (list(lista), agora)
        return lista

    sessao = winhttp.WinHttpOpen("SIGFTItaipu", _WINHTTP_ACCESS_TYPE_NO_PROXY,
                                 None, None, 0)
    if not sessao:
        log_cb("  (WinHttpOpen falhou - seguindo sem o proxy do Windows)")
        return _guardar([])

    try:
        opcoes = _Opcoes()
        opcoes.fAutoLogonIfChallenged = True   # proxy corporativo pede credencial
        config = _ConfigIE()

        # A configuração do USUÁRIO — a mesma do navegador — e não a do
        # serviço, que é o que o `netsh winhttp show proxy` mostra e costuma
        # estar VAZIA. Ler o registro à mão também não serve: esta chamada
        # cobre PAC, WPAD e proxy fixo de uma vez.
        if winhttp.WinHttpGetIEProxyConfigForCurrentUser(ctypes.byref(config)):
            pac_url = _ler_e_liberar(config.lpszAutoConfigUrl)
            estatico = _ler_e_liberar(config.lpszProxy)
            _ler_e_liberar(config.lpszProxyBypass)
            if pac_url:
                opcoes.dwFlags = _AUTOPROXY_CONFIG_URL
                opcoes.lpszAutoConfigUrl = pac_url
                origem = f"PAC ({pac_url})"
            elif config.fAutoDetect:
                opcoes.dwFlags = _AUTOPROXY_AUTO_DETECT
                opcoes.dwAutoDetectFlags = _AUTO_DETECT_DHCP | _AUTO_DETECT_DNS_A
                origem = "autodeteccao (WPAD)"
            elif estatico:
                lista = normalizar_proxies(estatico)
                log_cb(f"  Windows: proxy estatico {', '.join(lista)}")
                return _guardar(lista)
            else:
                log_cb("  Windows: nenhum proxy configurado para o usuario.")
                return _guardar([])
        else:
            opcoes.dwFlags = _AUTOPROXY_AUTO_DETECT
            opcoes.dwAutoDetectFlags = _AUTO_DETECT_DHCP | _AUTO_DETECT_DNS_A
            origem = "autodeteccao (WPAD)"

        info = _InfoProxy()
        if not winhttp.WinHttpGetProxyForUrl(sessao, url, ctypes.byref(opcoes),
                                             ctypes.byref(info)):
            codigo = ctypes.get_last_error()
            motivo = _ERROS_WINHTTP.get(codigo, f"erro {codigo}")
            log_cb(f"  Windows nao resolveu o proxy por {origem}: {motivo}.")
            return _guardar([])

        lista = normalizar_proxies(_ler_e_liberar(info.lpszProxy))
        _ler_e_liberar(info.lpszProxyBypass)
        if lista:
            log_cb(f"  Windows resolveu, via {origem}: {', '.join(lista)}")
        else:
            log_cb(f"  Windows respondeu CONEXAO DIRETA via {origem}.")
        return _guardar(lista)
    except Exception as e:  # noqa: BLE001 — nunca impedir as rotas antigas
        log_cb(f"  (falha ao consultar o proxy do Windows: {e})")
        return []
    finally:
        try:
            winhttp.WinHttpCloseHandle(sessao)
        except Exception:  # noqa: BLE001
            pass


# ──────────────────────────── a cascata de rotas ────────────────────────────

def estrategias(proxy: str | None = None, url: str = "",
                log_cb: Log = _nada) -> list[tuple[str, dict | None, bool]]:
    """Rotas a tentar, na ordem. Cada item: `(nome, proxies|None, trust_env)`.

    `proxies=None` deixa o `requests` decidir pelo ambiente; `proxies={}` força
    SEM proxy (conexão direta). Um `proxy` explícito curto-circuita tudo: é
    escolha da pessoa, e escolha explícita ganha de descoberta.

    A **conexão direta é sempre a última**. É a que funciona fora da VPN, então
    tem de existir; mas se viesse antes, numa rede com PAC ela levaria o
    timeout inteiro da VPN descartando pacotes antes de o app tentar o proxy
    certo — o usuário veria o programa travado a cada chamada.
    """
    if proxy:
        return [("proxy informado", {"http": proxy, "https": proxy}, False)]

    rotas: list[tuple[str, dict | None, bool]] = []
    vistos: set[str] = set()

    # Primeiro o proxy do PAC, resolvido pelo Windows: é o único que sabe a
    # resposta certa POR DESTINO. Sem PAC devolve [] e a ordem antiga fica
    # intacta — a via nova só acrescenta.
    for endereco in (proxies_do_windows_para(url, log_cb) if url else []):
        if endereco in vistos:
            continue
        vistos.add(endereco)
        alvo = endereco if "://" in endereco else f"http://{endereco}"
        rotas.append((f"proxy do Windows ({endereco})",
                      {"http": alvo, "https": alvo}, False))

    try:
        sistema = urllib.request.getproxies()
    except Exception:  # noqa: BLE001
        sistema = {}
    if sistema:
        rotas.append(("proxy do sistema", sistema, False))

    if any(os.getenv(v) for v in ("HTTPS_PROXY", "https_proxy",
                                  "HTTP_PROXY", "http_proxy")):
        rotas.append(("variaveis de ambiente", None, True))

    rotas.append(("conexao direta", {}, False))
    return rotas


def abrir(url: str, *, metodo: str = "GET", headers: dict | None = None,
          params: dict | None = None, json: object | None = None,
          timeout: int = 30, stream: bool = False, proxy: str | None = None,
          log_cb: Log = _nada, status_ok: Iterable[int] | None = (200,),
          _fabrica_sessao=None):
    """Requisição tentando cada rota até uma responder. Devolve `(sessão, resposta)`.

    A `sessão` volta junto de propósito: quem baixa um arquivo grande reaproveita
    a MESMA rota que já funcionou para a consulta, em vez de redescobri-la (e
    talvez cair numa rota diferente no meio do download).

    Levanta `FalhaDeRede` se nenhuma rota entregar um status de `status_ok`.
    Um status fora da lista (404, 401...) **não** é erro de rota: interrompe a
    cascata na hora, porque trocar de proxy não muda a resposta do servidor.

    `status_ok=None` desliga esse julgamento: qualquer resposta que chegou ao
    servidor conta como "a rota funcionou", e o que o status SIGNIFICA volta a
    ser de quem chamou. É o modo que os provedores de IA usam, porque eles já
    tratam o status com mensagem própria — se a cascata julgasse, um 401 do
    OpenRouter viraria `FalhaDeRede` e o "chave inválida" sumiria do log.

    `metodo` cobre GET e POST porque o SIG-FT precisa dos dois — o provedor
    compatível com OpenAI manda POST, o catálogo de modelos manda GET.

    `_fabrica_sessao` existe para o teste: é a costura por onde a suíte injeta
    um dublê de `requests.Session` e observa como cada rota foi configurada.
    """
    import requests

    fabrica = _fabrica_sessao or (lambda: requests.Session())

    injetar_certificados_windows(log_cb)
    rotas = estrategias(proxy, url, log_cb)
    problemas: list[str] = []
    houve_ssl = False

    for verificar_ssl in (True, False):
        if not verificar_ssl:
            if not houve_ssl:
                break   # nenhuma falha foi de certificado -> não relaxa o TLS
            log_cb("[!] Ultimo recurso: tentando SEM verificacao de certificado "
                   "(a raiz do Zscaler/GlobalProtect nao esta no Windows).")
            try:
                import urllib3

                urllib3.disable_warnings()
            except Exception:  # noqa: BLE001
                pass

        for nome, proxies, trust_env in rotas:
            sessao = fabrica()
            sessao.trust_env = trust_env
            if proxies is not None:
                sessao.proxies = dict(proxies)
            sessao.verify = verificar_ssl
            try:
                resp = sessao.request(metodo, url, headers=headers or {},
                                      params=params, json=json,
                                      timeout=timeout, stream=stream)
            except requests.exceptions.SSLError as e:
                houve_ssl = True
                problemas.append(f"{nome}: certificado nao confiavel "
                                 f"({resumo_erro(e, 120)})")
                log_cb(f"  [{nome}] certificado SSL nao confiavel - {resumo_erro(e)}")
                sessao.close()
                continue
            except requests.exceptions.RequestException as e:
                problemas.append(f"{nome}: sem conexao ({resumo_erro(e, 120)})")
                log_cb(f"  [{nome}] sem conexao - {resumo_erro(e)}")
                sessao.close()
                continue

            if status_ok is None or resp.status_code in status_ok:
                via = nome + ("" if verificar_ssl else " - SSL NAO verificado")
                log_cb(f"Conectado via {via}.")
                return sessao, resp

            # Chegou ao servidor: o problema é a requisição, não a rota.
            corpo = "" if stream else f" - {resp.text[:160]}"
            resp.close()
            sessao.close()
            raise FalhaDeRede(f"HTTP {resp.status_code} em {url}{corpo}")

    for linha in diagnostico(urllib.parse.urlparse(url).hostname or ""):
        log_cb(linha)
    raise FalhaDeRede("Nenhuma rota de rede funcionou. Tentativas:\n  - "
                      + "\n  - ".join(problemas or ["(nenhuma rota disponivel)"]))


# ─────────────────────────── diagnóstico de rede ────────────────────────────
#
# Quando NENHUMA rota funciona, a pergunta seguinte é sempre a mesma: o Windows
# tem proxy configurado? qual? o nome resolve? a porta 443 abre? Sem isso o log
# só diz "sem conexão", que não distingue firewall de proxy errado, e a pessoa
# fica trocando de VPN no escuro.

def resumo_erro(e: BaseException, limite: int = 240) -> str:
    """A mensagem MAIS ESPECÍFICA de uma exceção de rede.

    O `requests` embrulha o `urllib3`, que embrulha o erro de socket. O texto
    de fora (`HTTPSConnectionPool(host=..., port=443): Max retries exceeded`) é
    IDÊNTICO para causas completamente diferentes — timeout, DNS, conexão
    recusada, proxy recusando — que são diagnósticos opostos. Quem responde "o
    que aconteceu de fato" é a causa lá no fundo, e é o que esta função busca.
    """
    especifico = e

    # requests.ConnectionError -> MaxRetryError -> `.reason` é o erro real.
    alvo = e.args[0] if getattr(e, "args", None) else None
    if (motivo := getattr(alvo, "reason", None)) is not None:
        especifico = motivo

    vistos = {id(especifico)}
    for _ in range(6):          # limite: cadeias circulares existem
        proxima = especifico.__cause__ or especifico.__context__
        if proxima is None or id(proxima) in vistos:
            break
        vistos.add(id(proxima))
        especifico = proxima

    texto = f"{type(especifico).__name__}: {especifico}"
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _proxies_do_windows() -> list[str]:
    """Como o WINDOWS está configurado — que não é o que o Python enxerga.

    Mostra as três coisas de propósito: o `getproxies()` do Python ignora o
    `AutoConfigURL` (que é justamente como o Zscaler costuma ser distribuído),
    e o `netsh winhttp show proxy` mostra a configuração do SERVIÇO, que
    costuma estar vazia e engana quem está diagnosticando.
    """
    if os.name != "nt":
        return ["  (diagnostico de proxy do Windows: so no Windows)"]

    linhas: list[str] = []
    try:
        import winreg

        chave = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
            for nome in ("ProxyEnable", "ProxyServer", "AutoConfigURL",
                         "ProxyOverride"):
                try:
                    valor, _ = winreg.QueryValueEx(k, nome)
                    linhas.append(f"  {nome} = {valor}")
                except FileNotFoundError:
                    linhas.append(f"  {nome} = (nao definido)")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"  (nao foi possivel ler o registro: {e})")

    try:
        import subprocess

        r = subprocess.run(["netsh", "winhttp", "show", "proxy"],  # noqa: S603,S607
                           capture_output=True, text=True, timeout=15,
                           creationflags=0x08000000)   # CREATE_NO_WINDOW
        for linha in r.stdout.splitlines():
            if linha.strip():
                linhas.append(f"  [winhttp] {linha.strip()}")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"  (netsh winhttp indisponivel: {e})")
    return linhas


def diagnostico(host: str, porta: int = 443) -> list[str]:
    """Relatório do estado da rede para `host`. Nunca levanta exceção."""
    import socket

    linhas = ["--- Diagnostico de rede ---"]

    vistos = {v: os.getenv(v) for v in ("HTTPS_PROXY", "https_proxy",
                                        "HTTP_PROXY", "http_proxy", "NO_PROXY")}
    definidos = {k: v for k, v in vistos.items() if v}
    linhas.append(f"Variaveis de proxy do ambiente: {definidos or '(nenhuma)'}")

    try:
        linhas.append(f"O que o Python enxerga (getproxies): "
                      f"{urllib.request.getproxies() or '(nada)'}")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"O que o Python enxerga (getproxies): erro - {e}")

    linhas.append("Como o Windows esta configurado:")
    linhas.extend(_proxies_do_windows())

    if not host:
        return linhas

    # DNS e TCP separados: dizem coisas diferentes. Nome que não resolve é
    # bloqueio de DNS; porta que não abre com o nome resolvendo é firewall.
    try:
        enderecos = sorted({info[4][0] for info in socket.getaddrinfo(host, porta)})
        linhas.append(f"DNS de {host}: {', '.join(enderecos)}")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"DNS de {host}: FALHOU - {e}")
        return linhas + ["-> O nome nem resolve: e bloqueio de DNS da rede/VPN, "
                         "nao problema do aplicativo."]

    try:
        with socket.create_connection((host, porta), timeout=8):
            linhas.append(f"Conexao TCP direta a {host}:{porta}: ABRIU")
            linhas.append("-> A porta abre direto. Se mesmo assim falha, o bloqueio "
                          "esta no TLS ou o destino exige ir por proxy.")
    except socket.timeout:
        linhas.append(f"Conexao TCP direta a {host}:{porta}: TIMEOUT")
        linhas.append("-> Os pacotes estao sendo DESCARTADOS em silencio (tipico de "
                      "firewall corporativo). Ou o acesso a este destino nao esta "
                      "liberado na VPN, ou o trafego precisa ir por um proxy que o "
                      "Python nao descobriu - compare com o 'Como o Windows esta "
                      "configurado' acima.")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"Conexao TCP direta a {host}:{porta}: {type(e).__name__} - {e}")
    return linhas


# ───────────────────── a porta que os chamadores usam ───────────────────────
#
# `abrir` devolve `(sessão, resposta)` porque quem baixa arquivo grande precisa
# reaproveitar a rota. Para uma chamada comum isso é cerimônia: o chamador quer
# a resposta e mais nada. Daí estes dois atalhos.
#
# Os dois usam `status_ok=None` de propósito. Os pontos de HTTPS do SIG-FT já
# tratam o status por conta própria (`raise_for_status()` seguido de `except`
# com mensagem específica, como a cota estourada do Google CSE). A cascata
# decide QUAL ROTA usar; o que o status significa continua com quem chamou.

def get(url: str, **kwargs):
    """GET pela cascata de rotas. Devolve só a resposta.

    O status não é julgado aqui: `resp.raise_for_status()` continua sendo
    responsabilidade de quem chamou, exatamente como era com `requests.get`.
    """
    kwargs.setdefault("status_ok", None)
    _sessao, resposta = abrir(url, metodo="GET", **kwargs)
    return resposta


def post(url: str, **kwargs):
    """POST pela cascata de rotas. Devolve só a resposta. Ver `get`."""
    kwargs.setdefault("status_ok", None)
    _sessao, resposta = abrir(url, metodo="POST", **kwargs)
    return resposta

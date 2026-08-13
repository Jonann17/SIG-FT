r"""Leitura de `robots.txt` — a permissão que o site dá, e que o SIG-FT respeita.

Existe porque o navegador (`core/web/navegador.py`) é usado como ÚLTIMO
recurso quando o download simples falha, e "o download simples falhou" muitas
vezes quer dizer "o site não quis". Insistir com um navegador de verdade sem
antes perguntar seria contornar uma recusa; ler o `robots.txt` é perguntar.

**Falha FECHADA.** Se o `robots.txt` não puder ser lido — rede fora, timeout,
domínio estranho — a resposta é NÃO. É o inverso do resto do módulo, onde
falha de conveniência não pode custar a execução: aqui a dúvida é sobre
permissão, e agir sem permissão é o que se quer evitar.

Exceção: `robots.txt` que responde 404 significa "não há regra", e aí o
padrão da web é permitir. Só isso é tratado como liberação.

Usa `urllib.robotparser`, da stdlib — sem dependência nova.
"""
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

# O robots.txt de um domínio não muda durante um lote. Sem cache, um lote de
# 50 fichas releria o mesmo arquivo dezenas de vezes.
_cache = {}

TIMEOUT_S = 8


def _raiz(url):
    partes = urllib.parse.urlsplit(str(url or ""))
    if not partes.scheme or not partes.netloc:
        return None
    return f"{partes.scheme}://{partes.netloc}"


def _carregar(raiz):
    """`RobotFileParser` pronto, `True` para "não há regra", `None` para
    "não deu para saber"."""
    if raiz in _cache:
        return _cache[raiz]

    resultado = None
    try:
        with urllib.request.urlopen(f"{raiz}/robots.txt", timeout=TIMEOUT_S) as resposta:
            bruto = resposta.read().decode("utf-8", errors="ignore")
        leitor = urllib.robotparser.RobotFileParser()
        leitor.parse(bruto.splitlines())
        resultado = leitor
    except urllib.error.HTTPError as erro:
        # 404/410: o site não publica regra nenhuma. O padrão da web é
        # permitir, e é o único caso em que a ausência libera.
        resultado = True if erro.code in (404, 410) else None
    except Exception:
        resultado = None

    _cache[raiz] = resultado
    return resultado


def pode_acessar(url, user_agent="*"):
    """O site permite que um robô busque esta URL?

    `False` na dúvida — ver o docstring do módulo para por que a falha aqui é
    fechada e não aberta.
    """
    raiz = _raiz(url)
    if raiz is None:
        return False

    regra = _carregar(raiz)
    if regra is True:
        return True
    if regra is None:
        return False
    try:
        return bool(regra.can_fetch(user_agent, str(url)))
    except Exception:
        return False


def limpar_cache():
    """Só para teste — o cache é por processo e o app não vive o bastante
    para o `robots.txt` mudar debaixo dele."""
    _cache.clear()

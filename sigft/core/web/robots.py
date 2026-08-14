r"""Leitura de `robots.txt` — a permissão que o site dá, e que o SIG-FT respeita.

Existe porque o navegador (`core/web/navegador.py`) é usado como ÚLTIMO
recurso quando o download simples falha, e "o download simples falhou" muitas
vezes quer dizer "o site não quis". Insistir com um navegador de verdade sem
antes perguntar seria contornar uma recusa; ler o `robots.txt` é perguntar.

**Falha ABERTA** (decisão do usuário, 2026-08-13). Se o `robots.txt` não puder
ser lido — rede fora, timeout, servidor com defeito — a resposta é SIM.

A versão anterior falhava fechada, pelo argumento de que a dúvida era sobre
permissão. O usuário decidiu o contrário, e a decisão se sustenta: não
conseguir LER a regra não é o mesmo que a regra dizer não. Rede corporativa
com proxy derruba `robots.txt` com frequência, e falhar fechada ali
transformaria um problema de rede numa recusa silenciosa — o recurso pareceria
quebrado sem nunca dizer por quê.

O que continua barrando é o `Disallow` EXPLÍCITO. Um site que diz "não"
continua recebendo "está bem"; o que mudou é só o tratamento do silêncio.

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

    Só o `Disallow` explícito barra. Não conseguir ler o `robots.txt` libera —
    ver o docstring do módulo.

    A URL malformada continua sendo `False`: aí não há domínio a consultar, e
    não é dúvida sobre permissão, é entrada inválida.
    """
    raiz = _raiz(url)
    if raiz is None:
        return False

    regra = _carregar(raiz)
    if regra is True or regra is None:
        return True
    try:
        return bool(regra.can_fetch(user_agent, str(url)))
    except Exception:
        return True


def limpar_cache():
    """Só para teste — o cache é por processo e o app não vive o bastante
    para o `robots.txt` mudar debaixo dele."""
    _cache.clear()

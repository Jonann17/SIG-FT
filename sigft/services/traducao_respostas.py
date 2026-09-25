r"""Regras da tradução PT -> ES das RESPOSTAS das fichas (Tradutor 4.2).

Sem Excel e sem modelo: o motor chega INJETADO (`motor(list[str]) -> list[str]`,
o mesmo contrato de `traducao_pdm`), e é por isso que tudo aqui se testa sem
rede. O motor de produção é `sigft.core.tradutor_local.TradutorLocal`.

POR QUE CAMADAS ANTES DO MODELO (medido em 2026-09-25, spec
`docs/superpowers/specs/2026-09-25-tradutor-local-design.md`)
------------------------------------------------------------------------
O modelo local (OPUS-MT tc-big) traduz bem o texto corrido e erra o
vocabulário técnico brasileiro: "PORCA SEXTAVADA" virou "CERDA HEXAGONAL",
"Mancal de deslizamento" virou "Falta de deslizamiento", "Arruela" virou
"Lavadora". Trocar o termo pelo espanhol ANTES do modelo consertou metade; na
outra metade o modelo "retraduziu" o espanhol (`cojinete` -> `rodamiento`,
`tuerca` -> `cerda`). O que ele NÃO mexe são códigos (`6205-2RS`, `AISI 316L`)
-- daí o marcador: o termo vira um código, o modelo o copia, e o código vira o
termo da casa depois. Só que, com o marcador, a frase em volta às vezes
estraga ("Válvula de compuerta como vástago", era "con"). Por isso cada
resposta com termo do glossário vai em TRÊS versões, e vence a mais natural
que mantém o termo (ver `_versoes`).

As camadas, na ordem em que cada resposta passa:

1. vazio ou "não se traduz" (número, unidade, código, norma, `N/A`) -> igual;
2. glossário, FRASE INTEIRA -> o espanhol do glossário, sem modelo;
3. símbolo fora do vocabulário (`Ø`, `±`, `²`) -> marcador, volta igual;
4. o modelo, UMA ida para todas as versões distintas do lote;
5. conferências: marcador perdido, `⁇` ou prefixo vazado invalidam a versão;
   número que muda devolve o original; ponto final que o original não tinha
   sai. Termo da casa que nenhuma versão manteve vira `conferir` no log.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

NOME_GLOSSARIO_USUARIO = "GLOSSARIO_PT_ES.txt"

# =============================================================================
# Glossário da casa
# =============================================================================
# SÓ o que o modelo errou no experimento, ou erraria pelo mesmo motivo
# (termo técnico brasileiro que o espanhol não tem igual). Termo que o modelo
# já acerta NÃO entra: cada marcador a mais é um risco a mais de o modelo
# bagunçar a frase em volta. O do usuário vence este (ver `glossario_em_uso`).
GLOSSARIO_DA_CASA = {
    # mecânica
    "mancal": "cojinete",
    "mancais": "cojinetes",
    "porca": "tuerca",
    "porcas": "tuercas",
    "arruela": "arandela",
    "arruelas": "arandelas",
    "gaxeta": "empaquetadura",
    "gaxetas": "empaquetaduras",
    "retentor": "retén",
    "retentores": "retenes",
    "prisioneiro": "espárrago",
    "prisioneiros": "espárragos",
    "revenido": "revenido",
    "temperado e revenido": "templado y revenido",
    "zincado": "cincado",
    "galvanizado a fogo": "galvanizado en caliente",
    "içamento": "izaje",
    "olhal de içamento": "cáncamo de izaje",
    # elétrica
    "escova de carvão": "escobilla de carbón",
    "escovas de carvão": "escobillas de carbón",
    "porta-escova": "portaescobillas",
    "porta-escovas": "portaescobillas",
    "chave fim de curso": "interruptor de fin de carrera",
    "fim de curso": "fin de carrera",
    "tensão": "tensión",
    "enrolamento": "devanado",
    "enrolamentos": "devanados",
    # válvulas
    "válvula gaveta": "válvula de compuerta",
    "válvula borboleta": "válvula mariposa",
    "portinhola": "clapeta",
    # frases que o modelo trocou de sentido
    "conforme desenho": "según plano",
    "desenho": "plano",
    "desenhos": "planos",
    "ao tempo": "a la intemperie",
    "não aplicável": "no aplicable",
    "idem ao original": "ídem al original",
}

CABECALHO_GLOSSARIO_USUARIO = """\
# GLOSSARIO PT -> ES  (SIG-FT, Tradutor Tecnico 4.2)
#
# O tradutor roda NESTE computador: nenhuma resposta sai daqui. Quando ele
# errar um termo tecnico, escreva a correcao aqui e ela vale sempre.
#
# FORMATO: uma correcao por linha
#     portugues = espanhol
#
#   - a RESPOSTA INTEIRA igual ao lado esquerdo sai exatamente como o lado
#     direito, sem passar pelo tradutor;
#   - um TERMO dentro da resposta e protegido: o tradutor traduz o resto da
#     frase e o termo sai como voce escreveu.
#
# Maiusculas e acentos do lado esquerdo nao importam. O que estiver aqui vence
# o glossario que ja vem no programa. Linhas comecadas por # sao ignoradas.
#
# EXEMPLOS (tire o # da frente para valer):
# mancal guia = cojinete guia
# conforme catalogo = segun catalogo
"""

# =============================================================================
# O que não se traduz
# =============================================================================
# Siglas e normas: ficam como estão (e em maiúsculas na caixa de frase).
SIGLAS = frozenset({
    "ABNT", "NBR", "ASTM", "AISI", "SAE", "DIN", "ISO", "IEC", "IEEE", "NEMA",
    "ANSI", "API", "ASME", "JIS", "UL", "IP", "IK", "NR", "PTFE", "EPDM",
    "FKM", "PVC", "HDPE", "PEAD", "HART", "RMS", "TC", "TP", "CLP", "PLC",
    "LED", "USB", "IHM", "HMI", "CA", "CC", "AC", "DC", "NA", "NF", "RTD",
})

# Unidades e sinais, em minúsculas. Um token destes sozinho não é texto.
UNIDADES = frozenset({
    "v", "kv", "mv", "a", "ka", "ma", "w", "kw", "mw", "va", "kva", "mva",
    "var", "kvar", "hz", "khz", "rpm", "mm", "cm", "m", "km", "µm", "um",
    "mm2", "mm²", "m2", "m²", "m3", "m³", "kg", "g", "mg", "t", "ton", "bar",
    "mbar", "psi", "pa", "kpa", "mpa", "°c", "ºc", "°f", "°", "º", "%",
    "l", "ml", "l/min", "l/h", "l/s", "m3/h", "m³/h", "m3/s", "m³/s", "vca",
    "vcc", "vac", "vdc", "nm", "n.m", "kgf", "kgf.m", "kgf/cm2", "kgf/cm²",
    "n", "kn", "db", "lux", "cv", "hp", "pol", "pol.", "in", "h", "min", "s",
    "ms", "ohm", "ω", "kω", "mω", "µf", "uf", "nf", "pf", "ppm", "x", "×",
    "ø", "⌀", '"', "'",
})

# Respostas que dizem "não há", e que o Upload 4.3 reconhece como estão.
_NAO_HA = frozenset({"n/a", "na", "n.a.", "n.a", "n/d", "nd", "-", "--", "---",
                     ".", "..", "...", "0"})

_RE_TOKEN = re.compile(r"\S+")
_RE_DIGITOS = re.compile(r"\d+")
_BORDAS = "()[]{},;:"


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _chave(texto: str) -> str:
    """Forma de comparação: sem acento, minúsculas, espaço simples, sem o
    ponto final."""
    return " ".join(_sem_acento(texto).lower().split()).rstrip(".").strip()


def _nucleo(token: str) -> str:
    return token.strip(_BORDAS)


def nao_precisa_traduzir(texto) -> bool:
    """`True` para o que não é texto: número, unidade, código, norma, `N/A`.

    Todo token tem de ser "não linguístico" -- basta uma palavra de verdade
    para a resposta ir ao modelo. Marca e modelo (`WEG W22`) vão ao modelo, que
    os copia; aqui só entra o que é certo não mudar.
    """
    limpo = str(texto or "").strip()
    if not limpo:
        return True
    if limpo.lower() in _NAO_HA:
        return True
    for token in _RE_TOKEN.findall(limpo):
        nucleo = _nucleo(token)
        if not nucleo or not any(c.isalpha() for c in nucleo):
            continue
        if any(c.isdigit() for c in nucleo):
            continue
        if nucleo.upper() == nucleo and nucleo in SIGLAS:
            continue
        if nucleo.lower() in UNIDADES:
            continue
        return False
    return True


def caixa_de_frase(texto: str) -> tuple[str, bool]:
    """TUDO MAIÚSCULO -> caixa de frase, preservando sigla e código.

    O modelo aprendeu com texto corrido; em maiúsculas ele erra mais. Devolve
    `(texto, estava_em_caixa_alta)` para a resposta voltar como veio.
    """
    letras = [c for c in texto if c.isalpha()]
    if len(letras) <= 3 or not all(c.isupper() for c in letras):
        return texto, False
    partes = []
    for token in re.split(r"(\s+)", texto):
        nucleo = _nucleo(token)
        if (not token.strip() or any(c.isdigit() for c in token)
                or nucleo in SIGLAS):
            partes.append(token)
        else:
            partes.append(token.lower())
    frase = "".join(partes)
    for i, c in enumerate(frase):
        if c.isalpha():
            frase = frase[:i] + c.upper() + frase[i + 1:]
            break
    return frase, True


# =============================================================================
# Glossário: arquivo
# =============================================================================
def _ler_texto(caminho) -> str:
    """UTF-8 primeiro; cp1252 depois -- o Bloco de Notas ainda oferece ANSI.
    Mesma lição do glossário PT -> EN (`traducao_pdm._ler_texto`)."""
    try:
        with open(caminho, "rb") as arquivo:
            bruto = arquivo.read()
    except OSError:
        return ""
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return bruto.decode("utf-8", errors="replace")


def carregar_glossario(caminho) -> dict[str, str]:
    """`{portugues: espanhol}`, chaves em minúsculas. Arquivo ausente ou
    ilegível devolve `{}`: glossário é conforto, e não pode impedir a
    tradução de rodar."""
    termos = {}
    for linha in _ler_texto(caminho).splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        pt, _, es = linha.partition("=")
        pt = " ".join(pt.split()).lower()
        es = " ".join(es.split())
        if pt and es:
            termos[pt] = es
    return termos


def criar_glossario_do_usuario(caminho):
    """Cria o arquivo com as instruções, se ainda não existir. **Nunca
    sobrescreve**: o que o usuário escreveu é o que vale."""
    import os

    caminho = os.fspath(caminho)
    if not os.path.exists(caminho):
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(CABECALHO_GLOSSARIO_USUARIO)
    return caminho


def caminho_glossario_do_usuario():
    """`Documentos\\SIG-FT\\traducao\\GLOSSARIO_PT_ES.txt` -- fora da pasta do
    programa, para a atualização não apagar o que o usuário corrigiu."""
    from sigft.core import dados_usuario

    return dados_usuario.pasta_dados() / "traducao" / NOME_GLOSSARIO_USUARIO


def glossario_em_uso(caminho_usuario=None) -> dict[str, str]:
    """O da casa, com o do usuário por cima. A comparação ignora acento: um
    `icamento = ...` do usuário substitui o `içamento` da casa."""
    por_chave = {_chave(pt): (pt, es) for pt, es in GLOSSARIO_DA_CASA.items()}
    if caminho_usuario is not None:
        for pt, es in carregar_glossario(caminho_usuario).items():
            por_chave[_chave(pt)] = (pt, es)
    return dict(por_chave.values())


# =============================================================================
# Marcadores: o que o modelo tem de copiar sem mexer
# =============================================================================
# O marcador imita um CÓDIGO, que é o que o modelo copia (`6205-2RS`,
# `AISI 316L`). O padrão aceita o modelo ter posto espaço no meio ou mudado a
# caixa.
_PREFIXO_MARCADOR = "XQ"
PADRAO_MARCADOR = r"(?i)\bX\s?Q\s?\d{1,2}\b"

# Fora do ASCII, o que o português e o espanhol usam. O resto (`Ø`, `Ω`, `µ`,
# `±`, `²`...) o modelo não conhece: medido em 2026-09-25, o `Ø` virava `⁇`,
# ou, pedindo para copiar o desconhecido, o próprio prefixo `>>spa<<`. O token
# que tem um desses vai inteiro num marcador e volta como estava.
_PERMITIDOS = frozenset("áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑºª°«»¿¡–—‘’“”…·")

_VARIANTES = {
    "a": "aáàâãä", "e": "eéèêë", "i": "iíìîï", "o": "oóòôõö", "u": "uúùûü",
    "c": "cç", "n": "nñ",
}


def _padrao_do_termo(termo: str) -> re.Pattern:
    """Palavra inteira, sem ligar para acento nem caixa, e sem casar dentro de
    termo com hífen (`escova` não pega `porta-escova`)."""
    partes = []
    for c in _chave(termo):
        if c in _VARIANTES:
            partes.append(f"[{_VARIANTES[c]}]")
        elif c == " ":
            partes.append(r"\s+")
        else:
            partes.append(re.escape(c))
    return re.compile(r"(?<![\w-])" + "".join(partes) + r"(?![\w-])", re.IGNORECASE)


def _com_caixa_de(modelo: str, termo: str) -> str:
    """O termo em espanhol com a inicial maiúscula se o original a tinha."""
    if modelo[:1].isupper():
        return termo[:1].upper() + termo[1:]
    return termo


def _contem(texto: str, termo: str) -> bool:
    return bool(_padrao_do_termo(termo).search(texto))


def _estranho(token: str) -> bool:
    return any(ord(c) > 127 and c not in _PERMITIDOS for c in token)


# =============================================================================
# As versões de uma resposta
# =============================================================================
@dataclass(frozen=True)
class _Versao:
    texto: str          # o que vai ao modelo
    marcadores: tuple   # ((marcador, o que volta no lugar), ...)
    exigidos: tuple     # ((termo em espanhol, "pt = es"), ...) que a saída tem de ter


def _versoes(frase: str, termos) -> list[_Versao]:
    """Até três versões, da mais natural para a mais garantida:

    1. **direta** -- o modelo sozinho (às vezes ele já acerta o termo);
    2. **com o espanhol** -- o termo da casa já escrito na frase (a gramática
       fica intacta, mas o modelo pode "retraduzir" o termo);
    3. **com marcador** -- o termo vira um código que o modelo copia (o termo
       sai garantido, mas a frase em volta às vezes estraga).

    Sem termo do glossário na frase, só a direta.
    """
    # Uma resposta que JÁ traz algo com cara de marcador (um código `XQ1` de
    # verdade) teria esse código trocado na volta: nela, nada de marcador.
    pode_marcar = not re.search(PADRAO_MARCADOR, frase)
    numero = iter(range(1, 100))
    simbolos = []

    def marcar_simbolo(m):
        if not _estranho(m.group(0)):
            return m.group(0)
        marcador = f"{_PREFIXO_MARCADOR}{next(numero)}"
        simbolos.append((marcador, m.group(0)))
        return marcador

    base = re.sub(r"\S+", marcar_simbolo, frase) if pode_marcar else frase

    presentes = [t for t in termos if t[2].search(base)]
    if not presentes:
        return [_Versao(base, tuple(simbolos), ())]

    exigidos, marcadores = [], list(simbolos)
    com_espanhol, com_marcador = base, base
    for pt, es, padrao in presentes:         # do mais longo para o mais curto
        par = f"{pt} = {es}"

        def escrever(m, es=es, par=par):
            termo = _com_caixa_de(m.group(0), es)
            exigidos.append((termo, par))
            return termo

        def marcar(m, es=es):
            marcador = f"{_PREFIXO_MARCADOR}{next(numero)}"
            marcadores.append((marcador, _com_caixa_de(m.group(0), es)))
            return marcador

        com_espanhol = padrao.sub(escrever, com_espanhol)
        if pode_marcar:
            com_marcador = padrao.sub(marcar, com_marcador)

    versoes = [_Versao(base, tuple(simbolos), tuple(exigidos)),
               _Versao(com_espanhol, tuple(simbolos), tuple(exigidos))]
    if pode_marcar:
        versoes.append(_Versao(com_marcador, tuple(marcadores), ()))
    return versoes


# =============================================================================
# Tradução
# =============================================================================
class TraducaoFalhou(RuntimeError):
    """O motor não devolveu uma tradução por texto enviado."""


@dataclass(frozen=True)
class Traducao:
    original: str
    texto: str          # o espanhol (ainda com acento; quem grava tira)
    origem: str         # "vazio" | "igual" | "glossario" | "tradutor" | "conferir"
    aviso: str = ""


def _ajustar_ponto(original: str, traduzido: str) -> str:
    """O ponto final segue o original: o modelo acrescenta um ("Sim" -> "Sí.")."""
    if original.rstrip().endswith("."):
        return traduzido if traduzido.endswith(".") else traduzido + "."
    if traduzido.endswith(".") and not traduzido.endswith(".."):
        return traduzido[:-1].rstrip()
    return traduzido


def _numeros(texto: str) -> list[str]:
    return sorted(_RE_DIGITOS.findall(texto))


def _chamar(motor, textos: list[str]) -> list[str]:
    saida = list(motor(textos))
    if len(saida) != len(textos):
        raise TraducaoFalhou(
            f"o tradutor devolveu {len(saida)} texto(s) para {len(textos)} enviado(s)")
    return ["" if s is None else str(s).strip() for s in saida]


_MOTIVOS = {
    "vazio": "o tradutor devolveu vazio; ficou o original",
    "desconhecido": "o tradutor nao reconheceu um simbolo; ficou o original",
    "marcador": "o tradutor perdeu um trecho protegido; ficou o original",
}


def _restaurar(versao: _Versao, saida: str, original: str) -> tuple[str | None, str]:
    """A saída com os marcadores desfeitos, ou `(None, motivo)` se ela não
    serve de jeito nenhum."""
    if not saida:
        return None, "vazio"
    for sinal in ("\u2047", ">>", "<<"):
        if sinal in saida and sinal not in original:
            return None, "desconhecido"
    texto = saida
    for marcador, volta in versao.marcadores:
        numero = marcador[len(_PREFIXO_MARCADOR):]
        padrao = re.compile(r"(?i)\bX\s?Q\s?" + numero + r"\b")
        if not padrao.search(texto):
            return None, "marcador"
        texto = padrao.sub(lambda _m, volta=volta: volta, texto)
    if re.search(PADRAO_MARCADOR, texto) and not re.search(PADRAO_MARCADOR, original):
        return None, "marcador"
    if _numeros(texto) != _numeros(original):
        return None, ("a traducao mudou os numeros (" + ", ".join(_numeros(original))
                      + "); ficou o original")
    return texto, ""


def traduzir_respostas(textos, motor, glossario=None) -> list[Traducao]:
    """Traduz uma lista de respostas, devolvendo na MESMA ordem.

    O motor é chamado UMA vez, com todas as versões distintas do lote. Por
    resposta, vence a primeira versão (direta, com o espanhol, com marcador)
    que mantém os termos do glossário; se nenhuma mantém, fica a mais natural
    que ao menos passou nas conferências, marcada para conferir.
    """
    termos = sorted(
        ((pt, es, _padrao_do_termo(pt)) for pt, es in (glossario or {}).items()),
        key=lambda t: len(_chave(t[0])), reverse=True)
    frases = {_chave(pt): es for pt, es, _ in termos}

    resultado: list[Traducao | None] = [None] * len(textos)
    pendentes: dict[int, tuple[str, bool, list[_Versao]]] = {}

    for i, bruto in enumerate(textos):
        original = "" if bruto is None else str(bruto)
        limpo = original.strip()
        if not limpo:
            resultado[i] = Traducao(original, "", "vazio")
        elif nao_precisa_traduzir(limpo):
            resultado[i] = Traducao(original, limpo, "igual")
        elif _chave(limpo) in frases:
            es = _com_caixa_de(limpo, frases[_chave(limpo)])
            if caixa_de_frase(limpo)[1]:
                es = es.upper()
            resultado[i] = Traducao(original, _ajustar_ponto(limpo, es), "glossario")
        else:
            frase, alta = caixa_de_frase(limpo)
            pendentes[i] = (limpo, alta, _versoes(frase, termos))

    entradas = list(dict.fromkeys(v.texto for _, _, versoes in pendentes.values()
                                  for v in versoes))
    saidas = dict(zip(entradas, _chamar(motor, entradas))) if entradas else {}

    for i, (limpo, alta, versoes) in pendentes.items():
        escolhido, reserva, motivo = None, None, ""
        for versao in versoes:
            texto, problema = _restaurar(versao, saidas[versao.texto], limpo)
            if texto is None:
                motivo = motivo or problema
                continue
            faltando = [par for termo, par in versao.exigidos if not _contem(texto, termo)]
            if not faltando:
                escolhido = texto
                break
            if reserva is None:
                reserva = (texto, "o tradutor nao manteve o termo do glossario ("
                           + "; ".join(dict.fromkeys(faltando)) + ")")

        if escolhido is None and reserva is None:
            resultado[i] = Traducao(textos[i], limpo, "conferir", _MOTIVOS.get(motivo, motivo))
            continue
        texto, aviso = (escolhido, "") if escolhido is not None else reserva
        texto = _ajustar_ponto(limpo, texto)
        if alta:
            texto = texto.upper()
        resultado[i] = Traducao(textos[i], texto, "conferir" if aviso else "tradutor", aviso)

    return resultado


def resumo(traducoes) -> dict[str, int]:
    """Quantas respostas saíram de cada camada (só as que apareceram)."""
    return dict(Counter(t.origem for t in traducoes))

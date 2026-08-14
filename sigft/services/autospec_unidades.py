r"""Conversão de unidade CONFERIDA — para o lastro documental não reprovar
uma conversão correta.

POR QUE ESTE MÓDULO EXISTE
------------------------------------------------------------------------
O lastro documental (`autospec.valor_tem_lastro`, 2026-08-13) exige que todo
número respondido apareça no documento lido. Isso pega valor inventado, que
era o objetivo — mas reprovava junto uma coisa legítima: o documento diz
`350 bar` e a ficha pede a pressão em MPa, a IA responde `35 MPa`, e `35` não
está escrito em lugar nenhum.

Decisão do usuário em 2026-08-13: *"a regra de conversão de unidade reprova
acho que não é necessária, caso a conversão seja realizada de maneira
correta. No máximo coloque uma forma de verificação desta."*

Então é isso que este módulo faz: **refaz a conta**. Não confia na conversão
da IA — recalcula a partir do número do documento e compara. Se bater dentro
da tolerância, aprova E DIZ que foi conversão, para o engenheiro conferir. Se
não bater, continua reprovando.

A diferença entre "aceitar conversão" e "conferir conversão" é a diferença
entre confiar no modelo e verificar o modelo. `35 MPa` a partir de `350 bar`
passa; `3,5 MPa` a partir de `350 bar` não passa, e é justamente o erro de
ordem de grandeza que ninguém percebe olhando.

O QUE ESTÁ AQUI DENTRO
------------------------------------------------------------------------
Só as grandezas que aparecem em ficha técnica de sobressalente de
hidrelétrica: pressão, comprimento, massa, temperatura, vazão, potência,
torque, rotação e área. Sem dependência externa — a tabela é um dict.

Temperatura é caso à parte: a conversão é AFIM (`F = C*9/5 + 32`), não uma
multiplicação. Tratada em separado por isso.
"""
import re
import unicodedata

# Tolerância relativa. Datasheet arredonda: `350 bar` vira `35 MPa` exato,
# mas `175 bar` vira `2538 psi` (2537,86...). 1% cobre o arredondamento sem
# deixar passar erro de ordem de grandeza, que é o que se quer pegar.
TOLERANCIA_RELATIVA = 0.01

# Fator para a unidade BASE de cada grandeza.
#   valor_na_base = valor * FATOR
_FATORES = {
    # ---- pressão (base: pascal) -------------------------------------
    "pressao": {
        "pa": 1.0, "kpa": 1e3, "mpa": 1e6, "gpa": 1e9,
        "bar": 1e5, "mbar": 1e2, "kgf/cm2": 98066.5, "kgf/cm²": 98066.5,
        "psi": 6894.757, "atm": 101325.0,
    },
    # ---- comprimento (base: metro) ----------------------------------
    "comprimento": {
        "m": 1.0, "cm": 1e-2, "mm": 1e-3, "um": 1e-6, "µm": 1e-6, "km": 1e3,
        "in": 2.54e-2, "pol": 2.54e-2, '"': 2.54e-2, "ft": 0.3048,
    },
    # ---- massa (base: quilograma) -----------------------------------
    "massa": {"kg": 1.0, "g": 1e-3, "mg": 1e-6, "t": 1e3, "lb": 0.45359237, "oz": 0.0283495},
    # ---- vazão (base: m3/s) -----------------------------------------
    "vazao": {
        "m3/s": 1.0, "m3/h": 1 / 3600.0, "l/s": 1e-3, "l/min": 1e-3 / 60,
        "l/h": 1e-3 / 3600, "ml/min": 1e-6 / 60, "gpm": 6.30902e-5,
    },
    # ---- potência (base: watt) --------------------------------------
    "potencia": {"w": 1.0, "kw": 1e3, "mw": 1e6, "cv": 735.49875, "hp": 745.6999},
    # ---- torque (base: N.m) -----------------------------------------
    "torque": {"nm": 1.0, "n.m": 1.0, "knm": 1e3, "kgfm": 9.80665, "kgf.m": 9.80665,
               "lbft": 1.355818, "lb.ft": 1.355818},
    # ---- rotação (base: rpm) ----------------------------------------
    "rotacao": {"rpm": 1.0, "min-1": 1.0, "rps": 60.0, "hz": 60.0},
    # ---- área (base: m2) --------------------------------------------
    "area": {"m2": 1.0, "cm2": 1e-4, "mm2": 1e-6, "in2": 6.4516e-4},
}

# Unidade -> grandeza, para achar a dimensão a partir do símbolo.
_GRANDEZA_DA_UNIDADE = {
    unidade: grandeza for grandeza, tabela in _FATORES.items() for unidade in tabela
}

# Temperatura: conversão AFIM, fora da tabela de fatores de propósito.
_TEMPERATURA = {"c", "°c", "oc", "f", "°f", "of", "k"}

# Casa "350 bar", "25,4 mm", "35MPa", "0 a +70 °C", "50 l/min".
_RE_VALOR_UNIDADE = re.compile(
    r"([+-]?\d+(?:[.,]\d+)?)\s*"
    r"(°?[a-zµ]{1,3}(?:[./][a-z0-9]{1,4})?|kgf/cm[²2]|\")",
    re.IGNORECASE,
)


def _normalizar(texto):
    s = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _numero(bruto):
    try:
        return float(str(bruto).replace(",", "."))
    except (TypeError, ValueError):
        return None


# O que pode existir ENTRE os dois números de um intervalo, e nada mais:
# `0 a +70 C`, `0 to +70 C`, `0...70`, `0 bis 70`, `-20 até +70`.
_RE_CONECTOR_INTERVALO = re.compile(
    r"^\s{0,3}(?:a|ate|to|e|and|bis|hasta|y|und|-|–|\.{2,3}|/)?\s{0,3}$"
)

_RE_NUMERO_SOLTO = re.compile(r"[+-]?\d+(?:[.,]\d+)?")
_RE_UNIDADE_ADIANTE = re.compile(
    r"^\s*(kgf/cm[²2]|°?[a-zµ]{1,3}(?:[./][a-z0-9]{1,4})?|\")", re.IGNORECASE
)


def _unidade_valida(bruta):
    u = str(bruta or "").strip().lower().lstrip("°")
    if u in _GRANDEZA_DA_UNIDADE or u in _TEMPERATURA or ("°" + u) in _TEMPERATURA:
        return u
    return None


def extrair_medidas(texto):
    """`[(350.0, 'bar'), (25.4, 'mm')]` — pares número+unidade de um texto.

    **Número sem unidade HERDA a do vizinho**, e isso não é conveniência: é o
    que fecha um furo real. Um intervalo se escreve `0 a +70 C` — só o
    segundo número carrega a unidade. Sem herança, o `0` sairia da lista, e
    numa resposta convertida (`32 a 158 F`) o primeiro limite nunca seria
    conferido: bastaria acertar o segundo para o campo inteiro passar.

    Herda do PRÓXIMO número com unidade (é como o intervalo se lê); se não
    houver, do anterior.
    """
    normalizado = _normalizar(texto)
    brutos = []
    for m in _RE_NUMERO_SOLTO.finditer(normalizado):
        valor = _numero(m.group())
        if valor is None:
            continue
        adiante = _RE_UNIDADE_ADIANTE.match(normalizado[m.end():])
        brutos.append(
            [valor, _unidade_valida(adiante.group(1)) if adiante else None, m.start(), m.end()]
        )

    # A herança é ESTRITAMENTE LOCAL: só atravessa um conector de intervalo.
    #
    # A primeira versão herdava da unidade mais próxima em qualquer distância,
    # e isso criou um falso positivo imediato: o `1000` de `cs1000.pdf`
    # herdava o `bar` de `350 bar` sete palavras adiante, e `999 bar` passava
    # a conferir contra ele dentro da tolerância de 1%. Número de nome de
    # arquivo virando medida é o oposto do que este módulo existe para fazer.
    for i, item in enumerate(brutos):
        if item[1] is not None:
            continue
        for vizinho in (brutos[i + 1] if i + 1 < len(brutos) else None,
                        brutos[i - 1] if i > 0 else None):
            if vizinho is None or vizinho[1] is None:
                continue
            ini, fim = (item[3], vizinho[2]) if vizinho[2] > item[3] else (vizinho[3], item[2])
            if _RE_CONECTOR_INTERVALO.match(normalizado[ini:fim]):
                item[1] = vizinho[1]
                break

    return [(valor, unidade) for valor, unidade, _i, _f in brutos if unidade is not None]


def _para_base(valor, unidade):
    """`(valor_na_base, grandeza)` ou `(None, None)` se a unidade é
    desconhecida. Temperatura vira Celsius."""
    u = unidade.lstrip("°")
    if u in _TEMPERATURA or ("°" + u) in _TEMPERATURA:
        if u.startswith("f"):
            return (valor - 32) * 5 / 9, "temperatura"
        if u == "k":
            return valor - 273.15, "temperatura"
        return valor, "temperatura"
    grandeza = _GRANDEZA_DA_UNIDADE.get(u)
    if grandeza is None:
        return None, None
    return valor * _FATORES[grandeza][u], grandeza


def _da_base(valor_base, unidade):
    """Volta da unidade base para `unidade`. Inverso de `_para_base`.

    Existe porque a comparação precisa acontecer na unidade da RESPOSTA, não
    na base. Comparar em base foi a primeira versão e tinha um furo grave:
    a base da vazão é m³/s, onde `0,4 l/min` e `50 ml/min` valem 6,7e-6 e
    8,3e-7 — números tão pequenos que a tolerância absoluta (0,01) aprovava
    qualquer par. Na unidade da resposta, `0,4` contra `0,05` é obviamente
    diferente, e é assim que uma pessoa confere.
    """
    u = unidade.lstrip("°")
    if u in _TEMPERATURA or ("°" + u) in _TEMPERATURA:
        if u.startswith("f"):
            return valor_base * 9 / 5 + 32
        if u == "k":
            return valor_base + 273.15
        return valor_base
    grandeza = _GRANDEZA_DA_UNIDADE.get(u)
    if grandeza is None:
        return None
    return valor_base / _FATORES[grandeza][u]


def _proximos(a, b):
    """Comparação com tolerância RELATIVA, e absoluta perto do zero.

    Perto de zero a relativa não serve: `0 °C` e `0,3 °C` teriam diferença
    relativa infinita. Só que o absoluto tem de valer na unidade que a pessoa
    lê — ver `_da_base`.
    """
    if a is None or b is None:
        return False
    escala = max(abs(a), abs(b))
    if escala < 1e-9:
        return abs(a - b) < 1e-9
    if escala < 1.0:
        # Abaixo de 1 a relativa fica dura demais para o arredondamento do
        # datasheet (0,05 vs 0,0498). 1% de 1 é o piso.
        return abs(a - b) <= 0.01
    return abs(a - b) / escala <= TOLERANCIA_RELATIVA


def conferir_conversao(valor, unidade, contexto):
    """A medida `valor unidade` é conversão CORRETA de algo do contexto?

    Devolve a explicação (`"350 bar"`) quando bate, `None` quando não.
    Refazer a conta é o ponto: não se confia no cálculo da IA, recalcula-se a
    partir do número que está escrito no documento.
    """
    alvo_base, grandeza = _para_base(valor, unidade)
    if alvo_base is None:
        return None

    for valor_ctx, unidade_ctx in extrair_medidas(contexto):
        base_ctx, grandeza_ctx = _para_base(valor_ctx, unidade_ctx)
        if grandeza_ctx != grandeza or base_ctx is None:
            continue
        # Compara NA UNIDADE DA RESPOSTA, não na base — ver `_da_base`.
        esperado = _da_base(base_ctx, unidade)
        if _proximos(valor, esperado):
            return f"{valor_ctx:g} {unidade_ctx}"
    return None


def conferir_texto(texto, contexto):
    """`(tudo_confere, [explicações])` para um valor de campo inteiro.

    Toda medida do texto precisa ser conversão correta de algo do contexto.
    Basta uma não bater para devolver `False` — mesma regra do lastro
    literal: meia verdade num campo técnico é pior que campo vazio.
    """
    medidas = extrair_medidas(texto)
    if not medidas:
        return False, []

    explicacoes = []
    for valor, unidade in medidas:
        origem = conferir_conversao(valor, unidade, contexto)
        if origem is None:
            return False, []
        explicacoes.append(f"{valor:g} {unidade} = {origem}")
    return True, explicacoes

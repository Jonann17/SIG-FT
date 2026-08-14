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
        "psi": 6894.757, "psig": 6894.757, "atm": 101325.0,
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


# `2.500` é 2,5 num datasheet em inglês e 2500 num documento em português.
# Casa `1.234`, `12,345`: separador seguido de EXATAMENTE 3 dígitos.
_RE_AMBIGUO_MILHAR = re.compile(r"^[+-]?\d{1,3}[.,]\d{3}$")


def leituras(bruto):
    """Todos os valores que um número escrito assim pode significar.

    Quase sempre um só. Dois quando há ambiguidade de separador de milhar:
    `2.500` vale 2,5 (leitura inglesa) **ou** 2500 (leitura brasileira), e o
    documento é que decide qual. Devolver as duas e deixar o casamento
    escolher é mais honesto que adivinhar — e adivinhar errado aqui é um erro
    de **mil vezes**, que passa despercebido justamente por ser grande demais
    para parecer erro de digitação.
    """
    texto = str(bruto or "").strip()
    principal = _numero(texto)
    if principal is None:
        return []
    if not _RE_AMBIGUO_MILHAR.match(texto):
        return [principal]
    sem_separador = _numero(re.sub(r"[.,]", "", texto))
    if sem_separador is None or sem_separador == principal:
        return [principal]
    return [principal, sem_separador]


# O que pode existir ENTRE os dois números de um intervalo, e nada mais:
# `0 a +70 C`, `0 to +70 C`, `0...70`, `0 bis 70`, `-20 até +70`.
_RE_CONECTOR_INTERVALO = re.compile(
    r"^\s{0,3}(?:a|ate|to|e|and|bis|hasta|y|und|-|–|\.{2,3}|/)?\s{0,3}$"
)

_RE_NUMERO_SOLTO = re.compile(r"[+-]?\d+(?:[.,]\d+)?")
# Ate 6 letras, e nao 3. Achado na varredura de 2026-08-13: `2,05 kgfm` num
# datasheet brasileiro de motor era INVISIVEL -- `kgfm` tem 4 letras e o
# limite era 3, entao o torque nunca chegava a ser validado nem corrigido.
# Mesmo caso de `psig`, `mbar` e `min-1`. Ampliar o regex e seguro porque
# `_unidade_valida` so aceita o que esta na tabela: o que entra a mais aqui
# e descartado logo depois.
_RE_UNIDADE_ADIANTE = re.compile(
    r"^\s*(kgf/cm[²2]|kgf\.?m|°?[a-zµ]{1,6}(?:[./-][a-z0-9]{1,4})?|\")", re.IGNORECASE
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
    for indice, m in enumerate(_RE_NUMERO_SOLTO.finditer(normalizado)):
        candidatos = leituras(m.group())
        if not candidatos:
            continue
        adiante = _RE_UNIDADE_ADIANTE.match(normalizado[m.end():])
        unidade = _unidade_valida(adiante.group(1)) if adiante else None
        for valor in candidatos:
            # Cada leitura possível vira uma entrada; `indice` amarra as que
            # vieram do MESMO número escrito, para `conferir_texto` tratá-las
            # como alternativas (OU) e não como exigências (E).
            brutos.append([valor, unidade, m.start(), m.end(), indice])

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

    return [(valor, unidade) for valor, unidade, _i, _f, _n in brutos if unidade is not None]


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


def _medidas_agrupadas(texto):
    """`{indice_do_numero_escrito: [(valor, unidade), ...]}`.

    O agrupamento é o que faz `2.500 mm` ser tratado como "2,5 OU 2500", em
    vez de "2,5 E 2500" — que nunca poderia ser satisfeito.
    """
    grupos = {}
    normalizado = _normalizar(texto)
    brutos = []
    for indice, m in enumerate(_RE_NUMERO_SOLTO.finditer(normalizado)):
        for valor in leituras(m.group()):
            adiante = _RE_UNIDADE_ADIANTE.match(normalizado[m.end():])
            brutos.append((indice, valor, _unidade_valida(adiante.group(1)) if adiante else None))
    # Reaproveita a herança de unidade já resolvida por `extrair_medidas`.
    unidades = {u for _v, u in extrair_medidas(texto)}
    unidade_unica = next(iter(unidades)) if len(unidades) == 1 else None
    for indice, valor, unidade in brutos:
        efetiva = unidade or unidade_unica
        if efetiva is None:
            continue
        grupos.setdefault(indice, []).append((valor, efetiva))
    return grupos


# Quantos algarismos significativos manter no valor recalculado.
#
# Decisão do usuário em 2026-08-13: **preferir a informação mais completa**.
# A versão anterior arredondava pela precisão da fonte (`41 kg` -> `90,4 lb`),
# pelo argumento de não inventar exatidão. O usuário decidiu o contrário, e a
# decisão se defende: arredondar DESCARTA informação, e quem lê a ficha pode
# arredondar depois — o caminho inverso é impossível.
#
# 10 algarismos existe só para matar o ruído de ponto flutuante
# (`90.38950000000001`), não para limitar a precisão real.
ALGARISMOS_MAXIMOS = 10


def _formatar(valor):
    """Número no formato da planilha: vírgula decimal, sem ruído de float."""
    if valor == 0:
        return "0"
    import math

    expoente = math.floor(math.log10(abs(valor)))
    arredondado = round(valor, ALGARISMOS_MAXIMOS - 1 - expoente)
    if arredondado == int(arredondado):
        return str(int(arredondado))
    return repr(arredondado).replace(".", ",")


# Fim de frase que NÃO é ponto decimal nem separador de milhar: o `.` de
# `25.4` e o `,` de `41,5` têm dígito dos dois lados e não separam nada.
_RE_FIM_DE_FRASE = re.compile(r"(?<!\d)[.;:\n\r|](?!\d)")


def _medidas_com_janela(contexto):
    """`[(valor, unidade, frase_em_que_a_medida_aparece)]`.

    A frase é o que permite responder "qual das duas pressões?": no
    documento, `350 bar` está em "Maximum **operating** pressure" e `210 bar`
    em "**Peak** pressure". A pergunta da ficha diz "pressão de **trabalho**",
    e o glossário multilíngue já sabe que `trabalho` vale `operating`.

    **FRASE, e não uma janela de N caracteres.** A primeira versão pegava 90
    caracteres para trás, e com isso as duas medidas enxergavam a palavra
    `operating` — as duas pontuavam igual e o desempate nunca acontecia. O
    limite tem de ser semântico, não métrico.
    """
    normalizado = _normalizar(contexto)
    cortes = [0] + [m.end() for m in _RE_FIM_DE_FRASE.finditer(normalizado)] + [len(normalizado)]

    def _frase(posicao):
        for i in range(len(cortes) - 1):
            if cortes[i] <= posicao < cortes[i + 1]:
                return normalizado[cortes[i]:cortes[i + 1]]
        return normalizado

    saida = []
    for m in _RE_NUMERO_SOLTO.finditer(normalizado):
        adiante = _RE_UNIDADE_ADIANTE.match(normalizado[m.end():])
        unidade = _unidade_valida(adiante.group(1)) if adiante else None
        if unidade is None:
            continue
        frase = _frase(m.start())
        for valor in leituras(m.group()):
            saida.append((valor, unidade, frase))
    return saida


def _pontuar_pela_pergunta(trecho, pergunta):
    """Quantos termos da pergunta aparecem no trecho ao redor da medida.

    Usa a MESMA expansão multilíngue do retrieval (`autospec_rag`), que já
    sabe que `trabalho` vale `working`/`operating`/`betriebs`. Não há
    vocabulário novo a manter: é o glossário que já existe, aplicado a uma
    segunda pergunta.
    """
    if not pergunta:
        return 0
    try:
        from sigft.services.autospec_rag import expandir_consulta, tokenizar
    except ImportError:
        return 0
    alvo = set(tokenizar(trecho))
    # `set` na consulta expandida para um termo repetido não pesar duas vezes.
    return sum(1 for termo in set(expandir_consulta(pergunta)) if termo in alvo)


def corrigir_conversao(texto, contexto, pergunta=None):
    """Refaz a conta que a IA errou e devolve `(valor_corrigido, explicação)`.

    Pedido do usuário em 2026-08-13: quando a IA converte errado, o dado de
    origem é REAL — o que está errado é só a aritmética, e aritmética é o que
    um computador faz sem errar. Descartar joga fora informação boa.

    **Só corrige quando não há dúvida sobre a origem.** Se o documento tem uma
    única medida daquela grandeza, ela é a origem e a conta é determinística.
    Se tem várias (`350 bar` de trabalho e `210 bar` de pico), o erro deixa de
    ser aritmético e passa a ser de LEITURA — qual das duas o campo pedia? Aí
    o código não tem como saber, e chutar seria trocar um erro visível por um
    invisível. Nesse caso devolve `(None, motivo)` e o campo fica vazio.

    Não usa IA de propósito. Perguntar ao modelo "está certo?" convida a
    concordância; e a conta em si é exatamente o que ele já errou uma vez.
    """
    grupos = _medidas_agrupadas(texto)
    if not grupos:
        return None, "nao ha medida para recalcular"

    medidas_ctx = _medidas_com_janela(contexto)
    corrigido = str(texto)
    explicacoes = []

    for _indice, alternativas in sorted(grupos.items()):
        valor, unidade = alternativas[0]
        if conferir_conversao(valor, unidade, contexto) is not None:
            continue  # esta medida já estava certa

        _base, grandeza = _para_base(valor, unidade)
        if grandeza is None:
            return None, f"unidade desconhecida: {unidade}"

        candidatos = []
        for valor_ctx, unidade_ctx, trecho in medidas_ctx:
            # SÓ corrige quando há de fato uma CONVERSÃO — unidades
            # diferentes. Se a resposta está na mesma unidade do documento e
            # o número não bate, não houve erro de conta: o número está
            # simplesmente errado, e "corrigi-lo" seria inventar o valor.
            #
            # Bug real, achado na varredura de 2026-08-13: a IA respondeu
            # `0 bar` e o código devolvia `350 bar`. Nenhuma aritmética leva
            # de 0 a 350 — aquilo era um palpite ruim virando dado.
            if _normalizar(unidade_ctx) == _normalizar(unidade):
                continue
            base_ctx, grandeza_ctx = _para_base(valor_ctx, unidade_ctx)
            if grandeza_ctx == grandeza and base_ctx is not None:
                certo = _da_base(base_ctx, unidade)
                if certo is not None and not any(_proximos(certo, c[0]) for c in candidatos):
                    candidatos.append(
                        (certo, f"{valor_ctx:g} {unidade_ctx}",
                         _pontuar_pela_pergunta(trecho, pergunta))
                    )

        if not candidatos:
            return None, f"o documento nao tem nenhuma medida de {grandeza}"

        if len(candidatos) > 1:
            # DESEMPATE PELA PERGUNTA (2026-08-13, pedido do usuário).
            #
            # Duas pressões no documento não é motivo para descartar: o campo
            # DIZ qual quer. "6 - PRESSAO DE TRABALHO" casa com "Maximum
            # OPERATING pressure" e não com "PEAK pressure" — e o glossário
            # multilíngue do retrieval já sabe que `trabalho` vale
            # `operating`. Só desiste quando a pergunta não desempata, que é
            # quando escolher seria chute.
            candidatos.sort(key=lambda c: -c[2])
            melhor, segundo = candidatos[0], candidatos[1]
            if melhor[2] == 0 or melhor[2] == segundo[2]:
                opcoes = ", ".join(origem for _c, origem, _p in candidatos[:4])
                return None, (
                    f"o documento tem {len(candidatos)} medidas de {grandeza} ({opcoes}) e o "
                    f"enunciado do campo nao diz qual — preencha a mao"
                )
            candidatos = [melhor]

        certo, origem, _pontos = candidatos[0]
        texto_certo = _formatar(certo)
        corrigido = re.sub(
            rf"(?<![\d.,]){re.escape(f'{valor:g}'.replace('.', ','))}(?![\d.,])",
            texto_certo,
            corrigido.replace(f"{valor:g}", f"{valor:g}".replace(".", ",")),
            count=1,
        )
        if texto_certo not in corrigido:
            return None, "nao consegui reescrever o valor com seguranca"
        explicacoes.append(f"{valor:g} -> {texto_certo} {unidade} (de {origem})")

    if not explicacoes:
        return None, "nada a corrigir"
    return corrigido, "; ".join(explicacoes)


def numeros_sem_unidade(texto):
    """Os números do texto que NÃO carregam unidade conhecida.

    Existe para o lastro saber o que ainda precisa ser conferido pelo caminho
    literal: um número com unidade é conferido como MEDIDA (número e unidade
    juntos), um número solto só pode ser conferido por presença.
    """
    com_unidade = {valor for valor, _u in extrair_medidas(texto)}
    soltos = set()
    for m in _RE_NUMERO_SOLTO.finditer(_normalizar(texto)):
        for valor in leituras(m.group()):
            if valor not in com_unidade:
                soltos.add(valor)
    return soltos


def conferir_texto(texto, contexto):
    """`(tudo_confere, [explicações])` para um valor de campo inteiro.

    Todo número escrito precisa ser conversão correta de algo do contexto —
    basta um não bater para devolver `False`, mesma regra do lastro literal:
    meia verdade num campo técnico é pior que campo vazio.

    "Todo NÚMERO ESCRITO", e não "toda medida": um número ambíguo produz duas
    leituras, e basta UMA delas conferir. As leituras são alternativas do
    mesmo número, não números diferentes.
    """
    grupos = _medidas_agrupadas(texto)
    if not grupos:
        return False, []

    explicacoes = []
    for _indice, alternativas in sorted(grupos.items()):
        achou = None
        for valor, unidade in alternativas:
            origem = conferir_conversao(valor, unidade, contexto)
            if origem is not None:
                achou = f"{valor:g} {unidade} = {origem}"
                break
        if achou is None:
            return False, []
        explicacoes.append(achou)
    return True, explicacoes

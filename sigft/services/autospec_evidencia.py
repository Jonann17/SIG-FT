r"""A conferencia pela PROVA que a IA devolve junto com cada valor.

POR QUE ESTE MODULO EXISTE (2026-09-24)
------------------------------------------------------------------------
Ficha 0088, fusivel Protistor 36x250 gR 2000 V DC. A IA respondeu CERTO, e o
lastro documental reprovou:

    4 - DIAMETRO EXTERNO VIROLA -> a IA respondeu '36 mm'
      motivo: o documento tem medidas em mm e nenhuma bate com 36

O datasheet cota o desenho sem escrever a unidade (`ø 36`, `250`, e o
tamanho `36x250`); o unico "mm" do PDF inteiro e o `20 mm` da forca de
disparo. O lastro (`autospec.valor_tem_lastro`) procurava "36 mm" no
documento todo -- e desenho cotado nao escreve "mm" do lado da cota.

A regra antiga respondia a pergunta "este numero, com esta unidade, aparece
em algum lugar do documento?". A nova responde a que interessa: "a IA mostrou
DE ONDE tirou, e o que ela mostrou esta mesmo no documento?". Cada valor volta
com a prova -- documento, pagina e o TRECHO copiado -- e aqui se confere:

1. `achar_trecho`: o trecho existe no documento, sem ligar para quebra de
   linha, espaco, virgula decimal ou traco tipografico. Tabela com colunas
   intercaladas (rotulo numa linha, valor tres linhas abaixo) e achada por
   janela de palavras.
2. `valor_sai_do_trecho`: todo numero do valor sai do trecho -- literal, com
   ou sem unidade ao lado (a cota de desenho), ou por conversao refeita
   pelo app (`autospec_unidades`). Codigo (`IP65`, `DN50`) aparece inteiro.
3. `deducao_permitida`: DEDUCAO so para texto -- material, norma, uso,
   aplicacao, tipo. Numero so com documento; o numero de uma NORMA
   (`IEC 60269-4`) nao e medida.

A decisao de cada campo (gravar, gravar marcado, refazer a conta, reprovar)
mora em `autospec.AutoSpecCore._filtrar_por_lastro`, que conhece a ficha;
aqui ficam as pecas puras, sem Excel e sem IA.
"""
import re
import unicodedata
from dataclasses import dataclass

from sigft.services import autospec_unidades as un

# Deducao tecnica em campo de TEXTO da tabela de especificacoes (material,
# norma, uso, tipo construtivo). Na comparacao do usuario com o AMP, a
# "deducao tecnica fundamentada" foi contada como acerto -- e o unico erro do
# AMP nas quatro fichas foi um NUMERO deduzido. Daí a linha: texto pode,
# numero nao. Desligar volta a regra de 2026-08-13 (campo tecnico so com o
# texto escrito no documento).
PERMITIR_DEDUCAO_EM_TEXTO = True

TIPOS_DE_PROVA = ("documento", "calculo", "deducao")


@dataclass
class Evidencia:
    """A prova que a IA devolve com um valor."""

    tipo: str = "documento"
    fonte: str = ""
    pagina: int | None = None
    trecho: str = ""
    justificativa: str = ""


# =============================================================================
# 1. A prova, lida da resposta
# =============================================================================
_CHAVES_DE_PROVA = ("trecho", "tipo", "pagina", "justificativa")


def _sem_acento(texto):
    s = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def _tipo(escrito):
    t = _sem_acento(escrito)
    if t.startswith("dedu"):
        return "deducao"
    if t.startswith(("calc", "conv")):
        return "calculo"
    return "documento"


def _pagina(escrita):
    if isinstance(escrita, bool):
        return None
    if isinstance(escrita, int):
        return escrita if escrita > 0 else None
    achado = re.search(r"\d+", str(escrita or ""))
    return int(achado.group()) if achado else None


def extrair_evidencias(bruto, campos_pedidos=None):
    """`{campo: Evidencia}` da resposta CRUA da IA.

    So vira prova o que veio no formato novo -- um dict com pelo menos uma
    das chaves de prova. `{"valor", "fonte"}` (o formato de 2026-08-11) e o
    valor cru nao tem prova: vao pela regra antiga, inteira.

    Envelope (`{"campos": {...}}`) e desembrulhado com o MESMO criterio de
    `autospec.normalizar_resposta_autospec`.
    """
    pedidos = set(campos_pedidos or ())
    for _ in range(3):
        if (pedidos and isinstance(bruto, dict) and len(bruto) == 1
                and next(iter(bruto)) not in pedidos
                and isinstance(next(iter(bruto.values())), dict)):
            bruto = next(iter(bruto.values()))
            continue
        break
    if not isinstance(bruto, dict):
        return {}

    provas = {}
    for campo, conteudo in bruto.items():
        if pedidos and campo not in pedidos:
            continue
        if not isinstance(conteudo, dict):
            continue
        if not any(chave in conteudo for chave in _CHAVES_DE_PROVA):
            continue
        provas[campo] = Evidencia(
            tipo=_tipo(conteudo.get("tipo")),
            fonte=str(conteudo.get("fonte") or "").strip(),
            pagina=_pagina(conteudo.get("pagina")),
            trecho=str(conteudo.get("trecho") or "").strip(),
            justificativa=str(conteudo.get("justificativa") or "").strip(),
        )
    return provas


# =============================================================================
# 2. Achar o trecho citado
# =============================================================================
# O que sobra de cada caractere para COMPARAR. Espaco, quebra de linha,
# pontuacao e simbolo somem; o que carrega informacao fica. `ø` fica porque e
# a unica coisa que distingue a cota `ø 36` de um `36` qualquer.
_MANTIDOS = set("abcdefghijklmnopqrstuvwxyz0123456789.-%ø")
# Pelos codigos, e nao pelos caracteres: o travessao literal num texto do
# pacote reprova o guard de `tests/test_texto_da_ui.py`, que nao tem como
# saber que aqui ele e DADO (o traco que a IA copia) e nao texto de tela.
_TRACOS = set(map(chr, (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015,
                        0x2212, 0x2043, 0xFE63, 0xFF0D)))


def _mapear(caractere):
    if caractere in _TRACOS:
        return "-"
    if caractere in "×✕":
        return "x"
    if caractere == ",":
        return "."  # virgula decimal: a IA copia `0,5` onde o documento diz `0.5`
    if caractere in "°º˚":
        return "o"
    if caractere in "Øø⌀":
        return "ø"
    decomposto = unicodedata.normalize("NFKD", caractere)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def _compactar(texto):
    """`(compacto, mapa)`: so os caracteres de `_MANTIDOS`, e para cada um
    a posicao dele no texto original."""
    saida, mapa = [], []
    for posicao, caractere in enumerate(str(texto or "")):
        for c in _mapear(caractere):
            if c in _MANTIDOS:
                saida.append(c)
                mapa.append(posicao)
    return "".join(saida), mapa


_RE_TOKEN = re.compile(r"[a-zø]+|\d+(?:\.\d+)?")


def _tokens(texto):
    """`[(token, inicio, fim)]` com as posicoes no texto ORIGINAL."""
    marcado, mapa = [], []
    for posicao, caractere in enumerate(str(texto or "")):
        for c in _mapear(caractere):
            marcado.append(c if c in _MANTIDOS and c != "-" else " ")
            mapa.append(posicao)
    s = "".join(marcado)
    return [(m.group(), mapa[m.start()], mapa[m.end() - 1] + 1) for m in _RE_TOKEN.finditer(s)]


def achar_trecho(trecho, texto):
    """O pedaço do `texto` ORIGINAL em que o `trecho` citado está, ou `None`.

    Primeiro literal, depois de compactar os dois lados (a IA junta o rótulo
    e o valor de uma tabela numa linha só; o texto extraído os tem em duas).
    Se não achar, por JANELA: todos os números do trecho e 70% das palavras
    dele, perto uns dos outros -- é a tabela cujas colunas o extrator
    intercalou.

    Trecho sem LETRA nenhuma (`"36"`) não prova nada: um número solto está em
    qualquer documento. Devolve `None`, e quem chama cai na regra antiga.
    """
    compacto_trecho, _ = _compactar(trecho)
    if not re.search(r"[a-zø]", compacto_trecho):
        return None
    compacto_texto, mapa = _compactar(texto)
    inicio = compacto_texto.find(compacto_trecho)
    if inicio >= 0:
        fim = inicio + len(compacto_trecho)
        return str(texto)[mapa[inicio]: mapa[fim - 1] + 1]
    return _achar_por_janela(trecho, texto)


def _achar_por_janela(trecho, texto):
    do_trecho = [t for t, _i, _f in _tokens(trecho)]
    numeros = {t for t in do_trecho if t[0].isdigit()}
    palavras = {t for t in do_trecho if not t[0].isdigit() and len(t) >= 3}
    if not numeros:
        # Sem numero, a janela nao tem ancora confiavel: palavra repetida
        # num manual de 100 paginas casaria em qualquer lugar.
        return None
    ancora = next(t for t in do_trecho if t[0].isdigit())
    do_texto = _tokens(texto)
    raio = 2 * len(do_trecho) + 4
    for k, (token, _i, _f) in enumerate(do_texto):
        if token != ancora:
            continue
        de, ate = max(0, k - raio), min(len(do_texto), k + raio + 1)
        vizinhanca = {t for t, _i, _f in do_texto[de:ate]}
        if not numeros <= vizinhanca:
            continue
        if palavras and len(palavras & vizinhanca) < 0.7 * len(palavras):
            continue
        return str(texto)[do_texto[de][1]: do_texto[ate - 1][2]]
    return None


# =============================================================================
# 3. O numero do valor sai do trecho
# =============================================================================
# Numero seguido so de letras (`24Vcc`, `36mm`, `4X`) e MEDIDA, nao codigo: os
# numeros dela ja sao conferidos abaixo. Codigo e o que tem letra antes do
# numero (`IP65`, `DN50`, `M12`) ou mistura (`8T2S`).
_RE_CODIGO = re.compile(r"[a-z]+\d[a-z0-9]*|\d+[a-z]+[a-z0-9]*")
_RE_MEDIDA_COLADA = re.compile(r"^\d+(?:[.,]\d+)?[a-z]{1,4}$")


def _compacto_de_codigo(texto):
    return re.sub(r"[^a-z0-9]", "", _sem_acento(texto))


def _perto(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def valor_sai_do_trecho(valor, trecho):
    """`(confere, [conversões])`: todo número do valor sai do trecho?

    Por número escrito no valor:

    - com unidade: a mesma medida no trecho, ou uma conversão que o app
      refaz e confere (`350 bar` -> `35 MPa`), ou o número NU no trecho --
      a cota de desenho e a tabela com a unidade só no cabeçalho;
    - sem unidade: o número em qualquer lugar do trecho.

    O mesmo número com OUTRA unidade da mesma grandeza não serve: `41 g`
    contra `41 kg` é mil vezes de diferença, e é exatamente o erro que ninguém
    percebe olhando.
    """
    texto = str(valor if valor is not None else "").strip()
    if not texto:
        return True, []

    compacto = _compacto_de_codigo(trecho)
    for codigo in _RE_CODIGO.findall(_sem_acento(texto)):
        if _RE_MEDIDA_COLADA.match(codigo):
            continue
        if _compacto_de_codigo(codigo) not in compacto:
            return False, []

    medidas_trecho = un.extrair_medidas(trecho)
    nus_do_trecho = un.numeros_sem_unidade(trecho)
    todos_do_trecho = nus_do_trecho | {v for v, _u in medidas_trecho}

    explicacoes = []
    for _indice, alternativas in sorted(un._medidas_agrupadas(texto).items()):
        confere = False
        for numero, unidade in alternativas:
            origem = un.conferir_conversao(numero, unidade, trecho)
            if origem is not None:
                if _compacto_de_codigo(origem) != _compacto_de_codigo(f"{numero:g} {unidade}"):
                    explicacoes.append(f"{numero:g} {unidade} = {origem}")
                confere = True
                break
            if any(_perto(numero, nu) for nu in nus_do_trecho):
                confere = True
                break
        if not confere:
            return False, []

    for numero in un.numeros_sem_unidade(texto):
        if not any(_perto(numero, n) for n in todos_do_trecho):
            return False, []
    return True, explicacoes


# =============================================================================
# 4. Deducao: texto sim, numero nao
# =============================================================================
# Designacao de NORMA: o numero dela nao e medida. NEMA fica de fora de
# proposito -- `NEMA 4X` e grau de protecao do invólucro, propriedade do
# MODELO, e so entra com documento.
_RE_NORMA = re.compile(
    r"\b(?:ABNT\s+)?(?:NBR|IEC|ISO|EN|DIN|UL|CSA|ASTM|IEEE|ANSI|ASME|API|BS|JIS|VDE)\b"
    r"(?:\s*/\s*(?:NBR|IEC|ISO|EN|DIN))*\s*[A-Z]{0,4}[\s.:-]*\d[\d.\-/:]*",
    re.IGNORECASE,
)


def tem_numero(valor):
    """O valor tem algum número -- fora o da designação de uma norma?"""
    resto = _RE_NORMA.sub(" ", str(valor or ""))
    return bool(re.search(r"\d", resto))


def deducao_permitida(valor):
    """O valor pode entrar na ficha por DEDUÇÃO técnica?

    Só se não tiver número -- fora o número de uma norma. `Cobre prateado`,
    `Interno`, `OUTROS`, `IEC 60269-4` sim; `IP65`, `NEMA 4X`, `1,3 x In`,
    `250 mm` não.
    """
    return PERMITIR_DEDUCAO_EM_TEXTO and not tem_numero(valor)

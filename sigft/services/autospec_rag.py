r"""
Retrieval para o AutoSpecAI — mandar para a IA só os trechos que interessam.

Acrescentado em 2026-08-11. Até aqui o módulo não fazia RAG: fazia
*context stuffing*. O `retrieve_context` concatenava os documentos INTEIROS
(60.000 caracteres por manual local, 50.000 por documento web) e mandava tudo,
de uma vez, para responder campos que precisam de umas 20 linhas do documento.

    hoje:        ~55.000 tokens/ficha  ->  1000 fichas = US$ 27,50
    com este:     ~3.500 tokens/ficha  ->  1000 fichas = US$  1,80

POR QUE BM25 (LEXICAL) E NÃO EMBEDDING (SEMÂNTICO) COMO PADRÃO
------------------------------------------------------------------------
Contra a intuição, para ESTE domínio a busca lexical costuma ganhar. O que se
procura num datasheet é "peso líquido", "PVF100-4", "IP55", "DN50" — termo
exato, número, código de peça. Embedding é forte em sinônimo e paráfrase, e
notoriamente fraco em identificador alfanumérico: "PVF100-4" e "PVF100-8" caem
quase no mesmo ponto do espaço vetorial, e são peças diferentes.

Além disso, BM25 é Python puro. Embedding local exigiria `torch` (~2 GB) ou um
runtime ONNX — e o SIG-FT instala por `pip` no `.bat` de cada máquina, atrás de
proxy corporativo. Ver `docs/AUTOSPEC_MELHORIAS.md`.

O reforço semântico existe e é OPCIONAL (`autospec_embeddings.py`): quando a
biblioteca está disponível, entra como reordenação híbrida; quando não está, o
BM25 sozinho continua respondendo. Nunca é requisito.

PROVENIÊNCIA SOBREVIVE AO RECORTE
------------------------------------------------------------------------
Cada trecho carrega de qual documento veio. Sem isso, o recorte destruiria a
rastreabilidade campo->fonte conquistada no P-04 — a IA precisa continuar
podendo dizer "tirei do manual_bomba.pdf".
"""
import math
import re
import unicodedata

# Tamanho do trecho, em caracteres. ~1.200 cabe uma tabela de especificação
# inteira sem partir ao meio, que é o erro clássico de chunking em documento
# técnico: metade dos rótulos num trecho e metade dos valores no seguinte.
TAMANHO_TRECHO = 1200

# Sobreposição entre trechos vizinhos. Existe pelo mesmo motivo: um valor que
# caia exatamente na fronteira aparece INTEIRO em pelo menos um dos dois.
SOBREPOSICAO_TRECHO = 200

# Quantos trechos recuperar por campo perguntado. Baixo de propósito: o
# contexto final é a UNIÃO dos trechos de todos os campos, então 3 por campo
# num lote de 25 campos já dá bastante material.
TRECHOS_POR_CAMPO = 3

# Teto do contexto montado, em caracteres. Rede de segurança: mesmo com muitos
# campos, o prompt não volta a ser o monólito de 220.000 caracteres.
TETO_CONTEXTO_CHARS = 24000

# Abaixo deste ganho o recorte é dispensado e o contexto original segue
# inteiro. 0.9 = "só vale recortar se o resultado couber em 90% do tamanho".
# Documento pequeno cabe todo no contexto de qualquer jeito, e recortá-lo só
# acrescenta marcador repetido e embaralha a ordem de leitura -- medido: um
# contexto de 11.302 chars virava 12.171 depois do recorte.
GANHO_MINIMO_PARA_RECORTAR = 0.9

# Quantas vezes mais candidatos o BM25 traz quando há reordenador semântico.
# "Recupera largo, reordena estreito": entregar exatamente os 3 finais ao
# reordenador não lhe daria o que escolher.
FATOR_POOL_REORDENACAO = 4

# Parâmetros canônicos do BM25 (Robertson/Sparck Jones). k1 controla a
# saturação da frequência do termo; b, o peso da normalização por tamanho.
BM25_K1 = 1.5
BM25_B = 0.75

_MARCADOR = re.compile(r"^--- (LOCAL|WEB) DOC: (.+?) ---\s*$", re.MULTILINE)
_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*")


# =============================================================================
# GLOSSÁRIO PT->EN — a ficha pergunta em português, o datasheet responde inglês
# =============================================================================
# Acrescentado em 2026-08-11, DEPOIS de medir. A primeira versão deste módulo
# usava BM25 puro, e a medição contra um datasheet realista mostrou o furo:
#
#   consulta : "6 - PRESSAO DE TRABALHO (Indicar a pressao de trabalho)"
#   secao    : "Maximum operating pressure 175 bar. Peak pressure 210 bar."
#   em comum : NENHUM TOKEN
#
# `pressao` não casa com `pressure`; `temperatura` não casa com `temperature`.
# Dois dos cinco dados testados sumiram do contexto recortado. Pior: `peso`
# "funcionou" por acidente — casou em `kg`, não em `peso`.
#
# Isto é barato de resolver porque as perguntas da ficha são um conjunto
# FECHADO: as mesmas ~25 questões se repetem, variando com o PDM do material.
# Um glossário do vocabulário técnico cobre o caso de forma determinística,
# auditável e sem dependência nenhuma — e continua valendo quando o reforço
# semântico opcional não estiver instalado.
#
# A expansão é ADITIVA: os termos estrangeiros entram JUNTO dos originais,
# nunca no lugar. Código de peça (`PVF100-4`) e unidade (`kg`, `mm`, `bar`)
# seguem casando direto, que é onde o lexical é imbatível.
#
# POR QUE CINCO IDIOMAS, E NÃO SÓ INGLÊS (2026-08-13)
# ---------------------------------------------------------------------------
# O parque gerador de Itaipu não é abastecido por fornecedores de língua
# inglesa. Levantando quem realmente assina os equipamentos:
#
#   ALEMÃO    Voith Hydro (turbinas e reguladores), Siemens (geradores e
#             elétrica), HYDAC, Bosch Rexroth, Andritz, SEW, Festo, FAG.
#             É o idioma mais frequente depois do inglês neste domínio, e
#             muitos catálogos alemães são bilíngues DE/EN — mas as TABELAS,
#             que é onde estão os valores, costumam ficar só em alemão.
#   ESPANHOL  Itaipu é BINACIONAL: o espanhol é idioma oficial da entidade,
#             e a metade paraguaia documenta nele. Somam-se os fornecedores
#             latino-americanos e espanhóis.
#   FRANCÊS   Alstom (turbinas e geradores, hoje GE Hydro), Schneider.
#   ITALIANO  fabricantes de válvulas, bombas e hidráulica.
#
# Os valores são escritos SEM ACENTO de propósito: `tokenizar` normaliza por
# NFKD antes de comparar, então `Länge` no documento vira `lange`, e é assim
# que o glossário precisa guardar o termo para casar.
GLOSSARIO_MULTILINGUE = {
    "pressao": ["pressure", "druck", "presion", "pression", "pressione"],
    "temperatura": ["temperature", "temperatur", "temperatura"],
    "faixa": ["range", "bereich", "rango", "plage", "intervallo", "campo"],
    "peso": ["weight", "gewicht", "poids", "peso"],
    "liquido": ["net", "netto", "neto"],
    "bruto": ["gross", "brutto", "bruto", "brut", "lordo"],
    "dimensao": ["dimension", "size", "abmessung", "masse", "dimensione"],
    "dimensoes": ["dimensions", "size", "abmessungen", "masse", "medidas", "dimensioni"],
    "comprimento": ["length", "lange", "laenge", "longitud", "longueur", "lunghezza"],
    "largura": ["width", "breite", "ancho", "largeur", "larghezza"],
    "altura": ["height", "hohe", "hoehe", "altura", "hauteur", "altezza"],
    "espessura": ["thickness", "dicke", "starke", "espesor", "epaisseur", "spessore"],
    "diametro": ["diameter", "durchmesser", "diametre", "diametro"],
    "interno": ["inner", "inside", "internal", "innen",
               "innere", "interior", "interne", "interno"],
    "externo": ["outer", "outside", "external", "aussen",
               "aeussere", "exterior", "externe", "esterno"],
    "material": ["material", "werkstoff", "materiau", "matiere", "materiale"],
    "dureza": ["hardness", "shore", "harte", "haerte", "durete", "durezza"],
    "componentes": ["components", "parts", "kit",
                   "bauteile", "komponenten", "composants", "componenti"],
    "composicao": ["composition", "assembly", "zusammensetzung", "composicion", "composizione"],
    "aplicacao": ["application", "use", "anwendung", "einsatz", "aplicacion", "applicazione"],
    "tipo": ["type", "typ", "tipo"],
    "construtivo": ["construction", "design", "bauart",
                   "ausfuhrung", "construccion", "costruzione"],
    "normas": ["standard", "standards", "norm", "normen", "normas", "normes", "norme"],
    "norma": ["standard", "norm", "norma"],
    "certificado": ["certificate", "certification", "zertifikat",
                   "zulassung", "certificat", "certificato"],
    "caracteristicas": ["characteristics", "features", "specifications", "specs",
                       "merkmale", "kenndaten", "caracteristicas", "caracteristiques", "caratteristiche"],
    "embalagem": ["packaging", "package", "verpackung", "embalaje", "emballage", "imballaggio"],
    "transporte": ["transport", "shipping", "handling", "versand", "transporte", "trasporto"],
    "armazenamento": ["storage", "lagerung", "almacenamiento", "stockage", "stoccaggio"],
    "preservacao": ["preservation", "storage", "konservierung",
                   "conservacion", "conservation", "conservazione"],
    "limpeza": ["cleaning", "reinigung", "limpieza", "nettoyage", "pulizia"],
    "protecao": ["protection", "enclosure", "rating",
                "schutz", "schutzart", "proteccion", "protezione"],
    "empilhamento": ["stacking", "stapelung", "apilamiento", "empilage", "impilamento"],
    "unidade": ["unit", "einheit", "unidad", "unite", "unita"],
    "fabricante": ["manufacturer", "brand", "hersteller", "fabricant", "produttore"],
    "vedacao": ["seal", "sealing", "gasket", "dichtung",
               "junta", "sello", "joint", "guarnizione"],
    "eixo": ["shaft", "welle", "eje", "arbre", "albero"],
    "rolamento": ["bearing", "lager", "walzlager", "rodamiento", "roulement", "cuscinetto"],
    "tensao": ["voltage", "spannung", "voltaje", "tension", "tensione"],
    "corrente": ["current", "strom", "corriente", "courant", "corrente"],
    "potencia": ["power", "rating", "leistung", "potencia", "puissance", "potenza"],
    "rotacao": ["speed", "rpm", "drehzahl", "revoluciones", "vitesse", "giri"],
    "vazao": ["flow", "durchfluss", "volumenstrom", "caudal", "debit", "portata"],
    "velocidade": ["speed", "geschwindigkeit", "velocidad", "vitesse", "velocita"],
    "torque": ["torque", "drehmoment", "par", "couple", "coppia"],
    "rosca": ["thread", "gewinde", "rosca", "filetage", "filetto"],
    "conexao": ["connection", "port", "anschluss",
               "conexion", "raccordement", "connessione", "attacco"],
    "descarte": ["disposal", "waste", "entsorgung",
                "eliminacion", "desecho", "elimination", "smaltimento"],
    "legislacao": ["regulation", "legislation", "vorschrift",
                  "richtlinie", "legislacion", "reglementation", "normativa"],
    "periculosidade": ["hazard", "hazardous", "gefahr",
                      "gefahrstoff", "peligrosidad", "danger", "pericolosita"],
    "nocivo": ["hazardous", "harmful", "schadlich", "gefahrlich", "nocif", "nocivo"],
    "operacao": ["operating", "operation", "betrieb",
                "funcionamiento", "fonctionnement", "funzionamento"],
    "trabalho": ["working", "operating", "betriebs",
                "arbeits", "trabajo", "service", "esercizio"],
    "maxima": ["maximum", "max", "maximal", "maxima", "maximale", "massima"],
    "minima": ["minimum", "min", "minimal", "minima", "minimale"],
    # --- DISCRIMINANTES (2026-08-13) -------------------------------------
    # Estes não servem só para ACHAR o trecho: servem para distinguir duas
    # medidas da MESMA grandeza no mesmo documento. `pressao de trabalho` e
    # `pressao de pico` casam com o mesmo `pressure`; o que separa as duas é
    # `operating` vs `peak`. Usado por
    # `autospec_unidades.corrigir_conversao` para decidir de qual valor do
    # documento a resposta saiu -- sem isso, o campo era descartado por
    # "ambiguidade" que o enunciado, na verdade, resolvia.
    "pico": ["peak", "spitze", "punta", "pointe", "picco"],
    "ruptura": ["burst", "berstdruck", "rotura", "rupture", "rottura"],
    "teste": ["test", "proof", "prufdruck", "prueba", "essai", "prova"],
    "continuo": ["continuous", "dauer", "continuo", "continu"],
    "intermitente": ["intermittent", "aussetz", "intermitente"],
    "estatico": ["static", "statisch", "estatico", "statique", "statico"],
    "dinamico": ["dynamic", "dynamisch", "dinamico", "dynamique"],
    "entrada": ["inlet", "input", "eingang", "entrada", "entree", "ingresso"],
    "saida": ["outlet", "output", "ausgang", "salida", "sortie", "uscita"],
    "ambiente": ["ambient", "umgebung", "ambiente", "ambiante"],
    "armazenagem": ["storage", "lager", "almacenaje", "stockage"],
    "partida": ["starting", "anlauf", "arranque", "demarrage", "avviamento"],
    "vazio": ["idle", "leerlauf", "vacio", "vide", "vuoto"],
    "plena": ["full", "voll", "plena", "pleine", "piena"],
    "carga": ["load", "last", "carga", "charge", "carico"],
    "nominal": ["nominal", "rated", "nenn", "nennwert", "nominale"],
}


# Nome antigo, de quando o glossario era so PT->EN. Mantido porque o modulo
# e importado por nome em teste e em log.
GLOSSARIO_PT_EN = GLOSSARIO_MULTILINGUE


def expandir_consulta(consulta):
    """Tokens da consulta MAIS os equivalentes em inglês do glossário.

    Aditivo de propósito: o termo original continua valendo. Uma consulta que
    já esteja em inglês, ou que seja só um código de peça, passa intacta.
    """
    tokens = tokenizar(consulta)
    expandido = list(tokens)
    for token in tokens:
        expandido.extend(GLOSSARIO_MULTILINGUE.get(token, ()))
    return expandido


def tokenizar(texto):
    """Tokens comparáveis: sem acento, sem caixa.

    Mantém ponto, hífen e barra DENTRO do token (`pvf100-4`, `1.5/8`, `ip55`)
    — quebrar neles transformaria um código de peça em dois números soltos e
    faria `PVF100-4` casar com qualquer coisa que contenha "4".
    """
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _TOKEN.findall(s.lower())


class Trecho:
    """Um pedaço de documento, com a origem colada nele."""

    def __init__(self, texto, origem, ordem, tipo="LOCAL"):
        self.texto = texto
        self.origem = origem  # nome do arquivo local ou URL
        self.ordem = ordem    # posição no documento; desempate estável
        # "LOCAL" ou "WEB". Preservar isto NÃO é detalhe: a instrução 1 do
        # prompt manda `Priorize "LOCAL DOC"`, e ela só funciona se o
        # marcador reemitido continuar dizendo qual é qual. Recortar o
        # contexto sem carregar o tipo apagaria essa regra em silêncio.
        self.tipo = tipo
        self.tokens = tokenizar(texto)

    @property
    def marcador(self):
        return f"--- {self.tipo} DOC: {self.origem} ---"

    def __repr__(self):  # pragma: no cover - conveniência de depuração
        return f"<Trecho {self.tipo} {self.origem!r} #{self.ordem} {len(self.texto)}c>"


def _quebrar(texto, origem, ordem_inicial=0, tipo="LOCAL"):
    """Fatia um bloco em trechos com sobreposição, preferindo cortar em quebra
    de linha para não partir uma linha de tabela ao meio."""
    trechos = []
    total = len(texto)
    if total == 0:
        return trechos

    inicio = 0
    ordem = ordem_inicial
    while inicio < total:
        fim = min(inicio + TAMANHO_TRECHO, total)
        if fim < total:
            # Recua até a última quebra de linha dentro dos 20% finais do
            # trecho. Se não houver, corta no tamanho cheio mesmo.
            janela = texto.rfind("\n", inicio + int(TAMANHO_TRECHO * 0.8), fim)
            if janela > inicio:
                fim = janela
        pedaco = texto[inicio:fim].strip()
        if pedaco:
            trechos.append(Trecho(pedaco, origem, ordem, tipo=tipo))
            ordem += 1
        if fim >= total:
            break
        inicio = max(fim - SOBREPOSICAO_TRECHO, inicio + 1)
    return trechos


def dividir_em_trechos(contexto):
    """Quebra o contexto montado por `retrieve_context` em trechos, mantendo a
    origem de cada um.

    O contexto vem marcado por `--- LOCAL DOC: nome ---` e
    `--- WEB DOC: titulo ---`; esses marcadores viram o campo `origem`. Texto
    antes de qualquer marcador (não deveria haver) fica com origem
    `"(desconhecida)"` em vez de ser descartado — perder conteúdo em silêncio é
    exatamente o que este módulo existe para evitar.
    """
    texto = str(contexto or "")
    if not texto.strip():
        return []

    marcas = list(_MARCADOR.finditer(texto))
    if not marcas:
        return _quebrar(texto, "(desconhecida)")

    trechos = []
    cabecalho = texto[: marcas[0].start()].strip()
    if cabecalho:
        trechos.extend(_quebrar(cabecalho, "(desconhecida)"))

    for i, marca in enumerate(marcas):
        tipo = marca.group(1).strip().upper()
        origem = marca.group(2).strip()
        inicio = marca.end()
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        trechos.extend(
            _quebrar(texto[inicio:fim], origem, ordem_inicial=len(trechos), tipo=tipo)
        )
    return trechos


class IndiceBM25:
    """Índice BM25 sobre uma lista de `Trecho`. Sem dependência externa."""

    def __init__(self, trechos):
        self.trechos = list(trechos)
        self.n = len(self.trechos)
        self.tam_medio = (
            sum(len(t.tokens) for t in self.trechos) / self.n if self.n else 0.0
        )
        self.freq_doc = {}
        for trecho in self.trechos:
            for token in set(trecho.tokens):
                self.freq_doc[token] = self.freq_doc.get(token, 0) + 1

    def _idf(self, token):
        aparece = self.freq_doc.get(token, 0)
        if not aparece:
            return 0.0
        # IDF do BM25+ (sempre positivo): a variante clássica fica NEGATIVA
        # para termo presente em mais da metade dos documentos, o que aqui
        # penalizaria justamente o vocabulário comum do datasheet.
        return math.log(1 + (self.n - aparece + 0.5) / (aparece + 0.5))

    def pontuar(self, consulta):
        """`[(pontuacao, Trecho), ...]` ordenado do mais relevante ao menos."""
        # Expande com o glossário: a ficha pergunta em português e o datasheet
        # responde em inglês. Ver o bloco GLOSSARIO_PT_EN acima para a medição
        # que mostrou que sem isto dois de cinco dados sumiam do contexto.
        tokens = expandir_consulta(consulta)
        if not tokens or not self.n:
            return []

        resultados = []
        for trecho in self.trechos:
            if not trecho.tokens:
                continue
            tamanho = len(trecho.tokens)
            contagem = {}
            for token in trecho.tokens:
                contagem[token] = contagem.get(token, 0) + 1

            pontos = 0.0
            for token in tokens:
                freq = contagem.get(token, 0)
                if not freq:
                    continue
                denominador = freq + BM25_K1 * (
                    1 - BM25_B + BM25_B * (tamanho / (self.tam_medio or 1))
                )
                pontos += self._idf(token) * (freq * (BM25_K1 + 1)) / denominador
            if pontos > 0:
                resultados.append((pontos, trecho))

        resultados.sort(key=lambda par: (-par[0], par[1].ordem))
        return resultados

    def buscar(self, consulta, limite=TRECHOS_POR_CAMPO):
        return [trecho for _, trecho in self.pontuar(consulta)[:limite]]


def montar_contexto_relevante(
    contexto_completo,
    consultas,
    trechos_por_consulta=TRECHOS_POR_CAMPO,
    teto_chars=TETO_CONTEXTO_CHARS,
    reordenador=None,
):
    """Contexto enxuto: a UNIÃO dos trechos relevantes para cada consulta.

    `consultas` são os enunciados dos campos que faltam — o texto da pergunta
    da ficha ("16 - DIMENSOES (Indicar as dimensões do item...)") já é uma boa
    consulta, sem precisar reescrever nada.

    `reordenador`, quando passado, recebe `(consulta, trechos_candidatos)` e
    devolve os trechos reordenados. É o gancho do reforço semântico opcional
    (`autospec_embeddings.py`) — ausente, o BM25 decide sozinho.

    Devolve `(texto, estatisticas)`. As estatísticas alimentam o log: sem elas,
    o usuário não teria como saber que o contexto foi recortado nem quanto.
    """
    trechos = dividir_em_trechos(contexto_completo)
    estatisticas = {
        "chars_originais": len(str(contexto_completo or "")),
        "trechos_total": len(trechos),
        "trechos_usados": 0,
        "chars_finais": 0,
        "consultas": len(list(consultas) if consultas else []),
        "origens": [],
    }
    if not trechos:
        return "", estatisticas

    lista_consultas = [c for c in (consultas or []) if str(c or "").strip()]
    if not lista_consultas:
        # Sem campo faltante não há o que perguntar; devolver o documento
        # inteiro aqui seria voltar ao problema que este módulo resolve.
        return "", estatisticas

    indice = IndiceBM25(trechos)
    selecionados = {}
    for consulta in lista_consultas:
        if reordenador is None:
            candidatos = indice.buscar(consulta, limite=trechos_por_consulta)
        else:
            # "Recupera largo, reordena estreito": entregar só 3 candidatos ao
            # reordenador não teria serventia — ele precisa de material para
            # escolher. O BM25 traz um pool maior e o reforço semântico corta.
            pool = indice.buscar(
                consulta, limite=trechos_por_consulta * FATOR_POOL_REORDENACAO
            )
            try:
                candidatos = reordenador(consulta, pool) or pool
            except Exception:
                # Reforço semântico é opcional: falhar nele não pode derrubar
                # o retrieval lexical, que é o caminho principal.
                candidatos = pool
            candidatos = candidatos[:trechos_por_consulta]
        for trecho in candidatos:
            selecionados[(trecho.origem, trecho.ordem)] = trecho

    # Ordem de leitura original, não ordem de pontuação: um documento
    # remontado fora de ordem confunde o modelo mais do que ajuda.
    # LOCAL antes de WEB (a instrução 1 do prompt manda priorizar o manual do
    # usuário sobre o que veio da internet), e dentro de cada documento a
    # ordem de leitura original -- remontar fora de ordem confunde o modelo.
    escolhidos = sorted(
        selecionados.values(),
        key=lambda t: (0 if t.tipo == "LOCAL" else 1, t.origem, t.ordem),
    )

    partes = []
    usados = 0
    tamanho = 0
    origens = []
    for trecho in escolhidos:
        bloco = f"{trecho.marcador}\n{trecho.texto}"
        if tamanho + len(bloco) > teto_chars and partes:
            break
        partes.append(bloco)
        tamanho += len(bloco) + 2
        usados += 1
        if trecho.origem not in origens:
            origens.append(trecho.origem)

    texto = "\n\n".join(partes)

    # Recorte que não economiza não vale a pena. Em documento pequeno, quase
    # todos os trechos são selecionados e a repetição do marcador de origem em
    # cada um deixa o resultado MAIOR que o original — medido: 11.302 chars
    # viraram 12.171. Nesse caso o original é melhor: mesmo conteúdo, ordem de
    # leitura intacta, sem marcador repetido.
    originais = estatisticas["chars_originais"]
    if originais and len(texto) >= originais * GANHO_MINIMO_PARA_RECORTAR:
        estatisticas.update(
            trechos_usados=len(trechos),
            chars_finais=originais,
            origens=origens,
            recorte_dispensado=True,
        )
        return str(contexto_completo), estatisticas

    estatisticas.update(
        trechos_usados=usados, chars_finais=len(texto), origens=origens
    )
    return texto, estatisticas


def resumo_estatisticas(estatisticas):
    """Linha de log dizendo quanto do documento foi de fato enviado."""
    originais = estatisticas.get("chars_originais", 0)
    finais = estatisticas.get("chars_finais", 0)
    if not originais:
        return "Contexto vazio — nenhum documento foi lido."
    if estatisticas.get("recorte_dispensado"):
        return (
            f"Contexto pequeno ({originais} chars, "
            f"{estatisticas.get('trechos_total', 0)} trecho(s)) — enviado inteiro; "
            f"recortar nao economizaria."
        )
    reducao = 1 - (finais / originais) if originais else 0
    return (
        f"Contexto recortado: {estatisticas.get('trechos_usados', 0)} de "
        f"{estatisticas.get('trechos_total', 0)} trecho(s), "
        f"{finais} de {originais} chars ({reducao:.0%} a menos enviado a IA); "
        f"origens: {', '.join(estatisticas.get('origens') or []) or '(nenhuma)'}"
    )

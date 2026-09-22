r"""Catálogo de PDMs -- a fonte única de "quais PDMs existem, e o que se sabe
de cada um" para a escolha de PDM do módulo *cria fichas*.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
------------------------------------------------------------------------
Até 2026-09-22, para escolher entre 1193 PDMs, a IA recebia DUAS das 24
colunas da planilha-mestra (`PDMs_SAM-GM_1193.xlsx`): o código e o título.
Tudo o mais era descartado -- inclusive as **18,9 características distintas
por PDM** (média medida no arquivo real; máximo 74), que o app já lia, mas só
depois, para montar o template da ficha
(`services/pdm.processar_arquivo_pdm`).

Isso deixava a IA sem como desempatar os casos que mais aparecem:

  - 178 dos 467 nomes base cobrem mais de um PDM (VALVULA 44x, RELE 40x,
    CONJUNTO 27x);
  - 13 títulos são compartilhados por 2 PDMs, e em 4 desses pares os dois
    estão na MESMA classe FSC -- ali só a característica desempata;
  - a lista plana de 1193 linhas não dizia a classe de ninguém, apesar de o
    próprio código embutir a classe (`PDM.XXXX.YYY`, com XXXX == classe FSC
    em todos os PDMs válidos -- conferido no arquivo real).

O DESENHO
------------------------------------------------------------------------
O catálogo **pré-filtra por item**: um ranqueamento léxico devolve os ~12
candidatos mais plausíveis, com a classe e as características de cada um, e
eles vão ao prompt junto com a lista completa agrupada por classe -- que fica
como REDE. A rede não é luxo: medido contra as descrições reais, uma como
"IE4010 w/ 12GE SFP ... uplink ports" não tem nenhuma palavra que nomeie o
equipamento, e nenhum ranqueamento léxico a alcança.

O ranqueamento pesa cada palavra pela informação que ela carrega (uma palavra
que aparece em muitos PDMs pesa menos -- é o espírito do IDF), e pesa mais
quando o casamento é no nome base ou no modificador do que quando é numa
característica. Nada de embeddings: é lexical, determinístico e explicável,
que é o que permite testar o ranqueamento com asserção em vez de olhômetro.

DUAS ENTRADAS ACEITAS
------------------------------------------------------------------------
1. **A planilha-mestra**, direto como a Itaipu exporta (abas `TEMPLATE_PDM` e
   `GRUPOS_CLASES`) -- é o caminho bom, o único que tem característica.
2. **O formato manipulado** que o usuário entregava antes (abas `PDMs` e
   `Instruções PDMs`) -- sem característica, mas sobe. Quebrar os arquivos
   antigos seria pior do que não ter o sinal novo neles.

NÃO CONFUNDIR com `sigft/core/llm/catalogo.py`, que é o catálogo de *modelos
de IA*.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field


# =============================================================================
# Parâmetros do pré-filtro
# =============================================================================
# Quantos candidatos vão ao prompt por item, e quantas características de
# cada um. Os dois números saem de uma medição, não de gosto: com 15 e 10, um
# lote de 20 itens custava ~17 mil tokens só de candidatos, e o prompt inteiro
# passava dos 33 mil -- 39% acima do que o prompt antigo gastava. Com 12 e 6 o
# lote de 20 fica em ~8,7 mil e o total volta ao patamar de antes (~25 mil),
# agora com classe e característica dentro.
LIMITE_CANDIDATOS = 12

# As características existem para DESEMPATAR, não para descrever. Mandar as
# 74 do pior caso gastaria o contexto inteiro num item; as primeiras já
# separam os irmãos (é por elas que VALVULA ESFERA tem TIPO DE PASSAGEM e
# VALVULA GAVETA tem MATERIAL DA CUNHA).
MAX_CARACTERISTICAS_NO_BLOCO = 6

# Peso por onde a palavra casou. Nome base e modificador são o nome
# ESTRUTURADO do PDM (o padrão de catalogação); característica é sinal de
# apoio, e sozinha não deve promover um PDM da família errada.
PESO_NOME_BASE = 5.0
PESO_MODIFICADOR = 4.0
PESO_TITULO = 3.0
PESO_CARACTERISTICA = 1.0

# Palavras que aparecem em quase toda descrição de fornecedor e não
# discriminam nada. O corte por tamanho (< 3) já mata DE/DA/DO/EM/NA.
STOPWORDS = frozenset({
    "COM", "SEM", "PARA", "POR", "SOB", "SOBRE", "DOS", "DAS", "NAO", "UMA",
    "UNS", "ATE", "SEU", "SUA", "SEUS", "SUAS", "QUE", "OUT", "REF",
    "TIPO", "ITEM", "UNID", "UNIDADE", "PECA", "CONJ", "MARCA", "MODELO",
    "ESPECIFICADA", "NOVO", "NOVA",
})

# Quanto uma palavra do TÍTULO do PDM que NÃO apareceu na descrição custa.
#
# É o que faz `PDM.4320.007 - BOMBA` vencer `PDM.4310.004 - BOMBA VACUO`
# quando a descrição é só "Bomba KSB 123-ABC": a palavra "VACUO" não está na
# descrição, então afirmá-la é invenção. Sem esta penalidade o desempate caía
# na ordem do catálogo, e a ordem do arquivo real põe a BOMBA VACUO primeiro.
PENALIDADE_PALAVRA_NAO_CASADA = 0.25

# Glossário EN -> PT/ES, restrito a substantivos de EQUIPAMENTO.
#
# Por que existe: o catálogo da Itaipu é PT/ES e as descrições de fornecedor
# chegam em inglês. Medido em 2026-09-22 contra as 8 descrições dos exemplos
# do próprio prompt: "5 ft LOW LOSS CABLE ASSEMBLY" não achava `CABO`, e
# QUATRO das 8 devolviam lista vazia.
#
# É deliberadamente curto e só de substantivo: adjetivo e verbo traduzidos
# geram falso positivo (o "SEAL" de "sealed" viraria VEDACAO). Sigla de 2
# letras entra aqui porque o corte por tamanho do `tokenizar` a descartaria.
#
# NOTA DE FRONTEIRA: `services/autospec_rag.py` (frente do Rafael) tem um
# glossário multilíngue próprio, para outro fim -- casar DOCUMENTO com ficha,
# não descrição com PDM. Importar de lá acoplaria este módulo a uma zona
# reservada; a duplicação está registrada em `docs/refatoracao/PENDENCIAS.md`
# para ser unificada quando as duas frentes fecharem.
GLOSSARIO = {
    "AP": "ACCESS POINT",
    "BALL": "ESFERA",
    "BEARING": "ROLAMENTO",
    "BOARD": "PLACA",
    "BOLT": "PARAFUSO",
    "BREAKER": "DISJUNTOR",
    "BUSHING": "BUCHA",
    "CABLE": "CABO",
    "COIL": "BOBINA",
    "CONNECTOR": "CONECTOR",
    "CONTACTOR": "CONTATOR",
    "COUPLING": "ACOPLAMENTO",
    "FAN": "VENTILADOR",
    "FILTER": "FILTRO",
    "FUSE": "FUSIVEL",
    "GASKET": "JUNTA",
    "GAUGE": "MANOMETRO",
    "GEAR": "ENGRENAGEM",
    "HOSE": "MANGUEIRA",
    "LAMP": "LAMPADA",
    "NUT": "PORCA",
    "PANEL": "PAINEL",
    "PIPE": "TUBO",
    "PUMP": "BOMBA",
    "RELAY": "RELE",
    "RING": "ANEL",
    "SCREW": "PARAFUSO",
    "SEAL": "VEDACAO",
    "SERVER": "SERVIDOR",
    "SHAFT": "EIXO",
    "SPRING": "MOLA",
    "SWITCHGEAR": "PAINEL",
    "TRANSDUCER": "TRANSDUTOR",
    "TRANSFORMER": "TRANSFORMADOR",
    "TRANSMITTER": "TRANSMISSOR",
    "TUBE": "TUBO",
    "VALVE": "VALVULA",
    "WASHER": "ARRUELA",
    "WIRE": "FIO",
}

_RE_CODIGO_PDM = re.compile(r"PDM\.(\d{4})\.(\d{3})")
_RE_NAO_ALFANUM = re.compile(r"[^0-9A-Z]+")


def _sem_acento(texto) -> str:
    normalizado = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")


def _singular(token: str) -> str:
    """Plural ingênuo de PT/EN/ES, suficiente para nome de equipamento.

    "CAMERAS" -> "CAMERA" é o caso que obrigou: a descrição real
    "CAMERAS DOME FIZ AXIS P1375-E" não casava o PDM `CAMERA`. Não é
    stemmer: corta só o plural regular, porque cortar mais confunde palavras
    curtas (GAS, VIAS) que são sinal legítimo."""
    if len(token) > 4 and token.endswith("OES"):
        return token[:-3] + "AO"
    if len(token) > 4 and token.endswith("ES"):
        return token[:-2]
    if len(token) > 3 and token.endswith("S"):
        return token[:-1]
    return token


def normalizar(texto) -> str:
    """Caixa alta, sem acento, espaço colapsado. É a forma canônica usada
    para comparar strings de PDM -- e ela NÃO mexe em pontuação de propósito:
    a vírgula de "CABO, TRANSMISSAO DADOS" é exatamente o que o filtro do
    portal não casaria, então ela tem que continuar contando como diferença
    (quem conserta esse caso é `CatalogoPDM.resolver`, pelo código)."""
    return " ".join(_sem_acento(texto).upper().split())


def tokenizar(texto) -> set[str]:
    """Palavras úteis de um texto livre, para o ranqueamento.

    Cada palavra entra na sua forma original E no singular, e uma palavra do
    glossário entra também traduzida -- é o que permite uma descrição em
    inglês, no plural, achar um PDM em português no singular. Expandir na
    ENTRADA (em vez de traduzir o catálogo) mantém o catálogo fiel ao que a
    Itaipu publicou."""
    bruto = _RE_NAO_ALFANUM.split(_sem_acento(texto).upper())
    tokens = set()
    for t in bruto:
        if not t:
            continue
        traducao = GLOSSARIO.get(t)
        if traducao:
            # Sigla curta conhecida ("AP") passa mesmo abaixo do corte de
            # tamanho: o que a descartava era o corte, não a falta de sinal.
            tokens.update(traducao.split())
        if len(t) < 3 or t in STOPWORDS:
            continue
        tokens.add(t)
        singular = _singular(t)
        if singular != t and len(singular) >= 3:
            tokens.add(singular)
            traducao_singular = GLOSSARIO.get(singular)
            if traducao_singular:
                tokens.update(traducao_singular.split())
    return tokens - STOPWORDS


# =============================================================================
# Registros
# =============================================================================
@dataclass(frozen=True)
class PDM:
    """Um PDM do catálogo. No arquivo real ele nasce de N linhas da aba
    `TEMPLATE_PDM` -- uma por característica -- agrupadas pelo código."""

    codigo: str
    classe: str
    titulo: str
    nome_base: str = ""
    modificador: str = ""
    caracteristicas: tuple[str, ...] = ()

    @property
    def completo(self) -> str:
        """A string que vai ser DIGITADA no filtro de PDM do portal
        (`services/cria_fichas.processar_item_individual`). O formato é o
        mesmo que a coluna "PDM COMPLETO" das planilhas antigas trazia, e
        mudá-lo quebraria a busca no portal em silêncio."""
        return f"{self.codigo} - {self.titulo}"


@dataclass(frozen=True)
class ClasseFSC:
    """Uma classe da Federal Supply Classification, com o texto que o manual
    de regras usa para decidir a família do material."""

    numero: str
    descricao: str
    inclui: str = ""
    nao_inclui: str = ""
    notas: str = ""


# =============================================================================
# O catálogo
# =============================================================================
@dataclass
class CatalogoPDM:
    pdms: list[PDM]
    classes: list[ClasseFSC] = field(default_factory=list)

    def __post_init__(self):
        self._por_codigo = {p.codigo: p for p in self.pdms}
        self._por_completo = {normalizar(p.completo): p for p in self.pdms}
        self._classes_por_numero = {c.numero: c for c in self.classes}
        # Índice invertido + peso por palavra, montados uma vez. `_campos`
        # guarda, por PDM, em QUAL campo cada palavra apareceu -- é o que
        # permite pesar "casou no nome base" diferente de "casou numa
        # característica" sem refazer a tokenização a cada consulta.
        self._campos: list[dict[str, float]] = []
        # As palavras do TÍTULO, por PDM -- é sobre elas que a penalidade de
        # palavra não casada age (ver PENALIDADE_PALAVRA_NAO_CASADA).
        self._tokens_do_titulo: list[set[str]] = []
        frequencia: dict[str, int] = {}
        for p in self.pdms:
            pesos: dict[str, float] = {}
            self._tokens_do_titulo.append(tokenizar(p.titulo))
            for texto, peso in (
                (p.nome_base, PESO_NOME_BASE),
                (p.modificador, PESO_MODIFICADOR),
                (p.titulo, PESO_TITULO),
                (" ".join(p.caracteristicas), PESO_CARACTERISTICA),
            ):
                for token in tokenizar(texto):
                    # max: a palavra vale pelo campo MAIS forte em que ela
                    # aparece. Somar contaria duas vezes o token que está no
                    # nome base e repetido no título (quase todos).
                    pesos[token] = max(pesos.get(token, 0.0), peso)
            self._campos.append(pesos)
            for token in pesos:
                frequencia[token] = frequencia.get(token, 0) + 1

        total = max(len(self.pdms), 1)
        self._informacao = {
            token: math.log(1 + total / n) for token, n in frequencia.items()
        }

    def __len__(self) -> int:
        return len(self.pdms)

    # -- pertinência ---------------------------------------------------------
    def contem(self, texto_pdm) -> bool:
        """O PDM escrito assim existe no catálogo? É a guarda que impedia um
        código inventado (ou o título com vírgula a mais) de chegar ao
        portal."""
        return normalizar(texto_pdm) in self._por_completo

    def por_codigo(self, codigo) -> PDM | None:
        return self._por_codigo.get(normalizar(codigo))

    def resolver(self, texto_pdm) -> PDM | None:
        """O PDM canônico correspondente a `texto_pdm`, ou `None`.

        Casa primeiro pelo CÓDIGO, que é a parte que o portal usa para achar
        a ficha: assim um título levemente errado (a vírgula do
        `PDM.6145.011 - CABO, TRANSMISSAO DADOS`, que o prompt ensinou por
        oito meses) é CONSERTADO em vez de derrubar o item. Sem código
        reconhecível -- "NENHUM", texto solto -- devolve `None`."""
        achado = _RE_CODIGO_PDM.search(normalizar(texto_pdm))
        if achado:
            return self._por_codigo.get(achado.group(0))
        return self._por_completo.get(normalizar(texto_pdm))

    # -- pré-filtro ----------------------------------------------------------
    def candidatos(self, texto, limite: int = LIMITE_CANDIDATOS) -> list[PDM]:
        """Os PDMs mais plausíveis para uma descrição de material, do melhor
        para o pior. Só entram os que casaram alguma palavra: devolver
        candidato de pontuação zero seria devolver ruído com aparência de
        sugestão."""
        tokens = tokenizar(texto)
        if not tokens:
            return []

        pontuados = []
        for i, pesos in enumerate(self._campos):
            nota = sum(
                self._informacao.get(token, 0.0) * pesos[token]
                for token in tokens
                if token in pesos
            )
            if nota <= 0:
                continue
            # Cada palavra do título que a descrição NÃO trouxe é uma
            # afirmação a mais que o PDM faz sobre o material -- e que
            # ninguém confirmou. Penalizá-la é o que impede um título
            # específico de vencer o genérico por sorte de ordenação.
            sobrando = len(self._tokens_do_titulo[i] - tokens)
            pontuados.append((nota - sobrando * PENALIDADE_PALAVRA_NAO_CASADA, i))

        # `-nota` primeiro e o índice depois: empate desempata pela ordem do
        # catálogo, para o resultado ser estável entre execuções.
        pontuados.sort(key=lambda par: (-par[0], par[1]))
        return [self.pdms[i] for _nota, i in pontuados[:limite]]

    def buscar(self, texto, limite: int = 50) -> list[PDM]:
        """Busca para uma PESSOA escolher na tela, não para a IA.

        Diferente de `candidatos`, que ranqueia por informação: aqui o que
        importa é achar o que a pessoa está digitando. Casa por pedaço do
        texto (é o que se faz numa caixa de busca) e por código, e completa
        com o ranqueamento quando o pedaço não acha o bastante.

        Existe porque a revisão humana era um campo de texto livre: a pessoa
        tinha que digitar "PDM.4820.004 - VALVULA ESFERA" de cabeça, sem
        busca e sem validação -- e o que ela digitasse ia direto para o
        portal."""
        procurado = normalizar(texto)
        if not procurado:
            return self.pdms[:limite]

        achados = []
        vistos = set()
        for p in self.pdms:
            if procurado in normalizar(p.completo):
                achados.append(p)
                vistos.add(p.codigo)
            if len(achados) >= limite:
                return achados

        for p in self.candidatos(texto, limite=limite):
            if p.codigo not in vistos:
                achados.append(p)
                vistos.add(p.codigo)
            if len(achados) >= limite:
                break
        return achados

    def classes_com_pdm(self) -> list[ClasseFSC]:
        """As classes que têm pelo menos um PDM. No arquivo real são 124 de
        165 -- as outras 41 são armadilha: a IA raciocina até a classe e não
        há PDM nenhum para escolher lá."""
        usadas = {p.classe for p in self.pdms}
        return [c for c in self.classes if c.numero in usadas]

    # -- formatação para o prompt --------------------------------------------
    def lista_por_classe(self) -> str:
        """O catálogo INTEIRO, agrupado por classe FSC, com a descrição da
        classe no cabeçalho de cada grupo.

        Dois papéis num só texto, e é por isso que ele substitui a lista plana
        de hoje **mais** um índice de classes separado (medido: 12,4 mil tokens
        contra 10,4 + 1,6):

        1. **Liga a lista ao manual de regras.** A lista plana não dizia a
           classe de ninguém, apesar de o código embuti-la
           (`PDM.XXXX.YYY`) -- o prompt mandava "ache a classe, depois escolha
           o PDM daquela classe" sem dar como.
        2. **É a rede do pré-filtro.** Medido contra o arquivo real, uma
           descrição como "IE4010 w/ 12GE SFP ... uplink ports" não tem
           NENHUMA palavra que nomeie o equipamento -- só conhecimento de
           mundo sabe que é um switch. Nenhum ranqueamento léxico a alcança,
           e sem a lista inteira no prompt esse item ficaria cego.
        """
        por_classe: dict[str, list[PDM]] = {}
        for p in self.pdms:
            por_classe.setdefault(p.classe, []).append(p)

        partes = []
        for numero in sorted(por_classe):
            classe = self._classes_por_numero.get(numero)
            descricao = f" - {classe.descricao}" if classe else ""
            partes.append(f"## CLASSE {numero}{descricao}")
            partes.extend(
                f"- {p.completo}"
                for p in sorted(por_classe[numero], key=lambda x: x.codigo)
            )
        return "\n".join(partes)

    def manual_de_regras(self, numeros=None) -> str:
        """O manual de regras (INCLUI / NÃO INCLUI / NOTAS por classe).

        `numeros` restringe o manual às classes pedidas -- com candidatos por
        item, só as classes que aparecem entre os candidatos do lote têm
        utilidade, e o manual inteiro custa ~11,5 mil tokens."""
        alvo = self.classes_com_pdm()
        if numeros is not None:
            pedidos = {str(n).strip() for n in numeros}
            alvo = [c for c in alvo if c.numero in pedidos]

        partes = []
        for c in alvo:
            bloco = [f"- CLASSE {c.numero}: {c.descricao}"]
            if c.inclui:
                bloco.append(f"  - Inclui: {c.inclui}")
            if c.nao_inclui:
                bloco.append(f"  - Nao inclui: {c.nao_inclui}")
            if c.notas:
                bloco.append(f"  - Notas: {c.notas}")
            partes.append("\n".join(bloco))
        return "\n".join(partes)

    def bloco_de_candidatos(self, pdms) -> str:
        """Os candidatos de UM item, como o prompt os vê. A classe vai junto
        porque é ela que desempata os títulos repetidos (os dois
        `CAMERA VIDEO`, em 5836 e 6710, têm a MESMA string de PDM completo)."""
        linhas = []
        for p in pdms:
            linhas.append(f"- {p.completo}  [classe {p.classe}]")
            if p.caracteristicas:
                mostradas = p.caracteristicas[:MAX_CARACTERISTICAS_NO_BLOCO]
                linhas.append("    caracteristicas: " + "; ".join(mostradas))
        return "\n".join(linhas)


# =============================================================================
# Leitura de planilha
# =============================================================================
# Colunas da aba TEMPLATE_PDM, 0-based, conferidas contra o
# `PDMs_SAM-GM_1193.xlsx` (linha 6 é o cabeçalho; os dados começam na 7).
_MESTRA_PRIMEIRA_LINHA = 7
_COL_CODIGO = 0
_COL_CLASSE = 1
_COL_TITULO_ES = 2
_COL_TITULO_PT = 3
_COL_BASE_ES = 4
_COL_BASE_PT = 5
_COL_MODIF_ES = 6
_COL_MODIF_PT = 7
_COL_REVISAO = 9
_COL_CARACT_PT = 16

# Colunas da aba GRUPOS_CLASES, 0-based (linha 2 é o cabeçalho).
_CLASSES_PRIMEIRA_LINHA = 3
_COL_CL_NUMERO = 5
_COL_CL_DESC_ES = 6
_COL_CL_DESC_PT = 7
_COL_CL_INCLUI_PT = 9
_COL_CL_NAOINC_PT = 11
_COL_CL_NOTAS_PT = 13


def _txt(valor) -> str:
    if valor is None:
        return ""
    return " ".join(str(valor).split())


def _preferir(*valores) -> str:
    """O primeiro valor não vazio. Usado para cair no espanhol quando a
    coluna PT do arquivo vem vazia -- acontece, e um rótulo em espanhol é
    melhor do que rótulo nenhum."""
    for v in valores:
        texto = _txt(v)
        if texto:
            return texto
    return ""


def _revisao_como_numero(valor) -> float:
    """`"1"` -> 1.0; lixo -> -1.0 (perde para qualquer revisão de verdade).

    Gêmea de `services/tech_specs.revisao_como_numero`, de propósito e não por
    descuido: a de lá opera sobre um `DataFrame` do pandas e mora na camada de
    serviço, e `core/` não pode importar de `services/` sem inverter as
    camadas. A regra é a mesma; a unificação das duas está registrada em
    `docs/refatoracao/PENDENCIAS.md`."""
    texto = str(valor if valor is not None else "").strip().replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return -1.0


def _ler_mestra(wb) -> CatalogoPDM:
    ws = wb["TEMPLATE_PDM"]
    acumulado: dict[str, dict] = {}
    for linha in ws.iter_rows(min_row=_MESTRA_PRIMEIRA_LINHA, values_only=True):
        if not linha:
            continue
        codigo = _txt(linha[_COL_CODIGO]).upper()
        # O descarte que a linha 32661 do arquivo real exige: ela traz
        # `1192.999999999937` na coluna do código -- artefato de float que
        # viraria um PDM falso no catálogo.
        if not _RE_CODIGO_PDM.fullmatch(codigo):
            continue

        registro = acumulado.setdefault(codigo, {"revisao": None,
                                                 "caracts": []})

        # SÓ a revisão vigente, e isso vale para o TÍTULO tanto quanto para as
        # características.
        #
        # O Master guarda uma linha por (PDM, característica, REVISÃO), e 1.023
        # dos 1.194 PDMs do arquivo real têm mais de uma revisão. Nas
        # características, unir revisões traz de volta o que já saiu do PDM (o
        # "lixo de REMOVER" de 2026-08-18; ver PENDENCIAS.md) -- sinal FALSO no
        # desempate entre irmãos.
        #
        # No TÍTULO o dano é pior, e foi o usuário que apontou: o título é a
        # string DIGITADA no filtro de PDM do portal. Título de revisão antiga
        # não filtra nada, e a automação quebra com o PDM CERTO escolhido.
        # Medido no arquivo real: em 47 PDMs a primeira linha não é a vigente, e
        # em 4 deles o título difere -- `PDM.7010.018` é "SERVIDOR CONSOLE" na
        # revisão 0 e **"SERVIDOR"** na vigente (rev 2, 28/02/2025).
        #
        # Por isso os campos de identidade são REESCRITOS quando aparece uma
        # revisão maior, em vez de fixados na primeira linha vista.
        revisao = _revisao_como_numero(_valor(linha, _COL_REVISAO))
        if registro["revisao"] is not None and revisao < registro["revisao"]:
            continue
        if registro["revisao"] is None or revisao > registro["revisao"]:
            registro["revisao"] = revisao
            registro["caracts"] = []
            registro.update(
                classe=_txt(_valor(linha, _COL_CLASSE)),
                titulo=_preferir(_valor(linha, _COL_TITULO_PT),
                                 _valor(linha, _COL_TITULO_ES)),
                base=_preferir(_valor(linha, _COL_BASE_PT),
                               _valor(linha, _COL_BASE_ES)),
                modif=_preferir(_valor(linha, _COL_MODIF_PT),
                                _valor(linha, _COL_MODIF_ES)),
            )

        caract = _txt(_valor(linha, _COL_CARACT_PT))
        if caract and caract not in registro["caracts"]:
            registro["caracts"].append(caract)

    pdms = [
        PDM(
            codigo=codigo,
            # A classe vem da coluna, mas o código a embute -- e em 1193 dos
            # 1194 PDMs do arquivo real as duas concordam. Quando a coluna
            # vem vazia, o código resolve.
            classe=r["classe"] or _RE_CODIGO_PDM.fullmatch(codigo).group(1),
            titulo=r["titulo"],
            nome_base=r["base"],
            modificador=r["modif"],
            caracteristicas=tuple(r["caracts"]),
        )
        for codigo, r in acumulado.items()
    ]
    return CatalogoPDM(pdms=pdms, classes=_ler_classes_mestra(wb))


def _valor(linha, indice):
    return linha[indice] if indice < len(linha) else None


def _ler_classes_mestra(wb) -> list[ClasseFSC]:
    if "GRUPOS_CLASES" not in wb.sheetnames:
        return []
    ws = wb["GRUPOS_CLASES"]
    vistas: dict[str, ClasseFSC] = {}
    for linha in ws.iter_rows(min_row=_CLASSES_PRIMEIRA_LINHA, values_only=True):
        if not linha:
            continue
        numero = _txt(_valor(linha, _COL_CL_NUMERO))
        if not numero or numero in vistas:
            continue
        vistas[numero] = ClasseFSC(
            numero=numero,
            descricao=_preferir(_valor(linha, _COL_CL_DESC_PT),
                                _valor(linha, _COL_CL_DESC_ES)),
            inclui=_txt(_valor(linha, _COL_CL_INCLUI_PT)),
            nao_inclui=_txt(_valor(linha, _COL_CL_NAOINC_PT)),
            notas=_txt(_valor(linha, _COL_CL_NOTAS_PT)),
        )
    return list(vistas.values())


def _chave_de_coluna(nome) -> str:
    """Forma canônica de um NOME DE COLUNA, para casar cabeçalho.

    Diferente de `normalizar`, esta apaga a pontuação -- e é o `°` de
    "N° CLASSE" que obriga: ele é símbolo (categoria `So`), não acento, então
    `normalizar` o preserva e a busca por "N CLASSE" não achava a coluna. O
    resultado era um manual de regras VAZIO nas planilhas antigas, sem erro
    nenhum: o catálogo subia, só sem as classes."""
    return " ".join(_RE_NAO_ALFANUM.sub(" ", _sem_acento(nome).upper()).split())


def _cabecalho(ws) -> dict[str, int]:
    """Mapa "NOME DA COLUNA" -> índice, lido da primeira linha. Por nome e não
    por posição: as planilhas manipuladas do usuário não têm ordem garantida."""
    for linha in ws.iter_rows(min_row=1, max_row=1, values_only=True):
        return {
            _chave_de_coluna(v): i
            for i, v in enumerate(linha)
            if v is not None
        }
    return {}


def _ler_manipulada(wb) -> CatalogoPDM:
    """O formato que o usuário entregava antes: aba `PDMs` com a coluna
    "PDM COMPLETO" e aba `Instruções PDMs` com o manual. Não tem
    característica -- o pré-filtro segue funcionando, só com menos sinal."""
    ws = wb["PDMs"]
    colunas = _cabecalho(ws)
    idx = colunas.get("PDM COMPLETO")
    if idx is None:
        raise ValueError(
            'A aba "PDMs" nao tem a coluna "PDM COMPLETO". Entregue a '
            "planilha-mestra da Itaipu (abas TEMPLATE_PDM e GRUPOS_CLASES)."
        )

    pdms = []
    vistos = set()
    for linha in ws.iter_rows(min_row=2, values_only=True):
        completo = _txt(_valor(linha, idx))
        achado = _RE_CODIGO_PDM.search(completo.upper())
        if not achado or achado.group(0) in vistos:
            continue
        vistos.add(achado.group(0))
        titulo = completo[achado.end():].lstrip(" -").strip()
        palavras = titulo.split()
        pdms.append(PDM(
            codigo=achado.group(0),
            classe=achado.group(1),
            titulo=titulo,
            nome_base=palavras[0] if palavras else "",
            modificador=" ".join(palavras[1:]),
        ))
    return CatalogoPDM(pdms=pdms, classes=_ler_classes_manipulada(wb))


def _campo(linha, colunas, nome) -> str:
    """Valor de uma coluna pelo NOME do cabeçalho."""
    i = colunas.get(_chave_de_coluna(nome))
    return _txt(_valor(linha, i)) if i is not None else ""


def _ler_classes_manipulada(wb) -> list[ClasseFSC]:
    if "Instruções PDMs" not in wb.sheetnames:
        return []
    ws = wb["Instruções PDMs"]
    colunas = _cabecalho(ws)
    i_num = colunas.get("N CLASSE")
    if i_num is None:
        return []

    vistas: dict[str, ClasseFSC] = {}
    for linha in ws.iter_rows(min_row=2, values_only=True):
        numero = _txt(_valor(linha, i_num))
        if not numero or numero in vistas:
            continue

        vistas[numero] = ClasseFSC(
            numero=numero,
            descricao=_campo(linha, colunas, "CLASSE DESCRICAO PT"),
            inclui=_campo(linha, colunas, "CLASSE INCLUI PT"),
            nao_inclui=_campo(linha, colunas, "CLASSE NAO INCLUI PT"),
            notas=_campo(linha, colunas, "CLASSE NOTAS PT"),
        )
    return list(vistas.values())


def carregar(caminho) -> CatalogoPDM:
    """Lê o catálogo de uma planilha, aceitando a mestra da Itaipu ou o
    formato manipulado antigo. Levanta `ValueError` com o nome da aba
    esperada quando o arquivo não é nem um nem outro."""
    from openpyxl import load_workbook

    wb = load_workbook(caminho, read_only=True, data_only=True)
    try:
        if "TEMPLATE_PDM" in wb.sheetnames:
            return _ler_mestra(wb)
        if "PDMs" in wb.sheetnames:
            return _ler_manipulada(wb)
        raise ValueError(
            "A planilha nao tem a aba TEMPLATE_PDM (planilha-mestra da "
            'Itaipu) nem a aba "PDMs" (formato manipulado). Abas '
            f"encontradas: {', '.join(wb.sheetnames)}."
        )
    finally:
        wb.close()

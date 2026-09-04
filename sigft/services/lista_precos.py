"""Lista de preços — pareamento com a lista de sobressalentes que ela copia.

Ver `docs/superpowers/specs/2026-09-03-lista-precos-followup-design.md`.

A lista de preços é um documento do Aconex que copia o conteúdo da lista de
sobressalentes de um sistema e acrescenta informação de outro processo. Este
módulo responde UMA pergunta: **a que lista de sobressalentes esta lista de
preços se refere, e o código dela ainda é o mesmo?**

O algoritmo, e por que ele não olha o título para achar o par
--------------------------------------------------------------
1. da lista de preços, tira-se o sequencial final (`-01`, `-02`, …) → a RAIZ;
2. procuram-se no histórico TODOS os documentos com aquela raiz, em qualquer
   revisão e com qualquer sequencial;
3. descarta-se o `Tracking ID` da própria lista de preços; o que sobra é a
   família da lista de sobressalentes;
4. pega-se a revisão vigente (`Current`) dessa família;
5. se a raiz do código vigente for outra, **o RDS-PP mudou** — e é isso que o
   alerta aponta.

A primeira versão disto procurava o par entre os documentos com
"SOBRESSALENTES" no título, e errava: uma das listas tem título sem essa
palavra, e era declarada órfã embora existisse, vigente, com a raiz idêntica.
O título serve para saber **qual das famílias é a de preços** (contém "PREÇO"),
nunca para achar o par.

Medido em 2026-09-03 contra o histórico real (86.789 linhas): das 16 listas de
preços vigentes, 15 encontram a sua lista — 12 com o código em dia e 3 com o
RDS-PP mudado. Uma é órfã de verdade: a raiz dela só tem o tracking da própria
lista de preços.

Este módulo não importa pandas nem openpyxl: trabalha sobre uma sequência de
dicionários. É o que o torna testável sem planilha, sem Aconex e sem rede — ao
contrário do resto do PMIB Manager.
"""
from __future__ import annotations

import re

# Colunas do export do Aconex. Os nomes são os que `pmib_manager` já usa.
COL_DOC = "No. do Documento"
COL_TITULO = "Título"
COL_TRACKING = "Tracking ID"
COL_CURRENT = "Current"

# O sequencial que distingue a lista de preços: `-01`, `-02`, … no fim do
# código. Um ou dois dígitos — no histórico real vai até `-02`.
_SEQUENCIAL = re.compile(r"^(.*?)-(\d{1,2})$")

# Desfechos do pareamento.
PAR_ENCONTRADO = "par_encontrado"
RDSPP_MUDOU = "rdspp_mudou"
ORFA = "orfa"

# Textos da coluna ALERTA RDS-PP. Constantes porque a tela filtra por eles.
ALERTA_VAZIO = ""
ALERTA_ATUALIZAR = "Atualizar código Itaipu"
ALERTA_SEM_LISTA = "Sem lista correspondente"


def raiz(codigo: object) -> str:
    """O código sem o sequencial final.

    `#ITA0=A01AAM10&EPB020-02` -> `#ITA0=A01AAM10&EPB020`

    Sem sequencial, devolve o código como veio. É deliberado que isto seja
    aplicado aos DOIS lados do pareamento: há par em que a lista de
    sobressalentes TAMBÉM tem sequencial (`-01`) e a de preços é `-02`. Tirar
    o sequencial só do lado dos preços perderia esse par — foi o que fez o
    pareamento subir de 10 para 11 nos dados reais.
    """
    texto = str(codigo or "").strip()
    achado = _SEQUENCIAL.match(texto)
    return achado.group(1) if achado else texto


def eh_lista_de_precos(titulo: object) -> bool:
    """A lista COM PREÇOS se identifica pelo título, não pelo código.

    O sequencial não decide: as duas podem tê-lo. Só o título separa.
    """
    return "PREÇO" in str(titulo or "").upper()


def eh_de_sobressalentes(titulo: object) -> bool:
    """Título de lista de sobressalentes (com ou sem preços)."""
    return "SOBRESSALENTES" in str(titulo or "").upper()


def _registros_por_raiz(historico) -> dict[str, list[dict]]:
    """Índice `raiz -> linhas`, sobre o histórico INTEIRO.

    Inteiro, e não só as vigentes: quando o RDS-PP muda, o código que a lista
    de preços aponta some das vigentes e só existe como revisão antiga. É
    exatamente ali que ele precisa ser encontrado.
    """
    indice: dict[str, list[dict]] = {}
    for linha in historico:
        indice.setdefault(raiz(linha.get(COL_DOC)), []).append(linha)
    return indice


def _vigente(linhas) -> dict | None:
    for linha in linhas:
        if linha.get(COL_CURRENT) is True:
            return linha
    return None


def _registros_por_tracking(historico) -> dict[object, list[dict]]:
    """Índice `Tracking ID -> linhas`.

    Indispensável, e não conveniência: quando o RDS-PP muda, a revisão vigente
    tem RAIZ DIFERENTE da antiga. Procurá-la entre as linhas da raiz antiga
    nunca a encontraria — foi assim que a primeira versão deste módulo
    classificou como órfãs as 3 listas cujo código havia mudado.

    O tracking é o que atravessa a mudança de código: é a identidade do
    documento no Aconex, e o número não muda quando o RDS-PP muda.
    """
    indice: dict[object, list[dict]] = {}
    for linha in historico:
        indice.setdefault(linha.get(COL_TRACKING), []).append(linha)
    return indice


def parear(lista_de_precos: dict, historico, indice=None, por_tracking=None) -> dict:
    """A que lista de sobressalentes esta lista de preços se refere?

    `lista_de_precos` é a linha do Aconex da lista COM preços. `historico` é a
    sequência de linhas do export inteiro. `indice` é o retorno de
    `_registros_por_raiz`, para não reindexar a cada chamada num lote.

    Devolve um dicionário com:
      `desfecho`      — `PAR_ENCONTRADO`, `RDSPP_MUDOU` ou `ORFA`
      `lista`         — o código da lista de sobressalentes vigente, ou `None`
      `raiz_apontada` — a raiz que a lista de preços carrega hoje
      `alerta`        — o texto para a coluna ALERTA RDS-PP
    """
    if indice is None:
        indice = _registros_por_raiz(historico)
    if por_tracking is None:
        por_tracking = _registros_por_tracking(historico)

    codigo = str(lista_de_precos.get(COL_DOC) or "").strip()
    minha_raiz = raiz(codigo)
    meu_tracking = lista_de_precos.get(COL_TRACKING)

    # Os trackings que aparecem sob esta raiz, tirando o da própria lista de
    # preços. É o passo "pesquisa o XXXXX e acha qualquer um que tenha o
    # tracking ID".
    trackings = []
    for linha in indice.get(minha_raiz, []):
        tracking = linha.get(COL_TRACKING)
        if tracking == meu_tracking or tracking in trackings:
            continue
        trackings.append(tracking)

    if not trackings:
        return {
            "desfecho": ORFA,
            "lista": None,
            "raiz_apontada": minha_raiz,
            "alerta": ALERTA_SEM_LISTA,
        }

    # Para cada tracking, a revisão vigente é procurada no HISTÓRICO INTEIRO
    # daquele tracking -- não entre as linhas da raiz antiga. Quando o RDS-PP
    # muda, a revisão vigente tem outra raiz, e procurá-la sob a raiz velha
    # nunca a acharia.
    melhor = None
    for tracking in trackings:
        atual = _vigente(por_tracking.get(tracking, []))
        if atual is None:
            continue
        if eh_lista_de_precos(atual.get(COL_TITULO)):
            continue
        melhor = atual
        break

    if melhor is None:
        return {
            "desfecho": ORFA,
            "lista": None,
            "raiz_apontada": minha_raiz,
            "alerta": ALERTA_SEM_LISTA,
        }

    codigo_vigente = str(melhor.get(COL_DOC) or "").strip()
    if raiz(codigo_vigente) == minha_raiz:
        return {
            "desfecho": PAR_ENCONTRADO,
            "lista": codigo_vigente,
            "raiz_apontada": minha_raiz,
            "alerta": ALERTA_VAZIO,
        }

    return {
        "desfecho": RDSPP_MUDOU,
        "lista": codigo_vigente,
        "raiz_apontada": minha_raiz,
        "alerta": ALERTA_ATUALIZAR,
    }


def listas_de_precos_vigentes(historico):
    """As listas COM PREÇOS vigentes, na ordem do histórico."""
    return [
        linha
        for linha in historico
        if linha.get(COL_CURRENT) is True
        and eh_de_sobressalentes(linha.get(COL_TITULO))
        and eh_lista_de_precos(linha.get(COL_TITULO))
    ]


def levantar(historico) -> list[dict]:
    """O follow-up inteiro: uma entrada por lista de preços vigente.

    Cada entrada é a linha do Aconex acrescida do resultado do pareamento.
    Indexa o histórico UMA vez — com 86 mil linhas, reindexar por documento
    seria o custo dominante.
    """
    indice = _registros_por_raiz(historico)
    por_tracking = _registros_por_tracking(historico)
    resultado = []
    for precos in listas_de_precos_vigentes(historico):
        par = parear(precos, historico, indice=indice, por_tracking=por_tracking)
        resultado.append({"precos": precos, **par})
    return resultado


def texto_de_observacao(par: dict, hoje: str) -> str | None:
    """A linha que o app ACRESCENTA em OBSERVAÇÕES, ou `None` se não há o que
    dizer.

    O prefixo `[SIG-FT dd/mm]` existe para o usuário distinguir, de relance, o
    que ele escreveu do que o app escreveu — a coluna é dele, e o app só
    acrescenta.
    """
    if par["desfecho"] == RDSPP_MUDOU:
        return (
            f"[SIG-FT {hoje}] a lista mudou de {par['raiz_apontada']} "
            f"para {par['lista']}"
        )
    if par["desfecho"] == ORFA:
        return (
            f"[SIG-FT {hoje}] não achei lista de sobressalentes para esta "
            "lista de preços"
        )
    return None

"""A aba "Atividades" — a hierarquia e os totais das linhas de grupo.

Ver `docs/superpowers/specs/2026-09-03-lista-precos-followup-design.md` (frente
B) e o pedido do usuário em 2026-09-03.

A aba é hierárquica pela coluna `NV`:

    NV=1   linha de GRUPO — tem `CÓDIGO ITAIPU` e os totais
    NV=2   atividade
    NV=3   subatividade

As linhas que têm filhas carregam totais que, na planilha, eram **fórmulas**
(`COUNTIFS`, `MIN`, `MAX`) — 75 delas só nas 30 primeiras linhas. O usuário
decidiu em 2026-09-03: *"o SIG-FT calcula e escreve valor"*. As fórmulas saem,
e o app grava o número pronto a cada atualização.

O que isso ganha e o que custa
-------------------------------
**Ganha:** fórmula não sobrevive a inserção de linha no meio. Cada `COUNTIFS`
referencia um intervalo fixo (`$A22:$A25`); quem acrescentar uma atividade no
lugar errado desloca o intervalo e o total passa a contar as linhas erradas,
sem erro visível. Com o cálculo em Python, o intervalo é derivado da hierarquia
a cada execução e não tem como envelhecer.

**Custa:** a planilha deixa de se atualizar sozinha. Marcar uma atividade como
concluída à mão não muda o total do grupo até o SIG-FT rodar de novo. Era a
troca que o usuário aceitou, e ela está registrada aqui para quem estranhar o
número parado.

As regras saíram das fórmulas reais, não de suposição — inclusive a de
`DATA DE TÉRMINO`, que só preenche quando TODAS as filhas estão concluídas.
"""
from __future__ import annotations

# Colunas da aba, 1-based. Lidas do cabeçalho real em 2026-09-03.
COL_NV = 1
COL_CODIGO_ITAIPU = 2
COL_DESCRICAO = 3
COL_ATIVIDADES = 4
COL_CONCLUIDAS = 5
COL_TRAVADAS = 6
COL_DATA_PREVISTA_INICIO = 7
COL_DATA_INICIO = 8
COL_PREVISAO_TERMINO = 9
COL_DATA_TERMINO = 10
COL_STATUS = 11
COL_ALTERACAO_STATUS = 12
COL_COM_QUEM = 13
COL_DETALHE = 14
COL_CRITICIDADE = 15
COL_CONCLUIDA = 16

LINHA_CABECALHO = 1
STATUS_TRAVADA = "Travada"

# As colunas que o app CALCULA. As demais são do usuário e nunca são tocadas.
COLUNAS_CALCULADAS = (
    COL_ATIVIDADES,
    COL_CONCLUIDAS,
    COL_TRAVADAS,
    COL_DATA_PREVISTA_INICIO,
    COL_DATA_INICIO,
    COL_PREVISAO_TERMINO,
    COL_DATA_TERMINO,
)


def _nivel(linha) -> int | None:
    """O `NV` da linha, ou `None` se não for um número."""
    valor = linha.get("nv")
    if valor is None or valor == "":
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def filhas_diretas(linhas, indice: int) -> list[int]:
    """Os índices das filhas DIRETAS da linha `indice`.

    Filha direta é a de nível N+1 que aparece antes da próxima linha de nível
    <= N. É o que as fórmulas faziam: `COUNTIFS($A22:$A25,2)` na linha 21
    contava, no intervalo até o próximo grupo, só as de nível 2 — não as de
    nível 3.
    """
    meu_nivel = _nivel(linhas[indice])
    if meu_nivel is None:
        return []

    filhas = []
    for i in range(indice + 1, len(linhas)):
        nivel = _nivel(linhas[i])
        if nivel is None:
            continue
        if nivel <= meu_nivel:
            break
        if nivel == meu_nivel + 1:
            filhas.append(i)
    return filhas


def _concluida(linha) -> bool:
    """`CONCLUÍDA` é booleano na planilha; texto e vazio contam como não."""
    valor = linha.get("concluida")
    if isinstance(valor, bool):
        return valor
    return str(valor or "").strip().upper() in {"TRUE", "VERDADEIRO", "SIM", "X"}


def _travada(linha) -> bool:
    return str(linha.get("status") or "").strip().casefold() == STATUS_TRAVADA.casefold()


def _datas(linhas, indices, chave):
    """As datas não vazias das linhas indicadas, TODAS do mesmo tipo.

    ⚠️ Misturar tipos aqui derruba o `min()`/`max()` com
    `TypeError: '<' not supported between 'str' and 'datetime.datetime'` — e
    foi o que aconteceu na primeira execução contra a planilha real: quase toda
    célula é `datetime`, mas alguma traz texto (uma anotação onde devia haver
    data), e o lote inteiro morria por causa de uma célula.

    A coluna é de DATA, então a data é que manda: havendo qualquer `datetime`,
    os valores de outro tipo são descartados. Sem nenhum, cai para o que houver
    — uma coluna só de texto ainda dá um `min` coerente entre textos.
    """
    valores = []
    for i in indices:
        valor = linhas[i].get(chave)
        if valor not in (None, ""):
            valores.append(valor)

    from datetime import date, datetime

    datas = [v for v in valores if isinstance(v, (datetime, date))]
    if datas:
        return datas
    return [v for v in valores if isinstance(v, str)]


def agregar(linhas, indice: int) -> dict | None:
    """Os totais da linha `indice`, ou `None` se ela não tiver filhas.

    Sem filhas, a linha é uma atividade-folha: os totais não se aplicam e
    escrever zeros ali seria pior que deixar como está.
    """
    filhas = filhas_diretas(linhas, indice)
    if not filhas:
        return None

    total = len(filhas)
    concluidas = sum(1 for i in filhas if _concluida(linhas[i]))
    travadas = sum(1 for i in filhas if _travada(linhas[i]))

    previstas = _datas(linhas, filhas, "data_prevista_inicio")
    inicios = _datas(linhas, filhas, "data_inicio")
    previsoes = _datas(linhas, filhas, "previsao_termino")
    terminos = _datas(linhas, filhas, "data_termino")

    # DATA DE TÉRMINO só existe quando TODAS as filhas terminaram. É a regra da
    # fórmula original, e ela importa: um grupo com uma atividade em aberto NÃO
    # tem data de término, e preenchê-la diria que o trabalho acabou.
    if total > 0 and concluidas == total and terminos:
        data_termino = max(terminos)
    else:
        data_termino = ""

    return {
        "atividades": total,
        "concluidas": concluidas,
        "travadas": travadas,
        "data_prevista_inicio": min(previstas) if previstas else "",
        "data_inicio": min(inicios) if inicios else "",
        "previsao_termino": max(previsoes) if previsoes else "",
        "data_termino": data_termino,
    }


def recalcular(linhas) -> dict[int, dict]:
    """`{índice -> totais}` para toda linha que tem filhas."""
    return {
        indice: totais
        for indice in range(len(linhas))
        if (totais := agregar(linhas, indice)) is not None
    }


def linhas_de_grupo(linhas) -> list[int]:
    """Os índices das linhas de nível 1 — as que têm `CÓDIGO ITAIPU`."""
    return [i for i in range(len(linhas)) if _nivel(linhas[i]) == 1]


# =============================================================================
# O mural — o que fazer hoje, e o que vem a seguir
# =============================================================================
# [2026-09-03] Pedido do usuário: *"que ela seja visual, e funcione como um
# apontamento do que é preciso fazer naquele dia, ou o que deveria estar sendo
# feito, e algumas a frente também para que tenhamos uma ideia do que vem a
# seguir"*.
#
# ⚠️ Agrupa por TEMPO, não por status. Uma primeira versão agrupava por status
# (travada / em andamento / não iniciada) e não respondia a pergunta que o
# usuário faz ao abrir: *o que é para fazer hoje?* Status é atributo da
# atividade; urgência é relação entre a data dela e hoje — e é a urgência que
# ordena o dia.
#
# O status não sumiu: aparece dentro do cartão, onde serve de contexto.

STATUS_NAO_INICIADA = "Não iniciada"
STATUS_EM_DESENVOLVIMENTO = "Em desenvolvimento"
STATUS_CONCLUIDA = "Concluída"

# As faixas do mural, na ordem em que aparecem — que é a ordem da urgência.
ATRASADA = "atrasada"
TRAVADA = "travada"
DEVERIA_TER_COMECADO = "deveria_ter_comecado"
EM_ANDAMENTO = "em_andamento"
COMECA_HOJE = "comeca_hoje"
PROXIMOS_DIAS = "proximos_dias"

FAIXAS = (ATRASADA, TRAVADA, DEVERIA_TER_COMECADO, EM_ANDAMENTO, COMECA_HOJE,
          PROXIMOS_DIAS)

# Quantos dias à frente o mural enxerga. Decisão do usuário: 7 — uma semana
# cabe na tela e ainda é acionável.
HORIZONTE_DIAS = 7


def _so_data(valor):
    """A parte de data de um `datetime`, para comparar com `hoje` sem hora."""
    from datetime import date, datetime

    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def esta_concluida(linha) -> bool:
    """Concluída pela caixa OU pelo status.

    ⚠️ As duas colunas DIVERGEM na planilha real: há 2 linhas com
    `STATUS = "Concluída"` e só 1 com `CONCLUÍDA = True`. Exigir as duas
    deixaria uma atividade terminada aparecendo no mural para sempre.
    """
    if _concluida(linha):
        return True
    return str(linha.get("status") or "").strip().casefold() == STATUS_CONCLUIDA.casefold()


def classificar(linha, hoje, horizonte=HORIZONTE_DIAS):
    """`(faixa, dias)` — onde a atividade cai, e a distância em dias.

    `dias` é negativo no passado (atrasada há N dias), 0 hoje, positivo no
    futuro. É ele que a tela usa para escrever "venceu há 4 dias" ou "em 3
    dias" — o dado bruto fica aqui, a frase fica na interface.

    A ordem das checagens é a ordem da urgência: uma atividade atrasada E
    travada aparece como ATRASADA, porque o atraso é o que exige decisão.
    """
    if esta_concluida(linha):
        return None, None

    termino = _so_data(linha.get("previsao_termino"))
    inicio = _so_data(linha.get("data_prevista_inicio"))
    status = str(linha.get("status") or "").strip()
    em_andamento = status.casefold() == STATUS_EM_DESENVOLVIMENTO.casefold()

    # `DATA DE INÍCIO` preenchida é o registro de que a atividade COMEÇOU.
    # Antes só o status "Em desenvolvimento" contava, e a coluna era ignorada
    # — o mural dizia "era para começar há 9 dias" de atividade cuja data de
    # início estava preenchida havia mais de uma semana.
    comecou = _so_data(linha.get("data_inicio")) is not None

    # 0. TRAVADA vence todas as outras faixas.
    #
    # Decisão do usuário: *"os que estão travados já deram início, só estão
    # travados, outra categoria"*. O que impede uma atividade travada de
    # andar não é o calendário — é o bloqueio. Classificá-la pela data dizia
    # "era para começar há 8 dias" de coisa que já começou e parou, o que
    # esconde justamente a informação que pede ação: alguém precisa destravar.
    # O prazo não se perde: vai no `dias`, e a tela o escreve no cartão.
    if _travada(linha):
        return TRAVADA, (termino - hoje).days if termino is not None else None

    # 1. Passou da previsão de término e não terminou.
    if termino is not None and termino < hoje:
        return ATRASADA, (termino - hoje).days

    # 2. Já começou de fato.
    if em_andamento or comecou:
        dias = (termino - hoje).days if termino is not None else None
        return EM_ANDAMENTO, dias

    # 3. Era para ter começado e não começou.
    if inicio is not None and inicio < hoje:
        return DEVERIA_TER_COMECADO, (inicio - hoje).days

    # 4. Começa hoje.
    if inicio is not None and inicio == hoje:
        return COMECA_HOJE, 0

    # 5. O que vem a seguir, dentro do horizonte.
    if inicio is not None and 0 < (inicio - hoje).days <= horizonte:
        return PROXIMOS_DIAS, (inicio - hoje).days

    # (A rede que jogava travada-sem-data em DEVERIA_TER_COMECADO saiu: agora
    # travada tem faixa própria e é decidida lá em cima, com ou sem data.)
    return None, None


def grupo_de(linhas, indice):
    """A descrição do GRUPO (nível 1) a que a linha pertence, ou `None`.

    [2026-09-04] Pedido do usuário: *"para cada atividade deveríamos ter a
    descrição do nível 1 [...] pois eu li a atividade e não sei de qual grupo
    é"*. No mural as atividades vêm reordenadas por PRAZO, então elas chegam
    fora da ordem da planilha — e é a ordem da planilha que dizia, sozinha, a
    que frente cada uma pertencia. Ao reordenar, o mural perdeu essa
    informação sem repor nada no lugar.

    A hierarquia é posicional: o grupo de uma linha é o nível 1 mais próximo
    ACIMA dela. Vale para nível 2 e para nível 3 (a subatividade herda o
    mesmo grupo da atividade-mãe).
    """
    for i in range(indice, -1, -1):
        if _nivel(linhas[i]) == 1:
            return str(linhas[i].get("descricao") or "").strip() or None
    return None


def _criticidade(linha) -> int:
    try:
        return int(linha.get("criticidade") or 0)
    except (TypeError, ValueError):
        return 0


def mural(linhas, hoje, horizonte=HORIZONTE_DIAS) -> dict[str, list[dict]]:
    """As atividades agrupadas por faixa de tempo.

    Cada item é a linha original acrescida de `_faixa` e `_dias`, para a tela
    não precisar reclassificar.

    Só atividades de verdade: linhas de GRUPO (nível 1) e linhas que agregam
    outras ficam de fora — são totalizadores, não trabalho de alguém.

    Dentro de cada faixa: mais urgente primeiro (menor `dias`), e entre
    empatados, maior criticidade.
    """
    gavetas: dict[str, list[dict]] = {faixa: [] for faixa in FAIXAS}

    for indice, linha in enumerate(linhas):
        if _nivel(linha) == 1:
            continue
        if filhas_diretas(linhas, indice):
            continue

        faixa, dias = classificar(linha, hoje, horizonte)
        if faixa is None:
            continue

        item = dict(linha)
        item["_faixa"] = faixa
        item["_dias"] = dias
        item["_grupo"] = grupo_de(linhas, indice)
        item["_termino"] = frase_do_termino(
            linha.get("previsao_termino"), hoje,
            com_contagem=faixa not in FAIXAS_PELO_TERMINO,
        )
        gavetas[faixa].append(item)

    for lista in gavetas.values():
        # `dias` None (sem data) vai para o fim da faixa: sem data não há
        # urgência a comparar, mas a atividade ainda precisa aparecer.
        lista.sort(key=lambda a: (
            a["_dias"] if a["_dias"] is not None else 9999,
            -_criticidade(a),
        ))
    return gavetas


def total_do_mural(gavetas) -> int:
    return sum(len(v) for v in gavetas.values())


# As faixas cuja frase JÁ fala do término. Nelas o cartão não repete a
# contagem de dias — mostra só a data, que é o que faltava.
FAIXAS_PELO_TERMINO = (ATRASADA, TRAVADA, EM_ANDAMENTO)


def frase_do_termino(termino, hoje, com_contagem=True) -> str | None:
    """`"término 11/09/26 · faltam 7 dias"`, ou `None` se não houver data.

    [2026-09-04] Pedido do usuário: *"colocar a data prevista de finalização
    da atividade, assim dá um norte (e quantos dias tem para acabar)"*.

    O cartão só mostrava frases RELATIVAS ("era para começar ontem"), e
    nenhuma delas era sobre o fim: nas faixas de início dava para ler o
    cartão inteiro sem descobrir para quando a atividade é.

    `com_contagem=False` nas faixas cuja frase de prazo já conta os dias —
    repetir o mesmo número duas vezes no mesmo cartão só ocupa espaço.
    """
    dia = _so_data(termino)
    if dia is None:
        return None

    data = dia.strftime("%d/%m/%y")
    if not com_contagem:
        return f"término {data}"

    dias = (dia - hoje).days
    if dias < 0:
        conta = "venceu ontem" if dias == -1 else f"venceu há {abs(dias)} dias"
    elif dias == 0:
        conta = "termina hoje"
    elif dias == 1:
        conta = "falta 1 dia"
    else:
        conta = f"faltam {dias} dias"
    return f"término {data} · {conta}"


def frase_do_prazo(faixa, dias) -> str:
    """Como a tela escreve o prazo. Fica aqui para o texto ser testável."""
    if dias is None:
        return "sem data"
    if faixa == ATRASADA:
        d = abs(dias)
        return "venceu ontem" if d == 1 else f"venceu há {d} dias"
    if faixa == DEVERIA_TER_COMECADO:
        d = abs(dias)
        return "era para começar ontem" if d == 1 else f"era para começar há {d} dias"
    if faixa == COMECA_HOJE:
        return "começa hoje"
    if faixa == PROXIMOS_DIAS:
        return "começa amanhã" if dias == 1 else f"começa em {dias} dias"
    if faixa in (EM_ANDAMENTO, TRAVADA):
        # TRAVADA usa a mesma frase de EM_ANDAMENTO: o rótulo da faixa já diz
        # que está travada, então o cartão aproveita o espaço para o PRAZO.
        if dias < 0:
            return f"previsão venceu há {abs(dias)} dias"
        if dias == 0:
            return "previsão é hoje"
        return f"previsão em {dias} dias"
    return ""

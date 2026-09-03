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

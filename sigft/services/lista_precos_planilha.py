"""A aba "Lista de preços Follow-up" — criar e atualizar.

Ver `docs/superpowers/specs/2026-09-03-lista-precos-followup-design.md`.

Separado de `lista_precos.py` de propósito: lá está a REGRA (qual lista de
sobressalentes cada lista de preços copia), que se prova sem planilha nenhuma;
aqui está a ESCRITA, que precisa de openpyxl. Misturar as duas tornaria a
regra intestável sem Excel — e ela é a parte que erra.

O estilo é o da aba `Acompanhamento Sobressalente`
--------------------------------------------------
Lido da planilha real, não escolhido: fonte Calibri 11 em negrito na cor
`FF002060` (o azul escuro do cabeçalho), fundo de TEMA (índice 3 com tint
0.7998 — é cor de tema, não RGB, e reproduzi-la com um RGB aproximado deixaria
a aba nova visivelmente diferente das outras), bordas média/fina e texto
centralizado com quebra.

⚠️ **Cabeçalho na linha 1**, ao contrário da aba de sobressalentes (linha 2).
Decisão do usuário em 2026-09-03.
"""
from __future__ import annotations

NOME_ABA = "Lista de preços Follow-up"
LINHA_CABECALHO = 1

# As 12 colunas, na ordem. As 8 primeiras seguem a ordem da aba de
# sobressalentes; as 4 últimas são desta aba.
COLUNAS = [
    "N° DOCUMENTO ITAIPU",
    "N° DOCUMENTO CMI",
    "ÚLTIMA REVISÃO EMITIDA",
    "STATUS DA REVISÃO",
    "DATA DE ATUALIZAÇÃO",
    "DESCRIÇÃO",
    "ESPECIFICAÇÃO TÉCNICA",
    "CAPÍTULO",
    "LISTA DE SOBRESSALENTES",
    "ALERTA RDS-PP",
    "AÇÃO",
    "OBSERVAÇÕES",
]

# Colunas que o app escreve. `AÇÃO` e `OBSERVAÇÕES` ficam de fora: são do
# usuário, e sobrescrevê-las apagaria a decisão dele.
COLUNAS_DO_APP = COLUNAS[:10]

# Largura de cada coluna, no espírito da aba de sobressalentes (onde
# `DESCRIÇÃO` é larga porque o título do Aconex é longo).
LARGURAS = {
    "N° DOCUMENTO ITAIPU": 42.5,
    "N° DOCUMENTO CMI": 33.9,
    "ÚLTIMA REVISÃO EMITIDA": 19.4,
    "STATUS DA REVISÃO": 24.9,
    "DATA DE ATUALIZAÇÃO": 19.4,
    "DESCRIÇÃO": 97.9,
    "ESPECIFICAÇÃO TÉCNICA": 47.9,
    "CAPÍTULO": 13.0,
    "LISTA DE SOBRESSALENTES": 42.5,
    "ALERTA RDS-PP": 26.0,
    "AÇÃO": 14.0,
    "OBSERVAÇÕES": 60.0,
}

ALTURA_CABECALHO = 55.5
ALTURA_LINHA = 45.0

# Estilo do cabeçalho, lido da aba de sobressalentes.
COR_FONTE_CABECALHO = "FF002060"
TEMA_FUNDO_CABECALHO = 3
TINT_FUNDO_CABECALHO = 0.7997985778374584


def _estilos():
    """Os objetos de estilo do openpyxl. Import preguiçoso: este módulo é
    importado pelo `pmib_manager`, que roda em ambiente sem openpyxl nos
    testes."""
    from openpyxl.styles import Alignment, Border, Color, Font, PatternFill, Side

    fonte_cab = Font(name="Calibri", size=11, bold=True, color=COR_FONTE_CABECALHO)
    fundo_cab = PatternFill(
        patternType="solid",
        fgColor=Color(theme=TEMA_FUNDO_CABECALHO, tint=TINT_FUNDO_CABECALHO),
    )
    alin_cab = Alignment(horizontal="center", vertical="center", wrap_text=True)
    borda_cab = Border(
        left=Side(style="medium"),
        right=Side(style="thin"),
        top=Side(style="medium"),
        bottom=Side(style="medium"),
    )
    fonte_dado = Font(name="Calibri", size=11)
    alin_dado = Alignment(vertical="center", wrap_text=True)
    borda_dado = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    return {
        "fonte_cab": fonte_cab,
        "fundo_cab": fundo_cab,
        "alin_cab": alin_cab,
        "borda_cab": borda_cab,
        "fonte_dado": fonte_dado,
        "alin_dado": alin_dado,
        "borda_dado": borda_dado,
    }


def criar_aba(wb, nome=NOME_ABA):
    """Cria a aba com o cabeçalho formatado. Devolve a worksheet.

    Se a aba já existir, devolve a existente sem tocar em nada — recriar
    apagaria as colunas `AÇÃO` e `OBSERVAÇÕES`, que são do usuário.
    """
    from openpyxl.utils import get_column_letter

    if nome in wb.sheetnames:
        return wb[nome]

    ws = wb.create_sheet(title=nome)
    est = _estilos()

    for indice, titulo in enumerate(COLUNAS, start=1):
        celula = ws.cell(row=LINHA_CABECALHO, column=indice, value=titulo)
        celula.font = est["fonte_cab"]
        celula.fill = est["fundo_cab"]
        celula.alignment = est["alin_cab"]
        celula.border = est["borda_cab"]
        ws.column_dimensions[get_column_letter(indice)].width = LARGURAS.get(titulo, 20)

    ws.row_dimensions[LINHA_CABECALHO].height = ALTURA_CABECALHO

    # Congela o cabeçalho e liga o filtro: numa aba de follow-up, filtrar por
    # AÇÃO e por ALERTA é o uso principal.
    ws.freeze_panes = f"A{LINHA_CABECALHO + 1}"
    ws.auto_filter.ref = (
        f"A{LINHA_CABECALHO}:"
        f"{get_column_letter(len(COLUNAS))}{LINHA_CABECALHO}"
    )
    return ws


def mapa_de_colunas(ws):
    """`{título -> índice 1-based}` lido do cabeçalho da aba."""
    mapa = {}
    for indice in range(1, ws.max_column + 1):
        valor = ws.cell(row=LINHA_CABECALHO, column=indice).value
        if valor:
            mapa[str(valor).strip()] = indice
    return mapa


def linha_por_documento(ws, colunas):
    """`{código Itaipu -> número da linha}` das linhas já na aba."""
    coluna_doc = colunas.get("N° DOCUMENTO ITAIPU")
    if not coluna_doc:
        return {}
    existentes = {}
    for linha in range(LINHA_CABECALHO + 1, ws.max_row + 1):
        valor = ws.cell(row=linha, column=coluna_doc).value
        if valor:
            existentes[str(valor).strip()] = linha
    return existentes

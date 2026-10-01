# -*- coding: utf-8 -*-
"""
Regenera as notas de `_gerado/` a partir das planilhas do Box.

REGRA INEGOCIAVEL: este script **so le** o Box. Tudo que ele escreve vai para
`_gerado/`, dentro do cofre. Nao ha uma unica operacao de escrita apontando para
o Box neste arquivo — e nao deve haver.

Uso:
    python _scripts/regenerar_gerado.py

Requisitos: openpyxl
"""
from __future__ import annotations

import collections
import datetime
import pathlib
import sys

try:
    import openpyxl
except ImportError:
    sys.exit("Falta openpyxl. Rode:  pip install openpyxl")

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------
VAULT = pathlib.Path(__file__).resolve().parent.parent
GERADO = VAULT / "_gerado"

BOX = pathlib.Path.home() / "Box" / "CMI - Consórcio Itaipu" / "11 - Ger. Engenharia" / "15 - PDM"
MAPEADORA = BOX / "SOBRESSALENTES - PMIB" / "Mapeamento Listas de Sobressalentes.xlsx"
ABA = "Acompanhamento Sobressalente"

# Colunas de contagem de fichas, na ordem do funil
COLUNAS_FICHA = [
    "FICHAS EXISTENTES",
    "FICHAS COM O FORNECEDOR",
    "FICHAS RECEBIDAS",
    "FICHAS EM ELABORAÇÃO",
    "INFO. DO FORNECEDOR COMPLETO",
    "VALORIZAÇÃO",
    "FICHAS COM APLICAÇÃO - LMR FINALIZADA",
    "FICHAS EM ANÁLISE DE ITAIPU",
    "FICHAS EM CORREÇÃO",
    "FICHAS APROVADAS",
    "APTO PARA ENTREGA",
    "ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU",
]

COLUNAS_CATEGORICAS = [
    "SITUAÇÃO NO PMIB",
    "ESPECIFICAÇÃO TÉCNICA",
    "STATUS REAL",
    "ORIGEM FORNECEDOR",
]


def achar_coluna(cabecalho: list[str], nome: str) -> int | None:
    """Indice da coluna cujo cabecalho contem `nome` (case/newline-insensitive)."""
    alvo = nome.upper()
    for i, h in enumerate(cabecalho):
        if alvo in h.upper().replace("\n", " "):
            return i
    return None


def barra(valor: int, total: int, largura: int = 24) -> str:
    if not total:
        return ""
    cheio = round(valor / total * largura)
    return "█" * cheio + "░" * (largura - cheio)


def main() -> int:
    if not MAPEADORA.exists():
        sys.exit(f"Mapeadora nao encontrada:\n  {MAPEADORA}\nO Box esta sincronizado?")

    wb = openpyxl.load_workbook(MAPEADORA, data_only=True, read_only=True)
    ws = wb[ABA]
    linhas = list(ws.iter_rows(values_only=True))
    wb.close()

    cabecalho = [str(c).strip() if c else "" for c in linhas[1]]
    dados = [r for r in linhas[2:] if r and r[0]]

    hoje = datetime.date.today().isoformat()
    out: list[str] = []
    A = out.append

    A("---")
    A("tags: [gerado, indicadores]")
    A(f"gerado_em: {hoje}")
    A("fonte: Mapeamento Listas de Sobressalentes.xlsx")
    A("---")
    A("")
    A("# Panorama Quantitativo")
    A("")
    A("> [!warning] Nota gerada automaticamente")
    A("> Nao edite a mao — rode `python _scripts/regenerar_gerado.py`.")
    A(f"> Regenerada em **{hoje}** a partir da mapeadora no Box.")
    A("")
    A(f"**{len(dados)} listas de sobressalentes** mapeadas.")
    A("")

    # ---- funil de fichas -------------------------------------------------
    A("## O funil de fichas")
    A("")
    idx_exist = achar_coluna(cabecalho, "FICHAS EXISTENTES")
    total_fichas = 0
    if idx_exist is not None:
        total_fichas = sum(int(r[idx_exist]) for r in dados if isinstance(r[idx_exist], (int, float)))

    A("| Indicador | Fichas | % das existentes | |")
    A("|---|---:|---:|---|")
    for nome in COLUNAS_FICHA:
        i = achar_coluna(cabecalho, nome)
        if i is None:
            A(f"| {nome} | — | — | coluna nao encontrada |")
            continue
        tot = sum(int(r[i]) for r in dados if isinstance(r[i], (int, float)))
        pct = f"{tot / total_fichas * 100:.1f}%" if total_fichas else "—"
        rotulo = cabecalho[i].replace("\n", " ")
        A(f"| {rotulo} | **{tot}** | {pct} | `{barra(tot, total_fichas)}` |")
    A("")

    # ---- leitura dirigida ------------------------------------------------
    def total_de(nome: str) -> int:
        i = achar_coluna(cabecalho, nome)
        if i is None:
            return 0
        return sum(int(r[i]) for r in dados if isinstance(r[i], (int, float)))

    lmr = total_de("FICHAS COM APLICAÇÃO - LMR FINALIZADA")
    val = total_de("VALORIZAÇÃO")
    analise = total_de("FICHAS EM ANÁLISE DE ITAIPU")
    aprov = total_de("FICHAS APROVADAS")

    A("### Como ler estes numeros")
    A("")
    if total_fichas:
        A(f"- **Cobertura de LMR: {lmr / total_fichas * 100:.1f}%** "
          f"({lmr} de {total_fichas}). E o menor indicador da cadeia. "
          "Ver [[Secao - Aplicacao LMR]].")
        A(f"- **Cobertura de valorizacao: {val / total_fichas * 100:.1f}%** "
          f"({val} de {total_fichas}). Depende de outra area da GE e da lista EN.DT "
          "aprovada. Ver [[Secao - Valorizacao]].")
    if analise:
        A(f"- **Taxa de aprovacao: {aprov / analise * 100:.1f}%** "
          f"({aprov} aprovadas contra {analise} em analise). Cada ficha em analise "
          "fica 2 a 3 meses fora do controle do CMI.")
    A("")
    A("Metodo de leitura em [[Indicadores e Como Ler]].")
    A("")

    # ---- distribuicoes categoricas --------------------------------------
    for nome in COLUNAS_CATEGORICAS:
        i = achar_coluna(cabecalho, nome)
        if i is None:
            continue
        cont = collections.Counter(
            (str(r[i]).strip() if r[i] else "(vazio)") for r in dados
        )
        A(f"## {cabecalho[i].replace(chr(10), ' ')}")
        A("")
        A("| Valor | Listas | |")
        A("|---|---:|---|")
        for valor, n in cont.most_common():
            A(f"| {valor} | {n} | `{barra(n, len(dados), 18)}` |")
        A("")

    A("---")
    A("")
    A("Voltar para [[00 - Inicio]] · [[Mapeamento das Listas de Sobressalentes]]")

    GERADO.mkdir(parents=True, exist_ok=True)
    destino = GERADO / "Panorama Quantitativo.md"
    destino.write_text("\n".join(out), encoding="utf-8")
    print(f"OK -> {destino}")
    print(f"   {len(dados)} listas, {total_fichas} fichas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

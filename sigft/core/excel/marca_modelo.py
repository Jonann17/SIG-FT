r"""
A coluna `MARCA/MODELO` do `_STATUS_PMIB` — separar o fabricante do modelo.

A coluna guarda os dois juntos, separados por barra: `WAGO / 750-362`,
`NIDEC / MOD SVTN 3K6 W`, `CISCO / IE-3200-8T2S-E`. Quem precisa do FABRICANTE
sozinho — a busca de datasheet do AutoSpec, o combo de fabricante da ficha
duplicada — precisa quebrar essa string, e quebrar do mesmo jeito.

⚠️ **Há uma segunda implementação disto hoje**, em
`services/autospec.py::separar_marca_modelo`, que é a original. Ela não foi
movida para cá porque `autospec.py` pertence à outra frente de trabalho (ver
`docs/refatoracao/TRABALHO_PARALELO.md`) e mexer nele agora criaria conflito
caro por seis linhas. Esta versão é cópia fiel do comportamento dela, e a
migração está registrada em `docs/refatoracao/PENDENCIAS.md`: quando as duas
frentes se juntarem, o método de lá vira uma linha delegando para cá.
"""
from __future__ import annotations


def separar(bruto):
    r"""`"WAGO / 750-362"` -> `("WAGO", "750-362")`.

    Regras, e as duas vieram do formato real da planilha:

      - **sem barra, o texto inteiro é a MARCA.** É o caso de quem só anotou o
        fabricante, que é comum;
      - **quebra na PRIMEIRA barra.** `WAGO / 750-362/000-001` tem barra dentro
        do modelo, e quebrar em todas partiria o código de peça ao meio.

    Célula vazia (ou o `nan` que o pandas devolve) vira `("", "")` -- nunca
    `None`, para o chamador não precisar checar duas coisas.
    """
    texto = str(bruto or "").strip()
    if not texto or texto.lower() == "nan":
        return "", ""
    if "/" not in texto:
        return texto, ""
    marca, _, modelo = texto.partition("/")
    return marca.strip(), modelo.strip()


def fabricante(bruto):
    """Só o fabricante da célula `MARCA/MODELO` (`""` se não houver)."""
    return separar(bruto)[0]


def modelo(bruto):
    """Só o modelo da célula `MARCA/MODELO` (`""` se não houver)."""
    return separar(bruto)[1]

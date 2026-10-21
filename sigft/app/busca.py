"""Comparar texto como a pessoa digita: sem acento e sem caixa (2026-10-21, etapa 1b).

Usado pela busca do console (`app_qt/widgets/console.py`) e pela caixa do Ctrl+K
(`app_qt/catalogo.filtrar`). Sem Qt.
"""
from __future__ import annotations

import unicodedata


def normalizar(texto: object) -> str:
    """"Tensão AÇÃO" -> "tensao acao"."""
    decomposto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def contem(texto: object, consulta: object) -> bool:
    """`consulta` aparece em `texto`, sem olhar acento nem caixa. Consulta vazia: sim."""
    return normalizar(consulta).strip() in normalizar(texto)

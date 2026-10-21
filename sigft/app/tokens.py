"""Tokens do sistema visual (2026-10-20): cada cor tem um nome pelo papel que cumpre.

Sem Qt, como `theme.py`: quem desenha (folha de estilo, widgets) le daqui. Os dois
temas tem exatamente os mesmos papeis; o teste de contraste garante que o texto se le
(minimo 4,5:1) em cada par usado.
"""

ESCURO = {
    "fundo": "#14171A",
    "superficie": "#1C2024",
    "superficie_alta": "#252A2F",
    "borda": "#31373D",
    "texto": "#E7EAED",
    "texto_suave": "#9AA4AE",
    "primaria": "#00C975",
    "primaria_hover": "#00E085",
    "texto_sobre_primaria": "#0B1A12",
    "marca": "#035D67",
    "sucesso": "#00C975",
    "aviso": "#FFA726",
    "perigo": "#F2555A",
    "perigo_fundo": "#C9302C",
    "info": "#3B9EFF",
    "console_fundo": "#0E1012",
    "console_texto": "#C9CFD6",
}

CLARO = {
    "fundo": "#F3F5F6",
    "superficie": "#FFFFFF",
    "superficie_alta": "#EEF1F3",
    "borda": "#D5DBE0",
    "texto": "#1A1F24",
    "texto_suave": "#5B6670",
    "primaria": "#007A51",
    "primaria_hover": "#00875A",
    "texto_sobre_primaria": "#FFFFFF",
    "marca": "#035D67",
    "sucesso": "#00875A",
    "aviso": "#AA6600",  # 2026-10-20: #B26A00 da spec dava 4,24:1 sobre branco
    "perigo": "#C9302C",
    "perigo_fundo": "#C9302C",
    "info": "#0B6BCB",
    "console_fundo": "#0E1012",
    "console_texto": "#C9CFD6",
}

FONTE = {"titulo": 22, "secao": 15, "corpo": 13, "legenda": 12}
ESPACO = (4, 8, 12, 16, 24)
RAIO = {"controle": 6, "cartao": 10}


def paleta(tema: str) -> dict[str, str]:
    """Paleta do tema ("escuro" ou "claro"); qualquer outro valor cai no escuro."""
    return CLARO if tema == "claro" else ESCURO


def _luminancia(cor: str) -> float:
    cor = cor.lstrip("#")
    canais = []
    for i in (0, 2, 4):
        c = int(cor[i:i + 2], 16) / 255
        canais.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canais
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    """Razao de contraste WCAG entre duas cores "#RRGGBB" (1 a 21)."""
    la, lb = _luminancia(a), _luminancia(b)
    claro, escuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (escuro + 0.05)

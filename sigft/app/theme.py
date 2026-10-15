"""Tema visual do SIG-FT — a paleta e as fontes, em UM lugar só.

Checkpoint 7.1 do plano de refatoração (`docs/refatoracao/PLANO_REFATORACAO.md`,
Fase 7). A regra da fase é **zero redesign**: os valores aqui são os que o
`frontend.py` já usava, copiados sem alteração. Este módulo não inventa cor,
não renomeia chave e não "melhora" espaçamento — ele só para de repetir.

Por que este módulo NÃO importa biblioteca gráfica
--------------------------------------------------
Só dados: dicionários e tuplas da stdlib. Isso é deliberado e vale tanto para
o teste quanto para a produção:

* dá para importar `sigft.app.theme` em QUALQUER ambiente;
* mantém o princípio nº 2 da arquitetura (serviço nunca importa interface)
  válido também para quem só quer consultar a paleta.

A interface Qt (`sigft/app_qt/estilo.py`) lê as cores daqui. (As fontes em
tupla são o formato da interface antiga, que saiu em 2026-10-15; a Qt as
converte.)
"""
from __future__ import annotations

# =============================================================================
# Paleta — GE Vernova
# =============================================================================
# Copiada literalmente de `frontend.py` (dict `COLORS`). A ordem das chaves e
# os valores em hexadecimal são os mesmos; mudar qualquer um deles é redesign,
# e redesign está fora da Fase 7.
COLORS: dict[str, str] = {
    "primary": "#035D67",
    "primary_hover": "#047A83",
    "accent": "#00C975",
    "accent_hover": "#00E085",
    "danger": "#D32F2F",
    # Acrescentada em 2026-08-13 para a secao de conferencia do AutoSpec.
    # Aditiva: nenhuma cor existente mudou.
    "warning": "#FFA726",
    "sidebar": "#161616",
    "background": "#212121",
    "text_light": "#E0E0E0",
    "text_white": "#FFFFFF",
}

# Cinza do "cartão" interno das telas: o `fg_color="#2B2B2B"` que aparece
# ~20 vezes no `frontend.py`, sempre com `corner_radius=8`, sempre no frame
# que agrupa um bloco de controles. Nunca esteve no `COLORS` — mas é cor de
# tema como qualquer outra, e sem nome vira literal espalhado.
COR_CARTAO: str = "#2B2B2B"

# Cinza usado em texto de apoio (descrições sob um título). No `frontend.py`
# aparece como as strings literais "gray" e "gray70", que são nomes de cor do
# Tk — preservados aqui como estão, para não mudar um pixel.
COR_TEXTO_APOIO: str = "gray"
COR_TEXTO_APOIO_CLARO: str = "gray70"


# =============================================================================
# Fontes
# =============================================================================
# Tuplas no formato que a interface antiga aceita direto: (família, tamanho[, estilo]).
FONTE_TITULO_MODULO: tuple = ("Roboto", 24, "bold")
FONTE_SECAO: tuple = ("Roboto", 16, "bold")
FONTE_SUBTITULO: tuple = ("Roboto", 16)
FONTE_BOTAO: tuple = ("Roboto", 14, "bold")
FONTE_ROTULO: tuple = ("Roboto", 14, "bold")
FONTE_CORPO: tuple = ("Roboto", 13)
FONTE_CORPO_MIUDO: tuple = ("Roboto", 12)

# O console é o único lugar com fonte monoespaçada — alinhamento de log em
# lote depende disso (ver `core/relatorio_lote.py`, CP 4.4).
FONTE_CONSOLE: tuple = ("Consolas", 12)


# =============================================================================
# Medidas do esqueleto de módulo (ver `widgets/module_frame.py`)
# =============================================================================
# Os valores dominantes hoje no `frontend.py`. As telas que divergem passam o
# valor que já usavam por parâmetro — a padronização é do PADRÃO, não uma
# uniformização à força que mudaria o layout de quem é diferente de propósito.
ALTURA_HEADER: int = 50
ALTURA_CONSOLE: int = 150
PADDING_X: int = 20
PADDING_Y: int = 10

r"""
sigft/core/rpa/ficha_layout.py — `CONFIG_MAP`/`VARIAVEIS_SPECS`: fonte única
do layout da "Ficha Técnica Padrão" (Checkpoint 2.4 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.4, e diagnóstico
seção 1.3: "`CONFIG_MAP` do layout da ficha técnica | **duplicado** em
`analyzer_backend` e `autospec_backend` (ranges divergem: `H6:P6` vs `H6`)".

Este módulo substitui DUAS cópias divergentes do mesmo mapeamento de células
da aba "Ficha Técnica Padrão" (25 chaves, mesma ordem nas duas):

  - `analyzer_backend.py` (`CONFIG_MAP` linhas 25-51, `VARIAVEIS_SPECS`
    linhas 53-57) — usado por `DatasheetAnalyzer` para VALIDAR uma ficha já
    preenchida (score 0-100%, marca "FORNECER" em vermelho onde falta/é
    inválido).
  - `autospec_backend.py` (`CONFIG_MAP` linhas 34-60, `VARIAVEIS_SPECS`
    linhas 62-66) — usado por `AutoSpecCore` para DETECTAR campos vazios e
    PREENCHÊ-LOS via IA (fonte azul).

Levantamento campo a campo confirmou que `type`, `validation`, `weight` e
`cells` (das entradas checkbox) são IDÊNTICOS entre os dois mapas nas 25
chaves — nenhuma divergência real aí. As únicas diferenças reais eram:

  1. `range` (só nas entradas `"type": "cell"`): `analyzer_backend` guardava
     o range COMPLETO da célula mesclada no template Excel (ex.: `"H6:P6"`,
     `"L10:N10"`); `autospec_backend` guardava só a PRIMEIRA célula desse
     mesmo range (ex.: `"H6"`, `"L10"`). Conferido célula a célula: a
     primeira célula do range completo do analyzer é SEMPRE igual ao valor
     único do autospec, nas 16 entradas `"type": "cell"` — funcionalmente
     equivalentes, porque todo consumidor de `range` (nos dois arquivos
     originais) só usava a primeira célula na prática (`get_cell_from_range`
     no analyzer; `cfg["range"].split(":")[0]` no autospec, exceto em 2
     acessos diretos que o CP 2.4 corrigiu — ver `autospec_backend.py`,
     método `analyze_sheet`).
  2. `error_target`: só existia no `analyzer_backend`, só em entradas
     `"type": "checkbox"` (nem todas — `classificacao_periculosidade` e
     `logistica_reversa` não têm). É a célula onde `set_blank_error` escreve
     "FORNECER" quando o checkbox não foi marcado — às vezes é uma das
     próprias `cells` (ex. `tipo_fabricacao`), às vezes é uma célula
     DIFERENTE (ex. `sujeito_intemperies` -> `error_target: "U21"`, fora de
     `cells: ["Q21", "S21"]`).
  3. `desc`: só existia no `autospec_backend`, em quase todas as entradas
     EXCETO `texto_breve_material`, `unidade`, `fabricante`. É um texto
     humano explicando o que cada opção/célula significa (usado para montar
     o prompt de IA em `generate_ai_response` e a UI de campos faltantes).

DECISÃO CANÔNICA (arquiteto, CP 2.4): `CONFIG_MAP` unificado é a UNIÃO das
duas versões — cada uma das 25 entradas ganha todas as chaves que tinha em
QUALQUER um dos dois originais. Para `range`, o valor canônico é o COMPLETO
do `analyzer_backend` (mais informativo — documenta o span real da célula
mesclada no template Excel), não o de célula única do `autospec_backend`.
Consumidores que precisam só da primeira célula continuam fazendo
`.split(":")[0]` no ponto de uso (como o `analyzer_backend` já fazia via
`get_cell_from_range`) — nenhuma informação é perdida ao canonizar o range
completo, e quem só usava a primeira célula continua funcionando idêntico
desde que aplique o mesmo `.split(":")[0]` (ver PENDENCIAS.md, entrada do
CP 2.4, para o racional completo e os 2 pontos do `autospec_backend` que
precisaram desse ajuste).

`VARIAVEIS_SPECS` unificado é a união das 4 chaves DISJUNTAS dos dois
originais (`pergunta_range`/`resposta_range` do analyzer vs.
`pergunta_col_idx`/`resposta_col_idx` do autospec — mesmos dados, formas
diferentes: coluna "C" = índice 3, "M" = índice 13, sem colisão real) mais
`start_row`, deduplicado através de `sigft.config.LINHA_SPECS_FICHA` (=79) —
o mesmo valor mágico que os dois arquivos hardcodavam separadamente,
documentado desde o CP 1.1 e agora finalmente referenciado por quem o usa.

Só stdlib + `sigft.config` (para `LINHA_SPECS_FICHA`) — sem `import
openpyxl`: este módulo só contém dicts puros (dados, não lógica de Excel),
testável no ambiente sem as dependências pesadas de produção (ver
tests/conftest.py) e importável de qualquer lugar do pacote `sigft` sem
efeito colateral algum.
"""

from __future__ import annotations

from sigft import config

# -----------------------------------------------------------------------
# CONFIG_MAP — mapa de células fixas da aba "Ficha Técnica Padrão".
#
# Chaves por entrada:
#   - "range" (entradas "type": "cell") OU "cells" (entradas
#     "type": "checkbox"): localização na planilha. "range" é o span
#     COMPLETO da célula mesclada (ex. "H6:P6") — ver decisão canônica no
#     docstring do módulo acima.
#   - "type": "cell" (texto livre) ou "checkbox" (múltiplas opções
#     mutuamente exclusivas).
#   - "validation": "simple" (só checa se está preenchido) ou "ai" (também
#     passa pela validação semântica do Gemini).
#   - "weight": peso relativo (1-7) usado por `DatasheetAnalyzer` na
#     normalização 0-100%.
#   - "error_target" (opcional, só em algumas entradas "checkbox"): célula
#     onde `DatasheetAnalyzer.set_blank_error` escreve "FORNECER" quando
#     nenhuma opção foi marcada. Ausente = usa a 1ª célula de "cells".
#   - "desc" (opcional, ausente em texto_breve_material/unidade/fabricante):
#     descrição humana do campo/opções, usada por `AutoSpecCore` para montar
#     o prompt de IA e a UI de campos faltantes.
# -----------------------------------------------------------------------
CONFIG_MAP = {
    "texto_breve_material": {"range": "H6:P6", "type": "cell", "validation": "simple", "weight": 1},
    "unidade": {"range": "H8:J8", "type": "cell", "validation": "simple", "weight": 1},
    "tipo_fabricacao": {"cells": ["F10", "F12"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["F10", "F12"], "desc": "F10: Série, F12: Especial/Sob Pedido"},
    "fabricante": {"range": "L10:N10", "type": "cell", "validation": "simple", "weight": 1},
    "origem": {"cells": ["S6", "S8"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["S6", "S8"], "desc": "S6: BR/PY, S8: Outros"},
    "tipo": {"cells": ["S10", "S12"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["S10", "S12"], "desc": "S10: Reparável, S12: Não Reparável"},
    "comprimento_embalagem": {"range": "H17:K17", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm"},
    "largura_embalagem": {"range": "H19:K19", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm"},
    "altura_embalagem": {"range": "H21:K21", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm"},
    "peso_liquido": {"range": "P17:Q17", "type": "cell", "validation": "simple", "weight": 1, "desc": "kg"},
    "peso_bruto": {"range": "P19:Q19", "type": "cell", "validation": "simple", "weight": 1, "desc": "kg"},
    "sujeito_intemperies": {"cells": ["Q21", "S21"], "type": "checkbox", "validation": "simple", "weight": 1, "error_target": "U21", "desc": "Q21: Sim, S21: Não"},
    "posicao_armazenamento": {"cells": ["G25", "G27", "G29"], "type": "checkbox", "validation": "simple", "weight": 3, "error_target": "J27", "desc": "G25: Vertical, G27: Horizontal, G29: Indiferente"},
    "protecao": {"cells": ["S25", "S27", "S29"], "type": "checkbox", "validation": "simple", "weight": 3, "error_target": "O27", "desc": "S25: Nenhuma, S27: UV, S29: Eletrostática"},
    "nocivo": {"cells": ["E31", "E33"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": "L31", "desc": "E31: Não Nocivo, E33: Nocivo"},
    "empilhamento": {"range": "J35:L35", "type": "cell", "validation": "simple", "weight": 2, "desc": "Qtd Max Caixas"},
    "embalagem_transporte": {"range": "M42:V44", "type": "cell", "validation": "ai", "weight": 7, "desc": "Tipo e cuidados embalagem transporte"},
    "transporte": {"range": "M45:V47", "type": "cell", "validation": "ai", "weight": 3, "desc": "Procedimento elevação/transporte"},
    "preservacao": {"range": "M52:V53", "type": "cell", "validation": "ai", "weight": 6, "desc": "Cuidados preservação"},
    "metodo_limpeza": {"range": "M54:V55", "type": "cell", "validation": "ai", "weight": 3, "desc": "Métodos limpeza/secagem"},
    "ferramentas_para_preservacao": {"range": "M56:V58", "type": "cell", "validation": "ai", "weight": 1, "desc": "Ferramentas recomendadas"},
    "tipo_legislacao": {"range": "M63:V64", "type": "cell", "validation": "ai", "weight": 4, "desc": "Legislação aplicada"},
    "tipo_descarte": {"range": "M65:V66", "type": "cell", "validation": "ai", "weight": 2, "desc": "Tipo descarte/Melhores práticas"},
    "classificacao_periculosidade": {"cells": ["E69", "J69"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "E69: Classe 1 (Perigoso), J69: Classe 2 (Não Perigoso)"},
    "logistica_reversa": {"cells": ["P69", "T69"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "P69: Não se aplica, T69: Aplica-se"},
}

# -----------------------------------------------------------------------
# VARIAVEIS_SPECS — especificações técnicas variáveis (pergunta/resposta em
# linhas dinâmicas, a partir de `start_row`). As 4 chaves são as formas
# DISJUNTAS que cada consumidor original usava para os MESMOS dados
# (coluna "C" = índice 3, coluna "M" = índice 13):
#   - `pergunta_range`/`resposta_range`: usadas por `DatasheetAnalyzer`
#     (openpyxl `ws[f"{col}{row}"]`, precisa só da LETRA da coluna).
#   - `pergunta_col_idx`/`resposta_col_idx`: usadas por `AutoSpecCore`
#     (openpyxl `ws.cell(row=..., column=...)`, precisa do ÍNDICE 1-based).
# -----------------------------------------------------------------------
VARIAVEIS_SPECS = {
    "start_row": config.LINHA_SPECS_FICHA,
    "pergunta_range": "C:L",
    "resposta_range": "M:V",
    "pergunta_col_idx": 3,
    "resposta_col_idx": 13,
}

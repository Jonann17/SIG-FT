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
    "texto_breve_material": {"range": "H6:P6", "type": "cell", "validation": "simple", "weight": 1, "obrigatorio": True},
    "unidade": {"range": "H8:J8", "type": "cell", "validation": "simple", "weight": 1, "obrigatorio": True},
    "tipo_fabricacao": {"cells": ["F10", "F12"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["F10", "F12"], "desc": "F10: Série, F12: Especial/Sob Pedido", "obrigatorio": True},
    "fabricante": {"range": "L10:N10", "type": "cell", "validation": "simple", "weight": 1, "obrigatorio": True},
    "origem": {"cells": ["S6", "S8"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["S6", "S8"], "desc": "S6: BR/PY, S8: Outros", "obrigatorio": True},
    "tipo": {"cells": ["S10", "S12"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["S10", "S12"], "desc": "S10: Reparável, S12: Não Reparável", "obrigatorio": True},
    "comprimento_embalagem": {"range": "H17:K17", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm", "obrigatorio": True},
    "largura_embalagem": {"range": "H19:K19", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm", "obrigatorio": True},
    "altura_embalagem": {"range": "H21:K21", "type": "cell", "validation": "simple", "weight": 1, "desc": "cm", "obrigatorio": True},
    "peso_liquido": {"range": "P17:Q17", "type": "cell", "validation": "simple", "weight": 1, "desc": "kg", "obrigatorio": True},
    "peso_bruto": {"range": "P19:Q19", "type": "cell", "validation": "simple", "weight": 1, "desc": "kg"},
    "sujeito_intemperies": {"cells": ["Q21", "S21"], "type": "checkbox", "validation": "simple", "weight": 1, "error_target": "U21", "desc": "Q21: Sim, S21: Não", "obrigatorio": True},
    # ACRESCENTADO em 2026-08-26: estava na lista de campos obrigatorios do
    # usuario e nao existia no CONFIG_MAP. A celula (M23) nao foi chutada --
    # `services/upload_conditions.py:132` ja lia esse mesmo endereco
    # (`dados["controle_temperatura"] = get_val("M23")`) desde antes.
    # `validation: "simple"` e nao "ai": a pergunta e SIM/NAO com valores ao
    # lado, nao texto livre para a IA julgar.
    "controle_temp_umidade": {"range": "M23", "type": "cell", "validation": "simple", "weight": 2, "obrigatorio": True, "desc": "Necessidade de controle de temperatura e umidade"},
    "posicao_armazenamento": {"cells": ["G25", "G27", "G29"], "type": "checkbox", "validation": "simple", "weight": 3, "error_target": "J27", "desc": "G25: Vertical, G27: Horizontal, G29: Indiferente", "obrigatorio": True},
    "protecao": {"cells": ["S25", "S27", "S29"], "type": "checkbox", "validation": "simple", "weight": 3, "error_target": "O27", "desc": "S25: Nenhuma, S27: UV, S29: Eletrostática", "obrigatorio": True},
    "nocivo": {"cells": ["E31", "E33"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": "L31", "desc": "E31: Não Nocivo, E33: Nocivo", "obrigatorio": True},
    "empilhamento": {"range": "J35:L35", "type": "cell", "validation": "simple", "weight": 2, "desc": "Qtd Max Caixas"},
    "embalagem_transporte": {"range": "M42:V44", "type": "cell", "validation": "ai", "weight": 7, "desc": "Tipo e cuidados embalagem transporte", "obrigatorio": True},
    "transporte": {"range": "M45:V47", "type": "cell", "validation": "ai", "weight": 3, "desc": "Procedimento elevação/transporte", "obrigatorio": True, "aceita_nao_aplicavel": True},
    "preservacao": {"range": "M52:V53", "type": "cell", "validation": "ai", "weight": 6, "desc": "Cuidados preservação", "obrigatorio": True},
    "metodo_limpeza": {"range": "M54:V55", "type": "cell", "validation": "ai", "weight": 3, "desc": "Métodos limpeza/secagem", "obrigatorio": True, "aceita_nao_aplicavel": True},
    "ferramentas_para_preservacao": {"range": "M56:V58", "type": "cell", "validation": "ai", "weight": 1, "desc": "Ferramentas recomendadas", "obrigatorio": True, "aceita_nao_aplicavel": True},
    "tipo_legislacao": {"range": "M63:V64", "type": "cell", "validation": "ai", "weight": 4, "desc": "Legislação aplicada", "obrigatorio": True},
    "tipo_descarte": {"range": "M65:V66", "type": "cell", "validation": "ai", "weight": 2, "desc": "Tipo descarte/Melhores práticas", "obrigatorio": True},
    "classificacao_periculosidade": {"cells": ["E69", "J69"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "E69: Classe 1 (Perigoso), J69: Classe 2 (Não Perigoso)", "obrigatorio": True},
    "logistica_reversa": {"cells": ["P69", "T69"], "type": "checkbox", "validation": "simple", "weight": 2, "desc": "P69: Não se aplica, T69: Aplica-se", "obrigatorio": True},
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

# -----------------------------------------------------------------------
# Quantas linhas em branco SEGUIDAS significam "a lista acabou" (2026-08-26).
#
# Acréscimo ADITIVO nesta zona compartilhada: nenhum valor existente mudou.
# Mora aqui porque é uma propriedade do LAYOUT da ficha, e os dois lados
# precisam dela — o `analyzer` varre as specs para pontuar, o `autospec` para
# preencher.
#
# Por que existe: parar na PRIMEIRA linha vazia é o bug medido em 2026-08-26
# no analyzer — uma ficha com 5 perguntas em 6 linhas (uma linha de respiro no
# meio) tinha 2 perguntas analisadas, e as outras 3 sumiam da nota em silêncio.
# Folgado o bastante para atravessar um bloco de layout, curto o bastante para
# não varrer a planilha inteira.
#
# O valor vem do `AutoSpecCore.MAX_LINHAS_VAZIAS_SEGUIDAS` (R-08, 2026-08-11),
# que era o mesmo 25 escrito como atributo de classe. A migração do autospec
# para esta constante está registrada em PENDENCIAS.md — enquanto não
# acontecer, os dois números são iguais de propósito, não por coincidência.
# -----------------------------------------------------------------------
MAX_LINHAS_VAZIAS_SEGUIDAS = 25


# =============================================================================
# QUAL ABA DO WORKBOOK É A FICHA (2026-09-03)
# =============================================================================
# Acréscimo ADITIVO nesta zona compartilhada: nenhum valor existente mudou.
#
# Mora aqui pela mesma razão do `CONFIG_MAP`: é LAYOUT da ficha, e havia TRÊS
# módulos resolvendo por conta própria — `pdm.aplicar_templates_fichas`,
# `upload_conditions.extrair_dados_brutos_excel` e `AutoSpecCore.fill_save` —,
# os dois últimos exigindo o nome literal `"Ficha Técnica Padrão"`. É
# exatamente o caminho que fez o `CONFIG_MAP` acabar duplicado com ranges
# divergentes antes do CP 2.4.
#
# O que quebrava: uma ficha em INGLÊS tem a aba `"Standard Technical Sheet"`
# — e desde 2026-09-03 é o próprio SIG-FT que a nomeia assim, a pedido do
# usuário. O upload de condições devolvia `None` sem dizer por quê; o AutoSpec
# levantava `ValueError` pedindo uma aba em português.
NOME_CANONICO_DA_ABA = "Ficha Técnica Padrão"

# Como a aba se chama na ficha ENTREGUE AO FORNECEDOR quando o idioma é
# inglês. Não é escolha do código: é o nome que aparece na ficha
# `4500063671.0052_enUS.xlsx`, que o usuário entregou — ou seja, ele já
# renomeava à mão, ficha a ficha. O template `Technical_Sheet_of_PDM-R3.xlsx`
# ainda traz a aba com o nome em português.
NOME_DA_ABA_EM_INGLES = "Standard Technical Sheet"

# Nomes aceitos, normalizados (sem acento, minúsculas, sem espaço nas pontas).
NOMES_DA_ABA_DA_FICHA = (
    "ficha tecnica padrao",
    # Dos arquivos REAIS: o template EN traz a aba ainda com o nome em
    # PORTUGUÊS (herança do template do qual foi derivado), e a ficha já
    # preenchida traz "Standard Technical Sheet". Os dois circulam.
    "standard technical sheet",
    "standard datasheet",
    "technical datasheet",
    "datasheet",
)


def _normalizar_nome_de_aba(nome):
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(nome or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


def nome_da_aba_da_ficha(wb):
    """O NOME da aba onde a ficha técnica mora, dentro de um workbook.

    Devolve o nome, e não o objeto: é só disso que os chamadores precisam
    (`wb[nome]`), e pedir `.title` de volta ao chamador só criava um passo a
    mais para errar.

    **O que isto conserta.** Era `wb["Ficha Técnica Padrão"]`, nome fixo, em
    três módulos. No montador (`pdm`), um template com a aba noutro nome
    levantava `KeyError` DENTRO do laço, e o `except` genérico transformava
    isso em "ERRO ao gerar ficha {pmib}" **uma vez por ficha** — num lote de
    200 materiais, 200 linhas idênticas, nenhuma delas dizendo que o problema
    era a aba.

    Workbook de uma aba só usa ela: não há ambiguidade para resolver, e um
    arquivo válido não pode ser recusado por causa do nome.

    Nenhuma aba reconhecida levanta `ValueError` **com os nomes encontrados**
    — a mensagem precisa dizer ao usuário o que ele tem em mãos.
    """
    try:
        nomes = [ws.title for ws in wb.worksheets]
    except Exception:
        nomes = []
    if not nomes:
        # Não consegui enumerar as abas -- o que NÃO é o mesmo que "o arquivo
        # está errado". Cai no nome canônico e deixa o erro, se houver, vir de
        # quem de fato tentar usar a aba.
        return NOME_CANONICO_DA_ABA
    if len(nomes) == 1:
        return nomes[0]

    for nome in nomes:
        if _normalizar_nome_de_aba(nome) in NOMES_DA_ABA_DA_FICHA:
            return nome

    encontrados = ", ".join(f"'{n}'" for n in nomes) or "(nenhuma)"
    raise ValueError(
        "Nao achei a aba da ficha tecnica no arquivo. Abas encontradas: "
        f"{encontrados}. Esperado um destes nomes: "
        + ", ".join(f"'{n}'" for n in NOMES_DA_ABA_DA_FICHA)
    )


# =============================================================================
# O MARCADOR DE CAMPO FALTANTE, E O IDIOMA DA FICHA (2026-09-08)
# =============================================================================
# Acréscimo ADITIVO nesta zona compartilhada: nada existente muda.
#
# `FORNECER` é o que o `analyzer` escreve, em vermelho, nos campos que faltam
# ou foram recusados. Numa ficha em INGLÊS — que existe justamente para voltar
# a um fornecedor estrangeiro — a palavra chegava em português.
#
# POR QUE ISTO MORA AQUI, e não solto no analyzer: o marcador não é decoração,
# é PROTOCOLO. O AutoSpec o lê de volta (`AutoSpecCore.is_empty`) para saber
# que o campo continua vazio e precisa ser preenchido pela IA. Traduzir só o
# lado que ESCREVE faria o AutoSpec, numa ficha em inglês, tratar `PROVIDE`
# como resposta do fornecedor — e pular exatamente os campos marcados como
# faltantes. Quem escreve e quem lê têm de concordar, e a concordância mora
# num lugar só (princípio nº 1).
#
# O inglês escolhido é `PROVIDE`: verbo no imperativo, curto, mesmo registro
# do `FORNECER`. Trocar a palavra é editar esta linha, e mais nada.
MARCADORES_DE_FALTANTE = {
    "pt": "FORNECER",
    "en": "PROVIDE",
}
IDIOMA_PADRAO_DA_FICHA = "pt"


def marcador_de_faltante(idioma):
    """A palavra a escrever no campo que falta, no idioma da ficha.

    Idioma desconhecido cai no português: "não sei o idioma" é diferente de
    "é inglês", e a ficha que o aplicativo processa desde sempre é PT-BR.
    """
    return MARCADORES_DE_FALTANTE.get(
        str(idioma or "").strip().lower(),
        MARCADORES_DE_FALTANTE[IDIOMA_PADRAO_DA_FICHA],
    )


def e_marcador_de_faltante(valor):
    """O valor desta célula é um marcador escrito pelo aplicativo?

    Aceita a forma composta (`FORNECER (valor antigo)`), que é como
    `set_invalid_error` grava — e por isso compara com `startswith` sobre o
    marcador MAIS o delimitador, nunca com o marcador solto: `"Provided by
    supplier"` começa com as mesmas letras de `PROVIDE` e É uma resposta.
    """
    texto = str(valor or "").strip().upper()
    if not texto:
        return False
    return any(texto == marcador or texto.startswith(marcador + " (")
               for marcador in MARCADORES_DE_FALTANTE.values())


# O título da seção de especificações, por idioma. O `analyzer` já procurava
# os dois desde 2026-09-03 (`TITULOS_DAS_SPECS`) para achar a linha inicial;
# aqui o mesmo texto serve de PROVA DE IDIOMA — vem do próprio documento, e
# não de um parâmetro que alguém pode esquecer de passar. Ficha marcada no
# idioma errado não se denuncia sozinha.
TITULO_DAS_SPECS_POR_IDIOMA = {
    "pt": "ESPECIFICAÇÕES TÉCNICAS - INDIQUE AS ESPECIFICAÇÕES TÉCNICAS NO ESPAÇO LIVRE ABAIXO",
    "en": "TECHNICAL SPECIFICATIONS - INDICATE TECHNICAL SPECIFICATIONS IN THE FREE SPACE BELOW",
}


def idioma_da_ficha(ws):
    """`"pt"` ou `"en"`, deduzido do título da seção de especificações.

    Sem título reconhecido -> português, que é a ficha de sempre. Qualquer
    erro na leitura também: isto é conveniência de idioma, e não pode ser o
    motivo de uma ficha deixar de ser analisada.
    """
    try:
        for linha in ws.iter_rows(min_row=50, max_row=150, min_col=2, max_col=2):
            valor = linha[0].value
            if not valor:
                continue
            texto = str(valor).strip().upper()
            for idioma, titulo in TITULO_DAS_SPECS_POR_IDIOMA.items():
                if titulo in texto:
                    return idioma
    except Exception:
        pass
    return IDIOMA_PADRAO_DA_FICHA

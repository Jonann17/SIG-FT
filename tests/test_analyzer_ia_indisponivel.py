r"""
Teste do aviso quando a IA não responde no Analyzer.

Descoberto no 1º teste real do usuário (2026-08-11): o log de IA registrou
`sucesso: false` para `validar_ficha`, e mesmo assim o Analyzer produziu um
arquivo `..._completed_88%.xlsx`. O usuário concluiu, razoavelmente, que o
módulo tinha funcionado.

A causa é uma linha do código ORIGINAL (pré-refatoração):

    ai_valid_fixed = {k: True for k in dados_ia_validar}   # tudo VÁLIDO
    ...
    if ai_res:      # IA falhou -> `ai_res` é None -> bloco não roda
        ...
    for k, valid in ai_valid_fixed.items():
        if valid: total_score_earned += celulas_ai_map[k]['weight']

Ou seja: com a IA fora do ar, a ficha ganha 100% dos pontos que a IA deveria
julgar. A nota sai inflada e o único sinal era um `print` na janela preta.

Este teste NÃO trava a pontuação (mudá-la é decisão de produto, registrada em
PENDENCIAS.md) -- trava o AVISO, que é o que impedia o usuário de perceber.
"""
from __future__ import annotations

import inspect

from sigft.services import analyzer as analyzer_mod


def test_o_aviso_de_ia_indisponivel_existe_no_codigo():
    # Verificação estrutural: o serviço tem um ramo `if not ai_res` que avisa
    # ANTES de somar os pontos. Sem isso, a nota inflada volta a sair calada.
    fonte = inspect.getsource(analyzer_mod.DatasheetAnalyzer.processar_planilha)

    assert "if not ai_res:" in fonte, "sumiu o ramo que detecta IA indisponível"
    assert "INFLADA" in fonte, "o aviso precisa dizer que a nota não vale como aprovação"
    # E o aviso vem ANTES da soma dos pontos de IA.
    assert fonte.index("if not ai_res:") < fonte.index("total_score_earned += celulas_ai_map")


def test_o_aviso_sai_por_yield_e_nao_por_print():
    # `print` vai para a janela preta; `yield` vai para o console da UI, que é
    # onde o usuário está olhando. Foi exatamente essa diferença que fez o
    # problema passar despercebido.
    fonte = inspect.getsource(analyzer_mod.DatasheetAnalyzer.processar_planilha)
    trecho = fonte[fonte.index("if not ai_res:"):fonte.index("if ai_res:")]

    assert "yield" in trecho
    assert "print(" not in trecho

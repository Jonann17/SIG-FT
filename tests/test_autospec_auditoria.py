r"""O AutoSpec confere as respostas do FORNECEDOR contra o datasheet (2026-09-28).

Pedido do Luan: *"muitas vezes por preguica/desleixo eles respondem que
determinada caracteristica tecnica nao se aplica, o que nao e verdade, e essa
caracteristica esta nitidamente no datasheet que eu forneci"*. E: *"se
encontrar alguma divergencia com o mesmo dado do datasheet, voce apenas traz
isso no log de saida, mas nao sobrescreva"*.

Decisoes do usuario (spec
docs/superpowers/specs/2026-09-28-autospec-conferencia-fornecedor-design.md):

- "nao se aplica" com o valor no documento, e a PROVA conferida -> grava o
  valor do documento, com a resposta original no comentario da celula;
- divergencia de valor preenchido -> so no log, nada gravado;
- so a tabela de especificacoes; chamada de IA separada, sem tocar o
  preenchimento.
"""
from sigft.core.llm import prompts


# =============================================================================
# 1. O prompt da conferencia
# =============================================================================
def _prompt(context="<<<CONTEXTO>>>", lista="<<<LISTA>>>"):
    return prompts.montar_autospec_auditoria(
        "<<<NOME>>>", "<<<FAB>>>", "<<<DESC>>>", context, lista)


def test_o_prompt_interpola_o_material_e_termina_na_lista():
    texto = _prompt()
    for marca in ("<<<NOME>>>", "<<<FAB>>>", "<<<DESC>>>", "<<<CONTEXTO>>>"):
        assert marca in texto
    assert texto.endswith("<<<LISTA>>>")


def test_sem_contexto_o_prompt_diz_que_nao_ha_documento():
    assert "Nenhuma informação disponível." in _prompt(context="")
    assert "Nenhuma informação disponível." in _prompt(context=None)


def test_o_prompt_pede_a_prova_so_na_divergencia():
    texto = _prompt()
    assert '"situacao": "confere" | "diverge" | "nao_consta"' in texto
    assert '"valor_documento"' in texto and '"trecho"' in texto
    assert 'responda só a situação' in texto


def test_o_prompt_proibe_deducao():
    assert "Nunca deduza" in _prompt()


def test_o_prompt_diz_que_unidade_e_traducao_nao_sao_divergencia():
    texto = _prompt()
    assert "NÃO são divergência" in texto
    assert "24 Vcc = 24 VDC" in texto


def test_o_prompt_diz_que_nao_se_aplica_com_valor_no_documento_e_divergencia():
    texto = _prompt()
    assert '"Não se aplica"' in texto
    assert "a característica se aplica" in texto


def test_o_prompt_do_preenchimento_nao_mudou():
    """O preenchimento tem de continuar byte a byte igual -- a fixture do
    snapshot (tests/fixtures/prompts/autospec_prompt.txt) prova o texto; aqui
    so a garantia de que a conferencia NAO reaproveitou o prompt dele."""
    assert "CAMPOS A PREENCHER" not in _prompt()
    assert "RESPOSTAS DO FORNECEDOR A CONFERIR" in _prompt()

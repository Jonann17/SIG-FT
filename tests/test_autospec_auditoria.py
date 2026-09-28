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
import pytest

from sigft.core.llm import prompts
from sigft.services import autospec_auditoria as aud


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


# =============================================================================
# 2. A resposta da IA
# =============================================================================
IDS = ("var_row_80", "var_row_81", "var_row_82")


def test_a_resposta_e_lida_campo_a_campo_com_a_prova():
    bruto = {
        "var_row_80": {"situacao": "confere"},
        "var_row_81": {"situacao": "diverge", "valor_documento": "IP65", "tipo": "documento",
                       "fonte": "ds.pdf", "pagina": "2", "trecho": "Protection IP65",
                       "justificativa": "grau de protecao do invólucro"},
        "var_row_82": {"situacao": "nao_consta"},
    }
    itens = aud.ler_resposta(bruto, IDS)
    assert itens["var_row_80"].situacao == "confere"
    assert itens["var_row_82"].situacao == "nao_consta"
    divergente = itens["var_row_81"]
    assert divergente.situacao == "diverge"
    assert divergente.valor_documento == "IP65"
    assert divergente.prova.trecho == "Protection IP65"
    assert divergente.prova.pagina == 2
    assert divergente.prova.fonte == "ds.pdf"


def test_envelope_e_desembrulhado():
    itens = aud.ler_resposta({"respostas": {"var_row_80": {"situacao": "confere"}}}, IDS)
    assert itens["var_row_80"].situacao == "confere"


@pytest.mark.parametrize("escrito,esperado", [
    ("diverge", "diverge"), ("Divergente", "diverge"), ("DIVERGÊNCIA", "diverge"),
    ("não confere", "diverge"), ("nao_confere", "diverge"), ("diferente", "diverge"),
    ("confere", "confere"), ("Conferido", "confere"), ("OK", "confere"), ("igual", "confere"),
    ("nao_consta", "nao_consta"), ("não consta", "nao_consta"), ("", "nao_consta"),
    (None, "nao_consta"), ("talvez", "nao_consta"),
])
def test_a_situacao_escrita_de_outro_jeito_e_normalizada(escrito, esperado):
    itens = aud.ler_resposta({"var_row_80": {"situacao": escrito}}, IDS)
    assert itens["var_row_80"].situacao == esperado


def test_situacao_como_string_solta_tambem_vale():
    """Modelo que responde `{"ID": "confere"}` em vez do objeto."""
    assert aud.ler_resposta({"var_row_80": "confere"}, IDS)["var_row_80"].situacao == "confere"


def test_campo_nao_pedido_e_ignorado():
    assert "var_row_99" not in aud.ler_resposta({"var_row_99": {"situacao": "diverge"}}, IDS)


def test_diverge_sem_prova_fica_com_trecho_vazio():
    item = aud.ler_resposta({"var_row_80": {"situacao": "diverge", "valor_documento": "5"}},
                            IDS)["var_row_80"]
    assert item.valor_documento == "5" and item.prova.trecho == ""


@pytest.mark.parametrize("bruto", [None, ["confere"], "confere"])
def test_resposta_que_nao_e_objeto_e_recusada(bruto):
    with pytest.raises(ValueError, match="objeto JSON"):
        aud.ler_resposta(bruto, IDS)


# =============================================================================
# 3. Fornecedor e documento dizem a MESMA coisa?
# =============================================================================
@pytest.mark.parametrize("fornecedor,documento,pergunta", [
    ("24 Vcc", "24 VDC", ""),
    ("24Vcc", "24 VDC", ""),
    ("0,5 kW", "500 W", ""),
    ("10 bar", "1 MPa", ""),
    ("36", "36 mm", "4 - DIAMETRO (mm)"),
    ("-20 a 60 °C", "-20 °C to +60 °C", ""),
    ("Aço Inox", "aco inox", ""),
    ("Aço inox.", "AÇO INOX", ""),
])
def test_mesmo_valor_em_outra_forma_e_equivalente(fornecedor, documento, pergunta):
    assert aud.equivalentes(fornecedor, documento, pergunta)


@pytest.mark.parametrize("fornecedor,documento", [
    ("IP54", "IP65"),
    ("5 bar", "3 bar"),
    ("220 V", "220/380 V"),     # o documento diz MAIS que o fornecedor
    ("41 g", "41 kg"),
    ("Aço carbono", "Stainless steel AISI 316"),
    ("Aço inox", "Stainless steel"),   # traducao: quem julga e a IA, nao o app
    ("", "24 V"),
    ("24 V", ""),
])
def test_valor_diferente_nao_e_equivalente(fornecedor, documento):
    assert not aud.equivalentes(fornecedor, documento)


# =============================================================================
# 4. A lista que vai para o prompt
# =============================================================================
def test_a_lista_leva_id_pergunta_e_resposta_do_fornecedor():
    lista = aud.montar_lista({
        "var_row_85": {"desc": "7 - TENSAO NOMINAL (V)", "ref": "M85",
                       "resposta": "  Não se   aplica ", "nao_se_aplica": True},
        "var_row_86": {"desc": "8 - GRAU DE PROTECAO", "ref": "M86",
                       "resposta": "IP54", "nao_se_aplica": False},
    })
    linhas = lista.splitlines()
    assert linhas[0] == "- ID 'var_row_85': 7 - TENSAO NOMINAL (V) -> o fornecedor respondeu: \"Não se aplica\""
    assert linhas[1] == "- ID 'var_row_86': 8 - GRAU DE PROTECAO -> o fornecedor respondeu: \"IP54\""


def test_resposta_enorme_e_cortada_na_lista():
    lista = aud.montar_lista({"var_row_85": {"desc": "X", "ref": "M85",
                                             "resposta": "a" * 1000, "nao_se_aplica": False}})
    assert len(lista) < 400


# =============================================================================
# 5. O log e o resumo
# =============================================================================
def _resultado():
    r = aud.ResultadoAuditoria()
    r.na_preenchidos.append(("7 - TENSAO NOMINAL", "N/A", "24 Vcc", "ds.pdf, pag. 2"))
    r.divergencias.append(("12 - GRAU DE PROTECAO", "IP54", "IP65", "ds.pdf, pag. 1",
                           "Degree of protection IP65", "invólucro"))
    r.na_mantidos = 3
    r.conferem = 11
    r.sem_dado = 1
    r.descartados.append(("9 - PESO", "o trecho citado nao esta no documento lido"))
    return r


def test_o_log_diz_o_que_foi_gravado_e_o_que_so_foi_apontado():
    texto = "\n".join(linha for _nivel, linha in _resultado().linhas_de_log())
    assert "ESTAO no documento" in texto
    assert "fornecedor 'N/A' -> documento '24 Vcc' (ds.pdf, pag. 2)" in texto
    assert "NADA foi alterado na ficha" in texto
    assert "fornecedor 'IP54' x documento 'IP65' (ds.pdf, pag. 1)" in texto
    assert 'trecho: "Degree of protection IP65"' in texto
    assert "3 resposta(s)" in texto and "11 resposta(s) conferem" in texto
    assert "9 - PESO" in texto and "o trecho citado nao esta" in texto


def test_divergencia_e_aviso_no_log():
    niveis = dict((linha[:30], nivel) for nivel, linha in _resultado().linhas_de_log())
    assert any(n == "warn" for n in niveis.values())


def test_o_log_nao_usa_travessao():
    """tests/test_texto_da_ui.py: nada de travessao em texto de log."""
    for _nivel, linha in _resultado().linhas_de_log():
        assert chr(0x2014) not in linha


def test_nada_a_dizer_quando_nada_foi_conferido():
    assert aud.ResultadoAuditoria().linhas_de_log() == []


def test_o_resumo_do_lote():
    assert _resultado().resumo() == (
        "conferida: 1 'nao se aplica' preenchido(s) com o documento, "
        "1 divergencia(s) no log")
    vazio = aud.ResultadoAuditoria()
    vazio.conferem = 4
    assert vazio.resumo() == "conferida: nenhuma divergencia"

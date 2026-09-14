r"""O trio dimensional, e o corretor que fabricava valor (2026-09-14).

**O que o usuário viu.** O AutoSpec leu o datasheet `UCSC CONTROLLERS.pdf` e
escreveu na ficha `4500063671.0912`:

    18 - DIMENSOES (...): 55,118 x 55,118 x 55 mm (sem montagem); ...

quando o documento diz, com todas as letras:

    UCSCH1, UCSCH2, UCSCS2: 168 x 150 x 55 mm (6.61 x 5.90 x 2.17 in)

**O que a investigação mostrou** (medido, não deduzido):

1. A extração do PDF está **limpa** — o PyMuPDF entrega a linha com espaços e
   tudo. Não era OCR.
2. O RAG entrega a linha certa no contexto recortado. Não era retrieval.
3. `55.118` **não existe** no documento. É `2.17 in x 25,4`.
4. A IA **acertou.** Quem reescreveu foi o aplicativo: passando
   `"168 x 150 x 55 mm"` por `_filtrar_por_lastro`, sai
   `"55,118 x 55,118 x 55 mm"`.
5. E o mesmo caminho **aprova valor inventado**: `"999 x 888 x 777 mm"` sai
   como `"55,118 x 55,118 x 55,118 mm"`. A guarda que existe para barrar
   número inventado estava fabricando um.

**As duas causas, encadeadas:**

- `extrair_medidas` não entende `A x B x C unidade`: só o número colado na
  unidade vira medida. Num documento, `168 x 150 x 55 mm` dá **uma** medida
  (`55 mm`) — `168` e `150` somem. Então a resposta certa não acha par, e o
  lastro a reprova.
- Reprovada, ela cai em `corrigir_conversao`, que procura uma medida de
  comprimento em **outra unidade**, acha `2.17 in`, converte e **substitui**.

O conserto tem duas partes, e as duas são necessárias: a primeira faz a
resposta certa passar; a segunda impede que a errada seja inventada.
"""
import pytest

from sigft.services import autospec, autospec_unidades as un

# Copia literal do datasheet (página 8, extraída com PyMuPDF).
CONTEXTO = """Dimensions (H x D x W)
UCSCH1, UCSCH2, UCSCS2: 168 x 150 x 55 mm (6.61 x 5.90 x 2.17 in)
UCSCH1, UCSCH2, UCSCS2 with mounting: 204 x 152 x 55 mm (8.03 x 5.99 x 2.17 in)
UCECH1: 168 x 150 x 85 mm (6.61 x 5.91 x 3.35 in)"""

PERGUNTA = ("18 - DIMENSOES (Indicar o dimensional do item em mm. "
            "Ex.: 72,00 x 90,00 x 55,00 mm.)")


# =============================================================================
# A. O trio dimensional: `A x B x C unidade` são TRÊS medidas
# =============================================================================
def test_o_trio_dimensional_da_TRES_medidas():
    """`168 x 150 x 55 mm` é três medidas em milímetro, não uma.

    A unidade é escrita uma vez e vale para as três — é assim que todo
    datasheet do mundo escreve dimensão."""
    medidas = un.extrair_medidas("168 x 150 x 55 mm")
    assert sorted(medidas) == [(55.0, "mm"), (150.0, "mm"), (168.0, "mm")]


def test_o_par_dimensional_tambem(
):
    """`100 x 50 mm` — dois números, mesma regra."""
    assert sorted(un.extrair_medidas("100 x 50 mm")) == [(50.0, "mm"), (100.0, "mm")]


@pytest.mark.parametrize("separador", ["x", "X", "×"])
def test_os_separadores_que_aparecem_de_verdade(separador):
    texto = f"168 {separador} 150 {separador} 55 mm"
    assert len(un.extrair_medidas(texto)) == 3, texto


def test_sem_espaco_tambem_conta():
    """`168x150x55mm` — é como sai de muita extração de PDF."""
    assert len(un.extrair_medidas("168x150x55mm")) == 3


def test_o_documento_passa_a_enxergar_as_tres_dimensoes():
    """O lado que mais importa: no CONTEXTO, `168` e `150` viram medida em
    mm. Sem isso, a resposta certa nunca acha par."""
    medidas = un.extrair_medidas(CONTEXTO)
    em_mm = {v for v, u in medidas if u == "mm"}
    for esperado in (168.0, 150.0, 55.0, 204.0, 152.0, 85.0):
        assert esperado in em_mm, f"{esperado} mm sumiu do documento: {sorted(em_mm)}"


def test_as_polegadas_continuam_sendo_polegadas():
    """O trio entre parênteses é em `in`, e não pode contaminar o de mm."""
    medidas = un.extrair_medidas(CONTEXTO)
    em_pol = {v for v, u in medidas if u == "in"}
    for esperado in (6.61, 5.90, 2.17, 8.03, 5.99, 3.35, 5.91):
        assert esperado in em_pol, f"{esperado} in sumiu: {sorted(em_pol)}"
    assert 168.0 not in em_pol, "milimetro virou polegada"


def test_o_intervalo_continua_funcionando():
    """Regressão: a herança de unidade já existia para intervalo
    (`0 a +70 C`). Não pode quebrar."""
    assert sorted(un.extrair_medidas("-40 a 70 °C")) == [(-40.0, "c"), (70.0, "c")]


def test_numero_solto_sem_unidade_continua_sem_unidade():
    """A herança é local. `x` não pode virar uma licença para grudar unidade
    em qualquer número da frase."""
    assert un.extrair_medidas("modelo 1000 do catalogo, pressao 350 bar") == [(350.0, "bar")]


# =============================================================================
# B. A resposta CERTA passa no lastro
# =============================================================================
def test_a_resposta_certa_tem_lastro():
    """O caso do usuário, na direção que importa."""
    assert autospec.valor_tem_lastro("168 x 150 x 55 mm", CONTEXTO) is True


def test_a_resposta_certa_com_os_dois_modelos_tem_lastro():
    assert autospec.valor_tem_lastro(
        "168 x 150 x 55 mm (sem montagem); 204 x 152 x 55 mm (com montagem)",
        CONTEXTO) is True


def test_uma_dimensao_inventada_continua_sem_lastro():
    """A guarda não pode afrouxar: `999` não está no documento."""
    assert autospec.valor_tem_lastro("999 x 888 x 777 mm", CONTEXTO) is False


def test_dimensao_com_a_unidade_errada_continua_sem_lastro():
    """`168 x 150 x 55 cm` é mil vezes maior que o documento."""
    assert autospec.valor_tem_lastro("168 x 150 x 55 cm", CONTEXTO) is False


# =============================================================================
# C. O corretor não inventa mais
# =============================================================================
def test_o_corretor_NAO_reescreve_numero_sem_relacao_com_a_origem():
    """O coração do defeito: `168` não tem parentesco nenhum com `2.17 in`.
    Trocar um pelo outro não é corrigir aritmética, é inventar dado."""
    corrigido, motivo = un.corrigir_conversao("999 x 888 x 777 mm", CONTEXTO,
                                              pergunta=PERGUNTA)
    assert corrigido is None, f"fabricou {corrigido!r} ({motivo})"


def test_a_resposta_inventada_NAO_entra_na_ficha():
    """Ponta a ponta, pelo caminho que o usuário percorreu."""
    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    aprovados = core._filtrar_por_lastro(
        {"var_row_18": "999 x 888 x 777 mm"},
        {"var_row_18": {"desc": PERGUNTA}}, CONTEXTO)
    assert not aprovados.get("var_row_18"), \
        f"valor inventado entrou como {aprovados.get('var_row_18')!r}"


def test_a_resposta_CERTA_sai_intacta_do_filtro():
    """A regressão que mais dói: o aplicativo não pode reescrever o que a IA
    acertou."""
    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    resposta = "168 x 150 x 55 mm (sem montagem); 204 x 152 x 55 mm (com montagem)"
    aprovados = core._filtrar_por_lastro(
        {"var_row_18": resposta}, {"var_row_18": {"desc": PERGUNTA}}, CONTEXTO)
    assert aprovados.get("var_row_18") == resposta


# =============================================================================
# D. A correção LEGÍTIMA continua acontecendo
# =============================================================================
# O corretor existe por pedido do usuário (2026-08-13): quando a IA lê o
# número certo e erra só a conta, o dado é bom e a aritmética é do computador.
# Apertar a regra não pode matar isso.

CTX_PRESSAO = "Maximum operating pressure: 350 bar"


def test_erro_de_ORDEM_DE_GRANDEZA_continua_sendo_corrigido():
    """`3,5 MPa` a partir de `350 bar`: a leitura foi certa (350), a conta
    errou por 10. Os algarismos são os mesmos — 35 — e é isso que prova que
    a origem é a mesma."""
    corrigido, motivo = un.corrigir_conversao("3,5 MPa", CTX_PRESSAO,
                                              pergunta="PRESSAO DE TRABALHO")
    assert corrigido is not None, motivo
    assert "35" in corrigido


def test_unidade_trocada_sem_converter_continua_sendo_corrigido():
    """`350 MPa` a partir de `350 bar`: a IA copiou o número e trocou a
    unidade. A origem é inequívoca — é o próprio número."""
    corrigido, motivo = un.corrigir_conversao("350 MPa", CTX_PRESSAO,
                                              pergunta="PRESSAO DE TRABALHO")
    assert corrigido is not None, motivo
    assert "35" in corrigido


def test_numero_errado_na_MESMA_unidade_do_documento_nao_e_corrigido():
    """A regra que separa "errou a conta" de "escreveu outro número".

    O documento fala em `mm` e a resposta está em `mm`: **não houve conversão
    nenhuma**. Se o número não bate, ele está errado — e reescrevê-lo a partir
    das polegadas seria fabricar dado, que foi exatamente o defeito.

    Repare no contraste com o teste acima: lá o documento fala `bar` e a
    resposta vem em `MPa`, então houve conversão e a conta pode ser refeita.
    """
    corrigido, motivo = un.corrigir_conversao("999 mm", CONTEXTO, pergunta=PERGUNTA)
    assert corrigido is None, f"fabricou {corrigido!r}"
    assert "mm" in motivo and "outro" in motivo, motivo


def test_a_correcao_continua_valendo_quando_HOUVE_conversao():
    """A contraprova, para o conserto não virar "desligar o corretor": com o
    documento em `bar` e a resposta em `MPa`, a conta é refeita como sempre.

    `7 MPa` não sai de `350 bar` por conta nenhuma — mas o documento tem UMA
    pressão só, então a origem é inequívoca, e foi essa a decisão do usuário
    em 2026-08-13: dado bom, aritmética do computador."""
    corrigido, _motivo = un.corrigir_conversao("7 MPa", CTX_PRESSAO,
                                               pergunta="PRESSAO DE TRABALHO")
    assert corrigido == "35 MPa"

r"""
Três defeitos do `tech_specs` medidos contra o Master REAL (2026-08-18).

O usuário mandou `PDMs SAM-GM (1193).xlsx` e a ficha `4500063671.1453.xlsx`. Ler
os dois derrubou uma conclusão anterior e explicou três sintomas:

  1. **A revisão NÃO era irrecuperável.** A entrada de PENDENCIAS dizia que
     sim; estava errada. `TEMPLATE_PDM` tem a coluna `REVISIÓN`, e o cabeçalho
     de verdade está na LINHA 6 (a linha 3 é um cabeçalho de layout, com
     outros nomes: "Clase PDM", "Formato"…).

  2. **O "lixo" de REMOVER é revisão antiga.** Medido:

         PDM.4820.015   revisão 0: 42 características
                        revisão 1: 20  <- vigente
                        união:     44  <- o que entrava no JSON
                        lixo:      24

     Os 24 batem, nome por nome, com os `REMOVER` que o usuário não
     reconheceu (CONTINUACAO 1..4, COR, COMPRIMENTO…). E **1.023 dos 1.194
     PDMs** têm mais de uma revisão: não é caso isolado.

  3. **O limite de casas decimais é a regra, não a exceção.** Das 6.085 linhas
     `NUM`, **6.060 aceitam exatamente 2 casas**. Todo valor mais preciso que
     centésimo bate nisso -- é o "0,002" que o usuário relatou.

Também medido, e é o que torna o recuo para CHAR viável: **32.578 das 32.655
linhas aceitam `AD`** entre os símbolos (99,8%).
"""
import pytest

from sigft.services import tech_specs as ts


# =============================================================================
# 1. Revisão vigente
# =============================================================================
class _DataFrameFalso:
    """Mínimo do que `filtrar_revisao_vigente` usa: `.columns` e `df[coluna]`
    para ler, `df[lista_de_bool]` para filtrar. Um `DataFrame` de verdade não
    entra aqui porque `pandas` é stub na suíte."""

    def __init__(self, linhas):
        self.linhas = list(linhas)
        self.columns = sorted({c for l in self.linhas for c in l})

    def __getitem__(self, chave):
        if isinstance(chave, list):
            return _DataFrameFalso([l for l, manter in zip(self.linhas, chave) if manter])
        return [l.get(chave) for l in self.linhas]

    def __len__(self):
        return len(self.linhas)


def _pdm(revisoes):
    return _DataFrameFalso([{"REVISIÓN": r, "CARACTERÍSTICA - DESCRIPCIÓN PT": n}
                            for r, nomes in revisoes.items() for n in nomes])


def test_fica_so_com_a_maior_revisao():
    df = _pdm({"0": ["COR", "COMPRIMENTO", "CLASSE DE PRESSAO"],
               "1": ["CLASSE DE PRESSAO", "MATERIAL DO PRATO"]})

    vigente = ts.filtrar_revisao_vigente(df)

    assert sorted(vigente["CARACTERÍSTICA - DESCRIPCIÓN PT"]) == [
        "CLASSE DE PRESSAO", "MATERIAL DO PRATO"]


def test_o_lixo_da_revisao_antiga_some():
    """O sintoma exato que o usuário relatou: COR e COMPRIMENTO só existem na
    revisão 0 e chegavam ao JSON como REMOVER."""
    df = _pdm({"0": ["COR", "COMPRIMENTO"], "1": ["MATERIAL DO PRATO"]})

    restantes = ts.filtrar_revisao_vigente(df)["CARACTERÍSTICA - DESCRIPCIÓN PT"]

    assert "COR" not in restantes and "COMPRIMENTO" not in restantes


def test_a_deduplicacao_sozinha_NAO_resolvia():
    """Por que o filtro precisou existir: `deduplicar_contexto` colapsa nomes
    REPETIDOS entre revisões, mas característica que existiu só na revisão
    antiga tem nome ÚNICO -- passa pelo filtro e chega ao JSON."""
    contexto = [{"CARACTERISTICA_DESC_PT": n}
                for n in ("CLASSE DE PRESSAO", "COR", "CLASSE DE PRESSAO")]

    unicos = [c["CARACTERISTICA_DESC_PT"] for c in ts.deduplicar_contexto(contexto)]

    assert "COR" in unicos, "a deduplicação não tem como saber que COR é de outra revisão"


def test_revisao_nao_numerica_perde_para_uma_de_verdade():
    df = _pdm({"": ["VELHA"], "2": ["NOVA"]})

    assert ts.filtrar_revisao_vigente(df)["CARACTERÍSTICA - DESCRIPCIÓN PT"] == ["NOVA"]


def test_master_sem_a_coluna_de_revisao_devolve_tudo():
    """Descartar o PDM inteiro por causa de uma coluna ausente trocaria um
    problema visível por um mudo."""
    df = _DataFrameFalso([{"CARACTERÍSTICA - DESCRIPCIÓN PT": "X"}])

    assert len(ts.filtrar_revisao_vigente(df)) == 1


# =============================================================================
# 2. Casas decimais
# =============================================================================
@pytest.mark.parametrize("valor,esperado", [
    ("0,002", 3), ("40,79", 2), ("240", 0), ("1.5", 1), ("", 0), (None, 0),
    ("12 / 40", 0),
])
def test_conta_as_casas_decimais(valor, esperado):
    assert ts.casas_decimais_de(valor) == esperado


def test_o_caso_relatado_pelo_usuario_nao_cabe():
    """"Tenho que colocar 0,002 e o campo aceita apenas 2 unidades após a
    vírgula" -- e 6.060 das 6.085 linhas NUM do Master são assim."""
    assert ts.cabe_nas_casas("0,002", "2") is False
    assert ts.cabe_nas_casas("40,79", "2") is True


@pytest.mark.parametrize("limite", ["", None, "abc"])
def test_limite_ilegivel_assume_que_cabe(limite):
    """Lado seguro: um limite que não conseguimos ler não pode virar motivo
    para mover uma característica de lugar."""
    assert ts.cabe_nas_casas("0,00001", limite) is True


def _dados():
    return [
        {"CARACTERISTICA_CHAVE": "PRESSAO DE ABERTURA", "TIPO": "NUM",
         "ACAO": "PREENCHER", "RESPOSTA_PT_FINAL": "0,002", "SIMBOLO": "kgf/cm²"},
        {"CARACTERISTICA_CHAVE": "PRESSAO MAXIMA DE TRABALHO", "TIPO": "NUM",
         "ACAO": "PREENCHER", "RESPOSTA_PT_FINAL": "40,79", "SIMBOLO": "kgf/cm²"},
        {"CARACTERISTICA_CHAVE": "CARACTERISTICAS ADICIONAIS", "TIPO": "CHAR",
         "ACAO": "PREENCHER", "RESPOSTA_PT_FINAL": "N/A", "RESPOSTA_ES_FINAL": "N/A"},
    ]


def test_o_que_nao_cabe_vai_para_o_texto_livre_com_nome_e_valor():
    ajustados, movidas = ts.realocar_por_casas_decimais(
        _dados(), {"PRESSAO DE ABERTURA": "2", "PRESSAO MAXIMA DE TRABALHO": "2"})

    assert movidas == ["PRESSAO DE ABERTURA"]
    livre = [d for d in ajustados
             if d["CARACTERISTICA_CHAVE"] == "CARACTERISTICAS ADICIONAIS"][0]
    assert livre["RESPOSTA_PT_FINAL"] == "PRESSAO DE ABERTURA: 0,002 kgf/cm²"


def test_o_que_cabe_fica_onde_estava():
    ajustados, _ = ts.realocar_por_casas_decimais(
        _dados(), {"PRESSAO DE ABERTURA": "2", "PRESSAO MAXIMA DE TRABALHO": "2"})
    maxima = [d for d in ajustados
              if d["CARACTERISTICA_CHAVE"] == "PRESSAO MAXIMA DE TRABALHO"][0]

    assert maxima["ACAO"] == "PREENCHER"
    assert maxima["RESPOSTA_PT_FINAL"] == "40,79"


def test_a_caracteristica_movida_vira_REMOVER():
    """Deixá-la como PREENCHER faria o robô tentar de novo e falhar de novo;
    deixá-la em branco no portal confundiria "não coube" com "não se aplica"."""
    ajustados, _ = ts.realocar_por_casas_decimais(_dados(), {"PRESSAO DE ABERTURA": "2"})
    origem = [d for d in ajustados
              if d["CARACTERISTICA_CHAVE"] == "PRESSAO DE ABERTURA"][0]

    assert origem["ACAO"] == "REMOVER"


def test_varias_entram_uma_por_linha():
    """"Se tiver outras, colocamos mais de uma, separadas por uma quebra de
    linha" -- pedido do usuário."""
    dados = _dados()
    dados[1]["RESPOSTA_PT_FINAL"] = "0,00123"

    ajustados, movidas = ts.realocar_por_casas_decimais(
        dados, {"PRESSAO DE ABERTURA": "2", "PRESSAO MAXIMA DE TRABALHO": "2"})
    livre = [d for d in ajustados
             if d["CARACTERISTICA_CHAVE"] == "CARACTERISTICAS ADICIONAIS"][0]

    assert len(movidas) == 2
    assert livre["RESPOSTA_PT_FINAL"].count("\n") == 1


def test_o_NA_do_texto_livre_e_substituido_e_nao_concatenado():
    """"N/A" é resposta de "não há", e o que estamos acrescentando É conteúdo
    -- manter os dois faria a ficha dizer as duas coisas."""
    ajustados, _ = ts.realocar_por_casas_decimais(_dados(), {"PRESSAO DE ABERTURA": "2"})
    livre = [d for d in ajustados
             if d["CARACTERISTICA_CHAVE"] == "CARACTERISTICAS ADICIONAIS"][0]

    assert not livre["RESPOSTA_PT_FINAL"].startswith("N/A")


def test_texto_livre_com_conteudo_real_e_PRESERVADO():
    dados = _dados()
    dados[2]["RESPOSTA_PT_FINAL"] = "Montagem entre flanges."
    dados[2]["RESPOSTA_ES_FINAL"] = "Montaje entre bridas."

    ajustados, _ = ts.realocar_por_casas_decimais(dados, {"PRESSAO DE ABERTURA": "2"})
    livre = [d for d in ajustados
             if d["CARACTERISTICA_CHAVE"] == "CARACTERISTICAS ADICIONAIS"][0]

    assert livre["RESPOSTA_PT_FINAL"].startswith("Montagem entre flanges.")
    assert "PRESSAO DE ABERTURA: 0,002" in livre["RESPOSTA_PT_FINAL"]


def test_sem_campo_de_texto_livre_nada_e_movido():
    """Sem destino, mover viraria apagar. Melhor devolver como estava."""
    dados = [d for d in _dados() if d["CARACTERISTICA_CHAVE"] != "CARACTERISTICAS ADICIONAIS"]

    ajustados, movidas = ts.realocar_por_casas_decimais(dados, {"PRESSAO DE ABERTURA": "2"})

    assert movidas == []
    assert all(d["ACAO"] == "PREENCHER" for d in ajustados)


def test_REMOVER_nao_e_mexido():
    dados = [{"CARACTERISTICA_CHAVE": "COR", "ACAO": "REMOVER"}]

    ajustados, movidas = ts.realocar_por_casas_decimais(dados, {"COR": "2"})

    assert movidas == [] and ajustados == dados


# =============================================================================
# 3. Recuo para CHAR
# =============================================================================
def test_junta_valor_e_unidade():
    """"Juntar as duas informações e colocar em CHAR" -- pedido do usuário."""
    assert ts.juntar_para_char(
        {"RESPOSTA_PT_FINAL": "40,79", "SIMBOLO": "kgf/cm²"}) == "40,79 kgf/cm²"


def test_intervalo_leva_tambem_o_subtipo():
    assert ts.juntar_para_char({
        "RESPOSTA_PT_FINAL": "12 / 40", "SIMBOLO": "mm",
        "SUBTIPO_INTERVALO": "MINIMO / MAXIMO"}) == "12 / 40 mm (MINIMO / MAXIMO)"


def test_simbolo_adimensional_nao_polui_o_texto():
    """`AD` significa "sem unidade" -- escrevê-lo seria ruído."""
    assert ts.juntar_para_char(
        {"RESPOSTA_PT_FINAL": "Flange", "SIMBOLO": "AD"}) == "Flange"


def test_subtipo_nulo_nao_vira_texto():
    assert ts.juntar_para_char(
        {"RESPOSTA_PT_FINAL": "5", "SIMBOLO": "AD", "SUBTIPO_INTERVALO": None}) == "5"

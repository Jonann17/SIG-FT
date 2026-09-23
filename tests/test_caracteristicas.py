r"""O LEITOR da tabela de Características Técnicas do portal (E1).

Por que ele não existia: até 2026-09-23 o app sabia **escrever**
(`tech_specs._preencher_linha`) e **apagar** (`duplicadas_injetor.
limpar_caracteristicas`) características, mas nunca precisou LER o valor de
uma. O módulo de correção de PDM precisa, porque trocar o PDM faz o portal
apagar todas -- inclusive as que o PDM novo também tem.

O plano está em `docs/refatoracao/CORRECAO_PDM.md`.

O QUE ESTE LEITOR HERDA, E NÃO REDESCOBRE
------------------------------------------------------------------------
  - a **paginação** e o laço da tabela, de `limpar_caracteristicas`;
  - a pergunta **"que tipo esta linha oferece?"** feita à TELA, de
    `tech_specs._tipo_da_linha` -- e não ao Master, porque 35,7% das
    características mudam de tipo entre revisões;
  - a leitura da descrição por `textContent`: numa tabela rolável, a célula
    fora da viewport devolve string VAZIA em `.text`.

⚠️ NÃO É PROVA DE PORTAL. Os testes rodam contra um dublê de `RPAEngine` e
provam a LÓGICA (os 4 tipos, a paginação, o formato `<código>-<NOME>`). Se um
seletor estiver errado, tudo passa verde e nada funciona -- a validação é a
etapa E6 do plano, em sessão local.
"""
from __future__ import annotations

import re

from sigft.core.rpa import caracteristicas as carac


# =============================================================================
# Dublê de motor: uma tabela de portal descrita em dados
# =============================================================================
class _EngineDeTabela:
    """Responde como o portal responderia para as `paginas` declaradas.

    Cada linha é um dict com as chaves que aquele TIPO teria na tela -- é
    assim que o dublê representa "esta linha oferece textarea PT" sem
    precisar de HTML.
    """

    def __init__(self, paginas):
        self.paginas = paginas
        self.pagina = 0
        self.cliques = []

    # -- o que o leitor usa -------------------------------------------------
    def contar(self, seletor):
        if carac.XPATH_PROXIMA_PAGINA in seletor:
            return 1 if self.pagina < len(self.paginas) - 1 else 0
        if seletor == carac.XPATH_LINHAS:
            return len(self.paginas[self.pagina])
        return 1 if self._campo(seletor) is not None else 0

    def element_exists(self, seletor):
        return self.contar(seletor) > 0

    def esta_habilitado(self, _seletor):
        return self.pagina < len(self.paginas) - 1

    def texto(self, seletor):
        return str(self._campo(seletor) or "")

    def get_value(self, seletor):
        return str(self._campo(seletor) or "")

    def texto_selecionado(self, seletor):
        return str(self._campo(seletor) or "")

    def click_raw(self, seletor):
        self.cliques.append(seletor)
        if carac.XPATH_PROXIMA_PAGINA in seletor:
            self.pagina += 1

    # -- tradução seletor -> campo da linha ---------------------------------
    def _campo(self, seletor):
        # O indice esta em `)[N]`, logo apos o fecha-parenteses -- e NAO no
        # primeiro `[` do seletor: o XPath das linhas tem colchetes dentro
        # (`contains(@id, ...)`), e partir por eles pega o pedaco errado.
        achado = re.search(r"\)\[(\d+)\]", seletor)
        if not achado:
            return None
        indice = int(achado.group(1)) - 1
        linhas = self.paginas[self.pagina]
        if indice >= len(linhas):
            return None
        linha = linhas[indice]
        for chave, relativo in (
            ("descricao", carac.REL_DESCRICAO),
            ("valor_pt", carac.REL_VALOR_PT),
            ("valor_es", carac.REL_VALOR_ES),
            ("numero", carac.REL_INPUT_NUM),
            ("minimo", carac.REL_INPUT_MIN),
            ("maximo", carac.REL_INPUT_MAX),
            ("lista", carac.REL_SELECT_LISTA),
            ("subtipo", carac.REL_SELECT_INTERVALO),
            ("unidade", carac.REL_SELECT_UNIDADE),
        ):
            if seletor.endswith(relativo):
                return linha.get(chave)
        return None


def _engine(*paginas):
    return _EngineDeTabela(list(paginas))


# =============================================================================
# A. `<código>-<NOME>` -- a chave do casamento
# =============================================================================
def test_separa_o_codigo_do_nome():
    """O portal mostra `1064-CORRENTE NOMINAL`. O código é a chave do
    casamento (2278 códigos ↔ 2278 nomes no Master, bijeção perfeita) e o
    nome vira conferência."""
    assert carac.codigo_e_nome("1064-CORRENTE NOMINAL") == ("1064", "CORRENTE NOMINAL")


def test_separa_com_espacos_em_volta_do_hifen():
    assert carac.codigo_e_nome("1064 - CORRENTE NOMINAL") == ("1064", "CORRENTE NOMINAL")


def test_sem_codigo_o_nome_vem_inteiro():
    """Não inventar código: sem ele o casamento cai para o nome, e quem
    decide isso é quem casa, não quem lê."""
    assert carac.codigo_e_nome("CORRENTE NOMINAL") == ("", "CORRENTE NOMINAL")


def test_descricao_vazia_nao_estoura():
    assert carac.codigo_e_nome("") == ("", "")
    assert carac.codigo_e_nome(None) == ("", "")


def test_colapsa_espaco_e_quebra_de_linha_do_textContent():
    """`textContent` traz a indentação do HTML junto."""
    assert carac.codigo_e_nome("  1064 -\n  CORRENTE  NOMINAL ") == (
        "1064", "CORRENTE NOMINAL")


# =============================================================================
# B. Ler uma linha de cada tipo
# =============================================================================
def test_le_uma_linha_CHAR_com_os_dois_idiomas():
    """A ficha é bilíngue. Ler só o português perderia metade -- é o mesmo
    defeito que `limpar_caracteristicas` levou a corrigir em 2026-08-20."""
    engine = _engine([{
        "descricao": "1171-ACABAMENTO", "valor_pt": "PINTADO",
        "valor_es": "PINTADO", "unidade": "AD",
    }])

    lida = carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]")

    assert lida.codigo == "1171"
    assert lida.nome == "ACABAMENTO"
    assert lida.tipo == "CHAR"
    assert lida.valor_pt == "PINTADO"
    assert lida.valor_es == "PINTADO"
    assert lida.unidade == "AD"


def test_le_uma_linha_NUM():
    engine = _engine([{
        "descricao": "1230-TENSAO NOMINAL", "numero": "220", "unidade": "V",
    }])

    lida = carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]")

    assert lida.tipo == "NUM"
    assert lida.valor_pt == "220"
    assert lida.unidade == "V"


def test_le_uma_linha_INT_com_minimo_e_maximo():
    """Intervalo tem DOIS inputs e um select de subtipo. Ler só um deles
    perderia a faixa."""
    engine = _engine([{
        "descricao": "1230-FAIXA DE TEMPERATURA", "minimo": "-10",
        "maximo": "50", "subtipo": "ENTRE", "unidade": "°C",
        "numero": None,
    }])

    lida = carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]")

    assert lida.tipo == "INT"
    assert lida.minimo == "-10"
    assert lida.maximo == "50"
    assert lida.subtipo == "ENTRE"


def test_le_uma_linha_LISTA_pelo_texto_da_opcao():
    """Pelo TEXTO, não pelo `value`: quem repõe é `selecionar_por_texto`."""
    engine = _engine([{
        "descricao": "1118-TIPO", "lista": "HIDRAULICO", "unidade": "AD",
    }])

    lida = carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]")

    assert lida.tipo == "LISTA"
    assert lida.valor_pt == "HIDRAULICO"


def test_o_tipo_vem_da_TELA_e_nao_de_quem_chama():
    """35,7% das características mudam de tipo entre revisões (3160 de 8841
    no Master). Confiar num tipo declarado é o defeito que este leitor evita
    desde a primeira linha."""
    engine = _engine([{
        "descricao": "1230-TENSAO", "numero": "220",
    }])

    assert carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]").tipo == "NUM"


def test_INT_e_testado_antes_de_NUM():
    """A linha de intervalo tem inputs numéricos e casaria como NUM por
    engano -- a mesma ordem que `tech_specs._tipo_da_linha` já usa."""
    engine = _engine([{
        "descricao": "1230-FAIXA", "minimo": "1", "maximo": "9",
        "subtipo": "ENTRE", "numero": "5",
    }])

    assert carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]").tipo == "INT"


def test_linha_sem_campo_nenhum_devolve_tipo_vazio():
    """Não saber é uma resposta. Chutar um tipo faria a reposição escrever no
    campo errado."""
    engine = _engine([{"descricao": "9999-DESCONHECIDA"}])

    lida = carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]")

    assert lida.tipo == ""
    assert lida.esta_vazia is True


# =============================================================================
# C. Vazio x preenchido -- o que vai para a lista de apagar
# =============================================================================
def test_linha_sem_valor_e_marcada_como_vazia():
    engine = _engine([{"descricao": "1171-ACABAMENTO", "valor_pt": "",
                       "valor_es": "", "unidade": "AD"}])

    assert carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]").esta_vazia is True


def test_linha_com_valor_so_em_espanhol_nao_e_vazia():
    """Meia ficha preenchida ainda é informação -- apagá-la perderia o que o
    fornecedor escreveu."""
    engine = _engine([{"descricao": "1171-ACABAMENTO", "valor_pt": "",
                       "valor_es": "PINTADO", "unidade": "AD"}])

    assert carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]").esta_vazia is False


def test_so_a_unidade_preenchida_nao_conta_como_valor():
    """A unidade vem escolhida por padrão em muitas linhas; tratá-la como
    valor faria o módulo achar que a ficha inteira está preenchida."""
    engine = _engine([{"descricao": "1230-TENSAO", "numero": "", "unidade": "V"}])

    assert carac.ler_linha(engine, f"({carac.XPATH_LINHAS})[1]").esta_vazia is True


# =============================================================================
# D. A tabela inteira, com paginação
# =============================================================================
def test_le_a_tabela_de_uma_pagina():
    engine = _engine([
        {"descricao": "1-UM", "valor_pt": "A", "unidade": "AD"},
        {"descricao": "2-DOIS", "valor_pt": "B", "unidade": "AD"},
    ])

    lidas = carac.ler_tabela(engine)

    assert [c.codigo for c in lidas] == ["1", "2"]


def test_le_todas_as_paginas():
    """Ler só a primeira página perderia o resto da ficha em silêncio -- é o
    mesmo motivo pelo qual `limpar_caracteristicas` pagina."""
    engine = _engine(
        [{"descricao": "1-UM", "valor_pt": "A"}],
        [{"descricao": "2-DOIS", "valor_pt": "B"}],
        [{"descricao": "3-TRES", "valor_pt": "C"}],
    )

    lidas = carac.ler_tabela(engine)

    assert [c.codigo for c in lidas] == ["1", "2", "3"]


def test_para_de_paginar_quando_o_botao_some():
    engine = _engine([{"descricao": "1-UM", "valor_pt": "A"}])

    carac.ler_tabela(engine)

    assert engine.cliques == []


def test_tabela_vazia_devolve_lista_vazia():
    assert carac.ler_tabela(_engine([])) == []


def test_paginacao_sem_fim_nao_trava_o_robo(monkeypatch):
    """Um botão que nunca desabilita giraria para sempre. `limpar_caracteristicas`
    já tem o mesmo teto, pelo mesmo motivo."""
    monkeypatch.setattr(carac, "MAX_PAGINAS", 3)

    class _Infinita(_EngineDeTabela):
        def contar(self, seletor):
            if carac.XPATH_PROXIMA_PAGINA in seletor:
                return 1
            return super().contar(seletor)

        def esta_habilitado(self, _seletor):
            return True

        def click_raw(self, seletor):
            self.cliques.append(seletor)

    engine = _Infinita([[{"descricao": "1-UM", "valor_pt": "A"}]])

    lidas = carac.ler_tabela(engine)

    assert len(lidas) <= 3

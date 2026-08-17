r"""
Escrita na ficha ALVO (CP 6.3) — fabricante, referência `'D` e a purga.

O portal é de mentira, mas a TABELA é de verdade: o duplo mantém uma lista de
linhas que ENCOLHE quando o injetor manda excluir. Sem isso, o teste da purga
não valeria nada -- o defeito clássico aqui (avançar o índice depois de apagar)
passa em qualquer duplo que devolva uma tabela imutável, e deixaria metade das
características vivas na ficha real.
"""
import re

import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_injetor as injetor


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(injetor.time, "sleep", lambda _s: None)


def _indice_do_seletor(seletor):
    achado = re.search(r"\)\[(\d+)\]", seletor)
    return int(achado.group(1)) if achado else None


class _EngineFalso:
    def __init__(self, linhas=(), existentes=(), habilitados=()):
        self.linhas = list(linhas)          # descrições da tabela
        self.existentes = list(existentes)  # marcas de "existe na tela"
        self.habilitados = list(habilitados)
        self.cliques = []

    def contar(self, seletor):
        return len(self.linhas) if "TechnicalCharacteristics" in seletor else 0

    def texto(self, seletor):
        indice = _indice_do_seletor(seletor)
        if indice is None or indice > len(self.linhas):
            return ""
        return self.linhas[indice - 1]

    def element_exists(self, seletor):
        return any(marca in seletor for marca in self.existentes)

    def esta_habilitado(self, seletor):
        return any(marca in seletor for marca in self.habilitados)

    def click_raw(self, seletor):
        self.cliques.append(seletor)


class _PortalFalso:
    def __init__(self, engine):
        self.engine = engine
        self.cliques = []
        self.preenchidos = []
        self.excluidas = []
        self.salvou = []
        self.exclusao_falha_em = ()

    def safe_click(self, seletor):
        self.cliques.append(seletor)

    def safe_fill(self, seletor, texto):
        self.preenchidos.append((seletor, texto))

    def excluir_linha_com_confirmacao(self, seletor_linha):
        indice = _indice_do_seletor(seletor_linha)
        descricao = self.engine.linhas[indice - 1]
        if descricao in self.exclusao_falha_em:
            return False
        self.excluidas.append(descricao)
        self.engine.linhas.pop(indice - 1)  # a tabela ENCOLHE, como no portal
        return True

    def clicar_salvar_visivel(self, nome_secao=""):
        self.salvou.append(nome_secao)
        return True


# ===========================================================================
# Fabricante
# ===========================================================================
def test_fabricante_filtra_por_texto_e_clica_na_opcao():
    engine = _EngineFalso(existentes=["data-tooltip='SCHNEIDER'"])
    portal = _PortalFalso(engine)

    resultado = injetor.escolher_fabricante(portal, "SCHNEIDER")

    assert resultado.ok is True
    assert any(texto == "SCHNEIDER" for _s, texto in portal.preenchidos)
    assert any("data-tooltip='SCHNEIDER'" in c for c in portal.cliques)


def test_fabricante_que_nao_aparece_no_combo_nao_clica_em_nada():
    """Clicar "na primeira opção que sobrou" escolheria um fabricante PARECIDO,
    e fabricante errado não dá sintoma nenhum na tela."""
    engine = _EngineFalso(existentes=[])
    portal = _PortalFalso(engine)

    resultado = injetor.escolher_fabricante(portal, "SCHNEIDER", callback_log=lambda _m: None)

    assert resultado.ok is False
    assert not any("role='option'" in c for c in portal.cliques)


def test_fabricante_vazio_nem_abre_o_combo():
    engine = _EngineFalso()
    portal = _PortalFalso(engine)

    resultado = injetor.escolher_fabricante(portal, "")

    assert resultado.ok is False
    assert portal.cliques == []


def test_nome_de_fabricante_com_apostrofo_nao_quebra_o_xpath():
    engine = _EngineFalso(existentes=["concat("])
    portal = _PortalFalso(engine)

    resultado = injetor.escolher_fabricante(portal, "D'ANGELO")

    assert resultado.ok is True


# ===========================================================================
# Referência — a regra do 'D
# ===========================================================================
class _PortalComColisao(_PortalFalso):
    """Portal que recusa as N primeiras referências, como o real faz."""

    def __init__(self, engine, recusar=0, avisar_apos_clique=False):
        super().__init__(engine)
        self.recusar = recusar
        self.avisar_apos_clique = avisar_apos_clique
        self.tentativas = []
        self._colidindo = False

    def safe_fill(self, seletor, texto):
        super().safe_fill(seletor, texto)
        if sel.XPATH_REFERENCIA_INPUT in seletor or "Input_TextVar" in seletor:
            self.tentativas.append(texto)
            self._colidindo = (
                len(self.tentativas) <= self.recusar and not self.avisar_apos_clique
            )

    def safe_click(self, seletor):
        super().safe_click(seletor)
        if "fa-plus-circle" in seletor and self.avisar_apos_clique:
            self._colidindo = len(self.tentativas) <= self.recusar

    @property
    def engine(self):
        portal = self

        class _E:
            @staticmethod
            def element_exists(seletor):
                if "CoincidenceReference" in seletor:
                    return portal._colidindo
                return False

        return _E()

    @engine.setter
    def engine(self, _valor):
        pass


def test_referencia_sem_colisao_usa_o_codigo_cru():
    portal = _PortalComColisao(_EngineFalso(), recusar=0)

    resultado = injetor.escrever_referencia(portal, "2904616")

    assert resultado.ok is True
    assert portal.tentativas == ["2904616"]


def test_referencia_repetida_avanca_para_o_sufixo_D():
    """> "se aparecer 'a referência já existe', devemos colocar o partnumber
    dele 2904616 com o 'D1 no final" -- e quem decide é o portal."""
    portal = _PortalComColisao(_EngineFalso(), recusar=2)

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert portal.tentativas == ["2904616", "2904616'D1", "2904616'D2"]
    assert resultado.detalhe == "2904616'D2"


def test_colisao_detectada_so_DEPOIS_do_clique_tambem_avanca():
    """Não observamos em qual momento o portal valida -- ao digitar ou ao
    clicar no "+". Conferir nos dois é correto se for em qualquer um deles."""
    portal = _PortalComColisao(_EngineFalso(), recusar=1, avisar_apos_clique=True)

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert portal.tentativas == ["2904616", "2904616'D1"]


def test_todas_recusadas_notifica_e_NAO_aborta():
    """> "apenas notificar que não foi possível colocar a referência" -- não
    aborta a ficha nem desfaz o que já foi preenchido."""
    portal = _PortalComColisao(_EngineFalso(), recusar=999)
    logs = []

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=logs.append)

    assert resultado.ok is False
    assert len(portal.tentativas) == injetor.spec.MAX_TENTATIVAS_REFERENCIA + 1
    assert "à mão" in "\n".join(logs)


def test_sem_codigo_do_material_nao_escreve_lixo():
    """Gerar "'D1" sozinho escreveria uma referência que não é de ninguém."""
    portal = _PortalComColisao(_EngineFalso())

    resultado = injetor.escrever_referencia(portal, "", callback_log=lambda _m: None)

    assert resultado.ok is False
    assert portal.tentativas == []


# ===========================================================================
# Características técnicas — a purga
# ===========================================================================
_LINHAS = ["PESO LIQUIDO", "CODIGO PMIB", "TENSAO NOMINAL", "MATERIAL"]


def _com_tabela(linhas, proxima_pagina=False):
    existentes = ["página seguinte"] if proxima_pagina else []
    engine = _EngineFalso(linhas=linhas, existentes=existentes)
    return _PortalFalso(engine), engine


def test_apaga_todas_menos_o_codigo_pmib():
    portal, engine = _com_tabela(list(_LINHAS))

    resultado = injetor.limpar_caracteristicas(portal, "4500063671.1471",
                                               callback_log=lambda _m: None)

    assert resultado.ok is True
    assert engine.linhas == ["CODIGO PMIB"]
    assert sorted(portal.excluidas) == ["MATERIAL", "PESO LIQUIDO", "TENSAO NOMINAL"]


def test_a_linha_preservada_recebe_o_codigo_da_ficha_original():
    portal, _engine = _com_tabela(list(_LINHAS))

    injetor.limpar_caracteristicas(portal, "4500063671.1471", callback_log=lambda _m: None)

    valores = [texto for seletor, texto in portal.preenchidos if "TextArea_ValuePT" in seletor]
    assert valores == ["4500063671.1471"]


def test_o_indice_NAO_avanca_depois_de_apagar():
    """A tabela encolhe: apagada a linha `i`, a de baixo sobe para `i`. Avançar
    sempre pularia uma linha a cada exclusão -- metade das características
    sobreviveria à purga, e a ficha ficaria plausível e errada."""
    portal, engine = _com_tabela(["A", "B", "C", "CODIGO PMIB", "D", "E"])

    injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert engine.linhas == ["CODIGO PMIB"]
    assert portal.excluidas == ["A", "B", "C", "D", "E"]


def test_acento_e_caixa_da_descricao_nao_atrapalham():
    """O portal escreve "CODIGO PMIB" numa tela e "Código PMIB" em outra."""
    portal, engine = _com_tabela(["PESO", "  Código PMIB  "])

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert engine.linhas == ["  Código PMIB  "]


def test_sem_a_linha_do_codigo_pmib_o_resultado_e_erro():
    """A ficha duplicada perderia a ÚNICA característica que precisa ter -- e a
    tela não reclama de nada."""
    portal, _engine = _com_tabela(["PESO", "TENSAO"])

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert resultado.ok is False
    assert "CODIGO PMIB" in resultado.detalhe


def test_exclusao_que_falha_avanca_em_vez_de_travar():
    """O módulo antigo marcava sucesso sem conferir e nunca caía aqui -- era
    assim que uma exclusão falha passava por bem-sucedida. Conferindo, o risco
    novo é o laço tentar a MESMA linha para sempre."""
    portal, engine = _com_tabela(["TEIMOSA", "CODIGO PMIB"])
    portal.exclusao_falha_em = ("TEIMOSA",)
    logs = []

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=logs.append)

    assert resultado.ok is True           # o CODIGO PMIB foi preservado
    assert engine.linhas == ["TEIMOSA", "CODIGO PMIB"]
    assert any("Não consegui excluir" in linha for linha in logs)


def test_a_tabela_paginada_e_percorrida_ate_o_fim():
    """Apagar só a página 1 deixaria as características das outras páginas na
    ficha -- e o robô diria que terminou."""
    portal, engine = _com_tabela(["PESO", "CODIGO PMIB"], proxima_pagina=True)
    engine.habilitados = ["página seguinte"]

    paginas = {"n": 0}
    original = engine.esta_habilitado

    def esta_habilitado(seletor):
        if "página seguinte" in seletor:
            paginas["n"] += 1
            return paginas["n"] <= 2  # duas páginas, depois desabilita
        return original(seletor)

    engine.esta_habilitado = esta_habilitado

    injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert engine.cliques.count(sel.XPATH_CARACTERISTICAS_PROXIMA_PAGINA) == 2


def test_paginacao_sem_fim_para_no_teto_em_vez_de_travar():
    """O laço do módulo antigo é `while True` e depende de o botão desabilitar.
    Se ele nunca desabilitar, o robô pagina para sempre, apagando o que
    encontrar. O teto troca travamento por mensagem."""
    portal, engine = _com_tabela(["CODIGO PMIB"], proxima_pagina=True)
    engine.habilitados = ["página seguinte"]
    logs = []

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=logs.append)

    assert resultado.ok is False
    assert engine.cliques.count(
        sel.XPATH_CARACTERISTICAS_PROXIMA_PAGINA) == injetor.MAX_PAGINAS_CARACTERISTICAS
    assert "paginação sem fim" in resultado.detalhe


def test_salva_a_secao_no_fim():
    portal, _engine = _com_tabela(list(_LINHAS))

    injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert portal.salvou == ["Características Técnicas"]

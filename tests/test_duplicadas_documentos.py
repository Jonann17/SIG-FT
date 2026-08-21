r"""
Documentos / datasheets da ficha duplicada (CP 6.4).

O documento já existe no portal: a ficha nova ASSOCIA, não sobe arquivo.

⚠️ O DEFEITO QUE ESTE MÓDULO NASCE CONSERTANDO está no módulo antigo, e ele
próprio o admite. `ficha_duplicada._associar_documentos` marca o checkbox e
volta, com o comentário: *"(Aqui pode ser necessário clicar em um botão para
fechar o modal/confirmar, dependendo da UI)"*. É necessário -- o usuário
mandou o botão em 2026-08-19:

    <button data-button="" class="btn btn-primary" type="button">ASSOCIAR</button>

Sem esse clique, marcar a caixa não associa nada e o diálogo fecha igual: o
sintoma é uma ficha sem datasheet e um log dizendo que deu certo. É o mesmo
padrão do "+" da referência e do SALVAR sem toast.
"""
import pytest

from sigft.core.rpa.portal import PMIBPortal
from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_documentos as docs


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(docs.time, "sleep", lambda _s: None)


class _EngineDeDocumentos:
    """Diálogo de busca + tabela da ficha.

    `catalogo` é o que a busca acha; `na_ficha` é o que a ficha já tem. O
    ASSOCIAR é o que move do primeiro para o segundo -- se o teste não clicar
    nele, nada se move, que é exatamente o defeito do módulo antigo.
    """

    def __init__(self, catalogo=(), na_ficha=(), duplicados=(), sem_checkbox=()):
        self.catalogo = list(catalogo)
        self.na_ficha = list(na_ficha)
        self.duplicados = set(duplicados)
        self.sem_checkbox = set(sem_checkbox)
        self.busca = ""
        self.marcado = None
        self.cliques = []

    @staticmethod
    def _texto_do_seletor(seletor):
        import re
        achado = re.search(r"normalize-space\(\)='([^']*)'", seletor)
        return achado.group(1) if achado else None

    def contar(self, seletor):
        # ⚠️ O checkbox PRIMEIRO: o seletor dele é RELATIVO à linha, então
        # carrega o texto do `//td[@data-header='Descrição']` inteiro dentro
        # de si. Testado depois, o ramo da linha o capturava e o duplo dizia
        # que havia checkbox onde o teste tinha dito que não há.
        if "checkbox" in seletor:
            return 0 if self.busca in self.sem_checkbox else 1
        if "@data-header='Descrição'" in seletor and "ancestor::tr" in seletor:
            alvo = self._texto_do_seletor(seletor)
            if alvo is None or alvo != self.busca or alvo not in self.catalogo:
                return 0
            return 2 if alvo in self.duplicados else 1
        if "data-header=" in seletor and "ancestor::table" in seletor:
            return len(self.na_ficha)
        return 0

    def texto(self, seletor):
        import re
        achado = re.search(r"\)\[(\d+)\]", seletor)
        i = int(achado.group(1)) if achado else None
        if i and i <= len(self.na_ficha):
            return self.na_ficha[i - 1]
        return ""

    def esta_marcado(self, _seletor):
        return self.marcado is not None

    def click(self, _seletor):
        self.marcado = self.busca

    def click_dom(self, seletor):
        self.click(seletor)


class _PortalDeDocumentos:
    # Emprestados do PMIBPortal REAL: os dois só usam `self.engine`, então
    # ligá-los aqui testa a implementação de verdade em vez de uma cópia
    # que envelhece sozinha. São o conserto do travamento de 2026-08-20 --
    # ler o que pode não existir sem pagar o timeout do motor.
    texto_se_existir = PMIBPortal.texto_se_existir
    valor_se_existir = PMIBPortal.valor_se_existir

    def __init__(self, engine):
        self.engine = engine

    def safe_click(self, seletor):
        self.engine.cliques.append(seletor)
        if "ASSOCIAR" in seletor:
            # SÓ o ASSOCIAR move o documento para a ficha. Marcar a caixa não.
            if self.engine.marcado and self.engine.marcado not in self.engine.na_ficha:
                self.engine.na_ficha.append(self.engine.marcado)
            self.engine.marcado = None

    def safe_fill(self, _seletor, texto):
        self.engine.busca = texto
        self.engine.marcado = None

    def check_or_uncheck(self, seletor, deve_marcar, callback_log=None):
        return PMIBPortal.check_or_uncheck(self, seletor, deve_marcar, callback_log)


def _tela(**kwargs):
    engine = _EngineDeDocumentos(**kwargs)
    return _PortalDeDocumentos(engine), engine


# =============================================================================
# O caminho feliz, e o clique que faltava
# =============================================================================
def test_documento_do_catalogo_e_associado():
    portal, engine = _tela(catalogo=["DATASHEET QUINT4-PS"])

    resultado = docs.associar(portal, ["DATASHEET QUINT4-PS"], lambda _m: None)

    assert resultado.ok is True
    assert engine.na_ficha == ["DATASHEET QUINT4-PS"]


def test_o_botao_ASSOCIAR_e_clicado():
    """O clique que o módulo antigo não dá. Sem ele o duplo não move nada --
    e o portal também não."""
    portal, engine = _tela(catalogo=["DATASHEET QUINT4-PS"])

    docs.associar(portal, ["DATASHEET QUINT4-PS"], lambda _m: None)

    assert any("ASSOCIAR" in c for c in engine.cliques)


def test_a_busca_recebe_a_descricao():
    """A lista tem 809 itens em 162 páginas: sem busca não há como achar."""
    portal, engine = _tela(catalogo=["MANUAL DE INSTALACAO"])

    docs.associar(portal, ["MANUAL DE INSTALACAO"], lambda _m: None)

    assert engine.busca == "MANUAL DE INSTALACAO"


# =============================================================================
# O que NÃO pode acontecer
# =============================================================================
def test_documento_que_nao_aparece_na_busca_vira_pendencia():
    portal, _ = _tela(catalogo=[])
    linhas = []

    resultado = docs.associar(portal, ["DATASHEET SUMIDO"], linhas.append)

    assert resultado.ok is False
    assert any("não apareceu na busca" in l for l in linhas)


def test_descricao_ambigua_NAO_associa_nada():
    """Duas linhas com a mesma descrição exata: escolher uma é chute, e o
    diálogo fecha igual nos dois casos."""
    portal, engine = _tela(catalogo=["1188"], duplicados=["1188"])
    linhas = []

    resultado = docs.associar(portal, ["1188"], linhas.append)

    assert resultado.ok is False
    assert engine.na_ficha == []
    assert any("2 documentos" in l for l in linhas)


def test_checkbox_que_nao_marca_vira_pendencia():
    portal, engine = _tela(catalogo=["DATASHEET X"], sem_checkbox=["DATASHEET X"])
    linhas = []

    resultado = docs.associar(portal, ["DATASHEET X"], linhas.append)

    assert resultado.ok is False
    assert engine.na_ficha == []
    assert any("marcar a caixa" in l for l in linhas)


# =============================================================================
# A conferência antes de sair da página
# =============================================================================
def test_a_tabela_da_ficha_e_RELIDA_no_fim():
    """Marcar e clicar não prova que associou. Só a tabela da ficha prova."""
    portal, engine = _tela(catalogo=["A", "B"])
    linhas = []

    # "B" some da ficha depois de associado -- o portal recusou em silêncio.
    class _PortalQuePerdeB(type(portal)):
        def safe_click(self, seletor):
            super().safe_click(seletor)
            if "B" in engine.na_ficha:
                engine.na_ficha.remove("B")

    resultado = docs.associar(_PortalQuePerdeB(engine), ["A", "B"], linhas.append)

    assert resultado.ok is False
    assert any("NÃO ficaram" in l for l in linhas)


def test_documento_que_ja_esta_na_ficha_nao_e_associado_de_novo():
    portal, engine = _tela(catalogo=["A"], na_ficha=["A"])

    resultado = docs.associar(portal, ["A"], lambda _m: None)

    assert resultado.ok is True
    assert engine.cliques == [], "nada a fazer: já estava lá"


def test_ficha_original_sem_documentos_nao_e_falha():
    portal, _ = _tela()

    resultado = docs.associar(portal, [], lambda _m: None)

    assert resultado.ok is True
    assert "nenhum" in resultado.detalhe


# =============================================================================
# A aba tem NOMES DIFERENTES nos dois modos
# =============================================================================
def test_a_aba_de_documentos_tem_nome_proprio_na_edicao():
    """Log de 2026-08-20: `[Erro] A aba 'Documentos' não existe nesta tela`.

    Não era a aba que sumiu -- era o nome. Na visualização ela é "Documentos"
    (as imagens ficam sempre visíveis, num carrossel); na edição é "Documentos
    e imagens" (`aria-controls="b10-DocumentsandImages_Content"`).
    """
    assert sel.ABA_DOCUMENTOS == "Documentos"
    assert sel.ABA_DOCUMENTOS_EDICAO == "Documentos e imagens"


def test_o_robo_usa_o_nome_da_EDICAO_na_ficha_alvo():
    """Contrato entre o modo e o nome: a alvo é sempre aberta para editar."""
    import inspect

    from sigft.services import duplicadas_robo as robo

    fonte = inspect.getsource(robo.processar_ficha)
    assert "ABA_DOCUMENTOS_EDICAO" in fonte, (
        "a ficha alvo está em EDIÇÃO -- usar o nome da visualização faz a aba "
        "'não existir' e a seção inteira ser pulada"
    )

    leitura = inspect.getsource(robo.ler_documentos_da_original)
    assert "ABA_DOCUMENTOS_EDICAO" not in leitura, (
        "a ficha original é lida em VISUALIZAÇÃO -- lá o nome é o outro"
    )


# =============================================================================
# A conferência precisa esperar a tabela recarregar
# =============================================================================
def test_a_conferencia_rele_a_tabela_DEPOIS_de_uma_pausa(monkeypatch):
    """Log de 2026-08-20, 14h32 -- as duas linhas seguidas:

        Associado: 2904616
        [Erro] 1 documento(s) NÃO ficaram associados: 2904616.

    Ele associou e, no mesmo segundo, releu e não achou. O portal fecha o
    diálogo e recarrega a tabela da ficha; ler antes disso devolve o estado
    ANTERIOR -- e o robô acusa de falha o que acabou de dar certo, que é a
    pior espécie de falso alarme: some a confiança no log inteiro.

    A cura era uma pausa fixa de 3 s antes da releitura. Em 2026-08-21 o mesmo
    sintoma voltou COM a pausa (log das 16:17): 3 s não bastaram. Pausa fixa
    erra dos dois lados -- curta demais reprova a ficha certa, longa demais
    cobra o atraso de toda ficha que já estava pronta.

    O que se tranca agora é a regra que substituiu a pausa: a conferência
    INSISTE, e só conclui quando vê ou quando o teto estoura.
    """
    portal, engine = _tela(catalogo=["A"])

    leituras = {"n": 0}
    original = engine.contar

    def contar(seletor):
        if "data-header=" in seletor and "ancestor::table" in seletor:
            leituras["n"] += 1
        return original(seletor)

    engine.contar = contar
    docs.associar(portal, ["A"], lambda _m: None)

    assert leituras["n"] >= 2, (
        "a conferência tem de reler a tabela, não confiar no diálogo"
    )


# ===========================================================================
# TABELA ILEGÍVEL ≠ ASSOCIAÇÃO QUE FALHOU — defeito de 2026-08-21, 16:17
# ===========================================================================
# No log do usuário, três linhas em seis segundos:
#
#   [16:17:43] Associado: BOTÕES ACE SCHMERSAL
#   [16:17:46] [Erro] 1 documento(s) NÃO ficaram associados: BOTÕES ACE
#              SCHMERSAL. Associe à mão.
#
# O robô associou e, três segundos depois, a releitura não achou. Duas causas
# possíveis e o log não distinguia: a tabela ainda não tinha recarregado, ou o
# `escopo` (o id do painel, GERADO pelo OutSystems) mudou no meio e a leitura
# passou a apontar para o nada.
#
# As duas produzem a mesma frase -- e ela acusa a ASSOCIAÇÃO, que é a única das
# três coisas que a gente sabe ter acontecido. Ler ZERO linha numa tabela onde
# acabamos de associar não é prova de que a associação falhou: é prova de que
# não conseguimos ler.

class _EngineComTabelaIlegivel(_EngineDeDocumentos):
    """A associação funciona, mas a tabela da ficha lê SEMPRE zero linha --
    é o que o escopo errado (ou o painel ainda não remontado) produz."""

    def contar(self, seletor):
        if "data-header=" in seletor and "ancestor::table" in seletor:
            return 0
        return super().contar(seletor)


def test_nao_acusa_a_associacao_quando_a_tabela_nao_foi_lida():
    engine = _EngineComTabelaIlegivel(catalogo=["BOTÕES ACE SCHMERSAL"])
    portal = _PortalDeDocumentos(engine)
    logs = []

    docs.associar(portal, ["BOTÕES ACE SCHMERSAL"], logs.append)

    texto = "\n".join(logs)
    assert "não consegui ler" in texto.lower()
    assert "NÃO ficaram associados" not in texto


def test_tabela_ilegivel_continua_sendo_pendencia():
    """Não saber é diferente de estar certo: a coluna não pode fechar."""
    engine = _EngineComTabelaIlegivel(catalogo=["BOTÕES ACE SCHMERSAL"])
    portal = _PortalDeDocumentos(engine)

    resultado = docs.associar(portal, ["BOTÕES ACE SCHMERSAL"])

    assert not resultado.ok


def test_espera_a_tabela_recarregar_em_vez_de_conferir_uma_vez_so():
    """A releitura acontecia depois de UMA pausa fixa de 3 s. Se o portal
    demorasse 4, a ficha certa saía marcada como errada. Agora a conferência
    insiste até o documento aparecer."""
    engine = _EngineDeDocumentos(catalogo=["BOTÕES ACE SCHMERSAL"])
    demora = {"restam": 3}
    original = engine.contar

    def contar(seletor):
        if "data-header=" in seletor and "ancestor::table" in seletor:
            if demora["restam"] > 0:
                demora["restam"] -= 1
                return 0
        return original(seletor)

    engine.contar = contar
    portal = _PortalDeDocumentos(engine)

    assert docs.associar(portal, ["BOTÕES ACE SCHMERSAL"]).ok

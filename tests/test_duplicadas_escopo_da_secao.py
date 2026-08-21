r"""
O robô leu as CARACTERÍSTICAS achando que eram documentos (2026-08-20, 14h).

    38 documento(s) na ficha original.
    [Erro] Documento 'TIPO' não apareceu na busca. Associe à mão.
    [Erro] Documento 'TENSAO DE ENTRADA' não apareceu na busca.
    [Erro] Documento 'CORRENTE DE ENTRADA' não apareceu na busca.
    …

"TIPO", "TENSÃO DE ENTRADA", "CORRENTE DE SAÍDA" não são documentos: são
CARACTERÍSTICAS TÉCNICAS. O robô leu a tabela errada e passou minutos
buscando cada uma no catálogo de documentos.

O HTML despejado no mesmo log explica, e o motivo é banal: **as duas tabelas
têm uma coluna "Descrição"**. A de características é
`Ordem | Código | Descrição | Valor`; a de documentos também tem "Descrição".
`XPATH_LINHAS_DA_TABELA_DE` casa `//td[@data-header='Descrição']` na PÁGINA
INTEIRA e fica com o primeiro `ancestor::table` -- que é o de características,
porque vem antes no documento.

⚠️ E o discriminador "óbvio" NÃO serve: eu ia usar o aninhamento em
`Content.Tooltip`, que o usuário mostrou na célula do documento. O dump prova
que a célula de CARACTERÍSTICA tem exatamente o mesmo aninhamento
(`b12-b16-…-TooltipWrapper`). Conferir antes de implementar economizou uma
rodada inteira.

O que discrimina de verdade está no próprio HTML das abas, e é semântico:

    <button role="tab" aria-controls="b12-$b15">Características Técnicas</button>
    <button role="tab" aria-controls="b12-$b17">Documentos</button>

`aria-controls` aponta para o PAINEL da seção. Lido em tempo de execução (o id
é gerado e não pode ser escrito no código, mas pode ser lido -- mesma técnica
do prefixo do campo de referência), ele dá o escopo exato de cada tabela.
"""
import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_extrator as extrator


class _EngineComAbas:
    """Duas tabelas com coluna "Descrição", cada uma no seu painel.

    O duplo resolve o XPath do jeito que o portal faria: sem escopo, casa a
    PRIMEIRA tabela do documento (a de características); com escopo, casa só a
    do painel pedido.
    """

    PAINEIS = {"Características Técnicas": "b12-$b15", "Documentos": "b12-$b17"}
    CONTEUDO = {
        "b12-$b15": ["TIPO", "TENSAO DE ENTRADA", "CORRENTE DE SAIDA"],
        "b12-$b17": ["2904616", "MANUAL DE INSTALACAO"],
    }

    def __init__(self):
        self.cliques = []

    @staticmethod
    def _painel_do_seletor(seletor):
        import re
        achado = re.search(r"@id='([^']+)'", seletor)
        return achado.group(1) if achado else None

    @staticmethod
    def _indice(seletor):
        import re
        achado = re.search(r"\)\[(\d+)\]", seletor)
        return int(achado.group(1)) if achado else None

    def _linhas(self, seletor):
        painel = self._painel_do_seletor(seletor)
        if painel:
            return self.CONTEUDO.get(painel, [])
        # SEM escopo: a página inteira, e a 1ª tabela vem primeiro.
        return self.CONTEUDO["b12-$b15"]

    def contar(self, seletor):
        if "aria-selected" in seletor:
            return 1
        if "osui-tabs__header-item" in seletor:
            return 1
        if "data-header" in seletor:
            return len(self._linhas(seletor))
        return 0

    def atributo(self, seletor, nome):
        if nome != "aria-controls":
            return ""
        for aba, painel in self.PAINEIS.items():
            if f"'{aba}'" in seletor:
                return painel
        return ""

    def texto(self, seletor):
        linhas = self._linhas(seletor)
        i = self._indice(seletor)
        return linhas[i - 1] if i and i <= len(linhas) else ""


class _PortalComAbas:
    def __init__(self, engine):
        self.engine = engine

    def safe_click(self, seletor):
        self.engine.cliques.append(seletor)

    def texto_se_existir(self, seletor):
        return self.engine.texto(seletor)


@pytest.fixture
def portal():
    return _PortalComAbas(_EngineComAbas())


# =============================================================================
# 1. O escopo vem do `aria-controls` da aba
# =============================================================================
def test_le_o_id_do_painel_pelo_aria_controls(portal):
    assert extrator.id_do_painel(portal, "Documentos") == "b12-$b17"
    assert extrator.id_do_painel(portal, "Características Técnicas") == "b12-$b15"


def test_aba_inexistente_devolve_escopo_vazio():
    class _SemAba(_EngineComAbas):
        def atributo(self, seletor, nome):
            return ""

    assert extrator.id_do_painel(_PortalComAbas(_SemAba()), "Documentos") == ""


# =============================================================================
# 2. SEM escopo, lê a tabela errada -- a contraprova do defeito
# =============================================================================
def test_sem_escopo_a_leitura_cai_na_tabela_de_caracteristicas(portal):
    """CONTRAPROVA. Se um dia este teste passar a devolver documentos sem
    escopo, é o duplo que quebrou -- o portal continua tendo duas tabelas com
    coluna "Descrição"."""
    linhas = extrator.ler_tabela_de(portal, sel.COLUNA_DESCRICAO,
                                    coluna_referencia=None)

    assert [n for n, _ in linhas] == ["TIPO", "TENSAO DE ENTRADA", "CORRENTE DE SAIDA"]


def test_com_escopo_le_a_tabela_de_DOCUMENTOS(portal):
    linhas = extrator.ler_tabela_de(portal, sel.COLUNA_DESCRICAO,
                                    coluna_referencia=None, escopo="b12-$b17")

    assert [n for n, _ in linhas] == ["2904616", "MANUAL DE INSTALACAO"]


def test_o_escopo_aceita_id_com_cifrao(portal):
    """Os ids do OutSystems trazem `$` (`b12-$b17`). Um literal XPath mal
    montado quebraria justamente neles."""
    linhas = extrator.ler_tabela_de(portal, sel.COLUNA_DESCRICAO,
                                    coluna_referencia=None, escopo="b12-$b17")

    assert linhas, "o `$` no id não pode quebrar o seletor"


# =============================================================================
# 3. O robô passa a usar o escopo
# =============================================================================
def test_ler_documentos_da_original_usa_o_escopo_do_painel(monkeypatch):
    from sigft.services import duplicadas_robo as robo

    recebidos = {}
    monkeypatch.setattr(robo.extrator, "abrir_secao", lambda *_a, **_k: True)
    monkeypatch.setattr(robo.extrator, "id_do_painel", lambda *_a, **_k: "b12-$b17")
    monkeypatch.setattr(
        robo.extrator, "ler_tabela_de",
        lambda _p, coluna, _log=None, coluna_referencia="?", escopo=None: (
            recebidos.update(escopo=escopo) or []))

    robo.ler_documentos_da_original(_PortalComAbas(_EngineComAbas()), lambda _m: None)

    assert recebidos.get("escopo") == "b12-$b17", (
        "sem escopo, a leitura cai na tabela de características -- foi o que "
        "fez o robô procurar 'TENSAO DE ENTRADA' no catálogo de documentos"
    )


# =============================================================================
# 4. Desistir cedo -- o usuário não aguentou esperar
# =============================================================================
# *"Eu fechei porque eu não aguentei esperar ele errar todas as características
# da ficha original tentando buscar na seção de documentos."* (2026-08-20)
#
# 38 buscas fracassadas, ~47 segundos cada. Meia hora para chegar a uma
# conclusão que a terceira falha seguida já entregava: **a lista está errada**.
# Nenhuma ficha real tem 38 documentos que o catálogo desconhece um a um.
#
# Insistir também tinha custo na TELA. Cada tentativa abre o diálogo de
# associação; 38 diálogos empilhados são o *"a página está muito esquisita,
# ficando metade da tela, parecendo colapsar"* que o usuário relatou.
from sigft.services import duplicadas_documentos as docs  # noqa: E402


class _CatalogoVazio:
    """Portal em que NENHUMA busca acha o documento -- o caso real."""

    def __init__(self):
        self.buscas = []

    def contar(self, seletor):
        if "ancestor::table" in seletor or "data-header" in seletor:
            return 0
        return 0

    def texto(self, _seletor):
        return ""

    def esta_marcado(self, _seletor):
        return False

    def click(self, _seletor):
        pass


class _PortalDoCatalogoVazio:
    def __init__(self, engine):
        self.engine = engine

    def safe_click(self, _seletor):
        pass

    def safe_fill(self, _seletor, texto):
        self.engine.buscas.append(texto)

    def texto_se_existir(self, _seletor):
        return ""

    def check_or_uncheck(self, *_a, **_k):
        return False


def test_desiste_depois_de_algumas_falhas_seguidas(monkeypatch):
    monkeypatch.setattr(docs.time, "sleep", lambda _s: None)
    engine = _CatalogoVazio()
    portal = _PortalDoCatalogoVazio(engine)
    linhas = []

    resultado = docs.associar(
        portal, [f"CARACTERISTICA {i}" for i in range(38)], callback_log=linhas.append)

    assert resultado.ok is False
    assert len(engine.buscas) <= docs.MAX_FALHAS_SEGUIDAS, (
        "38 buscas de ~47s cada é meia hora para uma conclusão que a terceira "
        "falha já entregava"
    )
    assert any("desisti" in l.lower() for l in linhas)


def test_o_aviso_de_desistencia_diz_o_que_suspeitar(monkeypatch):
    """Quem lê o log precisa saber que o problema provável é a LISTA, não o
    catálogo -- foi exatamente esse o caso."""
    monkeypatch.setattr(docs.time, "sleep", lambda _s: None)
    portal = _PortalDoCatalogoVazio(_CatalogoVazio())
    linhas = []

    docs.associar(portal, ["A", "B", "C", "D", "E"], callback_log=linhas.append)

    texto = "\n".join(linhas).lower()
    assert "lista" in texto


# =============================================================================
# 5. A foto da página inteira precisa de coleira
# =============================================================================
def test_a_foto_da_pagina_inteira_tem_limite_proprio():
    """Com `//body` valendo, o log de 2026-08-20 saiu com 121 KB para 56
    linhas de texto -- o arquivo que o usuário manda para eu ler virou
    ilegível para ele. 20 000 caracteres bastaram, naquele mesmo log, para
    achar as duas tabelas com coluna "Descrição" e o `aria-controls` das abas.
    """
    class _LogFalso:
        def __init__(self):
            self.limites = []

        def bloco(self, _titulo, _texto, limite=None):
            self.limites.append(limite)

    class _EngineSoBody:
        def html_do_elemento(self, seletor):
            return "<body>…</body>" if seletor == extrator.XPATH_FICHA_INTEIRA else ""

    class _PortalSoBody:
        engine = _EngineSoBody()

    log = _LogFalso()
    extrator.fotografar(_PortalSoBody(), "Seção X", log)

    assert log.limites == [extrator.LIMITE_DA_FOTO_DA_PAGINA]


def test_a_foto_de_uma_secao_NAO_leva_o_limite_reduzido():
    """Só o último recurso é grande demais. Cortar a foto da seção seria
    jogar fora justamente o markup que se quer ler."""
    class _LogFalso:
        def __init__(self):
            self.limites = []

        def bloco(self, _titulo, _texto, limite=None):
            self.limites.append(limite)

    class _EngineComSecao:
        def html_do_elemento(self, seletor):
            return "<div>…</div>" if seletor == extrator.XPATH_CONTEUDO_DA_SECAO else ""

    class _PortalComSecao:
        engine = _EngineComSecao()

    log = _LogFalso()
    extrator.fotografar(_PortalComSecao(), "Seção X", log)

    assert log.limites == [None], "limite padrão do LogDeExecucao"


# =============================================================================
# 6. A foto da seção tem de ser DO PAINEL, não da página
# =============================================================================
def test_a_foto_da_secao_usa_o_painel(monkeypatch):
    """A foto de `//body` começa no topo da página, e a seção de Condições fica
    lá embaixo: com o teto de 20 000 caracteres que eu mesmo pus, o markup que
    eu precisava foi cortado antes de aparecer. A rodada de 2026-08-20 15h
    fotografou a aba certa e mesmo assim não trouxe um único "Comprimento".

    O `aria-controls` já dá o painel exato -- fotografar ELE resolve as duas
    pontas: cabe no limite e não traz nada de outra seção junto.
    """
    fotografados = []
    monkeypatch.setattr(extrator, "id_do_painel", lambda *_a, **_k: "b12-$b19")
    monkeypatch.setattr(extrator, "fotografar",
                        lambda _p, _t, _l=None, seletor=None: fotografados.append(seletor))

    engine = _EngineComAbas()
    extrator.abrir_secao(_PortalComAbas(engine), "Condições",
                         callback_log=lambda _m: None, log_auditoria=object())

    assert fotografados, "a seção aberta continua sendo fotografada"
    assert "b12-$b19" in (fotografados[0] or ""), (
        "a foto tem de ser do PAINEL da seção -- `//body` começa no topo da "
        "página e o corte engoliu justamente o que eu precisava ler"
    )

r"""
O primeiro campo de cada seção chegava VAZIO ao portal (2026-08-19).

Primeiro lote real depois da migração: 31 fichas, e em cada seção o portal
recusou com *"Por favor, verifique os campos"*. O usuário viu na tela que o
campo faltando era sempre **o primeiro da seção, o de espanhol**.

O que provou que o defeito era do ROBÔ e não da IA: o Excel gerado no mesmo
lote não tem **uma única** célula de texto vazia -- `legislacao_es`,
`cuidad_preserv_es` e `embalagem_transp_es` estavam todos preenchidos. O valor
existia e não chegava na tela.

E o código explica por que só o PRIMEIRO se perdia: em cada seção, a linha
imediatamente após o clique da aba é exatamente esse campo.

    self.safe_click('//*[@id="b10-b17-Title"]/div[5]')          <- abre Descarte
    self.safe_send_keys('…-TextArea_TypeLegislationES', …)      <- some

A aba do OutSystems re-renderiza o conteúdo ao ser ativada; o robô escrevia
antes de a renderização assentar e o re-render limpava o que ele tinha
acabado de escrever. Quando chegava no segundo campo, a tela já tinha
assentado -- daí o defeito ser sempre e só no primeiro.

Os testes abaixo reproduzem essa mecânica: um campo que "esquece" a primeira
escrita. Sem o conserto, o valor some; com ele, a releitura percebe e
reescreve.
"""
import pytest

from sigft.core.rpa.portal import PMIBPortal
from sigft.services import upload_conditions


class _EngineQueEsquece:
    """Campo que descarta a PRIMEIRA escrita -- como a aba que re-renderiza.

    `esquecer` é o conjunto de seletores com esse comportamento; os demais
    guardam normalmente.
    """

    def __init__(self, esquecer=(), nunca_aceita=()):
        self.valores = {}
        self.escritas = []
        self.esquecer = set(esquecer)
        self.nunca_aceita = set(nunca_aceita)
        self.ja_escreveu = set()
        self.esperou = []

    def fill(self, seletor, texto):
        self.escritas.append((seletor, texto))
        if seletor in self.nunca_aceita:
            self.valores[seletor] = ""
            return
        if seletor in self.esquecer and seletor not in self.ja_escreveu:
            self.ja_escreveu.add(seletor)
            self.valores[seletor] = ""   # o re-render limpou
            return
        self.valores[seletor] = texto

    def get_value(self, seletor):
        return self.valores.get(seletor, "")

    def click(self, seletor):
        pass

    def wait_visible(self, seletor):
        self.esperou.append(seletor)


@pytest.fixture(autouse=True)
def sem_dormir(monkeypatch):
    monkeypatch.setattr(upload_conditions.time, "sleep", lambda _s: None)


def _automacao(engine):
    automacao = upload_conditions.UploadAutomation()
    automacao.engine = engine
    automacao.portal = PMIBPortal(engine)
    return automacao


CAMPO = '//*[@id="b10-b17-b5-TextArea_TypeLegislationES"]'


# =============================================================================
# O defeito, e o conserto
# =============================================================================
def test_o_campo_que_esquece_a_primeira_escrita_e_REESCRITO():
    """O caso exato do lote real."""
    engine = _EngineQueEsquece(esquecer=[CAMPO])
    automacao = _automacao(engine)

    ok = automacao.preencher_conferindo(CAMPO, "Ley nº 12.305/2010", "legislacao_es")

    assert ok is True
    assert engine.get_value(CAMPO) == "Ley nº 12.305/2010"
    assert len(engine.escritas) == 2, "não bastou escrever de novo: releu e reescreveu"


def test_sem_a_conferencia_o_valor_teria_sumido_em_silencio():
    """Prova de que o duplo reproduz mesmo o defeito -- e de que o caminho
    antigo (`safe_send_keys` puro) o deixava passar."""
    engine = _EngineQueEsquece(esquecer=[CAMPO])
    automacao = _automacao(engine)

    automacao.safe_send_keys(CAMPO, "Ley nº 12.305/2010")

    assert engine.get_value(CAMPO) == "", "o duplo precisa reproduzir o defeito"


def test_campo_que_aceita_de_primeira_nao_e_reescrito():
    """Reescrever tudo por precaução dobraria o tempo do lote sem motivo."""
    engine = _EngineQueEsquece()
    automacao = _automacao(engine)

    automacao.preencher_conferindo(CAMPO, "texto", "legislacao_es")

    assert len(engine.escritas) == 1


def test_campo_que_nunca_aceita_vira_PENDENCIA_com_log():
    """Duas tentativas e desiste -- mas avisa. Antes disto o campo ficava
    vazio, o portal recusava a seção inteira e o log não dizia qual campo."""
    engine = _EngineQueEsquece(nunca_aceita=[CAMPO])
    automacao = _automacao(engine)
    linhas, pendencias = [], []

    ok = automacao.preencher_conferindo(
        CAMPO, "texto", "legislacao_es", linhas.append, pendencias)

    assert ok is False
    assert any("NÃO aceitou o valor" in l for l in linhas)
    assert pendencias and "legislacao_es" in pendencias[0]


def test_texto_vazio_nao_vira_pendencia():
    """Campo que o JSON mandou vazio é problema de outra camada (o prompt).
    Reclamar dele aqui só empilharia ruído sobre um defeito que já tem dono."""
    engine = _EngineQueEsquece(nunca_aceita=[CAMPO])
    automacao = _automacao(engine)
    pendencias = []

    assert automacao.preencher_conferindo(CAMPO, "", "x", None, pendencias) is True
    assert pendencias == []


def test_engine_que_nao_deixa_reler_nao_inventa_pendencia():
    class _SemLeitura(_EngineQueEsquece):
        def get_value(self, seletor):
            raise RuntimeError("sem leitura")

    automacao = _automacao(_SemLeitura())
    pendencias = []

    assert automacao.preencher_conferindo(CAMPO, "texto", "x", None, pendencias) is True
    assert pendencias == []


# =============================================================================
# A aba espera assentar antes de devolver
# =============================================================================
def test_abrir_aba_ESPERA_o_primeiro_campo_aparecer():
    """A espera é pelo campo visível, e não um `sleep` cego: o campo visível é
    a evidência de que a re-renderização terminou."""
    engine = _EngineQueEsquece()
    automacao = _automacao(engine)

    automacao.abrir_aba('//*[@id="b10-b17-Title"]/div[5]', CAMPO, "Descarte")

    assert engine.esperou == [CAMPO]


def test_aba_que_nao_mostra_o_campo_avisa_e_segue():
    """Não abortar é deliberado: a espera é uma otimização sobre a releitura,
    que continua sendo a rede de verdade."""
    class _NuncaMostra(_EngineQueEsquece):
        def wait_visible(self, seletor):
            raise RuntimeError("timeout")

    automacao = _automacao(_NuncaMostra())
    linhas = []

    automacao.abrir_aba('//*[@id="x"]', CAMPO, "Descarte", linhas.append)

    assert any("não mostrou o primeiro campo" in l for l in linhas)


# =============================================================================
# A fiação: todo campo de texto da seção passa pela conferência
# =============================================================================
def test_nenhum_campo_de_texto_ficou_sem_conferencia():
    """O defeito era num campo só, mas a causa (re-render) vale para qualquer
    um. Deixar metade conferida seria consertar o sintoma."""
    import ast
    import pathlib

    fonte = pathlib.Path(upload_conditions.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    classe = next(n for n in arvore.body
                  if isinstance(n, ast.ClassDef) and n.name == "UploadAutomation")
    metodo = next(n for n in classe.body
                  if isinstance(n, ast.FunctionDef) and n.name == "processar_lista")

    cruas = [c for c in ast.walk(metodo)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
             and c.func.attr == "safe_send_keys"]

    assert cruas == [], (
        f"{len(cruas)} campo(s) ainda escrevem sem conferir o que ficou na tela"
    )

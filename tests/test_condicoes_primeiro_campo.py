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
    assert any("NÃO aceitou" in l for l in linhas)
    assert any("texto" in l for l in linhas), (
        "a mensagem tem de dizer o que foi PEDIDO -- sem isso, quem lê o log "
        "não sabe o que digitar à mão"
    )
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


# =============================================================================
# O falso positivo que reprovou 28 fichas que o portal tinha aceitado
# =============================================================================
# Lote de 2026-08-19: 28 de 31 fichas saíram INCOMPLETO. O log dizia, por
# exemplo, `'Input_LiquidWeight' ficou '0,55'` -- um valor PLAUSÍVEL, não
# vazio. Cruzando com o Excel do mesmo lote:
#
#     Excel manda ',55'   ->   portal guarda '0,55'
#
# O portal NORMALIZA (repõe o zero à esquerda). A comparação era de TEXTO,
# então toda dimensão e todo peso menor que 1 virava pendência. E a origem de
# ',55' era uma regra do PRÓPRIO prompt -- "omita o zero à esquerda" --,
# herdada da versão antiga e mantida por mim na reescrita.
#
# Um alarme que dispara sempre é igual a alarme nenhum: some no meio do log, e
# o real some junto. Foi o que aconteceu -- havia perdas de verdade (',003'
# virando '0,0') afogadas em 20 falsos positivos.

@pytest.mark.parametrize("pedido,na_tela", [
    (",55", "0,55"),     # o caso do lote, dimensão e peso
    ("0,70", ",70"),     # e o inverso, se um dia o portal devolver sem o zero
    (",215", "0,215"),
    ("5", "5"),
])
def test_normalizacao_do_portal_NAO_e_falha(pedido, na_tela):
    assert upload_conditions.mesmo_valor(pedido, na_tela) is True


@pytest.mark.parametrize("pedido,na_tela", [
    ("10", "1"),         # perdeu um dígito -- valor errado no portal
    (",003", "0,0"),     # perdeu precisão -- limite de casas do campo
    (",005", "0,"),
    (",011", "0,"),
])
def test_perda_de_valor_de_verdade_CONTINUA_sendo_pega(pedido, na_tela):
    """O conserto do falso positivo não podia cegar o alarme real."""
    assert upload_conditions.mesmo_valor(pedido, na_tela) is False


def test_texto_livre_compara_como_TEXTO():
    """Só valor numérico dos dois lados vira comparação de número; o resto
    continua exigindo igualdade literal."""
    assert upload_conditions.mesmo_valor("Caixa de papelão", "Caixa de papelão") is True
    assert upload_conditions.mesmo_valor("Caixa de papelão", "Caixa") is False


def test_o_prompt_nao_manda_mais_omitir_o_zero():
    """A raiz do descasamento. O portal repõe o zero sozinho, então mandar
    ",55" só criava diferença entre o que se pede e o que se lê de volta."""
    from sigft.core.llm import prompts

    assert "omita o zero à esquerda" not in prompts.SYSTEM_CONDICOES


def test_o_campo_numerico_ganha_um_tempo_antes_da_releitura():
    """"10" foi lido como "1" -- o primeiro caractere. Só acontece se a leitura
    chega antes de a máscara do portal terminar de reformatar."""
    assert upload_conditions.PAUSA_CAMPO_ASSENTAR > 0


# =============================================================================
# Fidelidade ao que veio da ficha (2026-08-19)
# =============================================================================
# Correção do usuário: *"nenhum campo da parte de condições tem restrição de
# caracteres, então se for 0,0000000001 ele vai aceitar. Devemos ser
# estritamente fiel à informação que veio da ficha, fazendo a conversão para
# cm — se veio 0,1mm a informação será 0,01 cm"*.
#
# Isso desfaz duas suposições minhas: (a) que o campo tinha limite de casas, e
# (b) que valia adivinhar a unidade quando o número "parecesse absurdo".

@pytest.mark.parametrize("proibido", [
    "assuma milímetros", "assuma gramas", "assuma que a entrada estava em",
])
def test_o_prompt_nao_manda_mais_SUPOR_unidade(proibido):
    """Supor unidade é inventar dado: o número muda, fica plausível, e ninguém
    percebe."""
    from sigft.core.llm import prompts

    assert proibido not in prompts.SYSTEM_CONDICOES


def test_o_prompt_manda_converter_pela_unidade_DECLARADA():
    from sigft.core.llm import prompts
    corrido = " ".join(prompts.SYSTEM_CONDICOES.split())

    assert "Converta a partir da unidade DECLARADA na ficha, e só dela" in corrido
    assert '"0,1 mm" -> "0,01"' in corrido, "o exemplo do usuário tem de estar lá"


def test_o_prompt_proibe_arredondar():
    """"Se for 0,0000000001 ele vai aceitar." Cortar casas é perder informação
    que a ficha trouxe."""
    from sigft.core.llm import prompts
    corrido = " ".join(prompts.SYSTEM_CONDICOES.split())

    assert "NÃO ARREDONDE" in corrido
    assert "0,0000000001" in corrido


def test_valor_com_muitas_casas_e_conferido_normalmente():
    """A conferência não pode ser o que impede um valor legítimo de passar."""
    assert upload_conditions.mesmo_valor("0,0000000001", "0,0000000001") is True


# --- o separador decimal, e o defeito que ele quase escondeu ---------------

@pytest.mark.parametrize("texto,esperado", [
    ("0,5", 0.5),
    ("0.5", 0.5),          # ⚠️ virava 5.0 na 1ª versão -- dez vezes o valor
    ("1.234,56", 1234.56),  # ponto como milhar, só quando há vírgula
    ("10", 10.0),
    ("0,0000000001", 1e-10),
])
def test_o_separador_decimal_e_lido_nos_dois_formatos(texto, esperado):
    assert upload_conditions._para_numero(texto) == esperado


def test_ponto_decimal_nao_e_confundido_com_milhar():
    """A 1ª versão removia TODO ponto antes de converter, então "0.5" virava
    "05" = 5,0. Passaria despercebido justamente quando o portal devolvesse o
    número com ponto -- e aí a conferência aprovaria um valor errado ou
    reprovaria um certo."""
    assert upload_conditions.mesmo_valor("0,5", "0.5") is True
    assert upload_conditions.mesmo_valor("0,05", "0.5") is False


@pytest.mark.parametrize("lixo", ["abc", "", "   ", "-", "."])
def test_texto_nao_numerico_nao_vira_numero(lixo):
    assert upload_conditions._para_numero(lixo) is None

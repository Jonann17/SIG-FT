r"""
COMPLETO só com prova — Condições (2026-08-18).

Pedido do usuário: *"a respeito do salvar como completo no excel: ele só deve
fazer isso se tiver certeza que preencheu os campos de condições (salvo a
parte da valorização), então seja bom uma validação se ele conseguiu salvar
cada um dos campos."*

O que havia antes: `processar_lista` clicava em SALVAR nas 4 abas, dormia, e
chamava `atualizar_status_excel(..., "COMPLETO")` **incondicionalmente**. Os 12
blocos de campos terminavam em `except Exception as e: callback_log("Aviso:
Falha ...")` e o laço seguia. Uma ficha em que tudo falhou saía marcada como
pronta -- e planilha que diz COMPLETO no que ficou pela metade é pior do que
planilha vazia, porque ninguém volta para conferir o que está marcado como
pronto.

A prova que passou a existir é a do próprio portal. O usuário levantou o toast
com a tela à vista:

    <div class="feedback-message-text">As condições de armazenamento foram
     modificadas com sucesso!</div>

e observou a mecânica que torna o teste possível E perigoso ao mesmo tempo:
*"ela aparece relativamente rápido, fica um tempo e depois some"*. Ficar um
tempo significa que, ao salvar a 2ª seção, o toast da 1ª ainda pode estar na
tela -- daí o casamento exigir a PALAVRA DA SEÇÃO, e não só "sucesso". Esse
caso tem teste próprio abaixo, porque é o que separa validar de fingir que
valida.

Os duplos daqui são duck-typed e clicar em SALVAR **produz o toast**, como no
portal: é o que faz este arquivo exercitar a mecânica de verdade
(`portal.mensagem_confirma_secao` + a leitura da tela) em vez de um mock que
devolve True.
"""
import ast
import pathlib

import pytest

from sigft.core.rpa import portal as portal_mod
from sigft.core.rpa.portal import PMIBPortal
from sigft.services import upload_conditions


BOTOES_DE_SALVAR = {
    '//*[@id="b10-b17-b1-b35-Button"]/button': "Armazenamento",
    '//*[@id="b10-b17-$b3"]/div[3]/button': "Transporte",
    '//*[@id="b10-b17-$b4"]/div[4]/button': "Manutenção",
    '//*[@id="b10-b17-$b5"]/div[5]/button': "Descarte",
}

MENSAGEM = {
    "Armazenamento": "As condições de armazenamento foram modificadas com sucesso!",
    "Transporte": "As condições de transporte e movimentação foram modificadas com sucesso!",
    "Manutenção": "As condições de manutenção foram modificadas com sucesso!",
    "Descarte": "As condições de descarte foram modificadas com sucesso!",
}


class _EngineFake:
    """Engine duck-typed. Clicar num botão de SALVAR faz nascer o toast
    correspondente -- como no portal.

    `secoes_mudas` são as seções que gravam sem avisar (ou não gravam);
    `campos_que_falham` é o conjunto de seletores cuja escrita levanta, para
    reproduzir bloco de campos com defeito.
    """

    def __init__(self, *, secoes_mudas=(), campos_que_falham=(), toast_preso=None):
        self.secoes_mudas = set(secoes_mudas)
        self.campos_que_falham = set(campos_que_falham)
        self.toasts = [toast_preso] if toast_preso else []
        self.cliques = []

    # -- o que `safe_click`/`safe_fill` do portal chamam -------------------
    def click(self, seletor):
        self.cliques.append(seletor)
        secao = BOTOES_DE_SALVAR.get(seletor)
        if secao and secao not in self.secoes_mudas:
            # O portal não limpa o toast anterior na hora -- ele "fica um
            # tempo". Acumular reproduz isso.
            self.toasts.append(MENSAGEM[secao])

    def fill(self, seletor, texto):
        if seletor in self.campos_que_falham:
            raise RuntimeError("o site recusou o valor")

    # -- leitura do toast --------------------------------------------------
    def contar(self, seletor):
        if seletor == portal_mod.XPATH_MENSAGEM_DE_FEEDBACK:
            return len(self.toasts)
        return 0

    def texto(self, seletor):
        for posicao, mensagem in enumerate(self.toasts, start=1):
            if seletor == f"({portal_mod.XPATH_MENSAGEM_DE_FEEDBACK})[{posicao}]":
                return mensagem
        return ""

    # -- resto do contrato usado no caminho ------------------------------
    def esta_marcado(self, seletor):
        return False

    def click_dom(self, seletor):
        self.cliques.append(seletor)

    def focar(self, seletor):
        pass

    def press(self, teclas):
        pass

    def digitar_no_foco(self, texto):
        pass

    def goto(self, url):
        pass

    def current_url(self):
        return ""

    def screenshot(self, caminho):
        pass


FICHA = {
    "pmib_codigo": "4500063671.1234",
    "dimensoes": {"comprimento": "30", "largura": "20", "altura": "15"},
    "controle_temperatura": {
        "necessidade": "NÃO",
        "climatizacao": {"ativo": False, "temp_max": "", "temp_min": ""},
        "umidade": {"ativo": False, "hr_max": "", "hr_min": ""},
    },
    "posicao_armazenamento": "Vertical",
    "nocivo": {"status": "Não contém", "cuidado_es": "", "cuidado_pt": ""},
    "peso": {"liquido": "12,5", "bruto": "13,0"},
    "sujeito_intemperie": "NÃO",
    "protecao": ["SN"],
    "empilhamento": "5",
    "outros_cuidados": {"status": "NÃO", "cuidado_es": "", "cuidado_pt": ""},
    "embalagem_transp_es": "Caja", "embalagem_transp_pt": "Caixa",
    "posicao_icagem_es": "Asas", "posicao_icagem_pt": "Alças",
    "cuidad_preserv_es": "a", "cuidad_preserv_pt": "b",
    "limpeza_secagem_es": "c", "limpeza_secagem_pt": "d",
    "ferramentas_es": "e", "ferramentas_pt": "f",
    "legislacao_es": "g", "legislacao_pt": "h",
    "perigoso_10004": "NÃO",
    "descarte_es": "i", "descarte_pt": "j",
    "logistica_reversa": {"status": "NÃO", "logistica_reversa_es": "", "logistica_reversa_pt": ""},
}


@pytest.fixture(autouse=True)
def sem_espera_real(monkeypatch):
    """Nada de dormir de verdade: a espera do toast é de 8 s e a pausa de
    salvamento de 1 s por seção. Com 4 seções, um teste de caso ruim levaria
    mais de meio minuto -- e teste lento é teste que ninguém roda."""
    monkeypatch.setattr(upload_conditions.time, "sleep", lambda _s: None)
    monkeypatch.setattr(portal_mod, "TIMEOUT_CONFIRMACAO_S", 0.0)


def _automacao(engine):
    automacao = upload_conditions.UploadAutomation()
    automacao.engine = engine
    automacao.portal = PMIBPortal(engine)
    automacao.marcadas = []
    automacao.atualizar_status_excel = (
        lambda caminho, pmib, status, cb=None, ask=None: automacao.marcadas.append((pmib, status))
    )
    return automacao


def _rodar(engine, ficha=None):
    automacao = _automacao(engine)
    linhas = []
    completas, incompletas = automacao.processar_lista(
        [dict(ficha or FICHA)], "/tmp/status.xlsx", callback_log=linhas.append)
    return automacao, linhas, completas, incompletas


# =============================================================================
# 1. O caminho feliz continua marcando COMPLETO
# =============================================================================
def test_ficha_sem_falha_e_com_as_4_confirmacoes_vira_COMPLETO():
    automacao, _linhas, completas, incompletas = _rodar(_EngineFake())

    assert completas == ["4500063671.1234"]
    assert incompletas == []
    assert automacao.marcadas == [("4500063671.1234", "COMPLETO")]


# =============================================================================
# 2. Sem confirmação do portal, NÃO marca
# =============================================================================
def test_secao_que_nao_confirma_impede_o_COMPLETO():
    automacao, linhas, completas, incompletas = _rodar(
        _EngineFake(secoes_mudas=["Manutenção"]))

    assert automacao.marcadas == [], "marcou COMPLETO sem o portal ter confirmado"
    assert completas == []
    assert incompletas == ["4500063671.1234"]
    assert any("Manutenção" in l and "sem confirmação" in l for l in linhas)


def test_nenhuma_secao_confirmada_nao_marca_nada():
    """O pior caso, e o que motivou o pedido: robô rodou, nada gravou, ficha
    aparecia como pronta."""
    automacao, _linhas, _c, _i = _rodar(
        _EngineFake(secoes_mudas=BOTOES_DE_SALVAR.values()))

    assert automacao.marcadas == []


# =============================================================================
# 3. Campo que falhou também impede -- e aparece no log
# =============================================================================
def test_bloco_de_campos_com_falha_impede_o_COMPLETO():
    automacao, linhas, _c, incompletas = _rodar(
        _EngineFake(campos_que_falham=['//*[@id="b10-b17-b1-Input_PackingLength"]']))

    assert automacao.marcadas == []
    assert incompletas == ["4500063671.1234"]
    assert any("campo com falha" in l and "Dimensões" in l for l in linhas)


def test_a_mensagem_de_aviso_original_foi_preservada():
    """O texto "Aviso: Falha nas Dimensões. ..." é o de sempre. Registrar a
    pendência não podia mudar o que o usuário já conhece no console."""
    _automacao_, linhas, _c, _i = _rodar(
        _EngineFake(campos_que_falham=['//*[@id="b10-b17-b1-Input_PackingLength"]']))

    assert any(l.startswith("Aviso: Falha nas Dimensões.") for l in linhas)


# =============================================================================
# 4. O toast VELHO não pode confirmar a seção nova
# =============================================================================
def test_toast_de_outra_secao_nao_confirma_a_atual():
    """A armadilha que o usuário descreveu: a mensagem "fica um tempo" na
    tela. Ao salvar Transporte, o toast de Armazenamento pode continuar lá.

    Se o casamento fosse por "sucesso", esta ficha sairia COMPLETO com três
    seções não gravadas -- exatamente o defeito que este trabalho remove,
    reintroduzido pela porta dos fundos.
    """
    engine = _EngineFake(
        secoes_mudas=["Transporte", "Manutenção", "Descarte"],
        toast_preso=MENSAGEM["Armazenamento"],
    )
    automacao, _linhas, _c, _i = _rodar(engine)

    assert automacao.marcadas == [], (
        "um toast remanescente de outra seção foi aceito como confirmação"
    )


def test_a_confirmacao_exige_a_palavra_da_secao_e_nao_so_sucesso():
    assert portal_mod.mensagem_confirma_secao(MENSAGEM["Armazenamento"], "Armazenamento")
    assert not portal_mod.mensagem_confirma_secao(MENSAGEM["Armazenamento"], "Transporte")
    assert portal_mod.mensagem_confirma_secao(MENSAGEM["Transporte"], "Transporte")


def test_secao_desconhecida_nunca_confirma():
    """Nome fora da tabela devolve False. Inventar um casamento para um nome
    que não conhecemos seria adivinhar, e adivinhar aqui produz COMPLETO."""
    assert not portal_mod.mensagem_confirma_secao(
        "Tudo modificado com sucesso!", "Valorização")


# =============================================================================
# 5. A Valorização fica FORA do critério, de propósito
# =============================================================================
def test_a_valorizacao_nao_entra_no_criterio_de_completo():
    """"salvo a parte da valorização" -- pedido do usuário. Este módulo não
    preenche a aba financeira; exigir confirmação dela deixaria TODA ficha
    INCOMPLETO para sempre."""
    assert upload_conditions.SECOES_DE_CONDICOES == (
        "Armazenamento", "Transporte", "Manutenção", "Descarte")
    assert not any("valoriza" in s.lower() for s in upload_conditions.SECOES_DE_CONDICOES)


# =============================================================================
# 6. A classe continua inteira
# =============================================================================
# Durante ESTA mudança um helper de módulo foi inserido por engano no meio do
# corpo de `UploadAutomation`, o que aninhou `processar_lista`,
# `safe_save_with_pause` e `atualizar_status_excel` dentro dele. O arquivo
# COMPILA nessa forma -- `compileall` passou, e a classe simplesmente ficou
# sem três métodos. Só um teste que olhe a estrutura pega isso.
def test_uploadautomation_mantem_seus_metodos():
    fonte = (pathlib.Path(upload_conditions.__file__)).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    classe = next(n for n in arvore.body
                  if isinstance(n, ast.ClassDef) and n.name == "UploadAutomation")
    metodos = {n.name for n in classe.body if isinstance(n, ast.FunctionDef)}

    assert {"processar_lista", "safe_save_with_pause", "atualizar_status_excel",
            "safe_click", "safe_send_keys", "check_or_uncheck", "iniciar"} <= metodos

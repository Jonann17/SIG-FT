r"""
A seção "Fabricantes e fornecedores" da ficha ALVO tem QUANTAS linhas?

Sessão real de 2026-08-19, ficha 4500063671.1418. O log:

    Fabricante: PHOENIX CONTACT (campo de referência: b10-b11-b4-Input_TextVar)
    Referência: 2904616
    [Erro] Nenhum combo diz 'fornecedor' na tela.
    [Erro] 2 campos de Referência na tela e o fabricante não indicou qual é o
           dele. NÃO escrevi nada -- preencha à mão.
    Referência da GE Vernova vazia -- pulando, como combinado.
    4500063671.1418: falhou em fornecedor, referencia_fornecedor

E a TELA, no print que o usuário mandou depois, mostrando a mesma ficha em
edição:

    ┌ Adicionar Fabricante / Referência ─────────────────────────┐
    │ Fabricante  [ Selecione um fabricante ▾ ]                  │
    │ (tabela)    Sem fabricantes para mostrar...                │
    ├ Adicionar Fornecedor / Referência ─────────────────────────┤
    │ Fornecedor  GE ENERGIAS RENOVAVEIS LTDA   <- TEXTO, não combo
    │ Referência ⓘ [__________________]  ⊕                       │
    │ (tabela)    Sem fornecedores para mostrar...               │
    └────────────────────────────────────────────────────────────┘

Duas conclusões, e as duas contrariam o que o código assumia:

1. **A linha do fornecedor NÃO TEM COMBO nesta ficha** -- o fornecedor é fixo,
   e o ícone ⓘ que eu tinha catalogado como "o marcador da linha da GE
   Vernova" está justamente nela. Os dois `[Erro]` acima não são falhas: são o
   robô procurando uma linha que esta ficha não tem, e depois recusando (com
   razão) escrever num campo ambíguo. Ausência de linha ≠ falha; tratá-las
   como falha é o que fez a ficha sair "0 de 1".

2. **O "+" não comitou a linha do fabricante.** A prova está no próprio log:
   quando o passo do fornecedor contou os campos de Referência, achou DOIS --
   o da GE mais o do fabricante, que continuava na tela com o valor digitado.
   Se o "+" tivesse funcionado, a linha teria ido para a tabela e o formulário
   de adicionar teria se recolhido: seria UM. Mesmo assim o log disse
   "Referência: 2904616", porque `escrever_referencia` reporta sucesso depois
   de clicar no "+" sem nunca conferir se a linha entrou -- e `safe_click`
   engole a falha do clique por contrato. É o mesmo defeito de classe que o
   "COMPLETO só com prova" fechou em Condições.

O que este arquivo tranca é o comportamento certo dos dois pontos, mais a
regra de origem dos dados que o usuário corrigiu na mesma mensagem.
"""
import pytest

from sigft.services import duplicadas_injetor as injetor
from sigft.services import duplicadas_robo as robo
from tests.test_duplicadas_injetor import _EngineFalso, _PortalFalso


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(injetor.time, "sleep", lambda _s: None)


# =============================================================================
# 1. Linha de fornecedor SEM COMBO: a linha não existe, e isso não é falha
# =============================================================================
def test_sem_combo_de_fornecedor_a_linha_nao_existe_e_nao_e_falha():
    """Zero combos dizendo 'fornecedor' é a tela do print: o fornecedor é
    fixo. Uma linha que a ficha não tem não pode contar como pendência."""
    engine = _EngineFalso(combos=["Selecione um fabricante"])
    portal = _PortalFalso(engine)

    resultado = injetor.escolher_fornecedor(portal, "GE ENERGIAS RENOVAVEIS LTDA")

    assert resultado.ok is True, "ausência de linha não é falha"
    assert resultado.tem_linha is False


def test_sem_combo_de_fornecedor_o_log_explica_qual_linha_recebe_a_referencia():
    """Quem lê o log precisa saber que a referência não se perdeu -- ela vai
    pela linha fixa, com o CÓDIGO CMI/GE da planilha."""
    portal = _PortalFalso(_EngineFalso(combos=["Selecione um fabricante"]))
    linhas = []

    injetor.escolher_fornecedor(portal, "GE ENERGIAS RENOVAVEIS LTDA", linhas.append)

    assert any("fixa" in l.lower() for l in linhas)
    assert not any("[Erro]" in l for l in linhas), (
        "não é erro: é uma ficha cuja seção tem duas linhas em vez de três"
    )


def test_combo_de_fornecedor_PRESENTE_continua_sendo_usado():
    """A ficha do print tem duas linhas; outras podem ter três (o usuário
    descreveu um caso com dois fornecedores). Quem decide é a TELA, não uma
    constante -- então o caminho do combo não pode ser removido."""
    engine = _EngineFalso(
        combos=["Selecione um fornecedor"],
        ids_referencia=[], id_que_nasce="b1-b9-b3-Input_TextVar",
        opcoes=["SASSI"],
    )
    portal = _PortalFalso(engine)

    resultado = injetor.escolher_fornecedor(portal, "SASSI")

    assert resultado.ok is True
    assert resultado.tem_linha is True
    assert resultado.id_do_campo_de_referencia == "b1-b9-b3-Input_TextVar"


def test_linha_de_fornecedor_ausente_nao_tenta_escrever_referencia(monkeypatch):
    """O 2º `[Erro]` do log real era consequência do 1º: sem combo, o passo
    seguinte ia escrever mesmo assim e batia na ambiguidade. Se a linha não
    existe, não há nada a escrever nela."""
    escritas = []

    def _fake_escrever(portal, codigo, callback_log=None, id_do_campo="",
                       nome_da_secao="referencia", log_auditoria=None):
        escritas.append(nome_da_secao)
        return injetor.ResultadoDaSecao(nome_da_secao, True, codigo)

    monkeypatch.setattr(robo.injetor, "escrever_referencia", _fake_escrever)
    _montar_robo_de_mentira(monkeypatch, com_combo_de_fornecedor=False)

    robo.processar_ficha(_PortalFalso(_EngineFalso()), _FichaFalsa())

    assert "referencia_fornecedor" not in escritas, (
        "escrever na linha que não existe é o que produzia o erro de "
        "ambiguidade -- e, sem a recusa, poria a referência na linha da GE"
    )
    assert "referencia" in escritas, "a linha do FABRICANTE continua sendo escrita"


# =============================================================================
# 2. O "+" precisa de PROVA de que a linha entrou
# =============================================================================
def test_referencia_falha_quando_a_linha_NAO_entra_na_tabela():
    """O caso do log real: clicou no "+", nada foi para a tabela, e o campo
    continuou na tela com o valor digitado."""
    engine = _EngineFalso(ids_referencia=["b10-b11-b4-Input_TextVar"])
    portal = _PortalFalso(engine)
    portal.limpa_no_mais = False      # o "+" não fez nada -- o caso real
    linhas = []

    resultado = injetor.escrever_referencia(
        portal, "2904616", linhas.append, id_do_campo="b10-b11-b4-Input_TextVar")

    assert resultado.ok is False, (
        "reportar sucesso sem a linha na tabela é o que fez o usuário "
        "descobrir a falha só ao abrir a ficha"
    )
    assert any("não entrou" in l.lower() for l in linhas)
    assert any("2904616" in l for l in linhas), "o log tem de dizer o que digitar à mão"


def test_referencia_da_certo_quando_o_campo_se_recolhe():
    """Comitada a linha, o portal recolhe o formulário de adicionar -- o campo
    some da tela. É a mesma mecânica do "campo que nasce", ao contrário."""
    engine = _EngineFalso(ids_referencia=["b10-b11-b4-Input_TextVar"])
    portal = _PortalFalso(engine)
    portal.comita_no_mais = True

    resultado = injetor.escrever_referencia(
        portal, "2904616", None, id_do_campo="b10-b11-b4-Input_TextVar")

    assert resultado.ok is True
    assert resultado.detalhe == "2904616"


def test_referencia_da_certo_quando_o_campo_fica_mas_e_limpo():
    """A linha FIXA (a do fornecedor/GE) não some ao comitar -- ela esvazia.
    Os dois desfechos provam a mesma coisa: o portal levou o valor embora."""
    engine = _EngineFalso(ids_referencia=["b10-b11-b4-Input_TextVar"])
    portal = _PortalFalso(engine)
    portal.limpa_no_mais = True

    resultado = injetor.escrever_referencia(
        portal, "2904616", None, id_do_campo="b10-b11-b4-Input_TextVar")

    assert resultado.ok is True


def test_o_clique_no_mais_reporta_o_motivo_quando_falha():
    """`safe_click` engole por contrato, e foi por isso que um "+" que não
    funcionou virou log de sucesso. O caminho estrito diz o porquê."""
    engine = _EngineFalso(ids_referencia=["b10-b11-b4-Input_TextVar"])
    portal = _PortalFalso(engine)
    portal.erro_no_clique_estrito = TimeoutError("elemento não clicável")
    linhas = []

    resultado = injetor.escrever_referencia(
        portal, "2904616", linhas.append, id_do_campo="b10-b11-b4-Input_TextVar")

    assert resultado.ok is False
    assert any("não clicável" in l for l in linhas), (
        "o motivo do clique falho é a informação que faltava no log real"
    )


# =============================================================================
# 3. De ONDE vem cada dado -- correção do usuário em 2026-08-19
# =============================================================================
# *"embora a ficha original tenha o (ref. 08934100MEU38-208F) como referência
# da GE, não devemos copiar e colar na ficha alvo, pois esse número muda quando
# estamos trabalhando para outro sistema; essa informação deve vir
# exclusivamente da planilha _STATUS_PMIB. O código do material do fabricante
# (2904616) deve vir da _STATUS_PMIB, mas o nome do fabricante vem da ficha
# original."*

def test_o_NOME_do_fabricante_vem_da_ficha_original():
    # `ler_fabricantes_e_fornecedores` devolve pares (nome, referência).
    tabelas = {"fabricantes": [("PHOENIX CONTACT", "2904616")]}

    class _FichaComOutraMarca:
        fabricante = "PHOENIX CONTACTS S.A."   # a planilha diverge

    assert robo.achar_fabricante_na_tabela(tabelas, [], _FichaComOutraMarca()) \
        == "PHOENIX CONTACT"


def test_a_planilha_e_a_RESERVA_quando_a_original_nao_traz_fabricante():
    class _FichaComMarca:
        fabricante = "PHOENIX CONTACT"

    assert robo.achar_fabricante_na_tabela({}, [], _FichaComMarca()) == "PHOENIX CONTACT"


def test_nenhuma_referencia_lida_da_ficha_original_e_escrita_na_alvo():
    """A regra estrutural, e o motivo dela: *"esse número muda quando estamos
    trabalhando para outro sistema"*. Um teste de AST, porque o risco não é o
    valor de hoje -- é alguém, daqui a três meses, achar prático reaproveitar
    a referência que já está lida na mão."""
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(robo.processar_ficha))
    arvore = ast.parse(fonte)

    argumentos_escritos = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = getattr(no.func, "attr", "")
        if not alvo.startswith("escrever_referencia"):
            continue
        argumentos_escritos.extend(
            ast.unparse(a) for a in no.args if ast.unparse(a) != "portal")

    assert argumentos_escritos, "o teste precisa achar as chamadas de escrita"
    for argumento in argumentos_escritos:
        if argumento in ("callback_log",):
            continue
        assert argumento.startswith("ficha.") or argumento.startswith("getattr(ficha"), (
            f"{argumento!r} não vem da planilha. Só `ficha.*` (lido do "
            f"_STATUS_PMIB) pode ser escrito na ficha alvo -- referência lida "
            f"da ficha original muda de sistema para sistema."
        )


# =============================================================================
# Apoio
# =============================================================================
class _FichaFalsa:
    pmib = "4500063671.1418"
    ficha_original = "4500063671.1263"
    descricao = "FONTE DE ALIMENTAÇÃO"
    codigo_material = "2904616"
    codigo_fornecedor = ""
    fabricante = "PHOENIX CONTACT"
    linha = 7


def _montar_robo_de_mentira(monkeypatch, com_combo_de_fornecedor):
    """Neutraliza tudo que fala com o portal, menos o que o teste observa."""
    monkeypatch.setattr(robo, "ler_ficha_original", lambda *a, **k: {})
    monkeypatch.setattr(robo.extrator, "ler_fabricantes_e_fornecedores",
                        lambda *a, **k: {})
    monkeypatch.setattr(robo, "abrir_alvo_para_edicao", lambda *a, **k: True)

    def _secao(nome, tem_linha=True):
        def _fn(*a, **k):
            r = injetor.ResultadoDaSecao(nome, True, "")
            r.tem_linha = tem_linha
            return r
        return _fn

    monkeypatch.setattr(robo.injetor, "escolher_fabricante", _secao("fabricante"))
    monkeypatch.setattr(robo.injetor, "escolher_fornecedor",
                        _secao("fornecedor", com_combo_de_fornecedor))
    monkeypatch.setattr(robo.injetor, "escrever_referencia_da_ge",
                        _secao("ge_vernova"))
    monkeypatch.setattr(robo.injetor, "limpar_caracteristicas",
                        _secao("caracteristicas"))


# =============================================================================
# 4. O SALVAR da seção de Fabricantes — REMOVIDO em 2026-08-19
# =============================================================================
# Havia aqui um `test_salvar_da_secao_que_falha_vira_pendencia`, escrito no
# mesmo dia, provando que o retorno de `clicar_salvar_visivel` não podia ser
# descartado nesta seção. A premissa estava errada e quem a corrigiu foi o
# usuário: *"o único campo que não precisa salvar é o de fabricantes e
# fornecedores, esse não tem botão de salvar."*
#
# Bate com o resto do que se sabe da tela: quem comita a linha ali é o "+",
# e é por isso que a prova daquela seção é a linha ENTRAR NA TABELA -- testada
# em `test_referencia_falha_quando_a_linha_NAO_entra_na_tabela`, acima.
#
# O teste ficou aqui como registro porque o erro é atraente: toda seção do
# portal tem SALVAR, menos esta. Quem for "corrigir a inconsistência" no
# futuro vai reintroduzir uma pendência inventada em TODA ficha -- que é
# exatamente o que a versão anterior fazia, e durou um commit.

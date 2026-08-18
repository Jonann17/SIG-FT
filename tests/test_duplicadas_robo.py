r"""
O robô da ficha duplicada (CP 6.3) — a ordem das coisas e o que conta como ok.

O portal é de mentira; o que se testa é a ORQUESTRAÇÃO: por qual porta entra em
cada ficha, o que acontece quando uma etapa falha, e o que o lote reporta no
fim. As peças (extrator, injetor) têm os seus próprios testes.
"""
import pytest

from sigft import config
from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_injetor as injetor
from sigft.services import duplicadas_robo as robo


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(robo.time, "sleep", lambda _s: None)


class _Ficha:
    def __init__(self, pmib="4500063671.1418", original="4500063671.1471",
                 material="2904616", descricao="FONTE"):
        self.pmib = pmib
        self.ficha_original = original
        self.codigo_material = material
        self.codigo_fornecedor = "CMI-1"
        self.descricao = descricao
        self.linha = 12


class _PortalFalso:
    def __init__(self):
        self.engine = self
        self.cliques = []
        self.salvou = []

    # -- lado engine
    def click_nativo(self, seletor):
        self.cliques.append(seletor)

    def element_exists(self, _seletor):
        return False

    def contar(self, _seletor):
        return 0

    # -- lado portal
    def ir_para_lista(self):
        pass

    def safe_click(self, seletor):
        self.cliques.append(seletor)

    def safe_fill(self, _seletor, _texto):
        pass

    def clicar_salvar_visivel(self, nome=""):
        self.salvou.append(nome)
        return True


def _com_etapas(monkeypatch, *, blocos=(("Fabricantes", {"Fabricante": "SCHNEIDER"}),),
                achou_original=True, achou_alvo=True, secoes_ok=True):
    portal = _PortalFalso()
    monkeypatch.setattr(robo.extrator, "abrir_original_em_visualizacao",
                        lambda *_a, **_k: achou_original)
    monkeypatch.setattr(robo.extrator, "ler_secao_visivel", lambda *_a, **_k: list(blocos))
    monkeypatch.setattr(robo.extrator, "localizar_aba_da_ficha",
                        lambda *_a, **_k: "Em Elaboração" if achou_alvo else None)

    def _secao(nome):
        return lambda *_a, **_k: injetor.ResultadoDaSecao(nome, secoes_ok, "")

    monkeypatch.setattr(robo.injetor, "escolher_fabricante", _secao("fabricante"))
    monkeypatch.setattr(robo.injetor, "escrever_referencia", _secao("referencia"))
    monkeypatch.setattr(robo.injetor, "escrever_referencia_do_fornecedor", _secao("fornecedor"))
    monkeypatch.setattr(robo.injetor, "limpar_caracteristicas", _secao("caracteristicas"))
    return portal


# ===========================================================================
# Motor
# ===========================================================================
def test_o_modulo_novo_roda_em_playwright():
    """"Podemos fazer direto no motor novo" -- palavra do usuário. É o primeiro
    módulo do projeto que nunca teve versão Selenium."""
    assert config.get_rpa_engine(robo.NOME_DO_MODULO) == config.ENGINE_PLAYWRIGHT


def test_o_robo_novo_nao_importa_selenium():
    """Princípio nº 3: nenhum serviço conhece o motor. Se um `import selenium`
    entrar aqui, o módulo deixa de ser portável e o CP 5.5 volta a travar.

    A checagem é por AST, e não por `"selenium" in fonte`: a primeira versão
    era textual e reprovou os próprios COMENTÁRIOS que explicam por que não há
    Selenium aqui. Um teste que proíbe falar do assunto empurra a explicação
    para fora do código -- exatamente onde ela não serve.
    """
    import ast
    import inspect

    for modulo in (robo, injetor, robo.extrator):
        arvore = ast.parse(inspect.getsource(modulo))
        importados = []
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados += [alias.name for alias in no.names]
            elif isinstance(no, ast.ImportFrom):
                importados.append(no.module or "")
        assert not any("selenium" in nome.lower() for nome in importados), (
            f"{modulo.__name__} importa Selenium: {importados}")


# ===========================================================================
# Por qual porta entra em cada ficha
# ===========================================================================
def test_abre_a_original_em_visualizacao_e_a_alvo_em_edicao(monkeypatch):
    """A original a gente só LÊ (e ela pode estar em status que nem abre para
    edição); a alvo é onde se escreve."""
    portal = _com_etapas(monkeypatch)

    robo.processar_ficha(portal, _Ficha(), callback_log=lambda _m: None)

    assert any("-Edit" in c for c in portal.cliques)
    assert not any("-View" in c for c in portal.cliques)  # quem abre a original é o extrator


def test_ficha_original_nao_encontrada_e_erro_fatal_da_ficha(monkeypatch):
    """Sem a original não há de onde copiar: seguir para a alvo escreveria uma
    ficha com dados de lugar nenhum."""
    portal = _com_etapas(monkeypatch, achou_original=False)

    resultado = robo.processar_ficha(portal, _Ficha(), callback_log=lambda _m: None)

    assert resultado.ok is False
    assert "original" in resultado.erro_fatal
    assert portal.cliques == []  # não tocou na alvo


def test_ficha_alvo_nao_encontrada_para_o_processamento_dela(monkeypatch):
    portal = _com_etapas(monkeypatch, achou_alvo=False)

    resultado = robo.processar_ficha(portal, _Ficha(), callback_log=lambda _m: None)

    assert resultado.ok is False
    assert "alvo" in resultado.erro_fatal
    assert resultado.secoes == []


# ===========================================================================
# O que conta como sucesso
# ===========================================================================
def test_todas_as_secoes_ok_e_ficha_ok(monkeypatch):
    portal = _com_etapas(monkeypatch)

    resultado = robo.processar_ficha(portal, _Ficha(), callback_log=lambda _m: None)

    assert resultado.ok is True
    assert [s.nome for s in resultado.secoes] == [
        "fabricante", "referencia", "fornecedor", "caracteristicas"]


def test_uma_secao_falha_e_a_ficha_NAO_e_sucesso(monkeypatch):
    """Contar como sucesso o que ficou pela metade é o que faz um lote fechar
    "✅" com a ficha errada no portal."""
    portal = _com_etapas(monkeypatch, secoes_ok=False)

    resultado = robo.processar_ficha(portal, _Ficha(), callback_log=lambda _m: None)

    assert resultado.ok is False
    assert "falhou em" in resultado.resumo


def test_excecao_inesperada_nao_derruba_a_ficha_nem_o_lote(monkeypatch):
    portal = _com_etapas(monkeypatch)
    monkeypatch.setattr(robo.injetor, "escrever_referencia",
                        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))

    resultado = robo.processar_ficha(portal, _Ficha(), callback_log=lambda _m: None)

    assert resultado.ok is False
    assert "RuntimeError" in resultado.erro_fatal


# ===========================================================================
# O fabricante lido da original
# ===========================================================================
def test_acha_o_fabricante_em_qualquer_bloco():
    blocos = [("Volume", {"Altura": "3"}), ("Fabricantes", {"Fabricante": "SCHNEIDER"})]

    assert robo.achar_fabricante(blocos) == "SCHNEIDER"


def test_sem_rotulo_conhecido_devolve_vazio_em_vez_de_chutar():
    """Chutar aqui viraria fabricante ERRADO na ficha -- que não dá sintoma
    nenhum na tela. Vazio faz o injetor pular com aviso."""
    blocos = [("Volume", {"Altura": "3", "Peso": "10"})]

    assert robo.achar_fabricante(blocos) == ""


def test_fabricante_ausente_NAO_impede_o_resto(monkeypatch):
    """Perder também a purga por causa do fabricante seria trocar uma pendência
    pequena por uma ficha inteira errada."""
    portal = _com_etapas(monkeypatch, blocos=[("Volume", {"Altura": "3"})])
    logs = []

    resultado = robo.processar_ficha(portal, _Ficha(), callback_log=logs.append)

    assert len(resultado.secoes) == 4
    assert any("fabricante" in linha for linha in logs)


# ===========================================================================
# O lote
# ===========================================================================
def test_o_lote_segue_depois_de_uma_ficha_ruim(monkeypatch):
    portal = _com_etapas(monkeypatch)
    chamadas = {"n": 0}
    original = robo.processar_ficha

    def processar_ficha(p, ficha, callback_log=None):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            resultado = robo.ResultadoDaFicha(ficha.pmib, ficha.ficha_original)
            resultado.erro_fatal = "falhou de proposito"
            return resultado
        return original(p, ficha, callback_log)

    monkeypatch.setattr(robo, "processar_ficha", processar_ficha)

    resultados = robo.processar_lote(
        [_Ficha("A"), _Ficha("B")], callback_log=lambda _m: None, portal=portal)

    assert len(resultados) == 2
    assert [r.ok for r in resultados] == [False, True]


def test_o_resumo_final_lista_so_as_pendentes(monkeypatch):
    portal = _com_etapas(monkeypatch, secoes_ok=False)
    logs = []

    robo.processar_lote([_Ficha("A")], callback_log=logs.append, portal=portal)

    juntos = "\n".join(logs)
    assert "0 de 1" in juntos and "A: falhou em" in juntos


def test_parada_pedida_pelo_usuario_interrompe_entre_fichas(monkeypatch):
    """Parar NO MEIO de uma ficha deixaria a ficha pela metade no portal; entre
    fichas, o que já foi feito está salvo."""
    portal = _com_etapas(monkeypatch)
    logs = []

    robo.processar_lote([_Ficha("A"), _Ficha("B")], callback_log=logs.append,
                        portal=portal, deve_parar=lambda: True)

    assert "Parado pelo usuário" in "\n".join(logs)


def test_o_progresso_e_reportado_por_ficha(monkeypatch):
    portal = _com_etapas(monkeypatch)
    progresso = []

    robo.processar_lote([_Ficha("A"), _Ficha("B")], callback_log=lambda _m: None,
                        portal=portal, callback_progresso=progresso.append)

    assert progresso == [0.5, 1.0]


# ===========================================================================
# De onde vem cada dado — a ordem de precedência que o usuário definiu
# ===========================================================================
class _FichaComMarca(_Ficha):
    def __init__(self, fabricante="", codigo_fornecedor="CMI-1", **kwargs):
        super().__init__(**kwargs)
        self.fabricante = fabricante
        self.codigo_fornecedor = codigo_fornecedor
        self.linha = 12


def test_o_fabricante_vem_da_PLANILHA_e_nao_do_portal():
    """"Você sabe que tem, já te pedi para mapear no conhecimento do
    _STATUS_PMIB todas as informações que temos hoje." A coluna MARCA/MODELO
    está mapeada desde 2026-08-13; raspar o portal para descobrir o que ela já
    diz seria trabalho a mais para resultado igual ou pior."""
    blocos = [("Fabricantes", {"Fabricante": "DO PORTAL"})]

    assert robo.achar_fabricante(blocos, _FichaComMarca(fabricante="WAGO")) == "WAGO"


def test_sem_marca_na_planilha_a_ficha_original_entra_como_reserva():
    blocos = [("Fabricantes", {"Fabricante": "DO PORTAL"})]

    assert robo.achar_fabricante(blocos, _FichaComMarca(fabricante="")) == "DO PORTAL"


def test_sem_fabricante_em_lugar_nenhum_devolve_vazio_e_nao_chuta():
    assert robo.achar_fabricante([], _FichaComMarca(fabricante="")) == ""


def test_a_referencia_do_fornecedor_vem_da_FICHA_ORIGINAL_primeiro():
    """Ordem INVERTIDA em relação ao fabricante, e é decisão do usuário: "o
    fornecedor você pode tirar da ficha original, acho que seria mais
    correto"."""
    blocos = [("Fornecedores", {"Referência do fornecedor": "DA ORIGINAL"})]

    achada = robo.achar_referencia_do_fornecedor(
        blocos, _FichaComMarca(codigo_fornecedor="DA PLANILHA"))

    assert achada == "DA ORIGINAL"


def test_fornecedor_vazio_na_original_cai_para_a_planilha():
    """"...só caso lá estiver vazio" -- aí a coluna CÓDIGO CMI / CÓDIGO GE."""
    achada = robo.achar_referencia_do_fornecedor(
        [], _FichaComMarca(codigo_fornecedor="CMI-99"))

    assert achada == "CMI-99"


def test_fornecedor_vazio_nos_dois_devolve_vazio():
    """"Se por fim você não conseguir, deixa em branco" -- e a ficha vira
    INCOMPLETO na planilha, em vez de receber o código de outra."""
    assert robo.achar_referencia_do_fornecedor([], _FichaComMarca(codigo_fornecedor="")) == ""


def test_o_fornecedor_recebe_a_referencia_resolvida_pela_ordem_do_usuario(monkeypatch):
    """A ficha original tem precedência sobre a planilha para o FORNECEDOR --
    ordem invertida em relação ao fabricante, e é decisão do usuário."""
    portal = _com_etapas(
        monkeypatch,
        blocos=[("Fornecedores", {"Referência do fornecedor": "DA ORIGINAL"})])
    recebidos = []
    monkeypatch.setattr(
        robo.injetor, "escrever_referencia_do_fornecedor",
        lambda _p, referencia, _log=None: recebidos.append(referencia)
        or injetor.ResultadoDaSecao("fornecedor", True, ""))

    robo.processar_ficha(portal, _FichaComMarca(fabricante="WAGO",
                                                codigo_fornecedor="DA PLANILHA"),
                         callback_log=lambda _m: None)

    assert recebidos == ["DA ORIGINAL"]


def test_log_com_atributo_ausente_nao_derruba_a_ficha(monkeypatch):
    """CONTRAPROVA: a mensagem de aviso do fabricante lia `ficha.linha` direto.
    Num objeto sem esse atributo, o `AttributeError` era engolido pelo `except`
    do processamento e a ficha morria com "erro fatal" -- por causa de uma
    linha que existia só para avisar."""
    portal = _com_etapas(monkeypatch, blocos=[("Volume", {"Altura": "3"})])

    class _FichaCrua:
        pmib = "A"
        ficha_original = "B"
        codigo_material = "C"
        descricao = "D"
        # sem `linha`, sem `fabricante`, sem `codigo_fornecedor`

    resultado = robo.processar_ficha(portal, _FichaCrua(), callback_log=lambda _m: None)

    assert resultado.erro_fatal == ""
    assert len(resultado.secoes) == 4

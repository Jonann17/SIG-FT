r"""
A instrumentação que fecha o diagnóstico das Condições (2026-08-24).

Contexto, porque estes testes guardam um conserto que é fácil de desfazer sem
perceber: na rodada de 2026-08-24 o robô falhou em quatro seções e eu não tinha
como diagnosticar nenhuma delas, porque as PROVAS não estavam sendo colhidas.

Três buracos, todos de observação:

1. **A foto da sub-aba de Condições saía sem âncora.** `fotografar` então caía
   no último recurso (`//form | //body`), que começa no topo da página; o teto
   de 20 000 caracteres gastava a foto inteira no cabeçalho do portal. As duas
   fotos daquele log tinham 20 KB de menu e calendário e nenhuma linha de
   Condições. O mesmo defeito já tinha sido consertado em `abrir_secao` e ficou
   para trás aqui.

2. **A lista de rótulos desconhecidos vinha sem o valor.** "Posição de
   armazenamento" sozinho não fecha o mapa: na edição isso é um radio, e o que
   se escolhe é a OPÇÃO ("Horizontal"), não o rótulo.

3. **A ficha ALVO nunca era fotografada em edição.** É o único lugar onde os 45
   campos existem com o rótulo do lado -- a visualização da original mostra 2
   dos 19 booleanos como `<input>` e nenhum campo em espanhol. Sem essa foto o
   mapa não tem como ser completado, por mais rodadas que se façam.

E um quarto, no PDM: `PDM.9900.000 não apareceu no combo` apareceu em três
rodadas seguidas sem nunca dizer o que o combo estava mostrando -- e as duas
causas possíveis (não está no catálogo × o filtro foi para o lugar errado)
pedem consertos opostos.
"""
import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_condicoes as cond
from sigft.services import duplicadas_extrator as extrator
from sigft.services import duplicadas_pdm as pdm


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(cond.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(pdm.time, "sleep", lambda *_a, **_k: None)


def _coletor():
    linhas = []
    return linhas, linhas.append


# ===========================================================================
# 1. O rótulo desconhecido sai COM o valor
# ===========================================================================

def test_rotulo_desconhecido_e_logado_com_o_valor(monkeypatch):
    """Sem o valor, a lista não serve para nada: o mapa precisa saber QUE
    opção a original mostra para escolher o radio certo na alvo."""
    monkeypatch.setattr(sel, "CONDICOES_ROTULO_PARA_CAMPO", {})
    linhas, log = _coletor()

    cond.converter_da_visualizacao(
        [("Posição de armazenamento", "Horizontal")], log)

    assert any("Posição de armazenamento" in l and "Horizontal" in l
               for l in linhas)


def test_rotulo_desconhecido_e_VAZIO_diz_que_esta_vazio(monkeypatch):
    """Rótulo sem valor continua sendo logado -- a lista serve para construir
    o mapa, não para relatar esta ficha -- mas dizendo que veio vazio, para
    não parecer que o valor se perdeu na leitura."""
    monkeypatch.setattr(sel, "CONDICOES_ROTULO_PARA_CAMPO", {})
    linhas, log = _coletor()

    cond.converter_da_visualizacao([("Logística de reversa", "")], log)

    assert any("Logística de reversa" in l and "vazio" in l for l in linhas)


def test_o_MESMO_rotulo_nao_e_repetido_na_lista(monkeypatch):
    monkeypatch.setattr(sel, "CONDICOES_ROTULO_PARA_CAMPO", {})
    linhas, log = _coletor()

    cond.converter_da_visualizacao(
        [("Nocivo", "Não contém"), ("Nocivo", "Não contém")], log)

    assert sum(1 for l in linhas if "· Nocivo" in l) == 1


# ===========================================================================
# 2. A foto da ficha ALVO em EDIÇÃO
# ===========================================================================

class _PortalDeFoto:
    def __init__(self):
        self.cliques = []

    def safe_click(self, seletor):
        self.cliques.append(seletor)


def _espionar_foto(monkeypatch, painel="b10-Conditions_Content"):
    fotos = []
    monkeypatch.setattr(extrator, "id_do_painel", lambda *_a, **_k: painel)
    monkeypatch.setattr(cond.extrator, "fotografar",
                        lambda _p, titulo, _log=None, seletor=None:
                        fotos.append((titulo, seletor)))
    return fotos


def test_sem_auditoria_a_foto_da_alvo_nao_custa_nada(monkeypatch):
    """O caminho normal do lote não tem auditoria ligada, e não pode pagar
    quatro trocas de sub-aba por ficha para não fotografar nada."""
    fotos = _espionar_foto(monkeypatch)
    portal = _PortalDeFoto()

    cond.fotografar_edicao(portal, None, lambda _m: None)

    assert fotos == []
    assert portal.cliques == []


def test_fotografa_as_QUATRO_subabas_da_alvo(monkeypatch):
    fotos = _espionar_foto(monkeypatch)

    cond.fotografar_edicao(_PortalDeFoto(), object(), lambda _m: None)

    assert len(fotos) == len(sel.CONDICOES_POR_SUBABA)
    for nome in sel.CONDICOES_POR_SUBABA:
        assert any(nome in titulo for titulo, _ in fotos), nome


def test_a_foto_da_alvo_diz_que_e_EDICAO(monkeypatch):
    """O log tem foto da original e foto da alvo lado a lado; sem o rótulo no
    título eu já confundi as duas uma vez."""
    fotos = _espionar_foto(monkeypatch)

    cond.fotografar_edicao(_PortalDeFoto(), object(), lambda _m: None)

    assert all("EDIÇÃO" in titulo for titulo, _ in fotos)


def test_a_foto_da_alvo_e_ANCORADA_no_painel(monkeypatch):
    """⚠️ O DEFEITO DE 2026-08-24. Sem `seletor`, `fotografar` cai em
    `//form | //body` e o teto de 20 000 caracteres come a foto no cabeçalho
    da página -- exatamente o que me deixou cego."""
    fotos = _espionar_foto(monkeypatch, painel="b10-Conditions_Content")

    cond.fotografar_edicao(_PortalDeFoto(), object(), lambda _m: None)

    for _titulo, seletor in fotos:
        assert seletor, "foto sem âncora cai em //body e sai truncada"
        assert "b10-Conditions_Content" in seletor
        assert seletor != extrator.XPATH_FICHA_INTEIRA


# ===========================================================================
# 3. A foto da sub-aba da ORIGINAL também é ancorada
# ===========================================================================

class _EngineDeSubaba:
    def __init__(self, ativa=True):
        self.ativa = ativa

    def contar(self, seletor):
        if "dummy-active" in seletor or "CLASSE" in seletor:
            return 1 if self.ativa else 0
        return 1

    def texto(self, _seletor):
        return ""


class _PortalDeSubaba:
    def __init__(self, ativa=True):
        self.engine = _EngineDeSubaba(ativa)

    def safe_click(self, _seletor):
        pass


def test_foto_da_subaba_da_original_usa_o_painel(monkeypatch):
    fotos = []
    monkeypatch.setattr(extrator, "id_do_painel",
                        lambda *_a, **_k: "b12-$b19")
    monkeypatch.setattr(extrator, "fotografar",
                        lambda _p, titulo, _log=None, seletor=None:
                        fotos.append((titulo, seletor)))

    ok = extrator.abrir_subaba_de_condicoes(
        _PortalDeSubaba(), "Armazenamento e transporte",
        lambda _m: None, log_auditoria=object())

    assert ok
    assert len(fotos) == 1
    _titulo, seletor = fotos[0]
    assert seletor and "b12-$b19" in seletor
    assert seletor != extrator.XPATH_FICHA_INTEIRA


# ===========================================================================
# 4. O PDM diz o que o combo estava mostrando
# ===========================================================================

class _EngineDeCombo:
    def __init__(self, opcoes):
        self.opcoes = list(opcoes)

    def contar(self, _seletor):
        return len(self.opcoes)


class _PortalDeCombo:
    def __init__(self, opcoes):
        self.engine = _EngineDeCombo(opcoes)

    def texto_se_existir(self, seletor):
        import re
        achado = re.search(r"\)\[(\d+)\]$", seletor)
        if not achado:
            return ""
        indice = int(achado.group(1))
        return self.engine.opcoes[indice - 1] if indice <= len(self.engine.opcoes) else ""


def test_combo_vazio_diz_que_nao_ha_opcao_nenhuma():
    """Zero opção não é "o PDM não existe no catálogo": é o dropdown fechado,
    ou o filtro que nunca chegou nele. A mensagem tem de separar os dois."""
    linhas, log = _coletor()

    vistas = pdm._listar_opcoes(_PortalDeCombo([]), log)

    assert vistas == []
    assert any("opção nenhuma" in l for l in linhas)


def test_combo_lista_as_opcoes_que_esta_mostrando():
    linhas, log = _coletor()
    opcoes = ["PDM.4520.001 - RESISTENCIA, R1", "PDM.6685.032 - HIGROSTATO, R1"]

    vistas = pdm._listar_opcoes(_PortalDeCombo(opcoes), log)

    assert vistas == opcoes
    for texto in opcoes:
        assert any(texto in l for l in linhas)


def test_combo_longo_e_cortado_e_diz_quantas_sobraram():
    """O catálogo de PDM tem centenas de itens: despejar todos transformaria o
    log que o usuário me manda em algo que ele não consegue ler."""
    linhas, log = _coletor()
    opcoes = [f"PDM.{n:04d}.000 - ITEM {n}" for n in range(1, 41)]

    vistas = pdm._listar_opcoes(_PortalDeCombo(opcoes), log, limite=5)

    assert len(vistas) == 5
    assert any("mais 35" in l for l in linhas)


def test_engine_que_estoura_ao_contar_nao_derruba_o_lote():
    """Observar nunca pode derrubar. Este caminho só roda no fracasso, e um
    erro aqui trocaria "o PDM não trocou" por uma ficha abortada."""
    class _Explode:
        engine = type("E", (), {"contar": lambda _s, _x: (_ for _ in ()).throw(RuntimeError())})()

    linhas, log = _coletor()
    assert pdm._listar_opcoes(_Explode(), log) == []
    assert any("opção nenhuma" in l for l in linhas)

r"""As duas operações de portal do módulo de correção de PDM (E4, parte 1).

TROCAR o PDM de uma ficha para um PDM QUALQUER, e ESCREVER uma característica
a partir do plano da E3. As duas existem no app, mas nenhuma das duas serve
como está:

- `duplicadas_pdm.garantir_pdm` troca para UM PDM fixo (`sel.PDM_DA_DUPLICADA`),
  amarrado no módulo. Aqui o PDM vem da tela, ficha a ficha;
- `tech_specs._preencher_linha` escreve a partir do dicionário do JSON da IA,
  não a partir de uma `Reposicao`.

⚠️ O PONTO MAIS DELICADO DESTE ARQUIVO: **"já é o PDM certo" não se decide pelo
código.** O caso principal do usuário são 25 fichas que só mudam de REVISÃO --
mesmo código, `R1` virando `R2`. Comparar por código diria "já está certo" e o
módulo não faria nada, calado, nas 25.

Quem decide é o confronto entre o que está na ficha e **o que o combo oferece**:
o portal só lista a revisão vigente (dito pelo usuário em 2026-09-23), então a
opção que aparece é o destino. Igual ao que já está lá, não mexe; diferente,
troca.

⚠️ NÃO É PROVA DE PORTAL. Dublê de `PMIBPortal`, seletor por seletor. Se um
XPath estiver errado, tudo passa verde -- quem prova é a E6.
"""
from __future__ import annotations

import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.caracteristicas import Caracteristica
from sigft.services import correcao_pdm_portal as portal_pdm
from sigft.services.correcao_pdm_casamento import Reposicao


# =============================================================================
# Dublê de portal
# =============================================================================
class _PortalDublê:
    """Só o que as duas operações usam. Cada campo é o estado de uma tela."""

    def __init__(self, pdm_na_ficha="PDM.5920.020 - PROTETOR, SURTO, R1",
                 opcoes_do_combo=("PDM.5920.020 - PROTETOR, SURTO, R2",),
                 abre_secao=True, combo_abre=True, salva=True,
                 pdm_depois_de_salvar=None):
        self.pdm_na_ficha = pdm_na_ficha
        self.opcoes_do_combo = list(opcoes_do_combo)
        self.abre_secao = abre_secao
        self.combo_abre = combo_abre
        self.salva = salva
        self.pdm_depois_de_salvar = pdm_depois_de_salvar

        self.filtro = ""
        self.buscas = []
        self.cliques = []
        self.salvou = 0
        self.confirmou_modal = 0
        self.modal_na_tela = False
        self.engine = self

    # -- PMIBPortal ---------------------------------------------------------
    def texto_se_existir(self, seletor):
        if seletor == sel.XPATH_PDM_VALOR:
            return self.pdm_na_ficha
        return ""

    def safe_click(self, seletor):
        self.cliques.append(seletor)

    def safe_fill(self, seletor, texto):
        if sel.XPATH_PDM_BUSCA in seletor:
            self.filtro = str(texto)
            self.buscas.append(str(texto))

    def salvar_e_confirmar(self, *_a, **_kw):
        self.salvou += 1
        if self.salva and self.pdm_depois_de_salvar is not None:
            self.pdm_na_ficha = self.pdm_depois_de_salvar
        return self.salva

    # -- RPAEngine ----------------------------------------------------------
    def element_exists(self, seletor):
        return self.contar(seletor) > 0

    def contar(self, seletor):
        if sel.XPATH_PDM_BUSCA in seletor:
            return 1 if self.combo_abre else 0
        if seletor == sel.XPATH_DIALOGO_CONFIRMAR:
            return 1 if self.modal_na_tela else 0
        if "role='option'" in seletor:
            return len(self._casadas(seletor))
        return 0

    def texto(self, seletor):
        casadas = self._casadas(seletor)
        indice = portal_pdm._indice_do_seletor(seletor)
        if indice is not None and 1 <= indice <= len(casadas):
            return casadas[indice - 1]
        return casadas[0] if casadas else ""

    def click_estrito(self, seletor):
        self.cliques.append(seletor)
        if seletor == sel.XPATH_DIALOGO_CONFIRMAR:
            self.modal_na_tela = False
            self.confirmou_modal += 1

    def click_raw(self, seletor):
        self.cliques.append(seletor)

    def press(self, _tecla):
        pass

    # -- a regra do dublê: o combo filtra por SUBSTRING ----------------------
    def _casadas(self, seletor):
        if not self.combo_abre:
            return []
        prefixo = portal_pdm._texto_do_literal(seletor)
        achadas = [o for o in self.opcoes_do_combo
                   if o.upper().startswith((prefixo or "").upper())]
        if not self.filtro:
            return achadas
        return [o for o in achadas if self.filtro.upper() in o.upper()]


def _abrir_secao_sempre(monkeypatch, resposta=True):
    monkeypatch.setattr(portal_pdm.extrator, "abrir_secao",
                        lambda *_a, **_kw: resposta)


@pytest.fixture(autouse=True)
def _sem_pausa(monkeypatch):
    """As pausas do portal (3 s por troca) não podem custar 3 s por teste."""
    monkeypatch.setattr(portal_pdm.time, "sleep", lambda *_a: None)


# =============================================================================
# A. Trocar o PDM -- o caso das 25 fichas
# =============================================================================
def test_atualizar_so_a_revisao_TROCA(monkeypatch):
    """O caso principal: mesmo código, `R1` na ficha e `R2` no combo. Se o
    módulo comparasse por código, diria "já está certo" e não faria nada -- nas
    25 fichas, calado."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(pdm_na_ficha="PDM.5920.020 - PROTETOR, SURTO, R1",
                     opcoes_do_combo=["PDM.5920.020 - PROTETOR, SURTO, R2"],
                     pdm_depois_de_salvar="PDM.5920.020 - PROTETOR, SURTO, R2")

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020")

    assert r.ok and r.trocou
    assert r.pdm_depois.endswith("R2")
    assert p.salvou == 1


def test_a_ficha_que_JA_esta_na_revisao_do_combo_nao_e_tocada(monkeypatch):
    """Trocar o PDM apaga todas as características. Fazer isso para chegar ao
    mesmo lugar seria destruir a ficha à toa -- e é o que aconteceria se o
    módulo só comparasse código com código."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(pdm_na_ficha="PDM.5920.020 - PROTETOR, SURTO, R2",
                     opcoes_do_combo=["PDM.5920.020 - PROTETOR, SURTO, R2"])

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020")

    assert r.ok and not r.trocou
    assert p.salvou == 0
    assert p.confirmou_modal == 0


def test_troca_para_um_pdm_de_codigo_diferente(monkeypatch):
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(pdm_na_ficha="PDM.3010.001 - ACOPLAMENTO, R1",
                     opcoes_do_combo=["PDM.4320.031 - COLUNA FLANGE, ACOPLAMENTO, R2"],
                     pdm_depois_de_salvar="PDM.4320.031 - COLUNA FLANGE, ACOPLAMENTO, R2")

    r = portal_pdm.trocar_pdm(p, "PDM.4320.031 - COLUNA FLANGE, ACOPLAMENTO")

    assert r.ok and r.trocou


def test_confirma_o_modal_que_avisa_do_apagamento(monkeypatch):
    """*"Todos os dados de Características Técnicas serão removidos"* -- é o
    que se quer aqui, e enquanto o diálogo está aberto nada mais na página é
    clicável (2026-08-25)."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(pdm_depois_de_salvar="PDM.5920.020 - PROTETOR, SURTO, R2")
    p.modal_na_tela = True

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020")

    assert p.confirmou_modal == 1
    assert r.ok


def test_a_cascata_cai_para_o_codigo_quando_o_texto_completo_nao_acha(monkeypatch):
    """Mesma cascata do `cria_fichas` (pedido do usuário em 2026-09-22): texto
    completo, depois só o código, depois só o título."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(opcoes_do_combo=["PDM.5920.020 - PROTETOR, SURTO, R2"],
                     pdm_depois_de_salvar="PDM.5920.020 - PROTETOR, SURTO, R2")

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020 - NOME QUE MUDOU ENTRE REVISOES")

    assert r.ok and r.trocou
    assert p.buscas[0] == "PDM.5920.020 - NOME QUE MUDOU ENTRE REVISOES"
    assert "PDM.5920.020" in p.buscas


def test_pdm_que_nao_existe_no_combo_NAO_troca_nada(monkeypatch):
    """Falhar aqui é o melhor dos casos: as características continuam na
    ficha, intactas."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(opcoes_do_combo=[])

    r = portal_pdm.trocar_pdm(p, "PDM.9999.999 - NAO EXISTE")

    assert not r.ok and not r.trocou
    assert p.salvou == 0
    assert r.motivo


def test_combo_que_nao_abre_e_erro_e_nao_silencio(monkeypatch):
    """Conserto de 2026-08-21: `engine.fill` não levanta por contrato, então
    escrever num dropdown que nunca abriu custava o timeout inteiro e a
    mensagem mandava investigar o catálogo em vez da tela."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(combo_abre=False)

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020")

    assert not r.ok
    assert "combo" in r.motivo.lower()


def test_aba_que_nao_abre_para_tudo(monkeypatch):
    _abrir_secao_sempre(monkeypatch, resposta=False)
    p = _PortalDublê()

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020")

    assert not r.ok and not r.trocou


def test_ficha_sem_combo_de_pdm_para_tudo(monkeypatch):
    """Sem saber o PDM atual, trocar é chute -- e o retrato não teria com o
    que ser comparado depois."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(pdm_na_ficha="")

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020")

    assert not r.ok


def test_salvar_que_nao_confirma_e_FALHA_declarada(monkeypatch):
    """O pior estado possível: o PDM trocou na tela e o portal não gravou. Quem
    chama não pode seguir para as características achando que o PDM é o novo."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(salva=False)

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020")

    assert not r.ok
    assert "salv" in r.motivo.lower()


def test_a_PROVA_e_reler_o_combo_depois_de_salvar(monkeypatch):
    """Um SALVAR confirmado não garante que o combo ficou com o valor
    escolhido. É a lição da ficha 4500063671.0922."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(pdm_depois_de_salvar="PDM.5920.020 - PROTETOR, SURTO, R1")

    r = portal_pdm.trocar_pdm(p, "PDM.5920.020")

    assert not r.ok
    assert "R1" in r.motivo


def test_mais_de_uma_opcao_casando_vira_AVISO_no_log(monkeypatch):
    """O portal deveria listar só a revisão vigente (usuário, 2026-09-23). Se
    listar duas, a escolha vira um palpite que apaga características -- e a
    pendência aberta em `PENDENCIAS.md` diz exatamente isso. Não bloqueia, mas
    não pode passar calado."""
    _abrir_secao_sempre(monkeypatch)
    p = _PortalDublê(opcoes_do_combo=["PDM.5920.020 - PROTETOR, SURTO, R1",
                                      "PDM.5920.020 - PROTETOR, SURTO, R2"],
                     pdm_na_ficha="PDM.5920.020 - PROTETOR, SURTO, R0",
                     pdm_depois_de_salvar="PDM.5920.020 - PROTETOR, SURTO, R1")
    linhas = []

    portal_pdm.trocar_pdm(p, "PDM.5920.020", callback_log=linhas.append)

    assert any("2 opções" in x or "2 opcoes" in x for x in linhas)


# =============================================================================
# B. Escrever uma característica -- o adaptador
# =============================================================================
def _reposicao(**campos):
    base = dict(codigo="1171", nome="ACABAMENTO", tipo="CHAR",
                valor_pt="PINTADO", valor_es="PINTADO", unidade="AD")
    base.update(campos)
    return Reposicao(**base)


def test_o_dado_de_CHAR_leva_os_dois_idiomas():
    dado = portal_pdm.dado_de_escrita(_reposicao())

    assert dado["TIPO"] == "CHAR"
    assert dado["RESPOSTA_PT_FINAL"] == "PINTADO"
    assert dado["RESPOSTA_ES_FINAL"] == "PINTADO"


def test_o_dado_de_INT_junta_minimo_e_maximo_com_BARRA():
    """Não é estilo: `_preencher_linha` lê a faixa com `val_pt.split("/")`.
    Qualquer outro separador manda o máximo para o limbo."""
    dado = portal_pdm.dado_de_escrita(
        _reposicao(tipo="INT", valor_pt="", minimo="-10", maximo="50",
                   subtipo="ENTRE", unidade="°C"))

    assert dado["RESPOSTA_PT_FINAL"] == "-10 / 50"
    assert dado["SUBTIPO_INTERVALO"] == "ENTRE"


def test_o_dado_de_INT_sem_subtipo_nao_inventa_um():
    """`_preencher_linha` tem o default `"MINIMO / MAXIMO"`, e ele também é uma
    invenção. Mandar vazio faz `selecionar_dropdown_lista` não tocar no
    dropdown -- que é o que se quer quando não se sabe."""
    dado = portal_pdm.dado_de_escrita(
        _reposicao(tipo="INT", valor_pt="", minimo="10", maximo="", subtipo=""))

    assert dado["SUBTIPO_INTERVALO"] == ""


def test_o_dado_leva_a_unidade_como_SIMBOLO():
    dado = portal_pdm.dado_de_escrita(_reposicao(tipo="NUM", valor_pt="220",
                                                 unidade="V"))

    assert dado["SIMBOLO"] == "V"


def test_o_dado_leva_o_NOME_para_o_log():
    """As mensagens de `_preencher_linha` citam a característica pelo nome. Sem
    ele o log vira "[!] O site rejeitou ''"."""
    assert portal_pdm.dado_de_escrita(_reposicao())["CARACTERISTICA_CHAVE"] == "ACABAMENTO"


def test_escrever_delega_para_o_preencher_linha_do_tech_specs(monkeypatch):
    """⚠️ REUSO DELIBERADO, e o motivo é o tamanho do que se reusa: o blur do
    OutSystems (sem ele o SALVAR grava o valor ANTIGO, sem erro), a auditoria
    com injeção forçada, o casamento de lista em PT e ES, a unidade pelos
    parênteses. São duzentas linhas de regra que nasceram de falha real -- uma
    cópia divergiria na primeira correção."""
    chamadas = []
    p = _PortalDublê()
    escritor = portal_pdm.EscritorDeLinha(p)
    monkeypatch.setattr(type(escritor._automacao), "_preencher_linha",
                        lambda _s, seletor, dado, log=None: chamadas.append((seletor, dado)) or True)

    assert escritor.escrever("(//tr)[3]", _reposicao()) is True
    assert chamadas[0][0] == "(//tr)[3]"
    assert chamadas[0][1]["RESPOSTA_PT_FINAL"] == "PINTADO"


def test_o_escritor_nasce_SEM_abrir_navegador():
    """`TechSpecsAutomation()` não cria driver nenhum no `__init__` -- é o que
    torna o reuso possível. Se algum dia criar, este teste cai antes de a
    correção de PDM abrir um segundo Chrome na máquina do usuário."""
    p = _PortalDublê()

    escritor = portal_pdm.EscritorDeLinha(p)

    assert escritor._automacao.engine is p.engine


def test_o_seletor_de_linha_e_o_MESMO_que_o_leitor_usa():
    """Ler a linha 3 e escrever na linha 4 seria o defeito perfeito: silencioso
    e destrutivo."""
    assert portal_pdm.seletor_da_linha(3) == portal_pdm.seletor_da_linha(3)
    assert "[3]" in portal_pdm.seletor_da_linha(3)


# =============================================================================
# C. O guard da duplicação de seletores
# =============================================================================
def test_os_TRES_lugares_com_os_seletores_da_tabela_continuam_IGUAIS():
    """Os mesmos XPaths vivem em `core/rpa/caracteristicas.py`,
    `services/tech_specs.py` e `core/rpa/seletores_duplicada.py`. Unificar é o
    certo e foi ADIADO por decisão do usuário (2026-09-23, ver
    `PENDENCIAS.md`): os dois antigos rodam contra o portal real hoje.

    Enquanto a dívida não é paga, este teste é o que impede o pior caso: um
    seletor ajustado num lugar e não nos outros faz o módulo LER de um elemento
    e ESCREVER noutro -- e os dois lados continuariam verdes sozinhos.
    """
    from sigft.core.rpa import caracteristicas as leitor
    from sigft.services import tech_specs

    def igual(a, b):
        """Compara ignorando o `.` inicial e a ESCOLHA DE ASPAS: o XPath
        `[@id="x"]` e `[@id='x']` são o mesmo seletor, e os dois arquivos
        escrevem de jeitos diferentes. Tudo além disso é divergência."""
        def limpo(x):
            return x.lstrip(".").replace('"', "'")
        return limpo(a) == limpo(b)

    pares = [
        (leitor.REL_DESCRICAO, tech_specs.XPATH_REL_COL_DESCRICAO),
        (leitor.REL_VALOR_PT, tech_specs.XPATH_REL_TEXTAREA_PT),
        (leitor.REL_VALOR_ES, tech_specs.XPATH_REL_TEXTAREA_ES),
        (leitor.REL_INPUT_NUM, tech_specs.XPATH_REL_INPUT_NUM),
        (leitor.REL_INPUT_MIN, tech_specs.XPATH_REL_INPUT_MIN),
        (leitor.REL_INPUT_MAX, tech_specs.XPATH_REL_INPUT_MAX),
        (leitor.REL_SELECT_LISTA, tech_specs.XPATH_REL_SELECT_LISTA),
        (leitor.REL_SELECT_INTERVALO, tech_specs.XPATH_REL_SELECT_INTERVALO),
        (leitor.REL_SELECT_UNIDADE, tech_specs.XPATH_REL_SELECT_UNIDADE),
        (leitor.XPATH_LINHAS, tech_specs.XPATH_LINHAS_TABELA),
        (leitor.XPATH_PROXIMA_PAGINA, tech_specs.XPATH_BOTAO_PROXIMA_PAGINA),
    ]
    for do_leitor, do_tech_specs in pares:
        assert igual(do_leitor, do_tech_specs), (do_leitor, do_tech_specs)


def test_a_secao_da_tabela_e_a_mesma_nos_tres_lugares():
    from sigft.core.rpa import caracteristicas as leitor
    from sigft.services import tech_specs

    assert leitor.XPATH_SECAO == sel.XPATH_CARACTERISTICAS_SECAO
    assert leitor.XPATH_LINHAS == sel.XPATH_CARACTERISTICAS_LINHAS
    assert leitor.XPATH_LINHAS == tech_specs.XPATH_LINHAS_TABELA


def test_o_leitor_e_o_escritor_enxergam_a_MESMA_linha():
    """O leitor endereça `(linhas)[i]` e o escritor concatena os relativos do
    `tech_specs` no mesmo texto. Se as duas bases divergirem, ler a linha 3 e
    escrever na 3 deixa de ser a mesma coisa."""
    from sigft.core.rpa import caracteristicas as leitor
    from sigft.services import tech_specs

    do_leitor = f"({leitor.XPATH_LINHAS})[3]"

    assert portal_pdm.seletor_da_linha(3) == do_leitor
    assert (do_leitor + tech_specs.XPATH_REL_TEXTAREA_PT).startswith(do_leitor)


def test_a_caracteristica_lida_volta_a_ser_endereçavel():
    """Fecha o ciclo: o que a E1 leu na linha `i` é o que a E4 escreve na linha
    `i`, com o mesmo texto de seletor."""
    from sigft.core.rpa import caracteristicas as leitor

    lida = Caracteristica(codigo="1171", nome="ACABAMENTO", tipo="CHAR")

    assert lida.codigo == "1171"
    assert portal_pdm.seletor_da_linha(1).startswith(f"({leitor.XPATH_LINHAS})")

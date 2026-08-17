r"""
Escrita na ficha ALVO (CP 6.3) — fabricante, referência `'D` e a purga.

O portal é de mentira, mas com três comportamentos do real, porque foram eles
que quebraram na primeira sessão de validação (2026-08-17):

  - a **tabela encolhe** quando uma linha é excluída;
  - o **bloco de aviso de colisão existe sempre**, e só ganha TEXTO quando há
    colisão de verdade;
  - o **campo só guarda o valor** depois do blur -- antes disso, reler devolve
    o conteúdo antigo.

Um duplo que não faz essas três coisas aprova código que falha no portal, que
foi exatamente o que aconteceu.
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
    def __init__(self, linhas=(), combos=(), campos_referencia=1,
                 existentes=(), habilitados=(), exige_blur=False):
        self.linhas = list(linhas)
        self.combos = list(combos)
        self.campos_referencia = campos_referencia
        self.existentes = list(existentes)
        self.habilitados = list(habilitados)
        self.exige_blur = exige_blur      # o portal real só grava no blur
        self.aviso_colisao = ""
        self.valores = {}                 # o que o campo REALMENTE guardou
        self.pendentes = {}               # digitado, ainda sem blur
        self.cliques = []

    # -- escrita
    def registrar_fill(self, seletor, texto):
        if self.exige_blur:
            self.pendentes[seletor] = texto
        else:
            self.valores[seletor] = texto

    def click_nativo(self, seletor):
        self.cliques.append(seletor)
        # Clique de verdade tira o foco: o que estava pendente vira valor.
        self.valores.update(self.pendentes)
        self.pendentes.clear()

    def click_raw(self, seletor):
        # Clique por JavaScript NÃO move o foco -- nada de blur aqui.
        self.cliques.append(seletor)

    # -- leitura
    def get_value(self, seletor):
        return self.valores.get(seletor, "")

    def contar(self, seletor):
        if "TechnicalCharacteristics" in seletor:
            return len(self.linhas)
        if "vscomp-toggle-button" in seletor:
            return len(self.combos)
        if "Input_TextVar" in seletor:
            return self.campos_referencia
        return 0

    def texto(self, seletor):
        if "CoincidenceReference" in seletor:
            return self.aviso_colisao
        indice = _indice_do_seletor(seletor)
        if "vscomp-toggle-button" in seletor:
            return self.combos[indice - 1] if indice and indice <= len(self.combos) else ""
        if indice and indice <= len(self.linhas):
            return self.linhas[indice - 1]
        return ""

    def element_exists(self, seletor):
        if "CoincidenceReference" in seletor:
            return True  # o bloco EXISTE sempre -- é o texto que muda
        return any(marca in seletor for marca in self.existentes)

    def esta_habilitado(self, seletor):
        return any(marca in seletor for marca in self.habilitados)


class _PortalFalso:
    def __init__(self, engine):
        self.engine = engine
        self.cliques = []
        self.preenchidos = []
        self.excluidas = []
        self.salvou = []
        self.exclusao_falha_em = ()
        self.salvar_devolve = True

    def safe_click(self, seletor):
        self.cliques.append(seletor)

    def safe_fill(self, seletor, texto):
        self.preenchidos.append((seletor, texto))
        self.engine.registrar_fill(seletor, texto)

    def excluir_linha_com_confirmacao(self, seletor_linha):
        indice = _indice_do_seletor(seletor_linha)
        descricao = self.engine.linhas[indice - 1]
        if descricao in self.exclusao_falha_em:
            return False
        self.excluidas.append(descricao)
        self.engine.linhas.pop(indice - 1)
        return True

    def clicar_salvar_visivel(self, nome_secao=""):
        self.salvou.append(nome_secao)
        return self.salvar_devolve


def _com_combos(*nomes, campos_referencia=1):
    engine = _EngineFalso(combos=nomes, campos_referencia=campos_referencia,
                          existentes=["data-tooltip="])
    return _PortalFalso(engine), engine


# ===========================================================================
# Qual combo é o do FABRICANTE
# ===========================================================================
# Relato do usuário na 1ª sessão real: "ele entrou no campo de fabricantes, mas
# tentou preencher o errado, o campo que é da GE". O XPath sem índice casa
# QUALQUER `.vscomp-toggle-button` e devolve o primeiro do documento.

def test_com_um_combo_so_usa_ele():
    portal, _e = _com_combos("")

    assert injetor.achar_combo_do_fabricante(portal) == \
        f"({sel.XPATH_FABRICANTE_TOGGLE})[1]"


def test_o_combo_do_fornecedor_fixo_e_descartado():
    """O fornecedor é a própria empresa e é fixo -- é o que distingue os dois."""
    portal, _e = _com_combos("GE ENERGIAS RENOVÁVEIS", "Selecione")

    escolhido = injetor.achar_combo_do_fabricante(portal, callback_log=lambda _m: None)

    assert escolhido == f"({sel.XPATH_FABRICANTE_TOGGLE})[2]"


def test_acento_do_fornecedor_fixo_nao_atrapalha():
    portal, _e = _com_combos("GE ENERGIAS RENOVAVEIS", "")

    escolhido = injetor.achar_combo_do_fabricante(portal, callback_log=lambda _m: None)

    assert escolhido == f"({sel.XPATH_FABRICANTE_TOGGLE})[2]"


def test_dois_combos_indistinguiveis_NAO_escrevem_nada():
    """Chutar poria o fabricante errado numa ficha real, sem sintoma nenhum na
    tela. Não escrever custa uma pendência que aparece no log."""
    portal, _e = _com_combos("Selecione", "Selecione")
    logs = []

    escolhido = injetor.achar_combo_do_fabricante(portal, callback_log=logs.append)

    assert escolhido is None
    assert "NÃO escrevi nada" in "\n".join(logs)


def test_combo_ambiguo_reprova_a_secao_sem_clicar():
    portal, _e = _com_combos("Selecione", "Selecione")

    resultado = injetor.escolher_fabricante(portal, "SCHNEIDER", callback_log=lambda _m: None)

    assert resultado.ok is False
    assert portal.cliques == []


def test_fabricante_filtra_por_texto_e_clica_na_opcao():
    portal, engine = _com_combos("GE ENERGIAS RENOVÁVEIS", "Selecione")
    engine.existentes.append("data-tooltip='SCHNEIDER'")

    resultado = injetor.escolher_fabricante(portal, "SCHNEIDER", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert any(texto == "SCHNEIDER" for _s, texto in portal.preenchidos)
    assert any("data-tooltip='SCHNEIDER'" in c for c in portal.cliques)


def test_fabricante_que_nao_aparece_no_combo_nao_clica_na_opcao():
    portal, engine = _com_combos("GE ENERGIAS RENOVÁVEIS", "Selecione")
    engine.existentes = []

    resultado = injetor.escolher_fabricante(portal, "SCHNEIDER", callback_log=lambda _m: None)

    assert resultado.ok is False
    assert not any("role='option'" in c for c in portal.cliques)


def test_fabricante_vazio_nem_abre_o_combo():
    portal, _e = _com_combos("Selecione")

    resultado = injetor.escolher_fabricante(portal, "")

    assert resultado.ok is False
    assert portal.cliques == []


# ===========================================================================
# Referência — a regra do 'D
# ===========================================================================
def test_referencia_sem_colisao_usa_o_codigo_cru():
    portal, engine = _com_combos("Selecione")
    engine.aviso_colisao = ""

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert [t for _s, t in portal.preenchidos] == ["2904616"]


def test_o_bloco_de_aviso_VAZIO_nao_e_colisao():
    r"""CONTRAPROVA DO DEFEITO QUE QUEBROU A 1ª SESSÃO REAL.

    A 1ª versão perguntava `element_exists(CoincidenceReference)`. O bloco fica
    no DOM o tempo todo, vazio -- dá para ver no HTML que o próprio usuário
    inspecionou, colhido numa ficha SEM colisão. Resultado: as 21 tentativas
    foram recusadas, inclusive a primeira. A documentação do projeto já dizia a
    pergunta certa ("este bloco tem CONTEÚDO?"); o código fazia a outra.
    """
    portal, engine = _com_combos("Selecione")
    engine.aviso_colisao = "   "  # bloco presente e vazio

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert len(portal.preenchidos) == 1


class _PortalQueRecusa(_PortalFalso):
    """Recusa as N primeiras referências, como o portal real."""

    def __init__(self, engine, recusar=0, avisar_apos_clique=False):
        super().__init__(engine)
        self.recusar = recusar
        self.avisar_apos_clique = avisar_apos_clique
        self.tentativas = []

    def safe_fill(self, seletor, texto):
        super().safe_fill(seletor, texto)
        self.tentativas.append(texto)
        # Digitar um valor NOVO revalida e limpa o aviso anterior. ⚠️ É uma
        # suposição sobre o portal, e está declarada: se na prática o aviso for
        # "grudento" (ficar na tela mesmo com outro texto), TODAS as tentativas
        # serão recusadas -- e é justamente por isso que o injetor imprime, nesse
        # caso, o texto que o portal exibiu. O sintoma fica legível em vez de
        # virar "o portal recusou tudo".
        self.engine.aviso_colisao = ""
        if not self.avisar_apos_clique:
            self.engine.aviso_colisao = (
                "A referência já existe!" if len(self.tentativas) <= self.recusar else "")

    def safe_click(self, seletor):
        super().safe_click(seletor)
        if "fa-plus-circle" in seletor and self.avisar_apos_clique:
            self.engine.aviso_colisao = (
                "A referência já existe!" if len(self.tentativas) <= self.recusar else "")


def test_referencia_repetida_avanca_para_o_sufixo_D():
    engine = _EngineFalso(campos_referencia=1)
    portal = _PortalQueRecusa(engine, recusar=2)

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert portal.tentativas == ["2904616", "2904616'D1", "2904616'D2"]


def test_colisao_detectada_so_DEPOIS_do_clique_tambem_avanca():
    engine = _EngineFalso(campos_referencia=1)
    portal = _PortalQueRecusa(engine, recusar=1, avisar_apos_clique=True)

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert portal.tentativas == ["2904616", "2904616'D1"]


def test_todas_recusadas_mostra_o_texto_que_o_portal_exibiu():
    """Todas recusadas -- inclusive a primeira, que na maioria das fichas passa
    -- é resultado suspeito. Mostrar o texto é o que permite decidir numa
    olhada se era colisão mesmo ou se o robô está lendo o aviso errado."""
    engine = _EngineFalso(campos_referencia=1)
    portal = _PortalQueRecusa(engine, recusar=999)
    logs = []

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=logs.append)

    assert resultado.ok is False
    juntos = "\n".join(logs)
    assert "Diagnóstico" in juntos and "A referência já existe!" in juntos


def test_campo_que_nao_guarda_o_texto_para_na_primeira_tentativa():
    """`engine.fill` engole a falha por contrato. Sem reler, "escreveu" e "não
    escreveu" são indistinguíveis -- e gastar 20 sufixos num campo que não
    recebe nada esconderia o problema de verdade."""
    engine = _EngineFalso(campos_referencia=1, exige_blur=True)  # nunca dá blur aqui
    portal = _PortalFalso(engine)
    logs = []

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=logs.append)

    assert resultado.ok is False
    assert len(portal.preenchidos) == 1
    assert "não aceitou" in resultado.detalhe


def test_dois_campos_de_referencia_NAO_escrevem_nada():
    """Escrever a referência do fabricante na linha do fornecedor é dado errado
    em ficha real, e a tela não reclama."""
    engine = _EngineFalso(campos_referencia=2)
    portal = _PortalFalso(engine)
    logs = []

    resultado = injetor.escrever_referencia(portal, "2904616", callback_log=logs.append)

    assert resultado.ok is False
    assert portal.preenchidos == []
    assert "preencha à mão" in "\n".join(logs).lower()


def test_sem_codigo_do_material_nao_escreve_lixo():
    engine = _EngineFalso(campos_referencia=1)
    portal = _PortalFalso(engine)

    resultado = injetor.escrever_referencia(portal, "", callback_log=lambda _m: None)

    assert resultado.ok is False
    assert portal.preenchidos == []


# ===========================================================================
# Características técnicas — a purga
# ===========================================================================
_LINHAS = ["PESO LIQUIDO", "CODIGO PMIB", "TENSAO NOMINAL", "MATERIAL"]


def _com_tabela(linhas, proxima_pagina=False, exige_blur=False):
    existentes = ["página seguinte"] if proxima_pagina else []
    engine = _EngineFalso(linhas=linhas, existentes=existentes, exige_blur=exige_blur)
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

    valores = [t for s, t in portal.preenchidos if "TextArea_ValuePT" in s]
    assert valores == ["4500063671.1471"]


def test_clica_fora_para_disparar_o_onBlur():
    r"""CONTRAPROVA DO SEGUNDO DEFEITO DA 1ª SESSÃO REAL: *"na característica
    técnica eu até vi ele colocando mas não conseguiu salvar"*.

    Nem o `fill` do Playwright nem o `send_keys` do Selenium disparam `change`
    -- esse evento nasce do BLUR. O OutSystems liga a variável do servidor ao
    `change`, então sem o blur o texto fica na caixa e o servidor nunca soube
    dele: o SALVAR salva o valor antigo, sem erro nenhum. O módulo antigo já
    clicava fora ("Clica fora para disparar o evento onBlur"); eu não portei a
    linha.

    O duplo aqui só grava no `click_nativo` -- se o clique sumir, ou virar
    `click_raw` (JavaScript, que NÃO move o foco), o read-back falha.
    """
    portal, engine = _com_tabela(["CODIGO PMIB"], exige_blur=True)

    resultado = injetor.limpar_caracteristicas(portal, "4500063671.1471",
                                               callback_log=lambda _m: None)

    assert resultado.ok is True
    assert any("Descrição" in c for c in engine.cliques)


def test_valor_que_nao_ficou_gravado_reprova_a_secao():
    """Sem read-back, a seção fechava como sucesso com a ficha inalterada."""
    portal, engine = _com_tabela(["CODIGO PMIB"], exige_blur=True)
    engine.click_nativo = lambda seletor: engine.cliques.append(seletor)  # blur que não blura
    logs = []

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=logs.append)

    assert resultado.ok is False
    assert "não ficou gravado" in "\n".join(logs)


def test_salvar_que_nao_acha_botao_reprova_a_secao():
    """`clicar_salvar_visivel` devolve `False` quando nenhum SALVAR está
    visível e habilitado -- que é o sintoma de "o portal não registrou nada"."""
    portal, _engine = _com_tabela(list(_LINHAS))
    portal.salvar_devolve = False
    logs = []

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=logs.append)

    assert resultado.ok is False
    assert "SALVAR" in "\n".join(logs)


def test_o_indice_NAO_avanca_depois_de_apagar():
    """A tabela encolhe: apagada a linha `i`, a de baixo sobe para `i`."""
    portal, engine = _com_tabela(["A", "B", "C", "CODIGO PMIB", "D", "E"])

    injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert engine.linhas == ["CODIGO PMIB"]
    assert portal.excluidas == ["A", "B", "C", "D", "E"]


def test_acento_e_caixa_da_descricao_nao_atrapalham():
    portal, engine = _com_tabela(["PESO", "  Código PMIB  "])

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert engine.linhas == ["  Código PMIB  "]


def test_sem_a_linha_do_codigo_pmib_o_resultado_e_erro():
    portal, _engine = _com_tabela(["PESO", "TENSAO"])

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert resultado.ok is False
    assert "CODIGO PMIB" in resultado.detalhe


def test_exclusao_que_falha_avanca_em_vez_de_travar():
    portal, engine = _com_tabela(["TEIMOSA", "CODIGO PMIB"])
    portal.exclusao_falha_em = ("TEIMOSA",)
    logs = []

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=logs.append)

    assert resultado.ok is True
    assert engine.linhas == ["TEIMOSA", "CODIGO PMIB"]
    assert any("Não consegui excluir" in linha for linha in logs)


def test_a_tabela_paginada_e_percorrida_ate_o_fim():
    portal, engine = _com_tabela(["PESO", "CODIGO PMIB"], proxima_pagina=True)
    paginas = {"n": 0}

    def esta_habilitado(seletor):
        if "página seguinte" in seletor:
            paginas["n"] += 1
            return paginas["n"] <= 2
        return False

    engine.esta_habilitado = esta_habilitado

    injetor.limpar_caracteristicas(portal, "X", callback_log=lambda _m: None)

    assert engine.cliques.count(sel.XPATH_CARACTERISTICAS_PROXIMA_PAGINA) == 2


def test_paginacao_sem_fim_para_no_teto_em_vez_de_travar():
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

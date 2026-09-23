r"""O SERVIÇO de correção de PDM (E4, parte 2) — a ordem e as recusas.

O que este arquivo testa **não é a mecânica do portal** (isso é da E1 e da
E4a): é a ORDEM dos passos e as recusas. Cada uma delas existe para impedir que
uma ficha fique **pior do que estava**, e as três do plano são:

1. **não trocar o PDM se o retrato não gravou** — sem rede, não salta. Depois
   do CONFIRMAR o dado não existe mais em lugar nenhum;
2. **apagar só DEPOIS de repor** — apagar antes eliminaria as linhas que iam
   receber valor;
3. **não apagar nada se a reposição falhou** — melhor uma ficha com linhas
   vazias do que uma ficha sem as linhas.

E uma quarta, que saiu da `PENDENCIAS.md` da E3:

4. **não apagar nada quando o retrato tinha valores e nenhum voltou.** Isso não
   é uma ficha sem nada a reaproveitar: é o sintoma de uma leitura quebrada, e
   nesse estado apagar as "vazias" apagaria a ficha inteira.

⚠️ NÃO É PROVA DE PORTAL. Os colaboradores (ler a tabela, trocar o PDM, gravar
o retrato, escrever a linha) são substituídos por dublês. Quem prova que os
seletores estão certos é a E6.
"""
from __future__ import annotations

import pytest

from sigft.core.rpa.caracteristicas import Caracteristica
from sigft.services import correcao_pdm as servico
from sigft.services.correcao_pdm_portal import ResultadoDaTroca


# =============================================================================
# Dublês
# =============================================================================
class _EngineDeLinhas:
    """Uma tabela de uma página só. Apagar REMOVE de verdade -- é o que faz o
    laço de exclusão terminar, e o serviço confere isso."""

    def __init__(self, linhas, apagar_de_verdade=True):
        self.linhas = list(linhas)
        self.apagar_de_verdade = apagar_de_verdade

    def contar(self, _seletor):
        return len(self.linhas)

    def element_exists(self, _seletor):
        return False   # uma página só

    def esta_habilitado(self, _seletor):
        return False

    def click_raw(self, _seletor):
        pass

    def remover(self, indice):
        if self.apagar_de_verdade and 1 <= indice <= len(self.linhas):
            self.linhas.pop(indice - 1)


class _PortalBobo:
    """Só o que o serviço pede diretamente ao portal."""

    def __init__(self, abre=True, salva=True, linhas=(), apagar_de_verdade=True):
        self.abre = abre
        self.salva = salva
        self.salvou = 0
        self.excluidos = []
        self.engine = _EngineDeLinhas(linhas, apagar_de_verdade)

    def pesquisar_e_abrir(self, _pmib, **_kw):
        return self.abre

    def safe_click(self, _seletor):
        pass

    def texto_se_existir(self, _seletor):
        return "PDM.5920.020 - PROTETOR, SURTO, R1"

    def salvar_e_confirmar(self, *_a, **_kw):
        self.salvou += 1
        return self.salva

    def excluir_linha_com_confirmacao(self, seletor):
        self.excluidos.append(seletor)
        indice = int(seletor.split("[")[-1].rstrip("]"))
        self.engine.remover(indice)
        return True


class _Bancada:
    """Substitui os quatro colaboradores e registra a ORDEM das chamadas.

    A ordem é o objeto do teste: "gravou o retrato antes de trocar" só se
    verifica olhando a sequência, não os efeitos.
    """

    def __init__(self, antigas=(), novas=(), troca=None, grava=True,
                 escreve=True, so_novas=False):
        # `so_novas`: o modo "so repor" le a tabela UMA vez, e o que ele le ja
        # e a tabela nova. Sem isso o dubl devolveria `antigas` na unica
        # leitura e o teste mediria outra coisa.
        self.so_novas = so_novas
        self.antigas = list(antigas)
        self.novas = list(novas)
        self.troca = troca or ResultadoDaTroca(True, True, "R1", "R2")
        self.grava = grava
        self.escreve = escreve

        self.passos = []
        self.escritas = []
        self.leituras = 0

    def instalar(self, monkeypatch):
        monkeypatch.setattr(servico, "ler_tabela", self._ler_tabela)
        monkeypatch.setattr(servico.operacoes, "trocar_pdm", self._trocar)
        monkeypatch.setattr(servico.retrato, "gravar", self._gravar)
        monkeypatch.setattr(servico, "EscritorDeLinha", lambda _p: self)
        monkeypatch.setattr(servico, "ler_linha", self._ler_linha)
        return self

    # -- colaboradores ------------------------------------------------------
    def _ler_tabela(self, _engine):
        self.passos.append("ler")
        self.leituras += 1
        if self.so_novas or self.leituras > 1:
            return list(self.novas)
        return list(self.antigas)

    def _trocar(self, _portal, _pdm, callback_log=None):
        self.passos.append("trocar")
        return self.troca

    def _gravar(self, retrato):
        self.passos.append("gravar")
        if not self.grava:
            raise OSError("disco cheio")
        return f"/retratos/{retrato.pmib}.json"

    def escrever(self, seletor, reposicao, callback_log=None):
        self.passos.append("escrever")
        self.escritas.append((seletor, reposicao))
        return self.escreve

    def _ler_linha(self, engine, seletor):
        indice = int(seletor.split("[")[-1].rstrip("]"))
        linhas = list(getattr(engine, "linhas", self.novas))
        return linhas[indice - 1] if 1 <= indice <= len(linhas) else linhas[0]

    # -- o portal que enxerga a MESMA tabela nova ---------------------------
    def portal(self, **campos):
        return _PortalBobo(linhas=self.novas, **campos)


def _char(codigo="1171", nome="ACABAMENTO", pt="PINTADO", es="PINTADO"):
    return Caracteristica(codigo=codigo, nome=nome, tipo="CHAR", valor_pt=pt,
                          valor_es=es, unidade="AD")


def _vazia(codigo="1171", nome="ACABAMENTO", tipo="CHAR"):
    return Caracteristica(codigo=codigo, nome=nome, tipo=tipo)


@pytest.fixture(autouse=True)
def _sem_pausa(monkeypatch):
    monkeypatch.setattr(servico.time, "sleep", lambda *_a: None)


# =============================================================================
# A. As quatro recusas
# =============================================================================
def test_o_retrato_e_gravado_ANTES_de_trocar(monkeypatch):
    """Depois do CONFIRMAR o dado não existe mais em lugar nenhum: nem no
    portal, nem na planilha, nem na ficha."""
    b = _Bancada(antigas=[_char()], novas=[_vazia()]).instalar(monkeypatch)

    servico.corrigir_ficha(b.portal(), "4500063671.0242", "PDM.5920.020")

    assert b.passos.index("gravar") < b.passos.index("trocar")


def test_retrato_que_NAO_grava_impede_a_troca(monkeypatch):
    """Sem rede, não salta. Uma gravação que falhou é autorização negada para
    destruir o original -- e é por isso que `gravar` levanta em vez de calar."""
    b = _Bancada(antigas=[_char()], novas=[_vazia()], grava=False).instalar(monkeypatch)
    p = b.portal()

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert "trocar" not in b.passos
    assert not r.ok and r.etapa == "retrato"
    assert p.excluidos == []


def test_troca_que_falha_nao_repoe_nem_apaga(monkeypatch):
    b = _Bancada(antigas=[_char()], novas=[_vazia()],
                 troca=ResultadoDaTroca(False, False, motivo="nao esta no combo")
                 ).instalar(monkeypatch)
    p = b.portal()

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.9999.999")

    assert "escrever" not in b.passos
    assert p.excluidos == []
    assert not r.ok and r.etapa == "troca"


def test_apagar_acontece_SO_DEPOIS_de_repor(monkeypatch):
    """Apagar antes eliminaria justamente as linhas que iam receber valor."""
    b = _Bancada(antigas=[_char()],
                 novas=[_vazia(), _vazia("9999", "SOBRANDO", "NUM")]
                 ).instalar(monkeypatch)
    p = b.portal()

    servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert "escrever" in b.passos
    assert p.excluidos, "nada foi apagado"
    assert b.passos.index("escrever") < len(b.passos)


def test_reposicao_que_FALHA_nao_apaga_nada(monkeypatch):
    """Melhor uma ficha com linhas vazias do que uma ficha sem as linhas: o
    que está vazio a pessoa preenche, o que sumiu ela tem que redescobrir."""
    b = _Bancada(antigas=[_char()],
                 novas=[_vazia(), _vazia("9999", "SOBRANDO", "NUM")],
                 escreve=False).instalar(monkeypatch)
    p = b.portal()

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert p.excluidos == []
    assert not r.ok
    assert r.falhas


def test_leitura_quebrada_NAO_apaga_a_ficha_inteira(monkeypatch):
    """O retrato tinha valor e NENHUM voltou. Isso não é "não havia o que
    reaproveitar": é o sintoma de uma leitura quebrada (descrições sem o
    `<código>-<NOME>`, tabela que não carregou). Nesse estado, apagar as
    "vazias" apagaria a ficha inteira.

    Registrado em `PENDENCIAS.md` em 2026-09-23, junto com a decisão de NÃO
    casar por nome quando só um dos lados perdeu o código.
    """
    b = _Bancada(antigas=[_char("1171"), _char("1230", "OUTRA")],
                 novas=[_vazia("7777", "NADA A VER"), _vazia("8888", "IDEM")]
                 ).instalar(monkeypatch)
    p = b.portal()

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert p.excluidos == []
    assert not r.ok and r.etapa == "casamento"
    assert "nenhuma" in r.motivo.lower() or "leitura" in r.motivo.lower()


def test_ficha_que_nao_tinha_nada_a_reaproveitar_segue_normal(monkeypatch):
    """O oposto do teste acima, e o que impede a recusa de virar um bloqueio
    cego: retrato vazio E plano vazio é uma ficha em branco, não um defeito."""
    b = _Bancada(antigas=[_vazia()], novas=[_vazia("9999", "NOVA", "NUM")]
                 ).instalar(monkeypatch)
    p = b.portal()

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert r.ok
    assert p.excluidos


# =============================================================================
# B. A ficha que já estava certa
# =============================================================================
def test_ficha_ja_na_revisao_vigente_nao_e_tocada(monkeypatch):
    """`trocar_pdm` devolve `ok=True, trocou=False`. Não há nada a repor (as
    características nunca foram apagadas) e nada a apagar."""
    b = _Bancada(antigas=[_char()], novas=[_char()],
                 troca=ResultadoDaTroca(True, False, "R2", "R2")
                 ).instalar(monkeypatch)
    p = b.portal()

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert r.ok and not r.trocou
    assert "escrever" not in b.passos
    assert p.excluidos == []


def test_ficha_ja_certa_nao_gasta_uma_segunda_leitura(monkeypatch):
    """Ler a tabela de novo custa uma varredura paginada inteira por nada."""
    b = _Bancada(antigas=[_char()], novas=[_char()],
                 troca=ResultadoDaTroca(True, False)).instalar(monkeypatch)

    servico.corrigir_ficha(b.portal(), "4500063671.0242", "PDM.5920.020")

    assert b.leituras == 1


# =============================================================================
# C. O caminho feliz
# =============================================================================
def test_repoe_o_que_casou_e_relata_o_que_nao_voltou(monkeypatch):
    b = _Bancada(
        antigas=[_char("1171", "ACABAMENTO", "PINTADO"),
                 _char("1900", "SO NO VELHO", "SE PERDE")],
        novas=[_vazia("1171", "ACABAMENTO"), _vazia("2600", "SO NO NOVO", "NUM")],
    ).instalar(monkeypatch)

    r = servico.corrigir_ficha(b.portal(), "4500063671.0242", "PDM.5920.020")

    assert r.ok
    assert r.repostas == 1
    assert [p.codigo for p in r.nao_voltaram] == ["1900"]


def test_a_conversao_de_tipo_entra_na_conta_separada(monkeypatch):
    """O usuário precisa ver quais linhas mudaram de forma: são as que ele vai
    querer conferir com os olhos."""
    b = _Bancada(
        antigas=[Caracteristica(codigo="1230", nome="TENSAO", tipo="NUM",
                                valor_pt="220", unidade="V")],
        novas=[_vazia("1230", "TENSAO", "CHAR")],
    ).instalar(monkeypatch)

    r = servico.corrigir_ficha(b.portal(), "4500063671.0242", "PDM.5920.020")

    assert r.convertidas == 1
    assert b.escritas[0][1].valor_pt == "220 V"


def test_apaga_as_que_ficaram_em_branco_e_as_LISTA(monkeypatch):
    """Requisito 6 do usuário: *"apagar todas as características que ficaram
    em branco e se possível colocar num relatório todas as que ficaram em
    branco de cada ficha"*."""
    b = _Bancada(antigas=[_char()],
                 novas=[_vazia(), _vazia("9999", "SOBRANDO", "NUM")]
                 ).instalar(monkeypatch)
    p = b.portal()

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert r.apagadas == 1
    assert "SOBRANDO" in " ".join(r.em_branco)
    assert len(p.excluidos) == 1


def test_apagar_desligado_relata_sem_apagar(monkeypatch):
    """A lista continua saindo: o relatório é o requisito, apagar é a ação."""
    b = _Bancada(antigas=[_char()],
                 novas=[_vazia(), _vazia("9999", "SOBRANDO", "NUM")]
                 ).instalar(monkeypatch)
    p = b.portal()

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020",
                               apagar_vazias=False)

    assert r.apagadas == 0
    assert "SOBRANDO" in " ".join(r.em_branco)
    assert p.excluidos == []


def test_o_caminho_do_retrato_volta_no_resultado(monkeypatch):
    """É o que a pessoa abre quando quer conferir o que a ficha tinha antes --
    e o que o modo "só repor" recebe."""
    b = _Bancada(antigas=[_char()], novas=[_vazia()]).instalar(monkeypatch)

    r = servico.corrigir_ficha(b.portal(), "4500063671.0242", "PDM.5920.020")

    assert r.retrato.endswith(".json")


def test_ficha_que_nao_abre_para_antes_de_tudo(monkeypatch):
    b = _Bancada(antigas=[_char()], novas=[_vazia()]).instalar(monkeypatch)

    r = servico.corrigir_ficha(b.portal(abre=False), "4500063671.0242",
                               "PDM.5920.020")

    assert not r.ok and r.etapa == "abrir"
    assert b.passos == []


# =============================================================================
# D. A pausa antes de salvar -- o costume do `tech_specs`
# =============================================================================
def test_pausa_antes_de_salvar_quando_a_tela_pede(monkeypatch):
    """`tech_specs` NÃO salva sozinho: ele preenche e pausa para a pessoa
    conferir. Aqui a política é da tela, e o serviço só oferece o gancho."""
    b = _Bancada(antigas=[_char()], novas=[_vazia()]).instalar(monkeypatch)
    pausas = []

    servico.corrigir_ficha(b.portal(), "4500063671.0242", "PDM.5920.020",
                           callback_pause=pausas.append)

    assert pausas == ["4500063671.0242"]


def test_sem_callback_de_pausa_o_servico_salva_sozinho(monkeypatch):
    b = _Bancada(antigas=[_char()], novas=[_vazia()]).instalar(monkeypatch)
    p = b.portal()

    servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert p.salvou >= 1


# =============================================================================
# E. O lote
# =============================================================================
def test_uma_ficha_que_falha_nao_derruba_as_outras(monkeypatch):
    """25 fichas numa rodada: parar tudo na primeira que der errado obrigaria a
    refazer as que já tinham dado certo."""
    b = _Bancada(antigas=[_char()], novas=[_vazia()]).instalar(monkeypatch)
    quebrar = {"4500063671.0002"}
    original = b._trocar

    def _trocar(portal, pdm, callback_log=None, _pmib=None):
        return original(portal, pdm, callback_log)

    monkeypatch.setattr(servico.operacoes, "trocar_pdm", _trocar)

    def _abrir(pmib, **_kw):
        return pmib not in quebrar

    p = b.portal()
    p.pesquisar_e_abrir = _abrir

    resultados = servico.corrigir_lote(
        p, [("4500063671.0001", "PDM.5920.020"),
            ("4500063671.0002", "PDM.5920.020"),
            ("4500063671.0003", "PDM.5920.020")])

    assert [r.ok for r in resultados] == [True, False, True]


def test_o_lote_para_quando_o_usuario_pede(monkeypatch):
    """O botão "Parar" tem que valer entre fichas, e não só no fim."""
    b = _Bancada(antigas=[_char()], novas=[_vazia()]).instalar(monkeypatch)
    p = b.portal()
    p.deve_parar = lambda: True

    resultados = servico.corrigir_lote(
        p, [("4500063671.0001", "PDM.5920.020"),
            ("4500063671.0002", "PDM.5920.020")])

    assert len(resultados) < 2


def test_o_relatorio_do_lote_junta_o_de_cada_ficha(monkeypatch):
    b = _Bancada(antigas=[_char()],
                 novas=[_vazia(), _vazia("9999", "SOBRANDO", "NUM")]
                 ).instalar(monkeypatch)

    resultados = servico.corrigir_lote(
        b.portal(), [("4500063671.0001", "PDM.5920.020")])

    texto = "\n".join(servico.relatorio_do_lote(resultados))
    assert "4500063671.0001" in texto
    assert "SOBRANDO" in texto


def test_o_relatorio_do_lote_nao_usa_travessao(monkeypatch):
    b = _Bancada(antigas=[_char()], novas=[_vazia()]).instalar(monkeypatch)

    resultados = servico.corrigir_lote(
        b.portal(), [("4500063671.0001", "PDM.5920.020")])

    for linha in servico.relatorio_do_lote(resultados):
        assert "—" not in linha


def test_exclusao_que_MENTE_nao_trava_o_app(monkeypatch):
    """⚠️ O laço de exclusão de propósito NÃO avança o índice quando apaga: a
    linha de baixo sobe para o lugar. Se o portal devolver "apaguei" com a
    tabela intacta, o laço tenta a mesma linha para sempre e o app trava sem
    mensagem nenhuma.

    Conferir a contagem custa uma chamada e transforma trava em aviso. Sem o
    guard, ESTE teste não termina.
    """
    b = _Bancada(antigas=[_char()],
                 novas=[_vazia(), _vazia("9999", "SOBRANDO", "NUM")]
                 ).instalar(monkeypatch)
    p = b.portal(apagar_de_verdade=False)
    linhas = []

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020",
                               callback_log=linhas.append)

    assert r.apagadas == 0
    assert any("continua com" in x for x in linhas)


# =============================================================================
# F. O modo "só repor" -- a razão de o retrato ir para o disco
# =============================================================================
def test_repor_do_retrato_NAO_troca_o_pdm(monkeypatch):
    """Nesse ponto o PDM já está onde tem de estar. Trocar de novo apagaria as
    características outra vez -- e o segundo retrato seria o da ficha VAZIA,
    sobrescrevendo o único bom que restava."""
    b = _Bancada(novas=[_vazia()], so_novas=True).instalar(monkeypatch)
    monkeypatch.setattr(servico.retrato, "ler",
                        lambda _c: servico.retrato.Retrato(
                            pmib="4500063671.0242", pdm_antigo="A", pdm_novo="B",
                            caracteristicas=(_char(),)))

    r = servico.repor_do_retrato(b.portal(), "4500063671.0242",
                                 caminho="/retratos/x.json")

    assert "trocar" not in b.passos
    assert "gravar" not in b.passos
    assert r.ok and r.repostas == 1


def test_repor_do_retrato_pega_o_MAIS_NOVO_quando_nao_dizem_qual(monkeypatch):
    """O mais novo é o da tentativa que falhou -- é ele que tem o original."""
    b = _Bancada(novas=[_vazia()], so_novas=True).instalar(monkeypatch)
    monkeypatch.setattr(servico.retrato, "listar",
                        lambda _p: ["/retratos/novo.json", "/retratos/velho.json"])
    lidos = []
    monkeypatch.setattr(servico.retrato, "ler",
                        lambda c: lidos.append(c) or servico.retrato.Retrato(
                            pmib="1", pdm_antigo="A", pdm_novo="B",
                            caracteristicas=(_char(),)))

    servico.repor_do_retrato(b.portal(), "4500063671.0242")

    assert lidos == ["/retratos/novo.json"]


def test_repor_sem_retrato_nenhum_falha_declarado(monkeypatch):
    b = _Bancada(novas=[_vazia()], so_novas=True).instalar(monkeypatch)
    monkeypatch.setattr(servico.retrato, "listar", lambda _p: [])

    r = servico.repor_do_retrato(b.portal(), "4500063671.0242")

    assert not r.ok and r.etapa == "retrato"


def test_repor_de_retrato_corrompido_falha_declarado(monkeypatch):
    b = _Bancada(novas=[_vazia()], so_novas=True).instalar(monkeypatch)

    def _explode(_c):
        raise ValueError("nao e json")

    monkeypatch.setattr(servico.retrato, "ler", _explode)

    r = servico.repor_do_retrato(b.portal(), "4500063671.0242",
                                 caminho="/retratos/ruim.json")

    assert not r.ok and r.etapa == "retrato"


def test_salvar_que_nao_confirma_impede_o_apagamento(monkeypatch):
    """⚠️ Os valores repostos estão na TELA; a exclusão de uma linha chega ao
    servidor na hora. Apagar depois de um SALVAR que não confirmou deixaria a
    ficha com as linhas apagadas E a reposição perdida -- exatamente o "pior do
    que estava" que este módulo existe para impedir."""
    b = _Bancada(antigas=[_char()],
                 novas=[_vazia(), _vazia("9999", "SOBRANDO", "NUM")]
                 ).instalar(monkeypatch)
    p = b.portal(salva=False)

    r = servico.corrigir_ficha(p, "4500063671.0242", "PDM.5920.020")

    assert p.excluidos == []
    assert not r.ok
    assert r.repostas == 1, "o valor foi escrito; o que falhou foi gravar"

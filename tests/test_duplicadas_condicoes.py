r"""
Condições da ficha duplicada (CP 6.4) — cópia literal, salva e CONFERIDA.

A cópia é por XPATH, não por significado: o que está em `Input_PackingLength`
na original vai para `Input_PackingLength` na alvo. Isso é o que dispensa
interpretar rótulo, converter unidade ou traduzir radio -- e é legítimo aqui
porque a operação é DUPLICAR, não preencher.

O que estes testes trancam, além da cópia em si, é o pedido do usuário de
2026-08-19: *"antes de sair de cada uma das páginas, quero que você valide se
de fato conseguiu colocar os dados"*. Salvar com o toast prova que o portal
aceitou; só a releitura prova que o valor ficou.
"""
import pytest

from sigft.core.rpa.portal import PMIBPortal
from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_condicoes as cond


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(cond.time, "sleep", lambda _s: None)


class _EngineDeCondicoes:
    """Tela de Condições: cada campo é endereçado pelo SUFIXO do id.

    O duplo resolve o XPath `//*[contains(@id, 'X')]` de volta para `X`, que é
    exatamente o que o portal faz -- casar o sufixo com o campo cujo id
    gerado termina nele.
    """

    def __init__(self, valores=None, marcados=(), some_ao_ler=(),
                 nao_aceita=(), esvazia_ao_salvar=(), so_digitado=(),
                 esvazia_na_troca=()):
        self.valores = dict(valores or {})
        self.marcados = set(marcados)
        self.some_ao_ler = set(some_ao_ler)
        self.nao_aceita = set(nao_aceita)
        self.esvazia_ao_salvar = set(esvazia_ao_salvar)
        # `so_digitado`: o campo com MÁSCARA -- o `fill` (valor de uma vez)
        # não fica, só a digitação tecla a tecla. Hipótese do log de
        # 2026-10-19 para o volume que sumia.
        self.so_digitado = set(so_digitado)
        # `esvazia_na_troca`: valor que some quando se troca de sub-aba.
        self.esvazia_na_troca = set(esvazia_na_troca)
        self.digitadas = []
        self.teclas = []
        self.escritas = []
        self.cliques = []

    @staticmethod
    def _sufixo(seletor):
        import re
        achado = re.search(r"contains\(@id, '([^']+)'\)", seletor)
        return achado.group(1) if achado else seletor

    def get_value(self, seletor):
        sufixo = self._sufixo(seletor)
        if sufixo in self.some_ao_ler:
            raise RuntimeError("campo não está na tela")
        return self.valores.get(sufixo, "")

    def fill(self, seletor, texto):
        sufixo = self._sufixo(seletor)
        self.escritas.append((sufixo, texto))
        if sufixo not in self.nao_aceita and sufixo not in self.so_digitado:
            self.valores[sufixo] = texto

    def clear(self, seletor):
        self.valores[self._sufixo(seletor)] = ""

    def type_text(self, seletor, texto):
        sufixo = self._sufixo(seletor)
        self.digitadas.append((sufixo, texto))
        if sufixo not in self.nao_aceita:
            self.valores[sufixo] = self.valores.get(sufixo, "") + texto

    def press(self, teclas):
        self.teclas.append(teclas)

    def esta_marcado(self, seletor):
        sufixo = self._sufixo(seletor)
        if sufixo in self.some_ao_ler:
            raise RuntimeError("campo não está na tela")
        return sufixo in self.marcados

    def click(self, seletor):
        sufixo = self._sufixo(seletor)
        self.cliques.append(sufixo)
        self.marcados ^= {sufixo}   # clicar alterna o estado

    def click_dom(self, seletor):
        self.click(seletor)

    def contar(self, seletor):
        """Existe na tela? É o que `valor_se_existir` pergunta ANTES de ler --
        o conserto do travamento de 2026-08-20. `some_ao_ler` é justamente
        "não está na tela", então tem de contar zero aqui também; se contasse
        um, o duplo diria que o campo existe e a leitura seguinte estouraria,
        que é o comportamento antigo."""
        return 0 if self._sufixo(seletor) in self.some_ao_ler else 1

    def texto(self, _seletor):
        return ""


class _PortalDeCondicoes:
    # Emprestados do PMIBPortal REAL: os dois só usam `self.engine`, então
    # ligá-los aqui testa a implementação de verdade em vez de uma cópia
    # que envelhece sozinha. São o conserto do travamento de 2026-08-20 --
    # ler o que pode não existir sem pagar o timeout do motor.
    texto_se_existir = PMIBPortal.texto_se_existir
    valor_se_existir = PMIBPortal.valor_se_existir

    def __init__(self, engine, confirma=True):
        self.engine = engine
        self.confirma = confirma
        self.salvos = []

    def safe_click(self, seletor):
        self.engine.cliques.append(seletor)
        if "Title" in seletor:   # troca de sub-aba
            for sufixo in self.engine.esvazia_na_troca:
                self.engine.valores[sufixo] = ""

    def safe_fill(self, seletor, texto):
        self.engine.fill(seletor, texto)

    def check_or_uncheck(self, seletor, deve_marcar, callback_log=None):
        return PMIBPortal.check_or_uncheck(self, seletor, deve_marcar, callback_log)

    def salvar_e_confirmar(self, nome_secao="", callback_log=None, **_kwargs):
        self.salvos.append(nome_secao)
        for sufixo in self.engine.esvazia_ao_salvar:
            self.engine.valores[sufixo] = ""
        return self.confirma


def _tela(**kwargs):
    engine = _EngineDeCondicoes(**{k: v for k, v in kwargs.items()
                                   if k != "confirma"})
    return _PortalDeCondicoes(engine, kwargs.get("confirma", True)), engine


UM_CAMPO_DE_CADA = {
    "Armazenamento": {"Input_PackingLength": "40", "Checkbox4": True},
    "Transporte": {"TextArea_TransportPackagingPT": "Caixa de papelão"},
    "Manutenção": {"TextArea_CleaningMethodPT": "Pano seco"},
    "Descarte": {"TextArea_DiscardTypePT": "Sucata"},
}


# =============================================================================
# 1. Ler a original
# =============================================================================
def test_ler_traz_texto_e_booleano_com_o_tipo_certo():
    """O TIPO é o que diz, na escrita, se o campo se digita ou se clica."""
    portal, _ = _tela(valores={"Input_PackingLength": "40"}, marcados=["Checkbox4"])

    lido = cond.ler(portal)

    assert lido["Armazenamento"]["Input_PackingLength"] == "40"
    assert lido["Armazenamento"]["Checkbox4"] is True
    assert lido["Armazenamento"]["Checkbox5"] is False


def test_campo_que_nao_esta_na_tela_NAO_entra_no_dicionario():
    """Entrar com "" faria a escrita APAGAR um campo da alvo por causa de uma
    leitura que falhou -- o pior desfecho possível numa duplicação."""
    portal, _ = _tela(some_ao_ler=["Input_PackingLength", "Checkbox4"])

    lido = cond.ler(portal)

    assert "Input_PackingLength" not in lido["Armazenamento"]
    assert "Checkbox4" not in lido["Armazenamento"]


def test_ler_percorre_as_QUATRO_subabas():
    portal, _ = _tela()

    lido = cond.ler(portal)

    assert set(lido) == set(sel.CONDICOES_POR_SUBABA)


# =============================================================================
# 2. Escrever na alvo
# =============================================================================
def test_cada_subaba_e_salva_separadamente():
    """Cada aba tem o seu SALVAR no portal -- é assim que a seção funciona."""
    portal, _ = _tela()

    cond.escrever(portal, UM_CAMPO_DE_CADA)

    # O nome vai CRU (e não "Condições / Armazenamento") porque é a chave de
    # `PALAVRA_DA_SECAO` no portal -- é com ela que o toast é casado pela
    # palavra da seção, e um toast remanescente de outra sub-aba não confirma
    # esta.
    assert portal.salvos == ["Armazenamento", "Transporte",
                             "Manutenção", "Descarte"]


def test_texto_vazio_nao_e_escrito():
    """A alvo nasce vazia: escrever "" não acrescenta nada e é mais uma chance
    de disparar validação do portal sem motivo."""
    portal, engine = _tela()

    cond.escrever(portal, {"Transporte": {"TextArea_PositionCarePT": "   "}})

    assert engine.escritas == []


def test_booleano_FALSO_nao_marca_o_campo():
    portal, engine = _tela()

    cond.escrever(portal, {"Armazenamento": {"Checkbox4": False}})

    assert "Checkbox4" not in engine.marcados


def test_booleano_VERDADEIRO_marca_o_campo():
    portal, engine = _tela()

    cond.escrever(portal, {"Armazenamento": {"Checkbox4": True}})

    assert "Checkbox4" in engine.marcados


# =============================================================================
# 3. A conferência antes de sair da página
# =============================================================================
def test_campo_que_nao_ficou_gravado_vira_PENDENCIA_com_o_nome():
    """*"Antes de sair de cada uma das páginas, quero que você valide se de
    fato conseguiu colocar os dados."* O salvamento confirmou; o valor não
    ficou. Sem a releitura, isso sai como sucesso."""
    portal, _ = _tela(esvazia_ao_salvar=["Input_PackingLength"])
    linhas = []

    resultado = cond.escrever(portal, UM_CAMPO_DE_CADA, linhas.append)

    assert resultado.ok is False
    assert "Input_PackingLength" in "\n".join(linhas)


def test_tudo_conferido_devolve_sucesso():
    """"Tudo" passou a incluir a metade em ESPANHOL (2026-08-21).

    `UM_CAMPO_DE_CADA` traz só os `..._PT` -- é o que a leitura por
    VISUALIZAÇÃO consegue entregar, e por isso a seção fecha INCOMPLETA quando
    vem só isso (ver test_duplicadas_condicoes_visualizacao.py, §6). Aqui a
    pergunta é outra: *escreveu e conferiu tudo* devolve sucesso? Então o
    dicionário tem os dois idiomas, como numa cópia que veio inteira.
    """
    portal, _ = _tela()
    completo = {
        aba: dict(campos, **{s[:-2] + "ES": v for s, v in campos.items()
                             if s.endswith("PT")})
        for aba, campos in UM_CAMPO_DE_CADA.items()
    }

    resultado = cond.escrever(portal, completo, lambda _m: None)

    assert resultado.ok is True


def test_salvamento_nao_confirmado_reprova_a_subaba():
    portal, _ = _tela(confirma=False)

    resultado = cond.escrever(portal, UM_CAMPO_DE_CADA, lambda _m: None)

    assert resultado.ok is False
    assert "não confirmou" in resultado.detalhe


def test_uma_subaba_ruim_nao_impede_as_outras():
    """Ficha meio preenchida com o log dizendo o que faltou é melhor do que
    ficha vazia com erro genérico."""
    portal, engine = _tela(confirma=True, esvazia_ao_salvar=["Input_PackingLength"])

    cond.escrever(portal, UM_CAMPO_DE_CADA, lambda _m: None)

    # `set` e não `len == 4`: desde a autoconferência (2026-10-20) a sub-aba
    # que perdeu o valor é salva UMA segunda vez, no reparo.
    assert set(portal.salvos) == set(UM_CAMPO_DE_CADA), "as 4 sub-abas foram tentadas"
    assert engine.valores.get("TextArea_DiscardTypePT") == "Sucata"


def test_origem_vazia_e_PENDENTE_e_nao_ok():
    """⚠️ MUDOU EM 2026-08-21, pelo log do usuário: CONDIÇÕES saía COMPLETO em
    TODA ficha, para uma seção que ninguém tentou copiar.

    O extrator ainda não lê as Condições do modo de visualização -- ele mesmo
    escreve isso no log, duas linhas antes ("Condições NÃO serão copiadas:
    falta o mapa RÓTULO→campo"). Ou seja, a origem chega vazia SEMPRE, e
    `ok=True` aqui virava COMPLETO na planilha.

    `pendente` diz a verdade nos dois lados: não conta como falha no resumo do
    lote (não é falha, é etapa que falta) e não deixa a coluna fechar."""
    portal, _ = _tela()

    resultado = cond.escrever(portal, {}, lambda _m: None)

    assert resultado.ok is False
    assert resultado.pendente is True
    assert portal.salvos == []   # e continua sem escrever nada no portal


# =============================================================================
# 4. O mapa em si
# =============================================================================
def test_armazenamento_e_a_aba_que_ja_vem_aberta():
    """Posição `None` = não clica em nada. Clicar numa aba já aberta não é
    inofensivo em toda tela do OutSystems."""
    assert sel.CONDICOES_POR_SUBABA["Armazenamento"]["posicao"] is None


def test_escrita_volta_ao_armazenamento_depois_da_auditoria(monkeypatch):
    """A auditoria deixa Descarte ativa; abrir a seção não troca a sub-aba."""
    portal, engine = _tela()
    portal.ativa = "Armazenamento"
    escritas_na_aba = []
    clicar = portal.safe_click

    def selecionar(seletor):
        for nome, mapa in sel.CONDICOES_POR_SUBABA.items():
            posicao = mapa["posicao"] or sel.POSICAO_ARMAZENAMENTO
            if seletor == sel.XPATH_CONDICOES_SUBABA.format(posicao=posicao):
                portal.ativa = nome
        clicar(seletor)

    def preencher(seletor, texto):
        escritas_na_aba.append(portal.ativa)
        engine.fill(seletor, texto)

    # O portal REMOVE do DOM a sub-aba fechada: o campo-âncora de Armazenamento
    # só existe na tela enquanto ela é a ativa. É o que `abrir_subaba` usa para
    # saber se precisa clicar.
    contar = engine.contar

    def contar_com_aba_ativa(seletor):
        if seletor == cond.ancora_da_subaba("Armazenamento"):
            return 1 if portal.ativa == "Armazenamento" else 0
        return contar(seletor)

    monkeypatch.setattr(engine, "contar", contar_com_aba_ativa)
    monkeypatch.setattr(portal, "safe_click", selecionar)
    monkeypatch.setattr(portal, "safe_fill", preencher)
    monkeypatch.setattr(cond.extrator, "id_do_painel", lambda *_a: "")
    monkeypatch.setattr(cond.extrator, "fotografar", lambda *_a, **_k: None)

    cond.fotografar_edicao(portal, object())
    assert portal.ativa == "Descarte"
    cond.escrever(portal, {"Armazenamento": {"Input_PackingLength": "40"}})

    assert escritas_na_aba == ["Armazenamento"]


@pytest.mark.parametrize("valor", ["40", True, False])
def test_campo_ausente_na_conferencia_e_pendencia(valor):
    portal, _ = _tela(some_ao_ler=["campo"])
    assert cond.divergencias_da_subaba(portal, "Armazenamento", {"campo": valor}) == [
        ("campo", valor, None)]


def test_campo_ausente_nao_dispara_escrita_nem_retentativa_lenta():
    portal, engine = _tela(some_ao_ler=["Input_PackingLength", "Checkbox4"])
    campos = {"Input_PackingLength": "40", "Checkbox4": True}

    assert cond.escrever_subaba(portal, "Armazenamento", campos) == list(campos)
    assert len(cond.autoconferir(portal, "Armazenamento", campos)) == 2
    assert engine.escritas == []
    assert engine.digitadas == []
    assert engine.cliques == []


def test_subaba_que_nao_montou_nao_recebe_escrita_nem_salvamento():
    portal, engine = _tela(some_ao_ler=["Input_PackingLength"])
    # O radio também existe em Descarte: sozinho não prova a aba aberta.
    resultado = cond.escrever(portal, {"Armazenamento": {"RadioButton1-input": True}})
    assert not resultado.ok
    assert "RadioButton1-input" not in engine.marcados
    assert portal.salvos == []


def test_espera_subaba_renderizar_antes_de_escrever(monkeypatch):
    portal, engine = _tela()
    contar = engine.contar
    leituras = []

    def renderizando(seletor):
        if "Input_PackingLength" in seletor:
            leituras.append(seletor)
            return int(len(leituras) >= 3)
        return contar(seletor)

    monkeypatch.setattr(engine, "contar", renderizando)
    resultado = cond.escrever(portal, {"Armazenamento": {"Input_PackingLength": "40"}})
    assert resultado.ok
    assert engine.valores["Input_PackingLength"] == "40"


def test_nenhum_id_gerado_no_mapa():
    """`b10-b17-b1-` é gerado e muda de sessão -- a regra do projeto
    (`IDS_GERADOS_NAO_USAR`) vale aqui como em todo o resto do arquivo."""
    import re
    for nome, mapa in sel.CONDICOES_POR_SUBABA.items():
        for sufixo in tuple(mapa["textos"]) + tuple(mapa["booleanos"]):
            assert not re.match(r"^b\d+-", sufixo), f"{nome}/{sufixo} é id gerado"


# ===========================================================================
# Conferir a ficha ALVO antes de dizer que falta
# ===========================================================================
# *"A condição já estava feita, mas daí o robô deveria dar uma checada se está
# completa, pois eu havia marcado o Excel como completo e daí agora ele marcou
# como Incompleto, sendo que tá completo, mas outra pessoa fez."* (2026-08-21)
#
# "Eu não copiei" e "não está lá" são coisas diferentes. O módulo só sabia a
# primeira, e reportava a segunda -- apagando na planilha o trabalho de quem
# preencheu à mão.

def test_alvo_ja_preenchida_fecha_a_secao_sem_copiar_nada():
    # A ficha alvo tem TODOS os campos de texto preenchidos.
    from sigft.core.rpa import seletores_duplicada as _sel
    todos = {sufixo: "preenchido"
             for mapa in _sel.CONDICOES_POR_SUBABA.values()
             for sufixo in mapa["textos"]}
    portal, _engine = _tela(valores=todos)
    logs = []

    resultado = cond.escrever(portal, {}, logs.append)

    assert resultado.ok is True
    assert resultado.pendente is False
    assert portal.salvos == []          # NÃO sobrescreve o que já está lá
    juntos = "\n".join(logs)
    assert "JÁ preenchidas" in juntos
    assert "26 de 26" in juntos   # todos, e a conta fica no log


def test_alvo_vazia_continua_PENDENTE():
    """Sem conteúdo na alvo, nada mudou: a seção não foi feita por ninguém."""
    portal, _engine = _tela()

    resultado = cond.escrever(portal, {}, lambda _m: None)

    assert resultado.ok is False
    assert resultado.pendente is True


def test_PARCIALMENTE_preenchida_NAO_fecha():
    """⚠️ CORREÇÃO DO USUÁRIO (2026-08-21): *"tem que estar completo todos os
    campos; tem que ter conteúdo, só não pode estar em branco"*.

    A primeira versão fechava com QUALQUER conteúdo e mandava a conta para o
    log, para ele julgar. Julgar é o trabalho que a planilha existe para
    poupar: um `3 de 14` marcado COMPLETO é a mesma mentira que este módulo
    combate, com uma nota de rodapé."""
    portal, _engine = _tela(valores={"TextArea_StorageCareES": "algo"})
    logs = []

    resultado = cond.escrever(portal, {}, logs.append)

    assert resultado.pendente is True
    juntos = "\n".join(logs)
    assert "INCOMPLETAS" in juntos
    assert "Armazenamento" in juntos   # a conta continua no log, para achar o que falta


def test_booleano_marcado_NAO_conta_como_preenchido():
    """Rádio e checkbox sempre têm um estado; contá-los diria "preenchido"
    para toda ficha em branco."""
    portal, _engine = _tela(marcados=["Checkbox4", "Checkbox5"])

    resultado = cond.escrever(portal, {}, lambda _m: None)

    assert resultado.pendente is True


# =============================================================================
# 4. Autoconferência (pedido de 2026-10-20) — o log de 2026-10-19
# =============================================================================
# *"Seria bom que nosso robô faça sua autocomprovação: quando completa uma aba,
# repasse de volta verificando seu campo."* No log de 2026-10-19 o portal
# confirmou Armazenamento com o volume em branco em três fichas.
def test_campo_com_mascara_e_REESCRITO_tecla_a_tecla_antes_de_salvar():
    portal, engine = _tela(so_digitado=["Input_PackingLength"])
    linhas = []

    resultado = cond.escrever(portal, UM_CAMPO_DE_CADA, linhas.append)

    assert engine.valores["Input_PackingLength"] == "40"
    assert ("Input_PackingLength", "40") in engine.digitadas
    assert "TAB" in engine.teclas, "sem o blur o OutSystems não recebe o change"
    assert "corrigido na segunda tentativa" in "\n".join(linhas)
    assert "Armazenamento: " not in (resultado.detalhe or "")


def test_campo_que_PEGOU_no_fill_nao_e_redigitado():
    """O que funciona hoje não muda: a segunda forma é só para o que falhou."""
    portal, engine = _tela()

    cond.escrever(portal, UM_CAMPO_DE_CADA, lambda _m: None)

    assert engine.digitadas == []


def test_o_log_diz_o_que_pedi_e_o_que_ficou():
    """"Pedi 40, ficou ''" e "pedi 40, ficou 4" são defeitos diferentes."""
    portal, _ = _tela(nao_aceita=["Input_PackingLength"])
    linhas = []

    resultado = cond.escrever(portal, UM_CAMPO_DE_CADA, linhas.append)

    assert resultado.ok is False
    assert "Input_PackingLength (pedi '40', ficou '')" in "\n".join(linhas)


def test_campo_que_some_ao_salvar_e_reparado_e_salvo_de_novo():
    """O toast confirmou e o valor não ficou: UMA rodada de reparo."""
    portal, engine = _tela()
    sumiu = {"vez": 0}
    salvar_original = portal.salvar_e_confirmar

    def salva_perdendo_na_primeira(nome_secao="", callback_log=None, **kw):
        if nome_secao == "Armazenamento" and sumiu["vez"] == 0:
            sumiu["vez"] = 1
            engine.valores["Input_PackingLength"] = ""
        return salvar_original(nome_secao, callback_log, **kw)

    portal.salvar_e_confirmar = salva_perdendo_na_primeira
    linhas = []

    cond.escrever(portal, UM_CAMPO_DE_CADA, linhas.append)

    assert portal.salvos.count("Armazenamento") == 2
    assert engine.valores["Input_PackingLength"] == "40"
    assert "[Armazenamento] 2 campo(s), salvo e conferido." in "\n".join(linhas)


def test_numero_que_a_mascara_formatou_NAO_e_divergencia():
    assert cond.mesmo_valor("40", "40,00")
    assert cond.mesmo_valor("2,5", "2,50")
    assert cond.mesmo_valor("1000", "1.000,00")
    assert not cond.mesmo_valor("40", "4")
    assert not cond.mesmo_valor("40", "")
    assert not cond.mesmo_valor("Caixa", "caixa ")


def test_REPASSE_final_pega_valor_que_sumiu_ao_trocar_de_subaba():
    """Conferido com a sub-aba aberta, perdido quando o robô foi para a
    seguinte: só voltando lá se vê."""
    portal, _ = _tela(esvazia_na_troca=["Input_PackingLength"])
    linhas = []

    resultado = cond.escrever(portal, UM_CAMPO_DE_CADA, linhas.append)

    assert resultado.ok is False
    assert "mudaram depois de salvos" in resultado.detalhe
    assert "Repasse" in "\n".join(linhas)


def test_REPASSE_volta_CLICANDO_em_Armazenamento():
    """Na ida Armazenamento não se clica (já vem aberta); na volta, sim --
    senão a releitura olharia a tela de Descarte."""
    portal, engine = _tela()

    cond.escrever(portal, UM_CAMPO_DE_CADA, lambda _m: None)

    alvo = sel.XPATH_CONDICOES_SUBABA.format(posicao=sel.POSICAO_ARMAZENAMENTO)
    assert alvo in engine.cliques


def test_REPASSE_limpo_diz_que_conferiu():
    portal, _ = _tela()
    linhas = []
    completo = {
        aba: dict(campos, **{s[:-2] + "ES": v for s, v in campos.items()
                             if s.endswith("PT")})
        for aba, campos in UM_CAMPO_DE_CADA.items()
    }

    resultado = cond.escrever(portal, completo, linhas.append)

    assert resultado.ok is True
    assert "Repasse final: 4 sub-aba(s) relidas" in "\n".join(linhas)

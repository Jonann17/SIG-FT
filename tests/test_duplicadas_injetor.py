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
from sigft.core.rpa.portal import PMIBPortal
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


def _e_seletor_da_ge(seletor):
    """O seletor pede o campo da GE Vernova, ou justamente os OUTROS?

    Os dois mencionam `fa-info-circle` -- um exigindo, o outro dentro de um
    `not(...)`. Um duplo que olhasse só a presença do texto trataria os dois
    como iguais, e foi o que aconteceu: o "antes e depois" do fabricante passou
    a ler a lista da GE e devolveu campo nenhum.
    """
    if "fa-info-circle" not in seletor:
        return False
    return "not(" not in seletor


class _EngineFalso:
    def __init__(self, linhas=(), combos=(), campos_referencia=1,
                 existentes=(), habilitados=(), exige_blur=False,
                 ids_referencia=None, id_que_nasce=None, opcoes=None, ids_da_ge=None):
        self.linhas = list(linhas)
        self.combos = list(combos)
        self.campos_referencia = campos_referencia
        # Ids dos campos de Referência hoje na tela. `id_que_nasce` é o campo
        # que o portal RENDERIZA quando o fabricante é escolhido -- é o
        # comportamento que o usuário descreveu e o que torna a linha certa
        # descobrível em vez de adivinhada.
        self.ids_referencia = list(
            ids_referencia if ids_referencia is not None
            else [f"b1-b2-b{n}-Input_TextVar" for n in range(1, campos_referencia + 1)])
        self.id_que_nasce = id_que_nasce
        self.opcoes = list(opcoes or [])
        # Campos de Referência com ÍCONE DE INFORMAÇÃO: é o da GE Vernova,
        # que é fixo na tela e não nasce de combo nenhum.
        self.ids_da_ge = list(ids_da_ge or [])
        self.existentes = list(existentes)
        self.habilitados = list(habilitados)
        self.exige_blur = exige_blur      # o portal real só grava no blur
        self.aviso_colisao = ""
        self.valores = {}                 # o que o campo REALMENTE guardou
        self.pendentes = {}               # digitado, ainda sem blur
        self.cliques = []
        # Preenchido por `_PortalFalso.__init__`: o "+" é do portal, mas quem
        # o recebe é o engine (caminho estrito). Sem esse elo, o duplo não
        # consegue reproduzir "cliquei e a linha entrou".
        self._portal = None

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

    def click_estrito(self, seletor):
        """O caminho do "+": levanta em vez de engolir (2026-08-19).

        `portal.erro_no_clique_estrito`, quando setado, é o que o duplo
        levanta -- reproduz o clique que não pega no elemento.
        """
        erro = getattr(self._portal, "erro_no_clique_estrito", None) if self._portal else None
        if erro is not None:
            raise erro
        if self._portal is None:
            self.click_nativo(seletor)
            return
        # Passa pelo PORTAL, e não direto: é lá que moram as observações
        # (`portal.cliques`) e os ganchos que os outros testes usam -- o
        # `_PortalQueRecusa`, por exemplo, liga o aviso de colisão no clique do
        # "+". Em produção `click_estrito` é o mesmo clique, só que estrito;
        # desviar do portal no duplo criaria uma diferença que não existe.
        self._portal.safe_click(seletor)
        self._portal.aplicar_efeito_do_mais(seletor)

    # -- leitura
    def get_value(self, seletor):
        return self.valores.get(seletor, "")

    def contar(self, seletor):
        if "TechnicalCharacteristics" in seletor:
            return len(self.linhas)
        if "vscomp-toggle-button" in seletor:
            # O seletor por PLACEHOLDER filtra pelo `data-tooltip`; o genérico
            # não. Se o duplo devolvesse o mesmo para os dois, o teste da
            # estratégia 1 não provaria nada.
            alvo = re.search(r"@data-tooltip,\s*'([^']*)'", seletor)
            if alvo:
                return sum(1 for c in self.combos if alvo.group(1) in c)
            return len(self.combos)
        if _e_seletor_da_ge(seletor):
            return len(self.ids_da_ge)
        if "Input_TextVar" in seletor and "@id=" not in seletor:
            return len(self.ids_referencia)
        if "@id=" in seletor:
            # Campo endereçado pelo ID: existe enquanto o id estiver na tela.
            # `valor_se_existir` (o conserto do travamento de 2026-08-20)
            # pergunta isto ANTES de ler -- sem esta resposta o duplo diria
            # que todo campo sumiu, e "a linha entrou" sairia sempre verdade.
            # (`re` já vem do topo do arquivo -- reimportá-lo AQUI dentro
            # tornava o nome local e quebrava os outros ramos deste método.)
            achado = re.search(r"@id='([^']+)'", seletor)
            alvo = achado.group(1) if achado else None
            return 1 if alvo and alvo in self.ids_referencia else 0
        return 0

    def atributo(self, seletor, nome):
        indice = _indice_do_seletor(seletor)
        if nome != "id" or not indice:
            return ""
        fonte = self.ids_da_ge if _e_seletor_da_ge(seletor) else self.ids_referencia
        return fonte[indice - 1] if indice <= len(fonte) else ""

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
        if "role='option'" in seletor:
            # A opção só "existe" se o nome estiver na lista do dropdown --
            # senão o duplo aprovaria clicar em opção que não está lá, que é
            # justamente o erro de escolher fabricante parecido.
            return any(f"'{nome}'" in seletor for nome in self.opcoes)
        return any(marca in seletor for marca in self.existentes)

    def esta_habilitado(self, seletor):
        return any(marca in seletor for marca in self.habilitados)


class _PortalFalso:
    # Emprestados do PMIBPortal REAL: os dois só usam `self.engine`, então
    # ligá-los aqui testa a implementação de verdade em vez de uma cópia
    # que envelhece sozinha. São o conserto do travamento de 2026-08-20 --
    # ler o que pode não existir sem pagar o timeout do motor.
    texto_se_existir = PMIBPortal.texto_se_existir
    valor_se_existir = PMIBPortal.valor_se_existir

    def __init__(self, engine):
        self.engine = engine
        engine._portal = self
        # Efeito do "+" quando a linha ENTRA na tabela. São os dois desfechos
        # observados no portal, e os dois provam a mesma coisa -- o formulário
        # largou o valor: o campo do fabricante SOME (o de adicionar se
        # recolhe) e o campo fixo da GE ESVAZIA.
        #
        # O default é o desfecho BOM, e de propósito: o normal do portal é o
        # "+" funcionar. Fosse o contrário, todo teste que não fala do "+"
        # teria de carregar um remendo, e o duplo passaria a ensinar que o
        # normal é falhar. Quem reproduz o defeito de 2026-08-19 desliga os
        # dois explicitamente -- ver test_duplicadas_linha_do_fornecedor.py.
        self.comita_no_mais = False   # o campo some (linha do fabricante)
        self.limpa_no_mais = True     # o campo esvazia (linha fixa) -- default
        self.erro_no_clique_estrito = None
        # Como a tabela fica DEPOIS do salvamento. `None` = igual a antes.
        # Existe porque o portal recarrega a seção ao gravar, e o que volta
        # nem sempre é o que se deixou -- é justamente essa diferença que a
        # releitura de `limpar_caracteristicas` existe para pegar.
        self.linhas_apos_salvar = None
        self.cliques = []
        self.preenchidos = []
        self.excluidas = []
        self.salvou = []
        self.exclusao_falha_em = ()
        self.salvar_devolve = True

    def safe_click(self, seletor):
        self.cliques.append(seletor)
        # Escolher o fabricante RENDERIZA o campo de Referência dele.
        if "role='option'" in seletor and self.engine.id_que_nasce:
            self.engine.ids_referencia.append(self.engine.id_que_nasce)

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

    def aplicar_efeito_do_mais(self, seletor):
        if "fa-plus-circle" not in seletor:
            return
        if str(self.engine.aviso_colisao or "").strip():
            # Colisão de verdade: o portal recusa e a linha NÃO entra.
            # `.strip()` e não truthiness -- o bloco de aviso fica no DOM o
            # tempo todo, vazio ou com espaços, e foi confundir "presente" com
            # "tem conteúdo" que quebrou a 1ª sessão real.
            return
        if self.comita_no_mais:
            self.engine.ids_referencia = []
            self.engine.valores.clear()
        elif self.limpa_no_mais:
            self.engine.valores.clear()

    def salvar_e_confirmar(self, nome_secao="", callback_log=None, **_kwargs):
        """Passa a ser o caminho do módulo novo (2026-08-19): SALVAR + toast
        de sucesso NOVO na tela. O duplo delega no `clicar_salvar_visivel`
        de sempre -- a mecânica do toast é testada contra o `PMIBPortal`
        real em tests/test_duplicadas_salvar_com_prova.py, e reimplementá-la
        aqui só criaria uma segunda verdade para envelhecer sozinha."""
        return self.clicar_salvar_visivel(nome_secao)

    def clicar_salvar_visivel(self, nome_secao=""):
        self.salvou.append(nome_secao)
        if self.linhas_apos_salvar is not None:
            self.engine.linhas = list(self.linhas_apos_salvar)
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

def test_o_combo_se_identifica_pelo_proprio_placeholder():
    """ACHADO DE 2026-08-17, do HTML que o usuário levantou: enquanto está
    vazio, o combo diz `data-tooltip="Selecione um fabricante"`. O placeholder
    NOMEIA o campo -- e vale exatamente no momento em que precisamos dele,
    antes de escolher. É a estratégia 1, e ela dispensa a eliminação."""
    portal, _e = _com_combos("Selecione um fornecedor", "Selecione um fabricante")

    escolhido = injetor.achar_combo_do_fabricante(portal, callback_log=lambda _m: None)

    assert "data-tooltip" in escolhido
    assert escolhido.endswith(")[1]")  # o único que casa o placeholder


def test_com_um_combo_so_usa_ele():
    """Sem placeholder que case (ficha já com fabricante escolhido), cai na
    eliminação -- e com um combo só não há o que eliminar."""
    portal, _e = _com_combos("SCHNEIDER")

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
    engine.opcoes.append("SCHNEIDER")

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
    """Salvar que não confirma reprova a seção.

    ⚠️ A mensagem MUDOU em 2026-08-19 e o motivo importa: o injetor passou a
    chamar `salvar_e_confirmar`, e o "não achei o botão SALVAR" virou uma
    linha do PRÓPRIO portal (que o duplo substitui). O que o injetor diz agora
    é o veredito -- a seção não foi confirmada --, apontando para a linha
    acima. Continuar exigindo a palavra "SALVAR" aqui testaria o duplo, não o
    código.
    """
    portal, _engine = _com_tabela(list(_LINHAS))
    portal.salvar_devolve = False
    logs = []

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=logs.append)

    assert resultado.ok is False
    assert resultado.detalhe == "não salvou"
    assert "NÃO foi confirmada" in "\n".join(logs)


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
    """O laço não pode travar na linha que resistiu -- ele avança e avisa.

    ⚠️ O VEREDITO MUDOU EM 2026-08-19. Antes a seção saía `ok=True`: o aviso
    ia para o log e a ficha era dada por pronta com a característica teimosa
    ainda lá. O usuário fechou essa porta: *"se tiver mais características,
    estas devem ser excluídas, pois se não, não vai conseguir salvar"*. Uma
    linha que sobrou não é um detalhe cosmético -- ela impede a ficha de
    fechar, e a releitura depois do save agora reprova a seção.

    O que este teste continua provando é o que ele sempre provou: o laço
    AVANÇA (não fica tentando a mesma linha para sempre) e diz qual falhou.
    """
    portal, engine = _com_tabela(["TEIMOSA", "CODIGO PMIB"])
    portal.exclusao_falha_em = ("TEIMOSA",)
    logs = []

    resultado = injetor.limpar_caracteristicas(portal, "X", callback_log=logs.append)

    assert engine.linhas == ["TEIMOSA", "CODIGO PMIB"], "o laço avançou, não travou"
    assert any("Não consegui excluir" in linha for linha in logs)
    assert resultado.ok is False, "linha que sobrou impede a ficha de fechar"
    assert "sobraram" in resultado.detalhe


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


# ===========================================================================
# O campo de Referência é O QUE NASCEU
# ===========================================================================
# *"Daí quando seleciona uma caixa do dropdown aparece o campo de referência à
# direita."* É o achado que resolve a pergunta que não tinha resposta boa pelo
# DOM -- "qual dos campos de Referência é o do fabricante?" vira "qual apareceu
# agora?", que é objetiva.

def _com_combo_que_faz_nascer(id_novo="b10-b11-b4-Input_TextVar",
                              ids_existentes=("b10-b11-b2-Input_TextVar",)):
    engine = _EngineFalso(
        combos=("Selecione um fabricante",),
        opcoes=["SCHNEIDER"],
        ids_referencia=list(ids_existentes),
        id_que_nasce=id_novo,
    )
    return _PortalFalso(engine), engine


def test_o_campo_que_nasce_ao_escolher_e_o_do_fabricante():
    portal, _e = _com_combo_que_faz_nascer()

    resultado = injetor.escolher_fabricante(portal, "SCHNEIDER",
                                            callback_log=lambda _m: None)

    assert resultado.ok is True
    assert resultado.id_do_campo_de_referencia == "b10-b11-b4-Input_TextVar"


def test_nenhum_campo_novo_nao_vira_chute():
    """Zero campos novos = o portal não renderizou (ou a ficha já tinha
    fabricante). Devolver um id qualquer aqui reintroduziria o defeito que
    escreveu na linha da GE."""
    portal, _e = _com_combo_que_faz_nascer(id_novo=None)
    logs = []

    resultado = injetor.escolher_fabricante(portal, "SCHNEIDER", callback_log=logs.append)

    assert resultado.id_do_campo_de_referencia == ""
    assert "esperava 1" in "\n".join(logs)


def test_com_o_id_escreve_no_campo_certo_mesmo_havendo_outros():
    """O caso exato da 1ª sessão: dois campos de Referência na tela, e o
    primeiro em ordem de documento é o da GE."""
    engine = _EngineFalso(ids_referencia=["b10-b11-b2-Input_TextVar",
                                          "b10-b11-b4-Input_TextVar"])
    portal = _PortalFalso(engine)

    resultado = injetor.escrever_referencia(
        portal, "2904616", callback_log=lambda _m: None,
        id_do_campo="b10-b11-b4-Input_TextVar")

    assert resultado.ok is True
    seletores = [s for s, _t in portal.preenchidos]
    assert all("b10-b11-b4-Input_TextVar" in s for s in seletores)


def test_o_mais_clicado_e_o_da_MESMA_linha():
    """O "+" e o campo compartilham o caminho do bloco no OutSystems
    (`b10-b11-b4-`). Sem essa âncora, `//a[.//i[fa-plus-circle]]` clicaria o
    "+" da outra linha -- adicionando a referência no lugar errado."""
    engine = _EngineFalso(ids_referencia=["b10-b11-b4-Input_TextVar"])
    portal = _PortalFalso(engine)

    injetor.escrever_referencia(portal, "2904616", callback_log=lambda _m: None,
                                id_do_campo="b10-b11-b4-Input_TextVar")

    cliques_no_mais = [c for c in portal.cliques if "fa-plus-circle" in c]
    assert cliques_no_mais and all("b10-b11-b4-" in c for c in cliques_no_mais)


@pytest.mark.parametrize("id_bruto, esperado", [
    ("b10-b11-b4-Input_TextVar", "b10-b11-b4-"),
    ("b1-Input_TextVar", "b1-"),
    ("Input_TextVar", ""),          # sem prefixo nenhum
    ("b10-b11-b4-Outra_Coisa", ""),  # não é campo de referência
    ("", ""),
    (None, ""),
])
def test_prefixo_do_bloco(id_bruto, esperado):
    assert injetor.prefixo_do_bloco(id_bruto) == esperado


# ===========================================================================
# Fornecedor — mesma mecânica, mesma garantia
# ===========================================================================
def test_referencia_da_GE_vazia_e_pulada_sem_erro():
    """"Se estiver vazio, só ignorar" -- palavra do usuário."""
    engine = _EngineFalso(ids_da_ge=["b10-b11-b6-Input_TextVar"])
    portal = _PortalFalso(engine)

    resultado = injetor.escrever_referencia_da_ge(
        portal, "", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert portal.preenchidos == []


def test_a_referencia_da_GE_vai_para_o_campo_com_icone_de_informacao():
    """⚠️ CORREÇÃO DE UMA SUPOSIÇÃO MINHA: a primeira versão desta função
    selecionava a GE num COMBO, por simetria com o fabricante. O HTML que o
    usuário levantou mostra que não há combo -- o campo é fixo e já está na
    tela. Simetria é hipótese, não evidência."""
    engine = _EngineFalso(
        ids_referencia=["b10-b11-b4-Input_TextVar"],
        ids_da_ge=["b10-b11-b6-Input_TextVar"],
    )
    portal = _PortalFalso(engine)

    resultado = injetor.escrever_referencia_da_ge(
        portal, "CMI-99", callback_log=lambda _m: None)

    assert resultado.ok is True
    assert resultado.nome == "ge_vernova"   # é o nome que a planilha usa
    seletores = [s for s, t in portal.preenchidos if t == "CMI-99"]
    assert seletores and all("b10-b11-b6-Input_TextVar" in s for s in seletores)
    assert portal.cliques == [] or all("b10-b11-b6-" in c for c in portal.cliques)


def test_sem_campo_com_o_icone_NAO_escreve_nada():
    """Zero ou mais de um significa que a tela não é a que conhecemos --
    escrever no palpite poria a referência da GE numa linha de fabricante."""
    engine = _EngineFalso(ids_referencia=["b10-b11-b4-Input_TextVar"], ids_da_ge=[])
    portal = _PortalFalso(engine)
    logs = []

    resultado = injetor.escrever_referencia_da_ge(
        portal, "CMI-99", callback_log=logs.append)

    assert resultado.ok is False
    assert portal.preenchidos == []
    assert "à mão" in "\n".join(logs)


def test_o_campo_da_GE_nao_entra_na_conta_do_que_NASCEU():
    """Ele está na tela o tempo todo. Se entrasse na lista comparada pelo
    "antes e depois", um dia em que fosse renderizado depois ele apareceria
    como "nascido" -- e a referência do FABRICANTE iria para a linha da GE."""
    engine = _EngineFalso(
        combos=("Selecione um fabricante",), opcoes=["SCHNEIDER"],
        ids_referencia=[], ids_da_ge=["b10-b11-b6-Input_TextVar"],
        id_que_nasce="b10-b11-b4-Input_TextVar",
    )
    portal = _PortalFalso(engine)

    resultado = injetor.escolher_fabricante(portal, "SCHNEIDER",
                                            callback_log=lambda _m: None)

    assert resultado.id_do_campo_de_referencia == "b10-b11-b4-Input_TextVar"


# ===========================================================================
# A linha do FORNECEDOR — corrigida em 2026-08-18
# ===========================================================================
# Relato do usuário: *"ele não está conseguindo nem colocar a referência
# correta do fornecedor correto, ele está fazendo no campo de fornecimento da
# GE"*.
#
# A causa não era um seletor errado, era o MODELO: o código tratava
# "Fornecedor" e "GE Vernova" como a mesma linha. `PLACEHOLDER_COMBO_FORNECEDOR`
# estava mapeado desde 2026-08-17 e não era usado por ninguém -- o robô ia
# direto escrever no campo do ícone ⓘ.
#
#     Fabricante   combo  -> Referência = CÓDIGO DO MATERIAL
#     Fornecedor   combo  -> Referência = CÓDIGO DO MATERIAL
#     GE Vernova   fixo ⓘ -> Referência = CÓDIGO CMI / CÓDIGO GE

def test_o_combo_do_fornecedor_se_identifica_pelo_proprio_placeholder():
    portal, _engine = _com_combos("Selecione um fabricante", "Selecione um fornecedor")

    seletor = injetor.achar_combo_do_fornecedor(portal)

    assert seletor is not None
    assert sel.PLACEHOLDER_COMBO_FORNECEDOR in seletor


def test_sem_combo_de_fornecedor_na_tela_NAO_escreve_nada():
    """Recusar é a decisão central deste módulo: escrever no combo errado põe
    dado errado numa ficha real e não dá sintoma nenhum na tela."""
    portal, _engine = _com_combos("Selecione um fabricante")
    logs = []

    assert injetor.achar_combo_do_fornecedor(portal, logs.append) is None
    assert any("NÃO escrevi nada" in l for l in logs)


def test_dois_combos_de_fornecedor_tambem_recusam():
    portal, _engine = _com_combos("Selecione um fornecedor", "Selecione um fornecedor")
    logs = []

    assert injetor.achar_combo_do_fornecedor(portal, logs.append) is None
    assert any("não dá para saber qual" in l for l in logs)


def test_o_fornecedor_ausente_nao_e_confundido_com_o_fabricante():
    """O combo do FABRICANTE não pode virar o do fornecedor por eliminação.

    A 2ª estratégia de `achar_combo_do_fabricante` (eliminar "o que é o
    fornecedor fixo") se apoiava em premissa que a resposta do usuário de
    2026-08-18 derrubou -- o fornecedor VARIA. Por isso o lado do fornecedor
    não tem eliminação: sem o placeholder, recusa.
    """
    portal, _engine = _com_combos("Selecione um fabricante")

    assert injetor.achar_combo_do_fornecedor(portal) is None


def test_escolher_fornecedor_usa_o_campo_que_NASCEU_da_escolha():
    """Mesma mecânica do fabricante: a foto de antes/depois é o que diz em qual
    linha escrever, em vez de pegar a primeira "Referência" da tela."""
    engine = _EngineFalso(
        combos=("Selecione um fabricante", "Selecione um fornecedor"),
        existentes=["data-tooltip=", "vscomp-search-input"],
        opcoes=["SIEMENS DO BRASIL"],
        ids_referencia=["b10-b11-b2-Input_TextVar"],
        id_que_nasce="b10-b11-b8-Input_TextVar",
    )
    portal = _PortalFalso(engine)

    resultado = injetor.escolher_fornecedor(portal, "SIEMENS DO BRASIL")

    assert resultado.ok
    assert resultado.nome == "fornecedor"
    assert resultado.id_do_campo_de_referencia == "b10-b11-b8-Input_TextVar"


def test_fornecedor_sem_nome_nao_abre_combo_nenhum():
    portal, _engine = _com_combos("Selecione um fornecedor")

    resultado = injetor.escolher_fornecedor(portal, "")

    assert not resultado.ok
    assert portal.cliques == []


def test_fornecedor_que_nao_aparece_no_filtro_nao_seleciona_nada():
    """Não clicar em "a primeira opção que sobrou": o filtro textual pode
    deixar uma opção PARECIDA, e fornecedor errado não dá sintoma na tela."""
    engine = _EngineFalso(
        combos=("Selecione um fornecedor",),
        existentes=["data-tooltip=", "vscomp-search-input"],  # sem `role='option'`
    )
    portal = _PortalFalso(engine)
    logs = []

    resultado = injetor.escolher_fornecedor(portal, "FORNECEDOR INEXISTENTE", logs.append)

    assert not resultado.ok
    assert any("não apareceu no combo" in l for l in logs)


def test_a_funcao_da_GE_nao_se_chama_mais_fornecedor():
    """O nome antigo (`escrever_referencia_do_fornecedor`) ERA a causa do erro,
    não um detalhe dele: chamar de "fornecedor" a linha da GE fazia o valor do
    fornecedor parecer que ia para o lugar certo."""
    assert not hasattr(injetor, "escrever_referencia_do_fornecedor")
    assert hasattr(injetor, "escrever_referencia_da_ge")
    assert hasattr(injetor, "escolher_fornecedor")


def test_as_duas_referencias_nao_se_sobrescrevem_no_placar():
    """As duas linhas passam por `escrever_referencia`; com um nome fixo, o
    segundo resultado apagaria o primeiro e uma falha ficaria invisível."""
    engine = _EngineFalso(existentes=["Input_TextVar"],
                          ids_referencia=["b10-b11-b4-Input_TextVar"])
    portal = _PortalFalso(engine)

    do_fabricante = injetor.escrever_referencia(
        portal, "2904616", id_do_campo="b10-b11-b4-Input_TextVar")
    do_fornecedor = injetor.escrever_referencia(
        portal, "2904616", id_do_campo="b10-b11-b4-Input_TextVar",
        nome_da_secao="referencia_fornecedor")

    assert do_fabricante.nome == "referencia"
    assert do_fornecedor.nome == "referencia_fornecedor"

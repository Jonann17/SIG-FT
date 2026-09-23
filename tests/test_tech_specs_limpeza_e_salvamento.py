r"""Duas melhorias no Upload de Características Técnicas (2026-09-23).

**1. Apagar as características EM BRANCO que o JSON não menciona.**

Pedido do usuário: quando a ficha (a planilha traduzida) foi feita numa revisão
ANTIGA do PDM e o portal já está numa revisão mais nova, a tabela tem linhas que
não existiam na origem. Elas ficam em branco, e o robô as deixava lá com um
`·  ignorada (não veio no JSON)`. Agora são apagadas, e o log diz por quê.

⚠️ As três condições são todas necessárias, e cada uma protege um caso:

  - **em branco** -- uma linha COM valor que o JSON não menciona pode ter sido
    preenchida à mão. Apagá-la seria destruir trabalho humano;
  - **fora do JSON** -- uma linha em branco que o JSON MENCIONA é um
    preenchimento que falhou. Apagá-la esconderia justamente o que falta
    corrigir;
  - **a mesma chave do laço de preenchimento** -- se as duas rotinas
    calcularem a chave de jeitos diferentes, a limpeza apaga o que acabou de
    ser preenchido. É o teste mais importante deste arquivo.

**2. Validar o SALVAR pela mensagem do portal.**

Hoje o robô preenche e PAUSA em toda ficha, para a pessoa conferir e salvar. Com
a validação, ele salva, lê o toast e só pausa nas fichas que não salvaram --
que são justamente as que precisam de gente.

Os dois HTML vieram do usuário:

    <div class="feedback-message feedback-message-success feedback-message-autoclose" ...>
      <div class="feedback-message-text">As características técnicas foram salvas com sucesso!</div>
    <div class="feedback-message feedback-message-warning" ...>
      <div class="feedback-message-text">Por favor, verifique os campos</div>

⚠️ Repare que o de sucesso tem `feedback-message-autoclose` e o de aviso NÃO.
O aviso FICA na tela -- é o que torna seguro lê-lo depois de o salvamento
falhar, sem correr contra o relógio do toast.
"""
from __future__ import annotations

import pytest

from sigft.services import tech_specs


# =============================================================================
# Dublês
# =============================================================================
class _Linha:
    """Uma linha da tabela: a descrição e se ela tem algum valor."""

    def __init__(self, descricao, vazia=True):
        self.descricao = descricao
        self.vazia = vazia


class _EngineDeTabela:
    """Tabela paginada. Apagar REMOVE de verdade, como o portal faz."""

    def __init__(self, paginas):
        self.paginas = [list(p) for p in paginas]
        self.pagina = 0
        self.apagadas = []

    # -- o que a limpeza usa ------------------------------------------------
    def contar(self, seletor):
        if "página seguinte" in seletor:
            return 1 if self.pagina < len(self.paginas) - 1 else 0
        if seletor.endswith("/tr"):
            return len(self.paginas[self.pagina])
        return 1 if self._linha(seletor) else 0

    def element_exists(self, seletor):
        return self.contar(seletor) > 0

    def esta_habilitado(self, _seletor):
        return self.pagina < len(self.paginas) - 1

    def click_raw(self, seletor):
        if "página seguinte" in seletor:
            self.pagina += 1

    def texto(self, seletor):
        linha = self._linha(seletor)
        if linha is None:
            return ""
        return linha.descricao if "Descri" in seletor else ""

    def get_value(self, seletor):
        linha = self._linha(seletor)
        if linha is None or linha.vazia:
            return ""
        return "TEM VALOR" if "TextArea_ValuePT" in seletor else ""

    def texto_selecionado(self, _seletor):
        return ""

    def scroll_to(self, _seletor):
        pass

    # -- tradução do seletor ------------------------------------------------
    def _indice(self, seletor):
        import re
        achado = re.search(r"\)\[(\d+)\]", seletor)
        return int(achado.group(1)) if achado else None

    def _linha(self, seletor):
        indice = self._indice(seletor)
        if indice is None:
            return None
        atuais = self.paginas[self.pagina]
        # Só a coluna de descrição e o textarea PT existem no dublê; os outros
        # campos devolvem "nada", que é o que faz `tipo_da_linha` dar "CHAR".
        if not (1 <= indice <= len(atuais)):
            return None
        if "Descri" in seletor or "TextArea_ValuePT" in seletor:
            return atuais[indice - 1]
        return None

    def remover(self, indice):
        atuais = self.paginas[self.pagina]
        if 1 <= indice <= len(atuais):
            self.apagadas.append(atuais.pop(indice - 1).descricao)
            return True
        return False


class _PortalDeExclusao:
    def __init__(self, engine, apaga=True):
        self.engine = engine
        self.apaga = apaga

    def excluir_linha_com_confirmacao(self, seletor):
        if not self.apaga:
            return False
        return self.engine.remover(self.engine._indice(seletor))


def _automacao(paginas, apaga=True):
    """`TechSpecsAutomation` sem navegador, com a tabela do dublê."""
    automacao = tech_specs.TechSpecsAutomation()
    automacao.engine = _EngineDeTabela(paginas)
    automacao.portal = _PortalDeExclusao(automacao.engine, apaga=apaga)
    return automacao


# =============================================================================
# A. A chave -- o teste mais importante
# =============================================================================
def test_a_chave_da_limpeza_e_a_MESMA_do_laco_de_preenchimento():
    """⚠️ Se as duas rotinas calcularem a chave diferente, a limpeza apaga
    exatamente o que acabou de ser preenchido.

    O laço de preenchimento faz: regex `^\\s*\\d+\\s*-\\s*(.*)` sobre o
    `textContent` da descrição, depois `normalizar_texto`. A limpeza tem de
    chegar no mesmo lugar, partindo do mesmo texto.
    """
    automacao = _automacao([[]])

    for descricao in ("1650 - COMPONENTES", "1650-COMPONENTES",
                      "  8267 - CERTIFICADO  ", "8875 - ACESSORIOS 1",
                      "CARACTERISTICA SEM CODIGO", "1064 - CORRENTE NOMINAL"):
        assert (tech_specs.chave_da_caracteristica(descricao, automacao.normalizar_texto)
                == _chave_do_laco_de_preenchimento(descricao, automacao))


def _chave_do_laco_de_preenchimento(txt_tela, automacao):
    """Cópia EXATA do que `processar_lista` faz hoje, para comparar."""
    import re
    match = re.search(r"^\s*\d+\s*-\s*(.*)", txt_tela)
    return automacao.normalizar_texto(match.group(1) if match else txt_tela)


def test_a_chave_aguenta_o_formato_REAL_do_portal():
    """`1650 - COMPONENTES`, com espaços em volta do hífen -- medido no
    recorte real de 2026-09-23."""
    automacao = _automacao([[]])

    assert tech_specs.chave_da_caracteristica(
        "1650 - COMPONENTES", automacao.normalizar_texto) == "COMPONENTES"


# =============================================================================
# B. A limpeza -- as três condições
# =============================================================================
def test_apaga_a_linha_em_branco_que_o_JSON_nao_menciona():
    automacao = _automacao([[_Linha("1650 - COMPONENTES", vazia=True)]])
    linhas = []

    apagadas = automacao.apagar_em_branco_fora_do_json({}, linhas.append)

    assert apagadas == ["COMPONENTES"]
    assert automacao.engine.apagadas == ["1650 - COMPONENTES"]


def test_o_log_DIZ_por_que_a_linha_foi_apagada():
    """*"avisasse no log que essa característica foi apagada porque não estava
    no JSON de origem"*."""
    automacao = _automacao([[_Linha("1650 - COMPONENTES", vazia=True)]])
    linhas = []

    automacao.apagar_em_branco_fora_do_json({}, linhas.append)

    texto = "\n".join(linhas)
    assert "COMPONENTES" in texto
    assert "JSON" in texto


def test_NAO_apaga_a_linha_em_branco_que_ESTA_no_json():
    """Branco + no JSON = preenchimento que falhou. Apagar esconderia
    justamente o que falta corrigir."""
    automacao = _automacao([[_Linha("1650 - COMPONENTES", vazia=True)]])

    apagadas = automacao.apagar_em_branco_fora_do_json({"COMPONENTES": {}})

    assert apagadas == []
    assert automacao.engine.apagadas == []


def test_NAO_apaga_a_linha_COM_VALOR_fora_do_json():
    """Pode ter sido preenchida à mão. Apagar seria destruir trabalho
    humano."""
    automacao = _automacao([[_Linha("9999 - DIGITADA A MAO", vazia=False)]])

    apagadas = automacao.apagar_em_branco_fora_do_json({})

    assert apagadas == []
    assert automacao.engine.apagadas == []


def test_apaga_em_TODAS_as_paginas():
    """*"as características que ficaram em branco em todas as páginas"*."""
    automacao = _automacao([
        [_Linha("1 - A", vazia=True), _Linha("2 - B", vazia=False)],
        [_Linha("3 - C", vazia=True)],
    ])

    apagadas = automacao.apagar_em_branco_fora_do_json({})

    assert sorted(apagadas) == ["A", "C"]


def test_o_indice_NAO_avanca_quando_a_linha_e_apagada():
    """A linha de baixo sobe para o lugar. Avançar sempre deixaria metade das
    vazias para trás -- é a lição de `limpar_caracteristicas`."""
    automacao = _automacao([[_Linha("1 - A", vazia=True),
                             _Linha("2 - B", vazia=True),
                             _Linha("3 - C", vazia=True)]])

    apagadas = automacao.apagar_em_branco_fora_do_json({})

    assert sorted(apagadas) == ["A", "B", "C"]


def test_exclusao_que_falha_nao_trava_o_laco():
    """Um portal que recusa a exclusão não pode fazer o robô girar para
    sempre na mesma linha."""
    automacao = _automacao([[_Linha("1 - A", vazia=True)]], apaga=False)

    apagadas = automacao.apagar_em_branco_fora_do_json({})

    assert apagadas == []


def test_tabela_sem_nada_a_apagar_nao_mexe_em_nada():
    automacao = _automacao([[_Linha("1 - A", vazia=False)]])

    assert automacao.apagar_em_branco_fora_do_json({"A": {}}) == []


# =============================================================================
# C. O SALVAR e a mensagem do portal
# =============================================================================
class _PortalQueSalva:
    """Sucessos e avisos vêm SEPARADOS, como no portal: o de sucesso some
    sozinho (`feedback-message-autoclose`), o de aviso fica."""

    def __init__(self, confirma, mensagens=(), avisos=()):
        self.confirma = confirma
        self.mensagens = list(mensagens)
        self.avisos = list(avisos)
        self.salvou = 0

    def salvar_e_confirmar(self, *_a, **_kw):
        self.salvou += 1
        return self.confirma

    def _mensagens_de_feedback(self, so_sucesso=False, seletor=None):
        return list(self.mensagens)

    def mensagens_de_aviso(self):
        return list(self.avisos)


def test_salvamento_confirmado_devolve_OK():
    automacao = _automacao([[]])
    automacao.portal = _PortalQueSalva(
        True, ["As características técnicas foram salvas com sucesso!"])

    ok, mensagem = automacao.salvar_caracteristicas()

    assert ok is True
    assert "sucesso" in mensagem.lower()


def test_o_aviso_do_portal_volta_no_resultado():
    """*"Por favor, verifique os campos"* é o que a pessoa precisa ver para
    saber que aquela ficha pede a mão dela."""
    automacao = _automacao([[]])
    automacao.portal = _PortalQueSalva(False, avisos=["Por favor, verifique os campos"])

    ok, mensagem = automacao.salvar_caracteristicas()

    assert ok is False
    assert mensagem == "Por favor, verifique os campos"


def test_sem_toast_nenhum_tambem_e_falha_declarada():
    """Silêncio do portal não pode virar "salvou". A ficha fica para a
    conferência manual como qualquer outra que não confirmou."""
    automacao = _automacao([[]])
    automacao.portal = _PortalQueSalva(False, [])

    ok, mensagem = automacao.salvar_caracteristicas()

    assert ok is False
    assert mensagem == ""


def test_o_salvar_usa_a_ANCORA_da_secao_de_caracteristicas():
    """Sem âncora, `salvar_e_confirmar` varre a tela atrás de um botão
    "SALVAR" -- e a ficha tem um por seção. É o defeito de 2026-08-20."""
    registradas = {}
    automacao = _automacao([[]])

    class _Espiao(_PortalQueSalva):
        def salvar_e_confirmar(self, *a, **kw):
            registradas.update(kw)
            return True

    automacao.portal = _Espiao(True)
    automacao.salvar_caracteristicas()

    assert "TechnicalCharacteristics" in str(registradas.get("ancora", ""))


# =============================================================================
# D. O seletor do aviso, contra o HTML que o usuário mandou
# =============================================================================
def test_o_seletor_do_aviso_casa_o_html_real_do_portal():
    etree = pytest.importorskip("lxml.etree", reason="lxml e opcional")
    from sigft.core.rpa import portal as portal_mod

    html = (
        '<html><body>'
        '<div class="feedback-message feedback-message-success feedback-message-autoclose"'
        ' tabindex="0" role="alert"><i></i>'
        '<div class="feedback-message-text">As características técnicas foram salvas com sucesso!</div></div>'
        '<div class="feedback-message feedback-message-warning" tabindex="0" role="alert"><i></i>'
        '<div class="feedback-message-text">Por favor, verifique os campos</div></div>'
        '</body></html>'
    )
    doc = etree.fromstring(html, etree.HTMLParser(encoding="utf-8"))

    avisos = doc.xpath(portal_mod.XPATH_MENSAGEM_DE_AVISO)
    sucessos = doc.xpath(portal_mod.XPATH_MENSAGEM_DE_SUCESSO)

    assert [("".join(x.itertext())).strip() for x in avisos] == [
        "Por favor, verifique os campos"]
    assert [("".join(x.itertext())).strip() for x in sucessos] == [
        "As características técnicas foram salvas com sucesso!"]


def test_o_seletor_do_aviso_nao_pega_o_de_SUCESSO():
    """Confundir os dois faria a ficha salva virar pendência manual, e a
    ficha que falhou passar batido."""
    from sigft.core.rpa import portal as portal_mod

    assert "feedback-message-warning" in portal_mod.XPATH_MENSAGEM_DE_AVISO
    assert "feedback-message-success" not in portal_mod.XPATH_MENSAGEM_DE_AVISO


# =============================================================================
# E. QUAIS características travaram o salvamento (2026-09-23, 2º recorte)
# =============================================================================
# O usuário mandou o HTML de um campo recusado: o `<textarea>` ganha a classe
# `not-valid` e nasce embaixo dele um
# `<span class="text-error">Caracter inválido!</span>`.
#
# Isso transforma o "Por favor, verifique os campos" (que não diz nada) na
# lista exata do que corrigir -- e, numa linha `CHAR`, em QUAL dos dois
# idiomas, porque o aviso aparece embaixo de cada um separadamente.
_HTML_COM_ERRO = """
<html><body><div id="b10-TechnicalCharacteristics_Content"><table><tbody>
<tr class="table-row">
  <td data-header="Descrição"><span data-expression="">1650 - COMPONENTES</span></td>
  <td data-header="Valor ES/PT"><div data-container=""><div data-container=""><div data-container="">ES:</div><span><textarea data-textarea="" class="form-control text-uppercase" required="" rows="3" maxlength="1000" id="b10-b13-l3_0-331_28-TextArea_ValueES">BOMBA</textarea></span></div><div data-container=""><div data-container="">PT:</div><span><textarea data-textarea="" class="form-control text-uppercase" required="" rows="3" maxlength="1000" id="b10-b13-l3_0-331_28-TextArea_ValuePT">BOMBA</textarea></span></div></div></td>
</tr>
<tr class="table-row">
  <td data-header="Descrição"><span data-expression="">8267 - CERTIFICADO</span></td>
  <td data-header="Valor ES/PT"><div data-container=""><div data-container=""><div data-container="">ES:</div><span><textarea data-textarea="" class="form-control text-uppercase not-valid" required="" rows="3" maxlength="1000" id="b10-b13-l3_0-331_29-TextArea_ValueES">CERRADOã</textarea></span><div data-block="Utils.RequiredFieldInput_Warning" class="OSBlockWidget" id="b10-b13-l3_0-331_29-$b12"><div data-container=""><div data-container=""><span data-expression="" class="text-error">Caracter inválido!</span></div></div></div><div data-block="Utils.SAPLimitationInput_Warning" class="OSBlockWidget" id="b10-b13-l3_0-331_29-$b13"><div data-container=""></div></div></div><div data-container=""><div data-container="">PT:</div><span><textarea data-textarea="" class="form-control text-uppercase not-valid" required="" rows="3" maxlength="1000" id="b10-b13-l3_0-331_29-TextArea_ValuePT">FECHADOaã</textarea></span><div data-block="Utils.RequiredFieldInput_Warning" class="OSBlockWidget" id="b10-b13-l3_0-331_29-$b14"><div data-container=""><div data-container=""><span data-expression="" class="text-error">Caracter inválido!</span></div></div></div><div data-block="Utils.SAPLimitationInput_Warning" class="OSBlockWidget" id="b10-b13-l3_0-331_29-$b15"><div data-container=""></div></div></div></div></td>
</tr>
</tbody></table></div></body></html>
"""


class _MotorSobreHtml:
    """Interpreta XPath de verdade sobre o recorte acima."""

    def __init__(self, html):
        etree = pytest.importorskip("lxml.etree")
        self.etree = etree
        self.doc = etree.fromstring(html, etree.HTMLParser(encoding="utf-8"))

    def contar(self, seletor):
        return len(self.doc.xpath(seletor))

    def element_exists(self, seletor):
        return self.contar(seletor) > 0

    def esta_habilitado(self, _seletor):
        return False

    def click_raw(self, _seletor):
        pass

    def texto(self, seletor):
        achados = self.doc.xpath(seletor)
        return "".join(achados[0].itertext()) if achados else ""

    def get_value(self, seletor):
        achados = self.doc.xpath(seletor)
        if not achados:
            return ""
        no = achados[0]
        return "".join(no.itertext()) if no.tag == "textarea" else (no.get("value") or "")

    def texto_selecionado(self, _seletor):
        return ""

    def scroll_to(self, _seletor):
        pass


def _automacao_sobre_html():
    automacao = tech_specs.TechSpecsAutomation()
    automacao.engine = _MotorSobreHtml(_HTML_COM_ERRO)
    return automacao


def test_aponta_a_caracteristica_que_travou_o_salvamento():
    """*"Todas as características que tiver isso embaixo vai indicar que tem
    algum erro que deve ser checado"*."""
    achados = _automacao_sobre_html().caracteristicas_com_erro()

    assert [x["chave"] for x in achados] == ["CERTIFICADO"]


def test_a_linha_SEM_erro_nao_entra_na_lista():
    """A primeira linha do recorte está válida. Listá-la mandaria a pessoa
    conferir um campo que está certo."""
    achados = _automacao_sobre_html().caracteristicas_com_erro()

    assert "COMPONENTES" not in [x["chave"] for x in achados]


def test_diz_a_MENSAGEM_que_o_portal_deu():
    achados = _automacao_sobre_html().caracteristicas_com_erro()

    assert achados[0]["mensagem"] == "Caracter inválido!"


def test_diz_em_QUAL_IDIOMA_esta_o_problema():
    """*"Se for CHAR e tiver coisas incorretas no espanhol e PT, vai aparecer
    embaixo de cada um."* Numa ficha bilíngue, saber qual dos dois poupa
    procurar nos dois."""
    achados = _automacao_sobre_html().caracteristicas_com_erro()

    assert achados[0]["campos"] == ["PT", "ES"]


def test_o_marcador_do_campo_invalido_e_a_CLASSE_e_nao_o_texto():
    """A mensagem muda conforme o motivo ("Caracter inválido!", limite do SAP,
    campo obrigatório...). A classe `not-valid` no campo e a `text-error` no
    span são o que não muda."""
    fonte = tech_specs.XPATH_REL_CAMPO_INVALIDO + tech_specs.XPATH_REL_ERRO_DO_CAMPO

    assert "not-valid" in fonte
    assert "text-error" in fonte
    assert "Caracter" not in fonte

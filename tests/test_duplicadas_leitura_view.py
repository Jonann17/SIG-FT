r"""
Leitura da ficha original em modo de VISUALIZAÇÃO (CP 6.2).

O HTML aqui **é o do portal real**, colado pelo usuário em 2026-08-11 — não é
markup inventado para o teste passar. É o que torna estes testes uma prova de
que a estratégia funciona, e não uma prova de que ela é internamente
consistente.

A estratégia: a tela de visualização repete a mesma estrutura para todo campo
(um `<label>` e, logo depois, um bloco `PMIB_DataSheetView.Block_Expression`
com o valor). Não há id ligando os dois — o que liga é a **ordem de documento**.
Por isso o extrator faz UMA varredura pedindo rótulos e valores juntos, e o
pareamento acontece em `parear_rotulos_e_valores`, testado abaixo.

Duas varreduras separadas obrigariam a casar por índice, e bastaria um campo
sem valor para desalinhar tudo dali para baixo — erro que produz ficha
plausível e errada.

`lxml` não existe neste ambiente, então o HTML é lido com `html.parser` da
stdlib, reproduzindo o que os XPaths selecionam. O que se prova é a REGRA de
pareamento, que é onde a lógica pode errar.
"""
from html.parser import HTMLParser

import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services.duplicadas_spec import parear_rotulos_e_valores


# --- HTML REAL do portal, bloco "Volume (cm3)" ------------------------------
HTML_REAL = '''
<div data-block="Widgets.Fieldset" class="OSBlockWidget" id="b12-b20-b1-$b2"><fieldset
 data-advancedhtml=""><legend data-advancedhtml=""><div id="b12-b20-b1-b2-Legend"><span
 class="text-primary font-size-base">Volume (cm3)</span></div></legend><div
 id="b12-b20-b1-b2-Content"><div data-container="" id="b12-b20-b1-Volume"><div
 data-container="" class="margin-top-s"><div data-container=""><label data-label=""
 class="OSFillParent"><span class="text-primary">Comprimento da embalagem unitária</span></label><div
 data-container="" class="margin-top-s"><div data-block="PMIB_DataSheetView.Block_Expression"
 class="OSBlockWidget" id="b12-b20-b1-$b3"><span data-expression="">6</span></div></div></div><div
 data-container=""><label data-label="" class="OSFillParent"><span
 class="text-primary">Largura da embalagem unitária</span></label><div data-container=""
 class="margin-top-s"><div data-block="PMIB_DataSheetView.Block_Expression"
 class="OSBlockWidget" id="b12-b20-b1-$b4"><span data-expression="">6</span></div></div></div><div
 data-container=""><label data-label="" class="OSFillParent"><span
 class="text-primary">Altura da embalagem unitária</span></label><div data-container=""
 class="margin-top-s"><div data-block="PMIB_DataSheetView.Block_Expression"
 class="OSBlockWidget" id="b12-b20-b1-$b5"><span data-expression="">5</span></div></div></div></div></div></fieldset></div>
'''


class _LeitorDaTela(HTMLParser):
    """Reproduz o que os XPaths do modo de visualização selecionam: os `<span>`
    dentro de `<label data-label>` (rótulos) e os `<span data-expression>`
    dentro de um bloco `Block_Expression` (valores), em ordem de documento."""

    def __init__(self):
        super().__init__()
        self.tokens = []
        self._dentro_de_label = 0
        self._dentro_de_expressao = 0
        self._coletando = None
        self.legendas = []
        self._dentro_de_legend = 0

    def handle_starttag(self, tag, atributos):
        attrs = dict(atributos)
        if tag == "label" and "data-label" in attrs:
            self._dentro_de_label += 1
        elif tag == "legend":
            self._dentro_de_legend += 1
        elif tag == "div" and attrs.get("data-block") == "PMIB_DataSheetView.Block_Expression":
            self._dentro_de_expressao += 1
        elif tag == "span":
            if self._dentro_de_legend:
                self._coletando = "legenda"
            elif self._dentro_de_label:
                self._coletando = "rotulo"
            elif self._dentro_de_expressao and "data-expression" in attrs:
                self._coletando = "valor"

    def handle_endtag(self, tag):
        if tag == "label" and self._dentro_de_label:
            self._dentro_de_label -= 1
        elif tag == "legend" and self._dentro_de_legend:
            self._dentro_de_legend -= 1
        elif tag == "div" and self._dentro_de_expressao:
            self._dentro_de_expressao -= 1
        elif tag == "span":
            self._coletando = None

    def handle_data(self, dados):
        if self._coletando == "legenda":
            self.legendas.append(dados.strip())
        elif self._coletando in ("rotulo", "valor"):
            self.tokens.append((self._coletando, dados))


def _ler(html):
    leitor = _LeitorDaTela()
    leitor.feed(html)
    return leitor


# ===========================================================================
# A estratégia funciona no HTML real
# ===========================================================================
def test_o_bloco_real_vira_tres_pares_rotulo_valor():
    """A prova principal: markup do portal, sem adaptação, produz exatamente os
    campos da tela."""
    leitor = _ler(HTML_REAL)

    assert parear_rotulos_e_valores(leitor.tokens) == {
        "Comprimento da embalagem unitária": "6",
        "Largura da embalagem unitária": "6",
        "Altura da embalagem unitária": "5",
    }


def test_o_titulo_do_bloco_sai_da_legend():
    """"Volume (cm3)" é o nome do agrupamento -- não é campo, e não pode virar
    par. Vem da `<legend>`, num seletor separado."""
    assert _ler(HTML_REAL).legendas == ["Volume (cm3)"]


def test_o_titulo_do_bloco_nao_entra_como_rotulo_nem_como_valor():
    tokens = _ler(HTML_REAL).tokens

    assert not any("Volume" in texto for _tipo, texto in tokens)


def test_nenhum_id_gerado_e_necessario_para_ler_o_bloco():
    """`b12-b20-b1-$b3`/`$b4`/`$b5` são sequenciais e inúteis. A leitura usa
    `data-label`, `data-expression` e o nome do bloco -- todos semânticos."""
    for nome in ("XPATH_VIEW_ROTULO", "XPATH_VIEW_VALOR", "XPATH_VIEW_ROTULOS_E_VALORES"):
        valor = getattr(sel, nome)
        assert "$b" not in valor
        assert "b12-b20" not in valor


def test_o_sequencial_de_bloco_entrou_na_lista_de_ids_proibidos():
    assert "-$b" in sel.IDS_GERADOS_NAO_USAR


def test_a_consulta_unica_pede_rotulos_e_valores_juntos():
    """Um `|` de XPath devolve em ordem de documento, que é o que o pareamento
    precisa. Duas varreduras separadas obrigariam a casar por índice, e um
    campo sem valor desalinharia tudo dali para baixo."""
    assert " | " in sel.XPATH_VIEW_ROTULOS_E_VALORES
    assert sel.XPATH_VIEW_ROTULO in sel.XPATH_VIEW_ROTULOS_E_VALORES
    assert sel.XPATH_VIEW_VALOR in sel.XPATH_VIEW_ROTULOS_E_VALORES


# ===========================================================================
# A regra de pareamento, nos casos que a tela real produz
# ===========================================================================
def test_campo_em_branco_vira_string_vazia_e_nao_some():
    """Sumir seria pior: o injetor não saberia distinguir "não existe esse
    campo" de "existe e está vazio", e o segundo caso é informação."""
    tokens = [("rotulo", "Peso líquido"), ("rotulo", "Peso bruto"), ("valor", "1,15")]

    assert parear_rotulos_e_valores(tokens) == {"Peso líquido": "", "Peso bruto": "1,15"}


def test_valor_sem_rotulo_antes_e_descartado():
    """Acontece com texto solto no bloco. Atribuí-lo ao rótulo SEGUINTE
    inverteria o pareamento de toda a aba dali para baixo."""
    tokens = [("valor", "orfao"), ("rotulo", "Peso"), ("valor", "1")]

    assert parear_rotulos_e_valores(tokens) == {"Peso": "1"}


def test_rotulo_repetido_fica_com_o_primeiro_valor():
    tokens = [("rotulo", "Peso"), ("valor", "1"), ("rotulo", "Peso"), ("valor", "2")]

    assert parear_rotulos_e_valores(tokens) == {"Peso": "1"}


def test_espaco_e_quebra_de_linha_do_html_sao_normalizados():
    # O markup do portal tem indentação farta dentro dos spans.
    tokens = [("rotulo", "\n   Peso   líquido \n"), ("valor", "  1,15\n ")]

    assert parear_rotulos_e_valores(tokens) == {"Peso líquido": "1,15"}


def test_rotulo_vazio_e_ignorado():
    tokens = [("rotulo", "   "), ("valor", "1"), ("rotulo", "Peso"), ("valor", "2")]

    assert parear_rotulos_e_valores(tokens) == {"Peso": "2"}


def test_sequencia_vazia_devolve_dicionario_vazio():
    assert parear_rotulos_e_valores([]) == {}


@pytest.mark.parametrize("valor_bruto", [None, ""])
def test_valor_nulo_nao_derruba(valor_bruto):
    assert parear_rotulos_e_valores([("rotulo", "X"), ("valor", valor_bruto)]) == {"X": ""}

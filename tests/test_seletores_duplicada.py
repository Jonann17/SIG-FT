r"""
Seletores da ficha duplicada, levantados do DOM real do portal (2026-08-11).

Estes testes não conferem o portal — nenhum teste offline pode. O que eles
travam é a DISCIPLINA que evitou duas quebras futuras: dois dos três
componentes têm ids parcialmente GERADOS, e amarrar o seletor a eles funciona
na sessão em que se inspecionou o elemento e falha na seguinte, com "elemento
não encontrado" que parece mudança de portal e não é.

É o tipo de erro que só se evita antes de acontecer.
"""
import pytest

from sigft.core.rpa import inventario, seletores_duplicada as sel


# ===========================================================================
# A armadilha: nenhum seletor pode conter id gerado
# ===========================================================================
def _todos_os_seletores():
    return [
        (nome, valor) for nome, valor in vars(sel).items()
        if nome.startswith("XPATH") and isinstance(valor, str)
    ]


@pytest.mark.parametrize("fragmento", sel.IDS_GERADOS_NAO_USAR)
def test_nenhum_seletor_usa_id_gerado(fragmento):
    """`filepond--browser-h1d4zvekk` e `vscomp-search-input-3940` têm sufixo
    aleatório/sequencial. O id aparece no inspecionar elemento, parece o
    seletor mais preciso possível, e funciona na primeira tentativa -- a falha
    vem depois."""
    for nome, valor in _todos_os_seletores():
        assert fragmento not in valor, f"{nome} amarra um id gerado: {valor}"


def test_a_lista_de_ids_gerados_cobre_os_dois_widgets():
    # Serve de documentação executável: se aparecer um terceiro widget com id
    # gerado, ele entra aqui antes de virar seletor.
    assert any("filepond" in f for f in sel.IDS_GERADOS_NAO_USAR)
    assert any("vscomp" in f for f in sel.IDS_GERADOS_NAO_USAR)


def test_todo_seletor_e_um_xpath():
    for nome, valor in _todos_os_seletores():
        assert valor.startswith(("//", "(", ".")), f"{nome} não parece XPath: {valor}"


# ===========================================================================
# Casamento de classe pelo caminho seguro
# ===========================================================================
@pytest.mark.parametrize("nome", [
    "XPATH_FABRICANTE_TOGGLE", "XPATH_FABRICANTE_VALOR", "XPATH_FABRICANTE_BUSCA",
    "XPATH_IMAGENS_INPUT_ARQUIVO", "XPATH_DOCUMENTOS_LUPA",
])
def test_classe_e_casada_pela_lista_inteira_e_nao_por_substring(nome):
    """`contains(@class, 'vscomp-value')` casaria também
    `vscomp-value-outra-coisa`. O truque do `concat` com espaços em volta exige
    a classe INTEIRA na lista -- é o mesmo padrão que `cria_fichas` usa no
    `XPATH_PDM_FINAL`, já validado contra o portal."""
    valor = getattr(sel, nome)

    assert "concat(' ', normalize-space(@class), ' ')" in valor


def test_o_input_de_arquivo_e_ancorado_no_container_estavel():
    """Duas âncoras: o container do OutSystems (id estável, `MultiUploadContainer`)
    e a classe do FilePond. Só a classe casaria um FilePond de outra parte da
    tela, se houver."""
    valor = sel.XPATH_IMAGENS_INPUT_ARQUIVO

    assert "MultiUploadContainer" in valor
    assert "@type='file'" in valor


def test_os_campos_de_descricao_ignoram_o_prefixo_de_bloco():
    """`b10-b15-` é o caminho do bloco na tela do OutSystems e muda se alguém
    reorganizar o formulário. O sufixo é o que nomeia o campo."""
    for valor in (sel.XPATH_IMAGENS_DESCRICAO_ES, sel.XPATH_IMAGENS_DESCRICAO_PT):
        assert "contains(@id," in valor
        assert "b10-b15" not in valor


def test_es_e_pt_sao_seletores_distintos():
    # Trocar os dois escreveria a descrição no idioma errado -- erro que passa
    # despercebido porque o texto é o mesmo nos dois campos hoje.
    assert sel.XPATH_IMAGENS_DESCRICAO_ES != sel.XPATH_IMAGENS_DESCRICAO_PT
    assert "ES" in sel.XPATH_IMAGENS_DESCRICAO_ES
    assert "PT" in sel.XPATH_IMAGENS_DESCRICAO_PT


# ===========================================================================
# Formatos aceitos
# ===========================================================================
def test_os_formatos_aceitos_saem_do_accept_do_proprio_input():
    """O input declara `accept="image/jpeg,image/png"`. Uma imagem baixada em
    webp ou gif seria recusada pelo portal no envio."""
    assert set(sel.FORMATOS_DE_IMAGEM_ACEITOS) == {".jpg", ".jpeg", ".png"}


# ===========================================================================
# Os seletores com marcador de texto
# ===========================================================================
@pytest.mark.parametrize("nome", ["XPATH_FABRICANTE_OPCAO", "XPATH_DOCUMENTOS_LINHA"])
def test_seletores_parametrizados_declaram_o_marcador(nome):
    # São formatados pelo consumidor; sem o marcador, alguém concatenaria à
    # mão e o escape de aspas voltaria a ser problema (o `5' 1/2"` do CP 5.3).
    assert "{texto}" in getattr(sel, nome)


# ===========================================================================
# Integração com o inventário
# ===========================================================================
def test_o_inventario_enxerga_estes_seletores():
    """O `scripts/auditar_seletores.py` só confere o que está no inventário.
    Seletor novo fora dele é seletor invisível à auditoria quando o portal
    mudar."""
    modulos = {m for m, _n, _s, _r in inventario.coletar()}

    assert "sigft.core.rpa.seletores_duplicada" in modulos


def test_estes_seletores_nao_sao_relativos():
    # Nenhum é fragmento de linha de tabela, então todos podem ser conferidos
    # sozinhos contra a página pela auditoria.
    achados = [
        (n, r) for m, n, _s, r in inventario.coletar()
        if m == "sigft.core.rpa.seletores_duplicada"
    ]

    assert achados
    assert not any(relativo for _nome, relativo in achados)

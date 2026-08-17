r"""
Seletores da ficha duplicada, levantados do DOM real do portal (2026-08-11).

Estes testes não conferem o portal — nenhum teste offline pode. O que eles
travam é a DISCIPLINA que evitou duas quebras futuras: dois dos três
componentes têm ids parcialmente GERADOS, e amarrar o seletor a eles funciona
na sessão em que se inspecionou o elemento e falha na seguinte, com "elemento
não encontrado" que parece mudança de portal e não é.

É o tipo de erro que só se evita antes de acontecer.
"""
import re

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


def _literais_de_id(seletor):
    """Os textos com que o seletor compara `@id`.

    Casa as duas formas que aparecem aqui: `@id='x'` e `contains(@id, 'x')`.
    Olhar SÓ para comparações de id (em vez de procurar o fragmento no seletor
    inteiro) é o que evita um falso positivo real: a classe
    `vscomp-option-text` contém o prefixo de id proibido `vscomp-option-`, e é
    uma classe perfeitamente legítima. A primeira versão deste teste reprovou
    justamente por isso -- o guarda tem de ser tão preciso quanto a regra que
    ele defende.
    """
    return re.findall(r"@id\s*(?:=|,)\s*'([^']*)'", seletor)


@pytest.mark.parametrize("fragmento", sel.IDS_GERADOS_NAO_USAR)
def test_nenhum_seletor_compara_id_com_fragmento_gerado(fragmento):
    """`filepond--browser-h1d4zvekk`, `vscomp-search-input-3940`,
    `vscomp-option-3940-1625` e `…-l1_0-521_0-…` têm sufixo
    aleatório/sequencial. O id aparece no inspecionar elemento, parece o
    seletor mais preciso possível, e funciona na primeira tentativa -- a falha
    vem depois, noutra sessão, parecendo mudança de portal."""
    for nome, valor in _todos_os_seletores():
        for literal in _literais_de_id(valor):
            assert fragmento not in literal, (
                f"{nome} compara @id com {literal!r}, que contém o fragmento "
                f"gerado {fragmento!r}"
            )


def test_o_guarda_de_id_gerado_realmente_pega_uma_violacao():
    """Contraprova do teste acima: sem ela, um guarda que não encontrasse nada
    passaria por vácuo e ninguém saberia."""
    violacao = "//input[contains(@id, 'vscomp-search-input-3940')]"

    assert "vscomp-search-input-3940" in _literais_de_id(violacao)


def test_o_guarda_nao_confunde_classe_com_id():
    """A classe `vscomp-option-text` contém o prefixo de id proibido. Se o
    guarda olhasse o seletor inteiro, reprovaria um seletor correto -- foi o
    que aconteceu na primeira versão."""
    por_classe = (
        "//span[contains(concat(' ', normalize-space(@class), ' '), "
        "' vscomp-option-text ')]"
    )

    assert _literais_de_id(por_classe) == []


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


# ===========================================================================
# Segunda rodada de HTML real (2026-08-11): opção do combo, checkbox da linha,
# campo de referência, abas de status e a coluna Ações
# ===========================================================================
def test_a_opcao_do_combo_casa_pelo_data_tooltip_e_nao_pelo_texto():
    """O HTML da opção tem quebras de linha e espaços em volta do nome
    (`\\n            SCHNEIDER\\n          `). O `data-tooltip` traz o nome
    EXATO, sem isso."""
    valor = sel.XPATH_FABRICANTE_OPCAO

    assert "@data-tooltip={texto}" in valor
    assert "normalize-space(.)={texto}" not in valor


def test_a_opcao_do_combo_ancora_no_role_option():
    """Âncora semântica: sobrevive a mudança de classe do widget, que é o que
    uma atualização de biblioteca faz."""
    assert "@role='option'" in sel.XPATH_FABRICANTE_OPCAO


def test_o_checkbox_do_documento_ancora_no_cabecalho_da_coluna():
    """`id="b10-b15-b19-l1_0-521_0-Checkbox1"` traz o índice da LINHA, que muda
    a cada busca. `@data-header='Selecionar'` é escrito por quem desenhou a
    tela -- e é o mesmo atributo que `tech_specs` já usa."""
    valor = sel.XPATH_DOCUMENTOS_CHECKBOX_DA_LINHA

    assert "@data-header='Selecionar'" in valor
    assert "521" not in valor


def test_o_indice_de_linha_do_outsystems_esta_na_lista_de_ids_proibidos():
    # `-l1_0-` aparece em DUAS telas diferentes (checkbox do documento e coluna
    # Ações da lista de fichas), então é padrão, não coincidência.
    assert "-l1_0-" in sel.IDS_GERADOS_NAO_USAR


def test_o_campo_de_referencia_ancora_no_rotulo_e_nao_so_no_id():
    """`Input_TextVar` é nome GENÉRICO -- "input de variável de texto" --, não
    identifica o campo de Referência e provavelmente existe em outros pontos da
    tela. O rótulo é o que a pessoa lê e o que muda junto se o campo mudar de
    sentido."""
    valor = sel.XPATH_REFERENCIA_INPUT

    assert "Referência" in valor
    assert "Input_TextVar" in valor


def test_o_aviso_de_colisao_tem_seletor_proprio():
    """O achado da rodada: a mensagem "A referência já existe!" não é texto
    solto -- tem bloco com id semântico (`CoincidenceReference`). Varrer a tela
    atrás da frase seria frágil em idioma, redação e escopo."""
    assert "CoincidenceReference" in sel.XPATH_REFERENCIA_AVISO_COLISAO


def test_a_deteccao_por_bloco_nao_substitui_a_deteccao_por_texto():
    """As duas se somam: o bloco é o caminho estável, a frase é a rede para o
    caso de a mensagem vir por outro caminho. Se um dia só uma existir, a
    colisão passa despercebida e a referência sai errada."""
    from sigft.services import duplicadas_spec

    assert hasattr(duplicadas_spec, "e_erro_de_referencia_repetida")
    assert hasattr(sel, "XPATH_REFERENCIA_AVISO_COLISAO")


@pytest.mark.parametrize("nome", ["XPATH_ACAO_VISUALIZAR", "XPATH_ACAO_EDITAR"])
def test_as_acoes_exigem_o_sufixo_do_id_E_o_icone(nome):
    """Cada um sozinho já apareceu como armadilha: o id é parcialmente gerado,
    e `fa-pencil-square-o` é o MESMO ícone do lápis de `cria_fichas`, em outra
    tela. Exigir os dois torna o casamento inequívoco."""
    valor = getattr(sel, nome)

    assert "contains(@id," in valor
    assert "fa-" in valor


def test_visualizar_e_editar_sao_seletores_distintos():
    # Confundi-los abriria a ficha em EDIÇÃO, onde os valores são campos e não
    # texto -- o extrator não acharia nada e devolveria ficha vazia sem erro.
    assert sel.XPATH_ACAO_VISUALIZAR != sel.XPATH_ACAO_EDITAR
    assert "fa-file-o" in sel.XPATH_ACAO_VISUALIZAR
    assert "fa-pencil-square-o" in sel.XPATH_ACAO_EDITAR


def test_as_acoes_sao_relativas_a_linha():
    # Começam com `.` porque são concatenadas ao seletor da linha -- a lista
    # tem uma coluna Ações por ficha, e um `//` pegaria a primeira da tela.
    assert sel.XPATH_ACAO_VISUALIZAR.startswith(".")
    assert sel.XPATH_ACAO_EDITAR.startswith(".")


def test_a_aba_de_status_tem_seletor_de_contagem():
    """O badge permite pular direto para a aba com contagem > 0, em vez de
    abrir as 7 atrás da ficha."""
    assert "{texto}" in sel.XPATH_ABA_STATUS
    assert "badge" in sel.XPATH_ABA_STATUS_CONTAGEM

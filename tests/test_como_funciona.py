"""Os textos do "Como funciona" (2026-10-28): um por tela do menu, e um por aba
nas seções em que cada aba tem regra própria. Sem Qt.

Desenho: `docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`, parte 1.
"""
from __future__ import annotations

import pytest

from _idioma import em_idioma
from sigft.app import como_funciona, idioma
from sigft.app_qt import catalogo

TELAS_DO_MENU = [alvo for alvo, _titulo, _descricao in catalogo.MODULOS]


def _todas_as_chaves() -> list[str]:
    return [chave for tela in TELAS_DO_MENU for chave in como_funciona.chaves_da_tela(tela)]


def test_as_15_telas_do_menu_tem_texto():
    # 2026-10-30: o Upload de Fotos é a 13ª; 2026-11-04: Conferência de Listas e DocPack.
    assert len(TELAS_DO_MENU) == 15
    faltando = [chave for chave in _todas_as_chaves() if chave not in como_funciona.TEXTOS]
    assert faltando == []


def test_nenhum_texto_sobra():
    # Texto de tela que saiu do menu (ou de aba renomeada) não fica esquecido aqui.
    assert set(como_funciona.TEXTOS) == set(_todas_as_chaves())


def test_secoes_de_abas_sao_telas_do_menu():
    assert set(como_funciona.ABAS_DAS_SECOES) <= set(TELAS_DO_MENU)
    assert como_funciona.chaves_da_tela("LMR") == ("LMR.upload", "LMR.exclusao")
    assert como_funciona.chaves_da_tela("Translator") == ("Translator",)


@pytest.mark.parametrize("chave", sorted(como_funciona.TEXTOS))
def test_frase_e_de_3_a_6_itens(chave):
    texto = como_funciona.TEXTOS[chave]
    assert texto.frase.strip()
    assert como_funciona.MINIMO_DE_ITENS <= len(texto.itens) <= como_funciona.MAXIMO_DE_ITENS
    assert all(item.strip() for item in texto.itens)


@pytest.mark.parametrize("codigo", ["pt", "es", "en"])
def test_nenhum_item_passa_de_140_caracteres(codigo):
    with em_idioma(codigo):
        longos = {}
        for chave in como_funciona.TEXTOS:
            texto = como_funciona.traduzido(chave)
            for parte in (texto.frase, *texto.itens):
                if len(parte) > como_funciona.LIMITE_DO_ITEM:
                    longos[parte[:40]] = len(parte)
    assert longos == {}


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_tudo_traduzido(codigo):
    catalogo_do_idioma = idioma.catalogo(codigo)
    sem_traducao = [parte for texto in como_funciona.TEXTOS.values() for parte in (texto.frase, *texto.itens)
                    if not catalogo_do_idioma.get(parte)]
    assert sem_traducao == []


def test_traduzido_segue_o_idioma():
    chave = "Translator"
    original = como_funciona.TEXTOS[chave]
    assert como_funciona.traduzido(chave) == original
    with em_idioma("es"):
        em_espanhol = como_funciona.traduzido(chave)
    assert em_espanhol.frase == idioma.catalogo("es")[original.frase]
    assert len(em_espanhol.itens) == len(original.itens)


def test_chave_da_preferencia_por_tela():
    assert como_funciona.chave_da_preferencia("CriaFichas") == "como_funciona_aberto.CriaFichas"
    assert como_funciona.chave_da_preferencia("LMR.upload") == "como_funciona_aberto.LMR.upload"


def test_lmr_retoma_pela_posicao_e_diz_onde_fica_o_csv():
    # O campo de inicio recebe a POSICAO (int, grupos de codigos LMR contados
    # de 0, `LMRAutomation._resolver_linha_inicial`), nao um codigo LMR. O
    # erros_lmr.csv mora na pasta de logs desde 2026-10-30 (antes saia
    # relativo ao cwd, e o texto nao podia prometer onde).
    from sigft.services import lmr

    itens = como_funciona.TEXTOS["LMR.upload"].itens
    retomar = next(item for item in itens if item.startswith("Parou no meio?"))
    assert "posição" in retomar and "0 =" in retomar
    assert "todas as fichas" in retomar
    csv = next(item for item in itens if "erros_lmr.csv" in item)
    assert lmr.ARQUIVO_ERROS_LMR in csv
    assert "Documentos\\SIG-FT\\logs" in csv


def test_analyzer_relatorio_do_fornecedor_sai_pelo_botao():
    itens = como_funciona.TEXTOS["Analyzer"].itens
    assert any("GERAR RELATÓRIO PARA O FORNECEDOR (.xlsx)" in item for item in itens)
    assert not any(item.startswith("No fim") for item in itens)

r"""O RETRATO das características, em disco (E2 do plano).

POR QUE ELE EXISTE, e por que grava ANTES
------------------------------------------------------------------------
Trocar o PDM faz o portal apagar todas as características. **Depois do
CONFIRMAR, o dado não existe mais em lugar nenhum** — nem no portal, nem na
planilha. Se o robô morrer entre a troca e a reposição, um retrato que
estivesse só na memória morre junto, e a ficha fica vazia.

Por isso o retrato vai para o DISCO antes da troca, e por isso `gravar`
**levanta** em vez de engolir o erro: ao contrário de `pasta_logs()`, aqui uma
gravação que falhou em silêncio seria autorização para destruir o original.

Ele também é o que permite o modo **"só repor"**: se algo der errado depois da
troca, a reposição roda de novo a partir do arquivo, sem refazer nada.

Plano completo em `docs/refatoracao/CORRECAO_PDM.md`.
"""
from __future__ import annotations

import json

import pytest

from sigft.core.rpa.caracteristicas import Caracteristica
from sigft.services import correcao_pdm_retrato as retrato


@pytest.fixture(autouse=True)
def _pasta_isolada(tmp_path, monkeypatch):
    """Cada teste grava na sua própria pasta -- nunca em `Documentos`."""
    monkeypatch.setattr(retrato.dados_usuario, "pasta_dados", lambda: tmp_path)


def _caracteristicas():
    return [
        Caracteristica(codigo="1171", nome="ACABAMENTO", tipo="CHAR",
                       valor_pt="PINTADO", valor_es="PINTADO", unidade="AD"),
        Caracteristica(codigo="1230", nome="TENSAO NOMINAL", tipo="NUM",
                       valor_pt="220", unidade="V"),
        Caracteristica(codigo="1047", nome="FAIXA TEMPERATURA", tipo="INT",
                       minimo="-10", maximo="50", subtipo="ENTRE", unidade="°C"),
    ]


def _retrato():
    return retrato.Retrato(
        pmib="4500063671.0242",
        pdm_antigo="PDM.5920.020 - PROTETOR, SURTO, R1",
        pdm_novo="PDM.5920.020",
        caracteristicas=tuple(_caracteristicas()),
        # Momento EXPLICITO: sem ele, `gravar` preenche com a hora e a
        # comparacao de ida e volta acusaria o unico campo que o modulo
        # preenche de proposito. Quem testa esse preenchimento e
        # `test_guarda_o_momento_e_a_versao_do_formato`.
        momento="2026-09-23T10:00:00",
    )


# =============================================================================
# A. Onde ele mora
# =============================================================================
def test_a_pasta_fica_dentro_da_pasta_de_dados_do_usuario():
    """`Documentos\\SIG-FT\\`, nunca o diretório de trabalho -- sob
    `Program Files` o app não escreve, e foi o que derrubou a primeira
    instalação real em 2026-09-21."""
    assert retrato.pasta_retratos().name == "retratos_pdm"


def test_a_pasta_e_criada_se_faltar(tmp_path):
    assert retrato.pasta_retratos().is_dir()


def test_o_nome_do_arquivo_leva_o_pmib():
    caminho = retrato.gravar(_retrato())

    assert "4500063671.0242" in caminho.name
    assert caminho.suffix == ".json"


def test_dois_retratos_da_mesma_ficha_nao_se_sobrescrevem():
    """A segunda tentativa de uma ficha não pode apagar o retrato da
    primeira: se a primeira falhou no meio, é justamente ele que tem o
    original."""
    primeiro = retrato.gravar(_retrato())
    segundo = retrato.gravar(_retrato())

    assert primeiro != segundo
    assert primeiro.is_file() and segundo.is_file()


def test_pmib_com_caractere_proibido_nao_quebra_o_nome_do_arquivo():
    """Windows recusa `\\ / : * ? " < > |`. Um PMIB estranho não pode
    impedir a gravação -- ela é o que autoriza a troca."""
    sujo = retrato.Retrato(pmib='45/00:06*3671?0242', pdm_antigo="X",
                           pdm_novo="Y", caracteristicas=())

    caminho = retrato.gravar(sujo)

    assert caminho.is_file()
    for proibido in '\\/:*?"<>|':
        assert proibido not in caminho.name


# =============================================================================
# B. Ida e volta sem perda -- o que o módulo inteiro depende
# =============================================================================
def test_ida_e_volta_preserva_tudo():
    caminho = retrato.gravar(_retrato())

    lido = retrato.ler(caminho)

    assert lido == _retrato()


def test_preserva_acento():
    """O JSON é gravado com `ensure_ascii=False`: o arquivo também é para
    pessoa ler quando algo der errado."""
    original = retrato.Retrato(
        pmib="1", pdm_antigo="A", pdm_novo="B",
        caracteristicas=(Caracteristica(
            codigo="1", nome="TENSÃO MÁXIMA", tipo="CHAR",
            valor_pt="Ação de proteção", valor_es="Acción de protección",
            unidade="°C"),),
    )

    lido = retrato.ler(retrato.gravar(original))

    assert lido.caracteristicas[0].valor_es == "Acción de protección"
    assert lido.caracteristicas[0].unidade == "°C"


def test_preserva_texto_com_varias_linhas():
    """Os textareas do portal aceitam quebra de linha, e o transbordo de
    casas decimais do `tech_specs` escreve várias por linha."""
    texto = "linha 1\nlinha 2\nlinha 3"
    original = retrato.Retrato(
        pmib="1", pdm_antigo="A", pdm_novo="B",
        caracteristicas=(Caracteristica(codigo="1", nome="N", tipo="CHAR",
                                        valor_pt=texto),),
    )

    lido = retrato.ler(retrato.gravar(original))

    assert lido.caracteristicas[0].valor_pt == texto


def test_grava_os_dois_idiomas():
    """Decisão do usuário: *"dando a versão em pt e espanhol pra não
    perdermos nada"*."""
    conteudo = json.loads(retrato.gravar(_retrato()).read_text(encoding="utf-8"))

    primeira = conteudo["caracteristicas"][0]
    assert primeira["valor_pt"] == "PINTADO"
    assert primeira["valor_es"] == "PINTADO"


def test_guarda_o_pdm_antigo_com_a_revisao():
    """Sem a revisão não dá para saber, depois, se a ficha foi de R1 para R2
    ou ficou parada."""
    conteudo = json.loads(retrato.gravar(_retrato()).read_text(encoding="utf-8"))

    assert conteudo["pdm_antigo"] == "PDM.5920.020 - PROTETOR, SURTO, R1"
    assert conteudo["pdm_novo"] == "PDM.5920.020"


def test_guarda_o_momento_e_a_versao_do_formato():
    """A versão é o que permite ler um retrato antigo daqui a seis meses sem
    adivinhar o formato."""
    conteudo = json.loads(retrato.gravar(_retrato()).read_text(encoding="utf-8"))

    assert conteudo["versao"] == retrato.VERSAO_DO_FORMATO
    assert conteudo["momento"]


# =============================================================================
# C. Falhar barulhento -- a regra que protege o original
# =============================================================================
def test_gravacao_que_falha_LEVANTA_em_vez_de_calar(monkeypatch):
    """A regra do plano: *não trocar o PDM se o retrato não gravou*. Uma
    falha silenciosa aqui viraria autorização para destruir o original."""
    def _explode(*_a, **_kw):
        raise OSError("disco cheio")

    monkeypatch.setattr(retrato.Path, "write_text", _explode)

    with pytest.raises(OSError):
        retrato.gravar(_retrato())


def test_ler_arquivo_que_nao_existe_levanta(tmp_path):
    with pytest.raises(OSError):
        retrato.ler(tmp_path / "nao_existe.json")


def test_ler_json_corrompido_levanta_com_o_caminho_na_mensagem(tmp_path):
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{isto não é json", encoding="utf-8")

    with pytest.raises(ValueError, match="ruim.json"):
        retrato.ler(ruim)


# =============================================================================
# D. Achar o retrato de uma ficha -- o modo "só repor"
# =============================================================================
def test_lista_os_retratos_de_uma_ficha_do_mais_novo_para_o_mais_velho():
    """Quem vai repor quer o ÚLTIMO: é o da tentativa que falhou."""
    primeiro = retrato.gravar(_retrato())
    segundo = retrato.gravar(_retrato())

    achados = retrato.listar("4500063671.0242")

    assert achados[0] == segundo
    assert achados[1] == primeiro


def test_listar_ficha_sem_retrato_devolve_vazio():
    assert retrato.listar("0000000000.0000") == []


def test_listar_nao_mistura_fichas():
    retrato.gravar(_retrato())
    outra = retrato.Retrato(pmib="4500063671.9999", pdm_antigo="A",
                            pdm_novo="B", caracteristicas=())
    retrato.gravar(outra)

    assert len(retrato.listar("4500063671.0242")) == 1
    assert len(retrato.listar("4500063671.9999")) == 1

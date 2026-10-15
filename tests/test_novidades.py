# -*- coding: utf-8 -*-
"""O `CHANGELOG.md` como fonte UNICA das novidades.

Duas pontas leem o mesmo bloco: a tela do app ("o que ha de novo" da versao
instalada) e o workflow de Release (o corpo do Release no GitHub). Escrever as
duas a mao e garantir que divirjam no primeiro dia corrido -- e a divergencia
aparece justamente para o usuario, que le uma coisa no app e outra no GitHub.

Tudo aqui e funcao pura sobre texto: sem rede, sem interface, sem arquivo.
"""
import pathlib

import pytest

from sigft.core import novidades

RAIZ = pathlib.Path(__file__).resolve().parent.parent

EXEMPLO = """# Historico de versoes

Um paragrafo de introducao que NAO e novidade de versao nenhuma.

## 1.1.0 - 2026-10-01

- Novidade mais recente
- Outra novidade

## 1.0.0 - 2026-09-18

- A primeira versao
"""


# =============================================================================
# A. `analisar` -- os blocos, na ordem
# =============================================================================

def test_analisar_acha_os_dois_blocos_do_mais_novo_para_o_mais_velho():
    blocos = novidades.analisar(EXEMPLO)

    assert [b.versao for b in blocos] == ["1.1.0", "1.0.0"]


def test_o_paragrafo_de_introducao_nao_vira_novidade():
    """Texto antes do primeiro `##` e do arquivo, nao de uma versao."""
    blocos = novidades.analisar(EXEMPLO)

    assert all("introducao" not in item for b in blocos for item in b.itens)


def test_os_itens_ficam_no_bloco_certo():
    blocos = novidades.analisar(EXEMPLO)

    assert blocos[0].itens == ["Novidade mais recente", "Outra novidade"]
    assert blocos[1].itens == ["A primeira versao"]


def test_a_data_e_separada_da_versao():
    assert novidades.analisar(EXEMPLO)[0].data == "2026-10-01"


@pytest.mark.parametrize("cabecalho, esperado", [
    ("## 1.0.0 - 2026-09-18", "1.0.0"),
    ("## v1.0.0 - 2026-09-18", "1.0.0"),
    ("## 1.0.0", "1.0.0"),
    ("## 1.0.0-rc.1 - 2026-09-18", "1.0.0-rc.1"),
    ("##   1.0.0   -   2026-09-18  ", "1.0.0"),
])
def test_formas_aceitas_de_cabecalho(cabecalho, esperado):
    blocos = novidades.analisar(f"{cabecalho}\n- item\n")

    assert [b.versao for b in blocos] == [esperado]


@pytest.mark.parametrize("traco", ["-", "–", "—"])
def test_os_tres_tracos_separam_versao_e_data(traco):
    """Hifen, meia-risca e travessao, todos aceitos.

    Nao e capricho: o Markdown e escrito a mao e o editor de texto de alguem
    troca `-` por `–` sozinho. Se so o hifen valesse, o bloco inteiro
    deixaria de ser reconhecido e o Release sairia SEM notas -- em silencio.

    ATENCAO a quem for varrer travessao do projeto: os tracos dentro da
    expressao regular de `novidades` sao CLASSE DE CARACTERES, nao pontuacao.
    Tirar o `—` de la quebra este teste.
    """
    blocos = novidades.analisar(f"## 1.0.0 {traco} 2026-09-18\n- item\n")

    assert blocos[0].versao == "1.0.0"
    assert blocos[0].data == "2026-09-18"


@pytest.mark.parametrize("marcador", ["-", "*", "+"])
def test_os_tres_marcadores_de_lista_do_markdown(marcador):
    blocos = novidades.analisar(f"## 1.0.0\n{marcador} a novidade\n")

    assert blocos[0].itens == ["a novidade"]


def test_texto_vazio_nao_estoura():
    assert novidades.analisar("") == []
    assert novidades.analisar(None) == []


def test_arquivo_sem_nenhum_bloco_devolve_lista_vazia():
    assert novidades.analisar("# So um titulo\n\nsem versao nenhuma\n") == []


# =============================================================================
# B. `bloco_de` -- achar a versao instalada
# =============================================================================

def test_bloco_de_acha_a_versao_pedida():
    assert novidades.bloco_de(EXEMPLO, "1.0.0").itens == ["A primeira versao"]


def test_bloco_de_ignora_o_v_da_tag():
    assert novidades.bloco_de(EXEMPLO, "v1.0.0") is not None


def test_uma_pre_versao_acha_o_bloco_da_versao_final():
    """`1.1.0-rc.1` mostra as novidades da `1.1.0`.

    O bloco e escrito uma vez, quando a versao e planejada; o candidato a
    lancamento e a mesma coisa em teste. Exigir um bloco proprio para cada
    `-rc.N` faria o teste de pre-lancamento abrir sem novidade nenhuma.
    """
    assert novidades.bloco_de(EXEMPLO, "1.1.0-rc.1").versao == "1.1.0"


def test_versao_que_nao_existe_devolve_None():
    assert novidades.bloco_de(EXEMPLO, "9.9.9") is None


# =============================================================================
# C. `markdown()` -- o corpo do Release
# =============================================================================

def test_markdown_devolve_os_itens_como_lista():
    assert novidades.bloco_de(EXEMPLO, "1.0.0").markdown() == "- A primeira versao"


def test_titulo_junta_versao_e_data():
    assert novidades.bloco_de(EXEMPLO, "1.0.0").titulo() == "v1.0.0 (2026-09-18)"


def test_titulo_sem_data_nao_deixa_parenteses_vazio():
    bloco = novidades.analisar("## 1.0.0\n- item\n")[0]

    assert bloco.titulo() == "v1.0.0"


# =============================================================================
# D. O CHANGELOG.md DE VERDADE -- o portao que o CI repete
# =============================================================================

def test_o_repositorio_tem_um_CHANGELOG():
    assert (RAIZ / "CHANGELOG.md").is_file(), (
        "CHANGELOG.md sumiu. Ele e a fonte das notas do Release E do "
        "'o que ha de novo' do app."
    )


def test_o_CHANGELOG_de_verdade_tem_blocos_reconheciveis():
    texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")

    assert novidades.analisar(texto), (
        "nenhum bloco '## <versao>' reconhecivel no CHANGELOG.md"
    )


def test_a_versao_do_build_tem_bloco_no_CHANGELOG():
    """O portao que evita publicar um Release SEM notas.

    Sem este teste, o defeito so apareceria com a tag ja criada: o workflow
    procuraria o bloco da versao, nao acharia, e o Release sairia com o corpo
    vazio. Desfazer isso exige apagar o Release e a tag.
    """
    from sigft import _build_info

    texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")

    assert novidades.bloco_de(texto, _build_info.VERSAO) is not None, (
        f"_build_info.VERSAO e {_build_info.VERSAO}, mas o CHANGELOG.md nao "
        f"tem bloco para ela. Acrescente '## {_build_info.VERSAO} - <data>' "
        f"ANTES de criar a tag."
    )


# [2026-10-15] O caminho do CHANGELOG no `.exe` saía do `resource_path` da
# interface antiga; agora sai do `sys._MEIPASS` direto, sem importar interface.
def test_changelog_dentro_do_executavel_vem_da_raiz_do_bundle(tmp_path, monkeypatch):
    import sys

    from sigft.core import novidades as mod

    (tmp_path / "CHANGELOG.md").write_text("## 1.0.0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert mod.caminho_changelog() == str(tmp_path / "CHANGELOG.md")


def test_changelog_rodando_do_codigo_e_o_da_raiz_do_projeto(monkeypatch):
    import os
    import sys

    from sigft.core import novidades as mod

    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    assert mod.caminho_changelog() == os.path.join(raiz, "CHANGELOG.md")

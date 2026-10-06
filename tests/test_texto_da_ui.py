# -*- coding: utf-8 -*-
"""O travessao fora do texto que o usuario le -- e os dois lugares onde ele FICA.

O recorte (decisao do usuario, 2026-09-18): strings de UI e de log, FORA dos
arquivos da frente do Rafael e fora de `core/llm/prompts.py`. Comentario e
docstring nao entram: sao o estilo da casa em todo arquivo do repositorio, e
dos dois desenvolvedores.

O QUE ESTE ARQUIVO PROTEGE, e e a parte que importa
---------------------------------------------------
Nao e o travessao. E os DOIS lugares onde ele nao e pontuacao, e sim DADO --
trocar qualquer um dos dois quebra comportamento, em silencio:

  1. `services/duplicadas_condicoes.py` -- o travessao e MEMBRO de uma classe
     de caracteres que normaliza os tracos do portal. O PMIB escreve
     "Classe I - Perigoso" com hifen e "Classe II - Nao perigoso" com
     travessao NA MESMA LISTA de opcoes, e `NFKD` nao unifica os dois. Sem o
     travessao ali, a chave do mapa passa a depender de qual traco o portal
     usou no dia, e o sintoma e "opcao desconhecida" numa opcao escrita certa.

  2. `core/novidades.py` -- idem, na expressao regular do cabecalho do
     CHANGELOG. O arquivo e escrito a mao e o editor de texto troca `-` por
     travessao sozinho; se so o hifen valesse, o bloco deixaria de ser
     reconhecido e o Release sairia SEM notas, em silencio, com a tag ja
     criada.

Os dois tem teste de COMPORTAMENTO, logo abaixo. Um guard que so olhasse o
caractere diria "esta la" sem provar que ele ainda serve para alguma coisa.
"""
import ast
import pathlib

import pytest

from _caminhos import relativo_posix

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "sigft"

TRAVESSAO = "—"

# Frente do Rafael (docs/refatoracao/TRABALHO_PARALELO.md) + os prompts de IA.
# Ficaram de fora por decisao do usuario: mexer neles exigiria combinar com o
# Rafael antes, e prompt de IA e texto que a IA le, nao o usuario.
FORA_DO_RECORTE = {
    "sigft/services/autospec.py",
    "sigft/services/autospec_rag.py",
    "sigft/services/autospec_embeddings.py",
    "sigft/services/autospec_unidades.py",
    "sigft/services/autospec_conferencia.py",
    "sigft/core/web/navegador.py",
    "sigft/core/web/robots.py",
    "sigft/app/views/autospec.py",
    "sigft/core/llm/prompts.py",
}

# Os dois onde o travessao e DADO. Ver o docstring deste modulo.
ONDE_ELE_E_DADO = {
    "sigft/services/duplicadas_condicoes.py",
    "sigft/core/novidades.py",
    # 2026-10-05 (T3 do roteiro do Gestão PMIB v2): o "—" é o valor que a
    # pessoa escreve na linha da revisão em uso quando NÃO há revisão ("EM
    # USO: — - DATA DE ALTERAÇÃO: —"). Tirá-lo do conjunto `_SEM_REVISAO`
    # faria o Gestão PMIB gravar "—" como revisão na mapeadora.
    "sigft/services/status_pmib_arquivos.py",
    # 2026-10-05 (T7): o "—" é o marcador de "sem pendência" / "sem com quem"
    # que o template do painel (`sigft/assets/painel_template.html`) filtra
    # (`i.pe !== "—"`); os textos de qualidade são os da referência do cofre,
    # que o validador do painel compara palavra por palavra.
    "sigft/services/painel.py",
}


def _strings_com_travessao(caminho: pathlib.Path) -> list[tuple[int, str]]:
    """Literais de string com travessao, FORA de docstring."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    docstrings = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                           ast.ClassDef)):
            if (ast.get_docstring(no, clean=False) is not None
                    and no.body and isinstance(no.body[0], ast.Expr)):
                docstrings.add(id(no.body[0].value))

    return [
        (no.lineno, no.value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str)
        and TRAVESSAO in no.value and id(no) not in docstrings
    ]


# =============================================================================
# A. O guard
# =============================================================================

@pytest.mark.parametrize(
    "arquivo",
    sorted(PACOTE.rglob("*.py")),
    ids=lambda p: str(p.relative_to(RAIZ)),
)
def test_sem_travessao_no_texto_que_o_usuario_le(arquivo):
    # O caminho e comparado em formato POSIX, sempre. `str(Path.relative_to(...))`
    # usa o separador do SISTEMA: no Windows sai `sigft\services\autospec.py`, que
    # nao casa com nenhuma entrada destas listas -- e elas ficam INERTES.
    #
    # Foi o que derrubou o primeiro Release (run #1, 2026-09-21): nove testes
    # reprovaram no Windows, incluindo o arquivo onde o travessao e DADO. A suite
    # estava verde em Linux, e nenhum CI nosso podia ver.
    # Ver `tests/_caminhos.py` e `tests/test_caminhos_multiplataforma.py`.
    relativo = relativo_posix(arquivo, RAIZ)
    if relativo in FORA_DO_RECORTE:
        pytest.skip("fora do recorte -- ver o docstring")
    if relativo in ONDE_ELE_E_DADO:
        pytest.skip("aqui o travessao e DADO -- ver o docstring")

    achados = _strings_com_travessao(arquivo)

    assert not achados, (
        f"{relativo} tem travessao em texto de tela ou de log:\n  "
        + "\n  ".join(f"L{ln}: {v.strip()[:70]!r}" for ln, v in achados)
        + "\n\nUse hifen, dois-pontos ou ponto final. Se o travessao ali for "
          "DADO (classe de caracteres, valor de celula), acrescente o arquivo "
          "a ONDE_ELE_E_DADO deste teste, com o motivo."
    )


def test_a_lista_de_excecoes_nao_tem_arquivo_inexistente():
    """Excecao que sobrevive ao arquivo vira permissao esquecida."""
    for relativo in FORA_DO_RECORTE | ONDE_ELE_E_DADO:
        assert (RAIZ / relativo).is_file(), (
            f"{relativo} esta na lista de excecoes mas nao existe mais"
        )


def test_os_dois_lugares_de_DADO_realmente_tem_o_caractere():
    """Se o travessao sumir de la, a excecao vira mentira -- e o guard
    continuaria pulando o arquivo sem nada para proteger."""
    for relativo in ONDE_ELE_E_DADO:
        texto = (RAIZ / relativo).read_text(encoding="utf-8")
        assert TRAVESSAO in texto, (
            f"{relativo} esta em ONDE_ELE_E_DADO mas nao tem mais travessao. "
            f"Remova a linha da lista."
        )


# =============================================================================
# B. Os dois casos de DADO, provados por COMPORTAMENTO
# =============================================================================
#
# E aqui que a protecao vale: um guard que so conta caracteres nao prova que
# ele ainda SERVE para alguma coisa.

def test_o_portal_escrevendo_com_travessao_casa_com_o_mesmo_rotulo():
    """O caso real: o PMIB usa hifen numa opcao e travessao na de baixo."""
    from sigft.services.duplicadas_condicoes import chave_de_rotulo

    com_hifen = chave_de_rotulo("Classe I - Perigoso")
    com_travessao = chave_de_rotulo("Classe I — Perigoso")
    com_meia_risca = chave_de_rotulo("Classe I – Perigoso")

    assert com_hifen == com_travessao == com_meia_risca, (
        "os tracos deixaram de ser unificados: a chave do mapa passa a "
        "depender de qual traco o portal usou no dia"
    )


def test_o_CHANGELOG_escrito_com_travessao_continua_sendo_lido():
    """Se isto quebrar, o Release sai SEM notas -- em silencio."""
    from sigft.core.novidades import analisar

    for traco in ("-", "–", "—"):
        blocos = analisar(f"## 1.0.0 {traco} 2026-09-18\n- uma novidade\n")

        assert blocos, f"o cabecalho com `{traco}` deixou de ser reconhecido"
        assert blocos[0].versao == "1.0.0"
        assert blocos[0].data == "2026-09-18"


def test_a_revisao_em_uso_escrita_com_travessao_e_sem_revisao():
    """Se isto quebrar, o Gestão PMIB grava "—" na REVISÃO EM USO da mapeadora."""
    from sigft.services.status_pmib_arquivos import revisao_do_texto

    for traco in ("-", "–", "—"):
        texto = f"REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: {traco} - DATA DE ALTERAÇÃO: {traco}"
        assert revisao_do_texto(texto) is None, f"`{traco}` virou revisão"
    assert revisao_do_texto(
        "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: —") == "0A"


def test_o_marcador_de_sem_pendencia_do_painel_e_o_que_o_template_filtra():
    """Se isto quebrar, a fila de trabalho do painel passa a listar quem não
    tem pendência nenhuma."""
    from sigft.services import painel

    marcador = painel.pendencia(False, "INICIAR", "", {}, False, False, "")
    template = painel.caminho_do_template().read_text(encoding="utf-8")

    assert marcador == "—"
    assert f'i.pe !== "{marcador}"' in template
    assert painel.COM_QUEM.get("SEM STATUS", "—") == "—"
    assert 'chave: "—", nome: "Sem status válido"' in template


# =============================================================================
# C. Os vicios de voz, nos textos que foram reescritos
# =============================================================================

def test_nenhuma_mensagem_de_lote_usa_travessao_como_separador():
    """Os titulos de lote e o separador de motivo sairam do travessao.

    Dois-pontos, e nao hifen: o identificador ja tem hifen (`PMIB-9`), e
    `PMIB-9 - timeout` fica ambiguo na leitura rapida de um log.
    """
    from sigft.core.relatorio_lote import RelatorioLote

    class _Cbs:
        def __init__(self):
            self.linhas = []

        def log(self, msg, nivel="info"):
            self.linhas.append(msg)

        def progress(self, *a, **k):
            pass

    cbs = _Cbs()
    rel = RelatorioLote(cbs, titulo="X", total=1)
    rel.iniciar()
    rel.falha("PMIB-9", "timeout no portal")
    rel.finalizar()

    texto = "\n".join(cbs.linhas)

    assert TRAVESSAO not in texto, f"travessao no relatorio de lote:\n{texto}"
    assert "PMIB-9: timeout no portal" in texto

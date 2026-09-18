# -*- coding: utf-8 -*-
"""Onde o SIG-FT grava o que e do USUARIO -- e por que nao pode ser ao lado do .exe.

Ate aqui `api_config.json`, `user_prefs.json`, os caches de modelo e a pasta
`logs/` eram resolvidos a partir do DIRETORIO DE TRABALHO, ou seja, da pasta
do programa. Isso funcionava porque o app era extraido em `%LOCALAPPDATA%`,
onde o usuario escreve.

Com o instalador, o padrao passa a ser `Program Files` -- e ali usuario comum
NAO ESCREVE. Os quatro deixariam de funcionar de uma vez, e o sintoma seria o
pior possivel: as chaves de API somem a cada abertura, e o log de erro, que e
justamente o que diria o motivo, tambem nao grava.

Ha um segundo motivo, independente do instalador: a atualizacao reescreve a
pasta do programa. Dado do usuario guardado la seria apagado a cada versao
nova.

DECISAO DO USUARIO (2026-09-18): as chaves continuam COMPARTILHAVEIS, sem
DPAPI. O que muda e o LUGAR, nao o sigilo. Ver o CHANGELOG da 1.0.0.
"""
import json
import os

import pytest

from sigft.core import dados_usuario


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    """Aponta a pasta de dados para um `tmp_path`.

    A variavel existe primeiro para os TESTES: sem ela, esta suite escreveria
    na pasta Documentos de verdade de quem a rodasse -- e o arquivo deixado
    la passaria a valer para o app da pessoa. O DocManager pagou exatamente
    isso com o token de atualizacao.
    """
    monkeypatch.setenv("SIGFT_DADOS_DIR", str(tmp_path))
    dados_usuario.esquecer_pasta()
    yield tmp_path
    dados_usuario.esquecer_pasta()


# =============================================================================
# A. Onde e
# =============================================================================

def test_a_variavel_de_ambiente_manda(pasta):
    assert dados_usuario.pasta_dados() == pasta


def test_a_pasta_e_criada_se_nao_existir(tmp_path, monkeypatch):
    destino = tmp_path / "ainda-nao-existe" / "SIG-FT"
    monkeypatch.setenv("SIGFT_DADOS_DIR", str(destino))
    dados_usuario.esquecer_pasta()

    assert dados_usuario.pasta_dados().is_dir()


def test_caminho_de_um_arquivo_fica_dentro_da_pasta(pasta):
    assert dados_usuario.caminho("api_config.json") == pasta / "api_config.json"


def test_sem_a_variavel_o_caminho_nao_e_a_pasta_do_programa(monkeypatch, tmp_path):
    """O ponto da frente inteira.

    Seja qual for o sistema, o destino NAO pode ser o diretorio de trabalho
    -- que sob `Program Files` e somente-leitura.
    """
    monkeypatch.delenv("SIGFT_DADOS_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    dados_usuario.esquecer_pasta()

    destino = dados_usuario.pasta_dados()

    assert destino.resolve() != pathlib_cwd()
    assert "SIG-FT" in str(destino)


def pathlib_cwd():
    import pathlib

    return pathlib.Path.cwd().resolve()


def test_a_pasta_leva_o_nome_do_app(monkeypatch, tmp_path):
    monkeypatch.delenv("SIGFT_DADOS_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    dados_usuario.esquecer_pasta()

    assert dados_usuario.pasta_dados().name == "SIG-FT"


# =============================================================================
# B. A importacao do que ja existe -- ninguem recadastra nada
# =============================================================================

def test_o_api_config_antigo_e_importado_na_primeira_abertura(pasta, tmp_path):
    """Quem ja tem chaves ao lado do .exe nao pode perde-las na atualizacao."""
    antiga = tmp_path / "programa"
    antiga.mkdir()
    (antiga / "api_config.json").write_text(
        json.dumps({"GEMINI": "chave-antiga"}), encoding="utf-8")

    importados = dados_usuario.importar_do_lugar_antigo(antiga)

    assert "api_config.json" in importados
    destino = json.loads((pasta / "api_config.json").read_text(encoding="utf-8"))
    assert destino["GEMINI"] == "chave-antiga"


def test_a_importacao_NAO_sobrescreve_o_que_ja_esta_no_lugar_novo(pasta, tmp_path):
    """Rodar de novo nao pode desfazer o que a pessoa cadastrou depois."""
    (pasta / "api_config.json").write_text(
        json.dumps({"GEMINI": "a-que-vale"}), encoding="utf-8")
    antiga = tmp_path / "programa"
    antiga.mkdir()
    (antiga / "api_config.json").write_text(
        json.dumps({"GEMINI": "velha"}), encoding="utf-8")

    importados = dados_usuario.importar_do_lugar_antigo(antiga)

    assert importados == []
    atual = json.loads((pasta / "api_config.json").read_text(encoding="utf-8"))
    assert atual["GEMINI"] == "a-que-vale"


def test_o_user_prefs_antigo_tambem_vem_junto(pasta, tmp_path):
    antiga = tmp_path / "programa"
    antiga.mkdir()
    (antiga / "user_prefs.json").write_text(
        json.dumps({"ultimos": {"pdm": "C:/x"}}), encoding="utf-8")

    importados = dados_usuario.importar_do_lugar_antigo(antiga)

    assert "user_prefs.json" in importados


def test_o_env_antigo_vira_api_config(pasta, tmp_path):
    """Quem configurava por `.env` tambem nao recadastra nada."""
    antiga = tmp_path / "programa"
    antiga.mkdir()
    (antiga / ".env").write_text(
        "API_GEMINI_LUAN_GMAIL=chave-do-env\n"
        "# um comentario\n"
        "GOOGLE_SEARCH_API='entre aspas'\n",
        encoding="utf-8")

    dados_usuario.importar_do_lugar_antigo(antiga)

    salvo = json.loads((pasta / "api_config.json").read_text(encoding="utf-8"))
    assert salvo["GEMINI"] == "chave-do-env"
    assert salvo["GOOGLE_SEARCH"] == "entre aspas"


def test_o_api_config_ganha_do_env_quando_existem_os_dois(pasta, tmp_path):
    """O `api_config.json` e o que a tela do app grava: e o mais recente."""
    antiga = tmp_path / "programa"
    antiga.mkdir()
    (antiga / ".env").write_text("API_GEMINI_LUAN_GMAIL=do-env\n", encoding="utf-8")
    (antiga / "api_config.json").write_text(
        json.dumps({"GEMINI": "do-json"}), encoding="utf-8")

    dados_usuario.importar_do_lugar_antigo(antiga)

    salvo = json.loads((pasta / "api_config.json").read_text(encoding="utf-8"))
    assert salvo["GEMINI"] == "do-json"


def test_pasta_antiga_inexistente_nao_estoura(pasta, tmp_path):
    assert dados_usuario.importar_do_lugar_antigo(tmp_path / "nao-existe") == []


def test_arquivo_antigo_corrompido_nao_derruba_a_abertura(pasta, tmp_path):
    """JSON quebrado nao pode impedir o app de subir."""
    antiga = tmp_path / "programa"
    antiga.mkdir()
    (antiga / "api_config.json").write_text("{isto nao e json", encoding="utf-8")

    assert dados_usuario.importar_do_lugar_antigo(antiga) == []


# =============================================================================
# C. Os consumidores de verdade apontam para la
# =============================================================================

def test_o_config_de_chaves_aponta_para_a_pasta_de_dados(pasta):
    from sigft import config

    assert os.path.dirname(os.path.abspath(config.caminho_config())) == str(pasta)


def test_as_prefs_apontam_para_a_pasta_de_dados(pasta):
    from sigft.core import prefs

    assert os.path.dirname(os.path.abspath(prefs.caminho_config())) == str(pasta)


def test_o_cache_de_modelos_aponta_para_a_pasta_de_dados(pasta):
    from sigft.core.llm import catalogo

    for provedor in catalogo.CACHE_POR_PROVIDER:
        destino = catalogo.caminho_cache(provedor)
        assert os.path.dirname(os.path.abspath(destino)) == str(pasta), (
            f"o cache de {provedor} nao esta na pasta de dados"
        )


def test_o_log_de_erro_aponta_para_a_pasta_de_dados(pasta):
    """Sob Program Files, `logs/` ao lado do .exe nao grava.

    E o pior lugar para falhar: e justamente o log que diria o motivo de
    qualquer outra falha.
    """
    assert dados_usuario.pasta_logs().parent == pasta
    assert dados_usuario.pasta_logs().is_dir()


# =============================================================================
# D. O guard: nenhum caminho gravavel relativo sobra no pacote
# =============================================================================

def test_nenhum_modulo_resolve_arquivo_gravavel_pelo_diretorio_de_trabalho():
    """A trava que faz valer a frente inteira.

    Um `CONFIG_FILE = "algo.json"` novo, resolvido pelo cwd, volta a quebrar
    sob Program Files -- e so na maquina de quem instalou.
    """
    import ast
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent
    # Nomes relativos que SOBRARAM de proposito, com o motivo:
    permitidos = {
        # `config.CONFIG_FILE` e `prefs.CONFIG_FILE` continuam existindo como
        # NOME do arquivo (a pasta vem de `dados_usuario`); e o default do
        # parametro `config_path` das funcoes, que os testes sobrescrevem.
        "api_config.json", "user_prefs.json",
        "openrouter_models_cache.json", "gemini_models_cache.json",
        "empresa_models_cache.json",
    }

    infratores = []
    for arquivo in sorted((raiz / "sigft").rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            if not (isinstance(no.func, ast.Name) and no.func.id == "open"):
                continue
            modo = ""
            if len(no.args) > 1 and isinstance(no.args[1], ast.Constant):
                modo = str(no.args[1].value)
            for kw in no.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    modo = str(kw.value.value)
            if not any(c in modo for c in "wax"):
                continue
            alvo = no.args[0] if no.args else None
            if isinstance(alvo, ast.Constant) and isinstance(alvo.value, str):
                if alvo.value not in permitidos:
                    infratores.append(
                        f"{arquivo.relative_to(raiz)}:{no.lineno} -> open({alvo.value!r}, {modo!r})")

    assert not infratores, (
        "gravacao em caminho relativo (resolvido pelo diretorio de trabalho):\n  "
        + "\n  ".join(infratores)
        + "\n\nUse `sigft.core.dados_usuario.caminho(...)`."
    )


# =============================================================================
# E. A abertura do app faz a importacao -- uma vez, sem a pessoa pedir
# =============================================================================

def test_existe_a_rotina_de_primeira_abertura(pasta, tmp_path):
    """Quem ja usa o SIG-FT nao pode ter de recadastrar chave nenhuma.

    A pessoa atualiza e abre: as chaves que estavam ao lado do .exe (ou no
    `.env`) tem de aparecer sozinhas no lugar novo.
    """
    from sigft.core import dados_usuario as du

    antiga = tmp_path / "programa"
    antiga.mkdir()
    (antiga / "api_config.json").write_text(
        json.dumps({"GEMINI": "a-chave"}), encoding="utf-8")

    importados = du.migrar_se_preciso(pasta_antiga=antiga)

    assert importados == ["api_config.json"]
    assert (pasta / "api_config.json").is_file()


def test_a_migracao_e_silenciosa_na_segunda_abertura(pasta, tmp_path):
    """Nao pode avisar nada quando nao ha o que migrar -- e o caso normal."""
    from sigft.core import dados_usuario as du

    antiga = tmp_path / "programa"
    antiga.mkdir()

    assert du.migrar_se_preciso(pasta_antiga=antiga) == []


def test_a_migracao_nunca_derruba_a_abertura(pasta, monkeypatch):
    """Se a importacao estourar, o app abre assim mesmo.

    Perder a importacao e ruim; nao abrir e pior. O usuario recadastra as
    chaves pela tela; um app que nao sobe nao tem tela.
    """
    from sigft.core import dados_usuario as du

    def explode(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(du, "importar_do_lugar_antigo", explode)

    assert du.migrar_se_preciso(pasta_antiga="/qualquer") == []

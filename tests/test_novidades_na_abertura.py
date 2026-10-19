"""A regra da "janela de novidades" (`core/novidades.para_mostrar_na_abertura`).

Pendencia de 2026-09-25: o CHANGELOG ia no pacote para uma janela que nao
existia. A regra mora no core, sem Qt; a tela (`app_qt/novidades.py`) so mostra.
"""
import json

from sigft.core import novidades, prefs

CHANGELOG = """# Changelog

## 1.2.0 - 2026-10-19
- Home: a janela de novidades
- Upload: **mais rapido**

## 1.1.0 - 2026-10-01
- Copia: outra coisa
"""


def _decidir(tmp_path, versao="1.2.0", *, empacotado=True, texto=CHANGELOG):
    return novidades.para_mostrar_na_abertura(
        versao, empacotado=empacotado, texto=texto,
        config_path=str(tmp_path / "user_prefs.json"))


def _vista(tmp_path):
    return prefs.get_ultima_versao_vista(config_path=str(tmp_path / "user_prefs.json"))


def test_versao_nova_mostra_o_bloco_dela_e_grava_como_vista(tmp_path):
    prefs.set_ultima_versao_vista("1.1.0", config_path=str(tmp_path / "user_prefs.json"))

    bloco = _decidir(tmp_path)

    assert bloco is not None and bloco.versao == "1.2.0"
    assert bloco.itens[0] == "Home: a janela de novidades"
    assert _vista(tmp_path) == "1.2.0"


def test_mostra_UMA_vez_so(tmp_path):
    prefs.set_ultima_versao_vista("1.1.0", config_path=str(tmp_path / "user_prefs.json"))
    assert _decidir(tmp_path) is not None
    assert _decidir(tmp_path) is None


def test_primeira_instalacao_nao_mostra_e_grava(tmp_path):
    assert not (tmp_path / "user_prefs.json").exists()
    assert _decidir(tmp_path) is None
    assert _vista(tmp_path) == "1.2.0"


def test_quem_ja_usava_o_app_e_ATUALIZOU_ve_as_novidades(tmp_path):
    """Decisao do Jonathan (2026-10-19): `user_prefs.json` que ja existe sem a
    secao `novidades` e de quem usava uma versao anterior a esta janela. E
    atualizacao, nao primeira instalacao -- senao a versao que traz a janela
    nunca a mostraria."""
    (tmp_path / "user_prefs.json").write_text(
        json.dumps({"opcoes": {"gestao.painel": True}}), encoding="utf-8")

    bloco = _decidir(tmp_path)

    assert bloco is not None and bloco.versao == "1.2.0"
    assert _vista(tmp_path) == "1.2.0"
    assert prefs.get_opcao("gestao.painel", False,
                           config_path=str(tmp_path / "user_prefs.json")) is True


def test_pelo_codigo_fonte_nao_mostra_nem_grava(tmp_path):
    prefs.set_ultima_versao_vista("1.1.0", config_path=str(tmp_path / "user_prefs.json"))
    assert _decidir(tmp_path, empacotado=False) is None
    assert _vista(tmp_path) == "1.1.0"


def test_sem_bloco_no_changelog_nao_mostra_e_grava(tmp_path):
    prefs.set_ultima_versao_vista("1.1.0", config_path=str(tmp_path / "user_prefs.json"))
    assert _decidir(tmp_path, versao="1.3.0") is None
    assert _vista(tmp_path) == "1.3.0"


def test_changelog_ausente_nao_mostra(tmp_path, monkeypatch):
    prefs.set_ultima_versao_vista("1.1.0", config_path=str(tmp_path / "user_prefs.json"))
    monkeypatch.setattr(novidades, "caminho_changelog", lambda: str(tmp_path / "nao_existe.md"))
    assert _decidir(tmp_path, texto=None) is None
    assert _vista(tmp_path) == "1.2.0"


def test_le_o_changelog_do_pacote_quando_nao_recebe_texto(tmp_path, monkeypatch):
    arquivo = tmp_path / "CHANGELOG.md"
    arquivo.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(novidades, "caminho_changelog", lambda: str(arquivo))
    prefs.set_ultima_versao_vista("1.1.0", config_path=str(tmp_path / "user_prefs.json"))
    assert _decidir(tmp_path, texto=None).versao == "1.2.0"


def test_preferencia_ilegivel_nao_mostra_e_nao_quebra(tmp_path):
    (tmp_path / "user_prefs.json").write_text("{isto nao e json", encoding="utf-8")
    assert _decidir(tmp_path) is None


def test_versao_vista_de_tipo_errado_vale_como_ilegivel(tmp_path):
    (tmp_path / "user_prefs.json").write_text(
        json.dumps({"novidades": {"ultima_versao_vista": 7}}), encoding="utf-8")
    assert _vista(tmp_path) is None
    assert _decidir(tmp_path) is None


def test_erro_ao_ler_a_preferencia_nao_mostra_e_nao_levanta(tmp_path, monkeypatch):
    def explode(**kw):
        raise OSError("disco sumiu")

    monkeypatch.setattr(prefs, "situacao_versao_vista", explode)
    assert _decidir(tmp_path) is None


def test_sem_conseguir_gravar_NAO_mostra(tmp_path, monkeypatch):
    """Mostrar sem gravar seria mostrar em TODA abertura."""
    prefs.set_ultima_versao_vista("1.1.0", config_path=str(tmp_path / "user_prefs.json"))

    def explode(*a, **kw):
        raise PermissionError("somente leitura")

    monkeypatch.setattr(prefs, "set_ultima_versao_vista", explode)
    assert _decidir(tmp_path) is None


def test_gravar_a_versao_nao_apaga_as_outras_preferencias(tmp_path):
    caminho = str(tmp_path / "user_prefs.json")
    prefs.set_opcao("gestao.painel", True, config_path=caminho)
    prefs.set_ultima_versao_vista("1.1.0", config_path=caminho)
    assert prefs.get_opcao("gestao.painel", False, config_path=caminho) is True

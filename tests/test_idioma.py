"""O idioma da interface (2026-10-22): `t()`, os catálogos e a preferência."""
import json
import pathlib

import pytest

from sigft.app import idioma


@pytest.fixture
def catalogos(tmp_path, monkeypatch):
    (tmp_path / "es.json").write_text(json.dumps({
        "Salvar": "Guardar",
        "Ficha {atual} de {total}": "Ficha {atual} de {total}",
        "Abrir {nome}": "Abrir {name}",
        "Vazio": "",
    }), encoding="utf-8")
    (tmp_path / "en.json").write_text(json.dumps({"Salvar": "Save"}), encoding="utf-8")
    monkeypatch.setattr(idioma, "PASTA_CATALOGOS", tmp_path)
    monkeypatch.setattr(idioma, "_catalogos", {})
    return tmp_path


def test_os_testes_rodam_em_portugues():
    assert idioma.atual() == "pt"


def test_portugues_e_a_propria_chave(catalogos):
    assert idioma.t("Salvar") == "Salvar"


def test_traduz_no_idioma_definido(catalogos):
    assert idioma.definir("es") == "es"
    assert idioma.t("Salvar") == "Guardar"
    idioma.definir("en")
    assert idioma.t("Salvar") == "Save"


def test_sem_traducao_cai_no_portugues(catalogos):
    idioma.definir("es")
    assert idioma.t("Não existe no catálogo") == "Não existe no catálogo"
    assert idioma.t("Vazio") == "Vazio"     # tradução vazia vale como nenhuma


def test_valores_entram_no_lugar(catalogos):
    assert idioma.t("Ficha {atual} de {total}", atual=3, total=8) == "Ficha 3 de 8"
    idioma.definir("es")
    assert idioma.t("Ficha {atual} de {total}", atual=3, total=8) == "Ficha 3 de 8"


def test_traducao_com_valor_que_nao_casa_cai_no_portugues(catalogos):
    idioma.definir("es")
    assert idioma.t("Abrir {nome}", nome="x.xlsx") == "Abrir x.xlsx"


@pytest.mark.parametrize("traducao", ["Abrir {0}", "Abrir {nome!z}", "Abrir {nome.x}", "Abrir {"])
def test_traducao_que_nao_formata_cai_no_portugues(catalogos, traducao):
    """Qualquer erro do `format` na tradução (IndexError, ValueError, AttributeError...)
    vale o português, nunca derruba a tela."""
    idioma.catalogo("es")["Abrir {nome}"] = traducao
    idioma.definir("es")
    assert idioma.t("Abrir {nome}", nome="x.xlsx") == "Abrir x.xlsx"


def test_portugues_que_nao_formata_volta_sem_valores(catalogos, caplog):
    """Nem o português casa com os valores: devolve o texto como está e deixa UMA
    linha no log, em vez de levantar no meio da montagem da tela."""
    with caplog.at_level("WARNING", logger=idioma.__name__):
        assert idioma.t("Ficha {atual}", outro=1) == "Ficha {atual}"
    assert len(caplog.records) == 1
    caplog.clear()
    idioma.catalogo("es")["Ficha {atual}"] = "Ficha {nada}"
    idioma.definir("es")
    with caplog.at_level("WARNING", logger=idioma.__name__):
        assert idioma.t("Ficha {atual}", outro=1) == "Ficha {atual}"
    assert len(caplog.records) == 1


def test_sem_valores_as_chaves_ficam_como_estao(catalogos):
    assert idioma.t("Use {nome} no campo") == "Use {nome} no campo"


def test_idioma_invalido_vira_portugues(catalogos):
    assert idioma.definir("fr") == "pt"
    assert idioma.valido(None) == "pt"


def test_marcar_nao_muda_o_texto():
    assert idioma.marcar("Texto qualquer") == "Texto qualquer"


def test_catalogo_que_nao_se_le_nao_derruba(tmp_path, monkeypatch):
    (tmp_path / "es.json").write_text("isto não é json", encoding="utf-8")
    (tmp_path / "en.json").write_text("[1, 2]", encoding="utf-8")
    monkeypatch.setattr(idioma, "PASTA_CATALOGOS", tmp_path)
    monkeypatch.setattr(idioma, "_catalogos", {})
    idioma.definir("es")
    assert idioma.t("Salvar") == "Salvar"
    assert idioma.conferir() == ["es", "en"]


def test_os_catalogos_de_verdade_se_leem():
    assert idioma.conferir() == []


def test_escolhido_e_guardar(tmp_path, monkeypatch):
    monkeypatch.setattr(idioma, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    assert idioma.escolhido() is None
    assert idioma.guardar("en") == "en"
    assert idioma.escolhido() == "en"
    assert idioma.guardar("fr") == "pt"
    assert idioma.escolhido() == "pt"


def test_valor_invalido_nas_prefs_e_nao_escolhido(tmp_path, monkeypatch):
    monkeypatch.setattr(idioma, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    (tmp_path / "p.json").write_text('{"preferencias": {"idioma": "klingon"}}', encoding="utf-8")
    assert idioma.escolhido() is None


def test_preferencia_que_nao_se_le_vale_portugues(monkeypatch):
    from sigft.core import prefs

    def quebra(*_a, **_k):
        raise OSError("sem permissão")

    monkeypatch.setattr(prefs, "ler_preferencia", quebra)
    assert idioma.escolhido() == "pt"


def test_idioma_nao_conhece_qt():
    fonte = (pathlib.Path(idioma.__file__)).read_text(encoding="utf-8")
    assert "PySide6" not in fonte

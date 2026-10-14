import pytest

from sigft.app import backends


@pytest.fixture(autouse=True)
def _limpa(monkeypatch):
    monkeypatch.setattr(backends, "falhas", {})


def test_falha_fica_registrada_com_o_motivo(monkeypatch):
    monkeypatch.setattr(backends, "MODULOS", [("modulo_que_nao_existe_x", "pdm_backend", None, "Teste")])
    monkeypatch.setattr(backends, "pdm_backend", None)
    backends.carregar_todos()
    assert "pdm_backend" in backends.falhas
    assert "modulo_que_nao_existe_x" in backends.motivo_da_falha("pdm_backend")


def test_exigir_explica_quando_nao_carregou(monkeypatch):
    monkeypatch.setattr(backends, "autospec_backend", None)
    backends.falhas["autospec_backend"] = TypeError("unsupported operand type(s) for |")
    with pytest.raises(backends.BackendIndisponivel) as erro:
        backends.exigir("autospec_backend")
    texto = str(erro.value)
    assert "não carregou" in texto and "unsupported operand" in texto and "sigft.log" in texto


def test_exigir_devolve_o_modulo_carregado(monkeypatch):
    sentinela = object()
    monkeypatch.setattr(backends, "lmr_backend", sentinela)
    assert backends.exigir("lmr_backend") is sentinela


def test_exigir_sem_falha_registrada_ainda_explica(monkeypatch):
    monkeypatch.setattr(backends, "lmr_backend", None)
    with pytest.raises(backends.BackendIndisponivel, match="ainda não foi carregado"):
        backends.exigir("lmr_backend")


def test_falha_de_modulo_com_classes_responde_pelo_nome_da_classe(monkeypatch):
    """O Gerador de Fichas é `mixed_classes`: o módulo falha, mas as telas
    pedem pelo nome da CLASSE (`DataManager`), não pelo destino."""
    monkeypatch.setattr(backends, "MODULOS", [("modulo_que_nao_existe_y", "mixed_classes", ["DataManager"], "Teste")])
    monkeypatch.setattr(backends, "DataManager", None)
    ao_falhar_chamadas = []
    backends.carregar_todos(ao_falhar=lambda nome, erro: ao_falhar_chamadas.append(nome))
    assert len(ao_falhar_chamadas) == 1
    with pytest.raises(backends.BackendIndisponivel) as erro:
        backends.exigir("DataManager")
    texto = str(erro.value)
    assert "não carregou" in texto and "modulo_que_nao_existe_y" in texto

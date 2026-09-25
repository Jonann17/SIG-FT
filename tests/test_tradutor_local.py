r"""O motor de tradução LOCAL (`sigft.core.tradutor_local`).

Duas partes:

A-C. Com dublês de `ctranslate2` e `sentencepiece`: o que vai para o modelo
     (prefixo `>>spa<<`, `</s>`, beam 4), onde o modelo é
     procurado, e a mensagem quando ele não está em lugar nenhum.

D.   Com o MODELO DE VERDADE. Só roda onde ele existe: no workflow de release
     (Windows), que o prepara ANTES dos testes, e no experimento do branch de
     desenvolvimento. Em qualquer outro lugar é PULADO, nunca dá falso verde.
     É a prova de que os marcadores do glossário sobrevivem ao modelo real --
     o dublê de `test_traducao_respostas.py` só prova a ideia.
"""
import importlib.util
import os
import types

import pytest

from sigft.core import tradutor_local as tl


# =============================================================================
# Dublês
# =============================================================================
class _Resultado:
    def __init__(self, tokens):
        self.hypotheses = [tokens]


class _TranslatorFalso:
    criados = []

    def __init__(self, pasta, **kwargs):
        self.pasta = pasta
        self.kwargs = kwargs
        self.chamadas = []
        _TranslatorFalso.criados.append(self)

    def translate_batch(self, lote, **kwargs):
        self.chamadas.append((lote, kwargs))
        # "traduz" devolvendo os tokens de origem sem o prefixo e sem o </s>
        return [_Resultado([t for t in fonte if t not in (tl.PREFIXO_ES, tl.FIM)])
                for fonte in lote]


class _SentencePieceFalso:
    def __init__(self, model_file):
        self.model_file = model_file

    def encode(self, texto, out_type=str):
        return ["▁" + p for p in texto.split(" ")]

    def decode(self, pecas):
        return "".join(pecas).replace("▁", " ").strip()


def _modulos_falsos():
    _TranslatorFalso.criados = []
    ct2 = types.SimpleNamespace(Translator=_TranslatorFalso)
    spm = types.SimpleNamespace(SentencePieceProcessor=_SentencePieceFalso)
    return ct2, spm


def _pasta_de_modelo(tmp_path, nome="modelo"):
    pasta = tmp_path / nome
    pasta.mkdir()
    for arquivo in tl.ARQUIVOS_DO_MODELO:
        (pasta / arquivo).write_bytes(b"x")
    return pasta


# =============================================================================
# A. O que vai para o modelo
# =============================================================================
def test_cada_texto_vai_com_prefixo_do_espanhol_e_fim(tmp_path):
    ct2, spm = _modulos_falsos()
    motor = tl.TradutorLocal(_pasta_de_modelo(tmp_path), ctranslate2=ct2, sentencepiece=spm)
    saida = motor.traduzir(["Aço carbono", "Sim"])
    assert saida == ["Aço carbono", "Sim"]
    [(lote, kwargs)] = _TranslatorFalso.criados[0].chamadas
    assert lote[0] == [tl.PREFIXO_ES, "▁Aço", "▁carbono", tl.FIM]
    assert lote[1] == [tl.PREFIXO_ES, "▁Sim", tl.FIM]


def test_beam_4_e_desconhecido_nao_e_copiado(tmp_path):
    """Pedir ao modelo para COPIAR o desconhecido (`replace_unknowns`) trouxe o
    próprio prefixo `>>spa<<` no lugar do `Ø` (medido em 2026-09-25, rodada 3).
    O símbolo vai protegido por `traducao_respostas`, e o que escapar sai como
    `⁇`, que lá vira `conferir`."""
    ct2, spm = _modulos_falsos()
    motor = tl.TradutorLocal(_pasta_de_modelo(tmp_path), ctranslate2=ct2, sentencepiece=spm)
    motor.traduzir(["Ø 36 mm"])
    _, kwargs = _TranslatorFalso.criados[0].chamadas[0]
    assert kwargs["beam_size"] == 4
    assert not kwargs.get("replace_unknowns")


def test_lista_vazia_nao_carrega_o_modelo(tmp_path):
    ct2, spm = _modulos_falsos()
    motor = tl.TradutorLocal(_pasta_de_modelo(tmp_path), ctranslate2=ct2, sentencepiece=spm)
    assert motor.traduzir([]) == []
    assert _TranslatorFalso.criados == []


def test_modelo_carrega_uma_vez_so(tmp_path):
    ct2, spm = _modulos_falsos()
    motor = tl.TradutorLocal(_pasta_de_modelo(tmp_path), ctranslate2=ct2, sentencepiece=spm)
    motor.traduzir(["a b"])
    motor.traduzir(["c d"])
    assert len(_TranslatorFalso.criados) == 1


def test_o_motor_serve_como_funcao(tmp_path):
    """`traduzir_respostas` recebe um CALLABLE (`motor(textos)`)."""
    ct2, spm = _modulos_falsos()
    motor = tl.TradutorLocal(_pasta_de_modelo(tmp_path), ctranslate2=ct2, sentencepiece=spm)
    assert motor(["x y"]) == ["x y"]


# =============================================================================
# B. Onde o modelo é procurado
# =============================================================================
def test_variavel_de_ambiente_vence(tmp_path, monkeypatch):
    pasta = _pasta_de_modelo(tmp_path, "da_variavel")
    monkeypatch.setenv(tl.VARIAVEL_AMBIENTE, str(pasta))
    assert tl.localizar_modelo() == pasta


def test_pasta_incompleta_nao_serve(tmp_path, monkeypatch):
    pasta = tmp_path / "meia"
    pasta.mkdir()
    (pasta / "model.bin").write_bytes(b"x")
    monkeypatch.setenv(tl.VARIAVEL_AMBIENTE, str(pasta))
    monkeypatch.setattr(tl, "_pastas_padrao", lambda: [])
    with pytest.raises(tl.ModeloAusente):
        tl.localizar_modelo()


def test_procura_nas_pastas_padrao_em_ordem(tmp_path, monkeypatch):
    primeira, segunda = tmp_path / "vazia", _pasta_de_modelo(tmp_path, "boa")
    monkeypatch.delenv(tl.VARIAVEL_AMBIENTE, raising=False)
    monkeypatch.setattr(tl, "_pastas_padrao", lambda: [primeira, segunda])
    assert tl.localizar_modelo() == segunda


def test_pastas_padrao_incluem_o_pacote_o_repositorio_e_documentos(monkeypatch, tmp_path):
    monkeypatch.setattr("sigft.core.dados_usuario.pasta_dados", lambda: tmp_path / "docs")
    pastas = [str(p).replace("\\", "/") for p in tl._pastas_padrao()]
    assert any(p.endswith("modelos/tradutor_pt_es") for p in pastas)
    assert any(p.endswith("recursos/tradutor_pt_es") for p in pastas)
    assert str(tmp_path / "docs" / "modelos" / "tradutor_pt_es").replace("\\", "/") in pastas


def test_modelo_ausente_diz_onde_procurou_e_o_que_fazer(tmp_path, monkeypatch):
    monkeypatch.delenv(tl.VARIAVEL_AMBIENTE, raising=False)
    monkeypatch.setattr(tl, "_pastas_padrao", lambda: [tmp_path / "a", tmp_path / "b"])
    with pytest.raises(tl.ModeloAusente) as erro:
        tl.localizar_modelo()
    mensagem = str(erro.value)
    assert str(tmp_path / "a") in mensagem and str(tmp_path / "b") in mensagem
    assert "preparar_tradutor" in mensagem


def test_sem_pasta_explicita_o_motor_localiza_na_carga(tmp_path, monkeypatch):
    pasta = _pasta_de_modelo(tmp_path)
    monkeypatch.setenv(tl.VARIAVEL_AMBIENTE, str(pasta))
    ct2, spm = _modulos_falsos()
    tl.TradutorLocal(ctranslate2=ct2, sentencepiece=spm).traduzir(["a"])
    assert _TranslatorFalso.criados[0].pasta == str(pasta)


def test_sem_o_pacote_ctranslate2_a_mensagem_diz_o_que_instalar(tmp_path, monkeypatch):
    pasta = _pasta_de_modelo(tmp_path)

    def sem_pacote(nome):
        raise ImportError(f"No module named '{nome}'")

    monkeypatch.setattr(tl.importlib, "import_module", sem_pacote)
    with pytest.raises(tl.TradutorIndisponivel) as erro:
        tl.TradutorLocal(pasta).traduzir(["a"])
    assert "requirements" in str(erro.value)


# =============================================================================
# C. A instância do processo
# =============================================================================
def test_obter_devolve_sempre_a_mesma_instancia(monkeypatch):
    monkeypatch.setattr(tl, "_instancia", None)
    assert tl.obter() is tl.obter()


# =============================================================================
# D. O modelo DE VERDADE (pulado onde ele não existe)
# =============================================================================
def _modelo_real():
    if importlib.util.find_spec("ctranslate2") is None:
        return None
    try:
        return tl.localizar_modelo()
    except tl.ModeloAusente:
        return None


_REAL = _modelo_real()
com_modelo_real = pytest.mark.skipif(
    _REAL is None, reason="modelo local nao preparado nesta maquina (tools/preparar_tradutor.py)")


@com_modelo_real
def test_modelo_real_traduz_o_basico():
    motor = tl.TradutorLocal(_REAL)
    saida = motor.traduzir(["Aço inoxidável", "Cobre eletrolítico"])
    assert "acero inoxidable" in saida[0].lower()
    assert "electrol" in saida[1].lower()


@com_modelo_real
def test_modelo_real_preserva_o_simbolo_de_diametro():
    from sigft.services import traducao_respostas as tr
    [saida] = tr.traduzir_respostas(["Diâmetro externo Ø 150 mm"], tl.TradutorLocal(_REAL))
    assert saida.origem == "tradutor", saida
    assert "Ø" in saida.texto and "150" in saida.texto and "⁇" not in saida.texto
    assert ">>" not in saida.texto


@com_modelo_real
@pytest.mark.parametrize("original, esperado", [
    ("PORCA SEXTAVADA", "tuerca"),
    ("Mancal de deslizamento", "cojinete"),
    ("Arruela de pressão", "arandela"),
    ("Filtro de óleo do mancal guia", "cojinete"),
    ("Chave fim de curso", "fin de carrera"),
    ("Aço SAE 1045 temperado e revenido", "revenido"),
    ("Escova de carvão para anel coletor do gerador", "escobilla"),
    ("Mancais de rolamento lubrificados a óleo", "cojinetes"),
    ("Válvula gaveta com haste ascendente", "compuerta con"),
])
def test_modelo_real_com_o_glossario_da_casa(original, esperado):
    """Os erros medidos em 2026-09-25, agora com as três versões."""
    from sigft.services import traducao_respostas as tr
    motor = tl.TradutorLocal(_REAL)
    [saida] = tr.traduzir_respostas([original], motor, tr.glossario_em_uso())
    assert esperado in saida.texto.lower(), (saida, os.environ.get("GITHUB_JOB"))
    assert saida.origem in ("tradutor", "glossario"), saida

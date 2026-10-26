r"""
AutoSpec diz ONDE o tempo foi (2026-10-20).

Log do Luan na 1.2.1-rc.8: uma ficha levou 5min 03s e o log não dizia em quê
-- a suspeita era o LlamaParse com o PDF escaneado, mas sem tempo por passo
era hipótese. Pedido do Jonathan: *"que ele nos reporte o que faz e que
funcione da mesma forma"*. Por isso estes testes cobram SÓ o relato: nenhum
passo muda, nenhum limite de tempo é imposto.
"""
from __future__ import annotations

import itertools

import pytest

from sigft.services import autospec
from sigft.services.autospec import AutoSpecCore


@pytest.fixture
def relogio(monkeypatch):
    """Cada leitura do relógio avança 10 s: a conta fica previsível."""
    contador = itertools.count(0, 10)
    monkeypatch.setattr(autospec, "_agora", lambda: next(contador))


def _core_fake(falhar_na_ia=False):
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.analyze_sheet = lambda ficha, status: (
        "wb", {"campo_x": {"type": "text", "desc": "Campo X", "ref": "H1"}},
        "txt", "fab", "desc", "cod")

    def contexto(*a, **k):
        core._tempos_do_contexto = {"documentos locais": 120.0, "busca na web": 30.0}
        return "contexto", []

    core.retrieve_context = contexto
    if falhar_na_ia:
        def ia(*a, **k):
            raise RuntimeError("IA fora")
        core.generate_ai_response = ia
    else:
        core.generate_ai_response = lambda *a, **k: {"campo_x": "valor"}
    core.fill_save = lambda wb, ficha, dados, faltando, **k: "A_completed.xlsx"
    return core


def _linha_de_tempos(linhas):
    achadas = [linha for linha in linhas if linha.strip().startswith("-> Tempos:")]
    assert len(achadas) == 1, linhas
    return achadas[0]


def test_cada_ficha_termina_com_a_linha_de_tempos(relogio):
    linhas = list(_core_fake().process_queue([{"sheet": "A.xlsx", "refs": []}], None))
    tempos = _linha_de_tempos(linhas)

    # Os sub-passos do contexto entram com o nome deles, e não como um
    # "contexto" só: é lá que mora a suspeita (PDF local / LlamaParse).
    assert "documentos locais 2min 00s" in tempos
    assert "busca na web 30,0s" in tempos
    assert "IA " in tempos
    assert "salvar " in tempos
    assert "(total " in tempos


def test_o_passo_mais_demorado_vem_primeiro(relogio):
    tempos = _linha_de_tempos(list(_core_fake().process_queue(
        [{"sheet": "A.xlsx", "refs": []}], None)))
    corpo = tempos.split("Tempos:", 1)[1]
    assert corpo.strip().startswith("documentos locais")


def test_ficha_que_falha_tambem_diz_onde_o_tempo_foi(relogio):
    linhas = list(_core_fake(falhar_na_ia=True).process_queue(
        [{"sheet": "A.xlsx", "refs": []}], None))
    assert any("ERRO" in linha for linha in linhas)
    assert "documentos locais" in _linha_de_tempos(linhas)


def test_fake_antigo_sem_os_tempos_do_contexto_nao_quebra(relogio):
    core = _core_fake()
    core.retrieve_context = lambda *a, **k: ("contexto", [])
    tempos = _linha_de_tempos(list(core.process_queue([{"sheet": "A.xlsx", "refs": []}], None)))
    assert "documentos e busca" in tempos


# =============================================================================
# LlamaParse: o relato de quanto ele levou, sem mudar nada no que ele faz
# =============================================================================
class _LlamaParseQueDevolveVazio:
    chamadas = []

    def __init__(self, **kwargs):
        _LlamaParseQueDevolveVazio.chamadas.append(kwargs)

    def load_data(self, caminho):
        return []


def _core_com_llama(monkeypatch, classe):
    core = autospec.PDFProcessor.__new__(autospec.PDFProcessor)
    core.llama_key = "chave"
    monkeypatch.setattr(autospec, "LlamaParse", classe)
    monkeypatch.setattr(autospec, "_ler_pdf_local", lambda caminho: ("", None))
    monkeypatch.setattr(autospec.pypdf, "PdfReader", lambda caminho: type(
        "R", (), {"pages": []})())
    return core


def test_llamaparse_diz_quanto_levou_e_quanto_devolveu(monkeypatch, relogio, tmp_path):
    _LlamaParseQueDevolveVazio.chamadas.clear()
    core = _core_com_llama(monkeypatch, _LlamaParseQueDevolveVazio)
    linhas = []
    cb = autospec.UICallbacks(log=lambda msg, nivel="info", contexto=None: linhas.append(str(msg)))
    pdf = tmp_path / "sensor.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    core.extract_text(str(pdf), callbacks=cb)

    texto = "\n".join(linhas)
    assert "LlamaParse respondeu em 10,0s, mas sem texto (0 caracteres)" in texto
    # Só `ignore_errors=False` a mais: sem ele a biblioteca engole o erro
    # (print + lista vazia) e o log não tem como dizer o motivo. Nenhum
    # limite de tempo novo -- o pedido foi relatar, não mudar.
    assert _LlamaParseQueDevolveVazio.chamadas == [{"result_type": "text", "ignore_errors": False}]


class _Doc:
    def __init__(self, texto):
        self.text = texto


class _LlamaParseQueLe(_LlamaParseQueDevolveVazio):
    def load_data(self, caminho):
        return [_Doc("Tensão nominal 24 V")]


def test_llamaparse_que_le_diz_sucesso_com_tempo(monkeypatch, relogio, tmp_path):
    core = _core_com_llama(monkeypatch, _LlamaParseQueLe)
    linhas = []
    cb = autospec.UICallbacks(log=lambda msg, nivel="info", contexto=None: linhas.append(str(msg)))
    pdf = tmp_path / "sensor.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    texto, metodo = core.extract_text(str(pdf), callbacks=cb)

    assert "Tensão nominal" in texto
    assert any("LlamaParse leu sensor.pdf: 19 caracteres em 10,0s" in linha for linha in linhas)


class _LlamaParseQueEstoura(_LlamaParseQueDevolveVazio):
    def load_data(self, caminho):
        raise TimeoutError("sem resposta")


def test_llamaparse_que_falha_diz_depois_de_quanto_tempo(monkeypatch, relogio, tmp_path):
    core = _core_com_llama(monkeypatch, _LlamaParseQueEstoura)
    linhas = []
    cb = autospec.UICallbacks(log=lambda msg, nivel="info", contexto=None: linhas.append(str(msg)))
    pdf = tmp_path / "sensor.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    core.extract_text(str(pdf), callbacks=cb)

    assert any("LlamaParse falhou em sensor.pdf depois de 10,0s" in linha
               and "nao respondeu a tempo" in linha for linha in linhas)


class ProxyError(Exception):
    """Mesmo nome da classe do httpx: a classificação olha o NOME."""


class ConnectError(Exception):
    pass


class _Resposta401(Exception):
    pass


@pytest.mark.parametrize("erro,motivo", [
    (ProxyError("403 Forbidden"), "o proxy da empresa bloqueou a conexao"),
    (Exception("CONNECT tunnel failed, response 403"), "o proxy da empresa bloqueou a conexao"),
    (ConnectError("[Errno 11001] getaddrinfo failed"), "sem conexao com a LlamaCloud"),
    (Exception("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"),
     "o certificado da conexao foi recusado"),
    (TimeoutError("timed out"), "a LlamaCloud nao respondeu a tempo"),
    (_Resposta401("401 Unauthorized: Invalid API Key"), "a chave do LlamaParse foi recusada"),
    (Exception("429 Too Many Requests"), "limite de uso da LlamaCloud"),
    (ValueError("outra coisa"), "ValueError: outra coisa"),
])
def test_motivo_da_falha_e_diferenciado(erro, motivo):
    assert motivo in autospec.motivo_da_falha_de_rede(erro)

"""`--smoke` da interface Qt: o que o Release le do `.exe` (E6.1).

Desde o corte, `SIG-FT.exe --smoke` e respondido pela Qt. O `release.yml` le o
`conferencia-da-janela.txt` porque o `.exe` e `console=False`: o que ele
imprime NAO chega ao CI. Um smoke que so imprime reprova com "codigo 1" e mais
nada -- foi o run #3 de 2026-09-21, contado no `_smoke` de `sigft/app/main.py`.
Por isso o relatorio e gravado nos dois caminhos, com os avisos de backend.

E as telas Qt nascem na PRIMEIRA visita (fabricas de `TELAS`): um modulo de
tela que ficou fora do pacote so apareceria quando alguem clicasse no menu. O
smoke visita todas (menos as bloqueadas no menu), e tela que vira
`TelaComErro` reprova, com o nome e o motivo no relatorio.
"""
import pytest
from PySide6.QtWidgets import QWidget

from sigft.app import conferencia
from sigft.app_qt import catalogo
from sigft.app_qt import main as qmain


@pytest.fixture
def relatorio(qt_interface, monkeypatch, tmp_path):
    """Caminho do relatorio, num diretorio limpo (e no de trabalho que o smoke
    grava), sem backends de verdade e com as chaves num arquivo temporario."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.setattr(qmain.backends, "carregar_todos", lambda **k: None)
    return tmp_path / conferencia.ARQUIVO_JANELA


def _fabrica_que_anota(visitadas, chave):
    def criar(parent, controller):
        visitadas.append(chave)
        return QWidget(parent)
    return criar


def _fabrica_que_quebra(erro):
    def criar(parent, controller):
        raise erro
    return criar


def _ler(arquivo):
    return arquivo.read_text(encoding="utf-8")


# -- o relatorio em arquivo ----------------------------------------------------

def test_grava_o_relatorio_tambem_quando_da_certo(relatorio):
    """O passo do workflow imprime o arquivo sempre. Se ele so existisse na
    falha, um arquivo velho de outro build seria lido como se fosse deste."""
    assert qmain._smoke() == 0
    assert relatorio.is_file()
    assert "FALHOU" not in _ler(relatorio)


def test_aviso_de_backend_vai_para_o_relatorio(relatorio, monkeypatch):
    """Backend que nao carregou nao reprova (o app abre igual, de proposito),
    mas tem de estar escrito antes de chegar ao usuario."""
    def carregar(ao_falhar=None, **_):
        ao_falhar("AutoSpec RAG", ImportError("No module named 'faiss'"))

    monkeypatch.setattr(qmain.backends, "carregar_todos", carregar)

    assert qmain._smoke() == 0
    texto = _ler(relatorio)
    assert "AutoSpec RAG" in texto and "faiss" in texto


def test_grava_o_motivo_quando_a_janela_nao_monta(relatorio, monkeypatch):
    """Sem o motivo gravado, um smoke vermelho e um beco sem saida."""
    def janela_que_quebra():
        raise RuntimeError("widget orfao aqui")

    monkeypatch.setattr(qmain, "SIG_FT_App", janela_que_quebra)

    assert qmain._smoke() == 1
    texto = _ler(relatorio)
    assert "RuntimeError" in texto and "widget orfao aqui" in texto
    assert "Traceback" in texto, "sem a pilha nao da para saber o que quebrou"


def test_aviso_de_backend_vai_para_o_relatorio_tambem_na_falha(relatorio, monkeypatch):
    """O backend que nao carregou costuma ser a PISTA da falha da janela."""
    def carregar(ao_falhar=None, **_):
        ao_falhar("Tradutor", ImportError("No module named 'ctranslate2'"))

    def janela_que_quebra():
        raise RuntimeError("quebrou")

    monkeypatch.setattr(qmain.backends, "carregar_todos", carregar)
    monkeypatch.setattr(qmain, "SIG_FT_App", janela_que_quebra)

    assert qmain._smoke() == 1
    assert "ctranslate2" in _ler(relatorio)


# -- a visita as telas -----------------------------------------------------------

def test_visita_todas_as_telas_registradas_menos_as_bloqueadas(relatorio, monkeypatch):
    visitadas = []
    telas = {chave: _fabrica_que_anota(visitadas, chave)
             for chave in ("Home", "Primeira", "Segunda", "Fechada")}
    monkeypatch.setattr(qmain, "TELAS", telas)
    monkeypatch.setattr(catalogo, "TELAS_BLOQUEADAS", frozenset({"Fechada"}))

    assert qmain._smoke() == 0
    assert set(visitadas) == {"Home", "Primeira", "Segunda"}


def test_tela_que_nao_abre_reprova_com_o_nome_e_o_motivo(relatorio, monkeypatch):
    visitadas = []
    monkeypatch.setattr(qmain, "TELAS", {
        "Home": _fabrica_que_anota(visitadas, "Home"),
        "Sumida": _fabrica_que_quebra(
            ModuleNotFoundError("No module named 'sigft.app_qt.views.sumida'")),
    })

    assert qmain._smoke() == 1
    texto = _ler(relatorio)
    assert "Sumida" in texto
    assert "ModuleNotFoundError" in texto and "sigft.app_qt.views.sumida" in texto
    assert "Traceback" in texto, "sem a pilha nao da para saber QUAL import faltou"


def test_uma_tela_quebrada_nao_esconde_as_outras(relatorio, monkeypatch):
    """Cada hipotese no Release custa um build inteiro: o relatorio tem de
    trazer TODAS as telas que nao abrem, nao so a primeira."""
    visitadas = []
    monkeypatch.setattr(qmain, "TELAS", {
        "Home": _fabrica_que_anota(visitadas, "Home"),
        "Quebrada1": _fabrica_que_quebra(ImportError("falta o modulo um")),
        "Inteira": _fabrica_que_anota(visitadas, "Inteira"),
        "Quebrada2": _fabrica_que_quebra(ImportError("falta o modulo dois")),
    })

    assert qmain._smoke() == 1
    texto = _ler(relatorio)
    assert "Quebrada1" in texto and "falta o modulo um" in texto
    assert "Quebrada2" in texto and "falta o modulo dois" in texto
    assert "Inteira" in visitadas


# -- os icones (sistema visual, Task 6, 2026-10-20) -----------------------------

def test_icone_que_nao_desenha_reprova_o_smoke(relatorio, monkeypatch):
    """Um SVG (ou o QtSvg) que ficou fora do `.exe` daria botoes em branco sem
    erro nenhum -- a mesma classe do pymupdf-layout de 2026-10-20, um arquivo
    que falta so no pacote. O smoke do Release desenha os icones e reprova."""
    from sigft.app_qt import icones

    monkeypatch.setattr(icones, "conferir", lambda: ["house"])

    assert qmain._smoke() == 1
    texto = _ler(relatorio)
    assert "FALHOU" in texto and "house" in texto

import threading
from pathlib import Path

import pytest

from sigft.app_qt.widgets import console as qconsole

# Caminho a partir deste arquivo, não do cwd: outro teste da suíte faz os.chdir
# (test_llm_comparacao.py) sem restaurar, e o cwd não é a raiz quando este roda.
RAIZ = Path(__file__).resolve().parents[1]


def test_prefixo_e_formato_da_linha_sao_os_de_sempre():
    """O `"> "` que as 12 telas escreviam desde o monolito (era comparado com o
    console da interface antiga, que saiu em 2026-10-15; agora o valor fica
    travado aqui)."""
    assert qconsole.PREFIXO_LINHA == "> "
    assert qconsole.formatar_linha("oi") == "> oi"


@pytest.mark.parametrize("entrada, esperado", [
    ("texto", "> texto"), (42, "> 42"), (3.5, "> 3.5"), (None, "> None"), ("", "> "),
    ("com\nquebra", "> com\nquebra"), (ValueError("falhou"), "> falhou"),
])
def test_formatar_linha_aceita_qualquer_objeto(entrada, esperado):
    """As telas antigas caíam numa f-string, que aceita qualquer coisa: um
    TypeError aqui seria regressão num caminho de log -- o que só roda quando
    algo já deu errado. (Portado de `test_app_widgets.py`.)"""
    assert qconsole.formatar_linha(entrada) == esperado


def test_log_aceita_o_protocolo_e_o_nivel_nao_muda_a_renderizacao(qt_interface, qtbot):
    """`core/callbacks.py`: o nível não muda a RENDERIZAÇÃO (só o filtro o usa, 2026-10-21). Dar cor/prefixo a `error`
    seria mudar a aparência sem decisão. E `UICallbacks(log=console.log)`
    funciona direto, sem adaptador. (Portado de `test_app_widgets.py`.)"""
    from sigft.core.callbacks import UICallbacks

    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.log("msg", "error", {"pmib": "123"})
    for nivel in ("info", "warn", "error", "debug"):
        c.log("igual", nivel=nivel, contexto={"a": 1})
    UICallbacks(log=c.log).log("do serviço", nivel="info")
    qtbot.waitUntil(lambda: c.blockCount() >= 6, timeout=2000)
    assert c.toPlainText().splitlines() == ["> msg", *["> igual"] * 4, "> do serviço"]


def test_linhas_de_thread_chegam_em_ordem(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)

    def worker():
        for i in range(500):
            c.log(f"linha {i}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join()
    qtbot.waitUntil(lambda: c.blockCount() >= 500, timeout=3000)
    linhas = c.toPlainText().splitlines()
    assert linhas[0] == "> linha 0" and linhas[-1] == "> linha 499" and len(linhas) == 500


def test_aceita_qualquer_objeto(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.log(ValueError("x"))
    c.log(42)
    qtbot.waitUntil(lambda: c.blockCount() >= 2, timeout=2000)
    assert c.toPlainText().splitlines() == ["> x", "> 42"]


def test_somente_leitura_e_altura(qt_interface, qtbot):
    c = qconsole.ConsoleFrame(altura=120)
    qtbot.addWidget(c)
    assert c.isReadOnly() and c.height() == 120
    livre = qconsole.ConsoleFrame(altura=None)
    qtbot.addWidget(livre)
    assert livre.maximumHeight() > 120


def test_widget_destruido_nao_derruba_o_worker(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    c.log("antes")
    c.deleteLater()
    qtbot.wait(100)
    c.log("depois")  # não pode levantar


def test_texto_comeca_onde_comeca_no_ctktextbox(qt_interface, qtbot):
    # Medido nas capturas do polimento (Tradutor, PDM e Upload, interface antiga x Qt): no
    # CTkTextbox o texto começa 4 px mais à direita e 5 px mais abaixo que no
    # QPlainTextEdit cru (base da 1a linha e começo do ">"). O documento já tem
    # a margem de 4 do Qt; o recuo que falta vem da vista do console.
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QTextCursor

    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())   # #console: sem borda
    try:
        c = qconsole.ConsoleFrame()
        qtbot.addWidget(c)
        c.resize(400, 150)
        c.show()
        qtbot.waitExposed(c)
        primeira = c.cursorRect(QTextCursor(c.document())).topLeft()
        assert c.viewport().mapTo(c, primeira) == QPoint(4 + 4, 4 + 5)
        # A barra de rolagem não anda: o recuo é só da vista.
        barra = c.verticalScrollBar()
        assert barra.mapTo(c, barra.rect().topLeft()).y() == 0
    finally:
        qt_interface.setStyleSheet(anterior)


# --- filtro, busca e Copiar (2026-10-21, etapa 1b) ---------------------------------

MISTURA = [
    ("tudo certo", "info"),
    ("[Erro] Ficha 4500063671.0001 não encontrada", "info"),
    ("[Aviso] tabela vazia", "info"),
    ("Tensão nominal gravada", "info"),
    ("❌ 4500063671.0002: TimeoutError", "error"),
]


def _console_com(qtbot, linhas):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    for msg, nivel in linhas:
        c.log(msg, nivel)
    qtbot.waitUntil(lambda: c.blockCount() >= len(linhas), timeout=2000)
    return c


def test_filtro_erros_e_avisos(qt_interface, qtbot):
    c = _console_com(qtbot, MISTURA)
    c.filtrar("erros")
    assert c.toPlainText().splitlines() == ["> [Erro] Ficha 4500063671.0001 não encontrada",
                                            "> ❌ 4500063671.0002: TimeoutError"]
    assert c.barra.botoes["erros"].isChecked()
    c.filtrar("avisos")   # avisos E erros: tudo o que pede atenção
    assert len(c.toPlainText().splitlines()) == 3
    c.barra.botoes["tudo"].click()
    assert len(c.toPlainText().splitlines()) == 5


def test_busca_sem_acento_e_sem_caixa(qt_interface, qtbot):
    c = _console_com(qtbot, MISTURA)
    c.barra.campo.setText("TENSAO")
    assert c.toPlainText().splitlines() == ["> Tensão nominal gravada"]
    c.barra.campo.clear()
    assert len(c.toPlainText().splitlines()) == 5


def test_linha_nova_respeita_o_filtro(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.filtrar("erros")
    c.log("comum")
    c.log("[ERRO] ruim")
    qtbot.waitUntil(lambda: "ruim" in c.toPlainText(), timeout=2000)
    assert c.toPlainText().splitlines() == ["> [ERRO] ruim"]
    assert [linha.msg for linha in c.linhas()] == ["comum", "[ERRO] ruim"]   # guardou as duas


def test_copiar_leva_o_que_esta_a_vista(qt_interface, qtbot):
    from PySide6.QtWidgets import QApplication

    c = _console_com(qtbot, MISTURA)
    c.filtrar("erros")
    c.barra.copiar.click()
    assert QApplication.clipboard().text() == c.toPlainText()
    assert c.barra.copiar.text() == qconsole.TEXTO_COPIADO


def test_marca_e_linhas_desde(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.log("antes")
    marca = c.marca()
    c.log("[Erro] depois", "info")
    assert [(linha.msg, linha.nivel) for linha in c.linhas(desde=marca)] == [("[Erro] depois", "erro")]


def test_limpar_esquece_as_linhas_mas_nao_a_contagem(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.log("a")
    marca = c.marca()
    c.clear()
    assert c.linhas() == [] and c.toPlainText() == ""
    c.log("b")
    assert [linha.msg for linha in c.linhas(desde=marca)] == ["b"]


def test_barra_fica_embaixo_sem_mudar_a_altura(qt_interface, qtbot):
    c = qconsole.ConsoleFrame(altura=150)
    qtbot.addWidget(c)
    c.resize(400, 150)
    c.show()
    qtbot.waitExposed(c)
    vista = c.viewport().geometry()
    assert c.height() == 150
    assert c.barra.geometry().top() == vista.bottom() + 1
    assert c.barra.height() == qconsole.ALTURA_BARRA
    assert c.barra.geometry().right() == vista.right()   # não cobre a barra de rolagem


def test_barra_e_escura_nos_dois_temas():
    from sigft.app import tokens
    from sigft.app_qt import estilo

    for tema in ("escuro", "claro"):
        assert f"#barra_console {{ background: {tokens.ESCURO['console_fundo']}; }}" in \
            estilo.folha_de_estilo(tema)

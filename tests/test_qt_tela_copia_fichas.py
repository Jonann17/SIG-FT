"""Tela "Cópia de Fichas" (duplicadas) na interface Qt: leitura da planilha,
seleção, revisão e o robô com serviços falsos, e medidas contra o CustomTkinter."""
import threading

import pytest

from sigft.app import theme
from sigft.app.textos_dialogos import MSG_LOGIN_LOTE
from sigft.app_qt.views import copia_fichas as tela_mod
from sigft.services import duplicadas, duplicadas_robo


def _ficha(pmib, original, material="M-1", linha=2, descricao="VALVULA"):
    return duplicadas.FichaDuplicada(pmib=pmib, descricao=descricao, pdm_usado="PDM.9900.000.1",
                                     codigo_material=material, codigo_fornecedor="F-1",
                                     ficha_original=original, linha=linha)


FICHAS = [
    _ficha("4500063672.0001", "4500063671.0001", linha=2),
    _ficha("4500063672.0002", "ver ficha do motor", linha=3, descricao=""),
    _ficha("4500063672.0003", "", linha=4),                     # sem original: fora da fila
]


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloCopiaFichas(None, None)
    qtbot.addWidget(t)
    t.selecoes = []
    t.revisoes = []
    monkeypatch.setattr(tela_mod, "JanelaSelecaoDuplicadas", lambda p, fila, cb: t.selecoes.append(
        (fila, cb, threading.current_thread() is threading.main_thread())))
    monkeypatch.setattr(tela_mod, "JanelaRevisaoEdicao", lambda p, fila: t.revisoes.append(fila))
    return t


def _leitura(monkeypatch, fichas=FICHAS, falha=None, liberar=None):
    chamadas = []

    def localizar(caminho, callback_log=None):
        chamadas.append(caminho)
        callback_log("Lendo a aba _STATUS_PMIB...")
        if liberar is not None:
            liberar.wait(3)
        if falha:
            raise falha
        return list(fichas), f"{len(fichas)} duplicadas na planilha."

    monkeypatch.setattr(tela_mod.duplicadas, "localizar_duplicadas", localizar)
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/_STATUS_PMIB.xlsx")
    return chamadas


def _texto(tela):
    return tela.console.toPlainText()


def _fila(n=2):
    return [{"descricao": f"VALVULA {i}", "pmib_original": f"4500063671.000{i}",
             "pmib_alvo": f"4500063672.000{i}", "codigo_material": "M", "codigo_fornecedor": "F",
             "linha_excel": i + 1} for i in range(1, n + 1)]


# --- montagem -----------------------------------------------------------------

def test_monta_com_os_textos_e_estados(tela):
    assert tela.label_titulo.text() == "Módulo: Cópia de Fichas PMIB"
    assert tela.rotulo_etapa1.text() == "1. Selecionar Arquivo Base"
    assert tela.rotulo_etapa2.text() == "2. Execução"
    assert tela.btn_status.text() == "Selecionar _STATUS_PMIB"
    assert tela.lbl_status.text() == "Aguardando seleção..."
    assert tela.btn_resumo.text() == "1. Revisar / Editar Fichas"
    assert tela.btn_robo_novo.text() == "2. Iniciar Robô Web"
    assert tela.switch_auditoria.text() == "Gravar log de auditoria (com a estrutura das telas)"
    assert tela.switch_auditoria.isChecked()
    assert tela.btn_status.isEnabled()
    assert not tela.btn_resumo.isEnabled() and not tela.btn_robo_novo.isEnabled()
    assert tela.progress.fracao == 0.0                       # o "set(0)" do CTk


def test_cores_dos_botoes_e_rotulos(tela):
    assert tela.btn_status.property("variante") == "cinza"
    assert tela.btn_resumo.property("variante") == "cinza"
    assert tela.btn_robo_novo.property("variante") == "primario"
    assert theme.COLORS["accent"] in tela.rotulo_etapa1.styleSheet()
    assert "#808080" in tela.lbl_status.styleSheet()        # text_color="gray" do Tk
    assert theme.COLORS["accent"] in tela.progress.styleSheet()


# --- leitura da planilha --------------------------------------------------------

def test_cancelar_o_dialogo_nao_faz_nada(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    tela.btn_status.click()
    assert tela.caminho_status is None
    assert tela.btn_status.isEnabled()
    assert _texto(tela) == ""


def test_dialogo_com_a_chave_e_o_filtro_de_la(tela, monkeypatch):
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda *a, **k: pedidos.append((a, k)) or "")
    tela.selecionar_excel_pmib()
    assert pedidos == [(("copia_fichas.status_pmib", "excel"),
                        {"filetypes": [("Excel", "*.xlsx;*.xlsm")]})]


def test_leitura_monta_a_fila_e_abre_a_selecao(tela, qtbot, monkeypatch):
    liberar = threading.Event()
    chamadas = _leitura(monkeypatch, liberar=liberar)
    tela.btn_status.click()
    # Desligado NO CLIQUE, enquanto o Excel é lido.
    assert not tela.btn_status.isEnabled()
    qtbot.waitUntil(lambda: "> Lendo arquivo Excel, aguarde..." in _texto(tela), timeout=2000)
    liberar.set()
    qtbot.waitUntil(lambda: bool(tela.selecoes), timeout=3000)
    qtbot.waitUntil(tela.btn_status.isEnabled, timeout=2000)
    qtbot.waitUntil(lambda: "> 2 fichas identificadas como cópia." in _texto(tela), timeout=2000)

    assert chamadas == ["/d/_STATUS_PMIB.xlsx"]
    assert tela.caminho_status == "/d/_STATUS_PMIB.xlsx"
    texto = _texto(tela)
    assert "> Lendo a aba _STATUS_PMIB..." in texto
    assert "> 3 duplicadas na planilha." in texto
    assert (">    [Fora da fila] linha 4 (4500063672.0003): falta ficha original "
            "(coluna OBSERVAÇÕES).") in texto
    assert (">    [Atenção] linha 3 (4500063672.0002): OBSERVAÇÕES não tem código PMIB -- o robô "
            "vai tentar com 'ver ficha do motor'. Confira em 'Revisar / Editar'.") in texto
    assert "> 2 fichas identificadas como cópia." in texto

    assert tela.fila_completa == [
        {"descricao": "VALVULA", "pmib_original": "4500063671.0001", "pmib_alvo": "4500063672.0001",
         "codigo_material": "M-1", "codigo_fornecedor": "F-1", "linha_excel": 2},
        {"descricao": "Sem Descrição", "pmib_original": "ver ficha do motor",
         "pmib_alvo": "4500063672.0002", "codigo_material": "M-1", "codigo_fornecedor": "F-1",
         "linha_excel": 3},
    ]
    assert len(tela.impedidas) == 1
    fila, cb, na_interface = tela.selecoes[0]
    assert fila is tela.fila_completa and cb == tela._pos_selecao and na_interface
    assert tela.lbl_status.text() == ("Planilha carregada. Encontradas 2 duplicadas. "
                                      "(1 sem dados para o robô. Ver log.)")
    assert theme.COLORS["accent"] in tela.lbl_status.styleSheet()
    # Depois da leitura o botão fica com o fundo primary (o hover continua o #454545).
    assert f"background: {theme.COLORS['primary']}" in tela.btn_status.styleSheet()
    assert "#454545" in tela.btn_status.styleSheet()


def test_leitura_sem_duplicadas_nao_abre_a_selecao(tela, qtbot, monkeypatch):
    _leitura(monkeypatch, fichas=[])
    tela.btn_status.click()
    qtbot.waitUntil(lambda: "> 0 fichas identificadas como cópia." in _texto(tela), timeout=3000)
    qtbot.waitUntil(tela.btn_status.isEnabled, timeout=2000)
    assert tela.selecoes == []
    assert tela.lbl_status.text() == "Planilha carregada. Encontradas 0 duplicadas."


def test_falha_na_leitura_vira_log_e_devolve_o_botao(tela, qtbot, monkeypatch):
    _leitura(monkeypatch, falha=ValueError("coluna PDM ausente"))
    tela.btn_status.click()
    qtbot.waitUntil(lambda: "> Falha na leitura: coluna PDM ausente" in _texto(tela), timeout=3000)
    qtbot.waitUntil(tela.btn_status.isEnabled, timeout=2000)
    assert tela.selecoes == []
    assert tela.lbl_status.text() == "Aguardando seleção..."
    assert theme.COLORS["primary"] not in tela.btn_status.styleSheet()


def test_leitura_em_thread_comum(tela, qtbot, monkeypatch):
    # Thread comum (não daemon): é tarefa da pessoa, o "X" pergunta antes de fechar.
    liberar = threading.Event()
    _leitura(monkeypatch, liberar=liberar)
    antes = set(threading.enumerate())
    tela.btn_status.click()
    novas = [t for t in threading.enumerate() if t not in antes]
    try:
        assert novas and not any(t.daemon for t in novas)
    finally:
        liberar.set()
    qtbot.waitUntil(tela.btn_status.isEnabled, timeout=3000)


# --- seleção e revisão ------------------------------------------------------------

def test_pos_selecao_liga_os_botoes(tela, qtbot):
    fila = _fila(3)
    tela._pos_selecao(fila)
    assert tela.fila_selecionada is fila
    assert tela.lbl_status.text() == "3 fichas na fila para processar."
    qtbot.waitUntil(lambda: "> Fila final configurada com 3 fichas." in _texto(tela), timeout=2000)
    assert tela.btn_resumo.isEnabled() and tela.btn_robo_novo.isEnabled()
    tela._pos_selecao([])
    assert tela.lbl_status.text() == "0 fichas na fila para processar."
    assert not tela.btn_resumo.isEnabled() and not tela.btn_robo_novo.isEnabled()


def test_revisar_abre_a_janela_com_a_fila(tela):
    tela.abrir_revisao()
    assert tela.revisoes == []
    fila = _fila(2)
    tela._pos_selecao(fila)
    tela.btn_resumo.click()
    assert tela.revisoes == [fila]


def test_selecao_de_verdade_confirma_para_a_tela(qt_interface, qtbot):
    # Sem dublê: a janela Qt de seleção (tudo marcado) devolve os dicts à tela.
    t = tela_mod.ModuloCopiaFichas(None, None)
    qtbot.addWidget(t)
    t.fila_completa = _fila(3)
    t._pos_leitura_sucesso()
    dialogo = t.janela_selecao
    qtbot.addWidget(dialogo)
    dialogo.confirmar()
    assert t.fila_selecionada == t.fila_completa
    assert t.btn_robo_novo.isEnabled()


# --- robô --------------------------------------------------------------------------

class EngineFalso:
    def __init__(self):
        self.urls = []
        self.fechado = False

    def goto(self, url):
        self.urls.append(url)

    def fechar(self):
        self.fechado = True


class LogFalso:
    criados = []

    def __init__(self, modulo, contexto=None):
        self.modulo, self.contexto = modulo, contexto
        self.caminho = "/logs/duplicadas_1.log"
        self.linhas = []
        self.fechado = False
        LogFalso.criados.append(self)

    def envolver(self, callback):
        def registrar(msg):
            self.linhas.append(msg)
            callback(msg)
        return registrar

    def fechar(self):
        self.fechado = True


@pytest.fixture
def robo(tela, monkeypatch):
    from sigft.core import log_execucao

    estado = {"engine": EngineFalso(), "fichas": None, "marcar": None, "pausas": [],
              "falha": None, "liberar": threading.Event()}
    estado["liberar"].set()
    LogFalso.criados = []

    def processar_lote(fichas, callback_log=None, callback_progresso=None, portal=None,
                       log_auditoria=None):
        estado["fichas"] = fichas
        estado["log_auditoria"] = log_auditoria
        estado["liberar"].wait(3)
        callback_log("ficha 1 ok")
        callback_progresso(0.5)
        if estado["falha"]:
            raise estado["falha"]
        return [type("R", (), {"ok": True})(), type("R", (), {"ok": False})()]

    def marcar(caminho, resultados, callback_log=None):
        estado["marcar"] = (caminho, len(resultados))
        return 2, ["linha 9"]

    monkeypatch.setattr(duplicadas_robo, "iniciar", lambda: (estado["engine"], "portal"))
    monkeypatch.setattr(duplicadas_robo, "processar_lote", processar_lote)
    monkeypatch.setattr(duplicadas_robo, "marcar_status_na_planilha", marcar)
    monkeypatch.setattr(log_execucao, "LogDeExecucao", LogFalso)
    monkeypatch.setattr(tela, "pausar_e_esperar", lambda msg, **k: estado["pausas"].append(
        (msg, threading.current_thread() is threading.main_thread())))
    tela.caminho_status = "/d/_STATUS_PMIB.xlsx"
    tela._pos_selecao(_fila(2))
    return estado


def test_robo_completo_com_auditoria(tela, robo, qtbot):
    # A revisão manual edita os dicts: o robô tem de ler a edição.
    tela.fila_selecionada[0]["pmib_original"] = "4500063671.9999"
    robo["liberar"].clear()
    tela.btn_robo_novo.click()
    # Os três botões desligam NO CLIQUE.
    assert not any(b.isEnabled() for b in (tela.btn_robo_novo, tela.btn_resumo, tela.btn_status))
    robo["liberar"].set()
    qtbot.waitUntil(lambda: "[Auditoria] Log salvo" in _texto(tela), timeout=3000)
    qtbot.waitUntil(tela.btn_robo_novo.isEnabled, timeout=2000)
    assert tela.btn_resumo.isEnabled() and tela.btn_status.isEnabled()

    texto = _texto(tela)
    assert "> [Auditoria] Gravando em: /logs/duplicadas_1.log" in texto
    assert "> [Robô novo] 2 ficha(s) na fila. Abrindo o navegador..." in texto
    assert "> [Robô novo] Marcando o _STATUS_PMIB..." in texto
    assert "> [Robô novo] 1 de 2 sem pendência; 2 linha(s) marcada(s) na planilha, 1 falha(s)." in texto
    assert ("> [Robô novo] Confira no portal o que o log marcou como pendência antes de mudar "
            "o status das fichas.") in texto
    assert "> [Auditoria] Log salvo: /logs/duplicadas_1.log" in texto

    from sigft import config
    assert robo["engine"].urls == [config.PORTAL_URL] and robo["engine"].fechado
    assert robo["pausas"] == [(MSG_LOGIN_LOTE, False)]          # do worker
    fichas = robo["fichas"]
    assert [f.ficha_original for f in fichas] == ["4500063671.9999", "4500063671.0002"]
    assert [f.pmib for f in fichas] == ["4500063672.0001", "4500063672.0002"]
    assert fichas[0].codigo_material == "M" and fichas[0].linha == 2
    assert robo["marcar"] == ("/d/_STATUS_PMIB.xlsx", 2)
    log = LogFalso.criados[0]
    assert log.modulo == "duplicadas" and log.contexto == {"fichas": 2} and log.fechado
    assert robo["log_auditoria"] is log
    assert "[Robô novo] Marcando o _STATUS_PMIB..." in log.linhas
    qtbot.waitUntil(lambda: tela.progress.value() > 0, timeout=2000)


def test_robo_sem_auditoria(tela, robo, qtbot):
    tela.switch_auditoria.setChecked(False)
    tela.run_robo_novo_thread()
    qtbot.waitUntil(lambda: "Confira no portal" in _texto(tela), timeout=3000)
    qtbot.waitUntil(tela.btn_robo_novo.isEnabled, timeout=2000)
    assert LogFalso.criados == [] and robo["log_auditoria"] is None
    assert "[Auditoria]" not in _texto(tela)


def test_falha_do_robo_vira_log_fecha_o_navegador_e_devolve_os_botoes(tela, robo, qtbot):
    robo["falha"] = RuntimeError("portal fora do ar")
    tela.run_robo_novo_thread()
    qtbot.waitUntil(lambda: "> [Robô novo] Falha: RuntimeError: portal fora do ar" in _texto(tela),
                    timeout=3000)
    qtbot.waitUntil(tela.btn_status.isEnabled, timeout=2000)
    assert tela.btn_robo_novo.isEnabled() and tela.btn_resumo.isEnabled()
    assert robo["engine"].fechado and LogFalso.criados[0].fechado
    assert robo["marcar"] is None


def test_novo_status_desliga_robo_e_resumo_e_esvazia_a_fila(tela, qtbot, monkeypatch):
    """Revisão final: durante a leitura de um `_STATUS_PMIB` novo, a fila
    antiga não pode mais ir para o robô."""
    tela._pos_selecao(_fila(2))
    liberar = threading.Event()
    _leitura(monkeypatch, liberar=liberar)
    tela.btn_status.click()
    try:
        assert not tela.btn_robo_novo.isEnabled() and not tela.btn_resumo.isEnabled()
        assert tela.fila_selecionada == []
    finally:
        liberar.set()
    qtbot.waitUntil(tela.btn_status.isEnabled, timeout=3000)


def test_robo_marca_a_planilha_do_clique(tela, robo, qtbot):
    robo["liberar"].clear()
    tela.btn_robo_novo.click()
    tela.caminho_status = "/d/OUTRA_STATUS_PMIB.xlsx"     # trocada no meio do lote
    robo["liberar"].set()
    qtbot.waitUntil(lambda: robo["marcar"] is not None, timeout=3000)
    assert robo["marcar"] == ("/d/_STATUS_PMIB.xlsx", 2)
    qtbot.waitUntil(tela.btn_robo_novo.isEnabled, timeout=2000)


def test_um_robo_por_vez_selecao_e_leitura_nao_religam_os_botoes(tela, robo, qtbot):
    robo["liberar"].clear()
    tela.btn_robo_novo.click()
    try:
        assert tela._robo_ativo
        tela._pos_selecao(_fila(1))                       # uma seleção que chegou atrasada
        assert not tela.btn_robo_novo.isEnabled() and not tela.btn_resumo.isEnabled()
        tela.fila_completa = []
        tela._pos_leitura_sucesso()                       # uma leitura que terminou agora
        assert not tela.btn_status.isEnabled()
    finally:
        robo["liberar"].set()
    qtbot.waitUntil(tela.btn_robo_novo.isEnabled, timeout=3000)
    assert not tela._robo_ativo
    assert tela.btn_status.isEnabled() and tela.btn_resumo.isEnabled()


def test_robo_sem_fila_nao_faz_nada(tela, robo):
    tela.fila_selecionada = []
    tela.run_robo_novo_thread()
    assert tela.btn_status.isEnabled() and _texto(tela).count("Robô novo") == 0


# --- medidas ----------------------------------------------------------------------

def test_medidas_iguais_as_do_customtkinter(qt_interface, qtbot):
    # Medidas da tela CTk (1280x850, winfo_*), x relativo à área da tela (a barra
    # lateral tem 277 px): título (40, 30) h29; quadro rolável (40, 69) 923x458,
    # conteúdo recuado 6 (largura 900) e barra de 16 em x=946; cartão 1 (46, 85)
    # 900x96: título +15/+10, botão 250x28 em (61, 143), rótulo em x=326;
    # cartão 2 (46, 201) 900x178: botões 430x40 em y=259 (x 61 e 501), interruptor
    # em (61, 317) h24, barra 870x8 em (61, 356); console (40, 537) 923x283.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloCopiaFichas(None, None)
        qtbot.addWidget(t)
        t.resize(1003, 850)
        t.show()
        qtbot.waitExposed(t)
        qtbot.waitUntil(lambda: t.area.height() == 458, timeout=1000)

        def r(w):
            p = w.mapTo(t, w.rect().topLeft())
            return (p.x(), p.y(), w.width(), w.height())

        assert r(t.label_titulo)[:2] == (40, 30) and r(t.label_titulo)[3] == 29
        assert r(t.area) == (40, 69, 923, 458)
        assert r(t.area.verticalScrollBar())[0] == 946
        assert r(t.cartao_config) == (46, 85, 900, 96)
        assert r(t.rotulo_etapa1)[:2] == (61, 95) and r(t.rotulo_etapa1)[3] == 28
        assert r(t.btn_status) == (61, 143, 250, 28)
        assert r(t.lbl_status)[:2] == (326, 143) and r(t.lbl_status)[3] == 28
        assert r(t.cartao_acoes) == (46, 201, 900, 178)
        assert r(t.rotulo_etapa2)[:2] == (61, 211)
        assert r(t.btn_resumo) == (61, 259, 430, 40)
        assert r(t.btn_robo_novo) == (501, 259, 430, 40)
        assert r(t.switch_auditoria)[:2] == (61, 317) and r(t.switch_auditoria)[3] == 24
        assert r(t.progress) == (61, 356, 870, 8)
        # set(0): só o ponto de 8 px da ponta redonda (8/870 da faixa 0-1000).
        assert t.progress.value() == 9
        assert r(t.console) == (40, 537, 923, 283)
    finally:
        qt_interface.setStyleSheet(anterior)


@pytest.mark.parametrize("altura_janela, rolavel, console", [
    (850, 458, 283), (700, 346, 245), (600, 271, 220), (1000, 571, 320), (640, 301, 230),
])
def test_quadro_e_console_dividem_a_altura_como_o_grid_do_tk(qt_interface, qtbot, altura_janela,
                                                            rolavel, console):
    # grid do Tk: linha 1 (weight=3, pede 212) e linha 2 (weight=1, pede 200)
    # repartem a SOBRA 3:1. Medido no CTk em cinco alturas de janela.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloCopiaFichas(None, None)
        qtbot.addWidget(t)
        t.resize(1003, altura_janela)
        t.show()
        qtbot.waitExposed(t)
        qtbot.waitUntil(lambda: (t.area.height(), t.console.height()) == (rolavel, console),
                        timeout=1000)
    finally:
        qt_interface.setStyleSheet(anterior)


def test_medidas_da_pausa_de_login(qt_interface, qtbot):
    # A pausa que esta tela abre (PausaLoginDialog + MSG_LOGIN_LOTE), medida no
    # CTk 450x250: texto (wraplength 400, pady=30, expand) centrado em y=92;
    # CONTINUAR AUTOMAÇÃO 45 de altura em y=185, 20 do fundo, centrado.
    from sigft.app_qt import estilo
    from sigft.app_qt.widgets import dialogs

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        d = dialogs.PausaLoginDialog(None, mensagem=MSG_LOGIN_LOTE, evento_espera=threading.Event())
        qtbot.addWidget(d)
        d.show()
        qtbot.waitExposed(d)
        b = d.botao.geometry()
        assert (b.y(), b.height()) == (185, 45)
        assert abs(b.center().x() - 225) <= 1
        # 195 no CTk: texto + 7 de cada lado (a largura do texto muda com a fonte).
        # O texto medido como o Qt mede o do botão (`size`, que arredonda a
        # largura de cada letra; o `horizontalAdvance` pode dar 1 px a menos).
        from PySide6.QtCore import Qt

        texto = d.botao.fontMetrics().size(Qt.TextFlag.TextShowMnemonic, d.botao.text()).width()
        assert b.width() == max(estilo.LARGURA_BOTAO_CTK, texto + 2 * estilo.FOLGA_TEXTO_BOTAO_CTK)
        r = d.rotulo.geometry()
        assert (r.y(), r.height()) == (30, 125)        # o texto centrado em 92,5, como lá
    finally:
        qt_interface.setStyleSheet(anterior)

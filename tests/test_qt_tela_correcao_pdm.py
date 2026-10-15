"""Tela "Correção de PDM" na interface Qt.

A tela continua BLOQUEADA no menu (`catalogo.TELAS_BLOQUEADAS`): o port existe
para estar pronto quando ela for liberada. O robô e a planilha são dublês -- o
que se prova é a TELA: textos, ações em massa sobre a tabela, a confirmação
antes do portal, a ordem do worker (login, lote, relatório), as threads (barra
e perguntas só na thread da interface) e as medidas contra a interface antiga.
"""
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QMessageBox

from sigft.app.textos_dialogos import MSG_LOGIN_NOVA_FICHA
from sigft.app.theme import COLORS
from sigft.app_qt import catalogo, estilo
from sigft.app_qt.views import correcao_pdm as tela_mod
from sigft.services.correcao_pdm_planilha import FichaParaCorrigir

SIM, NAO = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No


def _fichas():
    return [
        FichaParaCorrigir("100001", "VALVULA A", "PDM.4820.004 - VALVULA (REV 3)", ""),
        FichaParaCorrigir("100002", "VALVULA B", "", ""),
        FichaParaCorrigir("100003", "VALVULA C", "PDM.4820.009 - CAMERA (REV 1)", "X"),
    ]


class CatalogoFalso:
    def __init__(self, n=3):
        self.n = n

    def __len__(self):
        return self.n


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloCorrecaoPDM()
    qtbot.addWidget(t)
    t.caixas = []

    def caixa(tipo):
        def f(parent, titulo, texto, *a, **k):
            t.caixas.append((tipo, titulo, texto))
            return QMessageBox.StandardButton.Ok
        return f

    for nome in ("information", "critical", "warning"):
        monkeypatch.setattr(tela_mod.QMessageBox, nome, caixa(nome))
    # Perguntas: resposta por título, e o botão padrão de cada uma fica registrado.
    t.respostas, t.perguntas = {}, []

    def perguntar(parent, titulo, texto, botoes, padrao):
        t.perguntas.append((titulo, texto, padrao, threading.current_thread() is threading.main_thread()))
        return t.respostas.get(titulo, NAO)

    monkeypatch.setattr(tela_mod.QMessageBox, "question", perguntar)
    return t


def _linhas(t):
    return [[t.tabela.topLevelItem(i).text(c) for c in range(5)] for i in range(t.tabela.topLevelItemCount())]


def _console(t, qtbot, contem):
    qtbot.waitUntil(lambda: contem in t.console.toPlainText(), timeout=3000)


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
def test_monta_com_os_textos(tela):
    assert tela.label_titulo.text() == "Correção de PDM"
    assert tela.label_subtitulo.text() == ("  troca o PDM da ficha e repõe as características "
                                           "que o PDM novo também tem")
    assert tela.btn_status.text() == "Selecionar _STATUS_PMIB"
    assert tela.lbl_status.text() == "Não selecionado"
    assert tela.btn_catalogo.text() == "Planilha de PDMs (opcional)"
    assert tela.lbl_catalogo.text() == "sem catálogo"
    assert tela.rotulo_acoes.text() == "Nas fichas selecionadas:"
    assert [tela.btn_so_revisao.text(), tela.btn_escolher_pdm.text(), tela.btn_limpar.text()] == [
        "Só atualizar a revisão", "Escolher PDM...", "Limpar"]
    assert [tela.tabela.headerItem().text(i) for i in range(5)] == [
        "Ficha", "Descrição", "PDM atual", "PDM novo", "Prévia"]
    assert tela.chk_apagar_vazias.text() == "Apagar as que ficarem em branco"
    assert tela.chk_apagar_vazias.isChecked()
    assert tela.chk_conferir.text() == "Conferir cada ficha antes de salvar"
    assert not tela.chk_conferir.isChecked()
    assert tela.btn_rodar.text() == "INICIAR CORREÇÃO"
    assert tela.btn_parar.text() == "Parar"
    assert tela.fichas == [] and tela.catalogo is None and tela.automacao is None


def test_continua_bloqueada_no_menu():
    assert "CorrecaoPDM" in catalogo.TELAS_BLOQUEADAS


def test_nao_importa_regra_de_planilha_nem_motor():
    import pathlib

    fonte = pathlib.Path(tela_mod.__file__).read_text(encoding="utf-8")
    for proibido in ("import pandas", "import openpyxl", "playwright", "selenium"):
        assert proibido not in fonte.lower()
    # (A biblioteca da interface antiga: `tests/test_sem_interface_antiga.py`.)


# ---------------------------------------------------------------------------
# Arquivos
# ---------------------------------------------------------------------------
def test_selecionar_status(tela, monkeypatch):
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda *a, **k: pedidos.append((a, k)) or "/x/_STATUS_PMIB.xlsx")
    monkeypatch.setattr(tela_mod.planilha_svc, "ler_fichas_do_arquivo", lambda c: _fichas())
    tela._sel_status()
    assert pedidos == [(("correcao_pdm.status_pmib", "excel"),
                        {"titulo": "Selecione o _STATUS_PMIB", "filetypes": [("Excel", "*.xlsx *.xlsm")]})]
    assert tela.lbl_status.text() == "3 ficha(s)"
    assert COLORS["accent"].lower() in tela.lbl_status.styleSheet().lower()
    assert [linha[0] for linha in _linhas(tela)] == ["100001", "100002", "100003"]


def test_selecionar_status_cancelado_nao_mexe(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    lidas = []
    monkeypatch.setattr(tela_mod.planilha_svc, "ler_fichas_do_arquivo", lambda c: lidas.append(c))
    tela._sel_status()
    assert lidas == [] and tela.lbl_status.text() == "Não selecionado"


def test_selecionar_status_que_falha(tela, monkeypatch):
    tela.fichas = _fichas()
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/x.xlsx")

    def falha(caminho):
        raise ValueError("aba sumiu")

    monkeypatch.setattr(tela_mod.planilha_svc, "ler_fichas_do_arquivo", falha)
    tela._sel_status()
    assert tela.caixas == [("critical", "Erro", "Não consegui ler a planilha:\naba sumiu")]
    assert len(tela.fichas) == 3 and tela.lbl_status.text() == "Não selecionado"


def test_status_sem_fichas_avisa_no_log(tela, qtbot, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/x.xlsx")
    monkeypatch.setattr(tela_mod.planilha_svc, "ler_fichas_do_arquivo", lambda c: [])
    tela._sel_status()
    assert tela.lbl_status.text() == "0 ficha(s)"
    _console(tela, qtbot, "> Nenhuma ficha encontrada. Confira se a aba é a 'Lista de Materiais' "
                          "e se há a coluna CÓDIGO PMIB.")


def test_selecionar_catalogo(tela, monkeypatch):
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda *a, **k: pedidos.append((a, k)) or "/x/SAM_GM.xlsx")
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda c: CatalogoFalso(1234))
    tela.fichas = _fichas()
    previas = []
    monkeypatch.setattr(tela_mod.planilha_svc, "previa",
                        lambda cat, atual, novo: previas.append(cat) or "ok")
    tela._sel_catalogo()
    assert pedidos == [(("correcao_pdm.sam_gm", "excel"),
                        {"titulo": "Selecione a planilha de PDMs", "filetypes": [("Excel", "*.xlsx *.xlsm")]})]
    assert tela.lbl_catalogo.text() == "1234 PDMs"
    assert COLORS["accent"].lower() in tela.lbl_catalogo.styleSheet().lower()
    assert previas and all(isinstance(c, CatalogoFalso) for c in previas)


def test_selecionar_catalogo_que_falha(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/x.xlsx")

    def falha(caminho):
        raise OSError("travado")

    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", falha)
    tela._sel_catalogo()
    assert tela.caixas == [("critical", "Erro", "Não consegui ler o catálogo:\ntravado")]
    assert tela.catalogo is None and tela.lbl_catalogo.text() == "sem catálogo"


# ---------------------------------------------------------------------------
# Tabela e ações em massa
# ---------------------------------------------------------------------------
def test_tabela_mostra_a_previa_do_servico(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.planilha_svc, "previa", lambda cat, atual, novo: f"prev:{novo}")
    tela.fichas = _fichas()
    tela._redesenhar()
    assert _linhas(tela)[2] == ["100003", "VALVULA C", "PDM.4820.009 - CAMERA (REV 1)", "X", "prev:X"]
    # Chave de cada linha = a posição (o iid do Treeview).
    assert tela.tabela.topLevelItem(1).data(0, tela_mod.Qt.ItemDataRole.UserRole) == "1"


def test_sem_selecao_vale_para_todas(tela):
    tela.fichas = _fichas()
    tela._redesenhar()
    assert tela._selecionadas() == tela.fichas
    tela.tabela.topLevelItem(2).setSelected(True)
    tela.tabela.topLevelItem(0).setSelected(True)
    assert [f.pmib for f in tela._selecionadas()] == ["100001", "100003"]


def test_so_atualizar_a_revisao(tela, qtbot):
    tela.fichas = _fichas()
    tela._redesenhar()
    tela._acao_so_revisao()
    assert tela.fichas[0].pdm_novo == tela_mod.planilha_svc.so_a_revisao("PDM.4820.004 - VALVULA (REV 3)")
    assert tela.fichas[0].pdm_novo
    assert tela.fichas[1].pdm_novo == ""
    assert _linhas(tela)[0][3] == tela.fichas[0].pdm_novo
    _console(tela, qtbot, "> Só atualizar a revisão: 2 ficha(s).\n>    1 ficha(s) sem PDM na planilha "
                          "ficaram de fora: não há código para copiar.")


def test_limpar_so_as_selecionadas(tela):
    tela.fichas = _fichas()
    for f in tela.fichas:
        f.pdm_novo = "NOVO"
    tela._redesenhar()
    tela.tabela.topLevelItem(1).setSelected(True)
    tela._acao_limpar()
    assert [f.pdm_novo for f in tela.fichas] == ["NOVO", "", "NOVO"]
    assert _linhas(tela)[1][3] == ""


def test_escolher_pdm_sem_catalogo_avisa(tela, monkeypatch):
    abertas = []
    monkeypatch.setattr(tela_mod, "JanelaEscolherPDM", lambda *a: abertas.append(a))
    tela.fichas = _fichas()
    tela._acao_escolher_pdm()
    assert tela.caixas == [("information", "Catálogo",
                            "Selecione antes a planilha de PDMs: é dela que sai a busca.")]
    assert abertas == []


class JanelaFalsa:
    def __init__(self, escolha):
        self.escolha_final = escolha
        self.escolha = None
        self.visivel = True
        self.trazida = 0

    def __call__(self, parent, catalogo):
        self.args = (parent, catalogo)
        return self

    def esperar(self):
        self.escolha = self.escolha_final
        self.visivel = False
        return self.escolha

    def isVisible(self):  # noqa: N802 -- nome do Qt
        return self.visivel

    def raise_(self):
        self.trazida += 1

    def activateWindow(self):  # noqa: N802 -- nome do Qt
        pass


def test_escolher_pdm_aplica_nas_selecionadas(tela, qtbot, monkeypatch):
    janela = JanelaFalsa(SimpleNamespace(completo="4820.010 - VALVULA GAVETA (REV 2)"))
    monkeypatch.setattr(tela_mod, "JanelaEscolherPDM", janela)
    tela.catalogo = CatalogoFalso()
    tela.fichas = _fichas()
    tela._redesenhar()
    tela.tabela.topLevelItem(0).setSelected(True)
    tela.tabela.topLevelItem(1).setSelected(True)
    tela._acao_escolher_pdm()
    assert janela.args == (tela, tela.catalogo)
    assert [f.pdm_novo for f in tela.fichas] == ["4820.010 - VALVULA GAVETA (REV 2)"] * 2 + ["X"]
    assert _linhas(tela)[1][3] == "4820.010 - VALVULA GAVETA (REV 2)"
    _console(tela, qtbot, "> 4820.010 - VALVULA GAVETA (REV 2) aplicado a 2 ficha(s).")


def test_escolher_pdm_cancelado_nao_muda_nada(tela, monkeypatch):
    monkeypatch.setattr(tela_mod, "JanelaEscolherPDM", JanelaFalsa(None))
    tela.catalogo = CatalogoFalso()
    tela.fichas = _fichas()
    tela._acao_escolher_pdm()
    assert [f.pdm_novo for f in tela.fichas] == ["", "", "X"]


def test_escolher_pdm_sem_fichas_nao_abre(tela, monkeypatch):
    abertas = []
    monkeypatch.setattr(tela_mod, "JanelaEscolherPDM", lambda *a: abertas.append(a))
    tela.catalogo = CatalogoFalso()
    tela._acao_escolher_pdm()
    assert abertas == []


def test_segundo_clique_nao_abre_outra_janela_de_pdm(tela, monkeypatch):
    aberta = JanelaFalsa(None)
    tela._janela_pdm = aberta
    criadas = []
    monkeypatch.setattr(tela_mod, "JanelaEscolherPDM", lambda *a: criadas.append(a))
    tela.catalogo = CatalogoFalso()
    tela.fichas = _fichas()
    tela._acao_escolher_pdm()
    assert criadas == [] and aberta.trazida == 1


def test_escolher_pdm_com_a_janela_de_verdade(tela, qtbot):
    """A `JanelaEscolherPDM` real (E3.2) abre modal e o `esperar()` devolve a escolha."""
    from PySide6.QtCore import QTimer

    pdm = SimpleNamespace(completo="4820.004 - VALVULA ESFERA (REV 4)", classe="4820",
                          caracteristicas=["DIAMETRO"])
    tela.catalogo = type("Cat", (), {"buscar": lambda self, texto, limite=40: [pdm],
                                     "__len__": lambda self: 1})()
    tela.fichas = _fichas()

    def confirmar():
        janela = tela._janela_pdm
        assert janela is not None and janela.isVisible()
        janela.confirmar()

    QTimer.singleShot(50, confirmar)
    tela._acao_escolher_pdm()
    assert [f.pdm_novo for f in tela.fichas] == ["4820.004 - VALVULA ESFERA (REV 4)"] * 3


# ---------------------------------------------------------------------------
# A rodada
# ---------------------------------------------------------------------------
class AutomacaoFalsa:
    criadas = []

    def __init__(self, falha_ao_iniciar=None):
        self.portal = SimpleNamespace(nome="portal")
        self.passos = []
        self.falha_ao_iniciar = falha_ao_iniciar
        AutomacaoFalsa.criadas.append(self)

    def iniciar(self):
        self.passos.append("iniciar")
        if self.falha_ao_iniciar:
            raise self.falha_ao_iniciar

    def abrir_portal(self, url):
        self.passos.append(("abrir", url))

    def solicitar_parada(self):
        self.passos.append("parar")

    def fechar(self):
        self.passos.append("fechar")


def _robo(tela, monkeypatch, *, falha=None, pausar_no_lote=None):
    AutomacaoFalsa.criadas = []
    monkeypatch.setattr(tela_mod.correcao_svc, "AutomacaoCorrecaoPDM", lambda: AutomacaoFalsa(falha))
    chamadas = []

    def corrigir_lote(portal, lote, callback_log=None, callback_pause=None, callback_progress=None,
                      apagar_vazias=True):
        chamadas.append(dict(portal=portal, lote=lote, callback_pause=callback_pause,
                             apagar_vazias=apagar_vazias))
        callback_log("corrigindo...")
        callback_progress(1, 2, item="100001")
        if callback_pause:
            callback_pause("100001")
        if pausar_no_lote:
            pausar_no_lote.wait(3)
        callback_progress(2, 2, item="100003")
        return ["r1", "r2"]

    monkeypatch.setattr(tela_mod.correcao_svc, "corrigir_lote", corrigir_lote)
    monkeypatch.setattr(tela_mod.correcao_svc, "relatorio_do_lote",
                        lambda res: [f"Correcao de PDM: {len(res)} ficha(s)", "fim"])
    tela.pausas = []
    monkeypatch.setattr(tela, "pausar_e_esperar",
                        lambda msg, *a: tela.pausas.append(
                            (msg, threading.current_thread() is threading.main_thread())))
    tela.relatorios = []
    monkeypatch.setattr(tela, "_oferecer_relatorio", lambda res: tela.relatorios.append(
        (res, threading.current_thread() is threading.main_thread())))
    tela.progressos = []
    original = tela._definir_progresso

    def definir(fracao):
        tela.progressos.append((fracao, threading.current_thread() is threading.main_thread()))
        original(fracao)

    monkeypatch.setattr(tela, "_definir_progresso", definir)
    return chamadas


def test_rodar_sem_pdm_novo_nao_faz_nada(tela, monkeypatch):
    chamadas = _robo(tela, monkeypatch)
    tela.fichas = [FichaParaCorrigir("1", pdm_novo="  ")]
    tela._rodar()
    assert tela.caixas == [("information", "Nada a fazer",
                            "Nenhuma ficha tem PDM novo. Use 'Só atualizar a revisão' ou "
                            "'Escolher PDM...' antes.")]
    assert tela.perguntas == [] and chamadas == [] and AutomacaoFalsa.criadas == []


def test_rodar_pede_confirmacao_e_nao_aceita_por_padrao(tela, monkeypatch):
    chamadas = _robo(tela, monkeypatch)
    tela.fichas = _fichas()
    tela._rodar()
    titulo, texto, padrao, na_interface = tela.perguntas[0]
    assert titulo == "Confirmar" and na_interface
    assert texto == ("1 ficha(s) vão ter o PDM trocado no portal.\n\n"
                     "O portal apaga as características técnicas na troca. O robô "
                     "fotografa antes e repõe o que couber, e o que não voltar sai "
                     "no relatório.\n\nSeguir?")
    # Operação destrutiva: Enter não confirma (o botão padrão é o "Não").
    assert padrao == NAO
    assert chamadas == [] and AutomacaoFalsa.criadas == [] and tela.btn_rodar.isEnabled()


def test_rodada_completa(tela, qtbot, monkeypatch):
    solta = threading.Event()
    chamadas = _robo(tela, monkeypatch, pausar_no_lote=solta)
    tela.fichas = _fichas()
    tela.respostas["Confirmar"] = SIM
    tela._rodar()
    # Desligado no clique; a thread é comum (o "X" pergunta antes de fechar).
    assert not tela.btn_rodar.isEnabled()
    qtbot.waitUntil(lambda: bool(chamadas), timeout=3000)
    vivas = [t for t in threading.enumerate() if t.name.startswith("tarefa:ModuloCorrecaoPDM")]
    assert vivas and not vivas[0].daemon
    solta.set()
    qtbot.waitUntil(lambda: tela.btn_rodar.isEnabled(), timeout=3000)
    robo = AutomacaoFalsa.criadas[0]
    assert robo.passos == ["iniciar", ("abrir", tela_mod.URL_LISTA_DE_FICHAS), "fechar"]
    assert tela.pausas == [(MSG_LOGIN_NOVA_FICHA, False)]
    assert chamadas[0]["portal"] is robo.portal
    assert chamadas[0]["lote"] == [("100003", "X")]
    assert chamadas[0]["callback_pause"] is None and chamadas[0]["apagar_vazias"] is True
    assert tela.progressos == [(0.5, True), (1.0, True)]
    assert tela.relatorios == [(["r1", "r2"], True)]
    _console(tela, qtbot, "> corrigindo...\n> Correcao de PDM: 2 ficha(s)\n> fim")


def test_rodada_com_conferencia_e_sem_apagar(tela, qtbot, monkeypatch):
    chamadas = _robo(tela, monkeypatch)
    tela.fichas = _fichas()
    tela.chk_conferir.setChecked(True)
    tela.chk_apagar_vazias.setChecked(False)
    # Os interruptores são lidos DEPOIS do login (como lá), mas na thread da interface.
    lidos = []
    original = tela.chk_conferir.isChecked
    monkeypatch.setattr(tela.chk_conferir, "isChecked", lambda: lidos.append(
        threading.current_thread() is threading.main_thread()) or original())
    tela.respostas["Confirmar"] = SIM
    tela._rodar()
    qtbot.waitUntil(lambda: tela.btn_rodar.isEnabled() and bool(chamadas), timeout=3000)
    assert chamadas[0]["apagar_vazias"] is False
    assert chamadas[0]["callback_pause"] is not None
    assert lidos and all(lidos)
    assert tela.pausas == [(MSG_LOGIN_NOVA_FICHA, False),
                           ("Confira a ficha 100001 no portal antes de salvar.", False)]


def test_erro_no_robo_vira_log_e_fecha_o_navegador(tela, qtbot, monkeypatch):
    _robo(tela, monkeypatch, falha=RuntimeError("chrome sumiu"))
    tela.fichas = _fichas()
    tela.respostas["Confirmar"] = SIM
    tela._rodar()
    qtbot.waitUntil(lambda: tela.btn_rodar.isEnabled() and bool(AutomacaoFalsa.criadas), timeout=3000)
    _console(tela, qtbot, "> [Erro] RuntimeError: chrome sumiu")
    assert AutomacaoFalsa.criadas[0].passos == ["iniciar", "fechar"]
    assert tela.relatorios == []


def test_parar(tela, qtbot):
    tela._parar()  # sem robô: nada
    assert "Parada" not in tela.console.toPlainText()
    tela.automacao = AutomacaoFalsa()
    tela._parar()
    assert tela.automacao.passos == ["parar"]
    _console(tela, qtbot, "> Parada pedida. Termino a ficha atual e paro.")


def test_progresso_zero_total(tela, qtbot, monkeypatch):
    vistos = []
    monkeypatch.setattr(tela, "_definir_progresso", lambda f: vistos.append(f))
    tela._progresso(0, 0)
    qtbot.waitUntil(lambda: vistos == [0], timeout=2000)


# ---------------------------------------------------------------------------
# O relatório em arquivo
# ---------------------------------------------------------------------------
def test_relatorio_recusado(tela, monkeypatch):
    salvos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file", lambda *a, **k: salvos.append(1))
    tela._oferecer_relatorio([])
    titulo, texto, padrao, _ = tela.perguntas[0]
    assert (titulo, texto) == ("Relatório", "Salvar o relatório num arquivo?")
    # Enter aqui guarda o relatório (o "Sim" do askyesno de lá): recusar perde a lista.
    assert padrao == SIM
    assert salvos == []


def test_relatorio_salvo(tela, qtbot, monkeypatch, tmp_path):
    destino = tmp_path / "rel.txt"
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file",
                        lambda *a, **k: pedidos.append((a, k)) or str(destino))
    monkeypatch.setattr(tela_mod.correcao_svc, "relatorio_do_lote", lambda r: ["linha 1", "linha 2"])
    tela.respostas["Relatório"] = SIM
    tela._oferecer_relatorio(["r"])
    assert pedidos == [(("correcao_pdm.relatorio", "texto"),
                        {"titulo": "Salvar relatorio", "defaultextension": ".txt",
                         "filetypes": [("Texto", "*.txt")]})]
    assert destino.read_text(encoding="utf-8") == "linha 1\nlinha 2"
    _console(tela, qtbot, f"> Relatório salvo em {destino}")


def test_relatorio_cancelado_no_dialogo(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file", lambda *a, **k: "")
    tela.respostas["Relatório"] = SIM
    tela._oferecer_relatorio(["r"])
    assert tela.caixas == []


def test_relatorio_que_nao_grava(tela, monkeypatch, tmp_path):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file",
                        lambda *a, **k: str(tmp_path / "nao" / "existe" / "rel.txt"))
    monkeypatch.setattr(tela_mod.correcao_svc, "relatorio_do_lote", lambda r: ["x"])
    tela.respostas["Relatório"] = SIM
    tela._oferecer_relatorio(["r"])
    assert tela.caixas[0][:2] == ("critical", "Erro")
    assert tela.caixas[0][2].startswith("Não consegui salvar:\n")


# ---------------------------------------------------------------------------
# Geometria contra a interface antiga
# ---------------------------------------------------------------------------
@pytest.fixture
def com_folha(qt_interface):
    """A folha e a fonte do app (Roboto com o hinting do `carregar_fontes`), como
    no `main`; as duas voltam ao que eram no fim."""
    anterior, fonte = qt_interface.styleSheet(), qt_interface.font()
    estilo.carregar_fontes()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    yield
    qt_interface.setStyleSheet(anterior)
    qt_interface.setFont(fonte)


def test_medidas_iguais_as_do_interface_antiga(com_folha, qtbot):
    # Medidas da tela antiga (interface antiga, janela 1280x850, sondadas com
    # winfo_*), já na origem da tela Qt (x=277 da janela, com o padx/pady=20 do
    # `show_frame`). Ver capturas/e4.8. Textos: ±6 px (fonte do Tk x Qt).
    t = tela_mod.ModuloCorrecaoPDM()
    qtbot.addWidget(t)
    t.resize(1003, 850)
    t.show()
    qtbot.waitExposed(t)
    # A faixa do console é ajustada no resizeEvent; o layout reflui logo depois.
    qtbot.waitUntil(lambda: t.content.height() == 521, timeout=2000)

    def geo(w):
        p = w.mapTo(t, w.rect().topLeft())
        return p.x(), p.y(), w.width(), w.height()

    def perto(a, b, tol=6):
        return all(abs(x - y) <= tol for x, y in zip(a, b))

    assert geo(t.label_titulo)[:2] == (40, 30)
    assert perto(geo(t.label_titulo), (40, 30, 205, 29))
    assert perto(geo(t.label_subtitulo), (245, 30, 449, 28))
    assert geo(t.content) == (40, 79, 923, 521)
    assert geo(t.btn_status) == (55, 91, 200, 28)
    assert geo(t.lbl_status)[:2] == (265, 91) and geo(t.lbl_status)[3] == 28
    x, y, _w, h = geo(t.btn_catalogo)
    assert (y, h, geo(t.btn_catalogo)[2]) == (91, 28, 210) and abs(x - 390) <= 4
    assert perto(geo(t.rotulo_acoes), (40, 141, 148, 28))
    assert perto(geo(t.btn_so_revisao), (202, 141, 170, 28))
    assert geo(t.btn_so_revisao)[2:] == (170, 28)
    assert geo(t.btn_escolher_pdm)[0] - sum(geo(t.btn_so_revisao)[::2]) == 8
    assert geo(t.btn_escolher_pdm)[1:] == (141, 140, 28)
    assert geo(t.btn_limpar)[0] - sum(geo(t.btn_escolher_pdm)[::2]) == 8
    assert geo(t.btn_limpar)[1:] == (141, 90, 28)
    # Tabela 908 + a barra de 15; altura 371.
    assert geo(t.tabela) == (40, 175, 923, 371)
    assert perto(geo(t.chk_apagar_vazias), (40, 558, 237, 24))
    assert geo(t.chk_conferir)[0] - sum(geo(t.chk_apagar_vazias)[::2]) == 20
    assert geo(t.chk_conferir)[1] == 558
    assert geo(t.btn_rodar) == (773, 556, 190, 28)
    assert geo(t.btn_parar) == (675, 556, 90, 28)
    assert geo(t.progress) == (40, 592, 923, 8)
    # O console fica centrado na linha 2 da grade (sticky="ew", peso 1 contra 3).
    assert geo(t.console) == (40, 645, 923, 150)


def test_console_divide_a_sobra_como_a_grade_do_tk(com_folha, qtbot):
    # Tk: a sobra da altura vai 3/4 para o conteúdo e 1/4 para a linha do console.
    t = tela_mod.ModuloCorrecaoPDM()
    qtbot.addWidget(t)
    t.resize(1003, 950)
    t.show()
    qtbot.waitExposed(t)
    qtbot.waitUntil(lambda: t.content.height() == 521 + 75, timeout=2000)
    # Linha do console +25: ele desce 75 (o conteúdo) + 12 (metade dos 25).
    assert abs(t.console.mapTo(t, t.console.rect().topLeft()).y() - (645 + 75 + 12)) <= 1


def test_barra_de_progresso_acompanha_a_largura(com_folha, qtbot):
    t = tela_mod.ModuloCorrecaoPDM()
    qtbot.addWidget(t)
    t.resize(1003, 850)
    t.show()
    qtbot.waitExposed(t)
    t._definir_progresso(0.4)
    # Pontas redondas por dentro: 8 + 0,4 * (923 - 8) = 374 px de 923.
    qtbot.waitUntil(lambda: abs(t.progress.value() - round(1000 * 374 / 923)) <= 1, timeout=2000)
    t.resize(803, 850)
    qtbot.waitUntil(lambda: abs(t.progress.value() - round(1000 * (8 + 0.4 * 715) / 723)) <= 1, timeout=2000)


def test_perguntas_usam_o_sim_nao_compartilhado():
    # O `_perguntar` local (cópia de `DialogosDeEspera.perguntar_sim_nao`) saiu:
    # o compartilhado ganhou o botão padrão (`padrao_sim`).
    assert not hasattr(tela_mod.ModuloCorrecaoPDM, "_perguntar")

"""Tela "Gestão de Sobressalentes" (PMIB Manager) na interface Qt.

Os backends são dublês: o que se prova é a TELA -- textos, validações, a ordem
das mensagens, a barra de progresso (só pela thread da interface), o popup das
listas novas, o painel e as autorizações de Itaipu.
"""
import sys
import threading
from types import SimpleNamespace

import pytest

from sigft.app import backends, theme
from sigft.app_qt.views import pmib_manager as tela_mod
from sigft.core.prefs import CHAVE_MAPEAMENTO


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------
class DataFrameFalso:
    """O pedaço do DataFrame que a tela usa: `iterrows` e `loc[indices]`."""

    def __init__(self, linhas):
        self.linhas = dict(linhas)  # {idx: {"No. do Documento": ..., "Título": ...}}
        self.loc = self

    def iterrows(self):
        return iter(self.linhas.items())

    def __getitem__(self, indices):
        return ("loc", list(indices))


class GerenteFalso:
    """`PMIBManager` de mentira: devolve as mensagens e, se pedido, chama o
    `callback_confirm` no meio (o popup das listas novas)."""

    def __init__(self, mensagens, *, df_novos=None, falha=None):
        self.mensagens, self.df_novos, self.falha = mensagens, df_novos, falha
        self.chamadas, self.confirmado = [], None

    def executar_fluxo(self, api, raiz, mestra, callback_confirm=None, callback_travados=None):
        self.chamadas.append((api, raiz, mestra, callback_travados))
        if self.falha:
            raise self.falha
        for m in self.mensagens:
            if m == "CONFIRMAR":
                self.confirmado = callback_confirm(self.df_novos)
                continue
            yield m


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    opcoes = {}
    monkeypatch.setattr(tela_mod.prefs, "get_opcao", lambda chave, padrao=None: opcoes.get(chave, padrao))
    monkeypatch.setattr(tela_mod.prefs, "set_opcao", lambda chave, valor: opcoes.__setitem__(chave, valor))
    lembrados = []
    monkeypatch.setattr(tela_mod.prefs, "remember_file", lambda chave, f: lembrados.append((chave, f)))
    t = tela_mod.ModuloPMIBManager()
    qtbot.addWidget(t)
    t.opcoes, t.lembrados, t.avisos = opcoes, lembrados, []
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info": t.avisos.append((tipo, ti, m)))
    # A barra só pode ser mexida na thread da interface: registra de qual veio.
    t.progressos = []
    original = t._definir_progresso

    def definir(fracao):
        t.progressos.append((threading.current_thread() is threading.main_thread(), fracao))
        original(fracao)

    monkeypatch.setattr(t, "_definir_progresso", definir)
    return t


@pytest.fixture
def avisos_qt(monkeypatch):
    """Os QMessageBox.warning do clique (thread da interface)."""
    lista = []
    monkeypatch.setattr(tela_mod.QMessageBox, "warning", staticmethod(lambda *a: lista.append(a[1:])))
    return lista


def _preencher(tela, api="/d/api.xlsx", raiz="/d/raiz", mestra="/d/Mapeamento.xlsx", aut=None):
    tela.path_api, tela.path_master = api, mestra
    tela.entry_root.setText(raiz)
    if aut is not None:
        tela.path_autorizados = aut


def _com_gerente(monkeypatch, gerente):
    monkeypatch.setattr(backends, "pmib_manager_backend", SimpleNamespace(PMIBManager=lambda: gerente))
    return gerente


def _rodar_gestao(tela, qtbot, ultima):
    tela.btn_run.click()
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=3000)
    qtbot.waitUntil(lambda: ultima in tela.console.toPlainText(), timeout=2000)
    return tela.console.toPlainText()


# ---------------------------------------------------------------------------
# Montagem e seletores
# ---------------------------------------------------------------------------
def test_monta_com_os_textos(tela):
    assert tela.label_titulo.text() == "Gestão de Sobressalentes"
    r = tela._rotulos
    assert r["config"].text() == "Configuração de Gestão de Fichas PMIB"
    assert r["autorizacoes"].text() == "Autorizações de entrega de Itaipu"
    assert r["descricao_aut"].text() == (
        "Grava AUTORIZADO nos _STATUS_PMIB da Pasta Raiz (passo 2) para cada PMIB do "
        "export de Itaipu (sobressalentes_autorizados_AAAAMMDDhhmm.xlsx).")
    assert r["raiz"].text() == "2. Pasta Raiz (Arquivos _STATUS_PMIB):"
    assert tela.btn_api.text() == "1. Selecionar Histórico Aconex DocManager (.xlsx)"
    assert tela.btn_master.text() == "3. Selecionar Mapeamento Sobressalentes (.xlsx)"
    assert tela.btn_autorizados.text() == "4. Selecionar export de autorizados (.xlsx)"
    assert tela.btn_buscar.text() == "Buscar"
    assert tela.btn_run.text() == "INICIAR PROCESSO DE GESTÃO"
    assert tela.btn_painel.text() == "Gerar painel"
    assert tela.btn_aplicar.text() == "APLICAR AUTORIZAÇÕES"
    assert tela.caixa_gerar_painel.text() == "Gerar painel ao terminar"
    for rotulo in (tela.lbl_api_status, tela.lbl_master_status, tela.lbl_autorizados):
        assert rotulo.text() == "Nenhum arquivo selecionado"
    assert tela.path_api == tela.path_master == tela.path_autorizados == ""
    assert tela.entry_root.text() == ""


def test_caixa_do_painel_vem_da_preferencia_e_e_lembrada(qt_interface, qtbot, monkeypatch):
    opcoes = {tela_mod.OPCAO_GERAR_PAINEL: False}
    monkeypatch.setattr(tela_mod.prefs, "get_opcao", lambda chave, padrao=None: opcoes.get(chave, padrao))
    monkeypatch.setattr(tela_mod.prefs, "set_opcao", lambda chave, valor: opcoes.__setitem__(chave, valor))
    t = tela_mod.ModuloPMIBManager()
    qtbot.addWidget(t)
    assert not t.caixa_gerar_painel.isChecked()
    t.caixa_gerar_painel.click()
    assert t.caixa_gerar_painel.isChecked() and opcoes[tela_mod.OPCAO_GERAR_PAINEL] is True


def test_preferencia_quebrada_nao_impede_a_tela_de_abrir(qt_interface, qtbot, monkeypatch):
    def quebra(*a, **k):
        raise OSError("config ilegível")

    monkeypatch.setattr(tela_mod.prefs, "get_opcao", quebra)
    monkeypatch.setattr(tela_mod.prefs, "set_opcao", quebra)
    t = tela_mod.ModuloPMIBManager()
    qtbot.addWidget(t)
    assert t.caixa_gerar_painel.isChecked()  # padrão: gera
    t.caixa_gerar_painel.click()  # lembrar falha em silêncio
    assert not t.caixa_gerar_painel.isChecked()


def test_seletores_de_arquivo(tela, monkeypatch):
    chamadas = []
    respostas = iter(["/d/Hist Aconex.xlsx", "/d/Mapeamento.xlsx", "/d/sobressalentes_autorizados_1.xlsx"])

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k["titulo"], k["filetypes"]))
        return next(respostas)

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", falso)
    tela.btn_api.click()
    tela.btn_master.click()
    tela.btn_autorizados.click()
    assert chamadas == [
        ("pmib_manager.api", "excel", "Selecione a Base de Dados API", [("Excel", "*.xlsx *.xls")]),
        ("pmib_manager.master", "excel", "Selecione a Planilha Mestra", [("Excel", "*.xlsx *.xls")]),
        ("pmib_manager.autorizados", "excel", "Selecione o export de autorizados de Itaipu",
         [("Excel", "*.xlsx")]),
    ]
    assert tela.path_api == "/d/Hist Aconex.xlsx"
    assert tela.path_master == "/d/Mapeamento.xlsx"
    assert tela.path_autorizados == "/d/sobressalentes_autorizados_1.xlsx"
    assert tela.lbl_api_status.text() == "Hist Aconex.xlsx"
    assert tela.lbl_master_status.text() == "Mapeamento.xlsx"
    assert tela.lbl_autorizados.text() == "sobressalentes_autorizados_1.xlsx"
    for rotulo in (tela.lbl_api_status, tela.lbl_master_status, tela.lbl_autorizados):
        assert theme.COLORS["accent"] in rotulo.styleSheet()
    for botao in (tela.btn_api, tela.btn_master, tela.btn_autorizados):
        assert theme.COLORS["primary"] in botao.styleSheet()
    # O mapeamento fica lembrado para o mural da Home.
    assert tela.lembrados == [(CHAVE_MAPEAMENTO, "/d/Mapeamento.xlsx")]


def test_cancelar_o_seletor_nao_mexe_em_nada(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    tela.btn_api.click()
    tela.btn_master.click()
    tela.btn_autorizados.click()
    assert tela.path_api == tela.path_master == tela.path_autorizados == ""
    assert tela.lbl_api_status.text() == "Nenhum arquivo selecionado"
    assert tela.lembrados == []


def test_lembrar_o_mapeamento_falhar_nao_atrapalha(tela, monkeypatch):
    def quebra(*a):
        raise OSError("sem disco")

    monkeypatch.setattr(tela_mod.prefs, "remember_file", quebra)
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/M.xlsx")
    tela.btn_master.click()
    assert tela.path_master == "/d/M.xlsx"


def test_buscar_a_pasta_raiz(tela, monkeypatch):
    chamadas = []

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k["titulo"]))
        return "/d/Fichas PMIB"

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_directory", falso)
    tela.btn_buscar.click()
    assert chamadas == [("pmib_manager.pasta_raiz", "pasta", "Selecione a Pasta Raiz")]
    assert tela.entry_root.text() == "/d/Fichas PMIB"
    # Cancelar (o wrapper devolve "") não apaga o que já estava no campo.
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_directory", lambda *a, **k: "")
    tela.btn_buscar.click()
    assert tela.entry_root.text() == "/d/Fichas PMIB"


# ---------------------------------------------------------------------------
# Gestão PMIB
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("faltando, mensagem", [
    ("api", "Por favor, selecione a Base do Aconex (Passo 1)."),
    ("raiz", "Por favor, selecione a Pasta Raiz (Passo 2)."),
    ("mestra", "Por favor, selecione a Planilha de mapeamento (Passo 3)."),
])
def test_gestao_valida_os_passos_na_ordem(tela, monkeypatch, avisos_qt, faltando, mensagem):
    gerente = _com_gerente(monkeypatch, GerenteFalso([]))
    _preencher(tela, **{faltando: ""})
    tela.btn_run.click()
    assert avisos_qt == [("Aviso", mensagem)]
    assert gerente.chamadas == [] and tela.btn_run.isEnabled()


def test_gestao_sem_backend_avisa_e_nao_trava(tela, monkeypatch):
    monkeypatch.setattr(backends, "pmib_manager_backend", None)
    monkeypatch.setattr(backends, "falhas", {"pmib_manager_backend": ImportError("sem openpyxl")})
    avisos = []
    monkeypatch.setattr("sigft.app_qt.widgets.module_frame.QMessageBox.warning",
                        staticmethod(lambda *a: avisos.append(a[1])))
    _preencher(tela)
    tela.btn_run.click()
    assert avisos == ["Módulo indisponível"]
    assert tela.btn_run.isEnabled() and tela.btn_aplicar.isEnabled() and tela.btn_painel.isEnabled()


def test_gestao_completa(tela, qtbot, monkeypatch):
    tela.caixa_gerar_painel.setChecked(False)
    gerente = _com_gerente(monkeypatch, GerenteFalso([
        ("Carregando Base de Dados do DocManager...", 0.05), ("Etapa sem progresso", None),
        " -> 3 fichas atualizadas", ("--- PROCESSO CONCLUÍDO ---", 1.0)]))
    travadas = []

    def no_meio(*a, **k):
        travadas.append((tela.btn_run.isEnabled(), tela.btn_aplicar.isEnabled(), tela.btn_painel.isEnabled()))
        return gerente.__class__.executar_fluxo(gerente, *a, **k)

    gerente.executar_fluxo = no_meio
    _preencher(tela)
    texto = _rodar_gestao(tela, qtbot, "--- PROCESSO CONCLUÍDO ---")
    assert travadas == [(False, False, False)]
    assert gerente.chamadas == [("/d/api.xlsx", "/d/raiz", "/d/Mapeamento.xlsx", tela.perguntar_arquivos_travados)]
    ordem = ["> Iniciando fluxo de gestão de sobressalentes...", "> Carregando Base de Dados do DocManager...",
             "> Etapa sem progresso", ">  -> 3 fichas atualizadas", "> --- PROCESSO CONCLUÍDO ---"]
    posicoes = [texto.index(linha) for linha in ordem]
    assert posicoes == sorted(posicoes)
    qtbot.waitUntil(lambda: len(tela.progressos) == 3, timeout=2000)
    # Só pela thread da interface; o `None` não mexe na barra; o fim enche.
    assert tela.progressos == [(True, 0.05), (True, 1.0), (True, 1.0)]
    assert tela.progress_bar.value() == tela.progress_bar.maximum()
    assert tela.avisos == [("info", "Sucesso", "Processo de Gestão PMIB finalizado com sucesso!")]
    assert tela.btn_aplicar.isEnabled() and tela.btn_painel.isEnabled()


def test_gestao_com_avisos_e_arquivos_nao_gravados(tela, qtbot, monkeypatch):
    tela.caixa_gerar_painel.setChecked(False)
    _com_gerente(monkeypatch, GerenteFalso([
        "[AVISO] _STATUS_PMIB aberto no Excel: pulado", "[AVISO] Não gravados nesta rodada (2):",
        " -> a.xlsx", "fim"]))
    _preencher(tela)
    _rodar_gestao(tela, qtbot, "fim")
    qtbot.waitUntil(lambda: bool(tela.avisos), timeout=2000)
    assert tela.avisos == [("aviso", "Concluído com avisos",
                            "O processo de Gestão PMIB terminou, mas 2 arquivo(s) não foram gravados nesta "
                            "rodada: o motivo de cada um e o que fazer estão no fim do log; e 1 aviso(s) "
                            "pedem atenção (procure as linhas [AVISO] no log).")]
    assert (True, 1.0) in tela.progressos


def test_gestao_com_erro_nao_diz_sucesso(tela, qtbot, monkeypatch):
    _com_gerente(monkeypatch, GerenteFalso(["[ERRO] Atualização Mapeamento: aba sumiu"]))
    _preencher(tela)
    texto = _rodar_gestao(tela, qtbot, "Painel não gerado")
    # A caixa do painel está ligada (padrão), mas fluxo com erro não gera.
    assert ">  -> Painel não gerado: o processo terminou com erro. Use o botão 'Gerar painel'." in texto
    assert tela.avisos == [("aviso", "Aviso",
                            "O processo foi interrompido ou terminou com erros.\n\n"
                            "O que foi gravado antes do erro continua gravado. Veja o log para saber o que faltou.")]
    assert tela.progressos == []


def test_gestao_com_excecao_vira_erro_fatal(tela, qtbot, monkeypatch):
    _com_gerente(monkeypatch, GerenteFalso([], falha=RuntimeError("planilha corrompida")))
    _preencher(tela)
    texto = _rodar_gestao(tela, qtbot, "[ERRO FATAL]")
    assert "> [ERRO FATAL]: planilha corrompida" in texto
    assert tela.avisos == [("erro", "Erro", "Ocorreu um erro fatal durante a execução:\nplanilha corrompida")]


def test_gestao_gera_o_painel_depois_da_gravacao(tela, qtbot, monkeypatch):
    ordem = []
    gerente = _com_gerente(monkeypatch, GerenteFalso(["gravado"]))
    monkeypatch.setattr(tela, "_gerar_painel_e_abrir",
                        lambda raiz, mestra: ordem.append(("painel", raiz, mestra)) or True)
    _preencher(tela)
    _rodar_gestao(tela, qtbot, "gravado")
    qtbot.waitUntil(lambda: bool(tela.avisos), timeout=2000)
    assert gerente.chamadas and ordem == [("painel", "/d/raiz", "/d/Mapeamento.xlsx")]
    assert tela.avisos == [("info", "Sucesso", "Processo de Gestão PMIB finalizado com sucesso!")]


def test_painel_que_falha_vira_aviso(tela, qtbot, monkeypatch):
    _com_gerente(monkeypatch, GerenteFalso(["gravado"]))
    monkeypatch.setattr(tela, "_gerar_painel_e_abrir", lambda raiz, mestra: False)
    _preencher(tela)
    _rodar_gestao(tela, qtbot, "gravado")
    qtbot.waitUntil(lambda: bool(tela.avisos), timeout=2000)
    assert tela.avisos == [("aviso", "Concluído com avisos",
                            "O processo de Gestão PMIB terminou, mas 1 aviso(s) pedem atenção "
                            "(procure as linhas [AVISO] no log).")]


# ---------------------------------------------------------------------------
# Popup das listas novas (o `callback_confirm`)
# ---------------------------------------------------------------------------
def _df_novos():
    return DataFrameFalso({
        7: {"No. do Documento": "IT-1", "Título": "Lista A"},
        9: {"No. do Documento": "IT-2", "Título": "Lista B"},
        12: {"No. do Documento": "IT-3", "Título": "Lista C"},
    })


def _abrir_popup(tela, qtbot, monkeypatch):
    tela.caixa_gerar_painel.setChecked(False)
    gerente = _com_gerente(monkeypatch, GerenteFalso(["antes", "CONFIRMAR", "depois"], df_novos=_df_novos()))
    _preencher(tela)
    tela.btn_run.click()
    qtbot.waitUntil(lambda: isinstance(getattr(tela, "_dialogo_aberto", None), tela_mod.NovasListasDialog),
                    timeout=3000)
    dialogo = tela._dialogo_aberto
    qtbot.waitUntil(dialogo.isVisible, timeout=2000)
    return gerente, dialogo


def test_popup_lista_as_novas_e_devolve_as_marcadas(tela, qtbot, monkeypatch):
    gerente, dialogo = _abrir_popup(tela, qtbot, monkeypatch)
    assert dialogo.windowTitle() == "Novas Listas Encontradas"
    assert dialogo.rotulo_titulo.text() == "Novas Listas de Sobressalentes Encontradas na base de dados:"
    assert dialogo.rotulo_instrucao.text() == (
        "Selecione abaixo quais você deseja adicionar à Planilha de Mapeamento.")
    assert [c.text() for c in dialogo.caixas.values()] == [
        "[IT-1]  -  Lista A", "[IT-2]  -  Lista B", "[IT-3]  -  Lista C"]
    assert all(c.isChecked() for c in dialogo.caixas.values())  # começam todas marcadas
    assert dialogo.isModal()
    dialogo.caixas[9].click()
    dialogo.botao_confirmar.click()
    qtbot.waitUntil(lambda: "depois" in tela.console.toPlainText(), timeout=3000)
    assert gerente.confirmado == ("loc", [7, 12])


def test_popup_marcar_e_desmarcar_todas(tela, qtbot, monkeypatch):
    gerente, dialogo = _abrir_popup(tela, qtbot, monkeypatch)
    dialogo.botao_desmarcar.click()
    assert not any(c.isChecked() for c in dialogo.caixas.values())
    dialogo.caixas[12].click()
    dialogo.botao_marcar.click()
    assert all(c.isChecked() for c in dialogo.caixas.values())
    dialogo.botao_desmarcar.click()
    dialogo.botao_confirmar.click()
    qtbot.waitUntil(lambda: "depois" in tela.console.toPlainText(), timeout=3000)
    assert gerente.confirmado == ("loc", [])


@pytest.mark.parametrize("como", ["ignorar", "fechar", "esc"])
def test_popup_ignorar_fechar_ou_esc_nao_adiciona_nada(tela, qtbot, monkeypatch, como):
    gerente, dialogo = _abrir_popup(tela, qtbot, monkeypatch)
    if como == "ignorar":
        dialogo.botao_ignorar.click()
    elif como == "fechar":
        dialogo.close()
    else:
        dialogo.reject()
    qtbot.waitUntil(lambda: "depois" in tela.console.toPlainText(), timeout=3000)
    # `pd.DataFrame()` vazio, como a tela antiga (o pandas é dublado na suíte).
    assert gerente.confirmado is sys.modules["pandas"].DataFrame.return_value


# ---------------------------------------------------------------------------
# Painel avulso
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("faltando, mensagem", [
    ("raiz", "Por favor, selecione a Pasta Raiz (Passo 2)."),
    ("mestra", "Por favor, selecione a Planilha de mapeamento (Passo 3)."),
])
def test_gerar_painel_valida(tela, avisos_qt, monkeypatch, faltando, mensagem):
    chamadas = []
    monkeypatch.setattr(tela, "_gerar_painel_e_abrir", lambda *a: chamadas.append(a))
    _preencher(tela, **{faltando: ""})
    tela.btn_painel.click()
    assert avisos_qt == [("Aviso", mensagem)] and chamadas == []


def test_gerar_painel_trava_os_botoes_e_devolve(tela, qtbot, monkeypatch):
    solta, chamadas = threading.Event(), []

    def gerar(raiz, mestra):
        chamadas.append((raiz, mestra))
        solta.wait(3)
        return True

    monkeypatch.setattr(tela, "_gerar_painel_e_abrir", gerar)
    _preencher(tela, api="")
    tela.btn_painel.click()
    assert not (tela.btn_run.isEnabled() or tela.btn_aplicar.isEnabled() or tela.btn_painel.isEnabled())
    solta.set()
    qtbot.waitUntil(tela.btn_painel.isEnabled, timeout=3000)
    assert chamadas == [("/d/raiz", "/d/Mapeamento.xlsx")]
    assert tela.btn_run.isEnabled() and tela.btn_aplicar.isEnabled()


def _painel_falso(monkeypatch, gerar):
    modulo = SimpleNamespace(NOME_DO_ARQUIVO="Painel de Sobressalentes.html", gerar_painel=gerar)
    monkeypatch.setitem(sys.modules, "sigft.services.painel", modulo)
    import sigft.services as servicos
    monkeypatch.setattr(servicos, "painel", modulo, raising=False)


def test_gerar_painel_e_abrir_no_navegador(tela, qtbot, monkeypatch, tmp_path):
    abertos = []

    def gerar(raiz, mestra, saida, callback_log=None):
        callback_log("painel: 3 PMIBs")
        return saida

    _painel_falso(monkeypatch, gerar)
    monkeypatch.setattr(tela_mod.webbrowser, "open", lambda url: abertos.append(url))
    assert tela._gerar_painel_e_abrir(str(tmp_path), "/d/M.xlsx") is True
    assert abertos == [(tmp_path / "Painel de Sobressalentes.html").resolve().as_uri()]
    qtbot.waitUntil(lambda: "painel: 3 PMIBs" in tela.console.toPlainText(), timeout=2000)
    assert "> Gerando o painel de sobressalentes..." in tela.console.toPlainText()


def test_painel_travado_diz_o_motivo(tela, qtbot, monkeypatch, tmp_path):
    def gerar(*a, **k):
        raise PermissionError(13, "Permission denied")

    _painel_falso(monkeypatch, gerar)
    monkeypatch.setattr(tela_mod.travas, "diagnosticar",
                        lambda saida, e: SimpleNamespace(motivo="está aberto no navegador",
                                                         o_que_fazer="Feche a aba."))
    assert tela._gerar_painel_e_abrir(str(tmp_path), "/d/M.xlsx") is False
    qtbot.waitUntil(lambda: "[AVISO] O painel não foi gravado" in tela.console.toPlainText(), timeout=2000)
    assert ("[AVISO] O painel não foi gravado: Painel de Sobressalentes.html está aberto no navegador. "
            "Feche a aba. Depois, clique em 'Gerar painel'.") in tela.console.toPlainText()


def test_painel_com_outro_erro_e_navegador_que_falha(tela, qtbot, monkeypatch, tmp_path):
    _painel_falso(monkeypatch, lambda *a, **k: (_ for _ in ()).throw(ValueError("sem dados")))
    assert tela._gerar_painel_e_abrir(str(tmp_path), "/d/M.xlsx") is False
    qtbot.waitUntil(lambda: "[AVISO] O painel não foi gerado: ValueError: sem dados"
                    in tela.console.toPlainText(), timeout=2000)

    _painel_falso(monkeypatch, lambda raiz, mestra, saida, callback_log=None: saida)

    def falha(url):
        raise OSError("sem navegador")

    monkeypatch.setattr(tela_mod.webbrowser, "open", falha)
    assert tela._gerar_painel_e_abrir(str(tmp_path), "/d/M.xlsx") is True
    qtbot.waitUntil(lambda: "[AVISO] Painel gravado, mas não consegui abri-lo no navegador (sem navegador)"
                    in tela.console.toPlainText(), timeout=2000)


# ---------------------------------------------------------------------------
# Autorizações de Itaipu
# ---------------------------------------------------------------------------
def _autorizados_falso(monkeypatch, linhas=(), falha=None):
    chamadas = []

    def executar(export, raiz, *, callback_travados=None):
        chamadas.append((export, raiz, callback_travados))
        if falha:
            raise falha
        yield from linhas

    modulo = SimpleNamespace(executar=executar)
    monkeypatch.setitem(sys.modules, "sigft.services.autorizados", modulo)
    import sigft.services as servicos
    monkeypatch.setattr(servicos, "autorizados", modulo, raising=False)
    return chamadas


@pytest.mark.parametrize("faltando, mensagem", [
    ("aut", "Por favor, selecione o export de autorizados de Itaipu (Passo 4)."),
    ("raiz", "Por favor, selecione a Pasta Raiz dos _STATUS_PMIB (Passo 2)."),
])
def test_autorizacoes_validam(tela, avisos_qt, monkeypatch, faltando, mensagem):
    chamadas = _autorizados_falso(monkeypatch)
    _preencher(tela, aut="/d/aut.xlsx")
    if faltando == "aut":
        tela.path_autorizados = ""
    else:
        tela.entry_root.setText("")
    tela.btn_aplicar.click()
    assert avisos_qt == [("Aviso", mensagem)] and chamadas == []


def _rodar_aut(tela, qtbot, ultima):
    tela.btn_aplicar.click()
    qtbot.waitUntil(tela.btn_aplicar.isEnabled, timeout=3000)
    qtbot.waitUntil(lambda: bool(tela.avisos), timeout=2000)
    qtbot.waitUntil(lambda: ultima in tela.console.toPlainText(), timeout=2000)
    return tela.console.toPlainText()


def test_autorizacoes_aplicadas(tela, qtbot, monkeypatch):
    chamadas = _autorizados_falso(monkeypatch, ["Lendo o export...", "12 PMIBs AUTORIZADOS"])
    _preencher(tela, aut="/d/aut.xlsx")
    texto = _rodar_aut(tela, qtbot, "12 PMIBs AUTORIZADOS")
    assert chamadas == [("/d/aut.xlsx", "/d/raiz", tela.perguntar_arquivos_travados)]
    ordem = ["> Aplicando o export de autorizados de Itaipu...", "> Lendo o export...", "> 12 PMIBs AUTORIZADOS"]
    assert [texto.index(linha) for linha in ordem] == sorted(texto.index(linha) for linha in ordem)
    qtbot.waitUntil(lambda: len(tela.progressos) == 2, timeout=2000)
    assert tela.progressos == [(True, 0), (True, 1.0)]
    assert tela.avisos == [("info", "Sucesso", "Autorizações de Itaipu aplicadas.")]


def test_autorizacoes_com_erro(tela, qtbot, monkeypatch):
    _autorizados_falso(monkeypatch, ["[ERRO] coluna PMIB não encontrada"])
    _preencher(tela, aut="/d/aut.xlsx")
    _rodar_aut(tela, qtbot, "coluna PMIB")
    assert tela.avisos == [("aviso", "Aviso", "As autorizações não foram aplicadas. Veja o motivo no log.")]


def test_autorizacoes_com_avisos(tela, qtbot, monkeypatch):
    _autorizados_falso(monkeypatch, ["[AVISO] Não gravados nesta rodada (1):", " -> x.xlsx"])
    _preencher(tela, aut="/d/aut.xlsx")
    _rodar_aut(tela, qtbot, "x.xlsx")
    assert tela.avisos == [("aviso", "Concluído com avisos",
                            "As autorizações foram aplicadas, mas 1 arquivo(s) não foram gravados nesta "
                            "rodada: o motivo de cada um e o que fazer estão no fim do log.")]


def test_autorizacoes_com_excecao(tela, qtbot, monkeypatch):
    _autorizados_falso(monkeypatch, falha=ValueError("export vazio"))
    _preencher(tela, aut="/d/aut.xlsx")
    texto = _rodar_aut(tela, qtbot, "[ERRO FATAL]")
    assert "> [ERRO FATAL]: export vazio" in texto
    assert tela.avisos == [("erro", "Erro", "Ocorreu um erro ao aplicar as autorizações:\nexport vazio")]
    assert tela.btn_run.isEnabled() and tela.btn_painel.isEnabled()


# ---------------------------------------------------------------------------
# A caixa de marcar (CTkCheckBox)
# ---------------------------------------------------------------------------
def test_caixa_de_marcar_alterna_pela_caixa_e_pelo_texto(qt_interface, qtbot):
    from PySide6.QtCore import QPoint, Qt
    from sigft.app_qt.widgets import controles

    c = controles.CaixaDeMarcar("Gerar painel ao terminar", tamanho_fonte=12)
    qtbot.addWidget(c)
    c.show()
    qtbot.waitExposed(c)
    assert c.height() == 24 and c.sizeHint().height() == 24
    texto = c.fontMetrics().horizontalAdvance(c.text())
    assert c.sizeHint().width() == controles.LADO_CAIXA + controles.VAO_TEXTO_CAIXA + texto
    qtbot.mouseClick(c, Qt.MouseButton.LeftButton, pos=QPoint(5, 12))
    assert c.isChecked()
    qtbot.mouseClick(c, Qt.MouseButton.LeftButton, pos=QPoint(c.width() - 3, 12))
    assert not c.isChecked()


# ---------------------------------------------------------------------------
# Texto dos avisos (a mesma regra da tela antiga)
# ---------------------------------------------------------------------------
def test_texto_dos_avisos():
    f = tela_mod._texto_dos_avisos
    assert f("X", 1, 0) == "X, mas 1 aviso(s) pedem atenção (procure as linhas [AVISO] no log)."
    assert f("X", 1, 3) == ("X, mas 3 arquivo(s) não foram gravados nesta rodada: o motivo de cada um e o "
                            "que fazer estão no fim do log.")


# ---------------------------------------------------------------------------
# Geometria contra o CustomTkinter
# ---------------------------------------------------------------------------
def test_medidas_iguais_as_do_customtkinter(qt_interface, qtbot, monkeypatch):
    # Medidas da tela antiga (CustomTkinter, janela 1280x850, winfo_* da tela;
    # aqui relativas à área da tela, que começa 277 px à direita -- a barra
    # lateral -- e no topo). Ver capturas/e4.2.
    from sigft.app_qt import estilo

    monkeypatch.setattr(tela_mod.prefs, "get_opcao", lambda chave, padrao=None: padrao)
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloPMIBManager()
        qtbot.addWidget(t)
        t.resize(1003, 850)
        t.show()
        qtbot.waitExposed(t)

        def geo(w):
            p = w.mapTo(t, w.rect().topLeft())
            return p.x(), p.y(), w.width(), w.height()

        r = t._rotulos
        cartao1, cartao2 = r["config"].parentWidget(), r["autorizacoes"].parentWidget()
        assert geo(t.label_titulo)[:2] == (40, 30)
        assert geo(cartao1) == (40, 84, 923, 301)
        assert geo(r["config"])[:2] == (55, 99) and geo(r["config"])[3] == 28
        # O botão cresce até caber o texto (286 lá; a medida do texto do Roboto
        # no Qt sai 3 px menor); o rótulo vem 15 px depois.
        x, y, w, h = geo(t.btn_api)
        assert (x, y, h) == (55, 140, 28) and abs(w - 286) <= 4
        assert geo(t.lbl_api_status)[:2] == (x + w + 15, 140)
        assert geo(r["raiz"]) == (55, 184, 280, 28)
        assert geo(t.entry_root) == (340, 184, 300, 28)
        assert geo(t.btn_buscar) == (645, 184, 80, 28)
        assert geo(t.btn_master) == (55, 228, 280, 28)
        assert geo(t.lbl_master_status)[:2] == (350, 228)
        assert geo(t.btn_run) == (326, 284, 350, 50)
        # Caixa (160 lá: 24 + 6 + texto) e "Gerar painel" a 20 px, o par
        # centrado no cartão: lá a caixa começa em 331 e o botão em 511.
        x, y, w, h = geo(t.caixa_gerar_painel)
        assert (y, h) == (344, 24) and abs(w - 160) <= 4 and abs(x - 331) <= 2
        bx, by, bw, bh = geo(t.btn_painel)
        assert (by, bw, bh) == (342, 160, 28) and bx - (x + w) == 20
        assert abs((x + bx + bw) / 2 - (40 + 923 / 2)) <= 1
        assert geo(cartao2)[:3] == (40, 395, 923)
        assert geo(r["autorizacoes"])[:2] == (55, 410)
        assert geo(r["descricao_aut"])[:2] == (55, 438) and geo(r["descricao_aut"])[3] == 34
        assert geo(t.btn_autorizados) == (55, 480, 280, 28)
        assert geo(t.lbl_autorizados)[:2] == (350, 480)
        assert geo(t.btn_aplicar) == (748, 480, 200, 28)
        assert geo(cartao2)[3] == 128
        assert geo(t.progress_bar) == (201, 543, 600, 12)
        assert geo(t.console) == (40, 565, 923, 245)
    finally:
        qt_interface.setStyleSheet(anterior)


def test_popup_medidas_iguais_as_do_customtkinter(qt_interface, qtbot):
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        itens = [(i, f"[IT-GEV-LMR-{i:04d}]  -  Lista {i}") for i in range(1, 13)]
        d = tela_mod.NovasListasDialog(None, itens=itens, evento_espera=threading.Event(), resultado={})
        qtbot.addWidget(d)
        d.show()
        qtbot.waitExposed(d)

        def geo(w):
            p = w.mapTo(d, w.rect().topLeft())
            return p.x(), p.y(), w.width(), w.height()

        assert (d.width(), d.height()) == (750, 550)
        assert geo(d.rotulo_titulo)[1] == 15 and geo(d.rotulo_instrucao)[1] == 48
        assert geo(d.area) == (20, 91, 710, 396)
        caixas = list(d.caixas.values())
        assert geo(caixas[0])[:2] == (36, 103) and geo(caixas[0])[3] == 24
        assert geo(caixas[1])[1] - geo(caixas[0])[1] == 36
        assert geo(d.botao_marcar) == (25, 507, 120, 28)
        assert geo(d.botao_desmarcar) == (155, 507, 120, 28)
        assert geo(d.botao_ignorar) == (415, 507, 150, 28)
        assert geo(d.botao_confirmar) == (575, 507, 150, 28)
    finally:
        qt_interface.setStyleSheet(anterior)

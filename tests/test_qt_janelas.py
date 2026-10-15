"""Janelas auxiliares das telas na interface Qt (E3.2).

Mesmo contrato de `sigft/app/views/janelas.py`, que é o que as telas usam:
mesmas assinaturas, mesmos callbacks, mesmos textos. A diferença que importa
é a `JanelaAcaoRobo`: lá ela era criada DE DENTRO do robô (widget fora da
thread da interface); aqui ela pode ser chamada do worker e a janela nasce na
thread da interface.
"""
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QApplication, QMessageBox

from sigft.app import theme
from sigft.app_qt import estilo
from sigft.app_qt.views import janelas
from sigft.app_qt.widgets import dialogos_selecao
from sigft.core.pdm_catalogo import PDM, CatalogoPDM


# --- dublês ------------------------------------------------------------------

class _Linha(dict):
    """O `row` do `iterrows()`: `.get` como a Series, e `to_numpy()`."""

    def to_numpy(self):
        return SimpleNamespace(tolist=lambda: list(self.values()))


class _At:
    def __init__(self, df):
        self._df = df

    def __setitem__(self, chave, valor):
        indice, coluna = chave
        self._df.linhas[self._df.index.index(indice)][coluna] = valor

    def __getitem__(self, chave):
        indice, coluna = chave
        return self._df.linhas[self._df.index.index(indice)][coluna]


class _Loc:
    """`df.loc[indice]`: a linha (com `.get`) do índice."""

    def __init__(self, df):
        self._df = df

    def __getitem__(self, indice):
        return _Linha(self._df.linhas[self._df.index.index(indice)])


class DfFalso:
    """Só o que as janelas usam de um DataFrame (o conftest dubla o pandas)."""

    def __init__(self, linhas, indice=None):
        self.linhas = [dict(linha) for linha in linhas]
        self.index = list(indice) if indice is not None else list(range(len(self.linhas)))
        self.columns = list(self.linhas[0]) if self.linhas else []
        self.at = _At(self)
        self.loc = _Loc(self)

    def iterrows(self):
        for indice, linha in zip(self.index, self.linhas):
            yield indice, _Linha(linha)

    def copy(self):
        return DfFalso(self.linhas, self.index)


REVISAO = [
    {"descricao_original": "VALVULA ESFERA 2POL", "pdm_escolhido": "PDM.4820.004 - VALVULA ESFERA",
     "descricao_curta": "VALV ESF", "unidade": "PC", "tipo": "Material"},
    {"descricao_original": "ROLAMENTO 6205", "pdm_escolhido": "PDM.3110.002 - ROLAMENTO",
     "descricao_curta": "ROLAM", "unidade": "PC", "tipo": "Material"},
    {"descricao_original": "CAMERA IP", "pdm_escolhido": "PDM.5820.010 - CAMERA VIDEO",
     "descricao_curta": "CAM", "unidade": "PC", "tipo": "Equipamento"},
]


def _catalogo(n=3):
    base = [PDM(codigo="PDM.4820.004", classe="4820", titulo="VALVULA ESFERA",
                caracteristicas=("DIAMETRO", "MATERIAL", "CLASSE", "EXTREMIDADE", "ACIONAMENTO",
                                 "NORMA", "VEDACAO")),
            PDM(codigo="PDM.3110.002", classe="3110", titulo="ROLAMENTO", caracteristicas=("DIAMETRO",)),
            PDM(codigo="PDM.5820.010", classe="5820", titulo="CAMERA VIDEO", caracteristicas=())]
    extras = [PDM(codigo=f"PDM.9{i:03d}.001", classe="9999", titulo=f"ITEM {i}") for i in range(max(0, n - 3))]
    return CatalogoPDM(base + extras)


def _fila():
    return [{"descricao": "BOMBA CENTRIFUGA", "pmib_original": "PMIB.001.1010", "pmib_alvo": "PMIB.001.2010"},
            {"descricao": "SELO MECANICO", "pmib_original": "PMIB.002.1020", "pmib_alvo": "PMIB.002.2020"}]


def _duplo_clique(qtbot, tree, linha):
    """Duplo clique de verdade na linha (o primeiro clique a seleciona, como no Tk)."""
    tree.window().show()
    qtbot.waitExposed(tree.window())
    centro = tree.visualItemRect(tree.topLevelItem(linha)).center()
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=centro)
    qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=centro)


def _textos(tree, coluna):
    return [tree.topLevelItem(i).text(coluna) for i in range(tree.topLevelItemCount())]


@pytest.fixture
def folha(qt_interface):
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    yield qt_interface
    qt_interface.setStyleSheet(anterior)


@pytest.fixture
def avisos(monkeypatch):
    """QMessageBox.warning trocado por um registro (não abre caixa no teste)."""
    registro = []
    monkeypatch.setattr(janelas.QMessageBox, "warning",
                        staticmethod(lambda _p, titulo, texto, *a: registro.append((titulo, texto))))
    return registro


def _fechar_depois(janela, ms=0):
    QTimer.singleShot(ms, janela.close)


# --- JanelaSelecao / JanelaSelecaoDuplicadas ----------------------------------

def test_janela_selecao_devolve_o_indice_do_dataframe_em_int(qt_interface, qtbot):
    escolhas = []
    df = DfFalso([{"DESCRIÇÃO": "A", "CÓDIGO PMIB": ""}, {"DESCRIÇÃO": "B", "CÓDIGO PMIB": "X"},
                  {"DESCRIÇÃO": "C", "CÓDIGO PMIB": ""}], indice=[5, 7, 9])
    dlg = janelas.JanelaSelecao(None, df, escolhas.append)
    qtbot.addWidget(dlg)
    assert isinstance(dlg, dialogos_selecao.TabelaSelecaoDialog)
    assert dlg.windowTitle() == "Seleção de Itens"
    assert dlg.rotulo.text() == "Selecione as linhas para processar:"
    assert dlg.botao_cancelar is None  # com_cancelar=False, como lá
    assert dlg.isModal()
    assert (dlg.width(), dlg.height()) == (900, 600)
    dlg.tree.topLevelItem(0).setSelected(True)
    dlg.tree.topLevelItem(2).setSelected(True)
    dlg.botao_confirmar.click()
    assert escolhas == [[5, 9]]


def test_janela_selecao_duplicadas_devolve_os_itens_da_fila(qt_interface, qtbot):
    escolhas = []
    fila = _fila() + [{"descricao": "PARAFUSO", "pmib_original": "P1", "pmib_alvo": "P2"}]
    dlg = janelas.JanelaSelecaoDuplicadas(None, fila, escolhas.append)
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Selecionar Fichas para Cópia"
    assert dlg.rotulo.text() == "Selecione as fichas que deseja processar neste lote:"
    assert [dlg.tree.headerItem().text(i) for i in range(3)] == [
        "Descrição", "PMIB Original (Base)", "PMIB Alvo (Novo)"]
    assert _textos(dlg.tree, 1) == ["PMIB.001.1010", "PMIB.002.1020", "P1"]
    assert dlg.selecionados == ["0", "1", "2"]  # tudo já vem marcado
    assert dlg.botao_cancelar is not None
    dlg.tree.topLevelItem(1).setSelected(False)
    dlg.botao_confirmar.click()
    assert escolhas == [[fila[0], fila[2]]]
    assert escolhas[0][0] is fila[0]  # o PRÓPRIO dict: a revisão edita a fila


def test_janela_selecao_duplicadas_cancelar_nao_chama(qt_interface, qtbot):
    escolhas = []
    dlg = janelas.JanelaSelecaoDuplicadas(None, _fila(), escolhas.append)
    qtbot.addWidget(dlg)
    dlg.botao_cancelar.click()
    assert escolhas == [] and not dlg.isVisible()


# --- JanelaResumo -------------------------------------------------------------

def test_janela_resumo_mostra_as_quatro_colunas_com_traco_no_que_falta(qt_interface, qtbot):
    df = DfFalso([{"descricao_original": "VALVULA", "PMIB_CRIADO": "PMIB.1", "pdm_escolhido": "PDM.A",
                   "PDM_COM_REVISAO": "PDM.A R2"},
                  {"descricao_original": "ROLAMENTO", "PMIB_CRIADO": "INTERROMPIDO"}])
    j = janelas.JanelaResumo(None, df)
    qtbot.addWidget(j)
    assert j.isVisible() and not j.isModal()
    assert j.windowTitle() == "Resumo Final"
    assert j.rotulo.text() == "Resumo da Execução"
    assert [j.tree.headerItem().text(i) for i in range(4)] == [
        "Descrição Original", "PMIB Criado", "PDM (IA)", "PDM (Portal Final)"]
    assert [j.tree.topLevelItem(1).text(i) for i in range(4)] == ["ROLAMENTO", "INTERROMPIDO", "-", "-"]
    assert j.botao_fechar.text() == "Fechar"
    j.botao_fechar.click()
    assert not j.isVisible()


def test_janela_resumo_sobrevive_sem_referencia(qt_interface, qtbot):
    # A tela abre e esquece (`na_interface(JanelaResumo, self, df)`): a janela
    # não pode sumir quando o Python solta o objeto.
    import gc
    janelas.JanelaResumo(None, DfFalso([{"descricao_original": "X"}]))
    gc.collect()
    abertas = [w for w in QApplication.topLevelWidgets()
               if isinstance(w, janelas.JanelaResumo) and w.isVisible()]
    assert abertas
    for w in abertas:
        w.close()


# --- JanelaEscolherPDM ----------------------------------------------------------

def test_escolher_pdm_lista_o_catalogo_e_seleciona_o_primeiro(qt_interface, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    assert j.isModal() and j.windowTitle() == "Escolher PDM"
    assert j.rotulo.text() == "Busque entre os 3 PDMs do catálogo:"
    assert j.entry_busca.placeholderText() == "ex.: valvula esfera  |  4820.004  |  camera"
    assert [j.lista.headerItem().text(i) for i in range(3)] == ["PDM", "Classe", "Características"]
    assert j.lista.topLevelItem(0).text(0) == "PDM.4820.004 - VALVULA ESFERA"
    assert j.lista.topLevelItem(0).text(1) == "4820"
    # só as 6 primeiras características
    assert j.lista.topLevelItem(0).text(2) == "DIAMETRO; MATERIAL; CLASSE; EXTREMIDADE; ACIONAMENTO; NORMA"
    assert j.lista.topLevelItem(0).isSelected()
    assert j.lista.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    assert j.lbl_contagem.text() == "3 PDM(s) na lista"
    j.close()


def test_escolher_pdm_avisa_quando_mostra_so_os_primeiros(qt_interface, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo(60))
    qtbot.addWidget(j)
    assert j.lista.topLevelItemCount() == 40
    assert j.lbl_contagem.text() == "40 PDM(s) na lista (mostrando os 40 primeiros)"
    j.close()


def test_escolher_pdm_busca_ao_digitar(qt_interface, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    qtbot.keyClicks(j.entry_busca, "rolamento")
    assert _textos(j.lista, 0)[0] == "PDM.3110.002 - ROLAMENTO"
    assert j.lista.topLevelItem(0).isSelected()
    j.close()


def test_escolher_pdm_confirmar_guarda_a_escolha_e_fecha(qt_interface, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    j.lista.setCurrentItem(j.lista.topLevelItem(2))  # o clique: troca a seleção (browse)
    assert [i.text(0) for i in j.lista.selectedItems()] == ["PDM.5820.010 - CAMERA VIDEO"]
    j.botao_usar.click()
    assert j.escolha.codigo == "PDM.5820.010"
    assert not j.isVisible()
    assert j.esperar() is j.escolha  # já fechada: volta na hora


def test_escolher_pdm_esperar_e_o_wait_window(qt_interface, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    QTimer.singleShot(0, j.botao_usar.click)
    escolha = j.esperar()
    assert escolha.codigo == "PDM.4820.004"


def test_escolher_pdm_enter_e_duplo_clique_confirmam(qt_interface, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    qtbot.keyClick(j.entry_busca, Qt.Key.Key_Return)
    assert j.escolha.codigo == "PDM.4820.004" and not j.isVisible()

    j2 = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j2)
    _duplo_clique(qtbot, j2.lista, 1)
    assert j2.escolha.codigo == "PDM.3110.002" and not j2.isVisible()


def test_escolher_pdm_sem_selecao_avisa_e_nao_fecha(qt_interface, qtbot, avisos):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    j.lista.clearSelection()
    j.botao_usar.click()
    assert avisos == [("Aviso", "Selecione um PDM da lista.")]
    assert j.isVisible() and j.escolha is None
    j.close()


def test_escolher_pdm_cancelar_e_x_devolvem_none(qt_interface, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    j.botao_cancelar.click()
    assert j.escolha is None and not j.isVisible()
    j2 = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j2)
    _fechar_depois(j2)
    assert j2.esperar() is None


def test_escolher_pdm_busca_sem_resultado(qt_interface, qtbot, avisos):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    j.entry_busca.setText("zzzzqqq")
    assert j.lista.topLevelItemCount() == 0
    assert j.lbl_contagem.text() == "0 PDM(s) na lista"
    j.confirmar()
    assert avisos == [("Aviso", "Selecione um PDM da lista.")]
    j.close()


# --- JanelaRevisaoPDM -------------------------------------------------------------

def _revisao(qtbot, callback=None, catalogo=None, df=None):
    df = df if df is not None else DfFalso(REVISAO)
    j = janelas.JanelaRevisaoPDM(None, df, callback or (lambda _df: None), catalogo=catalogo)
    qtbot.addWidget(j)
    return j, df


def test_revisao_pdm_preenche_a_tabela(qt_interface, qtbot):
    j, _ = _revisao(qtbot)
    assert j.isModal() and j.windowTitle() == "Revisão de PDMs - Pré-Automação"
    assert j.rotulo.text() == "Verifique os PDMs sugeridos antes da automação."
    assert [j.tree.headerItem().text(i) for i in range(7)] == [
        "ID", "Descrição Original", "PDM Escolhido (EDITÁVEL)", "Confiança", "Descrição Curta", "UN",
        "Tipo"]
    # Linha que não veio da IA ("Pular IA"): sem confiança, na ordem da planilha.
    assert [j.tree.topLevelItem(2).text(i) for i in range(7)] == [
        "2", "CAMERA IP", "PDM.5820.010 - CAMERA VIDEO", "", "CAM", "PC", "Equipamento"]
    assert j.tree.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert j.botao_confirmar.text() == "CONFIRMAR E AVANÇAR >>"
    assert j.botao_editar.text() == "Editar PDM Selecionado"
    j.close()


def test_revisao_pdm_editar_sem_selecao_avisa(qt_interface, qtbot, avisos):
    j, _ = _revisao(qtbot)
    j.botao_editar.click()
    assert avisos == [("Aviso", "Selecione uma ou mais linhas para editar o PDM.")]
    j.close()


def test_revisao_pdm_editar_com_catalogo_usa_a_janela_de_escolha(qt_interface, qtbot, monkeypatch):
    abertas = []

    class EscolhaFalsa:
        def __init__(self, parent, catalogo, sugestoes=()):
            abertas.append((parent, catalogo))
            self.escolha = catalogo.pdms[1]

        def esperar(self):
            return self.escolha

    monkeypatch.setattr(janelas, "JanelaEscolherPDM", EscolhaFalsa)
    cat = _catalogo()
    j, df = _revisao(qtbot, catalogo=cat)
    j.tree.topLevelItem(0).setSelected(True)
    j.tree.topLevelItem(2).setSelected(True)
    j.botao_editar.click()
    assert abertas == [(j, cat)]
    assert j.df_dados.at[0, "pdm_escolhido"] == "PDM.3110.002 - ROLAMENTO"
    assert j.df_dados.at[2, "pdm_escolhido"] == "PDM.3110.002 - ROLAMENTO"
    assert j.df_dados.at[1, "pdm_escolhido"] == "PDM.3110.002 - ROLAMENTO"  # já era
    assert _textos(j.tree, 2)[0] == "PDM.3110.002 - ROLAMENTO"
    assert _textos(j.tree, 1)[0] == "VALVULA ESFERA 2POL"  # o resto da linha fica
    assert df.at[0, "pdm_escolhido"] == "PDM.4820.004 - VALVULA ESFERA"  # trabalha numa cópia
    j.close()


def test_revisao_pdm_editar_com_catalogo_cancelado_nao_muda(qt_interface, qtbot, monkeypatch):
    class EscolhaFalsa:
        def __init__(self, parent, catalogo, sugestoes=()):
            self.escolha = None

        def esperar(self):
            return None

    monkeypatch.setattr(janelas, "JanelaEscolherPDM", EscolhaFalsa)
    j, _ = _revisao(qtbot, catalogo=_catalogo())
    j.tree.topLevelItem(0).setSelected(True)
    j.botao_editar.click()
    assert j.df_dados.at[0, "pdm_escolhido"] == "PDM.4820.004 - VALVULA ESFERA"
    j.close()


def test_revisao_pdm_editar_sem_catalogo_pede_texto(qt_interface, qtbot, monkeypatch):
    pedidos = []

    def get_text(parent, titulo, texto, *a, **k):
        pedidos.append((titulo, texto))
        return "PDM.1234.001 - NOVO", True

    monkeypatch.setattr(janelas.QInputDialog, "getText", staticmethod(get_text))
    j, _ = _revisao(qtbot)
    j.tree.topLevelItem(1).setSelected(True)
    j.botao_editar.click()
    assert pedidos == [("Editar PDM", "Digite o novo código PDM completo (ex: PDM.1234.001 - NOME):")]
    assert j.df_dados.at[1, "pdm_escolhido"] == "PDM.1234.001 - NOVO"
    assert _textos(j.tree, 2)[1] == "PDM.1234.001 - NOVO"
    j.close()


def test_revisao_pdm_editar_sem_catalogo_cancelado_nao_muda(qt_interface, qtbot, monkeypatch):
    monkeypatch.setattr(janelas.QInputDialog, "getText", staticmethod(lambda *a, **k: ("x", False)))
    j, _ = _revisao(qtbot)
    j.tree.topLevelItem(1).setSelected(True)
    j.botao_editar.click()
    assert j.df_dados.at[1, "pdm_escolhido"] == "PDM.3110.002 - ROLAMENTO"
    j.close()


def test_revisao_pdm_confirmar_pergunta_e_entrega_a_copia(qt_interface, qtbot, monkeypatch):
    perguntas = []
    respostas = [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes]

    def question(parent, titulo, texto, *a, **k):
        perguntas.append((titulo, texto))
        return respostas.pop(0)

    monkeypatch.setattr(janelas.QMessageBox, "question", staticmethod(question))
    recebidos = []
    j, df = _revisao(qtbot, callback=recebidos.append)
    j.botao_confirmar.click()  # "Não": fica aberta, ninguém chamado
    assert recebidos == [] and j.isVisible()
    j.botao_confirmar.click()
    assert perguntas == [("Confirmar", "Deseja prosseguir para a automação com estes dados?")] * 2
    assert recebidos == [j.df_dados] and recebidos[0] is not df
    assert not j.isVisible()


def test_revisao_pdm_com_pandas_de_verdade(qt_interface, qtbot, monkeypatch):
    pd = pytest.importorskip("pandas")
    if not isinstance(getattr(pd, "DataFrame", None), type):
        pytest.skip("pandas dublado pelo conftest")
    monkeypatch.setattr(janelas.QInputDialog, "getText", staticmethod(lambda *a, **k: ("PDM.X - Y", True)))
    df = pd.DataFrame(REVISAO)
    j, _ = _revisao(qtbot, df=df)
    j.tree.topLevelItem(1).setSelected(True)
    j.botao_editar.click()
    assert j.df_dados.at[1, "pdm_escolhido"] == "PDM.X - Y"
    assert df.at[1, "pdm_escolhido"] == "PDM.3110.002 - ROLAMENTO"
    j.close()


# --- revisão com a escolha em duas passadas (2026-10-08) ----------------------------
# As linhas como `preparar_para_revisao` as entrega: confiança, "por quê", 2º/3º lugar.

def _da_ia(pdm, confianca="", **extra):
    linha = {"descricao_original": extra.pop("descricao", "ITEM"), "pdm_escolhido": pdm, "pdm_ia": pdm,
             "confianca": confianca, "confianca_final": confianca, "rebaixada": False,
             "origem_do_nenhum": "", "sinais": {}, "alternativas": [], "justificativa": "",
             "interpretacao": {}, "descricao_curta": "C", "unidade": "PC", "tipo": "Material"}
    linha.update(extra)
    return linha


REVISAO_IA = [
    _da_ia("PDM.4820.004 - VALVULA ESFERA", "ALTA", descricao="VALVULA ESFERA 2POL",
           alternativas=[{"pdm": "PDM.3110.002", "motivo": "também gira"}, {"pdm": "PDM.5820.010"},
                         {"pdm": "PDM.0000.000"}]),
    _da_ia("PDM.3110.002 - ROLAMENTO", "BAIXA", descricao="ROLAMENTO 6205", rebaixada=True,
           justificativa="  rolamento de esferas  ",
           sinais={"na_busca": True, "nome_base": False, "caracteristicas": True},
           interpretacao={"e": "rolamento rigido de esferas"}),
    _da_ia("NENHUM", descricao="CAMERA IP", origem_do_nenhum="sem_resposta"),
    _da_ia("PDM.5820.010 - CAMERA VIDEO", "MEDIA", descricao="CAMERA ANALOGICA"),
]


def test_revisao_pdm_confianca_e_ordem_vem_do_servico(qt_interface, qtbot):
    j, _ = _revisao(qtbot, df=DfFalso(REVISAO_IA))
    # NENHUM, BAIXA, MÉDIA, ALTA; a coluna ID continua com o índice da planilha.
    assert _textos(j.tree, 0) == ["2", "1", "3", "0"]
    assert _textos(j.tree, 3) == ["SEM RESPOSTA", "BAIXA ↓", "MÉDIA", "ALTA"]
    assert _textos(j.tree, 1) == ["CAMERA IP", "ROLAMENTO 6205", "CAMERA ANALOGICA", "VALVULA ESFERA 2POL"]
    assert [j.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) for i in range(4)] == [2, 1, 3, 0]
    j.close()


def test_revisao_pdm_mostra_o_porque_da_linha_selecionada(qt_interface, qtbot):
    j, _ = _revisao(qtbot, df=DfFalso(REVISAO_IA))
    assert j.lbl_porque.text() == ""
    j.tree.topLevelItem(1).setSelected(True)          # a linha do índice 1
    assert j.lbl_porque.text() == (
        "Por quê: rolamento de esferas\n"
        "Conferências: na busca ✓ · nome base ✗ · características ✓\n"
        "A IA leu: rolamento rigido de esferas")
    j.tree.topLevelItem(0).setSelected(True)          # duas linhas: nenhum "por quê"
    assert j.lbl_porque.text() == ""
    j.tree.clearSelection()
    assert j.lbl_porque.text() == ""
    j.close()


def test_revisao_pdm_porque_e_texto_puro(qt_interface, qtbot):
    # Texto escrito pela IA: "<b>" aparece como está, nunca vira HTML.
    linha = _da_ia("PDM.4820.004 - VALVULA ESFERA", "ALTA", justificativa="<b>forte</b>")
    j, _ = _revisao(qtbot, df=DfFalso([linha]))
    j.tree.topLevelItem(0).setSelected(True)
    assert j.lbl_porque.text() == "Por quê: <b>forte</b>"
    assert j.lbl_porque.textFormat() == Qt.TextFormat.PlainText
    j.close()


def test_revisao_pdm_porque_nao_alarga_a_janela(folha, qtbot):
    longa = _da_ia("PDM.4820.004 - VALVULA ESFERA", "ALTA", justificativa="X" * 2000)
    j, _ = _revisao(qtbot, df=DfFalso([longa]))
    _mostrar(qtbot, j, 1250, 640)
    j.tree.topLevelItem(0).setSelected(True)
    QApplication.processEvents()
    assert j.width() == 1250 and j.lbl_porque.width() == 1226
    j.close()


def test_revisao_pdm_uma_linha_leva_o_2o_e_3o_lugar_ao_seletor(qt_interface, qtbot, monkeypatch):
    abertas = []

    class EscolhaFalsa:
        def __init__(self, parent, catalogo, sugestoes=()):
            abertas.append([(pdm.codigo, rotulo) for pdm, rotulo in sugestoes])
            self.escolha = catalogo.pdms[2]

        def esperar(self):
            return self.escolha

    monkeypatch.setattr(janelas, "JanelaEscolherPDM", EscolhaFalsa)
    j, _ = _revisao(qtbot, catalogo=_catalogo(), df=DfFalso(REVISAO_IA))
    j.tree.topLevelItem(3).setSelected(True)          # a linha do índice 0 (ALTA)
    j.botao_editar.click()
    # O PDM inexistente (PDM.0000.000) fica de fora: `sugestoes_da_linha`.
    assert abertas == [[("PDM.3110.002", "2º lugar: também gira"), ("PDM.5820.010", "3º lugar")]]
    j.tree.topLevelItem(2).setSelected(True)          # duas linhas: sem sugestões
    j.botao_editar.click()
    assert abertas[1] == []
    j.close()


def test_revisao_pdm_troca_manual_marca_manual_na_confianca(qt_interface, qtbot, monkeypatch):
    class EscolhaFalsa:
        def __init__(self, parent, catalogo, sugestoes=()):
            self.escolha = catalogo.pdms[1]

        def esperar(self):
            return self.escolha

    monkeypatch.setattr(janelas, "JanelaEscolherPDM", EscolhaFalsa)
    j, _ = _revisao(qtbot, catalogo=_catalogo(), df=DfFalso(REVISAO_IA))
    j.tree.topLevelItem(3).setSelected(True)
    j.botao_editar.click()
    assert j.tree.topLevelItem(3).text(2) == "PDM.3110.002 - ROLAMENTO"
    assert j.tree.topLevelItem(3).text(3) == "MANUAL"
    assert j.tree.topLevelItem(0).text(3) == "SEM RESPOSTA"   # as outras ficam
    # Só a tela muda: o que a IA disse continua na linha, para a calibração.
    assert j.df_dados.at[0, "pdm_escolhido"] == "PDM.3110.002 - ROLAMENTO"
    assert j.df_dados.at[0, "pdm_ia"] == "PDM.4820.004 - VALVULA ESFERA"
    assert j.df_dados.at[0, "confianca_final"] == "ALTA"
    j.close()


def test_escolher_pdm_com_sugestoes_fixas_no_topo_so_sem_busca(qt_interface, qtbot):
    cat = _catalogo()
    sugestao = [(cat.pdms[2], "2º lugar: é uma câmera")]
    j = janelas.JanelaEscolherPDM(None, cat, sugestoes=sugestao)
    qtbot.addWidget(j)
    assert _textos(j.lista, 0)[0] == "PDM.5820.010 - CAMERA VIDEO"
    assert _textos(j.lista, 2)[0] == "★ 2º lugar: é uma câmera"
    assert _textos(j.lista, 0).count("PDM.5820.010 - CAMERA VIDEO") == 1   # sem repetir
    assert j.lista.topLevelItem(0).isSelected()
    j.entry_busca.setText("camera")
    assert "★ 2º lugar: é uma câmera" not in _textos(j.lista, 2)
    j.entry_busca.setText("")
    assert _textos(j.lista, 2)[0] == "★ 2º lugar: é uma câmera"
    j.close()


# --- JanelaAcaoRobo ---------------------------------------------------------------

def _acao(qtbot):
    d = janelas.DialogoAcaoRobo(None, "Timeout no filtro", "PDM.4820.004 - VALVULA ESFERA")
    qtbot.addWidget(d)
    d.show()
    return d


def test_acao_robo_textos(qt_interface, qtbot):
    d = _acao(qtbot)
    assert d.windowTitle() == "Atenção: Intervenção Necessária"
    assert d.rotulo_erro.text() == "Ocorreu um erro ao processar o item:"
    assert d.caixa_erro.toPlainText() == "Timeout no filtro" and d.caixa_erro.isReadOnly()
    assert d.rotulo_pdm.text() == "PDM Atual: PDM.4820.004 - VALVULA ESFERA"
    assert [b.text() for b in (d.botao_retry, d.botao_pular, d.botao_mudar, d.botao_parar)] == [
        "[0] Tentar Novamente (Mesmo PDM)", "[1] Pular este Item", "[2] Mudar PDM e Tentar",
        "[3] Parar Automação e Salvar"]
    assert d.entry_pdm.placeholderText() == "Novo código PDM..."
    d.close()


@pytest.mark.parametrize("botao, escolha", [("botao_retry", "RETRY"), ("botao_pular", "SKIP"),
                                            ("botao_parar", "STOP")])
def test_acao_robo_cada_botao_responde(qt_interface, qtbot, botao, escolha):
    d = _acao(qtbot)
    getattr(d, botao).click()
    assert (d.escolha, d.novo_pdm) == (escolha, None)
    assert not d.isVisible()


def test_acao_robo_mudar_pdm(qt_interface, qtbot, avisos):
    d = _acao(qtbot)
    d.botao_mudar.click()
    assert avisos == [("Aviso", "Digite o novo PDM antes de clicar.")]
    assert d.escolha is None and d.isVisible()
    d.entry_pdm.setText("  PDM.3110.002 - ROLAMENTO ")
    d.botao_mudar.click()
    assert (d.escolha, d.novo_pdm) == ("CHANGE_PDM", "PDM.3110.002 - ROLAMENTO")
    assert not d.isVisible()


def test_acao_robo_fechar_no_x_para_tudo(qt_interface, qtbot):
    d = _acao(qtbot)
    d.close()
    assert d.escolha == "STOP"


def test_acao_robo_esc_nao_para_a_automacao(qt_interface, qtbot):
    # O Tk não tinha tecla nenhuma; no Qt Esc fecharia -- e fechar é PARAR.
    d = _acao(qtbot)
    qtbot.keyClick(d, Qt.Key.Key_Escape)
    assert d.isVisible() and d.escolha is None
    d.botao_pular.click()


def test_acao_robo_do_worker_abre_na_interface_e_espera(qt_interface, qtbot):
    resultado = {}
    threads = []

    def worker():
        threads.append(threading.get_ident())
        resultado["r"] = janelas.JanelaAcaoRobo(None, msg_erro="erro X", pdm_atual="PDM.A")

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    def aberta():
        return [w for w in QApplication.topLevelWidgets()
                if isinstance(w, janelas.DialogoAcaoRobo) and w.isVisible()]

    qtbot.waitUntil(lambda: bool(aberta()), timeout=3000)
    d = aberta()[0]
    assert d.caixa_erro.toPlainText() == "erro X"
    d.entry_pdm.setText("PDM.B")
    d.botao_mudar.click()
    qtbot.waitUntil(lambda: "r" in resultado, timeout=3000)
    t.join(2)
    r = resultado["r"]
    assert (r.escolha, r.novo_pdm) == ("CHANGE_PDM", "PDM.B")


def test_acao_robo_da_thread_da_interface_tambem_espera(qt_interface, qtbot):
    def responder():
        for w in QApplication.topLevelWidgets():
            if isinstance(w, janelas.DialogoAcaoRobo) and w.isVisible():
                w.botao_retry.click()

    QTimer.singleShot(50, responder)
    r = janelas.JanelaAcaoRobo(None, msg_erro="e", pdm_atual="p")
    assert (r.escolha, r.novo_pdm) == ("RETRY", None)


def test_acao_robo_que_falha_ao_abrir_solta_o_worker_com_stop(qt_interface, qtbot, monkeypatch, capsys):
    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(janelas, "DialogoAcaoRobo", explode)
    resultado = {}
    t = threading.Thread(target=lambda: resultado.update(r=janelas.JanelaAcaoRobo(None, "e", "p")),
                         daemon=True)
    t.start()
    qtbot.waitUntil(lambda: "r" in resultado, timeout=3000)
    assert resultado["r"].escolha == "STOP"
    assert "boom" in capsys.readouterr().err


# --- JanelaRevisaoEdicao ------------------------------------------------------------

def test_revisao_edicao_mostra_a_fila_numerada(qt_interface, qtbot):
    j = janelas.JanelaRevisaoEdicao(None, _fila())
    qtbot.addWidget(j)
    assert j.isModal() and j.windowTitle() == "Revisão e Edição Manual"
    assert j.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert j.rotulo.text() == "Dê um DUPLO CLIQUE em uma linha para editar os códigos PMIB."
    assert [j.tree.headerItem().text(i) for i in range(4)] == [
        "ID", "Descrição", "PMIB Original (Ler Dados)", "PMIB Alvo (Escrever)"]
    assert [j.tree.topLevelItem(1).text(i) for i in range(4)] == [
        "2", "SELO MECANICO", "PMIB.002.1020", "PMIB.002.2020"]
    assert j.tree.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    j.botao_concluir.click()
    assert not j.isVisible()


def test_revisao_edicao_duplo_clique_edita_o_dict_da_fila(qt_interface, qtbot, avisos):
    fila = _fila()
    j = janelas.JanelaRevisaoEdicao(None, fila)
    qtbot.addWidget(j)
    _duplo_clique(qtbot, j.tree, 1)
    pop = j.popup
    assert pop.isVisible() and pop.isModal() and pop.windowTitle() == "Editar Item"
    assert pop.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert pop.entry_orig.text() == "PMIB.002.1020" and pop.entry_alvo.text() == "PMIB.002.2020"
    pop.entry_alvo.setText("   ")
    pop.botao_salvar.click()
    assert avisos == [("Aviso", "Os códigos não podem ficar vazios.")]
    assert pop.isVisible() and fila[1]["pmib_alvo"] == "PMIB.002.2020"
    pop.entry_orig.setText(" PMIB.009.9999 ")
    pop.entry_alvo.setText("PMIB.009.8888")
    pop.botao_salvar.click()
    assert not pop.isVisible()
    assert fila[1] == {"descricao": "SELO MECANICO", "pmib_original": "PMIB.009.9999",
                       "pmib_alvo": "PMIB.009.8888"}
    assert [j.tree.topLevelItem(1).text(i) for i in (2, 3)] == ["PMIB.009.9999", "PMIB.009.8888"]
    j.close()


def test_popup_de_edicao_esc_nao_joga_fora_o_que_foi_digitado(qt_interface, qtbot):
    """Revisão final: o Tk não tinha tecla aqui, e o Esc padrão do QDialog
    fechava o pop-up perdendo os códigos digitados."""
    j = janelas.JanelaRevisaoEdicao(None, _fila())
    qtbot.addWidget(j)
    _duplo_clique(qtbot, j.tree, 1)
    pop = j.popup
    pop.entry_alvo.setText("PMIB.009.8888")
    qtbot.keyClick(pop.entry_alvo, Qt.Key.Key_Escape)
    qtbot.keyClick(pop, Qt.Key.Key_Escape)
    assert pop.isVisible() and pop.entry_alvo.text() == "PMIB.009.8888"
    pop.close()
    j.close()


def test_revisao_edicao_duplo_clique_sem_selecao_nao_abre(qt_interface, qtbot):
    j = janelas.JanelaRevisaoEdicao(None, _fila())
    qtbot.addWidget(j)
    j.on_double_click()
    assert j.popup is None
    j.close()


# --- medidas (capturas interface antiga, Xvfb, `capturas/e3.2/ctk_medidas.json`) -----------------

def _geo(w, base):
    p = w.mapTo(base, w.rect().topLeft())
    return [p.x(), p.y(), w.width(), w.height()]


def _mostrar(qtbot, j, largura, altura):
    j.resize(largura, altura)
    j.show()
    qtbot.waitExposed(j)
    QApplication.processEvents()


def test_medidas_acao_robo(folha, qtbot):
    d = janelas.DialogoAcaoRobo(None, "erro", "PDM.A")
    qtbot.addWidget(d)
    _mostrar(qtbot, d, 500, 350)
    assert _geo(d.rotulo_erro, d)[1:4:2] == [15, 28]
    assert _geo(d.caixa_erro, d) == [20, 53, 460, 60]
    assert _geo(d.rotulo_pdm, d)[1] == 123
    assert _geo(d.botao_retry, d) == [20, 171, 460, 28]
    assert _geo(d.botao_pular, d) == [20, 209, 460, 28]
    assert _geo(d.botao_parar, d) == [20, 285, 460, 28]
    entrada, mudar = _geo(d.entry_pdm, d), _geo(d.botao_mudar, d)
    assert entrada[:2] == [20, 247] and entrada[3] == 28
    assert mudar[1] == 247 and mudar[0] + mudar[2] == 480 and mudar[3] == 28
    assert mudar[0] - (entrada[0] + entrada[2]) == 5
    assert mudar[2] >= 140
    d.botao_pular.click()


def test_medidas_escolher_pdm(folha, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    _mostrar(qtbot, j, 900, 560)
    assert _geo(j.rotulo, j)[:2] == [10, 10]
    assert _geo(j.entry_busca, j) == [10, 44, 880, 28]
    assert _geo(j.lista, j) == [10, 88, 880, 424]
    assert _geo(j.lbl_contagem, j)[:2] == [10, 522]
    assert _geo(j.botao_usar, j) == [595, 522, 140, 28]
    assert _geo(j.botao_cancelar, j) == [745, 522, 140, 28]
    j.close()


def test_medidas_revisao_pdm(folha, qtbot):
    # 1250x640 desde 2026-10-08 (coluna Confiança e o "por quê" sob a tabela).
    j, _ = _revisao(qtbot)
    assert (j.width(), j.height()) == (1250, 640)
    _mostrar(qtbot, j, 1250, 640)
    assert _geo(j.topo, j) == [10, 10, 1230, 28]
    assert _geo(j.rotulo, j)[:2] == [10, 10]
    confirmar, editar = _geo(j.botao_confirmar, j), _geo(j.botao_editar, j)
    assert confirmar[0] + confirmar[2] == 1235 and confirmar[1] == 10 and confirmar[3] == 28
    assert confirmar[0] - (editar[0] + editar[2]) == 10 and editar[3] == 28
    assert _geo(j.tree, j) == [10, 48, 1230, 544]
    assert _geo(j.lbl_porque, j) == [12, 602, 1226, 28]
    j.close()


def test_medidas_resumo(folha, qtbot):
    j = janelas.JanelaResumo(None, DfFalso([{"descricao_original": "X"}]))
    qtbot.addWidget(j)
    _mostrar(qtbot, j, 1000, 500)
    assert _geo(j.rotulo, j)[1:4:2] == [10, 28]
    assert _geo(j.tree, j) == [10, 58, 980, 384]
    assert _geo(j.botao_fechar, j) == [430, 462, 140, 28]
    j.close()


def test_medidas_revisao_edicao_e_popup(folha, qtbot):
    j = janelas.JanelaRevisaoEdicao(None, _fila())
    qtbot.addWidget(j)
    _mostrar(qtbot, j, 900, 500)
    assert _geo(j.rotulo, j)[1:4:2] == [10, 28]
    assert _geo(j.tree, j) == [20, 58, 860, 374]
    assert _geo(j.botao_concluir, j) == [380, 457, 140, 28]
    j.tree.topLevelItem(0).setSelected(True)
    j.on_double_click()
    pop = j.popup
    _mostrar(qtbot, pop, 400, 300)
    assert _geo(pop.rotulo_orig, pop) == [20, 15, 360, 28]
    assert _geo(pop.entry_orig, pop) == [20, 48, 360, 28]
    assert _geo(pop.rotulo_alvo, pop) == [20, 96, 360, 28]
    assert _geo(pop.entry_alvo, pop) == [20, 129, 360, 28]
    assert _geo(pop.botao_salvar, pop) == [130, 182, 140, 28]
    pop.close()
    j.close()


def test_cores_dos_botoes_do_interface_antiga(qt_interface, qtbot):
    d = janelas.DialogoAcaoRobo(None, "e", "p")
    qtbot.addWidget(d)
    assert "#B8860B" in d.botao_pular.styleSheet() and "#DAA520" in d.botao_pular.styleSheet()
    assert "#FF0000" in d.botao_parar.styleSheet() and "#8B0000" in d.botao_parar.styleSheet()
    assert "#FF0000" in d.rotulo_erro.styleSheet()
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    assert theme.COLORS["accent"] in j.botao_usar.styleSheet()
    assert "#3A3A3A" in j.botao_cancelar.styleSheet()
    j.close()
    r, _ = _revisao(qtbot)
    assert "#008000" in r.botao_confirmar.styleSheet()  # "green" do Tk
    r.close()


# --- correções da revisão (Esc, janela que some, peças compartilhadas) ---------------

def test_revisao_pdm_esc_nao_joga_fora_as_edicoes(qt_interface, qtbot, monkeypatch):
    # Esc fechava pelo reject() padrão: as edições sumiam e ninguém era chamado
    # (a tela ficava com o "Analisar" desligado para sempre).
    monkeypatch.setattr(janelas.QInputDialog, "getText", staticmethod(lambda *a, **k: ("PDM.N - N", True)))
    j, _ = _revisao(qtbot)
    j.tree.topLevelItem(0).setSelected(True)
    j.botao_editar.click()
    qtbot.keyClick(j, Qt.Key.Key_Escape)
    qtbot.keyClick(j.tree, Qt.Key.Key_Escape)
    assert j.isVisible()
    assert j.df_dados.at[0, "pdm_escolhido"] == "PDM.N - N"
    j.close()


def _robo_no_worker(qtbot):
    resultado = {}
    t = threading.Thread(target=lambda: resultado.update(r=janelas.JanelaAcaoRobo(None, "e", "p")),
                         daemon=True)
    t.start()

    def aberta():
        return [w for w in QApplication.topLevelWidgets()
                if isinstance(w, janelas.DialogoAcaoRobo) and w.isVisible()]

    qtbot.waitUntil(lambda: bool(aberta()), timeout=3000)
    return aberta()[0], resultado


def test_acao_robo_escondida_sem_decisao_solta_o_worker_com_stop(qt_interface, qtbot):
    d, resultado = _robo_no_worker(qtbot)
    d.hide()
    qtbot.waitUntil(lambda: "r" in resultado, timeout=3000)
    assert resultado["r"] == janelas.DecisaoRobo("STOP", None)


def test_acao_robo_destruida_solta_o_worker_com_stop(qt_interface, qtbot):
    d, resultado = _robo_no_worker(qtbot)
    d.ao_sumir = None  # só o `destroyed` sobra: é ele que tem de soltar
    d.blockSignals(False)
    d.deleteLater()
    qtbot.waitUntil(lambda: "r" in resultado, timeout=3000)
    assert resultado["r"].escolha == "STOP"


def test_acao_robo_decisao_vale_mesmo_com_o_hide_depois(qt_interface, qtbot):
    d, resultado = _robo_no_worker(qtbot)
    d.botao_retry.click()
    qtbot.waitUntil(lambda: "r" in resultado, timeout=3000)
    assert resultado["r"].escolha == "RETRY"


def test_escolher_pdm_esperar_volta_se_escondida(qt_interface, qtbot):
    j = janelas.JanelaEscolherPDM(None, _catalogo())
    qtbot.addWidget(j)
    QTimer.singleShot(0, j.hide)
    assert j.esperar() is None


def test_tabela_ttk_compartilhada(qt_interface, qtbot):
    tree = dialogos_selecao.tabela_ttk([("A", 50, "w"), ("B", 80, "center")], selecao="browse",
                                       barra_horizontal=False)
    qtbot.addWidget(tree)
    item = dialogos_selecao.linha_ttk(tree, [1, "x"], chave=7)
    assert tree.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    assert tree.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert tree.textElideMode() == Qt.TextElideMode.ElideNone
    assert item.data(0, Qt.ItemDataRole.UserRole) == 7
    assert item.textAlignment(1) & Qt.AlignmentFlag.AlignHCenter
    assert isinstance(tree.esticar_colunas, dialogos_selecao.EsticaColunas)

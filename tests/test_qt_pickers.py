from sigft.app_qt.widgets import pickers


def test_arquivo_escolhido_fica_verde_e_avisa(qt_interface, qtbot):
    avisos = []
    linha = pickers.FilePickerRow(chave="k", categoria="excel", texto_botao="Selecionar",
                                  ao_escolher=avisos.append,
                                  dialog_fn=lambda **k: "/tmp/pasta/STATUS.xlsx")
    qtbot.addWidget(linha)
    assert linha.label_status.text() == pickers.TEXTO_SEM_ARQUIVO
    linha.botao.click()
    assert linha.valor == "/tmp/pasta/STATUS.xlsx"
    assert linha.label_status.text() == "STATUS.xlsx"
    # 2026-10-20: o verde é o papel `ok` da folha do tema, não uma cor no rótulo.
    assert linha.label_status.property("papel") == "ok"
    assert linha.botao.property("variante") == "primario"
    assert avisos == ["/tmp/pasta/STATUS.xlsx"]


def test_cancelar_nao_apaga_o_que_ja_estava(qt_interface, qtbot):
    respostas = iter(["/tmp/a.xlsx", ""])
    linha = pickers.FilePickerRow(chave="k", categoria="excel", texto_botao="S",
                                  dialog_fn=lambda **k: next(respostas))
    qtbot.addWidget(linha)
    linha.botao.click()
    linha.botao.click()
    assert linha.valor == "/tmp/a.xlsx"


def test_varios_e_pasta(qt_interface, qtbot):
    varios = pickers.MultiFilePickerRow(chave="k", categoria="excel", texto_botao="S",
                                        dialog_fn=lambda **k: ("/a.xlsx", "/b.xlsx"))
    pasta = pickers.FolderPickerRow(chave="k", texto_botao="S", dialog_fn=lambda **k: "/x/y/")
    for w in (varios, pasta):
        qtbot.addWidget(w)
        w.botao.click()
    assert varios.label_status.text() == "2 arquivos selecionados"
    assert pasta.label_status.text() == "/x/y/"


def test_limpar_volta_ao_cinza(qt_interface, qtbot):
    linha = pickers.FilePickerRow(chave="k", categoria="excel", texto_botao="S",
                                  texto_vazio="Nenhum", dialog_fn=lambda **k: "/a.xlsx")
    qtbot.addWidget(linha)
    linha.botao.click()
    linha.limpar()
    assert linha.valor is None and linha.label_status.text() == "Nenhum"


def test_medidas_iguais_as_do_interface_antiga(qt_interface, qtbot):
    # Lá: botão `pack(side="left")` e rótulo `pack(side="left", padx=15)` --
    # 15 px dos DOIS lados do rótulo, nada além disso; rótulo na fonte padrão
    # do CTkLabel (Roboto 13), nos dois estados.
    linha = pickers.FilePickerRow(chave="k", categoria="excel", texto_botao="S",
                                  largura_botao=220, dialog_fn=lambda **k: "/tmp/a.xlsx")
    qtbot.addWidget(linha)
    linha.show()
    qtbot.waitExposed(linha)
    rotulo = linha.label_status
    assert "font-size: 13px" in rotulo.styleSheet()
    assert rotulo.x() - (linha.botao.x() + linha.botao.width()) == 15
    assert linha.sizeHint().width() == 220 + 15 + rotulo.sizeHint().width() + 15
    linha.botao.click()
    assert "font-size: 13px" in rotulo.styleSheet()


def test_nome_longo_e_elidido_com_o_caminho_no_tooltip(qt_interface, qtbot):
    nome = ("Lista de PDMs SAM-GM revisao final aprovada pelo cliente em setembro de 2026 "
            "- versao definitiva para fatiamento geral.xlsx")
    linha = pickers.FilePickerRow(chave="k", categoria="excel", texto_botao="S",
                                  dialog_fn=lambda **k: "/tmp/" + nome)
    qtbot.addWidget(linha)
    minima = linha.minimumSizeHint().width()
    linha.botao.click()
    assert linha.minimumSizeHint().width() <= minima, "o nome longo alargava a linha"
    assert linha.label_status.text() == nome and linha.label_status.toolTip() == "/tmp/" + nome
    linha.limpar()
    assert linha.label_status.toolTip() == ""
    varios = pickers.MultiFilePickerRow(chave="k", categoria="excel", texto_botao="S",
                                        dialog_fn=lambda **k: ("/a.xlsx", "/b.xlsx"))
    qtbot.addWidget(varios)
    varios.botao.click()
    assert varios.label_status.toolTip() == "/a.xlsx\n/b.xlsx"


# =============================================================================
# Portados de `tests/test_app_pickers.py` (os seletores da interface antiga,
# que saiu em 2026-10-15): o contrato que só lá estava provado.
# =============================================================================

def _dialogo_que_devolve(valor, registro=None):
    """Dublê de diálogo: devolve `valor` e anota os kwargs recebidos."""
    def _dialogo(**kwargs):
        if registro is not None:
            registro.append(kwargs)
        return valor
    return _dialogo


def test_comeca_vazio_e_cinza(qt_interface, qtbot):
    linha = pickers.FilePickerRow(chave="x.y", categoria="excel", texto_botao="Selecionar")
    qtbot.addWidget(linha)
    assert linha.valor is None
    assert linha.label_status.text() == pickers.TEXTO_SEM_ARQUIVO
    # 2026-10-20: o cinza é o papel `legenda` da folha; o botão, o secundário.
    assert linha.label_status.property("papel") == "legenda"
    assert linha.botao.property("variante") == "secundario"


def test_callback_nao_dispara_quando_o_usuario_cancela(qt_interface, qtbot):
    recebidos = []
    linha = pickers.FilePickerRow(chave="x.y", categoria="excel", texto_botao="S",
                                  ao_escolher=recebidos.append, dialog_fn=_dialogo_que_devolve(""))
    qtbot.addWidget(linha)
    linha.botao.click()
    assert recebidos == [] and linha.valor is None


def test_a_chave_declarada_chega_ao_file_dialogs(qt_interface, qtbot, monkeypatch):
    """A tela declara chave/categoria uma vez; o seletor cuida do resto."""
    chamadas = []

    def espiao(chave, categoria, **kwargs):
        chamadas.append((chave, categoria))
        return ""

    monkeypatch.setattr(pickers.file_dialogs, "ask_open_file", espiao)
    linha = pickers.FilePickerRow(chave="pdm.template", categoria="excel", texto_botao="S")
    qtbot.addWidget(linha)
    linha.botao.click()
    assert chamadas == [("pdm.template", "excel")]


def test_a_pasta_escolhida_fica_memorizada_para_a_proxima_vez(qt_interface, qtbot, tmp_path):
    """O ganho do CP 1.5, automático: escolher um arquivo em `fichas/` faz o
    PRÓXIMO diálogo da mesma chave abrir em `fichas/`, sem a tela pedir nada.
    (O `user_prefs.json` cai na pasta de dados isolada pelo conftest.)"""
    pasta = tmp_path / "fichas"
    pasta.mkdir()
    arquivo = pasta / "ficha.xlsx"
    arquivo.write_text("x", encoding="utf-8")
    recebidos = []
    linha = pickers.FilePickerRow(chave="autospec.ficha", categoria="excel", texto_botao="S",
                                  dialog_fn=_dialogo_que_devolve(str(arquivo), recebidos))
    qtbot.addWidget(linha)
    linha.botao.click()
    linha.botao.click()
    assert recebidos[1]["initialdir"] == str(pasta)


def test_cada_categoria_lembra_a_propria_pasta(qt_interface, qtbot, tmp_path):
    """No AutoSpec, o seletor de ficha abre na pasta do último Excel e o de
    manuais na do último PDF -- sem vai-e-vem entre pastas."""
    pasta_excel, pasta_pdf = tmp_path / "planilhas", tmp_path / "manuais"
    pasta_excel.mkdir()
    pasta_pdf.mkdir()
    reg_excel, reg_pdf = [], []
    excel = pickers.FilePickerRow(chave="autospec.ficha", categoria="excel", texto_botao="F",
                                  dialog_fn=_dialogo_que_devolve(str(pasta_excel / "f.xlsx"), reg_excel))
    pdf = pickers.MultiFilePickerRow(chave="autospec.manuais", categoria="pdf", texto_botao="M",
                                     dialog_fn=_dialogo_que_devolve((str(pasta_pdf / "m.pdf"),), reg_pdf))
    for w in (excel, pdf):
        qtbot.addWidget(w)
    excel.botao.click()
    pdf.botao.click()
    excel.botao.click()
    pdf.botao.click()
    assert reg_excel[1]["initialdir"] == str(pasta_excel)
    assert reg_pdf[1]["initialdir"] == str(pasta_pdf)


def test_varios_cancelado_nao_apaga(qt_interface, qtbot):
    respostas = iter([("/a/f.xlsx",), ()])
    linha = pickers.MultiFilePickerRow(chave="x.y", categoria="excel", texto_botao="S",
                                       dialog_fn=lambda **k: next(respostas))
    qtbot.addWidget(linha)
    linha.botao.click()
    linha.botao.click()
    assert linha.valor == ("/a/f.xlsx",)


def test_pasta_mostra_o_nome_da_pasta_e_comeca_com_o_texto_de_pasta_vazia(qt_interface, qtbot):
    linha = pickers.FolderPickerRow(chave="analyzer.saida", texto_botao="Pasta",
                                    dialog_fn=_dialogo_que_devolve("/dados/saida"))
    qtbot.addWidget(linha)
    assert linha.label_status.text() == pickers.TEXTO_SEM_PASTA
    linha.botao.click()
    assert linha.label_status.text() == "saida"

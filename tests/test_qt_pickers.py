from sigft.app import theme
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
    assert theme.COLORS["accent"] in linha.label_status.styleSheet()
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

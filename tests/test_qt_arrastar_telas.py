"""Soltar o arquivo no botão de cada tela chega ao `selecionar_...` dela (2026-10-21).

Cada tela declara `ARRASTAVEIS`; o `ModuleFrame` liga o `Receptor` ao botão. O
soltar ENTREGA o arquivo à chave do diálogo e clica o botão: o `ask_open_file`
da tela acha a entrega e não abre o diálogo. Aqui o diálogo é trocado por um
falso que anota a chave pedida e a entrega pendente nela.
"""
import pytest

from sigft.app_qt import file_dialogs
from sigft.app_qt import main as qmain
from sigft.app_qt.views import (
    autospec, copia_fichas, correcao_pdm, cria_fichas, lmr, pdm, pmib_manager, translator,
    upload_conditions, upload_tech_specs,
)

# (tela em main.TELAS, botão, chave do diálogo, função de diálogo, uma extensão aceita)
CASOS = [
    ("AutoSpec", "btn_status", "autospec.status_pmib", "ask_open_file", ".xlsx"),
    ("AutoSpec", "btn_sheet", "autospec.ficha", "ask_open_file", ".xlsx"),
    ("AutoSpec", "btn_refs", "autospec.manuais", "ask_open_files", ".pdf"),
    ("AutoSpec", "btn_conf_importar", "autospec.conferencia", "ask_open_file", ".txt"),
    ("CopiaFichas", "btn_status", "copia_fichas.status_pmib", "ask_open_file", ".xlsm"),
    ("CorrecaoPDM", "btn_status", "correcao_pdm.status_pmib", "ask_open_file", ".xlsx"),
    ("CorrecaoPDM", "btn_catalogo", "correcao_pdm.sam_gm", "ask_open_file", ".xlsx"),
    ("CriaFichas", "btn_pmib", "cria_fichas.excel_pmib", "ask_open_file", ".xlsx"),
    ("CriaFichas", "btn_pdm", "cria_fichas.excel_pdm", "ask_open_file", ".xls"),
    ("CriaFichas", "btn_excel_edicao", "cria_fichas.excel_edicao", "ask_open_file", ".xlsx"),
    ("PDM", "btn_sam_gm", "pdm.sam_gm", "ask_open_file", ".xlsx"),
    ("PDM", "btn_pmib", "pdm.status_pmib", "ask_open_file", ".xlsx"),
    ("PDM", "btn_template", "pdm.template", "ask_open_file", ".xls"),
    ("PMIBManager", "btn_api", "pmib_manager.api", "ask_open_file", ".xlsx"),
    ("PMIBManager", "btn_master", "pmib_manager.master", "ask_open_file", ".xlsx"),
    ("PMIBManager", "btn_autorizados", "pmib_manager.autorizados", "ask_open_file", ".xlsx"),
    ("UploadConditions", "btn_status", "upload_conditions.status_pmib", "ask_open_file", ".xlsm"),
    ("UploadSpecs", "btn_status", "upload_tech_specs.status_pmib", "ask_open_file", ".xlsx"),
    ("UploadSpecs", "btn_master", "upload_tech_specs.master", "ask_open_file", ".xlsm"),
]

CLASSES = {
    "AutoSpec": autospec.ModuloAutoSpec, "CopiaFichas": copia_fichas.ModuloCopiaFichas,
    "CorrecaoPDM": correcao_pdm.ModuloCorrecaoPDM, "CriaFichas": cria_fichas.ModuloCriaFichas,
    "PDM": pdm.ModuloPDM, "PMIBManager": pmib_manager.ModuloPMIBManager,
    "UploadConditions": upload_conditions.ModuloUploadConditions,
    "UploadSpecs": upload_tech_specs.ModuloUploadTechSpecs,
}


@pytest.mark.parametrize("tela_chave, atributo, chave, funcao, extensao", CASOS)
def test_soltar_no_botao_chega_ao_selecionar_da_tela(qt_interface, qtbot, monkeypatch, tmp_path,
                                                    tela_chave, atributo, chave, funcao, extensao):
    arquivo = tmp_path / f"arquivo{extensao}"
    arquivo.write_text("x", encoding="utf-8")
    pedidos = []

    def falso(chave_pedida, _categoria, **_kwargs):
        pedidos.append((chave_pedida, file_dialogs.pendente(chave_pedida)))
        return () if funcao == "ask_open_files" else ""   # "cancelou": a tela para ali

    monkeypatch.setattr(file_dialogs, funcao, falso)
    tela = qmain.TELAS[tela_chave](None, None)
    qtbot.addWidget(tela)
    monkeypatch.setattr(tela, "backend", lambda _nome: object())
    getattr(tela, atributo).setEnabled(True)
    receptor = tela.receptores_de_arquivo[atributo]
    assert receptor.aceita([str(arquivo)])
    receptor.receber([str(arquivo)])
    assert pedidos == [(chave, (str(arquivo),))]
    # A entrega não sobra para o próximo clique.
    assert file_dialogs.pendente(chave) is None


def test_casos_cobrem_todo_arrastavel_declarado():
    declarados = {(t, a.atributo, a.chave) for t, classe in CLASSES.items() for a in classe.ARRASTAVEIS}
    assert declarados == {(t, atributo, chave) for t, atributo, chave, _f, _e in CASOS}


def test_botao_que_inicia_robo_nao_aceita_arrasto():
    # O "Iniciar" do Tradutor e da LMR abre o diálogo e já sobe o robô: soltar
    # um arquivo ali começaria um lote sem a pessoa pedir.
    assert translator.ModuloTranslator.ARRASTAVEIS == ()
    assert lmr.ModuloLMR.ARRASTAVEIS == ()

"""A IA por módulo na tela: o painel, a janela da tela e o botão "Configurar IA" (2026-11-04)."""
from __future__ import annotations

import json

import pytest

from sigft import config
from sigft.core.llm import modo, selecao
from sigft.app_qt.widgets import ia_do_modulo


class _Controller:
    def __init__(self, chaves=None):
        self.api_keys = dict(chaves or {})
        self.gravadas = []

    def get_key(self, nome):
        return self.api_keys.get(nome) or ""

    def save_keys(self, novas):
        self.gravadas.append(dict(novas))
        self.api_keys.update(novas)


@pytest.fixture
def arquivo(tmp_path, monkeypatch):
    caminho = tmp_path / "api_config.json"
    caminho.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))
    return caminho


def _painel(qtbot, tarefas, controller=None):
    painel = ia_do_modulo.PainelIaDoModulo(controller or _Controller({"OPENROUTER": "sk"}), tarefas)
    qtbot.addWidget(painel)
    return painel


def test_tres_modos_e_a_interna_desligada(qtbot, arquivo):
    painel = _painel(qtbot, ("condicoes",))
    assert set(painel.botoes_modo) == {modo.EXTERNA, modo.INTERNA, modo.WORKFLOW}
    assert not painel.botoes_modo[modo.INTERNA].isEnabled()
    assert painel.botoes_modo[modo.INTERNA].toolTip()
    assert painel.lista_modulos is None   # uma tarefa só: sem a lista dos módulos
    assert painel.modo == modo.EXTERNA


def test_central_lista_todos_os_modulos_e_troca_ao_clicar(qtbot, arquivo):
    painel = _painel(qtbot, config.TAREFAS_DO_PAINEL)
    assert painel.lista_modulos.count() == len(config.TAREFAS_DO_PAINEL)
    painel.lista_modulos.setCurrentRow(config.TAREFAS_DO_PAINEL.index("tech_specs"))
    assert painel.tarefa == "tech_specs"


def test_workflow_grava_o_webhook_do_modulo_e_o_modo(qtbot, arquivo):
    controller = _Controller()
    painel = _painel(qtbot, ("condicoes",), controller)
    painel.botoes_modo[modo.WORKFLOW].click()
    painel.campo_url.setText("https://amp.ge/webhook/condicoes")
    painel.campo_chave.setText("segredo")
    assert painel.salvar()
    assert controller.gravadas == [{"AMP_IA_CONDICOES_URL": "https://amp.ge/webhook/condicoes",
                                    "AMP_IA_CONDICOES_CHAVE": "segredo"}]
    assert modo.modo_da_tarefa("condicoes", config_path=arquivo) == modo.WORKFLOW


def test_workflow_recusa_endereco_de_teste(qtbot, arquivo):
    painel = _painel(qtbot, ("condicoes",))
    painel.botoes_modo[modo.WORKFLOW].click()
    painel.campo_url.setText("https://amp.ge/webhook-test/x")
    assert not painel.salvar()
    assert modo.modo_da_tarefa("condicoes", config_path=arquivo) == modo.EXTERNA


def test_externa_grava_o_modelo_escolhido_no_openrouter(qtbot, arquivo):
    painel = _painel(qtbot, ("validar_ficha",))
    assert painel.lista_modelos.count() > 0   # os favoritos curados, mesmo sem catálogo
    painel.lista_modelos.setCurrentRow(0)
    escolhido = painel.modelo_escolhido()
    assert painel.salvar()
    assert selecao.resolver("validar_ficha", config_path=arquivo) == {
        "provider": config.PROVIDER_OPENROUTER, "model": escolhido}


def test_externa_sem_modelo_nao_grava(qtbot, arquivo):
    painel = _painel(qtbot, ("validar_ficha",))
    painel.lista_modelos.setCurrentRow(-1)
    assert not painel.salvar()


def test_filtro_esconde_o_que_nao_casa(qtbot, arquivo):
    painel = _painel(qtbot, ("validar_ficha",))
    painel.campo_filtro.setText("zzz-nao-existe")
    assert painel.lista_modelos.count() == 0


def test_a_central_e_a_da_tela_ficam_iguais(qtbot, arquivo):
    """Uma grava, a outra (aberta) se redesenha: a fonte é uma só."""
    central = _painel(qtbot, config.TAREFAS_DO_PAINEL)
    central.selecionar_tarefa("condicoes")
    da_tela = _painel(qtbot, ("condicoes",))
    da_tela.botoes_modo[modo.WORKFLOW].click()
    da_tela.campo_url.setText("https://amp.ge/webhook/c")
    assert da_tela.salvar()
    assert central.modo == modo.WORKFLOW


def test_abre_mostrando_o_que_ja_vale(qtbot, arquivo):
    modo.definir_workflow("tech_specs", config_path=arquivo)
    painel = _painel(qtbot, ("tech_specs",), _Controller({"AMP_IA_TECH_SPECS_URL": "https://x/webhook/t"}))
    assert painel.modo == modo.WORKFLOW
    assert painel.campo_url.text() == "https://x/webhook/t"


def test_botao_configurar_ia_na_tela_abre_a_janela_do_modulo(qtbot, arquivo, qt_interface):
    from sigft.app_qt.views.analyzer import ModuloAnalyzer

    tela = ModuloAnalyzer(None, _Controller())
    qtbot.addWidget(tela)
    assert tela.botao_configurar_ia.text() == "Configurar IA"
    tela.botao_configurar_ia.click()
    janela = tela.janela_configurar_ia
    qtbot.addWidget(janela)
    assert janela.painel.tarefas == ("validar_ficha",)
    janela.close()


def test_telas_com_ia_tem_o_botao():
    from sigft.app import ia_por_modulo

    for tarefas in ia_por_modulo.TAREFAS_DA_TELA.values():
        assert tarefas and all(tarefa in config.TAREFAS_DO_PAINEL for tarefa in tarefas)
    assert ia_por_modulo.TAREFAS_DA_TELA["ModuloAutoSpec"] == ("autospec",)


def test_autospec_tem_o_botao_e_configura_a_tarefa_dele(qtbot, arquivo, qt_interface):
    """2026-11-05, pedido do Luan: a tela do AutoSpec tem o "Configurar IA" como as outras."""
    from sigft.app_qt.views.autospec import ModuloAutoSpec

    tela = ModuloAutoSpec(None, _Controller())
    qtbot.addWidget(tela)
    assert tela.botao_configurar_ia.text() == "Configurar IA"
    tela.botao_configurar_ia.click()
    janela = tela.janela_configurar_ia
    qtbot.addWidget(janela)
    assert janela.painel.tarefas == ("autospec",)
    janela.close()


def test_docpack_tem_o_botao_na_secao_e_configura_a_sugestao_de_pasta(qtbot, arquivo, qt_interface):
    """O DocPack é uma seção de abas (telas embutidas, sem cabeçalho): o botão fica no
    cabeçalho da seção e configura a tarefa da Etapa 1 (a sugestão de pasta)."""
    from sigft.app_qt.views.docpack_secao import ModuloDocPackSecao

    secao = ModuloDocPackSecao(None, _Controller())
    qtbot.addWidget(secao)
    assert secao.botao_configurar_ia.text() == "Configurar IA"
    secao.botao_configurar_ia.click()
    janela = secao.janela_configurar_ia
    qtbot.addWidget(janela)
    assert janela.painel.tarefas == ("docpack_pasta",)
    janela.close()

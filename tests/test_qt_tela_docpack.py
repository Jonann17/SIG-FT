"""A aba "DocPack" do PMIB Manager (Qt). O serviço é dublê: as regras têm os testes delas em
`test_docpack.py`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from sigft.app_qt.views import docpack as tela_mod
from sigft.services import conferencia_revisoes as cr
from sigft.services import docpack as svc

CODIGO = "#ST00=M00MEU10&MPB020"
OUTRO = "#ST00=OUTRO&MPB020"


def _lista(codigo, titulo="LISTA DE SOBRESSALENTES - GERADOR DIESEL"):
    return cr.ListaNaMapeadora(codigo, "0B", "", "", "0A", None, descricao=titulo)


def _tela(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(tela_mod.prefs, "get_last_file", lambda chave: None)
    monkeypatch.setattr(tela_mod.prefs, "ultima_pasta", lambda chave: None)
    monkeypatch.setattr(tela_mod.prefs, "get_default_dir", lambda nome: None)
    tela = tela_mod.ModuloDocPack()
    qtbot.addWidget(tela)
    tela.pasta_raiz = str(tmp_path)
    tela.templates = svc.Templates(str(tmp_path / "status.xlsx"))
    return tela


def _mostrar(tela):
    tela._mostrar_listas([_lista(CODIGO), _lista(OUTRO)],
                         {"03 - EBOP": {"CAP 03": {"GERADOR DIESEL": {}, "UPS": {}}}, "05 - UG": {}})


def _rodar_no_mesmo_fio(tela, monkeypatch):
    monkeypatch.setattr(tela, "iniciar_tarefa", lambda alvo, *args, botao=None: alvo(*args))
    monkeypatch.setattr(tela_mod.interface, "na_interface", lambda f, *a: f(*a))


def test_tabela_mostra_as_listas_desmarcadas(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    assert tela.tabela.topLevelItemCount() == 2
    item = tela.tabela.topLevelItem(0)
    assert (item.text(0), item.text(1)) == (CODIGO, "LISTA DE SOBRESSALENTES - GERADOR DIESEL")
    assert item.checkState(0) == Qt.CheckState.Unchecked
    assert tela.lbl_totais.text() == "2 lista(s) sem _STATUS_PMIB"
    assert tela.marcadas() == []


def test_colunas_seguem_a_hierarquia_da_et():
    nomes = [nome for nome, _ in tela_mod.COLUNAS]
    assert nomes[2:] == ["ET", "Capítulo", "Sistema", "Subsistema", "Pasta final"]
    assert sum(largura for _, largura in tela_mod.COLUNAS) == 850


def test_sugestoes_de_pasta_seguem_as_pastas_da_esquerda(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    assert tela.sugestoes_para(0, tela_mod.COL_ET) == ["03 - EBOP", "05 - UG"]
    assert tela.sugestoes_para(0, tela_mod.COL_CAPITULO) == []
    item = tela.tabela.topLevelItem(0)
    item.setText(tela_mod.COL_ET, "03 - EBOP")
    assert tela.sugestoes_para(0, tela_mod.COL_CAPITULO) == ["CAP 03"]
    item.setText(tela_mod.COL_CAPITULO, "CAP 03")
    # O sistema vazio é pulado: o subsistema vem das pastas do capítulo.
    assert tela.sugestoes_para(0, tela_mod.COL_SUBSISTEMA) == ["GERADOR DIESEL", "UPS"]
    assert tela.sugestoes_para(1, tela_mod.COL_SUBSISTEMA) == []


def test_so_as_colunas_de_pasta_se_editam(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    delegado = tela.tabela.itemDelegate()
    modelo = tela.tabela.model()
    assert delegado.createEditor(tela.tabela.viewport(), None, modelo.index(0, 0)) is None
    campo = delegado.createEditor(tela.tabela.viewport(), None, modelo.index(0, tela_mod.COL_ET))
    assert campo is not None and campo.completer() is not None and campo.isEditable()
    assert [campo.itemText(i) for i in range(campo.count())] == ["03 - EBOP", "05 - UG"]
    # O nome digitado (pasta nova) vale, sem espaço sobrando.
    campo.setEditText("  09 -  NOVA ")
    delegado.setModelData(campo, modelo, modelo.index(0, tela_mod.COL_ET))
    assert tela.tabela.topLevelItem(0).text(tela_mod.COL_ET) == "09 - NOVA"
    delegado.setEditorData(campo, modelo.index(0, tela_mod.COL_ET))
    assert campo.currentText() == "09 - NOVA"


def test_marcadas_leva_o_destino_da_linha(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    item = tela.tabela.topLevelItem(1)
    item.setCheckState(0, Qt.CheckState.Checked)
    for coluna, valor in ((2, "03 - EBOP"), (3, "CAP 03"), (5, "UPS/BATERIAS")):
        item.setText(coluna, valor)
    assert tela.marcadas() == [(1, svc.Destino(et="03 - EBOP", capitulo="CAP 03", subsistema="UPS/BATERIAS"))]


def test_criar_sem_nada_marcado_avisa(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    avisos = []
    monkeypatch.setattr(tela, "avisar", lambda titulo, msg, tipo="info", **_: avisos.append(msg))
    tela._criar()
    assert avisos == ["Marque pelo menos uma lista."]


def test_criar_sem_template_avisa(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    tela.templates = svc.Templates()
    avisos = []
    monkeypatch.setattr(tela, "avisar", lambda titulo, msg, tipo="info", **_: avisos.append(msg))
    tela._criar()
    assert avisos == ["Selecione o template do _STATUS_PMIB antes."]


def test_criar_mostra_o_plano_pergunta_e_chama_o_servico(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    _rodar_no_mesmo_fio(tela, monkeypatch)
    item = tela.tabela.topLevelItem(0)
    item.setCheckState(0, Qt.CheckState.Checked)
    item.setText(tela_mod.COL_ET, "03 - EBOP")
    item.setText(tela_mod.COL_SUBSISTEMA, "GERADOR DIESEL")
    linhas, chamadas, perguntas = [], [], []
    monkeypatch.setattr(tela, "log", lambda msg, *a, **k: linhas.append(str(msg)))
    monkeypatch.setattr(tela, "perguntar_sim_nao", lambda titulo, msg, **_: perguntas.append(msg) or True)
    monkeypatch.setattr(tela_mod.docpack_svc, "criar_dossies",
                        lambda pedidos, raiz, templates, **kw: chamadas.append((pedidos, raiz, templates)))
    tela._criar()
    assert perguntas == [f"Criar 1 dossiê(s) em {tmp_path}?"]
    pedidos, raiz, templates = chamadas[0]
    assert [(lista.codigo, destino) for lista, destino in pedidos] == [
        (CODIGO, svc.Destino(et="03 - EBOP", subsistema="GERADOR DIESEL"))]
    assert str(raiz) == str(tmp_path) and templates.status_pmib.endswith("status.xlsx")
    assert any("+ 03 - EBOP/GERADOR DIESEL" in linha.replace("\\", "/") for linha in linhas)
    # A prévia não cria nada no disco.
    assert not (tmp_path / "03 - EBOP").exists()


def test_criar_respondendo_nao_nao_cria(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    _rodar_no_mesmo_fio(tela, monkeypatch)
    item = tela.tabela.topLevelItem(0)
    item.setCheckState(0, Qt.CheckState.Checked)
    item.setText(2, "03 - EBOP")
    item.setText(4, "X")
    chamadas = []
    monkeypatch.setattr(tela, "perguntar_sim_nao", lambda *a, **k: False)
    monkeypatch.setattr(tela_mod.docpack_svc, "criar_dossies", lambda *a, **k: chamadas.append(a))
    tela._criar()
    assert chamadas == []


def test_destino_invalido_nao_pergunta(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    _rodar_no_mesmo_fio(tela, monkeypatch)
    tela.tabela.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)   # sem capítulo nem pasta
    perguntas = []
    monkeypatch.setattr(tela, "perguntar_sim_nao", lambda *a, **k: perguntas.append(a) or True)
    tela._criar()
    assert perguntas == []


def test_sugestao_da_ia_preenche_a_linha(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _mostrar(tela)
    _rodar_no_mesmo_fio(tela, monkeypatch)
    tela.tabela.topLevelItem(1).setCheckState(0, Qt.CheckState.Checked)
    monkeypatch.setattr(tela, "_cliente_ia", lambda: object())
    monkeypatch.setattr(tela_mod.docpack_svc, "sugerir_destino",
                        lambda lista, existentes, llm, **_kw: (svc.Destino(et="03 - EBOP", capitulo="CAP 03",
                                                                     subsistema="UPS"), "porque sim"))
    tela._sugerir()
    item = tela.tabela.topLevelItem(1)
    assert [item.text(c) for c in tela_mod.EDITAVEIS] == ["03 - EBOP", "CAP 03", "", "UPS", ""]
    assert item.toolTip(tela_mod.COL_SUBSISTEMA) == "porque sim"
    assert tela.tabela.topLevelItem(0).text(2) == ""


def test_listar_le_a_mapeadora_e_mostra(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _rodar_no_mesmo_fio(tela, monkeypatch)
    tela.caminho_mapeadora = str(tmp_path / "m.xlsx")
    mapeadora = cr.Mapeadora(tmp_path / "m.xlsx", None, [_lista(CODIGO)])
    monkeypatch.setattr(tela_mod.conferencia_svc, "ler_mapeadora", lambda caminho: mapeadora)
    monkeypatch.setattr(tela_mod.docpack_svc, "listas_sem_status_pmib", lambda m, raiz, **_kw: m.listas)
    monkeypatch.setattr(tela_mod.docpack_svc, "arvore_existente", lambda raiz: {"03 - EBOP": {}})
    tela._listar()
    assert tela.tabela.topLevelItemCount() == 1
    assert tela.existentes == {"03 - EBOP": {}}


def test_listar_deixa_de_fora_a_lista_que_ainda_nao_saiu_no_aconex(qt_interface, qtbot, tmp_path, monkeypatch):
    """2026-11-09, pedido do Luan: a lista que ainda não saiu no Aconex não entra na tabela, o total
    diz quantas ficaram de fora e o console diz quais, e por quê. 2026-11-10: a cancelada também."""
    emitida = cr.ListaNaMapeadora(CODIGO, "0B", "Em Processo", "Aprovado", "", None, descricao="A")
    nao_emitida = cr.ListaNaMapeadora(OUTRO, "0A", "Para Análise", "NÃO EMITIDO", "", None, descricao="B")
    cancelada = cr.ListaNaMapeadora("#ST00=CANC&MPB020", "0", "Cancelado", "Cancelado", "", None, descricao="C")
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _rodar_no_mesmo_fio(tela, monkeypatch)
    tela.caminho_mapeadora = str(tmp_path / "m.xlsx")
    monkeypatch.setattr(tela_mod.conferencia_svc, "ler_mapeadora",
                        lambda caminho: cr.Mapeadora(tmp_path / "m.xlsx", None, [emitida, nao_emitida, cancelada]))
    linhas = []
    monkeypatch.setattr(tela, "log", lambda msg, *a, **k: linhas.append(str(msg)))
    tela._listar()
    assert [lista.codigo for lista in tela.listas] == [CODIGO]
    assert tela.lbl_totais.text().startswith("1 lista(s) sem _STATUS_PMIB")
    assert "2 não emitida(s) ou cancelada(s) no Aconex" in tela.lbl_totais.text()
    assert any(OUTRO in linha and "NÃO EMITIDO" in linha for linha in linhas)
    assert any("#ST00=CANC&MPB020" in linha and "Cancelado" in linha for linha in linhas)


def test_listar_e_sugerir_levam_as_vizinhas_e_o_mapa_a_ia(qt_interface, qtbot, tmp_path, monkeypatch):
    """2026-11-09: o Listar calcula as listas vizinhas e o mapa da organização, com UM levantamento da
    raiz, e a sugestão da IA recebe os dois. Raiz de verdade: a lista A já tem dossiê."""
    dossie = tmp_path / "03 - EBOP" / "SFC" / "SFC HF-01 e HF-02"
    dossie.mkdir(parents=True)
    (dossie / "#ST00=B01BMU10&EPB020_STATUS_PMIB.xlsx").write_bytes(b"x")
    especificacao, capitulo = "SERVIÇOS AUXILIARES ELÉTRICOS", "CONVERSORES ESTÁTICOS DE FREQUÊNCIA"
    a = cr.ListaNaMapeadora("#ST00=B01BMU10&EPB020", "1A", "", "", "1A", None, descricao="SFC 50 E 60 HZ",
                            especificacao=especificacao, capitulo=capitulo)
    b = cr.ListaNaMapeadora("#ST00=B01BMU10TA010&EPB020", "0", "", "Aprovado", "0C", None, descricao="SFC THF",
                            especificacao=especificacao, capitulo=capitulo)
    tela = _tela(qtbot, tmp_path, monkeypatch)
    _rodar_no_mesmo_fio(tela, monkeypatch)
    tela.caminho_mapeadora = str(tmp_path / "m.xlsx")
    monkeypatch.setattr(tela_mod.conferencia_svc, "ler_mapeadora",
                        lambda caminho: cr.Mapeadora(tmp_path / "m.xlsx", None, [a, b]))
    levantamentos = []
    original = tela_mod.docpack_svc.levantar
    monkeypatch.setattr(tela_mod.docpack_svc, "levantar", lambda raiz: levantamentos.append(raiz) or original(raiz))
    tela._listar()
    assert [lista.codigo for lista in tela.listas] == [b.codigo] and len(levantamentos) == 1

    recebidos = []
    monkeypatch.setattr(tela, "_cliente_ia", lambda: object())
    monkeypatch.setattr(tela_mod.docpack_svc, "sugerir_destino",
                        lambda lista, existentes, llm, **kw: recebidos.append(kw) or (None, "sem resposta"))
    tela.tabela.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)
    tela._sugerir()
    (kw,) = recebidos
    assert [(v.codigo, v.pasta) for v in kw["vizinhas"]] == [(a.codigo, "03 - EBOP/SFC/SFC HF-01 e HF-02")]
    assert [(r.capitulo, r.pastas) for r in kw["mapa"]] == [(capitulo, (("03 - EBOP/SFC", 1),))]

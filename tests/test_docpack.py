"""DocPack (`services/docpack.py`): quais listas, o dossiê e a sugestão da IA (a lista com preço
saiu daqui em 2026-11-05: `test_lista_precos_arquivo.py`).

Os templates do `_STATUS_PMIB` e da lista com preço são as cópias do repositório
(`gestao-sobressalentes/_gestao_v2/`); o da Aplicação LMR é sintético (não há cópia).
"""
from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from _openpyxl_de_verdade import openpyxl_de_verdade

from sigft.services import conferencia_revisoes as cr
from sigft.services import docpack, status_pmib_arquivos

XL = None   # o openpyxl de verdade, durante cada teste (`_openpyxl`)


@pytest.fixture(autouse=True)
def _openpyxl():
    global XL
    with openpyxl_de_verdade(cr, docpack) as real:
        XL = real
        yield
    XL = None


def Workbook():  # noqa: N802 -- o nome do openpyxl
    return XL.Workbook()


def load_workbook(*args, **kw):
    return XL.load_workbook(*args, **kw)

RAIZ_REPO = Path(__file__).resolve().parents[1]
TEMPLATE_STATUS = RAIZ_REPO / "gestao-sobressalentes/_gestao_v2/template/codigo_itaipu_STATUS_PMIB_v2.xlsx"
CODIGO = "#ST00=M00MEU10&MPB020"
HOJE = date(2026, 11, 3)

CABECALHO = ["N° DOCUMENTO ITAIPU", "N° DOCUMENTO CMI", "ÚLTIMA REVISÃO EMITIDA", "STATUS DA REVISÃO",
             "DATA DE ATUALIZAÇÃO", "STATUS REAL", "REVISÃO EM USO", "DESCRIÇÃO", "ESPECIFICAÇÃO TÉCNICA",
             "CAPÍTULO", "RESPONSÁVEL", "PROCUREMENT", "ELABORADOR DO DOCUMENTO", "ORIGEM FORNECEDOR",
             "ENTREGA", "OBSERVAÇÃO", "EVENTOS DE PAGAMENTOS\nRELACIONADOS", "SITUAÇÃO NO PMIB",
             "LINK DA PLANILHA"]


def _mapeadora(tmp_path, linhas) -> Path:
    """Linhas: (código, título, revisão em uso, link ou None[, {coluna: valor}]). Sem o
    dicionário, a lista saiu no Aconex: 0B, Em Processo, STATUS REAL Aprovado."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Acompanhamento Sobressalente"
    ws.append(["Mapeamento"])
    ws.append(CABECALHO)
    for codigo, titulo, revisao, link, *outras in linhas:
        aconex = {"ÚLTIMA REVISÃO EMITIDA": "0B", "STATUS DA REVISÃO": "Em Processo", "STATUS REAL": "Aprovado"}
        aconex.update(*outras)
        ws.append([codigo, "CMI-0001", aconex["ÚLTIMA REVISÃO EMITIDA"], aconex["STATUS DA REVISÃO"], None,
                   aconex["STATUS REAL"], revisao, titulo,
                   "SERVICOS AUXILIARES ELETRICOS", "CAP 05", None, None, None, None, None, None,
                   "EP-12", None, "Abrir Box" if link else None])
        if link:
            ws.cell(ws.max_row, len(CABECALHO)).hyperlink = link
    caminho = tmp_path / "Mapeamento Listas de Sobressalentes.xlsx"
    wb.save(caminho)
    return caminho


def _lista(**campos) -> cr.ListaNaMapeadora:
    base = dict(codigo=CODIGO, ultima_revisao="0B", status_da_revisao="", status_real="", revisao_em_uso="0A",
                link=None, codigo_cmi="CMI-0001", descricao="LISTA DE SOBRESSALENTES - GERADOR DIESEL",
                especificacao="SERVICOS AUXILIARES ELETRICOS", capitulo="CAP 05", eventos="EP-12")
    base.update(campos)
    return cr.ListaNaMapeadora(**base)


def _template_lmr(tmp_path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "DOCS DE REFERÊNCIA"
    ws["A1"] = "LISTA DE SOBRESSALENTE:"
    ws.merge_cells("A1:B1")
    ws["A2"] = "Especificação técnica / capítulo:"
    ws["A3"] = "SUBSISTEMA:"
    caminho = tmp_path / "templates" / "Aplicação LMR - Sistema.xlsx"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb.save(caminho)
    return caminho


@pytest.fixture
def templates(tmp_path):
    return docpack.Templates(str(TEMPLATE_STATUS), str(_template_lmr(tmp_path)))


# -- quais listas --------------------------------------------------------------
def test_listas_sem_status_pmib_pula_link_vivo_e_lista_de_preco(tmp_path):
    raiz = tmp_path / "raiz"
    (raiz / "05 - X").mkdir(parents=True)
    (raiz / "05 - X" / "#ST00=VIVO&MPB020_STATUS_PMIB.xlsx").write_bytes(TEMPLATE_STATUS.read_bytes())
    caminho = _mapeadora(tmp_path, [
        (CODIGO, "LISTA DE SOBRESSALENTES - A", "0A", None),
        ("#ST00=LINK&MPB020", "LISTA DE SOBRESSALENTES - B", "0A", "x/y_STATUS_PMIB.xlsx"),
        ("#ST00=VIVO&MPB020", "LISTA DE SOBRESSALENTES - C", "0A", None),
        ("#ST00=PRECO&MPB021", "LISTA COM PREÇO", "0A", None),
        ("#ST00=COMP&MPB020", "LISTA DE PREÇOS DE SOBRESSALENTES", "0A", None),
        ("#ITA0=A01AAM10&EPB020-01", "", "0A", None),
    ])
    mapeadora = cr.ler_mapeadora(caminho)
    codigos = [lista.codigo for lista in docpack.listas_sem_status_pmib(mapeadora, raiz)]
    assert codigos == [CODIGO, "#ITA0=A01AAM10&EPB020-01"]


# -- só a lista que já saiu no Aconex (2026-11-09) ---------------------------------
# Pedido do Luan, depois de criar dossiês de listas que nem tinham saído no Aconex: "se a lista
# de sobressalentes ainda nem foi emitida, não quero criar o DocPack dela". O STATUS REAL é o
# da batalha de versões do DocManager, que o Gestão PMIB grava na mapeadora.
@pytest.mark.parametrize("campos, no_motivo", [
    ({"status_real": "NÃO EMITIDO"}, "NÃO EMITIDO"),
    ({"status_real": " nao emitido"}, "NÃO EMITIDO"),      # o valor antigo, digitado à mão
    ({"status_real": "Aprovado", "status_da_revisao": "Lista não emitida"}, "LISTA NÃO EMITIDA"),
    ({"status_real": "Aprovado", "ultima_revisao": ""}, "ÚLTIMA REVISÃO EMITIDA"),
    ({"status_real": "", "ultima_revisao": "0A"}, "sem STATUS REAL"),
])
def test_lista_que_ainda_nao_saiu_no_aconex_tem_o_motivo(campos, no_motivo):
    motivo = docpack.motivo_nao_emitida(_lista(**campos))
    assert motivo and no_motivo in motivo


@pytest.mark.parametrize("status_real", ["Aprovado", "Aprovado com Comentários", "Para Assinatura",
                                         "Em Processo", "Não Aprovado", "APROVADO"])
def test_lista_que_saiu_no_aconex_nao_tem_motivo(status_real):
    """Em processo ou não aprovada, a lista saiu: o DocPack a oferece."""
    assert docpack.motivo_nao_emitida(_lista(status_real=status_real)) is None


def test_listar_deixa_de_fora_a_lista_que_ainda_nao_saiu_no_aconex(tmp_path):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    nao_emitida, sem_revisao, com_link = "#ST00=NEMIT&MPB020", "#ST00=SEMREV&MPB020", "#ST00=LINK&MPB020"
    caminho = _mapeadora(tmp_path, [
        (CODIGO, "LISTA DE SOBRESSALENTES - A", "", None),
        (nao_emitida, "LISTA DE SOBRESSALENTES - B", "", None,
         {"ÚLTIMA REVISÃO EMITIDA": "0A", "STATUS DA REVISÃO": "Para Análise", "STATUS REAL": "NÃO EMITIDO"}),
        (sem_revisao, "LISTA DE SOBRESSALENTES - C", "", None,
         {"ÚLTIMA REVISÃO EMITIDA": None, "STATUS DA REVISÃO": None, "STATUS REAL": None}),
        # Já tem dossiê: fica fora pelo link, e não entra na conta das não emitidas.
        (com_link, "LISTA DE SOBRESSALENTES - D", "0A", "x/y_STATUS_PMIB.xlsx", {"STATUS REAL": "NÃO EMITIDO"}),
    ])
    mapeadora = cr.ler_mapeadora(caminho)
    assert [lista.codigo for lista in docpack.listas_sem_status_pmib(mapeadora, raiz)] == [CODIGO]
    fora = docpack.listas_nao_emitidas(mapeadora, raiz)
    assert [lista.codigo for lista, _motivo in fora] == [nao_emitida, sem_revisao]
    assert "NÃO EMITIDO" in fora[0][1] and "ÚLTIMA REVISÃO EMITIDA" in fora[1][1]


def test_a_mapeadora_traz_as_colunas_do_docpack(tmp_path):
    lista = cr.ler_mapeadora(_mapeadora(tmp_path, [(CODIGO, "TITULO", "0A", None)])).listas[0]
    assert (lista.codigo_cmi, lista.descricao, lista.especificacao, lista.capitulo, lista.eventos) == (
        "CMI-0001", "TITULO", "SERVICOS AUXILIARES ELETRICOS", "CAP 05", "EP-12")


def test_mapeadora_sem_as_colunas_opcionais_continua_lendo(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Acompanhamento Sobressalente"
    ws.append([])
    ws.append(list(cr.COLUNAS))
    ws.append([CODIGO, "0B", "x", "y", "0A", None])
    caminho = tmp_path / "m.xlsx"
    wb.save(caminho)
    lista = cr.ler_mapeadora(caminho).listas[0]
    assert lista.descricao == "" and lista.codigo == CODIGO


# -- textos ------------------------------------------------------------------------
def test_titulo_no_formato_do_template():
    assert docpack.texto_do_titulo(_lista(), "GERADOR DIESEL") == (
        "SERVICOS AUXILIARES ELETRICOS / CAP 05 / GERADOR DIESEL | #ST00=M00MEU10&MPB020 / CMI-0001 | EP-12")
    assert docpack.texto_do_titulo(_lista(eventos="", codigo_cmi=""), "X") == (
        "SERVICOS AUXILIARES ELETRICOS / CAP 05 / X | #ST00=M00MEU10&MPB020")


def test_linha_da_revisao_volta_pela_leitura_do_status_pmib():
    texto = docpack.texto_da_revisao("0A", HOJE)
    assert texto == "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/11/2026"
    assert status_pmib_arquivos.revisao_do_texto(texto) == "0A"


# -- destino -----------------------------------------------------------------------
def test_pasta_do_dossie_segue_a_hierarquia_da_et_e_pula_o_vazio(tmp_path):
    destino = docpack.Destino(et="05 - UNIDADE GERADORA", capitulo=" CAP 05 ", sistema="EXCITACAO",
                              subsistema="REGULADOR", pasta="")
    assert docpack.pasta_do_dossie(tmp_path, destino) == (
        tmp_path / "05 - UNIDADE GERADORA" / "CAP 05" / "EXCITACAO" / "REGULADOR")
    assert docpack.pasta_do_dossie(tmp_path, docpack.Destino(et="03 - EBOP", subsistema="GERADOR DIESEL")) == (
        tmp_path / "03 - EBOP" / "GERADOR DIESEL")


def test_barra_poe_mais_uma_pasta_naquele_passo(tmp_path):
    destino = docpack.Destino(et="05 - UG", capitulo="CAP 05", sistema="MANCAIS / GUIA", subsistema="SUB")
    assert docpack.partes_do_caminho(destino) == ["05 - UG", "CAP 05", "MANCAIS", "GUIA", "SUB"]


def test_nome_do_subsistema_e_o_do_nivel_ou_a_ultima_pasta():
    assert docpack.nome_do_subsistema(docpack.Destino(et="E", subsistema="SUB", pasta="FINAL")) == "SUB"
    assert docpack.nome_do_subsistema(docpack.Destino(et="E", pasta="A/FINAL")) == "FINAL"
    assert docpack.nome_do_subsistema(docpack.Destino(et="E", capitulo="CAP")) == "CAP"


@pytest.mark.parametrize("destino", [docpack.Destino("", "", "X"), docpack.Destino("A", "", ""),
                                     docpack.Destino("..", "", "X"), docpack.Destino("A", "S:", "X"),
                                     docpack.Destino("A", "", "B/.."), docpack.Destino("A", "", "", "", "X*")])
def test_destino_invalido(tmp_path, destino):
    with pytest.raises(docpack.ErroDocPack):
        docpack.pasta_do_dossie(tmp_path, destino)


def test_arvore_existente_sem_as_ignoradas_nem_as_do_dossie(tmp_path):
    for p in ("03 - EBOP/CAP 03/GERADOR DIESEL/LMR", "03 - EBOP/DATASHEETS", "00 - OBSOLETO/X", ".oculta",
              "05 - UG"):
        (tmp_path / p).mkdir(parents=True)
    assert docpack.arvore_existente(tmp_path) == {"03 - EBOP": {"CAP 03": {"GERADOR DIESEL": {}}}, "05 - UG": {}}
    assert docpack.pastas_existentes(tmp_path) == {"03 - EBOP": {"CAP 03": {}}, "05 - UG": {}}


def test_opcoes_do_nivel_dentro_das_pastas_de_cima():
    arvore = {"05 - UG": {"CAP 05": {"EXCITACAO": {"REGULADOR": {}}, "MANCAIS": {"GUIA": {"SUB": {}}}}}, "03 - EBOP": {}}
    assert docpack.opcoes_do_nivel(arvore, docpack.Destino(), "et") == ["03 - EBOP", "05 - UG"]
    destino = docpack.Destino(et="05 - ug", capitulo="CAP 05")
    assert docpack.opcoes_do_nivel(arvore, destino, "sistema") == ["EXCITACAO", "MANCAIS"]
    # O sistema vazio é pulado: o subsistema vem das pastas do capítulo.
    assert docpack.opcoes_do_nivel(arvore, destino, "subsistema") == ["EXCITACAO", "MANCAIS"]
    destino.sistema = "MANCAIS/GUIA"
    assert docpack.opcoes_do_nivel(arvore, destino, "subsistema") == ["SUB"]
    destino.capitulo = "CAP NOVO"
    assert docpack.opcoes_do_nivel(arvore, destino, "sistema") == []


def test_achar_templates_pelos_nomes_conhecidos(tmp_path):
    (tmp_path / "codigo_itaipu_STATUS_PMIB.xlsx").write_bytes(b"x")
    (tmp_path / "APLICACAO LMR - SOBRESSALENTES_template.xlsx").write_bytes(b"x")
    achados = docpack.achar_templates(tmp_path)
    assert Path(achados.status_pmib).name == "codigo_itaipu_STATUS_PMIB.xlsx"
    assert Path(achados.aplicacao_lmr).name == "APLICACAO LMR - SOBRESSALENTES_template.xlsx"


# -- o dossiê ------------------------------------------------------------------------
def _criar(tmp_path, templates, lista=None, destino=None, **kw):
    raiz = tmp_path / "raiz"
    raiz.mkdir(exist_ok=True)
    destino = destino or docpack.Destino("03 - EBOP", "", "GERADOR DIESEL")
    return raiz, docpack.criar_dossie(lista or _lista(), raiz, destino, templates, hoje=HOJE, **kw)


def test_dossie_completo(tmp_path, templates):
    raiz, resultado = _criar(tmp_path, templates)
    pasta = raiz / "03 - EBOP" / "GERADOR DIESEL"
    assert resultado.situacao == "criado", resultado
    assert sorted(p.name for p in pasta.iterdir()) == sorted(
        ["#ST00=M00MEU10&MPB020_STATUS_PMIB.xlsx", "LMR", "IMAGENS", "DATASHEETS"])
    assert [p.name for p in (pasta / "LMR").iterdir()] == ["Aplicação LMR - GERADOR DIESEL.xlsx"]
    # O _STATUS_PMIB novo conta como vivo, com o código certo.
    assert [c for c, _ in status_pmib_arquivos.listar(raiz).vivos] == [CODIGO]


def test_status_pmib_tem_titulo_e_revisao_e_guarda_o_resto(tmp_path, templates):
    raiz, _ = _criar(tmp_path, templates)
    status = raiz / "03 - EBOP" / "GERADOR DIESEL" / f"{CODIGO}_STATUS_PMIB.xlsx"
    wb = load_workbook(status)
    ws = wb["Lista de Materiais"]
    assert ws["A3"].value == docpack.texto_do_titulo(_lista(), "GERADOR DIESEL")
    assert status_pmib_arquivos.revisao_do_texto(ws["A4"].value) == "0A"
    assert ws["A5"].value == "ITEM"
    original = load_workbook(TEMPLATE_STATUS)
    assert set(wb.defined_names) == set(original.defined_names)
    assert wb.sheetnames == original.sheetnames
    # Só a aba editada mudou: o resto do pacote sai byte a byte.
    with zipfile.ZipFile(status) as novo, zipfile.ZipFile(TEMPLATE_STATUS) as velho:
        diferentes = {n for n in velho.namelist() if n in novo.namelist() and novo.read(n) != velho.read(n)}
    assert diferentes <= {"xl/worksheets/sheet1.xml", "xl/calcChain.xml", "[Content_Types].xml",
                          "xl/_rels/workbook.xml.rels"}


def test_dossie_com_a_hierarquia_inteira_usa_o_subsistema(tmp_path, templates):
    destino = docpack.Destino(et="05 - UNIDADE GERADORA", capitulo="CAP 05", sistema="EXCITACAO/AUX",
                              subsistema="REGULADOR", pasta="LOTE 1")
    raiz, resultado = _criar(tmp_path, templates, destino=destino)
    pasta = raiz / "05 - UNIDADE GERADORA" / "CAP 05" / "EXCITACAO" / "AUX" / "REGULADOR" / "LOTE 1"
    assert resultado.pasta == pasta and resultado.situacao == "criado"
    ws = load_workbook(pasta / f"{CODIGO}_STATUS_PMIB.xlsx")["Lista de Materiais"]
    assert ws["A3"].value == docpack.texto_do_titulo(_lista(), "REGULADOR")
    assert (pasta / "LMR").is_dir() and any(p.name.endswith("REGULADOR.xlsx") for p in (pasta / "LMR").iterdir())


def test_sem_revisao_fica_a_linha_do_template_e_avisa(tmp_path, templates):
    raiz, resultado = _criar(tmp_path, templates, lista=_lista(revisao_em_uso="", ultima_revisao=""))
    assert resultado.situacao == "aviso"
    assert any("revisão" in a for a in resultado.avisos)
    status = raiz / "03 - EBOP" / "GERADOR DIESEL" / f"{CODIGO}_STATUS_PMIB.xlsx"
    assert load_workbook(status)["Lista de Materiais"]["A4"].value == (
        load_workbook(TEMPLATE_STATUS)["Lista de Materiais"]["A4"].value)


def test_dossie_nao_tem_lista_com_preco(tmp_path, templates):
    # 2026-11-05: a lista com preço é do módulo Lista de Preços, não do DocPack.
    raiz, _ = _criar(tmp_path, templates)
    pasta = raiz / "03 - EBOP" / "GERADOR DIESEL"
    assert not any("PB021" in p.name for p in pasta.iterdir())
    assert not hasattr(docpack.Templates(), "lista_precos")


def test_aplicacao_lmr_preenche_os_rotulos(tmp_path, templates):
    raiz, _ = _criar(tmp_path, templates)
    lmr = raiz / "03 - EBOP" / "GERADOR DIESEL" / "LMR" / "Aplicação LMR - GERADOR DIESEL.xlsx"
    ws = load_workbook(lmr).active
    assert ws["C1"].value == CODIGO          # o rótulo é A1:B1 mesclado: o valor vai em C1
    assert ws["B2"].value == "SERVICOS AUXILIARES ELETRICOS / CAP 05"
    assert ws["B3"].value == "GERADOR DIESEL"


def test_aplicacao_lmr_sem_rotulo_avisa(tmp_path, templates):
    wb = Workbook()
    wb.active.title = "DOCS DE REFERENCIA"
    sem_rotulo = tmp_path / "lmr_vazio.xlsx"
    wb.save(sem_rotulo)
    templates.aplicacao_lmr = str(sem_rotulo)
    _, resultado = _criar(tmp_path, templates)
    assert resultado.situacao == "aviso"
    assert any("LISTA DE SOBRESSALENTE:" in a for a in resultado.avisos)


def test_nunca_sobrescreve(tmp_path, templates):
    raiz, _ = _criar(tmp_path, templates)
    status = raiz / "03 - EBOP" / "GERADOR DIESEL" / f"{CODIGO}_STATUS_PMIB.xlsx"
    status.write_bytes(b"da pessoa")
    _, resultado = _criar(tmp_path, templates)
    assert status.read_bytes() == b"da pessoa"
    assert resultado.situacao == "aviso"
    assert sum("já existia" in a for a in resultado.avisos) == 2


def test_codigo_vivo_na_raiz_pula_a_lista(tmp_path, templates):
    raiz, resultado = _criar(tmp_path, templates, vivos={CODIGO.upper()})
    assert resultado.situacao == "falhou"
    assert not (raiz / "03 - EBOP").exists()


def test_sem_template_do_status_pmib_falha_sem_criar_nada(tmp_path, templates):
    templates.status_pmib = ""
    raiz, resultado = _criar(tmp_path, templates)
    assert resultado.situacao == "falhou"
    assert not (raiz / "03 - EBOP").exists()


def test_sem_os_outros_templates_cria_com_aviso(tmp_path, templates):
    templates.aplicacao_lmr = ""
    raiz, resultado = _criar(tmp_path, templates)
    pasta = raiz / "03 - EBOP" / "GERADOR DIESEL"
    assert resultado.situacao == "aviso" and len(resultado.avisos) == 1
    assert (pasta / f"{CODIGO}_STATUS_PMIB.xlsx").is_file() and (pasta / "LMR").is_dir()


def test_pasta_obsoleta_avisa(tmp_path, templates):
    _, resultado = _criar(tmp_path, templates, destino=docpack.Destino("00 - OBSOLETO", "", "X"))
    assert any("não conta como vivo" in a for a in resultado.avisos)


def test_planejar_diz_o_que_ja_existe(tmp_path, templates):
    raiz = tmp_path / "raiz"
    (raiz / "03 - EBOP").mkdir(parents=True)
    passos = docpack.planejar(_lista(), raiz, docpack.Destino("03 - EBOP", "", "GD"), templates)
    assert [(p.caminho.relative_to(raiz).as_posix(), p.tipo, p.existe) for p in passos][:2] == [
        ("03 - EBOP", "pasta", True), ("03 - EBOP/GD", "pasta", False)]
    assert sum(p.tipo == "arquivo" for p in passos) == 2
    assert not (raiz / "03 - EBOP" / "GD").exists()


def test_criar_dossies_loga_e_resume(tmp_path, templates):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    linhas = []
    pedidos = [(_lista(), docpack.Destino("03 - EBOP", "", "GD")),
               (_lista(codigo="#ST00=B&MPB020"), docpack.Destino("", "", "GD"))]
    resultados = docpack.criar_dossies(pedidos, raiz, templates, log_cb=linhas.append)
    assert [r.situacao for r in resultados] == ["criado", "falhou"]
    assert linhas[0].startswith("DocPack: 2 lista(s)")
    assert any(linha.startswith("  ✅ " + CODIGO) for linha in linhas)
    assert any(linha.startswith("  ❌ #ST00=B&MPB020") for linha in linhas)
    assert "1 criado(s), 0 com aviso, 1 falha(s)" in linhas[-2]
    assert "Gestão PMIB" in linhas[-1]


# -- a IA -------------------------------------------------------------------------------
class _LLM:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.prompts = resposta, erro, []

    def generate(self, prompt, **_kw):
        self.prompts.append(prompt)
        if self.erro:
            raise self.erro
        return self.resposta


def test_sugestao_da_ia_na_hierarquia_da_et():
    llm = _LLM(SimpleNamespace(parsed_json={"et": "03 - EBOP", "capitulo": "CAP 03", "sistema": "",
                                            "subsistema": "GERADOR DIESEL", "pasta": "",
                                            "motivo": "o título fala do gerador"}, text=""))
    arvore = {"03 - EBOP": {"CAP 03": {"GERADOR DIESEL": {}}}, "05 - UG": {}}
    destino, motivo = docpack.sugerir_destino(_lista(), arvore, llm)
    assert destino == docpack.Destino(et="03 - EBOP", capitulo="CAP 03", subsistema="GERADOR DIESEL")
    assert motivo == "o título fala do gerador"
    assert "GERADOR DIESEL" in llm.prompts[0] and CODIGO in llm.prompts[0]
    assert '"et"' in llm.prompts[0] and '"subsistema"' in llm.prompts[0]


def test_sugestao_tolerante_ao_texto_e_ao_formato_de_antes():
    texto = 'Claro!\n```json\n{"capitulo": "05 - UG", "subsistema": "EXCITACAO",}\n```'
    # Sem "et": a resposta de antes, em que a primeira pasta se chamava "capitulo".
    assert docpack.ler_sugestao(texto) == docpack.Destino(et="05 - UG", subsistema="EXCITACAO")
    antigo = {"capitulo": "03 - EBOP", "sistema": "CAP 03", "pasta": "GERADOR DIESEL"}
    assert docpack.ler_sugestao(antigo) == docpack.Destino(et="03 - EBOP", capitulo="CAP 03",
                                                           subsistema="GERADOR DIESEL")


@pytest.mark.parametrize("llm", [_LLM(erro=RuntimeError("sem rede")),
                                 _LLM(SimpleNamespace(parsed_json={"capitulo": ""}, text="")),
                                 _LLM(SimpleNamespace(parsed_json={"et": "03 - EBOP"}, text=""))])
def test_sugestao_que_falha_nao_levanta(llm):
    destino, motivo = docpack.sugerir_destino(_lista(), {}, llm)
    assert destino is None and motivo

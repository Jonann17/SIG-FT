r"""Relatório em Excel do que faltou em cada ficha (2026-08-26).

**Para que serve** (pedido do usuário): pegar o resumo e mandar ao FORNECEDOR
como guia do que precisa ser corrigido. Uma linha por material, o código PMIB
numa coluna e, na outra, o resumo do que estava faltando ou errado — com a
justificativa, quando existe, de por que a informação não serve.

Quem lê este arquivo não é engenheiro do SIG-FT: é quem preencheu a ficha. Por
isso o resumo usa o RÓTULO do campo ("Peso líquido (kg)"), e não a chave
interna (`peso_liquido`), e por isso a justificativa da IA é repassada
literalmente — ela foi escrita para o fornecedor, e o prompt diz isso.
"""

from sigft.services import analyzer_relatorio as rel


def test_ficha_sem_problema_nenhum_nao_entra_no_relatorio():
    """Relatório é lista de pendências. Ficha aprovada não gera trabalho para
    ninguém, e listá-la só faria o fornecedor procurar o que não existe."""
    r = rel.RelatorioAnalise()
    assert r.registrar("4500063671.0071", "a.xlsx", nota=100, achados=[]) is None
    assert not r
    assert r.linhas() == []


def test_uma_linha_por_ficha_com_o_codigo_pmib_na_primeira_coluna():
    r = rel.RelatorioAnalise()
    r.registrar("4500063671.0071", "a.xlsx", nota=62,
                achados=[rel.Achado("fabricante", "vazio")])
    r.registrar("4500063671.0154", "b.xlsx", nota=80,
                achados=[rel.Achado("peso_liquido", "vazio")])
    linhas = r.linhas()
    assert [l[0] for l in linhas] == ["4500063671.0071", "4500063671.0154"]
    assert len(linhas) == 2


def test_o_resumo_usa_o_ROTULO_do_campo_e_nao_a_chave_interna():
    """`peso_liquido` não diz nada para quem preencheu a ficha."""
    resumo = rel.resumo([rel.Achado("peso_liquido", "vazio")])
    assert "Peso líquido" in resumo
    assert "peso_liquido" not in resumo


def test_campo_vazio_diz_que_esta_em_branco():
    resumo = rel.resumo([rel.Achado("fabricante", "vazio")])
    assert "Fabricante" in resumo
    assert "branco" in resumo.lower() or "preench" in resumo.lower()


def test_a_JUSTIFICATIVA_da_IA_vai_junto_quando_existe():
    """É o que o usuário pediu: "apresentando, caso válido, uma justificativa
    sobre o porque estava errado tal informação"."""
    resumo = rel.resumo([rel.Achado(
        "transporte", "invalido",
        motivo="A resposta não descreve a posição de içagem.")])
    assert "A resposta não descreve a posição de içagem." in resumo


def test_invalido_SEM_justificativa_ainda_diz_qual_campo():
    """Modelo mais fraco pode ignorar o `motivo` do prompt. O relatório não
    pode ficar mudo por causa disso."""
    resumo = rel.resumo([rel.Achado("transporte", "invalido")])
    assert "içagem" in resumo.lower() or "Posições" in resumo
    assert resumo.strip()


def test_obrigatorio_e_marcado_como_obrigatorio_no_resumo():
    """O fornecedor precisa saber o que BLOQUEIA o cadastro e o que só
    diminui a nota."""
    resumo = rel.resumo([rel.Achado("fabricante", "vazio", obrigatorio=True)])
    assert "obrigat" in resumo.lower()


def test_especificacao_tecnica_aparece_com_a_pergunta_dela():
    """As specs não têm chave no CONFIG_MAP — o que identifica cada uma é a
    própria pergunta escrita na planilha."""
    resumo = rel.resumo([rel.Achado(
        "Material de fabricação?", "invalido", motivo="Foi informada uma dimensão.",
        especificacao=True)])
    assert "Material de fabricação?" in resumo


def test_ficha_nao_analisada_explica_o_motivo_em_vez_de_listar_campos():
    resumo = rel.resumo([rel.Achado("", "nao_analisada",
                                    motivo="Ficha sem a secao de especificacoes tecnicas.")])
    assert "Ficha sem a secao de especificacoes tecnicas." in resumo


def test_o_resumo_junta_varios_achados_numa_celula_so():
    resumo = rel.resumo([
        rel.Achado("fabricante", "vazio", obrigatorio=True),
        rel.Achado("peso_liquido", "vazio", obrigatorio=True),
        rel.Achado("transporte", "invalido", motivo="Não descreve a içagem."),
    ])
    assert "Fabricante" in resumo and "Peso líquido" in resumo
    assert "Não descreve a içagem." in resumo


def test_a_nota_da_ficha_entra_no_relatorio():
    r = rel.RelatorioAnalise()
    r.registrar("4500063671.0071", "a.xlsx", nota=62,
                achados=[rel.Achado("fabricante", "vazio")])
    assert "62" in str(r.linhas()[0])


def test_sem_codigo_pmib_usa_o_nome_do_arquivo():
    """Ficha fora do padrão de nome ainda precisa ser identificável."""
    r = rel.RelatorioAnalise()
    r.registrar(None, "ficha_sem_codigo.xlsx", nota=50,
                achados=[rel.Achado("fabricante", "vazio")])
    assert "ficha_sem_codigo.xlsx" in r.linhas()[0][0]


def test_o_servico_de_relatorio_NAO_importa_tkinter():
    """Princípio nº 2 da arquitetura, verificado por AST — a mesma trava que
    `autospec_conferencia` tem."""
    import ast
    import inspect

    arvore = ast.parse(inspect.getsource(rel))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    assert "tkinter" not in importados
    assert "customtkinter" not in importados


def test_todo_campo_do_CONFIG_MAP_tem_rotulo():
    """Um campo sem rótulo cairia no relatório como chave interna, e o
    fornecedor receberia `ferramentas_para_preservacao` para interpretar."""
    from sigft.core.rpa.ficha_layout import CONFIG_MAP
    sem_rotulo = [k for k in CONFIG_MAP if k not in rel.ROTULOS]
    assert sem_rotulo == []


# =============================================================================
# Integração: quem preenche o relatório é o `processar_planilha`
# =============================================================================
from tests.test_analyzer_planilha import (  # noqa: E402
    FakeWorkbook, _aba_de_ficha, _analyzer, _sem)


def _rodar(an, ws, **kw):
    import sigft.services.analyzer as mod
    wb = FakeWorkbook([ws])
    original = mod.openpyxl.load_workbook
    mod.openpyxl.load_workbook = lambda *a, **k: wb
    kw.setdefault("pmib_sheet", None)
    kw.setdefault("callback_manual_desc", None)
    kw.setdefault("score_threshold", 101)
    kw.setdefault("root_output_dir", "/tmp/naosalva")
    try:
        return list(an.processar_planilha(
            input_filepath="4500063671.0071.xlsx",
            subfolder_name="s", original_filename="4500063671.0071.xlsx",
            custom_weights=None, max_variable_points=45.0, **kw))
    finally:
        mod.openpyxl.load_workbook = original


def test_ficha_completa_nao_gera_linha_no_relatorio():
    an = _analyzer()
    an.relatorio = rel.RelatorioAnalise()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    _rodar(an, _aba_de_ficha())
    assert not an.relatorio


def test_campo_em_branco_vira_achado_com_o_rotulo_certo():
    an = _analyzer()
    an.relatorio = rel.RelatorioAnalise()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    _rodar(an, _sem(_aba_de_ficha(), "fabricante"))
    pmib, texto, nota = an.relatorio.linhas()[0]
    assert pmib == "4500063671.0071"
    assert "Fabricante" in texto and "obrigat" in texto.lower()


def test_a_justificativa_que_a_IA_devolveu_chega_ao_relatorio():
    """O caminho inteiro: prompt pede `motivo`, a IA devolve, o analyzer
    guarda, o relatório escreve. É o que o fornecedor vai ler."""
    an = _analyzer()
    an.relatorio = rel.RelatorioAnalise()
    an._call_gemini_api = lambda p: {
        "campos_fixos": {"transporte": {"status": "INVALIDO",
                                        "motivo": "Nao descreve a posicao de icagem."}},
        "campos_variaveis": []}
    _rodar(an, _aba_de_ficha())
    texto = an.relatorio.linhas()[0][1]
    assert "Nao descreve a posicao de icagem." in texto


def test_resposta_ANTIGA_da_IA_sem_motivo_nao_quebra():
    """Compatibilidade: modelo que ignore o `motivo` do prompt (ou uma
    resposta em cache do formato anterior) continua produzindo relatório."""
    an = _analyzer()
    an.relatorio = rel.RelatorioAnalise()
    an._call_gemini_api = lambda p: {
        "campos_fixos": {"transporte": {"status": "INVALIDO"}},
        "campos_variaveis": []}
    _rodar(an, _aba_de_ficha())
    texto = an.relatorio.linhas()[0][1]
    assert "içagem" in texto or "Içagem" in texto


def test_especificacao_reprovada_entra_com_a_PERGUNTA_dela():
    an = _analyzer()
    an.relatorio = rel.RelatorioAnalise()
    an._call_gemini_api = lambda p: {
        "campos_fixos": {},
        "campos_variaveis": [{"status": "VALIDO"},
                             {"status": "INVALIDO", "motivo": "Informou uma dimensao."},
                             {"status": "VALIDO"}]}
    _rodar(an, _aba_de_ficha(n_specs=3))
    texto = an.relatorio.linhas()[0][1]
    assert "Pergunta 2?" in texto
    assert "Informou uma dimensao." in texto


def test_ficha_sem_especificacoes_entra_como_NAO_ANALISADA(tmp_path):
    an = _analyzer()
    an.relatorio = rel.RelatorioAnalise()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    _rodar(an, _aba_de_ficha(n_specs=0), root_output_dir=str(tmp_path))
    texto = an.relatorio.linhas()[0][1]
    assert "especificac" in texto.lower() or "especificaç" in texto.lower()


def test_analyzer_SEM_relatorio_continua_funcionando():
    """O relatório é opcional: quem não o liga não pode quebrar."""
    an = _analyzer()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    linhas = _rodar(an, _sem(_aba_de_ficha(), "fabricante"))
    assert any("Nota Normalizada" in l for l in linhas)


def test_o_relatorio_usa_o_codigo_PMIB_COMPLETO():
    """`0002` identifica dentro do contrato; quem recebe o arquivo precisa do
    código inteiro para achar o material."""
    an = _analyzer()
    an.relatorio = rel.RelatorioAnalise()
    an._call_gemini_api = lambda p: {"campos_fixos": {}, "campos_variaveis": []}
    _rodar(an, _sem(_aba_de_ficha(), "fabricante"))
    assert an.relatorio.linhas()[0][0] == "4500063671.0071"

r"""Conferência humana dos documentos duvidosos (2026-08-13).
Ver `sigft/services/autospec_conferencia.py` e a tela
(`sigft/app_qt/views/autospec.py`, `class ModuloAutoSpec`), seção
"CONFERÊNCIA DE DOCUMENTOS DUVIDOSOS".

**Por que a lógica está num serviço e não na tela.** A tela, quando isto
nasceu, não podia ser importada no ambiente de teste (abria janela real), então
tudo que morasse lá era código sem rede de segurança. Pondo a decisão aqui — agrupar, converter
a marcação da grade em seleção, reprocessar — a conferência inteira fica
testável, e o que sobra na tela é desenho de widget.

O caso que motivou: numa ficha real entrou **uma camiseta da Minnie no site
do Target**, porque a URL continha o código do material; no mesmo lote um
datasheet legítimo de distribuidor foi barrado por não citar a marca no
título. Indistinguíveis para o código, triviais para quem abre o link.
"""

from sigft.services import autospec_conferencia as conf
from sigft.services.autospec import AutoSpecCore


DOCS_0071 = [
    {"url": "https://www.target.com/p/minnie-t-shirt/-/A-1000325606",
     "title": "Women's Disney Minnie Mouse T-Shirt", "snippet": ""},
    {"url": "https://docs.rs-online.com/284f/A700000011330366.pdf",
     "title": "Fieldbus Coupler Modbus TCP; 4th generation Data Sheet", "snippet": ""},
]


# =============================================================================
# A. Acumular e agrupar
# =============================================================================
def test_ficha_sem_duvidoso_nao_entra_na_lista():
    """A tela só pode mostrar o que precisa de decisão. Ficha resolvida
    sozinha não vira trabalho para o engenheiro."""
    c = conf.Conferencia()
    assert c.registrar("a.xlsx", documentos=[]) is None
    assert not c
    assert c.pendencias == []


def test_documento_sem_url_e_ignorado():
    c = conf.Conferencia()
    assert c.registrar("a.xlsx", documentos=[{"title": "sem link"}]) is None


def test_agrupa_POR_FICHA():
    c = conf.Conferencia()
    c.registrar("0071.xlsx", material="WAGO 750-362", documentos=DOCS_0071)
    c.registrar("0154.xlsx", material="WAGO 750-513",
                documentos=[{"url": "https://x/1", "title": "t"}])
    assert len(c.pendencias) == 2
    assert c.total_documentos == 3
    assert c.pendencias[0].nome_curto == "0071.xlsx"
    assert c.pendencias[0].material == "WAGO 750-362"


def test_o_nome_curto_e_o_do_arquivo():
    c = conf.Conferencia()
    p = c.registrar("C:/Users/x/Box/fichas/4500063671.0071.xlsx",
                    documentos=[{"url": "https://x/1"}])
    assert p.nome_curto == "4500063671.0071.xlsx"


# =============================================================================
# B. Da grade de checkbox para a seleção
# =============================================================================
def test_so_o_que_foi_MARCADO_entra():
    c = conf.Conferencia()
    c.registrar("0071.xlsx", documentos=DOCS_0071)
    selecao = c.selecao_por_ficha({(0, 0): False, (0, 1): True})
    assert selecao == {"0071.xlsx": ["https://docs.rs-online.com/284f/A700000011330366.pdf"]}


def test_nada_marcado_nao_devolve_ficha_nenhuma():
    c = conf.Conferencia()
    c.registrar("0071.xlsx", documentos=DOCS_0071)
    assert c.selecao_por_ficha({(0, 0): False, (0, 1): False}) == {}
    assert c.selecao_por_ficha({}) == {}
    assert c.selecao_por_ficha(None) == {}


def test_indice_fora_da_faixa_nao_quebra():
    """A grade da tela é reconstruída a cada lote; um índice velho não pode
    derrubar o processamento."""
    c = conf.Conferencia()
    c.registrar("0071.xlsx", documentos=DOCS_0071)
    assert c.selecao_por_ficha({(9, 9): True, (0, 9): True}) == {}


def test_duas_fichas_viram_duas_entradas():
    c = conf.Conferencia()
    c.registrar("0071.xlsx", documentos=DOCS_0071)
    c.registrar("0154.xlsx", documentos=[{"url": "https://x/1"}])
    selecao = c.selecao_por_ficha({(0, 0): True, (1, 0): True})
    assert set(selecao) == {"0071.xlsx", "0154.xlsx"}


# =============================================================================
# C. O resumo no console
# =============================================================================
def test_sem_pendencia_nao_polui_o_log():
    assert conf.resumo_para_console(conf.Conferencia()) == []


def test_o_resumo_diz_quantos_e_onde_conferir():
    c = conf.Conferencia()
    c.registrar("0071.xlsx", documentos=DOCS_0071)
    texto = "\n".join(conf.resumo_para_console(c))
    assert "2 documento(s)" in texto and "1 ficha(s)" in texto
    assert "Conferencia de documentos" in texto
    assert "0071.xlsx: 2 link(s)" in texto


# =============================================================================
# D. A segunda passada
# =============================================================================
def _core_para_2a_passada(monkeypatch, contexto="", chamadas=None):
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.conferencia = conf.Conferencia()
    core.usar_navegador_ultimo_recurso = False

    def _analyze(ficha, status):
        return (object(), {"var_row_79": {"type": "text", "desc": "P", "ref": "M79"}},
                "MAT", "WAGO", "desc", "cod", "750-362")

    core.analyze_sheet = _analyze
    core.contexto_das_urls = lambda urls, refs=(), callbacks=None: contexto
    core.generate_ai_response = lambda *a, **k: {"var_row_79": "175 bar"}
    core.fill_save = lambda wb, ficha, resp, missing, callbacks=None: f"{ficha}_completed.xlsx"
    if chamadas is not None:
        original = core.contexto_das_urls
        core.contexto_das_urls = lambda urls, refs=(), callbacks=None: (
            chamadas.append(list(urls)) or original(urls, refs, callbacks)
        )
    return core


def test_selecao_vazia_nao_processa_nada(monkeypatch):
    core = _core_para_2a_passada(monkeypatch)
    linhas = list(core.processar_conferidos({}, None))
    assert any("Nenhum documento aprovado" in l for l in linhas)


def test_a_2a_passada_usa_SO_as_urls_aprovadas(monkeypatch):
    chamadas = []
    core = _core_para_2a_passada(monkeypatch, contexto="Pressure 175 bar." * 20,
                                 chamadas=chamadas)
    linhas = list(core.processar_conferidos({"0071.xlsx": ["https://aprovada/1"]}, None))
    assert chamadas == [["https://aprovada/1"]]
    assert any("Salvo:" in l for l in linhas)


def test_documento_aprovado_sem_texto_nao_vira_ficha_preenchida(monkeypatch):
    """Aprovar um link que não rende texto não pode fazer a IA responder do
    nada — seria o oposto do que a conferência existe para garantir."""
    core = _core_para_2a_passada(monkeypatch, contexto="   ")
    linhas = list(core.processar_conferidos({"0071.xlsx": ["https://vazia/1"]}, None))
    assert any("rendeu texto" in l for l in linhas)
    assert not any("Salvo:" in l for l in linhas)


def test_ficha_ja_completa_e_pulada(monkeypatch):
    core = _core_para_2a_passada(monkeypatch, contexto="texto" * 50)
    core.analyze_sheet = lambda f, s: (object(), {}, "M", "W", "d", "c", "m")
    linhas = list(core.processar_conferidos({"0071.xlsx": ["https://x/1"]}, None))
    assert any("já está completa" in l for l in linhas)


def test_erro_numa_ficha_nao_derruba_as_outras(monkeypatch):
    core = _core_para_2a_passada(monkeypatch, contexto="texto" * 50)

    def _analyze(ficha, status):
        if "quebra" in ficha:
            raise RuntimeError("ficha corrompida")
        return (object(), {"var_row_79": {"type": "text", "desc": "P", "ref": "M79"}},
                "MAT", "WAGO", "desc", "cod", "750-362")

    core.analyze_sheet = _analyze
    linhas = list(core.processar_conferidos(
        {"quebra.xlsx": ["https://x/1"], "ok.xlsx": ["https://x/2"]}, None
    ))
    texto = "\n".join(linhas)
    assert "ficha corrompida" in texto
    assert "Salvo:" in texto


# =============================================================================
# E. A fronteira que não pode ser cruzada
# =============================================================================
def test_o_servico_de_conferencia_NAO_importa_tkinter():
    """Princípio nº 2 da arquitetura: serviço nunca importa interface.
    Também é o que permite estes testes rodarem sem tela nenhuma."""
    import ast
    import inspect

    # AST e nao substring: a palavra "tkinter" aparece no docstring do
    # modulo, explicando justamente por que ela nao pode ser importada.
    arvore = ast.parse(inspect.getsource(conf))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    assert "tkinter" not in importados
    assert "customtkinter" not in importados

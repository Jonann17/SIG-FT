r"""A conferencia das respostas do fornecedor, no `AutoSpecCore` (2026-09-28).

Coleta (`analyze_sheet`), a chamada separada (`auditar_respostas_do_fornecedor`)
e a decisao campo a campo. As pecas puras estao em
tests/test_autospec_auditoria.py; o lote, em tests/test_autospec_auditoria_lote.py.

A regra que atravessa este arquivo inteiro, pedida pelo usuario: resposta com
VALOR do fornecedor nunca e gravada -- divergencia so no log. So "nao se
aplica" (e afins) pode ser trocado, e so com a prova conferida.
"""
import json


from sigft import config
from sigft.services import autospec, autospec_documentos as docs
from sigft.services.autospec import AutoSpecCore


# =============================================================================
# Andaimes
# =============================================================================
class _Resposta:
    def __init__(self, parsed):
        self.parsed_json = parsed
        self.text = json.dumps(parsed)


class _LLMFake:
    def __init__(self, parsed=None, aceita_pdf=False, falhas=None):
        self.parsed = parsed if parsed is not None else {}
        self.aceita_pdf = aceita_pdf
        self.falhas = list(falhas or [])
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None, anexos=None):
        self.chamadas.append({"prompt": prompt, "anexos": anexos, "tags": tags})
        falha = self.falhas.pop(0) if self.falhas else None
        if falha is not None:
            raise falha
        return _Resposta(self.parsed)


class ReadTimeout(Exception):
    pass


def _logs():
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append((nivel, str(msg)))

    return _CB(), registro


DATASHEET = (
    "Solenoid valve 2/2 NC\n"
    "Supply voltage 24 VDC\n"
    "Degree of protection IP65\n"
    "Weight 1.2 kg\n"
)


def _doc(paginas=(DATASHEET,), nome="ds.pdf", mime="", dados=None):
    return docs.Documento(nome=nome, origem="LOCAL", paginas=list(paginas),
                          mime=mime, dados=dados)


def _core(parsed, documentos=None, aceita_pdf=False, falhas=None):
    core = AutoSpecCore(
        gemini_key="k", llama_key=None, google_search_key=None, google_cse_id=None,
        selecao_resolvida={"provider": config.PROVIDER_GEMINI, "model": "m"},
    )
    core._llm = _LLMFake(parsed, aceita_pdf=aceita_pdf, falhas=falhas)
    core.usar_cache_resposta = False
    core._documentos = list(documentos if documentos is not None else [_doc()])
    return core


def _contexto(core):
    return "\n\n".join(d.texto_marcado() for d in core._documentos)


def _resp(resposta, desc="7 - TENSAO NOMINAL (V)", ref="M85"):
    from sigft.core.rpa import ficha_layout

    return {"desc": desc, "ref": ref, "resposta": resposta,
            "nao_se_aplica": ficha_layout.e_nao_se_aplica(resposta)}


def _auditar(core, respostas, contexto=None):
    cb, linhas = _logs()
    resultado = core.auditar_respostas_do_fornecedor(
        "Valvula solenoide", "ASCO", "Valvula 2/2", respostas,
        _contexto(core) if contexto is None else contexto, callbacks=cb)
    return resultado, linhas


# =============================================================================
# 1. Coleta: analyze_sheet guarda o que o fornecedor escreveu
# =============================================================================
def _letra(coluna):
    letras = ""
    while coluna:
        coluna, resto = divmod(coluna - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


class _Celula:
    def __init__(self, coordenada, valor):
        self.coordinate, self.value = coordenada, valor


class _Aba:
    def __init__(self, valores, max_row=110):
        self.valores, self.max_row = valores, max_row

    def __getitem__(self, coordenada):
        return _Celula(coordenada, self.valores.get(coordenada))

    def cell(self, row, column):
        coordenada = f"{_letra(column)}{row}"
        return _Celula(coordenada, self.valores.get(coordenada))


class _Livro:
    sheetnames = ["Ficha Técnica Padrão"]

    def __init__(self, aba):
        self.aba = aba

    def __getitem__(self, nome):
        return self.aba


def test_analyze_sheet_guarda_as_respostas_do_fornecedor(monkeypatch):
    aba = _Aba({
        "H6": "VALVULA SOLENOIDE", "L10": "ASCO",
        "C79": "1 - APLICACAO", "M79": "",                    # vazio: vai para o missing
        "C80": "2 - TENSAO NOMINAL (V):", "M80": "Não se aplica",
        "C81": "3 - GRAU DE PROTECAO", "M81": "IP54",
        "C82": "4 - PESO (kg)", "M82": 1.2,
    })
    monkeypatch.setattr(autospec.openpyxl, "load_workbook", lambda *a, **k: _Livro(aba))
    core = AutoSpecCore.__new__(AutoSpecCore)

    _wb, missing, *_ = core.analyze_sheet("4500063671.0001.xlsx", None)

    assert "var_row_79" in missing
    assert not {"var_row_80", "var_row_81", "var_row_82"} & set(missing)
    assert core.respostas_do_fornecedor == {
        "var_row_80": {"desc": "2 - TENSAO NOMINAL (V)", "ref": "M80",
                       "resposta": "Não se aplica", "nao_se_aplica": True},
        "var_row_81": {"desc": "3 - GRAU DE PROTECAO", "ref": "M81",
                       "resposta": "IP54", "nao_se_aplica": False},
        "var_row_82": {"desc": "4 - PESO (kg)", "ref": "M82",
                       "resposta": "1.2", "nao_se_aplica": False},
    }


def test_analyze_sheet_zera_as_respostas_da_ficha_anterior(monkeypatch):
    aba = _Aba({"C79": "1 - APLICACAO", "M79": ""})
    monkeypatch.setattr(autospec.openpyxl, "load_workbook", lambda *a, **k: _Livro(aba))
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.respostas_do_fornecedor = {"var_row_90": _resp("IP54")}

    core.analyze_sheet("4500063671.0002.xlsx", None)

    assert core.respostas_do_fornecedor == {}


def test_analyze_sheet_continua_devolvendo_7_elementos(monkeypatch):
    aba = _Aba({"C80": "2 - TENSAO", "M80": "N/A"})
    monkeypatch.setattr(autospec.openpyxl, "load_workbook", lambda *a, **k: _Livro(aba))
    assert len(AutoSpecCore.__new__(AutoSpecCore).analyze_sheet("x.xlsx", None)) == 7


# =============================================================================
# 2. Quando a IA NAO e chamada
# =============================================================================
def test_sem_resposta_do_fornecedor_nao_chama_a_ia():
    core = _core({})
    resultado, _ = _auditar(core, {})
    assert core._llm.chamadas == []
    assert resultado.linhas_de_log() == []


def test_sem_documento_nao_chama_a_ia_e_avisa():
    core = _core({}, documentos=[])
    resultado, linhas = _auditar(core, {"var_row_85": _resp("N/A")}, contexto="\n\n")
    assert core._llm.chamadas == []
    assert resultado.sem_documento
    assert any(n == "warn" and "Sem documento" in m for n, m in linhas)


# =============================================================================
# 3. "Nao se aplica": grava o valor do documento SO com a prova conferida
# =============================================================================
def test_nao_se_aplica_que_o_documento_prova_vira_o_valor_do_documento():
    core = _core({"var_row_85": {
        "situacao": "diverge", "valor_documento": "24 Vcc", "tipo": "documento",
        "fonte": "ds.pdf", "pagina": 1, "trecho": "Supply voltage 24 VDC"}})
    resultado, linhas = _auditar(core, {"var_row_85": _resp("Não se aplica")})

    assert resultado.gravar == {"var_row_85": "24 Vcc"}
    assert resultado.campos == {"var_row_85": {
        "type": "text", "desc": "7 - TENSAO NOMINAL (V)", "ref": "M85"}}
    nota = resultado.notas["var_row_85"]
    assert "'Não se aplica'" in nota and "Supply voltage 24 VDC" in nota and "ds.pdf" in nota
    assert resultado.na_preenchidos == [
        ("7 - TENSAO NOMINAL (V)", "Não se aplica", "24 Vcc", "ds.pdf, pag. 1")]
    assert any("ESTAO no documento" in m for _n, m in linhas)


def test_nao_se_aplica_que_o_documento_nao_traz_fica_como_esta():
    core = _core({"var_row_85": {"situacao": "nao_consta"}})
    resultado, _ = _auditar(core, {"var_row_85": _resp("N/A")})
    assert resultado.gravar == {} and resultado.na_mantidos == 1


def test_nao_se_aplica_confirmado_pela_ia_tambem_fica():
    core = _core({"var_row_85": {"situacao": "confere"}})
    resultado, _ = _auditar(core, {"var_row_85": _resp("N/A")})
    assert resultado.gravar == {} and resultado.na_mantidos == 1


def test_documento_que_tambem_diz_nao_se_aplica_nao_troca_nada():
    core = _core({"var_row_85": {"situacao": "diverge", "valor_documento": "N/A",
                                 "trecho": "Supply voltage 24 VDC"}})
    resultado, _ = _auditar(core, {"var_row_85": _resp("Não aplicável")})
    assert resultado.gravar == {} and resultado.na_mantidos == 1


def test_nao_se_aplica_trocado_por_deducao_nao_entra():
    core = _core({"var_row_85": {"situacao": "diverge", "valor_documento": "Aço inox",
                                 "tipo": "deducao", "justificativa": "valvulas costumam ser"}})
    resultado, _ = _auditar(core, {"var_row_85": _resp("N/A", desc="9 - MATERIAL")})
    assert resultado.gravar == {}
    assert resultado.descartados and "deduc" in resultado.descartados[0][1]


def test_nao_se_aplica_sem_trecho_nao_entra():
    core = _core({"var_row_85": {"situacao": "diverge", "valor_documento": "24 Vcc"}})
    resultado, _ = _auditar(core, {"var_row_85": _resp("N/A")})
    assert resultado.gravar == {} and len(resultado.descartados) == 1


def test_nao_se_aplica_com_trecho_inventado_nao_entra():
    core = _core({"var_row_85": {"situacao": "diverge", "valor_documento": "48 Vcc",
                                 "trecho": "Supply voltage 48 VDC", "fonte": "ds.pdf"}})
    resultado, _ = _auditar(core, {"var_row_85": _resp("N/A")})
    assert resultado.gravar == {} and len(resultado.descartados) == 1


def test_nao_se_aplica_com_texto_cujo_trecho_nao_existe_nao_entra_como_deducao():
    """`_conferir_pela_prova` aceitaria um TEXTO sem trecho como deducao
    marcada. Na conferencia do fornecedor, nao: so documento troca o que ele
    escreveu."""
    core = _core({"var_row_85": {"situacao": "diverge", "valor_documento": "Latão",
                                 "trecho": "Body material brass", "fonte": "ds.pdf"}})
    resultado, _ = _auditar(core, {"var_row_85": _resp("N/A", desc="9 - MATERIAL")})
    assert resultado.gravar == {}


# =============================================================================
# 4. Resposta com valor: divergencia so no log, NADA gravado
# =============================================================================
def test_divergencia_comprovada_vai_para_o_log_e_nao_e_gravada():
    core = _core({"var_row_86": {
        "situacao": "diverge", "valor_documento": "IP65", "fonte": "ds.pdf", "pagina": 1,
        "trecho": "Degree of protection IP65", "justificativa": "grau do invólucro"}})
    resultado, linhas = _auditar(core, {"var_row_86": _resp("IP54", desc="8 - GRAU DE PROTECAO",
                                                           ref="M86")})
    assert resultado.gravar == {} and resultado.campos == {} and resultado.notas == {}
    assert resultado.divergencias == [(
        "8 - GRAU DE PROTECAO", "IP54", "IP65", "ds.pdf, pag. 1",
        "Degree of protection IP65", "grau do invólucro")]
    assert any("NADA foi alterado" in m for _n, m in linhas)


def test_mesma_coisa_em_outra_unidade_nao_e_divergencia():
    core = _core({"var_row_85": {"situacao": "diverge", "valor_documento": "24 VDC",
                                 "trecho": "Supply voltage 24 VDC", "fonte": "ds.pdf"}})
    resultado, _ = _auditar(core, {"var_row_85": _resp("24 Vcc")})
    assert resultado.divergencias == [] and resultado.conferem == 1


def test_divergencia_com_trecho_que_nao_esta_no_documento_e_descartada():
    core = _core({"var_row_86": {"situacao": "diverge", "valor_documento": "IP67",
                                 "trecho": "Degree of protection IP67", "fonte": "ds.pdf"}})
    resultado, _ = _auditar(core, {"var_row_86": _resp("IP54", desc="8 - GRAU")})
    assert resultado.divergencias == [] and len(resultado.descartados) == 1


def test_divergencia_cujo_valor_nao_sai_do_trecho_e_descartada():
    core = _core({"var_row_86": {"situacao": "diverge", "valor_documento": "IP67",
                                 "trecho": "Degree of protection IP65", "fonte": "ds.pdf"}})
    resultado, _ = _auditar(core, {"var_row_86": _resp("IP54", desc="8 - GRAU")})
    assert resultado.divergencias == [] and len(resultado.descartados) == 1


def test_divergencia_sem_valor_ou_sem_trecho_e_descartada():
    core = _core({"var_row_86": {"situacao": "diverge", "valor_documento": "IP65"},
                  "var_row_87": {"situacao": "diverge", "trecho": "Weight 1.2 kg"}})
    resultado, _ = _auditar(core, {"var_row_86": _resp("IP54", ref="M86"),
                                   "var_row_87": _resp("2 kg", ref="M87")})
    assert resultado.divergencias == [] and len(resultado.descartados) == 2


def test_divergencia_tirada_da_linha_de_OUTRO_modelo_e_descartada():
    doc = _doc(paginas=["UCSCH1: 168 x 150 x 55 mm\nUCECH1: 168 x 150 x 85 mm\n"])
    core = _core({"var_row_90": {"situacao": "diverge", "valor_documento": "168 x 150 x 85 mm",
                                 "trecho": "UCECH1: 168 x 150 x 85 mm", "fonte": "ds.pdf"}},
                 documentos=[doc])
    core._modelo_do_item = "UCSCH1"
    resultado, _ = _auditar(core, {"var_row_90": _resp("168 x 150 x 55 mm", desc="DIMENSOES (mm)",
                                                       ref="M90")})
    assert resultado.divergencias == []
    assert "OUTRO modelo" in resultado.descartados[0][1]


def test_confere_e_nao_consta_so_contam():
    core = _core({"var_row_86": {"situacao": "confere"}, "var_row_87": {"situacao": "nao_consta"}})
    resultado, _ = _auditar(core, {"var_row_86": _resp("IP65", ref="M86"),
                                   "var_row_87": _resp("Latão", ref="M87")})
    assert (resultado.conferem, resultado.sem_dado) == (1, 1)
    assert resultado.gravar == {} and resultado.divergencias == []


def test_resposta_que_a_ia_nao_devolveu_conta_como_sem_dado():
    core = _core({})
    resultado, _ = _auditar(core, {"var_row_86": _resp("IP65", ref="M86")})
    assert resultado.sem_dado == 1 and resultado.falha is None


def test_resposta_com_valor_NUNCA_e_gravada_diga_a_ia_o_que_disser():
    """A regra do pedido: *"nao sobrescreva excluindo a informacao preenchida
    pelo fornecedor"*. Mesmo com a prova perfeita."""
    core = _core({campo: {"situacao": "diverge", "valor_documento": "24 Vcc",
                          "trecho": "Supply voltage 24 VDC", "fonte": "ds.pdf"}
                  for campo in ("var_row_85", "var_row_86", "var_row_87")})
    resultado, _ = _auditar(core, {"var_row_85": _resp("12 Vcc", ref="M85"),
                                   "var_row_86": _resp("Nenhum", ref="M86"),
                                   "var_row_87": _resp("Não", ref="M87")})
    assert resultado.gravar == {} and resultado.campos == {}


# =============================================================================
# 5. A chamada: mesmo envio do preenchimento, cache, recusa e falha
# =============================================================================
def test_o_prompt_leva_o_documento_e_a_lista_de_respostas():
    core = _core({"var_row_86": {"situacao": "confere"}})
    _auditar(core, {"var_row_86": _resp("IP65", desc="8 - GRAU DE PROTECAO", ref="M86")})
    prompt = core._llm.chamadas[0]["prompt"]
    assert "Supply voltage 24 VDC" in prompt
    assert "- ID 'var_row_86': 8 - GRAU DE PROTECAO -> o fornecedor respondeu: \"IP65\"" in prompt
    assert core._llm.chamadas[0]["tags"]["tarefa"] == "autospec"


def test_modelo_que_le_pdf_recebe_o_pdf_igual_ao_preenchimento():
    pdf = _doc(mime="application/pdf", dados=b"%PDF-1.4 fake")
    core = _core({"var_row_86": {"situacao": "confere"}}, documentos=[pdf], aceita_pdf=True)
    _auditar(core, {"var_row_86": _resp("IP65", ref="M86")})
    anexos = core._llm.chamadas[0]["anexos"]
    assert anexos and anexos[0].dados == b"%PDF-1.4 fake"


def test_provedor_que_recusa_o_pdf_faz_a_conferencia_cair_para_o_texto():
    pdf = _doc(mime="application/pdf", dados=b"%PDF-1.4 fake")
    core = _core({"var_row_86": {"situacao": "confere"}}, documentos=[pdf], aceita_pdf=True,
                 falhas=[RuntimeError("413 payload too large")])
    resultado, linhas = _auditar(core, {"var_row_86": _resp("IP65", ref="M86")})
    assert len(core._llm.chamadas) == 2
    assert not core._llm.chamadas[1]["anexos"]
    assert "Supply voltage 24 VDC" in core._llm.chamadas[1]["prompt"]
    assert resultado.falha is None and resultado.conferem == 1


def test_timeout_vira_falha_avisada_sem_derrubar_nada():
    core = _core({}, falhas=[ReadTimeout("read timed out")])
    resultado, linhas = _auditar(core, {"var_row_86": _resp("IP65", ref="M86")})
    assert resultado.falha and "ReadTimeout" in resultado.falha
    assert len(core._llm.chamadas) == 1
    assert any(n == "warn" and "conferencia das respostas do fornecedor falhou" in m.lower()
               for n, m in linhas)


def test_resposta_fora_do_formato_vira_falha():
    core = _core(["confere"])
    resultado, _ = _auditar(core, {"var_row_86": _resp("IP65", ref="M86")})
    assert resultado.falha and "objeto JSON" in resultado.falha


def test_a_segunda_vez_sai_do_cache_sem_chamar_a_ia(monkeypatch, tmp_path):
    monkeypatch.setattr(autospec, "_caminho_cache_resposta", lambda: str(tmp_path / "c.json"))
    core = _core({"var_row_86": {"situacao": "confere"}})
    core.usar_cache_resposta = True
    _auditar(core, {"var_row_86": _resp("IP65", ref="M86")})
    resultado, linhas = _auditar(core, {"var_row_86": _resp("IP65", ref="M86")})
    assert len(core._llm.chamadas) == 1
    assert resultado.conferem == 1
    assert any("cache" in m for _n, m in linhas)


# =============================================================================
# 6. Pagina sem texto (PDF-imagem): a prova nao tem onde ser conferida
# =============================================================================
def _pdf_imagem():
    """PDF de uma pagina sem camada de texto: a IA leu a imagem."""
    return _doc(paginas=[""], mime="application/pdf", dados=b"%PDF-1.4 imagem")


def test_nao_se_aplica_lido_em_pagina_sem_texto_nao_e_trocado():
    core = _core({"var_row_85": {"situacao": "diverge", "valor_documento": "24 Vcc",
                                 "trecho": "Supply voltage 24 VDC", "fonte": "ds.pdf",
                                 "pagina": 1}},
                 documentos=[_pdf_imagem()], aceita_pdf=True)
    resultado, _ = _auditar(core, {"var_row_85": _resp("N/A")}, contexto="")
    assert resultado.gravar == {}
    assert "pagina sem texto" in resultado.descartados[0][1]


def test_divergencia_lida_em_pagina_sem_texto_vai_para_o_log_marcada():
    core = _core({"var_row_86": {"situacao": "diverge", "valor_documento": "IP65",
                                 "trecho": "Degree of protection IP65", "fonte": "ds.pdf",
                                 "pagina": 1}},
                 documentos=[_pdf_imagem()], aceita_pdf=True)
    resultado, _ = _auditar(core, {"var_row_86": _resp("IP54", ref="M86")}, contexto="")
    assert resultado.gravar == {}
    assert len(resultado.divergencias) == 1
    assert "pagina sem texto, confira nela" in resultado.divergencias[0][3]

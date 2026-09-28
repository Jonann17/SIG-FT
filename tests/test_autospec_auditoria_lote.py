r"""A conferencia das respostas do fornecedor dentro do LOTE (2026-09-28).

`process_queue` e `processar_conferidos`, com os metodos pesados dublados --
mesmo andaime de tests/test_autospec_relatorio_lote.py. O que se prova aqui:

- ficha sem campo vazio, com resposta do fornecedor, deixa de ser pulada;
- o que a conferencia grava entra no MESMO `fill_save` do preenchimento;
- sem nada a gravar, nenhum `_completed` e criado;
- interruptor desligado = o comportamento de antes, inteiro;
- falha da conferencia nao derruba o preenchimento;
- nenhuma resposta com valor do fornecedor chega ao `fill_save`.
"""
from sigft.services import autospec_auditoria as aud
from sigft.services.autospec import AutoSpecCore

RESPOSTAS = {
    "var_row_85": {"desc": "7 - TENSAO", "ref": "M85", "resposta": "N/A", "nao_se_aplica": True},
    "var_row_86": {"desc": "8 - GRAU", "ref": "M86", "resposta": "IP54", "nao_se_aplica": False},
}
FALTANTE = {"var_row_80": {"type": "text", "desc": "2 - MATERIAL", "ref": "M80"}}


def _resultado(gravar=False, divergencia=False, falha=None, sem_documento=False):
    r = aud.ResultadoAuditoria(falha=falha, sem_documento=sem_documento)
    if gravar:
        r.gravar = {"var_row_85": "24 Vcc"}
        r.campos = {"var_row_85": {"type": "text", "desc": "7 - TENSAO", "ref": "M85"}}
        r.notas = {"var_row_85": "AutoSpec: o fornecedor respondeu 'N/A'..."}
        r.na_preenchidos = [("7 - TENSAO", "N/A", "24 Vcc", "ds.pdf, pag. 1")]
    if divergencia:
        r.divergencias = [("8 - GRAU", "IP54", "IP65", "ds.pdf", "IP65", "")]
    return r


def _core(missing, respostas, auditoria=None, ai_resp=None, notas_do_preenchimento=None):
    """`auditoria`: o `ResultadoAuditoria` que a conferencia dublada devolve."""
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.chamadas = {"auditar": [], "fill_save": [], "gerar": 0}

    def _analyze(ficha, status):
        core.respostas_do_fornecedor = dict(respostas)
        return "wb", dict(missing), "txt", "fab", "desc", "cod", ""

    def _gerar(*a, **k):
        core.chamadas["gerar"] += 1
        core.notas_por_campo = dict(notas_do_preenchimento or {})
        return dict(ai_resp or {})

    def _auditar(txt, fab, desc, resp, ctx, callbacks=None):
        core.chamadas["auditar"].append(dict(resp))
        return auditoria if auditoria is not None else aud.ResultadoAuditoria()

    def _fill_save(wb, ficha, ai_data, missing, **k):
        core.chamadas["fill_save"].append(
            {"ai_data": dict(ai_data), "missing": dict(missing),
             "notas": dict(getattr(core, "notas_por_campo", None) or {})})
        return ficha.replace(".xlsx", "_completed.xlsx")

    core.analyze_sheet = _analyze
    core.retrieve_context = lambda *a, **k: ("contexto", [])
    core.generate_ai_response = _gerar
    core.auditar_respostas_do_fornecedor = _auditar
    core.fill_save = _fill_save
    return core


def _rodar(core):
    return "\n".join(core.process_queue([{"sheet": "A.xlsx", "refs": []}], status_pmib_path=None))


def test_ficha_completa_com_resposta_do_fornecedor_e_conferida_e_nao_pulada():
    core = _core({}, RESPOSTAS, auditoria=_resultado(divergencia=True))
    texto = _rodar(core)
    assert "Ficha já está completa" not in texto
    assert core.chamadas["auditar"] == [RESPOSTAS]
    assert core.chamadas["gerar"] == 0


def test_ficha_completa_sem_nada_a_gravar_nao_gera_completed():
    core = _core({}, RESPOSTAS, auditoria=_resultado(divergencia=True))
    texto = _rodar(core)
    assert core.chamadas["fill_save"] == []
    assert "nao foi alterada" in texto
    assert "conferida: 1 divergencia(s) no log" in texto
    assert "1 sucesso(s)" in texto


def test_ficha_completa_com_nao_se_aplica_corrigido_gera_completed():
    core = _core({}, RESPOSTAS, auditoria=_resultado(gravar=True))
    _rodar(core)
    [salvo] = core.chamadas["fill_save"]
    assert salvo["ai_data"] == {"var_row_85": "24 Vcc"}
    assert salvo["missing"] == {"var_row_85": {"type": "text", "desc": "7 - TENSAO", "ref": "M85"}}
    assert salvo["notas"] == {"var_row_85": "AutoSpec: o fornecedor respondeu 'N/A'..."}


def test_ficha_completa_nao_herda_nota_da_ficha_anterior():
    core = _core({}, RESPOSTAS, auditoria=_resultado(gravar=True))
    core.notas_por_campo = {"var_row_85": "nota velha", "var_row_99": "outra velha"}
    _rodar(core)
    assert core.chamadas["fill_save"][0]["notas"] == {
        "var_row_85": "AutoSpec: o fornecedor respondeu 'N/A'..."}


def test_preenchimento_e_conferencia_saem_no_mesmo_fill_save():
    core = _core(FALTANTE, RESPOSTAS, auditoria=_resultado(gravar=True),
                 ai_resp={"var_row_80": "Latão"},
                 notas_do_preenchimento={"var_row_80": "AutoSpec: deducao"})
    _rodar(core)
    [salvo] = core.chamadas["fill_save"]
    assert salvo["ai_data"] == {"var_row_80": "Latão", "var_row_85": "24 Vcc"}
    assert set(salvo["missing"]) == {"var_row_80", "var_row_85"}
    assert salvo["notas"] == {"var_row_80": "AutoSpec: deducao",
                              "var_row_85": "AutoSpec: o fornecedor respondeu 'N/A'..."}


def test_nenhuma_resposta_com_valor_chega_ao_fill_save():
    core = _core(FALTANTE, RESPOSTAS, auditoria=_resultado(gravar=True, divergencia=True),
                 ai_resp={"var_row_80": "Latão"})
    _rodar(core)
    for salvo in core.chamadas["fill_save"]:
        assert "var_row_86" not in salvo["ai_data"]
        assert "var_row_86" not in salvo["missing"]


def test_interruptor_desligado_e_o_comportamento_de_antes():
    core = _core({}, RESPOSTAS, auditoria=_resultado(gravar=True))
    core.auditar_fornecedor = False
    texto = _rodar(core)
    assert "Ficha já está completa" in texto
    assert core.chamadas["auditar"] == [] and core.chamadas["fill_save"] == []


def test_ficha_completa_sem_resposta_do_fornecedor_continua_pulada():
    core = _core({}, {})
    texto = _rodar(core)
    assert "Ficha já está completa" in texto
    assert core.chamadas["auditar"] == []


def test_falha_da_conferencia_nao_derruba_o_preenchimento():
    core = _core(FALTANTE, RESPOSTAS, auditoria=_resultado(falha="ReadTimeout: x"),
                 ai_resp={"var_row_80": "Latão"})
    texto = _rodar(core)
    [salvo] = core.chamadas["fill_save"]
    assert salvo["ai_data"] == {"var_row_80": "Latão"}
    assert "1 sucesso(s)" in texto and "0 falha(s)" in texto


def test_ficha_so_de_conferencia_que_falhou_conta_como_falha():
    core = _core({}, RESPOSTAS, auditoria=_resultado(falha="ReadTimeout: x"))
    texto = _rodar(core)
    assert core.chamadas["fill_save"] == []
    assert "conferencia das respostas do fornecedor falhou" in texto
    assert "0 sucesso(s)" in texto and "1 falha(s)" in texto


def test_ficha_so_de_conferencia_sem_documento_conta_como_pulada():
    core = _core({}, RESPOSTAS, auditoria=_resultado(sem_documento=True))
    texto = _rodar(core)
    assert core.chamadas["fill_save"] == []
    assert "sem documento para conferir" in texto
    assert "1 pulado(s)" in texto


def test_o_lote_anuncia_quantas_respostas_vai_conferir():
    core = _core(FALTANTE, RESPOSTAS, ai_resp={"var_row_80": "Latão"})
    texto = _rodar(core)
    assert "Conferindo 2 resposta(s) do fornecedor" in texto


# =============================================================================
# 2a passada: regrava o `_completed`, entao confere tambem
# =============================================================================
class _Conferencia:
    def pendencia_da_ficha(self, ficha):
        return None


def _segunda_passada(core):
    core.conferencia = _Conferencia()
    core.contexto_das_urls = lambda urls, refs, callbacks=None: "documento aprovado"
    return "\n".join(core.processar_conferidos({"A.xlsx": ["https://x/ds.pdf"]}, None))


def test_segunda_passada_confere_as_respostas_do_fornecedor():
    core = _core({}, RESPOSTAS, auditoria=_resultado(gravar=True))
    _segunda_passada(core)
    assert core.chamadas["auditar"] == [RESPOSTAS]
    [salvo] = core.chamadas["fill_save"]
    assert salvo["ai_data"] == {"var_row_85": "24 Vcc"}


def test_segunda_passada_mescla_com_o_preenchimento():
    core = _core(FALTANTE, RESPOSTAS, auditoria=_resultado(gravar=True),
                 ai_resp={"var_row_80": "Latão"})
    _segunda_passada(core)
    [salvo] = core.chamadas["fill_save"]
    assert salvo["ai_data"] == {"var_row_80": "Latão", "var_row_85": "24 Vcc"}


def test_segunda_passada_sem_resposta_e_sem_faltante_continua_pulada():
    core = _core({}, {})
    texto = _segunda_passada(core)
    assert "Ficha já está completa" in texto and core.chamadas["auditar"] == []

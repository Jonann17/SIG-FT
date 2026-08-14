r"""Lastro documental: nenhum valor entra na ficha sem estar no documento.
Ver `docs/superpowers/specs/2026-08-13-lastro-documental-design.md`.

**Pedido do usuário, 2026-08-13:** "não gostei do ato de aceitar uma
informação errada. Isto não deve acontecer."

O que o código PODE garantir, e é o que estes testes guardam: **todo valor
escrito num campo técnico aparece literalmente no documento que foi lido**.
Se a IA responder um número que não está em lugar nenhum do contexto, o
campo fica VAZIO e o console diz qual foi e por quê.

O que o código NÃO pode garantir é "correto" no sentido de engenharia — se o
próprio datasheet estiver errado, ou se o documento for de outra peça, o
valor tem lastro e ainda assim está errado. Por isso o lastro é a segunda
camada; a primeira é o filtro anti-intruso (§4.3), e a terceira é a
conferência humana com a lista de origens.

**Exceção deliberada:** os 12 `GENERATIVE_FIELDS` (embalagem, transporte,
descarte…) existem justamente para serem gerados de conhecimento técnico —
as regras de negócio §3.2 pedem isso. Eles não têm datasheet de onde sair, e
por isso são separados e rotulados no console em vez de descartados.
"""
import pytest

from sigft import config
from sigft.services import autospec
from sigft.services.autospec import AutoSpecCore


CONTEXTO = (
    "--- LOCAL DOC: manual_hydac.pdf ---\n"
    "Maximum operating pressure 175 bar. Peak pressure 210 bar.\n"
    "Net weight 41 kg. Operating temperature range 0 to +70 C.\n"
    "Enclosure rating IP55. Seal material NBR (Nitrile).\n"
    "Shaft diameter 25.4 mm.\n"
)


# =============================================================================
# A. O que tem lastro e o que não tem
# =============================================================================
@pytest.mark.parametrize(
    "valor,tem_lastro,caso",
    [
        ("175 bar", True, "copiado do documento"),
        ("41 kg", True, "idem"),
        ("IP55", True, "codigo alfanumerico presente"),
        ("NBR", True, "palavra presente"),
        ("0 a +70 C", True, "numeros presentes, texto traduzido"),
        ("25,4 mm", True, "virgula decimal vs ponto no documento"),
        ("999 bar", False, "numero que NAO existe no documento"),
        ("175 bar a 300 bar", False, "um numero certo e outro inventado"),
        ("0,4 MPa", False, "conversao de unidade: 0.4 nao esta no documento"),
        ("Aco inoxidavel 316", False, "material que o documento nao cita"),
        ("", True, "vazio nao precisa de lastro"),
        ("N/A", True, "marcador curto, sem numero nem palavra longa"),
    ],
)
def test_lastro_de_um_valor(valor, tem_lastro, caso):
    assert autospec.valor_tem_lastro(valor, CONTEXTO) is tem_lastro, caso


def test_TODO_numero_respondido_precisa_estar_no_documento():
    """A regra mais importante: basta UM número inventado para o campo cair.
    Meia verdade num campo técnico é pior que campo vazio, porque passa na
    conferência por olhar certo."""
    assert autospec.valor_tem_lastro("entre 175 e 999 bar", CONTEXTO) is False


def test_sem_contexto_nada_tem_lastro():
    """Ficha sem documento nenhum: campo técnico não pode ser preenchido."""
    assert autospec.valor_tem_lastro("175 bar", "") is False


# =============================================================================
# B. O filtro aplicado à resposta inteira
# =============================================================================
def _core():
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.ultimas_fontes_por_campo = {}
    return core


def _cb():
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append((nivel, str(msg)))

    return _CB(), registro


CAMPOS = {
    "var_row_79": {"type": "text", "desc": "6 - PRESSAO", "ref": "M79"},
    "var_row_80": {"type": "text", "desc": "Peso", "ref": "M80"},
}


def test_campo_tecnico_sem_lastro_e_DESCARTADO():
    core = _core()
    cb, registro = _cb()
    valores = core._filtrar_por_lastro(
        {"var_row_79": "999 bar", "var_row_80": "41 kg"}, CAMPOS, CONTEXTO, cb
    )
    assert "var_row_79" not in valores, "valor sem lastro entrou na ficha"
    assert valores["var_row_80"] == "41 kg"


def test_o_descarte_NAO_e_silencioso():
    """O engenheiro precisa saber o que ficou faltando para buscar à mão."""
    core = _core()
    cb, registro = _cb()
    core._filtrar_por_lastro({"var_row_79": "999 bar"}, CAMPOS, CONTEXTO, cb)
    graves = [m for n, m in registro if n in ("warn", "error")]
    assert graves, "descarte passou em silencio"
    assert any("999 bar" in m for m in graves), "precisa dizer QUAL valor caiu"
    assert any("6 - PRESSAO" in m for m in graves), "precisa dizer QUAL campo"


def test_campo_gerado_por_conhecimento_tecnico_NAO_e_descartado():
    """Os 12 GENERATIVE_FIELDS existem para ser gerados — regras §3.2. Exigir
    lastro deles esvaziaria metade da ficha por desenho."""
    core = _core()
    cb, _ = _cb()
    campos = {"empilhamento": {"type": "text", "desc": "Empilhamento", "ref": "M42"}}
    valores = core._filtrar_por_lastro({"empilhamento": "5"}, campos, CONTEXTO, cb)
    assert valores["empilhamento"] == "5"


def test_todos_os_GENERATIVE_FIELDS_sao_isentos():
    core = _core()
    cb, _ = _cb()
    campos = {c: {"type": "text", "desc": c, "ref": "M1"} for c in autospec.GENERATIVE_FIELDS}
    entrada = {c: "valor inventado que nao esta no documento" for c in autospec.GENERATIVE_FIELDS}
    assert core._filtrar_por_lastro(entrada, campos, CONTEXTO, cb) == entrada


def test_sem_contexto_os_campos_tecnicos_ficam_todos_vazios():
    """Ficha sem documento: os campos técnicos não podem ser 'preenchidos'
    pelo conhecimento do modelo, porque não há como conferir."""
    core = _core()
    cb, registro = _cb()
    valores = core._filtrar_por_lastro(
        {"var_row_79": "175 bar", "var_row_80": "41 kg"}, CAMPOS, "", cb
    )
    assert valores == {}


# =============================================================================
# C. Fonte citada tem de ser um documento que existiu
# =============================================================================
def test_origens_reais_saem_do_contexto():
    origens = autospec.origens_do_contexto(
        "--- LOCAL DOC: manual.pdf ---\ntexto\n--- WEB DOC: https://x.com/ds.pdf ---\nmais"
    )
    assert origens == {"manual.pdf", "https://x.com/ds.pdf"}


def test_fonte_inventada_e_denunciada():
    """A IA citando um documento que nunca existiu é sinal de invenção — e o
    engenheiro precisa saber antes de homologar."""
    core = _core()
    cb, registro = _cb()
    core.ultimas_fontes_por_campo = {"var_row_79": "https://site-que-nao-existe.com/x.pdf"}
    core._conferir_fontes_citadas(CONTEXTO, cb)
    graves = [m for n, m in registro if n in ("warn", "error")]
    assert any("site-que-nao-existe" in m for m in graves)


def test_fonte_de_conhecimento_tecnico_nao_e_denunciada():
    core = _core()
    cb, registro = _cb()
    core.ultimas_fontes_por_campo = {"empilhamento": "conhecimento tecnico"}
    core._conferir_fontes_citadas(CONTEXTO, cb)
    assert not [m for n, m in registro if n in ("warn", "error")]


def test_fonte_real_nao_e_denunciada():
    core = _core()
    cb, registro = _cb()
    core.ultimas_fontes_por_campo = {"var_row_79": "manual_hydac.pdf"}
    core._conferir_fontes_citadas(CONTEXTO, cb)
    assert not [m for n, m in registro if n in ("warn", "error")]


# =============================================================================
# D. Integração — o caminho vivo e o do cache tratam igual
# =============================================================================
class _LLMFake:
    def __init__(self, parsed):
        self.parsed = parsed
        self.chamadas = 0

    def generate(self, prompt, *, system=None, json_mode=False, tags=None):
        self.chamadas += 1

        class R:
            parsed_json = self.parsed
            text = ""

        return R()


def _core_completo(parsed):
    core = AutoSpecCore(
        gemini_key="fake", llama_key=None, google_search_key=None, google_cse_id=None,
        selecao_resolvida={"provider": config.PROVIDER_GEMINI, "model": "m"},
    )
    core._llm = _LLMFake(parsed)
    return core


def test_o_caminho_vivo_descarta_valor_sem_lastro():
    core = _core_completo({"var_row_79": "999 bar", "var_row_80": "41 kg"})
    resultado = core.generate_ai_response("Bomba", "KSB", "Desc", CAMPOS, CONTEXTO)
    assert "var_row_79" not in resultado
    assert resultado.get("var_row_80") == "41 kg"


def test_o_caminho_do_CACHE_descarta_igual():
    """Um acerto de cache não pode ser uma porta de entrada para valor sem
    lastro — as duas rotas passam pela mesma verificação."""
    core = _core_completo({"var_row_79": "999 bar", "var_row_80": "41 kg"})
    primeiro = core.generate_ai_response("Bomba", "KSB", "Desc", CAMPOS, CONTEXTO)
    segundo = core.generate_ai_response("Bomba", "KSB", "Desc", CAMPOS, CONTEXTO)
    assert core._llm.chamadas == 1, "devia ter batido no cache"
    assert segundo == primeiro
    assert "var_row_79" not in segundo


def test_desligar_o_lastro_e_possivel_mas_nao_e_o_padrao():
    """Escape para diagnóstico. O padrão é exigir lastro."""
    core = _core_completo({"var_row_79": "999 bar"})
    assert core.exigir_lastro is True
    core.exigir_lastro = False
    assert core.generate_ai_response("B", "K", "D", CAMPOS, CONTEXTO) == {"var_row_79": "999 bar"}

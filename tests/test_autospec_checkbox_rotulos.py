r"""
Testes do P-01 (checkbox por rótulo) e do P-07 (leitura com `data_only`).
Ver docs/AUTOSPEC_MELHORIAS.md.

O problema do P-01 não era a IA "responder errado" — era o prompt oferecer
`['G25','G27','G29']`, endereços de célula que não dizem NADA a um modelo de
linguagem. Mesmo um acerto era chute entre 3 opções, e a resposta que não
casasse era descartada em silêncio.

A correção não depende de saber o que o modelo devolve hoje: o rótulo legível
("Vertical") é lido da própria planilha e oferecido no prompt, e `fill_save`
aceita **rótulo E endereço**. Funciona nos dois mundos.
"""
import pytest

import autospec_backend
from sigft import config
from sigft.core.callbacks import UICallbacks

AutoSpecCore = autospec_backend.AutoSpecCore


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json")
    )


# =============================================================================
# A. Extração do rótulo a partir da planilha
# =============================================================================
class _CelulaFake:
    def __init__(self, coordinate, value):
        self.coordinate = coordinate
        self.value = value


class _PlanilhaFake:
    """Worksheet mínima endereçada por (linha, coluna), como a real."""

    def __init__(self, valores):
        self._valores = valores  # {"H27": "Horizontal", ...}

    def cell(self, row, column):
        letras = ""
        c = column
        while c > 0:
            c, resto = divmod(c - 1, 26)
            letras = chr(ord("A") + resto) + letras
        coord = f"{letras}{row}"
        return _CelulaFake(coord, self._valores.get(coord))


def test_rotulo_a_direita_na_mesma_linha():
    """Disposição de 7 dos 9 grupos da ficha real."""
    ws = _PlanilhaFake({"H25": "Vertical", "H27": "Horizontal", "H29": "Indiferente"})
    assert AutoSpecCore._rotulos_do_checkbox(ws, ["G25", "G27", "G29"]) == {
        "G25": "Vertical",
        "G27": "Horizontal",
        "G29": "Indiferente",
    }


def test_rotulo_na_linha_de_cabecalho_acima():
    """Disposição dos 2 grupos da linha 69 (periculosidade / log. reversa):
    o rótulo fica na linha 68, à esquerda da coluna da marca."""
    ws = _PlanilhaFake({"D68": "Classe I - Perigoso", "H68": "Classe II – Não perigoso"})
    assert AutoSpecCore._rotulos_do_checkbox(ws, ["E69", "J69"]) == {
        "E69": "Classe I - Perigoso",
        "J69": "Classe II – Não perigoso",
    }


def test_marca_de_outro_grupo_nao_e_confundida_com_rotulo():
    """`J69` fica a 6 colunas de `P69`. Sem excluir as células de marcação
    conhecidas, a varredura à direita devolvia `"x"` como se fosse rótulo —
    erro observado na ficha real antes da correção."""
    ws = _PlanilhaFake({"P69": "x", "H68": "Classe II – Não perigoso"})
    assert AutoSpecCore._rotulos_do_checkbox(ws, ["J69"]) == {
        "J69": "Classe II – Não perigoso"
    }


def test_x_solto_nunca_vira_rotulo():
    ws = _PlanilhaFake({"H25": "x", "I25": "Vertical"})
    assert AutoSpecCore._rotulos_do_checkbox(ws, ["G25"]) == {"G25": "Vertical"}


def test_sem_rotulo_encontravel_a_celula_fica_de_fora():
    assert AutoSpecCore._rotulos_do_checkbox(_PlanilhaFake({}), ["G25"]) == {}


def test_worksheet_sem_cell_nao_derruba_a_analise():
    """Rótulo é enriquecimento opcional: worksheet duck-typed mais magra
    (fakes antigos) só perde o bônus, não quebra."""
    class _Magra: pass
    assert AutoSpecCore._rotulos_checkbox_seguro(_Magra(), ["G25"]) == {}


def test_erro_inesperado_na_leitura_de_rotulo_e_engolido():
    class _Explode:
        def cell(self, row, column): raise RuntimeError("planilha atípica")
    assert AutoSpecCore._rotulos_checkbox_seguro(_Explode(), ["G25"]) == {}


# =============================================================================
# B. Resolução da resposta da IA -> célula
# =============================================================================
INFO = {
    "type": "checkbox",
    "desc": "Posição de armazenamento",
    "options": ["G25", "G27", "G29"],
    "rotulos": {"G25": "Vertical", "G27": "Horizontal", "G29": "Indiferente"},
}


@pytest.mark.parametrize(
    "resposta,esperado,caso",
    [
        ("G27", "G27", "endereço de célula (forma antiga, preservada)"),
        ("g27", "G27", "endereço em minúsculas"),
        (" G27 ", "G27", "endereço com espaços"),
        ("Horizontal", "G27", "rótulo exato"),
        ("horizontal", "G27", "rótulo sem caixa"),
        ("HORIZONTAL", "G27", "rótulo em maiúsculas"),
        ("Indiferente.", "G29", "rótulo com pontuação"),
        ("Armazenar na posição horizontal", "G27", "rótulo dentro de frase"),
    ],
)
def test_respostas_que_devem_casar(resposta, esperado, caso):
    assert AutoSpecCore._resolver_celula_checkbox(resposta, INFO) == esperado, caso


def test_acento_nao_impede_o_casamento():
    info = {
        "type": "checkbox",
        "options": ["S10", "S12"],
        "rotulos": {"S10": "Reparável", "S12": "Não reparável"},
    }
    assert AutoSpecCore._resolver_celula_checkbox("NAO REPARAVEL", info) == "S12"
    assert AutoSpecCore._resolver_celula_checkbox("Não Reparável", info) == "S12"


@pytest.mark.parametrize("resposta", [None, "", "   ", "Sim", "Talvez", "Z99"])
def test_respostas_que_nao_devem_casar(resposta):
    assert AutoSpecCore._resolver_celula_checkbox(resposta, INFO) is None


def test_contencao_ambigua_nao_escolhe_no_chute():
    """Se a resposta contém DOIS rótulos, não dá para saber qual o usuário
    queria — melhor deixar em branco e avisar do que marcar o errado
    (regras de negócio §1.3: dado incorreto é pior que campo vazio)."""
    info = {
        "type": "checkbox",
        "options": ["A1", "A2"],
        "rotulos": {"A1": "Vertical", "A2": "Vertical ou Horizontal"},
    }
    assert AutoSpecCore._resolver_celula_checkbox("Vertical", info) == "A1"  # exato vence
    assert AutoSpecCore._resolver_celula_checkbox("pode ser Vertical ou Horizontal mesmo", info) is None


def test_sem_rotulos_ainda_aceita_endereco():
    """Compatibilidade total com o comportamento anterior: planilha sem
    rótulo legível continua funcionando pelo endereço."""
    info = {"type": "checkbox", "options": ["G25", "G27"], "rotulos": {}}
    assert AutoSpecCore._resolver_celula_checkbox("G25", info) == "G25"
    assert AutoSpecCore._resolver_celula_checkbox("Vertical", info) is None


# =============================================================================
# C. O prompt oferece rótulo quando existe
# =============================================================================
class _LLMCaptura:
    def __init__(self): self.prompt = None
    def generate(self, prompt, **kw):
        self.prompt = prompt
        class R: parsed_json = {}
        return R()


def _core_com_captura():
    core = AutoSpecCore(
        gemini_key="fake", llama_key=None, google_search_key=None, google_cse_id=None,
        selecao_resolvida={"provider": config.PROVIDER_GEMINI, "model": "m"},
    )
    captura = _LLMCaptura()
    core._llm = captura
    return core, captura


def test_prompt_oferece_rotulos_quando_a_planilha_os_tem():
    core, captura = _core_com_captura()
    core.generate_ai_response("Bomba", "KSB", "Desc", {"posicao_armazenamento": INFO}, "ctx")
    assert "Vertical" in captura.prompt
    assert "Horizontal" in captura.prompt
    assert "G25" not in captura.prompt, "endereço de célula não ajuda o modelo"


def test_prompt_cai_para_enderecos_quando_falta_rotulo():
    core, captura = _core_com_captura()
    info_parcial = dict(INFO, rotulos={"G25": "Vertical"})  # incompleto
    core.generate_ai_response("Bomba", "KSB", "Desc", {"posicao_armazenamento": info_parcial}, "ctx")
    assert "G25" in captura.prompt, "sem rótulo para todas as opções, volta ao endereço"


# =============================================================================
# D. Descarte deixou de ser silencioso
# =============================================================================
class _WsEscrita:
    def __init__(self): self.valores = {}
    def __getitem__(self, ref):
        ws = self
        class _Cel:
            @property
            def value(self): return ws.valores.get(ref)
            @value.setter
            def value(self, v): ws.valores[ref] = v
            font = None
        return _Cel()


class _WbFake:
    def __init__(self): self.ws = _WsEscrita(); self.salvo_em = None
    def __getitem__(self, nome): return self.ws
    def save(self, caminho): self.salvo_em = caminho


def _fill(ai_data, info=INFO):
    core = AutoSpecCore(
        gemini_key="fake", llama_key=None, google_search_key=None, google_cse_id=None,
        selecao_resolvida={"provider": config.PROVIDER_GEMINI, "model": "m"},
    )
    wb = _WbFake()
    linhas = []
    cb = UICallbacks(log=lambda m, nivel="info", contexto=None: linhas.append((str(m), nivel)))
    core.fill_save(wb, "ficha.xlsx", ai_data, {"posicao_armazenamento": info}, callbacks=cb)
    return wb, linhas


def test_rotulo_marca_a_celula_certa_e_limpa_as_outras():
    wb, _ = _fill({"posicao_armazenamento": "Horizontal"})
    assert wb.ws.valores["G27"] == "X"
    assert wb.ws.valores["G25"] is None and wb.ws.valores["G29"] is None


def test_resposta_nao_reconhecida_gera_AVISO_em_vez_de_silencio():
    """O coração do P-01: antes, isto não escrevia nada e não dizia nada."""
    wb, linhas = _fill({"posicao_armazenamento": "Sim"})
    assert "G25" not in wb.ws.valores or wb.ws.valores.get("G25") != "X"
    texto = " ".join(m for m, _ in linhas)
    assert "Sim" in texto and "posicao_armazenamento" in texto
    assert "warn" in {n for _, n in linhas}


def test_resumo_final_conta_os_checkboxes_nao_casados():
    _, linhas = _fill({"posicao_armazenamento": "Talvez"})
    assert any("1 checkbox" in m for m, _ in linhas)

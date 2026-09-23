r"""A PARADA GERAL — o botão da home que interrompe o que estiver rodando.

Pedido do usuário (2026-09-23): *"Preciso de um botão na home para interromper
quando precisar sair sem finalizar a lista e salvar como completo somente
aqueles que de fato concluíram"*.

A segunda metade já funcionava antes deste trabalho: `processar_lista` dá
`break` no `deve_parar()` e devolve `pmibs_finalizados`, então quem marca
COMPLETO no `_STATUS_PMIB` já recebia só as fichas concluídas. O que faltava
era o **botão único**: até aqui a parada morava dentro de cada tela (`PARAR
ROBÔ WEB`), e quem estivesse na home precisava lembrar em qual tela o robô
tinha sido disparado.

A regra do `CLAUDE.md` (princípio 2: "UI nunca contém regra de negócio") é o
motivo de a varredura morar aqui, num módulo importável, e não dentro de
`SIG_FT_App` -- lá ela só poderia ser conferida por AST.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from sigft.app import parada

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VIEWS = RAIZ / "sigft" / "app" / "views"
MAIN = RAIZ / "sigft" / "app" / "main.py"
HOME = VIEWS / "home.py"


class TelaQuePara:
    def __init__(self, rotulos=("robô web",)):
        self.rotulos = list(rotulos)
        self.chamadas = 0

    def interromper_tudo(self):
        self.chamadas += 1
        return list(self.rotulos)


class TelaParada:
    """Tela sem nada rodando: existe o método, mas não há o que parar."""

    def interromper_tudo(self):
        return []


class TelaSemParada:
    """Tela que não tem automação nenhuma (a home, por exemplo)."""


class TelaQuebrada:
    def interromper_tudo(self):
        raise RuntimeError("estourei")


# =============================================================================
# A varredura
# =============================================================================
def test_pede_parada_a_toda_tela_que_saiba_parar():
    a, b = TelaQuePara(["IA"]), TelaQuePara(["robô web"])

    parados = parada.parar_tudo({"A": a, "B": b, "C": TelaSemParada()})

    assert a.chamadas == 1 and b.chamadas == 1
    assert sorted(parados) == ["IA", "robô web"]


def test_tela_sem_o_metodo_e_simplesmente_pulada():
    """A maioria das telas não tem automação; não é erro, é o normal."""
    assert parada.parar_tudo({"Home": TelaSemParada()}) == []


def test_tela_sem_nada_rodando_nao_entra_no_relatorio():
    """Só aparece no aviso o que de fato recebeu o sinal."""
    assert parada.parar_tudo({"A": TelaParada()}) == []


def test_uma_tela_quebrada_NAO_impede_a_parada_das_outras():
    """⚠️ O teste que justifica o `try` do módulo.

    O botão de pânico é exatamente o que se aperta quando alguma coisa já está
    estranha. Se a tela A estourasse ao ser avisada, o robô da tela B seguiria
    rodando -- e o usuário apertou o botão justamente para sair.
    """
    boa = TelaQuePara(["robô web"])

    parados = parada.parar_tudo({"A": TelaQuebrada(), "B": boa})

    assert boa.chamadas == 1
    assert parados == ["robô web"]


def test_o_que_a_tela_devolve_de_estranho_nao_derruba_a_varredura():
    class TelaTagarela:
        def interromper_tudo(self):
            return "robô web"   # str, não lista

    assert parada.parar_tudo({"A": TelaTagarela()}) == ["robô web"]


def test_frames_vazio_nao_e_erro():
    assert parada.parar_tudo({}) == []


def test_aceita_qualquer_colecao_de_telas():
    """`SIG_FT_App.frames` é um dict, mas a varredura não depende disso."""
    assert parada.parar_tudo([TelaQuePara(["IA"])]) == ["IA"]


def test_a_ordem_dos_rotulos_segue_a_ordem_das_telas():
    parados = parada.parar_tudo([TelaQuePara(["IA"]), TelaQuePara(["robô web"])])
    assert parados == ["IA", "robô web"]


def test_rotulo_repetido_aparece_uma_vez_so():
    """Duas telas com o robô web parado viram um aviso, não dois."""
    parados = parada.parar_tudo([TelaQuePara(["robô web"]), TelaQuePara(["robô web"])])
    assert parados == ["robô web"]


def test_o_modulo_da_parada_nao_importa_tkinter():
    """Princípio 2 do `CLAUDE.md`, ao contrário: a regra não conhece a UI."""
    fonte = (RAIZ / "sigft" / "app" / "parada.py").read_text(encoding="utf-8")
    assert "import tkinter" not in fonte
    assert "customtkinter" not in fonte


# =============================================================================
# A fiação (por AST — as telas não podem ser importadas neste ambiente)
# =============================================================================
def _arvore(caminho):
    return ast.parse(caminho.read_text(encoding="utf-8"))


def _metodos(caminho, classe=None):
    achados = {}
    for no in ast.walk(_arvore(caminho)):
        if isinstance(no, ast.ClassDef) and (classe is None or no.name == classe):
            for filho in no.body:
                if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    achados[filho.name] = filho
    return achados


def _chamadas(no):
    nomes = []
    for filho in ast.walk(no):
        if isinstance(filho, ast.Call):
            alvo = filho.func
            partes = []
            while isinstance(alvo, ast.Attribute):
                partes.append(alvo.attr)
                alvo = alvo.value
            if isinstance(alvo, ast.Name):
                partes.append(alvo.id)
            if partes:
                nomes.append(".".join(reversed(partes)))
    return nomes


def test_o_app_tem_parar_tudo_e_ele_delega_para_o_modulo():
    metodos = _metodos(MAIN, "SIG_FT_App")
    assert "parar_tudo" in metodos, "SIG_FT_App precisa expor a parada geral"
    assert any("parada.parar_tudo" in c for c in _chamadas(metodos["parar_tudo"])), \
        "a varredura mora em sigft/app/parada.py, não dentro da UI"


def test_o_parar_tudo_do_app_NAO_lista_telas_na_mao():
    """⚠️ O guard que faz a parada continuar valendo para telas futuras.

    Se `parar_tudo` citasse `UploadSpecs` e `UploadConditions` pelo nome, a
    próxima tela com robô nasceria fora do botão de pânico -- e ninguém
    descobriria até precisar dele.
    """
    fonte = ast.get_source_segment(
        MAIN.read_text(encoding="utf-8"), _metodos(MAIN, "SIG_FT_App")["parar_tudo"])
    for tela in ("UploadSpecs", "UploadConditions", "CriaFichas", "AutoSpec"):
        assert tela not in fonte, f"{tela} citada na mão dentro de parar_tudo"


def test_a_home_tem_botao_de_parar_ligado_a_um_metodo_dela():
    metodos = _metodos(HOME, "HomeView")
    assert "parar_tudo" in metodos, "a home precisa do botão de parada"
    fonte = HOME.read_text(encoding="utf-8")
    assert "self.parar_tudo" in fonte, "o botão tem de chamar o método"


def test_o_botao_da_home_pede_confirmacao_antes_de_parar():
    """Parar no meio é caro: a ficha aberta no portal fica pela metade."""
    metodo = _metodos(HOME, "HomeView")["parar_tudo"]
    assert any("askyesno" in c for c in _chamadas(metodo))


def test_o_botao_da_home_chama_o_app_e_nao_as_telas_direto():
    metodo = _metodos(HOME, "HomeView")["parar_tudo"]
    chamadas = _chamadas(metodo)
    assert any("controller.parar_tudo" in c for c in chamadas)
    assert not any("solicitar_parada" in c for c in chamadas), \
        "a home não fala com automação nenhuma; ela pede ao app"


def _telas_com_automacao():
    """Telas que mandam parar alguma coisa — logo, telas que o botão alcança.

    Varre o diretório em vez de listar na mão: a tela nova entra no guard
    sozinha. Uma lista escrita aqui envelheceria no primeiro módulo novo, que
    é justamente quando o guard faria falta.
    """
    achadas = []
    for caminho in sorted(VIEWS.glob("*.py")):
        fonte = caminho.read_text(encoding="utf-8")
        if "solicitar_parada" in fonte or "cancelar_processo" in fonte:
            achadas.append(caminho)
    return achadas


def test_o_guard_das_telas_realmente_encontra_telas():
    """Meta-teste: um glob que não acha nada passaria calado nos dois abaixo."""
    assert len(_telas_com_automacao()) >= 2


@pytest.mark.parametrize("caminho", _telas_com_automacao(), ids=lambda c: c.name)
def test_toda_tela_QUE_SABE_PARAR_responde_a_parada_geral(caminho):
    """⚠️ O guard principal deste arquivo.

    Uma tela que sabe parar por dentro mas não responde à parada geral é um
    robô que o botão da home não alcança -- e ninguém descobre até o dia em
    que o botão for apertado com pressa. Foi para não depender de eu lembrar
    disso em cada tela nova que este teste existe.
    """
    nomes = set(_metodos(caminho))
    assert parada.PEDIDO_DE_PARADA in nomes, (
        f"{caminho.name} sabe parar por dentro mas nao responde a parada geral "
        f"da home: falta o metodo {parada.PEDIDO_DE_PARADA}()")


@pytest.mark.parametrize("caminho", _telas_com_automacao(), ids=lambda c: c.name)
def test_o_interromper_tudo_devolve_rotulos_e_nao_estoura_sem_robo(caminho):
    """Tem de ser seguro chamar com nada rodando: é o caso mais comum.

    A varredura engole a exceção (`parar_tudo` tem `try`), então uma tela que
    estourasse aqui sumiria do aviso sem ninguém notar -- pareceria que não
    havia nada rodando nela.
    """
    metodo = _metodos(caminho)[parada.PEDIDO_DE_PARADA]
    assert any(isinstance(n, ast.Return) and n.value is not None
               for n in ast.walk(metodo)), "precisa devolver os rótulos"
    assert any(isinstance(n, ast.If) for n in ast.walk(metodo)), \
        "precisa conferir se há algo rodando antes de avisar"


@pytest.mark.parametrize("caminho", _telas_com_automacao(), ids=lambda c: c.name)
def test_o_interromper_tudo_nao_abre_caixa_de_confirmacao(caminho):
    """Quem apertou o botão da home já confirmou uma vez.

    Uma segunda pergunta por tela transformaria o botão de pânico numa fila de
    caixas de diálogo -- e a `parar_tudo` roda na thread da UI.
    """
    metodo = _metodos(caminho)[parada.PEDIDO_DE_PARADA]
    assert not any("askyesno" in c or "askokcancel" in c
                   for c in _chamadas(metodo))

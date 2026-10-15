# -*- coding: utf-8 -*-
"""A interface do mural não pode citar nome que o serviço não tem.

Defeito real (2026-09-03): o mural nasceu com as faixas ATRASADA /
PARA_COMECAR / EM_ANDAMENTO / TRAVADA. Quando o usuário pediu que ele fosse
por PRAZO, `services/atividades.py` foi reescrito com faixas novas — e uma
linha da Home continuou citando `at.PARA_COMECAR` e `at.TRAVADA`.

O estrago foi grande para um erro tão bobo: o `AttributeError` subia ANTES do
`try` que protege a leitura, então o botão "Atividades do dia" não abria
janela nenhuma — nem uma mensagem de erro. Do lado de fora parecia botão
morto.

Por que `compileall` e `pyflakes` não pegam: `at.PARA_COMECAR` é sintaxe
válida e `at` está definido. Só olhando DENTRO do módulo importado dá para
saber que o atributo não existe — que é o que este teste faz.

Vale para qualquer nome (constante ou função), e para os arquivos que falam
com o serviço: o leitor lê a planilha (`services/mural_atividades.py`, para
onde a Home delega desde 2026-10-10), o widget desenha.
"""
import ast
import pathlib

import pytest

from sigft.services import atividades

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ARQUIVOS = [
    # [2026-10-10] A LEITURA da aba (o `_ler_mural` que morava nas duas Homes)
    # agora é do serviço `mural_atividades`; a Home só delega
    # (`tests/test_mural_atividades.py`). Os arquivos que citam o serviço
    # `atividades` são o leitor e o desenho (o da interface antiga saiu em
    # 2026-10-15).
    RAIZ / "sigft" / "services" / "mural_atividades.py",
    RAIZ / "sigft" / "app_qt" / "widgets" / "mural.py",
]
MURAIS = [p for p in ARQUIVOS if p.name == "mural.py"]
LEITOR = RAIZ / "sigft" / "services" / "mural_atividades.py"
FUNCAO_DE_LEITURA = "ler_mural_do_mapeamento"


def _funcao_de_leitura():
    arvore = ast.parse(LEITOR.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == FUNCAO_DE_LEITURA:
            return no
    pytest.fail(f"{FUNCAO_DE_LEITURA} nao encontrada em services/mural_atividades.py")


def _apelidos_do_servico(arvore):
    """Como este arquivo chama `sigft.services.atividades` (`at`, normalmente)."""
    apelidos = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and (no.module or "").startswith("sigft.services"):
            for alias in no.names:
                if alias.name == "atividades":
                    apelidos.add(alias.asname or alias.name)
        elif isinstance(no, ast.Import):
            for alias in no.names:
                if alias.name == "sigft.services.atividades" and alias.asname:
                    apelidos.add(alias.asname)
    return apelidos


@pytest.mark.parametrize("caminho", ARQUIVOS, ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_todo_nome_citado_existe_no_servico(caminho):
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    apelidos = _apelidos_do_servico(arvore)
    assert apelidos, f"{caminho.name} deveria importar sigft.services.atividades"

    faltando = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Attribute)
            and isinstance(no.value, ast.Name)
            and no.value.id in apelidos
            and not hasattr(atividades, no.attr)
        ):
            faltando.append(f"linha {no.lineno}: {no.value.id}.{no.attr}")

    assert not faltando, (
        f"{caminho.name} cita nomes que sigft/services/atividades.py nao tem:\n  "
        + "\n  ".join(faltando)
        + "\n\nOu o nome mudou no servico e a interface ficou para tras, ou ha um erro de digitacao."
    )


def test_gavetas_do_mural_saem_de_faixas():
    """A leitura monta as gavetas vazias derivando de `FAIXAS`, não a mão.

    Escrever as faixas a mão é exatamente o que apodreceu. Se alguém voltar a
    listá-las, este teste avisa.
    """
    trecho = ast.unparse(_funcao_de_leitura())
    assert "vazio = {faixa: [] for faixa in at.FAIXAS}" in trecho, (
        f"{FUNCAO_DE_LEITURA} deve derivar as gavetas de at.FAIXAS, nunca listar as faixas a mao."
    )


# =============================================================================
# O desenho precisa cobrir TODAS as faixas
# =============================================================================

def _chaves_do_dicionario(arvore, nome_do_dicionario, apelidos):
    """As chaves `at.<NOME>` de um dicionário no topo do módulo."""
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        alvos = [a.id for a in no.targets if isinstance(a, ast.Name)]
        if nome_do_dicionario not in alvos or not isinstance(no.value, ast.Dict):
            continue
        return {
            c.attr
            for c in no.value.keys
            if isinstance(c, ast.Attribute)
            and isinstance(c.value, ast.Name)
            and c.value.id in apelidos
        }
    return None


@pytest.mark.parametrize("caminho", MURAIS, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("dicionario", ["COR_FAIXA", "ROTULO_FAIXA", "EXPLICACAO_FAIXA"])
def test_o_mural_desenha_todas_as_faixas(dicionario, caminho):
    """Faixa sem cor/rótulo/explicação estoura KeyError na hora de desenhar.

    Foi o risco concreto ao criar a faixa TRAVADA em 2026-09-03: a regra
    ganhou a faixa nova no serviço, e se os três dicionários do desenho não
    ganhassem junto, o mural quebraria só quando existisse uma atividade
    travada — ou seja, não na hora de escrever o código, e sim na frente do
    usuário.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    apelidos = _apelidos_do_servico(arvore)

    cobertas = _chaves_do_dicionario(arvore, dicionario, apelidos)
    assert cobertas is not None, f"{dicionario} nao encontrado em mural.py"

    esperadas = {
        nome
        for nome in dir(atividades)
        if nome.isupper() and getattr(atividades, nome) in atividades.FAIXAS
        and nome != "FAIXAS"
    }
    assert esperadas <= cobertas, (
        f"mural.py::{dicionario} nao cobre as faixas: {sorted(esperadas - cobertas)}"
    )


# =============================================================================
# Planilha em read_only se le com iter_rows, nunca com ws.cell
# =============================================================================

def test_leitura_do_mural_nao_usa_ws_cell():
    """`ws.cell(l, c)` em `read_only=True` custa O(n²).

    Em modo read-only a aba é um FLUXO só-para-frente: cada `ws.cell` volta ao
    começo do XML. Eram 84 linhas x 10 colunas = 840 varreduras, e o mural
    levava **3,9 s** para abrir num arquivo de 40 KB — o usuário reclamou que
    "demora muito para abrir". Com `iter_rows` caiu para 0,06 s, 69x mais
    rápido, lendo exatamente os mesmos dados.

    O defeito não dá erro nenhum: só fica lento. Por isso precisa de trava —
    nada mais o denunciaria.
    """
    chamadas = [
        c.func.attr
        for c in ast.walk(_funcao_de_leitura())
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
    ]
    assert "cell" not in chamadas, (
        f"{FUNCAO_DE_LEITURA} voltou a usar ws.cell() numa planilha read_only: "
        "custo quadratico. Use ws.iter_rows(values_only=True)."
    )
    assert "iter_rows" in chamadas, f"{FUNCAO_DE_LEITURA} deve ler com iter_rows"

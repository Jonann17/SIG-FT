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

Vale para qualquer nome (constante ou função), e para os dois arquivos que
falam com o serviço: a Home lê a planilha, o widget desenha.
"""
import ast
import pathlib

import pytest

from sigft.services import atividades

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ARQUIVOS = [
    RAIZ / "sigft" / "app" / "views" / "home.py",
    RAIZ / "sigft" / "app" / "widgets" / "mural.py",
]


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


@pytest.mark.parametrize("caminho", ARQUIVOS, ids=lambda p: p.name)
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
    """A Home monta as gavetas vazias derivando de `FAIXAS`, não a mão.

    Escrever as faixas a mão é exatamente o que apodreceu. Se alguém voltar a
    listá-las, este teste avisa.
    """
    fonte = (RAIZ / "sigft" / "app" / "views" / "home.py").read_text(encoding="utf-8")
    assert "vazio = {faixa: [] for faixa in at.FAIXAS}" in fonte, (
        "Home._ler_mural deve derivar as gavetas de at.FAIXAS, nunca listar as faixas a mao."
    )

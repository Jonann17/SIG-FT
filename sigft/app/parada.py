"""A parada geral — o botão da home que interrompe o que estiver rodando.

Pedido do usuário (2026-09-23): *"preciso de um botão na home para interromper
quando precisar sair sem finalizar a lista"*.

Até aqui a parada morava dentro de cada tela (o `PARAR ROBÔ WEB` das telas de
upload). Quem estivesse na home precisava lembrar de qual tela o robô tinha
sido disparado para conseguir pedir parada — e no fim do expediente isso é
exatamente o que não se lembra.

A varredura mora aqui, e não dentro de `SIG_FT_App`, por dois motivos:

1. dentro da UI ela só poderia ser conferida por AST; aqui ela tem teste de
   comportamento de verdade (`tests/test_parada_geral.py`);
2. o princípio 2 do `CLAUDE.md` ao contrário — a regra não precisa conhecer
   tkinter, então não conhece.

⚠️ **A parada NÃO cancela o que já foi feito.** Cada automação responde ao
sinal fechando o ciclo atual e devolvendo o que concluiu: em
`tech_specs.processar_lista` isso é o `break` no `deve_parar()` seguido do
`return pmibs_finalizados`. Ou seja, a planilha de status só recebe COMPLETO
das fichas que o portal confirmou — que é o resto do pedido do usuário.
"""
from __future__ import annotations

# O nome do método que uma tela expõe para dizer "eu sei parar". Quem não tem
# é pulado: a maioria das telas não roda nada em segundo plano.
PEDIDO_DE_PARADA = "interromper_tudo"


def parar_tudo(frames):
    """Pede parada a toda tela que saiba parar.

    `frames` é o `SIG_FT_App.frames` (dict de nome → tela), mas serve qualquer
    coleção de telas. Devolve os rótulos do que recebeu o sinal, sem repetir,
    na ordem das telas — é o que a home mostra para a pessoa.
    """
    telas = frames.values() if hasattr(frames, "values") else frames
    parados = []

    for tela in telas:
        pedir = getattr(tela, PEDIDO_DE_PARADA, None)
        if not callable(pedir):
            continue
        try:
            rotulos = pedir()
        except Exception:
            # ⚠️ Deliberado. O botão de pânico é o que se aperta quando alguma
            # coisa JÁ está estranha; uma tela em mau estado não pode impedir
            # que o robô da tela do lado receba o sinal.
            continue
        if isinstance(rotulos, str):
            rotulos = [rotulos]
        for rotulo in rotulos or ():
            if rotulo and rotulo not in parados:
                parados.append(rotulo)

    return parados

r"""
Inventário dos seletores do portal — "o que este projeto procura na tela".

Existe para responder a uma pergunta que hoje não tem resposta barata: **o
portal PMIB vai ser atualizado; quando isso acontecer, o que exatamente
quebra?**

Hoje o projeto tem 176 seletores espalhados por 7 arquivos, e só 40 deles são
constantes nomeadas -- os outros ~136 são strings soltas no meio da lógica
(`upload_conditions.py` e `ficha_duplicada.py` concentram a maioria). Com isso,
uma atualização do portal vira caça ao literal, módulo por módulo, e o sintoma
chega sempre pelo caminho mais caro: o robô falhando no meio de um lote.

Este módulo NÃO move nenhum seletor de lugar (isso é refatoração de escopo
próprio, e mover 176 strings no meio de uma sessão de teste seria imprudente).
Ele COLETA por reflexão o que já existe, para que uma ferramenta possa
conferir todos contra a tela real de uma vez -- ver
`scripts/auditar_seletores.py`.

Por que reflexão e não uma lista escrita à mão: uma lista à mão nasce
desatualizada. Lendo os módulos, um seletor novo entra no inventário no
instante em que alguém o declara como constante -- e um seletor que continua
solto no meio do código fica de fora, o que é exatamente o incentivo certo
para ir nomeando os que faltam.

Só stdlib: este módulo é importado por script de diagnóstico, não pode exigir
Selenium, Playwright nem pandas para funcionar.
"""
from __future__ import annotations

import importlib

# Os módulos que falam com o portal. `ficha_duplicada` está na lista mesmo
# sendo reconstruído na Fase 6 -- é justamente quem tem mais seletor solto, e
# o inventário serve para dimensionar isso.
MODULOS_COM_SELETOR = (
    "sigft.core.rpa.portal",
    # Fase 6: seletores levantados do DOM real, com a justificativa de cada um
    # e o registro dos ids gerados que NÃO se deve usar.
    "sigft.core.rpa.seletores_duplicada",
    "sigft.services.apagar_lmr",
    "sigft.services.cria_fichas",
    "sigft.services.ficha_duplicada",
    "sigft.services.lmr",
    "sigft.services.tech_specs",
    "sigft.services.upload_conditions",
)

# Prefixo dos seletores RELATIVOS a uma linha de tabela (`XPATH_REL_*`). Eles
# não podem ser conferidos sozinhos contra a página -- `//textarea[...]` sem a
# linha na frente casaria textareas de qualquer linha, dando um "existe" que
# não prova nada. Ficam marcados, para a auditoria tratá-los à parte.
PREFIXO_RELATIVO = "XPATH_REL_"


def _e_seletor(nome, valor):
    return (
        nome.startswith("XPATH")
        and isinstance(valor, str)
        and valor.strip().startswith(("//", "(", "."))
    )


def coletar(modulos=MODULOS_COM_SELETOR):
    """[(módulo, nome, seletor, é_relativo)] de todas as constantes `XPATH*`.

    Ordenado por módulo e nome, para a saída de duas execuções ser
    comparável com `diff` -- é assim que se vê o que uma atualização do
    portal mudou.
    """
    achados = []
    for caminho in modulos:
        try:
            modulo = importlib.import_module(caminho)
        except Exception:
            # Um módulo que não importa (dependência ausente no ambiente) não
            # pode derrubar o inventário dos outros seis.
            continue
        for nome in sorted(dir(modulo)):
            valor = getattr(modulo, nome, None)
            if _e_seletor(nome, valor):
                achados.append((caminho, nome, valor, nome.startswith(PREFIXO_RELATIVO)))
    return sorted(achados, key=lambda linha: (linha[0], linha[1]))


def resumo_por_modulo(achados=None):
    """{módulo: quantidade} -- o número que diz onde dói mais numa
    atualização do portal."""
    achados = coletar() if achados is None else achados
    contagem = {}
    for modulo, _nome, _seletor, _rel in achados:
        contagem[modulo] = contagem.get(modulo, 0) + 1
    return contagem


def duplicados(achados=None):
    """Seletores IDÊNTICOS declarados em mais de um lugar.

    Cada duplicata é um ponto onde uma atualização do portal precisa ser
    corrigida N vezes, e onde é fácil corrigir N-1 e não perceber. É o
    primeiro alvo de qualquer unificação.
    """
    achados = coletar() if achados is None else achados
    por_seletor = {}
    for modulo, nome, seletor, _rel in achados:
        por_seletor.setdefault(seletor, []).append(f"{modulo}.{nome}")
    return {sel: locais for sel, locais in sorted(por_seletor.items()) if len(locais) > 1}

"""A regra da boas-vindas: quando ela aparece no lugar da Home (2026-10-28).

Desenho: `docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`,
parte 2. A tela é `sigft/app_qt/views/boas_vindas.py`; quem decide na montagem
da janela é `sigft/app_qt/main.py`. Este módulo não importa Qt.

Só para quem NUNCA usou: quem já usava o SIG-FT e atualiza não pode ganhar uma
página de "bem-vindo" no lugar da Home de sempre. Duas condições:

1. a preferência `boas_vindas_vista` (seção `opcoes` do `user_prefs.json`) não
   está gravada. Ela é gravada por "Ir para o início" e pelo clique num caminho,
   e não por mostrar a página: quem fecha o app sem escolher nada a vê de novo;
2. a pasta de dados (`Documentos\\SIG-FT\\`) não tem RASTRO DE USO.

O que é rastro de uso
---------------------
A regra mora em `sigft/core/rastros_de_uso.py` (a janela de novidades faz a
mesma pergunta, e o `core` não importa o `app`); os nomes continuam
importáveis daqui.

Nunca levanta: a abertura do app não pode depender disto. Na dúvida (pasta que
não se lê), não mostra.
"""
from __future__ import annotations

import logging
import os

# A regra do rastro de uso é do core (a janela de novidades a usa também);
# os nomes continuam importáveis daqui.
from sigft.core.rastros_de_uso import (  # noqa: F401
    ARQUIVO_DE_CHAVES,
    LOGS_DA_ABERTURA,
    SECOES_DE_USO,
    rastros_de_uso,
)

_log = logging.getLogger(__name__)

# Ligada, a página nunca aparece sozinha (o Ctrl+K e a Configuração a abrem
# igual). Só os testes a ligam (`tests/conftest.py`): a pasta de dados de cada
# teste é nova, e a janela abriria na boas-vindas em vez da Home. Quem testa a
# boas-vindas tira a variável.
ENV_DESLIGAR = "SIGFT_SEM_BOAS_VINDAS"

# A preferência (seção `opcoes`, liga/desliga) gravada quando a pessoa sai da página.
CHAVE_VISTA = "boas_vindas_vista"

def ja_vista() -> bool:
    from sigft.core import prefs

    return prefs.get_opcao(CHAVE_VISTA, False)


def deve_mostrar_boas_vindas() -> bool:
    """`True` só sem `boas_vindas_vista` e sem rastro de uso. Nunca levanta."""
    if os.environ.get(ENV_DESLIGAR):
        return False
    try:
        if ja_vista():
            return False
        rastros = rastros_de_uso()
    except Exception:  # noqa: BLE001 -- na dúvida, a Home de sempre
        _log.warning("nao consegui decidir a boas-vindas", exc_info=True)
        return False
    if rastros:
        _log.info("boas-vindas: ja usado (%s)", ", ".join(rastros))
    return not rastros


def marcar_vista() -> None:
    """Grava `boas_vindas_vista`: a página não abre mais sozinha. Nunca levanta."""
    from sigft.core import prefs

    try:
        prefs.set_opcao(CHAVE_VISTA, True)
    except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar o clique
        _log.warning("nao consegui gravar a boas-vindas como vista", exc_info=True)

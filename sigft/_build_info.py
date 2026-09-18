"""Identidade do BUILD -- escrita pelo CI, nunca editada a mao num release.

Esta e a fonte unica da versao do SIG-FT. O workflow
`.github/workflows/release.yml` reescreve este arquivo a partir da tag do Git
(`v1.0.0` -> `VERSAO = "1.0.0"`) antes de rodar o PyInstaller, de modo que o
executavel SEMPRE sabe qual versao ele e -- que e exatamente o que o
verificador de atualizacao compara com o ultimo Release do GitHub.

Por que a versao NAO pode vir de arquivo de configuracao
--------------------------------------------------------
`.env`, `api_config.json` e `user_prefs.json` sao arquivos do USUARIO: eles
sobrevivem a atualizacao de proposito (e o que impede a atualizacao de apagar
as chaves de API de alguem). Se a versao viesse de la, o app recem atualizado
continuaria se declarando na versao velha e ofereceria a MESMA atualizacao para
sempre -- o usuario clicaria em "atualizar" toda semana, com sucesso, sem nada
mudar. Versao e caracteristica do BINARIO, nao do usuario.

O DocManager pagou exatamente isso ate a v3.0.0. Aqui o defeito nasce
impossivel: `tests/test_build_info.py` reprova qualquer leitura de ambiente ou
de arquivo do usuario dentro deste modulo.

Os valores abaixo sao so o rotulo dos builds locais (feitos pelo
`Gerar-Executavel.bat`). Num Release eles sao sobrescritos.
"""
from __future__ import annotations

# Sobrescrito pelo CI a partir da tag. Em build local fica como esta.
VERSAO = "1.0.0"

# Commit curto e data do build (o CI preenche; local fica vazio).
COMMIT = ""
DATA_BUILD = ""

# "github-actions" quando gerado pelo workflow; "local" no .bat.
ORIGEM = "local"


def descricao() -> str:
    """Linha de diagnostico, ex.: `1.0.0 (github-actions - a1b2c3d - 2026-09-18)`.

    Num build local, onde COMMIT/DATA_BUILD ficam vazios, devolve so a versao
    -- em vez de `1.0.0 ()`, que so ocuparia espaco na barra de titulo.
    """
    extras = [p for p in (ORIGEM, COMMIT, DATA_BUILD) if p]
    return f"{VERSAO} ({' - '.join(extras)})" if extras else VERSAO

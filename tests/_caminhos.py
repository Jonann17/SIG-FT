# -*- coding: utf-8 -*-
"""Comparar caminho de arquivo sem depender do sistema onde o teste roda.

O DEFEITO QUE ORIGINOU ESTE ARQUIVO (2026-09-21, run #1 do Release)
--------------------------------------------------------------------
Os guards de `tests/` varrem os arquivos do pacote e pulam os que estao numa
lista de excecoes. A comparacao era assim:

    relativo = str(arquivo.relative_to(RAIZ))
    if relativo in FORA_DO_RECORTE:        # {"sigft/services/autospec.py", ...}
        pytest.skip(...)

`str(Path)` usa o separador DO SISTEMA:

    Linux    -> "sigft/services/autospec.py"     casa com a lista
    Windows  -> "sigft\\services\\autospec.py"    NAO casa

Ou seja: **as listas de excecao ficavam inertes no Windows.** Todo arquivo que
deveria ser pulado era testado, e nove reprovaram no primeiro Release --
incluindo `duplicadas_condicoes.py`, um dos dois lugares onde o travessao e
DADO e nao pontuacao.

A suite passava em Linux (3831 verdes) porque em Linux as barras casam.
**Nenhum CI nosso podia ver isso**, e so o build no Windows mostrou.

E o espelho exato do defeito que a Frente 0 consertou (`os.path.basename` nao
cortava `\\` no POSIX). Mesma familia: tratamento de caminho que muda com o
sistema. Por isso virou funcao com nome e teste proprio, em vez de um
`.as_posix()` solto em dois lugares -- da proxima vez que alguem escrever um
guard desses, o nome esta aqui para ser achado.

Nao e modulo de teste (o `_` no nome impede a coleta do pytest): e utilitario
para os guards. Testado em `tests/test_caminhos_multiplataforma.py`, com
`PureWindowsPath`, que roda no Linux.
"""
from __future__ import annotations


def relativo_posix(caminho, raiz) -> str:
    """`caminho` relativo a `raiz`, SEMPRE com barra normal.

    Use isto em vez de `str(caminho.relative_to(raiz))` sempre que o resultado
    for COMPARADO com alguma coisa (lista de excecoes, chave de dicionario).

    Para MOSTRAR o caminho numa mensagem de erro, `str()` continua certo --
    exibir com barra invertida no Windows e o que a pessoa espera ver.
    """
    return caminho.relative_to(raiz).as_posix()

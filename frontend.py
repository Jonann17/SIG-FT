"""Ponto de entrada do SIG-FT: abre a interface Qt (`sigft/app_qt/`).

É o arquivo que o `SIG-FT.spec` empacota (no `.exe`, quem é `"__main__"` é
ele) e o que o `SIG-FT.bat` e o `SIG-FT.command` (Mac) rodam. A interface em
si mora em `sigft/app_qt/`; `python -m sigft.app_qt.main` abre a mesma coisa.

Desde 2026-10-15 a interface é só a Qt: a interface antiga de antes saiu do
SIG-FT, com a opção que a abria e a queda para ela quando a Qt falhava. Se a Qt não
abrir, a pessoa recebe uma mensagem com o motivo e o caminho do `sigft.log`
(`sigft/core/erro_de_abertura.py`, sem biblioteca gráfica nenhuma), e o
processo sai com 1.

Este arquivo era o monolito de 5.675 linhas das 12 telas; o CP 7.3 o
transformou em shim, e o histórico está no `git log`.
"""
from __future__ import annotations

import sys

# Antes de tudo: com Python antigo o app abria pela metade, com erro enigmático.
from sigft.core.python_minimo import exigir_python_minimo

exigir_python_minimo()


def _a_qt_nao_abriu(erro: Exception) -> None:
    """A interface Qt não importou (PySide6 ausente ou quebrado) ou não subiu.

    Com `--smoke` (o passo do Release): grava o motivo e sai com 1, sem caixa
    nenhuma -- o Release não pode ficar esperando um OK. Sem isto, um PySide6
    que não carrega estourava ANTES do `_smoke`, o `.exe` sem console mostrava
    a caixa de traceback do PyInstaller e o passo esperava até o limite, sem
    relatório.

    Sem `--smoke`: o motivo vai para o `sigft.log`, para a saída de erro (a
    janela preta do `SIG-FT.bat`) e para uma caixa do sistema operacional; e
    sai com 1, para o lançador mostrar "Encerrado com erro" e esperar.
    """
    import traceback

    pilha = "".join(traceback.format_exception(erro))
    motivo = f"{type(erro).__name__}: {erro}"
    if "--smoke" in sys.argv:
        from sigft.app.conferencia import ARQUIVO_JANELA, gravar_relatorio

        relatorio = f"[smoke] FALHOU: a interface Qt nao abriu: {motivo}\n\n{pilha}"
        gravar_relatorio(ARQUIVO_JANELA, relatorio)
        print(relatorio)
        sys.exit(1)

    from sigft.core.erro_de_abertura import avisar

    avisar(motivo, pilha)
    sys.exit(1)


# ⚠️ O despacho precoce vem antes de qualquer import pesado, e é isto que faz o
# Release funcionar.
#
# Em 2026-09-21 o despacho de `--conferir-pacote` morava só no `main.py` da
# interface, atrás de um `if __name__ == "__main__"` que no bundle nunca é
# verdadeiro (no `.exe`, o `__main__` é ESTE arquivo): o `.exe` ignorava a flag,
# caía no `main()` e ABRIA A JANELA, e o passo do workflow, que chama o `.exe`
# com `Start-Process -Wait`, ficou pendurado esperando o usuário.
#
# Uma conferência de pacote tem de funcionar num pacote quebrado, então ela vem
# antes de tudo. `sigft/app/conferencia.py` é só stdlib, de propósito.
if __name__ == "__main__":
    from sigft.app.conferencia import despachar_cedo as _despachar_cedo

    _despachar_cedo()

    try:
        from sigft.app_qt.main import executar_da_linha_de_comando as _abrir_qt

        _abrir_qt()
    except Exception as erro:  # noqa: BLE001 -- ver `_a_qt_nao_abriu`
        _a_qt_nao_abriu(erro)
    # O `main()` da Qt termina o processo (`instancia.encerrar`) e o `--smoke`
    # sai com `sys.exit`. Se um dia ele voltar, o processo termina aqui.
    sys.exit(0)

"""Shim de compatibilidade — o aplicativo mudou para `sigft/app/`.

Checkpoint 7.3 do plano (`docs/refatoracao/PLANO_REFATORACAO.md`, Fase 7).

Este arquivo tinha 5.675 linhas: 12 telas, 6 janelas auxiliares, a splash e o
aplicativo, tudo junto. Cada peça mudou para o seu lugar:

    sigft/app/main.py            SIG_FT_App, SplashScreen, resource_path
    sigft/app/views/*.py         uma tela por arquivo
    sigft/app/views/janelas.py   as 6 janelas auxiliares
    sigft/app/theme.py           a paleta e as fontes (CP 7.1)
    sigft/app/widgets/           console, esqueleto de tela, pickers, diálogos
    sigft/app/backends.py        o registro que o splash carrega (CP 7.3)

**A forma de abrir o aplicativo continua a mesma; o que abre mudou** (E6.1,
2026-10-10): `python frontend.py` — e o `SIG-FT.bat` e o `SIG-FT.command` (Mac),
que fazem exatamente isso — abre a interface Qt (`sigft/app_qt/`).
`python frontend.py --ctk` abre a CustomTkinter de antes, enquanto durar a
transição. `python -m sigft.app_qt.main` e `python -m sigft.app.main` abrem cada
uma direto.

Por que o shim existe, em vez de simplesmente apagar o arquivo
--------------------------------------------------------------
Mesmo motivo dos shims dos `*_backend.py` (CP 4.1): o nome antigo continua
importável enquanto a refatoração não fecha. Aqui há consumidores concretos —
o `SIG-FT.bat`, que é o que o usuário clica, e os testes que leem
`frontend.py` por CAMINHO (`test_frontend_nomes_indefinidos.py`).

Os nomes reexportados abaixo são os que este arquivo expunha. `COLORS` está na
lista porque havia código lendo `frontend.COLORS`; a fonte de verdade dele
agora é `sigft/app/theme.py`, e há teste travando os dois juntos.
"""
from __future__ import annotations

import sys

# Antes de tudo: com Python antigo o app abria pela metade, com erro enigmático.
from sigft.core.python_minimo import exigir_python_minimo

exigir_python_minimo()


def _a_qt_nao_abriu(erro: Exception) -> None:
    """A interface Qt não importou (PySide6 ausente ou quebrado) ou não subiu.

    Com `--smoke` (o passo do Release): grava o motivo e sai com 1. Sem isto,
    um PySide6 que não carrega estourava ANTES do `_smoke`, o `.exe` sem
    console mostrava a caixa de traceback do PyInstaller e o passo esperava até
    o limite, sem relatório. E nunca cai no CustomTkinter: o Release tem de
    reprovar, não passar com a interface errada.

    Sem `--smoke` (decisão da transição): avisa no console e volta, e o
    `frontend.py` segue para a interface antiga no mesmo processo -- a pessoa
    continua trabalhando, e fica com o comando para abrir a antiga direto.
    """
    import os
    import traceback

    pilha = "".join(traceback.format_exception(erro))
    if "--smoke" in sys.argv:
        from sigft.app.conferencia import ARQUIVO_JANELA, gravar_relatorio

        relatorio = (f"[smoke] FALHOU: a interface Qt nao abriu: "
                     f"{type(erro).__name__}: {erro}\n\n{pilha}")
        gravar_relatorio(ARQUIVO_JANELA, relatorio)
        print(relatorio)
        sys.exit(1)

    # No `.exe` sem console, o aviso e a pilha vão para o `logs/sigft.log` (o
    # import do `sigft.app_qt.main`, que faria isso, foi o que falhou).
    from sigft.core.saida_log import desviar_saida_para_arquivo

    desviar_saida_para_arquivo()
    if getattr(sys, "frozen", False):
        comando = f'"{sys.executable}" --ctk'
    else:
        comando = f'"{sys.executable}" "{os.path.abspath(__file__)}" --ctk'
    print(pilha, file=sys.stderr)
    print(f"[SIG-FT] A interface nova (Qt) nao abriu: {type(erro).__name__}: {erro}")
    print("[SIG-FT] Abrindo a interface antiga para voce continuar trabalhando.")
    print(f"         Para abrir a antiga direto: {comando}", flush=True)


# ⚠️ ANTES do import pesado logo abaixo, e isto é o que faz o Release funcionar.
#
# Este arquivo é o que o `SIG-FT.spec` empacota — dentro do `.exe`, quem é
# `"__main__"` é ELE, e o `sigft/app/main.py` entra importado. Em 2026-09-21 o
# despacho de `--conferir-pacote` morava só lá, atrás de um
# `if __name__ == "__main__"` que no bundle nunca é verdadeiro: o `.exe`
# ignorava a flag, caía no `main()` e ABRIA A JANELA. O passo do workflow, que
# chama o `.exe` com `Start-Process -Wait`, ficou pendurado esperando um
# aplicativo que estava lá, aberto, esperando o usuário.
#
# Uma conferência de pacote tem de funcionar num pacote quebrado, então ela vem
# antes de tudo. `sigft/app/conferencia.py` é só stdlib, de propósito.
if __name__ == "__main__":
    from sigft.app.conferencia import despachar_cedo as _despachar_cedo

    _despachar_cedo()

    # A interface oficial é a Qt (E6.1), e ela entra AQUI, antes dos imports do
    # CustomTkinter logo abaixo: o modo Qt não importa tkinter (o Python do
    # Homebrew, no Mac, nem o traz). `--ctk` abre a interface antiga.
    if "--ctk" not in sys.argv:
        try:
            from sigft.app_qt.main import executar_da_linha_de_comando as _abrir_qt

            _abrir_qt()
        except Exception as erro:  # noqa: BLE001 -- ver `_a_qt_nao_abriu`
            _a_qt_nao_abriu(erro)  # com `--smoke` sai com 1; sem ele, segue para o CTk
        else:
            # Não volta: o `main()` da Qt termina o processo (`instancia.encerrar`)
            # e o `--smoke` sai com `sys.exit`. Se um dia voltar, sai aqui mesmo,
            # em vez de cair no CustomTkinter.
            sys.exit(0)

from sigft.app.main import (
    CONFIG_FILE,
    SIG_FT_App,
    SplashScreen,
    executar_da_linha_de_comando,
    main,
    resource_path,
)
from sigft.app.theme import COLORS
from sigft.app.views.analyzer import ModuloAnalyzer
from sigft.app.views.apagar_lmr import ModuloApagarLMR
from sigft.app.views.autospec import ModuloAutoSpec
from sigft.app.views.busca_pmib import ModuloBuscaPMIB
from sigft.app.views.copia_fichas import ModuloCopiaFichas
from sigft.app.views.correcao_pdm import ModuloCorrecaoPDM
from sigft.app.views.cria_fichas import ModuloCriaFichas
from sigft.app.views.home import HomeView
from sigft.app.views.janelas import (
    JanelaAcaoRobo,
    JanelaResumo,
    JanelaRevisaoEdicao,
    JanelaRevisaoPDM,
    JanelaSelecao,
    JanelaSelecaoDuplicadas,
)
from sigft.app.views.lmr import ModuloLMR
from sigft.app.views.pdm import ModuloPDM
from sigft.app.views.pmib_manager import ModuloPMIBManager
from sigft.app.views.translator import ModuloTranslator
from sigft.app.views.upload_conditions import ModuloUploadConditions
from sigft.app.views.upload_tech_specs import ModuloUploadTechSpecs

__all__ = [
    "COLORS",
    "CONFIG_FILE",
    "HomeView",
    "JanelaAcaoRobo",
    "JanelaResumo",
    "JanelaRevisaoEdicao",
    "JanelaRevisaoPDM",
    "JanelaSelecao",
    "JanelaSelecaoDuplicadas",
    "ModuloAnalyzer",
    "ModuloApagarLMR",
    "ModuloAutoSpec",
    "ModuloBuscaPMIB",
    "ModuloCopiaFichas",
    "ModuloCorrecaoPDM",
    "ModuloCriaFichas",
    "ModuloLMR",
    "ModuloPDM",
    "ModuloPMIBManager",
    "ModuloTranslator",
    "ModuloUploadConditions",
    "ModuloUploadTechSpecs",
    "SIG_FT_App",
    "SplashScreen",
    "executar_da_linha_de_comando",
    "main",
    "resource_path",
]


if __name__ == "__main__":
    # Chega aqui com `--ctk`, ou quando a Qt não abriu (ver `_a_qt_nao_abriu`).
    # `executar_da_linha_de_comando()`, e não `main()` direto: é ele que trata
    # `--smoke`. Chamar `main()` aqui engoliria a flag, porque o `__main__` do
    # `sigft/app/main.py` não roda no bundle. Ver o aviso lá em cima.
    executar_da_linha_de_comando()

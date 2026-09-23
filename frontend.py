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

**A forma de abrir o aplicativo continua a mesma** — `python frontend.py`, e o
`SIG-FT.bat`, que faz exatamente isso, não precisou mudar. A forma nova é
`python -m sigft.app.main`; as duas fazem o mesmo.

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
    # `executar_da_linha_de_comando()`, e não `main()` direto: é ele que trata
    # `--smoke`. Chamar `main()` aqui engoliria a flag, porque o `__main__` do
    # `sigft/app/main.py` não roda no bundle. Ver o aviso lá em cima.
    executar_da_linha_de_comando()

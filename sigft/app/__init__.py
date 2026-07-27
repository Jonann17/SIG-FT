"""Pacote `sigft.app` — camada de interface (UI) da refatoração do SIG-FT.

Ver docs/refatoracao/PLANO_REFATORACAO.md, seção "Arquitetura-alvo". Ao
contrário de `sigft.core`/`sigft.services`, os módulos deste pacote PODEM
depender de tkinter/customtkinter — nunca o contrário: nenhum serviço importa
nada de `sigft.app` (princípio nº 2 da arquitetura-alvo: "UI nunca contém
regra de negócio; serviço nunca importa tkinter").

Neste checkpoint (Fase 1 -> CP 1.5, 1ª metade) o pacote nasce com um único
módulo, `file_dialogs.py` (wrappers de `tkinter.filedialog` com memória de
caminho, lado UI de `sigft.core.prefs`) — os demais módulos previstos na
arquitetura-alvo (`main.py`, `splash.py`, `theme.py`, `widgets/`, `views/`)
chegam em checkpoints futuros (Fase 7). `frontend.py` continua sendo a UI de
produção até lá; nada deste pacote é consumido por ele ainda.
"""

"""Widgets compartilhados da interface do SIG-FT (Fase 7 do plano).

Um widget por conceito, no lugar das cópias que cada tela do `frontend.py`
mantinha. Os imports ficam nos submódulos, não aqui: `console.py` e
`module_frame.py` importam `customtkinter`, e um `from ... import *` neste
`__init__` obrigaria quem só quer a paleta (`sigft.app.theme`, que é stdlib
pura) a arrastar o Tk junto.
"""

"""As telas do SIG-FT, uma por arquivo — Checkpoint 7.3 (Fase 7 do plano).

Até aqui as 12 telas viviam dentro do `frontend.py`, num arquivo de 5.600
linhas. Cada uma passa a ter o seu arquivo, com os imports de que ela precisa
e nada mais.

Nada é importado aqui de propósito
----------------------------------
Um `from .apagar_lmr import ModuloApagarLMR` neste `__init__` faria com que
importar QUALQUER view arrastasse TODAS — e com elas o `customtkinter` e o que
mais cada uma puxe. Quem quer uma tela importa o módulo dela.

Como uma view acessa os backends
--------------------------------
`from sigft.app import backends`, depois `backends.pdm_backend.x` — sempre no
momento da chamada. NUNCA `from sigft.app.backends import pdm_backend`: isso
copia o `None` do instante do import, e o splash carrega depois. O porquê
está no docstring de `sigft/app/backends.py`.
"""

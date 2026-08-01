"""Pacote `sigft.services` — lógica de negócio dos backends do SIG-FT.

Ver docs/refatoracao/PLANO_REFATORACAO.md, seção "Arquitetura-alvo"
(`services/  # lógica de negócio (os atuais backends, magros)`) e Fase 4 ->
CP 4.1 ("Mover backends para `sigft/services/` com shims").

Cada módulo aqui é um dos antigos `*_backend.py` da raiz do repositório,
movido byte a byte (`mv`, sem reescrever conteúdo) e SEM nenhuma mudança de
comportamento — os imports absolutos que já usavam (`from sigft import
config`, `from sigft.core...`) continuam válidos de dentro de
`sigft/services/`, sem ajuste.

No lugar antigo (raiz do repositório), um shim de compatibilidade faz
ALIASING DE MÓDULO (`sys.modules[__name__] = <módulo novo>`), não
`from ... import *`: o nome antigo (ex.: `apagar_lmr_backend`) e o novo
(`sigft.services.apagar_lmr`) passam a ser LITERALMENTE o mesmo objeto de
módulo. Isso é necessário porque `frontend.py` carrega os backends por NOME
DE RAIZ via `importlib.import_module()` no splash
(`SplashScreen.carregar_modulos`, lista `modulos_para_carregar`) até a
Fase 7, e várias dezenas de testes fazem `import apagar_lmr_backend`/
`from analyzer_backend import DatasheetAnalyzer`/
`monkeypatch.setattr(<modulo_antigo>, "X", ...)` — um `import *` criaria
dois namespaces distintos (o dict de globals do shim x o do módulo real) e
qualquer patch feito pelo nome antigo deixaria de ter efeito no código real
que roda a partir de `sigft.services`, um bug silencioso. `import *` também
não exporta nomes com underscore.

Movidos no CP 4.1 (1ª metade — um commit por módulo, nesta ordem):
`apagar_lmr.py`, `lmr.py`, `search.py`, `pdm.py`, `translator.py`,
`analyzer.py`. A 2ª metade (`autospec`, `cria_fichas`, `upload_conditions`,
`tech_specs`, `ficha_duplicada` — como está, a reconstrução é na Fase 6 —,
`pmib_manager`) é uma tarefa separada; até ela terminar, esses 6 continuam
soltos na raiz como `*_backend.py`/`upload_ficha_duplicada.py`, sem shim.
"""

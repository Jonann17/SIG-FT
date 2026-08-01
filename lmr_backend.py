"""Shim de compatibilidade: `lmr_backend` -> `sigft.services.lmr`.

CP 4.1 do plano de refatoração (docs/refatoracao/PLANO_REFATORACAO.md,
Fase 4): o código real mora em `sigft/services/lmr.py`. Este arquivo
existe só para que o nome ANTIGO continue importável até a Fase 7
(`frontend.py` ainda carrega os backends por nome de raiz no splash, via
`importlib.import_module`).

Por que ALIASING (`sys.modules[__name__] = _modulo`) e não
`from ... import *`: assim `lmr_backend` e `sigft.services.lmr` são
LITERALMENTE o mesmo objeto de módulo. Com `import *` seriam dois
namespaces distintos, e qualquer `monkeypatch.setattr(lmr_backend, "X",
...)` (ou atribuição em runtime) alteraria só a cópia da raiz, sem efeito
no código real que roda a partir de `sigft.services` — uma classe inteira
de bug silencioso, especialmente nos ~15 arquivos de teste que importam
pelos nomes antigos. `import *` também não exporta nomes com underscore.
"""
import sys as _sys

from sigft.services import lmr as _modulo

_sys.modules[__name__] = _modulo

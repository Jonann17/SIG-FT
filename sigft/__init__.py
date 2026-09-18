"""Pacote `sigft` — arquitetura-alvo da refatoração do SIG-FT.

Ver docs/refatoracao/PLANO_REFATORACAO.md. Neste checkpoint (CP 0.1) o pacote
nasce vazio, como salvaguarda de estrutura; os módulos `core/`, `services/` e
`app/` são adicionados nos checkpoints seguintes.
"""

# A versão vem do `_build_info`, que é o que o CI carimba a partir da tag do
# Git. Aqui é REEXPORTAÇÃO, nunca uma cópia: dois literais de versão em dois
# arquivos divergem na primeira pressa, e a divergência é invisível — o app
# mostraria um número na tela e compararia outro com o Release.
# `tests/test_build_info.py` reprova a volta do literal.
from ._build_info import VERSAO as __version__

__all__ = ["__version__"]

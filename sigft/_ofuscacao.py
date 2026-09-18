"""Ofuscação do token de atualização embutido no build.

Mora num módulo próprio, **sem nenhum import do pacote**, porque duas pontas
distantes precisam dele e não podem divergir:

* `tools/preparar_build.py` — que ofusca, dentro do GitHub Actions, antes do
  PyInstaller rodar;
* `sigft/services/updater.py` — que desofusca, em tempo de execução, dentro do
  `.exe` na máquina do usuário.

Se as duas implementações se separassem, o token gerado num build deixaria de
ser legível pelo app: falha silenciosa, e o sintoma seria "o app parou de
avisar sobre atualização", sem erro nenhum no log.

O import vazio também importa por outro motivo: o script de build roda antes de
o ambiente do pacote estar montado. Se este módulo importasse `sigft.config`,
o build passaria a exigir `python-dotenv` só para carimbar um token.

⚠️ **Isto não é criptografia.** É um XOR com chave fixa, e a chave está logo
abaixo. O único objetivo é o token não aparecer num `strings SIG-FT.exe`. Quem
tiver o executável e quiser, extrai — por isso o token embutido **tem** de ser
um PAT *fine-grained*, somente leitura (`Contents: Read-only`) e restrito a
este repositório. O pior caso passa a ser alguém conseguir ler o código que
essa pessoa já recebeu. Ver `docs/BUILD.md`, seção "Rotação do token".
"""
from __future__ import annotations

import base64

CHAVE = b"SIGFTItaipu"


def _xor(dados: bytes) -> bytes:
    return bytes(b ^ CHAVE[i % len(CHAVE)] for i, b in enumerate(dados))


def ofuscar(token: str) -> str:
    """Texto claro -> o que vai para `_update_auth.py` (feito pelo CI)."""
    if not token:
        return ""
    return base64.b64encode(_xor(token.encode("utf-8"))).decode("ascii")


def desofuscar(texto_b64: str) -> str:
    """O inverso, usado pelo app ao procurar atualizações."""
    if not texto_b64:
        return ""
    return _xor(base64.b64decode(texto_b64.encode("ascii"))).decode("utf-8")

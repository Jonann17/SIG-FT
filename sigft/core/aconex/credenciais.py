# Copiado em parte de luanccozer/DocManager@c9683d2 (docmanager/services/credenciais.py): _dpapi, decifrar e a leitura do Cofre. Nao edite aqui sem levar ao DocManager -- PENDENCIAS 2026-10-26.
"""A leitura do cofre de credenciais do Aconex que o DocManager mantém.

O SIG-FT só LÊ `Documentos\\DocManager_Itaipu\\credenciais.json` (esquema 1): um
perfil por pessoa, com o Client ID, o User ID e o Client Secret cifrado pela DPAPI
do Windows. Nunca escreve nele. Perfil incompleto, ilegível ou cifrado em outra
conta do Windows fica de fora; sem perfil, o SIG-FT usa o extrato. O segredo não
vai para log, mensagem de erro nem `repr`. Desenho:
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §6.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# A chave da preferência (`prefs.ler_preferencia`/`gravar_preferencia`) com o perfil escolhido.
PREFERENCIA_PERFIL = "aconex.perfil"


@dataclass(frozen=True)
class PerfilAconex:
    nome: str
    client_id: str
    user_id: str
    client_secret: str = field(repr=False)


def caminho_do_cofre() -> Path:
    """O `credenciais.json` do DocManager: a mesma regra do `pasta_dados` dele
    (`DOCMANAGER_DADOS_DIR` ou `~/Documents/DocManager_Itaipu`), sem criar a pasta."""
    if custom := os.getenv("DOCMANAGER_DADOS_DIR", "").strip():
        return Path(custom) / "credenciais.json"
    return Path.home() / "Documents" / "DocManager_Itaipu" / "credenciais.json"


def _dpapi(funcao: str, dados: bytes) -> bytes:
    """Chama CryptProtectData/CryptUnprotectData via ctypes (sem dependência nova)."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    entrada = BLOB(len(dados), ctypes.cast(ctypes.create_string_buffer(dados),
                                           ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    crypt32 = ctypes.windll.crypt32
    chamada = getattr(crypt32, funcao)
    # CRYPTPROTECT_UI_FORBIDDEN (0x1): nunca abrir caixa de diálogo - o app pode
    # estar cifrando dentro de uma thread de trabalho, sem janela para exibir.
    ok = chamada(ctypes.byref(entrada), None, None, None, None, 0x01, ctypes.byref(saida))
    if not ok:
        raise OSError(f"{funcao} falhou (erro {ctypes.GetLastError()})")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _desproteger(dados: bytes) -> bytes:
    """O CryptUnprotectData. Separado para o teste simular a recusa da DPAPI (cofre
    cadastrado em outra conta do Windows) sem tocar no Windows."""
    return _dpapi("CryptUnprotectData", dados)


def decifrar(texto: str, cifrado: bool) -> str:
    bruto = base64.b64decode(texto.encode("ascii"))
    if cifrado:
        return _desproteger(bruto).decode("utf-8")
    return bruto.decode("utf-8")


def ler_perfis(caminho: Path | None = None) -> list[PerfilAconex]:
    """Os perfis completos do cofre, em ordem de nome. Nunca levanta: cofre ausente
    ou quebrado dá lista vazia, e perfil que não decifra fica de fora."""
    caminho = Path(caminho) if caminho else caminho_do_cofre()
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- sem cofre ou cofre quebrado: o SIG-FT usa o extrato
        return []
    usuarios = dados.get("usuarios") if isinstance(dados, dict) else None
    if not isinstance(usuarios, dict):
        return []
    perfis = []
    for nome in sorted(usuarios):
        registro = usuarios[nome]
        if not isinstance(registro, dict):
            continue
        try:
            segredo = decifrar(str(registro.get("secret") or ""), bool(registro.get("cifrado", False)))
        except Exception:  # noqa: BLE001 -- outra conta do Windows: a DPAPI recusa
            continue
        perfil = PerfilAconex(str(nome), str(registro.get("client_id") or ""),
                              str(registro.get("user_id") or ""), segredo)
        if perfil.client_id and perfil.user_id and perfil.client_secret:
            perfis.append(perfil)
    return perfis


def escolher_perfil(perfis: list[PerfilAconex], preferido: str | None) -> PerfilAconex | None:
    """Com um perfil só, ele; com vários, o `preferido`; senão `None` (quem chamou pergunta)."""
    if len(perfis) == 1:
        return perfis[0]
    return next((p for p in perfis if p.nome == preferido), None)

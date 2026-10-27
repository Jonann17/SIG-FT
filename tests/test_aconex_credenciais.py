"""O SIG-FT LÊ o cofre de credenciais do DocManager (nunca escreve nele).

`Documentos\\DocManager_Itaipu\\credenciais.json`: um perfil por pessoa (client ID,
user ID e o Client Secret, cifrado pela DPAPI do Windows). Sem cofre, ou com o
segredo de outra conta do Windows, o perfil fica de fora e o SIG-FT cai no
extrato. O segredo não aparece em lugar nenhum. Desenho:
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §6.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import pytest

from sigft.core.aconex import credenciais as cred


def _cofre(caminho: Path, usuarios: dict) -> Path:
    caminho.write_text(json.dumps({"schema": 1, "usuarios": usuarios}, ensure_ascii=False), encoding="utf-8")
    return caminho


def _b64(texto: str) -> str:
    return base64.b64encode(texto.encode("utf-8")).decode("ascii")


def test_cofre_ausente_devolve_vazio(tmp_path):
    assert cred.ler_perfis(tmp_path / "credenciais.json") == []


def test_le_so_os_perfis_completos(tmp_path):
    cofre = _cofre(tmp_path / "credenciais.json", {
        "Luan Cozer": {"client_id": "SCP_LUAN", "user_id": "1208560183", "secret": _b64("s3gr3d0"), "cifrado": False},
        "Incompleto": {"client_id": "SCP_X", "user_id": "", "secret": _b64("x"), "cifrado": False},
    })
    perfis = cred.ler_perfis(cofre)
    assert [(p.nome, p.client_id, p.user_id, p.client_secret) for p in perfis] == [
        ("Luan Cozer", "SCP_LUAN", "1208560183", "s3gr3d0")]


def test_perfis_em_ordem_de_nome(tmp_path):
    cofre = _cofre(tmp_path / "credenciais.json", {
        "Rafhael Martins": {"client_id": "B", "user_id": "2", "secret": _b64("t"), "cifrado": False},
        "Luan Cozer": {"client_id": "A", "user_id": "1", "secret": _b64("s"), "cifrado": False},
    })
    assert [p.nome for p in cred.ler_perfis(cofre)] == ["Luan Cozer", "Rafhael Martins"]


def test_json_quebrado_devolve_vazio(tmp_path):
    cofre = tmp_path / "credenciais.json"
    cofre.write_text("{quebrado", encoding="utf-8")
    assert cred.ler_perfis(cofre) == []


def test_perfil_que_a_dpapi_recusa_fica_de_fora(tmp_path, monkeypatch):
    cofre = _cofre(tmp_path / "credenciais.json", {
        "Luan Cozer": {"client_id": "SCP_LUAN", "user_id": "1", "secret": _b64("cifrado-em-outra-conta"), "cifrado": True},
        "Rafhael Martins": {"client_id": "B", "user_id": "2", "secret": _b64("t"), "cifrado": False},
    })

    def _recusa(dados):
        raise OSError("CryptUnprotectData falhou (erro 13)")

    monkeypatch.setattr(cred, "_desproteger", _recusa)
    assert [p.nome for p in cred.ler_perfis(cofre)] == ["Rafhael Martins"]


def test_segredo_nao_aparece_no_repr():
    perfil = cred.PerfilAconex("Luan Cozer", "SCP_LUAN", "1208560183", "s3gr3d0")
    assert "s3gr3d0" not in repr(perfil)
    assert "s3gr3d0" not in str(perfil)


def test_escolher_perfil():
    um = [cred.PerfilAconex("Luan Cozer", "A", "1", "s")]
    dois = um + [cred.PerfilAconex("Rafhael Martins", "B", "2", "t")]
    assert cred.escolher_perfil(um, None).nome == "Luan Cozer"
    assert cred.escolher_perfil(dois, "Rafhael Martins").nome == "Rafhael Martins"
    assert cred.escolher_perfil(dois, None) is None
    assert cred.escolher_perfil(dois, "Fulano") is None
    assert cred.escolher_perfil([], None) is None


def test_caminho_do_cofre_respeita_a_variavel(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANAGER_DADOS_DIR", str(tmp_path))
    assert cred.caminho_do_cofre() == tmp_path / "credenciais.json"


def test_caminho_do_cofre_padrao_e_o_do_docmanager(monkeypatch):
    monkeypatch.delenv("DOCMANAGER_DADOS_DIR", raising=False)
    assert cred.caminho_do_cofre() == Path.home() / "Documents" / "DocManager_Itaipu" / "credenciais.json"


def test_ler_perfis_sem_caminho_usa_o_cofre_do_docmanager(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANAGER_DADOS_DIR", str(tmp_path))
    _cofre(tmp_path / "credenciais.json",
           {"Luan Cozer": {"client_id": "A", "user_id": "1", "secret": _b64("s"), "cifrado": False}})
    assert [p.nome for p in cred.ler_perfis()] == ["Luan Cozer"]


@pytest.mark.skipif(os.name != "nt", reason="a DPAPI só existe no Windows")
def test_decifra_o_que_a_dpapi_cifrou(tmp_path):
    cifrado = base64.b64encode(cred._dpapi("CryptProtectData", "s3gr3d0".encode("utf-8"))).decode("ascii")
    cofre = _cofre(tmp_path / "credenciais.json",
                   {"Luan Cozer": {"client_id": "A", "user_id": "1", "secret": cifrado, "cifrado": True}})
    assert [p.client_secret for p in cred.ler_perfis(cofre)] == ["s3gr3d0"]

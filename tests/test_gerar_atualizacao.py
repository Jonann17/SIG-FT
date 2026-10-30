r"""
`tools/gerar_atualizacao.py` -- a metade do BUILD da atualização só com o que
mudou. Ver `docs/superpowers/specs/2026-10-27-atualizacao-como-cmi-design.md`.

  A. o manifesto de arquivos (`arquivos.json`);
  B. a diferença entre duas versões;
  C. quais versões anteriores viram base de um `.zip` de arquivos;
  D. o registro no `latest.json`;
  E. a orquestração;
  F. a fiação no workflow.

[2026-10-30] Sem o instalador pequeno (Inno em modo atualização): só o `.zip`
de arquivos, como no DocManager.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def _modulo():
    spec = importlib.util.spec_from_file_location("gerar_atualizacao", RAIZ / "tools" / "gerar_atualizacao.py")
    modulo = importlib.util.module_from_spec(spec)
    # Registrado ANTES de executar: o `@dataclass` procura o módulo da classe
    # em `sys.modules`.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


ga = _modulo()

SHA_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"  # sha256(b"abc")


def _escrever(raiz: Path, rel: str, dados: bytes) -> None:
    caminho = raiz / rel
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(dados)


def _man(versao, **arquivos):
    """Manifesto à mão: `arquivo=(sha, tamanho)`; `__` no nome vira `/`."""
    return {"versao": versao,
            "arquivos": {nome.replace("__", "/"): {"sha256": sha, "tamanho": tam}
                         for nome, (sha, tam) in arquivos.items()}}


# ===========================================================================
# A. O manifesto de arquivos
# ===========================================================================
def test_manifesto_tem_cada_arquivo_com_hash_e_tamanho_e_o_changelog(tmp_path):
    dist = tmp_path / "dist" / "SIG-FT"
    _escrever(dist, "SIG-FT.exe", b"abc")
    _escrever(dist, "_internal/pacote/modulo.pyd", b"xyz12")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_bytes(b"abc")

    m = ga.manifesto(dist, changelog, "1.2.0-rc.3")

    assert m["versao"] == "1.2.0-rc.3"
    assert m["arquivos"]["SIG-FT.exe"] == {"sha256": SHA_ABC, "tamanho": 3}
    assert m["arquivos"]["_internal/pacote/modulo.pyd"] == {
        "sha256": hashlib.sha256(b"xyz12").hexdigest(), "tamanho": 5}
    assert m["arquivos"]["CHANGELOG.md"]["sha256"] == SHA_ABC
    assert sorted(m["arquivos"]) == ["CHANGELOG.md", "SIG-FT.exe", "_internal/pacote/modulo.pyd"]


# ===========================================================================
# B. A diferença
# ===========================================================================
def test_diferenca_copia_o_novo_e_o_mudado_e_remove_o_que_sumiu():
    base = _man("1.2.0-rc.3", **{"SIG-FT.exe": ("a", 10), "_internal__igual.dll": ("b", 500),
                                 "_internal__velho__x.pyd": ("c", 7), "CHANGELOG.md": ("d", 3)})
    novo = _man("1.2.0-rc.4", **{"SIG-FT.exe": ("A", 11), "_internal__igual.dll": ("b", 500),
                                 "_internal__novo.pyd": ("e", 4), "CHANGELOG.md": ("D", 5)})

    d = ga.diferenca(base, novo)

    assert d.copiar == ["CHANGELOG.md", "SIG-FT.exe", "_internal/novo.pyd"]
    assert d.remover == ["_internal/velho/x.pyd"]
    assert d.bytes_copiar == 11 + 4 + 5
    assert d.bytes_total == 11 + 500 + 4 + 5


def test_nada_mudou_e_diferenca_vazia():
    m = _man("1", **{"SIG-FT.exe": ("a", 1)})

    d = ga.diferenca(m, _man("2", **{"SIG-FT.exe": ("a", 1)}))

    assert (d.copiar, d.remover, d.bytes_copiar) == ([], [], 0)


# ===========================================================================
# C. Quais versões anteriores viram base
# ===========================================================================
def _rel(tag, *, pre=False, draft=False, com_manifesto=True):
    ativos = [{"name": "latest.json", "id": 1}]
    if com_manifesto:
        ativos.append({"name": ga.ARQUIVO_ARQUIVOS, "id": 2})
    return {"tag_name": tag, "prerelease": pre, "draft": draft, "assets": ativos}


def test_bases_sao_as_tres_mais_recentes_com_manifesto_fora_a_atual():
    releases = [_rel("v1.2.0-rc.6", pre=True), _rel("v1.2.0-rc.5", pre=True), _rel("v1.2.0-rc.4", pre=True),
                _rel("v1.2.0-rc.3", pre=True), _rel("v1.2.0-rc.2", pre=True, com_manifesto=False)]

    assert ga.escolher_bases(releases, "v1.2.0-rc.6") == ["v1.2.0-rc.5", "v1.2.0-rc.4", "v1.2.0-rc.3"]


def test_a_ultima_versao_normal_com_manifesto_entra_sempre():
    # Quem está no último release normal é quase todo mundo: o pequeno
    # dele não pode ficar de fora porque saíram várias rcs depois.
    releases = [_rel("v1.2.1-rc.3", pre=True), _rel("v1.2.1-rc.2", pre=True), _rel("v1.2.1-rc.1", pre=True),
                _rel("v1.2.0"), _rel("v1.1.1", com_manifesto=False)]

    assert ga.escolher_bases(releases, "v1.2.1") == ["v1.2.1-rc.3", "v1.2.1-rc.2", "v1.2.1-rc.1", "v1.2.0"]


def test_escolher_bases_imprime_sem_retorno_de_carro_no_windows(tmp_path, monkeypatch):
    """Medido nos Releases 1.2.0-rc.5, rc.6, 1.2.0 e 1.2.1-rc.1: so a ULTIMA
    base virava atualizacao pequena. No runner Windows o `print` sai com
    `\r\n`, o `$(...)` do bash so corta o fim, e as outras tags chegavam ao
    `gh release download` como "v1.2.0\r" -- "release not found". Quem estava
    na versao anterior (quase todo mundo) recebia o instalador completo."""
    import io
    import json

    releases = tmp_path / "releases.json"
    releases.write_text(json.dumps([_rel("v1.2.0"), _rel("v1.2.0-rc.7", pre=True),
                                    _rel("v1.2.0-rc.6", pre=True)]), encoding="utf-8")
    bruto = io.BytesIO()
    saida_do_windows = io.TextIOWrapper(bruto, encoding="cp1252", newline="\r\n")
    monkeypatch.setattr(sys, "stdout", saida_do_windows)

    ga.main(["escolher-bases", "--releases", str(releases), "--tag-atual", "v1.2.1-rc.1"])
    saida_do_windows.flush()

    assert b"\r" not in bruto.getvalue()
    assert bruto.getvalue().decode().split() == ["v1.2.0", "v1.2.0-rc.7", "v1.2.0-rc.6"]


def test_rascunho_e_versao_sem_manifesto_nao_sao_base():
    releases = [_rel("v1.3.0", draft=True), _rel("v1.2.0", com_manifesto=False), _rel("v1.1.1", com_manifesto=False)]

    assert ga.escolher_bases(releases, "v1.2.0-rc.3") == []


# ===========================================================================
# D. O registro no latest.json
# ===========================================================================
def test_registrar_acrescenta_so_de_e_arquivos(tmp_path):
    zipado = tmp_path / "SIG-FT_Itaipu_Arquivos_1.2.0-rc.3_para_1.2.0-rc.4.zip"
    zipado.write_bytes(b"abc")
    latest = {"versao": "1.2.0-rc.4", "sha256": "do-completo"}

    ga.registrar(latest, "1.2.0-rc.3", zipado)
    ga.registrar(latest, "1.2.0-rc.2", zipado)

    assert latest["sha256"] == "do-completo"
    assert latest["atualizacoes"][0] == {
        "de": "1.2.0-rc.3", "arquivos": {"arquivo": zipado.name, "sha256": SHA_ABC, "tamanho": 3}}
    assert [a["de"] for a in latest["atualizacoes"]] == ["1.2.0-rc.3", "1.2.0-rc.2"]


def test_a_entrada_nova_nao_engana_o_app_ate_a_1_3_0(tmp_path):
    """[2026-10-30] O app 1.2.0 a 1.3.0 procura o instalador pequeno pelo
    `arquivo` e pelo `sha256` da entrada (`_pacote_pequeno`): sem os dois, ele
    não acha asset nenhum e baixa o completo. O nome do zip também não pode
    ser tomado pelo instalador: não é `.exe`."""
    zipado = tmp_path / "SIG-FT_Itaipu_Arquivos_1.3.0_para_1.3.2.zip"
    zipado.write_bytes(b"zip")
    entrada = ga.registrar({}, "1.3.0", zipado)["atualizacoes"][0]

    assert "arquivo" not in entrada and "sha256" not in entrada
    assert not entrada["arquivos"]["arquivo"].lower().endswith(".exe")


# ===========================================================================
# E. A orquestração
# ===========================================================================
@pytest.fixture
def cenario_com_dist(tmp_path):
    """A `dist/SIG-FT` e o CHANGELOG de verdade, e o `novo` e a base tirados
    deles por `manifesto` -- como no release.yml."""
    raiz = tmp_path
    bases = raiz / "bases"
    bases.mkdir()
    saida = raiz / "installer" / "Output"
    latest = raiz / "latest.json"
    latest.write_text(json.dumps({"versao": "1.2.0-rc.4"}), encoding="utf-8")
    dist_base, dist = raiz / "base" / "SIG-FT", raiz / "dist" / "SIG-FT"
    _escrever(dist_base, "SIG-FT.exe", b"exe antigo")
    _escrever(dist_base, "_internal/modelo.bin", b"m" * 1000)
    _escrever(dist_base, "_internal/sumiu.pyd", b"sumiu")
    _escrever(dist, "SIG-FT.exe", b"exe novo")
    _escrever(dist, "_internal/modelo.bin", b"m" * 1000)
    _escrever(dist, "_internal/novo/mod.pyd", b"novo")
    log_base, changelog = raiz / "CHANGELOG_base.md", raiz / "CHANGELOG.md"
    log_base.write_bytes(b"# 1.2.0-rc.3")
    changelog.write_bytes(b"# 1.2.0-rc.4")
    (bases / "v1.2.0-rc.3.json").write_text(
        json.dumps(ga.manifesto(dist_base, log_base, "1.2.0-rc.3")), encoding="utf-8")
    novo = ga.manifesto(dist, changelog, "1.2.0-rc.4")
    return raiz, saida, bases, novo, latest, dist_base, dist, log_base, changelog


def _pacotes(cenario, **kwargs):
    raiz, saida, bases, novo, latest, _db, dist, _lb, changelog = cenario
    return ga.pacotes(kwargs.pop("novo", novo), bases, versao="1.2.0-rc.4", latest=latest, pasta=dist,
                      saida=saida, changelog=changelog, **kwargs)


def test_pacotes_montam_o_zip_so_com_os_arquivos_e_registram(cenario_com_dist):
    raiz, saida, bases, novo, latest, *_ = cenario_com_dist

    feitos = _pacotes(cenario_com_dist)

    so_arquivos = saida / "SIG-FT_Itaipu_Arquivos_1.2.0-rc.3_para_1.2.0-rc.4.zip"
    assert feitos == [so_arquivos]
    with zipfile.ZipFile(so_arquivos) as z:
        assert json.loads(z.read("manifesto.json")) == {
            "de": "1.2.0-rc.3", "para": "1.2.0-rc.4",
            "alterados": ["CHANGELOG.md", "SIG-FT.exe", "_internal/novo/mod.pyd"],
            "removidos": ["_internal/sumiu.pyd"]}
        assert z.read("arquivos/CHANGELOG.md") == b"# 1.2.0-rc.4"
        assert z.read("arquivos/SIG-FT.exe") == b"exe novo"
        assert "arquivos/_internal/modelo.bin" not in z.namelist()
    [entrada] = json.loads(latest.read_text(encoding="utf-8"))["atualizacoes"]
    assert entrada == {"de": "1.2.0-rc.3", "arquivos": {
        "arquivo": so_arquivos.name,
        "sha256": hashlib.sha256(so_arquivos.read_bytes()).hexdigest(),
        "tamanho": so_arquivos.stat().st_size,
    }}
    # Nada de instalador pequeno na saída.
    assert [p.name for p in saida.iterdir()] == [so_arquivos.name]


def test_o_zip_so_com_os_arquivos_leva_a_instalacao_a_versao_nova(cenario_com_dist):
    """De ponta a ponta: a pasta instalada da base (a dist + o CHANGELOG na
    raiz, como o Inno a deixa) recebe o zip e confere com o `arquivos.json`
    novo -- os caminhos do manifesto são os mesmos do instalador."""
    from sigft.services import pacote_arquivos

    raiz, saida, bases, novo, latest, dist_base, dist, log_base, changelog = cenario_com_dist
    _pacotes(cenario_com_dist)
    instalada = raiz / "instalada"
    shutil.copytree(dist_base, instalada)
    shutil.copyfile(log_base, instalada / "CHANGELOG.md")

    pacote_arquivos.aplicar(saida / pacote_arquivos.nome_pacote("1.2.0-rc.3", "1.2.0-rc.4"),
                            instalada, novo)
    pacote_arquivos.limpar_restos(instalada)

    assert ga.manifesto(instalada, None, "1.2.0-rc.4") == novo


def test_pacote_grande_demais_nao_compensa_e_fica_de_fora(cenario_com_dist):
    raiz, saida, bases, novo, latest, *_ = cenario_com_dist
    novo["arquivos"]["_internal/modelo.bin"]["sha256"] = "modelo-reconvertido"

    assert _pacotes(cenario_com_dist, novo=novo) == []
    assert not list(raiz.rglob("SIG-FT_Itaipu_Arquivos_*"))
    assert "atualizacoes" not in json.loads(latest.read_text(encoding="utf-8"))


def test_zip_que_falha_nao_derruba_o_release(cenario_com_dist, capsys):
    # O completo já está pronto e serve para todo mundo: vira aviso, não erro.
    raiz, saida, bases, novo, latest, _db, dist, *_ = cenario_com_dist
    (dist / "SIG-FT.exe").unlink()  # some depois do manifesto

    assert _pacotes(cenario_com_dist) == []
    assert "::warning" in capsys.readouterr().out
    assert not list(raiz.rglob("SIG-FT_Itaipu_Arquivos_*"))
    assert "atualizacoes" not in json.loads(latest.read_text(encoding="utf-8"))


def test_nada_mudou_nao_gera_zip(cenario_com_dist):
    raiz, saida, bases, novo, latest, *_ = cenario_com_dist
    (bases / "v1.2.0-rc.3.json").write_text(json.dumps(dict(novo, versao="1.2.0-rc.3")), encoding="utf-8")

    assert _pacotes(cenario_com_dist) == []


def test_base_da_mesma_versao_e_ignorada(cenario_com_dist):
    raiz, saida, bases, novo, latest, *_ = cenario_com_dist
    (bases / "v1.2.0-rc.4.json").write_text(json.dumps(novo), encoding="utf-8")

    feitos = _pacotes(cenario_com_dist)

    assert [p.name for p in feitos] == ["SIG-FT_Itaipu_Arquivos_1.2.0-rc.3_para_1.2.0-rc.4.zip"]


# ===========================================================================
# F. A fiação no workflow
# ===========================================================================
def test_o_release_gera_manifesto_bases_e_pacotes_e_publica(tmp_path):
    texto = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    posicao = {nome: texto.index(f"- name: {nome}") for nome in (
        "Montar o instalador", "Gerar o manifesto e as notas do Release",
        "Manifesto de arquivos e atualizacao por arquivos", "Publicar o Release")}

    # O zip se registra no latest.json: ele tem de existir antes; e o Release
    # so e publicado depois, com tudo.
    assert (posicao["Montar o instalador"] < posicao["Gerar o manifesto e as notas do Release"]
            < posicao["Manifesto de arquivos e atualizacao por arquivos"] < posicao["Publicar o Release"])
    for subcomando in ("manifesto", "escolher-bases", "pacotes"):
        assert f"tools/gerar_atualizacao.py {subcomando}" in texto
    publicar = texto[posicao["Publicar o Release"]:]
    assert '"arquivos.json#' in publicar


def test_o_release_publica_o_zip_so_com_os_arquivos():
    """O `pacotes` recebe a dist e o CHANGELOG (os mesmos do `manifesto`) e
    grava em installer/Output, de onde o `.zip` sobe com o resto."""
    texto = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    pacotes = texto[texto.index("tools/gerar_atualizacao.py pacotes"):]
    assert "--pasta dist/SIG-FT --changelog CHANGELOG.md --saida installer/Output" in pacotes[:300]
    publicar = texto[texto.index("- name: Publicar o Release"):]
    laco = 'for pacote in installer/Output/SIG-FT_Itaipu_Arquivos_*.zip; do'
    assert laco in publicar
    assert '"$pacote#Atualizacao so com os arquivos' in publicar
    # Antes do create/upload: vai no mesmo `ativos`, normal ou pré-lançamento.
    assert publicar.index(laco) < publicar.index("gh release create")
    assert ga.pacote_arquivos.nome_pacote("1", "2").startswith("SIG-FT_Itaipu_Arquivos_")


def test_o_release_nao_monta_nem_publica_o_instalador_pequeno():
    """[2026-10-30] O pequeno saiu: nada de ISCC em modo atualização nem dos
    `.bin`, `Atualizacao_*.zip` e `Update_*.exe`."""
    texto = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    for resto in ("/DAtualizacao", "--iscc", "Output/*.bin", "SIG-FT_Itaipu_Atualizacao_",
                  "SIG-FT_Itaipu_Update_"):
        assert resto not in texto, resto


def test_guardar_artefatos_nao_reprova_o_release_e_nao_leva_o_instalador_a_toa():
    # 2026-10-07: a cota de artefatos lotou com o instalador de ~300 MB de
    # cada run (que ja esta no Release) e o job da 1.2.0-rc.2 ficou vermelho
    # DEPOIS de publicar -- e sem salvar o cache do modelo do tradutor.
    texto = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    passos = texto.split("      - name: ")
    guardar = next(p for p in passos if p.startswith("Guardar os artefatos do build"))
    quando_falha = next(p for p in passos if p.startswith("Guardar o instalador quando o Release nao saiu"))

    assert "continue-on-error: true" in guardar and "continue-on-error: true" in quando_falha
    assert "*.exe" not in guardar
    assert "if: failure()" in quando_falha

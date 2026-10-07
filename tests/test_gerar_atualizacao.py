r"""
`tools/gerar_atualizacao.py` -- a metade do BUILD da atualização só com o que
mudou. Ver `docs/superpowers/specs/2026-10-07-atualizacao-incremental-design.md`.

  A. o manifesto de arquivos (`arquivos.json`);
  B. a diferença entre duas versões;
  C. os includes que o Inno compila em modo atualização;
  D. quais versões anteriores viram base de um instalador pequeno;
  E. o registro no `latest.json`;
  F. a orquestração (o ISCC é um dublê: só o Windows o roda).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
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
    assert d.pastas_vazias == ["_internal/velho"]
    assert d.bytes_copiar == 11 + 4 + 5
    assert d.bytes_total == 11 + 500 + 4 + 5


def test_pastas_que_somem_saem_da_mais_funda_para_a_mais_rasa():
    base = _man("1", **{"a__b__c__1.txt": ("x", 1), "a__2.txt": ("y", 1)})
    novo = _man("2", **{"a__2.txt": ("y", 1)})

    assert ga.diferenca(base, novo).pastas_vazias == ["a/b/c", "a/b"]


def test_nada_mudou_e_diferenca_vazia():
    m = _man("1", **{"SIG-FT.exe": ("a", 1)})

    d = ga.diferenca(m, _man("2", **{"SIG-FT.exe": ("a", 1)}))

    assert (d.copiar, d.remover, d.pastas_vazias, d.bytes_copiar) == ([], [], [], 0)


# ===========================================================================
# C. Os includes do Inno
# ===========================================================================
def test_include_de_arquivos_mapeia_dist_e_changelog_para_a_pasta_do_app():
    d = ga.Diferenca(copiar=["SIG-FT.exe", "_internal/pacote/m.pyd", "CHANGELOG.md"], remover=[],
                     pastas_vazias=[], bytes_copiar=0, bytes_total=0)

    linhas = [linha for linha in ga.include_arquivos(d).splitlines() if linha.startswith("Source:")]

    assert linhas == [
        r'Source: "..\dist\SIG-FT\SIG-FT.exe"; DestDir: "{app}"; Flags: ignoreversion',
        r'Source: "..\dist\SIG-FT\_internal\pacote\m.pyd"; DestDir: "{app}\_internal\pacote"; Flags: ignoreversion',
        r'Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion',
    ]


def test_include_escapa_chave_e_aspas_que_o_inno_leria_como_constante():
    # `{` abre constante no Inno ({app}, {tmp}...): literal é `{{`. Aspas
    # dentro de valor entre aspas dobram.
    d = ga.Diferenca(copiar=['_internal/x{y}/a"b.txt'], remover=['_internal/{z}.dat'],
                     pastas_vazias=['_internal/x{y}'], bytes_copiar=0, bytes_total=0)

    arquivos = ga.include_arquivos(d)
    remocoes = ga.include_remocoes(d)

    assert r'Source: "..\dist\SIG-FT\_internal\x{{y}\a""b.txt"; DestDir: "{app}\_internal\x{{y}"' in arquivos
    assert r'Type: files; Name: "{app}\_internal\{{z}.dat"' in remocoes
    assert r'Type: dirifempty; Name: "{app}\_internal\x{{y}"' in remocoes


def test_include_de_remocoes_apaga_arquivo_por_arquivo_e_nunca_a_pasta_do_app():
    d = ga.Diferenca(copiar=[], remover=["_internal/velho/x.pyd", "solto.txt"],
                     pastas_vazias=["_internal/velho"], bytes_copiar=0, bytes_total=0)

    entradas = [linha for linha in ga.include_remocoes(d).splitlines() if linha.startswith("Type:")]

    assert entradas == [
        r'Type: files; Name: "{app}\_internal\velho\x.pyd"',
        r'Type: files; Name: "{app}\solto.txt"',
        r'Type: dirifempty; Name: "{app}\_internal\velho"',
    ]


# ===========================================================================
# D. Quais versões anteriores viram base
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


def test_rascunho_e_versao_sem_manifesto_nao_sao_base():
    releases = [_rel("v1.3.0", draft=True), _rel("v1.2.0", com_manifesto=False), _rel("v1.1.1", com_manifesto=False)]

    assert ga.escolher_bases(releases, "v1.2.0-rc.3") == []


# ===========================================================================
# E. O registro no latest.json
# ===========================================================================
def test_registrar_acrescenta_de_arquivo_sha_e_tamanho(tmp_path):
    pacote = tmp_path / "SIG-FT_Itaipu_Atualizacao_1.2.0-rc.3_para_1.2.0-rc.4.bin"
    pacote.write_bytes(b"abc")
    latest = {"versao": "1.2.0-rc.4", "sha256": "do-completo"}

    ga.registrar(latest, "1.2.0-rc.3", pacote)
    ga.registrar(latest, "1.2.0-rc.2", pacote)

    assert latest["sha256"] == "do-completo"
    assert latest["atualizacoes"][0] == {"de": "1.2.0-rc.3", "arquivo": pacote.name, "sha256": SHA_ABC, "tamanho": 3}
    assert [a["de"] for a in latest["atualizacoes"]] == ["1.2.0-rc.3", "1.2.0-rc.2"]


def test_o_pacote_nao_termina_em_exe():
    # O app 1.1.1 baixa "o primeiro .exe do Release": com o pequeno em .exe,
    # ele poderia pegar um instalador que não serve para ele.
    assert ga.nome_do_pacote("1.2.0-rc.3", "1.2.0-rc.4") == "SIG-FT_Itaipu_Atualizacao_1.2.0-rc.3_para_1.2.0-rc.4.bin"


# ===========================================================================
# F. A orquestração
# ===========================================================================
class _ISCC:
    """O ISCC de mentira: anota a linha de comando e "gera" o instalador."""

    def __init__(self, saida: Path, codigo=0):
        self.chamadas = []
        self.saida = saida
        self.codigo = codigo

    def __call__(self, comando, **_kwargs):
        self.chamadas.append(list(comando))
        if self.codigo == 0:
            self.saida.mkdir(parents=True, exist_ok=True)
            (self.saida / "SIG-FT_Itaipu_Atualizacao.exe").write_bytes(b"instalador pequeno")

        class _R:
            returncode = self.codigo
        return _R()


@pytest.fixture
def cenario(tmp_path):
    instalador = tmp_path / "installer"
    instalador.mkdir()
    (instalador / "sigft.iss").write_text("; de mentira", encoding="utf-8")
    bases = tmp_path / "bases"
    bases.mkdir()
    novo = _man("1.2.0-rc.4", **{"SIG-FT.exe": ("A", 30), "_internal__modelo.bin": ("m", 1000)})
    (bases / "v1.2.0-rc.3.json").write_text(json.dumps(
        _man("1.2.0-rc.3", **{"SIG-FT.exe": ("a", 29), "_internal__modelo.bin": ("m", 1000),
                              "_internal__sumiu.pyd": ("s", 5)})), encoding="utf-8")
    latest = tmp_path / "latest.json"
    latest.write_text(json.dumps({"versao": "1.2.0-rc.4"}), encoding="utf-8")
    return tmp_path, instalador, bases, novo, latest


def test_pacotes_monta_compila_renomeia_e_registra(cenario):
    raiz, instalador, bases, novo, latest = cenario
    iscc = _ISCC(instalador / "Output")

    feitos = ga.pacotes(novo, bases, versao="1.2.0-rc.4", numerica="1.2.0", iscc="ISCC.exe",
                        iss=instalador / "sigft.iss", latest=latest, executar=iscc)

    assert iscc.chamadas == [["ISCC.exe", "/DAtualizacao=1", "/DVersaoDe=1.2.0-rc.3", "/DMyAppVersion=1.2.0-rc.4",
                              "/DMyVersionInfo=1.2.0", str(instalador / "sigft.iss")]]
    assert [p.name for p in feitos] == ["SIG-FT_Itaipu_Atualizacao_1.2.0-rc.3_para_1.2.0-rc.4.bin"]
    assert feitos[0].read_bytes() == b"instalador pequeno"
    assert "SIG-FT.exe" in (instalador / ga.INCLUDE_ARQUIVOS).read_text(encoding="utf-8-sig")
    assert "sumiu.pyd" in (instalador / ga.INCLUDE_REMOCOES).read_text(encoding="utf-8-sig")
    registrado = json.loads(latest.read_text(encoding="utf-8"))["atualizacoes"]
    assert [(a["de"], a["arquivo"]) for a in registrado] == [("1.2.0-rc.3", feitos[0].name)]


def test_pacote_grande_demais_nao_compensa_e_fica_de_fora(cenario):
    raiz, instalador, bases, novo, latest = cenario
    novo["arquivos"]["_internal/modelo.bin"]["sha256"] = "modelo-reconvertido"  # 1000 de 1030 bytes
    iscc = _ISCC(instalador / "Output")

    feitos = ga.pacotes(novo, bases, versao="1.2.0-rc.4", numerica="1.2.0", iscc="ISCC.exe",
                        iss=instalador / "sigft.iss", latest=latest, executar=iscc)

    assert feitos == [] and iscc.chamadas == []
    assert "atualizacoes" not in json.loads(latest.read_text(encoding="utf-8"))


def test_iscc_que_falha_nao_derruba_o_release(cenario, capsys):
    # O instalador completo já está pronto e serve para todo mundo: o pequeno
    # que não compilou vira aviso no log do workflow, não erro.
    raiz, instalador, bases, novo, latest = cenario

    feitos = ga.pacotes(novo, bases, versao="1.2.0-rc.4", numerica="1.2.0", iscc="ISCC.exe",
                        iss=instalador / "sigft.iss", latest=latest, executar=_ISCC(instalador / "Output", codigo=2))

    assert feitos == []
    assert "::warning" in capsys.readouterr().out


def test_base_da_mesma_versao_e_ignorada(cenario):
    raiz, instalador, bases, novo, latest = cenario
    (bases / "v1.2.0-rc.4.json").write_text(json.dumps(novo), encoding="utf-8")
    iscc = _ISCC(instalador / "Output")

    ga.pacotes(novo, bases, versao="1.2.0-rc.4", numerica="1.2.0", iscc="ISCC.exe",
               iss=instalador / "sigft.iss", latest=latest, executar=iscc)

    assert [c[2] for c in iscc.chamadas] == ["/DVersaoDe=1.2.0-rc.3"]


# ===========================================================================
# G. A fiação no workflow
# ===========================================================================
def test_o_release_gera_manifesto_bases_e_pacotes_e_publica_os_dois(tmp_path):
    texto = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    posicao = {nome: texto.index(f"- name: {nome}") for nome in (
        "Montar o instalador", "Gerar o manifesto e as notas do Release",
        "Manifesto de arquivos e instaladores pequenos", "Publicar o Release")}

    # O pequeno se registra no latest.json: ele tem de existir antes; e o
    # Release so e publicado depois, com tudo.
    assert (posicao["Montar o instalador"] < posicao["Gerar o manifesto e as notas do Release"]
            < posicao["Manifesto de arquivos e instaladores pequenos"] < posicao["Publicar o Release"])
    for subcomando in ("manifesto", "escolher-bases", "pacotes"):
        assert f"tools/gerar_atualizacao.py {subcomando}" in texto
    publicar = texto[posicao["Publicar o Release"]:]
    assert '"arquivos.json#' in publicar and "installer/Output/*.bin" in publicar


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

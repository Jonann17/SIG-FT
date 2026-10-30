r"""
`sigft/services/pacote_arquivos.py` -- a atualização só com os arquivos, que o
próprio SIG-FT aplica aberto. Ver
`docs/superpowers/specs/2026-10-27-atualizacao-como-cmi-design.md`.

Montar e aplicar em pastas temporárias; o que só o Windows prova (renomear o
`.exe` em uso) entra como um `rename` que falha num caminho só.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from sigft.services import pacote_arquivos as pa


def _escrever(raiz: Path, rel: str, dados: bytes) -> None:
    caminho = raiz / rel
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(dados)


def _manifesto(pasta: Path, versao: str) -> dict:
    """O formato do `arquivos.json` do SIG-FT: `{"sha256", "tamanho"}`."""
    return {"versao": versao, "arquivos": {
        p.relative_to(pasta).as_posix(): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                          "tamanho": p.stat().st_size}
        for p in sorted(pasta.rglob("*")) if p.is_file()}}


def _retrato(pasta: Path) -> dict:
    return {p.relative_to(pasta).as_posix(): p.read_bytes()
            for p in sorted(pasta.rglob("*")) if p.is_file()}


@pytest.fixture
def cenario(tmp_path):
    """A pasta instalada (1.0) e a versão nova (1.1) com um arquivo alterado,
    um novo numa pasta nova e um removido."""
    instalada = tmp_path / "instalada"
    _escrever(instalada, "SIG-FT.exe", b"exe antigo")
    _escrever(instalada, "_internal/igual.pyd", b"igual")
    _escrever(instalada, "_internal/sumiu.pyd", b"vai sumir")
    _escrever(instalada, "unins000.dat", b"do instalador")  # fora do manifesto
    nova = tmp_path / "nova"
    _escrever(nova, "SIG-FT.exe", b"exe novo")
    _escrever(nova, "_internal/igual.pyd", b"igual")
    _escrever(nova, "_internal/novo/modulo.pyd", b"modulo novo")
    novo = _manifesto(nova, "1.1")
    saida = tmp_path / "saida"
    saida.mkdir()
    zipado = pa.montar(nova, ["SIG-FT.exe", "_internal/novo/modulo.pyd"], ["_internal/sumiu.pyd"],
                       "1.0", "1.1", saida)
    return instalada, nova, novo, zipado


def test_nome_do_pacote_nao_e_o_do_pequeno_nem_exe():
    from sigft.services import updater

    nome = pa.nome_pacote("1.3.0", "1.3.1")
    assert nome == "SIG-FT_Itaipu_Arquivos_1.3.0_para_1.3.1.zip"
    assert not nome.startswith(updater.PREFIXOS_DO_PEQUENO)
    assert not nome.lower().endswith(".exe")


def test_montar_grava_manifesto_e_os_arquivos(cenario):
    _instalada, nova, _novo, zipado = cenario
    with zipfile.ZipFile(zipado) as z:
        assert json.loads(z.read("manifesto.json")) == {
            "de": "1.0", "para": "1.1",
            "alterados": ["SIG-FT.exe", "_internal/novo/modulo.pyd"],
            "removidos": ["_internal/sumiu.pyd"]}
        assert sorted(z.namelist()) == ["arquivos/SIG-FT.exe", "arquivos/_internal/novo/modulo.pyd",
                                        "manifesto.json"]
        assert z.read("arquivos/SIG-FT.exe") == b"exe novo"


def test_montar_leva_extras_de_fora_da_pasta(tmp_path):
    pasta = tmp_path / "dist"
    _escrever(pasta, "SIG-FT.exe", b"x")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_bytes(b"# novidades")
    zipado = pa.montar(pasta, ["CHANGELOG.md", "SIG-FT.exe"], [], "1", "2", tmp_path,
                       extras={"CHANGELOG.md": changelog})
    with zipfile.ZipFile(zipado) as z:
        assert z.read("arquivos/CHANGELOG.md") == b"# novidades"


def test_montar_recusa_nome_que_o_app_recusaria(tmp_path):
    with pytest.raises(pa.ErroPacote):
        pa.montar(tmp_path, ["../fora.exe"], [], "1", "2", tmp_path)


def test_aplicar_troca_acrescenta_remove_e_confere(cenario):
    instalada, nova, novo, zipado = cenario

    alterados = pa.aplicar(zipado, instalada, novo)

    assert alterados == ["SIG-FT.exe", "_internal/novo/modulo.pyd"]
    depois = {k: v for k, v in _retrato(instalada).items() if not k.endswith(pa.SUFIXO_ANTIGO)}
    assert depois == {**_retrato(nova), "unins000.dat": b"do instalador"}
    # Os antigos ficam afastados até a próxima abertura.
    assert (instalada / ("SIG-FT.exe" + pa.SUFIXO_ANTIGO)).read_bytes() == b"exe antigo"
    assert (instalada / ("_internal/sumiu.pyd" + pa.SUFIXO_ANTIGO)).is_file()
    assert pa.limpar_restos(instalada) == 2
    assert not list(instalada.rglob(f"*{pa.SUFIXO_ANTIGO}"))


def test_aplicar_aceita_manifesto_com_sha_puro(cenario):
    # O formato do CMI (`{"rel": "<sha>"}`) também confere.
    instalada, _nova, novo, zipado = cenario
    puro = {"versao": novo["versao"], "arquivos": {k: v["sha256"] for k, v in novo["arquivos"].items()}}
    assert pa.aplicar(zipado, instalada, puro)


def test_arquivo_que_nao_confere_desfaz_tudo(cenario):
    instalada, _nova, novo, zipado = cenario
    antes = _retrato(instalada)
    novo["arquivos"]["_internal/novo/modulo.pyd"]["sha256"] = "0" * 64  # corrompido

    with pytest.raises(pa.ErroPacote, match="modulo.pyd"):
        pa.aplicar(zipado, instalada, novo)

    assert _retrato(instalada) == antes
    assert not (instalada / "_internal" / "novo").exists()  # a pasta criada também sai


def test_arquivo_em_uso_que_nao_renomeia_desfaz_tudo(cenario, monkeypatch):
    """No Windows, o que não deixa renomear (outro processo com o arquivo
    aberto sem compartilhar) faz o passo falhar no meio: o que já foi trocado
    volta."""
    instalada, _nova, novo, zipado = cenario
    antes = _retrato(instalada)
    renomear = Path.rename

    def rename_que_falha(self, alvo):
        if self.name == "sumiu.pyd":
            raise PermissionError(32, "em uso por outro processo")
        return renomear(self, alvo)

    monkeypatch.setattr(Path, "rename", rename_que_falha)
    with pytest.raises(pa.ErroPacote, match="desfeita"):
        pa.aplicar(zipado, instalada, novo)

    assert _retrato(instalada) == antes


def test_resto_de_atualizacao_anterior_e_substituido(cenario):
    instalada, _nova, novo, zipado = cenario
    (instalada / ("SIG-FT.exe" + pa.SUFIXO_ANTIGO)).write_bytes(b"de outra vez")

    pa.aplicar(zipado, instalada, novo)

    assert (instalada / ("SIG-FT.exe" + pa.SUFIXO_ANTIGO)).read_bytes() == b"exe antigo"


def test_resto_ainda_em_uso_ganha_outro_nome(cenario, monkeypatch):
    instalada, _nova, novo, zipado = cenario
    resto = instalada / ("SIG-FT.exe" + pa.SUFIXO_ANTIGO)
    resto.write_bytes(b"ainda aberto")
    apagar = Path.unlink

    def unlink_que_falha(self, *a, **k):
        if self == resto:
            raise PermissionError(32, "em uso")
        return apagar(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", unlink_que_falha)
    pa.aplicar(zipado, instalada, novo)

    assert resto.read_bytes() == b"ainda aberto"
    assert (instalada / ("SIG-FT.exe.1" + pa.SUFIXO_ANTIGO)).read_bytes() == b"exe antigo"


def test_pacote_para_outra_versao_e_recusado(cenario):
    instalada, _nova, novo, zipado = cenario
    antes = _retrato(instalada)
    novo["versao"] = "1.2"

    with pytest.raises(pa.ErroPacote, match="1.2"):
        pa.aplicar(zipado, instalada, novo)

    assert _retrato(instalada) == antes


@pytest.mark.parametrize("nome", [
    "../fora.exe", "_internal/../../fora.exe", "/etc/fora", "..\\..\\fora.exe",
    "C:/Windows/fora.dll", "arquivo.txt:fluxo", "pasta/./x", "pasta//x", "x.. ", "",
])
def test_zip_slip_e_recusado_antes_de_tocar_em_nada(tmp_path, nome):
    pasta = tmp_path / "instalada"
    _escrever(pasta, "SIG-FT.exe", b"original")
    antes = _retrato(pasta)
    zipado = tmp_path / "malicioso.zip"
    with zipfile.ZipFile(zipado, "w") as z:
        z.writestr("manifesto.json", json.dumps({
            "de": "1", "para": "2", "alterados": ["SIG-FT.exe", nome], "removidos": []}))
        z.writestr("arquivos/SIG-FT.exe", b"trocado")
        z.writestr(f"arquivos/{nome}", b"malicioso")

    with pytest.raises(pa.ErroPacote, match="invalido"):
        pa.aplicar(zipado, pasta, {"versao": "2", "arquivos": {}})

    assert _retrato(pasta) == antes
    assert not (tmp_path / "fora.exe").exists()


def test_zip_sem_manifesto_e_recusado(tmp_path):
    zipado = tmp_path / "x.zip"
    with zipfile.ZipFile(zipado, "w") as z:
        z.writestr("outra.txt", b"")
    with pytest.raises(pa.ErroPacote):
        pa.aplicar(zipado, tmp_path, {"versao": "2", "arquivos": {}})


def test_zip_que_nao_abre_vira_erro_pacote(tmp_path):
    zipado = tmp_path / "x.zip"
    zipado.write_bytes(b"nao e zip")
    with pytest.raises(pa.ErroPacote):
        pa.aplicar(zipado, tmp_path, {"versao": "2", "arquivos": {}})


def test_limpar_restos_conta_apaga_e_deixa_o_que_esta_em_uso(tmp_path, monkeypatch):
    _escrever(tmp_path, "a.exe" + pa.SUFIXO_ANTIGO, b"")
    _escrever(tmp_path, "_internal/b.dll.1" + pa.SUFIXO_ANTIGO, b"")
    _escrever(tmp_path, "_internal/em_uso.dll" + pa.SUFIXO_ANTIGO, b"")
    _escrever(tmp_path, "SIG-FT.exe", b"fica")
    apagar = Path.unlink

    def unlink_que_falha(self, *a, **k):
        if self.name.startswith("em_uso"):
            raise PermissionError(32, "em uso")
        return apagar(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", unlink_que_falha)
    assert pa.limpar_restos(tmp_path) == 2
    assert sorted(_retrato(tmp_path)) == ["SIG-FT.exe", "_internal/em_uso.dll" + pa.SUFIXO_ANTIGO]


def test_desfazer_que_nao_renomeia_de_volta_copia_o_original(cenario, monkeypatch):
    """[2026-10-27, revisao] O `.sigft-old` preso (antivirus) nao renomeia de
    volta: o desfazer COPIA, e o original volta inteiro."""
    instalada, nova, novo, zipado = cenario
    antes = _retrato(instalada)
    (nova / "SIG-FT.exe").write_bytes(b"estragado")  # nao confere -> desfaz
    renomear = Path.rename

    def rename_preso(self, alvo):
        if self.name.endswith(pa.SUFIXO_ANTIGO):
            raise PermissionError(32, "em uso")
        return renomear(self, alvo)

    monkeypatch.setattr(Path, "rename", rename_preso)
    with pytest.raises(pa.ErroPacote):
        pa.aplicar(zipado, instalada, _manifesto(nova, "1.1"))
    depois = {k: v for k, v in _retrato(instalada).items() if not k.endswith(pa.SUFIXO_ANTIGO)}
    assert depois == antes


def _zip_com(tmp_path, alterados, removidos, conteudo):
    nova = tmp_path / "nova_sobreposta"
    for rel, dados in conteudo.items():
        _escrever(nova, rel, dados)
    saida = tmp_path / "saida_sobreposta"
    saida.mkdir()
    zipado = saida / pa.nome_pacote("1.0", "1.1")
    with zipfile.ZipFile(zipado, "w") as z:
        z.writestr(pa.MANIFESTO, json.dumps({"de": "1.0", "para": "1.1",
                                             "alterados": alterados, "removidos": removidos}))
        for rel in alterados:
            z.write(nova / rel, pa.PASTA_NO_ZIP + rel)
    return nova, zipado


def test_caminho_em_alterados_e_removidos_nao_apaga_o_original(tmp_path):
    """[2026-10-27, revisao] A troca so de caixa (`PIL/x.pyd` -> `pil/x.pyd`)
    no Windows e o MESMO arquivo nas duas listas. O removido que coincide com
    um alterado (sem caixa) e ignorado; sem isso, o desfazer apagava o original."""
    instalada = tmp_path / "instalada"
    _escrever(instalada, "a.dll", b"OLD")
    nova, zipado = _zip_com(tmp_path, ["a.dll"], ["a.dll", "A.DLL"], {"a.dll": b"NEW"})
    pa.aplicar(zipado, instalada, _manifesto(nova, "1.1"))
    assert _retrato(instalada) == {"a.dll": b"NEW", "a.dll" + pa.SUFIXO_ANTIGO: b"OLD"}


def test_caminho_duplicado_em_alterados_e_recusado_sem_tocar_em_nada(tmp_path):
    instalada = tmp_path / "instalada"
    _escrever(instalada, "a.dll", b"OLD")
    nova, zipado = _zip_com(tmp_path, ["a.dll", "A.dll"], [], {"a.dll": b"NEW", "A.dll": b"NEW"})
    with pytest.raises(pa.ErroPacote):
        pa.aplicar(zipado, instalada, _manifesto(nova, "1.1"))
    assert _retrato(instalada) == {"a.dll": b"OLD"}


def test_afastar_nunca_apaga_o_antigo_que_esta_rodada_criou(tmp_path, monkeypatch):
    """Mesmo que o caminho chegue duas vezes ao afastamento, o `.sigft-old`
    criado nesta rodada nao e apagado: o segundo vai para `.1.sigft-old`."""
    _escrever(tmp_path, "a.dll", b"OLD")
    reservados: set = set()
    primeiro = pa._afastar(tmp_path / "a.dll", reservados)
    _escrever(tmp_path, "a.dll", b"NEW")
    segundo = pa._afastar(tmp_path / "a.dll", reservados)
    assert primeiro != segundo
    assert primeiro.read_bytes() == b"OLD" and segundo.read_bytes() == b"NEW"


def test_o_modulo_nao_importa_qt_nem_fora_da_stdlib():
    # Roda no runner do Release, que chama o script sem o ambiente do app.
    import ast

    arvore = ast.parse(Path(pa.__file__).read_text(encoding="utf-8"))
    importados = {n.module.split(".")[0] if isinstance(n, ast.ImportFrom) else a.name.split(".")[0]
                  for n in ast.walk(arvore) if isinstance(n, (ast.Import, ast.ImportFrom))
                  for a in (n.names if isinstance(n, ast.Import) else [None])}
    assert importados <= {"__future__", "hashlib", "json", "shutil", "zipfile", "collections", "pathlib"}


# -- conferir: SHA256 no que o pacote escreveu, tamanho no resto -------------
# Copiado do `conferir` do DocManager (`docmanager/services/pacote.py`): ler
# a pasta inteira com o antivirus abrindo cada arquivo levava minutos.

def _pasta_conferida(tmp_path):
    pasta = tmp_path / "pasta"
    _escrever(pasta, "SIG-FT.exe", b"exe novo")
    _escrever(pasta, "_internal/igual.pyd", b"igual")
    return pasta, _manifesto(pasta, "1.1")


def test_conferir_intocado_com_o_tamanho_certo_passa_mesmo_com_outro_conteudo(tmp_path):
    pasta, novo = _pasta_conferida(tmp_path)
    _escrever(pasta, "_internal/igual.pyd", b"IGUAL")  # mesmo tamanho, outro conteúdo

    pa.conferir(pasta, novo, ["SIG-FT.exe"])  # por desenho: só o tamanho


def test_conferir_intocado_com_outro_tamanho_falha(tmp_path):
    pasta, novo = _pasta_conferida(tmp_path)
    _escrever(pasta, "_internal/igual.pyd", b"igual mais longo")

    with pytest.raises(pa.ErroPacote, match="igual.pyd"):
        pa.conferir(pasta, novo, ["SIG-FT.exe"])


def test_conferir_escrito_com_sha_errado_falha_mesmo_com_o_tamanho_certo(tmp_path):
    pasta, novo = _pasta_conferida(tmp_path)
    _escrever(pasta, "SIG-FT.exe", b"exe NOVO")

    with pytest.raises(pa.ErroPacote, match="SIG-FT.exe"):
        pa.conferir(pasta, novo, ["SIG-FT.exe"])


def test_conferir_entrada_sem_tamanho_volta_ao_sha(tmp_path):
    pasta, novo = _pasta_conferida(tmp_path)
    _escrever(pasta, "_internal/igual.pyd", b"IGUAL")
    del novo["arquivos"]["_internal/igual.pyd"]["tamanho"]

    with pytest.raises(pa.ErroPacote, match="igual.pyd"):
        pa.conferir(pasta, novo, [])
    # O formato do CMI (o SHA puro) também.
    puro = {"versao": "1.1", "arquivos": {k: v["sha256"] for k, v in novo["arquivos"].items()}}
    with pytest.raises(pa.ErroPacote, match="igual.pyd"):
        pa.conferir(pasta, puro, [])


def test_conferir_arquivo_que_falta_falha(tmp_path):
    pasta, novo = _pasta_conferida(tmp_path)
    (pasta / "_internal" / "igual.pyd").unlink()

    with pytest.raises(pa.ErroPacote, match="igual.pyd"):
        pa.conferir(pasta, novo, ["SIG-FT.exe"])


def test_conferir_chama_o_progresso_total_vezes_e_termina_em_total(tmp_path):
    pasta, novo = _pasta_conferida(tmp_path)
    vistos = []

    pa.conferir(pasta, novo, ["SIG-FT.exe"], progresso=lambda feitos, total: vistos.append((feitos, total)))

    assert vistos == [(1, 2), (2, 2)]


def test_conferir_trocados_sem_diferenca_de_caixa(tmp_path):
    # O Windows não distingue caixa: `sig-ft.EXE` no pacote é o `SIG-FT.exe`
    # do manifesto, e ele foi ESCRITO -- vale o SHA, não o tamanho.
    pasta, novo = _pasta_conferida(tmp_path)
    _escrever(pasta, "SIG-FT.exe", b"exe NOVO")

    with pytest.raises(pa.ErroPacote, match="SIG-FT.exe"):
        pa.conferir(pasta, novo, ["sig-ft.EXE"])


def test_aplicar_confere_intocado_pelo_tamanho_e_desfaz_tudo_quando_nao_bate(cenario):
    instalada, _nova, novo, zipado = cenario
    antes = _retrato(instalada)
    novo["arquivos"]["_internal/igual.pyd"]["tamanho"] += 1  # a pasta não é a 1.0

    with pytest.raises(pa.ErroPacote, match="igual.pyd"):
        pa.aplicar(zipado, instalada, novo)

    assert _retrato(instalada) == antes
    assert not (instalada / "_internal" / "novo").exists()


def test_aplicar_nao_le_o_intocado_e_repassa_o_progresso(cenario, monkeypatch):
    instalada, _nova, novo, zipado = cenario
    lidos, vistos = [], []
    original = pa.sha256
    monkeypatch.setattr(pa, "sha256", lambda caminho: lidos.append(caminho.name) or original(caminho))

    pa.aplicar(zipado, instalada, novo, progresso=lambda f, t: vistos.append((f, t)))

    assert sorted(lidos) == ["SIG-FT.exe", "modulo.pyd"]  # o `igual.pyd` não foi lido
    assert vistos[-1] == (3, 3) and len(vistos) == 3

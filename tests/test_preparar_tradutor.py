r"""`tools/preparar_tradutor.py`: gera a pasta do modelo que vai no instalador.

A conversão de verdade precisa de `torch` e `transformers` e roda no workflow
de release; aqui o download e o conversor são dublados, e o que se prova é o
que o script garante: revisão FIXA, pasta completa, atribuição da licença,
troca atômica e o modelo fora do Git.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from sigft.core import tradutor_local

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("preparar_tradutor", RAIZ / "tools" / "preparar_tradutor.py")
pt = importlib.util.module_from_spec(_spec)
sys.modules["preparar_tradutor"] = pt
_spec.loader.exec_module(pt)


def _hf_falso(tmp_path):
    """O que o `snapshot_download` deixaria no disco."""
    pasta = tmp_path / "hf"
    pasta.mkdir()
    for nome in ("source.spm", "target.spm", "README.md", "config.json", "pytorch_model.bin"):
        (pasta / nome).write_text(nome, encoding="utf-8")
    return pasta


def _conversor_falso(chamadas):
    def converter(origem, destino, quantizacao):
        chamadas.append((str(origem), str(destino), quantizacao))
        Path(destino).mkdir(parents=True, exist_ok=True)
        (Path(destino) / "model.bin").write_bytes(b"pesos")
        (Path(destino) / "config.json").write_text("{}", encoding="utf-8")
        (Path(destino) / "shared_vocabulary.json").write_text("[]", encoding="utf-8")
    return converter


def test_a_revisao_do_modelo_e_fixa():
    """Um `main` que muda sozinho mudaria a tradução sem ninguém ver."""
    assert pt.MODELO_HF == "Helsinki-NLP/opus-mt-tc-big-itc-itc"
    assert len(pt.REVISAO) == 40 and all(c in "0123456789abcdef" for c in pt.REVISAO)


def test_prepara_a_pasta_completa_com_origem_e_licenca(tmp_path):
    chamadas, baixados = [], []
    destino = tmp_path / "recursos" / "tradutor_pt_es"
    pt.preparar(destino,
                baixar=lambda modelo, revisao: baixados.append((modelo, revisao)) or _hf_falso(tmp_path),
                converter=_conversor_falso(chamadas))
    assert baixados == [(pt.MODELO_HF, pt.REVISAO)]
    assert [q for _, _, q in chamadas] == ["int8"]
    assert tradutor_local.modelo_completo(destino)
    origem = json.loads((destino / "origem.json").read_text(encoding="utf-8"))
    assert origem["modelo"] == pt.MODELO_HF and origem["revisao"] == pt.REVISAO
    assert "CC-BY 4.0" in origem["licenca"]
    assert "Helsinki-NLP" in (destino / "LEIA-ME.txt").read_text(encoding="utf-8")
    assert not any(p.name.endswith(".tmp") for p in destino.parent.iterdir())


def test_pasta_ja_completa_nao_baixa_de_novo(tmp_path):
    destino = tmp_path / "pronto"
    destino.mkdir()
    for nome in tradutor_local.ARQUIVOS_DO_MODELO:
        (destino / nome).write_bytes(b"x")

    def nao_pode(*_a, **_k):
        raise AssertionError("baixou de novo")

    pt.preparar(destino, baixar=nao_pode, converter=nao_pode)


def test_conversao_que_falha_nao_deixa_pasta_pela_metade(tmp_path):
    destino = tmp_path / "tradutor_pt_es"

    def quebra(origem, destino_tmp, quantizacao):
        Path(destino_tmp).mkdir(parents=True)
        (Path(destino_tmp) / "model.bin").write_bytes(b"meio")
        raise RuntimeError("sem memoria")

    with pytest.raises(RuntimeError):
        pt.preparar(destino, baixar=lambda m, r: _hf_falso(tmp_path), converter=quebra)
    assert not destino.exists()


def test_verificar_diz_se_a_pasta_serve(tmp_path, capsys):
    assert pt.main(["--verificar", "--destino", str(tmp_path / "nada")]) == 1
    pronto = tmp_path / "pronto"
    pronto.mkdir()
    for nome in tradutor_local.ARQUIVOS_DO_MODELO:
        (pronto / nome).write_bytes(b"x")
    assert pt.main(["--verificar", "--destino", str(pronto)]) == 0


def test_o_destino_padrao_e_onde_o_app_procura_e_fica_fora_do_git():
    assert pt.DESTINO_PADRAO == RAIZ / "recursos" / tradutor_local.NOME_DA_PASTA
    assert pt.DESTINO_PADRAO in tradutor_local._pastas_padrao()
    gitignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert "recursos/tradutor_pt_es/" in gitignore

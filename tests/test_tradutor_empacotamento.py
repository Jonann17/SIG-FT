r"""O tradutor local chega ao instalador? (2026-09-25)

Três elos, e basta um solto para a tela 4.2 abrir num app que não traduz:

1. `requirements.txt` instala `ctranslate2` e `sentencepiece`;
2. o workflow de release PREPARA o modelo (`tools/preparar_tradutor.py`)
   antes dos testes e do PyInstaller -- antes dos testes para que os testes
   com o modelo de verdade rodem no Windows;
3. o `SIG-FT.spec` embute a pasta no lugar onde `tradutor_local` procura, e
   declara os dois pacotes (o motor os importa por nome, o que a análise
   estática do PyInstaller não enxerga).

A prova final é a `--conferir-pacote`, que traduz uma frase dentro do .exe
(`test_conferencia_do_pacote.py`).
"""
from pathlib import Path

import pytest

from sigft.core import tradutor_local

RAIZ = Path(__file__).resolve().parent.parent
SPEC = (RAIZ / "SIG-FT.spec").read_text(encoding="utf-8")
WORKFLOW = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")


def test_requirements_instala_o_motor():
    linhas = [linha.split(";")[0].strip().lower()
              for linha in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
              if linha.strip() and not linha.strip().startswith("#")]
    assert any(linha.startswith("ctranslate2") for linha in linhas)
    assert any(linha.startswith("sentencepiece") for linha in linhas)


def test_o_spec_embute_o_modelo_onde_o_app_procura():
    assert '"recursos", "tradutor_pt_es"' in SPEC or "recursos/tradutor_pt_es" in SPEC
    assert f'"modelos", "{tradutor_local.NOME_DA_PASTA}"' in SPEC


def test_o_spec_declara_os_pacotes_importados_por_nome():
    assert '"ctranslate2"' in SPEC and '"sentencepiece"' in SPEC
    assert 'collect_dynamic_libs("ctranslate2")' in SPEC


def _passos():
    """Os `- name:` do job de build, na ordem."""
    return [linha.strip()[len("- name:"):].strip()
            for linha in WORKFLOW.splitlines() if linha.strip().startswith("- name:")]


def _indice(trecho):
    for i, nome in enumerate(_passos()):
        if trecho.lower() in nome.lower():
            return i
    pytest.fail(f"passo com '{trecho}' nao existe no release.yml: {_passos()}")


def test_o_release_prepara_o_modelo_antes_dos_testes_e_do_pyinstaller():
    preparar = _indice("tradutor")
    assert preparar < _indice("Lint e testes")
    assert preparar < _indice("PyInstaller")
    assert "tools/preparar_tradutor.py" in WORKFLOW
    assert "preparar_tradutor.py --verificar" in WORKFLOW


def test_o_release_guarda_o_modelo_em_cache_pela_revisao():
    """Converter custa minutos e ~200 MB de torch; a revisão é fixa no script,
    então o cache pela chave do script só invalida quando ela muda."""
    assert "actions/cache" in WORKFLOW
    assert "hashFiles('tools/preparar_tradutor.py')" in WORKFLOW


def test_torch_e_transformers_nunca_entram_no_pacote():
    """So a CONVERSAO do modelo os usa. O `ctranslate2.converters` tenta
    importa-los (dentro de try/except), e a analise do PyInstaller levaria
    ~800 MB de torch para o instalador se eles estivessem no ambiente."""
    assert '"torch"' in SPEC and '"transformers"' in SPEC
    trecho = SPEC[SPEC.index("excludes="):SPEC.index("noarchive")]
    assert "torch" in trecho and "transformers" in trecho


def test_a_conversao_roda_num_ambiente_separado_do_build():
    """O mesmo motivo, na outra ponta: o torch nem chega ao ambiente do
    PyInstaller."""
    inicio = WORKFLOW.index("Preparar o tradutor local")
    passo = WORKFLOW[inicio:WORKFLOW.index("- name:", inicio)]
    assert "venv" in passo

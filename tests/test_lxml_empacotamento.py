r"""O lxml chega ao usuário? (2026-10-05, T1 do roteiro do Gestão PMIB v2)

Desde a T1, toda gravação de `_STATUS_PMIB` passa pelo editor cirúrgico
(`sigft/core/excel/cirurgico.py`), que precisa do lxml -- e o `StatusPMIB` só o
importa na hora de GRAVAR. Faltando no pacote, o app abre normalmente e quebra
no meio do trabalho, na primeira planilha que tentar marcar: o caso mais caro.

Três elos, como em `test_tradutor_empacotamento.py`:
1. `requirements.txt` instala o lxml (o `SIG-FT.bat` reinstala quando o arquivo
   muda);
2. o `SIG-FT.spec` o declara;
3. a `--conferir-pacote` o procura dentro do `.exe` antes de publicar.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _requisitos(nome):
    return [linha.split(";")[0].strip().lower()
            for linha in (RAIZ / nome).read_text(encoding="utf-8").splitlines()
            if linha.strip() and not linha.strip().startswith("#")]


def test_requirements_de_producao_instala_o_lxml():
    assert "lxml" in _requisitos("requirements.txt")


def test_requirements_dev_tambem_porque_o_ci_so_instala_ele():
    # Sem ele no CI os testes da gravação sem perda seriam PULADOS.
    assert "lxml" in _requisitos("requirements-dev.txt")


def test_o_spec_declara_o_lxml():
    spec = (RAIZ / "SIG-FT.spec").read_text(encoding="utf-8")
    assert '"lxml.etree"' in spec


def test_a_conferencia_do_pacote_procura_o_editor_e_o_lxml():
    from sigft.app import conferencia

    assert "lxml.etree" in conferencia.MODULOS_ESSENCIAIS
    assert "sigft.core.excel.cirurgico" in conferencia.MODULOS_ESSENCIAIS

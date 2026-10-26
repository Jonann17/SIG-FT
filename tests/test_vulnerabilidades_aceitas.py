"""O `empacotamento/vulnerabilidades-aceitas.txt`: o que o job "auditoria" do CI
deixa passar. Cada linha diz o aviso, o pacote e POR QUE não se aplica
(2026-10-26); sem o motivo, aceitar vira esquecer."""
from __future__ import annotations

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ACEITAS = RAIZ / "empacotamento" / "vulnerabilidades-aceitas.txt"
VERSOES = RAIZ / "empacotamento" / "versoes-do-release.txt"
LINHA = re.compile(r"^(?P<id>[A-Z]+-[\w-]+)\s+(?P<pacote>[\w.-]+)\s+--\s+(?P<motivo>.{40,})$")


def _linhas(caminho):
    return [l.strip() for l in caminho.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def test_cada_aviso_aceito_tem_pacote_e_motivo():
    linhas = _linhas(ACEITAS)
    assert linhas, "arquivo vazio: tire o --ignore-vuln do CI ou ponha a linha"
    for linha in linhas:
        assert LINHA.match(linha), f"linha sem o formato '<ID> <pacote> -- <motivo>': {linha!r}"


def test_aviso_aceito_e_de_pacote_que_vai_no_release():
    fixados = {l.split("==")[0].lower() for l in _linhas(VERSOES) if "==" in l}
    for linha in _linhas(ACEITAS):
        pacote = LINHA.match(linha)["pacote"].lower()
        assert pacote in fixados, f"{pacote} nao esta mais no Release: a linha sobra"


def test_o_ci_audita_as_versoes_do_release():
    ci = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pip-audit -r" in ci and "vulnerabilidades-aceitas.txt" in ci


def test_pypdf2_saiu_do_release():
    # PyPDF2 abandonado, com laco infinito em PDF montado (GHSA-4vvm-4w3v-6mr8).
    fixados = {l.split("==")[0].lower() for l in _linhas(VERSOES) if "==" in l}
    assert "pypdf2" not in fixados and "pypdf" in fixados

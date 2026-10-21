"""O resumo do fim do lote, sem Qt (2026-10-21, etapa 1b)."""
import os
from datetime import datetime

from sigft.app import niveis_log as n
from sigft.app import resumo_lote as r

PARES = [
    ("❌ 4500063671.0002: TimeoutError: sem resposta (1,2s)", n.ERRO),
    ("   [Aviso] 4500063671.0001: nao consegui ler o PDM atual.", n.AVISO),
    ("tudo certo", n.INFO),
    ("[ERRO] A lista de fichas do portal não respondeu.", n.ERRO),
    ("   [Erro] Ficha 4500063671.0002 não encontrada.", n.ERRO),
    ("   [Aviso] 4500063671.0001: nao consegui ler o PDM atual.", n.AVISO),   # repetida
]


def test_agrupa_por_codigo_na_ordem_e_sem_codigo_no_fim():
    grupos = r.agrupar(PARES)
    assert [g.rotulo for g in grupos] == ["4500063671.0002", "4500063671.0001", r.SEM_CODIGO]
    assert [t for t, _ in grupos[0].linhas] == [
        "❌ 4500063671.0002: TimeoutError: sem resposta (1,2s)",
        "[Erro] Ficha 4500063671.0002 não encontrada.",
    ]
    assert len(grupos[1].linhas) == 1            # a repetida entra uma vez
    assert grupos[2].linhas == (("[ERRO] A lista de fichas do portal não respondeu.", n.ERRO),)


def test_sem_problema_nao_ha_grupo():
    assert r.agrupar([("tudo certo", n.INFO)]) == []


def test_contagem_e_frases():
    assert r.contar(r.agrupar(PARES)) == (3, 1)
    assert r.frase_da_contagem(1, 0) == "1 erro"
    assert r.frase_da_contagem(0, 2) == "2 avisos"
    assert r.frase_da_contagem(2, 1) == "2 erros e 1 aviso"
    assert r.frase_do_fim("Upload duplicadas", 0, 0) == "Upload duplicadas terminou sem erro nem aviso."
    assert r.frase_do_fim("Upload duplicadas", 2, 1) == "Upload duplicadas terminou com 2 erros e 1 aviso."
    assert r.frase_do_fim("Upload duplicadas", 1, 0, falhou=True) == \
        "Upload duplicadas parou com erro. Veja o console."


def test_texto_para_copiar():
    texto = r.texto_para_copiar("Upload duplicadas", r.agrupar(PARES))
    linhas = texto.splitlines()
    assert linhas[0] == "Upload duplicadas: 3 erros e 1 aviso"
    assert linhas[2] == "4500063671.0002"
    assert linhas[3] == "  ❌ 4500063671.0002: TimeoutError: sem resposta (1,2s)"
    assert linhas[-1] == "  [ERRO] A lista de fichas do portal não respondeu."
    assert texto.endswith("\n")


def test_gravar_log_leva_tudo(tmp_path):
    caminho = r.gravar_log("Upload duplicadas", PARES, tmp_path / "resumos",
                           datetime(2026, 10, 21, 14, 5, 9))
    assert caminho.name == "Upload_duplicadas_2026-10-21_14-05-09.log"
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "Upload duplicadas: 21/10/2026 14:05:09"
    assert "> tudo certo" in linhas          # o log leva TUDO, não só os problemas


def test_desligado_pelo_ambiente(monkeypatch):
    monkeypatch.setenv(r.ENV_DESLIGAR, "1")
    assert not r.ligado()
    monkeypatch.delenv(r.ENV_DESLIGAR)
    assert r.ligado()


def test_os_testes_rodam_com_o_resumo_desligado():
    assert os.environ.get(r.ENV_DESLIGAR) == "1"   # tests/conftest.py

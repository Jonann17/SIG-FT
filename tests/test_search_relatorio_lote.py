r"""
Testes do Checkpoint 4.4 (2ª parte) — `sigft/services/search.py`,
`PMIBSearcher.executar_busca` migrado para `RelatorioLote` (padrão único de
log de lote).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.4.

`_encontrar_e_formatar_dataframe` (que usa pandas de verdade) é
monkeypatchada por arquivo — este ambiente de teste tem `pandas` como
`MagicMock` (tests/conftest.py), então a leitura de Excel em si não é
exercitada aqui (já é testada em outro lugar/em produção). O que se prova é
a FIAÇÃO do `RelatorioLote` dentro do laço real de `executar_busca`: início
com total/contexto, uma linha por arquivo processado, resumo final com
falhas listadas, e uma falha isolada não interrompe a varredura dos outros
arquivos.

Para a busca 'direcionada' produzir um "sucesso com match" de verdade (sem
reimplementar pandas), um `_FakeDataFrame`/`_FakeColuna` mínimo replica só a
cadeia de métodos que `executar_busca` usa (`.columns`, `.fillna().astype().
str.upper().str.contains()`, indexação por máscara, `.empty`, `.head().
tolist()`) — a lógica de busca em si (não tocada por este checkpoint)
continua sendo a de produção, só os dados são fakes.
"""
from __future__ import annotations

from sigft.services.search import PMIBSearcher


# =============================================================================
# Fake mínimo de DataFrame/Series -- só o suficiente para a busca
# 'direcionada' real (não reimplementada aqui) rodar de ponta a ponta.
# =============================================================================

class _FakeColuna(list):
    def fillna(self, valor):
        return _FakeColuna(x if x is not None else valor for x in self)

    def astype(self, tipo):
        return _FakeColuna(tipo(x) for x in self)

    @property
    def str(self):
        return self

    def upper(self):
        return _FakeColuna(x.upper() for x in self)

    def contains(self, termo, regex=False):
        return _FakeColuna(termo in x for x in self)

    def head(self, n):
        return _FakeColuna(self[:n])

    def tolist(self):
        return list(self)


class _FakeDataFrame:
    def __init__(self, colunas, linhas):
        self.columns = list(colunas)
        self._linhas = linhas  # lista de dicts coluna -> valor

    def __getitem__(self, chave):
        if isinstance(chave, _FakeColuna):
            filtradas = [linha for linha, incluir in zip(self._linhas, chave) if incluir]
            return _FakeDataFrame(self.columns, filtradas)
        return _FakeColuna(linha.get(chave) for linha in self._linhas)

    @property
    def empty(self):
        return not self._linhas


class _DataFrameComColunasQuebradas:
    """Simula uma falha inesperada durante a leitura das colunas (ex.:
    arquivo corrompido depois do parse inicial) -- usada para exercitar o
    ramo de FALHA sem tocar pandas real."""

    @property
    def columns(self):
        raise RuntimeError("colunas corrompidas (simulado)")


def _searcher_com_arquivos(tmp_path, comportamentos):
    """Cria 1 arquivo `*_STATUS_PMIB*.xlsx` real por entrada de
    `comportamentos` (só o NOME importa -- `os.walk` precisa achá-los de
    verdade) e monkeypatcha `_encontrar_e_formatar_dataframe` para devolver,
    por nome de arquivo, o resultado configurado."""
    searcher = PMIBSearcher.__new__(PMIBSearcher)
    searcher.sheet_names = ["Lista de Materiais"]

    for nome in comportamentos:
        (tmp_path / nome).write_bytes(b"conteudo-falso")

    def _fake_encontrar(caminho):
        import os
        nome = os.path.basename(caminho)
        comportamento = comportamentos[nome]
        if comportamento == "sem_cabecalho":
            return None, "Cabeçalho com a coluna 'DESCRIÇÃO' não encontrado."
        # Qualquer outro valor (`_FakeDataFrame`/`_DataFrameComColunasQuebradas`)
        # É o "DataFrame" devolvido tal qual -- a leitura real (pandas) não é
        # o que este checkpoint testa; só a fiação do RelatorioLote em torno
        # dela.
        return comportamento, "OK"

    searcher._encontrar_e_formatar_dataframe = _fake_encontrar
    return searcher


# =============================================================================
# Exigência 1 — início do lote com total + contexto (pasta/tipo de busca).
# =============================================================================

def test_inicio_do_lote_mostra_total_e_contexto(tmp_path):
    searcher = _searcher_com_arquivos(
        tmp_path, {"A_STATUS_PMIB.xlsx": _FakeDataFrame(["DESCRIÇÃO"], [])}
    )
    logs = []

    searcher.executar_busca(
        str(tmp_path), "direcionada", "MOTOR", coluna_especifica=None, callback_log=logs.append
    )
    texto = "\n".join(logs)

    assert "1 item(ns)" in texto
    assert f"pasta_raiz: {tmp_path}" in texto
    assert "tipo_busca: direcionada" in texto


def test_pasta_sem_nenhum_arquivo_status_pmib_nao_constroi_lote(tmp_path):
    # Early-return preservado tal qual -- nem chega a montar o RelatorioLote.
    searcher = PMIBSearcher.__new__(PMIBSearcher)
    logs = []

    resultado = searcher.executar_busca(str(tmp_path), "direcionada", "X", callback_log=logs.append)

    assert resultado == []
    assert "Nenhum arquivo _STATUS_PMIB encontrado" in "\n".join(logs)
    assert not any("Resumo" in m for m in logs)


# =============================================================================
# Exigência 2/3 — por item: identificador + aviso com causa e consequência.
# =============================================================================

def test_arquivo_sem_cabecalho_e_pulado_com_motivo(tmp_path):
    searcher = _searcher_com_arquivos(tmp_path, {"A_STATUS_PMIB.xlsx": "sem_cabecalho"})
    logs = []

    searcher.executar_busca(str(tmp_path), "direcionada", "X", callback_log=logs.append)
    texto = "\n".join(logs)

    assert "⏭️ A_STATUS_PMIB.xlsx" in texto
    assert "Cabeçalho com a coluna 'DESCRIÇÃO' não encontrado" in texto


def test_coluna_pedida_ausente_vira_aviso_com_causa_e_consequencia(tmp_path):
    df = _FakeDataFrame(["OUTRA COLUNA"], [{"OUTRA COLUNA": "x"}])
    searcher = _searcher_com_arquivos(tmp_path, {"A_STATUS_PMIB.xlsx": df})
    logs = []

    searcher.executar_busca(
        str(tmp_path), "direcionada", "MOTOR", coluna_especifica="DESCRIÇÃO", callback_log=logs.append
    )
    texto = "\n".join(logs)

    assert "⚠️" in texto
    assert "coluna 'DESCRIÇÃO' não existe neste arquivo" in texto
    assert "→" in texto  # causa -> consequência (exigência nº 3 do CP 4.4)
    # O arquivo ainda assim conta como processado com sucesso (só sem match).
    assert "✅ A_STATUS_PMIB.xlsx" in texto


def test_match_encontrado_aparece_no_resultado_e_no_log_do_item(tmp_path):
    df = _FakeDataFrame(
        ["CÓDIGO PMIB", "DESCRIÇÃO"],
        [{"CÓDIGO PMIB": "1", "DESCRIÇÃO": "MOTOR ELETRICO 220V"}],
    )
    searcher = _searcher_com_arquivos(tmp_path, {"A_STATUS_PMIB.xlsx": df})
    logs = []

    resultados = searcher.executar_busca(
        str(tmp_path), "direcionada", "MOTOR", coluna_especifica="DESCRIÇÃO", callback_log=logs.append
    )
    texto = "\n".join(logs)

    assert len(resultados) == 1
    assert resultados[0]["arquivo_nome"] == "A_STATUS_PMIB.xlsx"
    assert "✅ A_STATUS_PMIB.xlsx" in texto
    assert "match encontrado" in texto


# =============================================================================
# Exigência 4 — resumo final com falhas listadas; falha isolada não derruba
# o processamento dos demais arquivos.
# =============================================================================

def test_erro_inesperado_num_arquivo_vira_falha_e_nao_impede_os_outros(tmp_path):
    df_ok = _FakeDataFrame(
        ["CÓDIGO PMIB", "DESCRIÇÃO"], [{"CÓDIGO PMIB": "1", "DESCRIÇÃO": "VALVULA"}]
    )
    searcher = _searcher_com_arquivos(
        tmp_path,
        {
            "A_STATUS_PMIB.xlsx": df_ok,
            "B_STATUS_PMIB.xlsx": _DataFrameComColunasQuebradas(),
            "C_STATUS_PMIB.xlsx": "sem_cabecalho",
        },
    )
    logs = []

    resultados = searcher.executar_busca(
        str(tmp_path), "direcionada", "VALVULA", coluna_especifica="DESCRIÇÃO", callback_log=logs.append
    )
    texto = "\n".join(logs)

    # Os 3 arquivos foram tentados -- a falha do B não impediu A nem C.
    assert "✅ A_STATUS_PMIB.xlsx" in texto
    assert "❌ B_STATUS_PMIB.xlsx" in texto
    assert "⏭️ C_STATUS_PMIB.xlsx" in texto
    assert len(resultados) == 1  # o match de A não se perdeu

    assert "── Resumo:" in texto
    assert "1 sucesso(s)" in texto
    assert "1 falha(s)" in texto
    assert "1 pulado(s)" in texto
    assert "Falhas:" in texto
    trecho_falhas = texto[texto.index("Falhas:"):]
    assert "B_STATUS_PMIB.xlsx" in trecho_falhas
    assert "RuntimeError: colunas corrompidas (simulado)" in trecho_falhas
    assert "Tempo total:" in texto

    # A mensagem final ORIGINAL (contagem de correspondências) continua.
    assert "Busca finalizada! 1 correspondência(s) encontrada(s)." in texto

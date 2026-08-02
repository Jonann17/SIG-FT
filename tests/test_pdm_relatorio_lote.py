r"""
Testes do Checkpoint 4.4 (2ª parte) — `sigft/services/pdm.py`, as 3 funções
de LOTE migradas para `RelatorioLote` (padrão único de log de lote):
`pdms_fromItaipu_lista_geral`, `aplicar_templates_fichas` e
`logica_excluir_duplicados`.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.4.

As 3 funções já recebiam `log_callback` (assinatura ANTIGA, um callable
posicional) -- migradas via `sigft.core.callbacks.from_legacy` (a assinatura
pública de nenhuma delas mudou). `processar_pastas_fichas`/
`mover_fichas_para_raiz` NÃO têm canal de log e ficaram de fora (ver
PENDENCIAS.md).

Os fakes de workbook/worksheet seguem o mesmo espírito de
`tests/test_pdm_io.py` (fiéis o bastante para a função real de produção
rodar de ponta a ponta, sem depender de openpyxl/pandas reais, ausentes
neste ambiente de teste — ver tests/conftest.py).
"""
from __future__ import annotations

import os
from io import BytesIO

import pytest


# =============================================================================
# Fakes de workbook/worksheet -- openpyxl é MagicMock neste ambiente
# (tests/conftest.py); `pdm.load_workbook` é monkeypatchado em cada teste.
# =============================================================================

class _FakeCell:
    def __init__(self, value=None):
        self.value = value
        self.has_style = False


class _FakeWS:
    """Réplica fiel o bastante de uma worksheet `TEMPLATE_PDM` para
    `pdms_fromItaipu_lista_geral` rodar de ponta a ponta: 6 linhas de
    cabeçalho + 1 linha de dado por código (coluna A = código, coluna D =
    descrição) -- os mesmos índices que a função real lê. Ao contrário do
    fake simplificado de `test_pdm_io.py` (que só mede CONTAGEM de leituras
    de disco, então pode ignorar `min_row`), este RESPEITA `min_row` -- é
    preciso para o fatiamento `todas[i-1]` não estourar `IndexError` e
    produzir um resultado de SUCESSO de verdade."""

    def __init__(self, codigos):
        linhas = [(_FakeCell(f"h{h}"),) for h in range(6)]
        for cod in codigos:
            linhas.append((_FakeCell(cod), _FakeCell(), _FakeCell(), _FakeCell(f"DESC-{cod}")))
        self._linhas = linhas
        self.max_row = len(linhas)

    def iter_rows(self, min_row=1, values_only=False):
        for linha in self._linhas[min_row - 1:]:
            yield linha

    def cell(self, row, column, value=None):
        linha = self._linhas[row - 1]
        return linha[column - 1] if column - 1 < len(linha) else _FakeCell()

    def delete_rows(self, inicio, fim):
        pass


class _FakeWB:
    """Workbook falso para `pdms_fromItaipu_lista_geral` — `falha_ao_salvar`
    é um conjunto de códigos cujo `save()` deve estourar (simula arquivo
    travado/erro de disco), pelo nome do código aparecer no caminho final."""

    def __init__(self, codigos, falha_ao_salvar=()):
        self.sheetnames = ["TEMPLATE_PDM"]
        self._ws = _FakeWS(codigos)
        self._falha_ao_salvar = set(falha_ao_salvar)

    def __getitem__(self, nome):
        return self._ws

    def remove(self, ws):
        pass

    def save(self, caminho):
        for codigo in self._falha_ao_salvar:
            if codigo in caminho:
                raise PermissionError(f"arquivo travado (simulado): {caminho}")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("")

    def close(self):
        pass


# =============================================================================
# pdms_fromItaipu_lista_geral
# =============================================================================

def test_lista_geral_inicio_por_item_e_resumo_com_falha_isolada(monkeypatch, tmp_path):
    from sigft.services import pdm

    codigos = ["PDM_1000_001", "PDM_1000_002", "PDM_1000_003"]
    monkeypatch.setattr(
        pdm, "load_workbook",
        lambda fonte, *a, **k: _FakeWB(codigos, falha_ao_salvar={"PDM_1000_002"}),
    )

    destino = tmp_path / "destino"
    destino.mkdir()
    origem = tmp_path / "lista.xlsx"
    origem.write_bytes(b"conteudo-falso")

    logs = []
    resumo = pdm.pdms_fromItaipu_lista_geral(str(origem), str(destino), log_callback=logs.append)
    texto = "\n".join(logs)

    # Exigência 1: início com total + contexto (arquivos envolvidos).
    assert "3 item(ns)" in texto
    assert str(origem) in texto
    assert str(destino) in texto

    # Exigência 2: cada código gera uma linha com o identificador.
    assert "PDM_1000_001" in texto
    assert "PDM_1000_002" in texto
    assert "PDM_1000_003" in texto

    # Exigência 4: resumo final com a falha LISTADA -- e ela não derrubou os
    # outros 2 códigos.
    assert "── Resumo:" in texto
    assert "2 sucesso(s)" in texto
    assert "1 falha(s)" in texto
    assert "Falhas:" in texto
    trecho_falhas = texto[texto.index("Falhas:"):]
    assert "PDM_1000_002" in trecho_falhas
    assert "PermissionError" in trecho_falhas

    # Retorno público (consumido por frontend.py) preservado no formato de
    # sempre, refletindo só os 2 sucessos.
    assert "Criados: 2" in resumo
    assert "Total Analisado: 3" in resumo


def test_lista_geral_sem_log_callback_nao_levanta_excecao(monkeypatch, tmp_path):
    # Contrato preservado: `log_callback` continua opcional.
    from sigft.services import pdm

    codigos = ["PDM_2000_001"]
    monkeypatch.setattr(pdm, "load_workbook", lambda fonte, *a, **k: _FakeWB(codigos))
    destino = tmp_path / "destino"
    destino.mkdir()
    origem = tmp_path / "lista.xlsx"
    origem.write_bytes(b"x")

    resumo = pdm.pdms_fromItaipu_lista_geral(str(origem), str(destino))

    assert "Criados: 1" in resumo


# =============================================================================
# aplicar_templates_fichas
# =============================================================================

class _FakeCelulaAlvo:
    def __init__(self, value=None):
        self.value = value


class _FakeWSFonte:
    """Worksheet do PDM de ORIGEM (`wb_pdm.active`): só `.max_row`/`.cell`
    (colunas 1/2 -- Descrição/Resposta)."""

    def __init__(self, linhas):
        self._linhas = linhas
        self.max_row = len(linhas)

    def cell(self, row, column, value=None):
        desc, resp = self._linhas[row - 1]
        return _FakeCelulaAlvo(desc if column == 1 else resp)


class _FakeWBFonte:
    def __init__(self):
        self.active = _FakeWSFonte([("Peso", "10kg"), ("Cor", "Azul")])

    def close(self):
        pass


class _DimensoesAlvo(dict):
    def __missing__(self, chave):
        valor = _FakeCelulaAlvo()
        self[chave] = valor
        return valor


class _FakeWSAlvo:
    def merge_cells(self, **kwargs):
        pass

    def cell(self, row, column, value=None):
        return _FakeCelulaAlvo(value)

    @property
    def row_dimensions(self):
        return _DimensoesAlvo()


class _FakeWBAlvo:
    """Workbook falso da FICHA ALVO (cópia do template) -- `falhar=True`
    simula erro ao salvar a ficha final (ex.: arquivo aberto no Excel)."""

    def __init__(self, falhar=False):
        self._ws = _FakeWSAlvo()
        self._falhar = falhar

    def __getitem__(self, nome):
        return self._ws

    def save(self, caminho):
        if self._falhar:
            raise RuntimeError("arquivo aberto no Excel (simulado)")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("")

    def close(self):
        pass


def _fake_load_workbook_templates(falhar_no_indice):
    """`load_workbook` é chamado 2x por PMIB: 1x com uma STRING (PDM fonte),
    1x com `BytesIO` (cópia do template). Só a chamada com `BytesIO` conta
    como "índice do PMIB atual" (na MESMA ordem de `lista_dados`, que é uma
    lista -- ordem determinística, ao contrário do `set` de
    `pdms_fromItaipu_lista_geral`)."""
    contador = {"indice": 0}

    def fake(fonte, *args, **kwargs):
        if isinstance(fonte, BytesIO):
            indice = contador["indice"]
            contador["indice"] += 1
            return _FakeWBAlvo(falhar=(indice in falhar_no_indice))
        return _FakeWBFonte()

    return fake


def test_aplicar_templates_inicio_por_item_e_resumo_com_falha_isolada(monkeypatch, tmp_path):
    from sigft.services import pdm

    pasta_pdms = tmp_path / "pdms_modificados"
    pasta_pdms.mkdir()
    for i in range(3):
        (pasta_pdms / f"PDM_202{i}_001 - Peça {i}.xlsx").write_bytes(b"x")
    saida = tmp_path / "fichas"
    saida.mkdir()
    template = tmp_path / "template.xlsx"
    template.write_bytes(b"template-falso")

    # PMIB do meio (índice 1) falha ao salvar -- os outros 2 continuam.
    monkeypatch.setattr(pdm, "load_workbook", _fake_load_workbook_templates(falhar_no_indice={1}))

    lista_dados = [
        (f"4500063671.000{i}", f"PDM.202{i}.001 - Peça {i}", str(saida)) for i in range(3)
    ]

    logs = []
    msg_res, log_retorno = pdm.aplicar_templates_fichas(
        lista_dados, str(pasta_pdms), str(template), log_callback=logs.append
    )
    texto = "\n".join(logs)

    # Exigência 1: início com total + contexto.
    assert "3 item(ns)" in texto
    assert str(pasta_pdms) in texto
    assert str(template) in texto

    # Exigência 2: cada PMIB gera uma linha com o identificador.
    assert "4500063671.0000" in texto
    assert "4500063671.0001" in texto
    assert "4500063671.0002" in texto

    # Exigência 4: resumo final com a falha LISTADA -- 2 sucessos, 1 falha.
    assert "── Resumo:" in texto
    assert "2 sucesso(s)" in texto
    assert "1 falha(s)" in texto
    assert "Falhas:" in texto
    trecho_falhas = texto[texto.index("Falhas:"):]
    assert "4500063671.0001" in trecho_falhas

    # Retorno público preservado: "Fichas geradas: N" conta só os sucessos;
    # `log_retorno` (lista) continua recebendo a MESMA string de sempre.
    assert msg_res == "Fichas geradas: 2"
    assert any("ERRO ao gerar ficha 4500063671.0001" in linha for linha in log_retorno)


def test_aplicar_templates_pdm_fonte_nao_encontrado_conta_como_falha(monkeypatch, tmp_path):
    from sigft.services import pdm

    pasta_pdms = tmp_path / "pdms_modificados"
    pasta_pdms.mkdir()  # vazia -- nenhum PDM fonte disponível
    saida = tmp_path / "fichas"
    saida.mkdir()
    template = tmp_path / "template.xlsx"
    template.write_bytes(b"x")

    monkeypatch.setattr(pdm, "load_workbook", _fake_load_workbook_templates(falhar_no_indice=set()))

    logs = []
    msg_res, log_retorno = pdm.aplicar_templates_fichas(
        [("4500063671.0009", "PDM.9999.001 - X", str(saida))],
        str(pasta_pdms), str(template), log_callback=logs.append,
    )
    texto = "\n".join(logs)

    assert "❌ 4500063671.0009" in texto
    assert "PDM fonte não encontrado" in texto
    assert "1 falha(s)" in texto
    assert msg_res == "Fichas geradas: 0"
    assert log_retorno == ["FALHA: PDM fonte não encontrado para 4500063671.0009 (PDM_9999_001)"]


# =============================================================================
# logica_excluir_duplicados
# =============================================================================

def test_excluir_duplicados_inicio_por_item_resumo_e_falha_isolada(monkeypatch, tmp_path):
    from sigft.services import pdm

    pasta = tmp_path / "pdms"
    pasta.mkdir()

    # Grupo COM duplicata (2 arquivos) -- o MAIOR é excluído com sucesso.
    grande = pasta / "PDM_3000_001 - A.xlsx"
    grande.write_bytes(b"x" * 200)
    pequeno = pasta / "PDM_3000_001 - B.xlsx"
    pequeno.write_bytes(b"x" * 10)

    # Grupo SEM duplicata -- nunca entra no laço, nunca é logado, nunca conta
    # para o total do lote.
    unico = pasta / "PDM_4000_001 - C.xlsx"
    unico.write_bytes(b"x")

    # 2º grupo COM duplicata, mas a exclusão FALHA (simulado).
    falha_grande = pasta / "PDM_5000_001 - D.xlsx"
    falha_grande.write_bytes(b"x" * 200)
    falha_pequeno = pasta / "PDM_5000_001 - E.xlsx"
    falha_pequeno.write_bytes(b"x" * 10)

    remove_original = pdm.os.remove

    def remove_falho(caminho):
        if "PDM_5000_001" in caminho:
            raise PermissionError("arquivo em uso (simulado)")
        return remove_original(caminho)

    monkeypatch.setattr(pdm.os, "remove", remove_falho)

    logs = []
    resumo = pdm.logica_excluir_duplicados(str(pasta), log_callback=logs.append)
    texto = "\n".join(logs)

    # Exigência 1: início com total (só os 2 grupos COM duplicata) + contexto.
    assert "2 item(ns)" in texto
    assert str(pasta) in texto

    # Exigência 2: cada grupo com duplicata gera uma linha com o PDM ID.
    assert "PDM_3000_001" in texto
    assert "PDM_5000_001" in texto
    assert "PDM_4000_001" not in texto  # grupo sem duplicata é silencioso, como sempre foi

    # Exigência 4: resumo final, com a falha LISTADA -- não derrubou o outro.
    assert "── Resumo:" in texto
    assert "1 sucesso(s)" in texto
    assert "1 falha(s)" in texto
    assert "Falhas:" in texto
    trecho_falhas = texto[texto.index("Falhas:"):]
    assert "PDM_5000_001" in trecho_falhas

    # Comportamento real preservado: o maior arquivo do grupo sem falha foi
    # de fato excluído; o do grupo com falha simulada continua no disco.
    assert not grande.exists()
    assert pequeno.exists()
    assert falha_grande.exists()
    assert falha_pequeno.exists()
    assert unico.exists()
    assert "Total excluídos: 1" in resumo


def test_excluir_duplicados_pasta_invalida_nao_constroi_lote(tmp_path):
    # Early-return preservado tal qual -- nem chega a montar o RelatorioLote.
    from sigft.services import pdm

    resultado = pdm.logica_excluir_duplicados("")

    assert resultado == "Pasta inválida."

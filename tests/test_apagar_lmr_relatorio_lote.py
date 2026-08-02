r"""
Testes do Checkpoint 4.4 (2ª parte) — `sigft/services/apagar_lmr.py`, o loop
de exclusão de `ApagarLMRAutomation.executar_limpeza` migrado para
`RelatorioLote` (padrão único de log de lote).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.4. `apagar_lmr` não
tem um loop de VÁRIAS FICHAS — uma chamada de `executar_limpeza` já é sobre
UM PMIB só; o "lote" aqui é o conjunto de aplicações LMR apagadas dentro
dessa ficha (cada exclusão bem-sucedida é um "item").

Ambiente sem Selenium real (`tests/conftest.py` stuba `selenium.*` como
`MagicMock`): `self.wait`/`self.driver` são fakes duck-typed (nunca
`MagicMock`), e `TimeoutException`/`StaleElementReferenceException` (que no
módulo real são atributos `MagicMock`, não classes de exceção de verdade —
não servem para `raise`/`except`) são monkeypatchadas para exceções Python
REAIS — MESMA técnica/racional já usada em `tests/test_portal.py`
(`_excecoes_selenium_de_verdade`).
"""
from __future__ import annotations

import pytest

from sigft.core.callbacks import UICallbacks
from sigft.services import apagar_lmr


# ===========================================================================
# Exceções fake: ver docstring do módulo / tests/test_portal.py.
# ===========================================================================
class TimeoutExceptionFake(Exception):
    pass


class StaleElementReferenceExceptionFake(Exception):
    pass


@pytest.fixture(autouse=True)
def _excecoes_selenium_de_verdade(monkeypatch):
    monkeypatch.setattr(apagar_lmr, "TimeoutException", TimeoutExceptionFake)
    monkeypatch.setattr(apagar_lmr, "StaleElementReferenceException", StaleElementReferenceExceptionFake)


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    # `PAUSA_ABERTURA_ABA`/`PAUSA_POS_EXCLUSAO` continuam sendo respeitados
    # pelo código real (não removidos) -- só o `time.sleep` de verdade é que
    # vira no-op, para o teste não ficar lento.
    monkeypatch.setattr(apagar_lmr.time, "sleep", lambda *_a, **_kw: None)


# ===========================================================================
# Fakes duck-typed de wait/driver (mesmo espírito de tests/test_portal.py).
# ===========================================================================
class _FakeElemento:
    def __init__(self):
        self.cliques = 0

    def click(self):
        self.cliques += 1


class _FakeWait:
    """`until(condicao)` consome uma fila pré-programada: cada item é um
    elemento (devolvido) ou uma instância de exceção (levantada). A
    `condicao` real (EC.element_to_be_clickable, um MagicMock neste
    ambiente) é ignorada -- o código sob teste só usa o RESULTADO."""

    def __init__(self, respostas):
        self._fila = list(respostas)

    def until(self, condicao):
        proxima = self._fila.pop(0)
        if isinstance(proxima, BaseException):
            raise proxima
        return proxima


class _FakeDriver:
    def __init__(self):
        self.execute_script_chamadas = 0
        self.urls_visitadas = []

    def execute_script(self, script, elemento):
        self.execute_script_chamadas += 1

    def get(self, url):
        self.urls_visitadas.append(url)


def _automacao(respostas_wait):
    auto = apagar_lmr.ApagarLMRAutomation()
    auto.wait = _FakeWait(respostas_wait)
    auto.driver = _FakeDriver()
    return auto


def _capturar_logs():
    logs = []
    return UICallbacks(log=lambda msg, nivel="info", contexto=None: logs.append(str(msg))), logs


# ===========================================================================
# Exigência 1 — início do lote com contexto (PMIB).
# ===========================================================================

def test_inicio_do_lote_mostra_o_pmib_no_contexto(monkeypatch):
    callbacks, logs = _capturar_logs()
    auto = _automacao(
        [
            _FakeElemento(),  # botão da aba LMR
            TimeoutExceptionFake(),  # 1ª lixeira: nenhuma -- fim imediato
        ]
    )
    monkeypatch.setattr(auto, "_pesquisar_e_abrir", lambda pmib: (True, "Ficha aberta."))

    auto.executar_limpeza("4500063671.1234", callbacks=callbacks)
    texto = "\n".join(logs)

    assert "Apagando aplicações LMR" in texto
    assert "pmib: 4500063671.1234" in texto


# ===========================================================================
# Exigência 2 — por item: identificador aparece na linha.
# ===========================================================================

def test_cada_aplicacao_apagada_gera_uma_linha_com_identificador(monkeypatch):
    callbacks, logs = _capturar_logs()
    auto = _automacao(
        [
            _FakeElemento(),  # botão da aba LMR
            _FakeElemento(), _FakeElemento(),  # item 1: lixeira + confirmar
            _FakeElemento(), _FakeElemento(),  # item 2: lixeira + confirmar
            TimeoutExceptionFake(),  # fim -- nenhuma lixeira restante
        ]
    )
    monkeypatch.setattr(auto, "_pesquisar_e_abrir", lambda pmib: (True, "Ficha aberta."))

    auto.executar_limpeza("X", callbacks=callbacks)
    texto = "\n".join(logs)

    assert "✅ Aplicação 1" in texto
    assert "✅ Aplicação 2" in texto
    assert "Todas as aplicações visíveis foram apagadas" in texto


# ===========================================================================
# Exigência 4 — resumo final, com falha listada; sucesso anterior preservado.
# ===========================================================================

def test_resumo_final_mostra_contagens_e_erro_inesperado_para_o_loop(monkeypatch):
    callbacks, logs = _capturar_logs()
    auto = _automacao(
        [
            _FakeElemento(),  # botão da aba LMR
            _FakeElemento(), _FakeElemento(),  # item 1: sucesso
            _FakeElemento(),  # item 2: lixeira ok...
            RuntimeError("elemento não respondeu (simulado)"),  # ...confirmar falha
        ]
    )
    monkeypatch.setattr(auto, "_pesquisar_e_abrir", lambda pmib: (True, "Ficha aberta."))

    auto.executar_limpeza("4500063671.9999", callbacks=callbacks)
    texto = "\n".join(logs)

    # O sucesso do item 1 continua registrado -- o erro do item 2 não o apaga.
    assert "✅ Aplicação 1" in texto
    assert "❌ Aplicação 2" in texto
    assert "RuntimeError: elemento não respondeu (simulado)" in texto

    assert "── Resumo:" in texto
    assert "1 sucesso(s)" in texto
    assert "1 falha(s)" in texto
    assert "Falhas:" in texto
    trecho_falhas = texto[texto.index("Falhas:"):]
    assert "Aplicação 2" in trecho_falhas
    assert "Tempo total:" in texto

    # Comportamento original preservado: erro inesperado PARA o loop (não
    # tenta mais nenhuma aplicação depois dele) e o robô volta pra lista.
    assert auto.driver.urls_visitadas == [auto.url_inicial]


def test_stale_element_apenas_tenta_de_novo_sem_contar_como_item(monkeypatch):
    # StaleElementReferenceException é recuperável: o item nem chega a ser
    # contado -- o loop só repete a MESMA tentativa.
    callbacks, logs = _capturar_logs()
    auto = _automacao(
        [
            _FakeElemento(),  # botão da aba LMR
            StaleElementReferenceExceptionFake(),  # 1ª tentativa: tabela mudou
            _FakeElemento(), _FakeElemento(),  # 2ª tentativa: sucesso
            TimeoutExceptionFake(),  # fim
        ]
    )
    monkeypatch.setattr(auto, "_pesquisar_e_abrir", lambda pmib: (True, "Ficha aberta."))

    auto.executar_limpeza("X", callbacks=callbacks)
    texto = "\n".join(logs)

    assert "✅ Aplicação 1" in texto
    assert "1 sucesso(s)" in texto
    assert "0 falha(s)" in texto

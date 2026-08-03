r"""
Testes do Checkpoint 4.4 (2ª parte) — `sigft/services/apagar_lmr.py`, o loop
de exclusão de `ApagarLMRAutomation.executar_limpeza` migrado para
`RelatorioLote` (padrão único de log de lote).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.4. `apagar_lmr` não
tem um loop de VÁRIAS FICHAS — uma chamada de `executar_limpeza` já é sobre
UM PMIB só; o "lote" aqui é o conjunto de aplicações LMR apagadas dentro
dessa ficha (cada exclusão bem-sucedida é um "item").

CP 5.1 (Fase 5): `apagar_lmr` virou o PILOTO da migração para Playwright.
Duas consequências aqui, ambas simplificações:

  - `self.driver`/`self.wait` deram lugar a `self.engine` (um `RPAEngine`
    escolhido por `factory.criar_engine`), então o fake agora é de ENGINE, e
    a fila de respostas é consumida por `wait_clickable` -- que é a espera
    que o laço usa como SINAL DE FIM do lote.
  - as exceções que o laço discrimina passaram a ser as NEUTRAS de
    `core/rpa/engine.py` (`TempoEsgotado`/`ElementoObsoleto`), que são
    exceções Python de verdade. O monkeypatch que apontava os nomes do
    Selenium (atributos `MagicMock` neste ambiente, inúteis para
    `raise`/`except`) para fakes deixou de ser necessário.

Estes testes são, junto com os de `tests/test_portal.py`, a rede que segura o
laço de exclusão durante a troca de motor: eles descrevem o comportamento
observável (o que é log de sucesso, o que é falha, o que é fim normal) sem
depender de qual motor está por baixo.
"""
from __future__ import annotations

import pytest

from sigft.core.callbacks import UICallbacks
from sigft.core.rpa.engine import ElementoObsoleto, TempoEsgotado
from sigft.services import apagar_lmr


# ===========================================================================
# Exceções neutras -- ver docstring do módulo.
# ===========================================================================
TimeoutExceptionFake = TempoEsgotado
StaleElementReferenceExceptionFake = ElementoObsoleto


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    # `PAUSA_ABERTURA_ABA`/`PAUSA_POS_EXCLUSAO` continuam sendo respeitados
    # pelo código real (não removidos) -- só o `time.sleep` de verdade é que
    # vira no-op, para o teste não ficar lento.
    monkeypatch.setattr(apagar_lmr.time, "sleep", lambda *_a, **_kw: None)


# ===========================================================================
# Fake de engine (duck-typed, nunca MagicMock).
# ===========================================================================
class _FakeEngine:
    """Consome uma fila pré-programada em `wait_clickable`: cada item é
    `None` (a espera passa) ou uma instância de exceção (levantada).

    É `wait_clickable` que carrega a fila porque é ele que decide o fluxo do
    laço de exclusão -- `TempoEsgotado` ali significa "não há mais lixeiras,
    o lote acabou". `scroll_to`/`click_raw` só registram, como no motor real,
    onde a ação em si não tem resultado a inspecionar.
    """

    def __init__(self, respostas):
        self._fila = list(respostas)
        self.esperas = []
        self.cliques = []
        self.urls_visitadas = []

    def wait_clickable(self, seletor):
        self.esperas.append(seletor)
        proxima = self._fila.pop(0)
        if isinstance(proxima, BaseException):
            raise proxima

    def scroll_to(self, seletor):
        pass

    def click_raw(self, seletor):
        self.cliques.append(seletor)

    def goto(self, url):
        self.urls_visitadas.append(url)

    def fechar(self):
        pass


def _automacao(respostas_wait):
    auto = apagar_lmr.ApagarLMRAutomation()
    # `None` = a espera passa; a fila antiga usava um elemento fake para dizer
    # a mesma coisa, então qualquer não-exceção continua valendo como sucesso.
    auto.engine = _FakeEngine(
        [r if isinstance(r, BaseException) else None for r in respostas_wait]
    )
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
            None,  # botão da aba LMR
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
            None,  # botão da aba LMR
            None, None,  # item 1: lixeira + confirmar
            None, None,  # item 2: lixeira + confirmar
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
            None,  # botão da aba LMR
            None, None,  # item 1: sucesso
            None,  # item 2: lixeira ok...
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
    assert auto.engine.urls_visitadas == [auto.url_inicial]


def test_stale_element_apenas_tenta_de_novo_sem_contar_como_item(monkeypatch):
    # StaleElementReferenceException é recuperável: o item nem chega a ser
    # contado -- o loop só repete a MESMA tentativa.
    callbacks, logs = _capturar_logs()
    auto = _automacao(
        [
            None,  # botão da aba LMR
            StaleElementReferenceExceptionFake(),  # 1ª tentativa: tabela mudou
            None, None,  # 2ª tentativa: sucesso
            TimeoutExceptionFake(),  # fim
        ]
    )
    monkeypatch.setattr(auto, "_pesquisar_e_abrir", lambda pmib: (True, "Ficha aberta."))

    auto.executar_limpeza("X", callbacks=callbacks)
    texto = "\n".join(logs)

    assert "✅ Aplicação 1" in texto
    assert "1 sucesso(s)" in texto
    assert "0 falha(s)" in texto

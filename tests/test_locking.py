r"""
Testes do Checkpoint 1.3 — `sigft/core/excel/locking.py` (`save_with_retry`).

`save_with_retry` é testado com um `wb` FALSO (duck-typed, sem depender do
pacote openpyxl instalado) que levanta `PermissionError` um número
configurável de vezes antes de "salvar" com sucesso — e com `sleep_fn`
injetado como no-op para não deixar os testes lentos nem dependentes de
tempo real. Cobre as 4 variantes de UX do diagnóstico (ver docstring de
`locking.py`): interativo (via `on_locked` custom), auto-retry com sleep
fixo sem limite, log+sai (via `max_attempts=1`), e a política DEFAULT usada
pelo novo consumidor (`upload_tech_specs`, sem UX preexistente).
"""
import pytest

from sigft.core.excel.locking import DEFAULT_SLEEP_SECONDS, save_with_retry


class _FakeWorkbook:
    """`wb` duck-typed: só precisa de `.save(path)`. Levanta
    `PermissionError` nas primeiras `falhas_antes_do_sucesso` chamadas;
    na chamada seguinte "salva" com sucesso (registra o `path` recebido).
    Se `falhas_antes_do_sucesso` for `None`, SEMPRE falha (para testar
    esgotamento de `max_attempts`/abort via `on_locked`)."""

    def __init__(self, falhas_antes_do_sucesso=0, excecao=PermissionError):
        self.falhas_antes_do_sucesso = falhas_antes_do_sucesso
        self.excecao = excecao
        self.chamadas = 0
        self.paths_salvos = []

    def save(self, path):
        self.chamadas += 1
        if self.falhas_antes_do_sucesso is None or self.chamadas <= self.falhas_antes_do_sucesso:
            raise self.excecao(f"arquivo aberto (chamada {self.chamadas})")
        self.paths_salvos.append(path)


class _SleepSpy:
    """`sleep_fn` no-op que grava os segundos de cada chamada (sem dormir
    de verdade)."""

    def __init__(self):
        self.chamadas = []

    def __call__(self, segundos):
        self.chamadas.append(segundos)


# ===========================================================================
# Caso feliz: sucesso de primeira, sem PermissionError nenhuma.
# ===========================================================================

def test_sucesso_de_primeira_nao_chama_on_locked_nem_sleep():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=0)
    sleep_spy = _SleepSpy()
    chamado = []

    resultado = save_with_retry(
        wb, "status.xlsx", on_locked=lambda a, e: chamado.append((a, e)) or True, sleep_fn=sleep_spy
    )

    assert resultado is True
    assert wb.chamadas == 1
    assert wb.paths_salvos == ["status.xlsx"]
    assert chamado == []
    assert sleep_spy.chamadas == []


# ===========================================================================
# Variante 1/2 do diagnóstico: INTERATIVO (on_locked customizado).
# ===========================================================================

def test_on_locked_true_retenta_sem_dormir():
    # Ex.: upload_conditions.atualizar_status_excel / pmib_manager, quando o
    # usuário responde "sim" no popup -- o `while True` original NÃO dorme
    # entre a resposta do usuário e a nova tentativa.
    wb = _FakeWorkbook(falhas_antes_do_sucesso=2)
    sleep_spy = _SleepSpy()
    tentativas_vistas = []

    def on_locked(attempt, exc):
        tentativas_vistas.append(attempt)
        assert isinstance(exc, PermissionError)
        return True

    resultado = save_with_retry(wb, "s.xlsx", on_locked=on_locked, sleep_fn=sleep_spy)

    assert resultado is True
    assert wb.chamadas == 3  # 2 falhas + 1 sucesso
    assert tentativas_vistas == [1, 2]  # numeração 1-based da tentativa que FALHOU
    assert sleep_spy.chamadas == []  # on_locked=True nunca aciona o sleep_fn


def test_on_locked_false_aborta_relevantando_permission_error():
    # Ex.: usuário responde "não" -- callback_ask retorna False/None.
    wb = _FakeWorkbook(falhas_antes_do_sucesso=None)  # sempre falha
    chamadas_on_locked = []

    def on_locked(attempt, exc):
        chamadas_on_locked.append(attempt)
        return attempt < 2  # retenta 1x, desiste na 2ª falha

    with pytest.raises(PermissionError):
        save_with_retry(wb, "s.xlsx", on_locked=on_locked, sleep_fn=lambda s: None)

    assert chamadas_on_locked == [1, 2]
    assert wb.chamadas == 2  # nenhuma 3ª tentativa depois do abort


def test_on_locked_none_retornado_usa_sleep_e_logger_default_mas_ainda_retenta():
    # on_locked customizado que devolve None numa tentativa específica:
    # delega a pausa/log daquela tentativa para a política default, mas
    # continua no comando (usado por quem quer logar por conta própria E
    # ainda assim aproveitar o sleep_fn/logger built-in em certos casos).
    wb = _FakeWorkbook(falhas_antes_do_sucesso=1)
    sleep_spy = _SleepSpy()
    mensagens = []

    resultado = save_with_retry(
        wb, "s.xlsx", on_locked=lambda a, e: None, sleep_fn=sleep_spy, logger=mensagens.append
    )

    assert resultado is True
    assert sleep_spy.chamadas == [DEFAULT_SLEEP_SECONDS]
    assert len(mensagens) == 1
    assert "tentativa 1" in mensagens[0]


# ===========================================================================
# Variante 3 do diagnóstico: AUTO-RETRY com sleep fixo, sem limite.
# ===========================================================================

def test_sem_on_locked_usa_politica_default_sleep_e_retry_ate_max_attempts_none():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=4)
    sleep_spy = _SleepSpy()

    resultado = save_with_retry(wb, "s.xlsx", sleep_seconds=5, sleep_fn=sleep_spy)

    assert resultado is True
    assert wb.chamadas == 5
    assert sleep_spy.chamadas == [5, 5, 5, 5]  # 1 sleep por falha, nenhum depois do sucesso


def test_logger_e_chamado_a_cada_tentativa_da_politica_default():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=2)
    mensagens = []

    save_with_retry(wb, "s.xlsx", sleep_fn=lambda s: None, logger=mensagens.append, sleep_seconds=5)

    assert len(mensagens) == 2
    assert "tentativa 1" in mensagens[0]
    assert "tentativa 2" in mensagens[1]
    assert "5s" in mensagens[0]


def test_sem_logger_politica_default_nao_quebra_so_nao_loga():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=1)
    resultado = save_with_retry(wb, "s.xlsx", sleep_fn=lambda s: None)
    assert resultado is True


# ===========================================================================
# Variante 4 do diagnóstico: LOG + SAI (max_attempts=1, sem on_locked).
# ===========================================================================

def test_max_attempts_1_aborta_na_primeira_falha_sem_consultar_on_locked():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=None)
    chamado = []

    with pytest.raises(PermissionError):
        save_with_retry(
            wb,
            "s.xlsx",
            max_attempts=1,
            on_locked=lambda a, e: chamado.append(a) or True,
            sleep_fn=lambda s: None,
        )

    assert wb.chamadas == 1
    assert chamado == []  # on_locked nunca chega a ser consultado


def test_max_attempts_1_com_sucesso_de_primeira_nao_levanta():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=0)
    assert save_with_retry(wb, "s.xlsx", max_attempts=1) is True


# ===========================================================================
# max_attempts como teto de segurança MESMO com on_locked sempre True.
# ===========================================================================

def test_max_attempts_prevalece_sobre_on_locked_sempre_true():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=None)  # nunca teria sucesso
    contagem = {"chamadas": 0}

    def on_locked_sempre_true(attempt, exc):
        contagem["chamadas"] += 1
        return True

    with pytest.raises(PermissionError):
        save_with_retry(
            wb, "s.xlsx", on_locked=on_locked_sempre_true, max_attempts=3, sleep_fn=lambda s: None
        )

    assert wb.chamadas == 3
    # on_locked só é consultado nas tentativas 1 e 2: a 3ª já esgota
    # max_attempts ANTES de perguntar (teto de segurança tem prioridade).
    assert contagem["chamadas"] == 2


# ===========================================================================
# `attempt`/`exc` recebidos por `on_locked` e `path` repassado ao `wb.save`.
# ===========================================================================

def test_attempt_e_exc_repassados_corretamente_a_on_locked():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=3)
    vistos = []

    save_with_retry(
        wb, "s.xlsx", on_locked=lambda a, e: vistos.append((a, str(e))) or True, sleep_fn=lambda s: None
    )

    assert [a for a, _ in vistos] == [1, 2, 3]
    assert all("chamada" in msg for _, msg in vistos)


def test_path_e_sempre_o_mesmo_em_todas_as_tentativas():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=2)
    save_with_retry(wb, "caminho/especifico.xlsx", sleep_fn=lambda s: None)
    assert wb.paths_salvos == ["caminho/especifico.xlsx"]


# ===========================================================================
# Exceção que NÃO é PermissionError propaga imediatamente, sem retry.
# ===========================================================================

def test_excecao_diferente_de_permission_error_propaga_sem_retry():
    wb = _FakeWorkbook(falhas_antes_do_sucesso=None, excecao=OSError)
    chamado = []

    with pytest.raises(OSError):
        save_with_retry(wb, "s.xlsx", on_locked=lambda a, e: chamado.append(a) or True)

    assert wb.chamadas == 1
    assert chamado == []

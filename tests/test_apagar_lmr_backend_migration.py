r"""
Testes do Checkpoint 1.4 — migração de
`apagar_lmr_backend.ApagarLMRAutomation` para o protocolo `UICallbacks`
(piloto nº 2 do checkpoint — ver docs/refatoracao/PLANO_REFATORACAO.md,
Fase 1 -> CP 1.4).

`executar_limpeza` é RPA-pesado: logo na primeira linha chama
`self._pesquisar_e_abrir(pmib)`, que toca `self.driver`/`self.wait`
(Selenium) imediatamente (`self.driver.current_url`, linha 1 do método) —
não há nenhum trecho do CORPO de `executar_limpeza` alcançável sem
Selenium além do próprio log inicial. Por isso, em vez de mockar Selenium,
o teste faz `unittest.mock.patch.object` em `_pesquisar_e_abrir` (um método
IRMÃO da própria classe, não um objeto Selenium) para devolver
`(False, mensagem)` — reproduz exatamente o branch "ficha não encontrada"
descrito em docs/base-conhecimento/10-apagar-lmr-backend.md ("Se falha,
loga mensagem e retorna"), suficiente para exercitar de ponta a ponta a
resolução de `callbacks` no topo do método e a tradução de
`callback_log(txt)` -> `callbacks.log(msg)`, sem nunca entrar no loop de
exclusão (que só teria sentido testar com Selenium real ou um mock elaborado
o bastante para arriscar mascarar o próprio comportamento -- fora do escopo
deste checkpoint, ver PLANO_REFATORACAO.md/instruções do checkpoint).

`ApagarLMRAutomation()` é instanciado diretamente (sem `__new__`):
`__init__` só atribui `self.driver = None`/`self.wait = None`/
`self.url_inicial = ...`, sem efeito colateral pesado (confirmado lendo o
método) -- similar a `LMRAutomation`.
"""
from unittest.mock import patch

import apagar_lmr_backend
from sigft.core.callbacks import UICallbacks


# ===========================================================================
# Resolução de `callbacks` no topo de `executar_limpeza`: aceita tanto
# `callbacks=UICallbacks(...)` quanto o kwarg antigo `callback_log`, sem
# erro de assinatura -- `_pesquisar_e_abrir` é substituído para nunca
# alcançar Selenium de verdade.
# ===========================================================================

def test_executar_limpeza_aceita_callbacks_novo_e_para_na_ficha_nao_encontrada():
    logs = []
    auto = apagar_lmr_backend.ApagarLMRAutomation()

    with patch.object(auto, "_pesquisar_e_abrir", return_value=(False, "Ficha 4500063671.9999 não encontrada ou não editável.")):
        resultado = auto.executar_limpeza("4500063671.9999", callbacks=UICallbacks(log=logs.append))

    # [2026-08-28] Era `assert resultado is None`, caracterizando o `return`
    # CRU do caminho de falha. O `None` ali era ACIDENTE de escrita, não
    # decisão: ninguém lia o retorno.
    #
    # Agora o retorno significa "a exclusão terminou limpa?", e a tela usa
    # isso para decidir se LIMPA a coluna "APLICAÇÃO - LMR" do _STATUS_PMIB.
    # Ficha não encontrada -> `False`, que é a resposta certa: limpar a
    # marcação de uma ficha que nem abriu diria que ela está por fazer
    # enquanto as aplicações continuam no portal.
    assert resultado is False
    assert logs == [
        "Iniciando processo para PMIB: 4500063671.9999",
        "Ficha 4500063671.9999 não encontrada ou não editável.",
    ]


def test_executar_limpeza_aceita_callback_log_legado_e_para_na_ficha_nao_encontrada():
    logs = []
    auto = apagar_lmr_backend.ApagarLMRAutomation()

    with patch.object(auto, "_pesquisar_e_abrir", return_value=(False, "não encontrada")):
        resultado = auto.executar_limpeza("X", callback_log=logs.append)

    assert resultado is False
    assert logs == ["Iniciando processo para PMIB: X", "não encontrada"]


def test_executar_limpeza_sem_nenhum_callback_nao_levanta_excecao():
    # Nem `callbacks`, nem `callback_log` -- from_legacy() interno cobre
    # esse caso com um log no-op seguro.
    auto = apagar_lmr_backend.ApagarLMRAutomation()

    with patch.object(auto, "_pesquisar_e_abrir", return_value=(False, "não encontrada")):
        resultado = auto.executar_limpeza("X")

    assert resultado is False


def test_executar_limpeza_callbacks_explicito_tem_prioridade_sobre_callback_log():
    logs_novo = []
    logs_legado = []
    auto = apagar_lmr_backend.ApagarLMRAutomation()

    with patch.object(auto, "_pesquisar_e_abrir", return_value=(False, "não encontrada")):
        auto.executar_limpeza(
            "X",
            callbacks=UICallbacks(log=logs_novo.append),
            callback_log=logs_legado.append,
        )

    assert logs_novo == ["Iniciando processo para PMIB: X", "não encontrada"]
    assert logs_legado == []  # callback_log legado ignorado quando `callbacks` é passado


def test_executar_limpeza_repassa_pmib_codigo_para_pesquisar_e_abrir():
    auto = apagar_lmr_backend.ApagarLMRAutomation()

    with patch.object(auto, "_pesquisar_e_abrir", return_value=(False, "x")) as mock_pesquisar:
        auto.executar_limpeza("4500063671.1234", callback_log=lambda *_: None)

    mock_pesquisar.assert_called_once_with("4500063671.1234")

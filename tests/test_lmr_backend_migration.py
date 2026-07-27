r"""
Testes do Checkpoint 1.4 — migração de `lmr_backend.LMRAutomation` para o
protocolo `UICallbacks` (piloto nº 1 do checkpoint — ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.4).

`LMRAutomation.processar_lista`/`_processar_ficha_lmr_interna` são
RPA-pesados: a maior parte do corpo depende de `self.driver`/`self.wait`
(Selenium) — não testável offline (Fases 1-4 não tocam seletor/fluxo do
portal). Este arquivo foca no que É testável em isolamento, sem mockar
Selenium:

  (a) a RESOLUÇÃO de `callbacks` no topo de `processar_lista` aceita tanto
      `callbacks=UICallbacks(...)` quanto os kwargs antigos
      (`callback_log`/`callback_ask`/`callback_input`) sem erro de
      assinatura -- exercitado chamando `processar_lista([], ...)` (lista
      de PMIBs VAZIA: o `for` que toca `self.driver`/`self.wait` nunca
      executa, então o método roda até o fim sem qualquer Selenium real);
  (b) o trecho de `_processar_ficha_lmr_interna` alcançável SEM Selenium: o
      early-return quando `df_filtrado.empty` (roda ANTES de qualquer
      `self.wait`/`self.driver`) e, principalmente, a decisão de "linha
      inicial" -- extraída neste checkpoint para o método próprio
      `_resolver_linha_inicial` exatamente para poder ser testada assim
      (ver comentário acima do método em lmr_backend.py). Confirmado lendo
      o método inteiro: `_processar_ficha_lmr_interna` só chama
      `self.wait.until(...)` pela primeira vez DEPOIS de
      `_resolver_linha_inicial` já ter decidido `linha_inicio` -- então
      testar `_resolver_linha_inicial` isoladamente cobre o trecho
      "alcançável sem Selenium" citado no checkpoint.

Instâncias são criadas via `LMRAutomation.__new__(...)` (evita `__init__`
real) OU via `LMRAutomation()` direto quando não há problema -- `__init__`
só atribui `self.driver = None`/`self.wait = None`/`self.url_inicial = ...`,
sem nenhum efeito colateral pesado (sem I/O, sem abrir navegador nenhum) --
confirmado lendo o método. Os testes de `_resolver_linha_inicial` usam
`__new__` porque o método não usa NENHUM atributo de instância (só os
parâmetros recebidos), então nem precisa de `self` inicializado.

Não tenta exercitar o loop principal de preenchimento (usa
`self.wait.until(...)` a cada campo) nem o loop de busca/edição de
`processar_lista` com lista NÃO-vazia -- isso exigiria mockar Selenium de
forma extensa (e arriscaria reproduzir o próprio bug de "índice não avança
no except", documentado em docs/refatoracao/PENDENCIAS.md, como um loop
infinito dentro do teste). Fora isso, ver docstring da classe para o
racional completo.
"""
import pytest

import lmr_backend
from sigft.core.callbacks import UICallbacks


def _boom(*_args, **_kwargs):
    raise AssertionError("callback_input não deveria ter sido chamado neste cenário")


class _FakeDF:
    """Substituto mínimo de `pandas.DataFrame` para os 2 trechos de
    `_processar_ficha_lmr_interna`/`_resolver_linha_inicial` exercitados
    aqui -- só usam `len(df)`, `.empty` e `.shape[0]` (nunca `.loc`, que só
    é acessado DEPOIS do ponto que testamos). `pandas` está STUBADO como
    `MagicMock` neste ambiente de teste (ver tests/conftest.py) — um
    DataFrame FALSO evita depender da pandas real (ausente) e evita que
    `.empty`/`.shape` virem `MagicMock` (sempre truthy, mascarando o
    comportamento real)."""

    def __init__(self, n):
        self._n = n

    @property
    def empty(self):
        return self._n == 0

    @property
    def shape(self):
        return (self._n,)

    def __len__(self):
        return self._n


# ===========================================================================
# (a) processar_lista: resolução de `callbacks` no topo aceita `callbacks=`
#     novo E os kwargs antigos, sem erro de assinatura -- lista de PMIBs
#     vazia garante que o corpo Selenium do `for` nunca executa.
# ===========================================================================

def test_processar_lista_aceita_callbacks_novo_sem_tocar_selenium():
    logs = []
    auto = lmr_backend.LMRAutomation()  # __init__ é leve (só atribuições)

    resultado = auto.processar_lista([], None, callbacks=UICallbacks(log=logs.append))

    # Comportamento ORIGINAL preservado: método não tinha `return` (devolve
    # None implicitamente) -- CP 1.4 não pode mudar isso.
    assert resultado is None
    assert logs == ["Processo Finalizado."]


def test_processar_lista_aceita_kwargs_legados_sem_tocar_selenium():
    logs = []
    perguntas = []
    auto = lmr_backend.LMRAutomation()

    resultado = auto.processar_lista(
        [],
        None,
        callback_log=logs.append,
        callback_ask=lambda titulo, pergunta: perguntas.append((titulo, pergunta)) or True,
        callback_input=_boom,
    )

    assert resultado is None
    assert logs == ["Processo Finalizado."]
    assert perguntas == []  # lista vazia -> nenhuma ficha processada, nunca pergunta nada


def test_processar_lista_sem_nenhum_callback_nao_levanta_excecao():
    # Nem `callbacks`, nem nenhum kwarg legado -- from_legacy() interno
    # cobre esse caso com defaults seguros.
    auto = lmr_backend.LMRAutomation()
    resultado = auto.processar_lista([], None)
    assert resultado is None


def test_processar_lista_callbacks_explicito_tem_prioridade_sobre_legado():
    logs_novo = []
    logs_legado = []
    auto = lmr_backend.LMRAutomation()

    auto.processar_lista(
        [],
        None,
        callbacks=UICallbacks(log=logs_novo.append),
        callback_log=logs_legado.append,
    )

    assert logs_novo == ["Processo Finalizado."]
    assert logs_legado == []  # callback_log legado é ignorado quando `callbacks` é passado


# ===========================================================================
# (b) _processar_ficha_lmr_interna: early-return de `df_filtrado.empty`
#     (roda antes de qualquer self.wait/self.driver).
# ===========================================================================

def test_processar_ficha_lmr_interna_com_df_vazio_nao_toca_selenium():
    logs = []
    auto = lmr_backend.LMRAutomation.__new__(lmr_backend.LMRAutomation)

    resultado = auto._processar_ficha_lmr_interna(_FakeDF(0), UICallbacks(log=logs.append))

    assert resultado == []
    assert logs == [
        "Qtd aplicações nesta ficha: 0",
        "Nenhuma aplicação encontrada. Pulando.",
    ]


def test_processar_ficha_lmr_interna_repassa_callback_input_cru_para_resolver_linha_inicial():
    # df não-vazio faria o método entrar no while que toca Selenium -- não
    # testamos isso aqui (ver docstring do módulo). Mas com df vazio dá pra
    # confirmar que `callback_input` é aceito como parâmetro posicional
    # opcional sem erro de assinatura, mesmo não sendo usado neste caminho.
    auto = lmr_backend.LMRAutomation.__new__(lmr_backend.LMRAutomation)
    resultado = auto._processar_ficha_lmr_interna(_FakeDF(0), UICallbacks(log=lambda *a, **k: None), _boom)
    assert resultado == []


# ===========================================================================
# (b) _resolver_linha_inicial: trecho isolado, testado a fundo (é o
#     equivalente ao "trecho alcançável sem Selenium" citado no checkpoint).
# ===========================================================================

@pytest.fixture
def auto():
    return lmr_backend.LMRAutomation.__new__(lmr_backend.LMRAutomation)


def test_resolver_linha_inicial_sem_callback_input_devolve_zero_sem_perguntar(auto):
    # Gate original: `if callback_ask and callback_input`. Sem
    # callback_input, hoje o bloco inteiro é pulado -- mesmo com um `ask`
    # que diria "sim", `callback_input` nunca pode ser chamado.
    resultado = auto._resolver_linha_inicial(
        [0, 1, 2],
        UICallbacks(log=lambda *a, **k: None, ask=lambda p, *, titulo=None: True),
        callback_input=None,
    )
    assert resultado == 0


def test_resolver_linha_inicial_ask_recusado_no_op_default_devolve_zero(auto):
    # callback_input presente, mas nenhum `ask` real fornecido -> UICallbacks
    # usa o no-op (`ask()` -> False) -- reproduz "callback_ask ausente hoje"
    # (ver docstring de core/callbacks.py).
    resultado = auto._resolver_linha_inicial(
        [0, 1, 2],
        UICallbacks(log=lambda *a, **k: None),  # ask default no-op
        callback_input=_boom,
    )
    assert resultado == 0


def test_resolver_linha_inicial_usuario_recusa_devolve_zero_sem_chamar_input(auto):
    resultado = auto._resolver_linha_inicial(
        [0, 1, 2],
        UICallbacks(log=lambda *a, **k: None, ask=lambda p, *, titulo=None: False),
        callback_input=_boom,
    )
    assert resultado == 0


def test_resolver_linha_inicial_usuario_aceita_e_informa_linha_valida(auto):
    resultado = auto._resolver_linha_inicial(
        [0, 1, 2, 3],
        UICallbacks(log=lambda *a, **k: None, ask=lambda p, *, titulo=None: True),
        callback_input=lambda titulo, msg: "2",
    )
    assert resultado == 2


def test_resolver_linha_inicial_entrada_nao_numerica_cai_para_zero_e_loga(auto):
    logs = []
    resultado = auto._resolver_linha_inicial(
        [0, 1, 2],
        UICallbacks(log=logs.append, ask=lambda p, *, titulo=None: True),
        callback_input=lambda titulo, msg: "não é um número",
    )
    assert resultado == 0
    assert logs == ["Entrada inválida. Começando do 0."]


@pytest.mark.parametrize("valor_fora_do_range", ["-1", "99"])
def test_resolver_linha_inicial_fora_do_intervalo_e_limitado_a_zero(auto, valor_fora_do_range):
    resultado = auto._resolver_linha_inicial(
        [0, 1, 2],
        UICallbacks(log=lambda *a, **k: None, ask=lambda p, *, titulo=None: True),
        callback_input=lambda titulo, msg: valor_fora_do_range,
    )
    assert resultado == 0


def test_resolver_linha_inicial_chama_ask_com_pergunta_e_titulo_corretos(auto):
    vistos = {}

    def ask_spy(pergunta, *, titulo=None):
        vistos["ask"] = (pergunta, titulo)
        return False

    auto._resolver_linha_inicial(
        [0, 1, 2],
        UICallbacks(log=lambda *a, **k: None, ask=ask_spy),
        callback_input=lambda *a: "0",
    )

    assert vistos["ask"] == (
        "Deseja começar de uma linha específica (não do zero)?",
        "Configuração LMR",
    )


def test_resolver_linha_inicial_chama_callback_input_com_mensagem_original(auto):
    vistos = {}

    def input_spy(titulo, msg):
        vistos["input"] = (titulo, msg)
        return "1"

    resultado = auto._resolver_linha_inicial(
        [0, 1, 2, 3, 4],
        UICallbacks(log=lambda *a, **k: None, ask=lambda p, *, titulo=None: True),
        callback_input=input_spy,
    )

    assert resultado == 1
    assert vistos["input"] == ("Linha Inicial", "Digite o número da linha (0 a 4):")

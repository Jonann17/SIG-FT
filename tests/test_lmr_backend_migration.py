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
    # CP 4.4: `processar_lista` passou a emitir o padrão de lote (início +
    # resumo) em volta das mensagens que já existiam. Com lista VAZIA não há
    # linha de item nenhuma; o que importa aqui (contrato do CP 1.4) é que a
    # mensagem final continua chegando pelo callback recebido.
    assert "Processo Finalizado." in logs
    assert any("Resumo" in linha for linha in logs)


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
    # CP 4.4: `processar_lista` passou a emitir o padrão de lote (início +
    # resumo) em volta das mensagens que já existiam. Com lista VAZIA não há
    # linha de item nenhuma; o que importa aqui (contrato do CP 1.4) é que a
    # mensagem final continua chegando pelo callback recebido.
    assert "Processo Finalizado." in logs
    assert any("Resumo" in linha for linha in logs)
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

    # CP 4.4: idem ao teste acima -- o padrão de lote (início + resumo)
    # envolve as mensagens antigas. O ponto DESTE teste continua sendo que
    # tudo saiu pelo `callbacks` explícito e NADA pelo kwarg legado.
    assert "Processo Finalizado." in logs_novo
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


def test_callback_input_nunca_e_chamado(auto):
    """Sobrou da época do modal, e continua valendo pelo motivo oposto: antes
    `callback_input` só não era chamado quando o usuário recusava; hoje ele não
    é chamado NUNCA -- o parâmetro segue na assinatura porque a cadeia de
    chamadas o repassa, mas não faz nada."""
    resultado = auto._resolver_linha_inicial(
        [0, 1, 2],
        UICallbacks(log=lambda *a, **k: None, ask=lambda p, *, titulo=None: True),
        callback_input=_boom,   # estoura se for chamado
    )
    assert resultado == 0


# ===========================================================================
# Linha inicial: 0 por padrão, sem perguntar (2026-08-21)
# ===========================================================================
# *"O default das fichas deve ser começar do 0, e somente quando eu peço para
# começar de uma linha específica que deve aparecer a mensagem da ficha
# específica (tipo um toggle pra habilitar/desabilitar)."*
#
# Antes, TODA execução abria um Sim/Não e, se sim, um segundo diálogo pedindo o
# número — duas caixas por ficha para uma resposta que é "não" quase sempre.
# Quem decide agora é a TELA, pelo toggle, e ela manda o número pronto.

def _cbs(logs=None):
    return UICallbacks(log=(logs.append if logs is not None else (lambda *a, **k: None)),
                       ask=lambda p, *, titulo=None: True)


def test_sem_linha_inicial_comeca_do_zero_e_NAO_pergunta(auto):
    perguntou = []

    resultado = auto._resolver_linha_inicial(
        [0, 1, 2],
        UICallbacks(log=lambda *a, **k: None,
                    ask=lambda p, *, titulo=None: perguntou.append(p) or True),
        callback_input=lambda *_a: "2",
    )

    assert resultado == 0
    assert perguntou == []   # nenhuma caixa, nem o Sim/Não nem a do número


def test_a_tela_manda_a_linha_e_ela_e_usada(auto):
    assert auto._resolver_linha_inicial([0, 1, 2, 3], _cbs(), linha_inicio=2) == 2


def test_linha_fora_da_faixa_cai_para_zero_COM_aviso(auto):
    """Silenciar aqui faria o usuário pedir a linha 50 numa ficha de 3 códigos
    e achar que ela foi processada a partir dali."""
    logs = []

    assert auto._resolver_linha_inicial([0, 1, 2], _cbs(logs), linha_inicio=50) == 0
    assert any("fora da faixa" in linha for linha in logs)


def test_linha_negativa_tambem_cai_para_zero(auto):
    assert auto._resolver_linha_inicial([0, 1, 2], _cbs(), linha_inicio=-1) == 0


def test_linha_nao_numerica_cai_para_zero_com_aviso(auto):
    logs = []

    assert auto._resolver_linha_inicial([0, 1, 2], _cbs(logs), linha_inicio="abc") == 0
    assert any("inválida" in linha for linha in logs)

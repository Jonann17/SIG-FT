r"""
Testes do Checkpoint 1.4 — `sigft/core/callbacks.py` (`UICallbacks` /
`from_legacy`).

Cobre exatamente os 4 cenários pedidos pelo checkpoint:
  1. `UICallbacks` com todos os campos fornecidos.
  2. `UICallbacks(log=...)` só com log — defaults no-op corretos (`ask()`
     sem provedor devolve `False`; `pause()`/`progress()` não levantam
     exceção).
  3. `from_legacy()` adapta `callback_log`/`callback_ask` corretamente,
     incluindo a inversão de ordem título/pergunta.
  4. `from_legacy()` sem nenhum kwarg produz um `UICallbacks` com defaults
     seguros.

Só stdlib — `sigft.core.callbacks` não depende de nada pesado (ver
docstring do módulo), então este arquivo não precisa do stub de
`tests/conftest.py` para nada além do `sys.path` da raiz do repositório
(já garantido pelo próprio conftest para todo o diretório `tests/`).
"""
from sigft.core.callbacks import UICallbacks, from_legacy


# ===========================================================================
# 1. UICallbacks com todos os campos fornecidos.
# ===========================================================================

def test_uicallbacks_com_todos_os_campos_usa_os_provedores_informados():
    chamadas = []

    def meu_log(msg, nivel="info", contexto=None):
        chamadas.append(("log", msg, nivel, contexto))

    def meu_pause(motivo=None):
        chamadas.append(("pause", motivo))

    def meu_ask(pergunta, *, titulo=None):
        chamadas.append(("ask", pergunta, titulo))
        return True

    def meu_progress(atual, total, *, item=None):
        chamadas.append(("progress", atual, total, item))

    cb = UICallbacks(log=meu_log, pause=meu_pause, ask=meu_ask, progress=meu_progress)

    cb.log("oi", nivel="warn", contexto={"pmib": "x"})
    cb.pause("LOGIN_NECESSARIO")
    assert cb.ask("Confirma?", titulo="Título") is True
    cb.progress(1, 10, item="4500063671.1234")

    assert chamadas == [
        ("log", "oi", "warn", {"pmib": "x"}),
        ("pause", "LOGIN_NECESSARIO"),
        ("ask", "Confirma?", "Título"),
        ("progress", 1, 10, "4500063671.1234"),
    ]


def test_uicallbacks_campos_sao_atributos_diretamente_chamaveis():
    # Uso "cru" (sem passar por from_legacy) -- confirma que os 4 campos
    # citados no plano existem tal qual: log, pause, ask, progress.
    cb = UICallbacks(log=lambda *a, **k: None, pause=lambda *a, **k: None,
                      ask=lambda *a, **k: False, progress=lambda *a, **k: None)
    assert callable(cb.log)
    assert callable(cb.pause)
    assert callable(cb.ask)
    assert callable(cb.progress)


# ===========================================================================
# 2. UICallbacks(log=...) só com log -- defaults no-op corretos.
# ===========================================================================

def test_uicallbacks_so_com_log_tem_ask_pause_progress_no_op_seguros():
    logs = []
    cb = UICallbacks(log=logs.append)

    # ask() sem provedor -> False, sem levantar exceção.
    assert cb.ask("Alguma pergunta?") is False
    assert cb.ask("Outra", titulo="Título") is False

    # pause()/progress() não levantam exceção, com ou sem argumentos.
    cb.pause()
    cb.pause("motivo qualquer")
    cb.progress(1, 10)
    cb.progress(1, 10, item="x")

    # log continua funcionando normalmente (é o único campo obrigatório).
    cb.log("mensagem")
    assert logs == ["mensagem"]


def test_uicallbacks_log_obrigatorio_nao_aceita_construcao_sem_ele():
    import pytest

    with pytest.raises(TypeError):
        UICallbacks()  # falta o único campo obrigatório (log)


# ===========================================================================
# 3. from_legacy() adapta callback_log/callback_ask corretamente (incl. a
#    inversão de ordem título/pergunta).
# ===========================================================================

def test_from_legacy_adapta_callback_log_um_argumento():
    recebidos = []

    def callback_log(txt):
        recebidos.append(txt)

    cb = from_legacy(callback_log=callback_log)

    # A UI de hoje só entende 1 argumento (o texto) -- nivel/contexto são
    # aceitos pela assinatura nova mas IGNORADOS pelo adaptador legado.
    cb.log("mensagem simples")
    cb.log("mensagem com nivel", nivel="warn", contexto={"a": 1})

    assert recebidos == ["mensagem simples", "mensagem com nivel"]


def test_from_legacy_adapta_callback_ask_invertendo_ordem_titulo_pergunta():
    recebidos = []

    def callback_ask(titulo, pergunta):
        # Assinatura ANTIGA, posicional: (titulo, pergunta) -- ver
        # lmr_backend.py antes deste checkpoint.
        recebidos.append((titulo, pergunta))
        return True

    cb = from_legacy(callback_ask=callback_ask)

    # Assinatura NOVA: pergunta é o 1º posicional; titulo é keyword-only.
    resultado = cb.ask("Deseja continuar?", titulo="Configuração LMR")

    assert resultado is True
    assert recebidos == [("Configuração LMR", "Deseja continuar?")]


def test_from_legacy_repassa_resultado_de_callback_ask_sem_alterar():
    cb_nao = from_legacy(callback_ask=lambda titulo, pergunta: False)
    assert cb_nao.ask("Pergunta?") is False

    cb_sim = from_legacy(callback_ask=lambda titulo, pergunta: True)
    assert cb_sim.ask("Pergunta?") is True


def test_from_legacy_adapta_callback_pause_um_argumento():
    # callback_pause(motivo) -- convenção já usada por
    # upload_conditions_backend/upload_tech_specs_backend (fora do escopo
    # de migração deste checkpoint, mas o adaptador já existe para quando
    # esses módulos migrarem).
    recebidos = []
    cb = from_legacy(callback_pause=lambda motivo: recebidos.append(motivo))

    cb.pause("LOGIN_NECESSARIO")
    cb.pause()

    assert recebidos == ["LOGIN_NECESSARIO", None]


def test_from_legacy_callback_progress_e_passthrough_direto():
    # Não há assinatura legada estabelecida para progress (nenhum módulo
    # usa hoje) -- from_legacy só repassa o callback tal como recebido.
    recebidos = []
    cb = from_legacy(callback_progress=lambda atual, total, *, item=None: recebidos.append((atual, total, item)))

    cb.progress(3, 10, item="x")

    assert recebidos == [(3, 10, "x")]


def test_from_legacy_nao_aceita_callback_input_como_parametro():
    # Decisão do arquiteto (CP 1.4): callback_input (texto livre) fica FORA
    # do protocolo UICallbacks/from_legacy -- ver docstring de
    # sigft/core/callbacks.py e docs/refatoracao/PENDENCIAS.md. Confirma
    # que a função não aceita esse kwarg (proteção contra reintrodução
    # acidental).
    import pytest

    with pytest.raises(TypeError):
        from_legacy(callback_input=lambda titulo, pergunta: "42")


# ===========================================================================
# 4. from_legacy() sem nenhum kwarg produz um UICallbacks com defaults
#    seguros.
# ===========================================================================

def test_from_legacy_sem_argumentos_produz_callbacks_totalmente_no_op():
    cb = from_legacy()

    # log(): não levanta exceção, não propaga nada visível (não há como
    # observar "nada acontece" além de garantir que não quebra).
    cb.log("mensagem que deveria ser engolida em silêncio")
    cb.log("com nivel", nivel="warn", contexto={"x": 1})

    # ask(): sempre False -- reproduz "if callback_ask ausente: bloco
    # inteiro pulado" do código legado (ver docstring do módulo).
    assert cb.ask("Pergunta?") is False
    assert cb.ask("Pergunta?", titulo="Título") is False

    # pause()/progress(): no-op, não levantam exceção.
    cb.pause()
    cb.pause("motivo")
    cb.progress(0, 0)
    cb.progress(1, 5, item="y")


def test_from_legacy_sem_argumentos_devolve_instancia_de_uicallbacks():
    cb = from_legacy()
    assert isinstance(cb, UICallbacks)
    assert callable(cb.log)
    assert callable(cb.ask)
    assert callable(cb.pause)
    assert callable(cb.progress)

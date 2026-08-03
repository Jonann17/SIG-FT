r"""
Testes do Checkpoint 4.4 — padrão único de log em `sigft/services/lmr.py`
(`processar_lista`) e `sigft/services/upload_conditions.py`
(`processar_ia_lote`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.4, e
`sigft/core/relatorio_lote.py` (o helper, com 34 testes próprios). Aqui só se
verifica a FIAÇÃO: que cada serviço abre o lote com título/total/contexto,
registra cada item com seu identificador, e fecha com o resumo — sem perder
as mensagens específicas que já existiam.
"""
from __future__ import annotations

from sigft.core.callbacks import UICallbacks
from sigft.services import lmr as lmr_service
from sigft.services import upload_conditions as uc_service


# =============================================================================
# lmr.processar_lista
# =============================================================================

def test_lmr_lista_vazia_ainda_emite_inicio_e_resumo():
    # Um lote de zero itens continua sendo um lote: o usuário precisa ver que
    # rodou e que não havia nada a fazer.
    logs = []
    auto = lmr_service.LMRAutomation()

    auto.processar_lista([], None, callbacks=UICallbacks(log=logs.append))

    texto = "\n".join(logs)
    assert "LMR — aplicando TAGs nas fichas" in texto
    assert "Resumo" in texto
    assert "Processo Finalizado." in logs  # mensagem antiga preservada


def test_lmr_registra_falha_por_ficha_e_o_resumo_sai_mesmo_com_aborto():
    # `self.portal`/`self.driver` são None (driver nunca iniciado), então a
    # 1ª interação estoura -- caminho de "ERRO FATAL" do serviço. Aí o
    # `except` tenta recarregar a home e, como isso TAMBÉM falha, dá `break`
    # (comportamento PRÉ-EXISTENTE e sensato: sem home não há como seguir).
    #
    # O que este teste garante é justamente o valor do CP 4.4 nesse cenário:
    # mesmo com o lote abortando na 1ª ficha, o resumo SAI, registra a falha
    # com motivo e sinaliza quantas fichas ficaram sem processar — antes, o
    # usuário via só uma mensagem de erro solta.
    logs = []
    auto = lmr_service.LMRAutomation()
    callbacks = UICallbacks(log=logs.append, ask=lambda pergunta, titulo=None: True)

    auto.processar_lista(["PMIB-A", "PMIB-B"], None, callbacks=callbacks)

    texto = "\n".join(logs)
    assert "❌ PMIB-A" in texto
    assert "1 falha(s)" in texto
    assert "AttributeError" in texto  # motivo concreto, não "erro"
    # O resumo LISTA a falha, não só conta.
    assert texto.count("PMIB-A") >= 2
    # E diz o que ficou de fora por causa do aborto.
    assert "1 não processado(s)" in texto


def test_lmr_contexto_do_inicio_traz_a_quantidade_de_fichas():
    logs = []
    auto = lmr_service.LMRAutomation()
    callbacks = UICallbacks(log=logs.append, ask=lambda pergunta, titulo=None: True)

    auto.processar_lista(["A", "B", "C"], None, callbacks=callbacks)

    assert any("3 item(ns)" in linha for linha in logs)


# =============================================================================
# upload_conditions.processar_ia_lote
# =============================================================================

class _FakeLoc:
    def __getitem__(self, chave):
        raise KeyError(chave)


class _FakeDF:
    def __init__(self):
        self.loc = _FakeLoc()


def _processor():
    processor = uc_service.ConditionsProcessor.__new__(uc_service.ConditionsProcessor)
    processor.api_key = "chave-fake"
    processor.portal = uc_service.PMIBPortal()
    return processor


def test_upload_conditions_pula_arquivo_sem_codigo_pmib_com_motivo():
    logs = []
    processor = _processor()

    processor.processar_ia_lote(["arquivo_sem_codigo.xlsx"], _FakeDF(), callback_log=logs.append)

    texto = "\n".join(logs)
    assert "Condições — gerando conteúdo por IA" in texto
    assert "⏭️" in texto
    assert "não contém código PMIB" in texto
    # A mensagem específica que já existia continua saindo.
    assert any("Ignorado (Sem PMIB)" in linha for linha in logs)


def test_upload_conditions_resumo_lista_os_pulados():
    logs = []
    processor = _processor()

    processor.processar_ia_lote(
        ["sem_codigo_1.xlsx", "sem_codigo_2.xlsx"], _FakeDF(), callback_log=logs.append
    )

    texto = "\n".join(logs)
    assert "2 pulado(s)" in texto
    assert "Pulados:" in texto


def test_upload_conditions_registra_falha_da_ia_sem_derrubar_o_lote():
    logs = []
    processor = _processor()
    processor.extrair_dados_brutos_excel = lambda caminho: {"descricao_breve": "Bomba"}

    class _LLMQuebrado:
        def generate(self, *a, **k):
            raise RuntimeError("429 rate limit")

    processor._llm = _LLMQuebrado()

    resultado = processor.processar_ia_lote(
        ["4500063671.0001.xlsx", "4500063671.0002.xlsx"], _FakeDF(), callback_log=logs.append
    )

    texto = "\n".join(logs)
    assert resultado == []
    assert "2 falha(s)" in texto
    assert "429 rate limit" in texto
    # Mensagem específica antiga preservada.
    assert any("Falha definitiva no PMIB" in linha for linha in logs)


def test_upload_conditions_sucesso_conta_no_resumo():
    logs = []
    processor = _processor()
    processor.extrair_dados_brutos_excel = lambda caminho: {"descricao_breve": "Bomba"}

    class _Resp:
        parsed_json = {"legislacao_pt": "texto"}

    class _LLMOk:
        def generate(self, *a, **k):
            return _Resp()

    processor._llm = _LLMOk()

    resultado = processor.processar_ia_lote(
        ["4500063671.0001.xlsx"], _FakeDF(), callback_log=logs.append
    )

    texto = "\n".join(logs)
    assert len(resultado) == 1
    assert "1 sucesso(s)" in texto
    assert "✅ 4500063671.0001" in texto
    assert any("Sucesso API" in linha for linha in logs)


# =============================================================================
# tech_specs.processar_lista (lote de RPA)
# =============================================================================

def _automacao_tech_specs():
    from sigft.services import tech_specs as ts

    auto = ts.TechSpecsAutomation.__new__(ts.TechSpecsAutomation)
    auto.driver = None
    auto.wait = None
    auto.portal = ts.PMIBPortal()  # sem engine: `deve_parar()` funciona, o resto estoura
    return auto


def test_tech_specs_emite_inicio_e_resumo_com_falhas_listadas():
    # Sem driver, a 1ª interação de cada ficha estoura -- é o caminho de
    # "Erro geral {pmib}" do serviço, que NÃO aborta o lote.
    logs = []
    auto = _automacao_tech_specs()

    finalizados = auto.processar_lista(
        [
            {"METADATA": {"PMIB": "4500063671.0001"}, "DADOS_TRATADOS": []},
            {"METADATA": {"PMIB": "4500063671.0002"}, "DADOS_TRATADOS": []},
        ],
        callback_log=logs.append,
    )

    texto = "\n".join(logs)
    assert finalizados == []  # nenhuma concluiu
    assert "Características Técnicas — preenchendo no portal" in texto
    assert "2 item(ns)" in texto
    assert "❌ 4500063671.0001" in texto
    assert "❌ 4500063671.0002" in texto, "uma ficha com erro não aborta as seguintes"
    assert "2 falha(s)" in texto
    assert "Falhas:" in texto
    # Mensagens específicas que já existiam continuam saindo.
    assert any("Iniciando 4500063671.0001" in linha for linha in logs)
    assert any("Erro geral" in linha for linha in logs)


def test_tech_specs_lista_vazia_ainda_emite_inicio_e_resumo():
    logs = []
    auto = _automacao_tech_specs()

    assert auto.processar_lista([], callback_log=logs.append) == []

    texto = "\n".join(logs)
    assert "Características Técnicas" in texto
    assert "Resumo" in texto

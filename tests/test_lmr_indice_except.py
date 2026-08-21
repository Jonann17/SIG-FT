r"""
Testes do Checkpoint 4.2 — correção do não-incremento de índice no `except`
de `sigft/services/lmr.py::LMRAutomation._processar_ficha_lmr_interna`.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.2 ("Corrigir o
não-incremento de índice do `lmr` no except (com `ask` ao usuário)") e o
diagnóstico do plano, seção 1.5: "`lmr_backend`: no `except` do loop interno
o índice não avança -> risco de loop infinito".

O BUG: `index` só avança DENTRO do `try`, no laço de agrupamento de TAGs. Se
a exceção acontecesse ANTES disso (ex.: erro ao ler a linha do DataFrame), o
`while` externo repetia EXATAMENTE o mesmo item — para sempre. Como o
`except` abre um modal (`callbacks.ask`), na prática virava um modal atrás do
outro, sem saída a não ser matar o aplicativo no meio de um lote.

A CORREÇÃO distingue 2 situações, porque elas têm riscos opostos:
  (a) índice JÁ avançou (falha durante a interação com o portal) -> o laço
      segue sozinho; só avisa. NÃO oferece "tentar de novo": o item pode ter
      sido salvo parcialmente e repetir cegamente duplicaria TAGs no portal.
  (b) índice NÃO avançou (falha antes de qualquer envio) -> pergunta ao
      usuário: tentar de novo (seguro, nada foi enviado) ou pular. Sem
      provedor de `ask`, o contrato do CP 1.4 devolve `False` -> pula, que é
      o default SEGURO (garante progresso, nunca trava).

Estes testes são possíveis sem Selenium porque toda a parte quebrada roda
ANTES da primeira chamada a `self.driver`/`self.wait` — a falha é injetada
no próprio DataFrame.
"""
from __future__ import annotations

import pytest

from sigft.core.callbacks import UICallbacks
from sigft.services.lmr import LMRAutomation

# Teto de segurança: se a correção regredir, o laço volta a ser infinito e a
# suíte TRAVARIA (pior que falhar). Os fakes abaixo levantam ao ultrapassar
# este número de iterações, transformando "trava" em "falha visível".
_MAX_ITERACOES = 50


class _LoopInfinitoDetectado(BaseException):
    """Levantada pelos fakes quando o laço passa do teto -- sinal de que a
    correção do CP 4.2 regrediu.

    Herda de `BaseException`, NÃO de `Exception`, de propósito: o código sob
    teste captura `except Exception` dentro do laço, então uma sentinela
    derivada de `Exception` seria ENGOLIDA por ele e a suíte TRAVARIA em vez
    de falhar. De quebra, é uma demonstração concreta do ganho deste
    checkpoint: com o `except:` NU de antes, nem isto escaparia — inclusive
    `KeyboardInterrupt`, o que tornava um lote de 200 fichas impossível de
    interromper com Ctrl+C."""


class _Linha(dict):
    """Linha de DataFrame falsa: `row['Código_PMIB']` funciona igual."""


class _Loc:
    """Réplica mínima de `df.loc`, cobrindo as 2 formas usadas pelo código:
    `df.loc[i]` (linha inteira) e `df.loc[i, 'coluna']` (célula)."""

    def __init__(self, linhas, falhar_em=None, contador=None):
        self._linhas = linhas
        self._falhar_em = falhar_em
        self._contador = contador

    def __getitem__(self, chave):
        if self._contador is not None:
            self._contador["acessos"] += 1
            if self._contador["acessos"] > _MAX_ITERACOES:
                raise _LoopInfinitoDetectado(
                    "laço passou de %d iterações -- índice não avança no except"
                    % _MAX_ITERACOES
                )
        if isinstance(chave, tuple):
            indice, coluna = chave
            return self._linhas[indice][coluna]
        if self._falhar_em is not None and chave == self._falhar_em:
            raise KeyError(f"linha {chave} corrompida (injetado pelo teste)")
        return _Linha(self._linhas[chave])


class _ILoc:
    def __init__(self, linhas):
        self._linhas = linhas

    def __getitem__(self, indice):
        return _Linha(self._linhas[indice])


class _FakeDF:
    """DataFrame falso com só o que `_processar_ficha_lmr_interna` usa:
    `.empty`, `.shape[0]`, `len()`, `.loc` e `.iloc`."""

    def __init__(self, linhas, falhar_em=None):
        self._linhas = linhas
        self.empty = not linhas
        self.shape = (len(linhas), 3)
        self.contador = {"acessos": 0}
        self.loc = _Loc(linhas, falhar_em=falhar_em, contador=self.contador)
        self.iloc = _ILoc(linhas)

    def __len__(self):
        return len(self._linhas)


def _linhas(*codigos):
    return [
        {"PMIB": "4500063671.0001", "Código_PMIB": cod, "TAG_PMIB": f"TAG-{i}"}
        for i, cod in enumerate(codigos)
    ]


def _automacao():
    """Instância sem `__init__` -- `driver`/`wait` ficam ausentes de
    propósito: qualquer toque em Selenium vira AttributeError, que é
    justamente a falha "durante a interação com o portal" do cenário (a)."""
    auto = LMRAutomation.__new__(LMRAutomation)
    auto.driver = None
    auto.wait = None
    auto.portal = None
    return auto


def _callbacks(resposta_ask, registro):
    return UICallbacks(
        log=lambda msg, nivel="info", contexto=None: registro["logs"].append(msg),
        ask=lambda pergunta, titulo=None: (
            registro["asks"].append(pergunta) or resposta_ask
        ),
    )


# =============================================================================
# (b) Índice NÃO avançou -- o cenário que travava
# =============================================================================

def test_falha_antes_do_indice_avancar_com_ask_negativo_pula_o_item():
    # `ask` devolvendo False = "pular". Sem a correção, o índice ficaria
    # parado e o while repetiria o mesmo item indefinidamente.
    registro = {"logs": [], "asks": []}
    df = _FakeDF(_linhas("COD-A", "COD-B"), falhar_em=0)

    erros = df and _automacao()._processar_ficha_lmr_interna(
        df, _callbacks(False, registro)
    )

    # Item 0 falhou e foi pulado; item 1 seguiu (e falhou no Selenium ausente).
    assert len(registro["asks"]) == 2  # um por item, sem repetição infinita
    assert any("COD-A" in e["codigo_pmib"] or e["index"] == 0 for e in erros)


def test_falha_antes_do_indice_avancar_sem_provedor_de_ask_tambem_progride():
    # Contrato do CP 1.4: `UICallbacks.ask` sem provedor devolve False. É o
    # default SEGURO -- execução sem UI nunca pode travar num laço infinito.
    registro = {"logs": [], "asks": []}
    df = _FakeDF(_linhas("COD-A", "COD-B"), falhar_em=0)
    callbacks = UICallbacks(log=lambda msg, nivel="info", contexto=None: None)

    erros = _automacao()._processar_ficha_lmr_interna(df, callbacks)

    assert len(erros) == 2  # os 2 itens processados (e falhos), sem travar


def test_nem_com_ask_positivo_o_laco_repete_o_mesmo_item():
    """⚠️ MUDOU EM 2026-08-21, e para melhor.

    Antes o agrupamento acontecia DENTRO do laço, linha a linha, e uma falha
    logo na leitura da linha deixava o índice parado -- daí existir um ramo que
    perguntava "tentar de novo?" e, com "sim", repetia o mesmo item. Este teste
    provava que o laço realmente repetia, e que um teto detectaria a regressão
    para laço infinito.

    Com o agrupamento feito ANTES do laço (`agrupar_por_codigo`, para o código
    espalhado na planilha), não há mais nada que possa falhar antes do índice
    avançar: os grupos já estão em memória. O ramo de repetição ficou
    inalcançável, e o comportamento que sobra é o SEGURO -- avisar e seguir --,
    que é o que o próprio código já dizia preferir: *"o item pode ter sido
    salvo parcialmente no portal, e repetir cegamente duplicaria TAGs"*.

    O teto de laço infinito continua armado; o que este teste prende agora é
    que ele NÃO dispara nem com o usuário respondendo "sim" a tudo.
    """
    registro = {"logs": [], "asks": []}
    df = _FakeDF(_linhas("COD-A", "COD-B"), falhar_em=0)

    erros = _automacao()._processar_ficha_lmr_interna(df, _callbacks(True, registro))

    assert len(erros) == 2          # os dois itens tentados, nenhum repetido
    assert len(registro["asks"]) == 2


# =============================================================================
# (a) Índice JÁ avançou -- laço segue sozinho, sem oferecer repetição
# =============================================================================

def test_falha_depois_do_agrupamento_segue_para_o_proximo_sem_repetir():
    # Sem `falhar_em`: a leitura do DataFrame funciona, o agrupamento avança
    # o índice, e a falha vem no primeiro toque em Selenium (`self.wait` é
    # None). O laço tem que andar sozinho.
    registro = {"logs": [], "asks": []}
    df = _FakeDF(_linhas("COD-A", "COD-B", "COD-C"))

    erros = _automacao()._processar_ficha_lmr_interna(df, _callbacks(False, registro))

    assert len(erros) == 3  # os 3 códigos foram tentados, um a um
    assert [e["codigo_pmib"] for e in erros] == ["COD-A", "COD-B", "COD-C"]


def test_falha_depois_do_agrupamento_nao_oferece_tentar_de_novo():
    # A mensagem do cenário (a) é informativa ("segue para o próximo"), NÃO
    # uma escolha SIM/NÃO -- repetir às cegas poderia duplicar TAGs já salvas.
    registro = {"logs": [], "asks": []}
    df = _FakeDF(_linhas("COD-A"))

    _automacao()._processar_ficha_lmr_interna(df, _callbacks(False, registro))

    assert len(registro["asks"]) == 1
    pergunta = registro["asks"][0]
    assert "segue para o próximo" in pergunta
    assert "SIM =" not in pergunta  # não é uma escolha


def test_agrupamento_de_tags_consecutivas_ainda_junta_o_mesmo_codigo():
    # Regressão do comportamento original preservado: TAGs consecutivas com o
    # MESMO código viram um item só (o índice avança em bloco).
    registro = {"logs": [], "asks": []}
    df = _FakeDF(_linhas("COD-A", "COD-A", "COD-A", "COD-B"))

    erros = _automacao()._processar_ficha_lmr_interna(df, _callbacks(False, registro))

    assert [e["codigo_pmib"] for e in erros] == ["COD-A", "COD-B"]  # 2 grupos, não 4


# =============================================================================
# Invariante geral
# =============================================================================

@pytest.mark.parametrize("resposta_ask", [False, None])
def test_laco_sempre_termina_quando_o_usuario_nao_pede_repeticao(resposta_ask):
    # Qualquer resposta falsy de `ask` tem que garantir progresso.
    registro = {"logs": [], "asks": []}
    df = _FakeDF(_linhas("COD-A", "COD-B", "COD-C"), falhar_em=1)

    erros = _automacao()._processar_ficha_lmr_interna(
        df, _callbacks(resposta_ask, registro)
    )

    assert len(erros) == 3

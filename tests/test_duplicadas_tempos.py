r"""
Quanto tempo cada seção levou — a medição que falta antes de mexer nos sleeps.

O usuário observou em 2026-08-21: *"quando ele faz o fornecedor ele demora
muito para a segunda etapa"*. A tentação é sair caçando `time.sleep` e cortar
os maiores. Só que o robô tem 23 pausas nomeadas nos módulos de duplicadas, e
NENHUMA delas passa de 3 s -- ou seja, "demora muito" quase certamente não é
uma pausa, é um passo que se repete (o laço da Referência tenta `'D1`, `'D2`,
`'D3`… e cada tentativa custa uma ida ao servidor).

"Quase certamente" não é medição. Este arquivo tranca a medição: o resultado da
ficha passa a carregar o tempo de cada seção, e o log fecha com a conta. A
próxima rodada real diz ONDE o tempo está, em vez de a gente adivinhar.

⚠️ O tempo é medido ENTRE registros, não dentro da seção. É uma aproximação
deliberada: as seções rodam em sequência, então o intervalo entre o registro
da anterior e o desta é o custo desta -- e medir por dentro exigiria mexer nas
sete funções do injetor, que é muito estrago para um número.
"""
import pytest

from sigft.services import duplicadas_robo as robo
from sigft.services.duplicadas_injetor import ResultadoDaSecao


class _Relogio:
    """Relógio falso: avança só quando mandam. Testar tempo com o relógio de
    verdade é como o `flaky` nasce."""

    def __init__(self):
        self.agora = 100.0

    def __call__(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos


@pytest.fixture
def relogio(monkeypatch):
    falso = _Relogio()
    monkeypatch.setattr(robo.time, "monotonic", falso)
    return falso


def test_registrar_guarda_o_tempo_de_cada_secao(relogio):
    resultado = robo.ResultadoDaFicha("4500063671.1418", "4500063671.1471")
    relogio.avancar(2.0)
    resultado.registrar(ResultadoDaSecao("fabricante", True))
    relogio.avancar(18.0)
    resultado.registrar(ResultadoDaSecao("referencia", True))

    assert resultado.tempos == [("fabricante", 2.0), ("referencia", 18.0)]


def test_resumo_de_tempos_ordena_do_mais_caro_para_o_mais_barato(relogio):
    resultado = robo.ResultadoDaFicha("x", "y")
    relogio.avancar(2.0)
    resultado.registrar(ResultadoDaSecao("fabricante", True))
    relogio.avancar(18.0)
    resultado.registrar(ResultadoDaSecao("referencia", True))
    relogio.avancar(5.0)
    resultado.registrar(ResultadoDaSecao("imagens", True))

    # Do mais caro para o mais barato: quem lê o log quer o culpado primeiro,
    # não a ordem de execução (que ele já conhece).
    assert resultado.resumo_de_tempos.index("referencia") < \
        resultado.resumo_de_tempos.index("imagens") < \
        resultado.resumo_de_tempos.index("fabricante")


def test_resumo_de_tempos_mostra_segundos_com_uma_casa(relogio):
    resultado = robo.ResultadoDaFicha("x", "y")
    relogio.avancar(18.44)
    resultado.registrar(ResultadoDaSecao("referencia", True))
    assert "18.4 s" in resultado.resumo_de_tempos


def test_resumo_de_tempos_mostra_o_total(relogio):
    resultado = robo.ResultadoDaFicha("x", "y")
    relogio.avancar(2.0)
    resultado.registrar(ResultadoDaSecao("fabricante", True))
    relogio.avancar(3.0)
    resultado.registrar(ResultadoDaSecao("referencia", True))
    assert "5.0 s" in resultado.resumo_de_tempos


def test_resumo_de_tempos_sem_secao_nenhuma_e_vazio():
    """Ficha que morreu antes de rodar seção não pode imprimir uma linha de
    tempos vazia no meio do log -- ela já tem o erro fatal para contar."""
    assert robo.ResultadoDaFicha("x", "y").resumo_de_tempos == ""

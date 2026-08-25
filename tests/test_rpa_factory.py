r"""
`sigft/core/rpa/factory.py` — `criar_engine`.

⚠️ ESTE ARQUIVO ENCOLHEU MUITO NO CP 5.5 (2026-08-25), e o que saiu conta uma
história que vale guardar.

Ele nasceu no CP 5.1 testando `config.get_rpa_engine`: o mapa `RPA_ENGINE` por
módulo, a variável `SIGFT_RPA_ENGINE`, a precedência entre os dois, o erro no
valor desconhecido. Quinze testes para um interruptor — e eles se pagaram: era
esse interruptor que tornava a Fase 5 reversível, porque o aceite de cada
checkpoint era uma sessão no portal real, que podia dar errado.

A Fase 6 fechou validada no portal e o Selenium saiu do projeto. Com um motor
só, não há o que escolher, e o interruptor virou entulho. Os testes dele foram
junto.

**O que fica é o que continua sendo verdade:** `criar_engine` é o único lugar
que conhece uma classe de motor concreta. Nenhum serviço importa
`PlaywrightEngine` — pedem o motor à fábrica. É essa regra que faria a troca
por um motor futuro custar um `if` aqui e nada em lugar nenhum mais, e é ela
que estes testes trancam.

Nenhum motor é realmente construído: a classe concreta é substituída por uma
sentinela, então estes testes rodam sem Playwright e sem browser.
"""
from __future__ import annotations

import sigft.core.rpa.factory as factory_mod


class _EngineFalso:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _interceptar(monkeypatch):
    """Substitui a classe concreta que `criar_engine` importaria, no módulo de
    origem -- o import dentro da função resolve pelo `sys.modules`, então
    trocar o atributo lá basta."""
    criados = []

    def _criar(**kwargs):
        engine = _EngineFalso(**kwargs)
        criados.append(engine)
        return engine

    import sigft.core.rpa.playwright_engine as pe

    monkeypatch.setattr(pe.PlaywrightEngine, "criar", staticmethod(_criar))
    return criados


def test_criar_engine_sobe_o_playwright(monkeypatch):
    criados = _interceptar(monkeypatch)

    engine = factory_mod.criar_engine("apagar_lmr", wait_timeout=20)

    assert isinstance(engine, _EngineFalso)
    assert criados[0].kwargs == {"wait_timeout": 20, "download_dir": None}


def test_criar_engine_repassa_timeout_e_download_dir(monkeypatch):
    """Os dois parâmetros divergem entre call sites (10, 15 ou 20 segundos) e
    NÃO são unificados pela fábrica -- cada módulo preserva o valor que já
    usava antes da Fase 5. Se a fábrica os engolisse, a mudança seria
    invisível: o robô só ficaria mais impaciente."""
    criados = _interceptar(monkeypatch)

    factory_mod.criar_engine("duplicadas", wait_timeout=15, download_dir="/tmp/dl")

    assert criados[0].kwargs == {"wait_timeout": 15, "download_dir": "/tmp/dl"}


def test_nenhum_servico_importa_um_motor_concreto():
    """A regra que a fábrica existe para guardar, verificada no código-fonte.

    Um `from sigft.core.rpa.playwright_engine import ...` dentro de
    `services/` não quebra nada hoje e torna cara a troca de motor amanhã --
    que é justamente o custo que a Fase 5 pagou para eliminar. Falha aqui é
    barata; falha na próxima migração, não.
    """
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent / "sigft" / "services"
    culpados = [
        arquivo.name
        for arquivo in sorted(raiz.glob("*.py"))
        if "playwright_engine" in arquivo.read_text(encoding="utf-8")
    ]
    assert culpados == [], (
        f"{culpados} importam/citam um motor concreto -- peça à "
        f"`core.rpa.factory.criar_engine`."
    )

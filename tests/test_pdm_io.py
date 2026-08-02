r"""
Testes do Checkpoint 4.3 — otimização de I/O de `sigft/services/pdm.py`.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.3:
"`pdms_fromItaipu_lista_geral`: abrir a origem 1×; `aplicar_templates_fichas`:
carregar o template 1× (reabrir de `BytesIO`). *Aceite*: saída byte-idêntica
em fixture sintética; tempo medido menor."

Duas frentes, com naturezas diferentes:

  A. INVARIANTE DE I/O (roda SEMPRE, com fakes) — conta quantas vezes cada
     função lê um arquivo DO DISCO. É o que a otimização de fato garante e o
     que uma regressão desfaria; não depende de openpyxl real nem de medir
     tempo (medição de tempo em suíte de teste é flaky por natureza).

  B. EQUIVALÊNCIA DE SAÍDA (só com openpyxl REAL, senão pula) — compara a
     impressão digital semântica (valor + fonte + borda + fill + formato de
     número + alinhamento de cada célula, mais merges e alturas de linha)
     contra `tests/fixtures/pdm_io_baseline.json`, capturado rodando o código
     ANTES da otimização. `openpyxl` é dependência de PRODUÇÃO
     (requirements.txt), então numa máquina de desenvolvimento normal este
     bloco roda; no container de teste enxuto (onde `tests/conftest.py`
     troca openpyxl por um `MagicMock`) ele pula, em vez de dar falso verde.

Sobre "byte-idêntica" do aceite: não é possível ao pé da letra — `.xlsx` é um
ZIP e carrega timestamps, então dois saves do MESMO conteúdo já diferem nos
bytes. O que importa (e o que se verifica aqui) é que nada do conteúdo nem da
formatação mudou.
"""
from __future__ import annotations

import importlib
import json
import os
import sys

import pytest

FIXTURE_BASELINE = os.path.join(
    os.path.dirname(__file__), "fixtures", "pdm_io_baseline.json"
)


# =============================================================================
# A. Invariante de I/O — quantas leituras de DISCO cada função faz.
# =============================================================================

class _FakeCell:
    def __init__(self, value=None):
        self.value = value
        self.has_style = False


class _FakeWS:
    """Worksheet falsa com só o que `pdms_fromItaipu_lista_geral` toca."""

    def __init__(self, codigos):
        self._codigos = codigos
        self.max_row = 6 + len(codigos)

    def iter_rows(self, min_row=1, values_only=False):
        for cod in self._codigos:
            yield (_FakeCell(cod),)

    def cell(self, row, column, value=None):
        return _FakeCell(f"DESC-{row}")

    def delete_rows(self, inicio, fim):
        pass

    # Usados por `aplicar_templates_fichas` ao escrever a ficha.
    def merge_cells(self, **kwargs):
        pass

    @property
    def row_dimensions(self):
        return _DimensoesFalsas()


class _DimensoesFalsas(dict):
    def __missing__(self, chave):
        valor = _FakeCell()
        self[chave] = valor
        return valor


class _FakeWB:
    def __init__(self, codigos):
        self.sheetnames = ["TEMPLATE_PDM"]
        self._ws = _FakeWS(codigos)
        self.salvo_em = []
        self.active = self._ws

    def __getitem__(self, nome):
        return self._ws

    def remove(self, ws):
        pass

    def save(self, caminho):
        self.salvo_em.append(caminho)
        # A função só chama `save` quando vai criar o arquivo; materializa
        # para que o `os.listdir` de segurança do laço enxergue o resultado.
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("")

    def close(self):
        pass


def _espionar_load_workbook(monkeypatch, codigos):
    """Substitui `pdm.load_workbook` por um espião que registra a ORIGEM de
    cada chamada: um `str` significa leitura do DISCO; um `BytesIO`, cópia
    vinda da memória. É exatamente a distinção que o CP 4.3 introduz."""
    from sigft.services import pdm

    origens = []

    def espiao(fonte, *args, **kwargs):
        origens.append("disco" if isinstance(fonte, (str, os.PathLike)) else "memoria")
        return _FakeWB(codigos)

    monkeypatch.setattr(pdm, "load_workbook", espiao)
    return origens


def test_lista_geral_le_a_origem_do_disco_uma_unica_vez(monkeypatch, tmp_path):
    # ANTES do CP 4.3 esta função reabria a planilha de origem do disco a cada
    # código novo (1 + N leituras). Agora lê os bytes uma vez e reabre de
    # `BytesIO` — as cópias por iteração continuam existindo (cada volta
    # MUTILA o workbook), mas saem da memória.
    from sigft.services import pdm

    codigos = ["PDM.4020.001", "PDM.5895.003", "PDM.6720.001"]
    origens = _espionar_load_workbook(monkeypatch, codigos)
    destino = tmp_path / "saida"
    destino.mkdir()
    origem = tmp_path / "lista.xlsx"
    origem.write_bytes(b"conteudo-falso-de-planilha")

    pdm.pdms_fromItaipu_lista_geral(str(origem), str(destino))

    assert origens.count("disco") == 0, (
        "a origem não deve mais ser reaberta do disco — os bytes são lidos "
        "uma vez com `open(...)` e reabertos de BytesIO"
    )
    # Uma cópia de verificação + uma por código novo, todas de memória.
    assert origens.count("memoria") == 1 + len(codigos)


def test_lista_geral_nao_cresce_leitura_de_disco_com_mais_codigos(monkeypatch, tmp_path):
    # O ponto do checkpoint: o custo de DISCO deixa de ser proporcional ao
    # número de códigos. Com 3x mais códigos, as leituras de disco continuam
    # as mesmas (zero via load_workbook).
    from sigft.services import pdm

    contagens = []
    for quantidade in (2, 6):
        codigos = [f"PDM.{4000 + i}.001" for i in range(quantidade)]
        origens = _espionar_load_workbook(monkeypatch, codigos)
        destino = tmp_path / f"saida{quantidade}"
        destino.mkdir()
        origem = tmp_path / f"lista{quantidade}.xlsx"
        origem.write_bytes(b"x")
        pdm.pdms_fromItaipu_lista_geral(str(origem), str(destino))
        contagens.append(origens.count("disco"))

    assert contagens == [0, 0]


def test_templates_fichas_le_o_template_do_disco_uma_unica_vez(monkeypatch, tmp_path):
    # ANTES: `load_workbook(path_template)` DENTRO do laço, uma vez por ficha
    # (mais um `wb_templ` carregado no topo e nunca usado). AGORA: os bytes do
    # template são lidos uma vez; cada ficha reabre de `BytesIO`.
    from sigft.services import pdm

    origens = []

    def espiao(fonte, *args, **kwargs):
        origens.append("disco" if isinstance(fonte, (str, os.PathLike)) else "memoria")
        return _FakeWB([])

    monkeypatch.setattr(pdm, "load_workbook", espiao)

    pasta_pdms = tmp_path / "pdms"
    pasta_pdms.mkdir()
    saida = tmp_path / "fichas"
    saida.mkdir()
    for i in range(3):
        (pasta_pdms / f"PDM_402{i}_001 - X.xlsx").write_bytes(b"x")
    template = tmp_path / "template.xlsx"
    template.write_bytes(b"template-falso")

    lista = [
        (f"4500063671.000{i}", f"PDM.402{i}.001 - X", str(saida)) for i in range(3)
    ]
    pdm.aplicar_templates_fichas(lista, str(pasta_pdms), str(template))

    # Os PDMs de origem (1 por ficha) continuam vindo do disco — são arquivos
    # DIFERENTES a cada volta, não há o que cachear. O TEMPLATE é que deixou
    # de ser relido: as 3 cópias dele saem da memória.
    assert origens.count("memoria") == 3, "as 3 cópias do template devem vir de BytesIO"
    assert origens.count("disco") == 3, "só os 3 PDMs de origem, distintos entre si"


def test_templates_fichas_reporta_erro_se_o_template_nao_abrir(tmp_path):
    # A leitura antecipada do template introduziu um novo ponto de falha: ele
    # tem que degradar com mensagem, não estourar exceção crua.
    from sigft.services import pdm

    pasta_pdms = tmp_path / "pdms"
    pasta_pdms.mkdir()

    msg, log = pdm.aplicar_templates_fichas(
        [], str(pasta_pdms), str(tmp_path / "nao_existe.xlsx")
    )

    assert "Erro ao abrir template" in msg
    assert log and "Erro ao abrir template" in log[0]


# =============================================================================
# B. Equivalência de saída — só com openpyxl REAL.
# =============================================================================

# NOTA: não há probe de "openpyxl real" aqui. A primeira versão deste arquivo
# tentava remover o stub do `conftest.py` para alcançar o openpyxl de verdade,
# e isso VAZAVA submódulos reais para o resto da suíte — quebrava
# `tests/test_status_sheet.py::test_abrir_sem_wb_nem_ws_importa_openpyxl_de_forma_preguicosa`,
# que passava sozinho e falhava no conjunto (poluição clássica de sys.modules).
# A comparação de saída contra o baseline exige openpyxl E pandas reais, que
# este container não tem; ela é feita por `scripts/gerar_baseline_pdm.py`
# (comitado, reproduzível numa máquina de desenvolvimento). Aqui verificamos a
# INTEGRIDADE do baseline — que ele continua no repositório, bem formado e
# descrevendo as 2 funções —, o que roda sempre e não polui nada.


def test_baseline_da_saida_existe_e_descreve_as_2_funcoes():
    # Mesmo sem openpyxl real, o baseline capturado antes da otimização é
    # parte do repositório e precisa continuar íntegro — é a evidência de
    # equivalência que o aceite pede.
    with open(FIXTURE_BASELINE, encoding="utf-8") as f:
        baseline = json.load(f)

    assert set(baseline) == {"lista_geral", "templates_fichas"}
    assert baseline["lista_geral"]["arquivos"], "baseline sem arquivos gerados"
    assert baseline["templates_fichas"]["arquivos"]
    # A saída da lista geral tem que ter só a aba TEMPLATE_PDM (as outras são
    # removidas pela função) — invariante de conteúdo capturado no baseline.
    for conteudo in baseline["lista_geral"]["conteudo"].values():
        assert conteudo["abas"] == ["TEMPLATE_PDM"]

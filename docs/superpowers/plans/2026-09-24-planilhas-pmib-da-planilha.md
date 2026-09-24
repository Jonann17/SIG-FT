# Planilhas PMIB direto da planilha de PDMs — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a aba 2 do módulo "2. Planilhas PMIB" monta a ficha direto da planilha de PDMs da Itaipu (a pasta vira método antigo), e a aba 1 ganha "Regenerar as pastas" (From Itaipu e Modificados) com a revisão do PDM no nome.

**Architecture:** `core/pdm_catalogo.py` (único leitor da planilha) passa a guardar, por PDM, as características da revisão vigente em ordem de `SECUENCIA` e as identidades por revisão. `services/pdm_planilha.py` (novo) concentra as regras puras. `services/pdm.py` ganha a fonte "planilha" numa montagem de ficha que continua única. `services/pdm_regeneracao.py` (novo) regenera as duas pastas lendo a planilha uma vez. A tela só coleta campos e chama os serviços numa thread.

**Tech Stack:** Python 3.10, openpyxl, customtkinter (tela), pytest com os dublês de `tests/conftest.py`.

**Spec:** `docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md`.

## Global Constraints

- Python **3.10** (o CI roda 3.10; `ruff` com `target-version = "py310"`, regras `E9`, `F`, `B`). Em `except`, relevantar com `raise ... from e` (B904).
- Código, comentários, docs e commits em **português**; mensagem de commit **sem acento**.
- **Nenhum travessão (`—`) em literal de string** fora de docstring em `sigft/` (`tests/test_texto_da_ui.py`). Em tela e log, use `:` e `,`.
- Serviço não importa tkinter; tela não tem regra de negócio (princípio 2 do `CLAUDE.md`).
- Tela lê serviço carregado pelo splash por `backends.pdm_backend.<funcao>` no momento da chamada, ou importa o serviço **dentro** da função da thread (como `_op1_traduzir`). Nunca `from sigft.app.backends import pdm_backend`.
- `bash scripts/check.sh` **verde antes de cada commit**; `python -m ruff check .` limpo; `python -m pyflakes sigft/app/views/pdm.py` limpo.
- Os testes existentes do módulo passam **sem alteração**: `tests/test_pdm_io.py`, `tests/test_pdm_montador_idioma.py`, `tests/test_pdm_relatorio_lote.py`, `tests/test_traducao_pdm.py`.
- Branch: `claude/practical-einstein-16tqfl`; `git push -u origin claude/practical-einstein-16tqfl` depois de cada commit.
- Rodapé de todo commit:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_019RQRqXdewwcJEzdHB4k7k9
  ```
- A planilha real da Itaipu **não entra no repositório**. A validação com ela roda no scratchpad.

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `tests/_openpyxl_de_verdade.py` | criar | trocar o dublê do openpyxl pelo real durante UM teste |
| `sigft/core/pdm_catalogo.py` | alterar | `Caracteristica`, `Identidade`, campos novos em `PDM`/`CatalogoPDM`, leitura |
| `tests/test_pdm_catalogo.py` | alterar | religar os 9 testes de planilha adormecidos + seção F |
| `sigft/services/pdm_planilha.py` | criar | regras 1 a 9, nome de arquivo com revisão |
| `tests/test_pdm_planilha.py` | criar | as regras, em memória |
| `sigft/services/pdm.py` | alterar | montagem com fonte injetada; fonte planilha; escolha por revisão; `montar_pergunta` no "Formatar"; `formatar_tabela_de_perguntas` |
| `tests/test_pdm_montagem_planilha.py` | criar | montagem pela planilha e escolha por revisão, com openpyxl real |
| `sigft/services/pdm_regeneracao.py` | criar | regenerar as duas pastas |
| `tests/test_pdm_regeneracao.py` | criar | regeneração com openpyxl real |
| `sigft/app/views/pdm.py` | alterar | seletor no painel, seção de regeneração, fonte da aba 2 |
| `tests/test_pdm_tela_planilha.py` | criar | tela por AST |
| docs (`02`, `13`, `PENDENCIAS`, `ROTEIRO`, `CHANGELOG`) | alterar | registro |

---

### Task 1: O catálogo guarda as características em ordem, as identidades e a data

**Files:**
- Create: `tests/_openpyxl_de_verdade.py`
- Modify: `sigft/core/pdm_catalogo.py` (dataclasses antes de `PDM`; `PDM`; `CatalogoPDM`; constantes de coluna; `_ler_mestra`; `carregar`)
- Test: `tests/test_pdm_catalogo.py` (seção E: marcador; seção F nova no fim)

**Interfaces:**
- Produces:
  - `pdm_catalogo.Caracteristica(nome: str, ajuda: str = "", sequencia: int | None = None, linha: int | None = None)` (frozen)
  - `pdm_catalogo.Identidade(revisao: int | None, titulo: str, nome_base: str)` (frozen)
  - `PDM.caracteristicas_em_ordem: tuple[Caracteristica, ...] = ()` e `PDM.identidades: tuple[Identidade, ...] = ()`
  - `CatalogoPDM.exportado_em: str = ""` e `CatalogoPDM.origem: str = ""`
  - `tests/_openpyxl_de_verdade.openpyxl_de_verdade(*modulos)` (context manager)

- [ ] **Step 1: Criar o ajudante de openpyxl real**

`tests/_openpyxl_de_verdade.py`:

```python
"""O openpyxl de VERDADE dentro de um teste, e só dentro dele.

`tests/conftest.py` troca o openpyxl por um `MagicMock` -- a suíte roda sem as
dependências pesadas. O teste que precisa de planilha de verdade troca o dublê
pelo pacote real SÓ enquanto roda, e devolve o dublê no fim. Fazer a troca no
nível do arquivo VAZAVA módulos reais para o resto da suíte (ver a seção B de
`test_pdm_io.py`).

Existe como módulo porque o marcador que `test_pdm_catalogo.py` usava
(`skipif(openpyxl é o dublê)`) era SEMPRE verdadeiro sob o `conftest.py`: os
9 testes de leitura de planilha daquele arquivo nunca rodaram, nem no CI.

Sem o pacote instalado, o teste é PULADO: nunca dá falso verde.
"""
from __future__ import annotations

import contextlib
import importlib
import sys

import pytest

# Nomes que os módulos do app importam do openpyxl NO TOPO (`from openpyxl
# import load_workbook`). Eles ficam ligados ao dublê no momento do import, e
# trocar o `sys.modules` não os alcança: é preciso religá-los um a um.
_DO_PACOTE = ("load_workbook", "Workbook")
_DE_ESTILO = ("Border", "Side", "Alignment", "Font", "PatternFill")


def _e_do_openpyxl(nome):
    return nome == "openpyxl" or nome.startswith("openpyxl.")


@contextlib.contextmanager
def openpyxl_de_verdade(*modulos):
    """Durante o bloco, `import openpyxl` devolve o pacote real, e os nomes de
    `_DO_PACOTE`/`_DE_ESTILO` que existirem em `modulos` apontam para ele."""
    guardados = {n: m for n, m in sys.modules.items() if _e_do_openpyxl(n)}
    for nome in guardados:
        del sys.modules[nome]
    religados = []
    try:
        try:
            real = importlib.import_module("openpyxl")
        except ImportError:
            pytest.skip("openpyxl real nao instalado")
        if not hasattr(real, "Workbook") or "Mock" in type(real).__name__:
            pytest.skip("openpyxl real nao disponivel")
        estilos = importlib.import_module("openpyxl.styles")
        for modulo in modulos:
            for fonte, nomes in ((real, _DO_PACOTE), (estilos, _DE_ESTILO)):
                for nome in nomes:
                    if hasattr(modulo, nome):
                        religados.append((modulo, nome, getattr(modulo, nome)))
                        setattr(modulo, nome, getattr(fonte, nome))
        yield real
    finally:
        for nome in [n for n in list(sys.modules) if _e_do_openpyxl(n)]:
            del sys.modules[nome]
        sys.modules.update(guardados)
        for modulo, nome, valor in reversed(religados):
            setattr(modulo, nome, valor)
```

- [ ] **Step 2: Religar os testes adormecidos de `test_pdm_catalogo.py`**

Na seção E, trocar o bloco `def _openpyxl_real(): ...` + `requer_openpyxl = pytest.mark.skipif(...)` por:

```python
# Estes testes usavam `skipif(openpyxl e o dublê)` -- e sob o `conftest.py` o
# openpyxl e SEMPRE o dublê: nenhum deles rodou ate 2026-09-24, nem no CI. O
# fixture troca o dublê pelo pacote real so durante o teste.
@pytest.fixture
def openpyxl_real():
    with openpyxl_de_verdade() as modulo:
        yield modulo


requer_openpyxl = pytest.mark.usefixtures("openpyxl_real")
```

e no topo do arquivo, depois de `from sigft.core import pdm_catalogo`:

```python
from _openpyxl_de_verdade import openpyxl_de_verdade
```

- [ ] **Step 3: Rodar e ver os 9 testes RODANDO (não mais pulados)**

Run: `python -m pytest tests/test_pdm_catalogo.py -q -rs`
Expected: `51 passed` (42 que já passavam + os 9 religados; nenhum `SKIPPED`).

- [ ] **Step 4: Escrever os testes novos (seção F, no fim do arquivo)**

```python
# =============================================================================
# F. As caracteristicas em ordem, as identidades e a data (modulo 2, 2026-09-24)
# =============================================================================
# Logica pura sobre linhas em memoria: uma planilha FALSA com so o que o leitor
# usa. Assim estes testes rodam sempre, com ou sem openpyxl de verdade.
class _AbaFalsa:
    def __init__(self, linhas):
        self._linhas = [tuple(linha) for linha in linhas]

    def iter_rows(self, min_row=1, max_row=None, values_only=True):
        fim = len(self._linhas) if max_row is None else min(max_row, len(self._linhas))
        for indice in range(min_row - 1, fim):
            yield self._linhas[indice]


class _PlanilhaFalsa:
    def __init__(self, abas):
        self._abas = abas
        self.sheetnames = list(abas)

    def __getitem__(self, nome):
        return self._abas[nome]


def _linha_mestra(codigo, revisao, caract, *, seq=None, ajuda=None,
                  titulo="VALVULA X", base="VALVULA", modif="X", caract_es=None):
    """Uma linha da aba TEMPLATE_PDM, nas colunas REAIS (A=0 ... X=23)."""
    linha = [None] * 24
    linha[0], linha[1] = codigo, codigo.split(".")[1]
    linha[2] = linha[3] = titulo
    linha[4] = linha[5] = base
    linha[6] = linha[7] = modif
    linha[9], linha[13] = revisao, seq
    linha[15], linha[16], linha[18] = caract_es, caract, ajuda
    return linha


def _mestra_falsa(dados, exportado_em="23/09/2026 11:02:02"):
    preambulo = [
        ["TEMPLATE PARA LA IMPORTACIÓN/EXPORTACIÓN DE PDM"],
        ["Exportado el:", exportado_em],
        [], [], ["PDM - PADRÓN DESCRIPTIVO DE MATERIALES"], ["CÓDIGO PDM"],
    ]
    return _PlanilhaFalsa({"TEMPLATE_PDM": _AbaFalsa(preambulo + dados)})


def _em_ordem(catalogo, codigo):
    return [c.nome for c in catalogo.por_codigo(codigo).caracteristicas_em_ordem]


def test_caracteristicas_em_ordem_seguem_a_secuencia_e_nao_a_linha():
    """1.140 dos 1.199 PDMs da planilha de 23/09/2026 NAO trazem as linhas na
    ordem da SECUENCIA: o ACUMULADOR vem 1, 2, 20, 19... A ficha numerava pela
    ordem do arquivo."""
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.1650.001", "2", "DIMENSOES", seq="1"),
        _linha_mestra("PDM.1650.001", "2", "MATERIAL", seq="2"),
        _linha_mestra("PDM.1650.001", "2", "GAS DE ENCHIMENTO", seq="20"),
        _linha_mestra("PDM.1650.001", "2", "CLASSE DE PRESSAO", seq="19"),
    ]))

    assert _em_ordem(cat, "PDM.1650.001") == [
        "DIMENSOES", "MATERIAL", "CLASSE DE PRESSAO", "GAS DE ENCHIMENTO"]


def test_caracteristicas_em_ordem_so_da_revisao_vigente():
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.4820.015", "0", "CARACTERISTICA OBSOLETA", seq="1"),
        _linha_mestra("PDM.4820.015", "1", "DIAMETRO NOMINAL", seq="1"),
        _linha_mestra("PDM.4820.015", "1", "CLASSE DE PRESSAO", seq="2"),
    ]))

    assert _em_ordem(cat, "PDM.4820.015") == ["DIAMETRO NOMINAL", "CLASSE DE PRESSAO"]


def test_nome_e_ajuda_saem_como_a_planilha_traz():
    """O Upload Specs (4.3) casa o nome da ficha com o do Master por IGUALDADE:
    colapsar o espaco duplo quebraria o casamento. E a quebra de linha da ajuda
    e da Itaipu (54 ajudas da planilha de 23/09/2026 tem uma)."""
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.4310.001", "1", "  VAZAO  NOMINAL ", seq="1",
                      ajuda=" Indicar a vazao.\nObserv: FAD  "),
    ]))
    pdm = cat.por_codigo("PDM.4310.001")

    assert pdm.caracteristicas_em_ordem[0].nome == "VAZAO  NOMINAL"
    assert pdm.caracteristicas_em_ordem[0].ajuda == "Indicar a vazao.\nObserv: FAD"
    # o nome do RANQUEAMENTO continua normalizado, como sempre foi
    assert pdm.caracteristicas == ("VAZAO NOMINAL",)


def test_ajuda_vazia_vira_texto_vazio():
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.2940.900", "0", "APLICACAO", seq="1", ajuda=None),
        _linha_mestra("PDM.2940.900", "0", "USO", seq="2", ajuda=""),
    ]))

    ajudas = [c.ajuda for c in cat.por_codigo("PDM.2940.900").caracteristicas_em_ordem]
    assert ajudas == ["", ""]


def test_linha_aponta_de_onde_a_caracteristica_veio():
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.1650.001", "2", "B", seq="2"),
        _linha_mestra("PDM.1650.001", "2", "A", seq="1"),
    ]))

    pares = [(c.nome, c.linha) for c in cat.por_codigo("PDM.1650.001").caracteristicas_em_ordem]
    assert pares == [("A", 8), ("B", 7)]


def test_sequencia_ilegivel_vai_para_o_fim_na_ordem_do_arquivo():
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.1650.001", "2", "SEM ORDEM 1", seq=None),
        _linha_mestra("PDM.1650.001", "2", "SEGUNDA", seq="2"),
        _linha_mestra("PDM.1650.001", "2", "SEM ORDEM 2", seq="lixo"),
        _linha_mestra("PDM.1650.001", "2", "PRIMEIRA", seq="1"),
    ]))

    assert _em_ordem(cat, "PDM.1650.001") == ["PRIMEIRA", "SEGUNDA", "SEM ORDEM 1", "SEM ORDEM 2"]


def test_nome_cai_no_espanhol_quando_o_portugues_vem_vazio():
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.1650.001", "2", None, seq="1", caract_es="DIMENSIONES"),
    ]))

    assert _em_ordem(cat, "PDM.1650.001") == ["DIMENSIONES"]


def test_identidades_mostram_os_dois_pdms_de_um_codigo_duplicado():
    """Caso REAL da planilha de 23/09/2026: PDM.3010.007 e ACOPLAMENTO ROSCADO
    (R1, 2024) e FIXADOR (R0, 2026). A vigente continua sendo a de maior
    revisao; as identidades e que deixam ver a outra."""
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.3010.007", "1", "NORMAS TECNICAS APLICAVEIS", seq="7",
                      titulo="ACOPLAMENTO ROSCADO", base="ACOPLAMENTO", modif="ROSCADO"),
        _linha_mestra("PDM.3010.007", "0", "NORMAS TECNICAS APLICAVEIS", seq="1",
                      titulo="FIXADOR", base="FIXADOR", modif=""),
        _linha_mestra("PDM.3010.007", "0", "COMPRIMENTO TOTAL", seq="2",
                      titulo="FIXADOR", base="FIXADOR", modif=""),
    ]))
    pdm = cat.por_codigo("PDM.3010.007")

    assert pdm.titulo == "ACOPLAMENTO ROSCADO"
    assert [c.nome for c in pdm.caracteristicas_em_ordem] == ["NORMAS TECNICAS APLICAVEIS"]
    assert [(i.revisao, i.titulo, i.nome_base) for i in pdm.identidades] == [
        (1, "ACOPLAMENTO ROSCADO", "ACOPLAMENTO"),
        (0, "FIXADOR", "FIXADOR"),
    ]


def test_pdm_comum_tem_uma_identidade_so():
    cat = pdm_catalogo._ler_mestra(_mestra_falsa([
        _linha_mestra("PDM.1650.001", "2", "A", seq="1"),
        _linha_mestra("PDM.1650.001", "2", "B", seq="2"),
    ]))

    assert len(cat.por_codigo("PDM.1650.001").identidades) == 1


def test_exportado_em_vem_da_linha_2():
    cat = pdm_catalogo._ler_mestra(_mestra_falsa(
        [_linha_mestra("PDM.1650.001", "2", "A", seq="1")],
        exportado_em="23/09/2026 11:02:02"))

    assert cat.exportado_em == "23/09/2026 11:02:02"


def test_sem_a_linha_de_exportacao_a_data_fica_vazia():
    aba = _AbaFalsa([[], ["outra coisa", "x"], [], [], [], [],
                     _linha_mestra("PDM.1650.001", "2", "A", seq="1")])

    cat = pdm_catalogo._ler_mestra(_PlanilhaFalsa({"TEMPLATE_PDM": aba}))

    assert cat.exportado_em == ""


def test_formato_manipulado_nao_tem_caracteristicas_nem_identidades():
    aba = _AbaFalsa([["PDM COMPLETO"], ["PDM.4820.004 - VALVULA ESFERA"]])

    cat = pdm_catalogo._ler_manipulada(_PlanilhaFalsa({"PDMs": aba}))
    pdm = cat.por_codigo("PDM.4820.004")

    assert pdm.caracteristicas_em_ordem == ()
    assert pdm.identidades == ()
    assert cat.exportado_em == ""


@requer_openpyxl
def test_carregar_guarda_de_qual_arquivo_veio(tmp_path):
    caminho = os.path.join(str(tmp_path), "mestra.xlsx")
    _escrever_mestra(caminho)

    assert pdm_catalogo.carregar(caminho).origem == caminho
```

- [ ] **Step 5: Rodar e ver falhar**

Run: `python -m pytest tests/test_pdm_catalogo.py -q`
Expected: FAIL (`AttributeError: 'PDM' object has no attribute 'caracteristicas_em_ordem'`, `CatalogoPDM.__init__() got an unexpected keyword argument` etc.).

- [ ] **Step 6: Implementar em `sigft/core/pdm_catalogo.py`**

(a) Antes de `@dataclass(frozen=True) class PDM`, acrescentar:

```python
@dataclass(frozen=True)
class Caracteristica:
    """Uma característica da revisão VIGENTE de um PDM, como a planilha a traz.

    É a matéria-prima das perguntas da ficha do módulo 2
    (`services/pdm_planilha.py`). `nome` e `ajuda` saem VERBATIM, só sem
    espaço nas pontas, e não passam por `_txt`: o Upload Specs (4.3) casa o
    nome da ficha com o do Master por IGUALDADE exata, então colapsar um
    espaço duplo quebraria o casamento em silêncio. E a quebra de linha da
    ajuda (54 casos na planilha de 23/09/2026) é formatação da Itaipu.
    """

    nome: str
    ajuda: str = ""
    # SECUENCIA: a ordem oficial. A ordem das LINHAS no arquivo não é ela em
    # 1.140 dos 1.199 PDMs da planilha de 23/09/2026.
    sequencia: int | None = None
    # A linha da aba TEMPLATE_PDM de onde a característica veio. É por ela
    # que a regeneração da pasta From Itaipu copia a formatação da linha.
    linha: int | None = None


@dataclass(frozen=True)
class Identidade:
    """O que um código de PDM é numa revisão: título e nome base.

    Existe por causa de dois códigos da planilha de 23/09/2026 que trazem PDMs
    DIFERENTES: `PDM.3010.007` é ACOPLAMENTO ROSCADO na R1 e FIXADOR na R0;
    `PDM.5945.026` é UNIDADE RESISTOR e RELE SEGURANCA. O nome base muda, e é
    isso que separa o caso do histórico de revisão, em que só o modificador
    costuma mudar (`PDM.7010.018`: SERVIDOR CONSOLE na R0, SERVIDOR na R2)."""

    revisao: int | None
    titulo: str
    nome_base: str
```

(b) Em `PDM`, depois do campo `revisao`:

```python
    # As características da revisão vigente, na ordem da SECUENCIA, com a
    # ajuda. Diferente de `caracteristicas` (logo acima), que é o nome
    # normalizado, na ordem do arquivo, e existe para o RANQUEAMENTO: uma não
    # substitui a outra. Vazio no formato manipulado antigo.
    caracteristicas_em_ordem: tuple[Caracteristica, ...] = ()
    # Uma identidade por (revisão, nome base) vista na planilha, da maior
    # revisão para a menor. Vazio no formato manipulado antigo.
    identidades: tuple[Identidade, ...] = ()
```

(c) Em `CatalogoPDM`, depois de `classes`:

```python
    # A data da exportação, lida da linha 2 da aba TEMPLATE_PDM ("Exportado
    # el:"). É o que torna visível, no log, uma planilha velha.
    exportado_em: str = ""
    # O arquivo de onde o catálogo veio (preenchido por `carregar`).
    origem: str = ""
```

(d) Junto das constantes de coluna (`_COL_CARACT_PT = 16`):

```python
_COL_SEQUENCIA = 13
_COL_CARACT_ES = 15
_COL_AJUDA_PT = 18
```

(e) Depois de `_revisao_como_numero`, acrescentar:

```python
def _verbatim(valor) -> str:
    """O texto como a planilha traz, só sem espaço nas pontas. Ver
    `Caracteristica` para o porquê de não passar por `_txt`."""
    return "" if valor is None else str(valor).strip()


def _inteiro(valor) -> int | None:
    """`"12"` -> 12; vazio ou lixo -> None."""
    texto = str(valor if valor is not None else "").strip().replace(",", ".")
    try:
        return int(float(texto))
    except (ValueError, OverflowError):
        return None


def _ordem_oficial(caracteristica: Caracteristica):
    # Sem sequência legível vai para o fim; o desempate é a linha do arquivo.
    sequencia = caracteristica.sequencia
    return (sequencia is None, sequencia or 0, caracteristica.linha or 0)


def _da_maior_revisao(identidade: Identidade):
    return -(identidade.revisao if identidade.revisao is not None else -1)


def _exportado_em(ws) -> str:
    """O "Exportado el: <data>" da linha 2. Vazio se a linha não for essa."""
    for linha in ws.iter_rows(min_row=2, max_row=2, values_only=True):
        if linha and _txt(_valor(linha, 0)).upper().startswith("EXPORTADO"):
            return _txt(_valor(linha, 1))
    return ""
```

(f) Substituir o corpo de `_ler_mestra` por:

```python
def _ler_mestra(wb) -> CatalogoPDM:
    ws = wb["TEMPLATE_PDM"]
    acumulado: dict[str, dict] = {}
    for numero, linha in enumerate(
            ws.iter_rows(min_row=_MESTRA_PRIMEIRA_LINHA, values_only=True),
            start=_MESTRA_PRIMEIRA_LINHA):
        if not linha:
            continue
        codigo = _txt(linha[_COL_CODIGO]).upper()
        # O descarte que a linha 32661 do arquivo real exige: ela traz
        # `1192.999999999937` na coluna do código -- artefato de float que
        # viraria um PDM falso no catálogo.
        if not _RE_CODIGO_PDM.fullmatch(codigo):
            continue

        registro = acumulado.setdefault(codigo, {"revisao": None, "caracts": [],
                                                 "ordem": [], "identidades": {}})
        revisao = _revisao_como_numero(_valor(linha, _COL_REVISAO))
        titulo = _preferir(_valor(linha, _COL_TITULO_PT), _valor(linha, _COL_TITULO_ES))
        base = _preferir(_valor(linha, _COL_BASE_PT), _valor(linha, _COL_BASE_ES))

        # Toda (revisão, nome base) vista entra aqui, INCLUSIVE a de revisão
        # que o resto do laço descarta: é o que deixa ver os dois PDMs de um
        # código duplicado (ver `Identidade`).
        registro["identidades"].setdefault(
            (revisao, normalizar(base)),
            Identidade(revisao=int(revisao) if revisao >= 0 else None,
                       titulo=titulo, nome_base=base),
        )

        # SÓ a revisão vigente, e isso vale para o TÍTULO tanto quanto para as
        # características.
        #
        # O Master guarda uma linha por (PDM, característica, REVISÃO), e 1.023
        # dos 1.194 PDMs do arquivo real têm mais de uma revisão. Nas
        # características, unir revisões traz de volta o que já saiu do PDM (o
        # "lixo de REMOVER" de 2026-08-18; ver PENDENCIAS.md) -- sinal FALSO no
        # desempate entre irmãos.
        #
        # No TÍTULO o dano é pior, e foi o usuário que apontou: o título é a
        # string DIGITADA no filtro de PDM do portal. Título de revisão antiga
        # não filtra nada, e a automação quebra com o PDM CERTO escolhido.
        # Medido no arquivo real: em 47 PDMs a primeira linha não é a vigente, e
        # em 4 deles o título difere -- `PDM.7010.018` é "SERVIDOR CONSOLE" na
        # revisão 0 e **"SERVIDOR"** na vigente (rev 2, 28/02/2025).
        #
        # Por isso os campos de identidade são REESCRITOS quando aparece uma
        # revisão maior, em vez de fixados na primeira linha vista.
        if registro["revisao"] is not None and revisao < registro["revisao"]:
            continue
        if registro["revisao"] is None or revisao > registro["revisao"]:
            registro["revisao"] = revisao
            registro["caracts"] = []
            registro["ordem"] = []
            registro.update(
                classe=_txt(_valor(linha, _COL_CLASSE)),
                titulo=titulo,
                base=base,
                modif=_preferir(_valor(linha, _COL_MODIF_PT),
                                _valor(linha, _COL_MODIF_ES)),
            )

        caract = _txt(_valor(linha, _COL_CARACT_PT))
        if caract and caract not in registro["caracts"]:
            registro["caracts"].append(caract)

        nome = (_verbatim(_valor(linha, _COL_CARACT_PT))
                or _verbatim(_valor(linha, _COL_CARACT_ES)))
        if nome:
            registro["ordem"].append(Caracteristica(
                nome=nome,
                ajuda=_verbatim(_valor(linha, _COL_AJUDA_PT)),
                sequencia=_inteiro(_valor(linha, _COL_SEQUENCIA)),
                linha=numero,
            ))

    pdms = [
        PDM(
            codigo=codigo,
            # A classe vem da coluna, mas o código a embute -- e em 1193 dos
            # 1194 PDMs do arquivo real as duas concordam. Quando a coluna
            # vem vazia, o código resolve.
            classe=r["classe"] or _RE_CODIGO_PDM.fullmatch(codigo).group(1),
            titulo=r["titulo"],
            nome_base=r["base"],
            modificador=r["modif"],
            caracteristicas=tuple(r["caracts"]),
            revisao=(int(r["revisao"])
                     if r["revisao"] is not None and r["revisao"] >= 0
                     else None),
            caracteristicas_em_ordem=tuple(sorted(r["ordem"], key=_ordem_oficial)),
            identidades=tuple(sorted(r["identidades"].values(), key=_da_maior_revisao)),
        )
        for codigo, r in acumulado.items()
    ]
    return CatalogoPDM(pdms=pdms, classes=_ler_classes_mestra(wb),
                       exportado_em=_exportado_em(ws))
```

(g) Em `carregar`, trocar o `try:` por:

```python
    try:
        if "TEMPLATE_PDM" in wb.sheetnames:
            catalogo = _ler_mestra(wb)
        elif "PDMs" in wb.sheetnames:
            catalogo = _ler_manipulada(wb)
        else:
            raise ValueError(
                "A planilha nao tem a aba TEMPLATE_PDM (planilha-mestra da "
                'Itaipu) nem a aba "PDMs" (formato manipulado). Abas '
                f"encontradas: {', '.join(wb.sheetnames)}."
            )
        catalogo.origem = str(caminho)
        return catalogo
    finally:
        wb.close()
```

- [ ] **Step 7: Rodar e ver passar**

Run: `python -m pytest tests/test_pdm_catalogo.py tests/test_cria_fichas_escolha_de_pdm.py tests/test_pdm_titulo_fiel_ao_portal.py -q`
Expected: todos PASS, zero skip em `test_pdm_catalogo.py`.

- [ ] **Step 8: Portão e commit**

```bash
bash scripts/check.sh && python -m ruff check . && \
git add tests/_openpyxl_de_verdade.py tests/test_pdm_catalogo.py sigft/core/pdm_catalogo.py && \
git commit -m "Catalogo de PDMs: caracteristicas em ordem de SECUENCIA, identidades por revisao e data da exportacao" \
  -m "Materia-prima do modulo 2 direto da planilha. E religa os 9 testes de leitura de planilha do test_pdm_catalogo, que nunca rodavam: o skipif via sempre o duble do conftest." \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019RQRqXdewwcJEzdHB4k7k9" && \
git push -u origin claude/practical-einstein-16tqfl
```

---

### Task 2: As regras da montagem pela planilha (`services/pdm_planilha.py`)

**Files:**
- Create: `sigft/services/pdm_planilha.py`
- Test: `tests/test_pdm_planilha.py`

**Interfaces:**
- Consumes: `pdm_catalogo.PDM`, `Caracteristica`, `Identidade`, `CatalogoPDM`, `pdm_catalogo.normalizar`; `cria_fichas.codigo_do_pdm(texto) -> str`, `cria_fichas.revisao_do_pdm(texto) -> int | None`.
- Produces:
  - `PORTAL_ATRAS = "portal_atras"`, `PLANILHA_ATRAS = "planilha_atras"`, `MSG_SEM_CARACTERISTICAS: str`
  - `class PDMRecusado(ValueError)`
  - `PerguntasDoPDM(pdm, linhas: tuple[str, ...], divergencia: str = "", causa: str = "", consequencia: str = "")`
  - `montar_pergunta(numero, nome, ajuda) -> str`
  - `conferir_catalogo(catalogo) -> None` (levanta `PDMRecusado`)
  - `descrever_catalogo(catalogo) -> str`
  - `titulo_do_pdm_usado(texto) -> str`
  - `outras_identidades(pdm) -> list[Identidade]`, `descrever_identidades(identidades) -> str`
  - `perguntas_do_pdm(catalogo, pdm_usado) -> PerguntasDoPDM` (levanta `PDMRecusado`)
  - `nome_de_arquivo(pdm, sufixo="") -> str`, `revisao_no_nome(nome_arquivo) -> int | None`

- [ ] **Step 1: Escrever os testes**

`tests/test_pdm_planilha.py`:

```python
r"""As regras da montagem da ficha pela planilha de PDMs (`services/pdm_planilha.py`).

Lógica pura: os PDMs são montados em memória, sem planilha nem Excel. As
regras numeradas são as da seção 5 de
docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md.
"""
from __future__ import annotations

import pytest

from sigft.core.pdm_catalogo import PDM, Caracteristica, CatalogoPDM, Identidade
from sigft.services import pdm_planilha as regras


def _pdm(codigo="PDM.5925.001", titulo="DISJUNTOR BAIXA TENSAO", base="DISJUNTOR",
         modificador="BAIXA TENSAO", revisao=5,
         caracteristicas=(("TENSAO NOMINAL", "Indicar a tensao nominal."),
                          ("CORRENTE NOMINAL", "")),
         identidades=None):
    if identidades is None:
        identidades = (Identidade(revisao=revisao, titulo=titulo, nome_base=base),)
    return PDM(
        codigo=codigo, classe=codigo.split(".")[1], titulo=titulo, nome_base=base,
        modificador=modificador, revisao=revisao,
        caracteristicas=tuple(nome for nome, _ in caracteristicas),
        caracteristicas_em_ordem=tuple(
            Caracteristica(nome=nome, ajuda=ajuda, sequencia=i, linha=6 + i)
            for i, (nome, ajuda) in enumerate(caracteristicas, start=1)),
        identidades=tuple(identidades),
    )


def _catalogo(*pdms, exportado_em="23/09/2026 11:02:02",
              origem="C:/PDMs/PDMs_SAM-GM_23.09.26.xlsx"):
    return CatalogoPDM(pdms=list(pdms), exportado_em=exportado_em, origem=origem)


# O código duplicado REAL da planilha de 23/09/2026.
ACOPLAMENTO_OU_FIXADOR = _pdm(
    codigo="PDM.3010.007", titulo="ACOPLAMENTO ROSCADO", base="ACOPLAMENTO",
    modificador="ROSCADO", revisao=1,
    caracteristicas=(("NORMAS TECNICAS APLICAVEIS", "Indicar as normas."),),
    identidades=(Identidade(1, "ACOPLAMENTO ROSCADO", "ACOPLAMENTO"),
                 Identidade(0, "FIXADOR", "FIXADOR")),
)


# =============================================================================
# A. O texto da pergunta (regra 3)
# =============================================================================
def test_pergunta_com_ajuda_leva_a_ajuda_entre_parenteses():
    assert regras.montar_pergunta(1, "DIMENSOES", "Indicar as dimensoes.") == \
        "1 - DIMENSOES (Indicar as dimensoes.):"


@pytest.mark.parametrize("vazia", [None, float("nan"), "", "   ", "nan", "NaN", "None"])
def test_pergunta_sem_ajuda_nao_leva_parenteses_nem_nan(vazia):
    """Caso real: em 68 PDMs da planilha de 23/09/2026 TODAS as perguntas
    saíam como "1 - APLICACAO (nan):"."""
    assert regras.montar_pergunta(3, "APLICACAO", vazia) == "3 - APLICACAO:"


def test_pergunta_mantem_espaco_duplo_e_quebra_de_linha_do_meio():
    assert regras.montar_pergunta(1, " VAZAO  NOMINAL ", " Indicar a vazao.\nObserv: FAD ") == \
        "1 - VAZAO  NOMINAL (Indicar a vazao.\nObserv: FAD):"


def test_o_tradutor_le_os_dois_formatos_do_mesmo_jeito():
    """O Tradutor (4.2) corta no primeiro "(" e tira ":. " do fim
    (`services/translator.py`). Com ajuda ou sem, o nome que chega ao Upload
    Specs (4.3) tem de ser o mesmo."""
    def corte_do_tradutor(texto):
        return str(texto).split("(", 1)[0].strip().rstrip(":. ")

    com_ajuda = regras.montar_pergunta(2, "MATERIAL", "Indicar o material.")
    sem_ajuda = regras.montar_pergunta(2, "MATERIAL", None)

    assert corte_do_tradutor(com_ajuda) == corte_do_tradutor(sem_ajuda) == "2 - MATERIAL"


# =============================================================================
# B. O catálogo inteiro (regra 8) e a linha de início do log
# =============================================================================
def test_catalogo_sem_caracteristica_nenhuma_e_recusado():
    manipulado = CatalogoPDM(pdms=[PDM(codigo="PDM.4820.004", classe="4820",
                                       titulo="VALVULA ESFERA")])

    with pytest.raises(regras.PDMRecusado, match="TEMPLATE_PDM"):
        regras.conferir_catalogo(manipulado)


def test_catalogo_da_planilha_da_itaipu_passa():
    regras.conferir_catalogo(_catalogo(_pdm()))


def test_descricao_do_catalogo_traz_arquivo_data_e_total():
    assert regras.descrever_catalogo(_catalogo(_pdm(), ACOPLAMENTO_OU_FIXADOR)) == \
        "Planilha de PDMs: PDMs_SAM-GM_23.09.26.xlsx, exportada em 23/09/2026 11:02:02: 2 PDM(s)."


def test_descricao_sem_data_nao_inventa_data():
    assert regras.descrever_catalogo(_catalogo(_pdm(), exportado_em="")) == \
        "Planilha de PDMs: PDMs_SAM-GM_23.09.26.xlsx: 1 PDM(s)."


# =============================================================================
# C. As perguntas de um material (regras 1, 2, 3, 7)
# =============================================================================
def test_perguntas_saem_numeradas_na_ordem_do_catalogo():
    resultado = regras.perguntas_do_pdm(
        _catalogo(_pdm()), "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R5")

    assert resultado.linhas == (
        "1 - TENSAO NOMINAL (Indicar a tensao nominal.):",
        "2 - CORRENTE NOMINAL:",
    )
    assert resultado.pdm.codigo == "PDM.5925.001"
    assert resultado.divergencia == ""


def test_status_sem_codigo_e_recusado():
    with pytest.raises(regras.PDMRecusado, match="sem codigo de PDM"):
        regras.perguntas_do_pdm(_catalogo(_pdm()), "NENHUM")


def test_pdm_fora_da_planilha_e_recusado_com_a_data_da_planilha():
    with pytest.raises(regras.PDMRecusado,
                       match=r"PDM\.9999\.001 nao esta na planilha de PDMs \(exportada em 23/09/2026"):
        regras.perguntas_do_pdm(_catalogo(_pdm()), "PDM.9999.001 - X, , R0")


def test_pdm_sem_caracteristica_e_recusado():
    with pytest.raises(regras.PDMRecusado, match="nenhuma caracteristica"):
        regras.perguntas_do_pdm(_catalogo(_pdm(caracteristicas=())),
                                "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R5")


# =============================================================================
# D. Revisão diferente do portal (regras 4, 5, 9)
# =============================================================================
def test_portal_atras_da_planilha_gera_e_avisa():
    """O relatório da Itaipu de 23/09/2026 pede "su nueva revisión" para o
    PDM.5925.001; na planilha nova ele está na R5."""
    resultado = regras.perguntas_do_pdm(
        _catalogo(_pdm()), "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R1")

    assert resultado.linhas
    assert resultado.divergencia == regras.PORTAL_ATRAS
    assert resultado.causa == "PDM.5925.001 esta na R1 no portal e na R5 na planilha"
    assert resultado.consequencia == \
        "a ficha saiu com a R5; o PDM precisa subir de revisao no portal"


def test_planilha_atras_do_portal_gera_e_avisa():
    """Decisão do usuário (2026-09-23): gera e avisa, não recusa."""
    resultado = regras.perguntas_do_pdm(
        _catalogo(_pdm()), "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R6")

    assert resultado.linhas
    assert resultado.divergencia == regras.PLANILHA_ATRAS
    assert resultado.causa == "PDM.5925.001 esta na R6 no portal, mas a planilha so tem a R5"
    assert resultado.consequencia == \
        "a ficha saiu com a R5; exporte uma planilha nova da Itaipu"


def test_status_sem_revisao_nao_confere_nada():
    resultado = regras.perguntas_do_pdm(_catalogo(_pdm()), "PDM.5925.001 - DISJUNTOR BAIXA TENSAO")

    assert resultado.divergencia == ""


def test_r0_no_portal_e_revisao_de_verdade():
    resultado = regras.perguntas_do_pdm(
        _catalogo(_pdm(revisao=1)), "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R0")

    assert resultado.divergencia == regras.PORTAL_ATRAS


# =============================================================================
# E. Código com mais de um nome base (regra 6)
# =============================================================================
def test_codigo_duplicado_com_o_titulo_da_vigente_gera():
    resultado = regras.perguntas_do_pdm(
        _catalogo(ACOPLAMENTO_OU_FIXADOR), "PDM.3010.007 - ACOPLAMENTO, ROSCADO, R1")

    assert resultado.linhas == ("1 - NORMAS TECNICAS APLICAVEIS (Indicar as normas.):",)


def test_codigo_duplicado_com_o_titulo_do_outro_pdm_e_recusado():
    with pytest.raises(regras.PDMRecusado) as erro:
        regras.perguntas_do_pdm(_catalogo(ACOPLAMENTO_OU_FIXADOR), "PDM.3010.007 - FIXADOR, , R0")

    assert "ACOPLAMENTO ROSCADO (R1), FIXADOR (R0)" in str(erro.value)
    assert "O STATUS pede 'FIXADOR'" in str(erro.value)


def test_codigo_duplicado_sem_titulo_no_status_e_recusado():
    with pytest.raises(regras.PDMRecusado):
        regras.perguntas_do_pdm(_catalogo(ACOPLAMENTO_OU_FIXADOR), "PDM.3010.007")


def test_so_o_modificador_mudar_entre_revisoes_nao_recusa():
    """PDM.7010.018 é SERVIDOR CONSOLE na R0 e SERVIDOR na R2: histórico
    legítimo, mesmo nome base. Recusar aqui travaria toda ficha antiga."""
    servidor = _pdm(
        codigo="PDM.7010.018", titulo="SERVIDOR", base="SERVIDOR", modificador="",
        revisao=2, caracteristicas=(("NUMERO DE PROCESSADORES", ""),),
        identidades=(Identidade(2, "SERVIDOR", "SERVIDOR"),
                     Identidade(0, "SERVIDOR CONSOLE", "SERVIDOR")))

    resultado = regras.perguntas_do_pdm(_catalogo(servidor), "PDM.7010.018 - SERVIDOR, CONSOLE, R0")

    assert resultado.linhas == ("1 - NUMERO DE PROCESSADORES:",)
    assert resultado.divergencia == regras.PORTAL_ATRAS


def test_outras_identidades_so_as_de_outro_nome_base():
    assert [i.titulo for i in regras.outras_identidades(ACOPLAMENTO_OU_FIXADOR)] == ["FIXADOR"]
    assert regras.outras_identidades(_pdm()) == []


@pytest.mark.parametrize("texto, esperado", [
    ("PDM.3010.007 - ACOPLAMENTO, ROSCADO, R1", "ACOPLAMENTO ROSCADO"),
    ("PDM.4120.000 - UNIDADE EVAPORADORA, , R1", "UNIDADE EVAPORADORA"),
    ("PDM.4820.004 - VÁLVULA ESFERA", "VALVULA ESFERA"),
    ("PDM.3010.007", ""),
])
def test_titulo_do_pdm_usado(texto, esperado):
    assert regras.titulo_do_pdm_usado(texto) == esperado


# =============================================================================
# F. Nome de arquivo com a revisão
# =============================================================================
def test_nome_de_arquivo_leva_codigo_titulo_e_revisao():
    acumulador = _pdm(codigo="PDM.1650.001", titulo="ACUMULADOR", revisao=2)

    assert regras.nome_de_arquivo(acumulador) == "PDM_1650_001 - ACUMULADOR - R2.xlsx"
    assert regras.nome_de_arquivo(acumulador, sufixo="_formatado") == \
        "PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx"


def test_barra_do_titulo_vira_hifen_no_nome():
    """3 títulos da planilha de 23/09/2026 têm "/": no Windows a barra é
    separador de pasta, e é por eles que o fatiamento antigo falha."""
    pdm = _pdm(codigo="PDM.5445.007", titulo="EXTENSAO/TRONCO TORRE", revisao=1)

    assert regras.nome_de_arquivo(pdm) == "PDM_5445_007 - EXTENSAO-TRONCO TORRE - R1.xlsx"


def test_tab_e_espaco_duplo_do_titulo_viram_um_espaco_no_nome():
    pdm = _pdm(codigo="PDM.4310.026", titulo="TUBO \t\t RIGIDO", revisao=0)

    assert regras.nome_de_arquivo(pdm) == "PDM_4310_026 - TUBO RIGIDO - R0.xlsx"


def test_nome_de_arquivo_sem_revisao_legivel():
    pdm = _pdm(codigo="PDM.1650.001", titulo="ACUMULADOR", revisao=None)

    assert regras.nome_de_arquivo(pdm) == "PDM_1650_001 - ACUMULADOR.xlsx"


@pytest.mark.parametrize("nome, revisao", [
    ("PDM_1650_001 - ACUMULADOR - R2.xlsx", 2),
    ("PDM_1650_001 - ACUMULADOR - R12_formatado.xlsx", 12),
    ("/pasta/PDM_1650_001 - ACUMULADOR - R3_formatado.xlsx", 3),
    ("PDM_1650_001 - ACUMULADOR_formatado.xlsx", None),
    ("PDM_1650_001 - ACUMULADOR.xlsx", None),
    ("PDM_1650_001 - R2D2_formatado.xlsx", None),
])
def test_revisao_no_nome(nome, revisao):
    assert regras.revisao_no_nome(nome) == revisao
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_pdm_planilha.py -q`
Expected: FAIL (`ImportError: cannot import name 'pdm_planilha'`).

- [ ] **Step 3: Implementar `sigft/services/pdm_planilha.py`**

```python
r"""As regras da montagem da ficha a partir da PLANILHA de PDMs (módulo 2).

POR QUE EXISTE
------------------------------------------------------------------------
Até 2026-09-24 a ficha só nascia da pasta *PDMs Modificados*, que o próprio
app gerava em dois passos (fatiar, formatar) e que PULAVA o que já existia:
revisado um PDM, a pasta não se atualizava. Rodando o fluxo antigo na planilha
de 23/09/2026 apareceram ainda o `(nan)` no lugar da ajuda vazia (78 PDMs), a
ordem do arquivo no lugar da SECUENCIA (1.140 PDMs) e dois códigos com PDMs
diferentes misturados numa ficha só.

Aqui mora o que decide, para cada material, QUAIS perguntas entram na ficha e
o que avisar: funções puras sobre o catálogo (`core/pdm_catalogo.py`),
testáveis sem Excel. Quem escreve a ficha é `services/pdm.py`; quem regenera
as pastas é `services/pdm_regeneracao.py`.

As regras numeradas (1 a 9) são as da seção 5 de
`docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md`.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Any

from sigft.core import pdm_catalogo
# As duas leituras do texto que o PORTAL devolve para o PDM
# ("CODIGO - NOME BASE, MODIFICADOR, R<n>") moram em `cria_fichas`, e
# `correcao_pdm_planilha.py` já importa de lá do mesmo jeito: uma segunda
# cópia seria o começo de duas regras divergindo.
from sigft.services.cria_fichas import codigo_do_pdm, revisao_do_pdm

# Os dois sentidos da divergência de revisão (regras 4 e 5).
PORTAL_ATRAS = "portal_atras"
PLANILHA_ATRAS = "planilha_atras"

MSG_SEM_CARACTERISTICAS = (
    "Esta planilha nao traz as caracteristicas dos PDMs (e o formato antigo, "
    "com as abas 'PDMs' e 'Instrucoes PDMs'). Use a exportacao da Itaipu, com "
    "a aba TEMPLATE_PDM."
)

# O texto que o `str()` do pandas produz para célula vazia. O passo antigo
# "Formatar" lê o PDM com o pandas, e era daí que vinha o "(nan)" na ficha.
_AJUDA_VAZIA = {"", "NAN", "NONE"}

# ", R<n>" no fim do "PDM usado": a mesma forma que `cria_fichas.revisao_do_pdm`
# lê. Aqui ela só é RETIRADA, para sobrar o título.
_RE_REVISAO_NO_FIM = re.compile(r",\s*R\d+\s*$", re.IGNORECASE)
_RE_CODIGO = re.compile(r"PDM\.\d{4}\.\d{3}", re.IGNORECASE)

# `\ / : * ? " < > |` não entram em nome de arquivo no Windows. Três títulos da
# planilha de 23/09/2026 têm "/" (`EXTENSAO/TRONCO TORRE`...), e é por eles que
# o fatiamento antigo falha: a barra vira separador de pasta.
_PROIBIDOS_NO_NOME = re.compile(r'[\\/:*?"<>|]')

# " - R<n>" no fim do nome, antes da extensão ou do "_formatado".
_RE_REVISAO_NO_NOME = re.compile(r" - R(\d+)(?:_formatado)?\.[A-Za-z]+$", re.IGNORECASE)


class PDMRecusado(ValueError):
    """A ficha deste material NÃO pode ser montada pela planilha. A mensagem
    diz por quê e já vem pronta para o log."""


@dataclass(frozen=True)
class PerguntasDoPDM:
    """As perguntas de UM material, e a conferência de revisão com o portal."""

    pdm: Any                      # `pdm_catalogo.PDM`
    linhas: tuple[str, ...]       # "N - NOME (AJUDA):", já numeradas
    # "" quando as revisões batem ou não há como comparar (regra 9);
    # PORTAL_ATRAS (regra 4) ou PLANILHA_ATRAS (regra 5) quando divergem.
    divergencia: str = ""
    causa: str = ""
    consequencia: str = ""


# =============================================================================
# O texto da pergunta (regra 3)
# =============================================================================
def _texto_de_ajuda(ajuda) -> str:
    if ajuda is None:
        return ""
    if isinstance(ajuda, float) and math.isnan(ajuda):
        return ""
    texto = str(ajuda).strip()
    return "" if texto.upper() in _AJUDA_VAZIA else texto


def montar_pergunta(numero, nome, ajuda) -> str:
    """`"N - NOME (AJUDA):"`, ou `"N - NOME:"` quando não há ajuda.

    Sem os parênteses vazios de propósito: o Tradutor (4.2) corta a pergunta no
    primeiro "(" e tira o ":" do fim, então os dois formatos viram o mesmo
    `"N - NOME"` lá, e é esse nome que o Upload Specs (4.3) casa com o Master.
    Nome e ajuda saem como vieram, só sem espaço nas pontas: o casamento do
    4.3 é por igualdade."""
    nome = "" if nome is None else str(nome).strip()
    ajuda = _texto_de_ajuda(ajuda)
    if ajuda:
        return f"{numero} - {nome} ({ajuda}):"
    return f"{numero} - {nome}:"


# =============================================================================
# O catálogo inteiro (regra 8) e a linha de início do log
# =============================================================================
def conferir_catalogo(catalogo) -> None:
    """Levanta `PDMRecusado` quando a planilha não traz característica
    nenhuma: o formato manipulado antigo, que só tem o título dos PDMs."""
    if not any(p.caracteristicas_em_ordem for p in catalogo.pdms):
        raise PDMRecusado(MSG_SEM_CARACTERISTICAS)


def descrever_catalogo(catalogo) -> str:
    """A linha de início do lote. A data da exportação é o que torna visível,
    no log, uma planilha velha."""
    nome = os.path.basename(catalogo.origem) if catalogo.origem else "(sem nome)"
    quando = f", exportada em {catalogo.exportado_em}" if catalogo.exportado_em else ""
    return f"Planilha de PDMs: {nome}{quando}: {len(catalogo)} PDM(s)."


# =============================================================================
# O código com mais de um nome base (regra 6)
# =============================================================================
def titulo_do_pdm_usado(texto) -> str:
    """O título do "PDM usado", sem código, sem revisão e sem vírgula.

    `"PDM.3010.007 - ACOPLAMENTO, ROSCADO, R1"` -> `"ACOPLAMENTO ROSCADO"`;
    `"PDM.4120.000 - UNIDADE EVAPORADORA, , R1"` -> `"UNIDADE EVAPORADORA"`
    (a vírgula dupla é o modificador vazio, formato medido em 2026-09-23)."""
    bruto = str(texto or "")
    achado = _RE_CODIGO.search(bruto)
    if achado:
        bruto = bruto[achado.end():]
    bruto = _RE_REVISAO_NO_FIM.sub("", bruto)
    return pdm_catalogo.normalizar(bruto.replace(",", " ").strip(" -"))


def outras_identidades(pdm) -> list:
    """As identidades do código cujo NOME BASE não é o da revisão vigente.

    Vazia no PDM comum. Cheia nos dois códigos da planilha de 23/09/2026 que
    trazem PDMs diferentes (`PDM.3010.007`: ACOPLAMENTO ROSCADO e FIXADOR). É
    pelo nome base, e não pelo título, que isso se separa do histórico
    legítimo de revisão, em que só o modificador muda (`SERVIDOR CONSOLE`
    virou `SERVIDOR`)."""
    base = pdm_catalogo.normalizar(pdm.nome_base)
    return [i for i in pdm.identidades if pdm_catalogo.normalizar(i.nome_base) != base]


def descrever_identidades(identidades) -> str:
    """`"ACOPLAMENTO ROSCADO (R1), FIXADOR (R0)"`."""
    return ", ".join(
        f"{i.titulo} (R{'?' if i.revisao is None else i.revisao})" for i in identidades
    )


def _comeca_pelo_nome_base(titulo, nome_base) -> bool:
    base = pdm_catalogo.normalizar(str(nome_base or "").replace(",", " "))
    return bool(base) and (titulo == base or titulo.startswith(base + " "))


# =============================================================================
# As perguntas de um material (regras 1 a 7 e 9)
# =============================================================================
def perguntas_do_pdm(catalogo, pdm_usado) -> PerguntasDoPDM:
    """As perguntas do PDM que o `_STATUS_PMIB` associa ao material.

    Levanta `PDMRecusado` quando a ficha não pode ser montada (regras 6 e 7).
    Revisão diferente da do portal NÃO recusa (decisão do usuário,
    2026-09-23): a ficha sai com a revisão da planilha, e o resultado diz o
    sentido da divergência para o lote avisar."""
    texto = str(pdm_usado or "").strip()
    codigo = codigo_do_pdm(texto)
    if not codigo:
        raise PDMRecusado(f"o 'PDM usado' esta vazio ou sem codigo de PDM: '{texto}'")

    pdm = catalogo.por_codigo(codigo)
    if pdm is None:
        quando = f" (exportada em {catalogo.exportado_em})" if catalogo.exportado_em else ""
        raise PDMRecusado(f"{codigo} nao esta na planilha de PDMs{quando}")
    if not pdm.caracteristicas_em_ordem:
        raise PDMRecusado(f"{codigo} nao tem nenhuma caracteristica na planilha")

    if outras_identidades(pdm):
        pedido = titulo_do_pdm_usado(texto)
        if not _comeca_pelo_nome_base(pedido, pdm.nome_base):
            raise PDMRecusado(
                f"{codigo} aparece na planilha com mais de um nome base: "
                f"{descrever_identidades(pdm.identidades)}. O STATUS pede "
                f"'{pedido}'. Confira com a Itaipu; a ficha nao foi gerada."
            )

    linhas = tuple(
        montar_pergunta(numero, c.nome, c.ajuda)
        for numero, c in enumerate(pdm.caracteristicas_em_ordem, start=1)
    )

    no_portal = revisao_do_pdm(texto)
    if no_portal is None or pdm.revisao is None or no_portal == pdm.revisao:
        return PerguntasDoPDM(pdm=pdm, linhas=linhas)
    if no_portal < pdm.revisao:
        return PerguntasDoPDM(
            pdm=pdm, linhas=linhas, divergencia=PORTAL_ATRAS,
            causa=f"{codigo} esta na R{no_portal} no portal e na R{pdm.revisao} na planilha",
            consequencia=f"a ficha saiu com a R{pdm.revisao}; o PDM precisa subir de revisao no portal",
        )
    return PerguntasDoPDM(
        pdm=pdm, linhas=linhas, divergencia=PLANILHA_ATRAS,
        causa=f"{codigo} esta na R{no_portal} no portal, mas a planilha so tem a R{pdm.revisao}",
        consequencia=f"a ficha saiu com a R{pdm.revisao}; exporte uma planilha nova da Itaipu",
    )


# =============================================================================
# Nome de arquivo com a revisão (regeneração das pastas e método antigo)
# =============================================================================
def nome_de_arquivo(pdm, sufixo="") -> str:
    """`"PDM_1650_001 - ACUMULADOR - R2" + sufixo + ".xlsx"`.

    O código vem primeiro, na forma que o método antigo procura
    (`PDM_1650_001`), seguido de " - ": é o que as guardas antigas de "já
    existe" esperam. Sem revisão legível, fica sem o " - R<n>"."""
    base = f"{pdm.codigo.replace('.', '_')} - {pdm.titulo}"
    if pdm.revisao is not None:
        base += f" - R{pdm.revisao}"
    base = " ".join(_PROIBIDOS_NO_NOME.sub("-", base).split()).rstrip(". ")
    return f"{base}{sufixo}.xlsx"


def revisao_no_nome(nome_arquivo) -> int | None:
    """O `n` de `" - R<n>"` no fim do nome (antes da extensão ou do
    `_formatado`), ou `None` quando o nome não traz revisão."""
    achado = _RE_REVISAO_NO_NOME.search(os.path.basename(str(nome_arquivo or "")))
    return int(achado.group(1)) if achado else None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_pdm_planilha.py -q`
Expected: todos PASS.

- [ ] **Step 5: Portão e commit**

```bash
bash scripts/check.sh && python -m ruff check . && \
git add sigft/services/pdm_planilha.py tests/test_pdm_planilha.py && \
git commit -m "Modulo 2: regras da ficha montada pela planilha de PDMs (pdm_planilha)" \
  -m "Ordem pela SECUENCIA, pergunta sem (nan), revisao diferente do portal gera e avisa nos dois sentidos, codigo com mais de um nome base recusado quando o STATUS pede o outro PDM, e nome de arquivo com a revisao." \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019RQRqXdewwcJEzdHB4k7k9" && \
git push -u origin claude/practical-einstein-16tqfl
```

---

### Task 3: A montagem da ficha com a fonte "planilha" (`services/pdm.py`)

**Files:**
- Modify: `sigft/services/pdm.py`
- Test: `tests/test_pdm_montagem_planilha.py`

**Interfaces:**
- Consumes: tudo de `pdm_planilha` (Task 2); `CatalogoPDM.origem`, `.exportado_em` (Task 1).
- Produces:
  - `pdm.aplicar_templates_fichas_da_planilha(lista_dados, catalogo, path_template, log_callback=None, retry_lock=None) -> tuple[str, list[str]]`
  - `pdm.formatar_tabela_de_perguntas(ws, linhas)` — `linhas`: iterável de `(descricao, resposta)`
  - `pdm.aplicar_templates_fichas(...)`: assinatura, mensagens e retorno **iguais**; com dois arquivos do mesmo PDM, vence o de maior `revisao_no_nome`.

- [ ] **Step 1: Escrever os testes**

`tests/test_pdm_montagem_planilha.py`:

```python
r"""A ficha montada pela PLANILHA de PDMs, e a escolha por revisão no método antigo.

Com openpyxl REAL (ver `tests/_openpyxl_de_verdade.py`): o que se confere é a
ficha que o fornecedor abre, célula a célula.
"""
from __future__ import annotations

import ast
import inspect
import os
import textwrap

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade
from sigft.core.pdm_catalogo import PDM, Caracteristica, CatalogoPDM, Identidade
from sigft.services import pdm


@pytest.fixture
def openpyxl_real():
    with openpyxl_de_verdade(pdm) as modulo:
        yield modulo


def _pdm(codigo, titulo, revisao, caracteristicas, base=None, identidades=None):
    base = base or titulo.split()[0]
    return PDM(
        codigo=codigo, classe=codigo.split(".")[1], titulo=titulo, nome_base=base,
        revisao=revisao,
        caracteristicas_em_ordem=tuple(
            Caracteristica(nome=nome, ajuda=ajuda, sequencia=i, linha=6 + i)
            for i, (nome, ajuda) in enumerate(caracteristicas, start=1)),
        identidades=tuple(identidades or (Identidade(revisao, titulo, base),)),
    )


ACUMULADOR = _pdm("PDM.1650.001", "ACUMULADOR", 2, [
    ("DIMENSOES", "Indicar as dimensoes."),
    ("MATERIAL", "Indicar o material."),
    ("PESO", None),
])
DISJUNTOR = _pdm("PDM.5925.001", "DISJUNTOR BAIXA TENSAO", 5, [("TENSAO NOMINAL", "")])


def _catalogo(*pdms):
    return CatalogoPDM(pdms=list(pdms), exportado_em="23/09/2026 11:02:02",
                       origem="/pdms/PDMs_SAM-GM_23.09.26.xlsx")


def _template(pasta, openpyxl):
    caminho = os.path.join(str(pasta), "template.xlsx")
    wb = openpyxl.Workbook()
    wb.active.title = "Ficha Técnica Padrão"
    wb.save(caminho)
    return caminho


def _perguntas_da_ficha(caminho, openpyxl):
    ws = openpyxl.load_workbook(caminho)["Ficha Técnica Padrão"]
    return [ws.cell(row=linha, column=3).value for linha in range(79, ws.max_row + 1)
            if ws.cell(row=linha, column=3).value]


# =============================================================================
# A. A ficha pela planilha
# =============================================================================
def test_ficha_pela_planilha_tem_as_perguntas_da_C79_em_ordem_e_sem_nan(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()

    msg, _ = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real))

    assert msg == "Fichas geradas: 1"
    assert _perguntas_da_ficha(saida / "4500063671.0071.xlsx", openpyxl_real) == [
        "1 - DIMENSOES (Indicar as dimensoes.):",
        "2 - MATERIAL (Indicar o material.):",
        "3 - PESO:",
    ]


def test_ficha_pela_planilha_tem_a_mesma_geometria_do_metodo_antigo(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()

    pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real))
    ws = openpyxl_real.load_workbook(saida / "4500063671.0071.xlsx")["Ficha Técnica Padrão"]

    mescladas = {str(r) for r in ws.merged_cells.ranges}
    assert {"C79:L79", "M79:V79", "C81:L81", "M81:V81"} <= mescladas
    assert ws["C79"].font.size == 8
    assert ws.row_dimensions[79].height == 32
    assert ws["M79"].value is None   # a resposta fica para o fornecedor


def test_pdm_recusado_vira_falha_e_o_lote_segue(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()
    logs = []

    msg, log = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0001", "PDM.9999.001 - NAO EXISTE, , R0", str(saida)),
         ("4500063671.0002", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real), log_callback=logs.append)
    texto = "\n".join(logs)

    assert msg == "Fichas geradas: 1"
    assert not (saida / "4500063671.0001.xlsx").exists()
    assert (saida / "4500063671.0002.xlsx").exists()
    assert "1 falha(s)" in texto
    assert "PDM.9999.001 nao esta na planilha de PDMs" in texto
    assert log == ["FALHA: 4500063671.0001: PDM.9999.001 nao esta na planilha de PDMs "
                   "(exportada em 23/09/2026 11:02:02)"]


def test_o_log_comeca_dizendo_a_planilha_e_a_data(tmp_path, openpyxl_real):
    logs = []

    pdm.aplicar_templates_fichas_da_planilha(
        [], _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real), log_callback=logs.append)

    assert logs[0] == ("Planilha de PDMs: PDMs_SAM-GM_23.09.26.xlsx, exportada em "
                       "23/09/2026 11:02:02: 1 PDM(s).")


def test_as_revisoes_diferentes_sao_listadas_no_fim_nos_dois_sentidos(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()
    logs = []

    msg, _ = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0001", "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R1", str(saida)),
         ("4500063671.0002", "PDM.1650.001 - ACUMULADOR, , R3", str(saida))],
        _catalogo(ACUMULADOR, DISJUNTOR), _template(tmp_path, openpyxl_real),
        log_callback=logs.append)
    texto = "\n".join(logs)
    fim = texto[texto.index("── Resumo:"):]

    assert msg == "Fichas geradas: 2 (2 com revisao diferente do portal)"
    assert "PDM precisa subir de revisao no portal (1):" in fim
    assert "4500063671.0001: PDM.5925.001 esta na R1 no portal e na R5 na planilha" in fim
    assert "Planilha atras do portal, exporte uma nova da Itaipu (1):" in fim
    assert "4500063671.0002: PDM.1650.001 esta na R3 no portal, mas a planilha so tem a R2" in fim


def test_planilha_sem_caracteristicas_para_antes_de_comecar(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()
    manipulado = CatalogoPDM(pdms=[PDM(codigo="PDM.1650.001", classe="1650", titulo="ACUMULADOR")])

    msg, log = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0001", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        manipulado, _template(tmp_path, openpyxl_real))

    assert "TEMPLATE_PDM" in msg
    assert log == [msg]
    assert os.listdir(saida) == []


# =============================================================================
# B. Método antigo: dois arquivos do mesmo PDM na pasta
# =============================================================================
def _pdm_formatado(caminho, openpyxl, pergunta):
    wb = openpyxl.Workbook()
    wb.active.cell(row=1, column=1, value=pergunta)
    wb.save(caminho)


def test_metodo_antigo_usa_o_arquivo_de_revisao_mais_alta(tmp_path, openpyxl_real):
    """A pasta EN traduzida antes e depois de uma regeneração fica com as duas
    versões do mesmo PDM. Antes, a escolha dependia da ordem do disco."""
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    _pdm_formatado(pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx", openpyxl_real, "1 - VELHA:")
    _pdm_formatado(pasta / "PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx", openpyxl_real, "1 - NOVA:")
    _pdm_formatado(pasta / "PDM_1650_001 - ACUMULADOR - R1_formatado.xlsx", openpyxl_real, "1 - MEIO:")
    saida = tmp_path / "fichas"
    saida.mkdir()
    logs = []

    pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1650.001 - ACUMULADOR", str(saida))],
        str(pasta), _template(tmp_path, openpyxl_real), log_callback=logs.append)

    assert _perguntas_da_ficha(saida / "4500063671.0071.xlsx", openpyxl_real) == ["1 - NOVA:"]
    assert "3 arquivos do PDM_1650_001 na pasta" in "\n".join(logs)


# =============================================================================
# C. Uma implementação por conceito
# =============================================================================
def _chama(funcao, nome):
    arvore = ast.parse(textwrap.dedent(inspect.getsource(funcao)))
    return any(isinstance(no, ast.Call) and getattr(no.func, "attr", getattr(no.func, "id", None)) == nome
               for no in ast.walk(arvore))


def test_o_passo_formatar_monta_a_pergunta_pela_mesma_regra():
    """O "(nan)" saía de `processar_arquivo_pdm`; a regra da pergunta é uma só."""
    assert _chama(pdm.processar_arquivo_pdm, "montar_pergunta")


def test_o_passo_formatar_usa_a_mesma_tabela_da_regeneracao():
    assert _chama(pdm.salvar_tabela_formatada, "formatar_tabela_de_perguntas")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_pdm_montagem_planilha.py -q`
Expected: FAIL (`AttributeError: module 'sigft.services.pdm' has no attribute 'aplicar_templates_fichas_da_planilha'`).

- [ ] **Step 3: Implementar em `sigft/services/pdm.py`**

(a) Imports, no topo (junto dos demais):

```python
from dataclasses import dataclass, field
```
e, depois de `from sigft.core.excel import locking`:
```python
from sigft.services import pdm_planilha
```

(b) Em `processar_arquivo_pdm`, trocar a construção de `'Descrição'` por:

```python
        # A pergunta sai pela regra única de `pdm_planilha.montar_pergunta`
        # (2026-09-24): era aqui que nascia o "(nan)" quando a Itaipu não
        # escrevia a ajuda -- o pandas lê a célula vazia como NaN.
        nova_tabela = pd.DataFrame({
            'Descrição': [pdm_planilha.montar_pergunta(i + 1, q, s)
                          for i, (q, s) in enumerate(zip(col_q, col_s))],
            'Resposta': ['' for _ in range(len(col_q))]
        })
```

(c) Extrair a geometria de `salvar_tabela_formatada`. Acrescentar antes dela:

```python
def formatar_tabela_de_perguntas(ws, linhas):
    """A geometria do PDM formatado, uma implementação só: descrição nas
    colunas 1 a 10 mescladas, resposta nas 11 a 20 mescladas, fonte 8, quebra
    de texto, altura 32, bordas finas. Usada pelo passo "Formatar" e pela
    regeneração da pasta (`services/pdm_regeneracao.py`).

    `linhas`: iterável de `(descricao, resposta)`, na ordem."""
    borda = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
    estilo = Alignment(wrap_text=True, vertical='top')
    fonte = Font(size=8)

    for i, (descricao, resposta) in enumerate(linhas, start=1):
        ws.row_dimensions[i].height = 32

        # Formatação Coluna 1 (Desc)
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=10)
        c1 = ws.cell(row=i, column=1, value=descricao)
        c1.alignment = estilo; c1.font = fonte
        for c in range(1, 11): ws.cell(row=i, column=c).border = borda

        # Formatação Coluna 2 (Resp)
        ws.merge_cells(start_row=i, start_column=11, end_row=i, end_column=20)
        c2 = ws.cell(row=i, column=11, value=resposta)
        c2.alignment = estilo; c2.font = fonte
        for c in range(11, 21): ws.cell(row=i, column=c).border = borda
```

e, em `salvar_tabela_formatada`, trocar as linhas de `borda = ...` até o fim do `for` por:

```python
        formatar_tabela_de_perguntas(
            ws, ((row[0], row[1]) for row in nova_tabela.itertuples(index=False)))
```

(d) Substituir a função `aplicar_templates_fichas` inteira (de `def aplicar_templates_fichas(` até o `return f"Fichas geradas: {count}", log`) por:

```python
# =============================================================================
# MONTAGEM DA FICHA: uma implementação, duas fontes de perguntas
# =============================================================================
# Desde 2026-09-24 a montagem (template da memória, aba resolvida uma vez,
# linha 79, mesclas, fonte 8, altura 32, bordas, salvar perguntando) é UMA só.
# O que varia é de onde vêm as perguntas de cada material: da pasta de PDMs
# Modificados (método antigo, `aplicar_templates_fichas`) ou da planilha de
# PDMs (`aplicar_templates_fichas_da_planilha`). Ver
# docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md.

class _Recusado(Exception):
    """A fonte não tem as perguntas deste material.

    `motivo` vai para o resumo do lote; `linha_de_log`, para a lista `log` que
    as funções públicas devolvem (no método antigo ela é contrato:
    `tests/test_pdm_relatorio_lote.py`)."""

    def __init__(self, motivo, linha_de_log):
        super().__init__(motivo)
        self.motivo = motivo
        self.linha_de_log = linha_de_log


@dataclass
class _Perguntas:
    # `[(descricao, resposta), ...]` na ordem da ficha, a partir da linha 79.
    # Entrada vazia PULA uma linha: é o que o PDM formatado faz hoje com linha
    # em branco, e o método antigo tem de continuar igual.
    linhas: list
    # Completa a linha de sucesso do lote: "(PDM.5925.001 R5, 51 perguntas)".
    detalhe: str = ""
    # `[(causa, consequencia), ...]` para `RelatorioLote.aviso`.
    avisos: list = field(default_factory=list)
    divergencia: str = ""
    causa_da_divergencia: str = ""


def _ler_template(path_template):
    # CP 4.3 (otimização de I/O): o template é lido do disco UMA única vez,
    # para memória; cada ficha reabre uma cópia limpa de `BytesIO`.
    with open(path_template, "rb") as arquivo_template:
        return arquivo_template.read()


def _escolher_arquivo(candidatos):
    """O de maior revisão no nome; sem revisão conta como a menor; empate fica
    com o primeiro, que é o que a escolha fazia antes de existir revisão no
    nome (2026-09-24)."""
    def revisao(caminho):
        numero = pdm_planilha.revisao_no_nome(caminho)
        return -1 if numero is None else numero

    melhor = candidatos[0]
    for caminho in candidatos[1:]:
        if revisao(caminho) > revisao(melhor):
            melhor = caminho
    return melhor


def _perguntas_da_pasta(pasta_pdms_modificados):
    """A fonte do método antigo: o PDM formatado da pasta."""
    # Cache dos arquivos de PDM para não listar disco toda hora
    pdms_disponiveis = listar_arquivos_excel(pasta_pdms_modificados)

    def obter(pmib, pdm_nome):
        id_pdm = pdm_nome.split(" - ")[0].replace(".", "_")
        candidatos = [f for f in pdms_disponiveis if id_pdm in os.path.basename(f)]
        if not candidatos:
            msg_falha = f"PDM fonte não encontrado para {pmib} ({id_pdm})"
            raise _Recusado(msg_falha, f"FALHA: {msg_falha}")

        src = _escolher_arquivo(candidatos)
        avisos = []
        if len(candidatos) > 1:
            avisos.append((f"{len(candidatos)} arquivos do {id_pdm} na pasta",
                           f"usei {os.path.basename(src)}, o de revisao mais alta no nome"))
        wb_pdm = load_workbook(src)
        try:
            ws_pdm = wb_pdm.active
            linhas = [(ws_pdm.cell(row=i, column=1).value, ws_pdm.cell(row=i, column=2).value)
                      for i in range(1, ws_pdm.max_row + 1)]
        finally:
            wb_pdm.close()
        return _Perguntas(linhas=linhas, avisos=avisos)

    return obter


def _escrever_perguntas(ws_target, linhas):
    # Lógica de cópia (Linha 79 fixo)
    start_row = 79
    borda = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
    align = Alignment(wrap_text=True, vertical='top')
    font8 = Font(size=8)

    for i, (v_desc, v_resp) in enumerate(linhas, start=1):
        if not v_desc and not v_resp: continue

        row_idx = start_row + i - 1

        # Merge e escrita
        ws_target.merge_cells(start_row=row_idx, start_column=3, end_row=row_idx, end_column=12)
        ws_target.merge_cells(start_row=row_idx, start_column=13, end_row=row_idx, end_column=22)

        c_d = ws_target.cell(row=row_idx, column=3, value=v_desc)
        c_r = ws_target.cell(row=row_idx, column=13, value=v_resp)

        c_d.font = font8; c_d.alignment = align
        c_r.font = font8; c_r.alignment = align

        # Bordas
        for c in range(3, 13): ws_target.cell(row=row_idx, column=c).border = borda
        for c in range(13, 23): ws_target.cell(row=row_idx, column=c).border = borda

        ws_target.row_dimensions[row_idx].height = 32


def _montar_fichas(lista_dados, obter_perguntas, bytes_template, *, callbacks,
                   retry_lock, idioma, titulo, contexto, log):
    """O laço de montagem. Devolve `(count, erro_de_template, divergencias)`,
    com `divergencias = [(pmib, divergencia, causa), ...]` das fichas GERADAS."""
    count = 0
    nome_da_aba = None
    erro_de_template = None
    divergencias = []
    em_ingles = str(idioma or "pt").strip().lower().startswith("en")
    # CP 4.4: `RelatorioLote` (início com total/contexto, linha por item,
    # resumo final com as falhas listadas).
    with RelatorioLote(callbacks, titulo=titulo, total=len(lista_dados),
                       contexto=contexto) as lote:
        for pmib, pdm_nome, pasta_destino in lista_dados:
            try:
                perguntas = obter_perguntas(pmib, pdm_nome)
                for causa, consequencia in perguntas.avisos:
                    lote.aviso(pmib, causa, consequencia)

                # CP 4.3: cópia limpa do template vinda da MEMÓRIA.
                wb_target = load_workbook(BytesIO(bytes_template))

                # A aba e resolvida UMA vez, na primeira ficha, reaproveitando
                # o workbook que seria lido de qualquer jeito. Template errado
                # e problema do TEMPLATE, nao de cada ficha: falhar 200 vezes
                # com a mesma mensagem generica esconde a causa em vez de
                # mostra-la, entao o lote PARA com o motivo.
                if nome_da_aba is None:
                    try:
                        nome_da_aba = nome_da_aba_da_ficha(wb_target)
                    except ValueError as e:
                        erro_de_template = f"Erro no template: {e}"
                        log.append(erro_de_template)
                        lote.falha(pmib, erro_de_template)
                        break
                ws_target = wb_target[nome_da_aba]

                # A aba da ficha ENTREGUE ao fornecedor estrangeiro tem de ter
                # nome em ingles (decisao de 2026-09-03). Renomear e seguro do
                # lado de quem LE de volta: `analyzer._aba_da_ficha` escolhe a
                # aba por EVIDENCIA, nao por nome. A comparacao normalizada
                # evita renomear para o nome de OUTRA aba do mesmo workbook.
                if em_ingles and _normalizar_nome_de_aba(ws_target.title) != _ALVO_EN:
                    if not any(_normalizar_nome_de_aba(outra.title) == _ALVO_EN
                               for outra in wb_target.worksheets):
                        ws_target.title = NOME_DA_ABA_EM_INGLES

                _escrever_perguntas(ws_target, perguntas.linhas)

                out_file = os.path.join(pasta_destino, f"{pmib}.xlsx")
                locking.salvar_perguntando(wb_target, out_file, retry_lock=retry_lock)
                wb_target.close()
                count += 1
                linha_de_sucesso = f"ficha gerada: {os.path.basename(out_file)}"
                if perguntas.detalhe:
                    linha_de_sucesso += f" {perguntas.detalhe}"
                lote.sucesso(pmib, linha_de_sucesso)
                if perguntas.divergencia:
                    divergencias.append((pmib, perguntas.divergencia,
                                         perguntas.causa_da_divergencia))

            except _Recusado as e:
                log.append(e.linha_de_log)
                lote.falha(pmib, e.motivo)
            except Exception as e:
                msg_erro = f"ERRO ao gerar ficha {pmib}: {e}"
                log.append(msg_erro)
                lote.falha(pmib, f"{type(e).__name__}: {e}")

    return count, erro_de_template, divergencias


def aplicar_templates_fichas(lista_dados, pasta_pdms_modificados, path_template,
                             log_callback=None, retry_lock=None, idioma="pt"):
    """Método antigo: as perguntas vêm da pasta de PDMs Modificados.

    Assinatura, mensagens e retorno são os de sempre; a única mudança
    (2026-09-24) é que, com dois arquivos do mesmo PDM na pasta, vence o de
    revisão mais alta no nome, com aviso no log."""
    # CP 4.4: `callbacks` é local, a assinatura pública não muda.
    callbacks = from_legacy(callback_log=log_callback)
    log = []
    obter = _perguntas_da_pasta(pasta_pdms_modificados)
    try:
        bytes_template = _ler_template(path_template)
    except Exception as e:
        return f"Erro ao abrir template: {e}", [f"Erro ao abrir template: {e}"]

    count, erro_de_template, _ = _montar_fichas(
        lista_dados, obter, bytes_template, callbacks=callbacks,
        retry_lock=retry_lock, idioma=idioma,
        titulo="Aplicando templates de PDM nas fichas técnicas",
        contexto={"pasta_pdms_modificados": pasta_pdms_modificados, "template": path_template},
        log=log,
    )
    if erro_de_template:
        return erro_de_template, log
    return f"Fichas geradas: {count}", log


# As duas listas do fim do lote pela planilha (regras 4 e 5 do spec).
_TITULOS_DAS_DIVERGENCIAS = (
    (pdm_planilha.PORTAL_ATRAS, "PDM precisa subir de revisao no portal"),
    (pdm_planilha.PLANILHA_ATRAS, "Planilha atras do portal, exporte uma nova da Itaipu"),
)


def _listar_divergencias(callbacks, divergencias):
    """O `RelatorioLote` conta os avisos mas não os lista, e estas duas listas
    SÃO o que o usuário faz depois: subir revisão no portal, ou pedir planilha
    nova."""
    for tipo, titulo in _TITULOS_DAS_DIVERGENCIAS:
        do_tipo = [(pmib, causa) for pmib, qual, causa in divergencias if qual == tipo]
        if do_tipo:
            callbacks.log(f"{titulo} ({len(do_tipo)}):", nivel="warn")
            for pmib, causa in do_tipo:
                callbacks.log(f"   {pmib}: {causa}", nivel="warn")


def aplicar_templates_fichas_da_planilha(lista_dados, catalogo, path_template,
                                         log_callback=None, retry_lock=None):
    """As perguntas vêm da PLANILHA de PDMs (`catalogo`, de
    `pdm_catalogo.carregar`): revisão vigente, ordem da SECUENCIA, sem
    "(nan)". Sempre em português: a ficha em inglês usa a pasta traduzida
    (decisão do usuário, 2026-09-23). Regras em `services/pdm_planilha.py`."""
    callbacks = from_legacy(callback_log=log_callback)
    log = []
    try:
        pdm_planilha.conferir_catalogo(catalogo)
    except pdm_planilha.PDMRecusado as e:
        callbacks.log(str(e), nivel="error")
        return str(e), [str(e)]
    callbacks.log(pdm_planilha.descrever_catalogo(catalogo), nivel="info")
    try:
        bytes_template = _ler_template(path_template)
    except Exception as e:
        return f"Erro ao abrir template: {e}", [f"Erro ao abrir template: {e}"]

    def obter(pmib, pdm_nome):
        try:
            resultado = pdm_planilha.perguntas_do_pdm(catalogo, pdm_nome)
        except pdm_planilha.PDMRecusado as e:
            raise _Recusado(str(e), f"FALHA: {pmib}: {e}") from e
        pdm_do_item = resultado.pdm
        return _Perguntas(
            linhas=[(texto, None) for texto in resultado.linhas],
            detalhe=(f"({pdm_do_item.codigo} R{pdm_do_item.revisao}, "
                     f"{len(resultado.linhas)} perguntas)"),
            avisos=([(resultado.causa, resultado.consequencia)]
                    if resultado.divergencia else []),
            divergencia=resultado.divergencia,
            causa_da_divergencia=resultado.causa,
        )

    count, erro_de_template, divergencias = _montar_fichas(
        lista_dados, obter, bytes_template, callbacks=callbacks,
        retry_lock=retry_lock, idioma="pt",
        titulo="Montando fichas a partir da planilha de PDMs",
        contexto={"planilha": catalogo.origem, "template": path_template},
        log=log,
    )
    _listar_divergencias(callbacks, divergencias)
    if erro_de_template:
        return erro_de_template, log
    mensagem = f"Fichas geradas: {count}"
    if divergencias:
        mensagem += f" ({len(divergencias)} com revisao diferente do portal)"
    return mensagem, log
```

- [ ] **Step 4: Rodar os testes novos e os antigos do módulo**

Run: `python -m pytest tests/test_pdm_montagem_planilha.py tests/test_pdm_io.py tests/test_pdm_montador_idioma.py tests/test_pdm_relatorio_lote.py tests/test_traducao_pdm.py -q`
Expected: todos PASS; os quatro arquivos antigos **sem nenhuma alteração**.

- [ ] **Step 5: Portão e commit**

```bash
bash scripts/check.sh && python -m ruff check . && \
git add sigft/services/pdm.py tests/test_pdm_montagem_planilha.py && \
git commit -m "Modulo 2: ficha montada direto da planilha de PDMs, com a montagem ainda unica" \
  -m "A montagem ganha a fonte de perguntas injetada: pasta (metodo antigo, mesmas mensagens) ou planilha. No metodo antigo, com duas versoes do mesmo PDM na pasta, vence a de revisao mais alta no nome. O passo Formatar deixa de gerar (nan)." \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019RQRqXdewwcJEzdHB4k7k9" && \
git push -u origin claude/practical-einstein-16tqfl
```

---

### Task 4: Regenerar as duas pastas (`services/pdm_regeneracao.py`)

**Files:**
- Create: `sigft/services/pdm_regeneracao.py`
- Test: `tests/test_pdm_regeneracao.py`

**Interfaces:**
- Consumes: `pdm_catalogo.carregar`; `pdm_planilha.conferir_catalogo`, `descrever_catalogo`, `outras_identidades`, `descrever_identidades`, `montar_pergunta`, `nome_de_arquivo`, `revisao_no_nome`; `pdm.formatar_tabela_de_perguntas`, `pdm.extrair_pdm_id`; `locking.salvar_perguntando`.
- Produces: `pdm_regeneracao.regenerar_pastas(caminho_planilha, pasta_modificados, pasta_from_itaipu=None, log_callback=None, retry_lock=None) -> str` (levanta `ValueError` para entrada inválida); `PASTA_VERSOES_ANTIGAS = "_versoes_antigas"`.

- [ ] **Step 1: Escrever os testes**

`tests/test_pdm_regeneracao.py`:

```python
r"""Regenerar as pastas From Itaipu e Modificados a partir da planilha, com a
revisão no nome (`services/pdm_regeneracao.py`). Com openpyxl REAL."""
from __future__ import annotations

import os

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade
from sigft.services import pdm, pdm_regeneracao


@pytest.fixture
def openpyxl_real():
    with openpyxl_de_verdade(pdm) as modulo:
        yield modulo


def _linha_mestra(codigo, revisao, caract, *, seq, ajuda=None, titulo, base, modif=""):
    """Uma linha da aba TEMPLATE_PDM, nas colunas REAIS (A=0 ... X=23)."""
    linha = [None] * 24
    linha[0], linha[1] = codigo, codigo.split(".")[1]
    linha[2] = linha[3] = titulo
    linha[4] = linha[5] = base
    linha[6] = linha[7] = modif
    linha[9], linha[13], linha[16], linha[18] = revisao, seq, caract, ajuda
    return linha


def _escrever_mestra(caminho, dados):
    """O layout REAL da planilha de 23/09/2026: título mesclado A1:X1, data da
    exportação em A2/B2, A5:X5 mesclado, cabeçalho na 6, painel congelado em
    A6, autofiltro, largura e altura próprias."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TEMPLATE_PDM"
    ws["A1"] = "TEMPLATE PARA LA IMPORTACIÓN/EXPORTACIÓN DE PDM"
    ws.merge_cells("A1:X1")
    ws["A2"], ws["B2"] = "Exportado el:", "23/09/2026 11:02:02"
    ws["A5"] = "PDM - PADRÓN DESCRIPTIVO DE MATERIALES"
    ws.merge_cells("A5:X5")
    ws["A6"] = "CÓDIGO PDM"
    ws["A6"].font = Font(bold=True)
    ws["A6"].fill = PatternFill("solid", fgColor="FFFF00")
    ws.row_dimensions[1].height = 87
    ws.column_dimensions["A"].width = 17
    ws.freeze_panes = "A6"
    for linha in dados:
        ws.append(linha)
        ws.cell(row=ws.max_row, column=17).font = Font(color="FF0000")
    ws.auto_filter.ref = f"A6:X{ws.max_row}"
    wb.save(caminho)


ACUMULADOR = dict(titulo="ACUMULADOR", base="ACUMULADOR")
EXTENSAO = dict(titulo="EXTENSAO/TRONCO TORRE", base="EXTENSAO", modif="TRONCO TORRE")


@pytest.fixture
def mestra(tmp_path, openpyxl_real):
    caminho = str(tmp_path / "PDMs_SAM-GM.xlsx")
    _escrever_mestra(caminho, [
        _linha_mestra("PDM.1650.001", "2", "DIMENSOES", seq="1", ajuda="Indicar as dimensoes.", **ACUMULADOR),
        _linha_mestra("PDM.1650.001", "2", "PESO", seq="3", **ACUMULADOR),
        _linha_mestra("PDM.1650.001", "2", "MATERIAL", seq="2", ajuda="Indicar o material.", **ACUMULADOR),
        _linha_mestra("PDM.5445.007", "1", "ALTURA", seq="1", ajuda="Indicar a altura.", **EXTENSAO),
    ])
    return caminho


NOVO_ACUMULADOR = "PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx"


# =============================================================================
# A. Pasta Modificados
# =============================================================================
def test_regenera_a_modificados_com_a_revisao_no_nome(mestra, tmp_path):
    pasta = tmp_path / "modificados"

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    assert sorted(os.listdir(pasta)) == [
        NOVO_ACUMULADOR, "PDM_5445_007 - EXTENSAO-TRONCO TORRE - R1_formatado.xlsx"]


def test_o_pdm_formatado_segue_a_secuencia_e_nao_tem_nan(mestra, tmp_path, openpyxl_real):
    pasta = tmp_path / "modificados"

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))
    ws = openpyxl_real.load_workbook(pasta / NOVO_ACUMULADOR).active

    assert [ws.cell(row=i, column=1).value for i in (1, 2, 3)] == [
        "1 - DIMENSOES (Indicar as dimensoes.):",
        "2 - MATERIAL (Indicar o material.):",
        "3 - PESO:",
    ]
    assert {"A1:J1", "K1:T1"} <= {str(r) for r in ws.merged_cells.ranges}
    assert ws["A1"].font.size == 8
    assert ws.row_dimensions[1].height == 32


def test_a_versao_antiga_vai_para_versoes_antigas_sem_ser_apagada(mestra, tmp_path):
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    (pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").write_bytes(b"velho")

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    guardado = pasta / "_versoes_antigas" / "PDM_1650_001 - ACUMULADOR_formatado.xlsx"
    assert guardado.read_bytes() == b"velho"
    assert not (pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").exists()
    assert (pasta / NOVO_ACUMULADOR).exists()


def test_nome_repetido_em_versoes_antigas_ganha_numero(mestra, tmp_path):
    pasta = tmp_path / "modificados"
    (pasta / "_versoes_antigas").mkdir(parents=True)
    (pasta / "_versoes_antigas" / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").write_bytes(b"primeiro")
    (pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").write_bytes(b"segundo")

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    assert (pasta / "_versoes_antigas" / "PDM_1650_001 - ACUMULADOR_formatado.xlsx").read_bytes() == b"primeiro"
    assert (pasta / "_versoes_antigas" / "PDM_1650_001 - ACUMULADOR_formatado (2).xlsx").read_bytes() == b"segundo"


def test_arquivo_ja_na_revisao_atual_nao_e_regravado(mestra, tmp_path):
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    (pasta / NOVO_ACUMULADOR).write_bytes(b"sentinela")
    logs = []

    resumo = pdm_regeneracao.regenerar_pastas(mestra, str(pasta), log_callback=logs.append)

    assert (pasta / NOVO_ACUMULADOR).read_bytes() == b"sentinela"
    assert "ja em dia (R2)" in "\n".join(logs)
    assert "1 novo(s), 0 atualizado(s), 1 ja em dia, 0 falha(s)" in resumo


def test_ja_em_dia_ainda_move_a_versao_antiga_que_sobrou(mestra, tmp_path):
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    (pasta / NOVO_ACUMULADOR).write_bytes(b"sentinela")
    (pasta / "PDM_1650_001 - ACUMULADOR - R1_formatado.xlsx").write_bytes(b"r1")

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    assert (pasta / NOVO_ACUMULADOR).read_bytes() == b"sentinela"
    assert (pasta / "_versoes_antigas" / "PDM_1650_001 - ACUMULADOR - R1_formatado.xlsx").exists()


def test_nao_mexe_no_arquivo_do_outro_tipo_na_mesma_pasta(mestra, tmp_path):
    """Na Modificados, só o que tem `_formatado` é versão antiga."""
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    (pasta / "PDM_1650_001 - ACUMULADOR.xlsx").write_bytes(b"outro tipo")

    pdm_regeneracao.regenerar_pastas(mestra, str(pasta))

    assert (pasta / "PDM_1650_001 - ACUMULADOR.xlsx").read_bytes() == b"outro tipo"


def test_desistir_do_arquivo_aberto_nao_grava_o_novo(mestra, tmp_path, monkeypatch):
    """Arquivo aberto no Excel: a janela "feche e tente de novo" aparece
    (`retry_lock`). Se o usuário desistir, a pasta NÃO fica com duas versões."""
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    antigo = pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx"
    antigo.write_bytes(b"aberto no Excel")

    def move_travado(origem, destino):
        raise PermissionError("[WinError 32] arquivo em uso")

    monkeypatch.setattr(pdm_regeneracao.shutil, "move", move_travado)
    perguntados = []

    def retry_lock(caminho):
        perguntados.append(caminho)
        return False

    resumo = pdm_regeneracao.regenerar_pastas(mestra, str(pasta), retry_lock=retry_lock)

    assert perguntados == [str(antigo)]
    assert antigo.read_bytes() == b"aberto no Excel"
    assert not (pasta / NOVO_ACUMULADOR).exists()
    assert "1 falha(s)" in resumo


def test_codigo_duplicado_avisa_quem_ficou_de_fora(tmp_path, openpyxl_real):
    caminho = str(tmp_path / "PDMs.xlsx")
    _escrever_mestra(caminho, [
        _linha_mestra("PDM.3010.007", "1", "NORMAS TECNICAS APLICAVEIS", seq="7",
                      titulo="ACOPLAMENTO ROSCADO", base="ACOPLAMENTO", modif="ROSCADO"),
        _linha_mestra("PDM.3010.007", "0", "COMPRIMENTO TOTAL", seq="2",
                      titulo="FIXADOR", base="FIXADOR"),
    ])
    pasta = tmp_path / "modificados"
    logs = []

    pdm_regeneracao.regenerar_pastas(caminho, str(pasta), log_callback=logs.append)
    ws = openpyxl_real.load_workbook(
        pasta / "PDM_3010_007 - ACOPLAMENTO ROSCADO - R1_formatado.xlsx").active

    assert "a planilha traz tambem FIXADOR (R0)" in "\n".join(logs)
    assert ws.cell(row=1, column=1).value == "1 - NORMAS TECNICAS APLICAVEIS:"
    assert ws.cell(row=2, column=1).value is None


# =============================================================================
# B. Pasta From Itaipu (o fatiador que lê a planilha UMA vez)
# =============================================================================
def test_regenera_a_from_itaipu_com_a_revisao_no_nome(mestra, tmp_path):
    pasta = tmp_path / "from_itaipu"

    pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"), str(pasta))

    assert sorted(os.listdir(pasta)) == [
        "PDM_1650_001 - ACUMULADOR - R2.xlsx", "PDM_5445_007 - EXTENSAO-TRONCO TORRE - R1.xlsx"]


def test_a_fatia_tem_o_cabecalho_e_as_linhas_na_ordem_da_secuencia(mestra, tmp_path, openpyxl_real):
    pasta = tmp_path / "from_itaipu"

    pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"), str(pasta))
    wb = openpyxl_real.load_workbook(pasta / "PDM_1650_001 - ACUMULADOR - R2.xlsx")
    ws = wb["TEMPLATE_PDM"]

    assert wb.sheetnames == ["TEMPLATE_PDM"]
    assert ws["A1"].value == "TEMPLATE PARA LA IMPORTACIÓN/EXPORTACIÓN DE PDM"
    assert ws["B2"].value == "23/09/2026 11:02:02"
    assert [ws.cell(row=r, column=17).value for r in (7, 8, 9)] == ["DIMENSOES", "MATERIAL", "PESO"]
    assert ws.max_row == 9


def test_a_fatia_copia_a_formatacao_da_planilha(mestra, tmp_path, openpyxl_real):
    pasta = tmp_path / "from_itaipu"

    pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"), str(pasta))
    ws = openpyxl_real.load_workbook(pasta / "PDM_1650_001 - ACUMULADOR - R2.xlsx")["TEMPLATE_PDM"]

    assert {"A1:X1", "A5:X5"} <= {str(r) for r in ws.merged_cells.ranges}
    assert ws.freeze_panes == "A6"
    assert ws.auto_filter.ref == "A6:X9"
    assert ws.column_dimensions["A"].width == 17
    assert ws.row_dimensions[1].height == 87
    assert ws["A6"].font.bold is True
    assert ws["A6"].fill.fgColor.rgb == "00FFFF00"
    assert ws.cell(row=7, column=17).font.color.rgb == "00FF0000"


# =============================================================================
# C. Entrada que não serve: recusa ANTES de tocar em arquivo
# =============================================================================
def test_as_duas_pastas_iguais_sao_recusadas(mestra, tmp_path):
    pasta = tmp_path / "mesma"

    with pytest.raises(ValueError, match="nao podem ser a mesma"):
        pdm_regeneracao.regenerar_pastas(mestra, str(pasta), str(pasta))

    assert not pasta.exists()


def test_sem_pasta_modificados_e_recusado(mestra):
    with pytest.raises(ValueError, match="Pasta dos PDMs Modificados"):
        pdm_regeneracao.regenerar_pastas(mestra, "")


def test_sem_pasta_from_itaipu_so_a_modificados_e_regenerada(mestra, tmp_path):
    resumo = pdm_regeneracao.regenerar_pastas(mestra, str(tmp_path / "modificados"))

    assert "PDMs From Itaipu: pasta nao informada, nao foi regenerada." in resumo


def test_planilha_no_formato_antigo_e_recusada(tmp_path, openpyxl_real):
    caminho = str(tmp_path / "manipulada.xlsx")
    wb = openpyxl_real.Workbook()
    wb.active.title = "PDMs"
    wb.active.append(["PDM COMPLETO"])
    wb.active.append(["PDM.4820.004 - VALVULA ESFERA"])
    wb.save(caminho)

    with pytest.raises(ValueError, match="TEMPLATE_PDM"):
        pdm_regeneracao.regenerar_pastas(caminho, str(tmp_path / "modificados"))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_pdm_regeneracao.py -q`
Expected: FAIL (`ImportError: cannot import name 'pdm_regeneracao'`).

- [ ] **Step 3: Implementar `sigft/services/pdm_regeneracao.py`**

```python
r"""Regenerar as pastas de PDMs a partir da planilha, com a revisão no nome.

Pedido do usuário em 2026-09-23 (D5 do spec): as pastas *PDMs From Itaipu* e
*PDMs Modificados* nasciam dos passos antigos "Fatiar" e "Formatar", que PULAM
o que já existe: revisado um PDM, o arquivo velho ficava. Este módulo refaz as
duas a partir da planilha, com a revisão do PDM no nome
(`PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx`), e manda a versão antiga de
cada PDM para a subpasta `_versoes_antigas`: nada é apagado.

A pasta From Itaipu é fatiada lendo a planilha UMA vez. O "Fatiar" antigo relê
a planilha inteira a cada código (7,1 s cada na planilha de 23/09/2026, umas
2,4 horas para os 1.199), porque cada volta mutila o workbook que abriu: é a
otimização que o CP 4.3 deixou registrada em PENDENCIAS.md.

Desenho: seção 6 de
docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md.
"""
from __future__ import annotations

import os
import re
import shutil
from copy import copy
from types import SimpleNamespace

from sigft.core import pdm_catalogo
from sigft.core.callbacks import from_legacy
from sigft.core.excel import locking
from sigft.core.relatorio_lote import RelatorioLote
from sigft.services import pdm, pdm_planilha

PASTA_VERSOES_ANTIGAS = "_versoes_antigas"
SUFIXO_FORMATADO = "_formatado"

# As linhas 1 a 6 da aba TEMPLATE_PDM: título, "Exportado el:", o cabeçalho de
# layout e o cabeçalho de verdade (linha 6). Os dados começam na 7.
_LINHAS_DO_CABECALHO = 6

_EXTENSOES = (".xlsx", ".xlsm", ".xls")

# "A6:X21323" -> "A6:X" + a última linha da fatia.
_RE_FIM_DO_INTERVALO = re.compile(r"^([A-Z]+\d+:[A-Z]+)\d+$")


def regenerar_pastas(caminho_planilha, pasta_modificados, pasta_from_itaipu=None,
                     log_callback=None, retry_lock=None):
    """Regenera a pasta Modificados e, se informada, a From Itaipu.

    Levanta `ValueError` ANTES de tocar em qualquer arquivo quando a entrada
    não serve: pasta faltando, as duas pastas iguais, planilha ilegível ou no
    formato antigo. Devolve o resumo, uma linha por pasta."""
    if not pasta_modificados:
        raise ValueError("Selecione a 'Pasta dos PDMs Modificados'.")
    if pasta_from_itaipu and _mesma_pasta(pasta_modificados, pasta_from_itaipu):
        raise ValueError(
            "A 'Pasta (PDMs From Itaipu)' e a 'Pasta dos PDMs Modificados' nao "
            "podem ser a mesma: a busca de versoes antigas moveria os arquivos de "
            "uma para a outra."
        )
    try:
        catalogo = pdm_catalogo.carregar(caminho_planilha)
        pdm_planilha.conferir_catalogo(catalogo)
    except Exception as e:
        raise ValueError(f"Nao consegui usar a planilha de PDMs: {e}") from e

    callbacks = from_legacy(callback_log=log_callback)
    callbacks.log(pdm_planilha.descrever_catalogo(catalogo), nivel="info")
    pdms = sorted(catalogo.pdms, key=lambda p: p.codigo)

    resumo = [_regenerar_pasta(
        pasta_modificados, pdms, SUFIXO_FORMATADO, "PDMs Modificados",
        lambda p, caminho: _gravar_formatado(p, caminho, retry_lock),
        callbacks, retry_lock, avisar_identidades=True,
    )]
    if not pasta_from_itaipu:
        resumo.append("PDMs From Itaipu: pasta nao informada, nao foi regenerada.")
        return "\n".join(resumo)

    from openpyxl import load_workbook

    callbacks.log("Lendo a planilha com a formatacao, para a pasta From Itaipu...", nivel="info")
    wb_mestra = load_workbook(caminho_planilha)
    try:
        ws_mestra = wb_mestra["TEMPLATE_PDM"]
        resumo.append(_regenerar_pasta(
            pasta_from_itaipu, pdms, "", "PDMs From Itaipu",
            lambda p, caminho: _gravar_fatia(p, caminho, ws_mestra, retry_lock),
            callbacks, retry_lock, avisar_identidades=False,
        ))
    finally:
        wb_mestra.close()
    return "\n".join(resumo)


def _mesma_pasta(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _regenerar_pasta(pasta, pdms, sufixo, rotulo, gravar, callbacks, retry_lock, *,
                     avisar_identidades):
    os.makedirs(pasta, exist_ok=True)
    indice = _indexar(pasta, formatado=bool(sufixo))
    novos = atualizados = em_dia = 0
    with RelatorioLote(callbacks, titulo=f"Regenerando {rotulo} a partir da planilha",
                       total=len(pdms), contexto={"pasta": pasta}) as lote:
        for p in pdms:
            if not p.caracteristicas_em_ordem:
                lote.pulado(p.codigo, "sem caracteristica na planilha")
                continue
            if avisar_identidades:
                outras = pdm_planilha.outras_identidades(p)
                if outras:
                    lote.aviso(p.codigo,
                               f"a planilha traz tambem {pdm_planilha.descrever_identidades(outras)}",
                               f"ficou de fora, valeu {p.titulo} (R{p.revisao}); confira com a Itaipu")
            nome_novo = pdm_planilha.nome_de_arquivo(p, sufixo=sufixo)
            id_pdm = p.codigo.replace(".", "_")
            existentes = indice.get(id_pdm, [])
            antigos = [n for n in existentes if n != nome_novo]
            try:
                for nome in antigos:
                    _mover_para_versoes_antigas(pasta, nome, retry_lock)
                if nome_novo in existentes:
                    indice[id_pdm] = [nome_novo]
                    if antigos:
                        atualizados += 1
                        lote.sucesso(p.codigo, f"ja estava na R{p.revisao}; "
                                               f"{len(antigos)} versao(oes) antiga(s) movida(s)")
                    else:
                        em_dia += 1
                        lote.sucesso(p.codigo, f"ja em dia (R{p.revisao})")
                    continue
                gravar(p, os.path.join(pasta, nome_novo))
                indice[id_pdm] = [nome_novo]
                if antigos:
                    atualizados += 1
                    lote.sucesso(p.codigo, f"atualizado: {_de_onde(antigos)} -> R{p.revisao}")
                else:
                    novos += 1
                    lote.sucesso(p.codigo, f"novo: {nome_novo}")
            except Exception as e:
                lote.falha(p.codigo, f"{type(e).__name__}: {e}")
    return (f"{rotulo}: {novos} novo(s), {atualizados} atualizado(s), {em_dia} ja em dia, "
            f"{len(lote.falhas)} falha(s). Versoes antigas em "
            f"{os.path.join(pasta, PASTA_VERSOES_ANTIGAS)}")


def _indexar(pasta, *, formatado):
    """`{"PDM_1650_001": [nomes...]}` dos arquivos DESTE tipo na pasta: com
    `_formatado` na Modificados, sem ele na From Itaipu. Uma listagem por
    pasta, e não uma por PDM: a pasta mora no Box, e 1.199 listagens
    custariam caro."""
    indice = {}
    for nome in sorted(os.listdir(pasta)):
        if nome.startswith("~$") or not nome.lower().endswith(_EXTENSOES):
            continue
        if not os.path.isfile(os.path.join(pasta, nome)):
            continue
        if (SUFIXO_FORMATADO in nome) != formatado:
            continue
        id_pdm = pdm.extrair_pdm_id(nome)
        if id_pdm:
            indice.setdefault(id_pdm, []).append(nome)
    return indice


def _de_onde(nomes):
    """`"R1"`, `"sem revisao no nome"`, ou os dois: o que foi substituído."""
    revisoes = sorted({pdm_planilha.revisao_no_nome(n) for n in nomes},
                      key=lambda r: -1 if r is None else r)
    return ", ".join("sem revisao no nome" if r is None else f"R{r}" for r in revisoes)


def _mover_para_versoes_antigas(pasta, nome, retry_lock):
    """Move `nome` para `<pasta>/_versoes_antigas`, sem sobrescrever nada lá.

    Usa o canal `retry_lock` do `locking` (o `save_with_retry` só precisa de
    um objeto com `.save(caminho)`): arquivo aberto no Excel faz a janela
    "feche e tente de novo" aparecer, como em qualquer gravação do app. Se o
    usuário desistir, o `PermissionError` sobe e o PDM vira falha SEM o
    arquivo novo: a pasta não fica com duas versões."""
    origem = os.path.join(pasta, nome)
    destino_dir = os.path.join(pasta, PASTA_VERSOES_ANTIGAS)
    os.makedirs(destino_dir, exist_ok=True)
    destino = _nome_livre(os.path.join(destino_dir, nome))
    movedor = SimpleNamespace(save=lambda _caminho: shutil.move(origem, destino))
    locking.salvar_perguntando(movedor, origem, retry_lock=retry_lock)


def _nome_livre(caminho):
    """`caminho`, ou `caminho` com " (2)", " (3)"... antes da extensão."""
    if not os.path.exists(caminho):
        return caminho
    raiz, extensao = os.path.splitext(caminho)
    numero = 2
    while os.path.exists(f"{raiz} ({numero}){extensao}"):
        numero += 1
    return f"{raiz} ({numero}){extensao}"


def _gravar_formatado(p, caminho, retry_lock):
    """O PDM formatado: a mesma tabela do passo "Formatar"
    (`pdm.formatar_tabela_de_perguntas`), com as perguntas da planilha."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    # O nome que o `to_excel` do pandas dava à aba no passo antigo. Ninguém lê
    # a aba pelo nome (é sempre `wb.active`); o arquivo só fica igual ao de
    # sempre.
    ws.title = "Sheet1"
    linhas = [(pdm_planilha.montar_pergunta(numero, c.nome, c.ajuda), "")
              for numero, c in enumerate(p.caracteristicas_em_ordem, start=1)]
    pdm.formatar_tabela_de_perguntas(ws, linhas)
    locking.salvar_perguntando(wb, caminho, retry_lock=retry_lock)
    wb.close()


def _gravar_fatia(p, caminho, ws_mestra, retry_lock):
    """O PDM no formato da planilha (aba TEMPLATE_PDM): as 6 linhas do
    cabeçalho e as da revisão vigente, na ordem da SECUENCIA. É a mesma ordem
    das perguntas, para o passo antigo "Formatar" sobre este arquivo dar o
    mesmo PDM formatado que a regeneração grava."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "TEMPLATE_PDM"
    origens = (list(range(1, _LINHAS_DO_CABECALHO + 1))
               + [c.linha for c in p.caracteristicas_em_ordem])
    for destino, origem in enumerate(origens, start=1):
        _copiar_linha(ws_mestra, origem, ws, destino)
    _copiar_formato_da_aba(ws_mestra, ws, ultima_linha=len(origens))
    locking.salvar_perguntando(wb, caminho, retry_lock=retry_lock)
    wb.close()


def _copiar_linha(ws_origem, linha_origem, ws_destino, linha_destino):
    # A mesma cópia de estilo do "Fatiar" antigo (`pdm.pdms_fromItaipu_lista_geral`).
    for celula in ws_origem[linha_origem]:
        if celula.value is None and not celula.has_style:
            continue
        nova = ws_destino.cell(row=linha_destino, column=celula.column, value=celula.value)
        if celula.has_style:
            nova.font = copy(celula.font)
            nova.border = copy(celula.border)
            nova.fill = copy(celula.fill)
            nova.number_format = copy(celula.number_format)
            nova.alignment = copy(celula.alignment)
    altura = ws_origem.row_dimensions[linha_origem].height
    if altura is not None:
        ws_destino.row_dimensions[linha_destino].height = altura


def _copiar_formato_da_aba(ws_origem, ws_destino, *, ultima_linha):
    for letra, dimensao in ws_origem.column_dimensions.items():
        if dimensao.width:
            ws_destino.column_dimensions[letra].width = dimensao.width
    # `merge_cells` depois das células escritas: comparado com o "Fatiar"
    # antigo no cabeçalho real (2026-09-24), 0 célula diferente.
    for intervalo in ws_origem.merged_cells.ranges:
        if intervalo.max_row <= _LINHAS_DO_CABECALHO:
            ws_destino.merge_cells(intervalo.coord)
    if ws_origem.freeze_panes:
        ws_destino.freeze_panes = ws_origem.freeze_panes
    filtro = _RE_FIM_DO_INTERVALO.match(ws_origem.auto_filter.ref or "")
    if filtro:
        ws_destino.auto_filter.ref = f"{filtro.group(1)}{ultima_linha}"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_pdm_regeneracao.py -q`
Expected: todos PASS.

- [ ] **Step 5: Portão e commit**

```bash
bash scripts/check.sh && python -m ruff check . && \
git add sigft/services/pdm_regeneracao.py tests/test_pdm_regeneracao.py && \
git commit -m "Modulo 2: regenerar as pastas From Itaipu e Modificados pela planilha, com a revisao no nome" \
  -m "A versao antiga de cada PDM vai para _versoes_antigas (nada e apagado), arquivo aberto no Excel pergunta pelo retry_lock, e o fatiador le a planilha uma vez so em vez de uma vez por codigo." \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019RQRqXdewwcJEzdHB4k7k9" && \
git push -u origin claude/practical-einstein-16tqfl
```

---

### Task 5: A tela (`sigft/app/views/pdm.py`)

**Files:**
- Modify: `sigft/app/views/pdm.py`
- Test: `tests/test_pdm_tela_planilha.py`

**Interfaces:**
- Consumes: `backends.pdm_backend.aplicar_templates_fichas_da_planilha` (Task 3), `backends.pdm_backend.aplicar_templates_fichas` (inalterada), `pdm_regeneracao.regenerar_pastas` (Task 4), `pdm_catalogo.carregar` (Task 1).
- Produces: `ModuloPDM.fonte_perguntas` (`StringVar`, `"planilha"`/`"pasta"`), `ModuloPDM._op1_regenerar()`.

- [ ] **Step 1: Escrever os testes (AST)**

`tests/test_pdm_tela_planilha.py`:

```python
r"""A tela do módulo 2 com a fonte "planilha de PDMs" e a regeneração das pastas.

Por AST: `views/pdm.py` importa customtkinter e exige um root Tk (o mesmo
recurso de `test_pdm_montador_idioma.py`)."""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

VIEW = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app" / "views" / "pdm.py"


def _arvore():
    return ast.parse(VIEW.read_text(encoding="utf-8"))


def _metodo(nome):
    for no in ast.walk(_arvore()):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloPDM":
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == nome:
                    return item
    pytest.fail(f"metodo {nome} nao existe na tela do PDM")


def _chamadas(raiz, nome_funcao):
    return [no for no in ast.walk(raiz) if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute) and no.func.attr == nome_funcao]


def _textos(raiz):
    return [no.value for no in ast.walk(raiz)
            if isinstance(no, ast.Constant) and isinstance(no.value, str)]


def test_a_fonte_padrao_das_perguntas_e_a_planilha():
    init = _metodo("__init__")
    assert "fonte_perguntas" in ast.dump(init)
    assert any(k.arg == "value" and getattr(k.value, "value", None) == "planilha"
               for chamada in _chamadas(init, "StringVar") for k in chamada.keywords)


def test_a_aba_2_oferece_as_duas_fontes():
    textos = _textos(_metodo("_build_tab2"))
    assert "planilha" in textos
    assert "pasta" in textos


def test_planilha_com_ingles_e_recusado_antes_de_comecar():
    """A ficha em inglês precisa das perguntas TRADUZIDAS, que só existem na
    pasta. Pela planilha sairia ficha em inglês com perguntas em português, o
    erro que não se denuncia sozinho."""
    assert any("A ficha em inglês usa a pasta traduzida" in t
               for t in _textos(_metodo("_op2_executar")))


def test_a_aba_2_carrega_o_catalogo_e_chama_o_montador_da_planilha():
    metodo = _metodo("_op2_executar")
    assert _chamadas(metodo, "carregar")
    assert _chamadas(metodo, "aplicar_templates_fichas_da_planilha")


def test_a_aba_1_tem_a_regeneracao_e_ela_chama_o_servico():
    assert "_op1_regenerar" in ast.dump(_metodo("_build_tab1"))
    assert _chamadas(_metodo("_op1_regenerar"), "regenerar_pastas")


def test_o_seletor_da_planilha_fica_no_painel_de_cima():
    """As duas abas usam a planilha: o seletor subiu da aba 1 para o painel."""
    assert "_sel_sam_gm" in ast.dump(_metodo("_build_ui"))
    assert "_sel_sam_gm" not in ast.dump(_metodo("_build_tab1"))


def test_a_tela_nao_decide_pergunta_revisao_nem_nome_de_arquivo():
    """Princípio nº 2 do CLAUDE.md: regra de negócio mora no serviço."""
    fonte = VIEW.read_text(encoding="utf-8")
    for proibido in ("montar_pergunta", "perguntas_do_pdm", "revisao_do_pdm",
                     "nome_de_arquivo", "shutil"):
        assert proibido not in fonte, proibido


def test_as_chamadas_aos_servicos_batem_com_a_assinatura():
    """Um `log_callback=` que virasse `callback=` no serviço só quebraria no
    clique; os serviços são importáveis, então dá para conferir aqui."""
    from sigft.core import pdm_catalogo
    from sigft.services import pdm, pdm_regeneracao

    alvos = {
        "aplicar_templates_fichas_da_planilha": pdm.aplicar_templates_fichas_da_planilha,
        "aplicar_templates_fichas": pdm.aplicar_templates_fichas,
        "regenerar_pastas": pdm_regeneracao.regenerar_pastas,
        "carregar": pdm_catalogo.carregar,
    }
    problemas = []
    for nome, funcao in alvos.items():
        for chamada in _chamadas(_arvore(), nome):
            try:
                inspect.signature(funcao).bind(*chamada.args,
                                               **{k.arg: None for k in chamada.keywords})
            except TypeError as erro:
                problemas.append(f"{nome}: {erro}")
    assert not problemas, "\n".join(problemas)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_pdm_tela_planilha.py -q`
Expected: FAIL (`metodo _op1_regenerar nao existe`, `fonte_perguntas` ausente...).

- [ ] **Step 3: Implementar em `sigft/app/views/pdm.py`**

(a) Import, depois de `from sigft.core import prefs`:

```python
from sigft.core import pdm_catalogo
```

(b) Em `__init__`, depois de `self.modo_saida_fichas = ...`:

```python
        # Fonte das perguntas da aba 2 (2026-09-24): a planilha de PDMs é a
        # padrão; a pasta de PDMs Modificados continua como método antigo.
        self.fonte_perguntas = ctk.StringVar(value="planilha")
```

(c) Em `_build_ui`, trocar o `pady` de `f_path.pack(...)` para `pady=(0, 5)` e, logo depois do botão "Selecionar" da pasta, acrescentar:

```python
        # A planilha de PDMs subiu da aba 1 para cá em 2026-09-24: as duas
        # abas passaram a usá-la (regenerar/fatiar e criar as fichas).
        f_plan = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_plan.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(f_plan, text="Planilha de PDMs (SAM-GM):", width=190, anchor="w").pack(side="left")
        self.btn_sam_gm = ctk.CTkButton(f_plan, text="Selecionar", command=self._sel_sam_gm,
                                        fg_color="#3A3A3A", hover_color="#454545", width=100)
        self.btn_sam_gm.pack(side="left", padx=5)
        self.lbl_sam_gm_status = ctk.CTkLabel(f_plan, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_sam_gm_status.pack(side="left", padx=15)
```

(d) Substituir o início de `_build_tab1` (do comentário `# --- SEÇÃO 1: Fatiar lista geral (From Itaipu) ---` até o botão "Executar: Criar PDMs From Itaipu", inclusive) por:

```python
        # A pasta From Itaipu fica no topo da aba: a regeneração e o passo 1
        # antigo usam a mesma.
        f_dir = ctk.CTkFrame(parent, fg_color="transparent")
        f_dir.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(f_dir, text="Pasta (PDMs From Itaipu):", width=240, anchor="w").pack(side="left")
        ctk.CTkEntry(f_dir, textvariable=self.path_pdms_itaipu, width=280).pack(side="left", padx=5)
        ctk.CTkButton(f_dir, text="Buscar", width=80, command=lambda: self.path_pdms_itaipu.set(file_dialogs.ask_directory("pdm.pdms_itaipu", "pasta", titulo="Pasta de Origem dos PDMs"))).pack(side="left")

        # --- Regenerar as pastas a partir da planilha (2026-09-24) ---
        frm_regen = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_regen.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frm_regen, text="Regenerar as pastas a partir da planilha", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(
            frm_regen, font=("Roboto", 11), text_color="gray", justify="left", anchor="w",
            text=("Refaz a 'Pasta dos PDMs Modificados' e, se preenchida, a 'Pasta (PDMs From Itaipu)', "
                  "com a revisão no nome (PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx).\n"
                  "A versão antiga de cada PDM vai para a subpasta _versoes_antigas: nada é apagado."),
        ).pack(anchor="w", padx=10)
        ctk.CTkButton(frm_regen, text="Executar: Regenerar as pastas", command=self._op1_regenerar,
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(pady=10)

        # --- SEÇÃO 1: Fatiar lista geral (From Itaipu), método antigo ---
        frm_from = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_from.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frm_from, text="1. Fatiar Arquivo Geral (From Itaipu)", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(frm_from, text="Usa a 'Planilha de PDMs' do painel de cima. Só cria os PDMs que ainda não estão na pasta.",
                     font=("Roboto", 11), text_color="gray").pack(anchor="w", padx=10)

        ctk.CTkButton(frm_from, text="Executar: Criar PDMs From Itaipu", command=self._op1_from_itaipu, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(pady=10)
```

(e) Em `_op1_from_itaipu`, trocar a mensagem da primeira validação por:

```python
        if not lista: return messagebox.showwarning("Aviso", "Por favor, selecione a Planilha de PDMs no painel de cima.")
```

(f) Em `_build_tab2`, logo depois do rótulo "Configuração das Fichas PMIB":

```python
        # FONTE DAS PERGUNTAS (2026-09-24). A planilha de PDMs é a padrão: a
        # ficha sai da revisão vigente, sem pasta intermediária para manter. A
        # pasta continua como método antigo, e é por ela que sai a ficha em
        # inglês, que usa os PDMs traduzidos.
        f_fonte = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_fonte.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(f_fonte, text="Fonte das características:", width=240, anchor="w").pack(side="left")
        ctk.CTkRadioButton(f_fonte, text="Planilha de PDMs", variable=self.fonte_perguntas,
                           value="planilha").pack(side="left", padx=10)
        ctk.CTkRadioButton(f_fonte, text="Pasta de PDMs Modificados (método antigo)",
                           variable=self.fonte_perguntas, value="pasta").pack(side="left", padx=10)
```

(g) Novo método, depois de `_op1_traduzir`:

```python
    def _op1_regenerar(self):
        """Regenera as pastas a partir da planilha. A validação de verdade (as
        duas pastas iguais, a planilha no formato certo) é do serviço: a tela só
        confere que os campos foram preenchidos."""
        planilha = self.path_sam_gm.get()
        pasta_modificados = self.caminho_destino.get()
        pasta_itaipu = self.path_pdms_itaipu.get()
        if not planilha:
            return messagebox.showwarning("Aviso", "Selecione a planilha de PDMs no painel de cima.")
        if not pasta_modificados:
            return messagebox.showwarning("Aviso", "Selecione a 'Pasta dos PDMs Modificados' no painel de cima.")

        def task():
            try:
                from sigft.services import pdm_regeneracao
                self._safe_log("Regenerando as pastas a partir da planilha de PDMs...")
                resumo = pdm_regeneracao.regenerar_pastas(
                    planilha, pasta_modificados, pasta_itaipu or None,
                    log_callback=self._safe_log, retry_lock=self.perguntar_retry_excel)
                self._safe_log(resumo)
                self.after(0, lambda: messagebox.showinfo("Regeneração", resumo))
            except Exception as e:
                # `motivo` e não `{e}` dentro do lambda: o Python apaga `e` ao
                # sair do `except`, e o lambda só roda depois.
                motivo = str(e)
                self._safe_log(f"ERRO na regeneração: {motivo}")
                self.after(0, lambda: messagebox.showerror("Erro", f"A regeneração não foi feita:\n{motivo}"))

        threading.Thread(target=task, daemon=True).start()
```

(h) Em `_op2_executar`, trocar o bloco inicial (do comentário `# A pasta vem do IDIOMA escolhido` até o `return messagebox.showwarning("Aviso", "Selecione a 'Pasta dos PDMs Modificados' primeiro.")`) por:

```python
        # A FONTE das perguntas (2026-09-24): a planilha de PDMs, ou a pasta de
        # PDMs Modificados (método antigo). Em inglês, só a pasta: as perguntas
        # coladas têm de ser as traduzidas. Ver `_op1_traduzir`.
        da_planilha = self.fonte_perguntas.get() == "planilha"
        em_ingles = self.idioma_ficha.get() == "en"
        planilha = self.path_sam_gm.get()
        pasta_modificados = None
        if da_planilha:
            if em_ingles:
                return messagebox.showwarning(
                    "Aviso", "A ficha em inglês usa a pasta traduzida. Escolha a fonte "
                             "'Pasta de PDMs Modificados' ou o idioma Português.")
            if not planilha:
                return messagebox.showwarning("Aviso", "Selecione a planilha de PDMs no painel de cima.")
        else:
            pasta_modificados = (self.caminho_destino_en.get() if em_ingles
                                 else self.caminho_destino.get())
            if not pasta_modificados:
                if em_ingles:
                    return messagebox.showwarning(
                        "Aviso", "Idioma da ficha = English, mas a 'Pasta dos PDMs Modificados "
                                 "(EN)' não foi selecionada.\n\nEla fica na aba 1, no passo 3 "
                                 "(Traduzir para inglês).")
                return messagebox.showwarning("Aviso", "Selecione a 'Pasta dos PDMs Modificados' primeiro.")
```

e trocar a função `task` interna de `_op2_executar` por:

```python
        # THREADING DA CRIAÇÃO DE FICHAS
        def task():
            catalogo = None
            if da_planilha:
                # Antes de criar qualquer subpasta: planilha ilegível para o
                # lote sem deixar pasta vazia para trás.
                self._safe_log("Lendo a planilha de PDMs...")
                try:
                    catalogo = pdm_catalogo.carregar(planilha)
                except Exception as e:
                    motivo = str(e)
                    self._safe_log(f"ERRO ao ler a planilha de PDMs: {motivo}")
                    self.after(0, lambda: messagebox.showerror(
                        "Erro", f"Não consegui ler a planilha de PDMs:\n{motivo}"))
                    return

            self._safe_log(f"Preparando diretórios (Modo: {'Com Pastas' if criar_pastas else 'Apenas Planilhas'})...")
            dados_pastas, msg = backends.pdm_backend.processar_pastas_fichas(status_pmib, destino_fichas, lista_sel, criar_subpastas=criar_pastas)
            self._safe_log(msg)

            if not dados_pastas:
                self.after(0, lambda: messagebox.showinfo("Aviso", "Nenhum código foi processado."))
                return

            if da_planilha:
                msg_res, logs = backends.pdm_backend.aplicar_templates_fichas_da_planilha(
                    dados_pastas, catalogo, template,
                    log_callback=self._safe_log,
                    retry_lock=self.perguntar_retry_excel,
                )
            else:
                self._safe_log("Injetando os dados dos PDMs no Template (a partir da linha 79)...")
                # O idioma vai para o serviço, e não o nome da aba: quem sabe
                # como a aba se chama em inglês é o serviço
                # (`NOME_DA_ABA_EM_INGLES`). A tela só repassa a escolha.
                msg_res, logs = backends.pdm_backend.aplicar_templates_fichas(
                    dados_pastas, pasta_modificados, template,
                    log_callback=self._safe_log,
                    retry_lock=self.perguntar_retry_excel,
                    idioma=self.idioma_ficha.get(),
                )
            self._safe_log(msg_res)

            self._safe_log(">>> Processo de criação de fichas finalizado!")
            self.after(0, lambda: messagebox.showinfo(
                "Fim", f"Processo de criação de fichas finalizado.\n\n{msg_res}"))
```

- [ ] **Step 4: Rodar os testes da tela (novos e antigos) e o pyflakes**

Run: `python -m pytest tests/test_pdm_tela_planilha.py tests/test_pdm_montador_idioma.py tests/test_tela_correcao_pdm.py tests/test_texto_da_ui.py -q && python -m pyflakes sigft/app/views/pdm.py`
Expected: todos PASS; pyflakes sem saída.

- [ ] **Step 5: Abrir o app, se o contêiner deixar**

Run: `python -c "import tkinter, customtkinter" && timeout 20 xvfb-run -a python frontend.py`
Expected: a janela abre (processo morto pelo `timeout`, sem traceback). Se `tkinter`/`customtkinter`/`xvfb-run` não existirem no contêiner, registrar no relato final que o app NÃO foi aberto e que o passo 3.4b do roteiro cobre isso.

- [ ] **Step 6: Portão e commit**

```bash
bash scripts/check.sh && python -m ruff check . && python -m pyflakes frontend.py && \
git add sigft/app/views/pdm.py tests/test_pdm_tela_planilha.py && \
git commit -m "Modulo 2: tela com a fonte planilha de PDMs, e o botao Regenerar as pastas" \
  -m "O seletor da planilha sobe para o painel de cima (as duas abas usam). Aba 2: fonte das caracteristicas, planilha por padrao; planilha + ingles e recusado. Aba 1: Regenerar as pastas." \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019RQRqXdewwcJEzdHB4k7k9" && \
git push -u origin claude/practical-einstein-16tqfl
```

---

### Task 6: Validação com a planilha real e documentação

**Files:**
- Modify: `docs/base-conhecimento/02-pdm-backend.md`, `docs/base-conhecimento/13-montagem-da-ficha-tecnica.md`, `docs/refatoracao/PENDENCIAS.md`, `docs/ROTEIRO_DE_TESTE.md`, `CHANGELOG.md`
- Scratchpad (não versionado): `validar_fichas.py`, `validar_regeneracao.py`

**Interfaces:**
- Consumes: tudo das Tasks 1 a 5.

- [ ] **Step 1: Validar a montagem com a planilha real**

Script no scratchpad (`$SP` = scratchpad da sessão), rodado FORA do pytest com openpyxl e pandas reais:
- montar um template sintético (aba "Ficha Técnica Padrão");
- para os 10 PDMs da amostra do início da sessão (`PDM.1650.001`, `PDM.2940.900`, `PDM.3010.007`, `PDM.3010.800`, `PDM.4140.001`, `PDM.4320.900`, `PDM.4820.015`, `PDM.5920.020`, `PDM.5925.001`, `PDM.7010.018`), gerar a ficha pelo método antigo (pasta `$SP/modificados`, gerada no começo da sessão com o código ANTIGO) e pela planilha;
- comparar: mesmos nomes de característica (conjunto); ordem nova = `SECUENCIA`; zero `(nan)` na nova; `PDM.3010.007` só com as 13 do ACOPLAMENTO ROSCADO (a antiga tinha 19); e a ficha de `PDM.3010.007` pedida como "FIXADOR, , R0" recusada.

Expected: os critérios acima batem; anotar os números para o relato.

- [ ] **Step 2: Validar a regeneração com a planilha real**

Script no scratchpad:
- `regenerar_pastas(mestra, $SP/regen_mod, $SP/regen_itaipu)` com a planilha inteira; medir o tempo; contar arquivos (1.199 em cada pasta);
- conferir os 3 títulos com `/` e os 2 duplicados nos nomes/avisos;
- para os 10 PDMs da amostra, comparar a fatia nova com a do "Fatiar" antigo (`$SP/from_itaipu`) célula a célula (valor + fonte + borda + preenchimento + formato + alinhamento, a impressão digital de `scripts/gerar_baseline_pdm.py`): cabeçalho igual; linhas de dados iguais como CONJUNTO (a ordem muda de propósito); exceção esperada só em `PDM.3010.007` (as 6 linhas do FIXADOR saem);
- rodar de novo e conferir que tudo sai "ja em dia".

Expected: tudo bate; se passar de ~3 min, anotar e registrar em PENDENCIAS como otimização (cache de estilo por célula).

- [ ] **Step 3: Documentação**

`CHANGELOG.md`, no bloco `## 1.1.0`, uma seção nova antes de "**Tela inicial**":

```markdown
**Planilhas PMIB**

- As fichas passam a sair **direto da planilha de PDMs da Itaipu**, sem precisar manter as pastas "From Itaipu" e "PDMs Modificados" em dia. Na aba "Criar planilhas PMIB", a fonte "Planilha de PDMs" já vem marcada: basta escolher a planilha no painel de cima. A pasta continua disponível como método antigo, e é por ela que sai a ficha em inglês.
- As perguntas saem **na ordem oficial do PDM** e **sem o "(nan)"** que aparecia quando a Itaipu não escrevia o texto de ajuda.
- O log avisa quando o PDM do portal está numa **revisão diferente** da planilha, e no fim lista quais PDMs precisam subir de revisão no portal.
- Quando a planilha traz **dois PDMs diferentes com o mesmo código** (acontece em 2 códigos da exportação de 23/09/2026), a ficha não sai misturando os dois: o log mostra os dois nomes para conferir com a Itaipu.
- Botão novo **"Regenerar as pastas"**: refaz as duas pastas a partir da planilha, com a **revisão do PDM no nome do arquivo** (`PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx`). A versão antiga de cada PDM vai para a subpasta `_versoes_antigas`; nada é apagado.
```

`docs/refatoracao/PENDENCIAS.md`:
- na linha de 2026-08-18 "**Módulo de atualização dos PDMs formatados.**", riscar a descrição (`~~...~~`) e acrescentar `**RESOLVIDO em 2026-09-24**: a aba 2 monta a ficha direto da planilha (services/pdm_planilha.py) e a aba 1 regenera as duas pastas com a revisão no nome (services/pdm_regeneracao.py). Spec: docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md`; destino `Concluído`;
- seção nova no fim, `## 2026-09-24: o módulo 2 direto da planilha de PDMs`, com a tabela padrão e as linhas:
  1. `sigft/services/translator.py` × `tech_specs.py`: 6 nomes de característica têm parênteses no próprio nome (`FAIXA DE TENSAO DE ALIMENTACAO (CA)`/`(CC)`...). O Tradutor corta no primeiro "(" e junta os dois; o Upload Specs não casa nenhum. Defeito anterior a este trabalho. | Quando 4.2/4.3 forem tocados
  2. Exportação da Itaipu de 23/09/2026: `PDM.3010.007` e `PDM.5945.026` trazem dois PDMs diferentes no mesmo código, e a revisão menor tem a data mais nova. O app não os mistura mais (regra 6), mas o dado está errado na origem. | Levar à Itaipu
  3. `services/pdm.py::pdms_fromItaipu_lista_geral` (o "Fatiar" antigo) convive com o fatiador de `pdm_regeneracao`; e ele ainda falha nos 3 títulos com "/". | Aposentar depois da regeneração validada numa máquina real
  4. `tests/test_pdm_catalogo.py`: os 9 testes de leitura de planilha nunca rodaram (o `skipif` via sempre o dublê do `conftest.py`). Religados com `tests/_openpyxl_de_verdade.py`. Outros arquivos podem ter o mesmo padrão. | Informativo: procurar `skipif` sobre o dublê do openpyxl
  5. A planilha agora tem dois leitores: `core/pdm_catalogo.py` e o `pandas` de `tech_specs.preparar_dados_ia` (já registrado em 2026-09-22 para a regra da revisão). | Fase 8
  6. (só se o Step 2 medir mais de 3 min) tempo da regeneração da From Itaipu e a otimização proposta. | Otimização futura

`docs/ROTEIRO_DE_TESTE.md`:
- linha 3.4 da tabela da Etapa 3: `| 3.4 | **2. Planilhas PMIB** | Ver **3.4b** logo abaixo: mudou em 2026-09-24 | Gera as fichas pela planilha e regenera as pastas |`;
- subseção nova `### 3.4b — Planilhas PMIB direto da planilha de PDMs (2026-09-24)`, depois da 3.3b, com os passos: (1) painel de cima, escolher a planilha de PDMs exportada da Itaipu; (2) aba 2 com fonte "Planilha de PDMs", um `_STATUS_PMIB` real, o template PT, gerar; conferir na ficha as perguntas a partir da linha 79, na ordem do PDM, sem "(nan)", e o fim do log (revisão diferente do portal); (3) mesma coisa com fonte "Pasta" e conferir que o método antigo continua funcionando; (4) aba 1, "Regenerar as pastas" em duas pastas NOVAS (para não mexer nas de produção no primeiro teste); conferir os nomes com revisão, a subpasta `_versoes_antigas` numa segunda rodada com um arquivo antigo, e rodar de novo para ver "ja em dia"; (5) abrir um arquivo da From Itaipu regenerada e conferir cabeçalho, painel congelado e filtro;
- no bloco de copiar e preencher: `  3.4 Planilhas PMIB (planilha e pasta) .. [ OK / não testei / falhou: ______ ]` e `  3.4b Regenerar as pastas ............... [ OK / não testei / falhou: ______ ]`.

`docs/base-conhecimento/02-pdm-backend.md`: no quadro "Onde o código mora hoje", acrescentar as linhas `sigft/services/pdm_planilha.py` (regras da ficha pela planilha) e `sigft/services/pdm_regeneracao.py` (regenerar as pastas); e uma seção nova `## Desde 2026-09-24: a ficha direto da planilha`, com as funções novas (`aplicar_templates_fichas_da_planilha`, `formatar_tabela_de_perguntas`, `regenerar_pastas`), a escolha por revisão no método antigo e o `montar_pergunta` no "Formatar".

`docs/base-conhecimento/13-montagem-da-ficha-tecnica.md`: seção nova `## Desde 2026-09-24: a ficha pode nascer direto da planilha`, com o fluxo novo (planilha → catálogo → regras → montagem), as 9 regras em tabela curta, o nome com revisão e a `_versoes_antigas`; e, na seção "Quatro coisas que só se descobrem lendo o código", uma nota no item 4 dizendo que desde 2026-09-24 vence o arquivo de revisão mais alta no nome.

- [ ] **Step 4: Portão final e commit**

```bash
bash scripts/check.sh && python -m ruff check . && python -m pyflakes frontend.py && \
git add CHANGELOG.md docs/ && \
git commit -m "Modulo 2 direto da planilha: CHANGELOG, roteiro de teste, base de conhecimento e pendencias" \
  -m "Fecha a pendencia de 2026-08-18 (atualizacao dos PDMs formatados) e registra os achados: os 6 nomes com parenteses, os 2 codigos duplicados na exportacao da Itaipu, o Fatiar antigo a aposentar e os 9 testes que nunca rodavam." \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019RQRqXdewwcJEzdHB4k7k9" && \
git push -u origin claude/practical-einstein-16tqfl
```

---

## Desvios na execução (registrados ao executar)

- **Task 1:** a contagem esperada no Step 3 era "51 passed"; o arquivo tem 42 testes no total (33 que rodavam + os 9 religados). O critério que importa, nenhum `SKIPPED`, foi cumprido.
- **Task 4, desempenho** (investigado com `systematic-debugging`). A primeira versão do fatiador, rodada na planilha real, levava 3,5 s por PDM (uns 70 minutos para os 1.199). Duas causas, medidas por perfil e corrigidas uma de cada vez, cada uma com o seu teste de invariante:
  1. `ws[linha]` do openpyxl recalcula `max_column` varrendo as ~530 mil células a cada linha (75% do tempo). Correção: `iter_rows` com `max_row`/`max_col`, e `max_column` lido uma vez em `regenerar_pastas`. Teste: `test_fatiar_nao_varre_a_planilha_inteira_a_cada_linha`. Resultado: 830 ms por PDM.
  2. O `copy()` de estilo do openpyxl faz ida e volta em XML, e a atribuição compara por hash. Correção: `_CopiadorDeEstilo` copia cada estilo de origem uma vez e reaproveita o `_style` montado dentro de cada arquivo. Teste: `test_cada_estilo_da_planilha_e_copiado_uma_vez_so`. Resultado: 18 ms por PDM, nenhum arquivo diferente célula a célula da versão sem cache.
  - Medido no fim: **as duas pastas, 1.199 PDMs cada, em 44,9 s** (pico de 430 MB); a segunda rodada, toda "já em dia", em 9,2 s.
- **Task 6, Step 1:** as 10 fichas da amostra saíram idênticas, texto a texto, à lista `montar_pergunta` sobre `caracteristicas_em_ordem`, e, numa conferência independente do catálogo (a planilha crua, revisão vigente, ordenada pela coluna N), com a mesma contagem, os mesmos nomes e a mesma ordem. O "novo = SECUENCIA: False" do `PDM.7010.018` na primeira comparação era do script de comparação, que cortava o nome no primeiro " (" (`FAIXA DE TENSAO DE ALIMENTACAO (CA)`).
- **Task 6, Step 2:** o critério "cabeçalho igual ao do Fatiar antigo" não se sustentou, e quem estava errado era o antigo. Comparadas direto com a planilha, as 10 fatias novas são fiéis em valor, estilo e altura de linha. Contra o Fatiar antigo, os dados batem (valor e estilo) em 9 dos 10, e no `PDM.3010.007` saem exatamente as 6 linhas do FIXADOR; o que difere é: (a) a **altura das linhas**, porque o antigo reescreve a própria aba depois de `delete_rows`, que não desloca `row_dimensions` (206 das 249 linhas da amostra com a altura da POSIÇÃO; registrado em `PENDENCIAS.md` e travado por `test_a_altura_viaja_com_a_linha_e_nao_com_a_posicao`, que falha com a cópia posicional); (b) o autofiltro (`A6:X21323` no antigo, só as linhas do PDM no novo); (c) a fonte das células SEM estilo, que no antigo é a fonte padrão da planilha (`family=None`) e no novo a do openpyxl (`family=2`), sem diferença visível.

## Auto-revisão do plano (feita)

- **Cobertura do spec:** §4.1 → Task 1; §4.2 e §5 → Task 2; §4.3 → Task 3; §6 → Task 4; §7 → Task 5; §9 e §10 → Tasks 1 a 6. Mudança consciente em relação ao spec: `perguntas_do_pdm` não recebe `pmib` (o `RelatorioLote` já põe o PMIB na linha do aviso, e as listas do fim também); a linha de início diz `PDM(s)`.
- **Placeholders:** nenhum passo de código sem código. A documentação da Task 6 lista o conteúdo de cada trecho.
- **Tipos e nomes:** `Caracteristica`/`Identidade`/`caracteristicas_em_ordem`/`identidades`/`exportado_em`/`origem` (Task 1) são os usados nas Tasks 2 a 4; `PORTAL_ATRAS`/`PLANILHA_ATRAS`, `PDMRecusado`, `perguntas_do_pdm`, `conferir_catalogo`, `descrever_catalogo`, `outras_identidades`, `descrever_identidades`, `nome_de_arquivo`, `revisao_no_nome`, `montar_pergunta` (Task 2) batem com os usos em `pdm.py` e `pdm_regeneracao.py`; `formatar_tabela_de_perguntas` (Task 3) é o usado na Task 4; `regenerar_pastas` e `aplicar_templates_fichas_da_planilha` batem com a tela (Task 5).

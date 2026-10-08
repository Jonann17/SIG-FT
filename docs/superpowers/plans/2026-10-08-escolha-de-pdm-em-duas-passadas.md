# Escolha de PDM em duas passadas — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O Cria Fichas para de responder NENHUM quando existe PDM bom: a IA interpreta o material antes da busca, a escolha volta com confiança, 2º e 3º lugar e conferências, e o que o usuário decide na revisão fica registrado.

**Architecture:** Uma passada nova (`interpretar_material`, sem catálogo, 1 chamada por lote) diz o que cada material É; a busca léxica de hoje vira a frente B (4 vagas) e a interpretação vira a frente A (8 vagas). A passada 2 (`categorizar_pdm`) ganha campos de confiança, alternativas e características; o código calcula três sinais e rebaixa o ALTA que nada confirma. A tela de revisão mostra a confiança, ordena pelo que precisa de olho e oferece o 2º/3º lugar no seletor.

**Tech Stack:** Python 3.10+, `pytest`, CustomTkinter/ttk (só na tela), `LLMClient`/`get_llm` (`sigft/core/llm/`), catálogo `sigft/core/pdm_catalogo.py`.

**Spec:** `docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md`

## Global Constraints

- Python **3.10** é o mínimo (o CI roda nele).
- Código, comentários, docs e commits em **português**; mensagem de commit **sem acento**.
- **Zonas compartilhadas 🔴** (`sigft/core/llm/prompts.py`, `config.LLM_TASKS`): **commit isolado**, mensagem dizendo "zona compartilhada". Nenhuma tarefa toca `montar_autospec` nem arquivo da frente do Rafael.
- **Texto de tela e de log sem travessão "—"** (`tests/test_texto_da_ui.py` reprova). `prompts.py`, comentários e docstrings estão fora da regra.
- **Serviço não importa tkinter; tela não tem regra de negócio; serviço não conhece SDK de provedor** (só `get_llm`/`LLMClient`).
- **A suíte roda sem pandas real** (o `tests/conftest.py` dubla): as funções novas trabalham com listas e dicionários, e os testes usam dublês com `iterrows()`/`__len__`, nunca `pd.DataFrame`.
- **Antes de todo commit:** `bash scripts/check.sh` verde e `python -m ruff check .` limpo.
- **Snapshots:** só `tests/fixtures/prompts/cria_fichas_prompt.txt` é regerada e só `interpretar_material_prompt.txt` nasce — o aval do usuário é a aprovação da spec (§6). Nenhuma outra fixture muda.
- **Mexeu em `sigft/app/`:** as três partes de verificação do `CLAUDE.md` — `compileall`, o pyflakes que já roda na suíte, e **abrir o app** (`python frontend.py`). Sem display no ambiente, registre que a abertura fica para o usuário.
- **A passada 1 nunca derruba o lote** (spec §4.8): qualquer falha dela degrada para a busca de hoje, com uma linha de log.

## Mapa de arquivos

| Arquivo | Papel | Tarefas |
|---|---|---|
| `sigft/core/pdm_catalogo.py` | `candidatos_em_duas_frentes` | 1 |
| `sigft/config.py` 🔴, `sigft/core/llm/client.py` | registrar a tarefa `interpretar_material` | 2 |
| `sigft/core/llm/prompts.py` 🔴 | prompt da passada 1; reescrita da passada 2; exemplos por código | 3, 7 |
| `sigft/services/cria_fichas_escolha.py` (novo) | regras puras: interpretação, confiança, alternativas, sinais, ordem, rótulos, calibração | 4, 9, 12, 13 |
| `sigft/services/cria_fichas.py` | passada 1, passada 2 com interpretação, `preparar_para_revisao`, `classificar_para_revisao` | 5, 6, 8, 10, 11 |
| `sigft/app/views/cria_fichas.py` | chama `classificar_para_revisao`; grava a calibração | 11, 13 |
| `sigft/app/views/janelas.py` | coluna Confiança, ordem, "por quê", sugestões no seletor | 12 |
| `tests/…` | um arquivo por unidade (ver cada tarefa) | todas |
| docs (base de conhecimento, PENDENCIAS, mural, spec) | registro | 14 |

## Ajustes em relação à spec

Achados ao escrever este plano contra o código. A spec foi corrigida no mesmo commit onde o texto dela divergia.

1. **`interpretar_lote` é método do `GeminiCategorizer`** e devolve uma lista alinhada ao lote (`None` onde faltou), não `cria_fichas.interpretar_lote(df, llm) -> dict[int, Interpretacao]`: o cliente de IA mora no categorizador, e a lista alinhada é o que a busca e a revisão consomem.
2. **`alternativas` são objetos `{"pdm", "motivo"}`**: a §4.6 pede o motivo de cada sugestão no seletor, e a §4.3 dizia "lista de PDMs".
3. **O rótulo do NENHUM diz a causa**: `PDM NOVO?` quando a IA respondeu NENHUM, `SEM RESPOSTA` quando ela pulou o item, `FORA DO CATÁLOGO` quando a guarda recusou um PDM inventado. Chamar de "PDM novo?" um item que a IA nem respondeu seria falso. Linha que não veio da IA (modo "Pular IA") fica sem rótulo e na ordem da planilha.
4. **Alternativa repetida, ou igual à escolhida, sai sem log**: é redundância, não erro. A fora do catálogo é logada, como na tabela da §4.8.
5. **O sinal "nome base" compara pelo `tokenizar` do catálogo** (sem acento e com singular), não só pelo `normalizar`: "VÁLVULA" tem de confirmar `VALVULAS`.
6. O "por quê" mostra também o que a passada 1 leu do material (`A IA leu: ...`), e a calibração guarda as alternativas com o motivo.

---

### Task 1: Busca em duas frentes no catálogo

**Files:**
- Modify: `sigft/core/pdm_catalogo.py` (constante logo após `MAX_CANDIDATOS_POR_CLASSE`; método logo após `CatalogoPDM.candidatos`)
- Create: `tests/test_pdm_catalogo_duas_frentes.py`

**Interfaces:**
- Produces: `pdm_catalogo.VAGAS_DA_INTERPRETACAO: int = 8`; `CatalogoPDM.candidatos_em_duas_frentes(consulta_interpretada: str | None, consulta_crua: str, limite: int = LIMITE_CANDIDATOS, vagas_da_interpretacao: int = VAGAS_DA_INTERPRETACAO) -> list[PDM]`. Com `consulta_interpretada` vazia/`None`, devolve exatamente `self.candidatos(consulta_crua, limite=limite)`.

- [ ] **Step 1: Escrever os testes que falham**

```python
r"""A busca em duas frentes do pré-filtro de PDM (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md §4.2.

Frente A: a interpretação da IA ("é" + sinônimos), até 8 vagas.
Frente B: a busca de hoje, pela descrição crua, completando até 12. É a rede
contra uma interpretação errada, e por isso não é filtrada por ela.
"""
from __future__ import annotations

from sigft.core.pdm_catalogo import CatalogoPDM, PDM


def _pdm(codigo, base, mod="", caracts=()):
    titulo = f"{base} {mod}".strip()
    return PDM(codigo=codigo, classe=codigo.split(".")[1], titulo=titulo,
               nome_base=base, modificador=mod, caracteristicas=tuple(caracts))


def _codigos(pdms):
    return [p.codigo for p in pdms]


# --- O caso DISPLAY, com o ranqueamento real ---------------------------------
DISPLAY_CERTO = _pdm("PDM.6685.017", "INDICADOR", "DIGITAL",
                     ["CARACTERISTICAS DO DISPLAY", "FAIXA DE MEDICAO"])
CRUA_DISPLAY = "DISPLAY CRISTAL LIQUIDO 20X2 BACKLIGHT VERDE"
INTERPRETADA_DISPLAY = "INDICADOR DIGITAL MOSTRADOR DISPLAY LCD"


def _catalogo_do_display():
    """15 distratores com palavra da descrição no NOME BASE (peso 5,0), em 5
    classes (o teto é 3 por classe), contra o PDM certo, que só casa pela
    característica (peso 1,0)."""
    distratores = []
    for palavra, classe in (("CRISTAL", "5340"), ("LIQUIDO", "6850"),
                            ("VERDE", "6210"), ("BACKLIGHT", "6625"),
                            ("CRISTAL", "4820")):
        for j in range(3):
            distratores.append(_pdm(f"PDM.{classe}.{j:03d}", palavra, f"TIPO{j}"))
    outros = [_pdm(f"PDM.7010.{j:03d}", "SERVIDOR", f"M{j}") for j in range(5)]
    return CatalogoPDM(pdms=[DISPLAY_CERTO] + distratores + outros)


def test_PRECONDICAO_a_busca_de_hoje_deixa_o_display_fora_das_12_vagas():
    """O defeito que motivou a mudança, provado com o ranqueamento real."""
    assert "PDM.6685.017" not in _codigos(_catalogo_do_display().candidatos(CRUA_DISPLAY))


def test_a_interpretacao_poe_o_display_em_primeiro():
    achados = _catalogo_do_display().candidatos_em_duas_frentes(
        INTERPRETADA_DISPLAY, CRUA_DISPLAY)
    assert _codigos(achados)[0] == "PDM.6685.017"


def test_sem_interpretacao_e_identico_a_busca_de_hoje():
    cat = _catalogo_do_display()
    for vazia in ("", "   ", None):
        assert (_codigos(cat.candidatos_em_duas_frentes(vazia, CRUA_DISPLAY))
                == _codigos(cat.candidatos(CRUA_DISPLAY)))


# --- As cotas ------------------------------------------------------------------
def _catalogo_largo():
    """Classes todas distintas, para o teto por classe não interferir."""
    alfas = [_pdm(f"PDM.{1000 + j}.001", "ALFA", f"A{j}") for j in range(20)]
    betas = [_pdm(f"PDM.{3000 + j}.001", "BETA", f"B{j}") for j in range(20)]
    gamas = [_pdm(f"PDM.{5000 + j}.001", "GAMA", f"G{j}") for j in range(2)]
    return CatalogoPDM(pdms=alfas + betas + gamas)


def test_frente_a_fica_com_8_vagas_e_vem_primeiro():
    codigos = _codigos(_catalogo_largo().candidatos_em_duas_frentes("ALFA", "BETA"))
    assert len(codigos) == 12
    assert all(c.startswith("PDM.1") for c in codigos[:8])
    assert all(c.startswith("PDM.3") for c in codigos[8:])


def test_frente_b_completa_quando_a_interpretacao_rende_pouco():
    codigos = _codigos(_catalogo_largo().candidatos_em_duas_frentes("GAMA", "BETA"))
    assert len(codigos) == 12
    assert sum(c.startswith("PDM.5") for c in codigos) == 2
    assert sum(c.startswith("PDM.3") for c in codigos) == 10


def test_frente_a_completa_quando_a_descricao_crua_rende_pouco():
    codigos = _codigos(_catalogo_largo().candidatos_em_duas_frentes("ALFA", "GAMA"))
    assert len(codigos) == 12
    assert sum(c.startswith("PDM.5") for c in codigos) == 2
    assert sum(c.startswith("PDM.1") for c in codigos) == 10


def test_o_mesmo_pdm_nas_duas_frentes_entra_uma_vez_so():
    codigos = _codigos(_catalogo_largo().candidatos_em_duas_frentes("ALFA", "ALFA"))
    assert len(codigos) == len(set(codigos))


# --- O caso PLAQUETA -----------------------------------------------------------
def test_a_aplicacao_nao_passa_na_frente_dos_candidatos_da_interpretacao():
    """As válvulas que a palavra VALVULA puxa só entram depois do que a
    interpretação achou."""
    plaqueta = _pdm("PDM.5930.012", "PLAQUETA", "INDICADORA", ["MATERIAL", "TEXTO GRAVADO"])
    valvulas = [_pdm(f"PDM.{4810 + j}.001", "VALVULA", f"V{j}") for j in range(12)]
    placas = [_pdm(f"PDM.{9500 + j}.001", "PLACA", f"IDENT{j}") for j in range(4)]
    cat = CatalogoPDM(pdms=[plaqueta] + valvulas + placas)

    codigos = _codigos(cat.candidatos_em_duas_frentes(
        "PLAQUETA INDICADORA PLACA IDENTIFICACAO",
        "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC DUPLOMATIC"))

    assert codigos[0] == "PDM.5930.012"
    primeira_valvula = next(i for i, c in enumerate(codigos) if c.startswith("PDM.48"))
    assert primeira_valvula >= 5  # a plaqueta e as 4 placas vêm antes
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_pdm_catalogo_duas_frentes.py -q`
Expected: FAIL — `AttributeError: 'CatalogoPDM' object has no attribute 'candidatos_em_duas_frentes'` (o teste de PRECONDIÇÃO passa).

- [ ] **Step 3: Implementar**

Em `sigft/core/pdm_catalogo.py`, logo depois de `MAX_CANDIDATOS_POR_CLASSE = 3`:

```python
# Quantas das LIMITE_CANDIDATOS vagas vão para a busca feita com a
# interpretação da IA (frente A). As outras ficam com a busca pela descrição
# crua (frente B), que é a rede contra uma interpretação errada -- ver
# `CatalogoPDM.candidatos_em_duas_frentes`.
VAGAS_DA_INTERPRETACAO = 8
```

E, dentro de `CatalogoPDM`, logo depois do método `candidatos`:

```python
    def candidatos_em_duas_frentes(self, consulta_interpretada, consulta_crua,
                                   limite: int = LIMITE_CANDIDATOS,
                                   vagas_da_interpretacao: int = VAGAS_DA_INTERPRETACAO
                                   ) -> list[PDM]:
        """Os candidatos de um item quando a IA já disse o que ele É.

        Frente A: `consulta_interpretada` ("é" + sinônimos, no vocabulário do
        catálogo), até `vagas_da_interpretacao`. É o que leva um sinônimo ao
        nome base, onde ele pesa 5,0 em vez de 1,0: "DISPLAY CRISTAL LIQUIDO"
        não casa com INDICADOR DIGITAL, mas "INDICADOR DIGITAL" casa.

        Frente B: a busca de hoje, pela descrição crua, completando até
        `limite`. Não é filtrada pela interpretação, de propósito: se a IA
        errou a leitura, é por ela que o PDM certo ainda chega ao prompt.

        Uma frente que rende pouco cede a vaga à outra; um PDM nas duas entra
        uma vez só. Sem interpretação, o resultado é exatamente o de
        `candidatos(consulta_crua)`."""
        frente_b = self.candidatos(consulta_crua, limite=limite)
        if not str(consulta_interpretada or "").strip():
            return frente_b
        frente_a = self.candidatos(consulta_interpretada, limite=limite)

        escolhidos: list[PDM] = []
        vistos: set[str] = set()

        def pegar(fonte, ate):
            for pdm in fonte:
                if len(escolhidos) >= ate:
                    return
                if pdm.codigo not in vistos:
                    vistos.add(pdm.codigo)
                    escolhidos.append(pdm)

        pegar(frente_a, vagas_da_interpretacao)
        pegar(frente_b, limite)
        pegar(frente_a, limite)
        return escolhidos
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_pdm_catalogo_duas_frentes.py tests/test_pdm_catalogo.py -q`
Expected: PASS (os 8 novos e os antigos do catálogo).

- [ ] **Step 5: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/core/pdm_catalogo.py tests/test_pdm_catalogo_duas_frentes.py
git commit -m "Catalogo de PDMs: busca em duas frentes (interpretacao + descricao crua)"
```

---

### Task 2: Registrar a tarefa `interpretar_material` (zona compartilhada)

**Files:**
- Modify: `sigft/config.py` (dict `LLM_TASKS`, depois de `"traduzir_pdm"`)
- Modify: `sigft/core/llm/client.py` (dict `_POLITICA_RETRY_POR_TAREFA`, depois de `"traduzir_pdm"`)
- Modify: `tests/test_config.py` (`TAREFAS_ACRESCENTADAS_DEPOIS` e o mapa de `test_llm_tasks_provider_por_tarefa_segue_a_decisao`)

**Interfaces:**
- Produces: `get_llm("interpretar_material", api_key)` resolve como qualquer tarefa: escolha por tarefa no painel → escolha global → `LLM_TASKS["interpretar_material"]` (`gemini` / `gemini-3-flash-preview`). Política: `max_retries=1`.

- [ ] **Step 1: Atualizar os guards (vermelho)**

Em `tests/test_config.py`, troque a linha `TAREFAS_ACRESCENTADAS_DEPOIS = {"traduzir_pdm"}` e o comentário acima por:

```python
#   traduzir_pdm (2026-08-28): traducao PT->EN das perguntas dos PDMs
#   Modificados, para a ficha em ingles.
#   interpretar_material (2026-10-08): passada 1 da escolha de PDM do Cria
#   Fichas -- diz o que o material E, antes da busca no catalogo.
TAREFAS_ACRESCENTADAS_DEPOIS = {"traduzir_pdm", "interpretar_material"}
```

E no dicionário esperado de `test_llm_tasks_provider_por_tarefa_segue_a_decisao`, depois de `"traduzir_pdm": sigft_config.PROVIDER_GEMINI,`:

```python
        "interpretar_material": sigft_config.PROVIDER_GEMINI,
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_config.py -q`
Expected: FAIL em `test_llm_tasks_tem_exatamente_as_5_tarefas_do_cp_3_1` ("tarefa nova nao declarada") e no mapa de providers.

- [ ] **Step 3: Registrar no catálogo de tarefas**

Em `sigft/config.py`, dentro de `LLM_TASKS`, depois da entrada `"traduzir_pdm"`:

```python
    # [2026-10-08] passada 1 da escolha de PDM (Cria Fichas): diz o que cada
    # material E, no vocabulario do catalogo, antes da busca. Sem catalogo no
    # prompt e saida curta -- o modelo padrao da conta, e a falha so degrada
    # para a busca de hoje (spec 2026-10-08-escolha-de-pdm-em-duas-passadas).
    "interpretar_material": {"provider": PROVIDER_GEMINI, "model": "gemini-3-flash-preview"},
```

- [ ] **Step 4: Rodar o factory e ver o segundo guard falhar**

Run: `python -m pytest tests/test_llm_get_llm_factory.py -q -k TODA_tarefa`
Expected: FAIL — `ValueError: A tarefa 'interpretar_material' existe em LLM_TASKS mas nao tem politica de retry`.

- [ ] **Step 5: Registrar a política**

Em `sigft/core/llm/client.py`, dentro de `_POLITICA_RETRY_POR_TAREFA`, depois da entrada `"traduzir_pdm"`:

```python
    # `interpretar_material` (2026-10-08): passada 1 da escolha de PDM. UMA
    # retentativa: se ainda assim falhar, o lote segue com a busca de hoje
    # (`GeminiCategorizer.interpretar_lote` degrada sem levantar) -- nada se
    # perde, entao nao vale prender o usuario esperando mais.
    "interpretar_material": {
        "max_retries": 1,
        "retry_sleep_seconds": 2,
        "min_interval_seconds": None,
        "temperature": None,
    },
```

- [ ] **Step 6: Rodar e ver passar**

Run: `python -m pytest tests/test_config.py tests/test_llm_get_llm_factory.py -q`
Expected: PASS.

- [ ] **Step 7: Commit isolado (zona compartilhada)**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/config.py sigft/core/llm/client.py tests/test_config.py
git commit -m "config.LLM_TASKS (zona compartilhada): tarefa interpretar_material

Passada 1 da escolha de PDM do Cria Fichas. So acrescenta a chave; nenhuma
tarefa existente muda de modelo ou de politica."
```

---

### Task 3: Prompt da passada 1 (zona compartilhada)

**Files:**
- Modify: `sigft/core/llm/prompts.py` (função nova no fim do arquivo)
- Create: `tests/test_prompt_interpretar_material.py`

**Interfaces:**
- Produces: `prompts.montar_interpretar_material(itens_texto: str) -> str`. A resposta pedida é uma lista JSON de objetos `{"item": int, "e": str, "sinonimos": [str], "serve": str}`.

- [ ] **Step 1: Escrever os testes de conteúdo**

```python
r"""Propriedades do prompt da passada 1 (`interpretar_material`, 2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md §4.1.
"""
from __future__ import annotations

from sigft.core.llm import prompts


def _prompt():
    return prompts.montar_interpretar_material("<<<ITENS>>>")


def test_interpola_os_itens():
    assert "<<<ITENS>>>" in _prompt()


def test_pede_as_quatro_chaves_do_contrato():
    texto = _prompt()
    for chave in ("item", "e", "sinonimos", "serve"):
        assert f'"{chave}"' in texto, chave


def test_separa_o_que_a_peca_e_do_que_ela_serve():
    texto = _prompt()
    assert "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC" in texto
    assert "nunca o equipamento que ela serve" in texto


def test_pede_vocabulario_de_catalogo_sem_marca():
    assert "sem marca" in _prompt().lower()


def test_nao_pede_codigo_de_pdm():
    """A passada 1 não vê o catálogo: um código vindo dela seria inventado."""
    assert "PDM." not in _prompt()


def test_amarra_a_resposta_ao_numero_do_item():
    assert "### ITEM N" in _prompt()


def test_manda_responder_so_o_json():
    assert "Responda APENAS com a lista JSON" in _prompt()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_prompt_interpretar_material.py -q`
Expected: FAIL — `AttributeError: module 'sigft.core.llm.prompts' has no attribute 'montar_interpretar_material'`.

- [ ] **Step 3: Implementar**

No fim de `sigft/core/llm/prompts.py`:

```python
# =============================================================================
# 9. services.cria_fichas.GeminiCategorizer.interpretar_lote
#    tarefa "interpretar_material"  (2026-10-08)
# =============================================================================
def montar_interpretar_material(itens_texto):
    """Passada 1 da escolha de PDM: o que cada material É, nas palavras de um
    catálogo, antes de qualquer busca.

    Existe porque a busca do catálogo é por PALAVRA, e a descrição do
    fornecedor muitas vezes não traz a palavra do PDM: "DISPLAY CRISTAL
    LIQUIDO" é um INDICADOR DIGITAL. Esta passada não recebe o catálogo -- é o
    que a torna barata --, e por isso não escolhe código: o que ela escreve
    vira a consulta da busca (`CatalogoPDM.candidatos_em_duas_frentes`).

    Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md §4.1.
    """
    return f"""Você é um especialista em catalogação de materiais sobressalentes de usinas hidrelétricas.
Para cada item abaixo, diga o que o material É, com as palavras que um catálogo de materiais usaria. Você não vai escolher código nenhum: depois, uma busca no catálogo da Itaipu procura exatamente as palavras que você escrever aqui.

Para cada item, devolva:
- "e": o nome genérico do material, como um catálogo o chamaria: o substantivo da peça, seguido do que a qualifica, em maiúsculas, sem marca, sem modelo e sem medida. Ex.: "INDICADOR DIGITAL", "PLAQUETA INDICADORA", "VALVULA ESFERA", "SWITCH REDE".
- "sinonimos": até 4 outros nomes pelos quais o mesmo material é conhecido. Ex.: para um display de cristal líquido, "MOSTRADOR", "DISPLAY LCD", "VISOR DIGITAL".
- "serve": o equipamento a que a peça se destina, quando a descrição diz ("PARA VALVULA DUPLOMATIC" vira "VALVULA DUPLOMATIC"); string vazia quando não diz.

A regra mais importante: "e" é o que a peça É, nunca o equipamento que ela serve. Em "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC", a peça é uma plaqueta; a válvula vai em "serve".

Quando a descrição não nomeia o material (ex.: "IE4010 w/ 12GE SFP uplink ports"), use o que você sabe sobre o modelo para dizer o que ele é ("SWITCH REDE").

### ITENS
{itens_texto}

### RESPOSTA
Responda APENAS com a lista JSON, um objeto por item, sem texto antes ou depois:
[
  {{"item": 1, "e": "...", "sinonimos": ["...", "..."], "serve": "..."}}
]
O valor de "item" é o número do cabeçalho "### ITEM N" daquele item.
"""
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_prompt_interpretar_material.py tests/test_llm_prompts.py -q`
Expected: PASS.

- [ ] **Step 5: Commit isolado (zona compartilhada)**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/core/llm/prompts.py tests/test_prompt_interpretar_material.py
git commit -m "prompts.py (zona compartilhada): prompt interpretar_material

Passada 1 da escolha de PDM do Cria Fichas. Funcao nova; nenhum prompt
existente muda neste commit."
```

---

### Task 4: Regras puras da interpretação

**Files:**
- Create: `sigft/services/cria_fichas_escolha.py`
- Create: `tests/test_cria_fichas_escolha.py`

**Interfaces:**
- Produces (em `sigft.services.cria_fichas_escolha`):
  - `PDM_NENHUM = "NENHUM"`, `MAX_SINONIMOS = 4`
  - `@dataclass(frozen=True) class Interpretacao: e: str; sinonimos: tuple[str, ...] = (); serve: str = ""` com `como_dict() -> dict`
  - `texto_da_celula(valor) -> str` (`None` e `NaN` viram `""`; usada também pela Task 10)
  - `itens_para_interpretar(linhas: list[Mapping]) -> str`
  - `ler_interpretacoes(res_json, total: int) -> list[Interpretacao | None]`
  - `consulta_da_interpretacao(interpretacao: Interpretacao | None) -> str`

- [ ] **Step 1: Escrever os testes que falham**

```python
r"""Regras puras da escolha de PDM em duas passadas (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
Sem IA, sem tkinter, sem pandas: listas e dicionários.
"""
from __future__ import annotations

from sigft.services import cria_fichas_escolha as escolha
from sigft.services.cria_fichas_escolha import Interpretacao


# =============================================================================
# 1. A passada 1: o que vai, o que volta
# =============================================================================
def test_itens_para_interpretar_numera_e_leva_descricao_e_marca():
    texto = escolha.itens_para_interpretar([
        {"DESCRIÇÃO": "PLAQUETA EM ALUMINIO", "MARCA/MODELO": "DUPLOMATIC"},
        {"DESCRIÇÃO": "DISPLAY LCD", "MARCA/MODELO": None},
    ])
    assert "### ITEM 1\n- Descrição: PLAQUETA EM ALUMINIO\n- Marca/Modelo: DUPLOMATIC" in texto
    assert "### ITEM 2\n- Descrição: DISPLAY LCD\n- Marca/Modelo: " in texto


def test_itens_para_interpretar_nao_escreve_nan():
    """`NaN` do pandas vira o texto "nan" ao passar por `str`."""
    texto = escolha.itens_para_interpretar([{"DESCRIÇÃO": "X", "MARCA/MODELO": float("nan")}])
    assert "nan" not in texto.lower()


def test_ler_interpretacoes_casa_pelo_numero_e_nao_pela_ordem():
    lidas = escolha.ler_interpretacoes([
        {"item": 2, "e": "INDICADOR DIGITAL", "sinonimos": ["MOSTRADOR"], "serve": ""},
        {"item": 1, "e": "PLAQUETA INDICADORA", "sinonimos": [], "serve": "VALVULA DUPLOMATIC"},
    ], total=2)
    assert lidas[0] == Interpretacao(e="PLAQUETA INDICADORA", serve="VALVULA DUPLOMATIC")
    assert lidas[1] == Interpretacao(e="INDICADOR DIGITAL", sinonimos=("MOSTRADOR",))


def test_ler_interpretacoes_deixa_buraco_onde_faltou():
    lidas = escolha.ler_interpretacoes([{"item": 1, "e": "BOMBA"}], total=3)
    assert lidas[0] is not None and lidas[1] is None and lidas[2] is None


def test_ler_interpretacoes_descarta_e_vazio_numero_ruim_e_lixo():
    lidas = escolha.ler_interpretacoes(
        [{"item": 1, "e": "  "}, {"item": 99, "e": "X"}, {"item": "a", "e": "Y"}, "lixo"],
        total=2)
    assert lidas == [None, None]


def test_ler_interpretacoes_aceita_resposta_que_nao_e_lista():
    assert escolha.ler_interpretacoes({"erro": "x"}, total=2) == [None, None]
    assert escolha.ler_interpretacoes(None, total=1) == [None]


def test_ler_interpretacoes_limita_e_limpa_os_sinonimos():
    lidas = escolha.ler_interpretacoes(
        [{"item": 1, "e": "X", "sinonimos": ["A", "", None, "B", "C", "D", "E"]}], total=1)
    assert lidas[0].sinonimos == ("A", "B", "C", "D")


def test_ler_interpretacoes_tolera_sinonimos_que_nao_sao_lista():
    lidas = escolha.ler_interpretacoes([{"item": 1, "e": "X", "sinonimos": "A, B"}], total=1)
    assert lidas[0].sinonimos == ()


def test_a_consulta_leva_o_que_a_peca_e_e_os_sinonimos_mas_nao_o_que_ela_serve():
    """É o "serve" fora da consulta que tira as válvulas da vaga da plaqueta."""
    interp = Interpretacao(e="PLAQUETA INDICADORA", sinonimos=("PLACA IDENTIFICACAO",),
                           serve="VALVULA DUPLOMATIC")
    consulta = escolha.consulta_da_interpretacao(interp)
    assert consulta == "PLAQUETA INDICADORA PLACA IDENTIFICACAO"
    assert "VALVULA" not in consulta


def test_sem_interpretacao_a_consulta_e_vazia():
    assert escolha.consulta_da_interpretacao(None) == ""


def test_como_dict_e_o_formato_da_revisao():
    assert Interpretacao(e="X", sinonimos=("A",), serve="S").como_dict() == {
        "e": "X", "sinonimos": ["A"], "serve": "S"}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_escolha.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sigft.services.cria_fichas_escolha'`.

- [ ] **Step 3: Implementar**

`sigft/services/cria_fichas_escolha.py`:

```python
r"""A escolha de PDM em duas passadas: as regras puras (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md

Este módulo não chama IA e não conhece tkinter nem pandas: recebe listas e
dicionários e devolve listas e dicionários. Quem chama a IA é o
`GeminiCategorizer` (`services/cria_fichas.py`); quem mostra é a tela.
"""
from __future__ import annotations

from dataclasses import dataclass

# A resposta da IA quando nenhum PDM serve. Mora aqui, e `services/cria_fichas`
# a importa: as regras da revisão (rótulo, ordem) também precisam dela, e um
# conceito tem uma definição só.
PDM_NENHUM = "NENHUM"

MAX_SINONIMOS = 4


@dataclass(frozen=True)
class Interpretacao:
    """O que a passada 1 diz de UM item: o que ele é, por quais outros nomes
    é conhecido, e a que equipamento serve (quando a descrição diz)."""

    e: str
    sinonimos: tuple[str, ...] = ()
    serve: str = ""

    def como_dict(self) -> dict:
        return {"e": self.e, "sinonimos": list(self.sinonimos), "serve": self.serve}


def texto_da_celula(valor) -> str:
    """Texto limpo de uma célula: `None` e `NaN` do pandas viram vazio."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def itens_para_interpretar(linhas) -> str:
    """O bloco `### ITEM N` da passada 1: descrição e marca, nada mais."""
    partes = []
    for posicao, linha in enumerate(linhas, start=1):
        partes.append(
            f"### ITEM {posicao}\n"
            f"- Descrição: {texto_da_celula(linha.get('DESCRIÇÃO'))}\n"
            f"- Marca/Modelo: {texto_da_celula(linha.get('MARCA/MODELO'))}"
        )
    return "\n\n".join(partes)


def ler_interpretacoes(res_json, total) -> list:
    """Casa a resposta da passada 1 com os itens PELO número (`item`).

    Devolve `total` posições, com `None` onde a resposta faltou ou veio sem
    um `e` utilizável: esse item segue com a busca de hoje. Mesma régua de
    `cria_fichas.alinhar_resposta` -- casar por posição fazia um item pulado
    deslocar todos os seguintes."""
    alinhado = [None] * total
    for bruto in res_json if isinstance(res_json, list) else []:
        if not isinstance(bruto, dict):
            continue
        try:
            numero = int(bruto.get("item"))
        except (TypeError, ValueError):
            continue
        if not 1 <= numero <= total:
            continue
        e = texto_da_celula(bruto.get("e"))
        if not e:
            continue
        sinonimos = bruto.get("sinonimos")
        if not isinstance(sinonimos, list):
            sinonimos = []
        limpos = tuple(s for s in (texto_da_celula(x) for x in sinonimos) if s)
        alinhado[numero - 1] = Interpretacao(
            e=e, sinonimos=limpos[:MAX_SINONIMOS], serve=texto_da_celula(bruto.get("serve")))
    return alinhado


def consulta_da_interpretacao(interpretacao) -> str:
    """A consulta da frente A: o que a peça é, mais os sinônimos. O `serve`
    fica de fora de propósito -- era ele que puxava as válvulas para a vaga
    da plaqueta."""
    if interpretacao is None:
        return ""
    return " ".join((interpretacao.e,) + interpretacao.sinonimos)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cria_fichas_escolha.py -q`
Expected: PASS (11 testes).

- [ ] **Step 5: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas_escolha.py tests/test_cria_fichas_escolha.py
git commit -m "Cria Fichas: regras puras da interpretacao (passada 1)"
```

---

### Task 5: A passada 1 no categorizador

**Files:**
- Modify: `sigft/services/cria_fichas.py` (`PDM_NENHUM` passa a vir de `cria_fichas_escolha`; `GeminiCategorizer.__init__`; métodos novos `_cliente_da_interpretacao`, `modelo_da_interpretacao`, `interpretar_lote`; constante `ITENS_POR_INTERPRETACAO`)
- Create: `tests/test_cria_fichas_duas_passadas.py`
- Modify: `tests/test_llm_prompts_snapshot.py` (snapshot novo) e Create: `tests/fixtures/prompts/interpretar_material_prompt.txt`

**Interfaces:**
- Consumes: `prompts.montar_interpretar_material` (Task 3); `escolha.itens_para_interpretar`, `escolha.ler_interpretacoes`, `escolha.PDM_NENHUM` (Task 4); `get_llm("interpretar_material", ...)` (Task 2).
- Produces: `GeminiCategorizer.interpretar_lote(df_itens, callback_log=None) -> list[Interpretacao | None]` (nunca levanta; uma falha deixa `None` nas posições que faltavam, guarda as fatias que já tinham voltado, e loga `IA: interpretação indisponível (<motivo>). Seguindo só com a busca por palavras.`); `GeminiCategorizer.modelo_da_interpretacao -> str` (nunca levanta); atributo `GeminiCategorizer._llm_interpretacao` (substituível em teste); `cria_fichas.ITENS_POR_INTERPRETACAO = 60`. `cria_fichas.PDM_NENHUM` continua importável.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_cria_fichas_duas_passadas.py`:

```python
r"""O categorizador em duas passadas (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
"""
from __future__ import annotations

from sigft.core.llm.client import LLMResponse
from sigft.services import cria_fichas
from sigft.services.cria_fichas_escolha import Interpretacao


class _LLMFalso:
    """Grava cada chamada e devolve as respostas em sequência (a última se
    repete). Uma `Exception` na sequência é levantada naquela chamada."""

    provider_name = "falso"
    model = "falso-1"

    def __init__(self, *respostas):
        self.respostas = list(respostas) or [[]]
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None):
        self.chamadas.append({"prompt": prompt, "tags": tags})
        resposta = self.respostas[min(len(self.chamadas), len(self.respostas)) - 1]
        if isinstance(resposta, Exception):
            raise resposta
        return LLMResponse(text="", parsed_json=resposta, tokens_in=None,
                           tokens_out=None, custo_usd=None, model=self.model,
                           provider="gemini", duracao_s=0.0)


class _DataFrameFalso:
    """`iterrows` mínimo -- a suíte roda sem pandas real."""

    def __init__(self, linhas):
        self._linhas = linhas

    def iterrows(self):
        return enumerate(self._linhas)

    def __len__(self):
        return len(self._linhas)


def _linha(descricao, marca=""):
    return {"DESCRIÇÃO": descricao, "MARCA/MODELO": marca,
            "CÓDIGO DO MATERIAL": "1", "UNID.": "PC"}


def _categorizador(llm_interpretacao=None, llm=None):
    cat = cria_fichas.GeminiCategorizer("uma-chave")
    if llm_interpretacao is not None:
        cat._llm_interpretacao = llm_interpretacao
    if llm is not None:
        cat._llm = llm
    return cat


# =============================================================================
# 1. A passada 1
# =============================================================================
def test_interpretar_lote_devolve_uma_interpretacao_por_item():
    llm = _LLMFalso([{"item": 1, "e": "PLAQUETA INDICADORA", "sinonimos": [],
                      "serve": "VALVULA DUPLOMATIC"}])
    cat = _categorizador(llm_interpretacao=llm)

    lidas = cat.interpretar_lote(_DataFrameFalso([
        _linha("PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC", "DUPLOMATIC")]))

    assert lidas == [Interpretacao(e="PLAQUETA INDICADORA", serve="VALVULA DUPLOMATIC")]
    assert llm.chamadas[0]["tags"] == {"modulo": "cria_fichas_no_pmib_v1_backend",
                                       "tarefa": "interpretar_material"}
    assert "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC" in llm.chamadas[0]["prompt"]


def test_interpretar_lote_e_uma_chamada_so_para_lote_pequeno():
    llm = _LLMFalso([])
    _categorizador(llm_interpretacao=llm).interpretar_lote(
        _DataFrameFalso([_linha(f"ITEM {i}") for i in range(30)]))
    assert len(llm.chamadas) == 1


def test_interpretar_lote_fatia_acima_de_60_itens():
    llm = _LLMFalso([])
    lidas = _categorizador(llm_interpretacao=llm).interpretar_lote(
        _DataFrameFalso([_linha(f"ITEM {i}") for i in range(61)]))
    assert len(llm.chamadas) == 2
    assert len(lidas) == 61


def test_interpretar_lote_que_falha_NAO_derruba_o_lote():
    logs = []
    cat = _categorizador(llm_interpretacao=_LLMFalso(RuntimeError("sem chave")))

    lidas = cat.interpretar_lote(_DataFrameFalso([_linha("A"), _linha("B")]),
                                 callback_log=logs.append)

    assert lidas == [None, None]
    assert logs == ["IA: interpretação indisponível (sem chave). "
                    "Seguindo só com a busca por palavras."]


def test_interpretar_lote_que_falha_na_2a_fatia_guarda_a_1a():
    logs = []
    llm = _LLMFalso([{"item": 1, "e": "BOMBA"}], RuntimeError("rede"))

    lidas = _categorizador(llm_interpretacao=llm).interpretar_lote(
        _DataFrameFalso([_linha(f"ITEM {i}") for i in range(61)]), callback_log=logs.append)

    assert len(lidas) == 61
    assert lidas[0] == Interpretacao(e="BOMBA")
    assert lidas[60] is None
    assert len(logs) == 1


def test_modelo_da_interpretacao_descreve_o_cliente_da_passada_1():
    assert _categorizador(llm_interpretacao=_LLMFalso()).modelo_da_interpretacao == "falso/falso-1"


def test_PDM_NENHUM_continua_importavel_pelo_nome_antigo():
    assert cria_fichas.PDM_NENHUM == "NENHUM"
```

No fim de `tests/test_llm_prompts_snapshot.py`, um teste novo (mesmo padrão dos vizinhos):

```python
# =============================================================================
# 6. services.cria_fichas.GeminiCategorizer.interpretar_lote
#    tarefa "interpretar_material" (2026-10-08) -- fixture NASCIDA com a
#    spec docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md
# =============================================================================
def test_snapshot_cria_fichas_interpretar_material_prompt():
    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("chave-fake")
    fake = _FakeLLM(retorno=_resposta_ok([]))
    cat._llm_interpretacao = fake

    cat.interpretar_lote(_UmItemSo())

    assert len(fake.chamadas) == 1
    assert fake.chamadas[0]["prompt"] == _ler_fixture("interpretar_material_prompt")
    assert fake.chamadas[0]["system"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py -q`
Expected: FAIL — `AttributeError: 'GeminiCategorizer' object has no attribute 'interpretar_lote'`.

- [ ] **Step 3: Implementar**

Em `sigft/services/cria_fichas.py`:

(a) Nos imports do topo, junto de `from sigft.core.llm import prompts`:

```python
from sigft.services import cria_fichas_escolha as escolha
```

(b) Troque a linha `PDM_NENHUM = "NENHUM"` (o comentário de cima fica) por:

```python
PDM_NENHUM = escolha.PDM_NENHUM
```

(c) Logo depois de `ITENS_POR_BLOCO = 15`:

```python
# Itens por chamada da passada 1 (`interpretar_material`). Ela não carrega o
# catálogo, então o prompt é pequeno; o teto existe para a RESPOSTA (uma
# linha por item) não ficar longa a ponto de ser cortada.
ITENS_POR_INTERPRETACAO = 60
```

(d) Em `GeminiCategorizer.__init__`, depois de `self._llm = get_llm("categorizar_pdm", api_key)`:

```python
        # Passada 1 (2026-10-08): construída só quando usada -- se o provedor
        # dela não puder ser montado (chave ausente, por exemplo), o lote
        # degrada para a busca de hoje em vez de nem começar.
        self._llm_interpretacao = None
        # Os candidatos de cada item do último `processar_lote`, na ordem do
        # lote. É o que os sinais da revisão conferem ("estava na busca?").
        self.ultimos_candidatos = []
```

(e) Novos métodos em `GeminiCategorizer`, logo depois da propriedade `modelo_em_uso`:

```python
    def _cliente_da_interpretacao(self):
        if self._llm_interpretacao is None:
            self._llm_interpretacao = get_llm("interpretar_material", self.api_key)
        return self._llm_interpretacao

    @property
    def modelo_da_interpretacao(self) -> str:
        """`provider/model` da passada 1, no formato de uma linha de log.
        Nunca levanta: é só a linha de log de um passo que pode degradar."""
        try:
            llm = self._cliente_da_interpretacao()
            return f"{llm.provider_name}/{llm.model}"
        except Exception as e:
            return f"indisponível ({e})"

    def interpretar_lote(self, df_itens, callback_log=None) -> list:
        """Passada 1: o que cada material É, antes da busca no catálogo.

        Devolve uma posição por item, na ordem do lote -- `None` onde não há
        interpretação utilizável. NUNCA levanta: se uma chamada falhar (rede,
        chave, JSON inválido), as fatias que já voltaram ficam, o resto vira
        `None`, e esses itens seguem com a busca de hoje. Spec §4.8."""
        linhas = [linha for _indice, linha in df_itens.iterrows()]
        resultado = []
        try:
            llm = self._cliente_da_interpretacao()
            for fatia in _fatiar(linhas, ITENS_POR_INTERPRETACAO):
                if not fatia:
                    continue
                resp = llm.generate(
                    prompts.montar_interpretar_material(escolha.itens_para_interpretar(fatia)),
                    tags={"modulo": "cria_fichas_no_pmib_v1_backend",
                          "tarefa": "interpretar_material"},
                )
                resultado.extend(escolha.ler_interpretacoes(resp.parsed_json, total=len(fatia)))
        except Exception as e:
            if callback_log:
                callback_log(f"IA: interpretação indisponível ({e}). "
                             "Seguindo só com a busca por palavras.")
        return resultado + [None] * (len(linhas) - len(resultado))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py tests/test_cria_fichas_escolha_de_pdm.py -q`
Expected: PASS.

- [ ] **Step 5: Gerar a fixture do snapshot novo (aval: spec §6)**

```bash
python - <<'PY'
import sys
sys.path.insert(0, "tests")
import conftest  # noqa: F401 -- instala os dubles (pandas, selenium...)
import test_llm_prompts_snapshot as snap

cat = snap.cria_fichas_no_pmib_v1_backend.GeminiCategorizer("chave-fake")
fake = snap._FakeLLM(retorno=snap._resposta_ok([]))
cat._llm_interpretacao = fake
cat.interpretar_lote(snap._UmItemSo())
with open("tests/fixtures/prompts/interpretar_material_prompt.txt", "w",
          encoding="utf-8", newline="") as f:
    f.write(fake.chamadas[0]["prompt"])
print("fixture criada:", len(fake.chamadas[0]["prompt"]), "caracteres")
PY
```

Expected: `fixture criada: N caracteres`. Abra o arquivo e confira que é o prompt da passada 1 com o item "Bomba / KSB".

- [ ] **Step 6: Rodar o snapshot**

Run: `python -m pytest tests/test_llm_prompts_snapshot.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas.py tests/test_cria_fichas_duas_passadas.py \
        tests/test_llm_prompts_snapshot.py tests/fixtures/prompts/interpretar_material_prompt.txt
git commit -m "Cria Fichas: passada 1 (interpretar_lote), que degrada sem derrubar o lote"
```

---

### Task 6: A passada 2 recebe a interpretação e a busca em duas frentes

**Files:**
- Modify: `sigft/services/cria_fichas.py` — `processar_lote`, `_formatar_itens`, `_bloco_de_candidatos`, `_classes_relevantes`, `_DataFrameDeBloco`; métodos novos `_candidatos_do_item`, `_linha_da_interpretacao`
- Modify: `tests/test_cria_fichas_duas_passadas.py`

**Interfaces:**
- Consumes: `CatalogoPDM.candidatos_em_duas_frentes` (Task 1); `escolha.consulta_da_interpretacao` (Task 4).
- Produces: `GeminiCategorizer.processar_lote(df_itens, catalogo, callback_log=None, interpretacoes=None) -> list[dict | None]` (sem `interpretacoes`, idêntico a hoje); `GeminiCategorizer.ultimos_candidatos: list[list[PDM]]` alinhado ao lote; no prompt, a linha `- Interpretação: é <e> · sinônimos: <…> · serve a: <…>` antes dos candidatos.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_cria_fichas_duas_passadas.py`, junte aos imports do topo `from sigft.core import pdm_catalogo` e acrescente no fim:

```python
# =============================================================================
# 2. A passada 2 com a interpretação
#    Os candidatos de um item aparecem como "- <PDM>  [classe N]"; a LISTA DE
#    PDMS POR CLASSE traz todo PDM como "- <PDM>", sem o "[classe". É o sufixo
#    que diz se o PDM chegou como CANDIDATO.
# =============================================================================
def _pdm(codigo, base, mod="", caracts=()):
    titulo = f"{base} {mod}".strip()
    return pdm_catalogo.PDM(codigo=codigo, classe=codigo.split(".")[1], titulo=titulo,
                            nome_base=base, modificador=mod, caracteristicas=tuple(caracts))


DISPLAY_CERTO = _pdm("PDM.6685.017", "INDICADOR", "DIGITAL",
                     ["CARACTERISTICAS DO DISPLAY", "FAIXA DE MEDICAO"])


def _catalogo_do_display():
    distratores = []
    for palavra, classe in (("CRISTAL", "5340"), ("LIQUIDO", "6850"),
                            ("VERDE", "6210"), ("BACKLIGHT", "6625"),
                            ("CRISTAL", "4820")):
        for j in range(3):
            distratores.append(_pdm(f"PDM.{classe}.{j:03d}", palavra, f"TIPO{j}"))
    return pdm_catalogo.CatalogoPDM(pdms=[DISPLAY_CERTO] + distratores)


DISPLAY = _linha("DISPLAY CRISTAL LIQUIDO 20X2 BACKLIGHT VERDE")
INTERP_DISPLAY = Interpretacao(e="INDICADOR DIGITAL", sinonimos=("MOSTRADOR", "DISPLAY LCD"))


def test_sem_interpretacao_o_display_nao_chega_como_candidato():
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(_DataFrameFalso([DISPLAY]), _catalogo_do_display())
    assert "- PDM.6685.017 - INDICADOR DIGITAL  [classe 6685]" not in llm.chamadas[0]["prompt"]


def test_com_interpretacao_o_display_chega_ao_prompt_como_candidato():
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(_DataFrameFalso([DISPLAY]), _catalogo_do_display(),
                                           interpretacoes=[INTERP_DISPLAY])
    assert "- PDM.6685.017 - INDICADOR DIGITAL  [classe 6685]" in llm.chamadas[0]["prompt"]


def test_o_item_leva_a_linha_da_interpretacao():
    llm = _LLMFalso([])
    interp = Interpretacao(e="PLAQUETA INDICADORA", sinonimos=("PLACA",),
                           serve="VALVULA DUPLOMATIC")
    _categorizador(llm=llm).processar_lote(
        _DataFrameFalso([_linha("PLAQUETA PARA VALVULA")]), _catalogo_do_display(),
        interpretacoes=[interp])
    assert ("- Interpretação: é PLAQUETA INDICADORA · sinônimos: PLACA · "
            "serve a: VALVULA DUPLOMATIC") in llm.chamadas[0]["prompt"]


def test_item_sem_interpretacao_nao_leva_a_linha():
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(_DataFrameFalso([DISPLAY]), _catalogo_do_display(),
                                           interpretacoes=[None])
    assert "- Interpretação:" not in llm.chamadas[0]["prompt"]


def test_ultimos_candidatos_fica_alinhado_ao_lote():
    cat = _categorizador(llm=_LLMFalso([]))
    cat.processar_lote(_DataFrameFalso([DISPLAY, _linha("ZZZZ")]), _catalogo_do_display(),
                       interpretacoes=[INTERP_DISPLAY, None])
    assert len(cat.ultimos_candidatos) == 2
    assert "PDM.6685.017" in [p.codigo for p in cat.ultimos_candidatos[0]]
    assert cat.ultimos_candidatos[1] == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py -q`
Expected: FAIL — `TypeError: processar_lote() got an unexpected keyword argument 'interpretacoes'` (o teste sem interpretação já passa: é a pré-condição, o defeito de hoje).

- [ ] **Step 3: Implementar**

Em `sigft/services/cria_fichas.py`:

(a) Troque a classe `_DataFrameDeBloco` inteira por:

```python
class _DataFrameDeBloco:
    """O mínimo de `DataFrame` que `_formatar_itens` usa (`iterrows`/`len`).

    Existe para o fatiamento não depender de `df.iloc[a:b]`: o `df_itens` que
    chega aqui vem de `iloc[indices].copy()` na view, e fatiar por posição
    sobre um índice não reiniciado é exatamente o tipo de sutileza que causou
    o bug de numeração que este checkpoint conserta.

    `interpretacoes` e `candidatos` (2026-10-08) vêm calculados pelo
    `processar_lote`, um por item, na ordem dos pares -- calcular uma vez só
    é o que garante que o prompt, o manual podado e os sinais da revisão
    olhem os MESMOS candidatos."""

    def __init__(self, pares, interpretacoes=None, candidatos=None):
        self._pares = pares
        self.interpretacoes = interpretacoes
        self.candidatos = candidatos

    def iterrows(self):
        return iter(self._pares)

    def __len__(self):
        return len(self._pares)
```

(b) Troque o corpo de `processar_lote` (da linha `if not self.api_key: ...` até o `return resultado`) por:

```python
        if not self.api_key: raise ValueError("API Key não configurada.")

        pares = list(df_itens.iterrows())
        if interpretacoes is None:
            interpretacoes = [None] * len(pares)
        candidatos = [
            self._candidatos_do_item(linha, interpretacao, catalogo)
            for (_indice, linha), interpretacao in zip(pares, interpretacoes)
        ]
        self.ultimos_candidatos = candidatos

        blocos = _fatiar(list(range(len(pares))), ITENS_POR_BLOCO)
        resultado = []
        for numero_do_bloco, posicoes in enumerate(blocos, start=1):
            if callback_log and len(blocos) > 1:
                callback_log(
                    f"IA: bloco {numero_do_bloco}/{len(blocos)} "
                    f"({len(posicoes)} itens)"
                )
            df_bloco = _DataFrameDeBloco(
                [pares[p] for p in posicoes],
                interpretacoes=[interpretacoes[p] for p in posicoes],
                candidatos=[candidatos[p] for p in posicoes],
            )
            resultado.extend(self._processar_bloco(df_bloco, catalogo))
        return resultado
```

E a assinatura passa a ser:

```python
    def processar_lote(self, df_itens, catalogo, callback_log=None, interpretacoes=None):
```

Acrescente ao fim do docstring de `processar_lote`:

```python
        """...
        MUDOU EM 2026-10-08: `interpretacoes` (a passada 1, uma por item ou
        `None`) leva a busca para as duas frentes e põe a linha
        "Interpretação" no item. Sem ela, o resultado é o de antes.
        """
```

(c) Novos métodos estáticos em `GeminiCategorizer`, logo antes de `_bloco_de_candidatos`:

```python
    @staticmethod
    def _candidatos_do_item(linha, interpretacao, catalogo):
        """Os candidatos de UM item: a busca de hoje, ou as duas frentes
        quando a passada 1 disse o que o material é."""
        if catalogo is None:
            return []
        consulta_crua = f"{linha['DESCRIÇÃO']} {linha.get('MARCA/MODELO', '') or ''}"
        if interpretacao is None:
            return catalogo.candidatos(consulta_crua)
        return catalogo.candidatos_em_duas_frentes(
            escolha.consulta_da_interpretacao(interpretacao), consulta_crua)

    @staticmethod
    def _linha_da_interpretacao(interpretacao):
        partes = [f"é {interpretacao.e}"]
        if interpretacao.sinonimos:
            partes.append("sinônimos: " + ", ".join(interpretacao.sinonimos))
        if interpretacao.serve:
            partes.append(f"serve a: {interpretacao.serve}")
        return "- Interpretação: " + " · ".join(partes) + "\n"
```

(d) Troque `_bloco_de_candidatos` por (assinatura com `candidatos=None`):

```python
    @staticmethod
    def _bloco_de_candidatos(descricao, row, catalogo, candidatos=None):
        """Os candidatos de UM item. A marca entra na consulta junto com a
        descrição: em muitas linhas o substantivo do equipamento está só na
        coluna MARCA/MODELO. `candidatos` já calculados (pelo `processar_lote`)
        são usados como vieram."""
        if candidatos is None:
            consulta = f"{descricao} {row.get('MARCA/MODELO', '') or ''}"
            candidatos = catalogo.candidatos(consulta)
        if not candidatos:
            # Dizer que não há candidato é informação, não ruído: sem esta
            # linha o modelo poderia ler a ausência da seção como "a lista de
            # candidatos é a lista completa". Medido contra o arquivo real,
            # descrições como "IE4010 w/ 12GE SFP uplink ports" não têm
            # nenhuma palavra que nomeie o equipamento.
            return ("- CANDIDATOS: nenhum candidato foi pré-selecionado para "
                    "este item. Procure na LISTA DE PDMS POR CLASSE.\n")
        return "- CANDIDATOS (pré-selecionados por semelhança):\n" + \
            catalogo.bloco_de_candidatos(candidatos) + "\n"
```

(e) Em `_formatar_itens`, logo antes do `for posicao, (_indice, row) in enumerate(df.iterrows(), start=1):`, acrescente:

```python
        bloco = df if isinstance(df, _DataFrameDeBloco) else None
```

e troque o trecho final do laço

```python
            if catalogo is not None:
                texto += self._bloco_de_candidatos(descricao, row, catalogo)
```

por:

```python
            if bloco is not None and bloco.interpretacoes:
                interpretacao = bloco.interpretacoes[posicao - 1]
                if interpretacao is not None:
                    texto += self._linha_da_interpretacao(interpretacao)
            if catalogo is not None:
                pre = bloco.candidatos[posicao - 1] if bloco is not None and bloco.candidatos else None
                texto += self._bloco_de_candidatos(descricao, row, catalogo, candidatos=pre)
```

(f) Troque o corpo de `_classes_relevantes` por:

```python
        classes = set()
        pre = df_bloco.candidatos if isinstance(df_bloco, _DataFrameDeBloco) else None
        for posicao, (_indice, row) in enumerate(df_bloco.iterrows()):
            if pre is not None:
                achados = pre[posicao]
            else:
                consulta = f"{row['DESCRIÇÃO']} {row.get('MARCA/MODELO', '') or ''}"
                achados = catalogo.candidatos(consulta)
            for candidato in achados:
                classes.add(candidato.classe)
        return classes
```

- [ ] **Step 4: Rodar e ver passar — e os testes antigos intactos**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py tests/test_cria_fichas_escolha_de_pdm.py tests/test_llm_backend_migration.py tests/test_llm_prompts_snapshot.py -q`
Expected: PASS (inclusive o snapshot do `cria_fichas_prompt`, que ainda não mudou: sem interpretação, o prompt é o de antes).

- [ ] **Step 5: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas.py tests/test_cria_fichas_duas_passadas.py
git commit -m "Cria Fichas: passada 2 recebe a interpretacao e busca em duas frentes"
```

---

### Task 7: Reescrita do prompt da passada 2 (zona compartilhada)

**Files:**
- Modify: `sigft/core/llm/prompts.py` — `montar_categorizar_pdm` (corpo inteiro); constante nova `EXEMPLOS_CATEGORIZAR_PDM`; função nova `montar_exemplos_categorizar_pdm`
- Modify: `tests/test_prompt_categorizar_pdm.py` (testes novos; os antigos continuam valendo)
- Modify: `tests/fixtures/prompts/cria_fichas_prompt.txt` (regerada — aval: spec §6) e o docstring de `tests/test_llm_prompts_snapshot.py`

**Interfaces:**
- Produces: `prompts.EXEMPLOS_CATEGORIZAR_PDM: list[dict]` (chaves `rotulo`, `codigo`, `pdm_conferido` (`str | None`), `descricao_original`, `descricao_breve`, `por_que`); `prompts.montar_exemplos_categorizar_pdm(pdm_por_codigo=None) -> str` (com `pdm_por_codigo`, o título vem dele e código ausente tira o exemplo; sem, valem os `pdm_conferido` e saem os exemplos sem título conferido); `prompts.montar_categorizar_pdm(instrucoes, lista_pdms, itens_texto, exemplos_texto=None) -> str` (com `None`, usa `montar_exemplos_categorizar_pdm()`).
- Contrato de resposta (acréscimo): `confianca` (`"ALTA"|"MEDIA"|"BAIXA"`, `""` com NENHUM), `alternativas` (lista de até 2 `{"pdm": str, "motivo": str}`), `justificativa` (str), `caracteristicas_que_confirmam` (lista de str).

- [ ] **Step 1: Escrever os testes novos (vermelho)**

Acrescente ao fim de `tests/test_prompt_categorizar_pdm.py`:

```python
# =============================================================================
# 8. Duas passadas (2026-10-08)
#    Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md §4.3
# =============================================================================
def test_regra_b_cede_a_regra_a_quando_a_marca_e_da_aplicacao():
    """Caso real: PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC respondeu NENHUM
    com o PDM certo em 1º lugar entre os candidatos."""
    texto = _prompt()
    assert "a Regra A vence" in texto
    assert "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC" in texto
    assert "antes de qualquer outra coisa" not in texto


def test_nenhum_e_so_para_pdm_novo():
    texto = _prompt()
    assert "PDM novo precisa ser criado" in texto
    assert "melhor do que o PDM menos ruim" not in texto


def test_pede_confianca_alternativas_justificativa_e_caracteristicas():
    texto = _prompt()
    for chave in ("confianca", "alternativas", "justificativa",
                  "caracteristicas_que_confirmam"):
        assert f'"{chave}"' in texto, chave
    for nivel in ('"ALTA"', '"MEDIA"', '"BAIXA"'):
        assert nivel in texto, nivel


def test_a_lista_fechada_vale_tambem_para_as_alternativas():
    assert "cada PDM em 'alternativas'" in _prompt()


def test_explica_a_interpretacao_do_item():
    assert '"Interpretação"' in _prompt()


def test_o_que_vem_antes_do_manual_e_igual_em_todos_os_blocos():
    """Cache de prefixo: a parte constante (regras, lista, exemplos) vem antes
    da que muda a cada bloco (manual podado, itens)."""
    p1 = prompts.montar_categorizar_pdm("MANUAL DO BLOCO 1", "<<<LISTA>>>", "ITENS 1")
    p2 = prompts.montar_categorizar_pdm("MANUAL DO BLOCO 2", "<<<LISTA>>>", "ITENS 2")
    corte = "### MANUAL DE REGRAS"
    assert p1[:p1.index(corte)] == p2[:p2.index(corte)]
    assert p1.index("<<<LISTA>>>") < p1.index(corte)


def test_exemplos_sem_catalogo_saem_com_o_titulo_conferido():
    texto = prompts.montar_exemplos_categorizar_pdm()
    assert "- PDM: PDM.7010.018 - SERVIDOR" in texto
    # sem título conferido no Master: só entram com o catálogo carregado
    assert "PDM.5930.012" not in texto
    assert "PDM.6685.017" not in texto


def test_exemplos_com_catalogo_usam_o_titulo_do_catalogo():
    completos = {
        "PDM.7010.018": "PDM.7010.018 - SERVIDOR RACK",
        "PDM.5930.012": "PDM.5930.012 - PLAQUETA INDICADORA",
        "PDM.6685.017": "PDM.6685.017 - INDICADOR DIGITAL",
    }
    texto = prompts.montar_exemplos_categorizar_pdm(completos.get)
    assert "- PDM: PDM.7010.018 - SERVIDOR RACK" in texto
    assert "- PDM: PDM.5930.012 - PLAQUETA INDICADORA" in texto
    assert "- PDM: PDM.6685.017 - INDICADOR DIGITAL" in texto


def test_exemplo_cujo_codigo_nao_esta_no_catalogo_sai():
    assert prompts.montar_exemplos_categorizar_pdm(lambda _codigo: None).strip() == ""


def test_exemplos_sao_numerados_sem_buraco():
    texto = prompts.montar_exemplos_categorizar_pdm(
        {"PDM.6685.017": "PDM.6685.017 - X"}.get)
    assert "Exemplo 1 (" in texto
    assert "Exemplo 2 (" not in texto


def test_sairam_os_exemplos_de_patch_panel_e_access_point():
    texto = _prompt()
    assert "PDM.5895.006" not in texto  # PATCH PANEL
    assert "PDM.5895.015" not in texto  # ACCESS POINT
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_prompt_categorizar_pdm.py -q`
Expected: FAIL nos testes da seção 8; os antigos passam.

- [ ] **Step 3: Implementar**

Em `sigft/core/llm/prompts.py`, logo ANTES de `def montar_categorizar_pdm(`:

```python
# Os exemplos do `categorizar_pdm`, por CÓDIGO (2026-10-08).
#
# O título que vai no exemplo sai do catálogo carregado na hora (ver
# `montar_exemplos_categorizar_pdm`): um exemplo com título errado ensina o
# formato de fabricar título, e foi exatamente o defeito que a reescrita de
# 2026-09-22 corrigiu. `pdm_conferido` é o título conferido no Master naquela
# data, e só vale quando não há catálogo (os testes de conteúdo). Os dois
# exemplos sem `pdm_conferido` vêm dos casos reais do usuário e só entram com
# o catálogo -- o título exato deles nunca foi visto no repositório.
EXEMPLOS_CATEGORIZAR_PDM = [
    {
        "rotulo": "Mecânico -- o genérico vence quando nada confirma o específico",
        "codigo": "PDM.4320.007",
        "pdm_conferido": "PDM.4320.007 - BOMBA",
        "descricao_original": "Bomba KSB 123-ABC",
        "descricao_breve": "BOMBA - KSB 123-ABC",
        "por_que": ("a descrição não diz se é centrífuga, hidráulica ou de vácuo.\n"
                    "  Escolher `BOMBA HIDRAULICA` seria afirmar algo que ninguém disse."),
    },
    {
        "rotulo": "Câmera -- a nota da classe vence a semelhança de nome",
        "codigo": "PDM.5836.000",
        "pdm_conferido": "PDM.5836.000 - CAMERA VIDEO",
        "descricao_original": "CAMERAS DOME FIZ AXIS P1375-E",
        "descricao_breve": "CAMERA - P1375-E",
        "por_que": ("é câmera de rede/vídeo. A classe 6720 é de câmeras FOTOGRÁFICAS e\n"
                    "  a 6710 exclui câmeras de vídeo remetendo à 5836."),
    },
    {
        "rotulo": "Rede -- o modificador desempata",
        "codigo": "PDM.5895.016",
        "pdm_conferido": "PDM.5895.016 - VOIP GATEWAY",
        "descricao_original": "Cisco Analog Voice Gateway VG420 - 144FXS",
        "descricao_breve": "VOICE GATEWAY - VG420-144FXS",
        "por_que": ("existe também `PDM.5895.017 - GATEWAY`, mais genérico; aqui a\n"
                    "  descrição CONFIRMA que é de voz."),
    },
    {
        "rotulo": "Rede -- a descrição não nomeia o equipamento",
        "codigo": "PDM.5895.003",
        "pdm_conferido": "PDM.5895.003 - SWITCH",
        "descricao_original": "IE4010 w/ 12GE SFP, 12GE Copper PoE+ & 4GE SFP uplink ports",
        "descricao_breve": "SWITCH - IE-4010-16S12P",
        "por_que": ("nenhuma palavra da descrição diz \"switch\". As portas de uplink e o\n"
                    "  PoE+ dizem. É o caso em que a pré-seleção falha e a lista completa resolve."),
    },
    {
        "rotulo": "Peça descrita pela aplicação -- a Regra A vence a marca",
        "codigo": "PDM.5930.012",
        "pdm_conferido": None,
        "descricao_original": "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC",
        "descricao_breve": "PLAQUETA - VALVULA DUPLOMATIC",
        "por_que": ("a peça é a plaqueta; \"VALVULA DUPLOMATIC\" diz a que ela serve. A\n"
                    "  Duplomatic faz válvulas, mas não fez esta peça: a marca aqui é da aplicação."),
    },
    {
        "rotulo": "Sinônimo -- a característica confirma",
        "codigo": "PDM.6685.017",
        "pdm_conferido": None,
        "descricao_original": "DISPLAY CRISTAL LIQUIDO 20X2 BACKLIGHT VERDE",
        "descricao_breve": "DISPLAY LCD 20X2",
        "por_que": ("nenhuma palavra do título aparece na descrição, mas um display de\n"
                    "  cristal líquido é um indicador digital, e o PDM tem a característica\n"
                    "  CARACTERISTICAS DO DISPLAY, que confirma."),
    },
    {
        "rotulo": "Cabo",
        "codigo": "PDM.6145.011",
        "pdm_conferido": "PDM.6145.011 - CABO TRANSMISSAO DADOS",
        "descricao_original": "5 ft LOW LOSS CABLE ASSEMBLY W/N CONNECTORS",
        "descricao_breve": "CABO ACCESS POINT - AIR-CAB005LL-N",
        "por_que": "",
    },
    {
        "rotulo": "TI",
        "codigo": "PDM.7010.018",
        "pdm_conferido": "PDM.7010.018 - SERVIDOR",
        "descricao_original": "Servidor Dell PowerEdge C6600",
        "descricao_breve": "SERVIDOR - POWEREDGE C6600",
        "por_que": "",
    },
]


def montar_exemplos_categorizar_pdm(pdm_por_codigo=None):
    """O bloco de exemplos do `categorizar_pdm`.

    `pdm_por_codigo(codigo) -> str | None` devolve o PDM COMPLETO do catálogo
    carregado ("PDM.4320.007 - BOMBA"), ou `None` se o código não está lá --
    e aí o exemplo sai. Sem ele (testes, catálogo dublado), valem os
    `pdm_conferido`, e os exemplos sem título conferido ficam de fora.
    A numeração acompanha os exemplos que entraram, sem buraco."""
    blocos = []
    for exemplo in EXEMPLOS_CATEGORIZAR_PDM:
        if pdm_por_codigo is not None:
            completo = pdm_por_codigo(exemplo["codigo"])
        else:
            completo = exemplo["pdm_conferido"]
        if not completo:
            continue
        linhas = [
            f"Exemplo {len(blocos) + 1} ({exemplo['rotulo']}):",
            f"- Descrição original: {exemplo['descricao_original']}",
            f"- PDM: {completo}",
            f"- Descrição breve: {exemplo['descricao_breve']}",
        ]
        if exemplo["por_que"]:
            linhas.append(f"- Por quê: {exemplo['por_que']}")
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)
```

Troque a assinatura e o `return f"""…"""` de `montar_categorizar_pdm` (o docstring fica, com o parágrafo novo abaixo acrescentado ao fim dele):

```python
def montar_categorizar_pdm(instrucoes, lista_pdms, itens_texto, exemplos_texto=None):
    """...(docstring atual)...

    REESCRITO EM 2026-10-08 -- duas passadas
    ------------------------------------------------------------------------
    Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
    O item traz a "Interpretação" da passada 1; a resposta ganha confiança,
    alternativas, justificativa e as características que confirmam; NENHUM
    fica só para "PDM novo"; a Regra B cede à A quando a marca é da
    aplicação; a lista e os exemplos vêm ANTES do manual, para o prefixo ser
    igual em todos os blocos (cache); e os exemplos saem por código
    (`montar_exemplos_categorizar_pdm`).
    """
    if exemplos_texto is None:
        exemplos_texto = montar_exemplos_categorizar_pdm()
    return f"""
Você é um especialista em catalogação de materiais (PDM) altamente preciso.
Sua tarefa é classificar uma *lista de itens*, escolhendo para cada um o PDM
correto de um catálogo fechado.

### COMO O CATÁLOGO É ORGANIZADO
Todo PDM tem a forma `PDM.XXXX.YYY`, onde **XXXX é o número da classe FSC** e
YYY é o sequencial dentro dela. Ou seja: o código já diz a classe. Use isso --
o "MANUAL DE REGRAS" abaixo é organizado pelas mesmas classes XXXX, então a
regra de uma classe vale para todos os PDMs cujo código começa com ela.

### DUAS REGRAS DE CATALOGAÇÃO QUE DECIDEM A MAIORIA DOS CASOS DIFÍCEIS

**REGRA A -- o PDM descreve O QUE A PEÇA É, não a que ela serve.**
Todo título de PDM é `NOME BASE` + `MODIFICADOR`, nessa ordem: o nome base diz
o que a peça É, e o modificador apenas qualifica. Quando a descrição traz uma
peça *de* um componente -- a carcaça de um acoplamento, a junta de uma bomba,
o eixo de um redutor, o suporte de um motor --, ela é catalogada pelo que ELA
é, nunca pelo componente que ela serve.

É o erro mais caro que existe aqui, porque a palavra do componente costuma ser
a mais chamativa da descrição. Exemplo real: `COUPLING LANTERN, WITH WIRE MESH
OPENING`, da NETZSCH (fabricante de bombas). A palavra "COUPLING" salta aos
olhos, mas a peça é a **lanterna**: a coluna flangeada que une o acionamento ao
corpo da bomba e aloja o acoplamento no meio, com tela de proteção. Ela não
transmite torque -- ela sustenta e protege o que transmite. O PDM certo é
`PDM.4320.031 - COLUNA FLANGE ACOPLAMENTO` (nome base COLUNA FLANGE,
modificador ACOPLAMENTO), e NÃO um dos PDMs de acoplamento da classe 3010.

As características confirmam quando há dúvida: a peça estrutural pede
QUANTIDADE DE FUROS, DISTANCIA ENTRE FACES, TIPO DE FACE; um acoplamento de
verdade pede TORQUE NOMINAL, ROTACOES MAXIMA, DESALINHAMENTO ANGULAR.

**REGRA B -- o fabricante DA PEÇA sugere a família (a Regra A vence).**
Quando a marca é de quem fabricou a própria peça, ela restringe a classe FSC:
NETZSCH faz bombas, SKF faz rolamento, AXIS faz câmera de rede, Cisco faz
equipamento de rede. Mas a marca muitas vezes nomeia o equipamento que a peça
SERVE, e não quem a fez: em "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC", a
Duplomatic faz válvulas e a peça é uma plaqueta, não uma válvula. Marca que vem
depois de "PARA" ou "P/" descreve a aplicação; aí vale a Regra A.

### PROCESSO (para cada item)
1. Leia o item (Descrição, Marca/Modelo, Código do Material, Unidade) e a
   "Interpretação", quando houver: é o que uma leitura anterior do mesmo item
   disse que o material É, com sinônimos e a que ele serve. Aplique as regras
   A e B antes de olhar os candidatos.
2. Comece pelos "CANDIDATOS" daquele item. Eles vêm de duas buscas: uma pela
   interpretação e outra pelas palavras da descrição, e trazem a classe e as
   características de cada PDM. As características dizem o que aquele PDM
   descreve -- é o que separa irmãos parecidos (VALVULA ESFERA tem TIPO DE
   PASSAGEM e NUMERO DE VIAS; VALVULA GAVETA tem MATERIAL DA CUNHA).
3. Confira a escolha contra o "MANUAL DE REGRAS" da classe (o INCLUI e o
   NÃO INCLUI de uma classe vencem a semelhança de nome).
4. Se nenhum candidato servir, procure na "LISTA DE PDMS POR CLASSE". Os
   candidatos são uma ajuda, não um limite: quando a descrição não nomeia o
   equipamento (ex.: "IE4010 w/ 12GE SFP uplink ports", que é um switch), a
   pré-seleção não tem como acertar e a lista completa é o caminho.
5. Confirme pelas características: um PDM serve quando as características
   dele fazem sentido para o material. Liste em 'caracteristicas_que_confirmam'
   as que a descrição confirma.
6. Dê sempre o seu melhor palpite, com a confiança honesta. Um palpite com
   confiança BAIXA ajuda quem revisa, porque põe a pessoa na família certa;
   "NENHUM" obriga a procurar à mão entre todos os PDMs do catálogo.
7. Responda "NENHUM" só quando nenhum PDM do catálogo é sequer da família do
   material: é o caso em que um PDM novo precisa ser criado.

### REGRA DE LISTA FECHADA (a mais importante)
O valor de 'pdm_escolhido', e de cada PDM em 'alternativas', DEVE ser,
caractere por caractere, uma string que aparece **literalmente** na "LISTA DE
PDMS POR CLASSE" ou nos "CANDIDATOS" do item -- ou então "NENHUM". Não invente
código, não invente título, não monte um código novo a partir de dois que você
viu, e não conserte o que achar que está escrito errado. Se o PDM que você quer
não está na lista, ele não existe.

---
### LISTA DE PDMS POR CLASSE (ESCOLHA UM DESTES)
{lista_pdms}
---
### EXEMPLOS DE CLASSIFICAÇÃO CORRETA
(Guias de lógica. Todos os PDMs citados aqui existem no catálogo, mas a sua
escolha tem que sair da lista acima, não daqui.)

{exemplos_texto}

---
### MANUAL DE REGRAS (CLASSES FSC QUE TÊM PDM)
{instrucoes}
---
### ITENS PARA ANALISAR (EM LOTE):
{itens_texto}
---
### SUA TAREFA:
Analise CADA UM dos itens da lista "ITENS PARA ANALISAR".
Retorne um JSON contendo UMA LISTA de objetos, um por item, na MESMA ORDEM.

Formato da Resposta (Lista de JSON):
[
{{
    "item_processado": 1,
    "pdm_escolhido": "...",
    "confianca": "ALTA" | "MEDIA" | "BAIXA",
    "alternativas": [{{"pdm": "...", "motivo": "..."}}],
    "justificativa": "...",
    "caracteristicas_que_confirmam": ["..."],
    "descricao_curta": "...",
    "origem": "Importado" | "Nacional",
    "tipo de fabricação": "Catálogo" | "Especial",
    "tipo": "Reparável" | "Não Reparável",
    "unidade": "Unidade" | "Peça" | "Conjunto" | "metro - (m)" | "litro - (l)"
}},
{{
    "item_processado": 2,
    "pdm_escolhido": "...",
    "confianca": "...",
    "alternativas": [],
    "justificativa": "...",
    "caracteristicas_que_confirmam": [],
    "descricao_curta": "...",
    "origem": "...",
    "tipo de fabricação": "...",
    "tipo": "...",
    "unidade": "..."
}}
]

Regras para o JSON (para cada item):
1. 'item_processado': o NÚMERO DO ITEM, exatamente como aparece no cabeçalho
   "### ITEM N" daquele item. Não renumere e não pule: este número é o que
   liga a sua resposta ao material certo. Devolva um objeto para CADA item,
   mesmo os que você classificar como "NENHUM".
2. 'pdm_escolhido': o PDM COMPLETO, copiado literalmente da lista
   (ex: "PDM.1650.001 - ACUMULADOR"), ou "NENHUM".
3. 'confianca': "ALTA" quando a descrição (ou a interpretação) nomeia o
   material e as características do PDM confirmam; "MEDIA" quando a família
   está certa, mas a descrição não decide entre PDMs parecidos; "BAIXA" quando
   é o mais próximo que existe, mas pode haver PDM melhor. Com "NENHUM", use "".
4. 'alternativas': até 2 outros PDMs plausíveis, do mais para o menos provável,
   cada um copiado literalmente da lista e com o motivo em uma frase. Lista
   vazia se não houver outro plausível. Mesmo com "NENHUM", liste aqui os mais
   próximos, se houver.
5. 'justificativa': uma frase dizendo por que este PDM.
6. 'caracteristicas_que_confirmam': nomes de características do PDM escolhido,
   como aparecem nos CANDIDATOS, que a descrição confirma. Lista vazia se
   nenhuma.
7. 'descricao_curta': uma descrição de até 40 caracteres, sem acentuação.
8. 'origem': 'Importado' ou 'Nacional'.
9. 'tipo de fabricação': 'Catálogo' ou 'Especial'.
10. 'tipo': 'Reparável' ou 'Não Reparável'.
11. 'unidade': 'Unidade', 'Peça', 'Conjunto', 'metro - (m)' ou 'litro - (l)'.
    Se inconclusivo ou "NÃO ESPECIFICADA", use "Unidade".

Responda APENAS com a lista JSON. Não inclua texto antes ou depois.
"""
```

- [ ] **Step 4: Rodar os testes de conteúdo**

Run: `python -m pytest tests/test_prompt_categorizar_pdm.py tests/test_llm_prompts.py -q`
Expected: PASS (antigos e novos).

- [ ] **Step 5: Ver o snapshot falhar, e regerar a fixture (aval: spec §6)**

Run: `python -m pytest tests/test_llm_prompts_snapshot.py -q -k cria_fichas_categorizar`
Expected: FAIL (o texto mudou de propósito).

```bash
python - <<'PY'
import sys
sys.path.insert(0, "tests")
import conftest  # noqa: F401 -- instala os dubles
import test_llm_prompts_snapshot as snap

cat = snap.cria_fichas_no_pmib_v1_backend.GeminiCategorizer("chave-fake")
cat._formatar_itens = lambda df, catalogo=None: snap.CRIA_FICHAS_ITENS_TEXTO
fake = snap._FakeLLM(retorno=snap._resposta_ok([]))
cat._llm = fake
cat.processar_lote(df_itens=snap._UmItemSo(), catalogo=snap._CatalogoDeSnapshot())
with open("tests/fixtures/prompts/cria_fichas_prompt.txt", "w",
          encoding="utf-8", newline="") as f:
    f.write(fake.chamadas[0]["prompt"])
print("fixture regerada:", len(fake.chamadas[0]["prompt"]), "caracteres")
PY
```

No docstring do topo de `tests/test_llm_prompts_snapshot.py`, logo depois do parágrafo "⚠️ QUARTA REGERAÇÃO" (o de `upload_tech_specs`, 2026-09-28), acrescente:

```text
⚠️ QUINTA REGERAÇÃO -- `cria_fichas_prompt`, em 2026-10-08, com o aval do
usuário dado na aprovação da spec
docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md
(§6). O prompt de `categorizar_pdm` foi reescrito para as duas passadas. As
propriedades que importam continuam checadas por CONTEÚDO em
tests/test_prompt_categorizar_pdm.py.
```

Run: `python -m pytest tests/test_llm_prompts_snapshot.py -q`
Expected: PASS.

- [ ] **Step 6: Commit isolado (zona compartilhada)**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/core/llm/prompts.py tests/test_prompt_categorizar_pdm.py \
        tests/fixtures/prompts/cria_fichas_prompt.txt tests/test_llm_prompts_snapshot.py
git commit -m "prompts.py (zona compartilhada): categorizar_pdm em duas passadas

So montar_categorizar_pdm (e os exemplos dele) mudam; os outros prompts,
montar_autospec incluido, ficam intactos. Fixture cria_fichas_prompt regerada
com o aval da spec 2026-10-08 (§6)."
```

---

### Task 8: Os exemplos saem do Master carregado

**Files:**
- Modify: `sigft/services/cria_fichas.py` (`_processar_bloco`)
- Modify: `tests/test_cria_fichas_duas_passadas.py`

**Interfaces:**
- Consumes: `prompts.montar_exemplos_categorizar_pdm`, `prompts.montar_categorizar_pdm(..., exemplos_texto=)` (Task 7); `CatalogoPDM.por_codigo`.
- Produces: com catálogo real, o prompt mostra os exemplos com o título do Master; catálogo sem `por_codigo` (dublês) mantém o padrão sem catálogo.

- [ ] **Step 1: Escrever os testes que falham**

```python
# =============================================================================
# 3. Os exemplos vêm do catálogo
# =============================================================================
def test_o_exemplo_da_plaqueta_entra_com_o_titulo_do_master():
    plaqueta = _pdm("PDM.5930.012", "PLAQUETA", "INDICADORA", ["MATERIAL"])
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(
        _DataFrameFalso([_linha("X")]), pdm_catalogo.CatalogoPDM(pdms=[plaqueta]))
    assert "- PDM: PDM.5930.012 - PLAQUETA INDICADORA" in llm.chamadas[0]["prompt"]


def test_exemplo_cujo_pdm_nao_esta_no_master_carregado_nao_entra():
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(
        _DataFrameFalso([_linha("X")]), _catalogo_do_display())
    prompt = llm.chamadas[0]["prompt"]
    assert "PDM.7010.018" not in prompt          # SERVIDOR não está neste catálogo
    assert "- PDM: PDM.6685.017 - INDICADOR DIGITAL" in prompt
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py -q -k exemplo`
Expected: FAIL (hoje saem os exemplos conferidos, sem os do catálogo).

- [ ] **Step 3: Implementar**

Em `_processar_bloco`, troque a linha

```python
        prompt_template = prompts.montar_categorizar_pdm(instrucoes, lista_pdms, itens_texto)
```

por:

```python
        prompt_template = prompts.montar_categorizar_pdm(
            instrucoes, lista_pdms, itens_texto,
            exemplos_texto=self._exemplos_do_catalogo(catalogo),
        )
```

E acrescente o método estático, logo depois de `_processar_bloco`:

```python
    @staticmethod
    def _exemplos_do_catalogo(catalogo):
        """Os exemplos do prompt com o título do Master carregado (spec §4.3).
        Catálogo sem `por_codigo` (os dublês dos testes) fica com o padrão
        conferido -- `None` faz o prompt usá-lo."""
        por_codigo = getattr(catalogo, "por_codigo", None)
        if not callable(por_codigo):
            return None

        def completo(codigo):
            pdm = por_codigo(codigo)
            return pdm.completo if pdm is not None else None

        return prompts.montar_exemplos_categorizar_pdm(completo)
```

- [ ] **Step 4: Rodar e ver passar — snapshot intacto**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py tests/test_llm_prompts_snapshot.py tests/test_llm_backend_migration.py -q`
Expected: PASS (o snapshot usa um catálogo dublado sem `por_codigo`).

- [ ] **Step 5: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas.py tests/test_cria_fichas_duas_passadas.py
git commit -m "Cria Fichas: exemplos do prompt com o titulo do Master carregado"
```

---

### Task 9: Confiança, alternativas e sinais (regras puras)

**Files:**
- Modify: `sigft/services/cria_fichas_escolha.py`
- Modify: `tests/test_cria_fichas_escolha.py`

**Interfaces:**
- Consumes: `pdm_catalogo.normalizar`, `pdm_catalogo.tokenizar`, `PDM` (`codigo`, `nome_base`, `titulo`, `caracteristicas`, `caracteristicas_em_ordem`), `CatalogoPDM.resolver`.
- Produces:
  - `CONFIANCAS = ("ALTA", "MEDIA", "BAIXA")`, `MAX_ALTERNATIVAS = 2`
  - `normalizar_confianca(valor) -> str` (inválido → `"BAIXA"`; "MÉDIA" → `"MEDIA"`)
  - `alternativas_validas(item: dict, catalogo, escolhido: PDM | None) -> tuple[list[dict], list[str]]` — `(validas, recusadas)`; cada válida é `{"pdm": completo, "motivo": str}`
  - `calcular_sinais(escolhido: PDM | None, candidatos: list[PDM], interpretacao: Interpretacao | None, citadas) -> dict[str, bool]` com as chaves `na_busca`, `nome_base`, `caracteristicas`
  - `caracteristicas_inexistentes(pdm: PDM | None, citadas) -> list[str]` — as citadas que o PDM não tem (a Task 10 loga cada uma)
  - `confianca_final(confianca: str, sinais: dict) -> tuple[str, bool]` — `(final, rebaixada)`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_cria_fichas_escolha.py`, junte aos imports do topo:

```python
import pytest

from sigft.core.pdm_catalogo import Caracteristica, CatalogoPDM, PDM
```

e acrescente no fim:

```python
# =============================================================================
# 2. Confiança, alternativas e sinais
# =============================================================================
INDICADOR = PDM(codigo="PDM.6685.017", classe="6685", titulo="INDICADOR DIGITAL",
                nome_base="INDICADOR", modificador="DIGITAL",
                caracteristicas=("CARACTERISTICAS DO DISPLAY", "FAIXA DE MEDICAO"),
                caracteristicas_em_ordem=(Caracteristica(nome="Alimentação"),))
VALVULAS = PDM(codigo="PDM.4820.004", classe="4820", titulo="VALVULAS ESFERA",
               nome_base="VALVULAS", modificador="ESFERA")
PLAQUETA = PDM(codigo="PDM.5930.012", classe="5930", titulo="PLAQUETA INDICADORA",
               nome_base="PLAQUETA", modificador="INDICADORA")
CATALOGO = CatalogoPDM(pdms=[INDICADOR, VALVULAS, PLAQUETA])


@pytest.mark.parametrize("bruto,esperado", [
    ("ALTA", "ALTA"), ("media", "MEDIA"), ("MÉDIA", "MEDIA"), (" baixa ", "BAIXA"),
    ("", "BAIXA"), (None, "BAIXA"), ("certeza", "BAIXA"), (0.9, "BAIXA"),
])
def test_normalizar_confianca(bruto, esperado):
    assert escolha.normalizar_confianca(bruto) == esperado


def test_alternativas_resolvidas_pelo_catalogo_com_motivo():
    validas, recusadas = escolha.alternativas_validas(
        {"alternativas": [{"pdm": "PDM.4820.004 - VALVULAS ESFERA", "motivo": "se for válvula"},
                          {"pdm": "PDM.5930.012", "motivo": ""}]},
        CATALOGO, escolhido=INDICADOR)
    assert validas == [
        {"pdm": "PDM.4820.004 - VALVULAS ESFERA", "motivo": "se for válvula"},
        {"pdm": "PDM.5930.012 - PLAQUETA INDICADORA", "motivo": ""},
    ]
    assert recusadas == []


def test_alternativa_fora_do_catalogo_e_recusada():
    validas, recusadas = escolha.alternativas_validas(
        {"alternativas": [{"pdm": "PDM.0000.000 - INVENTADO"}]}, CATALOGO, escolhido=None)
    assert validas == []
    assert recusadas == ["PDM.0000.000 - INVENTADO"]


def test_alternativa_igual_a_escolhida_ou_repetida_sai_sem_ser_recusa():
    validas, recusadas = escolha.alternativas_validas(
        {"alternativas": ["PDM.6685.017 - INDICADOR DIGITAL", "PDM.5930.012",
                          "PDM.5930.012 - PLAQUETA INDICADORA"]},
        CATALOGO, escolhido=INDICADOR)
    assert [v["pdm"] for v in validas] == ["PDM.5930.012 - PLAQUETA INDICADORA"]
    assert recusadas == []


def test_no_maximo_duas_alternativas():
    validas, _ = escolha.alternativas_validas(
        {"alternativas": ["PDM.4820.004", "PDM.5930.012", "PDM.6685.017"]},
        CATALOGO, escolhido=None)
    assert len(validas) == 2


def test_alternativas_ausentes_ou_mal_formadas():
    assert escolha.alternativas_validas({}, CATALOGO, None) == ([], [])
    assert escolha.alternativas_validas({"alternativas": "x"}, CATALOGO, None) == ([], [])


INTERP_DISPLAY = Interpretacao(e="INDICADOR DIGITAL", sinonimos=("MOSTRADOR",))


def test_os_tres_sinais_confirmados():
    sinais = escolha.calcular_sinais(INDICADOR, [INDICADOR], INTERP_DISPLAY,
                                     ["CARACTERISTICAS DO DISPLAY"])
    assert sinais == {"na_busca": True, "nome_base": True, "caracteristicas": True}


def test_na_busca_e_falso_quando_veio_da_lista_completa():
    assert escolha.calcular_sinais(INDICADOR, [PLAQUETA], None, [])["na_busca"] is False


def test_nome_base_aceita_plural_e_acento():
    sinais = escolha.calcular_sinais(VALVULAS, [], Interpretacao(e="VÁLVULA ESFERA"), [])
    assert sinais["nome_base"] is True


def test_nome_base_falha_sem_interpretacao_ou_com_outra_peca():
    assert escolha.calcular_sinais(INDICADOR, [], None, [])["nome_base"] is False
    assert escolha.calcular_sinais(
        INDICADOR, [], Interpretacao(e="PLAQUETA"), [])["nome_base"] is False


def test_caracteristica_citada_tem_de_existir_no_pdm():
    """Inclusive as da revisão vigente, e com prefixo numérico ("5279 - ...")."""
    assert escolha.calcular_sinais(
        INDICADOR, [], None, ["5279 - Caracteristicas do display", "ALIMENTACAO"]
    )["caracteristicas"] is True
    assert escolha.calcular_sinais(
        INDICADOR, [], None, ["CARACTERISTICAS DO DISPLAY", "TORQUE"])["caracteristicas"] is False


def test_sem_caracteristica_citada_o_sinal_e_falso():
    assert escolha.calcular_sinais(INDICADOR, [], None, [])["caracteristicas"] is False
    assert escolha.calcular_sinais(INDICADOR, [], None, None)["caracteristicas"] is False


def test_o_prefixo_numerico_sai_dos_dois_lados():
    """Se o Master um dia trouxer "5279 - NOME", a conferência não pode quebrar."""
    com_prefixo = PDM(codigo="PDM.6685.017", classe="6685", titulo="INDICADOR DIGITAL",
                      nome_base="INDICADOR", caracteristicas=("5279 - CARACTERISTICAS DO DISPLAY",))
    assert escolha.calcular_sinais(
        com_prefixo, [], None, ["CARACTERISTICAS DO DISPLAY"])["caracteristicas"] is True


def test_caracteristicas_inexistentes_lista_so_as_que_o_pdm_nao_tem():
    assert escolha.caracteristicas_inexistentes(
        INDICADOR, ["CARACTERISTICAS DO DISPLAY", " TORQUE ", "", None]) == ["TORQUE"]
    assert escolha.caracteristicas_inexistentes(None, ["TORQUE"]) == []
    assert escolha.caracteristicas_inexistentes(INDICADOR, "TORQUE") == []


def test_sem_pdm_escolhido_nenhum_sinal():
    assert escolha.calcular_sinais(None, [INDICADOR], INTERP_DISPLAY, ["X"]) == {
        "na_busca": False, "nome_base": False, "caracteristicas": False}


@pytest.mark.parametrize("confianca,confirmados,esperado", [
    ("ALTA", 3, ("ALTA", False)),
    ("ALTA", 2, ("ALTA", False)),
    ("ALTA", 1, ("MEDIA", True)),
    ("ALTA", 0, ("MEDIA", True)),
    ("MEDIA", 0, ("MEDIA", False)),
    ("BAIXA", 3, ("BAIXA", False)),
])
def test_confianca_final(confianca, confirmados, esperado):
    chaves = ("na_busca", "nome_base", "caracteristicas")
    sinais = {c: i < confirmados for i, c in enumerate(chaves)}
    assert escolha.confianca_final(confianca, sinais) == esperado
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_escolha.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'normalizar_confianca'`.

- [ ] **Step 3: Implementar**

Em `sigft/services/cria_fichas_escolha.py`, nos imports:

```python
import re

from sigft.core.pdm_catalogo import normalizar, tokenizar
```

E no fim do arquivo:

```python
# =============================================================================
# A resposta da passada 2: confiança, alternativas e sinais (spec §4.4-4.5)
# =============================================================================
CONFIANCAS = ("ALTA", "MEDIA", "BAIXA")
MAX_ALTERNATIVAS = 2

_RE_PREFIXO_NUMERICO = re.compile(r"^\d+\s*-\s*")


def normalizar_confianca(valor) -> str:
    """ALTA, MEDIA ou BAIXA. O que não for um dos três vira BAIXA: na dúvida,
    o item vai para o topo da revisão, que é o lado seguro."""
    texto = normalizar(valor) if isinstance(valor, str) else ""
    return texto if texto in CONFIANCAS else "BAIXA"


def alternativas_validas(item, catalogo, escolhido) -> tuple:
    """O 2º e o 3º lugar que a IA sugeriu, conferidos no catálogo.

    Devolve `(validas, recusadas)`. Válida é `{"pdm": completo, "motivo": str}`,
    com o PDM canônico do catálogo. Recusada é o texto que não existe no
    catálogo -- a mesma guarda do `pdm_escolhido`. Repetida, ou igual à
    escolhida, só sai (não é erro da IA, é redundância)."""
    brutas = (item or {}).get("alternativas")
    if not isinstance(brutas, list):
        return [], []
    vistos = {escolhido.codigo} if escolhido is not None else set()
    validas, recusadas = [], []
    for bruta in brutas:
        if isinstance(bruta, dict):
            texto, motivo = bruta.get("pdm"), bruta.get("motivo")
        else:
            texto, motivo = bruta, ""
        texto = str(texto or "").strip()
        if not texto:
            continue
        pdm = catalogo.resolver(texto)
        if pdm is None:
            recusadas.append(texto)
            continue
        if pdm.codigo in vistos:
            continue
        vistos.add(pdm.codigo)
        validas.append({"pdm": pdm.completo, "motivo": str(motivo or "").strip()})
        if len(validas) >= MAX_ALTERNATIVAS:
            break
    return validas, recusadas


def _nome_base_bate(pdm, interpretacao) -> bool:
    """Toda palavra do nome base aparece no "é" ou num sinônimo? Comparação
    pelo `tokenizar` do catálogo: sem acento, com singular."""
    if pdm is None or interpretacao is None:
        return False
    consulta = tokenizar(consulta_da_interpretacao(interpretacao))
    palavras = [w for w in normalizar(pdm.nome_base or pdm.titulo).split() if tokenizar(w)]
    return bool(palavras) and all(tokenizar(w) & consulta for w in palavras)


def _sem_prefixo(nome) -> str:
    """`normalizar` mais o corte de um código na frente ("5279 - NOME"): é
    como o portal mostra a característica, e a IA pode copiar assim."""
    return _RE_PREFIXO_NUMERICO.sub("", normalizar(nome))


def _citadas_limpas(citadas) -> list:
    if not isinstance(citadas, list):
        return []
    return [str(c).strip() for c in citadas if str(c or "").strip()]


def caracteristicas_inexistentes(pdm, citadas) -> list:
    """As características citadas que o PDM escolhido NÃO tem (revisão
    vigente incluída), no texto em que a IA as escreveu."""
    if pdm is None:
        return []
    do_pdm = {_sem_prefixo(c) for c in pdm.caracteristicas}
    do_pdm |= {_sem_prefixo(c.nome) for c in pdm.caracteristicas_em_ordem}
    return [c for c in _citadas_limpas(citadas) if _sem_prefixo(c) not in do_pdm]


def _caracteristicas_existem(pdm, citadas) -> bool:
    """Ao menos uma citada, e todas existem no PDM."""
    if pdm is None or not _citadas_limpas(citadas):
        return False
    return not caracteristicas_inexistentes(pdm, citadas)


def calcular_sinais(escolhido, candidatos, interpretacao, citadas) -> dict:
    """As três conferências que o CÓDIGO faz da escolha da IA (spec §4.5)."""
    codigos = {p.codigo for p in candidatos or []}
    return {
        "na_busca": escolhido is not None and escolhido.codigo in codigos,
        "nome_base": _nome_base_bate(escolhido, interpretacao),
        "caracteristicas": _caracteristicas_existem(escolhido, citadas),
    }


def confianca_final(confianca, sinais) -> tuple:
    """ALTA só continua ALTA com pelo menos 2 de 3 sinais; senão vira MEDIA,
    rebaixada. Um ALTA que nada confirma é o erro mais caro: é o que se
    aprova sem olhar."""
    if confianca == "ALTA" and sum(bool(v) for v in sinais.values()) < 2:
        return "MEDIA", True
    return confianca, False
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cria_fichas_escolha.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas_escolha.py tests/test_cria_fichas_escolha.py
git commit -m "Cria Fichas: confianca, alternativas e os tres sinais da escolha"
```

---

### Task 10: `preparar_para_revisao` — o laço sai da tela

**Files:**
- Modify: `sigft/services/cria_fichas.py` (função de módulo nova, depois de `conferir_pdm`)
- Modify: `tests/test_cria_fichas_duas_passadas.py`

**Interfaces:**
- Consumes: `conferir_pdm`, `PDM_NENHUM` (já existem); `escolha.texto_da_celula` (Task 4); `escolha.alternativas_validas`, `escolha.calcular_sinais`, `escolha.caracteristicas_inexistentes`, `escolha.normalizar_confianca`, `escolha.confianca_final` (Task 9).
- Produces: `cria_fichas.preparar_para_revisao(respostas, linhas, catalogo, interpretacoes, candidatos, codigo_projeto, callback_log=None) -> tuple[list[dict], dict[str, int]]`. Cada linha devolvida tem os campos da resposta de hoje mais: `pdm_ia`, `origem_do_nenhum` (`"ia"|"sem_resposta"|"fora_do_catalogo"|""`), `confianca`, `confianca_final`, `rebaixada`, `sinais`, `alternativas`, `justificativa`, `caracteristicas_que_confirmam`, `interpretacao` (dict), `marca_modelo`, `codigo_projeto`, `descricao_original`. A contagem tem `sem_resposta`, `fora_do_catalogo`, `alternativas_recusadas`.

- [ ] **Step 1: Escrever os testes — primeiro a caracterização do laço de hoje**

Acrescente em `tests/test_cria_fichas_duas_passadas.py`:

```python
# =============================================================================
# 4. preparar_para_revisao -- 1º o comportamento que o laço da TELA tinha
#    (views/cria_fichas.py, antes de 2026-10-08), depois o novo
# =============================================================================
PLAQUETA = _pdm("PDM.5930.012", "PLAQUETA", "INDICADORA", ["MATERIAL", "TEXTO GRAVADO"])
CAT_REVISAO = pdm_catalogo.CatalogoPDM(pdms=[DISPLAY_CERTO, PLAQUETA])


def _preparar(respostas, linhas, interpretacoes=None, candidatos=None):
    logs = []
    saida, contagem = cria_fichas.preparar_para_revisao(
        respostas, linhas, CAT_REVISAO,
        interpretacoes or [None] * len(linhas),
        candidatos or [[] for _ in linhas],
        "PROJ-1", callback_log=logs.append)
    return saida, contagem, logs


def test_CARACTERIZACAO_item_sem_resposta_vira_nenhum_e_e_contado():
    saida, contagem, logs = _preparar([None], [_linha("PLAQUETA DE TESTE")])
    assert saida[0]["pdm_escolhido"] == "NENHUM"
    assert contagem["sem_resposta"] == 1
    assert logs == [" -> ⚠️ Item 1 sem resposta da IA. Marcado 'NENHUM' "
                    "para revisão: PLAQUETA DE TESTE"]


def test_CARACTERIZACAO_pdm_inventado_vira_nenhum_e_e_contado():
    saida, contagem, logs = _preparar(
        [{"pdm_escolhido": "PDM.0000.000 - INVENTADO"}], [_linha("X")])
    assert saida[0]["pdm_escolhido"] == "NENHUM"
    assert contagem["fora_do_catalogo"] == 1
    assert logs == [" -> ⚠️ Item 1: PDM fora do catalogo: 'PDM.0000.000 - INVENTADO'. "
                    "Marcado 'NENHUM'."]


def test_CARACTERIZACAO_codigo_certo_com_titulo_errado_e_consertado():
    saida, _, _ = _preparar([{"pdm_escolhido": "PDM.5930.012 - PLAQUETA, INDICADORA"}],
                            [_linha("X")])
    assert saida[0]["pdm_escolhido"] == "PDM.5930.012 - PLAQUETA INDICADORA"


def test_CARACTERIZACAO_leva_projeto_e_descricao_original():
    saida, _, _ = _preparar([{"pdm_escolhido": "NENHUM"}], [_linha("DESC ORIGINAL")])
    assert saida[0]["codigo_projeto"] == "PROJ-1"
    assert saida[0]["descricao_original"] == "DESC ORIGINAL"


def test_a_resposta_original_nao_e_alterada():
    respostas = [{"pdm_escolhido": "PDM.5930.012 - PLAQUETA, INDICADORA"}]
    _preparar(respostas, [_linha("X")])
    assert respostas[0]["pdm_escolhido"] == "PDM.5930.012 - PLAQUETA, INDICADORA"


# --- o novo ------------------------------------------------------------------
def test_alta_sem_conferencia_e_rebaixada():
    saida, _, _ = _preparar([{"pdm_escolhido": "PDM.5930.012", "confianca": "ALTA"}],
                            [_linha("X")])
    assert saida[0]["confianca"] == "ALTA"
    assert saida[0]["confianca_final"] == "MEDIA"
    assert saida[0]["rebaixada"] is True


def test_alta_confirmada_continua_alta():
    resposta = {"pdm_escolhido": "PDM.5930.012", "confianca": "ALTA",
                "caracteristicas_que_confirmam": ["TEXTO GRAVADO"]}
    saida, _, _ = _preparar(
        [resposta], [_linha("PLAQUETA PARA VALVULA")],
        interpretacoes=[Interpretacao(e="PLAQUETA INDICADORA")], candidatos=[[PLAQUETA]])
    assert saida[0]["sinais"] == {"na_busca": True, "nome_base": True, "caracteristicas": True}
    assert saida[0]["confianca_final"] == "ALTA"
    assert saida[0]["rebaixada"] is False


def test_nenhum_da_ia_nao_tem_confianca_e_guarda_a_origem():
    saida, _, _ = _preparar([{"pdm_escolhido": "NENHUM", "confianca": "ALTA"}], [_linha("X")])
    assert saida[0]["confianca"] == ""
    assert saida[0]["confianca_final"] == ""
    assert saida[0]["origem_do_nenhum"] == "ia"


def test_origem_do_nenhum_distingue_as_tres_causas():
    saida, _, _ = _preparar(
        [None, {"pdm_escolhido": "PDM.0000.000"}, {"pdm_escolhido": "PDM.5930.012"}],
        [_linha("A"), _linha("B"), _linha("C")])
    assert [s["origem_do_nenhum"] for s in saida] == ["sem_resposta", "fora_do_catalogo", ""]


def test_alternativa_recusada_e_logada_e_contada():
    saida, contagem, logs = _preparar(
        [{"pdm_escolhido": "PDM.5930.012",
          "alternativas": [{"pdm": "PDM.9999.999 - NAO EXISTE", "motivo": "x"}]}],
        [_linha("X")])
    assert saida[0]["alternativas"] == []
    assert contagem["alternativas_recusadas"] == 1
    assert logs == [" -> ⚠️ Item 1: alternativa fora do catálogo descartada: "
                    "'PDM.9999.999 - NAO EXISTE'"]


def test_caracteristica_citada_que_o_pdm_nao_tem_e_logada():
    saida, _, logs = _preparar(
        [{"pdm_escolhido": "PDM.5930.012", "caracteristicas_que_confirmam": ["TORQUE"]}],
        [_linha("X")])
    assert saida[0]["sinais"]["caracteristicas"] is False
    assert logs == [" -> ⚠️ Item 1: característica citada que o PDM não tem: 'TORQUE'"]


def test_guarda_o_que_a_ia_disse_para_a_calibracao():
    saida, _, _ = _preparar(
        [{"pdm_escolhido": "PDM.6685.017", "confianca": "baixa", "justificativa": " é um display "}],
        [_linha("DISPLAY", marca="ACME")],
        interpretacoes=[Interpretacao(e="INDICADOR DIGITAL", sinonimos=("MOSTRADOR",))])
    linha = saida[0]
    assert linha["pdm_ia"] == "PDM.6685.017 - INDICADOR DIGITAL"
    assert linha["confianca"] == "BAIXA"
    assert linha["justificativa"] == "é um display"
    assert linha["marca_modelo"] == "ACME"
    assert linha["interpretacao"] == {"e": "INDICADOR DIGITAL",
                                      "sinonimos": ["MOSTRADOR"], "serve": ""}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py -q -k "CARACTERIZACAO or alta or nenhum or alternativa or calibracao or original"`
Expected: FAIL — `AttributeError: module 'sigft.services.cria_fichas' has no attribute 'preparar_para_revisao'`.

- [ ] **Step 3: Implementar**

Em `sigft/services/cria_fichas.py`, logo depois de `conferir_pdm`:

```python
def preparar_para_revisao(respostas, linhas, catalogo, interpretacoes, candidatos,
                          codigo_projeto, callback_log=None):
    """Da resposta da IA à linha da tela de revisão, item a item.

    Até 2026-10-08 isto era um laço DENTRO da tela (`views/cria_fichas.py`),
    com a guarda contra PDM inventado no meio -- regra de negócio na UI,
    contra o princípio 2 do `CLAUDE.md`. O comportamento de antes está
    preservado (e trancado nos testes de CARACTERIZACAO); o que chegou junto
    é a confiança, as alternativas e os sinais (spec §4.4-4.5).

    Devolve `(linhas_da_revisao, contagem)`. `respostas` vem do
    `processar_lote` (uma por item, `None` onde a IA não respondeu);
    `interpretacoes` e `candidatos` são da mesma rodada, na mesma ordem."""
    def log(mensagem):
        if callback_log:
            callback_log(mensagem)

    contagem = {"sem_resposta": 0, "fora_do_catalogo": 0, "alternativas_recusadas": 0}
    saida = []
    for i, (resposta, linha) in enumerate(zip(respostas, linhas)):
        descricao = linha["DESCRIÇÃO"]
        origem_do_nenhum = ""
        if resposta is None:
            contagem["sem_resposta"] += 1
            origem_do_nenhum = "sem_resposta"
            item = {"pdm_escolhido": PDM_NENHUM}
            log(f" -> ⚠️ Item {i + 1} sem resposta da IA. Marcado "
                f"'NENHUM' para revisão: {str(descricao)[:40]}")
        else:
            item = dict(resposta)

        ok, motivo = conferir_pdm(item, catalogo)
        if not ok:
            contagem["fora_do_catalogo"] += 1
            origem_do_nenhum = "fora_do_catalogo"
            log(f" -> ⚠️ Item {i + 1}: {motivo}. Marcado 'NENHUM'.")
            item["pdm_escolhido"] = PDM_NENHUM

        escolhido_txt = str(item.get("pdm_escolhido") or "").strip()
        e_nenhum = escolhido_txt.upper() == PDM_NENHUM
        if e_nenhum and not origem_do_nenhum:
            origem_do_nenhum = "ia"
        escolhido = None if e_nenhum else catalogo.resolver(escolhido_txt)
        interpretacao = interpretacoes[i] if interpretacoes else None

        alternativas, recusadas = escolha.alternativas_validas(item, catalogo, escolhido)
        for texto in recusadas:
            contagem["alternativas_recusadas"] += 1
            log(f" -> ⚠️ Item {i + 1}: alternativa fora do catálogo descartada: {texto!r}")

        citadas = item.get("caracteristicas_que_confirmam")
        citadas = [str(c).strip() for c in citadas if str(c or "").strip()] \
            if isinstance(citadas, list) else []
        for nome in escolha.caracteristicas_inexistentes(escolhido, citadas):
            log(f" -> ⚠️ Item {i + 1}: característica citada que o PDM não tem: {nome!r}")
        sinais = escolha.calcular_sinais(
            escolhido, candidatos[i] if candidatos else [], interpretacao, citadas)
        if e_nenhum:
            confianca, final, rebaixada = "", "", False
        else:
            confianca = escolha.normalizar_confianca(item.get("confianca"))
            final, rebaixada = escolha.confianca_final(confianca, sinais)

        item.update({
            "pdm_ia": item["pdm_escolhido"],
            "origem_do_nenhum": origem_do_nenhum,
            "confianca": confianca,
            "confianca_final": final,
            "rebaixada": rebaixada,
            "sinais": sinais,
            "alternativas": alternativas,
            "justificativa": str(item.get("justificativa") or "").strip(),
            "caracteristicas_que_confirmam": citadas,
            "interpretacao": interpretacao.como_dict() if interpretacao is not None else {},
            "marca_modelo": escolha.texto_da_celula(linha.get("MARCA/MODELO")),
            "codigo_projeto": codigo_projeto,
            "descricao_original": descricao,
        })
        saida.append(item)
    return saida, contagem
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py tests/test_cria_fichas_escolha.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas.py tests/test_cria_fichas_duas_passadas.py
git commit -m "Cria Fichas: preparar_para_revisao, com o comportamento do laco da tela preservado"
```

---

### Task 11: O categorizador orquestra; a tela só chama

**Files:**
- Modify: `sigft/services/cria_fichas.py` (`GeminiCategorizer.classificar_para_revisao`)
- Modify: `sigft/app/views/cria_fichas.py` (`_ai_worker`: o bloco `else:` que chama a IA)
- Create: `tests/test_tela_cria_fichas_duas_passadas.py`
- Modify: `tests/test_cria_fichas_duas_passadas.py`

**Interfaces:**
- Consumes: `interpretar_lote` (Task 5), `processar_lote(..., interpretacoes=)` + `ultimos_candidatos` (Task 6), `preparar_para_revisao` (Task 10).
- Produces: `GeminiCategorizer.classificar_para_revisao(df_itens, catalogo, codigo_projeto, callback_log=None) -> tuple[list[dict], dict]`; na tela, o atributo `self._modelos_da_ia = {"passada_1": str, "passada_2": str}` (lido na Task 13).

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_cria_fichas_duas_passadas.py`:

```python
# =============================================================================
# 5. As duas passadas de ponta a ponta
# =============================================================================
def test_classificar_para_revisao_de_ponta_a_ponta():
    llm1 = _LLMFalso([{"item": 1, "e": "INDICADOR DIGITAL", "sinonimos": ["MOSTRADOR"]}])
    llm2 = _LLMFalso([{"item_processado": 1, "pdm_escolhido": "PDM.6685.017",
                       "confianca": "ALTA",
                       "caracteristicas_que_confirmam": ["CARACTERISTICAS DO DISPLAY"]}])
    cat = _categorizador(llm_interpretacao=llm1, llm=llm2)
    logs = []

    linhas, contagem = cat.classificar_para_revisao(
        _DataFrameFalso([DISPLAY]), _catalogo_do_display(), "PROJ-1", callback_log=logs.append)

    assert linhas[0]["pdm_escolhido"] == "PDM.6685.017 - INDICADOR DIGITAL"
    assert linhas[0]["confianca_final"] == "ALTA"
    assert linhas[0]["sinais"]["na_busca"] is True
    assert contagem["sem_resposta"] == 0
    assert "IA: 1 de 1 itens interpretados." in logs


def test_classificar_sem_chave_nao_chama_ia_nenhuma():
    llm1, llm2 = _LLMFalso([]), _LLMFalso([])
    cat = cria_fichas.GeminiCategorizer("")
    cat._llm_interpretacao, cat._llm = llm1, llm2
    with pytest.raises(ValueError):
        cat.classificar_para_revisao(_DataFrameFalso([DISPLAY]), _catalogo_do_display(), "P")
    assert llm1.chamadas == [] and llm2.chamadas == []


def test_classificar_com_passada_1_caida_ainda_classifica():
    llm2 = _LLMFalso([{"item_processado": 1, "pdm_escolhido": "PDM.6685.017"}])
    cat = _categorizador(llm_interpretacao=_LLMFalso(RuntimeError("rede")), llm=llm2)
    linhas, _ = cat.classificar_para_revisao(
        _DataFrameFalso([DISPLAY]), _catalogo_do_display(), "P")
    assert linhas[0]["pdm_escolhido"] == "PDM.6685.017 - INDICADOR DIGITAL"
    assert linhas[0]["interpretacao"] == {}


def test_passada_1_caida_manda_a_passada_2_igual_a_de_hoje():
    """Spec §4.8: sem a passada 1, o lote segue exatamente como hoje."""
    hoje = _LLMFalso([])
    _categorizador(llm=hoje).processar_lote(_DataFrameFalso([DISPLAY]), _catalogo_do_display())

    com_falha = _LLMFalso([])
    _categorizador(llm_interpretacao=_LLMFalso(RuntimeError("rede")), llm=com_falha) \
        .classificar_para_revisao(_DataFrameFalso([DISPLAY]), _catalogo_do_display(), "P")

    assert com_falha.chamadas[0]["prompt"] == hoje.chamadas[0]["prompt"]
```

(No topo do arquivo, junte aos imports `import pytest`.)

`tests/test_tela_cria_fichas_duas_passadas.py`:

```python
r"""A tela do Cria Fichas não tem mais a regra da revisão (2026-10-08).

Lida por AST: as telas não podem ser importadas neste ambiente.
"""
from __future__ import annotations

import ast
import pathlib

TELA = pathlib.Path(__file__).resolve().parent.parent / "sigft" / "app" / "views" / "cria_fichas.py"


def _chamadas():
    nomes = set()
    for no in ast.walk(ast.parse(TELA.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            nomes.add(no.func.attr)
    return nomes


def test_a_tela_nao_confere_pdm_sozinha():
    """A guarda contra PDM inventado mora em `preparar_para_revisao`."""
    assert "conferir_pdm" not in _chamadas()


def test_a_tela_delega_as_duas_passadas_ao_servico():
    assert "classificar_para_revisao" in _chamadas()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py tests/test_tela_cria_fichas_duas_passadas.py -q`
Expected: FAIL — `AttributeError: ... no attribute 'classificar_para_revisao'` e os dois guards da tela.

- [ ] **Step 3: Implementar o serviço**

Em `GeminiCategorizer`, logo antes de `processar_lote`:

```python
    def classificar_para_revisao(self, df_itens, catalogo, codigo_projeto, callback_log=None):
        """As duas passadas e a preparação para a revisão, de uma vez.

        Devolve `(linhas_da_revisao, contagem)` -- ver `preparar_para_revisao`.
        Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md."""
        if not self.api_key:
            raise ValueError("API Key não configurada.")
        linhas = [linha for _indice, linha in df_itens.iterrows()]

        if callback_log:
            callback_log(f"IA: interpretando {len(linhas)} itens ({self.modelo_da_interpretacao})...")
        interpretacoes = self.interpretar_lote(df_itens, callback_log=callback_log)
        if callback_log:
            lidas = sum(1 for i in interpretacoes if i is not None)
            callback_log(f"IA: {lidas} de {len(linhas)} itens interpretados.")

        respostas = self.processar_lote(df_itens, catalogo, callback_log=callback_log,
                                        interpretacoes=interpretacoes)
        return preparar_para_revisao(respostas, linhas, catalogo, interpretacoes,
                                     self.ultimos_candidatos, codigo_projeto, callback_log)
```

- [ ] **Step 4: Implementar a tela**

Em `sigft/app/views/cria_fichas.py`, no `_ai_worker`, troque o trecho que vai de `res_json = cat.processar_lote(` até o fim do `self.log(... f"PDM fora do catálogo: {fora_do_catalogo}")` (inclusive o laço `for i, item_json in enumerate(res_json):`) por:

```python
                # [2026-10-08] As duas passadas e a preparação da revisão
                # moram no serviço -- inclusive a guarda contra PDM inventado,
                # que era um laço aqui dentro (regra de negócio na tela).
                final_data, contagem = cat.classificar_para_revisao(
                    self.df_data_selecionado, self.catalogo, cod_proj,
                    callback_log=self.log,
                )
                self._modelos_da_ia = {
                    "passada_1": cat.modelo_da_interpretacao,
                    "passada_2": cat.modelo_em_uso,
                }

                self.log(
                    f"IA Finalizada. {len(final_data)} itens | "
                    f"sem resposta: {contagem['sem_resposta']} | "
                    f"PDM fora do catálogo: {contagem['fora_do_catalogo']}"
                )
```

Confira que a linha `self.df_processed = pd.DataFrame(final_data)` logo depois continua lá, e que `final_data = []` (no topo do `try`) continua alimentando o ramo "Pular IA".

No comentário dos imports do mesmo arquivo, o `cria_fichas_svc` deixou de entrar pela guarda (que foi para o serviço); ele continua importado pelas conferências pós-portal. Troque

```python
# O catálogo de PDMs (2026-09-22): lê a planilha-mestra da Itaipu e faz o
# pré-filtro de candidatos por item. `cria_fichas_svc` entra pelas guardas
# (`conferir_pdm`) -- o resto do serviço continua vindo por `backends`, que é
# quem resolve o shim de compatibilidade.
```

por

```python
# O catálogo de PDMs (2026-09-22): lê a planilha-mestra da Itaipu e faz o
# pré-filtro de candidatos por item. `cria_fichas_svc` entra pelas
# conferências do que o portal gravou (`codigo_do_pdm`, `revisao_do_pdm`) --
# o resto do serviço continua vindo por `backends`, que é quem resolve o shim
# de compatibilidade.
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_cria_fichas_duas_passadas.py tests/test_tela_cria_fichas_duas_passadas.py tests/test_frontend_nomes_indefinidos.py -q`
Expected: PASS.

- [ ] **Step 6: Verificação da tela (três partes)**

```bash
python -m compileall -q sigft/app/views/cria_fichas.py
python -m pyflakes sigft/app/views/cria_fichas.py
python frontend.py   # abrir e olhar a janela; sem display, registrar que fica para o usuario
```

- [ ] **Step 7: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas.py sigft/app/views/cria_fichas.py \
        tests/test_cria_fichas_duas_passadas.py tests/test_tela_cria_fichas_duas_passadas.py
git commit -m "Cria Fichas: classificar_para_revisao orquestra as duas passadas; a tela so chama"
```

---

### Task 12: A tela de revisão mostra a confiança

**Files:**
- Modify: `sigft/services/cria_fichas_escolha.py` (helpers de exibição)
- Modify: `sigft/app/views/janelas.py` (`JanelaEscolherPDM`, `JanelaRevisaoPDM`)
- Modify: `tests/test_cria_fichas_escolha.py`
- Modify: `tests/test_tela_cria_fichas_duas_passadas.py`
- Modify: `tests/test_cria_fichas_escolha_de_pdm.py` (os dublês de `editar_pdm` acompanham a assinatura nova do seletor)

**Interfaces:**
- Produces (em `cria_fichas_escolha`):
  - `ordem_para_revisao(linhas: list[Mapping]) -> list[int]` — posições: NENHUM → BAIXA → MEDIA → ALTA; linha que não veio da IA (sem `pdm_ia`, modo "Pular IA") fica por último, na ordem da planilha; empate mantém a ordem da planilha
  - `rotulo_de_confianca(linha) -> str` — `"ALTA"`, `"MÉDIA"`, `"MÉDIA ↓"`, `"BAIXA"`, `"PDM NOVO?"`, `"SEM RESPOSTA"`, `"FORA DO CATÁLOGO"`, ou `""` para linha que não veio da IA
  - `texto_do_porque(linha) -> str`
  - `sugestoes_da_linha(linha, catalogo) -> list[tuple[PDM, str]]`
  - `juntar_sugestoes(sugestoes, achados, limite) -> list[PDM]`
- `JanelaEscolherPDM(parent, catalogo, sugestoes=())`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_cria_fichas_escolha.py`:

```python
# =============================================================================
# 3. O que a tela de revisão mostra
# =============================================================================
def _linha_rev(pdm="PDM.5930.012 - PLAQUETA INDICADORA", final="ALTA", **extra):
    """Uma linha como o `preparar_para_revisao` devolve: tem `pdm_ia`."""
    linha = {"pdm_escolhido": pdm, "pdm_ia": pdm, "confianca_final": final}
    linha.update(extra)
    return linha


def test_ordem_poe_o_que_precisa_de_olho_primeiro():
    linhas = [_linha_rev(final="ALTA"), _linha_rev(final="BAIXA"),
              _linha_rev(pdm="NENHUM", final=""), _linha_rev(final="MEDIA"),
              _linha_rev(final="BAIXA")]
    assert escolha.ordem_para_revisao(linhas) == [2, 1, 4, 3, 0]


def test_ordem_sem_ia_mantem_a_planilha():
    """Modo "Pular IA": o PDM vem da planilha, NENHUM inclusive, e a ordem
    não muda."""
    linhas = [{"pdm_escolhido": "PDM.1"}, {"pdm_escolhido": "NENHUM"}]
    assert escolha.ordem_para_revisao(linhas) == [0, 1]


@pytest.mark.parametrize("linha,esperado", [
    (_linha_rev(final="ALTA"), "ALTA"),
    (_linha_rev(final="MEDIA"), "MÉDIA"),
    (_linha_rev(final="MEDIA", rebaixada=True), "MÉDIA ↓"),
    (_linha_rev(final="BAIXA"), "BAIXA"),
    (_linha_rev(pdm="NENHUM", final="", origem_do_nenhum="ia"), "PDM NOVO?"),
    (_linha_rev(pdm="NENHUM", final="", origem_do_nenhum="sem_resposta"), "SEM RESPOSTA"),
    (_linha_rev(pdm="NENHUM", final="", origem_do_nenhum="fora_do_catalogo"), "FORA DO CATÁLOGO"),
    ({"pdm_escolhido": "PDM.1"}, ""),
    ({"pdm_escolhido": "NENHUM"}, ""),  # "Pular IA": não foi a IA que disse NENHUM
])
def test_rotulo_de_confianca(linha, esperado):
    assert escolha.rotulo_de_confianca(linha) == esperado


class _BoolDoNumpy:
    """`numpy.True_ is True` é falso, e é o que a linha do pandas pode
    entregar numa coluna só de booleanos."""

    def __bool__(self):
        return True

    def __str__(self):
        return "True"


def test_rebaixada_vale_tambem_para_o_booleano_do_numpy():
    linha = _linha_rev(final="MEDIA", rebaixada=_BoolDoNumpy())
    assert escolha.rotulo_de_confianca(linha) == "MÉDIA ↓"


def test_texto_do_porque_junta_justificativa_conferencias_e_leitura():
    texto = escolha.texto_do_porque({
        "justificativa": "é um display",
        "sinais": {"na_busca": True, "nome_base": False, "caracteristicas": True},
        "interpretacao": {"e": "INDICADOR DIGITAL"},
    })
    assert texto == ("Por quê: é um display\n"
                     "Conferências: na busca ✓ · nome base ✗ · características ✓\n"
                     "A IA leu: INDICADOR DIGITAL")
    assert "—" not in texto


def test_texto_do_porque_vazio_sem_dados():
    assert escolha.texto_do_porque({"pdm_escolhido": "PDM.1"}) == ""


def test_sugestoes_sao_o_2o_e_o_3o_lugar_com_motivo():
    sugestoes = escolha.sugestoes_da_linha(
        {"alternativas": [{"pdm": "PDM.4820.004 - VALVULAS ESFERA", "motivo": "se for válvula"},
                          {"pdm": "PDM.5930.012 - PLAQUETA INDICADORA", "motivo": ""}]},
        CATALOGO)
    assert [(p.codigo, r) for p, r in sugestoes] == [
        ("PDM.4820.004", "2º lugar: se for válvula"), ("PDM.5930.012", "3º lugar")]


def test_sugestoes_sem_alternativas_ou_sem_catalogo():
    assert escolha.sugestoes_da_linha({}, CATALOGO) == []
    assert escolha.sugestoes_da_linha({"alternativas": [{"pdm": "PDM.5930.012"}]}, None) == []


def test_juntar_sugestoes_fixa_no_topo_sem_repetir():
    juntos = escolha.juntar_sugestoes([(PLAQUETA, "2º lugar")], [INDICADOR, PLAQUETA], 40)
    assert [p.codigo for p in juntos] == ["PDM.5930.012", "PDM.6685.017"]


def test_juntar_sugestoes_respeita_o_limite():
    assert len(escolha.juntar_sugestoes([(PLAQUETA, "x")], [INDICADOR, VALVULAS], 2)) == 2
```

Em `tests/test_tela_cria_fichas_duas_passadas.py`:

```python
JANELAS = TELA.parent / "janelas.py"


def _classe(nome):
    for no in ast.walk(ast.parse(JANELAS.read_text(encoding="utf-8"))):
        if isinstance(no, ast.ClassDef) and no.name == nome:
            return no
    raise AssertionError(nome)


def _chamadas_em(no):
    return {c.func.attr for c in ast.walk(no)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}


def test_o_seletor_aceita_sugestoes():
    init = next(f for f in _classe("JanelaEscolherPDM").body
                if isinstance(f, ast.FunctionDef) and f.name == "__init__")
    assert "sugestoes" in [a.arg for a in init.args.args + init.args.kwonlyargs]


def test_a_revisao_usa_as_regras_do_servico_para_exibir():
    chamadas = _chamadas_em(_classe("JanelaRevisaoPDM"))
    for regra in ("ordem_para_revisao", "rotulo_de_confianca",
                  "texto_do_porque", "sugestoes_da_linha"):
        assert regra in chamadas, regra


def test_a_revisao_nao_ordena_por_conta_propria():
    nomes = {c.func.id for c in ast.walk(_classe("JanelaRevisaoPDM"))
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "sorted" not in nomes


def test_a_revisao_tem_a_coluna_confianca():
    textos = {no.value for no in ast.walk(_classe("JanelaRevisaoPDM"))
              if isinstance(no, ast.Constant) and isinstance(no.value, str)}
    assert "Confiança" in textos
```

Em `tests/test_cria_fichas_escolha_de_pdm.py`, os dublês de `editar_pdm` passam a imitar a assinatura nova. Troque `_JanelaEscolherFalsa` e `_DfDaRevisaoFalso` por:

```python
class _JanelaEscolherFalsa:
    """Como a de verdade: abrir NÃO bloqueia, e a escolha só existe depois
    que a pessoa clica em "USAR ESTE PDM" -- o que acontece dentro do laço do
    Tk, isto é, no `wait_window` de quem abriu."""

    def __init__(self, parent, catalogo, sugestoes=()):
        self.escolha = None
        self.sugestoes = list(sugestoes)


class _DfDaRevisaoFalso:
    """`df.at[idx, coluna] = valor` vira uma chave `(idx, coluna)`, e
    `df.loc[idx]` devolve a linha como dicionário."""

    def __init__(self, linhas=None):
        self.at = {}
        self.loc = linhas if linhas is not None else {0: {}}
```

No `test_trocar_o_pdm_na_revisao_aplica_o_que_foi_escolhido_na_janela`, a linha da árvore ganha a coluna Confiança (índice 3) e o teste passa a conferir o "MANUAL":

```python
        tree = _ArvoreFalsa(
            {"0": ("0", "VALVULA 2 POL", "PDM.1111.001 - ERRADO", "BAIXA", "VALV", "UN", "MATERIAL")},
            selecao=["0"],
        )
```

e, no fim do teste:

```python
    assert revisao.tree.linhas["0"][3] == "MANUAL", (
        "a confiança era da escolha da IA, e a troca foi da pessoa"
    )
```

E um teste novo, logo depois dele:

```python
def test_o_seletor_abre_com_o_2o_e_o_3o_lugar_da_linha(monkeypatch):
    from sigft.app.views import janelas

    monkeypatch.setattr(janelas, "JanelaEscolherPDM", _JanelaEscolherFalsa)

    class _Revisao:
        tree = _ArvoreFalsa(
            {"0": ("0", "VALVULA", "PDM.1111.001 - X", "BAIXA", "V", "UN", "M")}, selecao=["0"])
        df_dados = _DfDaRevisaoFalso({0: {"alternativas": [
            {"pdm": "PDM.4820.004 - VALVULA ESFERA", "motivo": "se for esfera"}]}})
        catalogo = CATALOGO
        janela = None

        def wait_window(self, janela):
            self.janela = janela   # a pessoa fecha sem escolher

    revisao = _Revisao()
    janelas.JanelaRevisaoPDM.editar_pdm(revisao)

    assert [(p.codigo, r) for p, r in revisao.janela.sugestoes] == [
        ("PDM.4820.004", "2º lugar: se for esfera")]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_escolha.py tests/test_tela_cria_fichas_duas_passadas.py tests/test_cria_fichas_escolha_de_pdm.py -q`
Expected: FAIL nos testes da seção 3, nos guards de `janelas.py` e nos dois testes de `editar_pdm`.

- [ ] **Step 3: Implementar os helpers**

No fim de `sigft/services/cria_fichas_escolha.py`:

```python
# =============================================================================
# O que a tela de revisão mostra (spec §4.6). A tela só exibe o que sai daqui.
# =============================================================================
_PRIORIDADE = {"BAIXA": 1, "MEDIA": 2, "ALTA": 3}
_ROTULOS = {"ALTA": "ALTA", "MEDIA": "MÉDIA", "BAIXA": "BAIXA"}
_ROTULOS_DO_NENHUM = {"ia": "PDM NOVO?", "sem_resposta": "SEM RESPOSTA",
                      "fora_do_catalogo": "FORA DO CATÁLOGO"}
_NOMES_DOS_SINAIS = (("na_busca", "na busca"), ("nome_base", "nome base"),
                     ("caracteristicas", "características"))


def _e_nenhum(valor) -> bool:
    return isinstance(valor, str) and valor.strip().upper() == PDM_NENHUM


def _veio_da_ia(linha) -> bool:
    """A linha passou pelo `preparar_para_revisao`? No modo "Pular IA" o PDM
    vem da planilha, e não há confiança nenhuma a mostrar."""
    return isinstance(linha.get("pdm_ia"), str)


def _sim(valor) -> bool:
    """Verdadeiro para `True` e para o `numpy.True_` que a linha do pandas
    pode entregar (`numpy.True_ is True` é falso)."""
    return str(valor).strip().lower() == "true"


def ordem_para_revisao(linhas) -> list:
    """Em que ordem as linhas aparecem: NENHUM, BAIXA, MEDIA, ALTA. Linha que
    não veio da IA fica por último, sem reordenar. Empate fica na ordem da
    planilha -- a coluna ID continua mostrando o número original."""
    def chave(par):
        posicao, linha = par
        if not _veio_da_ia(linha):
            return (4, posicao)
        if _e_nenhum(linha.get("pdm_escolhido")):
            return (0, posicao)
        return (_PRIORIDADE.get(linha.get("confianca_final"), 4), posicao)
    return [posicao for posicao, _linha in sorted(enumerate(linhas), key=chave)]


def rotulo_de_confianca(linha) -> str:
    if not _veio_da_ia(linha):
        return ""
    if _e_nenhum(linha.get("pdm_escolhido")):
        return _ROTULOS_DO_NENHUM.get(linha.get("origem_do_nenhum"), "PDM NOVO?")
    rotulo = _ROTULOS.get(linha.get("confianca_final"), "")
    if rotulo and _sim(linha.get("rebaixada")):
        rotulo += " ↓"
    return rotulo


def texto_do_porque(linha) -> str:
    """O texto sob a tabela quando uma linha é selecionada."""
    partes = []
    justificativa = linha.get("justificativa")
    if isinstance(justificativa, str) and justificativa.strip():
        partes.append(f"Por quê: {justificativa.strip()}")
    sinais = linha.get("sinais")
    if isinstance(sinais, dict) and sinais:
        partes.append("Conferências: " + " · ".join(
            f"{nome} {'✓' if sinais.get(chave) else '✗'}" for chave, nome in _NOMES_DOS_SINAIS))
    interpretacao = linha.get("interpretacao")
    if isinstance(interpretacao, dict) and interpretacao.get("e"):
        partes.append(f"A IA leu: {interpretacao['e']}")
    return "\n".join(partes)


def sugestoes_da_linha(linha, catalogo) -> list:
    """O 2º e o 3º lugar como `(PDM, rótulo)`, para o seletor de PDM."""
    alternativas = linha.get("alternativas")
    if catalogo is None or not isinstance(alternativas, list):
        return []
    sugestoes = []
    for lugar, alternativa in enumerate(alternativas, start=2):
        alternativa = alternativa if isinstance(alternativa, dict) else {}
        pdm = catalogo.resolver(str(alternativa.get("pdm") or ""))
        if pdm is None:
            continue
        motivo = str(alternativa.get("motivo") or "").strip()
        sugestoes.append((pdm, f"{lugar}º lugar" + (f": {motivo}" if motivo else "")))
    return sugestoes


def juntar_sugestoes(sugestoes, achados, limite) -> list:
    """As sugestões fixas no topo, depois o resto da busca, sem repetir."""
    fixos = [pdm for pdm, _rotulo in sugestoes]
    codigos = {p.codigo for p in fixos}
    return (fixos + [p for p in achados if p.codigo not in codigos])[:limite]
```

- [ ] **Step 4: Implementar a tela**

Em `sigft/app/views/janelas.py`, nos imports:

```python
from sigft.services import cria_fichas_escolha as escolha
```

**`JanelaEscolherPDM`** — assinatura e estado:

```python
    def __init__(self, parent, catalogo, sugestoes=()):
```

logo depois de `self._achados = []`:

```python
        # 2º e 3º lugar da IA, fixos no topo enquanto a busca está vazia.
        self._sugestoes = list(sugestoes or ())
        self._rotulo_da_sugestao = {pdm.codigo: rotulo for pdm, rotulo in self._sugestoes}
```

e troque `_atualizar` por:

```python
    def _atualizar(self):
        procurado = self.entry_busca.get()
        self._achados = self.catalogo.buscar(procurado, limite=self.LINHAS_VISIVEIS)
        com_sugestoes = not procurado.strip() and self._sugestoes
        if com_sugestoes:
            self._achados = escolha.juntar_sugestoes(
                self._sugestoes, self._achados, self.LINHAS_VISIVEIS)
        self.lista.delete(*self.lista.get_children())
        for posicao, pdm in enumerate(self._achados):
            detalhe = "; ".join(pdm.caracteristicas[:6])
            if com_sugestoes and pdm.codigo in self._rotulo_da_sugestao:
                detalhe = "★ " + self._rotulo_da_sugestao[pdm.codigo]
            self.lista.insert("", "end", iid=str(posicao),
                              values=(pdm.completo, pdm.classe, detalhe))
        self.lbl_contagem.configure(
            text=f"{len(self._achados)} PDM(s) na lista"
            + (f" (mostrando os {self.LINHAS_VISIVEIS} primeiros)"
               if len(self._achados) >= self.LINHAS_VISIVEIS else "")
        )
        if self._achados:
            self.lista.selection_set("0")
```

**`JanelaRevisaoPDM`**:

(a) A lista de colunas passa a ser:

```python
        colunas = ["INDEX", "Descrição Original", "PDM Escolhido", "Confiança",
                   "Descrição Curta", "Unidade", "Tipo"]
```

(b) Depois de `self.tree.heading("PDM Escolhido", ...)`:

```python
        self.tree.heading("Confiança", text="Confiança"); self.tree.column("Confiança", width=110)
```

(c) Antes de `self.preencher_tabela()`:

```python
        # O "por quê" da linha selecionada: justificativa, conferências e o que
        # a IA leu do material (spec §4.6).
        self.lbl_porque = ctk.CTkLabel(self, text="", justify="left", anchor="w")
        self.lbl_porque.pack(fill="x", padx=12, pady=(0, 10))
        self.tree.bind("<<TreeviewSelect>>", self._mostrar_porque)
```

(d) Troque `preencher_tabela` por:

```python
    def preencher_tabela(self):
        for item in self.tree.get_children(): self.tree.delete(item)

        # A ORDEM vem do serviço (o que precisa de olho primeiro); a coluna ID
        # continua com o índice original, que é o que liga a linha à planilha.
        indices = list(self.df_dados.index)
        linhas = [row for _index, row in self.df_dados.iterrows()]
        for posicao in escolha.ordem_para_revisao(linhas):
            index, row = indices[posicao], linhas[posicao]
            vals = [
                index,
                row.get('descricao_original', ''),
                row.get('pdm_escolhido', ''),
                escolha.rotulo_de_confianca(row),
                row.get('descricao_curta', ''),
                row.get('unidade', ''),
                row.get('tipo', '')
            ]
            self.tree.insert("", "end", iid=index, values=vals)

    def _mostrar_porque(self, _evento=None):
        selecionados = self.tree.selection()
        texto = ""
        if len(selecionados) == 1:
            texto = escolha.texto_do_porque(self.df_dados.loc[int(selecionados[0])])
        self.lbl_porque.configure(text=texto)
```

(e) Em `editar_pdm`, troque `janela = JanelaEscolherPDM(self, self.catalogo)` por:

```python
            sugestoes = []
            if len(selecionados) == 1:
                sugestoes = escolha.sugestoes_da_linha(
                    self.df_dados.loc[int(selecionados[0])], self.catalogo)
            janela = JanelaEscolherPDM(self, self.catalogo, sugestoes=sugestoes)
```

e, no laço que atualiza a Treeview, depois de `novos_valores[2] = novo_pdm  # Índice 2 é a coluna PDM`:

```python
                novos_valores[3] = "MANUAL"  # a confiança era da escolha da IA
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_cria_fichas_escolha.py tests/test_tela_cria_fichas_duas_passadas.py tests/test_cria_fichas_escolha_de_pdm.py tests/test_frontend_nomes_indefinidos.py tests/test_texto_da_ui.py -q`
Expected: PASS.

- [ ] **Step 6: Verificação da tela (três partes)**

```bash
python -m compileall -q sigft/app/views/janelas.py
python -m pyflakes sigft/app/views/janelas.py
python frontend.py   # abrir; sem display, registrar que fica para o usuario
```

- [ ] **Step 7: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas_escolha.py sigft/app/views/janelas.py \
        tests/test_cria_fichas_escolha.py tests/test_tela_cria_fichas_duas_passadas.py \
        tests/test_cria_fichas_escolha_de_pdm.py
git commit -m "Revisao de PDMs: coluna Confianca, ordem por necessidade, por que e 2o/3o lugar no seletor"
```

---

### Task 13: Registro de calibração

**Files:**
- Modify: `sigft/services/cria_fichas_escolha.py`
- Modify: `sigft/app/views/cria_fichas.py` (`_pos_revisao_concluida`)
- Modify: `tests/test_cria_fichas_escolha.py`, `tests/test_tela_cria_fichas_duas_passadas.py`

**Interfaces:**
- Consumes: `dados_usuario.pasta_logs() -> Path`; as colunas `pdm_ia`, `pdm_escolhido`, `alternativas`, `confianca`, `confianca_final`, `sinais`, `interpretacao`, `descricao_original`, `marca_modelo` (Task 10).
- Produces: `ARQUIVO_DE_CALIBRACAO = "escolha_pdm.jsonl"`; `registro_de_calibracao(linha, data: str) -> dict | None`; `gravar_calibracao(linhas, modelos=None, caminho=None, data=None) -> int` (nunca levanta; 0 quando nada foi gravado).

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_cria_fichas_escolha.py`, junte `import json` aos imports do topo e acrescente no fim:

```python
# =============================================================================
# 4. Calibração: o que a IA disse x o que o usuário escolheu (spec §4.7)
# =============================================================================
def _linha_cal(final, **extra):
    linha = {
        "pdm_ia": "PDM.6685.017 - INDICADOR DIGITAL", "pdm_escolhido": final,
        "alternativas": [{"pdm": "PDM.5930.012 - PLAQUETA INDICADORA", "motivo": "x"},
                         {"pdm": "PDM.4820.004 - VALVULAS ESFERA", "motivo": "y"}],
        "confianca": "ALTA", "confianca_final": "MEDIA",
        "sinais": {"na_busca": True, "nome_base": False, "caracteristicas": False},
        "interpretacao": {"e": "INDICADOR DIGITAL"},
        "descricao_original": "DISPLAY", "marca_modelo": "ACME",
    }
    linha.update(extra)
    return linha


@pytest.mark.parametrize("final,posicao,trocou", [
    ("PDM.6685.017 - INDICADOR DIGITAL", 1, False),
    ("PDM.5930.012 - PLAQUETA INDICADORA", 2, True),
    ("PDM.4820.004 - VALVULAS ESFERA", 3, True),
    ("PDM.1111.111 - OUTRO", 0, True),
])
def test_posicao_do_final(final, posicao, trocou):
    registro = escolha.registro_de_calibracao(_linha_cal(final), "2026-10-08T10:00:00")
    assert registro["posicao_do_final"] == posicao
    assert registro["trocou"] is trocou


def test_nenhum_mantido_conta_como_primeiro_lugar():
    registro = escolha.registro_de_calibracao(
        _linha_cal("NENHUM", pdm_ia="NENHUM", alternativas=[]), "d")
    assert registro["posicao_do_final"] == 1
    assert registro["trocou"] is False


def test_linha_sem_pdm_ia_nao_entra():
    """Modo "Pular IA": não há o que calibrar."""
    assert escolha.registro_de_calibracao({"pdm_escolhido": "PDM.1"}, "d") is None
    assert escolha.registro_de_calibracao({"pdm_ia": float("nan")}, "d") is None


def test_alternativa_em_texto_tambem_conta_na_posicao():
    registro = escolha.registro_de_calibracao(
        _linha_cal("PDM.5930.012 - PLAQUETA INDICADORA",
                   alternativas=["PDM.5930.012 - PLAQUETA INDICADORA"]), "d")
    assert registro["posicao_do_final"] == 2


def test_gravar_calibracao_acrescenta_uma_linha_json_por_item(tmp_path):
    destino = tmp_path / "escolha_pdm.jsonl"
    n = escolha.gravar_calibracao(
        [_linha_cal("PDM.5930.012 - PLAQUETA INDICADORA"), {"pdm_escolhido": "PDM.1"}],
        modelos={"passada_1": "m1", "passada_2": "m2"}, caminho=destino, data="D")
    n2 = escolha.gravar_calibracao([_linha_cal("PDM.6685.017 - INDICADOR DIGITAL")],
                                   caminho=destino, data="D")
    linhas = destino.read_text(encoding="utf-8").splitlines()
    assert (n, n2, len(linhas)) == (1, 1, 2)
    primeiro = json.loads(linhas[0])
    assert primeiro["final"] == "PDM.5930.012 - PLAQUETA INDICADORA"
    assert primeiro["ia"]["confianca_final"] == "MEDIA"
    assert primeiro["modelos"] == {"passada_1": "m1", "passada_2": "m2"}
    assert primeiro["marca"] == "ACME"


def test_gravar_calibracao_nunca_levanta(tmp_path):
    """Um diretório no lugar do arquivo: o registro não pode travar a automação."""
    assert escolha.gravar_calibracao([_linha_cal("X")], caminho=tmp_path, data="D") == 0


def test_gravar_calibracao_sem_nada_para_gravar(tmp_path):
    destino = tmp_path / "x.jsonl"
    assert escolha.gravar_calibracao([{"pdm_escolhido": "PDM.1"}], caminho=destino) == 0
    assert not destino.exists()
```

Em `tests/test_tela_cria_fichas_duas_passadas.py`:

```python
def test_a_tela_grava_a_calibracao_ao_confirmar_a_revisao():
    for no in ast.walk(ast.parse(TELA.read_text(encoding="utf-8"))):
        if isinstance(no, ast.FunctionDef) and no.name == "_pos_revisao_concluida":
            assert "gravar_calibracao" in _chamadas_em(no)
            return
    raise AssertionError("_pos_revisao_concluida sumiu")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cria_fichas_escolha.py tests/test_tela_cria_fichas_duas_passadas.py -q`
Expected: FAIL — `AttributeError: ... no attribute 'registro_de_calibracao'` e o guard.

- [ ] **Step 3: Implementar**

Em `sigft/services/cria_fichas_escolha.py`, nos imports:

```python
import json
from datetime import datetime
from pathlib import Path

from sigft.core import dados_usuario
```

E no fim do arquivo:

```python
# =============================================================================
# Calibração (spec §4.7): o que a IA disse x o que o usuário escolheu
# =============================================================================
ARQUIVO_DE_CALIBRACAO = "escolha_pdm.jsonl"


def registro_de_calibracao(linha, data) -> dict | None:
    """Uma linha do registro, ou `None` quando a linha não veio da IA."""
    pdm_ia = linha.get("pdm_ia")
    if not isinstance(pdm_ia, str):
        return None
    final = str(linha.get("pdm_escolhido") or "")
    alternativas = linha.get("alternativas")
    alternativas = alternativas if isinstance(alternativas, list) else []
    opcoes = [normalizar(pdm_ia)] + [
        normalizar(str((a.get("pdm") if isinstance(a, dict) else a) or ""))
        for a in alternativas]
    alvo = normalizar(final)
    sinais = linha.get("sinais")
    interpretacao = linha.get("interpretacao")
    return {
        "data": data,
        "descricao": str(linha.get("descricao_original") or ""),
        "marca": str(linha.get("marca_modelo") or ""),
        "interpretacao": interpretacao if isinstance(interpretacao, dict) else {},
        "ia": {
            "pdm": pdm_ia,
            "confianca": str(linha.get("confianca") or ""),
            "confianca_final": str(linha.get("confianca_final") or ""),
            "sinais": sinais if isinstance(sinais, dict) else {},
            "alternativas": alternativas,
        },
        "final": final,
        "trocou": alvo != normalizar(pdm_ia),
        "posicao_do_final": opcoes.index(alvo) + 1 if alvo in opcoes else 0,
    }


def gravar_calibracao(linhas, modelos=None, caminho=None, data=None) -> int:
    """Acrescenta uma linha JSON por item vindo da IA. Devolve quantas.

    NUNCA levanta: o registro existe para medir a confiança com o tempo, e
    não pode travar a automação que vem depois da revisão."""
    data = data or datetime.now().isoformat(timespec="seconds")
    registros = []
    for linha in linhas:
        registro = registro_de_calibracao(linha, data)
        if registro is not None:
            registro["modelos"] = dict(modelos or {})
            registros.append(registro)
    if not registros:
        return 0
    try:
        destino = Path(caminho) if caminho else dados_usuario.pasta_logs() / ARQUIVO_DE_CALIBRACAO
        with open(destino, "a", encoding="utf-8") as arquivo:
            for registro in registros:
                arquivo.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    except OSError:
        return 0
    return len(registros)
```

Em `sigft/app/views/cria_fichas.py`, nos imports (junto de `from sigft.services import cria_fichas as cria_fichas_svc`):

```python
from sigft.services import cria_fichas_escolha
```

E em `_pos_revisao_concluida`, logo depois de `self.df_processed = df_atualizado`:

```python
        # [2026-10-08] O que a IA disse x o que a revisão decidiu, para a
        # confiança virar medição (spec §4.7). Nunca trava a automação.
        try:
            registrados = cria_fichas_escolha.gravar_calibracao(
                [row for _index, row in df_atualizado.iterrows()],
                modelos=getattr(self, "_modelos_da_ia", None),
            )
            if registrados:
                self.log(f"Calibração: {registrados} itens registrados.")
        except Exception as e:
            self.log(f"Calibração não registrada: {e}")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cria_fichas_escolha.py tests/test_tela_cria_fichas_duas_passadas.py tests/test_texto_da_ui.py -q`
Expected: PASS.

- [ ] **Step 5: Verificação da tela (três partes)**

```bash
python -m compileall -q sigft/app/views/cria_fichas.py
python -m pyflakes sigft/app/views/cria_fichas.py
python frontend.py   # sem display, registrar que fica para o usuario
```

- [ ] **Step 6: Commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add sigft/services/cria_fichas_escolha.py sigft/app/views/cria_fichas.py \
        tests/test_cria_fichas_escolha.py tests/test_tela_cria_fichas_duas_passadas.py
git commit -m "Cria Fichas: registro de calibracao da escolha de PDM (escolha_pdm.jsonl)"
```

---

### Task 14: Documentação

**Files:**
- Modify: `docs/base-conhecimento/01-cria-fichas-backend.md` (seção nova no fim)
- Modify: `docs/refatoracao/PENDENCIAS.md` (a entrada "2026-09-23 — o catálogo de PDMs é reenviado inteiro em cada bloco")
- Modify: `CLAUDE.md` (mural)
- Modify: `docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md` (status)

- [ ] **Step 1: Base de conhecimento**

No fim de `docs/base-conhecimento/01-cria-fichas-backend.md`:

```markdown
## 2026-10-08 — a escolha de PDM em duas passadas

Spec: `docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md`.

1. **Passada 1** (`GeminiCategorizer.interpretar_lote`, tarefa `interpretar_material`):
   uma chamada por lote (fatias de 60), sem catálogo, devolve por item o que o
   material É (`e`), sinônimos e a que ele serve. Falhou → o lote segue com a
   busca de hoje e uma linha de log; nunca derruba.
2. **Busca** (`CatalogoPDM.candidatos_em_duas_frentes`): 8 vagas pela
   interpretação, 4 pela descrição crua (a de hoje, intacta); uma frente que
   rende pouco cede a vaga.
3. **Passada 2** (`categorizar_pdm`): cada item leva a linha "Interpretação";
   a resposta traz `confianca`, `alternativas` (`{"pdm", "motivo"}`),
   `justificativa` e `caracteristicas_que_confirmam`. NENHUM só para "PDM novo".
4. **Revisão** (`preparar_para_revisao`, no serviço — saiu da tela): guarda
   contra PDM inventado, três sinais (na busca, nome base, características) e
   o rebaixamento do ALTA sem conferência. A tela mostra a coluna Confiança
   (o NENHUM diz a causa: PDM NOVO?, SEM RESPOSTA ou FORA DO CATÁLOGO),
   ordena NENHUM → BAIXA → MÉDIA → ALTA e oferece o 2º/3º lugar no seletor.
   No modo "Pular IA" nada disso aparece, e a ordem é a da planilha.
5. **Calibração**: ao confirmar a revisão, uma linha por item em
   `Documentos\SIG-FT\logs\escolha_pdm.jsonl` (IA × escolha final).

Regras puras em `services/cria_fichas_escolha.py`.
```

- [ ] **Step 2: PENDENCIAS**

Na entrada `## 2026-09-23 — o catálogo de PDMs é reenviado inteiro em cada bloco`, logo abaixo do título:

```markdown
> ✅ **Feito em 2026-10-08** (escolha de PDM em duas passadas): lista e
> exemplos vêm antes do manual, e o prefixo é igual em todos os blocos, provado
> em `tests/test_prompt_categorizar_pdm.py::test_o_que_vem_antes_do_manual_e_igual_em_todos_os_blocos`.
> A ressalva 2 abaixo (comparar a escolha antes × depois) é a validação §7 da
> spec, na máquina do usuário. Os blocos em paralelo continuam abertos.
```

- [ ] **Step 3: Mural do `CLAUDE.md`**

O mural tem 5 avisos: mova o mais antigo para a seção "Arquivado do mural do `CLAUDE.md`" do `PENDENCIAS.md` (regra 2 do mural) e acrescente:

```markdown
| 2026-10-08 | Luan | 🔴 **`prompts.py`: `categorizar_pdm` reescrito (duas passadas) e prompt novo `interpretar_material`; `LLM_TASKS` ganhou `interpretar_material`.** Fixture `cria_fichas_prompt.txt` regerada com aval. Nenhum prompt do AutoSpec mudou.<br>Spec: `docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md`. |
```

- [ ] **Step 4: Status da spec**

Troque a linha `**Status:**` da spec por:

```markdown
**Status:** implementado em 2026-10-08 (plano `docs/superpowers/plans/2026-10-08-escolha-de-pdm-em-duas-passadas.md`); aguardando a validação na máquina do usuário (§7).
```

- [ ] **Step 5: Verificação final e commit**

```bash
bash scripts/check.sh && python -m ruff check .
git add docs/ CLAUDE.md
git commit -m "Docs: escolha de PDM em duas passadas (base de conhecimento, pendencias, mural, spec)"
```

---

## Depois do plano (só na máquina do usuário — spec §7)

1. Abrir o app e conferir a tela de revisão (coluna Confiança, "por quê", sugestões).
2. Rodar o lote de 63 itens **até a revisão**, sem criar fichas: contar `PDM NOVO?`, acerto do 1º lugar, acerto em 2º/3º, e os dois casos reais.
3. Custo e tempo no painel "Gastos de IA", antes × depois.
4. Versão: PATCH, via rc, com a skill `sigft-lancar-versao`.

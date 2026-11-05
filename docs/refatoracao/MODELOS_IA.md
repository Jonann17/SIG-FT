# Seleção de Modelos de IA — SIG-FT

> Documento de decisão que define o **modelo padrão** e os **overrides por módulo** do
> SIG-FT. Consumido pela Fase 3 da refatoração: `config.LLM_TASKS` (CP 1.1/3.1), o seletor de
> modelo na UI (CP 3.3) e a tabela de preços do `UsageTracker` (CP 3.4). Preços mudam — os
> números aqui são de **julho/2026** e devem ser reconfirmados na implementação (são dados
> editáveis em `config.py`, não código).

## 1. Perfil real de cada tarefa (base para a escolha)

Extraído da base de conhecimento e do código dos backends. O que importa para custo×qualidade:

| Tarefa (`LLM_TASKS`) | Módulo | O que exige | Volume | Sensível a |
|---|---|---|---|---|
| `categorizar_pdm` | cria_fichas | Classificar itens contra vocabulário controlado (PDM) lendo manual de regras + lista de PDMs + 8 few-shot. **Raciocínio.** JSON em lote. | **Baixo** — 1 chamada em lote por projeto | qualidade do raciocínio; input grande |
| `validar_ficha` | analyzer | Juiz semântico: resposta é relevante/aplicável? VALIDO/INVALIDO por campo. | **Baixo** — *rate-limit de 60s* entre chamadas por design | qualidade de julgamento |
| `condicoes` | upload_conditions | Traduzir PT↔ES + conversão de unidades + enriquecimento legal + checagem de coerência. System prompt de 15 regras. JSON grande. | **Alto** — 1 por ficha, lotes | **PT/ES**, JSON, raciocínio; **custo/chamada** |
| `tech_specs` | upload_tech_specs | Normalizar características (CHAR/INT/NUM/LISTA) + unidades + decimais + PT/ES. JSON em lista. | **Alto** — 1 por ficha, lotes | JSON estrito, **custo/chamada**; mais mecânico |
| `autospec` | autospec | RAG: ler manuais (50–60k chars) + gerar specs por boas práticas. | **Médio/baixo** | **custo de input** (contexto longo); qualidade de geração |

Fatos que orientam a decisão para **este** projeto:
- **PT↔ES é função central** (`condicoes` e `tech_specs`): Gemini e GPT são fortes em línguas
  ibéricas; DeepSeek/Qwen são mais fracos e são provedores chineses → **preocupação de
  residência de dados** para material industrial da GE Vernova (já registrada em PENDENCIAS).
- **JSON estruturado confiável** importa em tudo: Gemini tem JSON mode nativo
  (`response_mime_type`), já usado no código — vantagem real de confiabilidade.
- **Erros propagam para fichas oficiais da Itaipu** → não cortar qualidade demais nas tarefas
  de raciocínio.
- O que o código roda **hoje** já é caro sem necessidade: `categorizar_pdm`/`validar_ficha`/
  `autospec` em **Gemini 3.1 Pro** (US$2/US$12) e `condicoes`/`tech_specs` em **Gemini 3.5
  Flash** (US$1,50/US$9) — ambos são o tier *premium* de cada família.

## 2. Score × preço (fonte: aimultiple, tabela do usuário — jul/2026)

Score = benchmark de capacidade **geral** (um número agregado). Preços em US$ por 1M tokens.
Coluna "Provedor/confiança" marca o que importa para dado industrial GE Vernova: 🟢 provedor
ocidental / 🔴 provedor chinês (residência de dado). Ordenado por relevância para a decisão.

| Modelo | Score | Input | Output | Provedor / nota |
|---|---|---|---|---|
| **Gemini 3 Flash Preview** | 67 | 0,50 | 3,00 | 🟢 Google — **← padrão recomendado** (PT/ES+JSON nativos) |
| MiniMax M3 | 66 | 0,30 | 1,20 | 🔴 MiniMax — mais barato com score alto; **economia máxima (opt-in)** |
| **Grok 4.5** | 86 | 2,00 | 6,00 | 🟢 xAI — **← tier "poder de decisão"** (melhor que Gemini Pro) |
| Qwen3 235B Thinking | 51 | 0,45 | 1,82 | 🔴 Alibaba — barato, score baixo |
| GPT-5 Mini | 54 | 0,25 | 2,00 | 🟢 OpenAI — barato e confiável, score baixo |
| Kimi K2.6 | 60 | 0,75 | 3,20 | 🔴 Moonshot |
| GPT-5.6 Luna | 65 | 1,00 | 6,00 | 🟢 OpenAI |
| Claude Sonnet 5 | 76 | 2,00 | 10,00 | 🟢 Anthropic — forte, output caro |
| Gemini 3.1 Pro Preview | 77 | 2,00 | 12,00 | 🟢 *usado hoje* em 3 tarefas — Grok 4.5 domina (86 @ $6) |
| Gemini 3.5 Flash | 59 | 1,50 | 9,00 | 🟢 *usado hoje* em condicoes/tech_specs — caro p/ o score |
| Gemini 2.5 Pro | 52 | 1,25 | 10,00 | 🟢 score baixo nesta bancada |
| Kimi K3 | 89 | 3,00 | 15,00 | 🔴 topo de score, output caro |
| GPT-5.6 Sol | 87 | 5,00 | 30,00 | 🟢 frontier caro |
| Claude Fable 5 | 92 | 10,00 | 50,00 | 🟢 topo absoluto, custo proibitivo p/ lote |

> **Correção de rota**: a v1 deste doc recomendava *Gemini 2.5 Flash* — modelo que **nem
> aparece nesta bancada** e foi superado pela linha Gemini 3 Flash. Recomendação revista
> abaixo com os dados reais da tabela.

## 3. Decisão: padrão, economia máxima e tier de poder

Três posições, todas trocáveis na UI (CP 3.3):

### PADRÃO (standard global): **Gemini 3 Flash Preview** (~$0,50/$3,00, score 67)

Por que este e não o M3 (que é mais barato e pontua quase igual):
- **Empate técnico de score** com o M3 (67 vs 66) — a decisão vai para os fatores que o score
  agregado não mede: **PT/ES nativo** (função central do SIG-FT), **JSON mode nativo** (já
  usado no código) e **residência de dado** (Google 🟢 vs MiniMax 🔴, para material industrial
  GE Vernova). Por US$1,80 a mais por 1M de output, você fica no provedor confiável e na
  família já validada. Diferença de custo irrelevante no volume do projeto.
- **vs o que roda hoje** (3.5 Flash $1,50/$9 e 3.1 Pro $2/$12): mais barato **e** mais bem
  pontuado que o 3.5 Flash (67 vs 59), a **1/3 do output**.

### ECONOMIA MÁXIMA (opt-in): **MiniMax M3** (~$0,30/$1,20, score 66)

Você está certo: no papel é o melhor score×preço da tabela. Fica disponível na UI e é a
escolha recomendada quando o custo for crítico **e** o lote não for sensível — bom candidato
para `tech_specs` (mais mecânico). Trade-offs a validar antes de adotar: provedor chinês 🔴
(dado), e PT/ES + confiabilidade de JSON **não verificados** no nosso caso (medir no A/B do
CP 3.3). Não é o default por causa do dado, não por causa do preço.

### PODER DE DECISÃO: **Grok 4.5** (~$2/$6, score 86) ← sua sugestão, adotada

Melhor que a minha proposta anterior (era Gemini 2.5/3.1 Pro). Grok 4.5 **domina** o Gemini
3.1 Pro nesta bancada: score 86 vs 77 e output pela metade ($6 vs $12), provedor ocidental 🟢.
Vira o tier de qualidade e o default de `categorizar_pdm` (raciocínio, lote raro → custo
absoluto irrisório).

### Config recomendada (pré-semear em `config.LLM_TASKS`)

Os ids abaixo são ilustrativos; confirmar os slugs reais no catálogo do OpenRouter na
implementação (ex.: `google/gemini-3-flash-preview`, `x-ai/grok-4.5`, `minimax/minimax-m3`).

```python
LLM_DEFAULT = {"provider": "gemini", "model": "gemini-3-flash-preview"}   # padrão global

LLM_TASKS = {
    # tarefa            provider    modelo                    # racional
    "categorizar_pdm": ("xai",     "grok-4.5"),               # raciocínio; lote raro; 86 @ $2/$6
    "validar_ficha":   ("gemini",  "gemini-3-flash-preview"), # juiz; rate-limit 60s → baixo volume
                                                              #   (subir p/ grok-4.5 se exigir)
    "condicoes":       ("gemini",  "gemini-3-flash-preview"), # alto volume; subir p/ grok-4.5 se
                                                              #   coerência/enriquecimento degradar
    "tech_specs":      ("gemini",  "gemini-3-flash-preview"), # mecânico; economia máx → minimax-m3
    "autospec":        ("gemini",  "gemini-3-flash-preview"), # RAG; subir p/ modelo forte se precisar
}
```

### Espectro na interface

- **Economia máxima** (lote não sensível): MiniMax M3, ou GPT-5 Mini para quem quiser 🟢 barato.
- **Padrão**: Gemini 3 Flash Preview.
- **Poder de decisão**: Grok 4.5 (melhor custo-benefício de topo); Claude Sonnet 5 / Kimi K3
  como alternativas de score alto se o caso pedir.

> Lembrete: o score é proxy **geral**. Para o SIG-FT o que decide é PT→ES limpo + JSON válido —
> por isso o CP 3.3 exige A/B numa amostra antes de trocar o default. Um número só não fecha
> a conta de uma ficha oficial.

## 4. Impacto de custo esperado

Saindo do setup atual (3 tarefas em 3.1 Pro $2/$12 + 2 em 3.5 Flash $1,50/$9) para o
recomendado (Gemini 3 Flash Preview $0,50/$3 em quase tudo; `categorizar_pdm` em Grok 4.5
$2/$6): como o **output** domina o custo em geração/JSON, a queda é de **~3× no output** das
tarefas de alto volume (`condicoes`/`tech_specs`: $9→$3) e de **2×** na tarefa de raciocínio
($12→$6) com **ganho de qualidade** (score 77→86). Na prática, redução de custo de IA na casa
de **60–70%** e, em alguns módulos, com resultado melhor. Puxando `tech_specs` para o M3, a
economia sobe mais. Os números reais aparecem no `UsageTracker` (CP 3.4), com custo efetivo do
OpenRouter.

## 5. Como isto entra na refatoração (sem downgrade silencioso)

- **CP 3.1** migra a camada de IA **preservando os modelos de hoje** (3.5 Flash / 3.1 Pro) —
  prova que a abstração `LLMClient` é equivalente, com zero mudança de comportamento.
- **CP 3.3** aplica os **defaults** desta página (Gemini 3 Flash Preview global; Grok 4.5 em
  `categorizar_pdm`) ao expor o seletor na UI, e o usuário **valida a qualidade num punhado de
  fichas (A/B)** antes de adotar — em especial se testar MiniMax M3 para `tech_specs`, onde
  PT/ES e JSON precisam ser confirmados. Nada de rebaixar em silêncio.
- **CP 3.4** semeia a tabela de preços (seção 2) para estimar custo dos provedores diretos; via
  OpenRouter o custo é real.

Fonte primária dos scores/preços: tabela **aimultiple/llm-pricing** (jul/2026) fornecida pelo
usuário. Preços de mercado cruzados com:
[BenchLM LLM pricing](https://benchlm.ai/llm-pricing) ·
[Morph LLM API compare](https://www.morphllm.com/llm-api) ·
[OpenRouter](https://openrouter.ai/models)

## 6. IA por módulo (2026-11-04)

Pedido do Luan: a escolha é **por módulo**, com três modos. **IA Externa** é o OpenRouter (o que este documento descreve: catálogo, favoritos, custo real). **IA Interna (AMP)** aparece desligada até o AMP ter API. **Workflow AMP** manda o prompt ao webhook do n8n daquele módulo (`AMP_IA_<TAREFA>_URL`/`_CHAVE`) e devolve o texto, sem repetição. O modo é derivado da seleção por tarefa (`_modelos_ia.por_tarefa`): o provedor `amp_workflow` é o workflow, qualquer outro é a IA Externa. O seletor global "Modelo padrão (avançado)" saiu em 2026-11-05 (o global que já estava salvo continua valendo para a tarefa sem escolha por módulo). Contrato do workflow e telas: `docs/superpowers/specs/2026-11-04-ia-por-modulo-design.md`.


## 2026-11-05 — sem depender da chave do Gemini

Pedido do Luan ("tirar que dependa sim ou sim da chave do Gemini"). Onde a chave era exigida à força:

1. **Cria Fichas** (`services/cria_fichas.py`, `classificar_para_revisao` e `processar_lote`): `if not self.api_key: raise ValueError("API Key não configurada.")`, com `api_key` = chave do Gemini, em QUALQUER modo. Agora `_exigir_chave` só exige quando o provedor resolvido é o Gemini direto.
2. **O padrão de quem nunca escolheu** (`LLM_MODELOS_HOJE`/`LLM_TASKS`) é Gemini direto. `get_llm` (`_padrao_pela_chave`), sem seleção salva, sem a chave do Gemini e COM a do OpenRouter, usa o mesmo modelo pelo OpenRouter (`google/<modelo>`). Com a chave do Gemini nada muda.
3. **AutoSpec** (zona do Rafael, não alterado): resolve a seleção por conta própria e passa `selecao_resolvida` ao `get_llm`, então o item 2 não o alcança; sem escolha salva, ele ainda pede a chave do Gemini. Aviso no mural.

---
tags: [sigft, ia]
---

# SIG-FT — Camada de IA

## A decisão de produto

Do `PLANO_REFATORACAO.md`, decisão de 24/07/2026:

> Camada de IA **generica e plugavel**, com **troca de modelo pela interface**.
> **OpenRouter e o gateway padrão** — uma única chave da acesso a Gemini, GPT, Kimi,
> DeepSeek etc., fornece o catalogo de modelos para a UI e devolve o **custo REAL**
> de cada chamada.

Dois caminhos diretos ficam disponiveis:
- **Gemini nativo** — preserva comportamento e free tier atuais, sem intermediario.
  Útil para **conteudo sensivel**.
- **Endpoint OpenAI-compativel genérico** — para a futura IA interna da empresa.

Estratégia de chaves: **todas opcionais, uma necessária**. No dia a dia basta
`OPENROUTER_API_KEY`; a UI só exibe provedores com chave configurada.

Inclui **rastreamento de gastos** por chamada, modelo e módulo (`core/llm/usage.py`).

## Como o modelo e escolhido

`config.py` tem dois dicionarios que não devem ser confundidos:

| Dicionario | O que e |
|---|---|
| `LLM_MODELOS_HOJE` | os modelos que o código **roda hoje**, por tarefa. Baseline de equivalencia — **não e o alvo** |
| `LLM_DEFAULT` / `LLM_TASKS` | os modelos **decididos** (padrão global + override por tarefa), conforme `docs/refatoracao/MODELOS_IA.md` |

Provedores registrados: `gemini`, `xai`, `openrouter`, `openai_compat`.

> [!important] Regra de manutenção
> **Trocar o modelo de um módulo e editar `config.py` ou usar o seletor da Home.
> Nunca editar o módulo.** Um serviço que sabe o nome do modelo quebrou o principio 4
> da [[SIG-FT - Arquitetura|arquitetura]].

## As tarefas de IA, uma a uma

| Tarefa | Módulo | O que a IA decide |
|---|---|---|
| `categorizar_pdm` | Criar Fichas | qual dos ~1174 PDMs descreve o material; descrição curta; origem; tipo; unidade |
| `analisar_ficha` | Analyzer | se cada campo esta valido; nota 0-100% |
| `condicoes` | Upload Condições | estruturar as 4 abas de condições a partir das células da ficha |
| `tech_specs` | Upload Specs | normalizar cada característica: tipo, unidade, formato |
| `autospec` | AutoSpec AI | preencher campo vazio a partir de RAG sobre datasheets e web |

## A lição mais cara do projeto: a REGRA 0

> [!danger] A IA inventou norma que o fornecedor não escreveu
> Até 18/08/2026 o prompt do módulo de Condições mandava *"enriquecer com legislacao"*
> e auto-corrigir a classificação `perigoso_10004` (NBR 10004). Resultado: a IA
> **preencheu norma ambiental que o fornecedor nunca declarou**.
>
> isso é grave num processo onde a ficha e documento contratual entregue a um cliente
> binacional, e a seção de descarte referência legislacao brasileira e paraguaia.

A correção foi a **REGRA 0 — fidelidade ao fornecedor**, soberana sobre todas as
outras: a IA **normaliza e formata o que a fonte diz; não acrescenta o que ela não diz**.

Fonte de verdade: `sigft/core/llm/prompts.py` -> `SYSTEM_CONDICOES`.

> [!tip] O principio generalizavel
> Em automação documental, **"melhorar" e um bug**. O valor da automação e transcrever
> fielmente em escala — não ter opinião. Todo prompt novo deste app deve dizer
> explicitamente o que a IA **não** pode inventar.
> Ver [[Secao - Condicoes]] e [[Diagnostico - Riscos]].

## A segunda lição: a hipotese plausivel e errada

Registrada no `CLAUDE.md`, 12/08/2026: investigando por que a busca web do AutoSpec não
achava datasheets, a primeira hipotese (o nome do fabricante poluindo a query) era
plausivel e **errada**. O teste mostrou que a query funcionava e que o problema estava
no **filtro, três camadas adiante**.

Por isso o repositorio adota `systematic-debugging` como skill obrigatória: **testar a
hipotese antes de corrigir**.

## O AutoSpec AI (RAG)

O módulo mais sofisticado. Preenche campos vazios da ficha:
1. identifica campos vazios pelo `CONFIG_MAP`;
2. recupera contexto de **documentos locais** (PDF/HTML, via LlamaParse) e de
   **busca web** (Google Custom Search, respeitando `robots.txt` — `core/web/robots.py`);
3. consulta o modelo;
4. escreve na planilha com **fonte azul** (`0000FF`) e sufixo `_completed` no arquivo.

A fonte azul e a marca de "isto foi gerado, confira" — rastreabilidade visual barata.

`GENERATIVE_FIELDS` limita **quais campos** a IA pode gerar por boas praticas quando
não ha dado explicito: empilhamento, embalagem de transporte, transporte, preservacao,
método de limpeza, ferramentas, tipo de legislacao, tipo de descarte, proteção, posição
de armazenamento, unidade, tipo. **Os demais campos exigem fonte.**

## Relacionados
[[SIG-FT - Modulos]] · [[Secao - Condicoes]] · [[Diagnostico - Riscos]]

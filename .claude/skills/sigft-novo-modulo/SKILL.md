---
name: sigft-novo-modulo
description: Criar um novo módulo no SIG-FT a partir de uma ideia do usuário. Usar quando o usuário descrever uma nova funcionalidade/tela/automação para o sistema de fichas técnicas ("quero um módulo que...", "adicionar uma tela para...", "automatizar X no portal"). Guia o entendimento da estrutura do projeto e a implementação seguindo as convenções existentes.
---

# Criar um novo módulo no SIG-FT

## Passo 1 — Entender a ideia (antes de qualquer código)

Extraia da conversa (pergunte apenas o que não estiver claro):
- **Entradas**: quais planilhas/arquivos o módulo lê? (aba? colunas-chave? formato do código PMIB?)
- **Saídas**: gera arquivos? escreve no `_STATUS_PMIB`? age no portal PMIB?
- **Usa RPA?** (portal https://apps.itaipu.gov.br/PMIB) — se sim, quais telas/abas do portal
- **Usa IA?** — se sim, qual tarefa (classificar, validar, traduzir, gerar) e que estrutura de resposta
- **Interação**: precisa de seleção de itens, revisão antes de executar, botão parar, pausa para login?

## Passo 2 — Mapear o terreno

1. Leia `docs/README.md` e `docs/refatoracao/PLANO_REFATORACAO.md` §2 (arquitetura-alvo) e §6
   (status — diz o quanto da refatoração já aconteceu).
2. Detecte o estado real da árvore:
   - **Se `sigft/` existe com `core/`**: o módulo novo nasce como `sigft/services/<nome>.py`
     + `sigft/app/views/<nome>.py`, usando `core/` (PMIBPortal, LLMClient/get_llm, StatusPMIB,
     normalize_pmib, find_header_row, UICallbacks). NÃO reimplemente nada que exista em `core/`.
   - **Se ainda é a estrutura plana** (`*_backend.py` na raiz): o módulo nasce como
     `<nome>_backend.py` + classe `Modulo<Nome>` no `frontend.py`, imitando o módulo análogo
     mais próximo.
3. Leia o doc da base de conhecimento do módulo mais parecido com a ideia
   (`docs/base-conhecimento/`) — ele descreve o padrão a seguir. Análogos por tipo:
   - RPA simples no portal → `10-apagar-lmr-backend.md`
   - RPA de preenchimento com dados de Excel → `09-lmr-backend.md` ou `05-upload-conditions-backend.md`
   - Pipeline IA → RPA → `06-upload-tech-specs-backend.md`
   - Só Excel/arquivos → `02-pdm-backend.md` ou `12-search-pmib-backend.md`
   - Gestão/KPIs → `11-pmib-manager-backend.md`

## Passo 3 — Convenções obrigatórias do projeto

- **Separação**: serviço nunca importa tkinter; view nunca contém regra de negócio.
  Comunicação por callbacks: `log(msg[, nivel, contexto])`, `pause(motivo)`, `ask(...)`,
  `progress(fração)`.
- **Threading na UI**: trabalho pesado em `threading.Thread(daemon=True)`; toda atualização
  de widget via `self.after(0, ...)`.
- **Logs** (padrão do CP 4.4 do plano): início de lote (o quê/quantos), linha por item
  (id + resultado ✅/⚠️/❌ + motivo), resumo final (sucessos/falhas/pulados/tempo).
- **Código PMIB**: sempre normalizar (apóstrofo, 4 casas após o ponto). Use a implementação
  única (`core/excel/pmib_codes.py` se existir; senão copie o comportamento de
  `upload_conditions_backend.carregar_lookup_status`).
- **Excel**: cabeçalho é dinâmico — nunca assuma linha fixa; trate `PermissionError`
  (arquivo aberto) com retry via callback.
- **Diálogos de arquivo**: nunca chame `filedialog` direto — use os wrappers com memória de
  caminho (`sigft/app/file_dialogs.py` + `sigft/core/prefs.py`, CP 1.5 do plano), informando
  a categoria (`excel`/`pdf`/`json`/`pasta`) e uma chave própria do campo (ex.:
  `"meumodulo.ficha"`), para que cada seletor reabra na última pasta usada daquele contexto.
  Se o campo corresponder a uma pasta padrão conhecida (SOBRESSALENTES - PMIB, PDMs
  modificados, Templates), pré-preencha a partir de `get_default_dir()`.
- **RPA**: login é manual (pausa aguardando o usuário); botão PARAR via flag
  `solicitar_parada()`; nunca invente seletores sem validar com o usuário no portal real.
- **IA**: nunca chame SDK de provedor direto se `core/llm/` existir — use `get_llm(tarefa)` e
  registre a tarefa em `config.LLM_TASKS`; prompts em `core/llm/prompts.py`.
- **Estilo visual**: paleta `COLORS` (GE Vernova), Roboto, layout header/conteúdo/console,
  botões de arquivo que ficam verdes (`COLORS["primary"]`) após seleção. Copie a estrutura
  visual de uma view existente — não crie estilo novo.

## Passo 4 — Registrar o módulo na aplicação

Estrutura plana (atual): 1) criar `<nome>_backend.py`; 2) adicionar variável global +
entrada na lista `modulos_para_carregar` da `SplashScreen.carregar_modulos`; 3) criar a
classe `Modulo<Nome>` no `frontend.py`; 4) registrar em `self.frames[...]` no `SIG_FT_App`;
5) adicionar botão na sidebar (`_criar_botao_menu`, na seção certa); 6) opcional: card na
`HomeView`.

Estrutura em pacote (pós-refatoração): 1) `sigft/services/<nome>.py`; 2)
`sigft/app/views/<nome>.py` herdando `ModuleFrame`; 3) registrar no `app/main.py`
(sidebar + frames); 4) config nova em `sigft/config.py` se necessário.

## Passo 5 — Fechar

1. `python -m py_compile` em tudo que tocou; rode `tests/` se existirem.
2. Documente: dispare o agente `doc-writer` para criar
   `docs/base-conhecimento/<NN>-<nome>.md` do módulo novo (próximo número livre).
3. Atualize `docs/README.md` (tabela de docs) e, se relevante, `README.md` raiz.
4. Commit com mensagem `Novo módulo: <nome> — <resumo de 1 linha>`.
5. Se o módulo usa RPA: avise o usuário que a validação precisa ser feita por ele no portal
   real, e ofereça um roteiro de teste (passo a passo do que clicar/conferir).

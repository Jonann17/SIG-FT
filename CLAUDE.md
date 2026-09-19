# SIG-FT — instruções para o Claude

Aplicativo desktop (Python + CustomTkinter) que automatiza a gestão de fichas técnicas de
materiais sobressalentes do projeto Itaipu: criação de fichas no Portal PMIB, RPA no portal,
geração de planilhas e módulos de IA sobre as fichas.

---

## ⚠️ LEIA PRIMEIRO — duas pessoas estão mexendo no projeto ao mesmo tempo

| Pessoa | Frente |
|---|---|
| **Luan** (`luanccozer`, dono do repo) | refatoração geral, seguindo `docs/refatoracao/PLANO_REFATORACAO.md` |
| **Rafael** (`rafhagmm`) | **apenas o módulo AutoSpecAI** |

**O contrato de fronteiras está em [`docs/refatoracao/TRABALHO_PARALELO.md`](docs/refatoracao/TRABALHO_PARALELO.md).
Leia antes de editar qualquer coisa.** Ele diz quais arquivos são de quem, o que está
congelado e como resolver os conflitos previsíveis.

O resumo que não pode ser esquecido:

- ✅ **CP 7.3 LIBERADO em 2026-08-26.** O AutoSpecAI está mergeado e a Etapa 3b do roteiro
  rodou numa máquina real. **Leia `TRABALHO_PARALELO.md` §3.1 antes de executar** — as telas
  `ModuloAutoSpec` e `ModuloAnalyzer` cresceram, e o documento lista o que precisa viajar
  junto com cada uma.
- ⛔ **Não use o AutoSpec como tela piloto** de nenhum checkpoint da Fase 7.
- 🟢 **São do Rafael:** `sigft/services/autospec.py` + `autospec_conferencia.py`,
  `autospec_rag.py`, `autospec_embeddings.py`, `autospec_unidades.py`, `autospec_backend.py`,
  `sigft/core/web/`, `class ModuloAutoSpec` no `frontend.py` (~linhas 3077–3508 —
  **confirme pelo nome da classe, o número anda**), `tests/test_autospec_*.py`,
  `docs/base-conhecimento/08-autospec-backend.md`.
- 🔴 **Zonas compartilhadas** (`ficha_layout.py` → `CONFIG_MAP`, `config.LLM_TASKS`,
  `core/llm/prompts.py`, tabelas de status): commit isolado + mensagem explícita.
- Conflito em `PENDENCIAS.md`: **mantenha as duas linhas**, nunca escolha um lado.
- Branch oficial: `claude/checkpoint-01-refactor-executor-5lawtu`.

### 📌 Mural — avisos de um lado para o outro

Aqui vai o que o **outro** Claude precisa saber **antes de escrever código**:
regra que mudou, armadilha nova, arquivo que trocou de casa. Está neste arquivo
de propósito — o `CLAUDE.md` já é carregado em toda sessão, então o aviso chega
sem custar nenhuma leitura extra. Um arquivo à parte custaria um `Read` por
sessão e seria esquecido justamente nas sessões corridas.

**Regras do mural** (é o que impede ele de virar outro `PENDENCIAS.md`):

1. **Efêmero.** Leu e absorveu — **apague a linha**. O mural guarda o que ainda
   não foi absorvido, não o histórico. O histórico é o `git log`.
2. **No máximo 5 avisos.** Passou disso, o mais antigo vira linha em
   `PENDENCIAS.md` e sai daqui.
3. **Duas linhas, no máximo, por aviso.** O detalhe mora no commit; aqui fica o
   que muda para o outro lado, e onde ler mais.
4. **Conflito de merge:** mesma regra do `PENDENCIAS.md` — **fique com os dois**.
5. Aviso **só quando afeta o outro lado**. Trabalho comum não vira aviso.

| Data | De | Aviso |
|---|---|---|
| 2026-09-08 | Rafael | **Tarefa de IA nova não entra mais em `LLM_MODELOS_HOJE`.** O catálogo agora é `config.LLM_TASKS` + `_POLITICA_RETRY_POR_TAREFA` (em `core/llm/client.py`); aquele mapa é só o baseline das 5 tarefas do CP 3.1. O passo a passo está no aviso longo em `config.py`, seção 6. |
| 2026-09-18 | Luan | **Nada de `requests.get`/`urlopen` direto: use `sigft.core.rede.get`/`.post`.** Com a VPN ligada a chamada direta morre por timeout (a rede so publica um arquivo PAC). Encostei em `autospec.py` (2 linhas) e `core/web/robots.py`; ha guard de AST reprovando ponto novo. |
| 2026-09-19 | Luan | **Travessão saiu do texto de tela e de log** (`tests/test_texto_da_ui.py` reprova a volta). Os arquivos do AutoSpec e os prompts ficaram DE FORA — se quiser alinhar, é combinar antes. Nos relatórios de lote o separador virou dois-pontos. |
| 2026-09-08 | Rafael | **`ficha_layout.py` ganhou 4 conceitos** (aditivos, nada removido): `nome_da_aba_da_ficha`, `marcador_de_faltante`, `e_marcador_de_faltante` e `idioma_da_ficha`. Se for abrir uma ficha ou escrever `FORNECER` nela, use-os — o nome da aba e o marcador mudam quando a ficha é em inglês. |

---

## ⚠️ Trabalho de PORTAL exige sessão LOCAL

A sessão do Claude Code **na web** roda num contêiner que **não alcança o
portal** (`curl` no PMIB devolve `CONNECT tunnel failed, 403`). Nela, tudo que o
Claude sabe do portal chega por recorte colado no chat -- e uma rodada sua é
gasta por hipótese dele. Foi o que travou o módulo de ficha duplicada por uma
semana em agosto/2026.

**Mexeu em seletor, fluxo do portal ou RPA? Sessão local, com o navegador
ligado por MCP.** O passo a passo (três comandos) está em
[`docs/OLHAR_O_PORTAL.md`](docs/OLHAR_O_PORTAL.md).

Sessão na web continua ótima para o que não depende do portal: planilha,
prompts de IA, refatoração, testes.

**Vai escrever função nova que toca o portal?** Leia primeiro a §0 de
[`docs/PORTAL_COMO_ELE_SE_COMPORTA.md`](docs/PORTAL_COMO_ELE_SE_COMPORTA.md) —
sete regras curtas, cada uma paga com pelo menos uma rodada perdida (a URL que
não muda, o modal que trava tudo, o `required=False` que não é opcional, a
recusa silenciosa). O checklist do fim do arquivo é o portão antes do commit.

⚠️ E o corolário que custou caro: **`scripts/check.sh` verde não é prova de
portal.** Os 3350 testes rodam contra dublês escritos pelo próprio Claude --
eles provam a ideia dele do portal, não o portal. Nada de RPA se declara pronto
sem uma execução real.

---

## Como verificar o trabalho

```bash
bash scripts/check.sh        # compileall (sintaxe, cobre frontend.py) + pytest
```

O **CI do GitHub** repete isso em todo commit (`.github/workflows/ci.yml`):
`compileall`, `pyflakes` no `frontend.py`, `ruff`, `pytest` e a conferência do
`CHANGELOG.md`. Ele roda em Ubuntu com Python 3.10 — o mínimo que o `SIG-FT.bat`
aceita — e instala `requests`, `openpyxl`, `python-dotenv` e `pillow` além do
`requirements-dev.txt`: as quatro escapam da dublagem do `conftest.py`, e sem
elas são 16 falhas que não são defeito do código.

> ⚠️ **"Verde na minha máquina" não é verde no CI.** A primeira versão daquele
> passo tinha só duas dependências, porque foi escrita a partir do que faltava
> num contêiner que já tinha as outras instaladas. Para levantar lista de
> dependência, use um venv limpo.

**Verde é pré-requisito de qualquer commit.** A suíte tem 3806 testes (+17 skipped) e é a
rede de segurança da refatoração — as dependências pesadas (pandas, openpyxl, selenium,
google-generativeai, tkinter…) são stubadas em `tests/conftest.py`, então a suíte roda em
ambiente sem elas.

`frontend.py` **não pode ser importado** neste ambiente (abre janela real). Para ele a
verificação tem TRÊS partes, e as três são necessárias:

1. `compileall` — sintaxe;
2. `python -m pyflakes frontend.py` — **nome indefinido**, que é o que `compileall` não
   vê. Já vem na suíte (`tests/test_frontend_nomes_indefinidos.py`);
3. **abrir o aplicativo.** `python frontend.py` e olhar a janela preta.

⚠️ Por que as três: em 2026-08-25 o CP 5.5 removeu um frame de `ModuloCopiaFichas` e
deixou um widget filho dele para trás. `compileall` passou, os 2625 testes passaram, e o
app morria na abertura com `NameError: name 'f_novo' is not defined`. Editou `frontend.py`?
**Abra o app antes de dizer que está pronto.**

---

## Arquitetura

A refatoração migra um monolito para o pacote `sigft/`, mantendo os nomes antigos vivos:

```
frontend.py          # UI monolítica (240 KB, 12 telas) — vira shim no CP 7.3
*_backend.py         # shims de compatibilidade → sigft/services/*
sigft/
├── config.py        # constantes, chaves, LLM_TASKS (tarefa → provedor+modelo)
├── core/
│   ├── excel/       # headers, pmib_codes, locking, status_sheet
│   ├── llm/         # client + providers (OpenRouter padrão), usage, prompts
│   ├── rpa/         # engine → selenium_engine | playwright_engine, portal, ficha_layout
│   ├── callbacks.py # protocolo UI↔serviço (log/pause/ask/progress)
│   └── prefs.py     # memória de caminhos dos diálogos
├── services/        # lógica de negócio (backends magros)
└── app/             # UI (file_dialogs hoje; views a partir do CP 7.3)
```

### Princípios que não se negociam

1. **Uma implementação por conceito** — cabeçalho de planilha, código PMIB, portal, LLM.
2. **UI nunca contém regra de negócio; serviço nunca importa tkinter.** A comunicação é só
   por callbacks (`core/callbacks.py`).
3. **Nenhum serviço conhece Selenium/Playwright** — só `PMIBPortal`. É o que torna a troca de
   motor barata.
4. **Nenhum serviço conhece o SDK de um provedor de IA** — só `LLMClient`. Modelo e provedor
   vêm de `config.py`.
5. **Seletores e fluxos do portal são intocáveis nas Fases 1–4.** Nas Fases 5–6 mudam, sempre
   validados com o usuário contra o portal real (não há como testar offline).
6. **Compatibilidade por shims:** os nomes antigos continuam importáveis até a Fase 7.

---

## Convenções

- **Idioma:** código, commits, comentários e docs em **português**. Mensagens de commit sem
  acento (o histórico segue esse padrão).
- **Escopo de checkpoint:** o `refactor-executor` implementa **só** o checkpoint pedido. O que
  descobrir fora do escopo vai para `docs/refatoracao/PENDENCIAS.md` — não corrige de carona.
- **Nada de reformatação em massa** de arquivo compartilhado (principalmente `frontend.py`)
  sem combinar antes: transforma merge trivial em conflito gigante.
- **Testes junto com a mudança.** Todo checkpoint concluído até aqui trouxe os seus.

---

## Skills e agentes

### 🎯 Regra Skill-First — vale para toda tarefa neste repositório

**Antes de responder ou executar qualquer coisa, avalie as skills disponíveis** (em especial o
ecossistema **Superpowers**, em `.claude/skills/`). Se houver *qualquer* chance de uma skill se
aplicar, **invoque-a** — e só então comece. Descobrir no meio do caminho que existia uma skill
melhor custa mais caro do que ler a skill antes.

Isto vale inclusive quando a tarefa parece pequena. "É só uma pergunta", "é só uma linha" e "eu
já sei fazer isso" são exatamente os momentos em que se pula a etapa e se retrabalha depois.

**Skills de processo vêm primeiro** (definem *como* atacar), skills de implementação vêm depois:

| Situação | Skill que abre o trabalho |
|---|---|
| Algo não funciona como devia — bug, teste vermelho, busca que não acha, resultado estranho | `systematic-debugging` — **causa raiz antes de qualquer correção** |
| Ideia nova, melhoria, "e se a gente..." | `brainstorming` |
| Vai escrever código de feature ou correção | `test-driven-development` |
| Tem um plano escrito para executar | `executing-plans` |
| Vai dizer "está pronto / funcionando / passou" | `verification-before-completion` — evidência antes da afirmação |
| Terminou uma frente e vai integrar | `finishing-a-development-branch` |
| Mexer num módulo do SIG-FT | `sigft-melhorar-modulo` (ou `sigft-novo-modulo`) |

Anuncie qual skill está usando e para quê. Se a skill tiver checklist, vire tarefas.

**Por que esta regra existe, com um caso concreto:** em 2026-08-12, investigando por que a busca
web do AutoSpec não achava datasheets, a primeira hipótese (o nome do fabricante poluindo a
query) era plausível, convincente — e **errada**. O `systematic-debugging` obriga a testar a
hipótese antes de corrigir; o teste mostrou que a query funcionava e que o problema estava no
filtro, três camadas adiante. Sem o skill, a "correção óbvia" teria sido implementada, não
resolveria nada, e o tempo perdido só apareceria no próximo teste do usuário.

**Exceção:** instrução direta do usuário ganha da skill. Se ele disser "pula o processo, faz
direto", faça — e diga que está pulando.

### O que existe

`.claude/agents/` — `doc-writer` (Haiku, escreve a base de conhecimento) e `refactor-executor`
(Sonnet, executa um checkpoint por vez).

`.claude/skills/` — `sigft-novo-modulo` e `sigft-melhorar-modulo` são do projeto. As demais
são de terceiros, vendorizadas para os dois desenvolvedores terem as mesmas ferramentas; a
origem, a licença e o modo de atualizar estão em [`.claude/skills/VENDOR.md`](.claude/skills/VENDOR.md).

> Se as skills de terceiros (`writing-plans`, `executing-plans`) sugerirem um formato de plano
> diferente: **o plano do projeto prevalece.** `docs/refatoracao/PLANO_REFATORACAO.md` é a
> fonte de verdade da refatoração.

---

## Documentação

| Onde | O quê |
|---|---|
| `docs/refatoracao/PLANO_REFATORACAO.md` | o plano: fases, checkpoints, critérios de aceite, quadro de status |
| `docs/refatoracao/TRABALHO_PARALELO.md` | **contrato de fronteiras entre as duas frentes** |
| `docs/refatoracao/PENDENCIAS.md` | achados fora de escopo, à espera de uma fase |
| `docs/refatoracao/MODELOS_IA.md` | modelos de IA, preços, defaults |
| `docs/base-conhecimento/` | um doc por módulo, descrevendo o comportamento atual |
| `docs/base-conhecimento/08b-autospec-contexto-negocio.md` | regras de negócio do AutoSpecAI (o "porquê") + anexo de divergências |
| `docs/AUTOSPEC_MELHORIAS.md` | **caderno da frente do AutoSpecAI** — achados abertos e o checklist de "não fechar sem" |
| `docs/ROTEIRO_DE_TESTE.md` | roteiro de validação manual, do ZIP até o portal |

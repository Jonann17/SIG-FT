# Trabalho paralelo — refatoração × AutoSpecAI

> **Para o Claude que estiver lendo isto:** este documento é um **contrato de fronteiras**
> entre duas pessoas mexendo no SIG-FT ao mesmo tempo. Ele tem precedência sobre a ordem
> natural dos checkpoints do `PLANO_REFATORACAO.md`. Se um checkpoint que você foi mandado
> executar colide com uma zona reservada aqui, **pare e avise o usuário** — não decida
> sozinho que "é um conflito pequeno".

**Vigente desde:** 2026-08-11
**Linha de trabalho oficial:** `claude/checkpoint-01-refactor-executor-5lawtu`

---

## 1. Quem está fazendo o quê

| Pessoa | GitHub | Frente de trabalho |
|---|---|---|
| **Luan** (dono do repo) | `luanccozer` | Refatoração geral, seguindo `PLANO_REFATORACAO.md` checkpoint a checkpoint |
| **Rafael** | `rafhagmm` | **Só o módulo AutoSpecAI** — evolução funcional, não refatoração estrutural |

As duas frentes rodam **ao mesmo tempo**, em branches separadas, partindo de
`claude/checkpoint-01-refactor-executor-5lawtu`.

### Estado da refatoração quando este contrato entrou em vigor

- Fases 0 a 4: ✅ concluídas
- Fase 5 (Playwright): 🟡 CP 5.1–5.4 com código pronto, aguardando sessão de validação real
  contra o portal; CP 5.5 ⛔ bloqueado de propósito
- Fases 6, 7 e 8: ☐ pendentes ← **é aqui que mora o risco de colisão**

### Branches

| Branch | Para quê |
|---|---|
| `claude/checkpoint-01-refactor-executor-5lawtu` | **a linha de verdade.** Todo trabalho sai dela e volta para ela |
| `claude/autospec-*` | frente do Rafael. Uma branch por frente de trabalho, sempre saindo da linha oficial atualizada |
| `claude/itaipu-delivery-refactor-vh0n67` | ⚠️ **abandonada.** Ver abaixo |

**Sobre a `itaipu-delivery-refactor`:** ela ainda é a branch **default do GitHub**, mas está
51 commits atrás da linha oficial. Auditado em 2026-08-11: o conteúdo dos 4 commits que ela
tem a mais (config.py central, `LLM_TASKS`, decisões de modelos de IA, CP 1.5) **já foi
reconciliado** na linha oficial pelo commit `4b139f7`; o único arquivo exclusivo dela é
`tests/test_config_load.py`, superseded por `tests/test_config.py`. **Não saia dela para
começar nada.** Trocar a default exige permissão de admin — é ação do Luan, em
*Settings → General → Default branch*.

---

## 2. Mapa de propriedade

🟢 **Exclusivo do Rafael** — o Claude do Luan não deve editar sem avisar:

| Arquivo | O que é |
|---|---|
| `sigft/services/autospec.py` | o serviço AutoSpec (a lógica de verdade, 449 linhas) |
| `autospec_backend.py` | shim de compatibilidade do AutoSpec (23 linhas) |
| `frontend.py`, **linhas ~2971–3146** | `class ModuloAutoSpec` — a tela do módulo. **Localize pela linha `class ModuloAutoSpec` até a `class` seguinte, não pelo número** — em 2026-08-11 o intervalo já andou de 2947–3122 para 2971–3146 por causa de um commit no mesmo arquivo, em questão de horas |
| `tests/test_autospec_*.py`, `tests/test_llm_autospec_migration.py` | testes do módulo |
| `tests/fixtures/prompts/autospec_prompt.txt` | fixture do prompt |
| `docs/base-conhecimento/08-autospec-backend.md` | doc do módulo |

🔴 **Compartilhado — conflito quase garantido se os dois mexerem junto:**

| Arquivo / trecho | Por que dói | Regra |
|---|---|---|
| `PLANO_REFATORACAO.md` → tabela "6. Status dos Checkpoints" | os dois acrescentam linha na mesma tabela, no mesmo fim de arquivo | ver §5 |
| `PENDENCIAS.md` → tabela | idem, tabela append-only | ver §5 |
| `sigft/core/rpa/ficha_layout.py` → `CONFIG_MAP` | **fonte única compartilhada entre `analyzer` e `autospec`** desde o CP 2.4 — mudar "para o AutoSpec" muda o analyzer junto | ver §4 |
| `sigft/config.py` → `LLM_TASKS["autospec"]` | mapa de tarefas de IA, arquivo que a refatoração também edita | ver §4 |
| `sigft/core/llm/prompts.py` → prompt do autospec | os 5 prompts moram no mesmo arquivo desde o CP 3.5 | ver §4 |
| `frontend.py` → linhas de **registro** do módulo | poucas linhas, espalhadas, e todo módulo passa por elas | ver §3.2 |

As linhas de registro do AutoSpec no `frontend.py` — identifique por **âncora de conteúdo**,
não por número (os números andam):

- `autospec_backend = None` (bloco de globais no topo)
- o card `titulo="5. AutoSpec AI (RAG)"` na Home
- a entrada `"autospec": "AutoSpec (RAG):"` no dicionário de rótulos
- `("autospec_backend", "autospec_backend", None, "AutoSpec RAG")` na lista de imports da splash
- a linha `global ... autospec_backend ...`
- `self.btn_auto = self._criar_botao_menu(... "6. AutoSpec AI (RAG)", "AutoSpec", row=12)`
- `self.frames["AutoSpec"] = ModuloAutoSpec(...)`

---

## 3. O que o Claude do Luan NÃO deve fazer

### 3.1 Checkpoints congelados enquanto o AutoSpecAI estiver aberto

⛔ **CP 7.3 — quebrar `frontend.py` em `app/views/*.py`.** É o mais perigoso do plano inteiro
para este arranjo. Ele move todas as 12 telas para arquivos novos. Se o Rafael tiver trabalho
aberto em `ModuloAutoSpec`, o arquivo que ele está editando deixa de existir e **toda linha
vira conflito** — o Git não tem como casar "linha 3000 do `frontend.py`" com "linha 40 do
`app/views/autospec.py`". Não é um merge difícil: é um merge que se resolve na mão, tela por
tela.
→ **Só execute o CP 7.3 depois que o AutoSpecAI estiver mergeado.** Se o plano mandar
executá-lo antes, pare e pergunte.

⚠️ **CP 7.1 e CP 7.2** — `theme.py`/`console.py`/`module_frame.py` e `pickers.py`/`dialogs.py`.
Reescrevem widgets que o `ModuloAutoSpec` usa (console, seletores de arquivo). Podem ser
executados, **desde que as telas piloto sejam outras** — o plano já indica `ApagarLMR` e
`Translator` no CP 7.1, o que está ótimo. **Não use o AutoSpec como piloto de nada.**

⚠️ **Qualquer refazimento das Fases 2, 3 ou 4 que toque `ficha_layout.py`, `prompts.py`,
`config.LLM_TASKS` ou `sigft/services/autospec.py`.** Essas fases estão concluídas; se
aparecer necessidade de voltar nelas, ver §4.

✅ **Livre, sem coordenação:** Fase 5 inteira (Playwright/RPA — o AutoSpec **não usa RPA**,
não tem browser no caminho), Fase 6 (`ficha_duplicada`), Fase 8 (ruff, type hints,
PyInstaller, isolamento Windows — desde que o lint não reescreva `autospec.py` em massa).

### 3.2 Regra do `frontend.py`

O arquivo é compartilhado, mas o Git resolve sozinho quando as edições ficam em regiões
diferentes. Então:

- **Pode:** editar qualquer outra tela, os widgets comuns, a sidebar, a Home.
- **Evite:** reindentar, reordenar classes, ou rodar formatador automático no arquivo inteiro
  — isso reescreve linhas que ninguém pediu para mudar e transforma um merge trivial em um
  conflito de 3.000 linhas. Se for rodar `ruff format`/`black` (CP 8.1), **combine antes**.
- **Se precisar mexer nas linhas de registro do AutoSpec** (renomear o módulo na sidebar,
  reordenar os botões, mudar a assinatura de `_criar_botao_menu`): pode, é pouca linha e o
  conflito é fácil — mas **cite no commit** que mexeu, para o outro lado saber.

---

## 4. Quando você precisa MESMO mexer numa zona compartilhada

Não é proibido — é que precisa de um jeito específico para o merge não doer:

1. **Faça a mudança sozinha, num commit só dela**, sem carona de outras alterações. Um commit
   de 5 linhas em `ficha_layout.py` se resolve em segundos; o mesmo diff dentro de um commit
   de 800 linhas vira arqueologia.
2. **Mensagem de commit explícita** sobre a zona tocada, ex.:
   `CONFIG_MAP: adiciona campo X (zona compartilhada analyzer/autospec)`
3. **Registre em `PENDENCIAS.md`** que a zona foi tocada, com a data.
4. Para `ficha_layout.py` especificamente: **nunca remova nem renomeie chave existente do
   `CONFIG_MAP`**. Só acrescente. Remoção quebra o analyzer e o autospec ao mesmo tempo, e o
   CP 2.4 deixou 119 testes de equivalência que vão acusar — mas só depois do merge.

---

## 5. Como não brigar pelas tabelas de status

`PLANO_REFATORACAO.md` (tabela de checkpoints) e `PENDENCIAS.md` (tabela de pendências) são
**append-only no fim do arquivo**. Dois lados acrescentando linha no mesmo ponto = conflito
em 100% dos merges.

Combinado:

- **O quadro de status dos checkpoints é do Luan.** O Rafael não escreve nele. O trabalho do
  AutoSpecAI não é um checkpoint do plano — não vira linha nessa tabela.
- **`PENDENCIAS.md` os dois usam.** Quando der conflito, a resolução é sempre a mesma e é
  boba: **ficar com as duas linhas**, uma embaixo da outra, ordenadas por data. Nunca escolha
  um lado. Se você é um Claude resolvendo esse conflito, mantenha ambas e siga.

---

## 6. Protocolo de consolidação (merge)

Ordem recomendada quando o AutoSpecAI ficar pronto:

1. Rafael atualiza a branch dele com a linha oficial **antes** de pedir o merge:
   ```bash
   git fetch origin claude/checkpoint-01-refactor-executor-5lawtu
   git merge origin/claude/checkpoint-01-refactor-executor-5lawtu
   ```
   Resolver conflito na branch de quem chegou depois é sempre mais barato.
2. Rodar o portão do projeto: `bash scripts/check.sh` (compileall + pytest). **Verde é
   pré-requisito de merge** — são 1.278 testes (+10 skipped) e eles são a rede de segurança
   da refatoração inteira.
3. Merge do AutoSpecAI em `claude/checkpoint-01-refactor-executor-5lawtu`.
4. **Só depois disso** o Luan libera o CP 7.3.

### Checklist de quem vai mergear

- [ ] `bash scripts/check.sh` verde nos dois lados
- [ ] Nenhum arquivo 🟢 do outro lado foi tocado sem aviso
- [ ] Conflito em `PENDENCIAS.md` resolvido mantendo **as duas** linhas
- [ ] `CONFIG_MAP` não perdeu chave (`pytest tests/test_ficha_layout.py`)
- [ ] Se `frontend.py` conflitou em mais de ~50 linhas: **parar e conversar**, não resolver
      na força bruta

---

## 7. Quando este documento deixa de valer

Este contrato existe porque há duas frentes simultâneas. Quando o AutoSpecAI estiver mergeado
e o Rafael não tiver trabalho aberto, o Luan pode retomar o plano na ordem normal — incluindo
o CP 7.3 — e este arquivo vira registro histórico. **Até lá, ele vale.**

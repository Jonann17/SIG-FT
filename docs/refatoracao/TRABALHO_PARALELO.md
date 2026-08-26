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
| `sigft/services/autospec.py` | o serviço AutoSpec (a lógica de verdade) |
| `sigft/services/autospec_rag.py` | retrieval (BM25 + glossário multilíngue) |
| `sigft/services/autospec_embeddings.py` | reforço semântico opcional |
| `sigft/services/autospec_unidades.py` | conversão de unidade conferida |
| `sigft/services/autospec_conferencia.py` | conferência humana dos documentos duvidosos |
| `sigft/core/web/` (`navegador.py`, `robots.py`) | leitura de página por navegador, último recurso |
| `autospec_backend.py` | shim de compatibilidade do AutoSpec (23 linhas) |
| `frontend.py`, **linhas ~3077–3508** | `class ModuloAutoSpec` — a tela do módulo. **Localize pela linha `class ModuloAutoSpec` até a `class` seguinte, não pelo número** — o intervalo já andou de 2947–3122 → 2971–3146 (2026-08-11) → 3077–3508 (2026-08-26). O número aqui envelhece a cada commit no arquivo; o nome da classe, não |
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

✅ **CP 7.3 — LIBERADO EM 2026-08-26.** Esteve congelado de 2026-08-11 até esta data.

Por que estava congelado, e por que deixou de estar: o CP 7.3 move as 12 telas para arquivos
novos. Com trabalho aberto em `ModuloAutoSpec`, o arquivo que o Rafael estava editando deixaria
de existir e **toda linha viraria conflito** — o Git não casa "linha 3000 do `frontend.py`" com
"linha 40 do `app/views/autospec.py`". Hoje **não há trabalho aberto**: o AutoSpecAI está
mergeado na linha oficial e a Etapa 3b do roteiro rodou numa máquina real, com resultado bom.

→ **Pode executar.** Mas leia as duas subseções abaixo antes: `ModuloAutoSpec` e
`ModuloAnalyzer` ganharam blocos que precisam viajar inteiros junto com as classes, e cada uma
tem uma armadilha de busca-e-substituição já documentada.

> ⚠️ **Depois do CP 7.3, mudança de tela na frente do Rafael fica mais cara** — ele passa a
> editar `app/views/*.py` enquanto o histórico dele fala de `frontend.py`. Se ele tiver uma
> leva grande de mudanças de UI engatilhada, vale combinar a ordem antes.

#### 🆕 2026-08-13 — o `ModuloAutoSpec` cresceu: leia isto antes do CP 7.3

A tela ganhou uma **seção nova**, a *Conferência de documentos*. Ela é o desfecho de uma
decisão de produto: o filtro anti-intruso passou a ter três destinos (`certo`, `duvidoso`,
`descartado`), e o do meio **precisa de uma pessoa**. Numa ficha real entrou uma camiseta da
Minnie do site do Target porque a URL continha o código do material; no mesmo lote, um datasheet
legítimo foi barrado por não citar a marca no título. Indistinguíveis para o código.

**O que isso muda para você, que vai executar o CP 7.3:**

| | |
|---|---|
| **Onde está** | `frontend.py`, dentro de `class ModuloAutoSpec`, sob o comentário-cabeçalho `CONFERÊNCIA DE DOCUMENTOS DUVIDOSOS` |
| **O que é** | 6 métodos (`_build_conferencia`, `_conferencia_mostrar`, `_conferencia_salvar`, `_conferencia_importar`, `_conferencia_processar`, `_conferencia_worker`) + 7 atributos (`self.conferencia`, `self.marcados_conf`, `self.frm_conf`, `self.lista_conf`, `self.btn_conf`, `self.btn_conf_salvar`, `self.btn_conf_importar`) |
| **Acoplamento com o resto do arquivo** | **nenhum.** Nada fora da classe usa esses nomes. Dentro da classe são dois pontos só: `_build_conferencia()` no fim do `setup_ui` e `_conferencia_mostrar(...)` na última linha do `_worker` |
| **`_novo_core()`** | método novo, extraído do `_worker`: monta o `AutoSpecCore` com as chaves e opções da tela. Os **dois** workers (fila e conferência) chamam ele. Se você mover só um, quebra o outro |
| **Como mover** | **em bloco, junto com a classe.** Não tente separar o bloco da tela — ele não é reaproveitável, é desenho de widget desta tela específica |

**A lógica não está na tela** — está em `sigft/services/autospec_conferencia.py`, com 16 testes.
Isso foi feito de propósito para o CP 7.3: quando você mover `ModuloAutoSpec`, o que vai junto é
só construção de widget, que é exatamente o que o checkpoint quer mover. Nenhuma regra de
negócio viaja com ele.

**Três coisas fora da classe** que a seção precisa, e que você pode encontrar no diff:

1. `import webbrowser` no topo do `frontend.py` — o link da conferência abre no navegador.
2. `from sigft.services import autospec_conferencia as conferencia_txt` — o serviço que
   salva/lê o `.txt`. **Fora do carregamento preguiçoso do splash de propósito:** o módulo só
   usa `os`/`re`/`datetime`, não puxa pandas nem selenium, e a seção precisa dele já na
   montagem da tela.
3. `COLORS["warning"] = "#FFA726"` — **aditivo**, nenhuma cor existente mudou.

Se o CP 7.3 for executado antes do merge desta frente, estas são as três linhas que também
precisam viajar (ou ser reintroduzidas no arquivo novo).

**Dois invariantes da seção têm teste** (`tests/test_autospec_conferencia_tela.py`, por AST
sobre o fonte, já que `frontend.py` não é importável). Se você mover o bloco e eles ficarem
vermelhos, não é o teste que está errado:

- **`_worker` chama `_conferencia_mostrar` ANTES de `_conferencia_salvar`.** O salvamento lê
  `self.marcados_conf`, e é `_mostrar` quem recria a grade; invertido, o `.txt` automático sai
  com as marcações do lote anterior — arquivo plausível e errado.
- **A seção nunca faz `pack_forget`.** O botão IMPORTAR precisa existir na tela de quem acabou
  de abrir o aplicativo e ainda não processou nada — é justamente quem mais precisa dele.

⚠️ **Uma armadilha de busca-e-substituição**, verificada em 2026-08-26: o `ModuloAnalyzer` tem
`self.btn_config`. Ele **não** colide com nenhum dos 7 nomes do bloco (`btn_conf`,
`btn_conf_salvar`, `btn_conf_importar`, `conferencia`, `frm_conf`, `lista_conf`,
`marcados_conf`) — mas um `sed`/replace em `btn_conf` o corrompe em silêncio, em outra tela.
Mova o bloco por recorte de texto, não por substituição de prefixo.

#### 🆕 2026-08-26 — o `ModuloAnalyzer` também cresceu

A frente do Rafael passou pelo Analyzer nesta data (7 defeitos medidos + 4 decisões do
usuário + relatório para o fornecedor). A tela ganhou:

| | |
|---|---|
| **Onde está** | `frontend.py`, `class ModuloAnalyzer` (~linhas 1480–1856 — **localize pelo nome da classe**) |
| **O que é novo** | 2 métodos (`_perguntar_descricao`, `_gerar_relatorio`) + 3 atributos (`relatorio_analise`, `btn_relatorio`, `_parar_de_perguntar_desc`) |
| **Fora da classe** | `from sigft.services import analyzer_relatorio` no topo — como o import da conferência, fora do splash de propósito (só stdlib + `ficha_layout`) |

**`_perguntar_descricao` é o método delicado do bloco.** Ele é chamado **pelo backend**, de
dentro da thread de processamento, e abre a janela com `self.after(0, ...)` + `threading.Event`
— o padrão que `ModuloUploadConditions._worker_web` já usava. Movido para outro arquivo, ele
continua precisando de um `self` que seja um widget tkinter com `.after()`. Não o transforme
em função solta.

⚠️ **A mesma armadilha de busca-e-substituição vale aqui**: `self.btn_relatorio` e
`self.btn_run` convivem com o `self.btn_config` que já existia. Recorte de texto, não replace
de prefixo.

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

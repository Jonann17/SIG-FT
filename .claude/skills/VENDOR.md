# Skills de terceiros instaladas neste repositório

As skills abaixo **não são do SIG-FT** — foram copiadas ("vendorizadas") de repositórios
públicos para dentro de `.claude/skills/` de propósito: assim elas viajam junto com o `git
clone` e **todo mundo que trabalha no projeto tem as mesmas skills**, sem precisar instalar
nada na própria máquina.

> Skills do próprio projeto (não mexer neste doc por causa delas):
> `sigft-novo-modulo`, `sigft-melhorar-modulo`.

---

## 1. superpowers — 14 skills

| | |
|---|---|
| Origem | https://github.com/obra/superpowers |
| Autor | Jesse Vincent |
| Licença | MIT (`Copyright (c) 2025 Jesse Vincent`) |
| Versão | 6.2.0 |
| Commit copiado | `44c9b2d` |
| Data da cópia | 2026-08-11 |

Skills: `brainstorming`, `dispatching-parallel-agents`, `executing-plans`,
`finishing-a-development-branch`, `receiving-code-review`, `requesting-code-review`,
`subagent-driven-development`, `systematic-debugging`, `test-driven-development`,
`using-git-worktrees`, `using-superpowers`, `verification-before-completion`,
`writing-plans`, `writing-skills`.

**Atenção a duas delas no contexto do SIG-FT:**

- `writing-plans` / `executing-plans` são um mecanismo de plano **genérico**. O SIG-FT já tem
  o seu: `docs/refatoracao/PLANO_REFATORACAO.md` + o agente `refactor-executor`. **O plano do
  projeto prevalece.** Não substitua um pelo outro nem migre o plano de formato.
- `using-superpowers` se descreve como "use ao começar qualquer conversa". Trate como
  opcional — ela não tem prioridade sobre o `CLAUDE.md` nem sobre o plano de refatoração.

## 2. caveman — 7 skills

| | |
|---|---|
| Origem | https://github.com/JuliusBrussee/caveman |
| Autor | Julius Brussee |
| Licença | MIT (`Copyright (c) 2026 Julius Brussee`) |
| Versão | 0.1.0 |
| Commit copiado | `3098342` |
| Data da cópia | 2026-08-11 |

Skills: `caveman`, `cavecrew`, `caveman-commit`, `caveman-compress`, `caveman-help`,
`caveman-review`, `caveman-stats`.

**O que muda em relação ao plugin original:** o caveman "de verdade" se ativa sozinho por
**hooks** (`SessionStart` e `UserPromptSubmit`, scripts Node em `src/hooks/`). Hooks moram em
`.claude/settings.json`, não dentro da skill — e **não foram instalados aqui de propósito**.

Consequência prática, que é o comportamento desejado:

- O modo caveman **não liga sozinho** para ninguém. Ninguém é pego de surpresa.
- Quem quiser usar, invoca na mão: `/caveman` (ou pede "modo caveman").
- Isso mantém o modo verboso e detalhado que o `refactor-executor` precisa para escrever as
  entradas do quadro de status do plano.

Se algum dia quiserem a ativação automática, ela é **por pessoa** (`/plugin marketplace add
JuliusBrussee/caveman` + `/plugin install caveman@caveman`), não pelo repositório — assim um
não impõe ao outro.

---

## Como atualizar uma skill de terceiro

Não edite estes diretórios à mão: a edição se perde na próxima atualização e some o
rastro de origem. Para atualizar:

```bash
git clone --depth 1 https://github.com/obra/superpowers /tmp/superpowers
rm -rf .claude/skills/<nome-da-skill>
cp -r /tmp/superpowers/skills/<nome-da-skill> .claude/skills/
# atualize o commit e a data na tabela acima
```

Se precisarem MESMO adaptar uma skill de terceiro ao SIG-FT, copie para um nome próprio
(ex.: `sigft-<algo>`) e adapte a cópia — deixando a original intacta.

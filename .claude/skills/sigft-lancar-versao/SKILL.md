---
name: sigft-lancar-versao
description: Usar SEMPRE que for publicar uma versão do SIG-FT — release normal ou pré-lançamento (rc) para testar —, escolher o número de uma versão, abrir ou editar um bloco `## X.Y.Z` do CHANGELOG.md, disparar o workflow Release (botão "Run workflow" ou tag `v*`), ou consertar uma versão publicada com o número errado.
---

# Lançar uma versão do SIG-FT

O número da versão segue a regra do Luan, e **número errado não é cosmético**: o
app compara versões (`updater.e_mais_nova`). Quem instalou uma `1.2.0-rc.1` nunca
recebe a `1.1.1` nem a `1.1.2` pela atualização automática — medido em 2026-09-25.

## A regra do número (Luan, 2026-09-25)

| O que mudou | Sobe | Exemplo real |
|---|---|---|
| Correção de bug, ajuste ou melhoria de função/módulo que **já existe** — mesmo que reescrito por dentro | **PATCH**: 1.1.0 → 1.1.1 → 1.1.2 | tradutor 4.2 passou a traduzir no computador; catálogo do OpenRouter voltou; atualização automática consertada |
| Algo **novo**, que não existia (módulo, tela, capacidade nova) | **MINOR**: 1.1.x → 1.2.0 | tela nova de Correção de PDM (1.1.0) |
| Mudança **muito grande** | **MAJOR**: 1.x → 2.0.0 | — |

- **Na dúvida, é PATCH.** MINOR ou MAJOR só com o "sim" do Luan **nesta conversa** — pergunte dizendo o que é novo.
- O ponto de partida é o **último release normal publicado** (`git ls-remote --tags origin`), nunca o bloco do topo do CHANGELOG nem a última rc: o bloco pode estar errado.
- **Um bloco só** esperando lançamento no CHANGELOG: o da próxima versão. Mudança nova entra nele, com o nome do módulo na frente de cada item (as notas perdem os títulos de seção). Achou dois? Junte no menor número — o Release publica só o bloco da própria versão, e os itens do outro somem.

## Pré-lançamento

`X.Y.Z-rc.N`: `X.Y.Z` é o bloco em aberto; `N` é a maior rc já existente dessa versão + 1. Ninguém recebe pré-lançamento como atualização. Release **normal** vira aviso na próxima abertura de todo app 1.1.1+: só com autorização explícita do Luan.

## Passo a passo

1. `git fetch`. Trabalhe na branch padrão do GitHub (`git ls-remote --symref origin HEAD`), com CI verde no commit que vai sair.
2. Liste tags e runs do workflow Release. **Run rodando, inclusive da outra frente? Espere terminar** — em paralelo, a numeração embaralha.
3. Número pela tabela. Bloco `## X.Y.Z - AAAA-MM-DD` único em aberto.
4. Ensaie as notas: numa pasta temporária, com o CHANGELOG copiado e um arquivo qualquer como instalador, `python tools/gerar_manifesto.py --instalador <arq> --versao X.Y.Z-rc.N --tag vX.Y.Z-rc.N`.
5. Dispare: Actions → Release → **Run workflow** (`versao`, `prerelease`), ou tag `v*`. Mecânica em `docs/BUILD.md`.
6. Confira: run verde, marca certa (pré-lançamento ou não), notas com os itens. Aviso no mural do `CLAUDE.md` se a outra frente precisa saber.

## Número errado já publicado

1. Run rodando: **cancele** antes do passo "Publicar o Release".
2. Publicado: saia com o número certo e veja o `download_count` do instalador errado (`get_release_by_tag`). Zero downloads = ninguém afetado.
3. **Não apague a tag**: o número fica queimado, e a próxima rc daquela versão continua a contagem — nunca dois builds diferentes com o mesmo nome. Para tirar o release da lista, o Luan o apaga na página de Releases, mantendo a tag.
4. Quem instalou o número errado reinstala o certo **à mão**: pela atualização automática, só sai do lugar quando a versão passar daquele número.

## Racionalizações (todas aconteceram em 2026-09-25)

| Pensamento | Realidade |
|---|---|
| "Funcionalidade nova, então é minor (SemVer)" | Melhoria de função que já existe é PATCH, mesmo reescrita. MINOR só com o sim do Luan. |
| "O bloco do topo já diz 1.2.0, sigo ele" | Confira contra o último release normal e a tabela. |
| "Abro um bloco novo para a minha mudança" | Um bloco só em aberto. |
| "É só uma rc, o número não importa" | Quem instala a rc fica preso naquele número. |
| "A outra frente está lançando, disparo junto" | Espere a run dela terminar. |

## Sinais de alerta — pare

- MINOR/MAJOR subindo sem o "sim" do Luan nesta conversa.
- Dois blocos `##` acima do último release normal.
- Release normal sem autorização explícita.

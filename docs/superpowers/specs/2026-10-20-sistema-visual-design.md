# Sistema visual do SIG-FT — parte 1 do redesenho (2026-10-20)

Pedido do Jonathan: *"que a visual seja mais linda, algo diferenciado para o
user experience"*, escolhendo A (polir), B (identidade) e C (tablero e passos
guiados), para uma próxima atualização. Ele delegou as decisões ("metele con lo
que te parezca mejor").

O redesenho foi dividido em três partes, cada uma com spec, plano e versão:

1. **Sistema visual (A + B)** — este documento.
2. Home tipo tablero (C, metade 1).
3. Telas com passos guiados (C, metade 2).

A ordem importa: os passos guiados feitos antes do sistema visual seriam
refeitos depois.

## Por que agora dá

Até 2026-10-15 a interface Qt copiava a CustomTkinter pixel a pixel, de
propósito: as duas conviviam e os testes de medida provavam que eram iguais. A
antiga saiu. A fidelidade a ela deixou de ser requisito, e os testes de medida
passam a travar as medidas NOVAS (continuam pegando mudança acidental).

## Decisões

### Identidade: evoluir a paleta atual, não trocar

O verde (`#00C975`) e o petróleo (`#035D67`) ficam: são a cara que os usuários
já conhecem, e o logo da GE Vernova dentro do app combina com eles. O que muda
são os **neutros** (hoje meia dúzia de cinzas soltos: `#3A3A3A`, `#454545`,
`#2B2B2B`, `#1E1E1E`…) e a **organização**: toda cor passa a ter um nome pelo
papel que cumpre.

### Tokens: um lugar só, dois temas

`sigft/app/tokens.py` (sem Qt, como `theme.py`):

| Papel | Escuro | Claro |
|---|---|---|
| `fundo` (janela) | `#14171A` | `#F3F5F6` |
| `superficie` (cartão, painel) | `#1C2024` | `#FFFFFF` |
| `superficie_alta` (campo, item em foco) | `#252A2F` | `#EEF1F3` |
| `borda` | `#31373D` | `#D5DBE0` |
| `texto` | `#E7EAED` | `#1A1F24` |
| `texto_suave` (legenda, dica) | `#9AA4AE` | `#5B6670` |
| `primaria` (ação principal) | `#00C975` | `#007A51` |
| `primaria_hover` | `#00E085` | `#00875A` |
| `texto_sobre_primaria` | `#0B1A12` | `#FFFFFF` |
| `marca` (barra lateral, títulos de seção) | `#035D67` | `#035D67` |
| `sucesso` | `#00C975` | `#00875A` |
| `aviso` | `#FFA726` | `#B26A00` |
| `perigo` (texto e ícone) | `#F2555A` | `#C9302C` |
| `perigo_fundo` (botão) | `#C9302C` | `#C9302C` |
| `info` | `#3B9EFF` | `#0B6BCB` |
| `console_fundo` | `#0E1012` | `#0E1012` |

O console fica escuro nos dois temas: é saída de terminal, e log é mais legível
assim. As cores de log por nível (erro, aviso, ok) vêm de `perigo`, `aviso` e
`sucesso`.

`theme.COLORS` continua existindo (é importado em muitos lugares) e passa a ser
**derivado** de `tokens` do tema escuro, para nada quebrar no caminho.

### Tipografia e espaços

- Roboto continua (já vem no pacote). Escala: título de tela 22 bold, seção 15
  bold, corpo 13, legenda 12.
- Console: `Cascadia Mono`, `Consolas`, monoespaçada do sistema (sem fonte nova
  no pacote; o Windows já tem as duas primeiras).
- Espaçamento em degraus de 4: 4, 8, 12, 16, 24. Raio: 6 (botão, campo), 10
  (cartão).

### Botões com hierarquia

`blocos.botao(variante=...)` já existe; as variantes passam a ser quatro, todas
na folha de estilo (nenhuma cor no `setStyleSheet` do botão):

- `primario` — preenchido com `primaria`, texto `texto_sobre_primaria`. Uma ação principal por tela. No escuro o texto é ESCURO sobre o verde vivo: branco sobre verde médio dava 3,1:1 (medido), abaixo do mínimo.
- `secundario` — contorno `borda`, texto `texto`. O resto.
- `perigo` — preenchido com `perigo_fundo`, texto branco (5,3:1). Parar robô, apagar, limpar lote.
- `fantasma` — só texto. Ações menores (abrir pasta, limpar campo).

O `cor_fundo=` cru dos 125 usos de `blocos.botao` é traduzido para uma variante
(ex.: `VERDE_TK` → `primario`, `#3A3A3A` → `secundario`, "PARAR…" → `perigo`).
`cor_fundo` continua aceito, mas um teste acusa uso novo.

### Ícones no lugar de emoji

Os emojis (🏠 📁 🔍 ⚙️ 🗑️ ✨ …) dependem do Noto Emoji e saem com cara de
celular. Entram ícones de linha **Lucide** (licença ISC, permite redistribuir),
só os usados (~25 SVG, poucos KB), em `assets/icons/`. O SVG usa
`currentColor`; `icones.icone(nome, cor)` troca pela cor do token e devolve um
`QIcon`. Botão com ícone = ícone + texto (o texto nunca some: é o que o teste e
o leitor de tela leem).

### Tema claro e escuro

- Seletor na barra da Home: **Escuro / Claro / Sistema** (Sistema segue o
  Windows via `QStyleHints.colorScheme()`).
- Fica em `user_prefs.json` (`core/prefs.py`, como a caixa de versões de teste).
- Trocar o tema regera a folha (`estilo.folha_de_estilo(tema)`) e aplica na
  hora, sem reiniciar. Por isso nenhuma tela pode ter cor própria no
  `setStyleSheet`: os 67 usos são revistos; os que só existem para cor passam a
  usar propriedade (`setProperty("papel", "legenda")`) e a cor sai da folha.

### Splash e logo

O logo da GE Vernova fica (é a regra de `docs/DISTRIBUICAO.md`). O splash é
refeito com os tokens: fundo `fundo`, logo, nome "SIG-FT", versão e a barra de
carregamento na cor `primaria`. Sem arte nova de logo nesta parte.

## Componentes que mudam

| Onde | O quê |
|---|---|
| `sigft/app/tokens.py` (novo) | as duas paletas, escala de fonte/espaço/raio |
| `sigft/app/theme.py` | `COLORS` derivado dos tokens escuros |
| `sigft/app_qt/estilo.py` | `folha_de_estilo(tema)`; variantes de botão; papéis de texto |
| `sigft/app_qt/icones.py` (novo) + `assets/icons/` | carregar e colorir os SVG |
| `sigft/app_qt/widgets/blocos.py` | `botao` sem cor própria; `cor_fundo` → variante |
| `sigft/app_qt/widgets/console.py` | fonte mono, cores por nível dos tokens |
| `sigft/app_qt/main.py` | barra lateral com ícones; aplicar tema na abertura |
| `sigft/app_qt/views/home.py` | seletor de tema; cartões novos |
| as 12 telas | cores cruas → papéis/variantes; emoji → ícone |
| `SIG-FT.spec` | `assets/icons` no pacote; QtSvg (plugin `iconengines`/`imageformats` svg) |

## O que NÃO muda

Ordem das telas, menu, textos, fluxos, serviços. Nenhum robô é tocado. Quem
abrir a versão nova encontra tudo no mesmo lugar.

## Riscos

- **QtSvg no instalador.** O `SIG-FT.spec` filtra plugins do Qt
  (`_qt_que_a_interface_nao_usa`). Se o plugin de SVG ficar de fora, os ícones
  somem SÓ no `.exe` — o mesmo tipo de defeito do `pymupdf-layout` em
  2026-10-20. Mitigação: o smoke (`frontend.py --smoke`) passa a conferir que
  um ícone carregou (`not QIcon.isNull()`), e o Release roda o smoke no
  `dist/`.
- **Cor esquecida no tema claro.** Um `setStyleSheet` com cor crua fica
  escuro no tema claro. Mitigação: teste que varre `sigft/app_qt` e acusa cor
  hexadecimal fora de `estilo.py`/`tokens.py` (com lista de exceções
  justificadas).
- **Testes de medida.** ~21 testes travam pixels da interface antiga: são
  reescritos para as medidas novas, um a um, com o motivo no commit.

## Testes

- Contraste: todo par `texto`/`superficie`, `texto_suave`/`superficie` e texto
  de botão/fundo de variante, nos dois temas, ≥ 4,5:1 (WCAG AA) — calculado no
  teste, não no olho.
- Varredura de cor crua (acima).
- Troca de tema em execução: abre a janela, troca, confere a cor de fundo de
  uma tela e do console.
- Ícones: todo nome usado existe em `assets/icons/` e carrega.
- Smoke com as 12 telas nos dois temas.

## Entrega

Uma versão (patch, como manda `sigft-lancar-versao`: melhoria do que existe).
Antes de lançar, prints das telas principais nos dois temas para o Jonathan e o
Luan aprovarem.

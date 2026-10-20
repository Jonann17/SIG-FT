# Sistema visual do SIG-FT — parte 1 do redesenho (2026-10-20)

Pedido do Jonathan: *"que a visual seja mais linda, algo diferenciado para o
user experience"*, escolhendo A (polir), B (identidade) e C (tablero e passos
guiados), para uma próxima atualização. Ele delegou as decisões ("metele con lo
que te parezca mejor").

O redesenho foi dividido em três partes, cada uma com spec, plano e versão:

1. **Sistema visual (A + B)** — este documento, em duas etapas, cada uma
   numa versão: **1a** o sistema visual, **1b** as ferramentas de uso
   (§ "Etapa 1b"). Separadas para que, se algo quebrar, se saiba o quê.
2. Home tipo tablero (C, metade 1).
3. Telas com passos guiados (C, metade 2) — leva junto o "continuar de onde
   parou" (§ "Para a parte 3").

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

Nota (2026-10-20): `aviso` claro mudou de `#B26A00` para `#AA6600`; o original media 4,24:1 sobre `superficie` (`#FFFFFF`), o novo mede 4,56:1.

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

**Logo da barra lateral com hover (pedido do Jonathan, 2026-10-20).** O bloco
logo + "SIG-FT" vira um botão: passar o mouse acende um brilho verde suave
(`QGraphicsDropShadowEffect` cor `primaria`, raio animado 0 → 18 px em 150 ms
por `QPropertyAnimation`, e o deslocamento −1 px), com a mãozinha e a dica
"Voltar ao início"; clicar leva à Home (`show_home`). Com o teclado: mesmo
brilho no foco. Sem animação para quem desliga animações no Windows
(`QStyleHints`/`SPI_GETCLIENTAREAANIMATION`): o brilho aparece direto, sem
transição.

O logo da GE Vernova fica (é a regra de `docs/DISTRIBUICAO.md`). O splash é
refeito com os tokens: fundo `fundo`, logo, nome "SIG-FT", versão e a barra de
carregamento na cor `primaria`. Sem arte nova de logo nesta parte.

### Nome no saudação da Home (decisão do Jonathan, 2026-10-20)

Hoje o SIG-FT não sabe quem o usa (o usuário do Windows é a matrícula, ex.
`560083605`). A Home passa a dizer "Bom dia, <nome>" com o nome que a pessoa
dá **uma vez**:

- **Quando:** na primeira abertura do SIG-FT que não tenha nome guardado --
  o que cobre a instalação nova e a primeira abertura depois de uma
  atualização (o app abre sozinho ao fim dos dois). NÃO no instalador: ele
  roda como administrador e para a máquina inteira, e o nome é de cada
  pessoa.
- **Onde fica:** `user_prefs.json` (`core/prefs.py`), em `Documentos\SIG-FT`,
  como as outras preferências.
- **Pergunta:** uma caixa curta, "Como podemos te chamar?", campo de texto,
  botões "Salvar" (primário) e "Agora não" (secundário).
- **"Agora não" ou fechar:** saudação sem nome ("Bom dia") e um registro de
  que já se perguntou -- não pergunta de novo. A pessoa troca ou dá o nome
  depois, clicando na saudação da Home (dica: "Mudar como te chamamos").
- **Saudação pelo relógio:** Bom dia (até 12h), Boa tarde (até 18h), Boa
  noite.
- **O nome só aparece na tela.** Não vai para log, planilha, IA ou portal.

## Etapa 1b: ferramentas de uso (escolhidas pelo Jonathan, 2026-10-20)

Vêm DEPOIS da 1a, já com os tokens e ícones novos. Nenhuma mexe em robô.

1. **Aviso do Windows** quando uma tarefa termina ou pede algo, só se a
   janela do SIG-FT não estiver em foco: "Upload duplicadas terminou: 6 de 8
   sem pendência" / "Faça o login no portal e aperte Continuar". Clicar traz
   a janela para a frente. `QSystemTrayIcon.showMessage` (vira notificação
   nativa do Windows; nenhuma dependência nova). Ganchos: o fim da tarefa
   (`ModuleFrame._tarefa_acabou`) e as esperas (`DialogosDeEspera.
   pausar_e_esperar` e irmãs). Liga/desliga na Home; ligado por padrão.
2. **Janela de resumo no fim do lote**: as linhas de erro e aviso que a
   tarefa escreveu no console (o mesmo critério de nível do item 5),
   agrupadas por ficha quando a linha traz o código PMIB; botões "Copiar
   lista" e "Abrir log". Abre só se houve erro ou aviso; tarefa limpa
   continua só com a faixa "Terminou". Não depende de cada serviço devolver
   um resultado estruturado (a maioria não devolve): lê o que já se loga.
3. **Arrastar o arquivo** para a linha de seleção (`FilePickerRow`) ou para
   o botão que abre o diálogo de arquivo (helper `aceitar_arquivo(widget,
   chave, extensões, ao_receber)` nas telas que usam botão). Extensão errada:
   o widget fica vermelho e não aceita. **Últimos arquivos**: até 5 por
   chave de diálogo, num menu ao lado do botão; vão para o
   `user_prefs.json` (hoje ele guarda só PASTAS: é uma chave nova, com o
   mesmo cuidado de caminho que sumiu).
4. **Ctrl+K**: caixa de busca no meio da janela com os 12 módulos e as
   ações da Home ("Modelos de IA", "Chaves de API", "Abrir logs", "Tema
   claro"…); filtra enquanto se digita (sem acento, sem caixa), setas e
   Enter. Lista das ações num lugar só (`catalogo.py`).
5. **Filtro do console**: "Tudo / Avisos / Erros", busca de texto e "Copiar".
   O nível vem do parâmetro `nivel` do protocolo de log quando o serviço o
   manda, e senão das marcas que os serviços já escrevem (`[Erro]`, `[ERRO]`,
   `❌`, `Falha` → erro; `[Aviso]`, `[!]`, `[Autoconferência]` → aviso). A
   lista de marcas fica num lugar só e tem teste com linhas reais dos logs.
6. **Tamanho da letra**: Normal / Grande (+2 px em toda a escala), na Home,
   aplicado na hora como o tema. Sai dos tokens.

## Para a parte 3: continuar de onde parou

Item 9 da lista de 2026-10-20: a tela de passos lembra o passo e os arquivos
escolhidos; reabrir o app oferece "Continuar o lote de ontem (passo 2 de 4)?".
Fica registrado aqui para não se perder; o desenho é da parte 3.

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

# O portal PMIB — como ele se comporta

> Escrito em 2026-08-25, no fim da primeira semana em que foi possível **olhar**
> o portal em vez de deduzi-lo. Cada item aqui custou pelo menos uma rodada
> perdida, e vários custaram dias.
>
> **Para que serve:** antes de escrever qualquer função nova que toque o portal,
> leia a §0. Ela é curta e evita a maioria dos erros que este projeto já pagou.
> O resto do arquivo é referência: procure a seção do componente que você vai
> mexer.
>
> Complementa (não substitui) [`OLHAR_O_PORTAL.md`](OLHAR_O_PORTAL.md), que
> explica *como* abrir o navegador, e
> [`refatoracao/FICHA_DUPLICADA.md`](refatoracao/FICHA_DUPLICADA.md), que tem o
> HTML cru de cada achado.

---

## 0. As sete regras, se você só for ler uma seção

1. **A URL não diz nada.** O portal é uma SPA. Espere pela TELA.
2. **Aba ativa não é aba montada.** Espere os campos, não o `aria-selected`.
3. **Contar nós não é ver.** O que some da tela pode continuar no DOM.
4. **Um modal aberto trava a página inteira**, e o log só acusa o botão que
   falhou — nunca o modal.
5. **`required=False` não quer dizer opcional.** Quem valida é o OutSystems.
6. **Recusa muitas vezes é silenciosa.** Às vezes o único sinal é um elemento
   aparecer ou sumir.
7. **Espere por CONDIÇÃO, nunca por relógio** — e conte tentativas, não
   segundos (senão o teste que anula o `sleep` gira em vazio).

---

## 1. Navegação

### A URL não muda quando você acha que muda

Clicar no ícone de visualizar abre a ficha e o endereço **continua**
`PMIB_DatasheetList`, por tempo indeterminado — às vezes para sempre. Quem
espera `"PMIB_DataSheetView" in url` conclui "não abriu" com a ficha aberta na
frente. Custou três tentativas silenciosas em 2026-08-25.

**O sinal certo é a TELA:** a aba «Condições» da própria ficha, que não existe
na lista e existe em toda ficha, nos dois modos.

```python
extrator.esperar_a_ficha_abrir(portal)   # é isto que você quer
```

⚠️ `portal.ir_para_lista()` decide pela URL (`if current_url != PORTAL_URL`).
Como a URL fica na da lista mesmo dentro de uma ficha, ele às vezes **não
navega**. Para código novo, prefira `engine.goto(config.PORTAL_URL)` seguido de
espera pelas abas de status (`//button[@role='tab']`).

### A busca da lista é assíncrona

`safe_fill` + ENTER e pronto **não** é suficiente: em servidor lento a linha
ainda não está no DOM e o código conclui "não está nesta aba". Com sete abas,
vira `não achei a ficha em nenhuma aba` — numa ficha que está lá.

Espere a LINHA aparecer (`_buscar_na_aba_atual` já faz). A ficha está quase
sempre em **Em Elaboração**, às vezes em **Em Análise ITAIPU** — a ordem de
`spec.ABAS_DE_STATUS_DA_LISTA` já reflete isso.

---

## 2. Renderização: o DOM mente sobre o que está visível

### Sub-aba fechada é removida; dropdown fechado NÃO é

Duas regras opostas, e confundi-las custou meio dia:

| | Ao fechar |
|---|---|
| Sub-aba de Condições | o conteúdo **sai do DOM** |
| Dropdown `vscomp` | as opções **ficam**, o container ganha `display: none` |

Consequência prática: `contar('[role=option]')` devolve 10 com o dropdown
fechado. Um guard de "a lista ainda está aberta?" baseado em contagem dá falso
positivo e aborta uma operação que deu certo.

**Para saber se um `vscomp` está aberto**, pergunte pelo container:

```python
engine.contar(sel.XPATH_PDM_DROPBOX_ABERTO)   # 0 = fechado
```

E a contrapartida boa: como a sub-aba fechada sai do DOM, `contains(@id, sufixo)`
é seguro **desde que a sub-aba certa esteja aberta**. É o que permite
`RadioButton1-input` significar coisas diferentes em Armazenamento e em
Descarte sem ambiguidade.

### Aba ativa não é aba montada

O `aria-selected` vira `true` no clique; os campos entram depois. Varrer nesse
intervalo dá leitura **parcial** — e parcial não é "menos dado", é dado que
falta sem sintoma. Medido na mesma ficha e mesma sub-aba:

| | com pausa | sem |
|---|---|---|
| `[Manutenção]` | 3 campos | 2 |
| `[Descarte]` | 4 campos | 3 |
| pares de idioma | 7 | 2 |

Um campo perdido na LEITURA custou uma seção inteira na GRAVAÇÃO: o `..._ES`
correspondente ficava órfão, e como em Descarte o espanhol é obrigatório o
portal recusava a sub-aba toda — levando junto campos que já estavam certos.

`extrator._esperar_a_subaba_montar` espera duas contagens iguais e positivas.

---

## 3. Modais: eles travam tudo e não aparecem em log nenhum

Trocar o PDM abre:

> **Trocar PDM** — Você tem certeza? Todos os dados de Características Técnicas
> serão removidos. Deseja continuar? **[CONFIRMAR] [CANCELAR]**

Enquanto ele está aberto, **nenhum clique da página passa**. O sintoma são
`TempoEsgotado` em série, cada um reclamando do próprio botão:

```
[Erro] Não consegui clicar no SALVAR de 'Armazenamento': TempoEsgotado.
       Algo pode estar cobrindo o botão -- salve à mão.
```

Foram cinco salvamentos seguidos assim, e **três rodadas** atrás da hipótese
errada. O log nunca ia mostrar um modal; um print do usuário resolveu em um
minuto.

**Regra para função nova:** toda ação que possa abrir confirmação deve conferir
`//*[@role='dialog']` depois. O escopo `role="dialog"` importa — "CONFIRMAR"
sozinho casa outros botões da tela.

```python
sel.XPATH_DIALOGO_CONFIRMAR   # //*[@role='dialog']//button[...'CONFIRMAR']
```

---

## 4. Os combos `virtual-select` (`vscomp`)

Fabricante, fornecedor, PDM, unidade de medida e contrato — **cinco na mesma
tela**, todos do mesmo widget.

### O dropdown não é filho do combo

Ele é teleportado para `<body>`, sob `#reactContainer`. **Nenhum eixo XPath
liga um ao outro** — nem `following`, nem `ancestor`.

O que liga é o **número da instância**, que aparece nos dois ids:

```
<div id="vscomp-ele-wrapper-5438">      <- o combo, com o valor "PDM...."
<input id="vscomp-search-input-5438">   <- a caixa de busca dele, no body
```

O número é gerado a cada renderização (`IDS_GERADOS_NAO_USAR` continua
valendo: ninguém escreve `5438` no código). Mas ele pode ser **lido do DOM** e
recomposto com `concat` + `substring-after` — ver `_INSTANCIA_DO_PDM` em
`seletores_duplicada.py`. Copie o padrão para qualquer combo novo.

⚠️ **Não identifique a caixa de busca pelo placeholder.** A do PDM diz só
"Pesquisar", igual à do contrato. Procurar "PDM" falha, cai num seletor
genérico que casa as cinco caixas, e `safe_fill` escreve na primeira —
escondida, de outro widget. Foi assim que o log passou três rodadas afirmando
que `PDM.9900.000` não estava no catálogo. Estava.

### Clique na opção

Alvo: o `div[@role='option']`, não o `<span>` de dentro. E confira depois: o
valor do combo mudou?

### Quando o filtro não acha, ele diz — mas só no DOM

O combo não dá erro nem limpa nada: aparece uma linha no lugar da lista.

```html
<div class="vscomp-no-search-results" tabindex="0"
     aria-hidden="false">PDM não encontrado</div>
```

> **Origem:** HTML fornecido pelo usuário em 2026-09-22, olhando a tela. O
> comportamento em volta dele (quando aparece, quanto demora) **ainda não foi
> observado numa execução** — ver a pendência de 2026-09-22 sobre a cascata de
> busca de PDM.

Duas armadilhas, as duas já conhecidas deste arquivo:

1. **Teste `@aria-hidden='false'`, não a existência do nó.** É a mesma regra da
   §2 — o `vscomp` esconde em vez de remover. Um guard por presença diria
   "não encontrado" sempre.
2. **Não case o TEXTO.** A tela alterna PT/ES e a redação em espanhol é
   desconhecida (mesmo motivo de `PALAVRA_DA_SECAO`, em PENDENCIAS). Seletor
   que depende de texto não traduzido falha em silêncio.

Quem usa: `services/cria_fichas.AutomacaoPMIB._buscar_pdm`, que tenta o texto
completo, depois só o código, depois só o título — nessa ordem, conferindo este
elemento entre uma tentativa e a outra. Antes disso o fluxo apertava ENTER sem
perguntar nada, e um texto que não casava quebrava a automação três passos
adiante, **com o PDM certo já escolhido**.

---

## 5. Validação: o portal quase nunca diz o que está errado

### `required=False` não quer dizer opcional

Quem valida é o OutSystems, em JS. Exemplo real: em Condições/Transporte os
campos `..._ES` têm `required` **falso** no HTML e ainda assim recusam o
salvamento — só depois de tentar salvar é que a classe `not-valid` aparece.

**O oráculo é a classe `not-valid` DEPOIS de um SALVAR recusado**, nunca o
atributo `required` antes.

### A mensagem genérica não nomeia campo

`Por favor, verifique os campos` é tudo o que aparece no topo. O campo culpado
está marcado no DOM:

```python
page.locator("//*[contains(@class,'not-valid')] | //*[@aria-invalid='true']")
```

Foi assim que apareceu `<div class="div-not-valid">Selecione pelo menos um
elemento!</div>` no fieldset «Proteção» — **um grupo de checkbox obrigatório**
que ninguém sabia que existia, e que sozinho recusava a seção inteira.

### Colisão de referência: silêncio total

Escrevendo `RTC-45`, `RTC-45'D1` e `RTC-45'D2` em sequência:

| Referência | Entrou? | `not-valid` | mensagem | `CoincidenceReference` |
|---|---|---|---|---|
| `RTC-45` | não | `False` | `''` | **1** |
| `RTC-45'D1` | não | `False` | `''` | **1** |
| `RTC-45'D2` | **sim** | `False` | `''` | **0** |

Nem mensagem, nem `not-valid`, nem toast. **O único sinal é o bloco
`CoincidenceReference` estar na tela.** Ver `injetor.houve_colisao`.

### O portal normaliza o que você escreve

`3,8` vira `3.8` no campo. Conferência que compara string acusa divergência
falsa. Compare como número quando o campo for numérico.

---

## 6. Leitura da ficha em modo de VISUALIZAÇÃO

**Três padrões de campo**, e os três coexistem na mesma tela:

| Padrão | Rótulo | Valor |
|---|---|---|
| **A** — texto/número | `label[@data-label]/span` | `div[@data-block='PMIB_DataSheetView.Block_Expression']/span[@data-expression]` |
| **B** — opção marcada | `span.text-primary` (fora de label e legend) | dentro de `label[@data-label]` **sem** span |
| **C** — texto solto | `label/span`, ou `span.text-primary`, ou **a própria `<legend>`** | nó de texto de um `div[@data-container]` folha |

O padrão B **inverte** o A: o que num é rótulo, no outro é valor. O padrão C
não tem elemento nenhum em volta do valor.

⚠️ **O padrão C foi a causa raiz da semana perdida.** Ele atinge `Posição de
armazenamento`, `Necessidade de controle de temperatura` e **`Proteção`** —
este último sem rótulo de campo algum, só a legenda do fieldset. O bloco saía
vazio, o injetor não marcava nada, e o grupo é obrigatório.

### A armadilha do contador de anexos

O clipe de papel também é `<span data-expression>0</span>`. Só não é lido por
causa do namespace: `XPATH_VIEW_VALOR` exige o ancestral
`data-block='PMIB_DataSheetView.Block_Expression'`, e o badge está sob
`Numbers.Badge`. **Exigir o nome completo do bloco não é preciosismo** — é o
que separa valor de contador. Quando um campo está vazio e o seletor afrouxa,
o valor lido vira `'0'`.

### O espanhol está no DOM, e não precisa de `hover`

Cada texto longo é um `Block_ExpressionBothLenguage`: o visível é o português,
e o espanhol está num balão pendurado em `#reactContainer`, ligado por
`aria-describedby`.

```html
<div class="osui-tooltip__content" id="…-b25-b2-Content"
     aria-describedby="…-b25-b2-Tooltip">   <span data-expression="">PORTUGUÊS</span>
<div class="osui-tooltip__balloon-wrapper__balloon" id="…-b25-b2-Tooltip">
     <span data-expression="">ESPANHOL</span>
```

Medido numa página recém-aberta, sem nenhum hover: **47 balões já no DOM**.

⚠️ Não suba do rótulo por `following::div[…osui-tooltip__content][1]`: você
encontra primeiro o tooltip do **clipe de anexos** e lê "Documentos
associados". Foi por isso que o módulo passou dias afirmando que a ficha
original não tinha espanhol. Tinha.

⚠️ E ancore em `//fieldset`. Sem âncora o seletor é de PÁGINA: ao trocar de
sub-aba você conta N, lê o bloco N+1 que já sumiu, e `engine.texto` gasta os
30 s de timeout **e estoura**.

### Ids: quais servem

| Sufixo | Vale? |
|---|---|
| `StoragePosition`, `Stacking`, `Classification`, `TypeLegislation`, `TypeDiscart`, `Reserve` | ✅ semânticos, use |
| `Input_PackingLength`, `TextArea_…PT/ES`, `RadioButtonN-input`, `CheckboxN` | ✅ estáveis (o prefixo é que muda) |
| `b12-b20-b1-$b3`, `vscomp-search-input-5442`, `filepond--browser-h1d4zvekk` | ❌ gerados — ver `IDS_GERADOS_NAO_USAR` |

---

## 7. Sessão e ambiente

**O login do PMIB não sobrevive ao fechamento do navegador.** Os cookies que
autenticam (`nr1/nr2PMIB_Security`, `KEYCLOAK_IDENTITY`, `AUTH_SESSION_ID`) são
**de sessão** — morrem no `close()`, e nenhum perfil persistente muda isso.
"Mantenha-me conectado" prolonga a sessão no SSO, não o cookie do PMIB.

Consequência para ferramentas: script de uma tacada só cobra um login por
execução. Para explorar, mantenha **um** navegador vivo (é o que o MCP faz, e é
o que o `piloto` em `docs/OLHAR_O_PORTAL.md` faz).

A sessão também **expira sozinha** em cerca de uma hora de uso.

---

## 8. Escrevendo código novo: o checklist

Antes de dar o commit de uma função que toca o portal:

- [ ] Ela espera por **condição**, não por `sleep` fixo?
- [ ] A espera conta **tentativas** (para o teste que anula `sleep` não girar em
      vazio) em vez de olhar o relógio?
- [ ] Ela **confere o resultado** da própria ação, ou devolve `True` no instante
      do clique?
- [ ] Se pode abrir modal, ela confere `role='dialog'` depois?
- [ ] Se lê um campo que pode sumir, ela usa `element_exists` antes de `texto`
      (senão são 30 s de timeout e uma exceção)?
- [ ] Se escreve, ela relê para provar que ficou?
- [ ] Quando falha, a mensagem diz **qual campo** e **por quê**, ou só constata
      o sintoma?
- [ ] O seletor foi conferido contra o DOM real, ou escrito de memória?

E o corolário que este projeto pagou caro para aprender:

> **`scripts/check.sh` verde não é prova de portal.** Os testes rodam contra
> dublês escritos pelo próprio Claude — eles provam a ideia dele do portal, não
> o portal. Nada de RPA se declara pronto sem uma execução real.

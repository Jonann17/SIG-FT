# AutoSpecAI — caderno de melhorias

Documento de trabalho da frente do **Rafael** (`rafhagmm`). Registra o que foi encontrado,
o que já foi feito e o que **não pode ser esquecido antes de dar a frente por encerrada**.

- Regras de negócio: [`docs/base-conhecimento/08b-autospec-contexto-negocio.md`](base-conhecimento/08b-autospec-contexto-negocio.md)
- Como o código funciona: [`docs/base-conhecimento/08-autospec-backend.md`](base-conhecimento/08-autospec-backend.md)
- Fronteiras com a refatoração: [`docs/refatoracao/TRABALHO_PARALELO.md`](refatoracao/TRABALHO_PARALELO.md)

---

## 🛑 NÃO FECHAR A FRENTE SEM RESOLVER

> Checklist obrigatório. Antes de declarar o AutoSpecAI concluído, passar por cada item.

- [x] ~~Checkbox: `fill_save` falha em silêncio~~ — **RESOLVIDO em 2026-08-11**, ver R-09.
- [x] ~~Escrever a parte do AutoSpec no roteiro de teste~~ — feito em 2026-08-12:
      `docs/ROTEIRO_DE_TESTE.md`, **Etapa 3b**. Ela não existia; o item abaixo
      mandava rodar uma etapa que não estava escrita.
- [ ] **Rodar a Etapa 3b** numa ficha real, com manual anexado — é o único item
      que sobra, e ele não é meu: precisa de máquina com o app, chave de IA e
      um PDF de fabricante. O que volta de lá (páginas lidas, qual busca rendeu,
      % de recorte) é o que destrava as duas decisões ainda abertas: instalar ou
      não OCR local, e reescrever ou não as queries de busca.
- [x] ~~`bash scripts/check.sh` verde~~ — verde desde 2026-08-11 (1550 testes em 2026-08-12)
- [x] ~~Merge na linha oficial~~ — feito em 2026-08-11 (commit `75e0988`); tudo
      que veio depois foi commitado direto nela.

---

## Achados em aberto

> Nenhum achado em aberto no momento. Os 8 mapeados na revisão de 2026-08-11 foram
> resolvidos — ver abaixo.

## Resolvido

### ✅ R-21 🔴 Conta refeita em vez de descarte + auditoria da conversão *(2026-08-13)*

**A conta é refeita, não descartada.** Pedido do usuário: quando a IA converte errado, o dado de
origem é REAL — o errado é só a aritmética, e aritmética é o que computador faz sem errar.

```
[warn] 1 campo(s) tiveram a CONTA REFEITA: a IA leu o numero certo do documento
       e converteu errado. O valor gravado e o recalculado:
       · 6 - PRESSAO (MPa): a IA disse '3,5 MPa', gravei '35 MPa' — 3.5 -> 35 mpa (de 350 bar)
```

**Só quando não há dúvida sobre a origem.** Com duas pressões no documento (`350 bar` de
trabalho, `210 bar` de pico), o erro deixa de ser aritmético e vira de LEITURA — qual o campo
pedia? Aí o campo fica vazio e o console lista as opções. Chutar trocaria erro visível por erro
invisível.

**Não usei IA para revalidar**, e a preocupação que você levantou é o motivo: perguntar "está
certo?" convida concordância, e a conta é justamente o que o modelo já errou uma vez. O
recálculo determinístico não tem esse problema — e não gasta token.

**A precisão não é inflada:** `41 kg` → `90,4 lb`, não `90,3895 lb`. Escrever quatro algarismos
que o fabricante nunca publicou é uma afirmação falsa sobre a exatidão da medida.

### A auditoria — 3 bugs, um deles grave

Você pediu para conferir se havia mais bugs. Havia. Os 20 fatores de conversão e a ida-e-volta
de todas as unidades estão íntegros (conferidos numericamente); os furos estavam no parsing:

| # | Bug | Gravidade |
|---|---|---|
| **1** | **`IP65` era APROVADO contra documento que diz `IP67`** — o `65` aparecia em "65 mm" e a conferência olhava só os dígitos | **grave**: grau de proteção errado entrava na ficha pelo caminho que existe para impedir isso |
| **2** | `2.500` lido sempre como 2,5 — em documento PT é 2500 | erro de **mil vezes**, grande demais para parecer erro de digitação |
| **3** | **`0 bar` era "corrigido" para `350 bar`** | a correção virava invenção: nenhuma aritmética leva de 0 a 350 |

Correções: código alfanumérico agora tem de aparecer **inteiro** no documento; número ambíguo
gera as **duas leituras** e o documento decide; correção só dispara quando as unidades diferem
(houve de fato conversão).

### Navegador

- **`robots.txt` ilegível agora LIBERA** (sua decisão). Não conseguir ler a regra não é a regra
  dizer não — e proxy corporativo derruba `robots.txt` com frequência. `Disallow` explícito
  continua barrando.
- **Playwright entrou no `_bootstrap_venv.bat`.** O `pip install playwright` traz só a
  biblioteca Python; o navegador é um binário de ~150 MB baixado pelo processo Node, sem wheel
  que o carregue — por isso precisava de passo próprio. Agora roda sozinho na primeira vez, com
  carimbo, e **nunca derruba a instalação**: se falhar (comum atrás de Zscaler), o app abre
  igual e só os dois recursos opcionais ficam de fora.

23 testes novos.


### ✅ R-20 🔴 Conversão de unidade CONFERIDA + navegador como último recurso *(2026-08-13)*

**Conversão.** O lastro (R-19) reprovava `35 MPa` a partir de `350 bar` — conversão correta,
descartada. Decisão do usuário: conferir em vez de reprovar. `sigft/services/autospec_unidades.py`
(novo) **refaz a conta** a partir do número do documento — não confia no cálculo da IA:

```
  35 mpa    -> 350 bar        0.4 l/min  -> 400 ml/min      158 f  -> 70 c
  3.5 mpa   -> REPROVADO      9.9 l/min  -> REPROVADO
```

`3,5 MPa` a partir de `350 bar` é 10× errado e é exatamente o que ninguém percebe olhando.
9 grandezas (pressão, comprimento, massa, temperatura, vazão, potência, torque, rotação, área),
só stdlib. Toda conversão aprovada é **anunciada no console** com a conta — aprovar em silêncio
seria pior que reprovar.

**Dois bugs meus, achados pelos próprios testes:**

- *Herança de unidade em intervalo.* `0 a +70 C` — só o segundo número tem unidade, e sem
  herança o `0` escapava da conferência: num intervalo convertido bastaria acertar um limite.
  A 1ª versão herdava de qualquer distância, e o `1000` de `cs1000.pdf` herdou o `bar` de
  `350 bar` sete palavras adiante — `999 bar` passou a casar dentro de 1%. A herança agora só
  atravessa conector de intervalo.
- *Comparação na unidade base.* A base da vazão é m³/s, onde `0,4 l/min` e `50 ml/min` valem
  6,7e-6 e 8,3e-7 — pequenos o bastante para a tolerância absoluta aprovar **qualquer** par.
  Apareceu na saída como `0,4 l/min = 50 ml/min` (o certo é 400). A comparação passou a ser
  feita na unidade da resposta, que é como uma pessoa confere.

**Navegador (403 e página JavaScript).** `sigft/core/web/navegador.py` + `robots.py` (novos),
fora de `services/` porque a arquitetura proíbe serviço conhecer Playwright.

**A ordem é a política:** tenta o download simples → só se falhar → só se o `robots.txt`
permitir → abre o navegador. Um site que diz "não" continua recebendo "está bem".

> **Revisto no mesmo dia (R-21):** o `robots.txt` falhava **fechada** aqui. Por decisão do
> usuário, passou a falhar **aberta** — não conseguir ler a regra não é a regra dizer não.

404/500 **não** acionam o navegador: "não existe" não é "não quero". O gatilho real é o 403 e,
mais importante, a página que baixa quase vazia — assinatura de aplicação JavaScript, pior que
o 403 porque o documento "chega" e não parece falha.

Playwright ausente = segue sem, como o reforço semântico. 53 testes novos.


### ✅ R-19 🔴 Lastro documental + glossário em 5 idiomas *(2026-08-13)*

Pedido do usuário: *"não gostei do ato de aceitar uma informação errada. Isto não deve
acontecer."*

Desenho completo: [`docs/superpowers/specs/2026-08-13-lastro-documental-design.md`](superpowers/specs/2026-08-13-lastro-documental-design.md).

**A resposta honesta primeiro.** "Correto" não é verificável por código — se o datasheet do
fabricante estiver errado, nenhuma verificação automática descobre. **"Rastreável ao documento"
é 100% verificável**, e é a garantia mais forte que existe aqui. Agora são três camadas:

| Camada | Pergunta |
|---|---|
| 1. Filtro anti-intruso (§4.3) | o documento é **deste material**? |
| 2. **Lastro documental** (novo) | o valor **saiu mesmo do documento**? |
| 3. Conferência humana | o documento **está certo**? |

**A regra:** se o valor tem número, **todos** os números precisam estar no contexto — basta um
inventado para o campo ficar vazio. `"entre 175 e 999 bar"` cai mesmo com o `175` correto:
meia verdade num campo técnico é pior que campo vazio, porque passa na conferência por parecer
certa. Números são normalizados (`25,4` = `25.40` = `25.4`) para não descartar valor certo por
pontuação.

> **Revisto no mesmo dia (R-20):** esta versão reprovava conversão de unidade — `35 MPa` a
> partir de `350 bar` ficava vazio. Passou a ser **conferida** em vez de reprovada: a conta é
> refeita a partir do número do documento. Conversão errada continua reprovando.

**Isento:** os 12 `GENERATIVE_FIELDS` (embalagem, transporte, descarte…), que as regras §3.2
mandam gerar de conhecimento técnico e não têm datasheet de onde sair.

Demonstrado contra um documento que diz `IP67`:

```
[warn] 3 campo(s) ficaram VAZIOS porque o valor respondido nao aparece no documento:
       · 13 - GRAU DE PROTECAO      -> a IA respondeu 'IP65'
       · 17 - FAIXA DE TENSAO (CC)  -> a IA respondeu '35 MPa'
[warn] 1 campo(s) citam uma fonte que NAO esta entre os documentos lidos
```

`IP65` contra `IP67` é o erro que passaria na conferência humana por ser plausível. Não chega
à célula.

**Rastreabilidade já existia** (P-04, a lista `-> Origem dos dados` do console). Agora tem duas
vizinhas — campos não respondidos e campos bloqueados — e as três descrevem o destino de
**todo** campo que faltava.

**Glossário multilíngue (PT/EN/DE/ES/FR/IT), 318 equivalentes.** O parque de Itaipu é Voith,
Siemens, HYDAC, Andritz (alemão), Alstom/GE Hydro (francês), e a entidade é **binacional** —
espanhol é idioma oficial. Antes, datasheet alemão não casava termo nenhum (`pressao` ≠
`Druck`) e o trecho com a resposta era recortado fora. Verificado nos 4 idiomas: 6/6 dados
preservados em cada um.

54 testes novos.

### ✅ R-18 🔴 Fichas difíceis — o que ia quebrar depois que a 1188 passou *(2026-08-12)*

A 1188 passou (28 de 29 campos, 21 com URL de origem). Ela é o caso **fácil**. Este item cobre
o que o `_STATUS_PMIB` real também tem. Cada falha foi **reproduzida rodando o código**.

Desenho completo: [`docs/superpowers/specs/2026-08-12-fichas-dificeis-design.md`](superpowers/specs/2026-08-12-fichas-dificeis-design.md).

**A mais grave — o filtro falhava ABERTO.** Ficha sem fabricante e sem código dava
`_termos_do_filtro() == []`, e lista vazia significa "não filtre". A proteção §4.3 aceitava
qualquer documento justamente na ficha em que menos se pode confiar no resultado. Agora, sem
âncora, **a busca web não acontece** e o console diz o que fazer. Basta uma das duas âncoras.

| # | Falha reproduzida | Correção |
|---|---|---|
| F-1 | sem âncora, filtro aceita tudo | busca web pulada, com explicação |
| F-2 | `DIVERSOS`/`N/A`/`SEM MARCA` viravam fabricante | reconhecidos como ausência de fabricante |
| F-3 | `INDUSTRIA E COMERCIO LTDA` virava âncora | `_tokens_ancora_fabricante` separada de `_nome_curto_fabricante` |
| F-4 | `1/2` e `110` viravam código de peça (e `1/2` virou a 1ª query!) | letra+dígito, ou numérico com 4+ dígitos |
| F-5 | `123` casava dentro de `123456` | fronteira de palavra para termo curto/numérico |
| F-6 | download sem teto de tamanho | `stream=True`, corte em 40 MB |

**F-3 era defeito meu**, introduzido na correção anterior: o fallback "se limpar tudo, use o
original" é certo para BUSCAR e errado para FILTRAR. São decisões diferentes e agora são funções
diferentes.

**E uma tensão que o teste resolveu melhor que eu.** Minha 1ª tentativa contra F-5 descartava
tokens de até 2 caracteres — e apagou `3M` inteiro. Marca curta legítima (`3M`, `GE`, `NSK`) não
pode ser jogada fora por ser curta. Fronteira de palavra resolve os dois lados.

**Três coisas que o console do teste bem-sucedido denunciou:**

- `tmp1wgju9r5.pdf: 6 pagina(s)` — nome do temporário. Agora mostra a URL.
- `Download recusado (HTTP 403)` — era o site do fabricante bloqueando robô, e parecia defeito
  do app. Agora diz isso.
- 29 faltantes → 28 origens: o 29º (`var_row_88`, "10 - PRECISAO") sumia em silêncio. Agora há
  uma lista de "campos que a IA não respondeu, preencha à mão".

30 testes; red-green conferido (22 falharam antes, 30 passam depois).

### ✅ R-17 🔴 Busca web achava, e o próprio código jogava fora *(2026-08-12)*

Falha real, ficha 4500063671.1188 (sensor HYDAC `CS1320-A-0-0-0-1/-000`), **sem PDF anexado**:
minimax preencheu 3 de 22 especificações, grok preencheu **0 de 22**.

O grok preencher zero foi **obediência, não burrice** — o prompt manda não inventar e ele não
recebeu contexto nenhum. Os 3 do minimax vieram do conhecimento dele, sem fonte conferível, o
que é pior que vazio. Trocar de modelo nunca resolveria: o erro estava antes da IA.

Desenho completo, com todas as medições: [`docs/superpowers/specs/2026-08-12-busca-web-datasheet-design.md`](superpowers/specs/2026-08-12-busca-web-datasheet-design.md).

**A hipótese que caiu primeiro.** Suspeita inicial: a razão social `HYDAC TECNOLOGIA LTDA`
poluía a query. Testado contra busca real — **a query funcionava**, a página certa vinha em 1º
e 3º lugar. Sem esse teste, a "correção óbvia" teria sido implementada sem resolver nada.

**D1 — o filtro anti-intruso era uma guilhotina.** Exigia a razão social INTEIRA como substring
do título/link. As páginas dizem `HYDAC`; nenhuma diz `HYDAC TECNOLOGIA LTDA`. O segundo termo
era o código interno do PMIB, que não existe na internet. **Medido: 0 de 4 resultados corretos
sobreviviam.** Nada era baixado.

**D2 — a cascata procurava o SKU, não o datasheet.** Buscava só `CS1320-A-0-0-0-1/-000`, que é
código de configuração de loja. O datasheet é publicado para a FAMÍLIA (`CS 1000 Series`).
Medido: código completo → páginas de e-commerce; família + `filetype:pdf` → **10 datasheets**.

**Colateral, também medido:** a razão social degrada o ranking (1 relevante de 7, contra 10 de
10 sem ela). A hipótese inicial não estava errada — estava **incompleta**.

| | Antes | Depois |
|---|---|---|
| Resultados corretos que passam o filtro | 0/4 | 3/4 |
| Concorrente (Parker) barrado | sim | sim |
| Queries que pedem PDF | 0 | 2 |
| Busca pela família do produto | não | sim |

Descartar 100% dos resultados virou `warn` listando os termos — era linha `info` no meio das
outras, e foi ela que escondeu a falha.

24 testes com os resultados **reais** do Google como fixture; red-green conferido revertendo o
código (22 failed → 24 passed).

> **Não resolvido:** seguir o link do PDF dentro da página do produto (mini-crawler), e página
> de fabricante em JavaScript, cujo HTML estático é magro. Ver §6 do desenho.

### ✅ R-16 🔴 Cache de resposta da IA — 100% de economia no rerun *(2026-08-12)*

Reprocessar um lote é o **normal**, não a exceção: se um campo saiu errado, o usuário ajusta a
planilha e roda tudo de novo. Até aqui cada rerun repagava a IA por ficha inteira, incluindo as
que já tinham vindo certas.

**A chave é o prompt inteiro** (hash SHA-256 de `provider|modelo|prompt`), não o nome do
arquivo. É o que torna o acerto seguro: o prompt já contém material, fabricante, contexto
recortado e a lista de campos faltantes, então tudo que mudaria a resposta já muda a chave.

| Situação | Comportamento | Por quê |
|---|---|---|
| Rodou de novo, nada mudou | **acerto** — 0 token | é a economia |
| Renomeou o arquivo, nada mudou | acerto | o nome não entra na chave |
| Editou a ficha / trocou o manual | chamada nova | contexto mudou |
| Trocou de modelo | chamada nova | servir a resposta do modelo A como se fosse do B tornaria a comparação entre modelos uma mentira |
| A IA falhou | **não guarda** | congelar a falha faria o rerun devolver o mesmo vazio para sempre |

**Duas decisões que não são óbvias:**

- **O que volta do cache é a resposta CRUA, replicada pela mesma normalização** do caminho
  vivo. Guardar o resultado já normalizado pareceria mais simples e perderia em silêncio o
  `ultimas_fontes_por_campo` — de que o `fill_save` depende.
- **O disco guarda o hash, nunca o prompt.** Medido num PDF real: o arquivo de cache tem 498
  chars contra 7.000 do prompt, e não contém nem o texto do datasheet nem o preâmbulo. Guardar
  o datasheet num `.json` ao lado do app contradiria em casa a decisão de mandar o mínimo para
  fora. Gitignored.

Medido, encadeado com o retrieval, num PDF real de 30 páginas lido inteiro pelo PyMuPDF:

```
1a execucao: 1 chamada,  ~1750 tokens de entrada   (o retrieval ja tinha cortado)
2a execucao: 0 chamadas,    ~0 tokens
respostas identicas: True   ·   fontes preservadas: True
```

31 testes.

### ✅ R-15 🟡 `json_mode=True` na chamada do AutoSpec *(2026-08-12)*

O prompt **pedia** JSON em texto (`Retorne JSON {ID: ...}`) e era só isso — o formato dependia
da boa vontade do modelo, e o `_limpar_e_parsear_json` (que raspa cercas ```` ```json ````) era
o único anteparo. Falha de parse ali devolve a ficha **vazia**.

Com o flag, os três providers pedem JSON nativo ao servidor (`response_mime_type` no Gemini,
`response_format` no OpenRouter/compat) e a limpeza vira rede de segurança em vez de caminho
principal. Passou a importar mais agora que o provedor é trocável: confiabilidade de formato
varia muito entre modelos.

Tem teste percorrendo a corrente inteira (`generate_ai_response` → `LLMClient` → provider),
porque um elo que engolisse o argumento no meio não apareceria de outro jeito.

> **Fora desta frente:** outros 3 dos 5 consumidores de IA do projeto (`analyzer`,
> `cria_fichas`, `upload_conditions`) estão sem o flag e no mesmo risco. Registrado em
> `docs/refatoracao/PENDENCIAS.md` e **não corrigido de carona** — são arquivos da refatoração
> do Luan.

### ✅ R-13 🔴 Frente 3: retrieval de verdade — 85% menos token *(2026-08-11)*

O módulo não fazia RAG, fazia **context stuffing**: concatenava os documentos inteiros
(60.000 chars/manual, 50.000/doc web) e mandava tudo para responder campos que precisam de
umas 20 linhas.

`sigft/services/autospec_rag.py` (novo) quebra o contexto em trechos, indexa com **BM25** e
manda só o que responde os campos pedidos. **Medido num datasheet de 40 páginas: 23.524 →
3.628 tokens (85% a menos), com 7/7 dos dados procurados preservados.**

**O furo que a medição encontrou — e que teria passado despercebido.** A primeira versão usava
BM25 puro, e a verificação mostrou:

```
consulta : "6 - PRESSAO DE TRABALHO (Indicar a pressao de trabalho)"
secao    : "Maximum operating pressure 175 bar. Peak pressure 210 bar."
em comum : NENHUM TOKEN
```

**A ficha pergunta em português; o datasheet responde em inglês.** `pressao` não casa com
`pressure`. Dois de cinco dados sumiam do contexto — exatamente o risco de "recorte que perde
informação". Pior: `peso` "funcionava" por acidente, casando em `kg`.

Meu argumento original de que "lexical ganha neste domínio" estava **incompleto**: vale para
código de peça (`PVF100-4`), não para o vocabulário técnico traduzido. Corrigido com um
**glossário PT→EN** (~55 pares) aplicado como expansão **aditiva** de consulta — o termo
original continua valendo, então código de peça e unidade seguem casando direto. As perguntas
da ficha são um conjunto fechado, o que torna o glossário determinístico e auditável.

**Duas travas contra o recorte piorar as coisas:**

- **Proveniência sobrevive.** O marcador `--- LOCAL DOC: x ---` / `--- WEB DOC: y ---` é
  reemitido em cada trecho, e LOCAL vem antes de WEB. Sem isso a instrução 1 do prompt
  (`Priorize "LOCAL DOC"`) viraria letra morta em silêncio.
- **Documento pequeno vai inteiro.** Medido: um contexto de 11.302 chars virava 12.171 depois
  do recorte, porque quase todo trecho era selecionado e cada um repetia o marcador. Abaixo de
  10% de ganho, o recorte é dispensado.

24 testes.

### ✅ R-14 🟡 Frente 3b: reforço semântico OPCIONAL *(2026-08-11)*

`sigft/services/autospec_embeddings.py` (novo) reordena os candidatos do BM25 por similaridade
de embedding, num arranjo **híbrido** (peso 0.5 — descartar o lexical entregaria o casamento de
código de peça ao modelo, que é onde ele erra) e no padrão *"recupera largo, reordena
estreito"*.

**É complemento, nunca requisito — e isso não é teórico.** Ao construir o módulo, o download do
modelo multilíngue falhou com **`ProxyError: 403 Forbidden`** no próprio ambiente de
desenvolvimento. Se o caminho semântico fosse obrigatório, o AutoSpec teria parado ali. Por
isso `fastembed` **não** entra no `requirements.txt`: uma dependência que pode falhar no
download não pode estar no caminho crítico da instalação pelo `.bat`.

Verificado nos três caminhos, todos preservando 5/5 dos dados e economizando 77%:

| Caminho | Resultado |
|---|---|
| Só BM25 + glossário (o que roda hoje) | 5/5 |
| Com reforço semântico | 5/5 |
| Reforço **quebrando no meio** | 5/5 — degradou sem perder nada |

O que o semântico acrescenta quando está disponível é o termo que ninguém cadastrou no
glossário: "vida útil" casando com "service life expectancy". Para ligar, na máquina de quem
quiser: `pip install fastembed`. O console diz, uma vez por lote, se está ativo ou não — sem
isso, "o embedding está ligado?" viraria adivinhação.

17 testes, com codificador injetado. **Ressalva honesta:** eles cobrem a lógica deste módulo,
não a biblioteca real — que não pôde ser exercitada aqui por causa do proxy.

### ✅ R-12 🔴 Frente 2 (camada 1): leitura local de PDF, com prova de que foi lido inteiro *(2026-08-11)*

**Decisões do usuário:** `1a` — só a camada local por enquanto; `2a` — leitura incompleta
avisa e segue.

**O problema que isto fecha.** A única aferição de "consegui ler" era:

```python
if t and len(t) > 100:
```

Cem caracteres. Um datasheet de 40 páginas do qual se leu **uma linha da capa** passava nesse
teste e entrava no contexto como se fosse o documento inteiro. A IA respondia "não encontrei"
para tudo, e nada no log dizia que o problema tinha sido a **leitura**, não o documento.

**PyMuPDF como primeira camada** (`_ler_pdf_local`). Preferido ao PyPDF2 por dois motivos:
preserva a ordem de leitura do layout — o PyPDF2 entrega texto corrido e **desmancha tabelas**,
e datasheet é quase só tabela — e entrega o texto **página a página**, que é o que permite
medir cobertura. Wheel pura, instala pelo `pip` sem binário de sistema, o que importa porque o
`SIG-FT.bat` só resolve o que o `pip` resolve.

**`RelatorioLeitura`** mede e o console mostra:

```
manual.pdf: 5 pagina(s), 5 lida(s) (100%), 594 chars [PyMuPDF]

misto.pdf: 5 pagina(s), 3 lida(s) (60%) — LEITURA INCOMPLETA. Sem texto nas
paginas: 3, 5. Provavelmente escaneadas; precisariam de OCR. Seguindo com o
que foi lido — confira os campos que dependiam dessas paginas.
```

Página com menos de 40 caracteres não conta como lida (número de página solto não é
conteúdo); cobertura abaixo de 80% marca o documento como incompleto. As páginas faltantes são
numeradas **1-based**, como o usuário conta.

**Inversão de privacidade, de brinde:** a nuvem (LlamaParse) era tentada **primeiro** sempre
que houvesse chave — o arquivo inteiro subia para a LlamaCloud mesmo quando o PDF tinha camada
de texto e podia ser lido aqui, de graça e sem sair da máquina. Agora a ordem é
**PyMuPDF → PyPDF2 → LlamaParse**, e ao recorrer à nuvem o log diz explicitamente que
*"o arquivo SAI da rede"*. Alinhado à decisão de privacidade registrada acima.

**O que continua faltando (consciente):** página realmente escaneada não é lida sem OCR. O
relatório diz quais são — é com esse número na mão que se decide se vale pagar o custo de
implantação do Tesseract (binário de sistema) ou do Docling (~500 MB + torch). 11 testes,
com os PDFs construídos no próprio teste pelo PyMuPDF (nenhum binário entra no repositório).

### ✅ R-11 🔴 Frente 1: a query se auto-sabotava *(2026-08-11)*

**Causa raiz de "o script não acha o que eu acho no Google em 5 segundos".**
O CSE do usuário estava correto (web inteira, sem sites) — o problema era a query.

O script mandava a **descrição inteira, em português**:

```
CONJUNTO REPARO PARA BOMBA 3527528 PVF100-4 NBR Hydac datasheet specs
```

O Google trata cada palavra como termo. `CONJUNTO`, `REPARO`, `PARA`, `BOMBA`, `NBR` são
prosa PT-BR e **não existem num datasheet da Hydac, escrito em inglês** — cada uma empurrava o
documento certo para baixo. E o truncamento do P-02 cortava do FIM, descartando primeiro
`PVF100-4` e `3527528`, os tokens que valem, e preservando a prosa.

`_identificadores` isola os tokens que parecem código de peça ou modelo (contêm dígito, 3+
caracteres) e a cascata passou a começar por eles — fabricante + identificador, curto, igual
ao que uma pessoa digita à mão. A prosa virou **fallback**, não a primeira tentativa:

```
1. Hydac 3527528 PVF100-4 datasheet     <- a query "humana"
2. Hydac PVF100-4 datasheet             <- só o modelo, mais reconhecível
3+. a prosa truncada (comportamento antigo, para descrição sem identificador)
```

Junto, duas decisões do usuário:

- **`gl=br`/`hl=pt` removidos.** Pediam ao Google resultado BRASILEIRO em PORTUGUÊS —
  exatamente o viés que derruba datasheet estrangeiro. O navegador dele, onde acha em 5
  segundos, não tem esse viés.
- **`num` de 3 para 10.** O CSE cobra a MESMA cota (1 query) para 3 ou 10 resultados; pedir 3
  jogava fora 70% do que já estava pago.

**Cache de busca** (`busca_web_cache.json`, TTL 7 dias, gitignored, mesmo padrão dos caches de
catálogo de modelo): guarda query → resposta crua da CSE. Reprocessar o mesmo lote — o normal
quando se ajusta um manual e roda de novo — deixou de queimar a cota inteira. Guarda as URLs,
não os arquivos: caminho de temporário não sobrevive à execução, mas a URL sim, e é ela que
custou cota.

24 testes novos. Fica em aberto medir, com o usuário, se a taxa de acerto subiu de fato —
é o próximo passo de validação real.

### ✅ R-09 🔴 P-01: checkbox por RÓTULO, e descarte deixou de ser mudo *(2026-08-11)*

**O diagnóstico mudou depois de olhar a ficha real.** A pergunta não era "o que a IA
responde?" — era por que o prompt oferecia `['G25','G27','G29']`. Endereço de célula não diz
nada a um modelo de linguagem: mesmo um acerto era **chute entre 3 opções**. Não é um problema
de qualidade a ser medido, é defeito de projeto — e por isso deu para corrigir sem a execução
real que eu tinha pedido.

O rótulo legível está na própria planilha, ao lado da marcação. `_rotulos_do_checkbox` o lê nas
duas disposições existentes (à direita na mesma linha; na linha de cabeçalho acima, para os 2
grupos da linha 69), ignorando células que são marcação de OUTRO grupo — sem isso, varrer à
direita de `J69` alcança `P69` e devolve `"x"` como rótulo.

**Validado na ficha real: 20/20 rótulos extraídos, 0 falhas.** O prompt passou de
`(Opções: ['G25','G27','G29'])` para `(Escolha UMA: ['Vertical','Horizontal','Indiferente'])`.

`_resolver_celula_checkbox` aceita **endereço** (forma antiga, preservada), **rótulo** (sem
acento, sem caixa) e **rótulo dentro de frase** — só quando um único rótulo casa, para não
escolher no chute. E o que não casar agora **gera aviso**, com resumo no fim: a falha
silenciosa que era o coração do P-01 deixou de existir.

Ficha sem rótulo encontrável continua funcionando pelo endereço — compatibilidade total.

### ✅ R-10 🔵 P-07: leitura com `data_only`, escrita sem *(2026-08-11)*

Decisão do usuário: abrir o arquivo duas vezes. `analyze_sheet` mantém o workbook SEM
`data_only` (é o que `fill_save` salva — `data_only=True` descartaria as fórmulas na gravação)
e abre um segundo, COM `data_only=True`, só para leitura. Sem isso, `is_empty` enxergava o
texto da fórmula (`"=A1"`) e tratava como preenchida uma célula cujo valor calculado é vazio.

Fallback: planilha nunca aberta no Excel não tem valor em cache e `data_only=True` devolve
`None` em toda fórmula — nesse caso volta à leitura direta, melhor que tratar a ficha inteira
como vazia.

### ✅ R-04 🟡 P-02: cascata de busca web ganhou o passo 3 *(2026-08-11)*

As regras de negócio (§4.2) descrevem 3 passos; o código tinha 2. Descrição longa e específica
não retorna nada no Google, e a ficha ficava sem contexto web — provável causa nº 1 de ficha
voltando vazia. `_montar_queries_busca` implementa o truncamento progressivo **por PALAVRA**
(decisão do usuário; cortar 4 caracteres, como o texto original sugeria, parte o token no meio
— `"PVF100-4"` → `"PVF10"` — e produz query pior que a anterior), com piso de 2 tokens e o
fabricante preservado em todas as rodadas (é ele que ancora o filtro anti-intruso).

Validado contra a ficha real `4500063671.0662`, que gera 6 queries degradando bem:

```
1. CONJUNTO REPARO PARA BOMBA 3527528 PVF100-4 NBR Hydac datasheet specs
2. CONJUNTO REPARO PARA BOMBA 3527528 PVF100-4 Hydac datasheet specs
...
6. CONJUNTO REPARO Hydac datasheet specs
```

Corrigido junto um defeito que só apareceu ao mexer aqui: o `break` da cascata disparava
quando a busca **devolvia arquivos**, não quando algum arquivo **virava contexto**. Três PDFs
ilegíveis encerravam a cascata e as queries mais genéricas nunca eram tentadas.

### ✅ R-05 🟡 P-03: imagens vão para o OCR *(2026-08-11)*

`.tif/.tiff/.png/.jpg/.jpeg/.bmp/.webp` passam pelo LlamaParse (que faz OCR) em vez de caírem
no BeautifulSoup como se fossem HTML. Sem chave do LlamaParse, o documento é ignorado **com
aviso**, em vez de virar texto-lixo em silêncio. O `_sufixo_para_url` também deixou de errar
com URL de PDF com query string (`.../datasheet.pdf?download=1`) e passou a olhar o
`Content-Type` da resposta.

### ✅ R-06 🟡 P-04: rastreabilidade campo→fonte *(2026-08-11)*

O prompt passou a pedir `{ID: {"valor": ..., "fonte": ...}}`, e o `process_queue` lista a
origem de cada campo no console — as regras §3.4 pedem isso para o engenheiro revisar antes de
homologar.

**Compatibilidade, que era o risco real desta mudança:** `_normalizar_resposta_ia` aceita as
DUAS formas. Se o modelo ignorar a instrução (modelo mais fraco, prompt truncado), a resposta
antiga `{campo: valor}` continua funcionando e só a fonte se perde. O **contrato de retorno de
`generate_ai_response` não mudou** — `fill_save` recebe o mesmo dicionário achatado de sempre e
não foi tocado.

Dependentes atualizados junto (era o cuidado pedido): a fixture congelada
`tests/fixtures/prompts/autospec_prompt.txt` (regenerada a partir da saída real, diff conferido
linha a linha), `tests/test_llm_prompts_snapshot.py`, `tests/test_llm_prompts.py`.

> ⚠️ `core/llm/prompts.py` é **zona compartilhada** — a mudança foi num commit isolado, com
> mensagem explícita e registro em `PENDENCIAS.md`, conforme `TRABALHO_PARALELO.md` §4.

### ✅ R-07 🟡 P-05: falhas deixaram de ser silenciosas *(2026-08-11)*

- Busca web: `except Exception: return []` mudo → log de erro com tipo e query. Cota diária do
  CSE estourada era indistinguível de "não achei nada".
- `PDFProcessor`: os três `except ... pass` agora dizem qual etapa falhou e por quê; PDF sem
  camada de texto (escaneado) é avisado explicitamente.
- `generate_ai_response`: `print(f"Erro IA: {e}")` ia para o **stdout** — a janela preta que
  ninguém olha. Agora vai pelos callbacks, como o CP 4.4 padronizou.
- Documento web descartado por texto insuficiente e resultado barrado pelo filtro anti-intruso
  passaram a aparecer no console.
- `" -> Consultando Gemini..."` virou `" -> Consultando a IA..."`: o provedor vem da seleção do
  usuário e a mensagem envelheceria igual à do guard de chave.

### ✅ R-08 🔵 P-06: varredura para na última linha preenchida *(2026-08-11)*

O laço ia até `ws.max_row`, que no openpyxl conta linha com **formatação**. Na ficha real as
perguntas acabam na 103 e `max_row` é 132; num template formatado até o fim, dezenas de
milhares de iterações inúteis por ficha. Agora encerra após
`MAX_LINHAS_VAZIAS_SEGUIDAS = 25` linhas sem pergunta — folgado para atravessar um bloco de
layout no meio da lista, curto para não varrer a planilha inteira. Seguro porque as perguntas
são numeradas em sequência (ver Anexo B do doc de contexto de negócio).

### ✅ R-01 🔴 `get_pmib_data` casava com o material errado *(2026-08-11)*

A comparação era `if code_suffix in val_pmib` — substring do sufixo de 4 dígitos contra o
código inteiro, **prefixo de contrato incluído**. Como `PREFIXO_CONTRATO` (`"4500063671"`)
contém ele mesmo sequências de 4 dígitos, **7 sufixos** (`0006`, `0063`, `0636`, `3671`,
`4500`, `5000`, `6367`) casavam com **qualquer** linha da planilha — e a função devolvia
descrição e código de material da **primeira linha**, de um material diferente.

Como o retorno alimenta o contexto RAG **e** as queries de busca web, a IA pesquisava e
preenchia a ficha inteira com base no material errado, em silêncio. É literalmente o cenário
que as regras de negócio (§1.3) classificam como pior que campo vazio.

Corrigido comparando sufixo com sufixo, via `core.excel.pmib_codes` (implementação única do
CP 1.2). De quebra conserta um **falso negativo**: quando o Excel guarda o código como número,
`4500063671.1050` vira o float `4500063671.105` e a busca antiga falhava — `normalize_pmib`
restaura o zero à direita. Casos legítimos preservados: apóstrofo do Excel, coluna só com o
sufixo, código no meio de texto livre. 22 testes em `tests/test_autospec_match_pmib.py`.

### ✅ R-02 🟡 Google CSE sem timeout *(2026-08-11)*

`search_and_download` chamava `requests.get(...)` sem `timeout`, então uma chamada pendurada
travava o módulo inteiro por tempo indefinido. `_download_file`, logo abaixo, já usava
`timeout=15`. Alinhado ao mesmo valor.

### ✅ R-03 🟡 Guard de chave preso ao Gemini *(2026-08-11)*

`__init__` exigia `gemini_key` mesmo quando o provedor resolvido era OpenRouter — quem
configurasse só `OPENROUTER_API_KEY` não conseguia usar o módulo. Agora o guard resolve o
provedor da tarefa (mesma cadeia do `get_llm`, resolvida uma vez só) e cobra a chave daquele
provedor. A mensagem é uma só, com provedor e chave interpolados, sem nenhum provedor
hardcoded no texto — decisão tomada olhando para a migração para OpenRouter.
16 testes em `tests/test_autospec_guard_chave.py`.

---

## 🔒 Decisão de arquitetura — postura de privacidade (2026-08-11)

**Decidido pelo usuário (Rafael).** Vale para todo o trabalho de melhoria daqui em diante.

### Alvo: cenário 2 — só a IA interna da empresa

Nenhum conteúdo de datasheet vai para Google, OpenRouter, Anthropic ou qualquer provedor
público. A IA usada é exclusivamente o endpoint OpenAI-compatível da empresa, já previsto em
`config.PROVIDER_OPENAI_COMPAT` (`EMPRESA_LLM_BASE_URL` + `EMPRESA_LLM_API_KEY`).

### Realidade de hoje: a chave ainda não existe

Por isso o cenário 2 **não pode ser o único caminho** — o módulo ficaria inutilizável até a
empresa liberar a chave. O combinado é uma **cadeia com degradação automática**:

```
1. IA interna da empresa (openai_compat)          ← alvo, preferido sempre que der
       │  falha: chave ausente, base_url ausente, endpoint fora do ar, erro na chamada
       ▼
2. OCR local + só os TRECHOS relevantes para a nuvem   ← fallback automático
```

**O que "falha" significa, explicitamente:** `EMPRESA_LLM_API_KEY` ausente ou vazia,
`EMPRESA_LLM_BASE_URL` ausente ou vazia, endpoint inalcançável, ou qualquer erro na chamada
depois dos retries da política da tarefa.

**Regras que o fallback tem de respeitar:**

1. **Nunca silencioso.** Cair para o cenário 3 muda para onde o dado vai — o usuário precisa
   ver no console, em `nivel="warn"`, qual caminho está sendo usado e por quê.
2. **Mesmo no fallback, o mínimo sai.** O cenário 3 pressupõe OCR local (sem LlamaCloud) e
   envio apenas dos trechos recuperados, nunca do documento inteiro. O fallback reduz a
   proteção, não a abandona.
3. **A escolha é registrada por ficha**, junto da rastreabilidade campo→fonte do P-04, para
   auditoria posterior.

### Consequências para o desenho das melhorias

- O **OCR tem de ser local** nos dois cenários — é o que elimina o LlamaCloud, que hoje é a
  maior exposição (recebe o arquivo inteiro).
- **Embeddings/seleção de trechos também locais** — no cenário 2 por coerência, no cenário 3
  por necessidade.
- A busca web (Google CSE) é assunto separado: ela expõe a *query*, não o datasheet. Fica
  fora desta decisão, mas vale confirmar com a empresa se a descrição do material pode ir
  para o Google.

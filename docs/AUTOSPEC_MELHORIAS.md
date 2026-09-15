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

### ✅ R-27 🔴 A conferência deixou de morrer junto com o aplicativo *(2026-08-17)*

**Relato do Luan, usando a ferramenta:** o lote roda, a lista de duvidosos aparece — e conferir
link por link leva tempo. Se ele precisa fechar o aplicativo antes de terminar, **perde o
processamento inteiro**: os links, o agrupamento por ficha e o que já tinha conferido. Rodar de
novo custa cota de CSE e tempo de IA, e o R-26 tinha acabado de criar essa lista justamente
para não jogar informação fora.

#### O que passou a existir

```
lote termina  ->  ⚠️ 6 documentos em 3 fichas para conferir
                  Conferencia salva em: ...\CONFERENCIA_AUTOSPEC_2026-08-17_1841.txt   ← sozinho
   ↓ (fecha o app, vai almoçar, volta no dia seguinte)
Seção 5 vazia  ->  [IMPORTAR CONFERÊNCIA (.txt)]  ->  links de volta, COM as marcações
   ↓
[PROCESSAR OS DOCUMENTOS MARCADOS]  ->  2ª passada normal
```

**Três decisões que não eram óbvias:**

| Decisão | Por quê |
|---|---|
| `.txt`, não JSON | O arquivo é para ser **lido e editado por uma pessoa**: abre no Bloco de Notas, clica no link, marca `[x]`. Um `JSONDecodeError` por uma vírgula seria a mesma perda que o recurso veio evitar. O parser aceita `[X]`, `[ x ]`, `[*]`, comentário no meio e linha em branco sobrando |
| **Salva sozinho** no fim do lote, além do botão | O botão só protege quem lembra de clicar. O relato foi de alguém que precisou fechar o app — e quem fecha às pressas não clica em nada |
| A seção **não se esconde mais** | O botão IMPORTAR precisa estar visível para quem acabou de abrir o aplicativo e ainda não processou nada. Escondida, o recurso não existiria para o caso que o motivou |

Onde salva: **pasta do `_STATUS_PMIB`** (pedido do usuário — é a pasta que ele já tem aberta).
Sem status utilizável, cai na pasta da ficha. O nome leva data e hora e **nunca sobrescreve**:
perder a conferência de ontem ao exportar a de hoje seria repetir o bug.

#### O que a verificação pegou

A suíte passou de primeira; o que achou problema foram as **mutações** e o **roteiro de ponta a
ponta**.

- **Mutação sobrevivente nº 1 — um guard meu era código morto.** Desliguei o `if not
  atual["ficha"]: continue` do parser e o teste continuou verde: quem realmente descarta link
  sem `FICHA:` acima é o `_fechar()`. Guard redundante que *parece* carregar peso engana quem
  ler depois — removido, com comentário dizendo onde a regra mora de verdade.
- **Mutação sobrevivente nº 2 — um teste meu não testava nada.** O teste de ordem do `_worker`
  usava `ast.walk`, que percorre em **largura**: trocando as duas chamadas de lugar ele
  continuava passando. Ordenado por `(lineno, col_offset)`, pega.
- **`classificar_resultado` com fabricante em string.** Achado escrevendo o roteiro, onde eu
  mesmo passei `"WAGO"` em vez de `["WAGO"]`: iterar a string dá `'W','A','G','O'`, termo de 1
  caractere nunca casa, o fabricante "some" e **todo** resultado vira `duvidoso` — em silêncio.
  Nenhum chamador de hoje passa string (`_tokens_ancora_fabricante` devolve lista), então é
  blindagem, não bug vivo. Uma linha, com teste.

**Ponta a ponta, com o filtro real e arquivo real no disco:** os 4 resultados do console da
ficha WAGO separados nos três destinos (oficial → `certo`, distribuidor e camiseta →
`duvidoso`, resenha de fone → `descartado`), `.txt` gravado, editado como uma pessoa editaria
(`[ X ]` com espaço, comentário escrito no fim, **salvo em ANSI**), reimportado, e a 2ª passada
baixando **só** a URL aprovada — a camiseta nunca foi baixada, o manual local foi junto.

**Ordem que virou teste:** `_conferencia_mostrar` **antes** de `_conferencia_salvar` no
`_worker`. O salvamento lê `self.marcados_conf` e é o `_mostrar` quem recria a grade;
invertido, o `.txt` automático sairia com as marcações do **lote anterior** — arquivo plausível
e errado, a pior categoria de bug deste módulo.

43 testes novos (35 no serviço, 8 na tela por AST — `frontend.py` não é importável).


### ✅ R-26 🔴 Conferência humana dos documentos duvidosos — a tela e a 2ª passada *(2026-08-13)*

O R-25 criou o destino `duvidoso` e não tinha para onde mandá-lo: o documento saía do contexto
e sumia. Esta é a outra metade — **o duvidoso vira uma pergunta para o engenheiro**, em vez de
uma decisão que o programa não tem como tomar.

#### O desenho, com as três decisões do usuário

| Pergunta | Decisão *(2026-08-13)* |
|---|---|
| Interromper a fila em cada dúvida, ou juntar tudo? | **Processa a fila inteira**, e no fim mostra a lista agrupada por ficha |
| O que basta para um resultado ser `certo` sozinho? | Citar **fabricante E modelo** — uma das duas não basta, vai para conferência |
| Onde a lista aparece? | **Seção nova na tela do AutoSpec**, não janela separada |

#### Como ficou

```
[fila roda inteira]  ->  ⚠️ 6 documento(s) em 3 ficha(s) precisam da SUA conferencia.
                              · 1188.xlsx: 2 link(s)
   ↓
Seção 5 da tela:  📄 1188.xlsx — WAGO / 750-362
                    ☐ 🔗 750-362 Modbus TCP coupler — Farnell      (abre no navegador)
                    ☐ 🔗 Minnie Mouse t-shirt — Target
   ↓
[PROCESSAR OS DOCUMENTOS MARCADOS]  ->  2ª passada, só com o que foi marcado
```

O link é clicável (`webbrowser.open`) porque conferir sem abrir o documento não é conferir.

#### O que a 2ª passada faz de diferente

`processar_conferidos` **não é** `process_queue` com outra entrada. A diferença é o contexto:
os documentos vêm de uma lista fechada de URLs **já julgadas por uma pessoa** e, por isso,
`contexto_das_urls` **não aplica o filtro anti-intruso**. Passar de novo desfaria a conferência
— o filtro existe justamente para decidir o que o engenheiro acabou de decidir. É a única porta
do módulo em que um documento entra sem passar pela §4.3, e ela existe porque alguém olhou.

Fora isso, o caminho é o mesmo de sempre: `analyze_sheet` → contexto → IA → `fill_save`, com
`RelatorioLote` e o mesmo contrato de generator, para a tela consumir do mesmo jeito. Os PDFs
locais da ficha original vão junto (guardados em `Pendencia.refs_locais`) — o engenheiro aprovou
links, não desistiu dos manuais.

#### Onde a lógica mora, e por quê

Tudo o que decide alguma coisa está em **`sigft/services/autospec_conferencia.py`**
(`Pendencia`, `Conferencia`, `resumo_para_console`), que **não importa tkinter** — um teste
verifica isso por AST, não por convenção. A tela ficou com 4 métodos de desenho de widget e
nenhuma regra. Isso é o princípio nº 2 da arquitetura, e é o que permite testar a conferência
inteira sem abrir janela: **16 testes** cobrem agrupamento, seleção por checkbox, índices
inválidos vindos da grade, e ficha sem pendência.

#### O aviso para o CP 7.3 (frente do Luan)

A seção é autocontida de propósito e está sob um comentário-cabeçalho que diz isso em voz alta.
`docs/refatoracao/TRABALHO_PARALELO.md` §3.1 e a entrada do CP 7.3 no
`PLANO_REFATORACAO.md` listam o que precisa viajar junto quando `frontend.py` for quebrado:
o bloco inteiro, o `_novo_core()` (compartilhado pelos dois workers), `import webbrowser` e a
chave aditiva `COLORS["warning"]`.


### ✅ R-25 🔴 Console de 10 fichas reais — 1 regressão minha e 3 bugs *(2026-08-13)*

O Luan mandou o terminal inteiro de 10 fichas do SFC. Ele mostrou o que nenhum teste sintético
pegaria.

#### A regressão que eu causei

**O lastro documental estava bloqueando campos que funcionavam.** Numa ficha, 7 dos 9 campos
barrados eram **identificação e classificação**, não especificação:

```
· fabricante                     -> a IA respondeu 'WAGO'
· texto_breve_material           -> 'WAGO – Acoplador Modbus TCP'
· S6: BR/PY, S8: Outros          -> 'Outros'
· E69: Classe 1, J69: Classe 2   -> 'Classe II – Não perigoso'
   motivo: nao ha medida para recalcular
```

O erro de raciocínio foi meu: apliquei a tudo uma regra que só faz sentido para dado técnico.
`fabricante = WAGO` não sai de datasheet, sai da planilha; `logística reversa = Aplica-se` sai de
julgamento sobre a legislação. **Exigir prova documental deles é exigir prova de algo que nunca
foi para ser provado assim.**

O lastro agora vale só para a **tabela de especificações** (`var_row_*`) — que é onde mora o
risco de um valor plausível e errado (`IP65` onde o documento diz `IP67`).

#### A camiseta da Minnie

O filtro binário deixou entrar, numa ficha real, **uma camiseta da Minnie no site do Target**:

```
Documento web aproveitado (WebScrape(BS4), 2266 chars):
  https://www.target.com/p/women-s-disney-minnie-mouse-oversized-graphic-t-shirt.../A-1000326972
```

A URL continha o código do material, e isso bastava. Junto entraram uma resenha de fone de
ouvido e **220.182 caracteres** de um site chinês de componentes.

**Três destinos agora** (desenho aprovado pelo usuário):

| | Regra | Destino |
|---|---|---|
| **certo** | cita o fabricante **e** um identificador | vira contexto |
| **duvidoso** | cita só uma das duas | **não** vira contexto; vai para conferência humana |
| **descartado** | nenhuma | jogado fora |

Verificado com os resultados reais: datasheet oficial → certo; **outro** produto WAGO → duvidoso;
camiseta → duvidoso; lixo → descartado.

#### Código com hífen não é número puro

Bug encontrado ao validar o acima: `750-362` compactava para `750362`, era classificado como
numérico puro, e a busca por fronteira procurava `750362` no alvo **não compactado** — onde está
escrito `750-362`. Nunca casava. **Todos** os códigos WAGO, CISCO e NIDEC da planilha têm hífen.

#### As listas do console se contradiziam

`texto_breve_material` aparecia ao mesmo tempo em "Origem dos dados" e em "a IA não respondeu" —
o tipo de contradição que faz o usuário parar de ler o log. As origens agora são podadas junto
com os campos bloqueados.

27 testes com os dados literais do console.


### ✅ R-24 🔴 A coluna G do STATUS_PMIB — causa raiz das fichas WAGO vazias *(2026-08-13)*

**O caso.** O Luan processou 4 fichas do escopo SFC HF-01/HF-02 e **nenhuma** teve a tabela de
características técnicas preenchida — 0/23, 0/16, 0/16, 0/6 — apesar de o site da WAGO com o
datasheet ser achável à mão em segundos.

**Causa raiz, medida nas fichas reais:** `texto_breve_material` e `fabricante` estavam **vazios
na própria ficha** — é o AutoSpec que vai preenchê-los. Sem eles a busca ia **só** com o `cod_mat` da
coluna E (`1000325606`) e **sem nome de fabricante nenhum** — a query saía literalmente como
`"1000325606"  datasheet`, com o espaço duplo onde o fabricante deveria estar.

> **Correção do usuário:** eu tinha escrito que esse código é interno da Itaipu. **Não é** — é o
> código interno da MARCA que produz o material (NIDEC, WAGO…), e serve sim como base de busca.
> O que faltava não era o código: era o **fabricante ao lado dele**. Sozinho e sem marca, um
> número de 10 dígitos casa com qualquer coisa — foi assim que uma camiseta do Target entrou
> (ver R-25).

**A planilha sabia a resposta o tempo todo**, na coluna **G — `MARCA/MODELO`**: `WAGO / 750-362`.
O AutoSpec lia só as colunas D e E; a G nunca era lida.

| | Antes | Depois |
|---|---|---|
| 1ª query (0071) | `"1000325606"  datasheet` | `WAGO 750-362 datasheet filetype:pdf` |
| Termos do filtro | `['1000325606']` | `['WAGO', '750-362', '1000325606']` |

Medido: `WAGO 750-362 datasheet` devolve **10 datasheets reais**, incluindo o oficial do
fabricante. Vale igual para `CISCO / IE-3200-8T2S-E` e `NIDEC / GAAPA`.

**Duas correções que vieram junto:**

- **O modelo da coluna G é identificador POR DEFINIÇÃO.** `NIDEC / GAAPA` não tem dígito, e a
  heurística de `_identificadores` exige um — `GAAPA` nunca seria âncora. A planilha, porém, o
  **declara** como modelo, e declaração vence heurística.
- **O modelo vem ANTES do código interno na cascata.** A query do `cod_mat` gastava a primeira
  consulta da CSE garantidamente à toa quando o código era o da Itaipu.

**A ficha continua tendo precedência:** se o engenheiro já escreveu o fabricante nela, é ele que
vale. O `_STATUS_PMIB` só entra no vazio — a ficha é a fonte, a planilha é a rede.

**Mais um do mesmo padrão, achado olhando a planilha real:** ela tem duas abas (`Lista de
Materiais` e `Checklist`) e o código usava `wb.active` — a aba que estava **selecionada quando
alguém salvou**. Fechar o arquivo com o `Checklist` à frente fazia `get_pmib_data` devolver vazio
para **toda** ficha, em silêncio. Agora a aba é escolhida por **ter o cabeçalho**, não por estar
aberta. É o mesmo "assumir em vez de verificar" dos achados anteriores.

20 testes, com as linhas reais da planilha do SFC como fixture.


### ✅ R-23 🔴 Varredura com 7 tipos de material real — 5 achados *(2026-08-13)*

Sete materiais típicos do parque de Itaipu passados pelo pipeline inteiro: sensor HYDAC,
rolamento SKF, anel Parker, motor WEG, válvula Swagelok em polegadas, servoválvula Bosch Rexroth
e um item sem código (Voith). Resultados de busca **reais do Google** como fixture; datasheets
escritos como fabricante escreve — vírgula decimal em português, ponto em inglês, alemão,
polegadas.

| # | Achado | Gravidade |
|---|---|---|
| **1** | **`6205` é designação ISO** — SKF, NSK e FAG fabricam todos "o 6205", e o catálogo do **concorrente passava** pelo filtro citando só isso. Mesmo caso de `380V`/`5CV` num motor: são **especificação, não identidade** | **grave** — §4.3 furada |
| **2** | **`2,05 kgfm` era INVISÍVEL** — o regex de unidade aceitava 3 letras e `kgfm` tem 4. Torque em kgf·m nunca era validado nem corrigido. Idem `psig`, `mbar`, `min-1` | **grave** — campo inteiro sem validação |
| **3** | `WEG EQUIPAMENTOS ELETRICOS SA` → `WEG ELETRICOS`; ancorar em `eletricos` aprova qualquer catálogo elétrico brasileiro | média |
| **4** | Valor **literal** anunciado como conversão (`30,3 kg = 30.3 kg`) — factualmente falso, e faz desconfiar de valor correto | média |
| **5** | Query truncada com preposição pendurada: `CONJUNTO DE REPARO PARA BOMBA DE KSB datasheet specs` | baixa |

**Como o #1 foi resolvido sem reabrir o furo de 12/08.** Identificador só ancora o filtro se for
**distintivo**: mistura letra e dígito **e** tem 5+ caracteres. Os três casos convivem:

```
HYDAC : ['HYDAC', '3332066', 'CS1320-A-0-0-0-1/-000', 'CS1320']   <- familia mantida
SKF   : ['SKF', '6205-2RS']                                       <- `6205` fora
WEG   : ['WEG']                                                   <- `380V`/`W22` fora
```

> **Um erro meu no caminho:** a 1ª versão parava no identificador e não acrescentava a família —
> e `CS1320` é justamente o que o datasheet de distribuidor cita. O teste de regressão da falha
> de 12/08 pegou na hora.

### Pipeline completo, ficha de motor WEG

```
[warn] 2 campo(s) vieram de CONVERSAO: 3,6775 kW (de 5 cv) · 104 F (de 40 C)
[warn] 1 campo(s) tiveram a CONTA REFEITA:
       · 5 - CONJUGADO NOMINAL (Nm): a IA disse '2,01 Nm', gravei '20,1036325 Nm'
         (de 2,05 kgfm)                                    <- erro de 10x, corrigido
[warn] 1 campo(s) ficaram VAZIOS: 7 - TENSAO DE ISOLAMENTO -> '600 V' (inventado)
```

47 testes novos.


### ✅ R-22 🔴 Desempate pelo enunciado, precisão completa e mais 1 bug *(2026-08-13)*

**O enunciado do campo desempata.** Você perguntou se esse processamento já existia: **não**. A
IA lê o documento inteiro, mas o *recálculo* não usava o enunciado — com duas pressões no
documento, descartava. Agora usa, e reaproveita o **glossário multilíngue do retrieval**, que já
sabe que `trabalho` vale `operating`/`betriebs`:

```
documento: "Maximum operating pressure 350 bar. Peak pressure 210 bar. Burst pressure 700 bar."

6 - PRESSAO DE TRABALHO  ->  35 MPa   (de 350 bar)
8 - PRESSAO DE PICO      ->  21 MPa   (de 210 bar)
9 - PRESSAO DE RUPTURA   ->  70 MPa   (de 700 bar)
PRESSAO (sem qualificar)  ->  vazio, e lista as 3
```

Entraram 15 termos **discriminantes** no glossário (`pico`, `ruptura`, `teste`, `contínuo`,
`estático`, `entrada`, `saída`, `ambiente`, `partida`, `carga`…): não servem para *achar* o
trecho, servem para distinguir duas medidas da mesma grandeza. 71 termos, 390 equivalentes.

> **Um detalhe que quase passou:** a 1ª versão olhava 90 caracteres antes da medida, e as duas
> pressões enxergavam a palavra `operating` — empatavam e o desempate nunca acontecia. A janela
> tem de ser a **frase**, um limite semântico, não métrico.

**Precisão completa** (sua decisão): `41 kg` → `90,3895275 lb`, não `90,4 lb`. Arredondar
descarta informação, e quem lê pode arredondar depois — o caminho inverso é impossível. O teto de
10 algarismos existe só para matar ruído de ponto flutuante (`90.38950000000001`).

### Mais um bug, da mesma família dos outros

Você previu certo. A varredura de 7 frentes achou **um a mais**, e do mesmo tipo:

> **`41 g` era APROVADO contra um documento que diz `41 kg`.** O caminho literal conferia só o
> NÚMERO, nunca a unidade. Mil vezes de diferença. Vale para todo par prefixo/grandeza:
> `350 kPa` contra `350 bar`, `25,4 cm` contra `25,4 mm`.

Agora número com unidade é conferido como **medida** (número e unidade juntos, literal ou por
conversão). Número sem unidade conhecida segue pelo caminho literal.

As outras 6 frentes da varredura (temperatura afim com negativos e Kelvin, unidade fora da
tabela, percentagem e razão, valor já correto não ser mexido, texto misto certo+inventado, campos
gerativos isentos) passaram sem achado.

**O padrão dos 4 bugs desta camada é o mesmo**: conferir uma parte do valor e concluir sobre o
todo — os dígitos sem o código (`IP65`), os dígitos sem a unidade (`41 g`), o número sem a
convenção de separador (`2.500`), a origem sem checar se houve conversão (`0 bar`). Anotado
porque é o que se deve procurar na próxima auditoria.

19 testes novos.


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

> **Revistos no mesmo dia (R-22):** (1) a origem ambígua deixou de ser descarte — o **enunciado
> do campo** desempata; (2) o arredondamento pela precisão da fonte foi revertido a pedido do
> usuário: prevalece a informação **mais completa**.

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

---

## 2026-09-14 — o aplicativo reescrevia a resposta CERTA da IA

**O que o usuário viu.** Ficha `4500063671.0912`, datasheet
`Datasheet - UCSC CONTROLLERS.pdf`:

```
18 - DIMENSOES (...): 55,118 x 55,118 x 55 mm (sem montagem); ...
```

quando o documento diz, com todas as letras:

```
UCSCH1, UCSCH2, UCSCS2: 168 x 150 x 55 mm (6.61 x 5.90 x 2.17 in)
```

### Três hipóteses descartadas por medição, antes de qualquer conserto

| Hipótese | Como foi descartada |
|---|---|
| **OCR** (a suspeita do usuário) | O PyMuPDF entrega a linha **limpa**, com espaços e tudo. O texto sem espaços que o usuário colou veio do leitor de PDF dele, não do pipeline |
| **Retrieval** (o RAG cortou a linha) | Rodado com o PDF real: a linha certa sobrevive ao recorte. A IA recebeu `168 x 150 x 55 mm (6.61 x 5.90 x 2.17 in)` |
| **A IA inventou** | `55.118` não existe no documento. É `2.17 in × 25,4` — e quem fez essa conta foi o **aplicativo** |

### A causa, em duas partes encadeadas

**1. `extrair_medidas` era cego a trio dimensional.** Em `168 x 150 x 55 mm`,
só o número colado na unidade virava medida. O documento inteiro oferecia
**uma** medida em mm (`55 mm`) — `168`, `150`, `204` e `152` não existiam.

**2. `corrigir_conversao` fabricava.** Sem par no documento, a resposta certa
era reprovada pelo lastro e caía no corretor, que procurava uma medida de
comprimento em **outra unidade**, achava `2.17 in`, convertia e **substituía**.

Medido, com o filtro de verdade:

| A IA respondia | Entrava na ficha |
|---|---|
| `168 x 150 x 55 mm` (correto) | `55,118 x 55,118 x 55 mm` |
| `168 mm` | `55,118 mm` |
| `999 x 888 x 777 mm` (inventado) | `55,118 x 55,118 x 55,118 mm`, **aprovado** |

A guarda que existe para barrar valor inventado estava **fabricando** um.

### O conserto (decisão do usuário: extrator + corretor estrito)

**Parte 1 — o separador de dimensão.** O módulo já tinha herança de unidade,
mas só atravessava conector de **intervalo** (`0 a 70 °C`). Agora atravessa
também o `x` do trio, e a passada **repete até estabilizar** — com uma passada
só, o `168` olhava para um `150` que ainda não tinha herdado nada.

**Parte 2 — a guarda contra inventar.** O corretor agora recusa quando **o
documento já fala a unidade da resposta**: aí não houve conversão nenhuma, o
número está simplesmente errado, e reescrevê-lo é fabricar dado.

Essa regra não é invenção nova — é o raciocínio que o próprio laço já
escrevia ao pular candidatos de mesma unidade. Ele só não era aplicado à
decisão: pulava os de mesma unidade e ia buscar outra unidade assim mesmo.

> **Uma regra minha que foi descartada no caminho.** A primeira tentativa
> exigia que os *algarismos* da resposta batessem com os do valor corrigido
> (`3,5` → `35`). Passou nos meus testes e **quebrou cinco** da suíte — os
> dois comportamentos que o usuário pediu em 2026-08-13: corrigir `100 lb` a
> partir de `41 kg`, e desempatar três pressões pelo enunciado do campo. A
> suíte estava certa e a regra estava errada.

### O que continua valendo, e o que continua em aberto

✅ Resposta certa entra **intacta**. ✅ Valor inventado é **descartado**.
✅ A correção legítima de aritmética continua acontecendo.

⚠️ **Duas limitações conhecidas, que este conserto não toca:**

1. **Modelo errado passa.** `168 x 150 x 85 mm` mistura a altura/profundidade
   do UCSCH1 com a largura do UCECH1 — e entra, porque os três números estão
   no documento. O lastro confere *presença*, não *pertinência*: ele não sabe
   qual variante do produto a ficha quer. É a limitação de desenho do lastro,
   e vale para todo campo.
2. **Se a IA converter por conta própria, o valor passa.** `55,118 mm` está a
   0,21% de `55 mm`, dentro da tolerância de 1%. O que mudou é que a IA não é
   mais **empurrada** para esse caminho — a resposta certa deixou de ser
   corrompida. Apertar a tolerância mexeria no arredondamento legítimo
   (`175 bar` → `2538 psi`), então ficou como está.

---

## 2026-09-14 (tarde) — "qual destes modelos é o meu?"

Dois pedidos do usuário que, investigados, viraram **um só eixo**: o aplicativo
não tinha noção de *"este documento fala de vários produtos"*.

### Frente 1 — o lastro conferia presença, não pertinência

`168 x 150 x 85 mm` mistura altura e profundidade do UCSCH1 com a largura do
UCECH1, e passava: os três números estão no documento.

**`contexto_do_modelo(contexto, modelo)`** recorta o documento por linha:

| A linha | Destino |
|---|---|
| se declara do MEU modelo (`UCSCH1, UCSCH2: ...`) | fica |
| se declara de OUTRO modelo (`UCECH1: ...`) | **sai** |
| não se declara de modelo nenhum (`Certificate:`, `Dimensions (H x D x W)`) | fica — spec compartilhada vale para todas as variantes |

O que marca uma linha como de-um-modelo é o lado esquerdo do `:` **parecer
código** — letra e dígito juntos. `Certificate:` e `Operating temperature:`
continuam sendo rótulo comum. Sem modelo informado, ou num documento em que
nenhuma linha se declara, devolve o contexto inteiro: recortar por um modelo
que não existe cegaria o lastro.

A comparação é por código compactado, então `IE-3200-8T2S-E` da planilha casa
com `IE3200-8T2S-E` do documento. Hífen não pode decidir se o dado entra.

### Frente 2 — o caso CISCO IE-3200-8T2S-E

**Não faltava busca web, nem leitura de HTML.** As duas existem — o AutoSpec
lê página com BeautifulSoup desde sempre. Faltavam duas coisas:

1. **A família nunca era procurada.** `_familia_do_identificador` cortava no
   PRIMEIRO hífen: `IE-3200-8T2S-E` → `IE`, duas letras → descartado. Agora
   tenta prefixos progressivos e fica com o **menor válido**: `IE-3200`. Mesmo
   caso de `NSD-100-A`. Medido: `CS1320`, `PVF100`, `750` e `1756` continuam
   idênticos.
2. **A página da família caía em "duvidosos".** O título fala da série, não do
   SKU; sem o código exato no trecho do Google, o resultado ia para a
   conferência humana em vez de virar contexto. Agora o **domínio do próprio
   fabricante** vale como segunda evidência — `cisco.com` falando de produto
   Cisco não é a camiseta da Minnie no Target.

> **A suíte pegou um erro meu aqui.** A primeira versão da regra do domínio
> aceitava `wago.com/br/p/750-513` para um item `750-362` — produto errado, do
> fabricante certo. Seria criar, dentro do filtro, exatamente o defeito de
> modelo-errado que esta rodada existe para fechar. A promoção agora recusa
> quando o resultado cita um **irmão** do meu produto: um código que começa
> pela mesma família e não é compatível com o meu. `IP67` não começa pela
> família de `IE-3200-8T2S-E`, então não conflita.

### O que não deu para verificar daqui

⚠️ **Não consegui abrir a página da Cisco.** O contêiner da sessão web não
alcança `cisco.com` (o proxy devolve 403, e a ferramenta de fetch também é
bloqueada). O diagnóstico acima é do **código**, medido offline com o item
real; o que falta é rodar o AutoSpec nessa ficha numa máquina com internet e
confirmar que a página passa a virar contexto.

---

## 2026-09-15 — a conversão certa que era jogada fora

Log da ficha `4500063671.0070 en-US`. A busca funcionou (datasheet da Cisco
achado e lido, 16 páginas), mas as dimensões ficaram vazias:

```
14 - DIMENSIONS (Indicate the dimensions of the item in (mm)
  -> a IA respondeu '152 x 91 x 135'
     motivo: nao ha medida para recalcular
```

### A causa, medida

O lastro foi testado contra **todas** as formas plausíveis de um datasheet
escrever a dimensão. Passa em todas — menos numa: quando o documento traz a
medida **só em polegada**.

```
5.98 × 25,4 = 151,9 → 152     3.58 × 25,4 = 90,9 → 91     5.31 × 25,4 = 134,9 → 135
```

A IA fez a conversão **certa**. E o mecanismo que existe exatamente para
aprovar conversão correta não pôde agir, porque a resposta veio **sem
unidade** — a pergunta já dizia `in (mm)`, então a IA não repetiu o `mm`. Sem
unidade não há medida; sem medida, não há conta para conferir.

Provado com a mesma resposta, mudando só isso:

| Resposta | Lastro | Medidas |
|---|---|---|
| `152 x 91 x 135` | ❌ | `[]` |
| `152 x 91 x 135 mm` | ✅ | `152 mm = 5.98 in; 91 mm = 3.58 in; 135 mm = 5.31 in` |

**Não é só a dimensão.** A ficha está cheia de enunciados que já declaram a
unidade (`em (mm)`, `em grau Celsius (°C)`), e em todos uma resposta numérica
crua perdia a conferência.

### Cinco consertos nesta rodada

1. **A unidade sai do enunciado.** `aplicar_unidade_da_pergunta` completa a
   resposta crua com a unidade que a pergunta declara — **só para conferir**;
   o que vai para a ficha continua o original. Enunciado que lista várias
   (`em (mV, V, A, mA)`) não declara nada: chutar seria pior.
2. **Um número, não três.** `corrigir_conversao` recusa quando mais de um
   número da resposta não confere. Erro de aritmética é **uma** conta que
   escorregou; três números errados são outra leitura. Sem isto,
   `900 x 800 x 700 mm` contra um documento só em polegada saía como
   `134,874 x 134,874 x 134,874 mm` — a mesma fabricação do dia 14, por um
   caminho que a guarda daquele dia não cobria (lá o documento falava a
   unidade da resposta; aqui só a outra).
3. **As 26 fontes fantasma.** O marcador do contexto leva o TÍTULO do
   documento; a IA cita a URL, que vem na linha seguinte e não era coletada.
   26 campos foram acusados de citar "fonte que NÃO está entre os documentos
   lidos" — citando exatamente o documento lido. Aviso falso em 26 campos
   ensina a ignorar o aviso, e aí o verdadeiro passa junto.
4. **O motivo diz o que faltou.** `nao ha medida para recalcular` não diz nada
   a quem lê. Agora vem acompanhado de `nao achei no documento: 900, 800, 700`.
   É o que teria dado este diagnóstico em dez segundos.
5. **`cm`, `cm`, `cm`, `kg`.** Os quatro rótulos que o usuário viu na lista de
   campos não respondidos. O log era fiel — no `CONFIG_MAP`, o `desc` desses
   campos é literalmente a unidade. Agora o nome do campo vai junto.

E uma **guarda de segurança** no recorte por modelo que entrou no dia 14: se
nenhuma linha casar com o modelo da planilha, não corta nada. É mais provável
que o modelo esteja grafado diferente do que o documento inteiro ser de outro
produto.

### A varredura da família (o /brainstorming pedido)

Feita por medição, não por especulação: 12 pares realistas de
resposta-correta + documento, cobrindo decimal vírgula×ponto, separador de
milhar nos dois idiomas, intervalo com conector diferente, unidade com ponto
(`in.`), grau de proteção com espaço (`IP 30`), peso convertido de libra,
tabela quebrada em linhas. **Nenhuma reprovada indevidamente.**

E a contraprova, 7 respostas erradas: número inventado, ordem de grandeza,
`IP67` contra `IP 30`, meia verdade (`entre 175 e 999 bar`), fonte inexistente
— **todas barradas**.

Dois casos "vazaram" e **não são vazamento**: `41 g` contra `41 kg` virou
`41000 g`, e `7 kg` contra `3 lb` virou `1,36 kg`. Nos dois o documento tem
uma única medida daquela grandeza, a origem é inequívoca, e o computador refez
a conta — que é a decisão do usuário de 2026-08-13. As duas aparecem na lista
de corrigidos do console.

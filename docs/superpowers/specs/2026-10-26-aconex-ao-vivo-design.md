# Aconex ao vivo no SIG-FT e a Conferência de Revisões

**Data:** 2026-10-26 · **Frente:** Luan · **Módulos:** Gestão PMIB (`services/pmib_manager.py`) e uma
tela nova, Conferência de Revisões
**Origem:** o rascunho "Workflow AMP" do Luan (25/10/2026) e a conversa de desenho de 25 e 26/10.
Nas palavras dele: *"em vez de pedir o extrato do aconex inteiro, podemos fazer a chamada direta
buscando o histórico, novos documentos e etc (mas garantindo a segunda opção também)"*.
**Estado:** desenho para aprovação. Nada construído.

---

## 1. Por que

Quando a lista de sobressalentes ganha uma revisão nova no Aconex, o `_STATUS_PMIB` dela precisa
acompanhar essa revisão. Hoje há muitas listas defasadas ao mesmo tempo, a mapeadora fica vermelha em
tantas linhas que o vermelho deixou de avisar, e uma lista que muda de novo passa despercebida até
alguém ir trabalhar nela.

O Luan desenhou um fluxo em três peças:

| Peça | O quê | Onde | Estado |
|---|---|---|---|
| **1 (este documento)** | o SIG-FT consulta o Aconex ao vivo; um botão aponta as listas com divergência de revisão e baixa a revisão nova para a pasta de cada uma | SIG-FT | desenho |
| 2 | a IA da empresa (AMP, com fluxos n8n) lê o PDF novo, compara com o `_STATUS_PMIB` e devolve as mudanças e as ações | AMP | desenho a fazer |
| 3 | aplicar no `_STATUS_PMIB` o que a pessoa confirmar | SIG-FT | depois; não precisa ser automática |

Esta peça resolve duas coisas sozinha. O Gestão PMIB deixa de exigir o extrato diário do DocManager
(~92 mil linhas, escolhido à mão). E a equipe passa a ver, num botão, quais listas mudaram e em que
situação está cada uma.

## 2. Vocabulário

| Termo | Significado |
|---|---|
| **Revisão em uso** | a revisão da lista que o `_STATUS_PMIB` reflete. Fica na linha "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO" do próprio arquivo, e o Gestão PMIB a copia para a coluna `REVISÃO EM USO` da mapeadora |
| **Última revisão emitida** | a revisão marcada `Current = True` no Aconex, aprovada ou não. É a coluna `ÚLTIMA REVISÃO EMITIDA` da mapeadora |
| **Divergência de revisão** | quando a revisão em uso é diferente da última revisão emitida (a "lista defasada") |
| **STATUS REAL** | o status que a "batalha de versões" do DocManager devolve para o documento (`calcular_status_real`), **sem passar pelo consolidado**. Os valores são `Aprovado`, `Aprovado com Comentários`, `Para Assinatura`, `Não Aprovado`, `Em Processo`, `NÃO EMITIDO`, `Cancelado` e os informativos. A aprovação não passa de uma família de revisões para outra (0 → 1) |
| **Família de aprovação** | `Aprovado`, `Aprovado com Comentários` e `Para Assinatura`. São os três que contam como "lista aprovada" |
| **Histórico do Aconex** | a tabela de revisões com as colunas do extrato do DocManager (`ORDEM_COLUNAS` em `docmanager/aconex_backend.py`), uma linha por versão de cada documento |

## 3. O que muda: duas partes

**A. Gestão PMIB ao vivo.** Continua rodando sozinho, como hoje. Muda de onde vem o histórico do
Aconex. Passa a preencher o STATUS REAL da mapeadora. E corrige a regra de lista nova (PB020).

**B. Conferência de Revisões.** É uma tela nova, com o botão "Conferir revisões". Ela lê a mapeadora
que o Gestão PMIB deixou, aponta todas as listas com divergência de revisão separadas pelo STATUS REAL,
e baixa a última revisão emitida de cada uma. Não grava em nenhuma planilha.

A parte A não chama a B, e o Gestão PMIB continua rodando separado de tudo o que este fluxo traz. A
parte B aproveita o que a A já calculou: lê a mapeadora, mas não grava nela.

## 4. Parte A: Gestão PMIB ao vivo

### 4.1 Duas fontes, a mesma tabela

Hoje o Gestão PMIB lê o extrato com `pd.read_excel(caminho_api)` e trabalha com esse `df_api`
(`pmib_manager._fluxo`, passo 1). O desenho troca esse passo por uma **fonte do histórico** com duas
implementações que entregam a mesma tabela (mesmas colunas, `Current` booleano):

| Fonte | Quando | Como |
|---|---|---|
| **Aconex ao vivo** | padrão | consulta a API com as credenciais do DocManager (§6) |
| **Extrato** | quando a ao vivo falha (sem credencial, sem rede, erro da API) | a tela pede o `Aconex_Historico_*.xlsx`, como hoje (botão "1. Selecionar Histórico Aconex DocManager") |

O resto do fluxo não muda: a renomeação pelo Tracking ID, os metadados, as listas novas com
confirmação, o acompanhamento das listas de preços e as atividades. O log e a tela dizem qual fonte
foi usada. A troca de fonte nunca acontece em silêncio.

### 4.2 O que a fonte ao vivo precisa trazer

Não é preciso trazer o Aconex inteiro, só o que o Gestão PMIB usa do extrato:

| Uso no Gestão PMIB | Documentos que a fonte precisa trazer |
|---|---|
| metadados e renomeação (`_buscar_rdspp_mais_recente`, parte A de `_atualizar_mapeamento`) | **todo o histórico** de cada lista conhecida (os códigos dos `_STATUS_PMIB` e os da coluna `N° DOCUMENTO ITAIPU` da mapeadora), **inclusive depois de uma mudança de código**, pelo mesmo Tracking ID |
| listas novas (parte B de `_atualizar_mapeamento`) | os documentos vigentes que atendem à regra nova da §4.3 |
| acompanhamento das listas de preços (`lista_precos.levantar`) | as listas de preços vigentes e o histórico de que a regra de pareamento precisa |
| atividades (`_atualizar_atividades`) | os mesmos códigos das listas |

Situação de cada chamada contra o Aconex real:

| Chamada | Situação |
|---|---|
| token OAuth `client_credentials` no Oracle Lobby, com `user_id` e `user_site` | provada (DocManager, em uso diário) |
| `GET /register` paginado com `show_document_history=true` (extração completa) | provada (é o extrato diário) |
| busca exata pelo código: `search_query='"<código>"'` | provada (DocManager, 2026-07-29) |
| download da versão vigente: `GET /register/{DocumentId}/markedup` | provada (idem) |
| busca por `trackingid` (a documentação oficial diz que o campo pode entrar na busca) | **a provar** |
| busca por PB020 no código e SOBRESSALENTES no título | **a provar** |

Se as buscas que faltam provar não funcionarem, a saída é a extração completa, que já é provada, porém
mais lenta. Antes de seguir por esse caminho, quem estiver construindo avisa o Luan, porque o pedido
dele foi justamente não puxar o Aconex inteiro.

### 4.3 Regra de lista nova: PB020 obrigatório

Começaram a aparecer como "lista nova" planilhas de comissionamento com SOBRESSALENTES no título. A
regra muda de:

> título com SOBRESSALENTES, sem PREÇO/PREÇOS no título e sem código terminado em `-01`

para:

> **código com `PB020`** **e** título com SOBRESSALENTES **e** título sem PREÇO/PREÇOS

O título é comparado sem acento e sem diferença de caixa (`PRECOS` também conta). O teste do `-01`
sai. Efeito: a lista do SMF (`#ITA0=A01AAM10&EPB020-01`), que é de sobressalentes e não de preços,
deixa de ser barrada por engano. Isso resolve a pendência de 2026-09-03 sobre o filtro de `-01`.

Hoje as listas com preços ainda usam código PB020 e se separam pelo título. Quando todas passarem para
PB021, o rastreio deve passar a usar o código. Essa mudança está registrada como pendência em
`PENDENCIAS.md` (2026-10-26) e não entra neste desenho.

### 4.4 STATUS REAL pela batalha de versões

O Gestão PMIB passa a escrever a coluna `STATUS REAL` da mapeadora. Ele a acha pelo nome, como as
outras; se a coluna não existir, avisa no log e não a cria. O valor é o **status real**, e não o
consolidado: distingue `Aprovado`, `Aprovado com Comentários` e `Para Assinatura` (decisão do Luan). O
caminho segue o que o DocManager usa em `docmanager/core/mapping.py`, parando antes do consolidado:

```
tl = resolver_linha_da_verdade(historico_do_tracking_id)        # core/truth_line.py
se tl.nao_emitido:  STATUS REAL = NÃO EMITIDO
senão:              STATUS REAL = calcular_status_real(tl.df_para_calculo, tl.revisao_atual)   # core/status_engine.py
```

O texto é gravado como a batalha o devolve. Vale para toda linha da mapeadora cujo código esteja no
histórico, tenha ela `_STATUS_PMIB` ou não. O cálculo funciona com as duas fontes, porque o extrato
também traz o histórico completo. Uma lista cujo código não aparece no histórico (a linha "SEM LISTA",
por exemplo) não muda e fica registrada no log.

**A coluna deixa de ser das pessoas.** Hoje o código diz que o STATUS REAL é coluna de pessoa e nunca
mexe nela (comentário T3-g em `pmib_manager.py`). Isso muda. Sempre que o valor de uma lista mudar, o
log mostra o antes e o depois. Na primeira rodada, isso revela tudo o que a batalha alterou nos
valores digitados. Um caso esperado é a mudança de família (0 → 1), em que a batalha zera a aprovação.

### 4.5 Os painéis precisam aceitar o vocabulário novo, antes

Três lugares contam "lista aprovada" comparando com o texto exato `APROVADO`:

| Onde | Linha |
|---|---|
| Power BI, `_gestao_v2/powerbi/05 - Medidas.dax` (no cofre) | `Listas[Status Real] = "APROVADO"`, nas medidas de listas aprovadas e de aprovadas sem fichas |
| painel HTML do SIG-FT, `sigft/assets/painel_template.html` | `l.sr === "APROVADO"` (listas aprovadas sem ficha) |
| protótipo do painel no cofre, `_scripts/prototipo_template.html` | `l.sr === "APROVADO"` |

Com o vocabulário novo, as listas em `Para Assinatura` e em `Aprovado com Comentários` deixariam de
contar. Hoje, só as em `Para assinatura` são 21. Por isso, **antes** de a parte A gravar o primeiro
STATUS REAL novo, os painéis passam a contar como aprovada a família de aprovação inteira, comparando
sem acento e sem caixa. Com essa comparação, eles funcionam tanto com o valor antigo (`APROVADO`)
quanto com o novo. Vale a regra dos dois painéis: definição que muda num, muda no outro. O Power BI é
feito no cofre e entregue no Box por `entregar_no_box.py`, com a ordem do Luan.

### 4.6 O que a parte A não faz

Não baixa PDF, não separa listas por grupo e não chama a parte B.

## 5. Parte B: Conferência de Revisões

### 5.1 Entrada

- **a mapeadora**, aba `Acompanhamento Sobressalente`, com as colunas `N° DOCUMENTO ITAIPU`,
  `ÚLTIMA REVISÃO EMITIDA`, `STATUS DA REVISÃO`, `STATUS REAL`, `REVISÃO EM USO` e `LINK DA PLANILHA`.
  Ela é **só lida**;
- **o Aconex**, só para baixar (§5.4).

A conferência usa o que o último Gestão PMIB deixou na mapeadora. Por isso a tela mostra quando a
mapeadora foi salva pela última vez e, se não foi hoje, sugere rodar o Gestão PMIB antes. Ela não
roda o Gestão PMIB sozinha.

### 5.2 A regra

Para cada linha da mapeadora:

1. sem `_STATUS_PMIB`, isto é, sem `LINK DA PLANILHA`, a linha entra só no total "Sem `_STATUS_PMIB`".
   Não há pasta para baixar nem planilha a conferir;
2. **tem divergência** quando `REVISÃO EM USO` ≠ `ÚLTIMA REVISÃO EMITIDA`. A comparação usa as revisões
   normalizadas (`normalizar_revisao` do DocManager), para que caixa ou espaço não criem divergência
   falsa. `REVISÃO EM USO` vazia conta como divergência, porque arquivo sem marca é arquivo não
   conferido;
3. sem divergência, a linha entra só no total "Em dia";
4. **com divergência, a lista sempre é baixada** (§5.4), e a categoria vem do STATUS REAL. A categoria
   serve para dar destaque, não para filtrar:

| STATUS REAL | Categoria | Por que a atenção |
|---|---|---|
| família de aprovação (`Aprovado`, `Aprovado com Comentários`, `Para Assinatura`) | **Aprovada, com divergência** | a lista que vale para trabalhar mudou e o `_STATUS_PMIB` ficou para trás. É a que pede atenção primeiro |
| `Em Processo` | **Em processo, com divergência** | há revisão nova tramitando, que ainda pode mudar |
| `Não Aprovado` | **Não aprovada, com divergência** | a revisão nova foi reprovada e outra deve vir |
| `NÃO EMITIDO`, `Cancelado`, informativo, vazio ou desconhecido | **Outros** | aparece com o status, para nada ficar escondido |

A comparação dos textos é sem acento e sem caixa. Assim, a mapeadora ainda com os valores antigos
(`APROVADO`, `EM PROCESSO`, `NÃO APROVADO`) também se encaixa.

### 5.3 Os exemplos que fecharam a regra

| Revisão em uso | No Aconex | STATUS REAL | Categoria | O que baixa |
|---|---|---|---|---|
| 0 | 0A aprovada; **0B em processo** (Current) | `Aprovado` (a batalha na família 0 acha a 0A) | Aprovada, com divergência | **a 0B** (decisão do Luan: sempre a `Current`) |
| 0C | 0C aprovada; **1A em processo** (Current) | `Em Processo` (família nova zera a aprovação) | Em processo, com divergência (decisão do Luan: "houve revisão") | a 1A |
| 0A | **0B não aprovada** (Current) | `Não Aprovado` | Não aprovada, com divergência | a 0B |
| (vazia) | 0 em `Para Assinatura` (Current) | `Para Assinatura` | Aprovada, com divergência | a 0 |
| 0A | 0A aprovada (Current) | `Aprovado` | — (Em dia) | nada |

Os cinco casos viram teste. Os STATUS REAL da tabela também são testados na batalha (§4.4), com
histórico sintético.

### 5.4 O download

Vale para toda lista com divergência, e só com o Aconex ao vivo:

- o PDF vai para a **pasta do `_STATUS_PMIB`** daquela lista. O `LINK DA PLANILHA` é um caminho
  relativo à pasta da mapeadora (`os.path.relpath` em `_gravar_na_mestra`), então funciona em qualquer
  máquina. Se o arquivo não estiver lá, a conferência procura pelo código na pasta raiz
  (`status_pmib_arquivos.listar`). Se ainda assim não achar, a lista vai para "Outros" com esse motivo;
- o `DocumentId` vem da busca exata pelo código (versão `Current`), a mesma chamada que o DocManager já
  usa;
- o nome é `<código>[<revisão>].pdf`, o padrão que já existe nas pastas (ex.:
  `#ITA0=Y01TF001&BPB020[0A].pdf`). O `<código>` é o `N° DOCUMENTO ITAIPU`, e a `<revisão>` é **a da
  versão que o Aconex devolveu** (campo `Revision` da busca), não a da mapeadora. Se as duas forem
  diferentes, a mapeadora está desatualizada. A linha avisa isso e sugere rodar o Gestão PMIB;
- se o arquivo já existe, não baixa de novo. O botão **nunca** sobrescreve nem apaga nada. A checagem é
  só pelo nome no padrão: um PDF da mesma revisão com outro nome não é reconhecido e é baixado de novo
  com o nome do padrão, o que não causa problema;
- se o PDF da **revisão em uso** não estiver na pasta, ele também é baixado, porque a peça 2 compara a
  revisão anterior com a nova. O `DocumentId` dele sai do histórico do código, numa busca com
  `show_document_history=true`. Se a revisão em uso não aparecer no histórico, o botão avisa e segue;
- o download usa `/markedup`, que é o único caminho provado. Esse arquivo pode trazer carimbos e
  anotações de revisão. Se o arquivo original (`GET /register/{DocumentId}`) servir melhor para a
  leitura da peça 2, a troca se decide lá;
- um download que falhar vira linha de erro no resumo, e o resto continua.

### 5.5 O que a tela mostra

- quando a mapeadora foi salva pela última vez;
- o total de cada categoria, mais "Em dia" e "Sem `_STATUS_PMIB`";
- uma tabela por categoria, na ordem da §5.2 (aprovadas primeiro), com código, revisão em uso, última
  revisão emitida, `STATUS DA REVISÃO` (o status da última revisão), STATUS REAL e o PDF (baixado, já
  existia ou falhou);
- o console com o passo a passo, como nas outras telas, e o log em arquivo.

Sem conexão com o Aconex, a tela mostra as categorias do mesmo jeito e avisa que, para baixar, é
preciso conexão.

### 5.6 A passagem para a peça 2

O que sai daqui para o AMP são todas as listas com divergência, cada uma com a sua categoria e com os
PDFs já nas pastas. O relatório da peça 2 mantém a separação: aprovadas com divergência primeiro, depois
em processo e não aprovadas. O formato da passagem (arquivo, chamada ao n8n ou formulário) se decide
no desenho da peça 2. Nada desta peça depende disso.

## 6. Credenciais

- O SIG-FT **só lê** o cofre do DocManager: `Documentos\DocManager_Itaipu\credenciais.json`. É o
  esquema 1, com o Client Secret cifrado pela DPAPI do usuário do Windows (ver
  `docmanager/services/credenciais.py`). O SIG-FT nunca escreve nesse arquivo.
- Se houver mais de um perfil, o SIG-FT usa o que o DocManager marca como atual, se houver. Senão,
  pergunta uma vez e guarda a escolha nas preferências do SIG-FT.
- Sem cofre ou sem perfil: a parte A usa o extrato, e a parte B mostra as categorias sem baixar.
- O segredo não aparece em log, preferência, mensagem de erro nem repositório.

## 7. O que vem do DocManager: cópia, por enquanto

Decisão do Luan: copiar agora e trocar por um pacote compartilhado depois. A pendência está registrada
em `docs/refatoracao/PENDENCIAS.md` (2026-10-26). Origem: `luanccozer/DocManager`, commit `c9683d2`
(2026-09-30).

| No DocManager | O que levar |
|---|---|
| `docmanager/aconex_backend.py` | `PROJECT_ID`, `ACONEX_INSTANCE`, `AUTH_URL`, `CAMPOS_STRING`, `ORDEM_COLUNAS`; o token (`_tentar_token`); a busca paginada, que renova o token quando recebe 401 (`_baixar_pagina`); a conversão do XML em tabela (`_parse_pagina`, `montar_dataframe`); a busca exata e o download (`_buscar_doc_atual`, `/markedup`) |
| `docmanager/services/credenciais.py` | só a leitura (`Cofre`, `decifrar`, a DPAPI) |
| `docmanager/core/truth_line.py`, `status_engine.py` | o caminho do STATUS REAL (§4.4). O `consolidation.py` **não** entra |
| `docmanager/core/constants.py`, `normalize.py`, `comissionamento.py`, `excecoes.py` | só o que os dois de cima usam. Isso inclui as listas de veredito (aprovação, reprovação, informativo, anulação, fantasmas), que também definem a família de aprovação |
| `tests/test_status_engine.py`, `test_aconex_backend.py`, `test_credenciais.py` | os testes das partes copiadas |

**A rede não é copiada.** O SIG-FT já tem a mesma solução em `sigft/core/rede.py` (truststore, cascata
do PAC e, como último recurso, conexão sem verificar o SSL). As chamadas copiadas passam por ela.

Cada arquivo copiado começa dizendo de onde veio (arquivo e commit do DocManager), para que o pacote
futuro possa comparar.

## 8. Restrições

- **Princípios do SIG-FT** (`CLAUDE.md`): nenhuma regra de negócio na tela; serviço não importa Qt; a
  conversa entre os dois é por callbacks. Uma implementação por conceito: a batalha e a família de
  aprovação ficam num lugar só dentro do SIG-FT. Nos painéis, a mesma lista é repetida em DAX e em JS,
  e as três cópias andam juntas.
- **Tela:** todo texto passa por `t()`, com tradução para `es` e `en`; cor por papel ou variante e
  ícones SVG (sistema visual); console com níveis. A tela entra no `--smoke`, e a mudança entra no
  `CHANGELOG.md`.
- **Testes:** sem rede e sem dado real no repositório. As respostas XML do Aconex são sintéticas. O
  `conftest` substitui pandas e openpyxl por dublês.
- **Limites da API:** passando do limite de volume ou de frequência, o Aconex devolve 503
  (`*_THROTTLE_LIMIT_REACHED`). Nesse caso, esperar e tentar de novo.
- **Só o Aconex.** Nada aqui toca o portal PMIB, onde só vale RPA.
- **Box:** a parte B só cria PDFs dentro das pastas das listas. Não mexe em planilha, não apaga e não
  sobrescreve.
- **Prova ao vivo:** como no portal, CI verde não prova a API. A validação final é feita numa máquina
  com o cofre do DocManager e acesso ao Aconex.

## 9. Fora do escopo

- a leitura pelo AMP e qualquer coisa de n8n (peça 2);
- gravar no `_STATUS_PMIB` (peça 3);
- o pacote compartilhado (pendência);
- passar o rastreio das listas de preços para o código PB021 (pendência; só quando a migração das
  listas acontecer);
- mudar o extrato diário do DocManager ou o que o Power BI lê dele;
- vigia diário ou agendamento: a conferência só roda quando alguém aperta o botão.

## 10. Como saber que deu certo

1. **Mesma mapeadora:** numa cópia da mapeadora e dos `_STATUS_PMIB`, o Gestão PMIB com a fonte ao vivo
   e com o extrato do mesmo dia dá o mesmo resultado em todas as colunas que ele grava.
2. **Mesmo STATUS REAL do DocManager:** para os mesmos documentos e o mesmo dia, o STATUS REAL do
   SIG-FT é igual ao status real (não o consolidado) que o DocManager calcula.
3. **Lista nova só com PB020:** uma planilha de comissionamento com SOBRESSALENTES no título não é
   sugerida, e a lista do SMF (`...PB020-01`) é.
4. **Painéis estáveis:** o número de listas aprovadas no Power BI e no painel HTML é o mesmo antes e
   depois da troca de vocabulário, com a mesma mapeadora.
5. **Os cinco casos da §5.3** passam como teste.
6. **No Box real:** o Luan confere as categorias; os PDFs caem nas pastas certas, com o nome certo; e a
   segunda rodada não baixa nada.
7. **Sem cofre:** a parte A pede o extrato e a parte B mostra as categorias sem baixar; as duas avisam
   isso na tela.
8. CI verde, e o `frontend.py --smoke` visita a tela nova.

## 11. O que fica com quem constrói

- nomes e lugares dos módulos. Sugestão: `sigft/core/aconex/` para cliente, credenciais e status;
  `sigft/services/conferencia_revisoes.py`; `sigft/app_qt/views/conferencia_revisoes.py`;
- as consultas exatas da fonte ao vivo e a prova delas (§4.2);
- o desenho da tela nova e o jeito como a tela do Gestão PMIB mostra a fonte usada;
- o tempo de espera e o número de tentativas no 503, e o tamanho de página;
- a ordem de entrega, respeitando uma condição: os painéis aceitam o vocabulário novo (§4.5) antes de
  a parte A gravar o STATUS REAL.

## 12. Quem decidiu o quê

| Decisão | Quem |
|---|---|
| Aconex ao vivo no SIG-FT, com o extrato como reserva (a tela pede para selecioná-lo) | Luan |
| Copiar do DocManager agora; pacote compartilhado depois (pendência) | Luan |
| STATUS REAL da mapeadora = status real da batalha, distinguindo Aprovado, Aprovado com Comentários e Para Assinatura (sem o consolidado) | Luan |
| Lista nova exige PB020 no código, SOBRESSALENTES no título e nada de PREÇOS; PB021 fica para quando as listas de preços migrarem (pendência) | Luan |
| Conferência usa a mapeadora (pastas pelo link, aproveitando o que o Gestão PMIB já rodou) | Luan, com a concordância de Claude |
| Baixar todas as listas com divergência, separando aprovada, em processo e não aprovada | Luan |
| Baixar sempre a revisão `Current = True`; mudança de família fica em "Em processo" | Luan |
| Botão próprio; o Gestão PMIB roda separado de tudo | Luan |
| Sem vigia diário: a mudança aparece quando alguém roda | Luan |
| Ler o cofre do DocManager em vez de ter cadastro próprio | Claude, recomendado junto com a opção (a) que o Luan escolheu |
| Painéis contam a família de aprovação, sem acento e sem caixa, antes de a parte A gravar | Claude |
| Família de aprovação = só os três rótulos (informativo vai para "Outros") | Claude |
| Tela própria "Conferência de Revisões"; mostra quando a mapeadora foi salva | Claude |
| Nome `<código>[<revisão>].pdf`, sem sobrescrever; baixar também a revisão em uso que faltar | Claude |
| Comparação de título sem acento na regra do PB020 | Claude |
| Log de toda mudança de STATUS REAL (antes → depois) | Claude |
| Rede pelo `core/rede.py` do SIG-FT, sem copiar a do DocManager | Claude |

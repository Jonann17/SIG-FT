# Cria Fichas: a escolha de PDM em duas passadas

**Data:** 2026-10-08 · **Frente:** Luan (Cria Fichas)
**Status:** implementada em 2026-10-08 (plano
`docs/superpowers/plans/2026-10-08-escolha-de-pdm-em-duas-passadas.md`, cujas seções de ajustes
listam o que o código refinou; o texto abaixo já está alinhado). Aguarda a validação na máquina
do usuário (§7).

> *"Ele está diversas vezes não apontando para nenhum PDM... Está vindo como Nenhum.... Mesmo
> quando eu sei que tem PDMs bons para escolher."*
>
> *"Pela descrição a IA deve interpretar que tipo de material é aquele, e muitas vezes tentar
> encontrar no catálogo nomes parecidos ou sinônimos. A IA conhece mais do que eu que tipo de
> equipamento é, e qual a melhor classificação pra ele. Se há dúvidas se encaixa naquele PDM,
> basta ver as características técnicas se se enquadram."*
>
> *"Nunca é bom ter NENHUM, porque no final eu preciso escolher um pdm."*

---

## 1. Como é hoje

O caminho de um item até a tela de revisão:

1. **Pré-filtro, sem IA** (`CatalogoPDM.candidatos`): quebra `DESCRIÇÃO + MARCA/MODELO` em
   palavras e pontua os 1.199 PDMs por raridade da palavra × peso do campo onde casou —
   nome base 5,0, modificador 4,0, título 3,0, **característica 1,0** —, menos 0,25 por palavra
   do título que a descrição não trouxe. Teto de 3 por classe, 12 vagas.
2. **`categorizar_pdm`** (grok-4.5, blocos de 15): escolhe entre os candidatos, com o catálogo
   inteiro no prompt como rede.
3. **Revisão** (`JanelaRevisaoPDM`): toda escolha passa por ela antes do portal.

**Os dois casos que o usuário trouxe, e por que cada um falha:**

| Item | PDM certo | Onde quebra |
|---|---|---|
| DISPLAY CRISTAL LIQUIDO 20X2 BACKLIGHT VERDE | `PDM.6685.017`, INDICADOR DIGITAL | **No pré-filtro.** A única ponte é a característica *CARACTERISTICAS DO DISPLAY*, no peso 1,0; qualquer PDM com "cristal", "liquido" ou "verde" no nome vale 5,0. Reproduzido: último de 7 num catálogo sintético; no Master não chega às 12 vagas, e o modelo nunca o vê. |
| PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC | `PDM.5930.012`, PLAQUETA INDICADORA | **No prompt.** O pré-filtro põe o PDM em **1º**, e a resposta foi NENHUM. Suspeita: a Regra B ("o fabricante restringe a classe antes de qualquer outra coisa") manda ficar na família de válvulas — e contradiz a Regra A ("a peça é catalogada pelo que ela É"). |

E a política que transforma dúvida em trabalho manual: *"NENHUM é uma resposta correta e
esperada — melhor do que o PDM menos ruim"*. Ela supõe que a escolha é final; não é — tudo
passa pela revisão, onde um palpite próximo se corrige com um clique e um NENHUM exige procurar
à mão entre 1.199.

## 2. Decisões do usuário (2026-10-08)

| # | Pergunta | Decisão |
|---|---|---|
| 1 | Quem interpreta o material | **A IA.** A busca por palavras deixa de ser porteira e vira rede. |
| 2 | Orçamento | **Aceita uma 2ª chamada curta** por lote. |
| 3 | "Probabilidade de ser aquele PDM" | **Confiança em três níveis** (ALTA/MÉDIA/BAIXA), e não porcentagem — a confiança que um modelo declara não é probabilidade calibrada. Junto: sinais objetivos calculados pelo código e o **2º e 3º lugar**. |
| 4 | NENHUM | **Só para "precisa de PDM novo"**, o caso raro. Para "não tenho certeza" existe BAIXA com palpite. |
| 5 | Aferir a confiança | **Registrar o que a IA disse × o que o usuário escolheu na revisão**, para o número virar medição com o tempo. |
| 6 | Arquitetura | **Duas passadas** (§4), aprovada. |

## 3. Abordagens consideradas

- **A — a interpretação alimenta a busca** (escolhida). A passada 1 traduz a descrição para o
  vocabulário do catálogo; o pré-filtro de hoje passa a buscar com esse texto, e casar sinônimo
  vira casar palavra no nome base. Resolve os dois casos pelo mesmo mecanismo e mantém a busca
  atual como rede.
- **B — a interpretação escolhe a classe FSC**, e a passada 2 vê só os PDMs daquela classe.
  Mais limpo, mas o risco fica concentrado: classe errada perde o item inteiro, sem rede — e
  adivinhar classe a partir de descrição de fornecedor é justamente o difícil.
- **C — busca semântica por embeddings.** A mais robusta para sinônimo e a mais cara de montar:
  o módulo de embeddings do projeto é da frente do Rafael (`autospec_embeddings.py`). Fica para
  depois, se a consulta traduzida ainda errar.

## 4. Desenho

```
lote (ex.: 63 itens)
 ├─ PASSADA 1  interpretar_material   1 chamada, SEM catálogo         §4.1
 ├─ BUSCA      duas frentes           código, sem IA                  §4.2
 ├─ PASSADA 2  categorizar_pdm        blocos de 15, como hoje         §4.3
 ├─ REVISÃO    preparar_para_revisao  código: guardas, sinais, ordem  §4.4–4.6
 └─ CALIBRAÇÃO registro .jsonl        ao confirmar a revisão          §4.7
```

### 4.1 Passada 1 — `interpretar_material`

- **Prompt** `prompts.montar_interpretar_material(itens)` e **tarefa** `"interpretar_material"`
  em `config.LLM_TASKS` — as duas são **zona compartilhada 🔴**: commit isolado, mensagem
  explícita. O modelo segue a resolução de qualquer tarefa: escolha por tarefa no painel →
  **escolha global do painel** → padrão do `config` (`gemini-3-flash-preview`). Política no
  `client`: 1 retentativa (a falha degrada sem perda, §4.8).
- **Entrada**, por item: número, descrição, marca/modelo. **Sem o catálogo** — é o que a torna
  barata.
- **Saída**, por item:

  ```json
  {"item": 7, "e": "PLAQUETA INDICADORA",
   "sinonimos": ["PLACA IDENTIFICACAO", "ETIQUETA"],
   "serve": "VALVULA DUPLOMATIC"}
  ```

  `e` é o que a peça É, no vocabulário de catálogo (substantivo genérico, sem marca);
  `sinonimos`, até 4; `serve`, o equipamento a que ela se destina, quando a descrição diz.
- **Uma chamada para o lote** (fatias de 60 acima disso). Serviço:
  `GeminiCategorizer.interpretar_lote(df)`, que devolve uma `Interpretacao` (ou `None`) por
  item, na ordem do lote: casa por número (mesma régua de `alinhar_resposta`) e descarta
  entrada sem `e` utilizável.

### 4.2 Busca em duas frentes — `CatalogoPDM.candidatos_em_duas_frentes(...)`

Função pura em `pdm_catalogo.py`, sobre o `candidatos()` de hoje, que não muda:

- **Frente A** — consulta `e + sinonimos`: **até 8 vagas**. As palavras de `serve` não fazem
  parte dela.
- **Frente B** — a busca de hoje, intacta (`DESCRIÇÃO + MARCA/MODELO`): **até 4 vagas**. É a
  rede contra erro da passada 1, por isso não é filtrada pelo que a passada 1 disse.
- União sem repetir (vale a 1ª ocorrência, A antes de B). Se uma frente render menos que a sua
  cota, a outra completa até 12 — o total, e com ele o tamanho do prompt, fica igual ao de hoje.
- Item sem interpretação → B ocupa as 12 vagas, que é exatamente o comportamento atual.

No caso da plaqueta, as válvulas que a palavra "VALVULA" puxa ficam limitadas às vagas da
frente B; as 8 da frente A vêm de "PLAQUETA INDICADORA" e sinônimos.

### 4.3 Passada 2 — `categorizar_pdm`

Mesma tarefa, mesmos blocos de 15, mesmo modelo. O que muda no prompt:

1. **Cada item traz a interpretação:** `- Interpretação: é PLAQUETA INDICADORA · sinônimos: … · serve a: VALVULA DUPLOMATIC`.
2. **Campos novos na resposta**, em acréscimo aos 7 de hoje:
   - `confianca`: `"ALTA"` | `"MEDIA"` | `"BAIXA"`;
   - `alternativas`: até 2 objetos `{"pdm": ..., "motivo": ...}`, com o PDM copiado
     literalmente da lista, em ordem (o motivo é o que o seletor mostra, §4.6);
   - `justificativa`: uma frase;
   - `caracteristicas_que_confirmam`: nomes de características do PDM escolhido que a descrição
     confirma — é o critério do usuário ("ver se as características se enquadram") virado
     campo, e é conferível (§4.5).
3. **Política:** sempre o melhor palpite, com a confiança honesta. NENHUM só quando nenhuma
   família do material existe no catálogo.
4. **Regra B subordinada à Regra A** (auditoria, achado P5): a marca só restringe a família
   quando é de quem fabricou a peça; marca depois de "PARA"/"P/" descreve a aplicação.
5. **Ordem das seções:** cabeçalho → LISTA DE PDMS → EXEMPLOS → MANUAL → ITENS (auditoria, P6).
   Tudo antes do MANUAL é idêntico nos blocos, e o cache de prefixo do provedor pode
   aproveitá-lo (~12,4 mil tokens por bloco a partir do 2º).
6. **Exemplos escritos por código** (auditoria, P8): o exemplo cita o código; o título vem do
   catálogo carregado na hora, e **código ausente do Master tira o exemplo**. Entram os dois
   casos reais (`PDM.5930.012`, `PDM.6685.017`); saem o PATCH PANEL e o ACCESS POINT, dois
   exemplos sem "Por quê" e da mesma classe 5895 de outros dois, para os domínios variarem.

`alinhar_resposta` e `processar_item_individual` não mudam: leem campo a campo pelo nome, e os
campos novos são só acréscimo.

### 4.4 Do JSON à linha da revisão — `cria_fichas.preparar_para_revisao(...)`

Hoje o laço que transforma a resposta em linha da revisão mora **na tela**
(`views/cria_fichas.py:353-379`) e já tem regra de negócio (a guarda contra PDM inventado), o
que contraria o princípio 2. Ele vai para o serviço antes de ganhar mais regras:

- comportamento de hoje, preservado: item sem resposta → NENHUM; `conferir_pdm` recusa PDM
  inventado → NENHUM; as contagens do resumo de log;
- novo: cada alternativa passa por `catalogo.resolver` (fora do catálogo ou igual à escolhida
  → descartada, com log); `confianca` ausente ou inválida → BAIXA; sinais e confiança final
  (§4.5).

A tela só monta o DataFrame com o que o serviço devolve e abre a revisão.

### 4.5 Sinais objetivos e a confiança final — função pura

Três conferências, cada uma ✓ ou ✗:

| Sinal | Confirma quando |
|---|---|
| **na busca** | o PDM escolhido estava entre os candidatos do item |
| **nome base** | todas as palavras do nome base do PDM escolhido aparecem no `e` ou num sinônimo da passada 1 |
| **características** | ao menos uma característica foi citada, e todas as citadas existem no PDM escolhido (revisão vigente) |

As comparações usam a mesma normalização do catálogo (`pdm_catalogo.normalizar`: maiúsculas, sem acento, espaços
colapsados).

**Regra da confiança final:** ALTA só continua ALTA com **pelo menos 2 de 3** sinais;
senão vira MÉDIA, marcada como rebaixada. MÉDIA e BAIXA ficam como vieram. Sem passada 1 para
o item, o sinal "nome base" conta como ✗ (ALTA passa a exigir os outros dois).

Por que rebaixar e não só mostrar: um ALTA sem nenhuma conferência é o erro mais caro — é
justamente o que se aprova sem olhar.

### 4.6 Tela de revisão

- Coluna nova **Confiança**: `ALTA`, `MÉDIA` ou `BAIXA`; `MÉDIA ↓` quando rebaixada. Para
  NENHUM, a causa: `PDM NOVO?` (a IA respondeu NENHUM), `SEM RESPOSTA` (a IA pulou o item) ou
  `FORA DO CATÁLOGO` (a guarda recusou um PDM inventado). Linha do modo "Pular IA" fica sem
  rótulo.
- **Ordem**: NENHUM → BAIXA → MÉDIA → ALTA; dentro do mesmo nível, a ordem da planilha. Linhas
  do modo "Pular IA" ficam na ordem da planilha. A coluna ID continua com o número original da
  linha. A ordenação é função do serviço; a tela só exibe.
- Ao selecionar uma linha, um rótulo sob a tabela mostra a justificativa e os sinais
  (`na busca ✓ · nome base ✓ · características ✗`).
- **Trocar o PDM:** `JanelaEscolherPDM` ganha `sugestoes=` e abre com o 2º e o 3º lugar fixos
  no topo, cada um com o motivo. A busca livre continua igual.

### 4.7 Registro de calibração

Ao confirmar a revisão (`_pos_revisao_concluida`), uma linha JSON por item em
`dados_usuario.pasta_logs() / "escolha_pdm.jsonl"`:

```json
{"data": "2026-10-08T14:02:11", "descricao": "...", "marca": "...",
 "interpretacao": {"e": "...", "sinonimos": [...], "serve": "..."},
 "ia": {"pdm": "...", "origem_do_nenhum": "", "confianca": "ALTA", "confianca_final": "MEDIA",
        "sinais": {"na_busca": true, "nome_base": false, "caracteristicas": false},
        "alternativas": [{"pdm": "...", "motivo": "..."}]},
 "final": "...", "trocou": true, "posicao_do_final": 2,
 "modelos": {"passada_1": "...", "passada_2": "..."}}
```

`posicao_do_final`: a posição do PDM final em `[escolhido, alternativa 1, alternativa 2]` —
1, 2 ou 3 —, ou 0 se ele veio da busca livre. NENHUM entra na comparação como qualquer outro
valor: a IA disse NENHUM e o usuário manteve → 1. `origem_do_nenhum` separa o NENHUM da IA
(`ia`) do item que ela nem respondeu (`sem_resposta`) ou que a guarda recusou
(`fora_do_catalogo`): só o primeiro é julgamento dela. Nada lê o arquivo ainda: depois de 2 ou 3
lotes, uma conta simples diz quanto ALTA de fato acerta.

### 4.8 Quando algo falha

A passada 1 nunca derruba o lote.

| Falha | O que acontece | No log |
|---|---|---|
| passada 1 cai (rede, chave, JSON inválido) | o lote segue **como hoje**: frente B nas 12 vagas, sem interpretação | `IA: interpretação indisponível (<motivo>). Seguindo só com a busca por palavras.` |
| passada 1 sem resposta para um item, ou `e` vazio | esse item segue como hoje | contagem no resumo |
| alternativa fora do catálogo | descartada | item e texto recusado |
| `confianca` ausente ou inválida | BAIXA | — |
| característica citada que não existe no PDM | sinal ✗ | item e nome citado |
| passada 2 cai | como hoje | como hoje |

## 5. O que NÃO muda

- Blocos de 15, modelo e política de retry da passada 2.
- Casamento da resposta pelo `item_processado`; a guarda que recusa PDM inventado.
- `processar_item_individual` e a criação no portal: NENHUM continua sendo "pular".
- `CatalogoPDM.candidatos()`: vira a frente B, intacta.
- Os 7 campos de resposta de hoje.

## 6. Testes

Todos offline, escritos antes do código (TDD), no padrão do projeto:

- **Caracterização antes de mover** (§4.4): o comportamento atual do laço da tela (sem
  resposta → NENHUM; inventado → NENHUM; contagens) vira teste do serviço **antes** da mudança
  de lugar, e o teste continua verde depois.
- **Busca em duas frentes:** cotas 8 + 4; completar quando uma frente rende pouco; sem
  repetição; sem interpretação = idêntico a `candidatos()`; os dois casos reais como regressão
  de mecanismo (catálogo sintético com os códigos reais): "INDICADOR DIGITAL" põe o
  `PDM.6685.017` nas vagas; as palavras de `serve` não promovem válvula na frente A.
- **Passada 1:** casamento por número, resposta parcial, lixo, e a degradação — o serviço que
  falha na passada 1 devolve o mesmo resultado de hoje, com a linha de log.
- **Passada 2:** campos novos lidos; alternativa fora do catálogo descartada; confiança
  inválida → BAIXA.
- **Sinais e regra de rebaixamento:** tabela de casos da função pura.
- **Cache:** dois blocos do mesmo lote compartilham o prefixo inteiro até o MANUAL — prova
  offline da propriedade que motivou a reordenação.
- **Exemplos por código:** código presente → título do catálogo; código ausente → exemplo
  some.
- **Ordem da revisão** e **registro de calibração** (com `tmp_path`).
- **Snapshots de prompt:** a fixture `cria_fichas_prompt.txt` é regerada e nasce a da passada 1,
  `interpretar_material_prompt.txt`.
  Pela regra do projeto, fixture só se regera com o aval do usuário: **aprovar esta spec é esse
  aval**, restrito a essas duas fixtures.
- **Tela:** guard por AST de que `views/cria_fichas.py` não chama mais `conferir_pdm` (a regra
  foi para o serviço), mais as três partes de verificação da UI — inclusive abrir o app.

## 7. O que só a máquina do usuário prova

- **Qualidade.** Rodar o mesmo lote de 63 itens **até a tela de revisão**, sem criar fichas, e
  contar: quantos `PDM NOVO?`; em quantos o 1º lugar acerta; em quantos o certo está no 2º ou
  3º; e os dois casos reais.
- **Custo e tempo.** O painel "Gastos de IA", antes × depois, no mesmo lote. Meta: não ficar
  mais caro que hoje — a passada 1 custa pouco, e o cache dos blocos 2 a 5 pode compensá-la, se
  o provedor da passada 2 aplicar cache de prefixo (não é garantido para todo provedor; o
  registro de uso mostra).
- **Versão.** Melhoria de função que já existe = PATCH (`sigft-lancar-versao`), passando por rc.

## 8. Fora do escopo agora

- Blocos da passada 2 em paralelo (registrado no `PENDENCIAS.md`).
- O relatório da calibração — agora só o registro.
- Busca por embeddings (abordagem C).
- Os achados da auditoria fora da escolha de PDM (P1–P4, P7, P9, P10).

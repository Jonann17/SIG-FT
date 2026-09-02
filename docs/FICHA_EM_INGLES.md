# Ficha técnica em inglês — caderno da frente

> Aberta em 2026-08-28. Companheira de
> [`base-conhecimento/13-montagem-da-ficha-tecnica.md`](base-conhecimento/13-montagem-da-ficha-tecnica.md),
> que mapeia **como a ficha nasce**. Aqui está o que muda para ela nascer em
> inglês, o que já está pronto e o que ainda espera.

## O problema

O SIG-FT tem **dois templates** de ficha — PT-BR e inglês —, mas as
características técnicas coladas dentro deles vêm sempre da **mesma** pasta de
PDMs Modificados, que está em português. A tradução era feita **à mão**, ficha
a ficha.

## O desenho (decisões do usuário, 2026-08-28)

| Pergunta | Decisão |
|---|---|
| Como o app sabe o idioma? | **Seletor explícito na tela** (Português / English). Deduzir do nome do arquivo do template quebraria em silêncio no dia em que alguém o renomeasse — e ficha montada no idioma errado não se denuncia sozinha |
| Qual motor de tradução? | **IA primeiro, `deep_translator` de reserva.** A IA entende termo técnico de hidrelétrica; a `deep_translator` é a mesma cadeia (Google → MyMemory) que o fluxo do espanhol já usa |
| Como corrigir termo errado? | **Glossário editável**, consultado antes do motor |
| Onde ficam os traduzidos? | Pasta paralela, escolhida na tela |

## O fluxo, agora

```
PDMs Modificados/                     (português, como sempre)
      │
      │  Aba 1, passo 3: "Traduzir PDMs Modificados para inglês"
      ▼
PDMs Modificados EN/                  + _GLOSSARIO_PT_EN.txt
      │                               + _CACHE_TRADUCAO.json
      │  Aba 2, idioma = English
      ▼
Ficha em inglês
```

O idioma escolhido na aba 2 decide **qual pasta** o montador usa. Em
português, nada muda: quem não tocar no seletor tem exatamente o
comportamento de sempre.

## O que o serviço faz, e por quê

`sigft/services/traducao_pdm.py`. Os arquivos traduzidos mantêm **nome e
geometria** dos originais, e isso não é estética:

- **o nome**, porque o montador acha o PDM por *substring* do id
  (`PDM_1234_001`) no nome do arquivo — renomear quebraria o casamento em
  silêncio;
- **a célula**, porque o montador lê `cell(linha, 1)` — escrever noutra coluna
  geraria fichas em branco, e ninguém perceberia até abrir uma.

Cada arquivo é **copiado** e só a célula da descrição é reescrita: mescla,
bordas, altura 32 e fonte 8 sobrevivem sem precisar ser refeitas.

**Só o miolo da pergunta viaja.** Em `"1 - Pressão de trabalho (bar):"`, o
`"1 - "` é numeração e o `":"` é pontuação — mandar os dois para um tradutor é
pedir para ele inventar. A unidade viaja **junto** com a descrição, de
propósito: `"Pressão (bar)"` dá ao motor o contexto que `"Pressão"` sozinho
não dá.

### Três camadas antes do motor

| Camada | Arquivo | Quem mantém |
|---|---|---|
| **Glossário** — frase inteira que estiver lá é usada verbatim, sem chamar o motor; termo solto vira vocabulário obrigatório no prompt | `_GLOSSARIO_PT_EN.txt` | **você**, editando à mão |
| **Cache** — rerodar a pasta não paga tradução de novo | `_CACHE_TRADUCAO.json` | a máquina |
| **Dedupe** — `Fabricante`, `Modelo`, `Peso` aparecem em dezenas de PDMs e vão ao motor uma vez só | (em memória) | — |

Separar glossário de cache é deliberado: o glossário é **curado por gente** e
vence tudo; o cache é crescido pela máquina. Misturar faria a sua correção se
perder na próxima limpeza de cache.

O glossário lê UTF-8 **e cp1252** — o arquivo é para ser editado à mão, e o
Bloco de Notas ainda oferece ANSI no "Salvar como". Mesma lição do `.txt` da
conferência do AutoSpec.

## Um defeito antigo que saiu junto

`aplicar_templates_fichas` fazia `wb_target["Ficha Técnica Padrão"]` — **nome
de aba fixo**. Um template com a aba noutro nome levantava `KeyError` dentro
do laço, e o `except` genérico transformava isso em `"ERRO ao gerar ficha
{pmib}"` **uma vez por ficha**: num lote de 200 materiais, 200 linhas
idênticas, nenhuma delas dizendo que o problema era a aba.

Agora `nome_da_aba_da_ficha` aceita variações (sem acento, maiúsculas, e os
nomes em inglês), usa a aba única quando só há uma, e — quando de fato não
reconhece nenhuma — **para o lote com os nomes encontrados na mensagem**.
Template errado é problema do template, não de cada ficha.

## Pendente: o template em inglês

⚠️ **Falta o arquivo.** Está tudo pronto e testado contra um template EN
*sintético* (aba `Standard Datasheet`, injeção na linha 79, colunas C e M).
Quando o template real chegar, conferir:

| O quê | Por que importa |
|---|---|
| **Nome da aba** | Se não for um dos aceitos (`Ficha Técnica Padrão`, `Standard Datasheet`, `Technical Datasheet`, `Datasheet`), basta acrescentá-lo a `NOMES_DA_ABA_DA_FICHA` |
| **Linha inicial** | O montador injeta a partir da **79**, fixa. Se a seção do template EN começar noutra linha, as perguntas caem no lugar errado — e isso **não** levanta erro nenhum |
| **Colunas C e M** | Idem: são fixas, e o desalinhamento é silencioso |

As duas últimas são as perigosas: nome de aba errado grita, geometria errada
não.

## Verificação

- **48 testes** (22 do serviço de tradução, 16 do montador/idioma, e os
  existentes do PDM que continuam passando).
- **Ponta a ponta com `.xlsx` reais**: pasta traduzida, dedupe (pergunta
  repetida foi ao motor uma vez só), cache (2ª rodada não consultou o motor),
  glossário vencendo o motor, mescla e altura preservadas, e as duas fichas
  montadas lado a lado — mesma célula C79, idiomas diferentes.
- O motor de tradução é **injetado** nos testes: testar o Google Tradutor
  seria medir a rede, não o código.

## Ainda em aberto

| Item | Nota |
|---|---|
| Rodar com o **template EN real** | ver acima |
| Rodar com o **motor de verdade** (IA/`deep_translator`) | o contêiner do Claude na web não tem `deep_translator` nem chave de IA; a qualidade da tradução técnica só dá para julgar na sua máquina |
| Semear o glossário com os termos do AutoSpec | o `GLOSSARIO_MULTILINGUE` do AutoSpec tem 71 termos PT/EN/DE/ES/FR/IT que serviriam de partida |

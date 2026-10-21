# Como uma ficha técnica nasce — do PDM da Itaipu à ficha em branco

> Mapeado em 2026-08-28. Este documento não descreve **um** módulo: descreve o
> **processo** que atravessa `sigft/services/pdm.py`, `sigft/app_qt/views/pdm.py`,
> o `_STATUS_PMIB` e os templates de ficha. Ele existe porque a pergunta
> "de onde vêm as características técnicas da ficha?" não tinha resposta em
> lugar nenhum. Atualizado em 2026-10-21 (um caminho só, pela planilha).

## O resumo em uma frase

A Itaipu exporta **a planilha de PDMs** (`PDMs_SAM-GM_<data>.xlsx`); o
aplicativo lê dela as perguntas de cada PDM e as cola dentro de um **template
de ficha**, escolhendo quais perguntas entram em qual ficha pelo **PDM que o
`_STATUS_PMIB` associa àquele código PMIB**. Em inglês, as perguntas são
traduzidas no caminho.

> **Desde 2026-10-21 há um caminho só** (pedido do Luan). O caminho antigo,
> pelas pastas "PDMs From Itaipu" e "PDMs Modificados" (fatiar a lista geral,
> formatar, regenerar, traduzir a pasta, excluir duplicados), saiu do SIG-FT
> junto com as abas "Processar PDMs" e "Excluir Duplicados". A história dele
> está no `git log` e na versão anterior deste documento.

## O caminho

```
  PDMs_SAM-GM_<data>.xlsx              (a exportação da Itaipu, aba TEMPLATE_PDM)
        │
        │  pdm_catalogo.carregar()      revisão vigente, características em ordem
        ▼
  CatalogoPDM
        │
        │  pdm.processar_pastas_fichas()      _STATUS_PMIB -> (PMIB, "PDM usado", pasta)
        │  pdm_planilha.perguntas_do_pdm()    as 9 regras abaixo, uma ficha por vez
        ▼
  as perguntas  "1 - NOME (AJUDA):"
        │
        │  (só em inglês) traducao_pdm: preparar_traducao() + traducao_conhecida()
        ▼
        │  pdm.aplicar_templates_fichas_da_planilha()   o montador (_montar_fichas)
        ▼
  Fichas/4500063671.0071.xlsx          (a ficha em branco, pronta p/ o fornecedor)
```

**`processar_pastas_fichas(arquivo_STATUS_PMIB, destino, ...)`** lê a planilha
de status e devolve, para cada material, a tripla
`(código PMIB formatado, "PDM.1234.001 - NOME, MOD, R2", pasta de destino)`. É
aqui que a associação **material → PDM** acontece: ela vem da coluna *"PDM
usado"* do `_STATUS_PMIB`, não de nenhuma regra do código.

**`aplicar_templates_fichas_da_planilha(lista, catalogo, path_template,
idioma="pt", traduzir=None, pasta_traducao=None)`** é o montador:

| Pergunta | Escreve na ficha |
|---|---|
| `"N - NOME (AJUDA):"` | coluna **C**, mesclando **3–12**, a partir da **linha 79** |
| (resposta, vazia) | coluna **M**, mesclando **13–22** |

Fonte 8, quebra de linha, altura 32, bordas finas. O template é lido do disco
**uma vez só**, para `BytesIO`, e cada ficha recebe uma cópia limpa a partir
desses bytes (CP 4.3).

| # | Situação | O que acontece |
|---|---|---|
| 1 | Qual revisão | A vigente: a maior `REVISIÓN` do código (a mesma regra do módulo 1 e do Upload Specs) |
| 2 | Ordem | Pela coluna `SECUENCIA`, numeradas de 1 a N; sem sequência legível, vai para o fim |
| 3 | Texto | `"N - NOME (AJUDA):"`, ou `"N - NOME:"` sem ajuda; nome e ajuda como a Itaipu escreveu. Acabou o `(nan)` |
| 4 | Portal numa revisão **menor** que a planilha | Gera com a da planilha; aviso de que o PDM precisa subir de revisão no portal |
| 5 | Portal numa revisão **maior** que a planilha | Gera com a da planilha; aviso para exportar uma planilha nova da Itaipu |
| 6 | Código com dois nomes base na planilha | Gera só se o título do "PDM usado" começar pelo nome base da revisão vigente; se não, recusa mostrando os dois |
| 7 | "PDM usado" sem código, código fora da planilha, PDM sem característica | Recusa aquela ficha; o lote segue |
| 8 | Planilha sem característica nenhuma (o formato manipulado antigo) | O lote para antes de começar |
| 9 | "PDM usado" sem revisão (formato antigo) | Sem conferência de revisão; gera com a vigente |

Os avisos 4 e 5 também saem agrupados no fim do log, com a lista dos PMIBs de
cada caso.

### Em inglês (desde 2026-10-21)

Com `idioma="en"`, antes de montar a primeira ficha o montador junta as
perguntas de todas as fichas do lote e as traduz de uma vez (cada texto uma
vez, em lotes de 60), com o glossário e o cache da pasta
`Documentos\SIG-FT\traducao_pdm\`. Cada ficha pega as traduções prontas; a
aba da ficha ganha o nome `Standard Technical Sheet`. Pergunta que não
traduziu fica em português, e a ficha ganha um aviso no log ("N pergunta(s) sem
traducao: ficaram em portugues na ficha em ingles"): o tradutor nunca derruba
o lote. Detalhes em [`docs/FICHA_EM_INGLES.md`](../FICHA_EM_INGLES.md).

## Duas coisas que só se descobrem lendo o código

1. **O nome da aba de destino ERA fixo: `"Ficha Técnica Padrão"`.** Um template
   cuja aba se chamasse outra coisa fazia o montador levantar `KeyError` — e o
   erro caía no `except` genérico do laço, virando `"ERRO ao gerar ficha
   {pmib}"` para **todas** as fichas: num lote de 200 materiais, 200 linhas
   idênticas, nenhuma dizendo que o problema era a aba.
   **Corrigido em 2026-08-28** (`nome_da_aba_da_ficha`): aceita variações,
   usa a aba única quando só há uma, e quando não reconhece nenhuma **para o
   lote** com os nomes encontrados na mensagem.

   O template em inglês real confirmou que a preocupação não era teórica — mas
   pelo avesso do que eu esperava: `Technical_Sheet_of_PDM-R3.xlsx` traz a aba
   com o nome **em português**, herdado do template do qual foi derivado, e é
   a ficha já preenchida (`4500063671.0052_enUS.xlsx`) que traz
   `Standard Technical Sheet`. Os dois nomes circulam.

2. **A linha 79 é fixa em três lugares independentes.** Aqui
   (`start_row = 79`), em `sigft/config.LINHA_SPECS_FICHA` (usado pelo
   `analyzer` e pelo `autospec`) e em `translator.py` (`current_row = 79`).
   Só os dois últimos estão unificados; este não. Ver `PENDENCIAS.md`, entrada
   de 2026-07-28 do CP 2.4.

## Onde cada coisa mora

| O quê | Onde |
|---|---|
| O montador e a leitura do `_STATUS_PMIB` | `sigft/services/pdm.py` |
| A leitura da planilha de PDMs (`CatalogoPDM`) | `sigft/core/pdm_catalogo.py` |
| As regras da ficha pela planilha | `sigft/services/pdm_planilha.py` |
| A tradução das perguntas (ficha em inglês) | `sigft/services/traducao_pdm.py` |
| Glossário e cache da tradução | `Documentos\SIG-FT\traducao_pdm\` (`traducao_pdm.pasta_da_traducao()`) |
| A tela (sem abas: planilha em cima, criação embaixo) | `sigft/app_qt/views/pdm.py` |
| Pasta padrão do template e do `_STATUS_PMIB` | `sigft/core/prefs.py` → `PASTAS_PADRAO_SEED` / `PASTAS_PADRAO_POR_CHAVE` |
| Layout da ficha preenchida (`CONFIG_MAP`) | `sigft/core/rpa/ficha_layout.py` |

## O template, nos dois idiomas

Até 2026-08-28 o aplicativo **não sabia em que idioma o template estava**: a
tela pedia *"Selecionar Template (.xlsx)"* e usava o arquivo escolhido; nada no
código distinguia o PT-BR do inglês, e as perguntas coladas vinham sempre em
português. A tela tem um **seletor de idioma**: em inglês, as perguntas da
planilha são traduzidas antes de entrar na ficha — ver
[`docs/FICHA_EM_INGLES.md`](../FICHA_EM_INGLES.md).

### A geometria dos dois, medida (2026-09-03)

Os dois templates são **o mesmo documento traduzido**, e a geometria não mudou
em nenhum ponto que o montador toca:

| | PT-BR | Inglês |
|---|---|---|
| Título da seção (B75) | `ESPECIFICAÇÕES TÉCNICAS - INDIQUE...` | `TECHNICAL SPECIFICATIONS - INDICATE...` |
| Primeira pergunta | **C79** | **C79** |
| Mescla da pergunta | `C{n}:L{n}` | `C{n}:L{n}` |
| Mescla da resposta | `M{n}:V{n}` | `M{n}:V{n}` |
| Abaixo da seção | vazio até a 156 | vazio até a 156 |
| Nome da aba | `Ficha Técnica Padrão` | `Ficha Técnica Padrão` **no template**, `Standard Technical Sheet` na ficha entregue |

Nada abaixo da linha 76 nos dois: por mais perguntas que o PDM traga, a
injeção não tem rodapé para sobrescrever.

### A forma da pergunta — o que ela realmente é

Não é um rótulo curto com a unidade entre parênteses. É o nome da
característica em MAIÚSCULAS seguido da **instrução de preenchimento inteira**,
com parênteses aninhados dentro:

```
9 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item. Nota: Material
especifico de compra com (Número de desenho, referência, nome usual, outros)):
```

De 100 a 200 caracteres. Quem for mexer em qualquer coisa que **leia ou
escreva** essa string — tradução, validação por IA, extração de campo — precisa
partir daqui, e não de `"1 - Pressão (bar):"`. Essa suposição errada já custou
uma regra de prompt que mandava deixar a instrução em português.

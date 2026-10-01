---
tags: [sigft, modulos, referencia]
---

# SIG-FT — Módulos

Os 13 módulos, na ordem em que aparecem no [[Ciclo de Vida de um Item|ciclo de vida]].
Cada um tem um doc próprio em `docs/base-conhecimento/` no repositorio.

---

## 1. Criar Fichas
`sigft/services/cria_fichas.py` · doc `01-cria-fichas-backend.md`

**Cria as fichas no portal e escolhe o PDM.** O módulo de entrada do processo.

Três operacoes:
1. **Leitura inteligente** do `_STATUS_PMIB` — detecta a linha de cabeçalho e sugere o
   código de projeto (procura a coluna `ITEM` e lê a célula uma linha acima).
2. **Classificação em lote por IA** — recebe a descrição do material, o catalogo de
   PDMs (abas `PDMs` e `Instrucoes PDMs`) e um manual de regras; devolve
   `pdm_escolhido`, `descricao_curta`, `origem`, `tipo`, `tipo de fabricacao`, `unidade`.
3. **RPA** — preenche PDM, Contrato, Código Projeto, Descrição Breve, Origem, Tipo,
   Unidade e Fabricacao.

**Escreve** `CODIGO PMIB` e `PDM usado` no [[Planilha STATUS_PMIB]].

Tem também **atualização de projeto em massa**, para quando o código de projeto muda.

> Por que importa: o PDM define as perguntas da ficha. **PDM errado = ficha inteira errada.**

---

## 2. PDM
`sigft/services/pdm.py` · doc `02-pdm-backend.md`

**Fatia o catalogo e gera a [[Planilha PMIB]] de cada material.**

- `pdms_fromItaipu_lista_geral()` — quebra o catalogo geral (aba `TEMPLATE_PDM`) em um
  arquivo por código PDM, **preservando estilos** (fonte, borda, fill, formato, alinhamento).
- `processar_pastas_fichas()` — lê o `_STATUS_PMIB` e monta a lista de fichas a gerar,
  formatando o código PMIB com zeros a esquerda.
- `aplicar_templates_fichas()` — copia o template da ficha e **injeta as perguntas do
  PDM a partir da linha 79**: descrição na coluna C (merge 3-12), resposta na coluna M
  (merge 13-22).
- `logica_excluir_duplicados()` — limpa arquivos PDM repetidos, mantendo o maior/mais recente.

---

## 3. Tradutor
`sigft/services/translator.py` · doc `04-translator-backend.md`

**Gera a aba `Especificacoes tecnicas copiar`** com as respostas em espanhol e
português, sem acento.

- lê pergunta (coluna C) e resposta (coluna M) a partir da linha 79
- traduz PT->ES com GoogleTranslator, **fallback MyMemory**
- remove acentos com `unidecode` (exigencia do [[Anexo I - Classificacao de Materiais Sobressalentes|Anexo I item 2.3.1]])
- ignora `-`, `N/A`, `NA`, `.`, `0`
- formata: cabeçalho azul escuro, linhas zebradas, bordas, wrap, altura 50

> Usa **xlwings** (Excel COM) — **só funciona no Windows com Excel instalado**.
> Suporta caminho maior que 240 caracteres via arquivo temporario.

---

## 4. AutoSpec AI
`sigft/services/autospec*.py` · docs `08-` e `08b-`

**Preenche campos vazios da ficha via RAG.** Ver [[SIG-FT - Camada de IA]].
Frente do **Rafael** (`rafhagmm`); mergeada em 26/08/2026.

Sub-módulos: `autospec_rag.py`, `autospec_embeddings.py`, `autospec_unidades.py`,
`autospec_conferencia.py`.

---

## 5. Analyzer
`sigft/services/analyzer.py` · doc `03-analyzer-backend.md`

**Valida e pontua a ficha antes de emitir.** E o substituto automático da revisão
independente que o processo não tem (ver [[Anatomia de uma Ficha Tecnica]]).

- valida campos fixos pelo `CONFIG_MAP` (validação simples ou por IA, com **peso 1-7**
  por campo) e as variáveis técnicas da linha 79 em diante
- normaliza a nota para **0-100%**
- separa em `FT_good/` e `FT_bad/`, com o percentual no nome do arquivo
- em campo vazio ou invalido, escreve **"FORNECER"** em vermelho; em campo invalido,
  usa `CellRichText`: `FORNECER (valor tachado)`
- `FORBIDDEN_NA_STRINGS` — lista de "N/A" que contam como vazio

---

## 6. Upload Condições
`sigft/services/upload_conditions.py` · doc `05-`

**Preenche as 4 abas de [[Secao - Condicoes|Condições]] no portal.**

- extrai as células fixas da ficha (H6, H17-H21, P17-P19, M23, G25-G29...)
- manda a IA estruturar, sob a **REGRA 0 de fidelidade ao fornecedor**
- preenche no portal: Armazenamento, Transporte, Manutenção, Descarte
- marca `CONDICOES = COMPLETO` no `_STATUS_PMIB`

---

## 7. Upload Specs (Características Técnicas)
`sigft/services/tech_specs.py` · doc `06-`

**Preenche a tabela de [[Secao - Caracteristicas Tecnicas|características]] no portal.**

- cruza `_STATUS_PMIB` + **Master PDM** (`TEMPLATE_PDM`) + a aba
  `Especificacoes tecnicas copiar` da ficha
- a IA normaliza cada característica com regras **CHAR / INT / NUM / LISTA**:
  virgula decimal, ponto-e-virgula para listas, conversão de unidade
  (ex.: `l/min` -> `m3/h`), retencao ou exclusão de `N/A`
- gera JSON com `METADATA` + `DADOS_TRATADOS`, cada item com ação
  **`PREENCHER`** ou **`REMOVER`**
- no portal: **loop de paginacao**, exclusão segura de linha, **auditoria de rejeicao**
- campos que o portal recusa viram **relatório de pendências manuais**

---

## 8. Cadastro LMR
`sigft/services/lmr.py` · doc `09-lmr-backend.md`

**Cadastra as aplicações da [[Secao - Aplicacao LMR]] no portal.**

- lê a aba `GERAL` com colunas `PMIB`, `Codigo_PMIB`, `TAG_PMIB`
- **agrupa TAGs consecutivas pelo mesmo código** — e o que reduz o número de operacoes
- preenche *Equipment Code*, *Quantity Installed* e *Tag*
- falhas vao para **`erros_lmr.csv`** (ficha, index, código, erro)

---

## 9. Apagar LMR
`sigft/services/apagar_lmr.py` · doc `10-`

**Exclui em massa todas as aplicações LMR de uma ficha.**

Loop de lixeira + confirmacao até `TimeoutException` indicar que não ha mais linha.

> Este módulo e um **sintoma**: existe porque refazer a LMR do zero e mais rapido que
> corrigir linha a linha — e porque o critério da LMR ainda muda.
> Ver [[Revisao da Aplicacao LMR - Agosto 2026]].

---

## 10. Ficha Duplicada
`sigft/services/duplicadas*.py` · docs `07-` e `refatoracao/FICHA_DUPLICADA.md`

**Clona uma ficha base para uma ficha alvo.** Ver [[Fichas Duplicadas]].

Módulos: `duplicadas.py` (fila), `duplicadas_extrator.py`, `duplicadas_injetor.py`,
`duplicadas_robo.py`, e um por seção (`_condicoes`, `_documentos`, `_imagens`,
`_pdm`, `_spec`).

> **Marcado para reconstrucao na Fase 6.** Decisão de produto registrada:
> *"não funciona como deveria e esta muito fraco"*.

---

## 11. Gestão PMIB
`sigft/services/pmib_manager.py` · doc `11-`

**Alimenta o [[Mapeamento das Listas de Sobressalentes]].** O módulo de visão macro.

1. carrega a base do **Aconex DocManager** (histórico de revisões)
2. varre a arvore procurando `*_STATUS_PMIB.xlsx`
3. **renomeia** cada arquivo pelo `Tracking ID` + `Current` do Aconex — resolve o
   arquivo orfao quando a lista muda de código. Ver [[Codigo CMI e Codigo Itaipu]]
4. lê cada `_STATUS_PMIB` (com `dtype=str`, para não perder zeros) e conta os indicadores
5. atualiza a planilha mestra: metadados, indicadores, **cascata de `SITUACAO NO PMIB`**,
   hyperlinks para os arquivos, índices percentuais
6. **inserção interativa** — listas novas encontradas são confirmadas pelo operador
   antes de entrar

Tem `callback_retry_lock` para o caso classico de a planilha estar aberta no Excel.

---

## 12. Buscar Material
`sigft/services/search.py` · doc `12-`

**Acha um material em qualquer `_STATUS_PMIB` do projeto.**

Dois modos:
- **direcionada** — busca numa coluna específica
- **generalista** — normalização agressiva: maiuscula, remove acento via
  `unicodedata.normalize('NFD')`, remove tudo que não e `A-Z0-9`, e concatena a linha
  inteira. `"Codigo-ABC-123"` vira `"CODIGOABC123"`

Varre recursivamente com `os.walk`, detecta o cabeçalho pela palavra `DESCRICAO`,
e devolve código Itaipu, arquivo, pasta, coluna do match e amostra.

> Existe porque **o mesmo material pode estar em várias listas** e descobrir isso a mao
> e inviavel. E o insumo prático para identificar [[Fichas Duplicadas|duplicadas]].

---

## 13. Home
`sigft/app/views/home.py`

Dashboard de entrada, configuracao das chaves de API e o **seletor de modelo de IA**
(global e por tarefa). Ver [[SIG-FT - Camada de IA]].

---

## Mapa módulo x etapa do processo

| Etapa | Módulo |
|---|---|
| Escolher PDM e criar ficha | Criar Fichas |
| Gerar planilha para o fornecedor | PDM |
| Traduzir para espanhol | Tradutor |
| Preencher lacunas com IA | AutoSpec AI |
| Conferir antes de emitir | Analyzer |
| Subir condições | Upload Condições |
| Subir características | Upload Specs |
| Cadastrar aplicações | Cadastro LMR |
| Refazer aplicações | Apagar LMR |
| Clonar ficha idêntica | Ficha Duplicada |
| Consolidar visão macro | Gestão PMIB |
| Achar material | Buscar Material |

## Relacionados
[[SIG-FT - Arquitetura]] · [[Ciclo de Vida de um Item]] · [[SIG-FT - Refatoracao]]

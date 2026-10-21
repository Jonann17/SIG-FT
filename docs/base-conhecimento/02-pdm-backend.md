# Planilhas PMIB (`pdm_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-10-21)
>
> | O quê | Onde |
> |---|---|
> | `pdm_backend.py` (shim do nome antigo) | `sigft/services/pdm.py` (serviço) · `sigft/app_qt/views/pdm.py` (tela, classe `ModuloPDM`) |
> | a leitura da planilha de PDMs | `sigft/core/pdm_catalogo.py` |
> | as regras da ficha pela planilha | `sigft/services/pdm_planilha.py` |
> | a tradução das perguntas (ficha em inglês) | `sigft/services/traducao_pdm.py` |
>
> **2026-10-21 (pedido do Luan): a tela ficou só com a planilha de PDMs
> (SAM-GM) e a criação das planilhas PMIB.** Sairam as abas "Processar PDMs"
> (fatiar From Itaipu, PDMs Modificados, traduzir a pasta, regenerar as pastas)
> e "Excluir Duplicados", o campo "Pasta dos PDMs Modificados" e a escolha da
> fonte das características: elas vêm sempre da planilha. Com elas sairam
> `pdms_fromItaipu_lista_geral`, `aplicar_templates_fichas` (o método antigo,
> pela pasta), `processar_arquivo_pdm`, `salvar_tabela_formatada`,
> `formatar_tabela_de_perguntas`, `listar_arquivos_excel`, `extrair_pdm_id`,
> `mover_fichas_para_raiz`, `logica_excluir_duplicados`, o
> `services/pdm_regeneracao.py` inteiro e `traducao_pdm.traduzir_pasta`. O que
> elas faziam está no `git log` e na versão anterior deste documento.
>
> O processo inteiro (do PDM da Itaipu à ficha em branco) está em
> [`13-montagem-da-ficha-tecnica.md`](13-montagem-da-ficha-tecnica.md).

## Propósito

Montar as **planilhas das fichas PMIB**: para cada material do `_STATUS_PMIB`,
uma cópia do template de ficha com as perguntas (características técnicas) do
PDM daquele material, tiradas da planilha de PDMs exportada pela Itaipu. Em
português ou em inglês.

## A tela

Sem abas desde 2026-10-21. De cima para baixo:

1. **Configuração Global**: "Planilha de PDMs (SAM-GM)" (botão + nome do
   arquivo; aceita arrastar o arquivo).
2. **Configuração das Fichas PMIB** (um cartão com dois quadros):
   - "Selecionar STATUS_PMIB (.xlsx)", "Pasta Destino das Fichas", "Selecionar
     Template (.xlsx)";
   - "Idioma da ficha": Português / English, com a dica "(English traduz as
     características da planilha)";
   - "Seleção de Itens" (Todos da Lista / Selecionar Manualmente) e "Formato
     de Saída" (Apenas Planilhas / Criar Subpastas + Planilhas);
   - "Executar: Criar Fichas PMIB".
3. O console, com a altura padrão das telas (o formulário rola quando não cabe).

A tela valida os campos no clique (planilha, STATUS_PMIB, pasta de destino,
template), lê a planilha numa tarefa (`pdm_catalogo.carregar`; ilegível para o
lote antes de criar qualquer subpasta), prepara as pastas e chama o montador.
Em inglês ela monta o motor de tradução padrão
(`traducao_pdm.motor_padrao(callbacks=...)`, sem `api_key`: `get_llm` resolve
a chave do provedor escolhido em "Modelos de IA") e o passa ao serviço.

## Entradas e Saídas

- **Entradas**:
  - a planilha de PDMs (`PDMs_SAM-GM_<data>.xlsx`, aba `TEMPLATE_PDM`), lida
    por `pdm_catalogo.carregar`;
  - o `_STATUS_PMIB`, aba "Lista de Materiais" (colunas "CÓDIGO PMIB" e "PDM
    usado"). O cabeçalho é ACHADO nas 30 primeiras linhas por
    `ler_lista_materiais` (layout v2 desde 04/10/2026: linha 5, com a revisão
    em uso na linha 4; o layout antigo, linha 4, também é lido);
  - o template de ficha (aba resolvida por `nome_da_aba_da_ficha`; perguntas a
    partir da linha 79).
- **Saídas**: `{pmib}.xlsx` na pasta de destino (ou numa subpasta por PMIB),
  e o log no console via callback.

## Funções (`sigft/services/pdm.py`)

- **`ler_lista_materiais(arquivo_status_pmib)`** → DataFrame da aba "Lista de
  Materiais" com o cabeçalho achado (`core.excel.headers.find_header_row`
  procurando `CÓDIGO PMIB`; `config.LINHA_STATUS_PMIB` só como reserva).
- **`codigos_pmib_da_lista(arquivo_status_pmib)`** → códigos PMIB normalizados,
  sem repetição e ordenados: o que a tela mostra em "Selecionar Manualmente"
  (levanta `ValueError` sem a coluna).
- **`processar_pastas_fichas(arquivo_STATUS_PMIB, destino_fichas,
  lista_selecionados=None, criar_subpastas=True)`** → `(lista_dados, msg)`, com
  tuplas `(cod_fmt, pdm_usado, pasta)`; normaliza o código PMIB por
  `core.excel.pmib_codes.normalize_pmib`.
- **`aplicar_templates_fichas_da_planilha(lista_dados, catalogo, path_template,
  log_callback=None, retry_lock=None, idioma="pt", traduzir=None,
  pasta_traducao=None)`** → `(mensagem, log)`. Para cada material, as perguntas
  de `pdm_planilha.perguntas_do_pdm` (revisão vigente, ordem da SECUENCIA, sem
  "(nan)") entram no template a partir da C79 (mescla C–L e M–V, fonte 8,
  altura 32, bordas). Recusa a ficha, e segue o lote, quando o PDM não está na
  planilha, não tem característica ou aparece com dois nomes base; avisa quando
  a revisão do portal difere da planilha e lista esses PDMs no fim do log.
  Template lido do disco uma vez (`BytesIO` por ficha); template sem aba
  reconhecível para o lote com os nomes das abas.

  **`idioma="en"` (2026-10-21)**: antes da primeira ficha, as perguntas de
  todas as fichas do lote vão ao motor `traduzir` (`list[str] -> list[str]`;
  sem ele, `traducao_pdm.motor_padrao`), cada texto uma vez, em lotes de 60,
  com o glossário e o cache de `pasta_traducao` (sem ela,
  `traducao_pdm.pasta_da_traducao()` = `Documentos\SIG-FT\traducao_pdm\`). A
  aba da ficha ganha o nome `Standard Technical Sheet`. Pergunta que não
  traduziu fica em português, com `lote.aviso` na ficha ("N pergunta(s) sem
  traducao"); lote do motor que falha vira aviso no log. O lote nunca para por
  causa do tradutor.

O laço de montagem é `_montar_fichas` (uma implementação: template da memória,
aba resolvida uma vez, `RelatorioLote`, `locking.salvar_perguntando`).

## Pontos de Atenção

- **Linha 79 fixa** (`_escrever_perguntas`): não busca dinamicamente a linha de
  início. Se o template mudar, os dados vão para o lugar errado.
- **Mescla fixa** (colunas 3–12 e 13–22): template com coluna a mais fica com a
  mescla errada.
- **Ficha em inglês com o motor de verdade** só se avalia na máquina do
  usuário (IA/`deep_translator` não rodam na suíte); ver
  [`docs/FICHA_EM_INGLES.md`](../FICHA_EM_INGLES.md).
- **Pastas padrão**: só o template (`pdm.template` → "Templates") e o
  `_STATUS_PMIB` (`pdm.status_pmib` → "SOBRESSALENTES - PMIB") têm pasta
  semeada em `core/prefs.py`; a dos PDMs Modificados saiu.

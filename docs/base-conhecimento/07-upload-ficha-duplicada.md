# Upload de Ficha Duplicada (`upload_ficha_duplicada.py`)

## Propósito

Clona fichas técnicas completas (informações gerais, fornecedores, condições, características, documentos, imagens) de uma ficha base para uma ficha alvo, usando Selenium para scraping/injeção de dados com purga de características preservando CÓDIGO PMIB da base. Orquestra 3 fases: fila (GerenciadorFilaPMIB), extração base (ExtratorFichaBase), injeção alvo (InjetorFichaAlvo), atualização status.

## Entradas e Saídas

**Entradas:**
- Planilha `_STATUS_PMIB` (aba "Lista de Materiais"): CÓDIGO PMIB, PDM usado (marcador "DUPLICADA"), OBSERVAÇÕES (regex `\d{10}\.\d+` extracts PMIB base)
- Fichas base já preenchidas no portal PMIB (informações gerais, fornecedores, condições, características, documentos, imagens)
- Fichas alvo vazias no portal PMIB (mesmo código estrutura, sem dados)

**Saídas:**
- Fichas alvo clonadas com todos os dados da base: info gerais, 1+ fornecedores, 4 abas condições, características (preservado CÓDIGO PMIB base), documentos associados, imagens uploaded
- Planilha `_STATUS_PMIB` atualizada com status "COMPLETO" para fichas clonadas (colunas INFO. GERAIS, CONDIÇÕES, CARACT. TÉCNICAS etc.)

## Classes e Funções

### ⚠️ Quem identifica as duplicadas mudou (CP 6.2, 2026-08-17)

A tela (`ModuloCopiaFichas._worker_leitura_excel`) **não chama mais**
`GerenciadorFilaPMIB.montar_fila_processamento`. Quem monta a fila agora é
`sigft/services/duplicadas.py` (`localizar_duplicadas`). O robô continua sendo
o desta página — `ExtratorFichaBase` / `InjetorFichaAlvo`; o que mudou é só
quem decide **quais** fichas entram.

O que a troca corrige, e nada disso é teórico:

| Situação | `GerenciadorFilaPMIB` | `duplicadas.localizar_duplicadas` |
|---|---|---|
| Cabeçalho `PDMs usados` | acha **zero** fichas (só aceita `PDM USADO`/`PDM`) | acha |
| Cabeçalho em caixa mista | funciona (`.str.upper()` nas colunas) | funciona (`achar_coluna`) |
| Ficha sem original/sem material | **descartada em silêncio** | fica na lista, com o motivo no log |
| `OBSERVAÇÕES` sem código PMIB | descartada em silêncio | entra com aviso, editável em "Revisar" |
| Regra de identificação | substring do que a tela passar | prefixo `PDM.9900.000` |

A tela sempre passou `marcador_duplicada="PDM.9900.000"`, então o default
`"DUPLICADA"` documentado abaixo **nunca rodou em produção** — a comparação
real sempre foi com o código, por substring. A única divergência de resultado
é a linha em que o código não está no começo do texto; essas saem como aviso
no log em vez de sumirem.

`GerenciadorFilaPMIB` continua no código e sem uso pela tela, até a Fase 6
fechar.

---

### GerenciadorFilaPMIB
**`__init__(caminho_excel, nome_aba="Lista de Materiais")`**: Armazena caminho e nome da aba.

**`_encontrar_cabecalho(df, limite_linhas=15)`**: Busca dinâmico de linha com "CÓDIGO PMIB" nas primeiras 15 linhas.

**`montar_fila_processamento(marcador_duplicada="DUPLICADA")`**: Lê Excel, normaliza CÓDIGO PMIB (dtype=str, remove apóstrofos, força 4 casas decimais via regex `\d{10}\.\d{3}$`), varre linhas buscando coluna PDM usado contendo "DUPLICADA", extrai PMIB base de OBSERVAÇÕES via regex `(\d{10}\.\d+)`, monta fila com dicts {descricao, pmib_original, pmib_alvo}. Retorna tuple (sucesso bool, fila ou mensagem erro).

### ExtratorFichaBase
**`__init__(dir_download_temp="./temp_downloads")`**: Inicializa caminho download, limpa pasta anterior.

**`_preparar_pasta_temp()`**: Cria ou limpa diretório `dir_download_temp`.

**`iniciar_driver_silencioso()`**: Chrome com prefs download automático (bypass prompt, diretório pré-configurado).

**`_ler_input(xpath)`**: Lê valor de input/textarea via get_attribute("value").

**`_ler_tabela_outsystems(data_header)`**: Busca células com `[@data-header]`, extrai span com `[@data-expression]`, retorna lista de textos.

**`_esperar_download_e_renomear(nome_descritivo)`**: Aguarda arquivo cair em dir_download (10s max), pega mais recente, remove .crdownload, sanitiza nome (alfanuméricos + espaço), renomeia com extensão original.

**`_pesquisar_e_abrir(pmib)`**: Navega URL_lista, preenche campo pesquisa, Enter, espera linha + clica lápis JS, await 3s.

**`_ler_select_por_label(texto_label)`**: Xpath `//label[.../following::select[1]`, extrai first_selected_option.text.

**`_ler_info_gerais()`**: Lê 4 selects: Origem, Tipo, Unidade de medida, Tipo de fabricação.

**`_ler_condicoes()`**: Abre Conditions_Header via click, varre 4 abas (ARMAZENAMENTO/TRANSPORTE/MANUTENCAO/DESCARTE), lê 10+ inputs/textareas + 15+ booleanos (radios/checkboxes) via contains() XPaths (ignorando prefixo dinâmico), retorna dict por aba com valores brutos.

**`extrair_dados_ficha(pmib_original)`**: Orquestrador—abre ficha, raspa info_gerais, fornecedores (zip de Fabricante + Referência das tabelas), condições (dict 4 abas), documentos (lista de nomes), imagens (loop `TabelaImagens`, click download, rename, guarda caminho + descrição PT/ES). Retorna dict estruturado.

### InjetorFichaAlvo
**`__init__(driver, wait)`**: Recebe driver + WebDriverWait já instanciados (compartilhados com Extrator).

**`safe_click(locator)`**: Scroll + wait presence + JS click.

**`_clicar_salvar_visivel(nome_secao="")`**: Encontra todos botões SALVAR visible+enabled na tela, clica primeiro, sleep 2.5s.

**`_adicionar_fornecedores(fornecedores)`**: Abre dropdown VSComp (customizado), pesquisa fabricante, Enter, preenche referência, clica (+) fa-plus-circle, sleep 1 entre fornecedores.

**`_limpar_caracteristicas_tecnicas(pmib_original)`**: Clica aba Características Técnicas, loop paginação+linhas, se descrição = "CODIGO PMIB" injeta pmib_original via textarea send_keys, senão clica lixeira + CONFIRMAR, sleep 2 entre exclusões, salva aba.

**`_associar_documentos(documentos)`**: Loop documentos—clica (+) Associar, pesquisa nome, Enter, await 2s, marca checkbox coluna Selecionar (assume modal/tabela visível).

**`_upload_imagens(imagens)`**: Loop imagens—preenche Input_DescriptionES/PT, encontra input type="file" FilePond, send_keys(caminho_absoluto), sleep 3 await upload.

**`_preencher_info_gerais(info_gerais)`**: Chama `_escrever_select_por_label` para 4 campos, salva.

**`_escrever_select_por_label(texto_label, valor_desejado)`**: Xpath `//label[.../following::select[1]`, Select.select_by_visible_text.

**`_preencher_condicoes(condicoes_por_aba)`**: Abre Conditions_Header, para cada aba (TRANSPORTE/MANUTENCAO/DESCARTE clica div[3/4/5]), preenche inputs/checkboxes/radios (booleano = click se != esperado), procura botão SALVAR visible e clica, sleep 1.5s.

**`_pesquisar_e_abrir(pmib)`**: Busca/abre ficha alvo (mesmo que ExtratorFichaBase).

**`clonar_ficha(dados_colhidos)`**: Orquestrador principal—abre ficha alvo via `_pesquisar_e_abrir(pmib_alvo)`, executa em ordem: info_gerais, fornecedores, condições, características (purga), documentos, imagens. Retorna True.

### AtualizadorStatusPMIB
**`__init__(caminho_excel, nome_aba="Lista de Materiais")`**: Armazena caminho e aba.

**`_blindar_numero_pmib(valor_celula)`**: Se float/int, formata `.4f`; se string, remove apóstrofos/vírgulas, normaliza com ljust(4, '0') se `\d{10}\.\d{2}`.

**`atualizar_ficha_concluida(pmib_alvo, secoes_concluidas, callback_log=None)`**: Abre openpyxl, busca dinâmico colunas por nome (INFO. GERAIS, CONDIÇÕES, CARACT. TÉCNICAS, etc.), preenche com "COMPLETO" apenas seções com True em dicionário secoes_concluidas, retry loop se PermissionError (sleep 5s).

## Fluxo Detalhado

**Fase 1 - Montagem de Fila**:
1. GerenciadorFilaPMIB.montar_fila_processamento() lê _STATUS_PMIB
2. Varre coluna "PDM usado" procurando "DUPLICADA"
3. Para cada PMIB marcado: extrai PMIB base de OBSERVAÇÕES via regex
4. Monta fila com {descricao, pmib_original (base), pmib_alvo (cópia)}

**Fase 2 - Extração Base**:
1. ExtratorFichaBase.iniciar_driver_silencioso() prepara Chrome com download automático
2. Para cada ficha base em fila:
   - `_pesquisar_e_abrir(pmib_original)`: busca e abre ficha
   - `_ler_info_gerais()`: extrai 4 selects (Origem, Tipo, Unidade, Fabricação)
   - `_ler_tabela_outsystems("Fabricante")` + `"Referência"`: zip fornecedores
   - `_ler_condicoes()`: abre 4 abas, raspa inputs/textareas/radios/checkboxes via XPath contains()
   - `_ler_tabela_outsystems("Descrição")`: documentos
   - Loop `TabelaImagens` rows: extrai descrição, clica download, renomeia, guarda caminho
3. Retorna dict estruturado com 6 chaves (pmib, info_gerais, fornecedores[], condicoes{4 abas}, documentos_associados[], imagens_baixadas[])

**Fase 3 - Injeção Alvo**:
1. InjetorFichaAlvo recebe driver do Extrator (reutiliza sessão browser)
2. Para cada ficha alvo em fila com dados_colhidos:
   - `clonar_ficha()` orquestra:
     a. `_preencher_info_gerais()`: preenche 4 selects, salva
     b. `_adicionar_fornecedores()`: loop fornecedores, abre VSComp, pesquisa, preenche ref, clica (+)
     c. `_preencher_condicoes()`: abre cada aba, preenche todos campos (inputs/textareas/radios/checkboxes), salva cada aba
     d. `_limpar_caracteristicas_tecnicas(pmib_original)`: purga todas características EXCETO "CÓDIGO PMIB" que recebe pmib_original, salva
     e. `_associar_documentos()`: loop nomes, pesquisa em modal, marca checkbox
     f. `_upload_imagens()`: preenche descrições PT/ES, send_keys(caminho_absoluto) para input FilePond, await upload
3. Retorna True se completo

**Fase 4 - Atualização Status**:
1. AtualizadorStatusPMIB.atualizar_ficha_concluida(pmib_alvo, secoes_concluidas)
2. Abre openpyxl _STATUS_PMIB
3. Busca dinâmico colunas: "CÓDIGO PMIB", "INFO. GERAIS", "CONDIÇÕES", "CARACT. TÉCNICAS"
4. Encontra linha com pmib_alvo (blindagem .4f)
5. Marca "COMPLETO" para seções com True no dicionário (ex: {"INFO. GERAIS": True, "CONDIÇÕES": True, ...})
6. Retry loop se PermissionError (5s sleep)

## Integrações

- **Planilhas**: `_STATUS_PMIB` (entrada fila + atualização status)
- **Portal PMIB**: Duas sessões Selenium (Extrator scraping ficha base, Injetor preenche ficha alvo), mesmo browser instance reutilizado
- **Sistema de Arquivos**: Download automático imagens em dir_download_temp, paths absolutos passados para FilePond
- **Módulos relacionados**: Padrão similar ao módulo 1/2 (safe_click, retry, callbacks), mas sem IA (puramente RPA)

## Pontos de Atenção

- **Regex PMIB base em OBSERVAÇÕES crítico**: Linha 66 `r'(\d{10}\.\d+)'` extrai de texto livre; formato esperado não garantido = risco de PMIB_base inválido sem validação.
- **Blindagem numérica duplicada**: Ambos GerenciadorFilaPMIB (linhas 72-76) e AtualizadorStatusPMIB (_blindar_numero_pmib) implementam mesma lógica; duplicação de código.
- **VSComp customizado sem fallback**: Linha 419 assume dropdown classe "vscomp-toggle-button"; se site alterar para Selects nativas, linhas 421-426 falham (input_search = None).
- **FilePond input type="file"**: Linha 544 assume element existe; se UI remove/renomeia o input, send_keys(path) falha silenciosamente.
- **Download renomeação assume extensão**: Linha 160 `os.path.splitext()` preserva extensão; PDF/PNG/DOCX esperados; se site envia sem extensão, nome fica vazio.
- **XPaths contains() dinâmicos**: Condições (linhas 301-342) mapeiam 10+ IDs via contains() para ignorar prefixo; mudança HTML/ID quebra mapping inteiro.
- **Purga preserva CÓDIGO PMIB**: Linha 462 filtra por "CODIGO PMIB" ou "CÓDIGO PMIB" em descrição; se característica 1º do sistema usa label diferente, lógica falha.
- **Loop paginação sem fallback**: Linha 590 procura botão "aria-label='Ir para a página seguinte'"; se UI muda label/posição, paginação trava em página 1.
- **Docmente associação modal não explícito**: Linhas 506-527 assume modal abre e tabela recarrega com Enter; sem log se documento não encontrado.
- **Sleep fixos extensos**: 3s uploads FilePond (linha 551), 2.5s após save OutSystems (linha 397); sem retry automático se timeout.
- **Sem validação de integridade**: Não verifica se ficha alvo ficou realmente preenchida após injeção; assume Selenium + sleep = sucesso.
- **Cancel_requested não implementado**: Diferente de módulos 1/2, não há flag de parada; fila roda até fim ou exception.
- **Dependência Windows**: Sanitização nome arquivo (linha 163) apenas remove caracteres especiais; paths longos podem falhar em Windows.
- **PermissionError retry infinito**: Linha 752-753 loop enquanto arquivo aberto; usuário pode ficar preso sem timeout/fallback.

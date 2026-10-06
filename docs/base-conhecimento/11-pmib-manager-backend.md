# PMIB Manager Backend (`pmib_manager_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `pmib_manager_backend.py` | `sigft/services/pmib_manager.py` (serviço) · `sigft/app/views/pmib_manager.py` (tela) |
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## ⚠️ Tratamento v2 (desde 2026-10-05) — leia antes do resto

O roteiro `gestao-sobressalentes/07 - Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`
(T0–T3) mudou o papel do módulo. O texto mais abaixo descreve o fluxo antigo; o que vale hoje:

| Passo | O que mudou |
|---|---|
| 2. Buscar `_STATUS_PMIB` | `status_pmib_arquivos.listar()` ignora pastas de teste/obsoletas/cópias (`testes_autospec`, `00 - OBSOLETO`, `10- TESTES`, `DATASHEETS`, `BACKUP`; nomes com `~$`, `- Copy`, `CÓPIA`, `COMENT`, `RESPOSTA`) — **cada ignorado aparece no log com o motivo**. Dois vivos com o mesmo código: fica o modificado por último, com `[AVISO]`. Defeito que motivou: o link "Abrir Box" de `#ST00=B01BMU10&EPB020` apontava para a cópia de `testes_autospec/`. |
| 5. Ler cada `_STATUS_PMIB` | **Antes** de ler, `_atualizar_autorizacao()` recalcula e **grava** em cada linha a `SITUAÇÃO DA AUTORIZAÇÃO` e os `DIAS DE ATRASO` pela regra de `services/autorizacao.py` (15 dias úteis do e-mail; antes eram 14 corridos e só contados para a mapeadora). Só as células que mudaram, pelo editor cirúrgico (`StatusPMIB` → `core/excel/cirurgico.py`): comentários em thread e listas suspensas ficam. Grava o nome definido `sigft_calculado_em` (data do cálculo). Arquivo sem a coluna SITUAÇÃO (layout antigo) não é gravado — o log diz. Arquivo aberto no Excel: a tela pergunta, nomeando o arquivo; "Cancelar" pula só ele. Também lê a **revisão em uso** na linha de texto acima do cabeçalho. |
| `_calcula_fichas` | Só total de fichas e contagem por STATUS (PMIB distinto, sem DUPLICADO) — o que a cascata usa. Saíram as contagens que iam para a mapeadora e o bloco dos 14 dias / "Atualizar template". |
| 6. Gravar na mapeadora | A mapeadora virou **cadastro** (decisão do Luan, 05/10/2026): grava só `LINK DA PLANILHA`, a cascata da `SITUAÇÃO NO PMIB` (agora a função pura `situacao_no_pmib`) e a `REVISÃO EM USO` (lida do `_STATUS_PMIB`; quando é igual à ÚLTIMA REVISÃO EMITIDA, grava o valor de lá, com o mesmo tipo, para a formatação condicional G≠C não acender à toa). Nenhuma contagem. As contagens saem dos `_STATUS_PMIB` pelo Power BI v2. |
| `executar_fluxo(..., hoje=None)` | `hoje` injetável — o kit de teste roda com `hoje = 2026-10-10`. |

**Autorizações de entrega de Itaipu (T4)** — bloco novo na mesma tela: "4. Selecionar export de autorizados" +
"APLICAR AUTORIZAÇÕES" (`services/autorizados.py`, porte do `apto_para_entrega_att.py` que vivia no Box com os
caminhos fixos). Para cada PMIB do `sobressalentes_autorizados_AAAAMMDDhhmm.xlsx`, nos `_STATUS_PMIB` vivos da
Pasta Raiz (mesmas exclusões): v2 → SITUAÇÃO := AUTORIZADO e, se DIAS estiver vazio, o atraso até a data do
export (tirada do nome); layout antigo → APTO := SIM. Grava pelo editor cirúrgico; PMIB do export que não está em
nenhum arquivo aparece como `[AVISO]`.

A mapeadora continua gravada pelo openpyxl (não tem comentário em thread nem lista de extensão). Se passar a
ter, o passo 4 escreve um `[AVISO]` antes de gravar.

**Como validar**: `tests/test_pmib_manager_v2.py` roda o fluxo inteiro sobre o kit do cofre
(`gestao-sobressalentes/_gestao_v2/fixtures/kit_gestao_pmib/`) e o confere com `validar_kit_gestao_pmib.py`
(KIT OK). Na máquina com o Box: rodar uma vez e conferir, num `_STATUS_PMIB`, SITUAÇÃO e DIAS atualizados e o
comentário em thread intacto; na mapeadora, REVISÃO EM USO e SITUAÇÃO NO PMIB, e o link de
`#ST00=B01BMU10&EPB020` apontando para o arquivo real.

## Propósito
Orquestra o gerenciamento integrado de fichas técnicas PMIB: carrega base Aconex DocManager (histórico de revisões), busca arquivos `_STATUS_PMIB.xlsx`, renomeia por Tracking ID/Current, atualiza planilha mestra com inserção interativa, calcula indicadores de progresso por ficha, grava KPIs, cascata de situação PMIB e hyperlinks.

## Entradas e Saídas
- **Entradas**: 
  - Arquivo Aconex DocManager (histórico colunas: No. do Documento, Tracking ID, Current, Título, Especialidade, etc.)
  - Pasta raiz com arquivos `*_STATUS_PMIB.xlsx`
  - Planilha mestra gerenciadora (aba ativa com colunas: N° DOCUMENTO ITAIPU, DESCRIÇÃO, STATUS DA REVISÃO, etc.)
  - Callbacks: `callback_confirm` (seleção interativa de novos), `callback_retry_lock` (retry se planilha aberta)
- **Saídas**: 
  - Arquivos renomeados (código antigo → novo código Tracking ID)
  - Planilha mestra atualizada com: metadados (No. do Documento, Título, Revisão), indicadores (fichas por status), cascata SITUAÇÃO NO PMIB, hyperlinks para arquivos, índices percentuais
  - Logs de progresso (msgs, frações 0.05-1.0)

## Classes e Funções

### `copiar_estilo_seguro()` (linha 15-36)
Função auxiliar que copia propriedades visuais de célula origem para destino: font, border, fill, alignment, number_format, protection.

### `PMIBManager` (linha 41)
Gerenciador de PMIB.

- `__init__()`: inicialização vazia (helper puro)
- `_buscar_rdspp_mais_recente(codigo_arquivo_fisico, df_api)`: busca versão mais recente de um código no histórico DocManager (linha 46-66)
  - Procura código em 'No. do Documento'
  - Se encontra, extrai Tracking ID
  - Procura versão com mesmo Tracking ID e Current=True
  - Retorna novo 'No. do Documento' ou código original
- `_renomear_arquivo_status_pmib(caminho_original, new_codigo_rdspp)`: renomeia arquivo mantendo estrutura diretório (linha 68-84)
  - Extrai nome e extensão
  - Cria novo nome: `{new_codigo}_STATUS_PMIB{ext}`
  - Se mesmo nome (case-insensitive), retorna sem fazer nada
  - Move arquivo, retorna tupla `(sucesso, mensagem, novo_caminho)`
- `_ler_status_pmib(codigo_rdspp, link)`: lê arquivo STATUS PMIB e mapeia colunas desejadas (linha 86-136)
  - Mapeamento: CÓDIGO DO MATERIAL, CÓDIGO CMI, CÓDIGO PMIB, STATUS, INFO. GERAIS, CARACT. TÉCNICAS, DOCUMENTOS E IMAGENS, CONDIÇÕES, VALORIZAÇÃO, APLICAÇÃO - LMR, DATA DO EMAIL, EQUIPAMENTO ENTREGUE, APTO PARA ENTREGA
  - Procura dinamicamente header pela palavra "DESCRIÇÃO" (linhas 0-9)
  - Lê com dtype=str (previne corte de zeros em números)
  - Limpa nomes de coluna, normaliza para uppercase
  - Adiciona coluna RDS_PP com código
  - Retorna tupla `(df_lido, codigo_rdspp)` ou `(None, None)` se erro
- `_calcula_fichas(df, rdspp)`: calcula indicadores de progresso por ficha (linha 138-252)
  - Filtra CÓDIGO PMIB válido, remove duplicados (keep='first')
  - **Nova Regra (linha 144-146)**: expulsa linhas com STATUS='DUPLICADO'
  - Conta fichas únicas
  - Mapeia STATUS → chaves dict (fichas_com_fornecedor, fichas_em_elaboracao, etc.)
  - **Fichas Recebidas**: pelo menos 1 coluna de "INFO. GERAIS", "CARACT. TÉCNICAS", "DOCUMENTOS E IMAGENS", "CONDIÇÕES" = "COMPLETO"
  - **Fichas Completas Info Fornecedor**: TODAS as 4 colunas = "COMPLETO"
  - **Fichas com Valorização**: VALORIZAÇÃO = "COMPLETO"
  - **Fichas com LMR**: APLICAÇÃO - LMR = "COMPLETO"
  - **Equipamentos Entregue**: ENTREGUE (normalizado uppercase) = "SIM"
  - **Fichas Aptas para Entrega**: APTO PARA ENTREGA = "SIM" AND (ENTREGUE != "SIM" ou não existe)
  - **Atraso Itaipu**: DATA INFORME + 14 dias < hoje AND APTO PARA ENTREGA != "SIM" AND ENTREGUE != "SIM"
  - Retorna dict: `{RDS_PP, total_fichas, fichas_com_fornecedor, fichas_em_analise_ib, fichas_em_correcao, fichas_aprovadas, fichas_recebidas, fichas_completas_info_fornecedor, fichas_com_valorizacao, fichas_com_aplicacao_lmr, equipamentos_entregue, fichas_aptas_para_entrega, atraso_autorizacao_itaipu}`
- `executar_fluxo(caminho_api, pasta_raiz_status, caminho_gerenciadora, callback_confirm, callback_retry_lock)`: orquestrador principal, generator (linha 255-592)

## Fluxo detalhado (6 etapas)

### Etapa 1: Carregar Base DocManager (yield 0.05)
- Lê arquivo Aconex com colunas: No. do Documento, Tracking ID, Current, Título, Revisão, Status, Data de Alteração, Especialidade, Subespecialidade
- Normaliza coluna 'Current' para boolean (string 'true' → True)
- Se coluna 'Current' não existe, interrompe com erro
- Retorna df_api

### Etapa 2: Buscar Arquivos _STATUS_PMIB (yield 0.15)
- os.walk recursivo em pasta_raiz_status
- Procura arquivos `*_status_pmib.xlsx` ou `*_status_pmib.xls` (case-insensitive)
- Extrai código do arquivo: `file.rsplit("_STATUS_PMIB", 1)[0]`
- Constrói lista: `(codigo_documento, caminho_completo)`
- Se nenhum encontrado, aviso e retorna

### Etapa 3: Renomeação por Tracking ID/Current (yield 0.25)
- Para cada arquivo encontrado:
  - Chama `_buscar_rdspp_mais_recente(codigo_antigo, df_api)`
  - Se código mudou, chama `_renomear_arquivo_status_pmib()`
  - Registra em dict: `codigos_renomeados[codigo_antigo] = (novo_codigo, caminho_atualizado)`
  - Yields mensagens de renomeação

### Etapa 4: Atualizar Planilha Mestra (yield 0.45)
- Carrega workbook mestra (aba ativa)
- Cria mapeamento de colunas (linha 312-321): N° DOCUMENTO ITAIPU ↔ No. do Documento, etc.
- **Substep A (linha 332-341)**: mapeia códigos existentes → tracking_ids_existentes
- **Substep B (linha 343-352)**: identifica novos candidatos
  - Filtra vigentes (Current=True)
  - Contém 'SOBRESSALENTES' no Título
  - Não contém 'PREÇOS' ou 'PREÇO'
  - Não termina com '-01'
  - Tracking ID não está em tracking_ids_existentes
- **Substep C (linha 354-381)**: inserção interativa
  - Callback `callback_confirm(df_reais_novos)` retorna DataFrame selecionado
  - Para cada linha selecionada:
    - Adiciona nova linha na mestra
    - Copia estilo da linha molde (anterior)
    - Preenche No. do Documento e Título
  - Yields mensagem com contagem inserida
- **Substep D (linha 383-417)**: atualiza metadados de linhas existentes
  - Para cada linha mestra (a partir de 3):
    - Busca código atual via `_buscar_rdspp_mais_recente()`
    - Se mudou, atualiza coluna No. do Documento
    - Procura dados reais em df_api (Current=True)
    - Preenche colunas mapeadas (Título, Revisão, Status, etc.)
  - Salva com laço de retry: se PermissionError (planilha aberta), callback `callback_retry_lock()` decide prosseguir ou cancelar (linha 406-415)

### Etapa 5: Calcular Indicadores (yield 0.75)
- Para cada código em codigos_renomeados:
  - Se arquivo existe:
    - Chama `_ler_status_pmib(codigo_atual, caminho_arquivo)`
    - Se leitura sucede, chama `_calcula_fichas(df_fichas, rdspp_lido)`
    - Salva resultado em dict com caminho absoluto
  - Ignora arquivos ~$ (temporários)

### Etapa 6: Gravar Indicadores na Mestra (yield 0.90)
- Recarrega workbook mestra
- Mapeia colunas target (linha 444-459): FICHAS EXISTENTES ↔ total_fichas, FICHAS RECEBIDAS ↔ fichas_recebidas, etc.
- Para cada linha mestra (a partir de 3):
  - Busca dados em resultados_por_rdspp por No. do Documento
  - **Coluna Link**: se caminho existe, cria hyperlink relativo com texto "Abrir Box" (linhas 484-498)
  - **Outras colunas**: preenche com valor numérico (0 se não existe)
  - **Índices Percentuais** (linhas 502-521):
    - Índice Emissão: `((fichas_em_analise_ib + fichas_em_correcao) / total) * 100`
    - Índice Conclusão: `(fichas_aprovadas / total) * 100`
    - Se total=0, ambos = "0.00%"
  - **Cascata SITUAÇÃO NO PMIB** (linhas 523-570):
    - Fallback: "EM ANDAMENTO"
    - Se STATUS DA REVISÃO = "LISTA NÃO EMITIDA" → "LISTA NÃO EMITIDA"
    - Se STATUS = "SEM LISTA" → "SEM LISTA"
    - Se total=0 → "INICIAR"
    - Se ini>0 → "CRIAÇÃO DAS FICHAS EM PROCESSO"
    - Se corr>0 AND elab>0 → "CORREÇÃO / ELABORAÇÃO"
    - Se corr>0 AND aprov>0 → "EM CORREÇÃO / FINALIZADO"
    - Se corr=total → "EM CORREÇÃO"
    - Se analise>0 AND elab>0 → "EM PROCESSO / ANÁLISE ITAIPU"
    - Se analise=total → "EM ANÁLISE ITAIPU"
    - Se forn>0 AND elab>0 → "FORNECEDOR / ELABORAÇÃO"
    - Se elab>0 → "EM PROCESSO DE PREENCHIMENTO"
    - Se forn=total → "FICHAS COM O FORNECEDOR"
    - Se (aprov+na)=total AND total>0 → "FINALIZADO"
    - Se cria>0 e nenhum avançou → "FICHAS CRIADAS"
  - Salva com laço de retry (callback_retry_lock)

## Integrações
- **Planilhas**: Aconex DocManager (histórico), `*_STATUS_PMIB.xlsx` (fichas por material), planilha mestra gerenciadora
- **Frontend**: callbacks para seleção interativa (callback_confirm), tratamento de lock de arquivo (callback_retry_lock)
- **Saída**: arquivos renomeados no filesystem, mestra atualizada em Excel

## Pontos de atenção
- Generator yields tuplas `(msg, progresso_fração)` ou strings; frontend deve iterar com next() ou for (linha 262, 439, 592)
- Callback `callback_confirm()` recebe DataFrame inteiro e retorna subset selecionado pelo usuário — implementação UI é responsabilidade do frontend
- Callback `callback_retry_lock()` retorna bool: True=repetir, False=cancelar; se cancelar, yield erro e retorna (linha 411-415)
- Mapeamento de colunas é case-sensitive nos nomes da mestra — colunas renomeadas quebram integração (linha 312-321)
- Novo código buscado em DocManager via fuzzy Tracking ID; se Tracking ID não existe, retorna código antigo (linha 58-66)
- Renomeação cria novo caminho via shutil.move — se destino já existe, levanta exceção (linha 80)
- Leitura _STATUS_PMIB procura header dinamicamente por "DESCRIÇÃO" nas linhas 0-9 (linha 61-70); se header após linha 9, falha silenciosamente
- dtype=str em read_excel previne truncamento de zeros, mas converte tudo para string; parsing posterior necessário (linha 76, 214)
- Normalização de 'Current' assume string 'true' lowercase — outros valores (True, TRUE, 1) não são capturados (linha 266)
- Status_revisao é normalizado uppercase (linha 527), mas valores na mestra podem ter case misto — comparação segura (linha 540-542)
- ~~Atraso_autorizacao_itaipu (14 dias corridos)~~ — saiu em 2026-10-05; a regra (15 dias úteis) é `services/autorizacao.py`, gravada linha a linha no `_STATUS_PMIB`
- Hyperlink é relativo ao diretório da mestra — se arquivos STATUS_PMIB se movem após criação do link, links quebram (linha 488)
- SITUAÇÃO NO PMIB é cascata com regras em ordem; primeira condição True define resultado — ordem importa (linha 540-569)
- Se nenhum arquivo processado, yield aviso e retorna sem atualizar mestra (linha 590)

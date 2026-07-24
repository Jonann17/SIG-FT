# PMIB Manager Backend (`pmib_manager_backend.py`)

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
- Atraso_autorizacao_itaipu requer coluna 'DATA INFORME' válida como data; erros de parse em coerce='coerce' resultam em NaT (linha 226)
- Hyperlink é relativo ao diretório da mestra — se arquivos STATUS_PMIB se movem após criação do link, links quebram (linha 488)
- SITUAÇÃO NO PMIB é cascata com regras em ordem; primeira condição True define resultado — ordem importa (linha 540-569)
- Se nenhum arquivo processado, yield aviso e retorna sem atualizar mestra (linha 590)

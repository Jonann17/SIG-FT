# Frontend (`frontend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `frontend.py` | `sigft/app/views/*.py`, `sigft/app/widgets/`, `sigft/app/theme.py` |
>
> Cada tela virou um arquivo próprio no CP 7.3 (ex.: `ModuloCriaFichas` em `sigft/app/views/cria_fichas.py`, `ModuloAnalyzer` em `sigft/app/views/analyzer.py`, `ModuloUploadConditions` em `sigft/app/views/upload_conditions.py`, etc.). O arquivo `frontend.py` continua como ponto de entrada compatível (92 linhas). Todos os widgets compartilhados estão em `sigft/app/widgets/` (console.py, dialogs.py, espera.py, module_frame.py, pickers.py).
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## Propósito

O módulo frontend implementa a interface gráfica desktop (CustomTkinter) do SIG-FT. Gerencia a navegação entre 12 módulos de tela especializados, o carregamento dinâmico de backends pesados via importlib durante a SplashScreen inicial, e a comunicação entre UI e lógica de negócio através de um padrão controller/getter para chaves API e callbacks de thread.

## Entradas e Saídas

- **Entradas**: Arquivos Excel (*.xlsx) selecionados via `filedialog`; credenciais de API (variáveis de ambiente `.env` + `api_config.json`); entrada do usuário via widgets (text fields, checkboxes, radio buttons, treeviews)
- **Saídas**: Arquivos Excel modificados (via `DataManager.atualizar_excel_final`); portal PMIB (via Selenium via `AutomacaoPMIB`); logs em console CTkTextbox; arquivos de fichas técnicas gerados em pastas de destino

## Classes e Funções

### Splash Screen e Inicialização

**`SplashScreen(ctk.CTk)`** — Tela modal de carregamento exibida antes da app principal.
- `__init__()` — Cria janela 500x350, centralizada, sem frame de título.
- `carregar_modulos()` — Thread que importa dinamicamente 11 backends (`cria_fichas_no_pmib_v1_backend`, `pdm_backend`, `analyzer_backend`, etc.) e atualiza a barra de progresso. Usa `importlib.import_module()` para evitar imports bloqueantes no startup. Ao fim, instancia `SIG_FT_App` e fecha a splash.

**`SIG_FT_App(ctk.CTk)`** — Janela principal (1280x850) com sidebar + container dinâmico.
- `__init__()` — Carrega logo/ícone, inicializa gestão de chaves API, cria sidebar com 12 botões de menu organizados em 3 seções (Início, Dados Técnicos, Gestão), instancia todos os frames em `self.frames` dict. **[2026-09-25]** No fim, chama `atualizacao.verificar_na_abertura(self)`: numa thread, pergunta ao GitHub se há Release mais novo que `_build_info.VERSAO` e, havendo, abre o aviso modal `JanelaAtualizacao` (o que mudou, "Atualizar agora" / "Agora não"). Só no app empacotado, instalado pelo instalador e com token; falha de rede ou de token vai só para o `sigft.log`. O botão **"Atualizações"** da barra da Home (`HomeView.procurar_atualizacoes`) faz a mesma pergunta e sempre responde. Código em `sigft/app/atualizacao.py` (tela) e `sigft/services/updater.py` (consulta, download, instalador).
- `fechar()` — **[2026-09-25]** O "X" da janela principal (`WM_DELETE_WINDOW`). Fechar a janela ENCERRA o processo: quando o laço de eventos acaba, `main()` chama `instancia.encerrar(0)` (`os._exit`), com ou sem thread presa. Havendo tarefa em andamento (thread comum viva: robô, tradução, consulta à IA — ver `instancia.tarefas_em_andamento`), pergunta antes, porque ela é interrompida no ponto em que está. Antes, um robô parado numa pausa mantinha o `SIG-FT.exe` vivo e sem janela, e esse fantasma travava o instalador. **Thread de fundo que não é tarefa da pessoa tem de ser `daemon=True`**, senão o "X" pergunta à toa. Se a própria janela não montar, `SplashScreen.iniciar_app_principal` mostra o erro (com o caminho do `sigft.log`) e encerra, em vez de sobrar uma janela invisível.
- `load_keys()` — Lê variáveis de ambiente (API_GEMINI_LUAN_GMAIL, GOOGLE_SEARCH_API, GOOGLE_CSE_API, LLAMA_CLOUD_API) e carrega/mescla com `api_config.json` persistido.
- `save_keys(new_keys)` — Persiste chaves em `api_config.json`.
- `get_key(key_id)` — Retorna chave por ID; usado por módulos via `self.controller.get_key("GEMINI")`.
- `show_frame(name)` — Método de navegação: esconde todos os frames com `grid_forget()` e exibe o frame nomeado.
- `_criar_botao_menu(parent, text, frame_name, row)` — Helper que cria botão de menu transparente com hover na cor primária.
- `_criar_label_secao(parent, text, row)` — Helper que cria label de seção (discreto, pequeno).

**`HomeView(ctk.CTkScrollableFrame)`** — Dashboard de boas-vindas e resumo visual do fluxo.
- Exibe cards com descrição de cada módulo, incluindo ícones, inputs esperados e outputs produzidos.
- Método auxiliar `criar_texto_simples(texto, row)` — Insere label de texto livre em linha específica do scroll frame.

### Janelas Auxiliares (Pop-ups Modais)

**`JanelaSelecao(ctk.CTkToplevel)`** — Permite multi-seleção de linhas de DataFrame via Treeview.
- `__init__(parent, dataframe, callback_confirmar)` — Renderiza tabela com scrollbars; aceita seleção múltipla (`selectmode="extended"`).
- Botão "Confirmar Seleção" chama `callback_confirmar(lista_de_indices)` e fecha a janela.

**`JanelaResumo(ctk.CTkToplevel)`** — Visualização read-only de resultados finais (1000x500).
- Coluna fixa: "Descrição Original", "PMIB Criado", "PDM (IA)", "PDM (Portal Final)".
- Sem edição; apenas para inspeção visual.

**`JanelaRevisaoPDM(ctk.CTkToplevel)`** — Pré-automação: revisar PDMs sugeridos pela IA antes do robô.
- `editar_pdm()` — Permite duplo-clique para editar campo "PDM Escolhido" de linhas selecionadas.
- `confirmar()` — Callback que passa DataFrame atualizado de volta para a tela pai.

**`JanelaAcaoRobo(ctk.CTkToplevel)`** — Modal de intervenção quando robô Selenium encontra erro.
- Apresenta 4 opções: [0] Retry, [1] Skip, [2] Change PDM + Retry, [3] Stop Automation.
- `_responder(acao)` — Grava escolha em `self.escolha` e destrói janela (desbloqueando thread waitando).
- `_mudar_pdm()` — Valida entrada do entry_pdm antes de marcar como CHANGE_PDM.

**`JanelaSelecaoDuplicadas(ctk.CTkToplevel)`** — Seleciona subset de fichas duplicadas para cópia.
- Pré-seleciona todas por padrão; Treeview com 3 colunas: Descrição, PMIB Original, PMIB Alvo.

**`JanelaRevisaoEdicao(ctk.CTkToplevel)`** — Edição manual de códigos PMIB Original/Alvo pós-regex.
- Duplo-clique em linha → abre pop-up com dois Entry fields.
- Alterações afetam diretamente a lista de fila em memória.

### Módulos de Tela (Frames)

Cada módulo herda de `ctk.CTkFrame` e segue padrão: `__init__(parent, controller)` → `_build_ui()` → `log(msg)` método auxiliar.

| Nº | Classe | Nó de Menu | Backend Usado | Descrição |
|---|---|---|---|---|
| 1 | `ModuloCriaFichas` | "1. Cria Fichas PMIB" | `cria_fichas_no_pmib_v1_backend` | Carrega Excel, chama IA (Gemini) para classificar PDMs, robô Selenium para preencher portal PMIB |
| 2 | `ModuloPDM` | "2. Planilhas PMIB" | `pdm_backend` | Fatia lista geral de PDMs, formata, cria fichas a partir de template |
| 3 | `ModuloAnalyzer` | "3. Analyzer (IA)" | `analyzer_backend` | Valida e pontua fichas técnicas via Gemini com pesos customizáveis |
| 4 | `ModuloUploadConditions` | "4.1. Upload Condições" | `upload_conditions_backend` | Upload de condições técnicas ao portal |
| 5 | `ModuloTranslator` | "4.2. Tradutor" | `translator_backend` | Tradução automática de especificações técnicas |
| 6 | `ModuloUploadTechSpecs` | "4.3. Upload Specs" | `upload_tech_specs_backend` | Upload de especificações técnicas ao portal |
| 7 | `ModuloCopiaFichas` | "5. Upload duplicadas" | `upload_ficha_duplicada` | Cópia em massa de fichas já criadas (leitura de original → escrita em alvo) |
| 8 | `ModuloAutoSpec` | "6. AutoSpec AI (RAG)" | `autospec_backend` | Geração automática de specs via RAG (Retrieval-Augmented Generation) |
| 9 | `ModuloLMR` | "7.1. LMR (Upload)" | `lmr_backend` | Upload e gestão de Lista de Materiais para Reposição (LMR) |
| 10 | `ModuloApagarLMR` | "7.2. Apagar LMR" | `apagar_lmr_backend` | Limpeza/exclusão de entradas LMR |
| 11 | `ModuloPMIBManager` | "8. PMIB Manager" | `pmib_manager_backend` | Gerenciamento geral de fichas PMIB (busca, edição em massa) |
| 12 | `ModuloBuscaPMIB` | "9. Search" | `search_pmib_backend` | Busca avançada no portal PMIB |

**Detalhes de ModuloCriaFichas** (principal):

Estrutura com 2 abas:
- **Aba 1: Criação de Fichas**
  - Seção 1: Código do Projeto (entry), Arquivo STATUS_PMIB (botão), Checkbox "Pular IA", Seleção de arquivo PDMs
  - Seção 2: Botões "Analisar (IA)", "Robô Web", "Ver Resumo", "Salvar no Excel", "Limpar"
  - Console de log no rodapé (tkinter Textbox, modo não-editável)

- **Aba 2: Editar código do projeto**
  - Novo Código do Projeto (entry)
  - Seleção de Excel com PMIB preenchido
  - Botão "Iniciar Robô de Edição"

Fluxo principal de criação:
1. Usuário seleciona Excel STATUS_PMIB com coluna "DESCRIÇÃO"
2. `DataManager.carregar_planilha_inteligente(arquivo, "Lista de Materiais", ["DESCRIÇÃO", "CÓDIGO PMIB"])` → auto-detecção de cabeçalho e extração de código de projeto da linha anterior ao "ITEM"
3. `JanelaSelecao` abre para multi-seleção de itens
4. Clique "Analisar (IA)":
   - `_ai_worker()` thread chama `GeminiCategorizer.processar_lote()` (ou pula IA se checkbox marcado)
   - Retorna JSON com PDM, descrição curta, origem, tipo, unidade, fabricação
   - `JanelaRevisaoPDM` abre para revisar/editar PDMs antes da automação
5. Clique "Robô Web":
   - `_bot_worker()` thread instancia `AutomacaoPMIB`, abre Chrome, tira login manual do usuário
   - Para cada item: `processar_item_individual()` preenche form completo via Selenium (TABs, active_element, Keys)
   - Captura PMIB criado e PDM final do portal
   - Se erro: `JanelaAcaoRobo` permite retry/change PDM/skip/stop
6. Clique "Salvar no Excel":
   - `DataManager.atualizar_excel_final(filepath, aba, lista_resultados)` encontra cabeçalho, localiza colunas "DESCRIÇÃO", "CÓDIGO PMIB", "PDM usado", escreve resultados
   - Loop askretrycancel se arquivo aberto

## Fluxo Detalhado

### Inicialização da App (frontend.py main)

1. Script principal (`if __name__ == "__main__"`) cria `SplashScreen()` e entra em `mainloop()`
2. SplashScreen inicia thread `carregar_modulos()`:
   - Itera sobre lista de 11 backends: `cria_fichas_no_pmib_v1_backend`, `pdm_backend`, etc.
   - Para cada um: chama `importlib.import_module(module_name)`, atribui variável global, atualiza label e progress bar
   - Ao fim: cria instância de `SIG_FT_App()`, destrói splash, passa controle a SIG_FT_App.mainloop()
3. `SIG_FT_App.__init__()`:
   - Carrega logo de `assets/logo.png` (caminho absoluto via `os.path.dirname(__file__)`)
   - Chama `load_keys()` → lê .env e `api_config.json`
   - Cria sidebar com 17 linhas de botões (12 módulos + Home + 2 labels de seção)
   - Instancia todos os 12 frames (+ HomeView) no dict `self.frames`
   - Chama `show_frame("Home")` → primeiro frame visível é HomeView

### Fluxo de Navegação (Clique Botão Menu)

1. Usuário clica botão "1. Cria Fichas PMIB" na sidebar
2. Botão chamou `self.show_frame("CriaFichas")` via lambda
3. `show_frame()` faz `grid_forget()` em todos os frames, depois `grid()` no frame nomeado
4. ModuloCriaFichas fica visível, pronto para interação

### Fluxo de Threading (Exemplo: IA)

1. Usuário clica "Analisar (IA)" em ModuloCriaFichas
2. `run_ai_thread()` inicia thread: `threading.Thread(target=self._ai_worker).start()`
3. `_ai_worker()` roda em thread secundária:
   - Chama `GeminiCategorizer(api_key).processar_lote(df, lista_pdms, instrucoes)` → chamada síncrona à Gemini API
   - Atualiza UI via `self.after(0, lambda: ...)` para garantir thread-safety do Tkinter
   - Ao fim, abre `JanelaRevisaoPDM` (também via `self.after()` para não quebrar no Tkinter)
4. Variáveis de estado (self.df_processed) são atualizadas no escopo da classe

### Fluxo de Robô Selenium (Exemplo: Criação de Ficha)

1. Usuário clica "Robô Web" após revisar PDMs
2. `run_automation_thread()` → `_bot_worker()` roda em thread:
   - Instancia `AutomacaoPMIB()`, chama `iniciar_driver()` → chrome headless ou full
   - Abre URL: `https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList`
   - `messagebox.showinfo()` pede login manual (bloqueia thread, usuário faz login, clica OK)
   - Loop iterativo sobre `self.df_processed`:
     - Chama `self.bot.processar_item_individual(row_atual)` → lógica principal no backend
     - Se sucesso: adiciona tupla `(descricao, pmib, pdm_final)` à lista `sucessos`
     - Se erro: abre `JanelaAcaoRobo()`, espera `janela.escolha`:
       - RETRY: continua loop while (retry=True)
       - CHANGE_PDM: modifica `row_atual['pdm_escolhido']`, continua loop
       - SKIP: pula para próximo item, tenta resetar portal
       - STOP: quebra loop principal, interrompe automação
   - Ao fim: monta DataFrame resumo via `pd.merge(self.df_processed, df_selenium, on='descricao_original')`
   - Abre `JanelaResumo()`

## Integrações

- **Planilhas**: Lê aba "Lista de Materiais" ou índice 0 de STATUS_PMIB, "PDMs" e "Instruções PDMs" de arquivo PDM para IA
- **Módulos internos**:
  - `ModuloCriaFichas` → `DataManager`, `GeminiCategorizer`, `AutomacaoPMIB` (de `cria_fichas_no_pmib_v1_backend`)
  - `ModuloPDM` → `pdm_backend` (processamento, formatação, criação de fichas)
  - `ModuloAnalyzer` → `analyzer_backend` (pontuação via IA)
  - `ModuloUploadConditions` → `upload_conditions_backend`
  - `ModuloTranslator` → `translator_backend`
  - `ModuloUploadTechSpecs` → `upload_tech_specs_backend`
  - `ModuloCopiaFichas` → `upload_ficha_duplicada`
  - `ModuloAutoSpec` → `autospec_backend`
  - `ModuloLMR` → `lmr_backend`
  - `ModuloApagarLMR` → `apagar_lmr_backend`
  - `ModuloPMIBManager` → `pmib_manager_backend`
  - `ModuloBuscaPMIB` → `search_pmib_backend`
- **Portal PMIB**: RPA via Selenium (ChromeDriver) para automação de formulários; uso extensivo de XPaths e `active_element` (Tab navigation)
- **APIs Externas**: Gemini (Google AI); chaves gerenciadas via `controller.get_key()`

## Pontos de Atenção

- **Threading + Tkinter**: Todos os atualizamentos de UI de threads secundárias usam `self.after(0, lambda: ...)`. Sem isso, causam travamentos ou crashes.
- **Console/Log repetido**: Múltiplos módulos (Analyzer, PDM, CriaFichas, etc.) implementam método `log(txt)` que insere em CTkTextbox. Padrão duplicado — candidato a classe base abstrata.
- **Botões "Parar/Cancelar"**: ModuloCriaFichas possui `btn_reset` gigante. Outros módulos não têm cancel explícito — apenas interrupção thread (encerrando driver ou break de loop).
- **Janelas de pausa por login**: `messagebox.showinfo()` bloqueia thread em `_bot_worker()` enquanto usuário faz login manual no portal. Funciona, mas travará UI durante pausa.
- **Seleção de arquivos**: `filedialog.askopenfilename()` e `filedialog.askdirectory()` chamados de thread principal (seguro); algumas telas abrem em thread (risco menor).
- **Sleeps fixos em Selenium**: `time.sleep(1.5)`, `time.sleep(5)`, `time.sleep(0.5)` espalhados em `processar_item_individual()` para aguardar renderização OutSystems. Frágeis a latência variável; melhor usar `WebDriverWait + EC.presence_of_element_located()`.
- **Except silencioso**: Alguns modelos (ex: `_bot_worker` try/finally) captura exceção ampla sem log de stack trace — dificulta debug.
- **Estado global de backends**: Variáveis globais `DataManager`, `GeminiCategorizer`, `AutomacaoPMIB`, etc. inicialmente `None`, preenchidas dinamicamente em SplashScreen. Risco: se reload da tela acontecer antes de SplashScreen terminar, NameError.
- **API Keys em .env**: Variáveis como `API_GEMINI_LUAN_GMAIL` hardcoded no código; mudança de nome exige refator. Melhor usar arquivo .env centralizado com chaves genéricas.
- **Importlib na SplashScreen**: Módulos importados com `importlib.import_module()`, não `import direto`. Permite reload, mas sem validação se módulo existe — falha silenciosamente durante splash se backend renomeado.
- **Dataframe merge em resume**: `pd.merge(self.df_processed, df_selenium, on='descricao_original', how='inner')` assume coluna idêntica em ambos DFs; mismatch causa perda de dados.
- **Windows only**: ChromeDriver hardcoded; código específico para OutSystems portal (XPaths frágeis se portal mudar).


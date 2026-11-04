# Frontend (`frontend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-10-15)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `frontend.py` | `sigft/app_qt/main.py` (janela, splash, registro `TELAS`), `sigft/app_qt/views/*.py`, `sigft/app_qt/widgets/`, `sigft/app/theme.py` |
>
> Cada tela virou um arquivo próprio no CP 7.3 (ex.: `ModuloCriaFichas` em `sigft/app_qt/views/cria_fichas.py`, `ModuloAnalyzer` em `sigft/app_qt/views/analyzer.py`, `ModuloUploadConditions` em `sigft/app_qt/views/upload_conditions.py`, etc.). O arquivo `frontend.py` é só o lançador da interface Qt. Os widgets compartilhados estão em `sigft/app_qt/widgets/` (console.py, dialogs.py, espera.py, module_frame.py, pickers.py, blocos.py). A interface CustomTkinter, que este texto descreve, saiu do SIG-FT em 2026-10-15; a Qt é a porta dela, com o mesmo comportamento.
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## Propósito

O módulo frontend implementa a interface gráfica desktop do SIG-FT (hoje em Qt/PySide6; quando este texto foi escrito, CustomTkinter). Gerencia a navegação entre 12 módulos de tela especializados, o carregamento dinâmico de backends pesados via importlib durante a SplashScreen inicial, e a comunicação entre UI e lógica de negócio através de um padrão controller/getter para chaves API e callbacks de thread.

## Entradas e Saídas

- **Entradas**: Arquivos Excel (*.xlsx) selecionados via `filedialog`; credenciais de API (variáveis de ambiente `.env` + `api_config.json`); entrada do usuário via widgets (text fields, checkboxes, radio buttons, treeviews)
- **Saídas**: Arquivos Excel modificados (via `DataManager.atualizar_excel_final`); portal PMIB (via Selenium via `AutomacaoPMIB`); logs em console CTkTextbox; arquivos de fichas técnicas gerados em pastas de destino

## Classes e Funções

### Splash Screen e Inicialização

**`SplashScreen(ctk.CTk)`** — Tela modal de carregamento exibida antes da app principal.
- `__init__()` — Cria janela 500x350, centralizada, sem frame de título.
- `carregar_modulos()` — Thread que importa dinamicamente 11 backends (`cria_fichas_no_pmib_v1_backend`, `pdm_backend`, `analyzer_backend`, etc.) e atualiza a barra de progresso. Usa `importlib.import_module()` para evitar imports bloqueantes no startup. Ao fim, instancia `SIG_FT_App` e fecha a splash.

**`SIG_FT_App(ctk.CTk)`** — Janela principal (1280x850) com sidebar + container dinâmico.
- `__init__()` — Carrega logo/ícone, inicializa gestão de chaves API, cria sidebar com 12 botões de menu organizados em 3 seções (Início, Dados Técnicos, Gestão), instancia todos os frames em `self.frames` dict. **[2026-09-25]** No fim, chama `atualizacao.verificar_na_abertura(self)`: numa thread, pergunta ao GitHub se há Release mais novo que `_build_info.VERSAO` e, havendo, abre o aviso modal `JanelaAtualizacao` (o que mudou, "Atualizar agora" / "Agora não"). Só no app empacotado, instalado pelo instalador e com token; falha de rede ou de token vai só para o `sigft.log`. O botão **"Atualizações"** da barra da Home (`HomeView.procurar_atualizacoes`) faz a mesma pergunta e sempre responde. Código em `sigft/app/atualizacao.py` (tela) e `sigft/services/updater.py` (consulta, download, instalador). **[2026-10-27]** "Atualizar agora" tenta primeiro a atualização por arquivos (`updater.pode_por_arquivos` / `aplicar_por_arquivos`: pasta do programa gravável, o próprio app troca os arquivos, se reabre com `updater.reabrir` e fecha); qualquer falha cai no instalador, que agora só fecha o app depois de avisar que subiu (`/SINAL`; senão `InstaladorNaoIniciou`, e o app fica aberto com o erro). Ver `docs/BUILD.md`, "Atualização por arquivos e o `/SINAL`".
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
| 11 | `ModuloPMIBManager` | "8. PMIB Manager" | `pmib_manager_backend` | Gerenciamento geral de fichas PMIB (busca, edição em massa). Desde 2026-10-27 o menu abre a seção `ModuloGestaoSobressalentes` (`views/gestao_sobressalentes.py`), com as abas Gestão PMIB (esta tela), Conferência de Revisões e Revisão no AMP: ver `14-aconex-e-conferencia-de-revisoes.md` |
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

## Sistema visual (2026-10-20)

A interface Qt (`sigft/app_qt/`) tem um sistema visual próprio; a spec está em
`docs/superpowers/specs/2026-10-20-sistema-visual-design.md`.

- **Tokens** (`sigft/app/tokens.py`): as paletas `ESCURO` e `CLARO` (papéis
  `fundo`, `superficie`, `superficie_alta`, `borda`, `texto`, `texto_suave`,
  `marca`, `primaria`, `perigo`, `aviso`, `info`...), `FONTE`, `ESPACO`, `RAIO` e
  `contraste()`. Texto sobre fundo tem contraste de pelo menos 4,5:1, e há teste que mede.
  `theme.COLORS` é derivado deles.
- **Folha de estilo** (`sigft/app_qt/estilo.py`): `folha_de_estilo(tema)` monta
  a folha do app a partir dos tokens; sem argumento vale `estilo.TEMA_ATUAL`.
  Cor só entra por **papel** (`definir_papel`) ou **variante** de botão
  (`primario`, `secundario`, `perigo`, `fantasma`), nunca hexadecimal na tela:
  `tests/test_qt_sem_cor_crua.py` acusa.
- **Ícones** (`sigft/app_qt/icones.py`, SVG Lucide em `assets/icons`, licença ISC):
  `icones.aplicar(botao, nome)` desenha na cor do tema; `icones.reaplicar(raiz)`
  repinta a árvore na troca de tema. Botão não leva emoji
  (há teste).
- **Tema** (`sigft/app_qt/tema.py`): escuro / claro / sistema, escolhido no
  seletor da Configuração (Aparência) e guardado nas preferências (`core/prefs.ler_preferencia`).
  `tema.aplicar` troca a folha do app, repinta os ícones e emite `tema.mudou`.
  Widget que guarde cor calculada na criação precisa ouvir `tema.mudou`.
- **Marca** (`widgets/marca.py`): logo + "SIG-FT System" no alto do menu,
  com brilho sob o mouse; clique volta à Home.
- **Saudação** (`sigft/app_qt/nome.py`): "Bom dia, <nome>", nome perguntado uma
  vez (aberto pelo lançador, nunca nos testes nem no `--smoke`). O nome só é
  lido por `nome.py` e `views/home.py`, e há teste que trava isso.
- **Splash**: no tema escolhido, com a versão do `_build_info`.

### Ferramentas de uso (etapa 1b, 2026-10-21)

- **Nível das linhas** (`sigft/app/niveis_log.py`, sem Qt): `classificar(msg, nivel)`;
  o `nivel` do protocolo vence quando é `error`/`warn` (ou sinônimo), senão a marca
  que ABRE a primeira linha, sem caixa e como palavra inteira: `[Erro`, `❌`, `Falha`,
  `Erro` → erro; `[Aviso]`, `[!]`, `[Autoconferência]`, `[Atenção]`, `Aviso`, `⚠` →
  aviso (`Erros:`, `Avisos: 2`, `0 falha(s)` seguem info). Tag nova de serviço sem
  nível decidido, ou texto de log que abre com Erro/Aviso/Falha e cai em info,
  reprova `tests/test_niveis_log.py`.
- **Console** (`widgets/console.py`): guarda cada linha com nível e número (`marca()`,
  `linhas(desde=)`); barra na margem de BAIXO: Tudo / Avisos (avisos e erros) / Erros,
  busca sem acento que espera 150 ms sem tecla, Copiar (só o que está à vista; sem
  nada à vista não mexe na área de transferência). A altura do console e o começo do
  texto não mudaram, mas a barra ocupa ~28 px da área de texto (no AutoSpec sobram
  umas 5 linhas). O console continua escuro no tema claro, de propósito.
  Em janela baixa (notebook 1366x768 maximizado, ~690 px úteis) o console de altura
  fixa cede até o mínimo do puxador (barra + duas linhas) em vez de empurrar a janela
  para fora da tela (2026-10-31, `tests/test_qt_tela_1366.py`).
- **Resumo do lote** (`sigft/app/resumo_lote.py` + `widgets/resumo_lote.py`): no fim
  da última tarefa da tela (`ModuleFrame._fim_do_lote`), se houve erro ou aviso, a
  janela agrupada por código PMIB (regex própria, "Sem código PMIB" para o resto),
  com "Copiar lista" e "Abrir log" (grava em `logs\resumos\`). A mesma linha repetida
  só com a duração no fim (falha do `RelatorioLote`) conta uma vez. Com uma caixa
  modal aberta, espera ela fechar; uma janela de resumo por tela. Desligada nos
  testes (`SIGFT_SEM_RESUMO_DO_LOTE`, conftest).
- **Arrastar e recentes** (`widgets/arrastar.py`): o soltar é aceito na hora e
  entregue depois (`QTimer.singleShot`, para não prender o Explorer): ENTREGA o
  arquivo à chave do diálogo (`file_dialogs.entregar`) e clica o botão; o
  `ask_open_file(chave)` acha a entrega e não abre o diálogo. Extensão errada pinta
  o alvo de vermelho; botão desligado recusa. Tela com botão declara `ARRASTAVEIS`
  (8 telas; Tradutor e LMR não têm); `FilePickerRow`, `MultiFilePickerRow` e
  `FileQueueList` já aceitam. Últimos 5 por chave em `user_prefs.json` (seção
  `recentes`), na seta ao lado da linha (só aparece com recente; não olha o disco
  na montagem) ou no botão direito.
- **Ctrl+K** (`widgets/paleta.py`): itens de `catalogo.comandos()` (os módulos, o
  bloqueado apagado e sem clique, + `catalogo.ACOES`, derivadas de
  `catalogo.ACOES_DA_HOME`, `SELETOR_TEMA` e `SELETOR_LETRA`: uma fonte só para a
  Home e a caixa), filtro `catalogo.filtrar`; quem faz é `SIG_FT_App.executar_comando`.
  No Linux/Mac um campo de texto com foco fica com o Ctrl+K (apaga até o fim da
  linha); no Windows a caixa abre.
- **Letra** (`sigft/app_qt/letra.py`): Normal / Grande (`tokens.AUMENTO_DA_LETRA`),
  aplicada na hora como o tema, com o sinal `letra.mudou`: a folha do app e cada
  folha própria ganham +2 px (só `px`); botão e rótulo de uma linha com largura fixa
  alargam até o `sizeHint` e voltam ao pixel no Normal; um vigia ajusta peça nova só
  com a letra grande. Regra somada à folha de uma peça entra por `blocos.pintar`
  (senão o aumento dobra). Smoke: `--letra grande`.
- **Aviso do Windows** (`sigft/app_qt/aviso_windows.py`): `QSystemTrayIcon.showMessage`
  fora de foco, no fim da tarefa e nas esperas (`widgets/espera.py`: login, Excel
  travado, arquivos travados, sim/não, pedir texto). O ícone da bandeja acende no
  aviso e some ao clicar ou quando o SIG-FT volta a ser o app ativo. Liga e desliga
  na Configuração, em Avisos. Nunca nos testes nem no `--smoke`
  (`SIGFT_SEM_AVISO_DO_WINDOWS`, conftest e `main._smoke`).

### Configuração e idioma (2026-10-22)

- **Engrenagem** (`views/configuracao.py`, `JanelaConfiguracao`, uma `JanelaPainel`): à direita do
  título da Home (`HomeView.btn_configuracao`, `abrir_configuracao`) e no Ctrl+K. Seções e ordem em
  `catalogo.SECOES_DA_CONFIGURACAO`; os botões que vieram da barra em
  `catalogo.ACOES_DA_CONFIGURACAO`. Nenhuma regra nova: tema e letra pela Home
  (`escolher_tema`/`escolher_letra`), nome por `nome.guardar`, aviso por `aviso_windows.ligar`,
  canal de testes por `updater`, Chaves/Modelos/atualização pelos métodos da Home.
- **Lâmpada** (2026-10-30; `views/sugestoes.py`, `JanelaSugestoes`, uma `JanelaPainel`): logo à
  esquerda da engrenagem, igual a ela (`HomeView.btn_sugestoes`, `abrir_sugestoes`;
  `catalogo.ACAO_SUGESTOES`, também no Ctrl+K). Uma só aberta; fechar só esconde, e o texto fica.
  "Escrever o e-mail" chama `services/sugestoes.abrir_rascunho` numa thread: rascunho no Outlook
  pelo COM (`Display`, nunca `Send`; "Para" vazio; com "Anexar o log", uma CÓPIA do `sigft.log` na
  pasta temporária), e sem Outlook o `mailto:` (sem anexo: a janela mostra o caminho do log).
- **Idioma** (`sigft/app/idioma.py`, sem Qt): `t("texto em português", **valores)`; a chave é o
  próprio texto; `es`/`en` em `sigft/app/idiomas/*.json`; sem tradução vale o português. Constante de
  módulo em `marcar(...)` e `t()` onde aparece. Só a interface muda; console, portal e planilhas não.
  O idioma vale ao abrir: `main._preparar_qt` (`--idioma` no smoke), a pergunta da primeira abertura
  (`escolha_de_idioma.py`, antes da splash) e o "Reiniciar agora" (`reinicio.py`, recusa com tarefa
  rodando). Os botões do Qt seguem o idioma (`main.LOCALE_DO_QT`; `qtbase_pt_BR`/`qtbase_es` no pacote).
- **Ferramenta** `tools/textos_da_interface.py`: o que falta e sobra nos catálogos, `t(f"...")`,
  `--literais <arquivo>` (o que a guarda acusa), `--faltando es` (JSON para preencher), `--arrumar`.
- **Guardas:** `tests/test_textos_da_interface.py` (catálogos completos, mesmos `{valores}`, sem
  travessão, e todo `sigft/app_qt` sem texto de interface fora de `t()`, exceto `NAO_E_INTERFACE`, com
  o motivo); `tests/test_qt_idioma_telas.py` (cada parte montada em `es`/`en` sem português à vista);
  `tests/test_qt_idioma_varredura.py` (as 12 telas sem corte nem rolagem lateral). Os testes rodam em
  português (conftest); a largura fixa alarga fora do português (`letra._pede_folga`).
- **Tela nova ou texto novo:** escreva em português dentro de `t()`, rode a ferramenta e preencha
  `es` e `en` seguindo o glossário abaixo.

**Glossário** (não se traduzem: SIG-FT, PMIB, Portal PMIB, PDM, SAM-GM, STATUS_PMIB, LMR, TAG,
AutoSpec, Analyzer, PMIB Manager, Search, Gestão PMIB, Excel, PDF, JSON, RDS-PP, Aconex, Box,
GE Vernova, Itaipu, nomes de provedor de IA, os nomes dos idiomas):

| pt | es | en |
|---|---|---|
| ficha (técnica) | ficha (técnica) | (technical) sheet |
| planilha | planilla | spreadsheet |
| robô | robot | robot |
| característica técnica | característica técnica | technical characteristic |
| lote | lote | batch |
| console | consola | console |
| Configuração | Configuración | Settings |
| Chaves de API / Modelos de IA / Gastos de IA | Claves de API / Modelos de IA / Gastos de IA | API keys / AI models / AI costs |
| versão de teste | versión de prueba | test version |
| fornecedor | proveedor | supplier |
| pasta / arquivo / tela | carpeta / archivo / pantalla | folder / file / screen |

Espanhol com "usted"; inglês com imperativo simples; tradução curta (no máximo uns 20% a mais).

### Diário, colunas e menu recolhível (2026-10-26)

- **Diário de quedas** (`sigft/core/diario.py`, sem Qt): `main()` chama `diario.abrir(versao=, idioma=)`
  depois da pergunta do idioma e antes da janela; ele lê a sessão anterior (`classificar`: `NORMAL`,
  `CAIU`, `ENCERRADO`) ANTES de gravar a nova `ABERTURA`, e liga `sys.excepthook`,
  `threading.excepthook` e o `faulthandler` (`logs/queda.log`; o com rastro vira `queda.log.anterior`).
  `SIG_FT_App.closeEvent` aceito grava `FECHAMENTO pela janela`. Passou de 1 MB, vira `diario.log.1`.
  Nunca levanta. A Home mostra `aviso_sessao` (cartão `#cartao[borda="aviso"]`) quando
  `diario.aviso_pendente()`; "Entendido" é `diario.dispensar_aviso()`. Nos testes vem desligado
  (`SIGFT_SEM_DIARIO`, no `conftest`); quem testa tira a variável e troca o `faulthandler` por um dublê.
- **Colunas lembradas** (`sigft/app_qt/widgets/colunas.py`): `instalar_colunas(tabela, chave,
  colunas_internas)` liga mover, largura e o menu do botão direito (esconder, "Restaurar colunas");
  guarda em `prefs` (seção `colunas`) pela chave da tabela e pela chave interna de cada coluna.
  `juntar` (pura) ignora coluna sumida, põe a nova no fim e trata preferência estragada como padrão.
  Na `tabela_ttk`, mexer desliga o `EsticaColunas` e a última coluna estica (e grava largura `None`,
  para voltar esticando); restaurar o religa.
  Usam: `TabelaSelecaoDialog(chave_colunas=, colunas_internas=)` (`selecao_de_itens`,
  `selecao_duplicadas`) e a Revisão antes do portal (`widgets/revisao_portal.py`, chave
  `revisao_portal`). O Resumo do lote ficou como estava (decisão de 2026-10-26).
- **Menu recolhível** (`SIG_FT_App.recolher_menu`/`alternar_menu`): barra com
  `estilo.LARGURA_BARRA_RECOLHIDA`, só ícones (o nome na dica, antes da dica de sempre), seções como
  `#traco_secao`, a marca só com o símbolo (`Marca.recolher`). Margens de 7 de cada lado
  (`MARGENS_DA_BARRA_RECOLHIDA`): na janela baixa a barra de rolagem come 10 px e a seta (36) ainda
  cabe. Lembrado em `prefs.get_opcao("menu_recolhido")`; Ctrl+K `acao:menu` (o texto diz "Recolher
  menu" ou "Expandir menu", `catalogo.comandos(menu_recolhido=)`). Cor só pela folha
  (`QPushButton[menu="true"][recolhido="true"]`, `#home[recolhido="true"]`).

### Ajuda para quem começa (2026-10-28)

Desenho: `docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`. Ideia do Corella
Automation (v1.4.0), adaptada.

- **"Como funciona"** (`sigft/app_qt/widgets/como_funciona.py`; os textos, sem Qt, em
  `sigft/app/como_funciona.py`): logo abaixo do título de cada tela do menu, sempre no mesmo lugar,
  uma frase curta à vista e o botão "Como funciona" (ícone `circle-help`, variante secundária), que
  abre de 3 a 6 itens: o que a tela espera receber, o que ela muda, o que acontece se parar no meio.
  Fechado na primeira vez; aberto ou fechado fica lembrado por tela (`prefs`,
  `como_funciona_aberto.<tela>`). A tela chama `instalar_como_funciona(self, "<chave>")` no fim do
  `_build_ui`; nas seções de abas (Aplicação LMR, PMIB Manager) o bloco segue a aba aberta, e a tela
  embutida numa aba não ganha bloco. Nos testes vem desligado (`SIGFT_SEM_COMO_FUNCIONA`): os testes de
  medida conferem cada pixel contra a interface antiga. A varredura de corte (`tests/_varredura.py`)
  tira a variável e mede cada tela e cada aba também com o bloco aberto.
- **Boas-vindas** (`sigft/app_qt/views/boas_vindas.py`, regra sem Qt em `sigft/app/boas_vindas.py`):
  página da pilha (NÃO modal), registrada em `main.TELAS` com a chave `main.CHAVE_BOAS_VINDAS`
  (`"BoasVindas"`) mas fora do menu lateral. `SIG_FT_App.__init__` monta a Home e, se
  `boas_vindas.deve_mostrar_boas_vindas()`, mostra a página (`mostrar_boas_vindas`). A pergunta do
  idioma já foi feita antes da janela; a do nome aparece por cima da página. Tem o título, uma frase,
  3 cartões de caminho (`CAMINHOS`: Criar fichas novas → `CriaFichas`; Completar fichas que já existem
  → `UploadConditions`; Acompanhar as listas de sobressalentes → `PMIBManager`), os lembretes do
  "Como funciona" e do Ctrl+K e o botão "Ir para o início". Caminho cuja tela está em
  `catalogo.TELAS_BLOQUEADAS` vem apagado (`#card:disabled`, `#card_titulo:disabled`), com a mesma
  dica do menu (`catalogo.dica_do_menu`), e o clique não faz nada.
  - **Quando aparece sozinha:** sem a opção `boas_vindas_vista` (`prefs`, seção `opcoes`) E sem
    rastro de uso na pasta de dados (`rastros_de_uso`): entrada em `user_prefs.json` nas seções
    `ultimos`, `categorias`, `pastas_padrao`, `arquivos`, `recentes` ou `colunas`
    (`SECOES_DE_USO`); versão vista das novidades DIFERENTE da atual (a janela de novidades só
    grava no app instalado e depois da decisão: versão anterior gravada é de quem atualizou);
    `user_prefs.json` ilegível; arquivo em `logs/` que não seja da própria abertura
    (`sigft.log`, `diario.*`, `queda.log*`), ou subpasta de `logs/` com arquivo; `api_config.json`
    com alguma chave preenchida. Idioma, tema, letra, nome, a versão vista quando é a atual e as opções liga/desliga NÃO
    contam: a primeira abertura os grava antes (ou logo depois) da decisão. Quem atualiza traz as
    pastas no `user_prefs.json` (pela migração, se vier de antes da pasta de dados) e não vê.
    Nunca levanta; na dúvida, a Home.
  - **Vista:** "Ir para o início" e o clique num caminho gravam `boas_vindas_vista`
    (`boas_vindas.marcar_vista`); só mostrar não grava (quem fecha o app sem escolher a vê de novo).
  - **Reabre:** Ctrl+K `acao:boas_vindas` ("Boas-vindas"; acha em português também, como as outras
    ações) e a seção **Ajuda** da janela Configuração ("Rever as boas-vindas", que fecha a janela).
  - `main.PAGINAS_FORA_DO_MENU` (Home e boas-vindas): as páginas da pilha que não exigem botão no
    menu nem cartão na Home (`tests/test_tela_correcao_pdm.py`).
  - Nos testes não abre sozinha (`SIGFT_SEM_BOAS_VINDAS`, no `conftest`); quem testa a página tira a
    variável. A varredura de corte (pt/es/en, letra Grande) passa por ela.

### IA por módulo (2026-11-04)

"Modelos de IA" (Configuração) abre a janela **IA por módulo** (`HomeView.abrir_janela_ia_por_modulo`): a lista dos módulos à esquerda e, à direita, os três modos (`widgets/ia_do_modulo.PainelIaDoModulo`): IA Externa (catálogo do OpenRouter com filtro, "Atualizar catálogo" numa thread e "Chave do OpenRouter..."), IA Interna (desligada) e Workflow AMP (endereço e chave do webhook do módulo). O painel de antes, do modelo padrão, abre pelo botão "Modelo padrão (avançado)...". Cria Fichas, Analyzer, Upload Condições, Upload Specs e Planilhas PMIB têm "Configurar IA" na linha do título (`instalar_configurar_ia`, sem somar altura), que abre o mesmo painel só com as tarefas da tela (`sigft/app/ia_por_modulo.TAREFAS_DA_TELA`). As duas portas gravam no mesmo lugar (`core/llm/modo.py` + as chaves) e se avisam (`ia_do_modulo.avisos().mudou`).

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


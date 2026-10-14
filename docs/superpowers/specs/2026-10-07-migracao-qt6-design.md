# Interface do SIG-FT: migração de CustomTkinter para Qt6 (PySide6)

**Data:** 2026-10-07 · **Frente:** contribuição externa (Jonathan, `Jonann17`), autorizada pelo Luan
**Origem:** pedido de revisão geral do código com prioridade em *"funcionalidade antes que
nada e otimização"*, e depois: *"podemos migrar todo pyqt6? es mejor que tkinter"* —
autorizado pelo Luan. Exigência do pedido: **otimizar e ficar igualmente bonito**.

**Decisões (2026-10-07):**
- **PySide6**, não PyQt6. Mesmo Qt por baixo, desempenho equivalente; a diferença é a
  licença: PyQt6 é GPL (distribuir o `.exe` obrigaria a abrir o código ou comprar a licença
  comercial da Riverbank), PySide6 é LGPL (o `.exe` pode sair com o código fechado, como hoje).
  O repositório é privado e não tem licença declarada.
- **Escopo "A":** mesmo comportamento, mesmos textos e fluxos; os defeitos de thread
  conhecidos são corrigidos no caminho (ver §6), porque reproduzi-los em código novo não
  faz sentido.
- **Estratégia "1":** uma interface Qt NOVA (`sigft/app_qt/`) ao lado da atual, tela por
  tela. A interface atual continua funcionando até o corte final (§10).
- **Entrega:** fora do repositório do Luan. Patches (`git format-patch`) e um log em
  `Jonann17/jonan`, `sig-ft-propuestas/`; o Luan aplica com `git am`.
- **AutoSpec:** o Rafael foi avisado para não mexer em nada até esse commit. A tela
  `ModuloAutoSpec` migra junto com as outras; o log leva uma nota para ele (§11).

---

## 1. Objetivo e critérios de aceite

A migração está pronta quando:

1. **Mesma aparência.** Paleta GE Vernova (`sigft/app/theme.py`), fonte Roboto, layout
   barra lateral + cabeçalho/conteúdo/console, mesmos ícones e logo. Conferido por captura de
   tela lado a lado, tela por tela (antes = CustomTkinter, depois = Qt), no Windows e no macOS.
   Decisão de produto nº 3 do plano ("sem redesign") continua valendo.
2. **Mesmo comportamento.** Toda tela faz o que fazia, com os mesmos textos. Nenhum serviço
   (`sigft/core/`, `sigft/services/`) muda de assinatura.
3. **Nenhum widget tocado fora da thread da interface.** Garantido por construção (§6) e por
   teste.
4. **Mais rápido**, medido antes e depois (§7): tempo até a janela principal, memória após
   abrir, e o console com 10.000 linhas.
5. **Roda no Windows e no macOS** a partir do código, e o `.exe` do Release monta e passa no
   `--smoke` e no `--conferir-pacote`.
6. **Suíte verde** (`bash scripts/check.sh`) e app aberto de verdade, como o `CLAUDE.md` exige.

Fora do escopo: redesenho, mudança em serviços ou no RPA, telas novas, trocar o motor do
robô. A tela `CorrecaoPDM` migra, mas continua **bloqueada** (`TELAS_BLOQUEADAS`).

## 2. Por que dá para fazer isso sem tocar nos serviços

O princípio nº 2 da arquitetura já está cumprido: **nenhum arquivo de `sigft/core/` ou
`sigft/services/` importa tkinter** (verificado por grep em 2026-10-07; as menções que
existem são comentários). A interface conversa com os serviços só por callbacks
(`sigft/core/callbacks.py`) e pelo registro `sigft/app/backends.py`. Tudo o que muda está
em `sigft/app/` (~11.000 linhas), em ~20 arquivos de teste, no `SIG-FT.spec`, no
`requirements.txt` e no CI.

## 3. Estrutura

```
sigft/app_qt/
├── __init__.py
├── main.py           # SIG_FT_App (QMainWindow), SplashScreen, main(), --smoke
├── estilo.py         # theme.py -> folha de estilo Qt (QSS) + carga das fontes
├── backends.py       # mesmo registro de hoje, guardando o MOTIVO de cada falha
├── interface.py      # na_interface(): o único caminho de uma thread até um widget
├── atualizacao.py    # janela da atualização automática
├── widgets/
│   ├── console.py        # ConsoleFrame
│   ├── module_frame.py   # ModuleFrame (cabeçalho, conteúdo, console)
│   ├── espera.py         # DialogosDeEspera: pausar_e_esperar, perguntar_retry_excel...
│   ├── pickers.py        # FilePickerRow, MultiFilePickerRow, FolderPickerRow, FileQueueList
│   ├── dialogs.py        # os diálogos de hoje, mesmos nomes
│   ├── mural.py
│   └── painel_janela.py
└── views/            # uma tela por arquivo, MESMOS nomes de arquivo e de classe de hoje
```

**Reaproveitado sem mudança:** `sigft/core/*`, `sigft/services/*`, `sigft/app/theme.py`
(continua a fonte única de cor e fonte — `estilo.py` lê de lá, não copia), as mensagens de
`sigft/app/widgets/dialogs.py` (`MSG_*`, `msg_*`: são texto, não widget; o Qt importa de
lá até o corte), a memória de pastas de `sigft/core/prefs.py` e `sigft/core/instancia.py`.

**`file_dialogs.py`** ganha a versão Qt com a MESMA assinatura (`ask_open_file`,
`ask_open_files`, `ask_save_file`, `ask_directory`, com `chave`, `categoria`,
`initialdir`, `dialog_fn`): só o diálogo por baixo muda para `QFileDialog`. A resolução de
pasta inicial e o `remember_dir` continuam sendo os de hoje.

## 4. Mapa CustomTkinter -> Qt

| Hoje | Qt | Observação |
|---|---|---|
| `ctk.CTk` / `SIG_FT_App` | `QMainWindow` | barra lateral `QScrollArea` + `QStackedWidget` |
| `ctk.CTkFrame` | `QFrame` com `objectName` | cor e borda vêm do QSS, não de argumento |
| `ctk.CTkScrollableFrame` | `QScrollArea` | |
| `ctk.CTkButton` | `QPushButton` | variantes (`primario`, `acento`, `perigo`, `menu`) por propriedade QSS |
| `ctk.CTkLabel` | `QLabel` | |
| `ctk.CTkEntry` (+ `show="*"`) | `QLineEdit` (`EchoMode.Password`) | |
| `ctk.CTkTextbox` / console | `QPlainTextEdit` só-leitura | ver §7 |
| `ctk.CTkProgressBar` | `QProgressBar` | modo indeterminado = `setRange(0, 0)` |
| `ctk.CTkCheckBox` / `CTkSwitch` | `QCheckBox` | |
| `ctk.CTkOptionMenu` / `CTkComboBox` | `QComboBox` | |
| `ctk.CTkTabview` | `QTabWidget` | |
| `ttk.Treeview` / `Listbox` | `QTableView` / `QListView` + modelo | ver §7 |
| `ctk.CTkToplevel` + `grab_set` + `wait_window` | `QDialog.exec()` | modal de verdade |
| `messagebox.*` | `QMessageBox` | sempre na thread da interface (§6) |
| `self.after(ms, f)` | `QTimer.singleShot(ms, f)` | só para atraso real; de thread, `na_interface` |
| `ctk.CTkImage` | `QPixmap` escalado com `SmoothTransformation` | proporção calculada, como hoje |

## 5. Aparência: como fica igual

- **Cores:** `estilo.py` monta UMA folha QSS a partir de `theme.COLORS`, `COR_CARTAO` etc.
  Os cinzas nomeados do Tk (`"gray30"`, `"gray45"`, `"gray60"`, `"gray70"`, `"gray"`) viram
  hexadecimal pela tabela do Tk (`grayNN` = NN% de 255; `gray` = `#BEBEBE`), numa função com
  teste — sem isso o Qt não entende o nome e cai no preto.
- **Fonte Roboto:** hoje ela não vem do sistema, vem DENTRO do pacote `customtkinter`
  (`assets/fonts/Roboto/Roboto-Regular.ttf` e `Roboto-Medium.ttf`). Sem copiar, o Qt cairia
  na fonte padrão e a app mudaria de cara. Os dois `.ttf` vão para `assets/fonts/`, com a
  licença (Apache 2.0), e são registrados com `QFontDatabase.addApplicationFont` antes da
  primeira janela. `Consolas` do console tem `Menlo` como alternativa no macOS.
- **Ícones em preto e branco.** Os ícones dos botões são emojis no texto (📋 🤖 💰 🔑 🔄 🏠).
  O Tk os desenha monocromáticos; o Qt usa a fonte de emoji COLORIDA do sistema (Apple no
  Mac, Segoe no Windows). Decisão do Jonathan (2026-10-07): **continuam em preto e branco.**
  Mecanismo, validado no protótipo: `assets/fonts/NotoEmoji-Regular.ttf` (Google, licença
  OFL, ~870 KB) registrada no início, e `estilo.mono(texto)` acrescenta o seletor U+FE0E
  ("apresentação de texto") depois de cada emoji. Só a fonte, ou só o seletor, NÃO bastam
  — testado: sem o seletor o Qt continua escolhendo a fonte colorida.
- **Espaçamento igual ao de hoje:** botões da barra lateral com 35 px de altura e 4 px
  entre eles, rótulo de seção com 20 px acima e 5 abaixo, botões da barra da Home com
  40 px — os valores que o CustomTkinter aplica hoje.
- **Cards da Home mais compactos** (decisão do Jonathan, 2026-10-07): a descrição ocupa a
  largura do card, sem o `wraplength=380` de hoje. Os 12 cards cabem sem rolar a tela em
  1280x850. É a única mudança visual deliberada; o resto segue a decisão nº 3.
- **Cantos arredondados, bordas e hover:** QSS (`border-radius`, `:hover`, `:disabled`),
  com os mesmos raios e cores que o CustomTkinter usa por padrão no tema `dark-blue`.
- **DPI:** o Qt 6 trata tela de alta resolução sozinho (Windows com escala 125/150% e
  Retina no Mac) — some o `check_dpi_scaling` que hoje solta aviso no console.
- **Conferência:** capturas lado a lado, com as de `docs/superpowers/specs/prints-janelas/`
  como referência dos diálogos.
- **Protótipo aprovado:** a Home em PySide6 foi prototipada fora do repositório e comparada
  lado a lado com a atual; o Jonathan aprovou o aspecto com os três ajustes acima.

## 6. Threads e interface

O padrão de hoje é `threading.Thread` + `self.after(0, ...)`, e onde alguém esqueceu o
`after` o widget é tocado fora da thread da interface — no macOS isso **derruba o app**. O
desenho troca a disciplina por mecanismo:

- **`interface.na_interface(func, *args)`**: emite um sinal de um `QObject` que vive na
  thread da interface; o Qt entrega o sinal por fila (`QueuedConnection`) e `func` roda lá.
  Chamável de qualquer thread. Substitui os ~85 `self.after(0, ...)` de hoje.
- **Threads continuam `threading.Thread`**, não `QThread`: os serviços não mudam, e o
  `instancia.tarefas_em_andamento()` (que pergunta antes de fechar com tarefa rodando)
  continua valendo do mesmo jeito — tarefa da pessoa é thread comum, fundo é `daemon=True`.
- **`DialogosDeEspera`** mantém a API (`pausar_e_esperar`, `perguntar_retry_excel`,
  `perguntar_arquivos_travados`) e a regra de hoje: da thread da interface, `QDialog.exec()`;
  de outra thread, `na_interface` abre o diálogo e a thread espera num `threading.Event`.
- **Corrige o defeito 1 da revisão:** `ModuloCriaFichas` abria `JanelaAcaoRobo` e
  `messagebox` de dentro do worker (`cria_fichas.py:463, 468, 475, 745`). Na versão Qt a
  janela passa por `DialogosDeEspera`, e o `wait_window` sai do `__init__` (pendência de
  2026-08-28 em `PENDENCIAS.md`).
- **Corrige o defeito 5:** o botão que dispara um robô é desabilitado NO CLIQUE, antes de
  criar a thread — dois cliques não sobem dois robôs.
- **Exceção não tratada num worker** vai para o console da tela e para o `sigft.log`, e o
  botão volta a ficar habilitado — nunca fica "morto".
- **Guarda em teste:** em modo de teste, `ModuleFrame` verifica a thread em cada acesso de
  widget feito pelos helpers; um teste roda cada worker com dublês e falha se algum toque
  vier de fora.

## 7. Otimizações

Cada uma é medida antes e depois (critério 4); se não melhorar, não entra.

1. **Telas criadas na primeira visita**, não as 13 na abertura. Hoje `SIG_FT_App.__init__`
   constrói todas. A barra lateral e os cards da Home continuam todos visíveis; a tela é
   montada no primeiro `show_frame` e reaproveitada depois.
2. **Sem pausas artificiais na splash:** saem o `time.sleep(0.1)` por módulo e o
   `time.sleep(0.8)` final (`main.py:309, 326`) — ~2 s por abertura. A splash continua
   igual na aparência e mostra o progresso real.
3. **Console rápido:** `QPlainTextEdit` com `appendPlainText` e limite de blocos
   (`setMaximumBlockCount`, 20.000 linhas), e as linhas que chegam de thread são juntadas e
   escritas em lote a cada ~50 ms. O `CTkTextbox` reescreve e rola a cada `insert`, e fica
   lento com lotes grandes.
4. **Listas e tabelas com modelo** (`QListView`/`QTableView`): a seleção de fichas e as
   listas de arquivos desenham só as linhas visíveis, em vez de um widget por item.
5. **Imagens escaladas uma vez** e guardadas em cache (logo e ícone).
6. **Imports pesados fora da thread da interface**, como hoje (a splash carrega os
   backends em segundo plano) — sem regressão no tempo até a primeira pintura.

## 8. Erros que hoje passam em silêncio (defeitos 2, 3 e 4 da revisão)

- **Backend que não carregou:** `backends.py` guarda o motivo (`falhas[nome] = erro`). A
  tela abre normalmente e, ao usar, mostra *"Este módulo não carregou: <motivo>. Veja
  Documentos\SIG-FT\logs\sigft.log"* — em vez de `AttributeError: 'NoneType'`. Nenhuma tela
  usa backend no próprio construtor (hoje `upload_tech_specs.py:31` usa, e por isso um
  backend quebrado impede a app inteira de abrir).
- **Python antigo:** o ponto de entrada confere `sys.version_info >= (3, 10)` antes de
  qualquer import pesado e explica o que instalar. `pyproject.toml` ganha
  `requires-python = ">=3.10"`.

## 9. Testes

- **`pytest-qt` com `QT_QPA_PLATFORM=offscreen`**: as telas Qt são construídas de verdade
  no CI do Linux, sem display — mais forte que o dublê `tests/ctk_falso.py`, que prova só a
  ideia que o próprio teste faz do CustomTkinter.
- Cada tela migrada traz os seus testes: monta, os botões ligam aos métodos certos, e o
  worker não toca widget fora da thread (§6).
- Os testes de hoje que dependem de `ctk_falso` continuam valendo para `sigft/app/` até o
  corte; no corte, são removidos junto com a interface antiga, e cada um tem equivalente Qt.
- CI (`.github/workflows/ci.yml`) instala PySide6 e roda em Python 3.10 (mínimo) **e** 3.12.

## 10. Build e corte final

- `requirements.txt`: `+PySide6` (só os módulos usados: QtCore, QtGui, QtWidgets);
  `customtkinter` sai **só no corte**.
- `SIG-FT.spec`: hooks do PySide6 (o PyInstaller já traz) e exclusão explícita dos módulos
  Qt que não usamos (WebEngine, 3D, Multimedia, QML...), para o `.exe` não engordar à toa;
  `assets/fonts/` entra nos `datas`.
- `sigft/app/conferencia.py` (`--conferir-pacote`) passa a conferir PySide6 e as fontes.
- **Corte:** `frontend.py` passa a importar de `sigft.app_qt.main`; `SIG-FT.bat` não muda.
  Depois do corte e de um Release validado, `sigft/app/` (exceto `theme.py`) e
  `customtkinter` saem. Até lá, `python -m sigft.app_qt.main` abre a versão nova.

## 11. Ordem e entrega

Cada etapa é um ou mais commits na branch local `local/jonan-cambios`, exportados como
patch para `Jonann17/jonan:sig-ft-propuestas/patches/` e descritos no `LOG.md`:

1. Base: `estilo.py`, fontes, `interface.py`, `backends.py`, `ModuleFrame`, console,
   pickers, diálogos, `file_dialogs` Qt, janela principal com barra lateral e Home. Telas
   ainda não migradas mostram "ainda não migrada para Qt".
2. Pilotos (os mesmos que o plano usou no CP 7.1): **ApagarLMR** e **Translator**.
3. LMR (aba única `AplicacaoLMR`), BuscaPMIB, PMIBManager, Analyzer, PDM.
4. UploadConditions, UploadTechSpecs, CopiaFichas, CorrecaoPDM (bloqueada).
5. CriaFichas (correção do defeito 1) e AutoSpec — com nota no log para o Rafael
   listando o que mudou na tela dele.
6. Atualização automática, mural, painel; medições finais; corte (§10).

O `LOG.md` registra, por etapa: o que mudou, por quê, como foi testado e a medição.
Ao final, uma linha no **mural do `CLAUDE.md`** avisa as duas frentes da troca de UI.

## 12. Riscos

| Risco | Mitigação |
|---|---|
| Luan e Rafael mexem em `sigft/app/` enquanto isto anda | a interface antiga continua intacta; cada patch é pequeno e por tela; Rafael congelado até o commit |
| Diferença visual sutil | captura lado a lado por tela, no Windows e no macOS, antes de dar a etapa por pronta |
| `.exe` maior | exclusão dos módulos Qt não usados; tamanho medido no Release |
| Portal não é testável daqui | os fluxos de robô só mudam na camada de diálogo; a validação contra o portal real fica com quem tem acesso à rede da empresa, antes do corte |
| Teste de UI ainda depende de dublê para o portal | igual a hoje: verde no CI não é prova de portal (`CLAUDE.md`) |

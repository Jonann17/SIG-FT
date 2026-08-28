# Padronização das janelas de diálogo — um padrão só, e a janela de Excel travado em todo módulo

**Data:** 2026-08-28 · **Frente:** refatoração geral (Luan)
**Origem:** *"toda vez que abre uma segunda tela pedindo confirmação de algo, eu gostaria que
seguisse o mesmo padrão... e buscando sempre melhorar a experiência do usuário, que seria ter
possibilidade de minimizar a tela"* + *"sempre que formos salvar em um excel devemos usar o
mesmo método, ou seja, se não deu de salvar aparece a janela instruindo a fechar e tentar o
salvamento de novo para todos módulos"*

---

## 1. O diagnóstico, medido

As 9 janelas secundárias do app foram abertas uma a uma e fotografadas. Nenhuma das 9 se
comporta como outra:

> **Os prints.** Os três do grupo 1 — o escopo deste documento — estão versionados em
> [`prints-janelas/`](prints-janelas/): o modelo (`Ação Manual Necessária`), o outro modelo
> (`Arquivo Bloqueado`) e a caixa fora do padrão (`Login Necessário`). Os do grupo 2, que
> serviram só para decidir o escopo, ficaram fora do repositório para não versionar ~600 KB de
> imagem de trabalho adiado.

| Janela | Minimiza | Segue o tema | Cores da paleta | Libera o app |
|---|---|---|---|---|
| Ação Manual Necessária (`PausaLoginDialog`) | ✅ | ✅ | ✅ | ✅ |
| Arquivo Bloqueado (`RetryLockDialog`) | ✅ | ✅ | ✅ | ✅ |
| Login Necessário (`messagebox`, 4 lugares) | ❌ | ❌ | ❌ | ❌ |
| Revisão de PDMs | ❌ | ❌ | ❌ | ❌ |
| Intervenção Necessária | ❌ | ✅ | ❌ | ❌ |
| Selecionar Fichas para Cópia | ❌ | ❌ | ✅ | ❌ |
| Revisão e Edição Manual | ✅ | ❌ | ✅ | ❌ |
| Resumo Final | ❌ | ❌ | ✅ | ✅ |
| Selecione os Códigos PMIB | ❌ | ✅ | ✅ | ❌ |

**A causa do "não minimiza" é `transient(parent)`.** Ele marca a janela como filha da
principal, e no Windows isso remove os botões de minimizar/maximizar e tira a janela da barra
de tarefas. Seis das nove o chamam. A `Revisão e Edição Manual` prova o ponto pelo avesso: é
uma das poucas que não chama, e é uma das poucas que minimiza.

**O padrão bom já existe no código.** A `PausaLoginDialog` faz tudo certo, e foi ela que o
usuário apontou como referência. O trabalho não é inventar um padrão — é estendê-lo.

## 2. Escopo: grupo 1 apenas

As caixas de diálogo do app se dividem em quatro grupos. Decisão do usuário em 2026-08-28:
**só o grupo 1 agora**; o grupo 2 muda "no futuro, quando for necessidade".

| Grupo | Qtd | O que é | Neste documento? |
|---|---|---|---|
| 1. Param o robô e esperam o usuário | 8 | pausa de login, Excel bloqueado | ✅ sim |
| 2. Escolha e revisão | 6 | selecionar fichas, revisar PDM, resumo | ❌ adiado |
| 3. Decisão sim/não | ~10 | "apagar tudo?", "interromper o robô?" | ❌ fora |
| 4. Aviso informativo | 36 | "Concluído", "Sucesso" | ❌ fora |

O requisito do Excel travado **pertence ao grupo 1** (a `RetryLockDialog` é uma das 8), e é o
que expande este trabalho para além da aparência — ver §4.

## 3. O mecanismo, uma vez

As duas frentes deste documento precisam da mesma coisa: **abrir um diálogo a partir da thread
do robô e esperar a resposta do usuário.**

Isso não é opcional nem detalhe de implementação. O Tk só pode ser tocado pela thread que criou
os widgets; os `_worker()` rodam em `threading.Thread`. As 3 telas que acertam já fazem o trio
correto, copiado em cada uma:

```python
evento = threading.Event()
self.after(0, lambda: self._mostrar_janela_pausa(msg, evento))
evento.wait()
```

As 4 que erram chamam `messagebox.showinfo(...)` **direto de dentro do worker** — criando um
widget fora da thread da interface. É a mesma classe de defeito que o CP 7.1 corrigiu no
console, onde 7 telas escreviam no `CTkTextbox` de dentro da thread. Funciona por sorte no
Windows; não é correto.

### 3.1 O mecanismo vive num mixin

> **Correção aplicada durante a implementação (2026-08-28).** Este parágrafo
> dizia "`ModuleFrame` ganha o mecanismo", e não sobreviveu ao contato com o
> código: das 12 telas, **só 2 herdam de `ModuleFrame`** (`ApagarLMR` e
> `Translator`, os pilotos do CP 7.1) — as outras 10 são `ctk.CTkFrame` puro.
> Exigir a migração das 10 para poder trocar 4 caixas de diálogo deixaria a
> correção refém de um trabalho muito maior.
>
> Virou `sigft/app/widgets/espera.py`, o mixin `DialogosDeEspera`: a tela o
> adota com uma linha (`class ModuloLMR(DialogosDeEspera, ctk.CTkFrame)`), e a
> `ModuleFrame` herda dele — então as 2 telas que já a usam ganham de graça,
> sem mudar nada. A ordem importa: o mixin vem ANTES da classe do
> CustomTkinter, para o `super().__init__` passar por ele.
>
> Telas que adotaram: `ApagarLMR` e `Translator` (via `ModuleFrame`), `LMR`,
> `CriaFichas`, `Analyzer` e `PDM` (direto).

Um método interno privado que serve aos dois casos, e dois métodos públicos sobre ele:

```python
def _abrir_e_esperar(self, construir_dialogo):
    """Abre um diálogo na thread da interface e BLOQUEIA quem chamou até o
    usuário decidir. Chamável de qualquer thread.

    `construir_dialogo(evento, resultado)` recebe o `threading.Event` que
    solta quem chamou e o dicionário onde o diálogo grava a decisão."""

def pausar_e_esperar(self, mensagem, texto_botao="CONTINUAR AUTOMAÇÃO") -> None:
    """Pausa de ação manual (login). Volta quando o usuário liberar."""

def perguntar_retry_excel(self, mensagem=MSG_EXCEL_BLOQUEADO) -> bool:
    """Arquivo travado. True = tentar de novo, False = ignorar e seguir."""
```

Um mecanismo, dois usos. É o mesmo raciocínio do `ConsoleFrame.log` do CP 7.1: uma
implementação que não dá para usar errado, em vez de um padrão que cada tela precisa lembrar
de repetir.

**Chamar da thread da interface por engano trava o app** (o `wait()` seguraria a mesma thread
que precisa processar o `after`). O método detecta esse caso e levanta `RuntimeError` com a
explicação, em vez de congelar em silêncio.

### 3.2 `PausaLoginDialog` ganha texto de botão configurável

Hoje é fixo em `"CONTINUAR AUTOMAÇÃO"`. A tela de exclusão de LMR é destrutiva, e o botão dizer
o que vai acontecer (`"COMEÇAR A EXCLUSÃO"`) é mais honesto do que um rótulo genérico. Padrão
inalterado, então as 3 telas atuais não mudam de aparência.

## 4. A janela de Excel travado em TODOS os módulos

Este é o requisito funcional do usuário, e é o de maior efeito prático.

### 4.1 O estado hoje

A peça certa **já existe**: `core/excel/locking.save_with_retry(wb, path, on_locked=...)`, do
CP 1.3, que unificou os 4 laços de `PermissionError` do diagnóstico. Só que nem todo mundo
passa por ela.

| Serviço | Como salva | Protegido? |
|---|---|---|
| `cria_fichas`, `pmib_manager`, `upload_conditions`, `tech_specs` | `save_with_retry` | ✅ |
| `analyzer` (1), `analyzer_relatorio` (1), `autospec` (1), `pdm` (3), `translator` (1) | `wb.save()` direto | ❌ **7 pontos** |

Nos 7 desprotegidos, gravar com a planilha aberta no Excel levanta `PermissionError` sem
janela nenhuma — o usuário perde o trabalho do lote e não sabe por quê.

### 4.2 O canal UI↔serviço

O princípio nº 2 da arquitetura é inegociável: **serviço nunca importa tkinter**. O serviço
não pode abrir a janela; ele precisa *perguntar* e a tela responde.

`UICallbacks` (CP 1.4) ganha um quinto canal:

```python
retry_lock: Callable[..., bool] | None = None   # (caminho) -> bool
```

Com no-op seguro no `__post_init__`, como os outros quatro: ausente, devolve `False`
(= "não retente"), que é exatamente o comportamento de hoje nos 7 pontos desprotegidos. Isso
importa: nenhum serviço muda de comportamento por ganhar o canal — só ganha a *possibilidade*
de perguntar.

Fluxo completo:

```
serviço: save_with_retry(wb, path, on_locked=lambda n, e: callbacks.retry_lock(path))
                                                                    │
tela:    UICallbacks(retry_lock=self.perguntar_retry_excel)  ←──────┘
                                    │
                                    └─> _abrir_e_esperar(RetryLockDialog) -> bool
```

### 4.3 Por que um canal dedicado, e não o `ask` genérico

`UICallbacks.ask` já existe e devolve `bool`. Reusá-lo evitaria acrescentar campo ao protocolo.
Foi descartado por dois motivos:

1. **A tela precisa saber o que está perguntando** para abrir a janela certa. Com `ask`
   genérico, ela receberia só um texto e teria de adivinhar pelo conteúdo — ou abriria um
   `askyesno` comum, perdendo a janela específica que o usuário pediu.
2. `ask` é usado hoje para outras perguntas de negócio. Sobrecarregá-lo faria uma mudança em
   um caminho afetar o outro.

## 5. Os checkpoints

Quatro, na ordem. Cada um fecha verde e é commitável sozinho.

### CP A — o mecanismo na `ModuleFrame`

`_abrir_e_esperar` + `pausar_e_esperar` + `perguntar_retry_excel`; `texto_botao` na
`PausaLoginDialog`.

*Aceite*: testes provando que (a) o diálogo é **agendado**, não criado na hora — com o dublê de
`after` que enfileira, do CP 7.1; (b) a thread que chamou é liberada quando o usuário decide;
(c) `perguntar_retry_excel` devolve `True`/`False` conforme o botão; (d) chamar da thread da
interface levanta `RuntimeError` em vez de travar.

### CP B — as 4 caixas de login viram o diálogo padrão

`apagar_lmr`, `lmr`, `cria_fichas` (2 lugares). As 3 telas que já acertam migram para o método
novo, e as 3 cópias de `_mostrar_janela_pausa` são removidas.

**Os textos são preservados** — reformatados no estilo do modelo (passos numerados), mas
dizendo o que já diziam. Duas delas carregam instrução específica que é informação útil, não
ruído:

| Tela | Instrução que precisa sobreviver |
|---|---|
| `apagar_lmr` | "...para começar a **EXCLUSÃO**" (botão: `COMEÇAR A EXCLUSÃO`) |
| `lmr` | "...para começar" |
| `cria_fichas` (1) | "Navegue até a página **com o botão 'Nova Ficha'**" |
| `cria_fichas` (2) | "Navegue até a página **PRINCIPAL** (onde fica a barra de pesquisa)" |

*Aceite*: nenhum `messagebox.showinfo` de login resta no `views/`; as 4 janelas abertas no app
real, conferidas na tela; os 3 `_mostrar_janela_pausa` removidos sem perda de comportamento.

### CP C — o canal `retry_lock` no protocolo

`UICallbacks.retry_lock` + no-op seguro + as telas ligando ao `perguntar_retry_excel`.

*Aceite*: `UICallbacks()` sem o canal continua funcionando e devolve `False`; teste do fluxo
completo (serviço pergunta → tela responde → `save_with_retry` retenta).

### CP D — os 7 pontos desprotegidos passam por `save_with_retry`

`analyzer`, `analyzer_relatorio`, `autospec`, `pdm` (3), `translator`.

⚠️ **`translator` é caso especial**: salva via `xlwings` com `wb.save()` **sem caminho**, e
`save_with_retry` chama `wb.save(path)`. O `upload_conditions` já resolveu isso com um
adaptador duck-typed mínimo (`services/upload_conditions.py`, ~linha 400) — usar o mesmo
caminho, não inventar outro.

*Aceite*: `grep` não encontra `wb.save(` fora de `save_with_retry` nos serviços; teste
simulando `PermissionError` em cada um dos 7 e conferindo que a pergunta chega à UI.

## 6. O que muda para o usuário

**Antes:** gravar com a planilha aberta falha em 7 lugares sem explicar; a pausa de login tem
duas aparências diferentes conforme a tela; 4 dessas janelas travam o app e não minimizam.

**Depois:** qualquer falha de gravação por arquivo aberto para, diz qual arquivo está travado e
espera — com "Tentar Novamente" e "Ignorar e Continuar", em todo módulo. Toda pausa de ação
manual tem a mesma cara, minimiza, e não impede de usar a janela principal.

## 7. Riscos

**As 4 telas deixam de travar o app.** É o objetivo, mas é mudança de comportamento: dá para
clicar na janela principal enquanto a pausa está aberta. As 3 telas que já usam o modelo se
comportam assim há tempos — não é território novo.

**`Ignorar e Continuar` num ponto que antes só falhava.** Nos 7 desprotegidos, o usuário passa
a poder escolher seguir sem salvar. É a mesma escolha que o `upload_conditions` já oferece, e o
resumo do lote (CP 4.4) registra o que não foi salvo.

**Nada disso é testável contra o portal.** Os 4 diálogos de login abrem antes do RPA e não
dependem do portal, então a suíte cobre. Mas, como sempre neste projeto, verde nos testes não
substitui abrir o app — ver `CLAUDE.md`.

## 8. Fora de escopo (registrado, não feito)

- **Grupo 2** (6 janelas de escolha/revisão): adiado por decisão do usuário. Os três defeitos
  medidos ficam registrados para quando for retomado: não minimizam, as tabelas `ttk.Treeview`
  são brancas num app escuro, e `Revisão de PDMs` / `Intervenção Necessária` usam cores fora da
  paleta (verde puro, azul, mostarda, vermelho puro).
- **`JanelaAcaoRobo` chama `wait_window()` dentro do próprio `__init__`**, então construir a
  janela bloqueia quem a construiu. Descoberto ao tentar abri-la para o print — travou o script
  de captura. Vai para `PENDENCIAS.md`.
- **Grupos 3 e 4** (~46 `messagebox`): permanecem nativos.
- **Botões que o usuário pediu para preservar** e que este trabalho não toca: "5. Salvar no
  Excel", "Salvar Alteração", "Salvar Chaves", "Salvar Pesos", "Salvar seleção", "[3] Parar
  Automação e Salvar", "Carregar JSON Salvo no Computador".

## 9. Verificação

1. `bash scripts/check.sh` verde (2849 testes na linha de base + os novos);
2. `python -m pyflakes` nos arquivos tocados — nenhum nome indefinido novo;
3. **abrir o app** e percorrer as 4 janelas de login migradas;
4. teste manual do Excel travado: abrir uma planilha no Excel, rodar um módulo que grava nela,
   confirmar que a janela aparece e que "Tentar Novamente" funciona depois de fechar o arquivo.

O item 4 é o único que prova o requisito do usuário de ponta a ponta, e não há como automatizá-lo
com fidelidade — o `PermissionError` do Windows depende do Excel estar de fato segurando o
arquivo.

r"""
sigft/app/file_dialogs.py — wrappers de `tkinter.filedialog` com memória de
caminho (Checkpoint 1.5 do plano de refatoração, decisão de produto nº 7;
lado UI de `sigft.core.prefs`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.5.

ESCOPO DESTA ETAPA (1ª metade do CP 1.5, aditiva): este módulo nasce aqui,
testado de ponta a ponta com um `dialog_fn` falso — mas NENHUM dos ~34 call
sites de `filedialog.*` em `frontend.py` foi migrado para usá-lo ainda
(migração é a etapa SEGUINTE; ver docs/refatoracao/PENDENCIAS.md).
`frontend.py` NÃO é tocado neste checkpoint.

4 funções, uma por diálogo do `tkinter.filedialog` usado hoje em
`frontend.py`:

  - `ask_open_file`  -> `filedialog.askopenfilename`  (1 arquivo)
  - `ask_open_files` -> `filedialog.askopenfilenames` (N arquivos)
  - `ask_save_file`  -> `filedialog.asksaveasfilename` (salvar 1 arquivo)
  - `ask_directory`  -> `filedialog.askdirectory`      (1 pasta)

Cada wrapper faz 3 coisas em torno do diálogo real:
  1. resolve `initialdir` via `sigft.core.prefs.get_initial_dir(chave,
     categoria)` (ordem: chave > categoria > pasta padrão da chave > `None`
     — ver `core/prefs.py` para o contrato completo);
  2. chama o diálogo (`dialog_fn` injetado, ou — quando `dialog_fn` não é
     passado — a função REAL correspondente de `tkinter.filedialog`);
  3. se o usuário SELECIONOU algo (resultado não-vazio): grava a PASTA
     resultante via `sigft.core.prefs.remember_dir(chave, categoria, pasta)`
     e devolve o resultado (normalizado — ver "Contrato de retorno" abaixo);
     se o usuário CANCELOU (resultado vazio): NÃO grava nada, devolve o
     vazio tal qual.

Contrato de retorno / cancelamento preservado
-----------------------------------------------
Hoje, os ~34 call sites de `frontend.py` já tratam o retorno vazio do
`filedialog` (`""` para os 3 diálogos singulares, `()`/`""` para
`askopenfilenames`, dependendo da versão do Tk — ver nota abaixo) como
"usuário cancelou" (`if p:`/`if f:`/`if ps:`). Estes wrappers preservam essa
forma de retorno — vazio nunca levanta exceção nem vira `None` — e além
disso NORMALIZAM o tipo devolvido:
  - `ask_open_file`/`ask_save_file`/`ask_directory`: sempre `str` (`""`
    quando cancelado).
  - `ask_open_files`: sempre `tuple[str, ...]` (`()` quando cancelado) —
    normaliza uma inconsistência histórica conhecida do Tk, em que
    `askopenfilenames` pode devolver uma `str` vazia (em vez de uma tupla
    vazia) ao cancelar, ou até uma `str` única (em vez de uma tupla de 1
    elemento) quando só um arquivo é escolhido em builds antigos do Tcl/Tk.
Isso é o que garante que a migração futura dos call sites (trocar
`filedialog.askopenfilename(...)` por `file_dialogs.ask_open_file(chave,
categoria, ...)`) seja um replace direto — o `if p:`/`if ps:` que já existe
em cada um continua funcionando sem alteração.

Testabilidade — tkinter fica NA BORDA
----------------------------------------
Este ambiente de teste NÃO TEM tkinter instalado (`ModuleNotFoundError: No
module named 'tkinter'`, confirmado) e este módulo NÃO PODE fazer `import
tkinter`/`from tkinter import filedialog` no TOPO do arquivo — quebraria o
import do módulo inteiro (e de qualquer um que o importe) neste ambiente.
Por isso:
  - o import de `tkinter.filedialog` é PREGUIÇOSO: só acontece DENTRO de
    cada função wrapper, e só quando `dialog_fn` não foi passado — mesmo
    padrão de `openpyxl` em `core/excel/status_sheet.abrir()`.
  - `dialog_fn` é injetável em toda função (parâmetro keyword-only,
    assinatura `(**kwargs) -> str | Sequence[str]`, os mesmos kwargs que a
    função real do `tkinter.filedialog` correspondente aceitaria). Testes
    SEMPRE passam uma função Python simples (fake) que devolve um caminho
    fixo — nunca exercitam o import real do tkinter. Ver
    tests/test_file_dialogs.py.
  - `initialdir`/`title`/`filetypes`/`defaultextension` são passados ao
    diálogo mesmo quando `None`: o mecanismo de opções do tkinter
    (`tkinter.Misc._options`, usado por todo `commondialog.Dialog.show`,
    base de `filedialog.*`) IGNORA silenciosamente qualquer opção com valor
    `None` antes de montar a chamada Tcl — é o mesmo comportamento hoje
    obtido em `frontend.py` quando um `title`/`initialdir` não é informado a
    um diálogo. Não há necessidade (nem vantagem) de montar `kwargs`
    condicionalmente aqui.

`config_path` é parâmetro keyword-only extra (além dos sugeridos pelo
checkpoint), repassado tal qual para `sigft.core.prefs` — não está nos ~34
call sites de produção (que sempre usam o `user_prefs.json` real, o default),
mas é o que permite isolar o `user_prefs.json` de teste (`tmp_path`) sem
precisar de `monkeypatch` em nenhum estado de módulo global.

Só stdlib (`os`, `typing`) + `sigft.core.prefs` — nenhuma dependência pesada,
nenhum `import tkinter` no import deste módulo.
"""

from __future__ import annotations

import os
from typing import Callable, Sequence

from sigft.core import prefs

# Assinatura de um "dialog_fn": aceita os mesmos kwargs que a função real do
# `tkinter.filedialog` correspondente aceitaria (`initialdir`, `title`,
# `filetypes`, `defaultextension`, ...) e devolve o que aquele diálogo
# devolveria (uma `str` para os diálogos singulares; uma sequência de `str`,
# ou uma `str` vazia/única em builds antigas do Tk, para `askopenfilenames`).
DialogFn = Callable[..., object]

# nome do wrapper -> nome da função REAL correspondente em
# `tkinter.filedialog`, resolvida preguiçosamente por `_resolver_dialog_fn`.
_NOME_TK_POR_WRAPPER: dict[str, str] = {
    "ask_open_file": "askopenfilename",
    "ask_open_files": "askopenfilenames",
    "ask_save_file": "asksaveasfilename",
    "ask_directory": "askdirectory",
}


def _resolver_dialog_fn(nome_wrapper: str, dialog_fn: DialogFn | None) -> DialogFn:
    """Devolve `dialog_fn` se foi passado (SEMPRE o caso em teste — ver
    docstring do módulo); senão resolve PREGUIÇOSAMENTE a função real
    correspondente de `tkinter.filedialog` (o import só acontece aqui, e só
    quando de fato vamos abrir um diálogo de verdade)."""
    if dialog_fn is not None:
        return dialog_fn

    from tkinter import filedialog  # import preguiçoso -- ver docstring do módulo

    return getattr(filedialog, _NOME_TK_POR_WRAPPER[nome_wrapper])


def _eh_vazio(resultado: object) -> bool:
    """`True` se `resultado` é a forma "vazia" que os diálogos do tkinter
    usam para sinalizar cancelamento: string vazia (todos os diálogos
    singulares) OU sequência vazia (`askopenfilenames`, que devolve uma
    tupla de caminhos). `None` também conta como vazio, por tolerância extra
    (nenhum diálogo real do tkinter devolve `None`, mas um `dialog_fn` fake
    de teste poderia, por engano ou de propósito)."""
    if resultado is None:
        return True
    if isinstance(resultado, str):
        return resultado == ""
    try:
        return len(resultado) == 0
    except TypeError:
        return False


def ask_open_file(
    chave: str,
    categoria: str,
    *,
    titulo: str | None = None,
    filetypes: Sequence[tuple[str, str]] | None = None,
    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE,
    dialog_fn: DialogFn | None = None,
) -> str:
    """Wrapper com memória de caminho de `tkinter.filedialog.askopenfilename`
    (seleção de 1 arquivo existente para ABRIR/LER).

    `chave`/`categoria` identificam o campo/tipo para a memória de pasta (ver
    `sigft.core.prefs.get_initial_dir`). Devolve o caminho do arquivo
    escolhido, ou `""` se o usuário cancelar — mesmo contrato de retorno do
    `tkinter.filedialog` original, preservado para não quebrar os `if p:` já
    existentes nos call sites de `frontend.py` quando migrarem.
    """
    fn = _resolver_dialog_fn("ask_open_file", dialog_fn)
    initial = prefs.get_initial_dir(chave, categoria, config_path=config_path)

    resultado = fn(initialdir=initial, title=titulo, filetypes=filetypes)
    if _eh_vazio(resultado):
        return ""

    caminho = str(resultado)
    prefs.remember_dir(chave, categoria, os.path.dirname(caminho), config_path=config_path)
    return caminho


def ask_open_files(
    chave: str,
    categoria: str,
    *,
    titulo: str | None = None,
    filetypes: Sequence[tuple[str, str]] | None = None,
    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE,
    dialog_fn: DialogFn | None = None,
) -> tuple[str, ...]:
    """Wrapper com memória de caminho de
    `tkinter.filedialog.askopenfilenames` (seleção de N arquivos existentes).

    Devolve uma tupla com os caminhos escolhidos, ou `()` se o usuário
    cancelar. A pasta lembrada é a do PRIMEIRO arquivo selecionado
    (`os.path.dirname(resultado[0])`) — mesmo comportamento observável de uma
    única chamada ao diálogo, presumindo que os demais arquivos estejam na
    mesma pasta (a UI/OS já os apresenta assim, por ser 1 diálogo só).
    """
    fn = _resolver_dialog_fn("ask_open_files", dialog_fn)
    initial = prefs.get_initial_dir(chave, categoria, config_path=config_path)

    resultado = fn(initialdir=initial, title=titulo, filetypes=filetypes)
    if _eh_vazio(resultado):
        return ()

    if isinstance(resultado, str):
        # Alguns builds antigos do Tcl/Tk devolvem uma STRING única (não uma
        # sequência) quando só 1 arquivo é selecionado -- normaliza para
        # tupla de 1 elemento em vez de iterar caractere a caractere.
        caminhos = (resultado,)
    else:
        caminhos = tuple(str(item) for item in resultado)

    prefs.remember_dir(chave, categoria, os.path.dirname(caminhos[0]), config_path=config_path)
    return caminhos


def ask_save_file(
    chave: str,
    categoria: str,
    *,
    titulo: str | None = None,
    filetypes: Sequence[tuple[str, str]] | None = None,
    defaultextension: str | None = None,
    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE,
    dialog_fn: DialogFn | None = None,
) -> str:
    """Wrapper com memória de caminho de
    `tkinter.filedialog.asksaveasfilename` (escolher onde SALVAR 1 arquivo,
    novo ou existente).

    Devolve o caminho escolhido para salvar, ou `""` se o usuário cancelar.
    """
    fn = _resolver_dialog_fn("ask_save_file", dialog_fn)
    initial = prefs.get_initial_dir(chave, categoria, config_path=config_path)

    resultado = fn(
        initialdir=initial,
        title=titulo,
        filetypes=filetypes,
        defaultextension=defaultextension,
    )
    if _eh_vazio(resultado):
        return ""

    caminho = str(resultado)
    prefs.remember_dir(chave, categoria, os.path.dirname(caminho), config_path=config_path)
    return caminho


def ask_directory(
    chave: str,
    categoria: str,
    *,
    titulo: str | None = None,
    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE,
    dialog_fn: DialogFn | None = None,
) -> str:
    """Wrapper com memória de caminho de `tkinter.filedialog.askdirectory`
    (seleção de 1 pasta).

    Devolve a pasta escolhida, ou `""` se o usuário cancelar. Diferente dos
    outros 3 wrappers, o resultado JÁ É a pasta a lembrar (sem
    `os.path.dirname`) — não há arquivo, só diretório.
    """
    fn = _resolver_dialog_fn("ask_directory", dialog_fn)
    initial = prefs.get_initial_dir(chave, categoria, config_path=config_path)

    resultado = fn(initialdir=initial, title=titulo)
    if _eh_vazio(resultado):
        return ""

    caminho = str(resultado)
    prefs.remember_dir(chave, categoria, caminho, config_path=config_path)
    return caminho

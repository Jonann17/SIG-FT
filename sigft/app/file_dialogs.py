r"""
sigft/app/file_dialogs.py — a memória de pastas dos diálogos de arquivo
(Checkpoint 1.5 do plano de refatoração, decisão de produto nº 7; lado UI de
`sigft.core.prefs`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.5.

Nasceu como os wrappers de diálogo da interface antiga; desde 2026-10-15 (a
interface antiga saiu do SIG-FT) é só a LÓGICA, sem biblioteca gráfica: o
diálogo em si vem de quem chama, pelo `dialog_fn`. Quem o fornece é
`sigft/app_qt/file_dialogs.py`, com o `QFileDialog` -- é por lá que as telas
chamam.

4 funções, uma por tipo de diálogo:

  - `ask_open_file`  (1 arquivo)
  - `ask_open_files` (N arquivos)
  - `ask_save_file`  (salvar 1 arquivo)
  - `ask_directory`  (1 pasta)

Cada uma faz 3 coisas em torno do diálogo:
  1. resolve `initialdir` — um override CONTEXTUAL explícito (parâmetro
     `initialdir`, ver seção própria abaixo) se houver e for válido; senão
     via `sigft.core.prefs.get_initial_dir(chave, categoria)` (ordem: chave
     > categoria > pasta padrão da chave > `None` — ver `core/prefs.py` para
     o contrato completo);
  2. chama o diálogo (`dialog_fn`, obrigatório);
  3. se o usuário SELECIONOU algo (resultado não-vazio): grava a PASTA
     resultante via `sigft.core.prefs.remember_dir(chave, categoria, pasta)`
     e devolve o resultado (normalizado — ver "Contrato de retorno" abaixo);
     se o usuário CANCELOU (resultado vazio): NÃO grava nada, devolve o
     vazio tal qual.

Override contextual de `initialdir` (2ª metade do CP 1.5)
-----------------------------------------------------------
Além da resolução via `sigft.core.prefs.get_initial_dir` acima, as 4 funções
aceitam um parâmetro extra `initialdir` (keyword-only, `str |
os.PathLike[str] | None = None`) para o caso em que quem CHAMA já sabe qual é
a pasta certa por CONTEXTO IMEDIATO da própria tela — não por memória entre
sessões. Caso de uso real: na tela do PDM (`_op1_modificados`), o seletor do
"arquivo PDM específico" abre na pasta que o usuário ACABOU de escolher no
campo "Pasta (PDMs From Itaipu)" da MESMA tela, momentos antes — informação
que `prefs` não tem como conhecer.

Regra de prioridade: se `initialdir` for passado E apontar para uma pasta que
existe DE FATO no disco (`os.path.isdir`), ele VENCE — a resolução de
`prefs.get_initial_dir` nem chega a ser chamada nesse caso. Se `initialdir`
for omitido (`None`, o default) OU apontar para algo que não é uma pasta
válida (inexistente, string vazia, arquivo em vez de pasta), o comportamento
cai INTEGRALMENTE para a resolução normal via `prefs.get_initial_dir` — ou
seja, é sempre seguro passar um valor que pode estar vazio/desatualizado
(nenhuma exceção é levantada). Em AMBOS os casos, o `remember_dir` na SAÍDA
continua acontecendo normalmente — este parâmetro só influencia onde o
diálogo ABRE, nunca o que é lembrado depois.

Contrato de retorno / cancelamento
------------------------------------
As telas tratam o retorno vazio como "usuário cancelou" (`if p:`/`if ps:`).
Vazio nunca levanta exceção nem vira `None`, e o tipo devolvido é
normalizado:
  - `ask_open_file`/`ask_save_file`/`ask_directory`: sempre `str` (`""`
    quando cancelado).
  - `ask_open_files`: sempre `tuple[str, ...]` (`()` quando cancelado) — um
    diálogo que devolva uma `str` única (em vez de uma sequência de 1) é
    normalizado para tupla de 1, em vez de iterar caractere a caractere.

O `dialog_fn`
-------------
Parâmetro keyword-only de toda função, assinatura `(**kwargs) -> str |
Sequence[str]`. Recebe `initialdir`, `title`, `filetypes` (e
`defaultextension`, no salvar), mesmo quando `None`: quem traduz para o
diálogo de verdade decide o que fazer com cada um. Os testes passam uma
função Python simples (fake) que devolve um caminho fixo — ver
tests/test_file_dialogs.py.

`config_path` é parâmetro keyword-only extra, repassado tal qual para
`sigft.core.prefs` — a produção usa o `user_prefs.json` real (o default), e
os testes isolam o deles (`tmp_path`) sem `monkeypatch` em estado global.

Só stdlib (`os`, `typing`) + `sigft.core.prefs`.
"""

from __future__ import annotations

import os
from typing import Callable, Sequence

from sigft.core import prefs

# Assinatura de um "dialog_fn": recebe `initialdir`, `title`, `filetypes` (e
# `defaultextension`, no salvar) e devolve o caminho escolhido (`str`), ou os
# caminhos (sequência de `str`) no de vários arquivos; vazio = cancelou.
DialogFn = Callable[..., object]


def _resolver_dialog_fn(nome_wrapper: str, dialog_fn: DialogFn | None) -> DialogFn:
    """O diálogo é da interface: sem `dialog_fn` não há o que abrir. Falha
    alto, com o caminho certo, em vez de abrir nada em silêncio."""
    if dialog_fn is None:
        raise TypeError(
            f"{nome_wrapper}: falta o `dialog_fn` (o diálogo de verdade). As telas "
            "chamam por `sigft.app_qt.file_dialogs`, que fornece o do Qt.")
    return dialog_fn


def _eh_vazio(resultado: object) -> bool:
    """`True` se `resultado` é a forma "vazia" que um diálogo usa para
    sinalizar cancelamento: string vazia (os diálogos singulares) OU sequência
    vazia (o de vários arquivos). `None` também conta como vazio, por
    tolerância extra (um `dialog_fn` fake de teste poderia devolvê-lo)."""
    if resultado is None:
        return True
    if isinstance(resultado, str):
        return resultado == ""
    try:
        return len(resultado) == 0
    except TypeError:
        return False


def _resolver_initialdir(
    chave: str,
    categoria: str,
    initialdir: str | os.PathLike[str] | None,
    *,
    config_path: str | os.PathLike[str],
) -> str | None:
    """Resolve o `initialdir` de fato repassado ao diálogo: um override
    CONTEXTUAL explícito (parâmetro `initialdir` de quem chama) tem
    PRIORIDADE sobre a memória de `sigft.core.prefs`, mas só quando aponta
    para uma pasta que existe DE FATO no disco (`os.path.isdir`); caso
    contrário (`None`, string vazia, caminho inexistente ou que não é uma
    pasta) cai integralmente para a resolução normal via
    `prefs.get_initial_dir` (chave > categoria > pasta padrão da chave >
    `None`) — ver docstring do módulo, seção "Override contextual de
    `initialdir`". Nunca levanta exceção: um `initialdir` de tipo
    inesperado (não `str`/`os.PathLike`) é tratado como ausente."""
    if initialdir is not None:
        try:
            candidato = os.fspath(initialdir)
        except TypeError:
            candidato = ""
        if candidato and os.path.isdir(candidato):
            return candidato

    return prefs.get_initial_dir(chave, categoria, config_path=config_path)


def ask_open_file(
    chave: str,
    categoria: str,
    *,
    titulo: str | None = None,
    filetypes: Sequence[tuple[str, str]] | None = None,
    initialdir: str | os.PathLike[str] | None = None,
    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE,
    dialog_fn: DialogFn | None = None,
) -> str:
    """Seleção de 1 arquivo existente para ABRIR/LER, com memória de caminho.

    `chave`/`categoria` identificam o campo/tipo para a memória de pasta (ver
    `sigft.core.prefs.get_initial_dir`). `initialdir` é um override
    CONTEXTUAL opcional que vence a memória quando aponta para uma pasta
    válida (ver docstring do módulo). Devolve o caminho do arquivo
    escolhido, ou `""` se o usuário cancelar (os `if p:` das telas).
    """
    fn = _resolver_dialog_fn("ask_open_file", dialog_fn)
    initial = _resolver_initialdir(chave, categoria, initialdir, config_path=config_path)

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
    initialdir: str | os.PathLike[str] | None = None,
    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE,
    dialog_fn: DialogFn | None = None,
) -> tuple[str, ...]:
    """Seleção de N arquivos existentes, com memória de caminho.

    `initialdir` é um override CONTEXTUAL opcional que vence a memória
    quando aponta para uma pasta válida (ver docstring do módulo). Devolve
    uma tupla com os caminhos escolhidos, ou `()` se o usuário cancelar. A
    pasta lembrada é a do PRIMEIRO arquivo selecionado
    (`os.path.dirname(resultado[0])`) — mesmo comportamento observável de uma
    única chamada ao diálogo, presumindo que os demais arquivos estejam na
    mesma pasta (a UI/OS já os apresenta assim, por ser 1 diálogo só).
    """
    fn = _resolver_dialog_fn("ask_open_files", dialog_fn)
    initial = _resolver_initialdir(chave, categoria, initialdir, config_path=config_path)

    resultado = fn(initialdir=initial, title=titulo, filetypes=filetypes)
    if _eh_vazio(resultado):
        return ()

    if isinstance(resultado, str):
        # Um diálogo que devolva uma STRING única (não uma sequência) quando
        # só 1 arquivo é selecionado -- normaliza para tupla de 1 elemento em
        # vez de iterar caractere a caractere.
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
    initialdir: str | os.PathLike[str] | None = None,
    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE,
    dialog_fn: DialogFn | None = None,
) -> str:
    """Escolher onde SALVAR 1 arquivo (novo ou existente), com memória de
    caminho.

    `initialdir` é um override CONTEXTUAL opcional que vence a memória
    quando aponta para uma pasta válida (ver docstring do módulo). Devolve
    o caminho escolhido para salvar, ou `""` se o usuário cancelar.
    """
    fn = _resolver_dialog_fn("ask_save_file", dialog_fn)
    initial = _resolver_initialdir(chave, categoria, initialdir, config_path=config_path)

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
    initialdir: str | os.PathLike[str] | None = None,
    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE,
    dialog_fn: DialogFn | None = None,
) -> str:
    """Seleção de 1 pasta, com memória de caminho.

    `initialdir` é um override CONTEXTUAL opcional que vence a memória
    quando aponta para uma pasta válida (ver docstring do módulo). Devolve
    a pasta escolhida, ou `""` se o usuário cancelar. Diferente dos outros 3
    wrappers, o resultado JÁ É a pasta a lembrar (sem `os.path.dirname`) —
    não há arquivo, só diretório.
    """
    fn = _resolver_dialog_fn("ask_directory", dialog_fn)
    initial = _resolver_initialdir(chave, categoria, initialdir, config_path=config_path)

    resultado = fn(initialdir=initial, title=titulo)
    if _eh_vazio(resultado):
        return ""

    caminho = str(resultado)
    prefs.remember_dir(chave, categoria, caminho, config_path=config_path)
    return caminho

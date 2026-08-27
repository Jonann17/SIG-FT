"""Dublê de `tkinter` para os testes da Fase 7.

`sigft/app/widgets/pickers.py` importa `tkinter` no TOPO, e isso é deliberado:
a `Listbox` das filas de ficha não tem equivalente no CustomTkinter, então o
módulo não tem como se livrar dela.

`sigft/app/file_dialogs.py` resolve o mesmo problema de outro jeito (import
preguiçoso dentro da função) porque lá o tkinter só aparece no momento de
abrir o diálogo. Num widget que É uma Listbox, não dá.

Daí este dublê: a suíte roda tanto na máquina do desenvolvedor quanto no
contêiner sem tkinter e sem display, e nos dois casos exercita a mesma coisa.

Fidelidade: só `Listbox`, `Scrollbar` e as constantes que o `pickers.py` usa.
A `Listbox` guarda os itens numa lista de verdade, para que o teste possa
afirmar O QUE apareceu na tela — que é a metade interessante da fila de
fichas.
"""
from __future__ import annotations

# Constantes do tkinter que o pickers.py referencia.
END = "end"
EXTENDED = "extended"
MULTIPLE = "multiple"
SINGLE = "single"


class _WidgetTk:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = dict(kwargs)

    def pack(self, **kwargs):
        self.chamadas_pack = getattr(self, "chamadas_pack", [])
        self.chamadas_pack.append(kwargs)

    def grid(self, **kwargs):
        pass

    def config(self, **kwargs):
        self.kwargs.update(kwargs)

    configure = config


class Listbox(_WidgetTk):
    """Guarda os itens de verdade — é o que o teste da fila precisa ver."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.itens: list[str] = []
        self._selecao: tuple[int, ...] = ()

    def insert(self, indice, texto):
        if indice == END:
            self.itens.append(texto)
        else:
            self.itens.insert(int(indice), texto)

    def delete(self, inicio, fim=None):
        if inicio == 0 and fim == END:
            self.itens.clear()
        else:
            del self.itens[int(inicio)]

    def curselection(self):
        return self._selecao

    def selecionar(self, *indices):
        """Só do dublê: simula o usuário marcando linhas."""
        self._selecao = tuple(indices)

    def size(self):
        return len(self.itens)

    def get(self, inicio, fim=None):
        if fim is None:
            return self.itens[int(inicio)]
        return list(self.itens)

    def yview(self, *args):
        pass


class Scrollbar(_WidgetTk):
    def set(self, *args):
        pass


class Frame(_WidgetTk):
    pass


class Tk(_WidgetTk):
    pass


class StringVar:
    def __init__(self, value="", **kwargs):
        self._valor = value

    def get(self):
        return self._valor

    def set(self, valor):
        self._valor = valor


# =============================================================================
# tkinter.filedialog
# =============================================================================
# Precisa existir como ATRIBUTO deste módulo, e não só em
# `sys.modules["tkinter.filedialog"]`: `from tkinter import filedialog`
# procura o atributo no módulo-pai primeiro, e um dublê que não é um pacote de
# verdade nunca chega ao `sys.modules`.
#
# `sigft/app/file_dialogs.py` resolve estas quatro por nome
# (`_NOME_TK_POR_WRAPPER`) e `tests/test_file_dialogs.py` compara a função
# resolvida com `getattr(filedialog, nome)` — os dois lados leem daqui, então
# a identidade bate.
#
# Nenhuma delas ABRE nada: um teste que abrisse um seletor de pastas de
# verdade na tela de quem roda a suíte já foi um defeito real deste projeto
# (ver o docstring de `test_sem_dialog_fn_resolve_a_funcao_real_do_tkinter`).
class _FileDialogFalso:
    """Namespace com as quatro funções que o `file_dialogs` resolve."""

    @staticmethod
    def askopenfilename(**kwargs):
        return ""

    @staticmethod
    def askopenfilenames(**kwargs):
        return ()

    @staticmethod
    def asksaveasfilename(**kwargs):
        return ""

    @staticmethod
    def askdirectory(**kwargs):
        return ""


filedialog = _FileDialogFalso()


class _MessageBoxFalso:
    """Nenhuma caixa de verdade: devolve o "sim" silencioso e registra."""

    def __init__(self):
        self.chamadas = []

    def _registrar(self, tipo, titulo, mensagem):
        self.chamadas.append((tipo, titulo, mensagem))

    def showinfo(self, titulo="", mensagem="", **kwargs):
        self._registrar("info", titulo, mensagem)

    def showwarning(self, titulo="", mensagem="", **kwargs):
        self._registrar("warning", titulo, mensagem)

    def showerror(self, titulo="", mensagem="", **kwargs):
        self._registrar("error", titulo, mensagem)

    def askyesno(self, titulo="", mensagem="", **kwargs):
        self._registrar("askyesno", titulo, mensagem)
        return True


messagebox = _MessageBoxFalso()


# =============================================================================
# tkinter.ttk
# =============================================================================
# `Treeview` é a tabela dos popups de seleção (`TabelaSelecaoDialog`). Guarda
# as linhas e a seleção de verdade: o teste precisa afirmar QUE LINHAS voltam
# do diálogo, e é aí que mora o defeito clássico — devolver o índice da tela
# em vez do índice do dado.
class Treeview(_WidgetTk):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.linhas: dict = {}
        self.ordem: list = []
        self.cabecalhos: dict = {}
        self.colunas_config: dict = {}
        self._selecao: list = []

    def heading(self, coluna, **kwargs):
        self.cabecalhos[coluna] = kwargs.get("text", "")

    def column(self, coluna, **kwargs):
        self.colunas_config[coluna] = kwargs

    def insert(self, pai, indice, iid=None, values=(), **kwargs):
        chave = str(iid)
        self.linhas[chave] = tuple(values)
        self.ordem.append(chave)
        return chave

    def delete(self, *iids):
        for iid in iids:
            self.linhas.pop(str(iid), None)
            if str(iid) in self.ordem:
                self.ordem.remove(str(iid))

    def get_children(self, item=""):
        return tuple(self.ordem)

    def selection(self):
        return tuple(self._selecao)

    def selection_add(self, *iids):
        for iid in iids:
            if str(iid) not in self._selecao:
                self._selecao.append(str(iid))

    def selection_set(self, *iids):
        self._selecao = [str(i) for i in iids]

    def yview(self, *args):
        pass

    def xview(self, *args):
        pass


class _TtkFalso:
    Treeview = Treeview
    Scrollbar = Scrollbar
    Frame = Frame


ttk = _TtkFalso()


# =============================================================================
# tkinter.simpledialog
# =============================================================================
# Usado por `views/analyzer.py`, `views/lmr.py` e `views/janelas.py` para pedir
# um valor solto ao usuário. Como o `messagebox`, registra a chamada e devolve
# um valor fixo -- nada abre.
class _SimpleDialogFalso:
    def __init__(self):
        self.chamadas = []
        self.resposta = None

    def askstring(self, titulo="", prompt="", **kwargs):
        self.chamadas.append(("askstring", titulo, prompt))
        return self.resposta

    def askinteger(self, titulo="", prompt="", **kwargs):
        self.chamadas.append(("askinteger", titulo, prompt))
        return self.resposta

    def askfloat(self, titulo="", prompt="", **kwargs):
        self.chamadas.append(("askfloat", titulo, prompt))
        return self.resposta


simpledialog = _SimpleDialogFalso()

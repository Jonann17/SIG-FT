"""Dublê de `customtkinter` para os testes da Fase 7.

Por que um dublê ESCRITO À MÃO, e não o `MagicMock` que o `conftest.py` usa
para as outras dependências pesadas
------------------------------------------------------------------------
Duas razões, e a segunda é a que importa:

1. **`MagicMock` não serve de classe-base.** `class ConsoleFrame(ctk.CTkTextbox)`
   com um `MagicMock` no lugar levanta `TypeError` no import — o módulo nem
   carrega.

2. **O `after()` precisa ENFILEIRAR, não executar.** É nisso que o dublê ganha
   do CustomTkinter de verdade: aqui o teste consegue afirmar que `log()`
   *agendou* o trabalho em vez de mexer no widget na hora. Com o Tk real, um
   `after(0, ...)` executado no fim é indistinguível de um `insert()` direto —
   e distinguir os dois É o aceite do CP 7.1 ("`log()` thread-safe único").
   Ver `processar_eventos()`.

Também torna a suíte determinística nos dois ambientes onde ela roda: a
máquina do desenvolvedor (com CustomTkinter e display) e o contêiner (sem
nenhum dos dois). Sem isso, testar widget dependeria de haver display.

Fidelidade: só o necessário para o CP 7.1. Não desenha, não mede, não posiciona
— registra o que foi chamado e com quê.
"""
from __future__ import annotations


class _Widget:
    """Base de todos os dublês: guarda master/kwargs e aceita as chamadas de
    geometria sem fazer nada."""

    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = dict(kwargs)
        self.filhos: list = []
        # Fila do `after`: a lista de (func, args) ainda NÃO executados.
        # Compartilhada com a raiz para que o teste possa drenar tudo de um
        # ponto só, como faz o mainloop do Tk.
        self.pendentes: list = []
        self.chamadas_grid: list = []
        self.chamadas_pack: list = []
        self.destruido = False
        if isinstance(master, _Widget):
            master.filhos.append(self)

    # -- geometria (registradas, para o teste poder conferir) ----------------
    def grid(self, **kwargs):
        self.chamadas_grid.append(kwargs)

    def pack(self, **kwargs):
        self.chamadas_pack.append(kwargs)

    def grid_columnconfigure(self, indice, **kwargs):
        pass

    def grid_rowconfigure(self, indice, **kwargs):
        pass

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)

    def cget(self, chave):
        return self.kwargs.get(chave)

    def destroy(self):
        self.destruido = True

    # -- agendamento --------------------------------------------------------
    def after(self, delay, func=None, *args):
        """Enfileira em vez de executar — é o ponto do dublê.

        O `_Widget` raiz é quem guarda a fila, para que o teste drene tudo com
        uma chamada só (`processar_eventos()`), sem precisar saber qual widget
        agendou o quê.
        """
        if func is not None:
            self._raiz().pendentes.append((func, args))
        return "after#dublê"

    def _raiz(self) -> "_Widget":
        no = self
        while isinstance(no.master, _Widget):
            no = no.master
        return no

    def processar_eventos(self, maximo: int = 1000) -> int:
        """Executa o que o `after` enfileirou — o papel do mainloop do Tk.

        Devolve quantas tarefas rodaram. `maximo` corta laço infinito caso uma
        tarefa reagende outra.
        """
        raiz = self._raiz()
        executadas = 0
        while raiz.pendentes and executadas < maximo:
            func, args = raiz.pendentes.pop(0)
            func(*args)
            executadas += 1
        return executadas


class CTkBaseClass(_Widget):
    pass


class CTkFrame(_Widget):
    pass


class CTkScrollableFrame(_Widget):
    pass


class CTkLabel(_Widget):
    pass


class CTkButton(_Widget):
    pass


class CTkEntry(_Widget):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self._valor = ""

    def get(self):
        return self._valor

    def insert(self, indice, texto):
        self._valor += str(texto)

    def delete(self, inicio, fim=None):
        self._valor = ""


class CTkProgressBar(_Widget):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.valor = 0

    def set(self, valor):
        self.valor = valor


class CTkTextbox(_Widget):
    """O dublê que mais importa: acumula o texto inserido, para o teste poder
    afirmar o FORMATO exato da linha de log."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.texto = ""
        self.viu_o_fim = 0

    def insert(self, indice, texto):
        if self.destruido:
            raise RuntimeError("widget destruído")
        self.texto += str(texto)

    def see(self, indice):
        self.viu_o_fim += 1

    def get(self, inicio="1.0", fim="end"):
        return self.texto

    def delete(self, inicio, fim=None):
        self.texto = ""


class CTkToplevel(_Widget):
    pass


class CTk(_Widget):
    pass


class CTkFont:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class CTkImage:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class CTkCheckBox(_Widget):
    pass


class CTkComboBox(_Widget):
    pass


class CTkOptionMenu(_Widget):
    pass


class CTkTabview(_Widget):
    def add(self, nome):
        return CTkFrame(self)


class CTkSegmentedButton(_Widget):
    pass


class StringVar:
    def __init__(self, value="", **kwargs):
        self._valor = value

    def get(self):
        return self._valor

    def set(self, valor):
        self._valor = valor


class BooleanVar:
    def __init__(self, value=False, **kwargs):
        self._valor = value

    def get(self):
        return self._valor

    def set(self, valor):
        self._valor = valor


def set_appearance_mode(modo):
    pass


def set_default_color_theme(tema):
    pass

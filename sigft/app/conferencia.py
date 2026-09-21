"""`--conferir-pacote`: o bundle consegue importar o que o app precisa?

Módulo **deliberadamente pobre**: só stdlib, nenhum import do resto do `sigft`,
nada de tkinter. E isso é o ponto inteiro.

Por que ele existe separado do `main.py`
----------------------------------------
A primeira versão disto morava no `main.py`, e o teste que a exercitava falhou
assim:

    ModuleNotFoundError: No module named 'tkinter'

O `main.py` importa tkinter, CustomTkinter, PIL e as 12 telas no topo. Rodar
`--conferir-pacote` por lá significa pagar todos esses imports **antes** de
conseguir relatar qualquer coisa — ou seja: **num bundle quebrado, a
conferência quebra junto**, e o passo do CI morre com um traceback em vez de
dizer o que está faltando.

Era o contrário do que ela existe para fazer. Uma conferência de pacote tem de
funcionar justamente quando o pacote está incompleto.

Como é usada
------------
No workflow de Release, no Windows, contra o `.exe` recém-compilado:

    SIG-FT.exe --conferir-pacote

O `SIG-FT.spec` usa `console=False`, e um `.exe` sem console **não se prende ao
terminal**: nem a saída nem o `$LASTEXITCODE` chegam por uma chamada direta do
PowerShell. Por isso o relatório é **gravado em arquivo**, e o workflow o lê.
"""
from __future__ import annotations

import importlib.util
import sys

# O que, faltando no bundle, derruba o app NO USO e não na abertura — o caso
# mais caro, porque a pessoa descobre no meio do trabalho, com o navegador já
# aberto ou a planilha já carregada.
MODULOS_ESSENCIAIS = [
    # o próprio pacote
    "sigft.config",
    "sigft.core.rede",
    "sigft.core.dados_usuario",
    "sigft.services.autospec",
    "sigft.services.cria_fichas",
    # as dependências pesadas que o PyInstaller pode não coletar sozinho
    "pandas",
    "openpyxl",
    "playwright",
    "requests",
    "customtkinter",
    "PIL",
    "fitz",           # pymupdf: primeira camada da leitura de PDF
    "bs4",
    "google.generativeai",
]

ARQUIVO_CONFERENCIA = "conferencia-do-pacote.txt"

# O relatório do `--smoke`, pela mesma razão que o de cima existe. Ver
# `gravar_relatorio`.
ARQUIVO_JANELA = "conferencia-da-janela.txt"


def gravar_relatorio(nome: str, texto: str) -> None:
    """Grava um diagnóstico do `.exe` no diretório de trabalho.

    Existe porque o `SIG-FT.spec` usa `console=False`, e **um `.exe` sem
    console não se prende ao terminal**: nem o que ele imprime nem o
    `$LASTEXITCODE` chegam por uma chamada direta do PowerShell. Um
    diagnóstico que só vá para a saída padrão simplesmente não existe para
    quem lê o log do CI.

    A regra estava implementada no `--conferir-pacote` e esquecida no
    `--smoke`, e o resultado apareceu no run #3 de 2026-09-21: a janela não
    montou, o passo reprovou com `codigo 1` e **mais nada**. Uma checagem que
    falha sem dizer por quê custa o mesmo build e não diz nada — cada hipótese
    vira uma rodada inteira. Por isso virou função com nome: o próximo
    diagnóstico que o `.exe` fizer de si mesmo usa esta, e não reaprende a
    lição.

    Nunca levanta. Ela roda no caminho de erro; deixar o relatório quebrar o
    relato seria trocar um diagnóstico ruim por nenhum.
    """
    try:
        with open(nome, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto.rstrip() + "\n")
    except OSError as e:  # noqa: BLE001 — ver docstring
        print(f"(nao foi possivel gravar o {nome}: {e})", file=sys.stderr)


def conferir_pacote(modulos: list[str] | None = None) -> tuple[str, bool]:
    """`(relatório, tudo_certo)` — o bundle consegue importar o que precisa?

    Usa `importlib.util.find_spec`, e **não** `importlib.metadata`, por dois
    motivos que o Corella Suite pagou em produção:

    * `importlib.metadata` não viaja para dentro do `.exe` — o `.dist-info` só
      entra com `copy_metadata` no `.spec`. Então `version("pandas")` levanta
      `PackageNotFoundError` **com o pandas funcionando**, e foi assim que um
      diagnóstico passou a dizer "pandas: não instalado" num app que usava
      pandas o tempo todo;
    * `find_spec` **não importa** o módulo, o que importa num app que não pode
      carregar o pandas inteiro só para conferir.

    E a pergunta certa nunca foi "o arquivo está lá?": módulo Python puro não
    vira pasta em `_internal/` — o PyInstaller só deixa lá o que tem extensão
    binária ou arquivo de dados, e o resto vai para dentro do PYZ. Uma
    conferência por arquivo reprovaria um build perfeitamente bom.
    """
    alvos = list(modulos if modulos is not None else MODULOS_ESSENCIAIS)

    try:
        from sigft import _build_info

        cabecalho = [f"Conferencia do pacote SIG-FT v{_build_info.VERSAO}",
                     f"  ({_build_info.descricao()})", ""]
    except Exception:  # noqa: BLE001 — se nem isso importa, o relatório diz
        cabecalho = ["Conferencia do pacote SIG-FT",
                     "  (nao foi possivel ler a versao do build)", ""]

    linhas = list(cabecalho)
    faltando: list[str] = []

    for nome in alvos:
        try:
            achado = importlib.util.find_spec(nome) is not None
        except (ImportError, ValueError, AttributeError):
            # Um pacote-pai ausente faz `find_spec` levantar em vez de devolver
            # `None`. Para esta pergunta, levantar e devolver `None` são a
            # mesma resposta: não está lá.
            achado = False
        linhas.append(f"  {'OK   ' if achado else 'FALTA'}  {nome}")
        if not achado:
            faltando.append(nome)

    if faltando:
        linhas += ["", f"FALTANDO {len(faltando)}: " + ", ".join(faltando)]
    else:
        linhas += ["", f"Todos os {len(alvos)} modulos essenciais estao no pacote."]

    return "\n".join(linhas), not faltando


FLAG = "--conferir-pacote"


def despachar_cedo(argv: list[str] | None = None) -> None:
    """Trata `--conferir-pacote` e NÃO volta, se a flag estiver presente.

    Chamada no **topo de cada ponto de entrada**, antes dos imports pesados.
    Existe como função para que a flag tenha UM dono: em 2026-09-21 o despacho
    estava escrito à mão dentro de um `if __name__ == "__main__"` no `main.py`
    — que o bundle não executa, porque quem o `SIG-FT.spec` empacota é o
    `frontend.py`. A condição era sempre falsa, o `.exe` ignorava a flag e
    abria a janela, e o passo do Release ficava pendurado esperando um
    aplicativo que estava ali, aberto, esperando o usuário.

    Ver `tests/test_ponto_de_entrada.py`, que roda o script apontado pelo
    `Analysis(...)` do spec em vez de escolher um arquivo a dedo.
    """
    if FLAG in (sys.argv if argv is None else argv):
        sys.exit(cli())


def cli() -> int:
    """Grava o relatório e devolve o código de saída (0 = tudo certo)."""
    relatorio, tudo_certo = conferir_pacote()
    gravar_relatorio(ARQUIVO_CONFERENCIA, relatorio)
    print(relatorio)
    return 0 if tudo_certo else 1

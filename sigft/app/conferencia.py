"""`--conferir-pacote`: o bundle consegue importar o que o app precisa?

Módulo **deliberadamente pobre**: só stdlib, nenhum import do resto do `sigft`,
nada de biblioteca gráfica. E isso é o ponto inteiro.

Por que ele existe separado do `main.py`
----------------------------------------
A primeira versão disto morava no `main.py` da interface (na época, a antiga),
e o teste que a exercitava falhou com `ModuleNotFoundError` da biblioteca
gráfica, que o contêiner não tinha.

Aquele `main.py` importava a biblioteca gráfica, PIL e as 12 telas no topo. Rodar
`--conferir-pacote` por lá significa pagar todos esses imports **antes** de
conseguir relatar qualquer coisa — ou seja: **num bundle quebrado, a
conferência quebra junto**, e o passo do CI morre com um traceback em vez de
dizer o que está faltando.

Era o contrário do que ela existe para fazer. Uma conferência de pacote tem de
funcionar justamente quando o pacote está incompleto.

As duas conferências que precisam CARREGAR algo de verdade -- o tradutor
(`conferir_tradutor`) e a Qt (`conferir_qt`) -- importam o que usam dentro da
função, e nunca levantam: o que falhar vira linha de FALHA no relatório.

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
import os
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
    # o editor que grava nos `_STATUS_PMIB` sem apagar comentário (2026-10-05).
    # O `StatusPMIB` só o importa na hora de gravar: faltando no bundle, o app
    # abre e quebra na primeira planilha que tentar marcar.
    "lxml.etree",
    "sigft.core.excel.cirurgico",
    "playwright",
    # as regras do portal conferidas antes do navegador (2026-10-16, R2). As
    # quatro telas de robô as importam: faltando, a tela não abre.
    "pydantic",
    "pydantic_core",
    "sigft.core.pmib_regras",
    "requests",
    "fitz",           # pymupdf: primeira camada da leitura de PDF
    "bs4",
    "google.generativeai",
    # o tradutor local da tela 4.2 (2026-09-25). O motor os importa por NOME
    # (`importlib`), o que o PyInstaller não enxerga sozinho.
    "ctranslate2",
    "sentencepiece",
    "sigft.core.tradutor_local",
    "sigft.services.translator",
    # a interface Qt, a oficial desde o corte (E6.1, 2026-10-10).
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
    "sigft.app_qt.main",
    # As telas Qt são importadas na PRIMEIRA visita (as fábricas de
    # `sigft.app_qt.main.TELAS`): uma que ficasse fora do pacote só apareceria
    # quando alguém clicasse no menu. `tests/test_conferencia_do_pacote.py`
    # trava esta lista com o registro: tela nova em `TELAS` entra aqui também.
    "sigft.app_qt.views.home",
    "sigft.app_qt.views.translator",
    "sigft.app_qt.views.aplicacao_lmr",
    "sigft.app_qt.views.cria_fichas",
    "sigft.app_qt.views.pdm",
    "sigft.app_qt.views.analyzer",
    "sigft.app_qt.views.upload_conditions",
    "sigft.app_qt.views.upload_tech_specs",
    "sigft.app_qt.views.correcao_pdm",
    "sigft.app_qt.views.upload_fotos",
    "sigft.app_qt.views.copia_fichas",
    "sigft.app_qt.views.autospec",
    # O PMIB Manager é a seção de abas: ela importa a Gestão PMIB, a Conferência
    # de Revisões e a Revisão no AMP (2026-10-27).
    "sigft.app_qt.views.gestao_sobressalentes",
    "sigft.app_qt.views.busca_pmib",
    # A boas-vindas (2026-10-28): página da pilha, fora do menu.
    "sigft.app_qt.views.boas_vindas",
]

# A frase que a conferência traduz dentro do .exe, e o que a tradução tem de
# conter. Frase simples de propósito: o que se confere é "o modelo carrega e
# traduz", não a qualidade (essa tem teste próprio).
FRASE_DE_PROVA = "Aço inoxidável"
ESPERADO_NA_PROVA = "acero inoxidable"

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

    E a pergunta certa nunca foi "o arquivo está lá?". Até a 1.3.1-rc.1 o módulo
    Python puro de terceiros não virava pasta em `_internal/` — ia para dentro
    do PYZ, e uma conferência por arquivo reprovaria um build perfeitamente
    bom. Desde 2026-10-27 (`noarchive=True` no `SIG-FT.spec`) todo módulo vira
    `.pyc` solto, mas `find_spec` responde igual nos dois formatos — e é a
    pergunta que importa: o aplicativo consegue importar?
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


def conferir_tradutor() -> tuple[str, bool]:
    """`(linha do relatório, funcionou)` -- o tradutor local traduz, aqui?

    `find_spec` só diz que o `ctranslate2` está no pacote. Não diz se a DLL
    dele carrega no Windows nem se o modelo (~218 MB) entrou em
    `modelos/tradutor_pt_es`. Por isso a prova é traduzir uma frase de
    verdade: se falhar, o release para antes de publicar um tradutor que não
    traduz.
    """
    try:
        from sigft.core import tradutor_local

        pasta = tradutor_local.localizar_modelo()
        [saida] = tradutor_local.TradutorLocal(pasta).traduzir([FRASE_DE_PROVA])
    except Exception as erro:  # noqa: BLE001 -- o relatório diz o quê
        return f"  FALHA  tradutor local: {type(erro).__name__}: {erro}", False
    funcionou = ESPERADO_NA_PROVA in saida.lower()
    marca = "OK   " if funcionou else "FALHA"
    return f"  {marca}  tradutor local: '{FRASE_DE_PROVA}' -> '{saida}' ({pasta})", funcionou


# -- A interface Qt (E6.2) ------------------------------------------------------

MODULOS_DA_QT = ("PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets")

# A plataforma que o Qt usa em cada sistema quando `QT_QPA_PLATFORM` não diz
# outra. O plugin dela tem de ir no pacote: `empacotamento/hooks/
# hook-PySide6.QtGui.py` a mantém, e um teste trava as duas pontas juntas.
PLATAFORMA_PADRAO = {"win32": "windows", "darwin": "cocoa", "linux": "xcb"}

# O estilo nativo, que vem num PLUGIN (no Windows, `qmodernwindowsstyle.dll`,
# que registra "windows11" e "windowsvista"). Faltando, o Qt usa outro estilo
# sem avisar ninguém. No Linux o estilo, o Fusion, já vem dentro do QtWidgets.
ESTILO_NATIVO = {"win32": "windowsvista", "darwin": "macos"}

# As traduções que `_instalar_traducao` (sigft/app_qt/main.py) carrega: os "Sim",
# "Não" e "Cancelar" dos diálogos em português e em espanhol (o inglês é o do Qt).
TRADUCOES_DA_QT = (("pt_BR", "qtbase"), ("es", "qtbase"))


def plataformas_do_qt(ambiente=None, sistema: str | None = None) -> list[str]:
    """As plataformas que o Qt tentaria, na ordem, pela regra dele mesmo.

    As de `QT_QPA_PLATFORM` (`"windows:darkmode=2"` -> `windows`; `"wayland;xcb"`
    -> as duas, em ordem); sem a variável, a do sistema. No Release ela não
    existe, então é `windows`; no --smoke sem tela e nos testes, `offscreen`.
    """
    ambiente = os.environ if ambiente is None else ambiente
    sistema = sys.platform if sistema is None else sistema
    pedidas = [parte.split(":", 1)[0].strip()
               for parte in (ambiente.get("QT_QPA_PLATFORM") or "").split(";")]
    return [p for p in pedidas if p] or [PLATAFORMA_PADRAO.get(sistema, "xcb")]


def _pasta_do_qt(nome: str) -> str:
    """Uma pasta do Qt (`PluginsPath`, `TranslationsPath`) como o próprio Qt a
    acha -- no pacote, pelo `qt.conf` que o PySide6 cria ao ser importado."""
    from PySide6.QtCore import QLibraryInfo

    return QLibraryInfo.path(getattr(QLibraryInfo.LibraryPath, nome))


def _conferir_plataforma() -> tuple[str, bool]:
    """CARREGA os plugins de plataforma do pacote até achar o que o Qt usaria.

    Sem ele a janela não abre -- e, no Windows, o Qt ainda mostra uma caixa
    modal ("no Qt platform plugin could be initialized") que deixaria o passo
    `--smoke` do Release pendurado até o tempo-limite, sem dizer o motivo.
    Carregar (e não só achar o arquivo) pega também a DLL de que ele depende.
    """
    from PySide6.QtCore import QPluginLoader

    procuradas = plataformas_do_qt()
    pasta = os.path.join(_pasta_do_qt("PluginsPath"), "platforms")
    try:
        arquivos = sorted(os.listdir(pasta))
    except OSError:
        arquivos = []
    nao_carregaram = []
    for arquivo in arquivos:
        carregador = QPluginLoader(os.path.join(pasta, arquivo))
        if not carregador.load():
            nao_carregaram.append(f"{arquivo} ({carregador.errorString()})")
            continue
        chaves = {str(c).lower() for c in carregador.metaData().get("MetaData", {}).get("Keys", [])}
        carregador.unload()
        for plataforma in procuradas:
            if plataforma.lower() in chaves:
                return f"  OK     Qt: plataforma '{plataforma}' ({os.path.join(pasta, arquivo)})", True
    detalhe = f"; nao carregaram: {', '.join(nao_carregaram)}" if nao_carregaram else ""
    return (f"  FALHA  Qt: nenhum plugin da plataforma '{procuradas[0]}' carregou de {pasta} "
            f"-- sem ele a janela nao abre{detalhe}"), False


def _conferir_estilo() -> tuple[str, bool] | None:
    nativo = ESTILO_NATIVO.get(sys.platform)
    if not nativo:
        return None
    from PySide6.QtWidgets import QStyleFactory

    achados = QStyleFactory.keys()
    if nativo.lower() in {estilo.lower() for estilo in achados}:
        return f"  OK     Qt: estilo nativo '{nativo}'", True
    return (f"  FALHA  Qt: o estilo nativo '{nativo}' nao esta no pacote -- a janela abriria com "
            f"outro, sem aviso (achados: {', '.join(achados)})"), False


def _conferir_traducao() -> tuple[str, bool]:
    from PySide6.QtCore import QLocale, QTranslator

    pasta = _pasta_do_qt("TranslationsPath")
    linhas, tudo_certo = [], True
    for idioma, catalogo in TRADUCOES_DA_QT:
        tradutor = QTranslator()
        if tradutor.load(QLocale(idioma), catalogo, "_", pasta):
            linhas.append(f"  OK     Qt: traducao {idioma} ({tradutor.filePath()})")
        else:
            linhas.append(f"  FALHA  Qt: a traducao {idioma} ({catalogo}_{idioma}.qm) nao esta em "
                          f"{pasta} -- os dialogos sairiam em ingles")
            tudo_certo = False
    return "\n".join(linhas), tudo_certo


def _conferir_fontes() -> tuple[str, bool]:
    from sigft.app_qt import estilo

    faltando = [nome for nome in estilo.ARQUIVOS_DE_FONTE
                if not os.path.isfile(os.path.join(estilo.PASTA_FONTES, nome))]
    if faltando:
        return (f"  FALHA  Qt: fontes fora do pacote: {', '.join(faltando)} "
                f"(procurei em {estilo.PASTA_FONTES})"), False
    return f"  OK     Qt: fontes {', '.join(estilo.ARQUIVOS_DE_FONTE)} ({estilo.PASTA_FONTES})", True


def conferir_qt() -> tuple[str, bool]:
    """`(linhas do relatório, funcionou)` -- a interface Qt CARREGA, aqui?

    `find_spec` (em `conferir_pacote`) acha `PySide6.QtCore` sem carregar o
    `QtCore.pyd` nem as DLLs do Qt: um pacote sem o `Qt6Core.dll` passaria lá e
    só morreria na abertura. Aqui o import é de verdade, e depois vem o que a
    janela lê do disco: o plugin da plataforma (carregado), o estilo nativo,
    as traduções pt_BR e es e as fontes. Tudo sem criar a `QApplication` -- que, sem o
    plugin da plataforma, travaria em vez de responder.
    """
    for nome in MODULOS_DA_QT:
        try:
            importlib.import_module(nome)
        except Exception as erro:  # noqa: BLE001 -- o relatório diz o quê
            return f"  FALHA  Qt nao carrega: {nome}: {type(erro).__name__}: {erro}", False
    try:
        import PySide6
        from PySide6.QtCore import qVersion

        linhas = [f"  OK     Qt carrega: PySide6 {PySide6.__version__}, Qt {qVersion()} "
                  f"({', '.join(nome.split('.')[-1] for nome in MODULOS_DA_QT)})"]
    except Exception as erro:  # noqa: BLE001
        return f"  FALHA  Qt nao carrega: {type(erro).__name__}: {erro}", False

    tudo_certo = True
    for conferir in (_conferir_plataforma, _conferir_estilo, _conferir_traducao, _conferir_fontes):
        try:
            resultado = conferir()
        except Exception as erro:  # noqa: BLE001 -- uma conferência quebrada não cala as outras
            resultado = (f"  FALHA  Qt: {conferir.__name__}: {type(erro).__name__}: {erro}", False)
        if resultado is None:
            continue
        linha, certo = resultado
        linhas.append(linha)
        tudo_certo = tudo_certo and certo
    return "\n".join(linhas), tudo_certo


def cli() -> int:
    """Grava o relatório e devolve o código de saída (0 = tudo certo)."""
    relatorio, pacote_ok = conferir_pacote()
    linha_do_tradutor, tradutor_ok = conferir_tradutor()
    linhas_da_qt, qt_ok = conferir_qt()
    relatorio = relatorio + "\n\n" + linha_do_tradutor + "\n\n" + linhas_da_qt
    gravar_relatorio(ARQUIVO_CONFERENCIA, relatorio)
    print(relatorio)
    return 0 if (pacote_ok and tradutor_ok and qt_ok) else 1

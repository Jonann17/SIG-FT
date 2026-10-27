# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller para o SIG-FT — Checkpoint 8.3 do plano de refatoração.

Uso (não chame o `pyinstaller` direto — o `.bat` cuida do ambiente):

    Gerar-Executavel.bat

O que gera: `dist/SIG-FT/SIG-FT.exe` mais a pasta de apoio ao lado.

Por que pasta (`--onedir`) e não arquivo único (`--onefile`)
------------------------------------------------------------
`--onefile` produz um .exe que, a CADA execução, descompacta tudo num
diretório temporário. Para este app isso é ruim por três motivos concretos:

1. **A abertura fica lenta.** São centenas de MB (pandas, playwright, o
   Chromium). O splash existe justamente para encurtar a espera percebida —
   descompactar antes dele aparecer desfaz o ganho.
2. **Antivírus corporativo.** Um executável que se descompacta sozinho em
   `%TEMP%` a cada execução é o padrão que mais dispara heurística. Numa
   máquina com a política da GE Vernova, é pedir para ser barrado.
3. **O navegador do Playwright.** Ele precisa de um caminho estável; extrair
   ~150 MB de Chromium a cada abertura é desperdício puro.

Onde ficam os dados do usuário
------------------------------
Distinção que importa e que é fácil errar:

* **Dentro do bundle** (somente leitura, achado por `resource_path`, que sabe
  ler o `sys._MEIPASS`, ou pelo `__file__` do módulo, que no bundle também
  aponta para dentro dele): `assets/` -- o logo, o ícone e as fontes da
  interface Qt --, a Qt e as licenças dela (ver "A interface Qt" abaixo).
* **Fora, ao lado do .exe** (graváveis, achados pelo diretório de trabalho):
  `api_config.json`, `user_prefs.json`, `logs/`, os caches de modelo.

Empacotar os graváveis dentro do bundle os tornaria somente-leitura — e, no
`--onefile`, o usuário perderia as chaves de API a cada execução, porque a
pasta temporária é apagada no fim. É por isso que `CONFIG_FILE` é resolvido a
partir do diretório de trabalho, e não por `resource_path`.
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# =============================================================================
# Recursos que entram no bundle
# =============================================================================
datas = [
    # O ícone da janela e o logo do splash. `resource_path` os acha tanto no
    # .py quanto dentro do .exe. Leva junto `assets/icons` (2026-10-20): os SVG
    # do Lucide que os botões e o menu desenham (`sigft/app_qt/icones.py`, que
    # os procura em `_internal/assets/icons`) e a LICENSE deles (ISC). O
    # `--smoke` do Release reprova se algum não desenhar dentro do `.exe`.
    ("assets", "assets"),
    # O CHANGELOG: é dele que sai o "o que há de novo" mostrado depois de uma
    # atualização (`sigft/core/novidades.py`). Sem ele no bundle, a janela de
    # novidades abre vazia justamente na hora em que ela importa.
    ("CHANGELOG.md", "."),
    # O template do painel HTML do Gestão PMIB (2026-10-05, T7). Vai para
    # `sigft/assets/`, que é onde `services/painel.caminho_do_template` procura
    # (ao lado do pacote, inclusive dentro do .exe).
    (os.path.join("sigft", "assets", "painel_template.html"), os.path.join("sigft", "assets")),
    # Os catálogos de tradução da interface (2026-10-22, `sigft/app/idioma.py`).
    # Vão para `sigft/app/idiomas/`, onde o `idioma` os procura
    # (`Path(__file__).parent / "idiomas"`, também dentro do .exe). Sem eles o app
    # abre em português sem aviso: o `--smoke` do Release reprova (`idioma.conferir`).
    (os.path.join("sigft", "app", "idiomas"), os.path.join("sigft", "app", "idiomas")),
]

# =============================================================================
# O navegador do Playwright
# =============================================================================
# Ler com atenção: é o ponto que decide se o RPA funciona na máquina da
# empresa.
#
# O Playwright NÃO traz o navegador no pacote pip — ele baixa depois, com
# `playwright install chromium`, de `cdn.playwright.dev`. Numa rede com
# inspeção SSL (Zscaler e afins) esse download costuma falhar, e falha num
# processo Node que ignora as variáveis de certificado do Python (só respeita
# `NODE_EXTRA_CA_CERTS`) — ver README.md, seção "Rede corporativa (Zscaler)".
#
# O build PODE embutir o navegador — mas isso é OPT-IN desde 2026-08-28, e a
# mudança foi por causa da REVISÃO DE SEGURANÇA da TI, não por questão técnica.
#
# Um Chromium embutido é um navegador que NÃO recebe os patches de segurança da
# política da empresa: ele congela na versão do dia do build e fica fora do
# inventário que a TI gerencia. Numa máquina corporativa essa é a objeção mais
# forte contra o pacote, e ela é legítima.
#
# O caminho recomendado passou a ser o `SIG-FT.bat` + `Instalar-Playwright.bat`
# (Python oficial, pacotes do PyPI com versão declarada, Chromium do canal
# oficial e atualizável). Ver `docs/SEGURANCA_TI.md`.
#
# Como funciona quando se opta por embutir: `SIGFT_EMBUTIR_NAVEGADOR=1` faz o
# `Gerar-Executavel.bat` definir `PLAYWRIGHT_BROWSERS_PATH=0` ANTES do
# `playwright install`, e aí o navegador é instalado DENTRO do pacote
# `playwright` (em vez de em `%LOCALAPPDATA%\ms-playwright`) — o
# `collect_data_files` abaixo o encontra e leva junto.
#
# No caminho PADRÃO (sem a variável) o navegador está fora do pacote e esta
# coleta traz só os arquivos de dados do `playwright`, sem o browser: o .exe
# funciona para tudo menos RPA, e o robô usa o Chromium instalado à parte na
# máquina. É o mesmo `collect_data_files` nos dois casos — o que muda é o que
# existe dentro do pacote na hora do build, não esta linha.
#
# ⚠️ CORREÇÃO 2026-09-04, achada compilando de verdade: a variável de
# ambiente NÃO bastava.
#
# `SIGFT_EMBUTIR_NAVEGADOR` decide se o `.bat` INSTALA o navegador dentro do
# pacote `playwright`. Só que `collect_data_files` recolhe TUDO que estiver
# no pacote — inclusive um navegador que uma execução ANTERIOR tenha deixado
# lá. Uma vez embutido, ficava embutido para sempre, e o build seguia
# anunciando "Navegador NAO embutido (padrao)".
#
# O estrago medido: **841 MB** de Chromium num pacote que deveria ter ~250,
# com três consequências:
#
#   1. a posição de segurança documentada para a TI ("o pacote não leva
#      navegador") passava a ser FALSA, sem ninguém perceber;
#   2. os caminhos internos do Chromium estouram o limite de 260 caracteres
#      do Windows — nem o PowerShell consegue listá-los, e o `tar` que
#      extrai o ZIP na máquina de destino falha;
#   3. o ZIP para o Box triplicava de tamanho.
#
# Agora o filtro é explícito: sem a variável, `.local-browsers` fica de fora,
# esteja ele lá ou não.
_dados_playwright = collect_data_files("playwright", include_py_files=False)

if not os.environ.get("SIGFT_EMBUTIR_NAVEGADOR"):
    _dados_playwright = [
        (origem, destino)
        for (origem, destino) in _dados_playwright
        if ".local-browsers" not in str(origem).replace("\\", "/")
    ]

datas += _dados_playwright

# =============================================================================
# O tradutor local da tela 4.2 (2026-09-25)
# =============================================================================
# O modelo (~218 MB) é gerado por `tools/preparar_tradutor.py` em
# `recursos/tradutor_pt_es` e entra como `modelos/tradutor_pt_es` -- é ali
# que `sigft/core/tradutor_local.py` procura dentro do .exe (`sys._MEIPASS`).
# Sem a pasta o build SEGUE e avisa: o app abre, e só a tela 4.2 diz que falta
# o modelo. O workflow de release prepara a pasta antes, e a
# `--conferir-pacote` traduz uma frase dentro do .exe.
_MODELO_TRADUTOR = os.path.join("recursos", "tradutor_pt_es")
if os.path.isdir(_MODELO_TRADUTOR):
    datas += [(_MODELO_TRADUTOR, os.path.join("modelos", "tradutor_pt_es"))]
else:
    print("[SIG-FT] AVISO: recursos/tradutor_pt_es nao existe -- o tradutor 4.2 "
          "vai sem modelo (rode tools/preparar_tradutor.py)")

# As DLLs do CTranslate2 (o motor em C++ e o OpenMP). O pacote as carrega de
# dentro da própria pasta.
binarios = collect_dynamic_libs("ctranslate2")

# =============================================================================
# A interface Qt (E6.2, 2026-10-10)
# =============================================================================
# Desde o corte (E6.1) o `.exe` abre a interface Qt (`sigft/app_qt/`), e desde
# 2026-10-15 só ela: a interface antiga saiu do SIG-FT (e a biblioteca dela e o
# Tcl/Tk saem do pacote, nos `excludes`). O PySide6 entra pela análise (o
# `frontend.py` importa
# `sigft.app_qt.main`) e pelos hooks do PyInstaller, que trazem as DLLs do Qt,
# os plugins e as traduções. Três peças são escolha nossa:
#
#   1. os plugins: só a plataforma e o estilo, no hook
#      `empacotamento/hooks/hook-PySide6.QtGui.py` (o `hookspath` do Analysis),
#      e o módulo QtNetwork fora, nos `excludes` (lá está por quê);
#   2. as traduções e o OpenGL por software: filtrados depois da análise, em
#      "A Qt que a interface não usa", lá embaixo;
#   3. as licenças, logo aqui.
#
# O que a interface lê do disco já vem por outros caminhos e é conferido
# DENTRO do `.exe` pela `--conferir-pacote` (`sigft/app/conferencia.py`,
# `conferir_qt`): as fontes em `assets/fonts` (o `("assets", "assets")` lá em
# cima; `estilo.PASTA_FONTES` sai do `__file__`, que no bundle é
# `_internal/sigft/app_qt/estilo.pyc`, e cai em `_internal/assets/fonts`), a
# tradução `qtbase_pt_BR` e o plugin da plataforma (achados pelo `qt.conf` que
# o PySide6 cria ao ser importado).
#
# Licenças. O Qt for Python (PySide6, shiboken6) e o Qt vão sob a LGPLv3, que
# pede a quem distribui: avisar que a biblioteca está no programa, mandar junto
# o texto da LGPL e o da GPL, e deixar a biblioteca trocável (no onedir, as
# DLLs do Qt e os `.pyd` ficam em arquivos à parte, em `_internal/PySide6`).
# O wheel NÃO traz o texto da LGPL: medido no 6.12, o `.dist-info` do Windows
# tem só o METADATA ("License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only")
# e um `LicenseRef-Qt-Commercial.txt`, sobre a licença comercial; o do Linux,
# só o METADATA. Por isso o aviso e
# os textos oficiais da FSF moram em `empacotamento/licencas/` (com o SHA-256
# conferido em `tests/test_qt_no_pacote.py`), e os arquivos do wheel vêm do
# ambiente do build, na versão que vai no pacote. Tudo em `_internal/licencas/`.
datas += [(os.path.join("empacotamento", "licencas", nome), "licencas")
          for nome in ("LEIA-ME-Qt.txt", "LGPL-3.0.txt", "GPL-3.0.txt")]


def _licencas_do_wheel(distribuicao):
    """O METADATA e o `.dist-info/licenses/` do pacote instalado no build."""
    from importlib import metadata

    try:
        dist = metadata.distribution(distribuicao)
    except metadata.PackageNotFoundError:
        raise SystemExit(f"[SIG-FT] ERRO: {distribuicao} nao esta instalado no ambiente do build. "
                         "A interface oficial e a Qt: pip install -r requirements.txt") from None
    return [(str(dist.locate_file(arquivo)), os.path.join("licencas", distribuicao))
            for arquivo in dist.files or []
            if arquivo.parts[0].endswith(".dist-info")
            and (arquivo.name == "METADATA" or "licenses" in arquivo.parts)]


datas += _licencas_do_wheel("PySide6_Essentials") + _licencas_do_wheel("shiboken6")

# =============================================================================
# Imports que o PyInstaller não enxerga sozinho
# =============================================================================
# O splash importa os backends por NOME, com `importlib.import_module`
# (ver `sigft/app/backends.py`). Import dinâmico é invisível para a análise
# estática do PyInstaller: sem declarar aqui, o .exe abre e todos os 11
# módulos falham no carregamento, um por um, na barra de progresso.
hiddenimports = [
    "cria_fichas_no_pmib_v1_backend",
    "pdm_backend",
    "analyzer_backend",
    "translator_backend",
    "upload_conditions_backend",
    "upload_tech_specs_backend",
    "autospec_backend",
    "lmr_backend",
    "apagar_lmr_backend",
    "pmib_manager_backend",
    "search_pmib_backend",
]

# O pacote `sigft` inteiro: os serviços entram por
# aqueles shims dinâmicos acima, e as telas Qt são importadas na PRIMEIRA visita
# (dentro das fábricas de `sigft.app_qt.main.TELAS`). Sem esta coleta, uma tela
# que a análise não enxergasse só faltaria quando alguém clicasse no menu -- a
# `--conferir-pacote` procura cada uma, e um teste trava as duas listas juntas.
hiddenimports += collect_submodules("sigft")

# Provedores de IA são importados PREGUIÇOSAMENTE dentro das funções
# (`core/llm/client.py`), de propósito — mesma razão dos backends: o
# PyInstaller não os vê.
hiddenimports += [
    "sigft.core.llm.providers.gemini",
    "sigft.core.llm.providers.openrouter",
    "sigft.core.llm.providers.openai_compat",
]

# `pip_system_certs` não é importado por ninguém: ele age no import do Python
# (via .pth) para fazer o SSL usar o repositório de certificados do WINDOWS.
# É o que faz as chamadas HTTPS funcionarem atrás do Zscaler. Sem ele no
# bundle, o .exe volta a dar CERTIFICATE_VERIFY_FAILED na máquina da empresa.
hiddenimports += ["pip_system_certs", "pip_system_certs.wrapt_requests"]

# O motor do tradutor local importa os dois por NOME (`importlib`), só na
# primeira tradução -- para o resto do app não pagar o custo.
hiddenimports += ["ctranslate2", "sentencepiece"]

# O editor cirúrgico (`sigft/core/excel/cirurgico.py`, 2026-10-05) grava os
# `_STATUS_PMIB` com o lxml -- e o `StatusPMIB` só o importa na hora de gravar.
# A análise estática o acha pelo `collect_submodules("sigft")`; declarado aqui
# para não depender disso, junto com o `_elementpath` que o `etree` carrega por
# dentro. Sem ele, o app abre e a primeira gravação de planilha falha.
hiddenimports += ["lxml.etree", "lxml._elementpath"]

# Os ícones da interface (2026-10-20, `sigft/app_qt/icones.py`) são SVG
# desenhados pelo `QSvgRenderer`: o módulo QtSvg e o `Qt6Svg.dll` têm de ir.
# A análise o acha pelo import do `icones.py`; declarado por extenso para não
# depender disso. NÃO precisa dos plugins de SVG (`imageformats/qsvg`,
# `iconengines/qsvgicon`), que o hook do QtGui continua tirando: o desenho é
# feito pelo módulo, sem passar pelo carregador de imagem do Qt.
hiddenimports += ["PySide6.QtSvg"]


# Ícone do executável.
#
# 1ª escolha: `build/SIG-FT.ico`, que o `Gerar-Executavel.bat` monta com as
#    medidas pequenas (16/24/32/48...) que o Windows usa na barra de tarefas.
# 2ª escolha: o `.ico` do repositório. Desde 2026-09-22 ele já vem com todas
#    as medidas, então esta escolha não perde nada -- e é a que o CI usa,
#    porque o workflow de Release não roda o `.bat`.
#
# Quem chama o `pyinstaller` na mão (sem o .bat) cai na 2ª e ainda assim sai
# com o ícone certo, em vez do ícone genérico do PyInstaller.
_ICONE = os.path.join("build", "SIG-FT.ico")
if not os.path.exists(_ICONE):
    _ICONE = os.path.join("assets", "icone-sig-ft.ico")
if not os.path.exists(_ICONE):
    _ICONE = None

a = Analysis(
    ["frontend.py"],
    pathex=[os.path.abspath(".")],
    binaries=binarios,
    datas=datas,
    hiddenimports=hiddenimports,
    # O hook que escolhe os plugins do Qt (ver "A interface Qt", acima). Hook
    # daqui ganha do embutido no PyInstaller para o mesmo módulo. Pelo
    # `SPECPATH`: o PyInstaller acha as `datas` a partir da pasta do spec, mas
    # o `hookspath` a partir da pasta ATUAL -- rodado de outra pasta, o hook
    # sumiria calado e a Qt iria inteira.
    hookspath=[os.path.join(SPECPATH, "empacotamento", "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    # Módulos de teste não vão para produção.
    #
    # `torch` e `transformers`: só a CONVERSÃO do modelo do tradutor os usa
    # (`tools/preparar_tradutor.py`, num ambiente à parte no workflow). O
    # `ctranslate2.converters` tenta importá-los dentro de try/except, e numa
    # máquina de build que os tenha instalados a análise levaria ~800 MB de
    # torch para o instalador.
    #
    # (`PySide6` e `shiboken6` estiveram aqui até a E6.2, quando a interface
    # oficial ainda era a antiga. Hoje sem eles o `.exe` não abre.)
    #
    # `tkinter`, `_tkinter` e `customtkinter` (2026-10-15): a interface antiga
    # saiu do SIG-FT, e nenhum arquivo do projeto os importa
    # (`tests/test_sem_interface_antiga.py`). Quem ainda os puxaria é import
    # opcional de terceiros (o `PIL.ImageTk`, por exemplo): sem a exclusão, a
    # análise levaria o `_tkinter`, a libtcl/libtk e os dados do Tcl/Tk
    # (`_tcl_data`, `_tk_data`), que o hook do PyInstaller recolhe junto.
    #
    # `PySide6.QtNetwork`: ninguém no SIG-FT o importa. Quem o puxa é um
    # `from . import QtNetwork` CONDICIONAL do `PySide6/__init__.py` (só no
    # Windows, se existir a pasta `PySide6\openssl`, que o wheel do PyPI não
    # tem, e dentro de try/except ImportError) -- a análise segue o import e
    # levaria o módulo, o Qt6Network e os plugins de TLS e de rede: 3,6 MB no
    # Windows. Se um dia alguém usar o QtNetwork, `tests/test_qt_no_pacote.py`
    # manda tirar esta linha antes que o `.exe` quebre.
    #
    # `PIL._avif` (2026-10-19): o leitor de imagem AVIF do Pillow, 7,9 MB no
    # Windows. Nenhum arquivo do SIG-FT abre AVIF, e o Pillow aguenta a falta
    # dele (`AvifImagePlugin`: `try: from . import _avif / except ImportError`,
    # conferido no Pillow 13, o fixado em `empacotamento/versoes-do-release.txt`).
    #
    # `pymupdf.layout`, `pymupdf4llm` e `onnxruntime` (2026-10-20): o PyMuPDF
    # 2.0 traz os dois primeiros como dependência OBRIGATÓRIA, e o
    # `pymupdf/layout/__init__.py` carrega um modelo ONNX no IMPORT
    # (`activate()`). O PyInstaller levava o código sem os arquivos do modelo,
    # e `import pymupdf` levantava `FileNotFoundError: .../layout_rf2.4.1+imf1.yaml`
    # -- o AutoSpec não lia PDF nenhum da rc.5 à rc.7. O PyMuPDF aguenta a
    # falta dos dois (`try: import pymupdf.layout / except ImportError` e o
    # mesmo para o `pymupdf4llm`, conferido no 2.0), e o SIG-FT não usa
    # nenhum deles (as tabelas saem do `find_tables(use_layout=False)`). O
    # `onnxruntime` só vinha por eles. Juntos, ~120 MB a menos no pacote.
    # Trava: `tests/test_pymupdf_sem_layout.py`.
    excludes=["pytest", "_pytest", "mypy", "ruff", "torch", "transformers",
              "PySide6.QtNetwork", "tkinter", "_tkinter", "customtkinter",
              "PIL._avif", "pymupdf.layout", "pymupdf4llm", "onnxruntime"],
    # TODO o Python FORA do `.exe`: um `.pyc` por módulo em `_internal/`.
    #
    # 1º passo (2026-10-19), só o SIG-FT: `module_collection_mode={"sigft":
    # "pyc"}`. Medido entre a 1.2.1-rc.4 e a rc.5: dos 38,6 MB que mudaram,
    # 37,1 MB eram o `SIG-FT.exe` -- o PYZ, com TODO o Python do pacote, mora
    # dentro dele, e uma linha mudada no SIG-FT trocava o `.exe` inteiro. Com o
    # código à parte, mudar um módulo muda só o `.pyc` dele (provado num build
    # de teste: o `.exe` sai idêntico byte a byte).
    #
    # 2º passo (2026-10-27), as bibliotecas também: `noarchive=True`. Medido
    # entre a 1.3.0 e a 1.3.1-rc.1 (`conteudo-do-exe.json` e `arquivos.json`
    # do Release): o `PYZ.pyz` foi a ÚNICA entrada do `.exe` que mudou --
    # `certifi` e `nltk` subiram e o `PyPDF2` saiu --, e a atualização pequena
    # foi de ~1,5 MB para ~38 MB só por isso. Com `noarchive`, o PyInstaller
    # 6.x (`_get_module_collection_mode`, em `building/build_main.py`) troca o
    # modo PYZ por PYC para TODO módulo puro: o PYZ sai vazio, o
    # `base_library.zip` (a stdlib de arranque) deixa de existir e vira `.pyc`
    # solto também, e o `{"sigft": "pyc"}` ficou redundante (saiu). Dentro do
    # `.exe` sobra o bootloader, o `frontend.py` compilado, os módulos de
    # arranque do PyInstaller (`pyimod*`, `pyiboot01_bootstrap`) e os runtime
    # hooks (`pyi_rth_*`): ele só muda quando muda o PyInstaller (ou o
    # pyinstaller-hooks-contrib), o Python, o ícone/versão ou o `frontend.py`.
    # Provado com ESTE spec num build em Linux (PyInstaller 6.22.3, Python
    # 3.13): PYZ com 0 módulos, sem `base_library.zip`, executável de 100 KB
    # (33,9 MB sem a opção), e `--conferir-pacote` e `--smoke` passam.
    #
    # O preço, aceito:
    #   * muito mais arquivos em disco: no mesmo build, de 572 para 5660
    #     (~5100 `.pyc`), e +51 MB, porque o `.pyc` solto não é comprimido
    #     como no PYZ (o instalador comprime tudo de novo);
    #   * a abertura pode ficar um pouco mais lenta: um arquivo por módulo
    #     em vez de um arquivo só, e o antivírus do Windows olha cada um na
    #     1ª vez (no Linux, com o disco quente, o `--smoke` levou o mesmo
    #     tempo: ~2,5 s nos dois);
    #   * caminho mais comprido: o `.pyc` mais fundo (do `llama_cloud`) tem
    #     169 caracteres a partir de `_internal`, e cabe nos 260 do Windows
    #     só porque a pasta de instalação é curta;
    #   * a PRIMEIRA atualização depois desta ainda é grande, uma última vez:
    #     o `.exe` muda (perde o PYZ) e todos os `.pyc` das bibliotecas são
    #     novos. Daí em diante, dependência que muda leva só os arquivos dela.
    #
    # O `__file__` de cada módulo continua sendo `_internal/<pacote>/x.pyc`, o
    # mesmo caminho "virtual" que o PYZ já dava -- quem calcula pasta a partir
    # dele não percebe. Os `.pyc` entram em `a.datas` (destino
    # `pacote/modulo.pyc`), então os filtros de `a.datas` lá embaixo passam
    # por eles: nenhum casa com um `.pyc` (navegador, descritores do Google e
    # traduções/OpenGL do Qt são todos arquivos de dados ou DLLs), e os
    # `excludes` acima agem antes, na análise. Trava:
    # `tests/test_conferencia_do_pacote.py` (`noarchive=True`).
    noarchive=True,
)

# =============================================================================
# REDE FINAL: o navegador nao entra, venha de onde vier
# =============================================================================
# Filtrar a saida do `collect_data_files` acima NAO bastou -- medido em
# 2026-09-04: mesmo com aquele filtro, 735 MB de `.local-browsers` chegaram ao
# pacote. Nao ha hook de playwright nem no PyInstaller nem no
# pyinstaller-hooks-contrib (procurei nos dois), entao a entrada vem por
# caminho que este arquivo nao controla na origem.
#
# Em vez de continuar cacando a origem, filtramos o RESULTADO: depois da
# analise, tudo o que mencionar `.local-browsers` sai das listas. E o unico
# ponto por onde todo arquivo empacotado passa, entao nao ha como escapar.
#
# Por que isso importa mais que o tamanho:
#   * a posicao de seguranca documentada para a TI ("o pacote nao leva
#     navegador") passava a ser falsa sem ninguem perceber;
#   * os caminhos internos do Chromium estouram o limite de 260 caracteres do
#     Windows, e o `tar` que extrai o ZIP na maquina de destino falha ali --
#     o build "funciona" e a instalacao sai quebrada.
if not os.environ.get("SIGFT_EMBUTIR_NAVEGADOR"):

    def _sem_navegador(toc):
        """Tira do TOC toda entrada que cite `.local-browsers`."""
        limpos = []
        for entrada in toc:
            texto = "/".join(str(parte) for parte in entrada).replace(os.sep, "/")
            if ".local-browsers" in texto:
                continue
            limpos.append(entrada)
        return limpos

    _antes = len(a.datas) + len(a.binaries)
    a.datas = _sem_navegador(a.datas)
    a.binaries = _sem_navegador(a.binaries)
    _depois = len(a.datas) + len(a.binaries)
    print(f"[SIG-FT] navegador fora do pacote: {_antes - _depois} arquivos removidos")


# =============================================================================
# Os 586 descritores de API do Google que ninguem usa
# =============================================================================
# `googleapiclient/discovery_cache/documents/` sao 586 arquivos JSON, 102 MB,
# um para CADA API REST do Google -- `abusiveexperiencereport`, `acmedns`,
# `accesscontextmanager`... O SIG-FT nao usa nenhuma: o `googleapiclient`
# entra de carona como dependencia do `google-generativeai`, que importa o
# MODULO `discovery` mas nao le esses documentos (o Gemini fala pelo cliente
# proprio, nao por discovery).
#
# Eram 25% do pacote -- o segundo maior item, perdendo so para o driver do
# Playwright, que esse sim e necessario.
#
# Se um dia alguem chamar `discovery.build()`, a ausencia do cache NAO quebra:
# o proprio googleapiclient busca o descritor pela rede. So o modulo e que nao
# pode sair; os documentos, sim.
_ANTES_G = len(a.datas)
a.datas = [
    entrada for entrada in a.datas
    if "discovery_cache/documents" not in str(entrada[0]).replace(os.sep, "/")
]
if _ANTES_G != len(a.datas):
    print(f"[SIG-FT] descritores do Google fora do pacote: {_ANTES_G - len(a.datas)} arquivos")


# =============================================================================
# A Qt que a interface não usa  (E6.2)
# =============================================================================
# Os plugins saem antes, no hook (lá está por quê). Aqui, depois da análise,
# saem dois itens que não puxam biblioteca nenhuma -- medidos no wheel 6.12 do
# Windows, que é o que vai no instalador:
#
#   * as traduções: o PyInstaller leva as ~100 do Qt (`qt_*` e `qtbase_*`,
#     7 MB), e a interface carrega a do idioma escolhido: `qtbase_pt_BR` ou
#     `qtbase_es` (o inglês não precisa) -- os "Sim", "Não" e "Cancelar" dos
#     diálogos (`_instalar_traducao`, em sigft/app_qt/main.py);
#   * o `opengl32sw.dll` (20,6 MB, só no Windows): o OpenGL por software que o
#     Qt usa no Qt Quick e no QOpenGLWidget quando a placa de vídeo não serve.
#     A interface é QtWidgets puro, que desenha sem OpenGL.
#
# Com os plugins e o QtNetwork (nos `excludes`), a parte do Qt no pacote do
# Windows cai de 78,4 para 43,2 MB (ver docs/BUILD.md, "A interface Qt dentro
# do pacote").
_TRADUCOES_DO_QT = {"qtbase_pt_BR.qm", "qtbase_es.qm"}


def _qt_que_a_interface_nao_usa(entrada):
    destino = str(entrada[0]).replace("\\", "/")
    if not destino.startswith("PySide6/"):
        return False
    pasta, _, nome = destino.rpartition("/")
    if pasta.endswith("/translations"):     # PySide6/translations ou PySide6/Qt/translations
        return nome not in _TRADUCOES_DO_QT
    return nome.lower() == "opengl32sw.dll"


_ANTES_QT = len(a.datas) + len(a.binaries)
a.datas = [entrada for entrada in a.datas if not _qt_que_a_interface_nao_usa(entrada)]
a.binaries = [entrada for entrada in a.binaries if not _qt_que_a_interface_nao_usa(entrada)]
print(f"[SIG-FT] Qt que a interface nao usa, fora do pacote: "
      f"{_ANTES_QT - len(a.datas) - len(a.binaries)} arquivos")


# Com `noarchive=True` o `a.pure` sai vazio (ver o comentário no Analysis): o
# PYZ continua existindo dentro do `.exe`, mas sem módulo nenhum.
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SIG-FT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX é outro gatilho clássico de antivírus corporativo.
    # `console=False` — [2026-09-04] pedido do usuário: *"quando executo o
    # executável, não pode ficar com o powershell aberto"*.
    #
    # Esta linha era `True`, e não por descuido: o console ERA o canal de
    # diagnóstico. É nele que apareciam "Erro ao carregar <módulo>" da splash
    # e o `CERTIFICATE_VERIFY_FAILED` do Zscaler — e foi lendo essa saída que
    # se achou o ícone apontando para o lugar errado depois do CP 7.3.
    #
    # Por isso a mudança não foi só apagar o console: `sigft/app/main.py`
    # ganhou `_desviar_saida_para_arquivo()`, que sem console manda `print` e
    # traceback para `logs/sigft.log`, ao lado do .exe. O canal mudou de
    # lugar, não sumiu — se some, uma primeira execução na GE Vernova troca
    # uma mensagem clara por "não funciona".
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # O PyInstaller no Windows quer `.ico` para o ícone do EXECUTÁVEL (o `.png`
    # serve para a janela Qt, mas não para o arquivo).
    # `_ICONE` vem da escolha mais acima: o `build/SIG-FT.ico` que o
    # `Gerar-Executavel.bat` gera a partir do PNG, ou o
    # `assets/icone-sig-ft.ico` do repositório, que é o que o CI usa. Sem
    # nenhum dos dois, o build segue com o ícone padrão em vez de falhar.
    icon=_ICONE,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SIG-FT",
)

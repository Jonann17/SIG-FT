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
  ler o `sys._MEIPASS`): `assets/logo.png`.
* **Fora, ao lado do .exe** (graváveis, achados pelo diretório de trabalho):
  `api_config.json`, `user_prefs.json`, `logs/`, os caches de modelo.

Empacotar os graváveis dentro do bundle os tornaria somente-leitura — e, no
`--onefile`, o usuário perderia as chaves de API a cada execução, porque a
pasta temporária é apagada no fim. É por isso que `CONFIG_FILE` é resolvido a
partir do diretório de trabalho, e não por `resource_path`.
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# =============================================================================
# Recursos que entram no bundle
# =============================================================================
datas = [
    # O ícone da janela e o logo do splash. `resource_path` os acha tanto no
    # .py quanto dentro do .exe.
    ("assets", "assets"),
]

# `customtkinter` carrega temas de arquivos .json que ele traz junto. Sem isto,
# o app abre com o tema padrão errado ou nem abre.
datas += collect_data_files("customtkinter")

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
datas += collect_data_files("playwright", include_py_files=False)

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

# O pacote `sigft` inteiro: as views são importadas pelo `main.py`, mas os
# serviços entram por aqueles shims dinâmicos acima.
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


# Ícone do executável.
#
# 1ª escolha: `build/SIG-FT.ico`, que o `Gerar-Executavel.bat` monta com as
#    medidas pequenas (16/24/32/48...) que o Windows usa na barra de tarefas.
# 2ª escolha: o `.ico` do repositório, que tem só 256x256 — serve, mas o
#    Windows reduz na hora e a barra de título fica menos nítida.
#
# Quem chama o `pyinstaller` na mão (sem o .bat) cai na 2ª e ainda assim sai
# com o ícone certo, em vez do ícone genérico do PyInstaller.
_ICONE = os.path.join("build", "SIG-FT.ico")
if not os.path.exists(_ICONE):
    _ICONE = os.path.join("assets", "SIG-FT-logo-2.ico")
if not os.path.exists(_ICONE):
    _ICONE = None

a = Analysis(
    ["frontend.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Módulos de teste não vão para produção.
    excludes=["pytest", "_pytest", "mypy", "ruff"],
    noarchive=False,
)

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
    # `console=True` DE PROPÓSITO, mesmo sendo um app de janela.
    #
    # O SIG-FT.bat já avisa: "Pode fechar esta janela preta só DEPOIS de
    # fechar o SIG-FT -- é nela que aparecem os erros". Isso não é hábito,
    # é o canal de diagnóstico real do app: o splash imprime "Erro ao
    # carregar <módulo>" ali, e foi lendo essa saída que se achou o
    # ícone/logo apontando para o lugar errado depois do CP 7.3.
    #
    # Numa primeira execução em máquina nova -- que é justamente o caso da
    # GE Vernova, com Zscaler no caminho -- esconder o console troca uma
    # mensagem clara ("CERTIFICATE_VERIFY_FAILED") por "não funciona".
    # Quando o app estiver rodando estável lá, vale reconsiderar.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # O PyInstaller no Windows quer `.ico` para o ícone do EXECUTÁVEL. O
    # projeto só tem o `.png` (que serve para a janela, via CustomTkinter,
    # mas não para o arquivo). `Gerar-Executavel.bat` converte o PNG em
    # `build/SIG-FT.ico` antes de chamar o PyInstaller; se a conversão não
    # rolar, o build segue com o ícone padrão em vez de falhar.
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

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

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# =============================================================================
# Recursos que entram no bundle
# =============================================================================
datas = [
    # O ícone da janela e o logo do splash. `resource_path` os acha tanto no
    # .py quanto dentro do .exe.
    ("assets", "assets"),
    # O CHANGELOG: é dele que sai o "o que há de novo" mostrado depois de uma
    # atualização (`sigft/core/novidades.py`). Sem ele no bundle, a janela de
    # novidades abre vazia justamente na hora em que ela importa.
    ("CHANGELOG.md", "."),
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

# O motor do tradutor local importa os dois por NOME (`importlib`), só na
# primeira tradução -- para o resto do app não pagar o custo.
hiddenimports += ["ctranslate2", "sentencepiece"]

# O editor cirúrgico (`sigft/core/excel/cirurgico.py`, 2026-10-05) grava os
# `_STATUS_PMIB` com o lxml -- e o `StatusPMIB` só o importa na hora de gravar.
# A análise estática o acha pelo `collect_submodules("sigft")`; declarado aqui
# para não depender disso, junto com o `_elementpath` que o `etree` carrega por
# dentro. Sem ele, o app abre e a primeira gravação de planilha falha.
hiddenimports += ["lxml.etree", "lxml._elementpath"]


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
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Módulos de teste não vão para produção.
    #
    # `torch` e `transformers`: só a CONVERSÃO do modelo do tradutor os usa
    # (`tools/preparar_tradutor.py`, num ambiente à parte no workflow). O
    # `ctranslate2.converters` tenta importá-los dentro de try/except, e numa
    # máquina de build que os tenha instalados a análise levaria ~800 MB de
    # torch para o instalador.
    excludes=["pytest", "_pytest", "mypy", "ruff", "torch", "transformers"],
    noarchive=False,
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

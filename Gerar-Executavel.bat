@echo off
rem ===========================================================================
rem  SIG-FT -- gera o executavel (dist\SIG-FT\SIG-FT.exe).
rem
rem  Checkpoint 8.3 do plano de refatoracao.
rem
rem  PARA QUE SERVE: distribuir o app para uma maquina que nao tem Python, ou
rem  onde instalar Python/rodar pip nao e permitido. Quem TEM Python continua
rem  usando o SIG-FT.bat, que e mais rapido de atualizar.
rem
rem  DEMORA. Sao centenas de MB (pandas, playwright, Chromium). Da primeira vez
rem  conte varios minutos.
rem ===========================================================================
setlocal
title SIG-FT - gerar executavel

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"

rem --- 1. Ferramenta de build ------------------------------------------------
echo.
echo [1/4] Verificando o PyInstaller...
"%SIGFT_PY%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo       Instalando PyInstaller...
    call :_pip_install pyinstaller
    if errorlevel 1 goto :erro_pip
)

rem --- 2. O navegador do Playwright (OPCIONAL, desligado por padrao) ----------
rem  ATENCAO: embutir o Chromium e OPT-IN desde 2026-08-28, e a mudanca foi
rem  por causa da REVISAO DE SEGURANCA da TI, nao por questao tecnica.
rem
rem  Um Chromium embutido e um navegador que NAO recebe os patches de
rem  seguranca da politica da empresa: ele congela na versao do dia do build e
rem  fica fora do inventario que a TI gerencia. Numa maquina corporativa isso
rem  e a objecao mais forte contra o pacote, e ela e legitima.
rem
rem  O caminho recomendado passou a ser o SIG-FT.bat + Instalar-Playwright.bat:
rem  Python oficial, pacotes do PyPI com versao declarada em requirements.txt,
rem  e o Chromium vindo do canal oficial do Playwright -- atualizavel, e MUITO
rem  mais facil de aprovar. Ver docs/SEGURANCA_TI.md.
rem
rem  Para embutir assim mesmo (maquina sem Python, sem permissao de pip, e com
rem  o aval da TI):
rem      set SIGFT_EMBUTIR_NAVEGADOR=1
rem      Gerar-Executavel.bat
echo.
if not defined SIGFT_EMBUTIR_NAVEGADOR (
    echo [2/4] Navegador NAO embutido ^(padrao^).
    echo       O .exe roda tudo menos o RPA; para o robo do portal, a maquina
    echo       precisa do Chromium do Playwright instalado a parte
    echo       ^(Instalar-Playwright.bat^).
    echo       Para embutir: set SIGFT_EMBUTIR_NAVEGADOR=1 antes de rodar.
    echo       Leia docs/SEGURANCA_TI.md antes -- ha implicacao de seguranca.
    goto :fim_navegador
)

echo [2/4] SIGFT_EMBUTIR_NAVEGADOR=1 -- instalando o navegador DENTRO do pacote...
echo       Lembre-se: o Chromium embutido nao recebe patches pela politica da
echo       empresa. Confirme com a TI antes de distribuir este build.

rem  PLAYWRIGHT_BROWSERS_PATH=0 manda o Playwright instalar o Chromium DENTRO
rem  do proprio pacote (em vez de %LOCALAPPDATA%\ms-playwright). E assim que o
rem  SIG-FT.spec consegue leva-lo junto no bundle.
set "PLAYWRIGHT_BROWSERS_PATH=0"

rem  Rede corporativa: o download do navegador nao passa pelo pip. Quem manda
rem  no processo Node e NODE_EXTRA_CA_CERTS. Se o usuario ja apontou o
rem  certificado da empresa em SSL_CERT_FILE, reaproveitamos (mesma logica do
rem  Instalar-Playwright.bat).
if not defined NODE_EXTRA_CA_CERTS if defined SSL_CERT_FILE (
    set "NODE_EXTRA_CA_CERTS=%SSL_CERT_FILE%"
    echo       Usando o certificado de SSL_CERT_FILE para o download.
)

"%SIGFT_PY%" -m playwright install chromium
if errorlevel 1 (
    echo.
    echo       [AVISO] O navegador NAO foi baixado.
    echo.
    echo       O executavel vai ser gerado assim mesmo, e funciona para tudo
    echo       MENOS o RPA ^(robo do portal^). Isso e proposital: um build que
    echo       para aqui deixaria voce sem nada, e as outras 8 telas funcionam.
    echo.
    echo       Em rede com Zscaler o motivo costuma ser o certificado. Veja o
    echo       README.md, secao "Rede corporativa ^(Zscaler^)", item 3.
    echo.
    pause
)
:fim_navegador

rem --- 3. Icone do executavel ------------------------------------------------
rem
rem  A FONTE e assets\SIG-FT-logo-2.ico -- o icone do SIG-FT, escolhido pelo
rem  usuario em 2026-09-04. O logo.png (GE Vernova) NAO entra aqui: ele e a
rem  imagem desenhada DENTRO da tela, nao o icone do app.
rem
rem  Por que reescrever o .ico em vez de usar o arquivo direto: o original tem
rem  UM tamanho so, 256x256. O Windows pede 16, 32 e 48 para a barra de
rem  tarefas e a barra de titulo -- sem eles ele reduz o 256 na hora, e sai
rem  borrado. Este passo gera as medidas pequenas uma vez, no build.
echo.
echo [3/4] Preparando o icone...
if not exist "build" mkdir "build"
"%SIGFT_PY%" -c "from PIL import Image; Image.open('assets/SIG-FT-logo-2.ico').save('build/SIG-FT.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])" 2>nul
if not exist "build\SIG-FT.ico" (
    echo       [aviso] Nao consegui preparar o assets\SIG-FT-logo-2.ico.
    echo               Tentando o logo.png como reserva...
    "%SIGFT_PY%" -c "from PIL import Image; Image.open('assets/logo.png').save('build/SIG-FT.ico', sizes=[(16,16),(32,32),(48,48),(256,256)])" 2>nul
)
if not exist "build\SIG-FT.ico" (
    echo       [aviso] O executavel sai com o icone padrao. Nao e impeditivo.
)

rem --- 4. O build -------------------------------------------------------------
rem  CONSTROI EM CAMINHO CURTO, e isso nao e capricho.
rem
rem  O Windows limita caminho a 260 caracteres (MAX_PATH), e por padrao esse
rem  limite esta LIGADO (HKLM\SYSTEM\CurrentControlSet\Control\FileSystem
rem  -> LongPathsEnabled = 0). A arvore interna do Chromium sozinha ja tem
rem  ~157 caracteres:
rem
rem    \_internal\playwright\driver\package\.local-browsersrem    chromium_headless_shell-1234\chrome-headless-shell-win64\...
rem
rem  Com o projeto dentro do OneDrive (que e o caso), a raiz ja gasta ~93.
rem  Soma: estoura, e o PyInstaller morre no meio da copia com
rem  "WinError 206: O nome do arquivo ou a extensao e muito grande" -- deixando
rem  um dist/ pela metade que PARECE pronto.
rem
rem  Medido nesta maquina em 2026-08-27. Por isso build e trabalho vao para
rem  %LOCALAPPDATA%\SIG-FT (curto, e onde o venv ja mora), e so o resultado e
rem  copiado de volta.
set "SIGFT_BUILD_DIR=%LOCALAPPDATA%\SIG-FT\build-exe"
set "SIGFT_DIST_DIR=%LOCALAPPDATA%\SIG-FT\dist-exe"

echo.
echo [4/4] Gerando o executavel. Isto DEMORA -- va tomar um cafe.
echo       Trabalhando em %SIGFT_DIST_DIR%
echo       ^(caminho curto: a arvore do Chromium estoura o limite de 260
echo        caracteres do Windows se o build sair de dentro do OneDrive^)
echo.
rem  ANTES de empacotar: o codigo compila?
rem
rem  Isto existe por um caso real de 2026-09-04. Um modulo (sigft/app/main.py)
rem  ficou com erro de sintaxe, e o PyInstaller empacotou assim mesmo,
rem  SEM RECLAMAR -- terminou dizendo "PRONTO", com o .exe no lugar e o
rem  tamanho certo. O modulo quebrado simplesmente nao entrou, e o app morria
rem  na abertura com "ModuleNotFoundError: No module named 'sigft.app.main'".
rem
rem  Um build que produz pacote quebrado e diz que deu certo e pior do que um
rem  build que falha. Dois segundos de compileall fecham essa porta.
echo       Conferindo a sintaxe do codigo...
"%SIGFT_PY%" -m compileall -q frontend.py sigft >nul
if errorlevel 1 (
    echo.
    echo [ERRO] Ha erro de SINTAXE no codigo. O PyInstaller empacotaria assim
    echo        mesmo e o .exe morreria na abertura. Corrija antes.
    echo.
    "%SIGFT_PY%" -m compileall frontend.py sigft
    goto :erro_build
)

"%SIGFT_PY%" -m PyInstaller --noconfirm --clean ^
    --distpath "%SIGFT_DIST_DIR%" ^
    --workpath "%SIGFT_BUILD_DIR%" ^
    SIG-FT.spec
if errorlevel 1 goto :erro_build

echo.
echo [4/4] Copiando o resultado para dist\SIG-FT ...
if exist "%~dp0dist\SIG-FT" rmdir /s /q "%~dp0dist\SIG-FT"
if not exist "%~dp0dist" mkdir "%~dp0dist"
rem  /MIR e nao /E -- PRECAUCAO, nao correcao de defeito observado.
rem
rem  Nos builds medidos em 2026-09-04 o `rmdir /s /q` da linha acima sempre
rem  funcionou, e o dist bateu com a saida do PyInstaller. Mas a combinacao e
rem  fragil: `rmdir` FALHA em silencio quando a pasta tem caminho acima de
rem  260 caracteres (a arvore do Chromium chega la), e o /E so ACRESCENTA.
rem  Se o rmdir falhar, o dist vira mistura de dois builds -- parece pronto e
rem  leva arquivos que o build atual nao colocou, e a unica pista e o
rem  tamanho, que ninguem confere.
rem
rem  /MIR espelha: o que nao existe na origem e APAGADO no destino. Fecha a
rem  brecha sem depender de o rmdir ter dado certo.
robocopy "%SIGFT_DIST_DIR%\SIG-FT" "%~dp0dist\SIG-FT" /MIR /NFL /NDL /NJH /NJS /NP >nul
rem  robocopy usa codigos < 8 para sucesso; 8+ e erro de verdade.
if errorlevel 8 (
    echo.
    echo       [AVISO] Nao consegui copiar para dist\SIG-FT -- provavelmente o
    echo               mesmo limite de 260 caracteres, agora na copia.
    echo.
    echo       O executavel ESTA PRONTO e funciona, em:
    echo               %SIGFT_DIST_DIR%\SIG-FT
    echo       Distribua a partir dali.
    echo.
    pause
    endlocal
    exit /b 0
)

echo.
echo ===========================================================================
echo  PRONTO: dist\SIG-FT\SIG-FT.exe
echo.
echo  COMO DISTRIBUIR: copie a PASTA dist\SIG-FT inteira. O .exe sozinho nao
echo  funciona -- ele depende dos arquivos ao lado.
echo.
echo  NA MAQUINA DE DESTINO, as chaves de API e as preferencias sao gravadas
echo  AO LADO do .exe (api_config.json, user_prefs.json, logs\). Por isso a
echo  pasta precisa ficar num lugar onde o usuario tenha permissao de ESCRITA
echo  -- a Area de Trabalho ou Documentos servem; "C:\Program Files" nao.
echo.
echo  Detalhes e solucao de problemas: docs\BUILD.md
echo ===========================================================================
echo.
pause
endlocal
exit /b 0

rem ---------------------------------------------------------------------------
:_pip_install
rem  Respeita a configuracao de pip da maquina (rede corporativa), igual ao
rem  _bootstrap_venv.bat: SIGFT_PIP_ARGS > pip_corporativo.txt > padrao.
set "_ARGS=--isolated --index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org"
if defined SIGFT_PIP_ARGS set "_ARGS=%SIGFT_PIP_ARGS%"
if not defined SIGFT_PIP_ARGS if exist "%~dp0pip_corporativo.txt" (
    for /f "usebackq tokens=* delims=" %%L in ("%~dp0pip_corporativo.txt") do (
        echo %%L | findstr /b "#" >nul || if not defined _LIDO (
            set "_ARGS=%%L"
            set "_LIDO=1"
        )
    )
)
"%SIGFT_PY%" -m pip install %_ARGS% %1
exit /b %errorlevel%

:erro_pip
echo.
echo [ERRO] Nao consegui instalar o PyInstaller.
echo.
echo        Em rede corporativa, copie pip_corporativo.txt.exemplo para
echo        pip_corporativo.txt e ajuste. Veja o README.md.
echo.
pause
endlocal
exit /b 1

:erro_build
echo.
echo [ERRO] O PyInstaller falhou. As mensagens acima dizem o motivo.
echo        Problemas comuns estao em docs\BUILD.md.
echo.
pause
endlocal
exit /b 1

:erro
echo.
echo [SIG-FT] Nao consegui preparar o ambiente. Leia as mensagens acima.
echo.
pause
endlocal
exit /b 1

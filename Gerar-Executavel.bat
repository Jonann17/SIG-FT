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

rem --- 2. O navegador do Playwright DENTRO do pacote --------------------------
rem  Este passo e o que faz o RPA funcionar na maquina da empresa.
rem
rem  PLAYWRIGHT_BROWSERS_PATH=0 manda o Playwright instalar o Chromium DENTRO
rem  do proprio pacote (em vez de %LOCALAPPDATA%\ms-playwright). E assim que o
rem  SIG-FT.spec consegue leva-lo junto no bundle -- e quem rodar o .exe nao
rem  precisa baixar nada, o que importa porque esse download e feito por um
rem  processo Node que costuma ser barrado pelo Zscaler.
echo.
echo [2/4] Instalando o navegador DENTRO do pacote (para ir junto no .exe)...
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

rem --- 3. Icone do executavel ------------------------------------------------
echo.
echo [3/4] Preparando o icone...
if not exist "build" mkdir "build"
"%SIGFT_PY%" -c "from PIL import Image; Image.open('assets/logo.png').save('build/SIG-FT.ico', sizes=[(16,16),(32,32),(48,48),(256,256)])" 2>nul
if errorlevel 1 (
    echo       [aviso] Nao consegui converter o PNG em .ico.
    echo               O executavel sai com o icone padrao. Nao e impeditivo.
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
set "SIGFT_BUILD_DIR=%LOCALAPPDATA%\SIG-FTuild-exe"
set "SIGFT_DIST_DIR=%LOCALAPPDATA%\SIG-FT\dist-exe"

echo.
echo [4/4] Gerando o executavel. Isto DEMORA -- va tomar um cafe.
echo       Trabalhando em %SIGFT_DIST_DIR%
echo       ^(caminho curto: a arvore do Chromium estoura o limite de 260
echo        caracteres do Windows se o build sair de dentro do OneDrive^)
echo.
"%SIGFT_PY%" -m PyInstaller --noconfirm --clean ^
    --distpath "%SIGFT_DIST_DIR%" ^
    --workpath "%SIGFT_BUILD_DIR%" ^
    SIG-FT.spec
if errorlevel 1 goto :erro_build

echo.
echo [4/4] Copiando o resultado para dist\SIG-FT ...
if exist "%~dp0dist\SIG-FT" rmdir /s /q "%~dp0dist\SIG-FT"
if not exist "%~dp0dist" mkdir "%~dp0dist"
robocopy "%SIGFT_DIST_DIR%\SIG-FT" "%~dp0dist\SIG-FT" /E /NFL /NDL /NJH /NJS /NP >nul
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

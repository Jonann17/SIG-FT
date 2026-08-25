@echo off
rem ===========================================================================
rem  SIG-FT -- bootstrap do ambiente virtual (script interno)
rem
rem  Nao rode este arquivo direto. Ele e chamado por:
rem     SIG-FT.bat          -> abre o aplicativo
rem     Testar-SIG-FT.bat   -> roda a suite de testes
rem
rem  O que faz:
rem     1. escolhe/cria o ambiente virtual (venv);
rem     2. instala requirements.txt (e requirements-dev.txt se SIGFT_DEV=1)
rem        so quando o arquivo mudou desde a ultima instalacao;
rem     3. devolve o caminho do venv em %SIGFT_VENV_DIR%.
rem
rem  Nao usa "setlocal": roda no escopo de quem chamou, para que
rem  %SIGFT_VENV_DIR% chegue de volta.
rem
rem  NOTA: mensagens sem acentos de proposito -- o console do Windows usa
rem  code page 850/437 e acentos em .bat saem embaralhados.
rem ===========================================================================

rem --- raiz do repositorio (este script vive em <raiz>\scripts\) -------------
for %%I in ("%~dp0..") do set "SIGFT_RAIZ=%%~fI"

rem --- 1. onde fica o venv --------------------------------------------------
rem Ordem: variavel SIGFT_VENV > .venv do projeto > %LOCALAPPDATA% > criar novo.
set "SIGFT_VENV_DIR="
if defined SIGFT_VENV set "SIGFT_VENV_DIR=%SIGFT_VENV%"
if not defined SIGFT_VENV_DIR if exist "%SIGFT_RAIZ%\.venv\Scripts\python.exe" set "SIGFT_VENV_DIR=%SIGFT_RAIZ%\.venv"
if not defined SIGFT_VENV_DIR if exist "%LOCALAPPDATA%\SIG-FT\venv\Scripts\python.exe" set "SIGFT_VENV_DIR=%LOCALAPPDATA%\SIG-FT\venv"
if not defined SIGFT_VENV_DIR call :_escolher_local_novo

rem --- 2. cria o venv se ainda nao existe ------------------------------------
if not exist "%SIGFT_VENV_DIR%\Scripts\python.exe" (
    call :_criar_venv
    if errorlevel 1 exit /b 1
)
set "SIGFT_PY=%SIGFT_VENV_DIR%\Scripts\python.exe"

rem --- 3. dependencias ------------------------------------------------------
call :_resolver_pip_args
call :_instalar "%SIGFT_RAIZ%\requirements.txt" requirements
if errorlevel 1 exit /b 1
if defined SIGFT_DEV (
    call :_instalar "%SIGFT_RAIZ%\requirements-dev.txt" requirements-dev
    if errorlevel 1 exit /b 1
)

rem --- 4. navegador do Playwright -------------------------------------------
rem Por que isto NAO vem junto com o `pip install`: o pacote `playwright` do
rem PyPI traz so a biblioteca Python. O navegador (Chromium, ~150 MB) e um
rem binario baixado a parte, pelo processo Node do Playwright -- nao existe
rem wheel que o carregue. Por isso precisa de um passo proprio.
rem
rem Roda UMA vez (carimbo no venv) e NUNCA derruba a instalacao: em rede
rem corporativa este download e o que mais falha, e o SIG-FT funciona sem ele
rem -- o motor de RPA e o Playwright, e a leitura de pagina por navegador
rem no AutoSpec e um recurso de ultimo recurso, opcional por desenho.
call :_instalar_navegador

exit /b 0


rem ===========================================================================
rem  Sub-rotinas
rem ===========================================================================

:_escolher_local_novo
rem Por padrao o venv vai para <raiz>\.venv. Mas se o projeto estiver dentro de
rem OneDrive/Box/Dropbox/Google Drive, o servico tentaria sincronizar dezenas de
rem milhares de arquivos -- ai o venv vai para fora da pasta sincronizada.
set "SIGFT_VENV_DIR=%SIGFT_RAIZ%\.venv"
call :_pasta_sincronizada "%SIGFT_RAIZ%"
if errorlevel 1 (
    set "SIGFT_VENV_DIR=%LOCALAPPDATA%\SIG-FT\venv"
    echo [SIG-FT] A pasta do projeto esta dentro de um servico de sincronizacao
    echo          ^(OneDrive/Box/Dropbox/Google Drive^). Para nao sincronizar
    echo          milhares de arquivos, o ambiente virtual vai ficar fora dela:
    echo          %LOCALAPPDATA%\SIG-FT\venv
    echo.
)
exit /b 0

:_pasta_sincronizada
rem errorlevel 1 = parece pasta sincronizada
echo(%~1|find /i "onedrive" >nul && exit /b 1
echo(%~1|find /i "\dropbox" >nul && exit /b 1
echo(%~1|find /i "\box\" >nul && exit /b 1
echo(%~1|find /i "\box sync" >nul && exit /b 1
echo(%~1|find /i "google drive" >nul && exit /b 1
echo(%~1|find /i "googledrive" >nul && exit /b 1
exit /b 0

:_criar_venv
echo [SIG-FT] Primeira execucao: criando o ambiente virtual em
echo          %SIGFT_VENV_DIR%
echo          Isso baixa as dependencias e leva alguns minutos. Nas proximas
echo          vezes o aplicativo abre direto.
echo.
call :_achar_python
if not defined SIGFT_PY_BASE (
    echo [ERRO] Python 3 nao foi encontrado neste computador.
    echo        Instale o Python 3.12 em https://www.python.org/downloads/
    echo        e marque "Add python.exe to PATH" na primeira tela do instalador.
    exit /b 1
)
echo [SIG-FT] Usando o interpretador: %SIGFT_PY_BASE%
%SIGFT_PY_BASE% -m venv "%SIGFT_VENV_DIR%"
if not exist "%SIGFT_VENV_DIR%\Scripts\python.exe" (
    echo.
    echo [ERRO] Nao consegui criar o ambiente virtual em:
    echo        %SIGFT_VENV_DIR%
    echo        Verifique se voce tem permissao de escrita nessa pasta.
    exit /b 1
)
exit /b 0

:_achar_python
set "SIGFT_PY_BASE="
for %%V in (3.12 3.13 3.11 3.10) do call :_testar_python "py -%%V"
if not defined SIGFT_PY_BASE call :_testar_python "py -3"
if not defined SIGFT_PY_BASE call :_testar_python "python"
exit /b 0

:_testar_python
rem Aceita 3.10+ . O teste evita os sinais "<" e ">" de proposito: dentro de um
rem .bat eles sao operadores de redirecionamento e so as aspas os protegem --
rem "in [(3, m) for m in range(10, 40)]" diz a mesma coisa sem depender disso.
if defined SIGFT_PY_BASE exit /b 0
%~1 -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3, m) for m in range(10, 40)] else 1)" >nul 2>&1 && set "SIGFT_PY_BASE=%~1"
exit /b 0

:_resolver_pip_args
rem Rede corporativa com inspecao SSL (Zscaler e afins) costuma quebrar o pip.
rem Estes argumentos resolvem o caso mais comum. Para ajustar sem editar este
rem arquivo, use (nesta ordem de prioridade):
rem    1. variavel de ambiente SIGFT_PIP_ARGS
rem    2. arquivo pip_corporativo.txt na raiz (1a linha nao-comentada)
rem Veja pip_corporativo.txt.exemplo.
set "SIGFT_PIP_ARGS_EFETIVO=--isolated --index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org"
if exist "%SIGFT_RAIZ%\pip_corporativo.txt" (
    set "_pip_achou="
    for /f "usebackq eol=# tokens=* delims=" %%L in ("%SIGFT_RAIZ%\pip_corporativo.txt") do call :_primeira_linha_pip "%%L"
)
if defined SIGFT_PIP_ARGS set "SIGFT_PIP_ARGS_EFETIVO=%SIGFT_PIP_ARGS%"
exit /b 0

:_primeira_linha_pip
if defined _pip_achou exit /b 0
if "%~1"=="" exit /b 0
set "_pip_achou=1"
set "SIGFT_PIP_ARGS_EFETIVO=%~1"
echo [SIG-FT] Argumentos de pip vindos de pip_corporativo.txt.
exit /b 0

:_instalar
rem %1 = arquivo de requirements   %2 = nome curto do carimbo
rem So reinstala quando o arquivo mudou -- o carimbo guarda o hash da ultima
rem instalacao bem-sucedida dentro do proprio venv.
if not exist "%~1" exit /b 0
call :_hash_arquivo "%~1"
set "_stamp=%SIGFT_VENV_DIR%\.sigft-%~2.stamp"
set "_hash_ant="
if exist "%_stamp%" set /p _hash_ant=<"%_stamp%"
if /i "%_hash_ant%"=="%_hash%" exit /b 0
echo.
echo [SIG-FT] Instalando as dependencias de %~nx1 ...
rem Atualizar o pip e so uma cortesia: se falhar, seguimos com o pip do venv --
rem por isso nao ha checagem de errorlevel nesta linha, so na de baixo.
"%SIGFT_PY%" -m pip install --upgrade pip %SIGFT_PIP_ARGS_EFETIVO%
"%SIGFT_PY%" -m pip install %SIGFT_PIP_ARGS_EFETIVO% -r "%~1"
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar as dependencias de %~nx1.
    call :_dica_rede
    exit /b 1
)
>"%_stamp%" echo %_hash%
echo [SIG-FT] Dependencias de %~nx1 instaladas.
echo.
exit /b 0

:_instalar_navegador
rem Pula se ja foi feito, se o usuario desligou, ou se nao ha playwright.
if defined SIGFT_SEM_NAVEGADOR exit /b 0
set "_stamp_nav=%SIGFT_VENV_DIR%\.sigft-playwright.stamp"
if exist "%_stamp_nav%" exit /b 0
"%SIGFT_PY%" -c "import playwright" >nul 2>&1
if errorlevel 1 exit /b 0

rem Ja instalado por fora (Instalar-Playwright.bat, ou outro projeto)? Entao
rem so carimba, sem baixar 150 MB de novo.
"%SIGFT_PY%" -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop()" >nul 2>&1
if not errorlevel 1 (
    >"%_stamp_nav%" echo ok
    exit /b 0
)

echo.
echo [SIG-FT] Baixando o navegador Chromium ^(~150 MB, so na primeira vez^).
echo          Ele serve para dois recursos OPCIONAIS: o motor novo de RPA e a
echo          leitura de paginas de fabricante que so montam com JavaScript.
echo          Se falhar, o aplicativo funciona do mesmo jeito.
echo.
rem Rede com inspecao SSL: o download nao passa pelo pip, e sim pelo processo
rem Node do Playwright, que ignora as variaveis do Python. Quem manda nele e
rem NODE_EXTRA_CA_CERTS -- ver Instalar-Playwright.bat e o README.
if not defined NODE_EXTRA_CA_CERTS if defined SSL_CERT_FILE (
    set "NODE_EXTRA_CA_CERTS=%SSL_CERT_FILE%"
)
"%SIGFT_PY%" -m playwright install chromium
if errorlevel 1 (
    echo.
    echo [SIG-FT] Nao consegui baixar o navegador -- SEGUINDO ASSIM MESMO.
    echo          Os dois recursos que dependem dele ficam indisponiveis; todo
    echo          o resto funciona. Para tentar de novo com as dicas de rede
    echo          corporativa, rode o Instalar-Playwright.bat.
    echo.
    exit /b 0
)
>"%_stamp_nav%" echo ok
echo [SIG-FT] Navegador instalado.
echo.
exit /b 0

:_hash_arquivo
set "_hash="
for /f "usebackq skip=1 tokens=* delims=" %%H in (`certutil -hashfile "%~1" SHA256 2^>nul`) do call :_primeira_linha_hash "%%H"
rem Sem certutil: cai para data+tamanho, que tambem muda quando o arquivo muda.
if not defined _hash for %%F in ("%~1") do set "_hash=%%~tF-%%~zF"
exit /b 0

:_primeira_linha_hash
if defined _hash exit /b 0
echo(%~1|find /i "certutil" >nul && exit /b 0
set "_hash=%~1"
set "_hash=%_hash: =%"
exit /b 0

:_dica_rede
echo.
echo        Se voce esta em rede corporativa com inspecao SSL ^(Zscaler^), o pip
echo        costuma falhar com "SSLError" ou "CERTIFICATE_VERIFY_FAILED".
echo        Copie pip_corporativo.txt.exemplo para pip_corporativo.txt e ajuste
echo        os argumentos ^(indice interno, proxy, --trusted-host^) conforme o
echo        que o time de TI indicar. Detalhes no README.md, secao
echo        "Rede corporativa ^(Zscaler^)".
exit /b 0

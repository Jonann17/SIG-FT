@echo off
title Iniciando SIG-FT...

REM ===========================================================================
REM  SIG-FT -- abre o aplicativo na maquina do usuario.
REM
REM  Mesmo esquema do "DocManager Itaipu.bat": o ZIP fica no Box, este arquivo
REM  ve se ha versao nova, baixa, extrai em %LOCALAPPDATA% e abre.
REM
REM  ESTE ARQUIVO E O ZIP FICAM NO BOX. O usuario clica aqui e mais nada.
REM  Nao precisa de Python, nao precisa compilar, nao precisa de permissao de
REM  administrador.
REM
REM  ATUALIZAR = trocar o SIG-FT.zip no Box. Na proxima abertura, este script
REM  percebe sozinho.
REM ===========================================================================

REM =========================================================================
REM 1. Caminho padrao da pasta no Box
REM =========================================================================
REM  A pasta e:
REM     %USERPROFILE%\Box\CMI - Consorcio Itaipu\11 - Ger. Engenharia\
REM        15 - PDM\_python_pdm
REM
REM  ATENCAO ao "Consorcio": no Box ele tem ACENTO, e um .bat NAO pode conter
REM  esse caractere. O arquivo e lido na pagina de codigo do console (850/437),
REM  nao em UTF-8, e o acento vira lixo -- o caminho deixa de casar e o usuario
REM  cai no seletor de pasta sem entender por que.
REM
REM  Por isso o curinga Cons*rcio: o "for /d" resolve o nome real da pasta,
REM  com acento e tudo, sem que o acento precise existir neste arquivo.
set "REDE="
for /d %%D in ("%USERPROFILE%\Box\CMI - Cons*rcio Itaipu") do (
    set "REDE=%%D\11 - Ger. Engenharia\15 - PDM\_python_pdm"
)

if defined REDE if exist "%REDE%\SIG-FT.zip" goto :copiar

REM =========================================================================
REM FALLBACK: nao achou no caminho padrao -> pede a pasta ao usuario
REM =========================================================================
echo O arquivo SIG-FT.zip nao foi encontrado no caminho padrao.
echo Abrindo janela para voce selecionar a pasta onde ele esta...
echo.

for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -Command "Add-Type -AssemblyName System.windows.forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = 'O SIG-FT nao foi encontrado. Selecione a pasta onde esta o arquivo SIG-FT.zip:'; $f.ShowNewFolderButton = $false; if($f.ShowDialog() -eq 'OK'){ $f.SelectedPath }"`) do set "REDE=%%I"

if not exist "%REDE%\SIG-FT.zip" (
    echo.
    echo ERRO: O arquivo SIG-FT.zip nao foi encontrado na pasta selecionada,
    echo       ou voce cancelou.
    echo       Verifique se o seu Box esta sincronizado e tente novamente.
    pause
    exit
)

:copiar
REM =========================================================================
REM 2. Sincronizacao e extracao blindada
REM =========================================================================
set "LOCAL=%LOCALAPPDATA%\SIG-FT_CMI"
if not exist "%LOCAL%" mkdir "%LOCAL%"

echo Verificando se ha atualizacoes do sistema...
robocopy "%REDE%" "%LOCAL%" SIG-FT.zip /XO /FFT >nul 2>&1
set "ROBO_ERR=%ERRORLEVEL%"

set "PRECISA_EXTRAIR=0"

REM robocopy: codigos 1..7 = copiou alguma coisa; 8+ = erro de verdade.
if %ROBO_ERR% GTR 0 if %ROBO_ERR% LSS 8 set "PRECISA_EXTRAIR=1"

REM TRAVA DE SEGURANCA: se o .exe nao esta la, extrai mesmo sem download novo.
REM O caso real e o antivirus corporativo apagar o executavel depois da
REM primeira extracao -- sem esta linha, o app simplesmente nunca mais abriria
REM e o robocopy diria que esta tudo em dia.
if not exist "%LOCAL%\SIG-FT\SIG-FT.exe" if not exist "%LOCAL%\SIG-FT.exe" set "PRECISA_EXTRAIR=1"

if "%PRECISA_EXTRAIR%"=="1" (
    echo.
    echo Preparando o sistema para uso ou instalando atualizacao...
    taskkill /F /IM SIG-FT.exe >nul 2>&1
    tar -xf "%LOCAL%\SIG-FT.zip" -C "%LOCAL%"
)

REM =========================================================================
REM 3. Navegador do RPA -- usa o Chrome/Edge JA instalado na maquina
REM =========================================================================
REM  O pacote NAO leva navegador dentro, de proposito: um Chromium embutido
REM  congela na versao do dia do build e fica fora do que a TI atualiza.
REM
REM  Aqui apontamos para o navegador que a propria empresa ja instala e
REM  mantem. Se nenhum for achado, o app abre igual -- so o RPA (robo do
REM  portal) e que fica sem navegador, e ele avisa na hora.
if not defined SIGFT_PLAYWRIGHT_EXECUTABLE (
    if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
        set "SIGFT_PLAYWRIGHT_EXECUTABLE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    ) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
        set "SIGFT_PLAYWRIGHT_EXECUTABLE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    ) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
        set "SIGFT_PLAYWRIGHT_EXECUTABLE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    ) else if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
        set "SIGFT_PLAYWRIGHT_EXECUTABLE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
    ) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
        set "SIGFT_PLAYWRIGHT_EXECUTABLE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
    )
)

if defined SIGFT_PLAYWRIGHT_EXECUTABLE (
    echo Navegador do RPA: %SIGFT_PLAYWRIGHT_EXECUTABLE%
) else (
    echo [i] Nenhum Chrome/Edge encontrado. O app abre normalmente; so o robo
    echo     do portal e que vai reclamar de navegador quando for usado.
)

REM Certificado da empresa (Zscaler e afins): se a TI ja apontou um bundle em
REM SSL_CERT_FILE, o Node do Playwright tambem passa a respeita-lo.
if not defined NODE_EXTRA_CA_CERTS if defined SSL_CERT_FILE (
    set "NODE_EXTRA_CA_CERTS=%SSL_CERT_FILE%"
)

:abrir
REM  O /d NAO e detalhe: ele define o DIRETORIO DE TRABALHO do aplicativo.
REM
REM  Sem ele, o .exe herda o diretorio de onde este .bat foi clicado -- ou
REM  seja, a PASTA DO BOX. E "api_config.json" e "user_prefs.json" sao
REM  resolvidos a partir do diretorio de trabalho. O estrago seria duplo: o
REM  app procuraria as chaves de API no Box (e nao acharia), e gravaria o
REM  user_prefs.json de cada usuario LA, um por cima do outro.
if exist "%LOCAL%\SIG-FT\SIG-FT.exe" (
    start "" /d "%LOCAL%\SIG-FT" "%LOCAL%\SIG-FT\SIG-FT.exe"
    exit
)

if exist "%LOCAL%\SIG-FT.exe" (
    start "" /d "%LOCAL%" "%LOCAL%\SIG-FT.exe"
    exit
)

echo.
echo ERRO CRITICO: O executavel nao foi encontrado apos a extracao.
echo.
echo Duas possiveis causas:
echo 1. O arquivo SIG-FT.zip la no Box esta corrompido ou incompleto
echo    (o Box pode nao ter terminado de sincronizar -- veja o icone dele).
echo 2. O Antivirus corporativo apagou o executavel achando que era ameaca.
echo    Executavel gerado por PyInstaller sem assinatura digital e um falso
echo    positivo comum; nesse caso, peca a liberacao a TI.
echo.
pause
exit

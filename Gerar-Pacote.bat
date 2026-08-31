@echo off
rem ===========================================================================
rem  SIG-FT -- gera o SIG-FT.zip para distribuir pelo Box.
rem
rem  QUEM USA: so voce, na sua maquina. Quem vai USAR o SIG-FT na GE Vernova
rem  nao roda isto -- roda o "SIG-FT Itaipu.bat", que baixa e abre sozinho.
rem
rem  O ESQUEMA (o mesmo do DocManager):
rem     1. este .bat compila e zipa           -> SIG-FT.zip
rem     2. voce copia o .zip para o Box
rem     3. na maquina da empresa, "SIG-FT Itaipu.bat" ve que ha versao nova,
rem        baixa, extrai em %LOCALAPPDATA% e abre.
rem
rem  ATUALIZAR o app na empresa = trocar o .zip no Box. Nada alem disso.
rem ===========================================================================
setlocal
title SIG-FT - gerar pacote para o Box

cd /d "%~dp0"

rem --- 1. Compila (o Gerar-Executavel.bat cuida do venv e do PyInstaller) ----
echo.
echo  ============================================================
echo   [1/3] Compilando...
echo  ============================================================
echo.
call "%~dp0Gerar-Executavel.bat"
if errorlevel 1 goto :erro_build

if not exist "dist\SIG-FT\SIG-FT.exe" (
    echo.
    echo [ERRO] O build terminou mas dist\SIG-FT\SIG-FT.exe nao existe.
    goto :erro_build
)

rem --- 2. Zipa a PASTA (nao o .exe solto) -----------------------------------
rem  O build e --onedir de proposito (ver SIG-FT.spec): com --onefile o app
rem  descompacta tudo num temporario novo A CADA execucao, e as chaves de API
rem  gravadas ao lado do .exe se perderiam toda vez.
rem
rem  O zip guarda a PASTA "SIG-FT" inteira, para o launcher extrair e achar
rem  "SIG-FT\SIG-FT.exe" -- o mesmo formato que o DocManager.zip usa.
echo.
echo  ============================================================
echo   [2/3] Compactando dist\SIG-FT  ->  SIG-FT.zip
echo  ============================================================
echo.
if exist "SIG-FT.zip" del /q "SIG-FT.zip"

rem `tar` vem no Windows 10/11 e cria zip sem depender de PowerShell lento.
tar -a -c -f "SIG-FT.zip" -C "dist" "SIG-FT"
if errorlevel 1 goto :erro_zip
if not exist "SIG-FT.zip" goto :erro_zip

rem --- 3. Relatorio ---------------------------------------------------------
echo.
echo  ============================================================
echo   [3/3] Pronto.
echo  ============================================================
echo.
for %%A in ("SIG-FT.zip") do echo   Arquivo: %%~fA
for %%A in ("SIG-FT.zip") do set /a TAM_MB=%%~zA/1048576
echo   Tamanho: aproximadamente %TAM_MB% MB
echo.
echo   PROXIMO PASSO: copie o SIG-FT.zip para
echo      %%USERPROFILE%%\Box\SIG-FT Itaipu\
echo   junto com o arquivo "SIG-FT Itaipu.bat".
echo.
echo   Na maquina da empresa, o usuario clica no "SIG-FT Itaipu.bat" e
echo   pronto -- ele detecta a versao nova, baixa e abre.
echo.

rem --- Aviso sobre o navegador do RPA ---------------------------------------
if not defined SIGFT_EMBUTIR_NAVEGADOR (
    echo  ------------------------------------------------------------
    echo   [i] Este pacote NAO leva o Chromium do Playwright dentro.
    echo.
    echo       Nao e esquecimento: um navegador embutido congela na versao
    echo       do dia do build e fica fora do que a TI atualiza -- e a
    echo       objecao mais forte numa revisao de seguranca corporativa.
    echo.
    echo       Na maquina da empresa o RPA usa o Chrome/Edge que JA esta
    echo       instalado la, e o "SIG-FT Itaipu.bat" acha isso sozinho.
    echo       Ver docs\SEGURANCA_TI.md.
    echo  ------------------------------------------------------------
    echo.
)

pause
endlocal
exit /b 0

:erro_zip
echo.
echo [ERRO] Nao consegui criar o SIG-FT.zip.
echo        Verifique se ha espaco em disco e se a pasta dist\SIG-FT existe.
echo.
pause
endlocal
exit /b 1

:erro_build
echo.
echo [ERRO] A compilacao falhou -- o pacote NAO foi gerado.
echo        As mensagens acima dizem o motivo; docs\BUILD.md tem os casos comuns.
echo.
pause
endlocal
exit /b 1

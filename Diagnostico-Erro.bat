@echo off
rem ===========================================================================
rem  SIG-FT -- roda o aplicativo GRAVANDO tudo num arquivo.
rem
rem  PARA QUE SERVE: quando o app fecha sozinho, ou mostra uma mensagem e some
rem  rapido demais para ler. A janela preta normal fecha junto com o app e
rem  leva o erro embora; aqui ele fica gravado em disco.
rem
rem  COMO USAR
rem    1. clique duas vezes neste arquivo;
rem    2. reproduza o problema (rode a mesma ficha, clique no mesmo botao);
rem    3. quando o app fechar, o erro estara em  logs\erro_<data>_<hora>.txt
rem       -- o caminho aparece na tela no fim.
rem
rem  O arquivo tem so o que o Python escreveu: nenhuma ficha, nenhuma planilha,
rem  nenhuma chave de API. Da para mandar sem medo.
rem ===========================================================================
setlocal
title SIG-FT - diagnostico de erro

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

rem Carimbo de data/hora sem depender do formato regional (WMIC devolve
rem sempre AAAAMMDDHHMMSS). Se o WMIC nao existir, cai para um nome fixo.
set "CARIMBO="
for /f "skip=1 tokens=1" %%d in ('wmic os get localdatetime 2^>nul') do (
    if not defined CARIMBO set "CARIMBO=%%d"
)
if not defined CARIMBO set "CARIMBO=ultimo"
set "SAIDA=%~dp0logs\erro_%CARIMBO:~0,8%_%CARIMBO:~8,6%.txt"

echo.
echo  ============================================================
echo   Gravando tudo em:
echo   %SAIDA%
echo  ============================================================
echo.
echo  Reproduza o problema agora. Quando o SIG-FT fechar, volte aqui.
echo.

rem 2^>^&1 junta o canal de ERRO com o normal: o traceback do Python sai no
rem canal de erro, e sem isso ele nao entraria no arquivo -- que e justamente
rem o que precisamos ver.
"%SIGFT_PY%" -X faulthandler "%~dp0frontend.py" > "%SAIDA%" 2>&1

echo.
echo  ============================================================
echo   O SIG-FT fechou. O que ele escreveu esta em:
echo.
echo   %SAIDA%
echo.
echo   Ultimas linhas:
echo  ============================================================
echo.
powershell -NoProfile -Command "if (Test-Path '%SAIDA%') { Get-Content '%SAIDA%' -Tail 25 } else { 'O arquivo nao foi criado.' }"
echo.
echo  ============================================================
echo   Mande o arquivo acima (ou o texto que apareceu) para analise.
echo  ============================================================
echo.
pause
endlocal
exit /b 0

:erro
echo.
echo [SIG-FT] Nao consegui preparar o ambiente. Leia as mensagens acima.
echo.
pause
endlocal
exit /b 1

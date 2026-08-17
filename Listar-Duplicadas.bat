@echo off
rem ===========================================================================
rem  Lista as fichas DUPLICADAS de um _STATUS_PMIB -- clique duas vezes.
rem
rem  SO LE a planilha: nao abre navegador, nao toca no portal PMIB e nao
rem  altera o arquivo. E o primeiro teste da Fase 6 (ficha duplicada): antes
rem  de existir robo, confira se a IDENTIFICACAO esta certa.
rem
rem  Pode arrastar a planilha para cima deste arquivo, ou dar dois cliques e
rem  informar o caminho.
rem ===========================================================================
setlocal
title SIG-FT -- fichas duplicadas

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"

set "PLANILHA=%~1"
if "%PLANILHA%"=="" (
    echo Informe o caminho do arquivo _STATUS_PMIB.xlsx
    echo (ou arraste a planilha para cima deste .bat)
    echo.
    set /p PLANILHA="Caminho: "
)

"%SIGFT_PY%" "%~dp0scripts\listar_duplicadas.py" "%PLANILHA%"
echo.
pause
endlocal
exit /b 0

:erro
echo.
echo [SIG-FT] Encerrado com erro. As mensagens acima dizem o motivo.
echo.
pause
endlocal
exit /b 1

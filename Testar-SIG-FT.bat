@echo off
rem ===========================================================================
rem  SIG-FT -- roda a suite de testes automatizados.
rem
rem  Use este arquivo para conferir, no SEU computador, se a instalacao esta
rem  sa e se nada quebrou. Ele nao abre o aplicativo nem toca no portal PMIB:
rem  os testes rodam offline, sem navegador, sem chamar IA e sem abrir Excel.
rem
rem  Compartilha o mesmo ambiente virtual do SIG-FT.bat e instala, alem das
rem  dependencias normais, as de teste (requirements-dev.txt).
rem ===========================================================================
setlocal
title SIG-FT - testes

set "SIGFT_DEV=1"
call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"

echo.
echo [SIG-FT] Rodando os testes...
echo.
"%SIGFT_PY%" -m pytest -q
if errorlevel 1 goto :falhou

echo.
echo [SIG-FT] Tudo passou.
echo.
pause
endlocal
exit /b 0

:falhou
echo.
echo [SIG-FT] Alguns testes falharam. A lista acima mostra quais -- copie a
echo          saida inteira ao relatar o problema.
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

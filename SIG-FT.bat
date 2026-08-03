@echo off
rem ===========================================================================
rem  SIG-FT -- clique duas vezes neste arquivo para abrir o aplicativo.
rem
rem  Na PRIMEIRA vez ele cria o ambiente virtual e instala as dependencias
rem  (leva alguns minutos). Nas vezes seguintes ele so abre o aplicativo.
rem
rem  Nao precisa instalar nada antes, so o Python 3 (3.10 ou mais novo):
rem  https://www.python.org/downloads/  -- marque "Add python.exe to PATH".
rem
rem  Rede corporativa com Zscaler: veja o README.md, secao
rem  "Rede corporativa (Zscaler)".
rem ===========================================================================
setlocal
title SIG-FT

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

rem Roda a partir da raiz do projeto: .env, api_config.json, assets\ e as
rem planilhas de trabalho sao resolvidos por caminho relativo.
cd /d "%~dp0"

echo [SIG-FT] Abrindo o aplicativo. Pode fechar esta janela preta so DEPOIS
echo          de fechar o SIG-FT -- e nela que aparecem os erros.
echo.
"%SIGFT_PY%" "%~dp0frontend.py"
if errorlevel 1 goto :erro

endlocal
exit /b 0

:erro
echo.
echo [SIG-FT] Encerrado com erro. As mensagens acima dizem o motivo.
echo.
pause
endlocal
exit /b 1

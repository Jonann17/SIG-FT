@echo off
rem ===========================================================================
rem  SIG-FT -- confere se o motor Playwright funciona NESTA maquina.
rem
rem  Abre um navegador e exercita as mesmas operacoes que os modulos usam no
rem  portal (digitar, ler de volta, teclar, clicar, rolar, print de tela) --
rem  mas contra um site publico, NAO contra o PMIB.
rem
rem  Serve para separar duas perguntas: "o Playwright funciona aqui?" (esta,
rem  responde em qualquer computador) e "o portal responde bem a ele?" (so na
rem  maquina da empresa, com voce acompanhando).
rem
rem  Requer o navegador baixado uma vez: Instalar-Playwright.bat
rem ===========================================================================
setlocal
title SIG-FT - smoke do Playwright

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"
"%SIGFT_PY%" scripts\smoke_playwright.py
if errorlevel 1 goto :falhou

echo.
pause
endlocal
exit /b 0

:falhou
echo.
echo [SIG-FT] O smoke nao passou. A saida acima diz em qual passo.
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

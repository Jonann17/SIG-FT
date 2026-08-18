@echo off
rem ===========================================================================
rem  SIG-FT -- captura o HTML de uma tela do portal PMIB.
rem
rem  Para que serve: mapear uma tela nova custa hoje abrir o "inspecionar
rem  elemento" e copiar caixa por caixa, a mao. Isto abre o navegador com o
rem  SEU login ja valendo (perfil persistente), voce navega ate a tela, volta
rem  aqui e tecla ENTER -- e o HTML sai na janela preta, pronto para colar.
rem
rem  E SOMENTE-LEITURA: nao clica, nao digita, nao salva nada no portal.
rem  Pode rodar numa ficha real sem medo.
rem
rem  Requer o navegador baixado uma vez: Instalar-Playwright.bat
rem ===========================================================================
setlocal
title SIG-FT - capturar tela do portal

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

set "ALVO=%~1"
if "%ALVO%"=="" set "ALVO=//fieldset"

echo.
echo [SIG-FT] Vou abrir o navegador. Navegue ate a tela que quer capturar.
echo [SIG-FT] XPath a capturar: %ALVO%
echo.
echo [SIG-FT] Para capturar outra coisa, rode assim:
echo [SIG-FT]    Capturar-Tela-do-Portal.bat "//table"
echo.

"%SIGFT_PY%" "%~dp0scripts\auditar_seletores.py" --capturar "%ALVO%" --max 5
if errorlevel 1 goto :falhou

echo.
echo [SIG-FT] Pronto. Selecione o texto acima (botao direito ^> Marcar), copie
echo [SIG-FT] com ENTER e cole para o Claude.
echo.
pause
endlocal
exit /b 0

:falhou
echo.
echo [SIG-FT] A captura nao terminou. A saida acima diz por que.
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

@echo off
rem ===========================================================================
rem  SIG-FT no motor NOVO (Playwright) -- clique duas vezes neste arquivo.
rem
rem  E o mesmo aplicativo do SIG-FT.bat; a unica diferenca e que a automacao
rem  do portal roda em Playwright em vez de Selenium.
rem
rem  POR QUE ESTE ARQUIVO EXISTE, em vez de "e so definir uma variavel":
rem  a instrucao `set SIGFT_RPA_ENGINE=playwright` so funciona no Prompt de
rem  Comando (cmd). No PowerShell -- que e o terminal que o Windows abre por
rem  padrao hoje -- `set` e outro comando (Set-Variable) e NAO define variavel
rem  de ambiente: o app abria no motor ANTIGO sem nenhum aviso, e o teste do
rem  motor novo media a coisa errada. Um arquivo para clicar nao tem como
rem  errar isso.
rem
rem  Antes de usar, rode uma vez o Instalar-Playwright.bat (baixa o navegador).
rem
rem  Para voltar ao motor antigo: feche e use o SIG-FT.bat normal. A variavel
rem  vale so para esta janela, nao fica gravada em lugar nenhum.
rem ===========================================================================
setlocal
title SIG-FT (Playwright)

set "SIGFT_RPA_ENGINE=playwright"

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"

echo [SIG-FT] Motor de automacao: PLAYWRIGHT (SIGFT_RPA_ENGINE=%SIGFT_RPA_ENGINE%)
echo          O login do PMIB fica guardado no perfil do navegador, entao a
echo          partir da segunda vez nao e preciso logar de novo.
echo.
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
echo Se a falha foi ao abrir o navegador, rode o Instalar-Playwright.bat e,
echo em seguida, o Smoke-Playwright.bat para conferir o motor sem o portal.
echo.
pause
endlocal
exit /b 1

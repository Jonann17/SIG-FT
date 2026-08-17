@echo off
rem ===========================================================================
rem  SIG-FT no motor ANTIGO (Selenium) -- SO USE SE O NORMAL DER PROBLEMA.
rem
rem  O atalho do dia a dia e o SIG-FT.bat. Este aqui existe para UMA coisa:
rem  se a automacao do portal comecar a se comportar mal depois da troca para
rem  o Playwright, voltar ao motor que rodou em producao por meses -- sem
rem  editar codigo, sem reverter commit, sem esperar ninguem.
rem
rem  Ele substituiu o antigo SIG-FT-Playwright.bat, que nao fazia diferenca
rem  nenhuma: desde 2026-08-11 o Playwright JA E O PADRAO dos modulos portados
rem  (ver `RPA_ENGINE` em sigft/config.py), entao aquele atalho abria
rem  exatamente o mesmo aplicativo que o SIG-FT.bat -- e dava a impressao de
rem  ser uma escolha quando nao era.
rem
rem  Qual motor esta valendo aparece impresso nesta janela preta ao abrir o
rem  aplicativo, nos dois atalhos.
rem
rem  A variavel vale so para esta janela: fechou, acabou. Para voltar ao
rem  normal, use o SIG-FT.bat.
rem ===========================================================================
setlocal
title SIG-FT (motor antigo - Selenium)

set "SIGFT_RPA_ENGINE=selenium"

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"

echo [SIG-FT] ATENCAO: rodando no motor ANTIGO (Selenium), a pedido deste
echo          atalho. Se voce nao esta investigando um problema do motor novo,
echo          feche e use o SIG-FT.bat.
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
pause
endlocal
exit /b 1

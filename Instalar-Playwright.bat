@echo off
rem ===========================================================================
rem  SIG-FT -- baixa o navegador do Playwright (motor novo de RPA).
rem
rem  SO E PRECISO RODAR ISTO PARA TESTAR O MOTOR NOVO. O aplicativo funciona
rem  sem ele o RPA nao roda: o Playwright e o unico motor desde o CP 5.5.
rem
rem  Depois de instalar, para rodar um modulo no motor novo:
rem      set SIGFT_RPA_ENGINE=playwright
rem      SIG-FT.bat
rem  Para voltar ao motor antigo, feche a janela ou:
rem
rem ===========================================================================
setlocal
title SIG-FT - navegador do Playwright

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"

echo.
echo [SIG-FT] Baixando o navegador Chromium do Playwright (~150 MB)...
echo.

rem Rede corporativa com inspecao SSL: o download nao passa pelo pip, e sim
rem pelo processo Node do Playwright, que ignora as variaveis do Python. Quem
rem manda nele e NODE_EXTRA_CA_CERTS. Se o usuario ja apontou o certificado da
rem empresa em SSL_CERT_FILE (ver README), reaproveitamos aqui.
if not defined NODE_EXTRA_CA_CERTS if defined SSL_CERT_FILE (
    set "NODE_EXTRA_CA_CERTS=%SSL_CERT_FILE%"
    echo [SIG-FT] Usando o certificado de SSL_CERT_FILE para o download.
    echo.
)

"%SIGFT_PY%" -m playwright install chromium
if errorlevel 1 goto :falhou

echo.
echo [SIG-FT] Navegador instalado.
echo.
pause
endlocal
exit /b 0

:falhou
echo.
echo [ERRO] Falha ao baixar o navegador.
echo.
echo        Em rede corporativa com Zscaler, o download costuma quebrar com
echo        "unable to get local issuer certificate" ou "self signed
echo        certificate in certificate chain". Duas saidas:
echo.
echo        1^) aponte o certificado raiz da empresa para o Node:
echo              setx NODE_EXTRA_CA_CERTS C:\certs\zscaler-root.pem
echo           feche e reabra o terminal, e rode este arquivo de novo.
echo.
echo        2^) se a TI mantiver um espelho interno, aponte o Playwright
echo           para ele:
echo              setx PLAYWRIGHT_DOWNLOAD_HOST https://espelho.empresa/playwright
echo.
echo        Detalhes no README.md, secao "Rede corporativa ^(Zscaler^)".
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

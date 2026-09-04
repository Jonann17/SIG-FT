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

rem --- 1b. As chaves de API viajam junto ------------------------------------
rem
rem  Decisao do usuario (2026-09-04): "quero que todos quem usa tenha acesso
rem  as mesmas chaves". Entao o api_config.json entra no pacote, ao lado do
rem  .exe -- que e onde o app o procura (o caminho e resolvido a partir do
rem  diretorio de trabalho, e o launcher agora o fixa com "start /d").
rem
rem  ATENCAO, e leia esta parte antes de copiar o ZIP para qualquer lugar:
rem  a partir daqui o SIG-FT.zip CONTEM SEGREDO EM TEXTO CLARO. Quem abrir o
rem  zip le as chaves. A permissao da pasta do Box passa a ser, sozinha, o
rem  controle de acesso as chaves -- e elas ficam tambem em texto claro no
rem  %LOCALAPPDATA% de cada maquina que rodar o app.
rem
rem  Consequencia pratica: se alguem sair do time, ou o zip vazar, a unica
rem  saida e ROTACIONAR as chaves no provedor. Vale manter todas num lugar
rem  onde isso seja rapido.
rem
rem  O .env NAO e o canal: dentro do executavel ele seria lido de dentro do
rem  bundle (resource_path), nao daqui. O api_config.json e o mecanismo
rem  unico -- e e o que a propria tela de chaves do app grava.
echo.
echo  ============================================================
echo   [1b/3] Chaves de API
echo  ============================================================
echo.
if exist "api_config.json" (
    copy /y "api_config.json" "dist\SIG-FT\api_config.json" >nul
    echo   api_config.json incluido no pacote.
    echo.
    echo   [!] O SIG-FT.zip passa a conter as chaves EM TEXTO CLARO.
    echo       Quem tiver acesso a pasta do Box tem acesso as chaves.
    echo       Se vazar, rotacione as chaves no provedor.
) else (
    echo   ***********************************************************
    echo   *  ATENCAO: o pacote vai sair SEM AS CHAVES DE API.       *
    echo   ***********************************************************
    echo.
    echo   Nao existe api_config.json nesta pasta.
    echo.
    echo   E o caso TIPICO de quem acabou de baixar o ZIP do GitHub: o
    echo   api_config.json e ignorado pelo git DE PROPOSITO, para chave
    echo   nunca subir para o repositorio. Ele nao vem no download.
    echo.
    echo   SE VOCE QUER QUE TODOS COMPARTILHEM AS MESMAS CHAVES:
    echo     1. feche esta janela;
    echo     2. copie o seu api_config.json para esta pasta;
    echo     3. rode o Gerar-Pacote.bat de novo.
    echo.
    echo   Se seguir assim mesmo, cada usuario tera que preencher as
    echo   chaves na tela "Chaves de API" da Home, na propria maquina.
    echo.
    pause
)
echo.

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
echo   PROXIMO PASSO: copie DOIS arquivos para a pasta do Box
echo.
echo      %%USERPROFILE%%\Box\CMI - Consorcio Itaipu\
echo         11 - Ger. Engenharia\15 - PDM\_python_pdm\
echo.
echo      1. SIG-FT.zip           (o aplicativo)
echo      2. SIG-FT Itaipu.bat    (o que o usuario clica)
echo.
echo   O .bat so precisa ser copiado UMA vez. Nas atualizacoes seguintes
echo   basta trocar o SIG-FT.zip -- o .bat percebe sozinho.
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

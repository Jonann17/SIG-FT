@echo off
rem ===========================================================================
rem  SIG-FT -- gera planilhas de teste, para experimentar o app sem ter dados
rem  reais em maos (ex.: no computador de casa).
rem
rem  Cria a pasta  dados_de_teste\  com:
rem     4500063671.0001_STATUS_PMIB.xlsx   (e o .0002)
rem     fichas\4500063671.0001.xlsx        (e o .0002)
rem     LMR_aplicacoes.xlsx
rem
rem  Com isso da para abrir o app e rodar de ponta a ponta os modulos que so
rem  mexem em Excel: Buscar Material, PDM, Analyzer, AutoSpec, Gestao PMIB.
rem
rem  ATENCAO: sao dados INVENTADOS, montados a partir do que o CODIGO espera.
rem  Servem para ver o fluxo das telas funcionando -- NAO provam que o layout
rem  bate com a ficha real da Itaipu. Os modulos de RPA continuam precisando
rem  do portal PMIB.
rem ===========================================================================
setlocal
title SIG-FT - gerar dados de teste

call "%~dp0scripts\_bootstrap_venv.bat"
if errorlevel 1 goto :erro

cd /d "%~dp0"
"%SIGFT_PY%" scripts\gerar_dados_de_teste.py
if errorlevel 1 goto :erro

echo.
pause
endlocal
exit /b 0

:erro
echo.
echo [SIG-FT] Nao consegui gerar os dados. Leia as mensagens acima.
echo.
pause
endlocal
exit /b 1
